#include "player.h"
#include "media_identity.h"
#include <QApplication>
#include <QActionGroup>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QFileInfo>
#include <QHBoxLayout>
#include <QInputDialog>
#include <QJsonDocument>
#include <QMenuBar>
#include <QMessageBox>
#include <QMimeData>
#include <QMouseEvent>
#include <QScrollArea>
#include <QSaveFile>
#include <QSignalBlocker>
#include <QSplitter>
#include <QStyle>
#include <QUrl>
#include <QVBoxLayout>
#include <cmath>
#include <algorithm>
#include <QLineEdit>
#include <QDesktopServices>
#include <QImageReader>
#include <QKeyEvent>
#include <QWindow>
#include <QThread>

namespace {
QString timeText(double seconds) {
    const auto t=static_cast<qint64>((std::max)(0.,seconds));
    return QString("%1:%2:%3").arg(t/3600,2,10,QChar('0')).arg(t/60%60,2,10,QChar('0')).arg(t%60,2,10,QChar('0'));
}
void identify(QWidget* w,const QString& id,const QString& label) {
    w->setObjectName(id); w->setAccessibleName(label);
}
QPushButton* button(const QString& text,const QString& id,QWidget* parent=nullptr) {
    auto* b=new QPushButton(text,parent); identify(b,id,text); b->setCursor(Qt::PointingHandCursor);
    b->setFocusPolicy(Qt::NoFocus); return b;
}
}
int SeekSlider::at(const QMouseEvent* e) const {
    const int usable=(std::max)(1,width()-18);
    return QStyle::sliderValueFromPosition(minimum(),maximum(),qBound(0,qRound(e->position().x())-9,usable),usable);
}
void SeekSlider::mousePressEvent(QMouseEvent* e) {
    if(e->button()==Qt::LeftButton) { setSliderDown(true); setValue(at(e)); emit sliderMoved(value()); e->accept(); }
    else QSlider::mousePressEvent(e);
}
void SeekSlider::mouseMoveEvent(QMouseEvent* e) {
    if(isSliderDown()) { setValue(at(e)); emit sliderMoved(value()); e->accept(); }
    else QSlider::mouseMoveEvent(e);
}
void SeekSlider::mouseReleaseEvent(QMouseEvent* e) {
    if(e->button()==Qt::LeftButton && isSliderDown()) { setValue(at(e)); setSliderDown(false); e->accept(); }
    else QSlider::mouseReleaseEvent(e);
}
PlayerWindow::PlayerWindow(const QString& root,const QString& controlDir,QWidget* parent)
:QMainWindow(parent),root_(root),controlDir_(controlDir) {
    setWindowTitle("映澈 0.6.0 · 自然人像"); setAcceptDrops(true); resize(1220,760); setMinimumSize(850,560);
    QDir().mkpath(QDir(root_).filePath("data"));
    loadSettings(); buildUi(); buildMenus(); applyBeauty(beauty_);
    beautyToggle_->setChecked(loadedEnabled_);pictureStatus_->setText(settingsNotice_.isEmpty()?"全局默认 · 新视频从这里开始":settingsNotice_);
    qApp->installEventFilter(this);
    connect(qApp,&QGuiApplication::screenRemoved,this,[this](QScreen*){
        if(controlsWindow_)reuniteView(true);
    });
    connect(&tick_,&QTimer::timeout,this,&PlayerWindow::updatePlayback); tick_.start(200);
    seekDebounce_.setSingleShot(true); seekDebounce_.setInterval(100);
    connect(&seekDebounce_,&QTimer::timeout,this,[this]{ video_->seek(timeline_->value()/1000.); });
    saveDebounce_.setSingleShot(true); saveDebounce_.setInterval(700);
    connect(&saveDebounce_,&QTimer::timeout,this,&PlayerWindow::saveSettings);
    if(!controlDir_.isEmpty()) { QDir().mkpath(controlDir_); connect(&testTimer_,&QTimer::timeout,this,&PlayerWindow::testTick); testTimer_.start(100); }
}
void PlayerWindow::buildUi() {
    auto* central=new QWidget(this); setCentralWidget(central);
    auto* layout=new QVBoxLayout(central);mainLayout_=layout; layout->setSpacing(0); layout->setContentsMargins(0,0,0,0);
    header_=new QWidget(central); header_->setObjectName("header");
    auto* top=new QHBoxLayout(header_); top->setContentsMargins(20,12,20,12);
    auto* brand=new QLabel("映澈",header_); brand->setObjectName("brand"); top->addWidget(brand);
    auto* tag=new QLabel("BEAUTY PLAYER",header_); tag->setObjectName("tag"); top->addWidget(tag);
    top->addSpacing(20);
    fileLabel_=new QLabel("本地视频 · 自然美颜",header_); fileLabel_->setObjectName("fileTitle"); top->addWidget(fileLabel_,1);
    auto* open=button("打开视频","openButton",header_); open->setProperty("accent",true); top->addWidget(open);
    auto* sideButton=button("面板","panelButton",header_); top->addWidget(sideButton);
    auto* separate=button("双屏 / 合并","separateView",header_);top->addWidget(separate);
    connect(separate,&QPushButton::clicked,this,&PlayerWindow::toggleSeparateView);
    connect(open,&QPushButton::clicked,this,&PlayerWindow::openDialog);
    connect(sideButton,&QPushButton::clicked,this,[this]{ side_->setVisible(!side_->isVisible()); });
    layout->addWidget(header_);
    auto* middle=new QSplitter(Qt::Horizontal,central);middle_=middle; middle->setChildrenCollapsible(false);
    video_=new VideoWidget(root_,middle); middle->addWidget(video_);
    side_=new QTabWidget(middle); side_->setObjectName("sidePanel"); side_->setMinimumWidth(275); side_->setMaximumWidth(380);
    auto* scroll=new QScrollArea(side_); scroll->setWidgetResizable(true); scroll->setFrameShape(QFrame::NoFrame);
    auto* beautyPanel=new QWidget(scroll);
    auto* beautyLayout=new QVBoxLayout(beautyPanel); beautyLayout->setContentsMargins(18,16,18,20); beautyLayout->setSpacing(12);
    beautyToggle_=new QCheckBox("开启人像美颜",beautyPanel); identify(beautyToggle_,"beautyEnabled","开启人像美颜"); beautyToggle_->setChecked(true);
    beautyLayout->addWidget(beautyToggle_);
    pictureScope_=new QComboBox(beautyPanel);identify(pictureScope_,"pictureScope","画面设置范围");
    pictureScope_->addItems({"单片设置 · 自动保存","全局默认 · 用于新视频","临时预览 · 不保存"});pictureScope_->setCurrentIndex(1);
    beautyLayout->addWidget(pictureScope_);
    pictureStatus_=new QLabel(beautyPanel);pictureStatus_->setWordWrap(true);pictureStatus_->setObjectName("muted");beautyLayout->addWidget(pictureStatus_);
    connect(pictureScope_,qOverload<int>(&QComboBox::currentIndexChanged),this,&PlayerWindow::restorePicture);
    auto* engineLabel=new QLabel("GPUPixel 1.3 · 肤质引擎",beautyPanel);
    identify(engineLabel,"beautyEngine","GPUPixel 美颜引擎");beautyLayout->addWidget(engineLabel);
    compareToggle_=new QCheckBox("左右对比 · 左侧原画",beautyPanel); identify(compareToggle_,"compareEnabled","左右对比"); beautyLayout->addWidget(compareToggle_);
    holdOriginal_=button("按住看原片 · R","holdOriginal",beautyPanel);beautyLayout->addWidget(holdOriginal_);
    connect(holdOriginal_,&QPushButton::pressed,this,[this]{previewOriginal(true);});
    connect(holdOriginal_,&QPushButton::released,this,[this]{previewOriginal(false);});
    auto* presetRow=new QHBoxLayout();
    for(const QString& label:{"自然","柔和","暗光"}) {
        auto* b=button(label,"preset"+label,beautyPanel); presetRow->addWidget(b);
        connect(b,&QPushButton::clicked,this,[this,label] {
            QJsonObject p=defaultBeauty();
            if(label=="柔和") { p["smooth"]=40;p["white"]=12;p["detail"]=70;p["sharp"]=4; }
            if(label=="暗光") { p["smooth"]=18;p["white"]=35;p["pink"]=0;p["sharp"]=0; }
            applyBeauty(p);rememberPicture(); saveDebounce_.start();
        });
    }
    beautyLayout->addLayout(presetRow);
    auto* tip=new QLabel("局部温和调节 · 暗光预设不恢复丢失细节",beautyPanel);tip->setWordWrap(true); tip->setObjectName("muted"); beautyLayout->addWidget(tip);
    int index=0;
    for(const auto& p:parameters) {
        if(index==0||index==5||index==9) {
            auto* group=new QLabel(index==0?"肤质与肤色":index==5?"五官与轮廓":"妆感与细节",beautyPanel);
            group->setObjectName("sectionLabel"); beautyLayout->addWidget(group);
        }
        auto* row=new QVBoxLayout(); row->setSpacing(3);
        auto* title=new QHBoxLayout(); title->addWidget(new QLabel(QString::fromUtf8(p.label),beautyPanel),1);
        auto* field=new QSpinBox(beautyPanel); field->setRange(p.minimum,p.maximum); field->setValue(p.initial);
        field->setFixedWidth(74); identify(field,QString::fromLatin1(p.key)+"Value",QString::fromUtf8(p.label)+"数值");
        field->setButtonSymbols(QAbstractSpinBox::PlusMinus); field->setKeyboardTracking(false); title->addWidget(field); row->addLayout(title);
        auto* slider=new QSlider(Qt::Horizontal,beautyPanel); slider->setRange(p.minimum,p.maximum); slider->setValue(p.initial);
        identify(slider,QString::fromLatin1(p.key)+"Slider",QString::fromUtf8(p.label));
        connect(slider,&QSlider::valueChanged,field,&QSpinBox::setValue);
        connect(field,qOverload<int>(&QSpinBox::valueChanged),slider,&QSlider::setValue);
        const QString key=QString::fromLatin1(p.key); fields_.insert(key,field);
        connect(field,qOverload<int>(&QSpinBox::valueChanged),this,[this,key](int value){
            beauty_[key]=value; if(!applying_) { video_->setBeauty(beauty_);rememberPicture(); saveDebounce_.start(); }
        });
        row->addWidget(slider); beautyLayout->addLayout(row); ++index;
    }
    auto* reset=button("重置当前范围","resetBeauty",beautyPanel); beautyLayout->addWidget(reset);
    connect(reset,&QPushButton::clicked,this,&PlayerWindow::resetPicture);
    beautyLayout->addStretch();
    scroll->setWidget(beautyPanel); side_->addTab(scroll,"美颜");
    buildSwapPanel();
    playlist_=new QListWidget(side_); identify(playlist_,"playlist","播放列表"); side_->addTab(playlist_,"列表");
    connect(playlist_,&QListWidget::itemDoubleClicked,this,[this](QListWidgetItem* item){openFile(item->data(Qt::UserRole).toString());});
    middle->addWidget(side_); middle->setStretchFactor(0,1); middle->setStretchFactor(1,0); middle->setSizes({900,300});
    layout->addWidget(middle,1);
    footer_=new QWidget(central); footer_->setObjectName("footer");
    auto* bottom=new QVBoxLayout(footer_); bottom->setContentsMargins(20,10,20,12); bottom->setSpacing(8);
    timeline_=new SeekSlider(footer_); identify(timeline_,"timeline","播放进度"); timeline_->setRange(0,0); bottom->addWidget(timeline_);
    connect(timeline_,&QSlider::sliderMoved,this,[this](int value){
        timeLabel_->setText(timeText(value/1000.)+" / "+timeText(duration_));
        if(!seekDebounce_.isActive()) seekDebounce_.start();
    });
    connect(timeline_,&QSlider::sliderReleased,this,[this]{seekDebounce_.stop();video_->seek(timeline_->value()/1000.);});
    auto* controls=new QHBoxLayout(); controls->setSpacing(8);
    auto* prev=button("上一段","previousButton",footer_); controls->addWidget(prev);
    play_=button("播放","playButton",footer_); play_->setProperty("accent",true); play_->setMinimumWidth(72); controls->addWidget(play_);
    auto* next=button("下一段","nextButton",footer_); controls->addWidget(next);
    timeLabel_=new QLabel("00:00:00 / 00:00:00",footer_); identify(timeLabel_,"timeLabel","播放时间"); timeLabel_->setMinimumWidth(180); controls->addWidget(timeLabel_);
    controls->addStretch();
    speed_=new QDoubleSpinBox(footer_); identify(speed_,"speedControl","播放倍速"); speed_->setRange(.25,4); speed_->setSingleStep(.25); speed_->setDecimals(2);speed_->setValue(1);speed_->setSuffix(" ×");speed_->setFixedWidth(90);speed_->setButtonSymbols(QAbstractSpinBox::PlusMinus);speed_->setKeyboardTracking(false);
    controls->addWidget(speed_);
    mute_=new QCheckBox("静音",footer_); identify(mute_,"muteControl","静音"); controls->addWidget(mute_);
    volume_=new QSlider(Qt::Horizontal,footer_); identify(volume_,"volumeControl","音量");volume_->setRange(0,100);volume_->setValue(80);volume_->setFixedWidth(85);controls->addWidget(volume_);
    auto* full=button("全屏","fullscreenButton",footer_); controls->addWidget(full); bottom->addLayout(controls);
    auto* statusRow=new QHBoxLayout();
    status_=new QLabel("拖入视频，或按 Ctrl + O",footer_); identify(status_,"statusLabel","播放状态");statusRow->addWidget(status_,1);
    analysisLabel_=new QLabel("本地处理",footer_);identify(analysisLabel_,"analysisLabel","人脸分析状态"); statusRow->addWidget(analysisLabel_);
    bottom->addLayout(statusRow); layout->addWidget(footer_);
    connect(prev,&QPushButton::clicked,this,[this]{nextFile(-1);});
    connect(next,&QPushButton::clicked,this,[this]{nextFile(1);});
    connect(play_,&QPushButton::clicked,this,[this]{if(currentFile_.isEmpty())openDialog();else video_->command({"cycle","pause"});});
    connect(full,&QPushButton::clicked,this,&PlayerWindow::toggleFullscreen);
    connect(speed_,qOverload<double>(&QDoubleSpinBox::valueChanged),this,[this](double speed){video_->property("speed",QString::number(speed));});
    connect(volume_,&QSlider::valueChanged,this,[this](int volume){video_->property("volume",QString::number(volume));});
    connect(mute_,&QCheckBox::toggled,this,[this](bool b){video_->property("mute",b?"yes":"no");});
    connect(beautyToggle_,&QCheckBox::toggled,this,[this](bool value){video_->setBeautyEnabled(value);if(!applying_){rememberPicture();saveDebounce_.start();}});
    connect(compareToggle_,&QCheckBox::toggled,video_,&VideoWidget::setCompare);
    connect(video_,&VideoWidget::doubleClicked,this,&PlayerWindow::toggleFullscreen);
    connect(video_,&VideoWidget::analysisStatus,analysisLabel_,&QLabel::setText);
    connect(video_,&VideoWidget::errorOccurred,this,[this](const QString& error){status_->setText(error);status_->setToolTip(error);});
    connect(video_,&VideoWidget::fileLoaded,this,[this]{
        video_->property("speed",QString::number(speed_->value()));
        video_->property("volume",QString::number(volume_->value()));
        status_->setText("正在播放");
        updatePlayback();
    });
    connect(video_,&VideoWidget::ended,this,[this]{if(playlist_->currentRow()+1<playlist_->count())nextFile(1);});
}
void PlayerWindow::buildSwapPanel() {
    auto* scroll=new QScrollArea(side_);scroll->setWidgetResizable(true);scroll->setFrameShape(QFrame::NoFrame);
    auto* panel=new QWidget(scroll);auto* layout=new QVBoxLayout(panel);layout->setContentsMargins(18,18,18,18);layout->setSpacing(13);
    auto* title=new QLabel("实验功能 · 照片换脸",panel);title->setObjectName("sectionLabel");layout->addWidget(title);
    auto* warning=new QLabel("跟踪和遮挡处理仍不稳定。每次启动默认关闭，请主动启用。",panel);warning->setWordWrap(true);layout->addWidget(warning);
    auto* select=button("选择源照片…","selectSwapSource",panel);select->setProperty("accent",true);layout->addWidget(select);
    connect(select,&QPushButton::clicked,this,&PlayerWindow::chooseSwapSource);
    sourceLabel_=new QLabel("选择清晰正面照；多人照片取最大人脸",panel);sourceLabel_->setWordWrap(true);sourceLabel_->setObjectName("muted");layout->addWidget(sourceLabel_);
    swapToggle_=new QCheckBox("启用换脸",panel);identify(swapToggle_,"swapEnabled","启用换脸");layout->addWidget(swapToggle_);
    connect(swapToggle_,&QCheckBox::toggled,video_,&VideoWidget::setSwapEnabled);
    layout->addWidget(new QLabel("替换视频中的哪张脸",panel));swapTarget_=new QComboBox(panel);identify(swapTarget_,"swapTarget","换脸目标");
    swapTarget_->addItem("最大人脸","largest");swapTarget_->addItem("全部人脸","all");
    for(int i=0;i<4;++i)swapTarget_->addItem(QString("从左第 %1 张脸").arg(i+1),QString::number(i));layout->addWidget(swapTarget_);
    auto addValue=[this,panel,layout](const QString& label,const QString& id,int initial) {
        auto* row=new QHBoxLayout();row->addWidget(new QLabel(label,panel),1);auto* field=new QSpinBox(panel);field->setRange(0,100);field->setValue(initial);field->setFixedWidth(90);field->setKeyboardTracking(false);identify(field,id,label);row->addWidget(field);layout->addLayout(row);return field;
    };
    swapStrength_=addValue("换脸融合强度","swapStrength",100);swapFeather_=addValue("边缘柔和程度","swapFeather",35);
    auto options=[this]{video_->setSwapOptions(swapTarget_->currentData().toString(),swapFeather_->value(),swapStrength_->value());};
    connect(swapTarget_,qOverload<int>(&QComboBox::currentIndexChanged),this,[options](int){options();});
    connect(swapStrength_,qOverload<int>(&QSpinBox::valueChanged),this,[options](int){options();});
    connect(swapFeather_,qOverload<int>(&QSpinBox::valueChanged),this,[options](int){options();});
    auto* clear=button("清除源照片","clearSwapSource",panel);layout->addWidget(clear);
    connect(clear,&QPushButton::clicked,this,[this]{swapToggle_->setChecked(false);sourceLabel_->setText("尚未选择源照片");video_->setSwapSource(QString());});
    swapLabel_=new QLabel("源照片与视频均在本机处理",panel);identify(swapLabel_,"swapStatus","换脸状态");swapLabel_->setWordWrap(true);layout->addWidget(swapLabel_);
    connect(video_,&VideoWidget::swapStatus,swapLabel_,&QLabel::setText);
    auto* edge=new QLabel("Edge 网页增强",panel);edge->setObjectName("sectionLabel");layout->addWidget(edge);
    bridgeToggle_=new QCheckBox("启用 Edge 连接",panel);identify(bridgeToggle_,"bridgeEnabled","启用 Edge 连接");layout->addWidget(bridgeToggle_);
    connect(bridgeToggle_,&QCheckBox::toggled,this,&PlayerWindow::setBridgeEnabled);
    bridgeLabel_=new QLabel("开启后，在扩展中选择网页视频",panel);identify(bridgeLabel_,"bridgeStatus","Edge 连接状态");bridgeLabel_->setWordWrap(true);layout->addWidget(bridgeLabel_);
    auto* folder=button("打开扩展文件夹","openExtensionFolder",panel);layout->addWidget(folder);
    connect(folder,&QPushButton::clicked,this,[this]{QDesktopServices::openUrl(QUrl::fromLocalFile(QDir(root_).filePath("edge-extension")));});
    auto* note=new QLabel("浏览器的源照片在扩展中单独选择。关闭播放器会停止连接。",panel);note->setWordWrap(true);note->setObjectName("muted");layout->addWidget(note);layout->addStretch();
    scroll->setWidget(panel);side_->addTab(scroll,"换脸");
}
void PlayerWindow::chooseSwapSource() {
    const QString path=QFileDialog::getOpenFileName(this,"选择换脸源照片",lastDirectory_,"照片 (*.jpg *.jpeg *.png *.webp *.bmp);;所有文件 (*)");
    if(path.isEmpty())return;
    QImageReader reader(path);reader.setAutoTransform(true);
    if(!reader.canRead()) {swapLabel_->setText("无法读取这张照片");return;}
    sourceLabel_->setText(QFileInfo(path).fileName());video_->setSwapSource(path);
}
void PlayerWindow::setBridgeEnabled(bool enabled) {
    if(!enabled) {
        if(bridge_ && bridge_->state()!=QProcess::NotRunning) {bridge_->terminate();if(!bridge_->waitForFinished(500)){bridge_->kill();bridge_->waitForFinished(500);}}
        bridgeLabel_->setText("Edge 连接已关闭");return;
    }
    if(!bridge_) {
        bridge_=new QProcess(this);
        connect(bridge_,&QProcess::readyReadStandardOutput,this,[this]{
            bridgeOutput_+=bridge_->readAllStandardOutput();
            if(bridgeOutput_.contains("bridgeReady"))bridgeLabel_->setText("Edge 本地连接已就绪");
            if(bridgeOutput_.size()>4000)bridgeOutput_=bridgeOutput_.right(4000);
        });
        connect(bridge_,&QProcess::readyReadStandardError,this,[this]{bridge_->readAllStandardError();});
        connect(bridge_,&QProcess::errorOccurred,this,[this](QProcess::ProcessError){bridgeLabel_->setText("Edge 服务启动失败，请检查运行库");});
        connect(bridge_,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,[this](int,QProcess::ExitStatus){
            if(bridgeToggle_->isChecked()){QSignalBlocker block(bridgeToggle_);bridgeToggle_->setChecked(false);bridgeLabel_->setText("Edge 服务已停止；端口可能被映澈后台服务或其他实例占用");}
        });
    }
    if(bridge_->state()!=QProcess::NotRunning)return;
    bridgeOutput_.clear();bridgeLabel_->setText("正在启动 Edge 本地连接…");
    const QString model=QDir(root_).filePath("models/face_landmarker.task"),config=QDir(root_).filePath("edge-extension/bridge-config.json");
    const QString packaged=QDir(root_).filePath("app/face_engine_v041/FaceEngine.exe");
    if(QFileInfo::exists(packaged))bridge_->start(packaged,{"--bridge",model,config});
    else bridge_->start(QDir(root_).filePath("tools/python/Scripts/python.exe"),{"-u",QDir(root_).filePath("tools/face_worker.py"),"--bridge",model,config});
}
void PlayerWindow::buildMenus() {
    menus_=menuBar();
    auto* files=menuBar()->addMenu("文件");
    auto* playback=menuBar()->addMenu("播放");
    auto* view=menuBar()->addMenu("画面");
    auto* subtitles=menuBar()->addMenu("字幕");
    auto* audio=menuBar()->addMenu("音轨");
    files->addAction("打开视频…",QKeySequence("Ctrl+O"),this,&PlayerWindow::openDialog);
    files->addAction("保存当前画面…",QKeySequence("Ctrl+S"),this,&PlayerWindow::screenshot);
    files->addSeparator(); files->addAction("退出",QKeySequence("Alt+F4"),this,&QWidget::close);
    playback->addAction("播放 / 暂停",QKeySequence("Space"),this,[this]{video_->command({"cycle","pause"});});
    playback->addAction("后退 5 秒",QKeySequence("Left"),this,[this]{video_->seek(-5,true);});
    playback->addAction("前进 5 秒",QKeySequence("Right"),this,[this]{video_->seek(5,true);});
    playback->addAction("上一帧",QKeySequence(","),this,[this]{video_->command({"frame-back-step"});});
    playback->addAction("下一帧",QKeySequence("."),this,[this]{video_->command({"frame-step"});});
    playback->addAction("跳转到时间…",QKeySequence("Ctrl+G"),this,&PlayerWindow::jumpDialog);
    auto* speeds=playback->addMenu("倍速");
    for(double v:{.25,.5,.75,1.,1.25,1.5,1.75,2.,2.5,3.,4.})
        speeds->addAction(QString::number(v)+" ×",this,[this,v]{speed_->setValue(v);});
    playback->addAction("恢复 1 倍速",QKeySequence("Backspace"),this,[this]{speed_->setValue(1);});
    playback->addAction("减速",QKeySequence("["),this,[this]{speed_->setValue(speed_->value()-.25);});
    playback->addAction("加速",QKeySequence("]"),this,[this]{speed_->setValue(speed_->value()+.25);});
    auto* loop=playback->addAction("单段循环"); loop->setCheckable(true);
    connect(loop,&QAction::toggled,this,[this](bool b){video_->property("loop-file",b?"inf":"no");});
    view->addAction("全屏 / 窗口",QKeySequence("F11"),this,&PlayerWindow::toggleFullscreen);
    view->addAction("分离到另一屏 / 合并",QKeySequence("F10"),this,&PlayerWindow::toggleSeparateView);
    view->addAction("退出全屏",QKeySequence("Esc"),this,[this]{if(isFullScreen())toggleFullscreen();});
    auto* top=view->addAction("窗口置顶");top->setCheckable(true);
    connect(top,&QAction::toggled,this,[this](bool b){setWindowFlag(Qt::WindowStaysOnTopHint,b);show();});
    view->addAction("显示 / 隐藏面板",QKeySequence("F8"),this,[this]{side_->setVisible(!side_->isVisible());});
    view->addAction("开启 / 关闭美颜",QKeySequence("B"),this,[this]{beautyToggle_->toggle();});
    view->addAction("左右对比",QKeySequence("C"),this,[this]{compareToggle_->toggle();});
    subtitles->addAction("加载字幕…",QKeySequence("Ctrl+L"),this,&PlayerWindow::subtitleDialog);
    auto* subTracks=subtitles->addMenu("选择字幕");
    connect(subTracks,&QMenu::aboutToShow,this,[this,subTracks]{
        subTracks->clear(); subTracks->addAction("关闭字幕",this,[this]{video_->property("sid","no");});
        for(const auto& value:video_->tracks()) {
            const auto t=value.toObject(); if(t.value("type").toString()!="sub")continue;
            const QString id=t.value("id").toString();
            auto* action=subTracks->addAction(id+" "+t.value("lang").toString()+" "+t.value("title").toString(),this,[this,id]{video_->property("sid",id);});
            action->setCheckable(true);action->setChecked(t.value("selected").toString()=="yes");
        }
    });
    connect(audio,&QMenu::aboutToShow,this,[this,audio]{
        audio->clear();
        for(const auto& value:video_->tracks()) {
            const auto t=value.toObject();if(t.value("type").toString()!="audio")continue;
            const QString id=t.value("id").toString();
            auto* action=audio->addAction(id+" "+t.value("lang").toString()+" "+t.value("title").toString(),this,[this,id]{video_->property("aid",id);});
            action->setCheckable(true);action->setChecked(t.value("selected").toString()=="yes");
        }
    });
    auto* help=menuBar()->addMenu("帮助");
    help->addAction("快捷键",this,[this]{QMessageBox::information(this,"操作快捷键","Ctrl+O 打开视频\n空格 播放/暂停\n← / → 后退/前进 5 秒\n, / . 逐帧后退/前进\n[ / ] 减速/加速\nBackspace 恢复 1 倍速\nCtrl+G 跳转时间\nF11 / 双击画面 全屏\nF8 显示/隐藏面板\nB 美颜开关\nC 左右对比\nCtrl+S 保存当前画面");});
    help->addAction("关于映澈",this,[this]{QMessageBox::information(this,"映澈 0.6.0","本地实时美颜播放器\n局部自然美颜 · 单片参数记忆\nR 按住看原片 · F10 双屏 / 合并\n换脸、Edge 补帧为实验功能，默认关闭。\n源照片与画面在本机处理。");});
    // Keep keyboard actions active while the menu bar is hidden in fullscreen.
    for(auto* action:findChildren<QAction*>()) {
        if(!action->shortcut().isEmpty()) addAction(action);
    }
}
void PlayerWindow::updatePlayback() {
    if(!video_->isReady()||!video_->hasMedia()) { if(currentFile_.isEmpty()) play_->setText("播放"); return; }
    const QString codec=video_->text("video-format").toUpper();
    if(!codec.isEmpty() && codec!=displayedCodec_) { displayedCodec_=codec; status_->setText("正在播放 · "+codec); }
    duration_=video_->number("duration");
    if(resumePending_) {
        if(duration_<=0) return;
        resumePending_=false;
        if(resumeAt_>3 && resumeAt_<duration_-5) { video_->seek(resumeAt_); return; }
    }
    const double pos=video_->number("time-pos");
    if(!timeline_->isSliderDown()) {
        QSignalBlocker block(timeline_);
        timeline_->setRange(0,static_cast<int>((std::min)(duration_*1000.,2147483000.)));
        timeline_->setValue(static_cast<int>((std::min)(pos*1000.,2147483000.)));
        timeLabel_->setText(timeText(pos)+" / "+timeText(duration_));
    }
    play_->setText(video_->text("pause")=="yes"?"播放":"暂停");
    {QSignalBlocker b(speed_);speed_->setValue(video_->number("speed",1));}
    {QSignalBlocker b(volume_);volume_->setValue(static_cast<int>(video_->number("volume",80)));}
    if(!currentFile_.isEmpty() && duration_>0) positions_[currentFile_]=pos;
}
void PlayerWindow::openDialog() {
    const auto list=QFileDialog::getOpenFileNames(this,"打开视频",lastDirectory_,"视频文件 (*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.ts *.m2ts *.mts *.mpg *.mpeg *.m4v *.rm *.rmvb *.vob *.ogv);;所有文件 (*)");
    if(!list.isEmpty()) openFiles(list);
}
void PlayerWindow::openFiles(const QStringList& files) {
    for(const auto& f:files) {
        const QFileInfo info(f); if(!info.isFile())continue;
        const QString path=info.absoluteFilePath();
        bool found=false;
        for(int i=0;i<playlist_->count();i++)if(playlist_->item(i)->data(Qt::UserRole).toString()==path)found=true;
        if(!found) {auto* item=new QListWidgetItem(info.fileName(),playlist_);item->setData(Qt::UserRole,path);item->setToolTip(path);}
    }
    if(!files.isEmpty())openFile(QFileInfo(files.first()).absoluteFilePath());
}
void PlayerWindow::openFile(const QString& f) {
    if(!QFileInfo(f).isFile()) {status_->setText("找不到视频文件");return;}
    updatePlayback();saveSettings();currentFile_=QFileInfo(f).absoluteFilePath();
    previewOriginal(false);mediaKey_=mediaIdentity(currentFile_);
    {QSignalBlocker block(pictureScope_);pictureScope_->setCurrentIndex(mediaKey_.isEmpty()?2:0);}
    restorePicture(pictureScope_->currentIndex());
    resumeAt_=positions_.value(currentFile_).toDouble(); resumePending_=true;
    lastDirectory_=QFileInfo(f).absolutePath();
    fileLabel_->setText(QFileInfo(f).fileName());fileLabel_->setToolTip(currentFile_);
    setWindowTitle(QFileInfo(f).fileName()+" — 映澈");
    for(int i=0;i<playlist_->count();i++)if(playlist_->item(i)->data(Qt::UserRole).toString()==currentFile_)playlist_->setCurrentRow(i);
    displayedCodec_.clear();status_->setText("正在打开…");video_->loadFile(currentFile_);
}
void PlayerWindow::nextFile(int delta) {
    const int row=playlist_->currentRow()+delta;
    if(row>=0&&row<playlist_->count())openFile(playlist_->item(row)->data(Qt::UserRole).toString());
}
void PlayerWindow::jumpDialog() {
    bool ok=false;
    const QString result=QInputDialog::getText(this,"跳转到时间","输入 时:分:秒，或秒数",QLineEdit::Normal,timeText(video_->number("time-pos")),&ok);
    if(!ok)return;
    const auto parts=result.trimmed().split(':');
    double seconds=0;bool valid=parts.size()<=3&&!parts.isEmpty();
    for(const auto& part:parts){bool n=false;const double value=part.toDouble(&n);if(!n||value<0||!std::isfinite(value))valid=false;seconds=seconds*60+value;}
    if(valid)video_->seek(qBound(0.,seconds,duration_));
    else status_->setText("时间格式不正确");
}
void PlayerWindow::subtitleDialog() {
    const QString path=QFileDialog::getOpenFileName(this,"加载字幕",lastDirectory_,"字幕 (*.srt *.ass *.ssa *.vtt *.sub);;所有文件 (*)");
    if(!path.isEmpty())video_->command({"sub-add",path,"select"});
}
void PlayerWindow::screenshot() {
    if(currentFile_.isEmpty())return;
    const QString path=QFileDialog::getSaveFileName(this,"保存当前画面",lastDirectory_+"/映澈-"+QDateTime::currentDateTime().toString("yyyyMMdd-HHmmss")+".png","PNG (*.png)");
    if(!path.isEmpty())video_->saveFrame(path);
}
void PlayerWindow::toggleFullscreen() {
    previewOriginal(false);
    if(controlsWindow_) {if(isFullScreen())showNormal();else showFullScreen();return;}
    if(isFullScreen()) {
        if(wasMaximized_)showMaximized();else showNormal();
        menus_->show();header_->show();footer_->show();side_->setVisible(sideBeforeFull_);
    } else {
        wasMaximized_=isMaximized();sideBeforeFull_=side_->isVisible();
        menus_->hide();header_->hide();footer_->hide();side_->hide();showFullScreen();
    }
}
void PlayerWindow::applyBeauty(const QJsonObject& values) {
    beauty_=sanitizeBeauty(values);applying_=true;
    for(auto it=fields_.cbegin();it!=fields_.cend();++it)it.value()->setValue(beauty_.value(it.key()).toInt());
    applying_=false;if(video_)video_->setBeauty(beauty_);
}
QString PlayerWindow::settingsPath() const {
    return QDir(controlDir_.isEmpty()?QDir(root_).filePath("data"):controlDir_).filePath("settings-v2.json");
}
void PlayerWindow::rememberPicture() {
    if(applying_||!pictureScope_)return;
    if(!settingsWritable_){pictureStatus_->setText(settingsNotice_+" · 调整仅本次有效");return;}
    QJsonObject value{{"beauty",beauty_},{"enabled",beautyToggle_->isChecked()}};
    const int scope=pictureScope_->currentIndex();
    if(scope==1)defaults_=value;
    else if(scope==0 && !mediaKey_.isEmpty()) {
        if(!mediaSettings_.contains(mediaKey_) && mediaSettings_.size()>=2000) {
            QSignalBlocker block(pictureScope_);pictureScope_->setCurrentIndex(2);
            pictureStatus_->setText("单片设置已达 2000 条，本片仅临时生效；已有设置保留");return;
        }
        mediaSettings_[mediaKey_]=value;
    }
    pictureStatus_->setText(scope==2?"临时预览，切换范围或换片后丢弃":scope==1?"正在保存全局默认":mediaKey_.isEmpty()?"未识别媒体，本次不保存":"正在保存此视频的画面参数");
}
void PlayerWindow::restorePicture(int scope) {
    if(scope==2) {
        if(mediaKey_.isEmpty()) {
            applyBeauty(defaults_.value("beauty").toObject());
            applying_=true;beautyToggle_->setChecked(defaults_.value("enabled").toBool(true));applying_=false;
        }
        pictureStatus_->setText(!settingsWritable_?settingsNotice_:mediaKey_.isEmpty()?"无法建立媒体标识，本片仅临时预览":"临时预览 · 不保存");return;
    }
    const auto saved=scope==0?mediaSettings_.value(mediaKey_).toObject():QJsonObject();
    const auto value=saved.isEmpty()?defaults_:saved;
    applyBeauty(value.value("beauty").toObject());
    applying_=true;beautyToggle_->setChecked(value.value("enabled").toBool(true));applying_=false;
    pictureStatus_->setText(scope==1?"全局默认 · 用于新视频":mediaKey_.isEmpty()?"尚未打开可识别的视频":saved.isEmpty()?"此视频继承全局默认；调节后自动单独保存":"已恢复此视频的画面参数");
    if(!settingsWritable_)pictureStatus_->setText(settingsNotice_+" · 调整仅本次有效");
}
void PlayerWindow::resetPicture() {
    const int scope=pictureScope_->currentIndex();
    if(scope==0){mediaSettings_.remove(mediaKey_);restorePicture(0);}
    else if(scope==1){defaults_={{"beauty",defaultBeauty()},{"enabled",true}};restorePicture(1);}
    else {applyBeauty(defaults_.value("beauty").toObject());applying_=true;beautyToggle_->setChecked(defaults_.value("enabled").toBool(true));applying_=false;}
    saveDebounce_.start();
}
void PlayerWindow::previewOriginal(bool value) {
    originalHeld_=value;if(video_)video_->setOriginalPreview(value);
    if(!value && holdOriginal_)holdOriginal_->setDown(false);
}
bool PlayerWindow::eventFilter(QObject* object,QEvent* event) {
    if(event->type()==QEvent::ApplicationDeactivate || event->type()==QEvent::WindowDeactivate)previewOriginal(false);
    if(object==controlsWindow_ && event->type()==QEvent::Close && !closing_) {
        static_cast<QCloseEvent*>(event)->ignore();QTimer::singleShot(0,this,[this]{reuniteView(true);});return true;
    }
    if(event->type()==QEvent::KeyPress || event->type()==QEvent::KeyRelease) {
        auto* widget=qobject_cast<QWidget*>(object);
        const bool ours=widget && (widget->window()==this || widget->window()==controlsWindow_);
        auto* key=static_cast<QKeyEvent*>(event);
        if(ours && key->key()==Qt::Key_R && (key->modifiers()==Qt::NoModifier || (originalHeld_ && event->type()==QEvent::KeyRelease))) {
            const bool editing=qobject_cast<QLineEdit*>(widget) || qobject_cast<QAbstractSpinBox*>(widget);
            if(!editing || originalHeld_) {
                if(!key->isAutoRepeat())previewOriginal(event->type()==QEvent::KeyPress);
                return true;
            }
        }
    }
    return QMainWindow::eventFilter(object,event);
}
void PlayerWindow::toggleSeparateView() {
    if(controlsWindow_){reuniteView(false);return;}
    const auto screens=QGuiApplication::screens();
    if(screens.size()<2){status_->setText("当前只有一块显示器，保持单窗口播放");return;}
    previewOriginal(false);if(isFullScreen())toggleFullscreen();
    dockedGeometry_=saveGeometry();dockedMaximized_=isMaximized();
    QScreen* source=screen();QScreen* target=nullptr;
    for(auto* candidate:screens)if(candidate!=source && (!target || candidate->size().width()*candidate->devicePixelRatio()>target->size().width()*target->devicePixelRatio()))target=candidate;
    if(!target)return;
    displayScreen_=target;
    controlsWindow_=new QMainWindow(this,Qt::Window);controlsWindow_->setObjectName("controlsWindow");controlsWindow_->setWindowTitle("映澈 · 播放控制");
    auto* panel=new QWidget(controlsWindow_);auto* column=new QVBoxLayout(panel);column->setContentsMargins(0,0,0,0);column->setSpacing(0);
    controlsWindow_->setCentralWidget(panel);
    // Only ordinary widgets move. The single video widget and mpv context stay put.
    menus_->setParent(controlsWindow_);controlsWindow_->setMenuBar(menus_);
    column->addWidget(header_);side_->setMaximumWidth(QWIDGETSIZE_MAX);column->addWidget(side_,1);column->addWidget(footer_);
    header_->show();side_->show();footer_->show();menus_->show();
    for(auto* action:actions())controlsWindow_->addAction(action);
    controlsWindow_->resize(qMin(1000,source->availableGeometry().width()),qMin(820,source->availableGeometry().height()));
    controlsWindow_->move(source->availableGeometry().topLeft());controlsWindow_->show();
    setMinimumSize(360,220);showNormal();windowHandle()->setScreen(target);setGeometry(target->geometry());showFullScreen();
    status_->setText("画面已分离；F10 合并，关闭控制窗口会暂停并合并");
}
void PlayerWindow::reuniteView(bool pause) {
    if(!controlsWindow_)return;
    previewOriginal(false);if(pause)video_->property("pause","yes");
    auto* old=controlsWindow_;controlsWindow_=nullptr;displayScreen_=nullptr;
    showNormal();menus_->setParent(this);setMenuBar(menus_);
    mainLayout_->insertWidget(0,header_);middle_->addWidget(side_);side_->setMaximumWidth(380);mainLayout_->addWidget(footer_);
    header_->show();side_->show();footer_->show();menus_->show();middle_->setSizes({900,300});
    old->hide();old->deleteLater();setMinimumSize(850,560);restoreGeometry(dockedGeometry_);
    bool reachable=false;for(auto* s:QGuiApplication::screens())if(s->availableGeometry().intersects(frameGeometry()))reachable=true;
    if(!reachable && QGuiApplication::primaryScreen())move(QGuiApplication::primaryScreen()->availableGeometry().topLeft());
    if(dockedMaximized_)showMaximized();else showNormal();
    video_->update();status_->setText(pause?"窗口已合并并暂停":"已恢复单窗口播放");
}
void PlayerWindow::loadSettings() {
    const QString path=settingsPath();
    QFile file(QFileInfo::exists(path)?path:QDir(QFileInfo(path).absolutePath()).filePath("settings.json"));
    if(!file.open(QIODevice::ReadOnly)) {
        if(file.exists()){settingsWritable_=false;settingsNotice_="配置不可读取，本次不保存";}
        return;
    }
    if(file.size()>4*1024*1024){settingsWritable_=false;settingsNotice_="配置过大，已保留原文件；本次不保存";return;}
    const auto doc=QJsonDocument::fromJson(file.readAll());
    if(!doc.isObject()){settingsWritable_=false;settingsNotice_="配置损坏，已保留原文件；本次不保存";return;}
    const auto obj=doc.object();const int version=obj.value("version").toInt();
    if(version==1) {
        if(!obj.value("beauty").isObject()){settingsWritable_=false;settingsNotice_="旧配置结构损坏，已保留原文件；本次不保存";return;}
        defaults_={{"beauty",sanitizeBeauty(obj.value("beauty").toObject())},{"enabled",true}};
        settingsNotice_="已导入旧全局设置并限制到温和范围；旧配置保留";
    } else if(version==2) {
        bool valid=obj.value("defaults").isObject() && obj.value("defaults").toObject().value("beauty").isObject() && obj.value("media").isObject();
        const auto records=obj.value("media").toObject();
        for(auto it=records.constBegin();valid && it!=records.constEnd();++it)valid=it.value().isObject() && it.value().toObject().value("beauty").isObject();
        if(!valid){settingsWritable_=false;settingsNotice_="配置结构损坏，已保留原文件；本次不保存";return;}
        defaults_=obj.value("defaults").toObject();defaults_["beauty"]=sanitizeBeauty(defaults_.value("beauty").toObject());
        mediaSettings_=obj.value("media").toObject();
    } else {settingsWritable_=false;settingsNotice_="配置版本不支持，保留原文件；本次不保存";return;}
    beauty_=sanitizeBeauty(defaults_.value("beauty").toObject());loadedEnabled_=defaults_.value("enabled").toBool(true);
    positions_=obj.value("positions").toObject();
    lastDirectory_=obj.value("lastDirectory").toString();
}
void PlayerWindow::saveSettings() {
    if(!settingsWritable_)return;
    while(positions_.size()>100)positions_.erase(positions_.begin());
    QSaveFile file(settingsPath());
    if(!file.open(QIODevice::WriteOnly)) {if(status_)status_->setText("设置保存失败：目录不可写");if(pictureStatus_)pictureStatus_->setText("画面参数尚未保存：目录不可写");return;}
    QJsonObject obj{{"version",2},{"defaults",defaults_},{"media",mediaSettings_},{"positions",positions_},{"lastDirectory",lastDirectory_}};
    const auto bytes=QJsonDocument(obj).toJson(QJsonDocument::Compact);
    if(bytes.size()>4*1024*1024){if(pictureStatus_)pictureStatus_->setText("配置达到容量限制，当前调整未保存；原文件保留");return;}
    if(file.write(bytes)!=bytes.size()||!file.commit()) {
        if(status_)status_->setText("设置保存失败");if(pictureStatus_)pictureStatus_->setText("画面参数保存失败，本次调整尚未保存");
    } else if(pictureStatus_ && pictureScope_->currentIndex()!=2) {
        pictureStatus_->setText(pictureScope_->currentIndex()==1?"全局默认已保存":mediaKey_.isEmpty()?"尚未打开可识别的视频":mediaSettings_.contains(mediaKey_)?"单片设置已保存；改名、移动后仍可恢复":"此视频继承全局默认");
    }
}
void PlayerWindow::closeEvent(QCloseEvent* e) {
    closing_=true;previewOriginal(false);updatePlayback();saveSettings();setBridgeEnabled(false);video_->shutdown();
    if(controlsWindow_)controlsWindow_->hide();e->accept();
}
void PlayerWindow::dragEnterEvent(QDragEnterEvent* e) {if(e->mimeData()->hasUrls())e->acceptProposedAction();}
void PlayerWindow::dropEvent(QDropEvent* e) {
    QStringList paths;for(const auto& u:e->mimeData()->urls())if(u.isLocalFile())paths.append(u.toLocalFile());
    openFiles(paths);e->acceptProposedAction();
}
void PlayerWindow::testTick() {
    // Opt-in local testing only. No socket, network listener, or always-on control API.
    QFile cmd(QDir(controlDir_).filePath("command.json"));
    if(cmd.open(QIODevice::ReadOnly)&&cmd.size()<1024*1024) {
        const auto doc=QJsonDocument::fromJson(cmd.readAll());
        if(doc.isObject()) {
            const auto o=doc.object();const auto id=static_cast<qint64>(o.value("id").toDouble(-1));
            if(id>testCommandId_) {
                testCommandId_=id;const QString action=o.value("action").toString();
                if(action=="load")openFiles({o.value("path").toString()});
                else if(action=="seek")video_->seek(o.value("seconds").toDouble());
                else if(action=="pause")video_->property("pause",o.value("value").toBool()?"yes":"no");
                else if(action=="speed")speed_->setValue(o.value("value").toDouble(1));
                else if(action=="engine")video_->setBeautyEngine("gpupixel");
                else if(action=="beauty") {applyBeauty(o.value("values").toObject());rememberPicture();saveDebounce_.start();}
                else if(action=="scope")pictureScope_->setCurrentIndex(o.value("value").toInt());
                else if(action=="reset-picture")resetPicture();
                else if(action=="hold-original")previewOriginal(o.value("value").toBool());
                else if(action=="separate")toggleSeparateView();
                else if(action=="close-controls" && controlsWindow_)controlsWindow_->close();
                else if(action=="screen-loss-contract")reuniteView(true);
                else if(action=="resize")resize(o.value("width").toInt(1220),o.value("height").toInt(760));
                else if(action=="test-stall")QThread::msleep(static_cast<unsigned long>(std::clamp(o.value("ms").toInt(),0,1000)));
                else if(action=="enabled")beautyToggle_->setChecked(o.value("value").toBool());
                else if(action=="compare")compareToggle_->setChecked(o.value("value").toBool());
                else if(action=="swap-source") {sourceLabel_->setText(QFileInfo(o.value("path").toString()).fileName());video_->setSwapSource(o.value("path").toString());}
                else if(action=="swap") {swapToggle_->setChecked(o.value("value").toBool());video_->setSwapOptions(o.value("target").toString("largest"),o.value("feather").toInt(35),o.value("strength").toInt(100));}
                else if(action=="bridge")bridgeToggle_->setChecked(o.value("value").toBool());
                else if(action=="fullscreen")toggleFullscreen();
                else if(action=="snapshot")video_->saveFrame(o.value("path").toString());
                else if(action=="windowshot")grab().save(o.value("path").toString());
                else if(action=="controlshot" && controlsWindow_)controlsWindow_->grab().save(o.value("path").toString());
                else if(action=="quit")close();
            }
        }
    }
    auto state=video_->diagnostics();state["commandId"]=static_cast<double>(testCommandId_);state["file"]=currentFile_;
    state["mediaKey"]=mediaKey_;state["pictureScope"]=pictureScope_->currentIndex();state["pictureStatus"]=pictureStatus_->text();state["separated"]=controlsWindow_!=nullptr;
    state["settingsWritable"]=settingsWritable_;state["analysisStatus"]=analysisLabel_->text();
    state["displayDpr"]=devicePixelRatioF();state["displayScreen"]=screen()?screen()->name():QString();state["controlsScreen"]=controlsWindow_&&controlsWindow_->screen()?controlsWindow_->screen()->name():QString();
    QJsonArray screens;for(auto* s:QGuiApplication::screens())screens.append(QJsonObject{{"name",s->name()},{"width",s->size().width()},{"height",s->size().height()},{"dpr",s->devicePixelRatio()},{"refreshHz",s->refreshRate()}});state["screens"]=screens;
    state["bridgeEnabled"]=bridgeToggle_->isChecked();state["bridgeStatus"]=bridgeLabel_->text();state["swapStatus"]=swapLabel_->text();state["fullscreen"]=isFullScreen();state["windowWidth"]=width();state["windowHeight"]=height();
    QSaveFile output(QDir(controlDir_).filePath("state.json"));
    if(output.open(QIODevice::WriteOnly)) {const auto bytes=QJsonDocument(state).toJson();if(output.write(bytes)==bytes.size())output.commit();}
}
