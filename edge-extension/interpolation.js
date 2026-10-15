(() => {
if(globalThis.YingcheInterpolation)return;
// One decoded frame of look-ahead. Four anchors cover early callbacks and display jitter.
class YingcheInterpolation {
 constructor(){
  this.state='starting';this.reason='正在加载补帧模型';this.frames=[];this.intervals=[];this.epoch=0;
  this.canvas=document.createElement('canvas');this.probe=new OffscreenCanvas(32,18);
  this.probeContext=this.probe.getContext('2d',{willReadFrequently:true,alpha:false});
  this.counts={input:0,output:0,generated:0,cuts:0};this.sample={...this.counts,time:performance.now()};
  this.rates={input:0,output:0,generated:0};this.gpuMs=0;this.delayMs=0;this.slow=0;
 }
 ensure(width,height){
  if(this.disposed||this.state==='error'||this.state==='limited')return;
  const key=width+':'+height;if(this.sizeKey===key)return;
  this.sizeKey=key;const epoch=++this.epoch;this.state='starting';this.reset();
  this.initialize(width,height,epoch).catch(e=>{if(epoch===this.epoch&&!this.disposed)this.fail(e.message);});
 }
 async initialize(width,height,epoch){
  // Disposing the old device also invalidates outstanding asynchronous setup.
  this.releaseGPU();
  if(!navigator.gpu)throw Error('此页面没有 WebGPU，请使用 HTTPS 和新版 Edge');
  const adapter=await navigator.gpu.requestAdapter({powerPreference:'high-performance'});
  if(epoch!==this.epoch||this.disposed)return;
  if(!adapter?.features.has('shader-f16'))throw Error('显卡或浏览器不支持 WebGPU 半精度补帧');
  const device=await adapter.requestDevice({requiredFeatures:['shader-f16']});
  if(epoch!==this.epoch||this.disposed){device.destroy();return;}
  this.device=device;
  device.addEventListener('uncapturederror',event=>{if(this.device===device&&!this.disposed)this.fail(event.error.message);});
  device.lost.then(info=>{if(this.device===device&&!this.disposed&&info.reason!=='destroyed')this.fail('显卡连接中断，已恢复普通输出');});
  const get=async name=>{const r=await fetch(chrome.runtime.getURL('vendor/framegen/'+name));if(!r.ok)throw Error('补帧模型读取失败');return r;};
  const [weightsBin,weightsManifest]=await Promise.all([get('rt_v7s.bin').then(r=>r.arrayBuffer()),get('rt_v7s.json').then(r=>r.json())]);
  if(epoch!==this.epoch||this.disposed)return;
  const w=Math.ceil(width/16)*16,h=Math.ceil(height/16)*16;
  const runtime=await YingcheFramegenRT.createRT(device,{w,h,weightsBin,weightsManifest,textureInput:true,textureOutput:true,staticGuard:true});
  if(epoch!==this.epoch||this.disposed){runtime.destroy();return;}
  this.runtime=runtime;this.canvas.width=width;this.canvas.height=height;
  const usage=GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.COPY_DST|GPUTextureUsage.RENDER_ATTACHMENT;
  this.textures=Array.from({length:4},()=>device.createTexture({size:[width,height],format:'rgba8unorm',usage}));
  this.middle=device.createTexture({size:[w,h],format:'rgba8unorm',usage:GPUTextureUsage.STORAGE_BINDING|GPUTextureUsage.TEXTURE_BINDING});
  this.context=this.canvas.getContext('webgpu');const format=navigator.gpu.getPreferredCanvasFormat();
  this.context.configure({device,format,alphaMode:'opaque'});
  const module=device.createShaderModule({code:`
   struct V { @builtin(position) p:vec4f, @location(0) uv:vec2f }
   @vertex fn vs(@builtin(vertex_index) i:u32)->V {
    let p=array<vec2f,3>(vec2f(-1,-1),vec2f(3,-1),vec2f(-1,3))[i];
    var o:V;o.p=vec4f(p,0,1);o.uv=vec2f((p.x+1)*.5,(1-p.y)*.5);return o;
   }
   @group(0) @binding(0) var s:sampler;
   @group(0) @binding(1) var t:texture_2d<f32>;
   @fragment fn fs(v:V)->@location(0) vec4f {return textureSample(t,s,v.uv);}`});
  this.pipeline=device.createRenderPipeline({layout:'auto',vertex:{module,entryPoint:'vs'},fragment:{module,entryPoint:'fs',targets:[{format}]},primitive:{topology:'triangle-list'}});
  const sampler=device.createSampler({minFilter:'linear',magFilter:'linear'});
  this.bindings=new Map([...this.textures,this.middle].map(texture=>[texture,device.createBindGroup({layout:this.pipeline.getBindGroupLayout(0),entries:[{binding:0,resource:sampler},{binding:1,resource:texture.createView()}]})]));
  this.state='ready';this.reason='等待视频帧';this.slot=0;
 }
 reset(){
  this.frames=[];this.intervals=[];this.lastDue=null;this.lastSignature=null;this.pair=null;this.lastDraw=-1;this.delayMs=0;
  if(this.runtime&&['active','bypass'].includes(this.state)){this.state='ready';this.reason='等待视频帧';}
 }
 capture(source,now,metadata){
  if(!this.runtime||!['ready','active','bypass'].includes(this.state))return;
  const due=metadata.expectedDisplayTime||now;
  const interval=this.lastDue===null?0:due-this.lastDue;
  if(interval>180||interval<0)this.reset();
  if(interval>5&&interval<180){this.intervals.push(interval);if(this.intervals.length>20)this.intervals.shift();}
  this.lastDue=due;
  this.probeContext.drawImage(source,0,0,32,18);
  const signature=this.probeContext.getImageData(0,0,32,18).data;
  let diff=0,changed=0;
  if(this.lastSignature){for(let i=0;i<signature.length;i+=4){let d=0;for(let c=0;c<3;c++)d+=Math.abs(signature[i+c]-this.lastSignature[i+c]);diff+=d;changed+=d>115;}diff/=32*18*3*255;}
  const cut=diff>.24&&changed>32*18*.65,still=!!this.lastSignature&&diff<.0002;
  this.lastSignature=signature;if(cut)this.counts.cuts++;
  const texture=this.textures[this.slot++%4];
  this.device.queue.copyExternalImageToTexture({source},{texture},[source.width,source.height]);
  this.frames.push({texture,due,cut,still,id:this.counts.input++});if(this.frames.length>4)this.frames.shift();
 }
 draw(now){
  if(!this.runtime||!this.frames.length)return null;
  const sorted=[...this.intervals].sort((a,b)=>a-b),interval=sorted.length?sorted[Math.floor(sorted.length/2)]:1000/30;
  if(sorted.length>=8&&interval<1000/55){this.state='bypass';this.reason='输入已接近 60 FPS';this.delayMs=0;return null;}
  if(now-this.lastDue>180){this.state='ready';this.reason='等待视频帧';return null;}
  if(this.pending){
   if(now-this.pendingSince>200){this.fail('补帧响应超时，已恢复普通输出','limited');return null;}
   return {hold:true};
  }
  this.delayMs=interval+8;const target=now-this.delayMs;
  let a=this.frames[0],b=a;
  for(let i=1;i<this.frames.length;i++){b=this.frames[i];if(target<=b.due)break;a=b;}
  let t=a===b?0:Math.max(0,Math.min(1,(target-a.due)/(b.due-a.due)));
  const generated=t>.03&&t<.97&&!b.cut&&!b.still&&a!==b;
  let texture=t>=.97?b.texture:a.texture;
  const start=performance.now(),device=this.device,epoch=this.epoch;
  if(generated){
   const key=a.id+':'+b.id;if(key!==this.pair){this.runtime.prepPair(a.texture,b.texture);this.pair=key;}
   this.runtime.runT(t,this.middle);texture=this.middle;this.counts.generated++;
  }
  const enc=device.createCommandEncoder(),pass=enc.beginRenderPass({colorAttachments:[{view:this.context.getCurrentTexture().createView(),loadOp:'clear',storeOp:'store',clearValue:{r:0,g:0,b:0,a:1}}]});
  pass.setPipeline(this.pipeline);pass.setBindGroup(0,this.bindings.get(texture));pass.draw(3);pass.end();device.queue.submit([enc.finish()]);
  this.pending=true;this.pendingSince=now;this.counts.output++;this.lastDraw=target;
  this.state='active';this.reason='神经网络补帧';
  device.queue.onSubmittedWorkDone().then(()=>{
   if(epoch!==this.epoch||this.disposed)return;
   this.pending=false;const elapsed=performance.now()-start;this.gpuMs=this.gpuMs?this.gpuMs*.85+elapsed*.15:elapsed;
   this.slow=elapsed>22?this.slow+1:Math.max(0,this.slow-1);
   if(this.slow>=12)this.fail('显卡处理超时，已恢复普通输出；关闭再打开补帧可重试','limited');
  }).catch(e=>{if(epoch===this.epoch&&!this.disposed)this.fail(e.message);});
  return {source:this.canvas,generated};
 }
 get status(){
  const now=performance.now(),seconds=(now-this.sample.time)/1000;
  if(seconds>=1){for(const key of ['input','output','generated'])this.rates[key]=(this.counts[key]-this.sample[key])/seconds;this.sample={...this.counts,time:now};}
  return {interpolationState:this.state,interpolationReason:this.reason,inputFps:this.rates.input,interpolatedFps:this.rates.generated,generatedFrames:this.counts.generated,interpolationMs:this.gpuMs,interpolationDelayMs:this.delayMs,sceneCuts:this.counts.cuts};
 }
 fail(reason,state='error'){this.epoch++;this.state=state;this.reason=reason;this.releaseGPU();this.reset();}
 releaseGPU(){
  this.runtime?.destroy();this.runtime=null;this.textures?.forEach(t=>t.destroy());this.textures=null;this.middle?.destroy();this.middle=null;
  this.context?.unconfigure();this.context=null;const device=this.device;this.device=null;device?.destroy();this.bindings=null;this.pending=false;
 }
 dispose(){this.disposed=true;this.epoch++;this.releaseGPU();this.reset();}
}
globalThis.YingcheInterpolation=YingcheInterpolation;
})();
