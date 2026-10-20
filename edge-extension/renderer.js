(() => {
if (globalThis.YingcheRenderer) return;
const VERTEX = "#version 300 es\nprecision highp float;\nout vec2 uv;\nvoid main() {\n    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);\n    uv = p;\n    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n}\n";
const FRAGMENT = "#version 300 es\nprecision highp float;\nprecision highp int;\nin vec2 uv;\nout vec4 frag;\nuniform sampler2D frameTex;\nuniform sampler2D originalTex;\nuniform int gpupixelEnabled;\nuniform float trackingWeight;\nuniform vec2 faceMotion[4];\nuniform sampler2D regionTex;\nuniform sampler2D swapTex;\nuniform int swapEnabled;\nuniform int swapPrecomposed;\nuniform float swapStrength;\nuniform vec2 texel;\nuniform vec2 imageSize;\nuniform int enabled;\nuniform int compareMode;\nuniform int faceCount;\nuniform int trackedFaceCount;\nuniform vec2 points[32];\nuniform float smoothValue, detailValue, whiteValue, warmValue, pinkValue;\nuniform float slimValue, eyesValue, chinValue, noseValue, lipValue, blushValue, sharpValue;\nuniform sampler2D baseTex;\nfloat distancePx(vec2 a, vec2 b) { return length((a-b)*imageSize); }\nfloat luma(vec3 c){return dot(c,vec3(.299,.587,.114));}\n// Frequency-separated skin: GPUPixel supplies only the smoothed fine texture; shading and hue stay original.\nvec3 skinTone(vec2 p,float radius){\n    vec3 b=texture(baseTex,p).rgb,g=texture(frameTex,p).rgb,lowB=vec3(0.),lowG=vec3(0.);\n    for(int i=0;i<12;i++){\n        float a=float(i)*.5235988;vec2 o=floor(vec2(cos(a),sin(a))*radius*((i&1)==0?1.:.55)+.5)*texel;\n        lowB+=texture(baseTex,p+o).rgb;lowG+=texture(frameTex,p+o).rgb;\n    }\n    lowB/=12.;lowG/=12.;\n    float s=clamp(smoothValue/100.,0.,1.),keep=clamp(detailValue/150.,0.,1.);\n    float yb=luma(b),yl=luma(lowB);\n    float y=yl+(luma(g)-luma(lowG))*(1.-.75*s*(1.-.5*keep));\n    return clamp(vec3(y)+mix(b-yb,lowB-yl,s*.5),0.,1.);\n}\nvec2 eyeWarp(vec2 p,vec2 c,float radius,float amount) {\n    float t=clamp(1.0-distancePx(p,c)/max(radius,1.0),0.0,1.0);\n    return c+(p-c)*(1.0-amount*t*t);\n}\nvec2 moveWarp(vec2 p,vec2 c,vec2 delta,float radius) {\n    float t=clamp(1.0-distancePx(p,c)/max(radius,1.0),0.0,1.0);\n    return p+delta*t*t*(3.0-2.0*t);\n}\nvec3 sourceAt(vec2 position) {\n    vec3 base=texture(frameTex,position).rgb;\n    if(swapEnabled==1 && swapPrecomposed==0) {\n        vec2 sampleUV=vec2(position.x,1.-position.y);\n        float nearest=1.;vec2 offset=vec2(0.);\n        for(int i=0;i<trackedFaceCount;i++) {\n            vec2 center=(points[i*8+2]+points[i*8+3])*.5;\n            float d=distancePx(sampleUV,center)/max(1.,distancePx(points[i*8+2],points[i*8+3])*.9);\n            if(d<nearest){nearest=d;offset=faceMotion[i];}\n        }\n        sampleUV-=offset;\n        vec4 face=texture(swapTex,sampleUV);\n        return mix(base,face.rgb,face.a*swapStrength);\n    }\n    return base;\n}\nvoid main() {\n    // mpv's FBO is rendered with FLIP_Y=1. Region maps use top-down image coords.\n    vec2 p=uv;\n    if((enabled==0 && swapEnabled==0) || (compareMode==1 && uv.x<.5)) {\n        frag=texture(originalTex,p); return;\n    }\n    vec2 t=vec2(p.x,1.0-p.y);\n    for(int i=0;i<faceCount;i++) {\n        int k=i*8;\n        vec2 left=points[k+2], right=points[k+3], center=(left+right)*.5;\n        float width=distancePx(left,right);\n        t=eyeWarp(t,points[k],width*.21,eyesValue*.0028*trackingWeight);\n        t=eyeWarp(t,points[k+1],width*.21,eyesValue*.0028*trackingWeight);\n        t=moveWarp(t,left,(left-center)*slimValue*.0015*trackingWeight,width*.55);\n        t=moveWarp(t,right,(right-center)*slimValue*.0015*trackingWeight,width*.55);\n        vec2 chin=points[k+4], nose=points[k+5];\n        t=moveWarp(t,chin,(nose-chin)*chinValue*.0015*trackingWeight,width*.5);\n        t=moveWarp(t,points[k+6],(points[k+6]-nose)*noseValue*.003*trackingWeight,width*.19);\n        t=moveWarp(t,points[k+7],(points[k+7]-nose)*noseValue*.003*trackingWeight,width*.19);\n    }\n    p=vec2(t.x,1.0-t.y);\n    vec3 src=sourceAt(p);\n    if(enabled==0) {frag=vec4(src,1.);return;}\n    vec2 maskUV=t;float radius=6.;\n    for(int i=0;i<faceCount;i++) {\n        vec2 center=(points[i*8+2]+points[i*8+3])*.5;float width=distancePx(points[i*8+2],points[i*8+3]);\n        if(distancePx(t,center)<width*.8){maskUV=t-faceMotion[i];radius=max(3.,width*.07);}\n    }\n    vec3 masks=texture(regionTex,maskUV).rgb*trackingWeight;\n    // GPUPixel filtered the whole frame; only tracked skin takes it, everything else stays original.\n    if(gpupixelEnabled==1)src=mix(texture(baseTex,p).rgb,skinTone(p,radius),masks.r);\n    vec3 skin=src;\n    float bright=whiteValue/200.;\n    float yy=luma(skin);\n    if(bright>=0.) skin+=vec3(bright*1.2*yy*(1.-yy));\n    else skin*=1.0+bright*.65;\n    skin+=vec3(.055,-.012,-.055)*(warmValue/100.);\n    skin+=vec3(.035,-.015,.005)*(pinkValue/150.);\n    vec3 color=mix(src,clamp(skin,0.,1.),masks.r);\n    float lum=dot(color,vec3(.2126,.7152,.0722));\n    vec3 lipColor=vec3(.70,.13,.24)*(.5+lum*.8);\n    color=mix(color,lipColor,masks.g*clamp(lipValue/150.,0.,1.)*.75);\n    color=mix(color,vec3(.88,.30,.38)*(.6+lum*.5),\n              masks.b*clamp(blushValue/150.,0.,1.)*.28);\n    if(compareMode==1 && abs(uv.x-.5)<texel.x) color=vec3(.55,.85,.77);\n    frag=vec4(clamp(color,0.,1.),1.);\n}\n";
class YingcheRenderer {
 constructor(canvas) {
  this.canvas=canvas;this.gl=canvas.getContext('webgl2',{alpha:true,antialias:false,preserveDrawingBuffer:true});
  const g=this.gl;if(!g)throw Error('浏览器不支持 WebGL 2');
  const compile=(type,source)=>{const s=g.createShader(type);g.shaderSource(s,source);g.compileShader(s);if(!g.getShaderParameter(s,g.COMPILE_STATUS))throw Error(g.getShaderInfoLog(s));return s;};
  const vs=compile(g.VERTEX_SHADER,VERTEX),fs=compile(g.FRAGMENT_SHADER,FRAGMENT);
  this.program=g.createProgram();g.attachShader(this.program,vs);g.attachShader(this.program,fs);g.linkProgram(this.program);
  g.deleteShader(vs);g.deleteShader(fs);
  if(!g.getProgramParameter(this.program,g.LINK_STATUS))throw Error(g.getProgramInfoLog(this.program));
  this.uniforms={};
  this.textures=[0,1,2].map(i=>{const t=g.createTexture();g.activeTexture(g.TEXTURE0+i);g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,1,1,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array(4));return t;});
  this.vao=g.createVertexArray();this.data=null;this.frames=0;this.disposed=false;this.analysisEpoch=0;
  this.gpu=new YingcheGPUPixel(canvas,g,this.textures[0]);this.ready=this.gpu.initialized;
  this.points=new Float32Array(64);this.motion=new Float32Array(8);this.lastInput=-1;this.lastGPUKey='';this.latencyMs=70;this.intervalMs=70;this.lastSampleTime=null;this.status={trackingWeight:0,shownFaces:0,shownSwapFaces:0};
  // Synchronised display (enabled by the controller only when it can delay the page audio equally):
  // decoded frames wait in a short ring and are shown delayMs later, so each shown frame lies
  // between two finished analyses and effect geometry is interpolated, not extrapolated.
  this.syncWanted=false;this.syncActive=false;this.ring=[];this.ringEpoch=0;this.frameId=0;this.newest=null;this.shown=null;
  this.results=[0,1,2,3].map(()=>({at:-1e9,epoch:-1,mask:this.texture(),swap:this.texture()}));this.resultCursor=0;
  this.delayMs=110;this.delayTarget=110;this.roundTrips=[];this.bracketed=[];this.playingSince=0;this.lastShownId=-1;
  this.readFbo=g.createFramebuffer();this.drawFbo=g.createFramebuffer();
 }
 texture(){const g=this.gl,t=g.createTexture();g.bindTexture(g.TEXTURE_2D,t);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);g.texImage2D(g.TEXTURE_2D,0,g.RGBA,1,1,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array(4));return t;}
 loc(name){if(!(name in this.uniforms))this.uniforms[name]=this.gl.getUniformLocation(this.program,name);return this.uniforms[name];}
 // Seeks/loads also drop delayed frames; a settings change keeps them.
 clear(keepFrames=false){this.data=null;this.analysisEpoch++;this.lastSampleTime=null;this.status={trackingWeight:0,shownFaces:0,shownSwapFaces:0};if(!keepFrames){this.ringEpoch++;this.newest=null;this.shown=null;this.roundTrips=[];this.delayTarget=110;}}
 // Frame the next analysis is keyed to, so results land on the display timeline.
 newestFrame(){return this.syncWanted&&this.newest?.epoch===this.ringEpoch?{at:this.newest.at,pts:this.newest.pts}:null;}
 async analysis(data) {
  const epoch=this.analysisEpoch;
  // ImageBitmap upload ignores WebGL UNPACK_PREMULTIPLY_ALPHA_WEBGL. Keep straight alpha for the shader mix.
  const decode=async b64=>{if(!b64)return null;const b=Uint8Array.from(atob(b64),c=>c.charCodeAt(0));return createImageBitmap(new Blob([b],{type:'image/png'}),{premultiplyAlpha:'none',colorSpaceConversion:'none'});};
  const [mask,swap]=await Promise.all([decode(data.mask),decode(data.swap)]);
  if(this.disposed||epoch!==this.analysisEpoch){mask?.close();swap?.close();return;}
  const g=this.gl;g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,false);g.pixelStorei(g.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
  const slot=this.results[this.resultCursor];this.resultCursor=(this.resultCursor+1)%this.results.length;
  [[mask,slot.mask],[swap,slot.swap]].forEach(([img,t])=>{g.activeTexture(g.TEXTURE1);g.bindTexture(g.TEXTURE_2D,t);if(img){g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,img);img.close();}else g.texImage2D(g.TEXTURE_2D,0,g.RGBA,1,1,0,g.RGBA,g.UNSIGNED_BYTE,new Uint8Array(4));});
  Object.assign(slot,{at:data.sampleTime,pts:data.pts,epoch:this.analysisEpoch,faces:(data.faces||[]).slice(0,4),motion:data.motion||[],ids:data.trackIds||[],hasSwap:!!data.swap,swapFaces:data.swapFaces||0,id:data.id,sceneCut:!!data.sceneCut});
  const latency=Math.max(0,performance.now()-data.sampleTime);
  const gap=this.lastSampleTime===null?0:data.sampleTime-this.lastSampleTime;
  this.latencyMs=this.latencyMs*.6+Math.min(400,latency)*.4;
  if(gap>0&&gap<500)this.intervalMs=this.intervalMs*.6+gap*.4;
  const push=(list,v)=>{list.push(v);if(list.length>40)list.shift();},p90=list=>{const s=[...list].sort((a,b)=>a-b);return s.length?s[Math.floor(s.length*.9)]:0;};
  // A frame just after one analysed frame waits for the next analysed frame plus its latency.
  if(gap>0&&gap<250)push(this.roundTrips,Math.min(400,latency)+gap);
  if(this.roundTrips.length>=10)this.delayTarget=Math.round(Math.min(250,Math.max(70,p90(this.roundTrips)+10))/10)*10;
  this.lastSampleTime=data.sampleTime;this.data=data;
 }
 // Called for every presented video frame while synchronised, with that frame's exact media time.
 ingest(video,mediaTime,cw,ch){
  if(this.disposed||!this.gpu.ready||video.readyState<2||!video.videoWidth)return;
  const g=this.gl;
  g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,this.textures[0]);
  g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,true);g.pixelStorei(g.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
  g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,video);g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,false);
  this.inputW=video.videoWidth;this.inputH=video.videoHeight;
  this.capture(mediaTime,cw,ch,performance.now());
 }
 // Copies the current decoded frame into the delay ring (canvas-sized, so 4K input stays bounded).
 capture(position,cw,ch,now){
  const g=this.gl;
  if(this.ring.length&&(this.ring[0].w!==cw||this.ring[0].h!==ch)){this.ring.forEach(s=>g.deleteTexture(s.tex));this.ring=[];this.newest=null;this.shown=null;}
  let slot=null;
  for(const s of this.ring)if(s!==this.newest&&s!==this.shown&&(s.epoch!==this.ringEpoch||s.at<now-this.delayMs-120)&&(!slot||s.at<slot.at))slot=s;
  if(!slot&&this.ring.length<24){slot={tex:this.texture(),w:cw,h:ch};g.bindTexture(g.TEXTURE_2D,slot.tex);g.texImage2D(g.TEXTURE_2D,0,g.RGBA8,cw,ch,0,g.RGBA,g.UNSIGNED_BYTE,null);this.ring.push(slot);}
  if(!slot)for(const s of this.ring)if(s!==this.newest&&s!==this.shown&&(!slot||s.at<slot.at))slot=s;
  g.bindFramebuffer(g.READ_FRAMEBUFFER,this.readFbo);g.framebufferTexture2D(g.READ_FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,this.textures[0],0);
  g.bindFramebuffer(g.DRAW_FRAMEBUFFER,this.drawFbo);g.framebufferTexture2D(g.DRAW_FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,slot.tex,0);
  g.blitFramebuffer(0,0,this.inputW,this.inputH,0,0,cw,ch,g.COLOR_BUFFER_BIT,g.LINEAR);
  g.bindFramebuffer(g.READ_FRAMEBUFFER,null);g.bindFramebuffer(g.DRAW_FRAMEBUFFER,null);
  Object.assign(slot,{at:now,pts:position,id:++this.frameId,epoch:this.ringEpoch});this.newest=slot;
 }
 render(video,config,position,speed=1,paused=video.paused) {
  if(this.disposed||!this.gpu.ready||video.readyState<2||!video.videoWidth)return false;
  const g=this.gl,w=video.videoWidth,h=video.videoHeight,cw=this.canvas.width,ch=this.canvas.height;
  const decodedFrames=video.getVideoPlaybackQuality?.().totalVideoFrames;
  const inputKey=(decodedFrames>0?decodedFrames:video.currentTime)+':'+w+':'+h;
  const now=performance.now();
  this.syncActive=this.syncWanted&&!paused;
  if(!this.syncActive){this.playingSince=now;this.bracketed=[];}
  if(paused&&Math.abs(this.delayTarget-this.delayMs)>=30)this.delayMs=this.delayTarget;
  // While synchronised, frames arrive through ingest(); the direct upload covers everything else.
  const ringLive=this.syncWanted&&this.newest?.epoch===this.ringEpoch;
  if(!ringLive&&this.lastInput!==inputKey){
   g.activeTexture(g.TEXTURE0);g.bindTexture(g.TEXTURE_2D,this.textures[0]);
   g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,true);g.pixelStorei(g.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
   g.texImage2D(g.TEXTURE_2D,0,g.RGBA,g.RGBA,g.UNSIGNED_BYTE,video);g.pixelStorei(g.UNPACK_FLIP_Y_WEBGL,false);
   this.inputW=w;this.inputH=h;this.lastInput=inputKey;
  }
  if(ringLive)this.lastInput='';
  // Frame to show: the one captured delayMs ago while synchronised, otherwise the current one.
  let shown=null;
  if(this.syncActive&&this.newest?.epoch===this.ringEpoch){
   const due=now-this.delayMs;let oldest=null;
   for(const s of this.ring){if(s.epoch!==this.ringEpoch)continue;if(s.at<=due&&(!shown||s.at>shown.at))shown=s;if(!oldest||s.at<oldest.at)oldest=s;}
   shown=shown||oldest;
  }else if(this.syncWanted&&this.newest?.epoch===this.ringEpoch)shown=this.newest;
  this.shown=shown;
  const frameTexture=shown?shown.tex:this.textures[0],t=shown?shown.at:now,shownPts=shown?shown.pts:position;
  if(shown){this.displayPts=shown.pts;this.displayLagMs=now-shown.at;}
  if(this.lastFrameKey!==(shown?'s'+shown.id:inputKey)){this.lastFrameKey=shown?'s'+shown.id:inputKey;this.lastGPUKey='';}
  // Analyses around the shown frame; geometry is interpolated between them when both exist.
  let A=null,B=null;
  for(const r of this.results){if(r.epoch!==this.analysisEpoch)continue;if(r.at<=t){if(!A||r.at>A.at)A=r;}else if(!B||r.at<B.at)B=r;}
  // The first result after a confirmed cut belongs to the new shot; frames before it may still be the old one.
  if(!shown||B?.sceneCut)B=null;
  if(this.syncActive&&now-this.playingSince>1000+this.delayMs&&shown&&shown.id!==this.lastShownId&&(A||B)){
   this.lastShownId=shown.id;this.bracketed.push(!!(A&&B));if(this.bracketed.length>60)this.bracketed.shift();
   const misses=this.bracketed.filter(x=>!x).length;
   if(this.bracketed.length>=30&&misses>this.bracketed.length*.15&&this.delayTarget>this.delayMs+15){this.delayMs=this.delayTarget;this.bracketed=[];}
  }
  const R=B&&(!A||B.at-t<t-A.at)?B:A,other=R===A?B:A;
  // Keep full effect through measured transit plus a normal update interval.
  // The hard cap still rejects old poses if processing stalls.
  const lifetime=Math.min(350,Math.max(220,this.latencyMs+this.intervalMs*1.5+90));
  const valid=!!R&&Math.abs(shownPts-R.pts)*1000<lifetime*Math.max(1,speed);
  const age=paused?0:(A&&B?0:Math.abs(t-(R?.at||0)));
  // Synchronised frames normally have measurements on both sides; when a latency spike leaves one
  // without, fade quickly rather than draw an effect where the face no longer is.
  const weight=valid?Math.max(0,Math.min(1,this.syncActive&&shown?(120-age)/60:(lifetime-age)/80)):0;
  const faces=valid?R.faces:[],swapOn=!!(valid&&config.swapEnabled&&R.hasSwap&&config.swapStrength>0&&weight>0);
  const points=this.points,motion=this.motion;points.fill(0);motion.fill(0);
  faces.forEach((face,i)=>{
   const j=A&&B&&other?other.ids.indexOf(R.ids[i]):-1;let at;
   if(j>=0&&other.faces[j]){const f=Math.min(1,Math.max(0,(t-A.at)/Math.max(1,B.at-A.at))),fa=R===A?face:other.faces[j],fb=R===A?other.faces[j]:face;at=(k,c)=>fa[k][c]*(1-f)+fb[k][c]*f;}
   else{const velocity=R.motion?.[i]||[0,0],dt=paused?0:Math.max(-.06,Math.min(.06,(t-R.at)/1000));let dx=velocity[0]*dt,dy=velocity[1]*dt;const bound=Math.hypot(face[2][0]-face[3][0],face[2][1]-face[3][1])*.25,len=Math.hypot(dx,dy);if(len>bound&&bound>0){dx*=bound/len;dy*=bound/len;}at=(k,c)=>face[k][c]+(c?dy:dx);}
   for(let k=0;k<8;k++){points[i*16+k*2]=at(k,0);points[i*16+k*2+1]=at(k,1);}
   motion[i*2]=(points[i*16+4]+points[i*16+6])/2-(face[2][0]+face[3][0])/2;motion[i*2+1]=(points[i*16+5]+points[i*16+7])/2-(face[2][1]+face[3][1])/2;
  });
  const maskTexture=valid?R.mask:this.textures[1],swapTexture=valid?R.swap:this.textures[2];
  const draw=(frame,fbo,enabled,precomposed,compare,base=frame)=>{
   g.bindFramebuffer(g.FRAMEBUFFER,fbo);g.viewport(0,0,cw,ch);
   g.disable(g.DEPTH_TEST);g.disable(g.BLEND);g.disable(g.SCISSOR_TEST);g.disable(g.CULL_FACE);
   g.colorMask(true,true,true,true);g.useProgram(this.program);
   [frame,maskTexture,swapTexture,frameTexture,base].forEach((t,i)=>{g.activeTexture(g.TEXTURE0+i);g.bindTexture(g.TEXTURE_2D,t);g.bindSampler(i,null);});
   g.uniform1i(this.loc('frameTex'),0);g.uniform1i(this.loc('regionTex'),1);g.uniform1i(this.loc('swapTex'),2);g.uniform1i(this.loc('baseTex'),4);
   g.uniform1i(this.loc('originalTex'),3);g.uniform1i(this.loc('gpupixelEnabled'),1);
   g.uniform2f(this.loc('texel'),1/cw,1/ch);g.uniform2f(this.loc('imageSize'),cw,ch);
   g.uniform1f(this.loc('trackingWeight'),weight);g.uniform1i(this.loc('enabled'),enabled?1:0);
   g.uniform1i(this.loc('swapEnabled'),swapOn?1:0);g.uniform1i(this.loc('swapPrecomposed'),precomposed?1:0);
   g.uniform1f(this.loc('swapStrength'),config.swapStrength/100*weight);g.uniform1i(this.loc('compareMode'),compare?1:0);
   g.uniform1i(this.loc('faceCount'),enabled?Math.min(4,faces.length):0);g.uniform1i(this.loc('trackedFaceCount'),Math.min(4,faces.length));
   g.uniform2fv(this.loc('points[0]'),points);g.uniform2fv(this.loc('faceMotion[0]'),motion);
   for(const [key,value] of Object.entries(config.beauty))g.uniform1f(this.loc(key+'Value'),value);
   g.bindVertexArray(this.vao);g.drawArrays(g.TRIANGLES,0,3);
  };
  let source=frameTexture,sw=shown?cw:w,sh=shown?ch:h;
  if(swapOn){
   if(!this.composite){
    this.composite=g.createTexture();g.bindTexture(g.TEXTURE_2D,this.composite);
    g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MIN_FILTER,g.LINEAR);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_MAG_FILTER,g.LINEAR);
    g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_S,g.CLAMP_TO_EDGE);g.texParameteri(g.TEXTURE_2D,g.TEXTURE_WRAP_T,g.CLAMP_TO_EDGE);
    this.compositeFbo=g.createFramebuffer();
   }
   const size=cw+':'+ch;
   if(this.compositeSize!==size){
    g.bindTexture(g.TEXTURE_2D,this.composite);g.texImage2D(g.TEXTURE_2D,0,g.RGBA8,cw,ch,0,g.RGBA,g.UNSIGNED_BYTE,null);
    g.bindFramebuffer(g.FRAMEBUFFER,this.compositeFbo);g.framebufferTexture2D(g.FRAMEBUFFER,g.COLOR_ATTACHMENT0,g.TEXTURE_2D,this.composite,0);
    if(g.checkFramebufferStatus(g.FRAMEBUFFER)!==g.FRAMEBUFFER_COMPLETE)throw Error('无法分配换脸画面缓冲');
    this.compositeSize=size;
   }
   draw(source,this.compositeFbo,false,false,false);source=this.composite;sw=cw;sh=ch;
  }
  let output=source;const p=config.beauty;
  if(config.enabled){
   const key=[this.lastFrameKey,cw,ch,p.smooth,p.detail,p.white,p.sharp,swapOn?R.id:0,swapOn?motion.join(','):0,config.swapStrength].join(':');
   if(key!==this.lastGPUKey){this.filtered=this.gpu.render(sw,sh,cw,ch,p,source);this.lastGPUKey=key;}
   output=this.filtered;
  }else this.lastGPUKey='';
  draw(output,null,config.enabled,true,config.compare,source);this.frames++;
  this.status={trackingWeight:weight,trackingAgeMs:age,trackingLifetimeMs:lifetime,shownFaces:weight>0?faces.length:0,shownSwapFaces:swapOn?(R.swapFaces||0):0,
   syncActive:this.syncActive,syncDelayMs:this.delayMs,displayLagMs:shown?now-shown.at:0,displayPts:shownPts,frameSlots:this.ring.length,bracketed:!!(A&&B),
   drawnEyes:faces.length?[[points[0],points[1]],[points[2],points[3]]]:null};return true;
 }
 dispose(){if(this.disposed)return;this.disposed=true;this.gpu.dispose();const g=this.gl;this.textures.forEach(t=>g.deleteTexture(t));this.ring.forEach(s=>g.deleteTexture(s.tex));this.results.forEach(r=>{g.deleteTexture(r.mask);g.deleteTexture(r.swap);});g.deleteFramebuffer(this.readFbo);g.deleteFramebuffer(this.drawFbo);if(this.composite)g.deleteTexture(this.composite);if(this.compositeFbo)g.deleteFramebuffer(this.compositeFbo);g.deleteVertexArray(this.vao);g.deleteProgram(this.program);g.getExtension('WEBGL_lose_context')?.loseContext();}
}
globalThis.YingcheRenderer=YingcheRenderer;
})();
