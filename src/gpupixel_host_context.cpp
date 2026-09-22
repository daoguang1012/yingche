// Host-context adapter for GPUPixel 1.3.0. Filters remain upstream implementations.
// All calls run on the Qt render thread with its compatibility GL context current.
#include <windows.h>
#include "core/gpupixel_context.h"
#include <stdexcept>
namespace gpupixel {
GPUPixelContext* GPUPixelContext::instance_ = nullptr;
std::mutex GPUPixelContext::mutex_;
GPUPixelContext::GPUPixelContext():framebuffer_factory_(nullptr),current_shader_program_(nullptr),gl_context_(nullptr) {
 CreateContext(); framebuffer_factory_=new FramebufferFactory();
}
GPUPixelContext::~GPUPixelContext(){ delete framebuffer_factory_; }
GPUPixelContext* GPUPixelContext::GetInstance(){
 if(!instance_){std::lock_guard<std::mutex> lock(mutex_);if(!instance_)instance_=new GPUPixelContext();}return instance_;
}
void GPUPixelContext::Destroy(){delete instance_;instance_=nullptr;}
FramebufferFactory* GPUPixelContext::GetFramebufferFactory() const{return framebuffer_factory_;}
void GPUPixelContext::SetActiveGlProgram(GPUPixelGLProgram* program){
 // mpv and Qt also bind programs; an SDK-private cache cannot describe host GL state.
 current_shader_program_=program;program->UseProgram();
 const auto position=program->GetAttribLocation("position");
 if(position>=0)glEnableVertexAttribArray(static_cast<GLuint>(position));
}
void GPUPixelContext::Clean(){framebuffer_factory_->Clean();}
void GPUPixelContext::Init(){CreateContext();}
void GPUPixelContext::CreateContext(){if(!wglGetCurrentContext()||!gladLoadGL())throw std::runtime_error("GPUPixel requires a current OpenGL context");}
void GPUPixelContext::ReleaseContext(){}
void GPUPixelContext::UseAsCurrent(){if(!wglGetCurrentContext())throw std::runtime_error("GPUPixel context is not current");}
void GPUPixelContext::PresentBufferForDisplay(){}
void GPUPixelContext::SyncRunWithContext(std::function<void()> task){UseAsCurrent();task();}
}
