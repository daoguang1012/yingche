"""Popup connection pill against the real bridge_server.py; no models, user profile or user port.

The face processor is a stub, so this checks only the loopback session path the background service
provides: offline hint, automatic reconnect once the service starts, manual check and preset marking.
"""
import argparse,json,shutil,subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
STUB='''import base64
def decode_image(value):return base64.b64decode(value['png'])
class FaceProcessor:
    source_ready=False
    def __init__(self,model):pass
    def process(self,req):return {'id':req.get('id',0),'generation':req.get('generation',0),'faces':[],'ms':0.0}
    def set_source(self,image):return {'provider':'stub','sourceFaces':1}
    def close(self):pass
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chrome',type=Path,default=ROOT/'tools/chromium153-test/chrome.exe')
    parser.add_argument('--port',type=int,default=29967)
    args=parser.parse_args()
    out=ROOT/'work/v060'/('popup-service-'+str(time.time_ns()));out.mkdir(parents=True)
    ext=out/'extension';shutil.copytree(ROOT/'edge-extension',ext)
    # Only the loopback port changes, so a running user bridge is never contacted.
    background=(ext/'background.js').read_text(encoding='utf-8');assert "127.0.0.1:18766'" in background
    (ext/'background.js').write_text(background.replace("127.0.0.1:18766'",f"127.0.0.1:{args.port}'"),encoding='utf-8')
    manifest=json.loads((ext/'manifest.json').read_text(encoding='utf-8'));manifest['host_permissions']=[f'http://127.0.0.1:{args.port}/*']
    (ext/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    config=json.loads((ext/'bridge-config.json').read_text(encoding='utf-8'));config['port']=args.port
    (out/'bridge-config.json').write_text(json.dumps(config),encoding='utf-8')
    (out/'stub').mkdir();(out/'stub/face_worker.py').write_text(STUB,encoding='utf-8')
    launch=f"import sys;sys.path[:0]=[{str(out/'stub')!r},{str(ROOT/'tools')!r}];from bridge_server import run;run('none',{str(out/'bridge-config.json')!r})"
    result={'passed':False};bridge=None
    with sync_playwright() as p:
        context=p.chromium.launch_persistent_context(str(out/'profile'),executable_path=str(args.chrome),headless=False,args=[f'--disable-extensions-except={ext}',f'--load-extension={ext}'])
        try:
            worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            ident=worker.url.split('/')[2];assert ident==config['extensionId'],ident
            page=context.new_page();page.goto(f'chrome-extension://{ident}/popup.html')
            expect(page.locator('#connect')).to_have_attribute('data-state','offline',timeout=10000)
            expect(page.locator('#message')).to_contain_text('后台服务');result['offlineHint']=True
            bridge=subprocess.Popen([sys.executable,'-u','-c',launch],stdout=subprocess.PIPE,text=True)
            assert json.loads(bridge.stdout.readline())['bridgeReady']
            expect(page.locator('#connect')).to_have_attribute('data-state','online',timeout=10000)
            expect(page.locator('#message')).to_contain_text('已连接');result['autoReconnect']=True
            page.locator('#connect').click();expect(page.locator('#message')).to_contain_text('已连接');result['manualCheck']=True
            page.locator('[data-preset="strong"]').click();expect(page.locator('[data-preset="strong"]')).to_have_class('active')
            page.locator('.fine summary').click();page.locator('#range-smooth').fill('20');expect(page.locator('[data-preset="strong"]')).not_to_have_class('active');result['presetMarking']=True
            bridge.terminate();bridge.wait(5);bridge=None
            expect(page.locator('#connect')).to_have_attribute('data-state','offline',timeout=10000);result['detectsStop']=True
            page.screenshot(path=str(out/'popup.png'),full_page=True);result['passed']=True
        finally:
            if bridge:bridge.terminate()
            context.close()
    (out/'popup-service.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
