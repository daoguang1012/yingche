// Thin texture bridge. All beauty passes and LUTs are GPUPixel 1.3.0 upstream.
#include "gpupixel/gpupixel.h"
#include "core/gpupixel_context.h"
#include "core/gpupixel_framebuffer.h"
#include <algorithm>
#include <stdexcept>
namespace {
std::shared_ptr<gpupixel::BeautyFaceFilter> beauty;
std::shared_ptr<gpupixel::GPUPixelFramebuffer> input;
GLuint readFbo=0;
std::string lastError;
void boundary(){
  glBindVertexArray(0);
  glBindBuffer(GL_ARRAY_BUFFER,0);glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0);
  glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
  for(GLuint i=0;i<8;i++){glDisableVertexAttribArray(i);glBindSampler(i,0);}
  glPixelStorei(GL_UNPACK_ALIGNMENT,4);glPixelStorei(GL_UNPACK_ROW_LENGTH,0);
  glPixelStorei(GL_UNPACK_SKIP_ROWS,0);glPixelStorei(GL_UNPACK_SKIP_PIXELS,0);
  glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_SCISSOR_TEST);glDisable(GL_CULL_FACE);
  glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
}
}
extern "C" {
EMSCRIPTEN_KEEPALIVE const char* yingche_version(){return "GPUPixel 1.3.0 / 5415b738 / WASM";}
EMSCRIPTEN_KEEPALIVE const char* yingche_error(){return lastError.c_str();}
EMSCRIPTEN_KEEPALIVE int yingche_init(){
  try{
    gpupixel::GPUPixelContext::GetInstance()->UseAsCurrent();boundary();
    gpupixel::GPUPixel::SetResourcePath("/gpupixel");
    beauty=gpupixel::BeautyFaceFilter::Create();
    if(!beauty)throw std::runtime_error("BeautyFaceFilter initialization failed");
    glGenFramebuffers(1,&readFbo);
    if(glGetError()!=GL_NO_ERROR)throw std::runtime_error("GPUPixel WebGL initialization error");
    return 1;
  }catch(const std::exception& e){lastError=e.what();return 0;}
}
EMSCRIPTEN_KEEPALIVE unsigned yingche_render(unsigned texture,int sw,int sh,int width,int height,
                                             float smooth,float detail,float white,float sharp){
  try{
    if(!beauty||!texture||width<2||height<2)return 0;
    gpupixel::GPUPixelContext::GetInstance()->UseAsCurrent();boundary();
    if(!input||input->GetWidth()!=width||input->GetHeight()!=height)
      input=std::make_shared<gpupixel::GPUPixelFramebuffer>(width,height);
    glBindFramebuffer(GL_READ_FRAMEBUFFER,readFbo);
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,texture,0);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER,input->GetFramebuffer());
    glBlitFramebuffer(0,0,sw,sh,0,0,width,height,GL_COLOR_BUFFER_BIT,GL_LINEAR);
    float blur=std::clamp(smooth/150.f,0.f,1.333f);
    float sharpen=std::clamp((blur>0?detail/150.f*.25f:0.f)+sharp/150.f*.4f,0.f,.65f);
    beauty->SetBlurAlpha(std::max(blur,sharpen>0?1.e-6f:0.f));
    beauty->SetSharpen(sharpen);beauty->SetWhite(std::clamp(white/200.f,0.f,1.f));
    beauty->SetInputFramebuffer(input);beauty->Render();
    auto output=beauty->GetFramebuffer();
    glBindFramebuffer(GL_FRAMEBUFFER,0);glBindVertexArray(0);
    return output?output->GetTexture():0;
  }catch(const std::exception& e){lastError=e.what();return 0;}
}
EMSCRIPTEN_KEEPALIVE void yingche_release(){
  beauty.reset();input.reset();
  if(readFbo)glDeleteFramebuffers(1,&readFbo);readFbo=0;
  gpupixel::GPUPixelContext::Destroy();
}
}
