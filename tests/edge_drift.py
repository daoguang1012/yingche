"""Browser effect drift on the generated motion clips (exact ground truth), synchronised display off vs on.

Isolated Chromium + extension copy + source bridge on a test port; the page video plays with sound.
Also verifies the Web Audio route: audible, follows the element's volume and mute, and is delayed.
Usage: python tests/edge_drift.py [fps ...]
"""
import json,shutil,socket,subprocess,sys,threading,time,statistics
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import numpy as np
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];PORT=29867;PAGE=18868
PHASES=['still','swing','reversal','zoom','tilt','shake','still2']
HTML='<!doctype html><meta charset="utf-8"><body style="margin:0;background:#000"><video loop preload="auto" style="width:1280px;height:720px" src="/clip.mp4"></video>'
fpss=[int(a) for a in sys.argv[1:] if a.isdigit()] or [30,60]
current={'path':None}

class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path.startswith('/clip.mp4'):
            path=current['path'];total=path.stat().st_size;start,end,status=0,total-1,200
            if self.headers.get('Range'):
                a,b=self.headers['Range'].removeprefix('bytes=').split('-',1);start=int(a);end=int(b) if b else end;status=206
            self.send_response(status);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
            if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
            self.end_headers()
            try:
                with path.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
            except (BrokenPipeError,ConnectionResetError):pass
        else:
            data=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

def main():
    out=ROOT/'work/drift'/('edge-'+str(time.time_ns()));out.mkdir(parents=True)
    ext=out/'extension';shutil.copytree(ROOT/'edge-extension',ext)
    for name in ['background.js','manifest.json','bridge-config.json']:
        p=ext/name;p.write_text(p.read_text(encoding='utf-8').replace('18766',str(PORT)),encoding='utf-8')
    log=open(out/'bridge.log','w',encoding='utf-8')
    bridge=subprocess.Popen([sys.executable,'-u',str(ROOT/'tools/face_worker.py'),'--bridge',str(ROOT/'models/face_landmarker.task'),str(ext/'bridge-config.json')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    server=ThreadingHTTPServer(('127.0.0.1',PAGE),Fixture);threading.Thread(target=server.serve_forever,daemon=True).start()
    report=[];runs=[];checks={}
    try:
        for _ in range(300):
            assert bridge.poll() is None,'bridge exited'
            try:
                with socket.create_connection(('127.0.0.1',PORT),timeout=.2):break
            except OSError:time.sleep(.1)
        with sync_playwright() as p:
            context=p.chromium.launch_persistent_context(str(out/'profile'),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,viewport={'width':1300,'height':760},
                ignore_default_args=['--disable-backgrounding-occluded-windows','--mute-audio'],args=['--window-size=1340,840','--autoplay-policy=no-user-gesture-required',f'--disable-extensions-except={ext}',f'--load-extension={ext}'])
            worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker',timeout=30000)
            ident=worker.url.split('/')[2];worker.evaluate('()=>chrome.storage.local.clear()')
            page=context.new_page();cdp=context.browser.new_browser_cdp_session()
            for fps in fpss:
                current['path']=ROOT/f'work/motion/motion-{fps}.mp4';truth=json.loads((ROOT/f'work/motion/motion-{fps}.json').read_text(encoding='utf-8'))
                page.goto(f'http://127.0.0.1:{PAGE}/?{fps}');page.wait_for_function('document.querySelector("video").readyState>=2')
                page.click('video')  # user activation, as on a real site
                target=next(t for t in cdp.send('Target.getTargets',{'filter':[{'type':'tab','exclude':False}]})['targetInfos'] if t['url'].startswith(f'http://127.0.0.1:{PAGE}/'))
                cdp.send('Extensions.triggerAction',{'id':ident,'targetId':target['targetId']});page.wait_for_timeout(200)
                tab=worker.evaluate(f'async()=>(await chrome.tabs.query({{}})).find(t=>t.url?.startsWith("http://127.0.0.1:{PAGE}/")).id')
                popup=context.new_page();popup.goto(f'chrome-extension://{ident}/popup.html?tab={tab}');popup.wait_for_selector('#range-smooth',state='attached')
                popup.evaluate('async(tab)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;c.enabled=true;c.beauty.slim=60;c.beauty.eyes=40;return chrome.runtime.sendMessage({type:"set-config",tabId:tab,config:c});}',tab)
                popup.locator('#enable').click();expect(popup.locator('#message')).to_contain_text('已启用',timeout=30000)
                status=lambda:popup.evaluate('(tabId)=>chrome.runtime.sendMessage({type:"status",tabId})',tab)
                for sync in [False,True]:
                    worker.evaluate('async([tabId,off])=>chrome.scripting.executeScript({target:{tabId},args:[off],func:off=>{globalThis.__yingcheSyncDisabled=off;}})',[tab,not sync])
                    page.bring_to_front();page.evaluate('()=>{const v=document.querySelector("video");v.pause();v.currentTime=0;}');page.wait_for_timeout(1200)
                    page.wait_for_function('document.visibilityState==="visible"&&document.hasFocus()',timeout=10000)
                    page.evaluate('document.querySelector("video").play()');page.wait_for_timeout(600)
                    samples=[];end=time.monotonic()+18.5
                    while time.monotonic()<end:
                        page.wait_for_timeout(90);samples.append(status())
                    runs.append({'fps':fps,'sync':sync,'samples':samples})
                    byphase={k:[] for k in PHASES};seg=truth['segments']
                    for s in samples:
                        if s.get('displayPts') is None or not s.get('drawnEyes') or (s.get('trackingWeight') or 0)<.5:continue
                        i=min(len(truth['eyes'])-1,round(s['displayPts']*fps));t=i/fps
                        phase=PHASES[min(len(PHASES)-1,max(k for k in range(len(seg)-1) if seg[k]<=t))]
                        true=np.array(truth['eyes'][i])*[1920,1080];drawn=np.array(s['drawnEyes'])*[1920,1080]
                        byphase[phase].append(float(np.linalg.norm(drawn-true,axis=1).mean()/np.linalg.norm(true[0]-true[1])*100))
                    allerr=[e for v in byphase.values() for e in v]
                    item={'fps':fps,'sync':sync,'n':len(allerr),'medianPct':round(statistics.median(allerr),1),'p90Pct':round(sorted(allerr)[int(len(allerr)*.9)],1),'maxPct':round(max(allerr),1),
                          'phaseMedianPct':{k:round(statistics.median(v),1) for k,v in byphase.items() if v},'syncActiveRatio':round(sum(1 for s in samples if s.get('syncActive'))/len(samples),2),
                          'syncDelayMs':samples[-1].get('syncDelayMs'),'audioDelayMs':samples[-1].get('audioDelayMs'),'audioRouted':samples[-1].get('audioRouted'),'outputFps':round(statistics.median(s.get('outputFps') or 0 for s in samples),1)}
                    report.append(item);print(json.dumps(item,ensure_ascii=False),flush=True)
                # Audio route: audible, follows element volume/mute.
                if fps==fpss[-1]:
                    checks=worker.evaluate('''async(tabId)=>(await chrome.scripting.executeScript({target:{tabId},func:async()=>{
                      const v=document.querySelector('video'),route=globalThis.__yingcheAudioRoutes?.get(v);if(!route)return {routed:false};
                      const a=route.context.createAnalyser();a.fftSize=2048;route.delay.connect(a);const buf=new Float32Array(2048);
                      const rms=async()=>{await new Promise(r=>setTimeout(r,500));let s=0;for(let k=0;k<10;k++){await new Promise(r=>setTimeout(r,60));a.getFloatTimeDomainData(buf);s+=Math.sqrt(buf.reduce((x,y)=>x+y*y,0)/buf.length);}return s/10;};
                      v.volume=1;v.muted=false;const full=await rms();v.volume=.2;const low=await rms();v.muted=true;const muted=await rms();v.muted=false;v.volume=1;
                      return {routed:true,state:route.context.state,delayMs:Math.round(route.delay.delayTime.value*1000),baseLatencyMs:Math.round(route.context.baseLatency*1000),outputLatencyMs:Math.round((route.context.outputLatency||0)*1000),rmsFull:full,rmsLow:low,rmsMuted:muted};
                    }}))[0].result''',tab)
                    print('AUDIO',json.dumps(checks),flush=True)
                page.screenshot(path=str(out/f'page-{fps}.png'));popup.close()
            context.close()
    finally:
        server.shutdown();bridge.terminate();bridge.wait(10);log.close()
    (out/'drift.json').write_text(json.dumps({'report':report,'audio':checks,'runs':runs},ensure_ascii=False,indent=1),encoding='utf-8');print(out)

if __name__=='__main__':main()
