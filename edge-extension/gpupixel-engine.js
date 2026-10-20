(() => {
if(globalThis.YingcheGPUPixel)return;
class YingcheGPUPixel {
 constructor(canvas,gl,texture){
  this.gl=gl;this.texture=texture;this.handles=new Map();this.disposed=false;this.ready=false;this.version='';
  this.initialized=this.init(canvas);
 }
 async init(canvas){
  const module=await GPUPixelModule({canvas,preinitializedWebGLContext:this.gl,print:()=>{},printErr:text=>console.error('[GPUPixel]',text)});
  this.module=module;
  if(this.disposed)return;
  this.gl.pixelStorei(this.gl.UNPACK_FLIP_Y_WEBGL,false);
  this.gl.pixelStorei(this.gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
  if(!module._yingche_init())throw Error('GPUPixel 初始化失败：'+module.UTF8ToString(module._yingche_error()));
  this.nativeReady=true;
  const id=module.GL.getNewId(module.GL.textures);
  this.textureId=id;this.texture.name=id;module.GL.textures[id]=this.texture;this.handles.set(this.texture,id);
  this.version=module.UTF8ToString(module._yingche_version());this.ready=true;
 }
 render(sw,sh,w,h,p,texture=this.texture){
  if(!this.ready||this.disposed)throw Error('GPUPixel 尚未就绪');
  const m=this.module;
  let sourceId=this.handles.get(texture);
  if(!sourceId){sourceId=m.GL.getNewId(m.GL.textures);texture.name=sourceId;m.GL.textures[sourceId]=texture;this.handles.set(texture,sourceId);}
  const id=m._yingche_render(sourceId,sw,sh,w,h,p.smooth,p.detail,p.white,p.sharp);
  if(!id||!m.GL.textures[id])throw Error('GPUPixel 处理失败：'+m.UTF8ToString(m._yingche_error()));
  return m.GL.textures[id];
 }
 dispose(){
  if(this.disposed)return;this.disposed=true;this.ready=false;
  if(this.nativeReady){this.module._yingche_release();this.nativeReady=false;}
  if(this.module)for(const id of this.handles.values())this.module.GL.textures[id]=null;this.handles.clear();
  this.module=null;
 }
}
globalThis.YingcheGPUPixel=YingcheGPUPixel;
})();
