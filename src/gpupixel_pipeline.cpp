#include "gpupixel_pipeline.h"
#include "gpupixel/gpupixel.h"
#include "core/gpupixel_context.h"
#include "core/gpupixel_framebuffer.h"
#include <QDir>
#include <QFileInfo>
#include <algorithm>
#include <stdexcept>
struct GPUPixelPipeline::Impl {
 std::shared_ptr<gpupixel::BeautyFaceFilter> beauty;
 std::shared_ptr<gpupixel::GPUPixelFramebuffer> input;
};
GPUPixelPipeline::GPUPixelPipeline()=default;
GPUPixelPipeline::~GPUPixelPipeline()=default;
bool GPUPixelPipeline::initialize(const QString& root,QString& error){
 try{
  if(!gladLoadGL())throw std::runtime_error("GPUPixel host GL loader failed");
  const QString path=QDir(root).filePath("app/gpupixel");
  for(const char* file:{"lookup_gray.png","lookup_origin.png","lookup_skin.png","lookup_light.png"})
   if(!QFileInfo::exists(QDir(path).filePath(QString("res/")+file)))throw std::runtime_error("GPUPixel lookup resource missing");
  gpupixel::GPUPixel::SetResourcePath(path.toUtf8().toStdString());
  impl_=std::make_unique<Impl>();
  glBindVertexArray(0);
  glBindBuffer(GL_ARRAY_BUFFER,0);glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);
  impl_->beauty=gpupixel::BeautyFaceFilter::Create();
  if(!impl_->beauty)throw std::runtime_error("GPUPixel shader initialization failed");
  impl_->beauty->SetBlurAlpha(0);impl_->beauty->SetWhite(0);impl_->beauty->SetSharpen(0);
  glBindVertexArray(0);return true;
 }catch(const std::exception& e){error=QString::fromUtf8(e.what());impl_.reset();return false;}
}
unsigned int GPUPixelPipeline::render(unsigned int sourceFbo,int width,int height,const QJsonObject& p){
 if(!impl_||!impl_->beauty)return 0;
 glBindVertexArray(0);glBindBuffer(GL_ARRAY_BUFFER,0);glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0);
 for(GLuint i=0;i<8;++i)glDisableVertexAttribArray(i);
 glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_SCISSOR_TEST);glDisable(GL_CULL_FACE);
 glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
 if(!impl_->input||impl_->input->GetWidth()!=width||impl_->input->GetHeight()!=height)
  impl_->input=std::make_shared<gpupixel::GPUPixelFramebuffer>(width,height);
 glBindFramebuffer(GL_READ_FRAMEBUFFER,sourceFbo);glBindFramebuffer(GL_DRAW_FRAMEBUFFER,impl_->input->GetFramebuffer());
 glBlitFramebuffer(0,0,width,height,0,0,width,height,GL_COLOR_BUFFER_BIT,GL_NEAREST);
 auto val=[&](const char* key){return static_cast<float>(p.value(key).toDouble());};
 const float blur=std::clamp(val("smooth")/150.f,0.f,1.333f);
 const float sharpen=std::clamp((blur>0.f?val("detail")/150.f*.25f:0.f)+val("sharp")/150.f*.4f,0.f,.65f);
 // Upstream's desktop shader gates sharpening on blurAlpha > 0. Keep the independent
 // clarity control usable at zero smoothing without a visible smoothing contribution.
 impl_->beauty->SetBlurAlpha(std::max(blur,sharpen>0.f?1.e-6f:0.f));
 impl_->beauty->SetWhite(std::clamp(val("white")/200.f,0.f,1.f));
 impl_->beauty->SetSharpen(sharpen);
 impl_->beauty->SetInputFramebuffer(impl_->input);impl_->beauty->Render();
 auto output=impl_->beauty->GetFramebuffer();glBindVertexArray(0);return output?output->GetTexture():0;
}
void GPUPixelPipeline::release(){impl_.reset();gpupixel::GPUPixelContext::Destroy();}
