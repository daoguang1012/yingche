#include "video.h"
#include <QBuffer>
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonDocument>
#include <QMouseEvent>
#include <QOpenGLContext>
#include <QPainter>
#include <QThread>
#include <cmath>
#include <algorithm>
#include <vector>
#include <stdexcept>

VideoWidget::VideoWidget(const QString& root,QWidget* parent):QOpenGLWidget(parent),root_(root) {
    setObjectName("videoCanvas"); setAccessibleName("视频画面");
    setMinimumSize(360,220); setFocusPolicy(Qt::StrongFocus);
    clock_.start();
    connect(this,&QOpenGLWidget::frameSwapped,this,[this]{ if(context_&&!stopping_) api_.render_context_report_swap(context_); });
    analysisTimer_.setInterval(8); analysisTimer_.setTimerType(Qt::PreciseTimer);
    connect(&analysisTimer_,&QTimer::timeout,this,&VideoWidget::submitAnalysis);
    transitionTimer_.setInterval(25);
    connect(&transitionTimer_,&QTimer::timeout,this,[this]{
        if(beautyTransitionPending_ || (faceCount_>0 && text("pause")!="yes" && clock_.elapsed()-resultSampleTime_<230))update();
        if(beautyEnabled_ && loaded_ && faceCount_>0 && text("pause")!="yes" && clock_.elapsed()-resultSampleTime_>=200 && !fallbackNotice_) {
            fallbackNotice_=true;emit analysisStatus("跟踪已过期 · 原片，等待新结果");
        }
    });
    transitionTimer_.start();
}
VideoWidget::~VideoWidget() { shutdown(); }
void VideoWidget::shutdown() {
    if(stopping_) return;
    stopping_=true; analysisTimer_.stop();transitionTimer_.stop();
    if(worker_) {
        disconnect(worker_,nullptr,this,nullptr);
        worker_->closeWriteChannel();
        if(!worker_->waitForFinished(1000)) {
            worker_->terminate();
            if(!worker_->waitForFinished(500)) { worker_->kill(); worker_->waitForFinished(1000); }
        }
    }
    if(handle_) api_.set_wakeup_callback(handle_,nullptr,nullptr);
    if(glFunctionsReady_ && isValid()) {
        makeCurrent();
        if(context_) {
            api_.render_context_set_update_callback(context_,nullptr,nullptr);
            api_.render_context_free(context_); context_=nullptr;
        }
        gpupixel_.release(); gpupixelReady_=false;
        frame_.reset(); analysis_.reset(); composite_.reset();cutSample_.reset(); shader_.reset();
        if(maskTexture_) glDeleteTextures(1,&maskTexture_);
        if(swapTexture_) glDeleteTextures(1,&swapTexture_);
        if(vao_) glDeleteVertexArrays(1,&vao_);
        doneCurrent();
    }
    if(handle_) { api_.terminate_destroy(handle_); handle_=nullptr; }
}
void VideoWidget::initializeGL() {
    if(!initializeOpenGLFunctions()) {
        glError_="OpenGL 3.3 初始化失败"; emit errorOccurred(glError_); return;
    }
    glFunctionsReady_=true;
    glGenVertexArrays(1,&vao_);
    glGenTextures(1,&maskTexture_); glGenTextures(1,&swapTexture_);
    for(GLuint texture:{maskTexture_,swapTexture_}) {
        glBindTexture(GL_TEXTURE_2D,texture);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
    }
    mask_=QImage(2,2,QImage::Format_RGBA8888);mask_.fill(Qt::black);
    swapImage_=QImage(2,2,QImage::Format_RGBA8888);swapImage_.fill(Qt::transparent);uploadMask();
    shader_=std::make_unique<QOpenGLShaderProgram>();
    if(!shader_->addShaderFromSourceFile(QOpenGLShader::Vertex,":/src/fullscreen.vert") ||
       !shader_->addShaderFromSourceFile(QOpenGLShader::Fragment,":/src/beauty.frag") || !shader_->link()) {
        glError_=shader_->log(); emit errorOccurred(glError_); return;
    }
    QString error;
    if(!api_.load(QDir(root_).filePath("app/libmpv-2.dll"),error)) {
        glError_="播放内核加载失败："+error; emit errorOccurred(glError_); return;
    }
    handle_=api_.create();
    if(!handle_) { emit errorOccurred("无法创建播放内核"); return; }
    const std::pair<const char*,const char*> options[]={
        {"config","no"},{"terminal","no"},{"vo","libmpv"},{"hwdec","auto-copy"},
        {"idle","yes"},{"keep-open","yes"},{"audio-pitch-correction","yes"},{"video-timing-offset","0"},
        {"input-default-bindings","no"},{"input-vo-keyboard","no"},
        {"osc","no"},{"osd-level","0"},{"keepaspect","no"},
        {"cache","yes"},{"demuxer-max-bytes","96MiB"},
        {"screenshot-format","png"},{"target-colorspace-hint","no"}
    };
    for(const auto& item:options) api_.set_option_string(handle_,item.first,item.second);
    const int init=api_.initialize(handle_);
    if(init<0) { emit errorOccurred(QString::fromUtf8(api_.error_string(init))); return; }
    api_.request_log_messages(handle_,"error");
    api_.set_wakeup_callback(handle_,[](void* p){
        QMetaObject::invokeMethod(static_cast<VideoWidget*>(p),&VideoWidget::pollEvents,Qt::QueuedConnection);
    },this);
    mpv_opengl_init_params glInit{[](void*,const char* name)->void*{
        return reinterpret_cast<void*>(QOpenGLContext::currentContext()->getProcAddress(name));
    },nullptr};
    mpv_render_param params[]={
        {MPV_RENDER_PARAM_API_TYPE,const_cast<char*>(MPV_RENDER_API_TYPE_OPENGL)},
        {MPV_RENDER_PARAM_OPENGL_INIT_PARAMS,&glInit},{MPV_RENDER_PARAM_INVALID,nullptr}};
    const int rc=api_.render_context_create(&context_,handle_,params);
    if(rc<0) { emit errorOccurred("视频渲染初始化失败："+QString::fromUtf8(api_.error_string(rc))); return; }
    api_.render_context_set_update_callback(context_,[](void* p){
        QMetaObject::invokeMethod(static_cast<VideoWidget*>(p),&VideoWidget::renderUpdate,Qt::QueuedConnection);
    },this);
    for(const char* name:{"time-pos","duration","speed","volume","dwidth","dheight","avsync","frame-drop-count","decoder-frame-drop-count","estimated-vf-fps"})
        api_.observe_property(handle_,0,name,MPV_FORMAT_DOUBLE);
    for(const char* name:{"pause","mute","eof-reached","video-format","hwdec-current","aid","sid"})
        api_.observe_property(handle_,0,name,MPV_FORMAT_STRING);
    api_.observe_property(handle_,0,"track-list",MPV_FORMAT_NODE);
    for(int i=0;i<8;++i)glBindSampler(i,0);
    gpupixelReady_=gpupixel_.initialize(root_,gpupixelError_);
    resetGLBoundary();
    if(!gpupixelReady_)emit errorOccurred("GPUPixel 初始化失败："+gpupixelError_);
    startWorker(); analysisTimer_.start();
    emit ready();
    if(!pendingFile_.isEmpty()) { const QString path=pendingFile_; pendingFile_.clear(); loadFile(path); }
}
void VideoWidget::renderUpdate() {
    if(stopping_||!context_) return;
    needFrame_=true; update();
}
void VideoWidget::paintGL() {
    if(!glFunctionsReady_) {
        QPainter painter(this);
        painter.fillRect(rect(),QColor("#10181b"));
        painter.setPen(Qt::white);
        painter.drawText(rect(),Qt::AlignCenter,glError_);
        return;
    }
    const qreal dpr=devicePixelRatioF();
    const int pw=qRound(width()*dpr), ph=qRound(height()*dpr);
    glBindFramebuffer(GL_FRAMEBUFFER,defaultFramebufferObject());
    glViewport(0,0,pw,ph); glClearColor(.027f,.035f,.043f,1.f); glClear(GL_COLOR_BUFFER_BIT);
    if(!context_||!loaded_) {
        QPainter p(this); p.setRenderHint(QPainter::Antialiasing);
        p.setPen(QColor("#e6efed")); QFont title=font(); title.setPointSize(24); title.setWeight(QFont::DemiBold); p.setFont(title);
        p.drawText(rect().adjusted(24,0,-24,-50),Qt::AlignCenter,"映澈");
        QFont sub=font(); sub.setPointSize(11); p.setFont(sub); p.setPen(QColor("#829493"));
        p.drawText(rect().adjusted(24,55,-24,0),Qt::AlignCenter,glError_.isEmpty()?"拖入视频，即刻播放\nCtrl + O 打开文件":glError_);
        return;
    }
    const double dw=number("dwidth",16),dh=number("dheight",9);
    const double aspect=dw/(std::max)(1.,dh);
    int vw=pw,vh=qRound(pw/aspect);
    if(vh>ph) { vh=ph; vw=qRound(ph*aspect); }
    vw=(std::max)(2,vw); vh=(std::max)(2,vh);
    // Bound internal rendering cost on very high-DPI windows, preserving aspect.
    QSize renderSize(vw,vh);
    renderSize.scale(2560,1440,Qt::KeepAspectRatio);
    if(renderSize.width()>vw) renderSize=QSize(vw,vh);
    bool resized=false;
    if(!frame_||frame_->size()!=renderSize) {
        QOpenGLFramebufferObjectFormat fmt; fmt.setInternalTextureFormat(GL_RGBA8);
        frame_=std::make_unique<QOpenGLFramebufferObject>(renderSize,fmt);
        if(!frame_->isValid()) { glError_="无法分配视频画面缓冲"; emit errorOccurred(glError_); return; }
        resized=true;
    }
    if(needFrame_||resized) {
        resetGLBoundary();
        api_.render_context_update(context_);
        mpv_opengl_fbo fbo{static_cast<int>(frame_->handle()),renderSize.width(),renderSize.height(),GL_RGBA8};
        int flip=1,block=0;
        mpv_render_param params[]={{MPV_RENDER_PARAM_OPENGL_FBO,&fbo},
            {MPV_RENDER_PARAM_FLIP_Y,&flip},{MPV_RENDER_PARAM_BLOCK_FOR_TARGET_TIME,&block},
            {MPV_RENDER_PARAM_INVALID,nullptr}};
        api_.render_context_render(context_,params);
        needFrame_=false; ++rendered_;
        if(beautyEnabled_||swapEnabled_) {
            QElapsedTimer cutClock;cutClock.start();
            if(!cutSample_)cutSample_=std::make_unique<QOpenGLFramebufferObject>(QSize(32,18));
            QOpenGLFramebufferObject::blitFramebuffer(cutSample_.get(),QRect(0,0,32,18),frame_.get(),QRect(QPoint(),frame_->size()),GL_COLOR_BUFFER_BIT,GL_LINEAR);
            const QImage sample=cutSample_->toImage().convertToFormat(QImage::Format_RGB32);
            const double ms=cutClock.nsecsElapsed()/1000000.;cutReadbackMs_+=ms;cutReadbackMaxMs_=(std::max)(cutReadbackMaxMs_,ms);++cutReadbackSamples_;
            if(!previousCutSample_.isNull() && sample.size()==previousCutSample_.size()) {
                double sum=0.;int changed=0;
                for(int y=0;y<18;++y)for(int x=0;x<32;++x) {
                    const auto a=sample.pixel(x,y),b=previousCutSample_.pixel(x,y);
                    const double delta=(std::abs(qRed(a)-qRed(b))+std::abs(qGreen(a)-qGreen(b))+std::abs(qBlue(a)-qBlue(b)))/3.;
                    sum+=delta;if(delta>32.)++changed;
                }
                if(sum/576.>35. && changed>288) {invalidateFaces();++cuts_;}
            }
            previousCutSample_=sample;
        }
    }
    const double age=std::abs(number("time-pos")-resultPts_);
    const double maxAge=.20*(std::max)(1.,number("speed",1.));
    const bool valid=resultGeneration_==generation_ && age<=maxAge && workerReady_;
    const double wallAge=text("pause")=="yes" && age<.04 ? 0. : std::max(0.,clock_.elapsed()-resultSampleTime_);
    const float trackingWeight=valid?static_cast<float>(std::clamp((200.-wallAge)/80.,0.,1.)):0.f;
    trackingWeight_=trackingWeight;
    auto predicted=points_;
    std::array<QVector2D,4> offsets{};
    const float ahead=text("pause")=="yes"?0.f:static_cast<float>(std::min(wallAge/1000.,.060));
    if(valid)for(int i=0;i<faceCount_;++i) {
        offsets[i]=velocities_[i]*ahead;
        const float bound=(points_[i*8+2]-points_[i*8+3]).length()*.25f;
        if(offsets[i].length()>bound && bound>0.f)offsets[i]=offsets[i].normalized()*bound;
        for(int j=0;j<8;++j)predicted[i*8+j]+=offsets[i];
    }
    if(maskDirty_)uploadMask();
    const bool useSwap=!originalPreview_&&swapEnabled_&&swapSourceReady_&&valid&&swapFaces_>0&&swapStrength_>0&&trackingWeight>0;
    unsigned int inputFbo=frame_->handle(),inputTexture=frame_->texture();
    if(useSwap) {
        if(!composite_||composite_->size()!=renderSize) {
            QOpenGLFramebufferObjectFormat fmt;fmt.setInternalTextureFormat(GL_RGBA8);
            composite_=std::make_unique<QOpenGLFramebufferObject>(renderSize,fmt);
        }
        if(!composite_->isValid()){emit errorOccurred("无法分配换脸画面缓冲");return;}
        glBindFramebuffer(GL_FRAMEBUFFER,composite_->handle());glViewport(0,0,renderSize.width(),renderSize.height());
        glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_SCISSOR_TEST);
        shader_->bind();
        glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,frame_->texture());
        glActiveTexture(GL_TEXTURE2);glBindTexture(GL_TEXTURE_2D,swapTexture_);
        glActiveTexture(GL_TEXTURE3);glBindTexture(GL_TEXTURE_2D,frame_->texture());
        shader_->setUniformValue("frameTex",0);shader_->setUniformValue("swapTex",2);shader_->setUniformValue("originalTex",3);
        shader_->setUniformValue("enabled",0);shader_->setUniformValue("compareMode",0);
        shader_->setUniformValue("swapEnabled",1);shader_->setUniformValue("swapPrecomposed",0);
        shader_->setUniformValue("swapStrength",swapStrength_/100.f*trackingWeight);
        shader_->setUniformValue("faceCount",0);shader_->setUniformValue("trackedFaceCount",faceCount_);
        shader_->setUniformValue("imageSize",QVector2D(renderSize.width(),renderSize.height()));
        shader_->setUniformValueArray("points",predicted.data(),32);shader_->setUniformValueArray("faceMotion",offsets.data(),4);
        glBindVertexArray(vao_);glDrawArrays(GL_TRIANGLES,0,3);glBindVertexArray(0);shader_->release();
        inputFbo=composite_->handle();inputTexture=composite_->texture();
    }
    const double blend=std::clamp((clock_.elapsed()-beautyChangedAt_)/180.,0.,1.);
    for(const auto& p:parameters) {
        const double a=transitionFromBeauty_.value(p.key).toDouble(),b=beauty_.value(p.key).toDouble();
        const double value=a+(b-a)*blend;
        if(std::abs(displayedBeauty_.value(p.key).toDouble()-value)>.000001)gpupixelDirty_=true;
        displayedBeauty_[p.key]=value;
    }
    if(blend>=1.)beautyTransitionPending_=false;
    bool useGPUPixel=!originalPreview_&&beautyEnabled_&&beautyEngine_=="gpupixel"&&gpupixelReady_&&valid&&faceCount_>0&&trackingWeight>0;
    if(useGPUPixel && (gpupixelFrame_!=rendered_||gpupixelDirty_||useSwap)) {
        for(int i=0;i<8;++i)glBindSampler(i,0);
        try {gpupixelTexture_=gpupixel_.render(inputFbo,renderSize.width(),renderSize.height(),displayedBeauty_);}
        catch(const std::exception& error) {gpupixelTexture_=0;gpupixelError_=QString::fromUtf8(error.what());}
        if(!gpupixelTexture_) {gpupixelReady_=false;emit errorOccurred("美颜渲染不可用 · 已回原片");emit analysisStatus("肤质引擎不可用 · 原片");}
        gpupixelFrame_=rendered_;gpupixelDirty_=false;
    }
    useGPUPixel=useGPUPixel&&gpupixelTexture_!=0;
    glBindFramebuffer(GL_FRAMEBUFFER,defaultFramebufferObject());
    glViewport((pw-vw)/2,(ph-vh)/2,vw,vh);
    glDisable(GL_DEPTH_TEST); glDisable(GL_BLEND); glDisable(GL_SCISSOR_TEST);
    if(maskDirty_) uploadMask();
    shader_->bind();
    glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D,useGPUPixel?gpupixelTexture_:inputTexture);
    glActiveTexture(GL_TEXTURE3); glBindTexture(GL_TEXTURE_2D,frame_->texture());
    glActiveTexture(GL_TEXTURE4); glBindTexture(GL_TEXTURE_2D,inputTexture);
    glActiveTexture(GL_TEXTURE1); glBindTexture(GL_TEXTURE_2D,maskTexture_);
    glActiveTexture(GL_TEXTURE2); glBindTexture(GL_TEXTURE_2D,swapTexture_);
    shader_->setUniformValue("originalTex",3); shader_->setUniformValue("gpupixelEnabled",useGPUPixel?1:0);
    shader_->setUniformValue("baseTex",4);
    shader_->setUniformValue("frameTex",0); shader_->setUniformValue("regionTex",1); shader_->setUniformValue("swapTex",2);
    shader_->setUniformValue("texel",QVector2D(1.f/renderSize.width(),1.f/renderSize.height()));
    shader_->setUniformValue("imageSize",QVector2D(renderSize.width(),renderSize.height()));
    shader_->setUniformValue("trackingWeight",trackingWeight);
    shader_->setUniformValue("enabled",beautyEnabled_&&useGPUPixel?1:0);
    shader_->setUniformValue("compareMode",compare_?1:0);
    shader_->setUniformValue("swapEnabled",useSwap?1:0);
    shader_->setUniformValue("swapPrecomposed",1);
    shader_->setUniformValue("swapStrength",swapStrength_/100.f);
    shader_->setUniformValue("trackedFaceCount",valid?faceCount_:0);
    shader_->setUniformValue("faceCount",valid&&beautyEnabled_&&useGPUPixel?faceCount_:0);
    shader_->setUniformValueArray("points",predicted.data(),32);
    shader_->setUniformValueArray("faceMotion",offsets.data(),4);
    shader_->setUniformValueArray("effectWeights",effectWeights_.data(),4,1);
    for(const auto& param:parameters)
        shader_->setUniformValue((QByteArray(param.key)+"Value").constData(),static_cast<float>(displayedBeauty_.value(param.key).toDouble()));
    glBindVertexArray(vao_); glDrawArrays(GL_TRIANGLES,0,3); glBindVertexArray(0);
    shader_->release();resetGLBoundary();
}
void VideoWidget::resetGLBoundary() {
    // libmpv requires GL defaults. GPUPixel uses client attributes and 8 texture units.
    glUseProgram(0);glBindVertexArray(0);
    for(GLuint i=0;i<8;++i) {
        glDisableVertexAttribArray(i);glActiveTexture(GL_TEXTURE0+i);
        glBindTexture(GL_TEXTURE_2D,0);glBindSampler(i,0);
    }
    glActiveTexture(GL_TEXTURE0);glBindBuffer(GL_ARRAY_BUFFER,0);glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0);
    glBindBuffer(GL_PIXEL_PACK_BUFFER,0);glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);
    for(GLenum key:{GL_PACK_ROW_LENGTH,GL_PACK_SKIP_ROWS,GL_PACK_SKIP_PIXELS,GL_UNPACK_ROW_LENGTH,GL_UNPACK_SKIP_ROWS,GL_UNPACK_SKIP_PIXELS})glPixelStorei(key,0);
    glPixelStorei(GL_PACK_ALIGNMENT,4);glPixelStorei(GL_UNPACK_ALIGNMENT,4);
    glDisable(GL_DEPTH_TEST);glDisable(GL_BLEND);glDisable(GL_CULL_FACE);glDisable(GL_SCISSOR_TEST);
    glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
}
void VideoWidget::uploadMask() {
    const QImage masks[]={mask_.convertToFormat(QImage::Format_RGBA8888),swapImage_.convertToFormat(QImage::Format_RGBA8888)};
    const GLuint textures[]={maskTexture_,swapTexture_};
    for(int i=0;i<2;++i) {
        glActiveTexture(GL_TEXTURE1+i);glBindTexture(GL_TEXTURE_2D,textures[i]);
        glPixelStorei(GL_UNPACK_ALIGNMENT,4);
        glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,masks[i].width(),masks[i].height(),0,GL_RGBA,GL_UNSIGNED_BYTE,masks[i].constBits());
    }
    maskDirty_=false;glActiveTexture(GL_TEXTURE0);
}
void VideoWidget::pollEvents() {
    if(stopping_||!handle_) return;
    for(;;) {
        mpv_event* ev=api_.wait_event(handle_,0);
        if(ev->event_id==MPV_EVENT_NONE) break;
        if(ev->event_id==MPV_EVENT_FILE_LOADED) { loaded_=true; invalidateFaces(); needFrame_=true; emit fileLoaded(); update(); }
        else if(ev->event_id==MPV_EVENT_START_FILE) { awaitingPlayback_=true; loaded_=false; invalidateFaces(); update(); }
        else if(ev->event_id==MPV_EVENT_SEEK) { awaitingPlayback_=true; invalidateFaces(); }
        else if(ev->event_id==MPV_EVENT_PLAYBACK_RESTART) { awaitingPlayback_=false; needFrame_=true; submittedFrame_=-1;update(); }
        else if(ev->event_id==MPV_EVENT_END_FILE) {
            const auto* end=static_cast<mpv_event_end_file*>(ev->data);
            if(end && end->reason==MPV_END_FILE_REASON_ERROR) {
                loaded_=false; emit errorOccurred("无法播放："+QString::fromUtf8(api_.error_string(end->error))); update();
            } else if(end && end->reason==MPV_END_FILE_REASON_EOF && !eofSignaled_) { eofSignaled_=true; emit ended(); }
        } else if(ev->event_id==MPV_EVENT_PROPERTY_CHANGE) {
            const auto* changed=static_cast<const mpv_event_property*>(ev->data);
            if(changed && changed->name && changed->data) {
                const QString name=QString::fromUtf8(changed->name);
                if(changed->format==MPV_FORMAT_DOUBLE)
                    properties_[name]=*static_cast<double*>(changed->data);
                else if(changed->format==MPV_FORMAT_STRING)
                    properties_[name]=QString::fromUtf8(*static_cast<char**>(changed->data));
                else if(changed->format==MPV_FORMAT_NODE && name=="track-list") {
                    tracks_=QJsonArray();
                    const auto* node=static_cast<mpv_node*>(changed->data);
                    if(node->format==MPV_FORMAT_NODE_ARRAY && node->u.list) {
                        for(int i=0;i<(std::min)(node->u.list->num,100);++i) {
                            const auto& entry=node->u.list->values[i];
                            if(entry.format!=MPV_FORMAT_NODE_MAP || !entry.u.list) continue;
                            QJsonObject track;
                            for(int j=0;j<entry.u.list->num;++j) {
                                const auto& value=entry.u.list->values[j];
                                QString str;
                                if(value.format==MPV_FORMAT_STRING) str=QString::fromUtf8(value.u.string);
                                else if(value.format==MPV_FORMAT_INT64) str=QString::number(value.u.int64);
                                else if(value.format==MPV_FORMAT_FLAG) str=value.u.flag?"yes":"no";
                                track[QString::fromUtf8(entry.u.list->keys[j])]=str;
                            }
                            tracks_.append(track);
                        }
                    }
                }
                if(name=="eof-reached") {
                    const bool eof=properties_.value(name).toString()=="yes";
                    if(eof && loaded_ && !eofSignaled_) { eofSignaled_=true; emit ended(); }
                    else if(!eof) eofSignaled_=false;
                }
            }
            emit playbackChanged();
        }
        else if(ev->event_id==MPV_EVENT_COMMAND_REPLY && ev->error<0) emit errorOccurred(QString::fromUtf8(api_.error_string(ev->error)));
    }
}
void VideoWidget::command(const QStringList& args) {
    if(!handle_||stopping_) return;
    QList<QByteArray> utf8; for(const auto& a:args) utf8.append(a.toUtf8());
    std::vector<const char*> raw; for(const auto& a:utf8) raw.push_back(a.constData()); raw.push_back(nullptr);
    const int rc=api_.command_async(handle_,0,raw.data());
    if(rc<0) emit errorOccurred(QString::fromUtf8(api_.error_string(rc)));
}
void VideoWidget::property(const QString& name,const QString& value) {
    if(name=="speed" && std::abs(value.toDouble()-number("speed",1.))>.001)invalidateFaces();
    command({"set",name,value});
}
void VideoWidget::loadFile(const QString& path) {
    if(!isReady()) { pendingFile_=path; return; }
    displayedBeauty_=beauty_;transitionFromBeauty_=beauty_;beautyTransitionPending_=false;
    awaitingPlayback_=true; loaded_=false; eofSignaled_=false; properties_.remove("duration"); properties_.remove("time-pos"); properties_.remove("video-format");
    invalidateFaces(); update(); command({"loadfile",path,"replace"}); property("pause","no");
}
void VideoWidget::seek(double seconds,bool relative) {
    if(!std::isfinite(seconds)) return;
    awaitingPlayback_=true;invalidateFaces();
    command({"seek",QString::number(seconds,'f',3),relative?"relative+exact":"absolute+exact"});
}
double VideoWidget::number(const char* name,double fallback) const {
    const auto found=properties_.constFind(QString::fromLatin1(name));
    if(found==properties_.cend()) return fallback;
    bool ok=false;
    const double value=found.value().toDouble(&ok);
    return ok&&std::isfinite(value)?value:fallback;
}
QString VideoWidget::text(const char* name) const {
    return properties_.value(QString::fromLatin1(name)).toString();
}
QJsonArray VideoWidget::tracks() const { return tracks_; }
void VideoWidget::setBeauty(const QJsonObject& v) {
    transitionFromBeauty_=displayedBeauty_;beautyChangedAt_=clock_.elapsed();beautyTransitionPending_=true;beauty_=sanitizeBeauty(v);gpupixelDirty_=true;update();
}
void VideoWidget::setBeautyEnabled(bool v) { beautyEnabled_=v; if(v) invalidateFaces(); update(); }
void VideoWidget::setCompare(bool v) { compare_=v; update(); }
void VideoWidget::setOriginalPreview(bool v) {originalPreview_=v;update();}
void VideoWidget::setSwapEnabled(bool value) {
    swapEnabled_=value;analysisTimer_.setInterval(8);invalidateFaces();
}
void VideoWidget::setSwapSource(const QString& path) {
    sourcePath_=path;sourcePending_=true;swapSourceReady_=false;invalidateFaces();
    if(worker_ && worker_->state()==QProcess::NotRunning) startWorker();
    emit swapStatus(path.isEmpty()?"正在清除源照片":"正在加载源照片与换脸模型…");
}
void VideoWidget::setSwapOptions(const QString& target,int feather,int strength) {
    swapTarget_=target;swapFeather_=std::clamp(feather,0,100);swapStrength_=std::clamp(strength,0,100);invalidateFaces();
}
void VideoWidget::setBeautyEngine(const QString& engine) {
    Q_UNUSED(engine);beautyEngine_="gpupixel";gpupixelDirty_=true;update();
}
void VideoWidget::invalidateFaces() {
    previousCutSample_=QImage();trackingWeight_=0.;effectWeights_.fill(0.f);faceSignals_=QJsonArray();fallbackNotice_=false;
    swapImage_=QImage(2,2,QImage::Format_RGBA8888);swapImage_.fill(Qt::transparent);swapFaces_=0;
    gpupixelDirty_=true;swapPending_=false;
    ++generation_; velocities_.fill(QVector2D()); faceCount_=0; resultGeneration_=-1; resultPts_=-999.;
    mask_=QImage(2,2,QImage::Format_RGBA8888); mask_.fill(Qt::black); maskDirty_=true; update();
}
void VideoWidget::startWorker() {
    if(worker_) { disconnect(worker_,nullptr,this,nullptr);worker_->deleteLater(); }
    workerReady_=false;busy_=false;sourceBusy_=false;swapSourceReady_=false;workerBuffer_.clear();workerError_.clear();
    worker_=new QProcess(this);
    connect(worker_,&QProcess::readyReadStandardOutput,this,&VideoWidget::workerOutput);
    connect(worker_,&QProcess::readyReadStandardError,this,[this]{
        const auto err=worker_->readAllStandardError();
        if(workerError_.size()<4000) workerError_+=QString::fromUtf8(err).left(4000-workerError_.size());
    });
    connect(worker_,&QProcess::errorOccurred,this,[this](QProcess::ProcessError){
        workerReady_=false; busy_=false; faceCount_=0;
        emit analysisStatus("人脸引擎不可用 · 局部效果暂停");
    });
    connect(worker_,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int,QProcess::ExitStatus){
        workerReady_=false; busy_=false; invalidateFaces();
        if(!stopping_) emit analysisStatus("人脸引擎已停止 · 局部效果暂停");
    });
    const QString packaged=QDir(root_).filePath("app/face_engine_v061/FaceEngine.exe");
    if(QFileInfo::exists(packaged)) worker_->start(packaged,{QDir(root_).filePath("models/face_landmarker.task")});
    else worker_->start(QDir(root_).filePath("tools/python/Scripts/python.exe"),
        {"-u",QDir(root_).filePath("tools/face_worker.py"),QDir(root_).filePath("models/face_landmarker.task")});
    emit analysisStatus("人脸引擎准备中");
}
void VideoWidget::submitAnalysis() {
    if(stopping_||!workerReady_) return;
    if(busy_) {
        if(clock_.elapsed()-submittedAt_>(sourceBusy_?60000:12000)) {
            worker_->kill(); workerReady_=false; busy_=false; invalidateFaces();
            emit analysisStatus("人脸分析超时 · 局部效果暂停");
            if(sourceBusy_) emit swapStatus("源照片加载超时，请重新选择照片重试");
        }
        return;
    }
    if(sourcePending_) {
        QJsonObject command{{"id",++requestId_},{"action",sourcePath_.isEmpty()?"clear-source":"source"},{"path",sourcePath_}};
        const auto payload=QJsonDocument(command).toJson(QJsonDocument::Compact)+'\n';
        if(worker_->write(payload)!=payload.size()) {emit swapStatus("源照片发送失败");return;}
        sourcePending_=false;sourceBusy_=true;busy_=true;submittedAt_=clock_.elapsed();return;
    }
    if(awaitingPlayback_||!loaded_||(!beautyEnabled_&&!swapEnabled_)||!frame_||needFrame_||!isVisible()) return;
    if(!swapPending_ && rendered_==submittedFrame_ && resultGeneration_==generation_) return;
    const double pts=number("time-pos");
    if(!swapPending_ && text("pause")=="yes" && resultGeneration_==generation_ && resultFrame_==rendered_ && std::abs(pts-resultPts_)<.002) return;
    makeCurrent();
    QSize s=frame_->size(); if(s.width()>960||s.height()>720)s.scale(960,720,Qt::KeepAspectRatio);
    if(!analysis_||analysis_->size()!=s) analysis_=std::make_unique<QOpenGLFramebufferObject>(s);
    QOpenGLFramebufferObject::blitFramebuffer(analysis_.get(),QRect(QPoint(),s),frame_.get(),QRect(QPoint(),frame_->size()),GL_COLOR_BUFFER_BIT,GL_LINEAR);
    const QImage image=analysis_->toImage().convertToFormat(QImage::Format_RGBA8888);
    glBindFramebuffer(GL_FRAMEBUFFER,defaultFramebufferObject()); doneCurrent();
    if(image.isNull()) return;
    const QByteArray rgba(reinterpret_cast<const char*>(image.constBits()),image.sizeInBytes());
    QJsonObject req{{"id",++requestId_},{"generation",generation_},{"pts",pts},
        {"width",image.width()},{"height",image.height()},{"rawBytes",rgba.size()},{"sampleTime",double(clock_.elapsed())},
        {"paused",text("pause")=="yes"},{"stableBeauty",true},{"swapEnabled",swapEnabled_&&swapSourceReady_},{"swapTarget",swapTarget_},{"swapFeather",swapFeather_}};
    const QByteArray payload=QJsonDocument(req).toJson(QJsonDocument::Compact)+'\n';
    if(worker_->write(payload)!=payload.size()||worker_->write(rgba)!=rgba.size()) { worker_->kill();emit analysisStatus("人脸引擎通信失败"); return; }
    sourceBusy_=false;busy_=true; submittedFrame_=rendered_; submittedAt_=clock_.elapsed();
}
void VideoWidget::workerOutput() {
    workerBuffer_+=worker_->readAllStandardOutput();
    if(workerBuffer_.size()>8*1024*1024) { workerBuffer_.clear(); worker_->kill(); return; }
    qsizetype nl;
    while((nl=workerBuffer_.indexOf('\n'))>=0) {
        const auto line=workerBuffer_.left(nl); workerBuffer_.remove(0,nl+1);
        QJsonParseError err; const auto doc=QJsonDocument::fromJson(line,&err);
        if(err.error!=QJsonParseError::NoError||!doc.isObject()) continue;
        const auto obj=doc.object();
        if(obj.value("ready").toBool()) { workerReady_=true; emit analysisStatus("人脸引擎就绪"); continue; }
        if(obj.contains("fatal")) { workerError_=obj.value("fatal").toString(); emit analysisStatus("模型加载失败 · 局部效果暂停"); continue; }
        busy_=false;sourceBusy_=false;
        if(obj.contains("sourceReady")) {
            swapSourceReady_=obj.value("sourceReady").toBool();invalidateFaces();
            emit swapStatus(swapSourceReady_?"源照片已就绪 · "+obj.value("provider").toString():"源照片已清除");continue;
        }
        if(obj.value("sourceError").toBool()) {swapSourceReady_=false;emit swapStatus(obj.value("error").toString());continue;}
        if(obj.value("generation").toInt(-1)!=generation_) continue;
        if(obj.contains("error")) { invalidateFaces(); emit analysisStatus("识别失败 · 局部效果暂停"); continue; }
        const double pts=obj.value("pts").toDouble(-999.);
        if(std::abs(pts-number("time-pos"))>.25*(std::max)(1.,number("speed",1.))) continue;
        const auto faces=obj.value("faces").toArray();
        faceSignals_=obj.value("faceSignals").toArray();
        effectWeights_.fill(0.f);const auto weights=obj.value("effectWeights").toArray();
        for(int i=0;i<std::min(4,static_cast<int>(weights.size()));++i)effectWeights_[i]=static_cast<float>(std::clamp(weights[i].toDouble(),0.,1.));
        faceCount_=(std::min)(4,static_cast<int>(faces.size()));
        points_.fill(QVector2D());
        for(int i=0;i<faceCount_;++i) {
            const auto ps=faces[i].toArray();
            if(ps.size()!=8) { faceCount_=0; break; }
            for(int j=0;j<8;++j) { const auto p=ps[j].toArray(); if(p.size()==2) points_[i*8+j]=QVector2D(p[0].toDouble(),p[1].toDouble()); }
        }
        QImage decoded;
        decoded.loadFromData(QByteArray::fromBase64(obj.value("mask").toString().toLatin1()),"PNG");
        if(decoded.isNull()) { invalidateFaces(); continue; }
        QImage swapped;
        if(obj.contains("swap")) swapped.loadFromData(QByteArray::fromBase64(obj.value("swap").toString().toLatin1()),"PNG");
        if(swapped.isNull()) {swapped=QImage(2,2,QImage::Format_RGBA8888);swapped.fill(Qt::transparent);}
        swapImage_=swapped;swapFaces_=obj.value("swapFaces").toInt();swapPending_=obj.value("swapPending").toBool();
        swapMs_=obj.value("swapMs").toDouble();swapAgeMs_=obj.value("swapAgeMs").toDouble();swapError_=obj.value("swapError").toString();
        if(!swapError_.isEmpty())emit swapStatus("换脸失败："+swapError_);
        mask_=decoded; maskDirty_=true;gpupixelDirty_=true; resultPts_=pts; resultGeneration_=generation_;
        resultFrame_=submittedFrame_;
        analysisMs_=obj.value("ms").toDouble();
        resultSampleTime_=obj.value("sampleTime").toDouble(clock_.elapsed());
        roundTripMs_=std::max(0.,clock_.elapsed()-resultSampleTime_);++analysisCompleted_;
        trackingMode_=obj.value("trackingMode").toString();
        velocities_.fill(QVector2D());const auto motion=obj.value("motion").toArray();
        for(int i=0;i<std::min(faceCount_,static_cast<int>(motion.size()));++i) {
            const auto v=motion[i].toArray();if(v.size()==2)velocities_[i]=QVector2D(v[0].toDouble(),v[1].toDouble());
        }
        fallbackNotice_=false;
        emit analysisStatus(!gpupixelReady_?"肤质引擎不可用 · 原片":faceCount_?QString("人像 %1 · 分析 %2 ms%3").arg(faceCount_).arg(analysisMs_,0,'f',0).arg(roundTripMs_>120?" · 延迟较高，效果减弱":""):"未检测到可靠人脸 · 原画");
        update();QTimer::singleShot(0,this,&VideoWidget::submitAnalysis);
    }
}
QJsonObject VideoWidget::diagnostics() const {
    return {{"version","0.6.0"},{"originalPreview",originalPreview_},{"beautyTransitionPending",beautyTransitionPending_},{"cutReadbackMeanMs",cutReadbackSamples_?cutReadbackMs_/cutReadbackSamples_:0.},{"cutReadbackMaxMs",cutReadbackMaxMs_},{"cutReadbackSamples",cutReadbackSamples_},{"trackingWeight",trackingWeight_},{"faceSignals",faceSignals_},{"detectedCuts",cuts_},{"avsyncAvailable",properties_.contains("avsync")},{"dropsAvailable",properties_.contains("frame-drop-count")},{"renderWidth",frame_?frame_->width():0},{"renderHeight",frame_?frame_->height():0},{"swapEngine","Deep-Live-Cam"},{"swapPending",swapPending_},{"swapMs",swapMs_},{"swapAgeMs",swapAgeMs_},{"swapError",swapError_},{"beautyEngine",beautyEngine_},{"gpupixelReady",gpupixelReady_},{"gpupixelError",gpupixelError_},{"analysisCompleted",analysisCompleted_},{"roundTripMs",roundTripMs_},{"trackingAgeMs",double(clock_.elapsed())-resultSampleTime_},{"trackingMode",trackingMode_},
        {"position",number("time-pos")},{"duration",number("duration")},{"speed",number("speed",1)},
        {"paused",text("pause")=="yes"},{"faces",faceCount_},{"generation",generation_},{"resultGeneration",resultGeneration_},
        {"analysisMs",analysisMs_},{"rendered",rendered_},{"workerReady",workerReady_},{"awaitingPlayback",awaitingPlayback_},{"needFrame",needFrame_},{"analysisBusy",busy_},
        {"workerError",workerError_},{"glError",glError_},{"hwdec",text("hwdec-current")},{"avsync",number("avsync")},{"drops",number("frame-drop-count")},{"decoderDrops",number("decoder-frame-drop-count")},{"tracks",tracks_},
        {"swapEnabled",swapEnabled_},{"swapSourceReady",swapSourceReady_},{"swapTarget",swapTarget_},{"swapStrength",swapStrength_},{"swapFeather",swapFeather_},{"swapFaces",swapFaces_},
        {"beauty",beauty_},{"enabled",beautyEnabled_},{"compare",compare_},{"loaded",loaded_}};
}
void VideoWidget::saveFrame(const QString& path) {
    if(!grabFramebuffer().save(path)) emit errorOccurred("截图保存失败");
}
void VideoWidget::mouseDoubleClickEvent(QMouseEvent*) { emit doubleClicked(); }
void VideoWidget::mouseReleaseEvent(QMouseEvent* e) { if(e->button()==Qt::LeftButton) emit clicked(); }
