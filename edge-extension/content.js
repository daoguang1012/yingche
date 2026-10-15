// Presentation and controller are bundled so cached loaders cannot omit a new dependency.
(() => {
if(globalThis.YingchePresentation)return;
class YingchePresentation {
 constructor(canvas,root,onError){
  this.canvas=canvas;this.root=root;this.onError=onError;this.epoch=0;this.compatible=null;this.frames=0;this.shown=0;this.rate=0;this.rateAt=performance.now();this.rateCount=0;
 }
 setCompatible(compatible){
  compatible=!!compatible;if(this.compatible===compatible){if(this.error)throw Error(this.error);return;}
  this.release();this.compatible=compatible;this.frames=0;
  if(!compatible){this.element=this.canvas;this.root.replaceChildren(this.canvas);return;}
  try{
  if(!HTMLCanvasElement.prototype.captureStream)throw Error('当前浏览器不支持 VSR 兼容输出，请关闭兼容模式');
  // Capturing WebGL directly yields RGB frames that bypass Chromium's video processor.
  // An opaque 2D staging canvas takes the video-compatible capture path instead.
  this.staging=document.createElement('canvas');
  this.staging.width=this.canvas.width;this.staging.height=this.canvas.height;
  this.context=this.staging.getContext('2d',{alpha:false});
  if(!this.context)throw Error('无法创建 VSR 兼容画面');
  this.stream=this.staging.captureStream(0);this.track=this.stream.getVideoTracks()[0];
  if(!this.track?.requestFrame)throw Error('当前浏览器不支持逐帧视频输出，请关闭兼容模式');
  const video=document.createElement('video');
  video.muted=true;video.defaultMuted=true;video.playsInline=true;video.autoplay=true;
  video.disablePictureInPicture=true;video.setAttribute('aria-hidden','true');
  video.style.pointerEvents='none';video.srcObject=this.stream;this.element=video;
  this.root.replaceChildren(video);
  const epoch=this.epoch;
  const shown=()=>{if(this.epoch!==epoch)return;this.shown++;this.outputCallback=video.requestVideoFrameCallback(shown);};this.outputCallback=video.requestVideoFrameCallback(shown);
  video.play().catch(e=>{if(this.epoch===epoch){this.error='兼容视频输出失败：'+e.message;this.onError(this.error);}});
  }catch(e){this.release();this.error=e.message;throw e;}
 }
 present(source=this.canvas){
  if(this.error)throw Error(this.error);
  if(!this.compatible){if(this.element!==source){source.style.cssText=this.element?.style.cssText||this.canvas.style.cssText;this.root.replaceChildren(source);this.element=source;}this.frames++;this.shown++;return true;}
  const {width,height}=source;
  if(this.staging.width!==width||this.staging.height!==height){this.staging.width=width;this.staging.height=height;}
  this.context.drawImage(source,0,0);this.track.requestFrame();this.frames++;
  return this.element.readyState>=2;
 }
 get fps(){const now=performance.now(),seconds=(now-this.rateAt)/1000;if(seconds>=1){this.rate=(this.shown-this.rateCount)/seconds;this.rateCount=this.shown;this.rateAt=now;}return this.rate;}
 release(){
  this.epoch++;this.error='';
  this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.track=null;
  if(this.element instanceof HTMLVideoElement){this.element.cancelVideoFrameCallback(this.outputCallback);this.element.pause();this.element.srcObject=null;this.element.remove();}
  this.staging=null;this.context=null;this.element=null;
 }
 dispose(){this.release();this.compatible=null;}
}
globalThis.YingchePresentation=YingchePresentation;
})();

(() => {
if(globalThis.__yingcheController)return;
const send=async message=>{const result=await chrome.runtime.sendMessage(message);if(result?.error)throw Error(result.error);return result;};
const controller={version:'0.6.0',engine:'GPUPixel WASM',engineReady:false,active:false,generation:0,busy:false,frames:0,analysis:0,lastError:'',needsCapture:false,stream:null};
let video,input,host,canvas,panel,renderer,presentation,config,raf,observer,lastSubmit=0,lastPosition=-1,parentStyle,videoStyle,seekHandler,originalParent,visibilityHandler,playHandler,captureCanvas,captureContext,lastAnalysisFrame=-1,lastPaint=-1000;
function base64(bytes){let text='';for(let i=0;i<bytes.length;i+=16384)text+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(text);}
function status(text,error=false){controller.lastError=error?text:'';if(panel)panel.querySelector('.status').textContent=text;}
function invalidate(){controller.generation++;renderer?.clear();interpolation?.reset();lastSubmit=0;lastAnalysisFrame=-1;controller.swapPending=false;}
function geometry(){
 if(!host||!video)return;
 presentation.setCompatible(config.vsrCompatible);
 const r=video.getBoundingClientRect(),parent=host.parentElement,p=parent.getBoundingClientRect();
 const sx=parent.offsetWidth?p.width/parent.offsetWidth:1,sy=parent.offsetHeight?p.height/parent.offsetHeight:1;
 const width=r.width/sx,height=r.height/sy;Object.assign(host.style,{left:((r.left-p.left)/sx+parent.scrollLeft-parent.clientLeft)+'px',top:((r.top-p.top)/sy+parent.scrollTop-parent.clientTop)+'px',width:width+'px',height:height+'px'});
 const ratio=(input.videoWidth||video.videoWidth)/(input.videoHeight||video.videoHeight||1);
 let cw=width,ch=width/ratio;if(ch>height){ch=height;cw=height*ratio;}
 Object.assign(presentation.element.style,{position:'absolute',left:(width-cw)/2+'px',top:(height-ch)/2+'px',width:cw+'px',height:ch+'px'});
 const pixelRatio=Math.min(devicePixelRatio,2),scale=Math.min(1,2560/(cw*pixelRatio),1440/(ch*pixelRatio));
 const sourceScale=Math.min(1,2560/(input.videoWidth||2),1440/(input.videoHeight||2));
 const bw=Math.max(2,Math.round(config.vsrCompatible?(input.videoWidth||2)*sourceScale:cw*pixelRatio*scale)),bh=Math.max(2,Math.round(config.vsrCompatible?(input.videoHeight||2)*sourceScale:ch*pixelRatio*scale));
 if(canvas.width!==bw||canvas.height!==bh){canvas.width=bw;canvas.height=bh;}
 syncInterpolation();
}
async function compatibleCapture(){
 try{
  if(video.mediaKeys)throw Error('该视频使用受保护播放，无法增强');
  if(!globalThis.RestrictionTarget||!navigator.mediaDevices?.getDisplayMedia)throw Error('当前页面不支持元素捕获，请使用 HTTPS 页面和新版 Edge');
  status('请在浏览器提示中选择当前标签页');
  const stream=await navigator.mediaDevices.getDisplayMedia({video:true,audio:false,preferCurrentTab:true,selfBrowserSurface:'include'});
  controller.stream=stream;const track=stream.getVideoTracks()[0];
  if(!track.restrictTo)throw Error('此 Edge 版本不支持元素捕获');
  videoStyle={value:video.style.getPropertyValue('isolation'),priority:video.style.getPropertyPriority('isolation')};video.style.setProperty('isolation','isolate');
  const restriction=await RestrictionTarget.fromElement(video);await track.restrictTo(restriction);
  const capture=document.createElement('video');capture.muted=true;capture.playsInline=true;capture.srcObject=stream;await capture.play();
  input=capture;controller.needsCapture=false;invalidate();watchFrames();panel.querySelector('.capture').hidden=true;
  track.addEventListener('ended',()=>stop());status('兼容捕获已连接 · 原网页音频继续播放');
 }catch(e){controller.stream?.getTracks().forEach(t=>t.stop());controller.stream=null;status(e.message,true);}
}
function makePanel(){
 const shell=document.createElement('div');shell.id='yingche-panel';Object.assign(shell.style,{position:'fixed',right:'18px',top:'18px',zIndex:'2147483646'});
 const shadow=shell.attachShadow({mode:'closed'});shadow.innerHTML=`<style>:host{all:initial}*{box-sizing:border-box}section{width:280px;padding:12px;background:#10221eee;color:#daede2;font:13px "Microsoft YaHei",sans-serif;border:1px solid #608875;border-radius:10px;box-shadow:0 4px 24px #0006}header{display:flex;align-items:center;justify-content:space-between}button,input,select{font:inherit}button{background:#284d3e;color:#e5f4eb;border:1px solid #608875;border-radius:5px;padding:5px 8px;cursor:pointer}.status{font-size:11px;line-height:1.5;color:#adcbbb;margin:10px 0;overflow-wrap:anywhere}.row{display:flex;gap:7px;align-items:center}.timeline{width:100%;margin:10px 0}select{color:#dbe9e1;background:#173429;padding:4px}.capture{width:100%;margin-top:8px}button[hidden]{display:none}</style><section><header><strong>映澈 0.6.0 · GPUPixel</strong><button class="close" title="停止增强">关闭</button></header><div class="status">正在初始化 GPUPixel…</div><div class="row"><button class="play">播放/暂停</button><select class="speed" aria-label="倍速"><option value=".5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option><option value="2">2×</option><option value="3">3×</option><option value="4">4×</option></select><button class="full">网页全屏</button></div><input class="timeline" type="range" min="0" max="1000" step="1" value="0" aria-label="播放进度"><button class="capture" hidden>跨域兼容捕获</button></section>`;
 document.documentElement.append(shell);panel=shadow;
 shadow.querySelector('.close').onclick=()=>stop();shadow.querySelector('.play').onclick=()=>video.paused?video.play().catch(e=>status(e.message,true)):video.pause();shadow.querySelector('.speed').onchange=e=>{video.playbackRate=Number(e.target.value);};shadow.querySelector('.full').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await originalParent.requestFullscreen();}catch(e){status(e.message,true);}};
 shadow.querySelector('.timeline').oninput=e=>{if(Number.isFinite(video.duration))video.currentTime=video.duration*Number(e.target.value)/1000;};shadow.querySelector('.capture').onclick=compatibleCapture;
 return shell;
}
let interpolation,frameCallback,frameInput,panelHost;
function syncInterpolation(){
 if(config.interpolation&&!interpolation)interpolation=new YingcheInterpolation();
 if(!config.interpolation&&interpolation){interpolation.dispose();interpolation=null;}
 interpolation?.ensure(canvas.width,canvas.height);
}
function watchFrames(){
 if(frameInput&&frameCallback!==undefined)frameInput.cancelVideoFrameCallback(frameCallback);
 frameInput=input;
 const next=(now,metadata)=>{
  if(!controller.active||frameInput!==input)return;
  if(interpolation?.runtime&&!video.paused&&!video.seeking&&!controller.needsCapture&&controller.engineReady){
   try{if(renderer.render(input,config,video.currentTime,video.playbackRate,false))interpolation.capture(canvas,now,metadata);}
   catch(e){interpolation.fail(e.message);}
  }
  frameCallback=input.requestVideoFrameCallback(next);
 };
 frameCallback=input.requestVideoFrameCallback(next);
}
function loop(now){
 if(!controller.active)return;
 if(!video.isConnected){stop();return;}
 try{geometry();}catch(e){host.style.visibility='hidden';status(e.message,true);raf=requestAnimationFrame(loop);return;}
 if(Number.isFinite(video.duration)&&video.duration>0)panel.querySelector('.timeline').value=String(video.currentTime/video.duration*1000);
 if(!controller.needsCapture&&input.readyState>=2){
  try{if(now-lastPaint>=1000/60-1){
   lastPaint=now;let frame=null;
   if(interpolation&&!video.paused&&!video.seeking){try{frame=interpolation.draw(now);}catch(e){interpolation.fail(e.message);}}
   if(!frame?.hold){const source=frame?.source||(interpolation?.state==='bypass'&&!video.paused?canvas:null);
    if((source||renderer.render(input,config,video.currentTime,video.playbackRate,video.paused))&&presentation.present(source||canvas))host.style.visibility='visible';}
   controller.frames=renderer.frames;
  }}
  catch(e){if(e.name==='SecurityError'||/origin|cross/i.test(e.message)){controller.needsCapture=true;host.style.visibility='hidden';panel.querySelector('.capture').hidden=false;status('此视频禁止直接取帧，请点击跨域兼容捕获并选择当前标签页',true);}else {host.style.visibility='hidden';status(e.message,true);}}
  const frameId=input.getVideoPlaybackQuality?.().totalVideoFrames||input.currentTime;
  if(!controller.needsCapture&&!controller.busy&&now-lastSubmit>=8&&!video.seeking&&((!video.paused&&frameId!==lastAnalysisFrame)||lastPosition!==video.currentTime||controller.swapPending)){
   controller.busy=true;lastSubmit=now;lastPosition=video.currentTime;lastAnalysisFrame=frameId;const epoch=controller.generation;
   analyze(epoch).finally(()=>{controller.busy=false;});
  }
 }
 raf=requestAnimationFrame(loop);
}
async function analyze(epoch){
 try{
  const w=input.videoWidth,h=input.videoHeight;const scale=Math.min(960/w,720/h,1),cw=Math.max(2,Math.round(w*scale)),ch=Math.max(2,Math.round(h*scale));
  if(!captureCanvas||captureCanvas.width!==cw||captureCanvas.height!==ch){captureCanvas=new OffscreenCanvas(cw,ch);captureContext=captureCanvas.getContext('2d',{alpha:false});}
  const pts=video.currentTime,sampleTime=performance.now(),paused=video.paused,settings=config;
  captureContext.drawImage(input,0,0,cw,ch);
  // A compressed frame avoids cloning multi-megabyte RGBA strings through MV3 messaging.
  const blob=await captureCanvas.convertToBlob({type:'image/jpeg',quality:.94});
  const bytes=new Uint8Array(await blob.arrayBuffer());
  if(!controller.active||epoch!==controller.generation)return;
  controller.frameBytes=bytes.byteLength;controller.encodeMs=performance.now()-sampleTime;
  const result=await send({type:'analyze',payload:{id:++controller.analysis,generation:epoch,pts,sampleTime,width:cw,height:ch,jpeg:base64(bytes),paused,swapEnabled:settings.swapEnabled,swapTarget:settings.swapTarget,swapFeather:settings.swapFeather}});
  if(!controller.active||epoch!==controller.generation)return;
  const activeRenderer=renderer;await activeRenderer.analysis(result);
  if(!controller.active||epoch!==controller.generation){if(renderer===activeRenderer)activeRenderer.clear();return;}
  controller.lastFaces=result.faces.length;controller.swapFaces=result.swapFaces||0;controller.analysisMs=result.ms;controller.swapMs=result.swapMs||0;controller.swapState=result.swapState||'';controller.swapAgeMs=result.swapAgeMs||0;controller.swapReused=!!result.swapReused;controller.swapPending=!!result.swapPending;controller.swapError=result.swapError||'';controller.roundTripMs=performance.now()-result.sampleTime;status(`GPUPixel · ${result.faces.length} 张脸 · ${result.ms.toFixed(0)} ms${config.swapEnabled?' · 换脸 '+(result.swapFaces||0)+' 张'+(result.swapPending?' · 生成中':''):''}`);
 }catch(e){if(!controller.active||epoch!==controller.generation)return;lastPosition=-1;renderer?.clear();host.style.visibility='hidden';if(e.name==='SecurityError'){controller.needsCapture=true;panel.querySelector('.capture').hidden=false;status('视频跨域保护，请使用兼容捕获',true);}else status(e.message,true);}
}
async function start(newConfig){
 stop();const candidates=[...document.querySelectorAll('video')].filter(v=>{const r=v.getBoundingClientRect();return v.videoWidth&&r.width>80&&r.height>60;}).sort((a,b)=>{const x=a.getBoundingClientRect(),y=b.getBoundingClientRect();return y.width*y.height-x.width*x.height;});
 video=candidates[0];if(!video)throw Error('没有找到已加载的视频，请先点网页播放器播放');if(video.mediaKeys)throw Error('受保护的视频暂不支持增强');
 config=newConfig;input=video;originalParent=video.parentElement;parentStyle={value:originalParent.style.getPropertyValue('position'),priority:originalParent.style.getPropertyPriority('position')};if(getComputedStyle(originalParent).position==='static')originalParent.style.setProperty('position','relative');
 host=document.createElement('div');host.id='yingche-video-layer';Object.assign(host.style,{position:'absolute',pointerEvents:'none',zIndex:String((Number.parseInt(getComputedStyle(video).zIndex)||0)+1),overflow:'hidden',visibility:'hidden'});
 const shadow=host.attachShadow({mode:'closed'});canvas=document.createElement('canvas');shadow.append(canvas);video.after(host);renderer=new YingcheRenderer(canvas);presentation=new YingchePresentation(canvas,shadow,text=>status(text,true));panelHost=makePanel();
 controller.active=true;controller.generation++;controller.needsCapture=false;controller.lastError='';lastPosition=-1;lastSubmit=0;lastPaint=-1000;lastAnalysisFrame=-1;
 seekHandler=invalidate;video.addEventListener('seeking',seekHandler);video.addEventListener('loadeddata',seekHandler);
 playHandler=()=>{lastPosition=-1;lastAnalysisFrame=-1;interpolation?.reset();};video.addEventListener('play',playHandler);video.addEventListener('pause',playHandler);video.addEventListener('ratechange',playHandler);
 visibilityHandler=()=>{if(document.visibilityState==='visible'){invalidate();lastPosition=-1;lastPaint=-1000;}};document.addEventListener('visibilitychange',visibilityHandler);
 const activeRenderer=renderer;await activeRenderer.ready;if(!controller.active||renderer!==activeRenderer)return {active:false};controller.engineReady=true;controller.engine=activeRenderer.gpu.version;observer=new ResizeObserver(geometry);observer.observe(video);watchFrames();raf=requestAnimationFrame(loop);return {active:true,version:controller.version,engine:controller.engine,videoWidth:video.videoWidth,videoHeight:video.videoHeight};
}
function stop(){
 controller.active=false;controller.engineReady=false;controller.generation++;cancelAnimationFrame(raf);observer?.disconnect();observer=null;
 if(frameInput&&frameCallback!==undefined)frameInput.cancelVideoFrameCallback(frameCallback);frameInput=null;frameCallback=undefined;interpolation?.dispose();interpolation=null;
 controller.stream?.getTracks().forEach(t=>t.stop());controller.stream=null;
 if(video&&seekHandler){video.removeEventListener('seeking',seekHandler);video.removeEventListener('loadeddata',seekHandler);}
 if(video&&playHandler){video.removeEventListener('play',playHandler);video.removeEventListener('pause',playHandler);video.removeEventListener('ratechange',playHandler);}
 if(visibilityHandler)document.removeEventListener('visibilitychange',visibilityHandler);captureCanvas=null;captureContext=null;
 if(video&&videoStyle){video.style.setProperty('isolation',videoStyle.value,videoStyle.priority);videoStyle=null;}
 if(originalParent&&parentStyle)originalParent.style.setProperty('position',parentStyle.value,parentStyle.priority);
 presentation?.dispose();presentation=null;renderer?.dispose();renderer=null;host?.remove();panelHost?.remove();host=null;panelHost=null;panel=null;lastPosition=-1;
 return {active:false};
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
 if(sender.id!==chrome.runtime.id)return;
 if(message.type==='yingche-start'){start(message.config).then(reply).catch(e=>{stop();reply({error:e.message});});return true;}
 if(message.type==='yingche-stop'){reply(stop());return;}
 if(message.type==='yingche-config'){config=message.config;invalidate();lastPosition=-1;reply({ok:true});return;}
 if(message.type==='yingche-status'){reply({version:controller.version,engine:controller.engine,engineReady:controller.engineReady,swapMs:controller.swapMs||0,swapState:controller.swapState,swapAgeMs:controller.swapAgeMs,swapReused:controller.swapReused,swapPending:controller.swapPending,swapError:controller.swapError,active:controller.active,frames:controller.frames,analysis:controller.analysis,faces:controller.lastFaces||0,swapFaces:controller.swapFaces||0,analysisMs:controller.analysisMs||0,roundTripMs:controller.roundTripMs||0,frameBytes:controller.frameBytes||0,encodeMs:controller.encodeMs||0,...(renderer?.status||{}),presentation:presentation?.compatible?'video':'canvas',outputFrames:presentation?.frames||0,outputFps:presentation?.fps||0,...(interpolation?.status||{interpolationState:'off'}),outputWidth:canvas?.width||0,outputHeight:canvas?.height||0,needsCapture:controller.needsCapture,error:controller.lastError});}
});
controller.stop=stop;globalThis.__yingcheController=controller;
})();
