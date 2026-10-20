"""Browser face-swap latency breakdown: isolated Chromium, production extension copy, bridge on a test port.

Usage: python tests/edge_swap_latency.py [--engine source|frozen] [--seconds 10] [--label NAME]
Prints per-stage medians/p95 from the extension's own status.
"""
import argparse,json,shutil,socket,subprocess,sys,threading,time,statistics
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
PORT=29866;PAGE=18867
HTML='<!doctype html><meta charset="utf-8"><body style="margin:0;background:#000"><video muted loop preload="auto" style="width:1280px;height:720px" src="/sample.mp4"></video>'

def fixture(video):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_GET(self):
            if self.path.startswith('/sample.mp4'):
                total=video.stat().st_size;start,end,status=0,total-1,200
                if self.headers.get('Range'):
                    a,b=self.headers['Range'].removeprefix('bytes=').split('-',1);start=int(a);end=int(b) if b else end;status=206
                self.send_response(status);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
                if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
                self.end_headers()
                try:
                    with video.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
                except (BrokenPipeError,ConnectionResetError):pass
            else:
                data=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',PAGE),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();return server

def stats(values):
    values=sorted(v for v in values if v is not None)
    if not values:return None
    return {'median':round(statistics.median(values),1),'p95':round(values[min(len(values)-1,int(len(values)*.95))],1),'n':len(values)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--engine',choices=['source','frozen','frozen061'],default='source');ap.add_argument('--seconds',type=float,default=10)
    ap.add_argument('--label',default='run');ap.add_argument('--video',type=Path,default=ROOT/'work/portrait-motion.mp4');ap.add_argument('--source',type=Path,default=ROOT/'work/v02/swap-source.jpg')
    ap.add_argument('--beauty',action='store_true',help='keep beauty enabled during the run')
    args=ap.parse_args()
    out=ROOT/'work/latency'/(args.label+'-'+str(time.time_ns()));out.mkdir(parents=True)
    ext=out/'extension';shutil.copytree(ROOT/'edge-extension',ext)
    for name in ['background.js','manifest.json','bridge-config.json']:
        p=ext/name;p.write_text(p.read_text(encoding='utf-8').replace('18766',str(PORT)),encoding='utf-8')
    if args.engine.startswith('frozen'):cmd=[str(ROOT/('app/face_engine_v061' if args.engine=='frozen061' else 'app/face_engine_v041')/'FaceEngine.exe'),'--bridge',str(ROOT/'models/face_landmarker.task'),str(ext/'bridge-config.json')]
    else:cmd=[sys.executable,'-u',str(ROOT/'tools/face_worker.py'),'--bridge',str(ROOT/'models/face_landmarker.task'),str(ext/'bridge-config.json')]
    log=open(out/'bridge.log','w',encoding='utf-8');bridge=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    server=fixture(args.video);report={'label':args.label,'engine':args.engine}
    try:
        for _ in range(300):
            assert bridge.poll() is None,'bridge exited, see '+str(out/'bridge.log')
            try:
                with socket.create_connection(('127.0.0.1',PORT),timeout=.2):break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            context=p.chromium.launch_persistent_context(str(out/'profile'),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,viewport={'width':1300,'height':760},
                ignore_default_args=['--disable-backgrounding-occluded-windows'],args=['--window-size=1340,840',f'--disable-extensions-except={ext}',f'--load-extension={ext}'])
            worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker',timeout=30000)
            ident=worker.url.split('/')[2];worker.evaluate('()=>chrome.storage.local.clear()')
            page=context.new_page();page.goto(f'http://127.0.0.1:{PAGE}/');page.wait_for_function('document.querySelector("video").readyState>=2')
            cdp=context.browser.new_browser_cdp_session();target=next(t for t in cdp.send('Target.getTargets',{'filter':[{'type':'tab','exclude':False}]})['targetInfos'] if t['url']==f'http://127.0.0.1:{PAGE}/')
            cdp.send('Extensions.triggerAction',{'id':ident,'targetId':target['targetId']});page.wait_for_timeout(200)
            tab=worker.evaluate(f'async()=>(await chrome.tabs.query({{}})).find(t=>t.url==="http://127.0.0.1:{PAGE}/").id')
            popup=context.new_page();popup.goto(f'chrome-extension://{ident}/popup.html?tab={tab}');popup.wait_for_selector('#range-smooth',state='attached')
            popup.locator('#enable').click();expect(popup.locator('#message')).to_contain_text('已启用',timeout=30000)
            popup.locator('#sourceFile').set_input_files(str(args.source));expect(popup.locator('#message')).to_contain_text('源照片已就绪',timeout=90000)
            popup.wait_for_timeout(400)  # the popup saves its own config 100 ms after a source upload
            popup.evaluate('async(tab)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;c.swapEnabled=true;c.swapStrength=100;c.enabled=%s;return chrome.runtime.sendMessage({type:"set-config",tabId:tab,config:c});}'%('true' if args.beauty else 'false'),tab)
            page.bring_to_front();page.evaluate('document.querySelector("video").play()');page.wait_for_timeout(2500)
            samples=[];start=time.monotonic()
            while time.monotonic()-start<args.seconds:
                page.wait_for_timeout(100)
                samples.append(popup.evaluate('(tabId)=>chrome.runtime.sendMessage({type:"status",tabId})',tab))
            page.screenshot(path=str(out/'page.png'))
            # Same paused frame, beauty off vs on (swap off), for visual review of the skin composite.
            page.evaluate('document.querySelector("video").pause()')
            for name,enabled in [('look-original',False),('look-beauty',True)]:
                popup.evaluate('async([tab,on])=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;c.swapEnabled=false;c.enabled=on;return chrome.runtime.sendMessage({type:"set-config",tabId:tab,config:c});}',[tab,enabled])
                page.bring_to_front();page.wait_for_timeout(1500);page.screenshot(path=str(out/(name+'.png')))
            keys=['roundTripMs','analysisMs','swapMs','swapAgeMs','encodeMs','frameBytes','trackingAgeMs']
            report.update({k:stats([s.get(k) for s in samples]) for k in keys})
            report['visibleSwapLagMs']=stats([s.get('roundTripMs',0)+s.get('swapAgeMs',0) for s in samples if s.get('swapFaces')])
            report['shownSwapRatio']=round(sum(1 for s in samples if s.get('shownSwapFaces'))/max(1,len(samples)),3)
            report['swapStates']={str(st):sum(1 for s in samples if s.get('swapState')==st) for st in {s.get('swapState') for s in samples}}
            report['analysesPerSecond']=round((samples[-1]['analysis']-samples[0]['analysis'])/args.seconds,2)
            report['outputFps']=stats([s.get('outputFps') for s in samples])
            context.close()
    finally:
        server.shutdown();bridge.terminate();bridge.wait(10);log.close()
    (out/'latency.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
