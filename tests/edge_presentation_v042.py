'''Presentation-only acceptance. The moving-face stress test and its initial failures remain in edge_playback_v042.py and playback-after.json.'''
import json,time,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/v042';EXT=ROOT/'work/v042/test-extension'
HTML='''<!doctype html><meta charset="utf-8"><title>映澈扩展验收</title><style>body{margin:0;padding:24px;background:#101b18;color:#c8ded2;font:16px "Microsoft YaHei"}h1{font-size:20px;font-weight:500;margin:0 0 18px}main{width:1600px}video{display:block;width:1600px;height:900px;background:#000}p{color:#93afa0;font-size:13px}</style><h1>映澈 · 网页播放器验收</h1><main id="player"><video controls muted preload="auto" src="/sample.mp4"></video></main><p>公开技术测试素材 · 当前页面由本地测试服务器提供</p>'''
class Fixture(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  if self.path.startswith('/sample.mp4'):
   path=ROOT/'work/portrait-motion.mp4';total=path.stat().st_size;start=0;end=total-1;status=200
   if self.headers.get('Range'):
    first,last=self.headers['Range'].removeprefix('bytes=').split('-',1);start=int(first);end=int(last) if last else end;status=206
   self.send_response(status);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
   if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
   self.end_headers()
   try:
    with path.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
   except (BrokenPipeError,ConnectionResetError):pass
  elif self.path=='/' or self.path.startswith('/cross'):
   html=HTML.replace('src="/sample.mp4"','src="http://localhost:18768/sample.mp4"') if self.path.startswith('/cross') else HTML
   data=html.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  else:self.send_response(404);self.end_headers()
servers=[]
for port in [18767,18768]:
 server=ThreadingHTTPServer(('127.0.0.1',port),Fixture);servers.append(server);threading.Thread(target=server.serve_forever,daemon=True).start()
results=[]
def record(text):results.append(text);print(text,flush=True)
try:
 with sync_playwright() as p:
  context=p.chromium.launch_persistent_context(str(OUT/('chromium-playback-'+str(time.time_ns()))),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,viewport={'width':1660,'height':1020},ignore_default_args=['--disable-backgrounding-occluded-windows'],args=['--window-size=1700,1080','--enable-unsafe-extension-debugging',f'--disable-extensions-except={EXT}',f'--load-extension={EXT}'])
  errors=[];context.on('weberror',lambda e:errors.append(str(e.error)))
  worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker',timeout=30000)
  extension_id=worker.url.split('/')[2];assert extension_id=='apamfckhomfpifcdadlphjjpbllfnpba',extension_id
  worker.evaluate('()=>chrome.storage.local.clear()')
  record('Production manifest loaded; expected stable extension ID'); print('BRIDGE_TARGET',worker.evaluate('async()=>({base:BASE,version:(await call("/session",{})).version})'),flush=True); assert worker.evaluate('BASE')=='http://127.0.0.1:29766'
  page=context.new_page();page.goto('http://127.0.0.1:18767/');page.wait_for_timeout(1000);print('VIDEO_STATE',page.evaluate('()=>{const v=document.querySelector("video");return {src:v.currentSrc,ready:v.readyState,network:v.networkState,error:v.error?.message,codec:v.canPlayType("video/webm; codecs=vp9")}}'),flush=True);page.wait_for_function('document.querySelector("video").readyState>=2')
  page.evaluate('document.querySelector("video").currentTime=5');page.wait_for_timeout(1000);print('SEEK_STATE',page.evaluate('()=>{const v=document.querySelector("video");return {time:v.currentTime,seeking:v.seeking,ready:v.readyState,error:v.error?.message,paused:v.paused,duration:v.duration}}'),flush=True);page.wait_for_function('!document.querySelector("video").seeking',polling=100)
  cdp=context.browser.new_browser_cdp_session()
  targets=cdp.send('Target.getTargets',{'filter':[{'type':'tab','exclude':False}]})['targetInfos']
  target=next(t for t in targets if t['url']=='http://127.0.0.1:18767/')
  cdp.send('Extensions.triggerAction',{'id':extension_id,'targetId':target['targetId']})
  page.wait_for_timeout(200)
  record('Browser toolbar action grants activeTab, without extra site permissions')
  tab_id=worker.evaluate('async()=> (await chrome.tabs.query({})).find(t=>t.url==="http://127.0.0.1:18767/").id')
  popup=context.new_page();popup.goto(f'chrome-extension://{extension_id}/popup.html?tab={tab_id}');popup.wait_for_selector('#range-smooth',state='attached')
  popup.locator('#connect').click();expect(popup.locator('#message')).to_contain_text('已连接',timeout=30000);record('Popup connects to packaged local FaceEngine')
  popup.locator('#enabled').uncheck();popup.wait_for_timeout(200)
  popup.locator('#enable').click();page.bring_to_front();popup.wait_for_timeout(2500)
  msg=popup.locator('#message').inner_text();print('ENABLE',msg,flush=True)
  assert '已启用' in msg,msg
  def status():return popup.evaluate('(tabId)=>chrome.runtime.sendMessage({type:"status",tabId})',tab_id)
  def wait_status(test,seconds=20):
   until=time.monotonic()+seconds
   while time.monotonic()<until:
    s=status()
    if test(s):return s
    popup.wait_for_timeout(100)
   raise AssertionError(status())
  s=wait_status(lambda s:s.get('faces')==1 and s.get('active'));record('Production scripts inject and detect a face on paused video');assert s.get('version')=='0.4.2' and s.get('engineReady') and 'GPUPixel 1.3.0' in s.get('engine','') and 'WASM' in s.get('engine',''),s;record('Actual compiled GPUPixel WASM runtime is ready: '+s['engine'])
  # A known translucent colour must not be multiplied by alpha twice in ImageBitmap upload.
  import base64,io
  from PIL import Image
  blob=io.BytesIO();Image.new('RGBA',(8,8),(200,100,50,128)).save(blob,format='PNG');alpha_png=base64.b64encode(blob.getvalue()).decode()
  alpha_result=worker.evaluate('''async({tabId,png})=>{const r=await chrome.scripting.executeScript({target:{tabId},args:[png],func:async(png)=>{
   const c=document.createElement('canvas');c.width=64;c.height=64;const r=new YingcheRenderer(c);await r.ready;
   try{const v=document.querySelector('video');const cfg={enabled:false,swapEnabled:false,swapStrength:100,beauty:{}};
    const pixel=()=>{const p=new Uint8Array(4);r.gl.readPixels(10,10,1,1,r.gl.RGBA,r.gl.UNSIGNED_BYTE,p);return [...p];};
    r.render(v,cfg,v.currentTime,1,true);const original=pixel();
    await r.analysis({id:999,pts:v.currentTime,sampleTime:performance.now(),faces:[],swap:png});cfg.swapEnabled=true;r.render(v,cfg,v.currentTime,1,true);
    return {original,composite:pixel()};
   }finally{r.dispose();}
  }});return r[0].result;}''',{'tabId':tab_id,'png':alpha_png})
  expected=[v*127/255+t*128/255 for v,t in zip(alpha_result['original'][:3],[200,100,50])]
  alpha_error=max(abs(x-y) for x,y in zip(expected,alpha_result['composite'][:3]));assert alpha_error<2,alpha_result
  record('Straight alpha swap edge pixel check passes: error '+str(round(alpha_error,3)))
  page.locator('video').screenshot(path=str(OUT/'edge-original.png'))
  popup.locator('#sourceFile').set_input_files(str(ROOT/'work/v02/swap-source.jpg'))
  expect(popup.locator('#message')).to_contain_text('源照片已就绪',timeout=70000)
  s=wait_status(lambda s:s.get('swapFaces')==1);swap_ms=s.get('analysisMs');record('Source upload and actual GPU face swap succeed: '+str(swap_ms)+' ms')
  page.screenshot(path=str(OUT/'edge-swapped-page.png'));page.locator('video').screenshot(path=str(OUT/'edge-swapped.png'));popup.screenshot(path=str(OUT/'edge-popup.png'),full_page=True)
  import numpy as np
  from PIL import Image
  a=np.asarray(Image.open(OUT/'edge-original.png').convert('RGB')).astype(float);b=np.asarray(Image.open(OUT/'edge-swapped.png').convert('RGB')).astype(float);diff=np.abs(a-b);changed=int((diff.max(2)>15).sum());assert changed>500,changed
  record(f'Composited video pixels change after face swap: {changed} pixels above 15/255')
  worker.evaluate('''async(tabId)=>chrome.scripting.executeScript({target:{tabId},func:()=>{
   const rawPresent=YingchePresentation.prototype.present;YingchePresentation.prototype.present=function(){globalThis.__presentation=this;return rawPresent.call(this);};
   const raw=YingcheRenderer.prototype.render;globalThis.__rawRender=raw;
   globalThis.__probe={frames:0,geometryFrames:0,swapFrames:0,weightSum:0};
   YingcheRenderer.prototype.render=function(...args){const ok=raw.apply(this,args);if(ok){globalThis.__liveRenderer=this;globalThis.__liveArgs=args;
    if(!args[4]){const p=globalThis.__probe;const w=this.gl.getUniform(this.program,this.loc('trackingWeight'));const faces=this.gl.getUniform(this.program,this.loc('faceCount'));const swap=this.gl.getUniform(this.program,this.loc('swapEnabled'));p.frames++;p.geometryFrames+=w>.95&&faces>0;p.swapFrames+=!!swap;p.weightSum+=w;}}return ok;};
   globalThis.__pixelProbe=()=>{const r=globalThis.__liveRenderer,args=globalThis.__liveArgs.slice();args[2]=document.querySelector('video').currentTime;
    const face=r.data?.faces[0];if(!face)return {error:'No rendered face'};
    const g=r.gl,cw=r.canvas.width,ch=r.canvas.height,cx=(face[2][0]+face[3][0])/2*cw,cy=(1-(face[2][1]+face[3][1])/2)*ch;
    const size=Math.max(30,Math.hypot((face[2][0]-face[3][0])*cw,(face[2][1]-face[3][1])*ch)*1.6);
    const x=Math.max(0,Math.floor(cx-size/2)),y=Math.max(0,Math.floor(cy-size*.65)),w=Math.min(cw-x,Math.ceil(size)),h=Math.min(ch-y,Math.ceil(size*1.3));
    const read=(cfg)=>{const a=args.slice();a[1]=cfg;globalThis.__rawRender.apply(r,a);const p=new Uint8Array(w*h*4);g.readPixels(x,y,w,h,g.RGBA,g.UNSIGNED_BYTE,p);return p;};
    const cfg=args[1],actual=read(cfg),original=read({...cfg,enabled:false,swapEnabled:false}),geometry=read({...cfg,swapEnabled:false}),swap=read({...cfg,enabled:false});
    const delta=(pixels)=>{let sum=0,changed=0;for(let i=0;i<pixels.length;i+=4){let m=0;for(let j=0;j<3;j++){const d=Math.abs(pixels[i+j]-original[i+j]);sum+=d;m=Math.max(m,d);}changed+=m>10;}return {mean:sum/(w*h*3),changed};};
    globalThis.__rawRender.apply(r,args);return {actual:delta(actual),geometry:delta(geometry),swap:delta(swap),weight:r.status.trackingWeight};
   };
  }})''',tab_id)
  def inspect(expression):
   return worker.evaluate('async({tabId,expression})=>(await chrome.scripting.executeScript({target:{tabId},func:expression==="reset"?()=>globalThis.__probe={frames:0,geometryFrames:0,swapFrames:0,weightSum:0}:expression==="pixels"?()=>globalThis.__pixelProbe():()=>globalThis.__probe}))[0].result',{'tabId':tab_id,'expression':expression})
  popup.evaluate('async(tabId)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;for(const k in c.beauty)c.beauty[k]=0;c.beauty.slim=150;c.beauty.eyes=100;c.enabled=true;c.swapEnabled=true;c.swapStrength=100;return chrome.runtime.sendMessage({type:"set-config",tabId,config:c});}',tab_id)
  phases=[]
  for speed,seconds in []:
   page.evaluate('document.querySelector("video").pause();document.querySelector("video").currentTime=2')
   popup.evaluate('async(tabId)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;for(const k in c.beauty)c.beauty[k]=0;c.beauty.slim=150;c.beauty.eyes=100;c.enabled=true;c.swapEnabled=true;c.swapStrength=100;return chrome.runtime.sendMessage({type:"set-config",tabId,config:c});}',tab_id)
   page.bring_to_front();wait_status(lambda s:s.get('shownSwapFaces',0)>=1 and s.get('trackingWeight',0)>.95)
   page.evaluate('(speed)=>{const v=document.querySelector("video");v.playbackRate=speed;v.play();}',speed);page.wait_for_timeout(1300)
   inspect('reset');samples=[];pixels=[];start=time.monotonic();before=page.evaluate('document.querySelector("video").currentTime');last=-1
   while time.monotonic()-start<seconds:
    page.wait_for_timeout(150);samples.append(status())
    tick=int(time.monotonic()-start)
    if tick!=last:last=tick;pixels.append(inspect('pixels'))
   report={'speed':speed,'seconds':time.monotonic()-start,'startPTS':before,'endPTS':page.evaluate('document.querySelector("video").currentTime'),'render':inspect('stats'),'samples':samples,'pixels':pixels}
   phases.append(report);page.screenshot(path=str(OUT/('playing-'+str(speed)+'x.png')))
   summary={'speed':speed,**report['render'],'medianRoundTripMs':float(np.median([x['roundTripMs'] for x in samples])),'medianFrameBytes':float(np.median([x['frameBytes'] for x in samples])),'geometryPixelChecks':sum(x.get('geometry',{}).get('changed',0)>40 for x in pixels),'swapPixelChecks':sum(x.get('swap',{}).get('changed',0)>100 for x in pixels),'pixelChecks':len(pixels)}
   print('PLAYBACK_PHASE',json.dumps(summary),flush=True)
   (OUT/'presentation-acceptance.json').write_text(json.dumps({'phases':phases},ensure_ascii=False,indent=2),encoding='utf-8')
   r=report['render'];assert r['frames']>seconds*25,r
   assert r['geometryFrames']/r['frames']>.95,r
   assert r['swapFrames']/r['frames']>.95,r
   assert summary['geometryPixelChecks']==len(pixels),pixels
   assert summary['swapPixelChecks']==len(pixels),pixels
  hidden=context.new_page();hidden.goto('about:blank');hidden.bring_to_front();hidden.wait_for_timeout(2200);page.bring_to_front()
  page.evaluate('document.querySelector("video").currentTime=3');wait_status(lambda s:s.get('shownSwapFaces',0)>0 and s.get('trackingWeight',0)>.95)
  recovery=inspect('pixels');assert recovery['geometry']['changed']>40 and recovery['swap']['changed']>100,recovery
  record('Foreground resume reacquires current pose and preserves both effects');hidden.close()
  page.evaluate('document.querySelector("video").pause();document.querySelector("video").currentTime=25');wait_status(lambda s:s.get('faces')==0 and s.get('shownSwapFaces')==0 and s.get('shownFaces')==0)
  record('Seek to blank clears actual rendered geometry and swap')
  page.evaluate('document.querySelector("video").pause();document.querySelector("video").currentTime=5');page.bring_to_front()
  wait_status(lambda s:s.get('shownSwapFaces',0)>0 and s.get('presentation')=='video');page.wait_for_timeout(600)
  presentation_pixels=worker.evaluate('''async(tabId)=>(await chrome.scripting.executeScript({target:{tabId},func:()=>{
   const p=globalThis.__presentation;const c=document.createElement('canvas');c.width=320;c.height=180;const x=c.getContext('2d',{willReadFrequently:true});
   const read=image=>{x.drawImage(image,0,0,320,180);return x.getImageData(0,0,320,180).data;};
   const output=read(p.element),rendered=read(p.canvas),original=read(document.querySelector('video'));let delta=0,changed=0;
   for(let i=0;i<output.length;i+=4){let d=0;for(let j=0;j<3;j++){delta+=Math.abs(output[i+j]-rendered[i+j]);d=Math.max(d,Math.abs(output[i+j]-original[i+j]));}changed+=d>10;}
   return {meanOutputError:delta/(320*180*3),changedPixels:changed,muted:p.element.muted,audioTracks:p.stream.getAudioTracks().length,width:p.element.videoWidth,height:p.element.videoHeight};
  }}))[0].result''',tab_id)
  assert presentation_pixels['meanOutputError']<3,presentation_pixels
  assert presentation_pixels['changedPixels']>100 and presentation_pixels['muted'] and presentation_pixels['audioTracks']==0,presentation_pixels
  print('VISIBLE_VIDEO_PIXELS',json.dumps(presentation_pixels),flush=True)
  output_motion=[]
  for speed in [1,2]:
   page.evaluate('(speed)=>{const v=document.querySelector("video");v.currentTime=3;v.playbackRate=speed;v.play();}',speed);page.bring_to_front();page.wait_for_timeout(500)
   before=page.evaluate('document.querySelector("video").currentTime');state_before=status();page.wait_for_timeout(2000);state_after=status();after=page.evaluate('document.querySelector("video").currentTime')
   assert after-before>speed*1.7,(speed,before,after)
   output_motion.append({'speed':speed,'mediaAdvance':after-before,'outputFrames':state_after['outputFrames']-state_before['outputFrames']})
   assert output_motion[-1]['outputFrames']>=80,output_motion[-1]
   print('VIDEO_OUTPUT_MOTION',json.dumps(output_motion[-1]),flush=True)
  trace_events=[];trace_done=[];cdp.on('Tracing.dataCollected',lambda e:trace_events.extend(e['value']));cdp.on('Tracing.tracingComplete',lambda e:trace_done.append(True))
  page.evaluate('document.querySelector("video").style.visibility="hidden";document.querySelector("video").playbackRate=1;document.querySelector("video").play()');page.wait_for_timeout(500)
  cdp.send('Tracing.start',{'categories':'gpu,media,viz','transferMode':'ReportEvents'});page.wait_for_timeout(3000);cdp.send('Tracing.end')
  until=time.monotonic()+15
  while not trace_done and time.monotonic()<until:page.wait_for_timeout(100)
  toggles=[e for e in trace_events if e.get('name')=='ToggleNvidiaVpSuperResolution' and e.get('args',{}).get('on') is True]
  assert len(toggles)>60,len(toggles)
  (OUT/'vsr-trace.json').write_text(json.dumps([e for e in trace_events if 'SuperResolution' in e.get('name','') or 'VideoProcessor' in e.get('name','')]),encoding='utf-8')
  record('Processed video with original hidden invokes NVIDIA VSR: '+str(len(toggles))+' calls in 3 seconds; driver activation is not claimed')
  page.evaluate('document.querySelector("video").pause();document.querySelector("video").style.visibility=""')
  worker.evaluate('async(tabId)=>chrome.scripting.executeScript({target:{tabId},func:()=>globalThis.__oldTrack=globalThis.__presentation.track})',tab_id)
  popup.locator('#vsrCompatible').uncheck();page.bring_to_front();wait_status(lambda s:s.get('presentation')=='canvas')
  track_state=worker.evaluate('async(tabId)=>(await chrome.scripting.executeScript({target:{tabId},func:()=>globalThis.__oldTrack.readyState}))[0].result',tab_id);assert track_state=='ended',track_state
  popup.locator('#vsrCompatible').check();page.bring_to_front();wait_status(lambda s:s.get('presentation')=='video' and s.get('outputFrames',0)>10)
  page.screenshot(path=str(OUT/'vsr-compatible.png'));popup.screenshot(path=str(OUT/'vsr-popup.png'),full_page=True)
  record('VSR mode switches live and releases the previous video capture track')
  (OUT/'vsr-output.json').write_text(json.dumps({'pixels':presentation_pixels,'motion':output_motion,'nvidiaVpCalls':len(toggles),'sourceHiddenDuringTrace':True,'driverActivationVerified':False},ensure_ascii=False,indent=2),encoding='utf-8')
  popup.locator('#clearSource').click();expect(popup.locator('#message')).to_contain_text('源照片已清除')
  popup.locator('#stop').click();wait_status(lambda s:not s.get('active'));assert page.locator('#yingche-video-layer').count()==0
  assert not errors,errors
  result={'version':'0.4.2','browser':context.browser.version,'phases':phases,'recovery':recovery,'checks':results,'errors':errors,'passed':True}
  (OUT/'presentation-acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('PRESENTATION_ACCEPTANCE_OK',flush=True)
  context.close()
finally:
 for server in servers:server.shutdown();server.server_close()
