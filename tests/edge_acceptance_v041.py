'''Runs only public fixtures and our extension in an isolated Chromium profile.'''
import json,time,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/v041';EXT=ROOT/'work/v041/test-extension'
HTML='''<!doctype html><meta charset="utf-8"><title>映澈扩展验收</title><style>body{margin:0;padding:24px;background:#101b18;color:#c8ded2;font:16px "Microsoft YaHei"}h1{font-size:20px;font-weight:500;margin:0 0 18px}main{width:960px}video{display:block;width:960px;height:540px;background:#000}p{color:#93afa0;font-size:13px}</style><h1>映澈 · 网页播放器验收</h1><main id="player"><video controls muted preload="auto" src="/sample.mp4"></video></main><p>公开技术测试素材 · 当前页面由本地测试服务器提供</p>'''
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
  context=p.chromium.launch_persistent_context(str(OUT/('chromium-regression-'+str(time.time_ns()))),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=True,viewport={'width':1280,'height':780},args=['--enable-unsafe-extension-debugging',f'--disable-extensions-except={EXT}',f'--load-extension={EXT}'])
  errors=[];context.on('weberror',lambda e:errors.append(str(e.error)))
  worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker',timeout=30000)
  extension_id=worker.url.split('/')[2];assert extension_id=='apamfckhomfpifcdadlphjjpbllfnpba',extension_id
  worker.evaluate('()=>chrome.storage.local.clear()')
  record('Production manifest loaded; expected stable extension ID')
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
  s=wait_status(lambda s:s.get('faces')==1 and s.get('active'));record('Production scripts inject and detect a face on paused video');assert s.get('version')=='0.4.1' and s.get('engineReady') and 'GPUPixel 1.3.0' in s.get('engine','') and 'WASM' in s.get('engine',''),s;record('Actual compiled GPUPixel WASM runtime is ready: '+s['engine'])
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
  # Verify GPUPixel changes the replacement face, not only the original background.
  popup.evaluate('async(tabId)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;for(const k in c.beauty)c.beauty[k]=0;c.beauty.white=120;c.enabled=true;return chrome.runtime.sendMessage({type:"set-config",tabId,config:c});}',tab_id)
  wait_status(lambda s:s.get('swapFaces')==1 and not s.get('swapPending'));popup.wait_for_timeout(300)
  page.locator('video').screenshot(path=str(OUT/'edge-swap-beauty.png'))
  enhanced=np.asarray(Image.open(OUT/'edge-swap-beauty.png').convert('RGB')).astype(float)
  mask=diff.max(2)>15;face_beauty_delta=float(np.abs(enhanced-b)[mask].mean());assert face_beauty_delta>2,face_beauty_delta
  record('GPUPixel whitening applies after face swap: face ROI delta '+str(round(face_beauty_delta,2)))
  popup.evaluate('async(tabId)=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;c.enabled=false;return chrome.runtime.sendMessage({type:"set-config",tabId,config:c});}',tab_id)
  wait_status(lambda s:s.get('swapFaces')==1 and not s.get('swapPending'))
  page.evaluate('document.querySelector("video").currentTime=25');wait_status(lambda s:s.get('faces')==0 and s.get('swapFaces')==0);record('Seek to empty scene clears browser face swap')
  page.evaluate('document.querySelector("video").currentTime=5');wait_status(lambda s:s.get('swapFaces')==1)
  popup.locator('#swapStrength').fill('0');popup.locator('#swapStrength').dispatch_event('change');popup.wait_for_timeout(600)
  page.locator('video').screenshot(path=str(OUT/'edge-strength-zero.png'))
  c=np.asarray(Image.open(OUT/'edge-strength-zero.png').convert('RGB')).astype(float);assert np.abs(c-a).mean()<1, float(np.abs(c-a).mean());record('Swap strength zero restores original video pixels')
  popup.locator('#enabled').check();popup.locator('[data-preset="strong"]').click();popup.wait_for_timeout(600)
  page.locator('video').screenshot(path=str(OUT/'edge-beauty.png'));d=np.asarray(Image.open(OUT/'edge-beauty.png').convert('RGB')).astype(float);assert (np.abs(d-a).max(2)>15).sum()>100;record('Beauty sliders affect browser composite independently of face-swap strength')
  page.evaluate('document.querySelector("video").playbackRate=2;document.querySelector("video").play()');before=page.evaluate('document.querySelector("video").currentTime');popup.wait_for_timeout(1500);after=page.evaluate('document.querySelector("video").currentTime');assert after>before+2;page.evaluate('document.querySelector("video").pause()');record('Underlying playback and 2x speed continue during processing')
  popup.locator('#clearSource').click();expect(popup.locator('#message')).to_contain_text('源照片已清除');wait_status(lambda s:s.get('swapFaces')==0);record('Clear source removes face identity from bridge')
  popup.locator('#stop').click();wait_status(lambda s:not s.get('active'));assert page.locator('#yingche-video-layer').count()==0 and page.locator('#yingche-panel').count()==0;assert page.locator('#player').evaluate('(e)=>e.style.position')=='';record('Stop removes overlay and restores original page layout')
  page.goto('http://127.0.0.1:18767/cross');page.wait_for_function('document.querySelector("video").readyState>=2');popup.locator('#enable').click();s=wait_status(lambda s:s.get('needsCapture'));assert s.get('error');record('Cross-origin video reports capture requirement, with original video retained')
  page.screenshot(path=str(OUT/'edge-cross-origin.png'));popup.locator('#stop').click()
  assert not errors,errors
  (OUT/'edge-acceptance.json').write_text(json.dumps({'browser':context.browser.version,'productionManifest':True,'extensionId':extension_id,'checks':results,'errors':errors,'changedPixels':changed,'faceBeautyDelta':face_beauty_delta,'alphaBlendError':alpha_error,'swapAnalysisMs':swap_ms,'note':'Isolated Chromium test, localhost fixture. Edge user-profile installation and real sites not tested.'},ensure_ascii=False,indent=2),encoding='utf-8')
  context.close()
finally:
 for server in servers:server.shutdown();server.server_close()
