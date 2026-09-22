// GPUPixel host adapter: share the extension's WebGL2 context on this JS thread.
#include "core/gpupixel_context.h"
#include <stdexcept>
EM_JS(int, yingche_register_context, (), {
  const gl = Module.preinitializedWebGLContext;
  if (!gl) return 0;
  const handle = GL.registerContext(gl, {majorVersion: 2, minorVersion: 0, enableExtensionsByDefault: true});
  GL.makeContextCurrent(handle);
  return handle;
});
namespace gpupixel {
GPUPixelContext* GPUPixelContext::instance_ = nullptr;
std::mutex GPUPixelContext::mutex_;
GPUPixelContext::GPUPixelContext():framebuffer_factory_(nullptr),current_shader_program_(nullptr),wasm_context_(0) {
  CreateContext(); framebuffer_factory_=new FramebufferFactory();
}
GPUPixelContext::~GPUPixelContext(){delete framebuffer_factory_;}
GPUPixelContext* GPUPixelContext::GetInstance(){if(!instance_)instance_=new GPUPixelContext();return instance_;}
void GPUPixelContext::Destroy(){delete instance_;instance_=nullptr;}
FramebufferFactory* GPUPixelContext::GetFramebufferFactory() const{return framebuffer_factory_;}
void GPUPixelContext::SetActiveGlProgram(GPUPixelGLProgram* program){
  current_shader_program_=program;program->UseProgram();
  auto position=program->GetAttribLocation("position");
  if(position>=0)glEnableVertexAttribArray(position);
}
void GPUPixelContext::Clean(){framebuffer_factory_->Clean();}
void GPUPixelContext::Init(){CreateContext();}
void GPUPixelContext::CreateContext(){
  if(!wasm_context_)wasm_context_=yingche_register_context();
  if(!wasm_context_)throw std::runtime_error("WebGL2 context registration failed");
}
void GPUPixelContext::ReleaseContext(){}
void GPUPixelContext::UseAsCurrent(){emscripten_webgl_make_context_current(wasm_context_);}
void GPUPixelContext::PresentBufferForDisplay(){}
void GPUPixelContext::SyncRunWithContext(std::function<void()> task){UseAsCurrent();task();}
}
