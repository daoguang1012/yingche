"""Real browser/bridge acceptance for neural interpolation and existing effects."""
import json, time, threading, functools
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/v050';EXT=OUT/'test-extension'
HTML='''<!doctype html><meta charset="utf-8"><title>映澈 0.5 补帧验收</title><style>body{margin:0;padding:20px;background:#101b18;color:#d6e7dc;font:16px "Microsoft YaHei"}h1{font-size:20px}main{width:1600px}video{display:block;width:1600px;height:900px;background:#000}</style><h1>映澈 · AI 补帧与 VSR 实播验证</h1><main><video controls muted loop src="/work/portrait-motion.mp4"></video></main>'''
(OUT/'playback.html').write_text(HTML,encoding='utf-8')
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  paths={'/work/portrait-motion.mp4':ROOT/'work/portrait-motion.mp4','/work/v050/portrait-1080p24.mp4':OUT/'portrait-1080p24.mp4','/work/v050/portrait-720p60.mp4':OUT/'portrait-720p60.mp4'}
  if self.path not in paths:return super().do_GET()
  path=paths[self.path];total=path.stat().st_size;start=0;end=total-1;status=200
  if self.headers.get('Range'):
   first,last=self.headers['Range'].removeprefix('bytes=').split('-',1);start=int(first);end=int(last) if last else end;status=206
  self.send_response(status);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
  if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
  self.end_headers()
  try:
   with path.open('rb') as f:f.seek(start);self.wfile.write(f.read(end-start+1))
  except (BrokenPipeError,ConnectionResetError):pass
server=ThreadingHTTPServer(('127.0.0.1',18769),functools.partial(Quiet,directory=str(ROOT)))
threading.Thread(target=server.serve_forever,daemon=True).start()
checks=[];phases=[];errors=[]
def record(text):checks.append(text);print(text,flush=True)
try:
 with sync_playwright() as p:
  context=p.chromium.launch_persistent_context(str(OUT/('acceptance-profile-'+str(time.time_ns()))),executable_path=str(ROOT/'tools/chromium153-test/chrome.exe'),headless=False,viewport={'width':1660,'height':1030},ignore_default_args=['--disable-backgrounding-occluded-windows'],args=['--window-size=1700,1110','--enable-unsafe-extension-debugging',f'--disable-extensions-except={EXT}',f'--load-extension={EXT}'])
  context.on('weberror',lambda e:errors.append(str(e.error)))
  worker=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
  extension_id=worker.url.split('/')[2];assert extension_id=='apamfckhomfpifcdadlphjjpbllfnpba'
  worker.evaluate('()=>chrome.storage.local.clear()')
  page=context.new_page();url='http://127.0.0.1:18769/work/v050/playback.html';page.goto(url);page.wait_for_function('document.querySelector("video").readyState>=2')
  cdp=context.browser.new_browser_cdp_session();targets=cdp.send('Target.getTargets',{'filter':[{'type':'tab','exclude':False}]})['targetInfos']
  target=next(t for t in targets if t['url']==url);cdp.send('Extensions.triggerAction',{'id':extension_id,'targetId':target['targetId']})
  tab_id=worker.evaluate('(url)=>chrome.tabs.query({}).then(ts=>ts.find(t=>t.url===url).id)',url)
  popup=context.new_page();popup.goto(f'chrome-extension://{extension_id}/popup.html?tab={tab_id}');popup.wait_for_selector('#range-smooth',state='attached')
  popup.locator('#enable').click();expect(popup.locator('#message')).to_contain_text('已启用',timeout=30000)
  def status():return popup.evaluate('(tabId)=>chrome.runtime.sendMessage({type:"status",tabId})',tab_id)
  def inspect(code):return worker.evaluate('async(tabId)=>{const r=(await chrome.scripting.executeScript({target:{tabId},func:()=>('+code+')}))[0];if(r.error)throw Error(r.error.message);return r.result;}',tab_id)
  def config(**settings):return popup.evaluate('async({tabId,settings})=>{const c=(await chrome.runtime.sendMessage({type:"config"})).config;return chrome.runtime.sendMessage({type:"set-config",tabId,config:{...c,...settings}})}',{'tabId':tab_id,'settings':settings})
  inspect('''(()=>{
   const draw=YingcheInterpolation.prototype.draw;globalThis.__timing=[];YingcheInterpolation.prototype.draw=function(...args){globalThis.__fi=this;const r=draw.apply(this,args);if(globalThis.__timing.length<360)globalThis.__timing.push({now:args[0],delay:this.delayMs,frames:this.frames.map(f=>({due:f.due,still:f.still,cut:f.cut})),generated:r?.generated,hold:r?.hold});return r;};
   const present=YingchePresentation.prototype.present;YingchePresentation.prototype.present=function(...args){globalThis.__presentation=this;return present.apply(this,args);};
  })()''')
  page.bring_to_front();page.evaluate('document.querySelector("video").play()');page.wait_for_timeout(2500)
  def phase(name,seconds=5):
   samples=[];start=time.monotonic()
   while time.monotonic()-start<seconds:page.wait_for_timeout(250);samples.append(status())
   r={'name':name,'samples':samples};phases.append(r)
   (OUT/'interpolation-acceptance.json').write_text(json.dumps({'checks':checks,'phases':phases,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
   summary={k:round(sum(x.get(k,0) for x in samples)/len(samples),2) for k in ['inputFps','outputFps','interpolatedFps','interpolationMs','interpolationDelayMs','shownFaces','shownSwapFaces']}
   summary.update(state=samples[-1].get('interpolationState'),reason=samples[-1].get('interpolationReason'),video=page.evaluate('(()=>{const v=document.querySelector("video");return {rate:v.playbackRate,time:v.currentTime,paused:v.paused,quality:v.getVideoPlaybackQuality()};})()'));print(name,json.dumps(summary,ensure_ascii=False),flush=True);return summary
  # This fixture contains held frames around 4-5 seconds. Anchors and static pairs
  # must not inflate the generated-frame counter; the pixel check below measures motion.
  base=phase('30fps_beauty_vsr');(OUT/'timing-debug.json').write_text(json.dumps(inspect('globalThis.__timing')),encoding='utf-8');assert base['state']=='active',base;assert base['outputFps']>=52,base;assert base['interpolatedFps']>=12,base
  record('30 FPS video reaches >=52 presented FPS with neural frames, GPUPixel and VSR output')
  # Count pixel changes in the ACTUAL captured output video, independent of submission counters.
  inspect('''(()=>{const v=globalThis.__presentation.element,c=new OffscreenCanvas(64,36),x=c.getContext('2d',{willReadFrequently:true});
   globalThis.__pixels={frames:0,changed:0,energy:0};let last=null;const until=performance.now()+2200;
   const sample=()=>{x.drawImage(v,0,0,64,36);const d=x.getImageData(0,0,64,36).data;const s=globalThis.__pixels;s.frames++;let delta=0;
    for(let i=0;i<d.length;i+=4){s.energy+=d[i]+d[i+1]+d[i+2];if(last)delta+=Math.abs(d[i]-last[i])+Math.abs(d[i+1]-last[i+1])+Math.abs(d[i+2]-last[i+2]);}
    s.changed+=delta>500;last=d;if(performance.now()<until)v.requestVideoFrameCallback(sample);};v.requestVideoFrameCallback(sample);})()''')
  page.wait_for_timeout(2400);pixels=inspect('globalThis.__pixels');print('ACTUAL_OUTPUT_PIXELS',pixels,flush=True);assert pixels['frames']>=100 and pixels['changed']>=85 and pixels['energy']>100000,pixels
  page.screenshot(path=str(OUT/'interpolation-playing.png'));popup.screenshot(path=str(OUT/'interpolation-popup.png'),full_page=True)
  popup.locator('#sourceFile').set_input_files(str(ROOT/'work/v02/swap-source.jpg'));expect(popup.locator('#message')).to_contain_text('源照片已就绪',timeout=70000);page.bring_to_front()
  page.evaluate('document.querySelector("video").currentTime=3');page.wait_for_timeout(1800)
  combined=phase('30fps_beauty_swap_vsr');assert combined['state']=='active' and combined['interpolatedFps']>15 and combined['shownSwapFaces']>.6,combined
  record('Neural interpolation also works with actual photo face swap and GPUPixel')
  page.evaluate('document.querySelector("video").playbackRate=2');page.wait_for_timeout(1800);fast=phase('2x_bypass',2)
  assert fast['video']['rate']==2 and fast['outputFps']>=50,fast;record('2x playback remains smooth; interpolation follows observed decoded-frame cadence')
  page.evaluate('document.querySelector("video").pause();document.querySelector("video").playbackRate=1;document.querySelector("video").currentTime=25');page.wait_for_timeout(1400)
  blank=status();assert blank['shownFaces']==0 and blank['shownSwapFaces']==0,blank
  before=blank['generatedFrames'];page.wait_for_timeout(1000);assert status()['generatedFrames']==before
  record('Seek clears previous faces and interpolation anchors; paused playback generates no frames')
  page.evaluate('document.querySelector("video").currentTime=4;document.querySelector("video").play()');page.wait_for_timeout(1400)
  config(vsrCompatible=False);page.bring_to_front();page.wait_for_timeout(1300);plain=phase('canvas_output',2);assert plain['state']=='active',plain
  config(vsrCompatible=True);page.bring_to_front();page.wait_for_timeout(1300)
  page.evaluate('document.querySelector("video").style.visibility="hidden"')
  trace=[];done=[];cdp.on('Tracing.dataCollected',lambda e:trace.extend(e['value']));cdp.on('Tracing.tracingComplete',lambda e:done.append(True))
  cdp.send('Tracing.start',{'categories':'gpu,media,viz','transferMode':'ReportEvents'});page.wait_for_timeout(2500);cdp.send('Tracing.end')
  until=time.monotonic()+15
  while not done and time.monotonic()<until:page.wait_for_timeout(100)
  toggles=[e for e in trace if e.get('name')=='ToggleNvidiaVpSuperResolution' and e.get('args',{}).get('on') is True]
  assert len(toggles)>50,len(toggles);record(f'Interpolated output invokes NVIDIA VSR path ({len(toggles)} calls / 2.5 s); driver activation not claimed')
  page.evaluate('document.querySelector("video").style.visibility=""')
  # Deterministic scene-cut, device-loss and slow-GPU branches on the actual session.
  cut=inspect('''(()=>{const f=globalThis.__fi;f.reset();const c=document.createElement('canvas');c.width=f.canvas.width;c.height=f.canvas.height;const x=c.getContext('2d');const now=performance.now();
   x.fillStyle='black';x.fillRect(0,0,c.width,c.height);f.capture(c,now,{expectedDisplayTime:now});x.fillStyle='white';x.fillRect(0,0,c.width,c.height);f.capture(c,now+33,{expectedDisplayTime:now+33});
   return {cut:f.frames[1].cut,before:f.counts.generated,result:f.draw(now+33+8+16.5)?.generated,after:f.counts.generated};})()''')
  assert cut['cut'] and cut['before']==cut['after'] and not cut['result'],cut;record('Large scene change skips neural mixing across the cut')
  inspect('globalThis.__fi.fail("test device loss")');page.wait_for_timeout(900);fallback=status();assert fallback['active'] and fallback['interpolationState']=='error' and not fallback['error'],fallback
  assert page.locator('#yingche-video-layer').evaluate('(e)=>e.style.visibility')=='visible';record('GPU failure falls back to existing enhanced playback')
  config(interpolation=False);page.wait_for_timeout(250);config(interpolation=True);page.wait_for_timeout(1500);recovered=status();assert recovered['interpolationState']=='active',recovered
  config(swapEnabled=False)
  page.evaluate('(()=>{const v=document.querySelector("video");v.src="/work/v050/portrait-1080p24.mp4";v.load();v.play();})()');page.wait_for_timeout(2000)
  full=phase('1080p24_beauty_vsr',4);assert full['state']=='active' and 22<full['inputFps']<26 and full['outputFps']>=52,full
  resolution=status();assert resolution['outputWidth']==1920 and resolution['outputHeight']==1080,resolution
  record('Actual 1080p / 24 FPS clip keeps full resolution and reaches >=52 presented FPS')
  page.evaluate('(()=>{const v=document.querySelector("video");v.src="/work/v050/portrait-720p60.mp4";v.load();v.play();})()');page.wait_for_timeout(1800)
  high=phase('60fps_input',2)
  # Chromium may deliver only 30 decoded callbacks/s for a covered source video.
  if high['inputFps']>55:assert high['state']=='bypass',high
  else:assert high['state']=='active' and high['outputFps']>=52,high
  config(interpolation=False);page.wait_for_timeout(200)
  inspect('Object.defineProperty(navigator,"gpu",{configurable:true,value:undefined})');config(interpolation=True);page.wait_for_timeout(800)
  unavailable=status();assert unavailable['interpolationState']=='error' and unavailable['active'],unavailable
  record('Missing WebGPU automatically falls back without interrupting the source video')
  inspect('delete navigator.gpu');config(interpolation=False);page.wait_for_timeout(200);config(interpolation=True);page.wait_for_timeout(1300)
  old=inspect('(()=>{globalThis.__oldFi=globalThis.__fi;globalThis.__oldTrack=globalThis.__presentation.track;return true;})()')
  popup.locator('#stop').click();page.wait_for_timeout(500);assert not status()['active'];assert page.locator('#yingche-video-layer').count()==0
  released=inspect('({device:!!globalThis.__oldFi.device,disposed:globalThis.__oldFi.disposed,track:globalThis.__oldTrack.readyState})');assert released=={'device':False,'disposed':True,'track':'ended'},released
  record('Stopping releases GPU device, textures, video frame callbacks and captured video track')
  assert not errors,errors
  (OUT/'interpolation-acceptance.json').write_text(json.dumps({'version':'0.5.0','passed':True,'browser':context.browser.version,'checks':checks,'phases':phases,'pixels':pixels,'nvidiaVpCalls':len(toggles),'driverActivationVerified':False,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
  print('INTERPOLATION_ACCEPTANCE_OK',flush=True);context.close()
finally:server.shutdown();server.server_close()
