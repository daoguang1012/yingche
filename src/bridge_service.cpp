// Tray-resident loopback service for the browser extension. It runs only the frozen 0.4.1 bridge engine,
// so the extension works without opening the player. Protocol, port and security checks are unchanged.
#include <QAction>
#include <QApplication>
#include <QCheckBox>
#include <QCloseEvent>
#include <QDateTime>
#include <QDesktopServices>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFont>
#include <QFrame>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QLocalServer>
#include <QLocalSocket>
#include <QMenu>
#include <QPainter>
#include <QPlainTextEdit>
#include <QPointer>
#include <QProcess>
#include <QPushButton>
#include <QSettings>
#include <QSystemTrayIcon>
#include <QTcpSocket>
#include <QTimer>
#include <QUrl>
#include <QVBoxLayout>
#ifdef Q_OS_WIN
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#endif

namespace {
const char* kInstanceName="yingche-bridge-service";
#ifdef Q_OS_WIN
const char* kRunKey="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run";
#endif
enum class State{Stopped,Starting,Ready,Busy,Failed};

QColor stateColor(State state){
    switch(state){
    case State::Ready:return QColor("#7fd6a4");
    case State::Starting:case State::Busy:return QColor("#e8c26a");
    case State::Failed:return QColor("#f08f7a");
    default:return QColor("#6f8d84");
    }
}
QIcon logo(const QColor& dot=QColor()){
    QPixmap pixmap(64,64);pixmap.fill(Qt::transparent);
    QPainter p(&pixmap);p.setRenderHint(QPainter::Antialiasing);p.setPen(Qt::NoPen);
    p.setBrush(QColor("#b0dbc1"));p.drawEllipse(4,4,56,56);
    p.setBrush(QColor("#183c2c"));p.drawPolygon(QPolygonF({QPointF(25,18),QPointF(46,32),QPointF(25,46)}));
    if(dot.isValid()){p.setBrush(QColor("#0c1215"));p.drawEllipse(37,37,27,27);p.setBrush(dot);p.drawEllipse(41,41,19,19);}
    return QIcon(pixmap);
}
bool portInUse(const QString& text){
    return text.contains("10048")||text.contains("Errno 98")||text.contains("in use",Qt::CaseInsensitive)||text.contains("EADDRINUSE");
}
}

class BridgeService : public QWidget {
public:
    explicit BridgeService(const QString& root):root_(root) {
        setWindowTitle("映澈后台服务");setWindowIcon(logo());setObjectName("service");setFixedWidth(420);
        auto* layout=new QVBoxLayout(this);layout->setContentsMargins(22,20,22,18);layout->setSpacing(14);

        auto* header=new QHBoxLayout;header->setSpacing(12);
        auto* mark=new QLabel(this);mark->setPixmap(logo().pixmap(44,44));header->addWidget(mark);
        auto* names=new QVBoxLayout;names->setSpacing(1);
        auto* brand=new QLabel("映澈后台服务",this);brand->setObjectName("brand");names->addWidget(brand);
        auto* tag=new QLabel("为 Edge / Chrome 扩展提供本机人脸引擎",this);tag->setObjectName("muted");names->addWidget(tag);
        header->addLayout(names,1);layout->addLayout(header);

        auto* card=new QFrame(this);card->setObjectName("card");
        auto* cardLayout=new QVBoxLayout(card);cardLayout->setContentsMargins(16,14,16,14);cardLayout->setSpacing(6);
        auto* titleRow=new QHBoxLayout;titleRow->setSpacing(9);
        dot_=new QLabel(card);dot_->setFixedSize(10,10);titleRow->addWidget(dot_);
        title_=new QLabel(card);title_->setObjectName("stateTitle");titleRow->addWidget(title_,1);
        address_=new QLabel(card);address_->setObjectName("address");titleRow->addWidget(address_);
        cardLayout->addLayout(titleRow);
        detail_=new QLabel(card);detail_->setObjectName("detail");detail_->setWordWrap(true);cardLayout->addWidget(detail_);
        auto* buttons=new QHBoxLayout;buttons->setSpacing(8);buttons->setContentsMargins(0,8,0,0);
        toggle_=new QPushButton(card);toggle_->setProperty("accent",true);buttons->addWidget(toggle_,1);
        restart_=new QPushButton("重启",card);buttons->addWidget(restart_);
        models_=new QPushButton("下载人脸模型",card);models_->hide();buttons->addWidget(models_);
        cardLayout->addLayout(buttons);layout->addWidget(card);

        auto* steps=new QLabel("连接扩展",this);steps->setObjectName("section");layout->addWidget(steps);
        auto* stepOne=new QLabel("① 在 <b>edge://extensions</b> 或 <b>chrome://extensions</b> 开启开发人员模式，加载 <b>edge-extension</b> 文件夹。",this);
        stepOne->setWordWrap(true);stepOne->setObjectName("step");layout->addWidget(stepOne);
        auto* stepTwo=new QLabel("② 打开视频网页，点击扩展图标 →「启用当前视频」。服务运行时无需打开播放器。",this);
        stepTwo->setWordWrap(true);stepTwo->setObjectName("step");layout->addWidget(stepTwo);
        auto* links=new QHBoxLayout;links->setSpacing(8);
        auto* folder=new QPushButton("打开扩展文件夹",this);links->addWidget(folder);
        logButton_=new QPushButton("显示日志",this);logButton_->setCheckable(true);links->addWidget(logButton_);
        links->addStretch(1);layout->addLayout(links);
        log_=new QPlainTextEdit(this);log_->setReadOnly(true);log_->setMaximumBlockCount(200);log_->setFixedHeight(130);log_->hide();layout->addWidget(log_);

        auto* line=new QFrame(this);line->setObjectName("line");line->setFixedHeight(1);layout->addWidget(line);
        autostart_=new QCheckBox("登录 Windows 后自动在后台运行",this);layout->addWidget(autostart_);
#ifndef Q_OS_WIN
        autostart_->hide();
#endif
        auto* note=new QLabel("关闭窗口后服务仍在通知区域运行，右键托盘图标可退出。视频与照片只在本机处理，仅监听 127.0.0.1。",this);
        note->setObjectName("muted");note->setWordWrap(true);layout->addWidget(note);

        connect(toggle_,&QPushButton::clicked,this,[this]{if(wanted_&&(state_==State::Starting||state_==State::Ready))stop();else start();});
        connect(restart_,&QPushButton::clicked,this,[this]{stop();start();});
        connect(models_,&QPushButton::clicked,this,[this]{QDesktopServices::openUrl(QUrl::fromLocalFile(path("DownloadModels.cmd")));});
        connect(folder,&QPushButton::clicked,this,[this]{QDesktopServices::openUrl(QUrl::fromLocalFile(path("edge-extension")));});
        connect(logButton_,&QPushButton::toggled,this,[this](bool on){log_->setVisible(on);logButton_->setText(on?"隐藏日志":"显示日志");fit();});
        connect(autostart_,&QCheckBox::toggled,this,&BridgeService::setAutostart);
        autostart_->setChecked(autostartEnabled());
        if(autostart_->isChecked())setAutostart(true); // Refresh the command after the folder was moved.

        if(QSystemTrayIcon::isSystemTrayAvailable()){
            tray_=new QSystemTrayIcon(logo(stateColor(State::Stopped)),this);
            auto* menu=new QMenu(this);
            statusAction_=menu->addAction("已停止");statusAction_->setEnabled(false);
            menu->addSeparator();
            menu->addAction("打开面板",this,[this]{showPanel();});
            toggleAction_=menu->addAction("启动服务",this,[this]{toggle_->click();});
            menu->addAction("重启服务",this,[this]{stop();start();});
            menu->addAction("打开扩展文件夹",this,[this]{QDesktopServices::openUrl(QUrl::fromLocalFile(path("edge-extension")));});
            menu->addSeparator();
            menu->addAction("退出",this,[this]{quit();});
            tray_->setContextMenu(menu);
            connect(tray_,&QSystemTrayIcon::activated,this,[this](QSystemTrayIcon::ActivationReason reason){
                if(reason==QSystemTrayIcon::Trigger||reason==QSystemTrayIcon::DoubleClick)showPanel();
            });
            tray_->show();
        }
        connect(qApp,&QCoreApplication::aboutToQuit,this,[this]{quitting_=true;stop();});
        setState(State::Stopped,"已停止","点击「启动服务」后扩展即可连接。");
    }
    ~BridgeService() override {
#ifdef Q_OS_WIN
        if(job_)CloseHandle(job_);
#endif
    }

    void showPanel(){showNormal();raise();activateWindow();}

    void start(){
        wanted_=true;attempt_++;fatal_.clear();models_->hide();
        const QString config=path("edge-extension/bridge-config.json");
        QFile file(config);
        if(!file.open(QIODevice::ReadOnly)){fail("缺少 edge-extension/bridge-config.json","请完整解压文件夹，保留 edge-extension 目录。");return;}
        const QJsonObject values=QJsonDocument::fromJson(file.read(64*1024)).object();
        port_=values.value("port").toInt(18766);address_->setText(QString("127.0.0.1:%1").arg(port_));
        if(values.value("extensionId").toString().isEmpty()){fail("扩展配置无效","bridge-config.json 缺少 extensionId。");return;}
        if(!QFileInfo::exists(path("models/face_landmarker.task"))){
            fail("缺少人脸模型","运行 DownloadModels.cmd 并选择 1 安装约 4 MB 的人脸追踪模型，完成后点「重试」。");models_->show();return;
        }
        if(!QFileInfo::exists(path("app/face_engine_v061/FaceEngine.exe"))&&!QFileInfo::exists(path("tools/python/Scripts/python.exe"))){
            fail("缺少本地引擎","找不到 app/face_engine_v061/FaceEngine.exe，请重新完整解压。");return;
        }
        probe();
    }

    void stop(){
        wanted_=false;attempt_++;
        if(engine_&&engine_->state()!=QProcess::NotRunning){
            engine_->terminate();
            if(!engine_->waitForFinished(500)){engine_->kill();engine_->waitForFinished(1000);}
        }
        if(!quitting_)setState(State::Stopped,"已停止","扩展暂时无法连接，点击「启动服务」恢复。");
    }

protected:
    void closeEvent(QCloseEvent* event) override {
        if(tray_&&!quitting_){
            event->ignore();hide();
            if(!hintShown_){hintShown_=true;tray_->showMessage("映澈后台服务","服务仍在后台运行，右键托盘图标可退出。",logo(),3000);}
            return;
        }
        event->accept();quit();
    }

private:
    QString path(const QString& relative) const {return QDir(root_).filePath(relative);}

    // A listener already on the port is usually the player's own Edge connection; never start a second one.
    // While it is held, re-check quietly so the service takes over once the player releases the port.
    void probe(){
        if(state_!=State::Busy)setState(State::Starting,"正在检查端口…","");
        auto* socket=new QTcpSocket(this);const QPointer<QTcpSocket> guard(socket);const int attempt=attempt_;
        auto settle=[this,guard,attempt](bool busy){
            if(!guard||guard->property("settled").toBool())return;
            guard->setProperty("settled",true);guard->abort();guard->deleteLater();
            if(attempt!=attempt_||!wanted_)return;
            if(!busy){launch();return;}
            setState(State::Busy,"端口已被占用",QString("127.0.0.1:%1 已有程序在监听，通常是映澈播放器的 Edge 连接，扩展此时可直接使用。播放器关闭 Edge 连接后，后台服务会自动接管。").arg(port_));
            QTimer::singleShot(5000,this,[this,attempt]{if(attempt==attempt_&&wanted_&&state_==State::Busy)probe();});
        };
        connect(socket,&QTcpSocket::connected,this,[settle]{settle(true);});
        connect(socket,&QTcpSocket::errorOccurred,this,[settle](QAbstractSocket::SocketError){settle(false);});
        QTimer::singleShot(1500,this,[settle]{settle(false);});
        socket->connectToHost(QStringLiteral("127.0.0.1"),static_cast<quint16>(port_));
    }

    void launch(){
        if(!engine_){
            engine_=new QProcess(this);
            connect(engine_,&QProcess::readyReadStandardOutput,this,[this]{consume(engine_->readAllStandardOutput());});
            connect(engine_,&QProcess::readyReadStandardError,this,[this]{
                const QByteArray text=engine_->readAllStandardError();lastError_=(lastError_+QString::fromLocal8Bit(text)).right(4000);append(QString::fromLocal8Bit(text).trimmed());
            });
            connect(engine_,&QProcess::started,this,[this]{track();});
            connect(engine_,&QProcess::errorOccurred,this,[this](QProcess::ProcessError error){
                if(error==QProcess::FailedToStart)fail("无法启动本地引擎","请确认文件完整，并已安装 Microsoft Visual C++ 运行库。");
            });
            connect(engine_,qOverload<int,QProcess::ExitStatus>(&QProcess::finished),this,&BridgeService::finished);
        }
        if(engine_->state()!=QProcess::NotRunning)return;
        ready_=false;output_.clear();lastError_.clear();fatal_.clear();
        setState(State::Starting,"正在启动本地引擎…","首次启动需要载入人脸模型，通常几秒内完成。");
        append(QString("[%1] 启动引擎").arg(QDateTime::currentDateTime().toString("HH:mm:ss")));
        const QStringList bridge={"--bridge",path("models/face_landmarker.task"),path("edge-extension/bridge-config.json")};
        const QString packaged=path("app/face_engine_v061/FaceEngine.exe");
        if(QFileInfo::exists(packaged))engine_->start(packaged,bridge);
        else engine_->start(path("tools/python/Scripts/python.exe"),QStringList{"-u",path("tools/face_worker.py")}+bridge);
    }

    void consume(const QByteArray& chunk){
        output_+=chunk;
        int end;
        while((end=output_.indexOf('\n'))>=0){
            const QByteArray line=output_.left(end).trimmed();output_.remove(0,end+1);
            if(line.isEmpty())continue;
            append(QString::fromUtf8(line));
            const QJsonObject value=QJsonDocument::fromJson(line).object();
            if(value.value("bridgeReady").toBool()){
                ready_=true;
                setState(State::Ready,"运行中","扩展可以连接。在视频网页点击扩展图标 →「启用当前视频」。");
            }
            if(value.contains("fatal"))fatal_=value.value("fatal").toString();
        }
        if(output_.size()>64*1024)output_.clear();
    }

    void finished(int code,QProcess::ExitStatus){
        append(QString("[%1] 引擎已退出（代码 %2）").arg(QDateTime::currentDateTime().toString("HH:mm:ss")).arg(code));
        if(quitting_||!wanted_)return;
        if(portInUse(fatal_)||portInUse(lastError_)){
            const int attempt=attempt_;
            setState(State::Busy,"端口已被占用",QString("127.0.0.1:%1 已被其他程序使用，可能是映澈播放器的 Edge 连接。端口释放后会自动接管。").arg(port_));
            QTimer::singleShot(5000,this,[this,attempt]{if(attempt==attempt_&&wanted_&&state_==State::Busy)probe();});
            return;
        }
        if(ready_){
            const qint64 now=QDateTime::currentMSecsSinceEpoch();
            while(!restarts_.isEmpty()&&now-restarts_.first()>10*60*1000)restarts_.removeFirst();
            if(restarts_.size()<3){
                restarts_.append(now);const int attempt=attempt_;
                setState(State::Starting,"引擎意外退出，正在重启…","两秒后自动重新启动。");
                if(tray_&&!isVisible())tray_->showMessage("映澈后台服务","本地引擎意外退出，正在自动重启。",logo(stateColor(State::Starting)),3000);
                QTimer::singleShot(2000,this,[this,attempt]{if(attempt==attempt_&&wanted_)launch();});
                return;
            }
        }
        const QString reason=!fatal_.isEmpty()?fatal_:lastError_.trimmed().section('\n',-1);
        fail(ready_?"引擎反复退出，已停止重启":"启动失败",reason.isEmpty()?QString("本地引擎退出（代码 %1）。可打开日志查看详情。").arg(code):reason);
    }

    void fail(const QString& title,const QString& detail){
        setState(State::Failed,title,detail);
        if(tray_&&!isVisible())tray_->showMessage("映澈后台服务",title,logo(stateColor(State::Failed)),4000);
    }

    void setState(State state,const QString& title,const QString& detail){
        state_=state;
        const QColor color=stateColor(state);
        dot_->setStyleSheet(QString("background:%1;border-radius:5px;").arg(color.name()));
        title_->setText(title);detail_->setText(detail);detail_->setVisible(!detail.isEmpty());
        const bool running=wanted_&&(state==State::Starting||state==State::Ready);
        toggle_->setText(running?"停止服务":state==State::Stopped?"启动服务":"重试");
        restart_->setEnabled(state==State::Ready);
        if(tray_){
            tray_->setIcon(logo(color));tray_->setToolTip("映澈后台服务 · "+title);
            statusAction_->setText(title);toggleAction_->setText(toggle_->text());
        }
        fit();
    }

    // Wrapped labels only report their height for a given width, so size the fixed-width panel explicitly.
    void fit(){
        layout()->activate();
        setFixedHeight(layout()->hasHeightForWidth()?layout()->totalHeightForWidth(width()):layout()->totalSizeHint().height());
    }

    void append(const QString& text){if(!text.isEmpty())log_->appendPlainText(text);}

    void quit(){quitting_=true;stop();qApp->quit();}

    // A job object ends the engine with this service, so a crash cannot leave the port held by an orphan.
    void track(){
#ifdef Q_OS_WIN
        if(!job_){
            job_=CreateJobObjectW(nullptr,nullptr);
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            if(job_)SetInformationJobObject(job_,JobObjectExtendedLimitInformation,&limits,sizeof(limits));
        }
        if(!job_)return;
        HANDLE process=OpenProcess(PROCESS_SET_QUOTA|PROCESS_TERMINATE,FALSE,static_cast<DWORD>(engine_->processId()));
        if(process){AssignProcessToJobObject(job_,process);CloseHandle(process);}
#endif
    }

    bool autostartEnabled() const {
#ifdef Q_OS_WIN
        return QSettings(kRunKey,QSettings::NativeFormat).contains("YingcheBridge");
#else
        return false;
#endif
    }
    void setAutostart(bool enabled){
#ifdef Q_OS_WIN
        QSettings run(kRunKey,QSettings::NativeFormat);
        if(enabled)run.setValue("YingcheBridge","\""+QDir::toNativeSeparators(QCoreApplication::applicationFilePath())+"\" --tray");
        else run.remove("YingcheBridge");
#else
        Q_UNUSED(enabled);
#endif
    }

    QString root_;
    int port_=18766,attempt_=0;
    bool wanted_=false,ready_=false,quitting_=false,hintShown_=false;
    State state_=State::Stopped;
    QString fatal_,lastError_;
    QByteArray output_;
    QList<qint64> restarts_;
    QProcess* engine_=nullptr;
    QLabel *dot_=nullptr,*title_=nullptr,*detail_=nullptr,*address_=nullptr;
    QPushButton *toggle_=nullptr,*restart_=nullptr,*models_=nullptr,*logButton_=nullptr;
    QCheckBox* autostart_=nullptr;
    QPlainTextEdit* log_=nullptr;
    QSystemTrayIcon* tray_=nullptr;
    QAction *statusAction_=nullptr,*toggleAction_=nullptr;
#ifdef Q_OS_WIN
    HANDLE job_=nullptr;
#endif
};

int main(int argc,char** argv){
    QApplication app(argc,argv);
    app.setApplicationName("映澈后台服务");app.setOrganizationName("BeautyPlayer");app.setQuitOnLastWindowClosed(false);
    {
        // A second launch only brings the running instance forward.
        QLocalSocket other;other.connectToServer(kInstanceName);
        if(other.waitForConnected(300)){other.write("show");other.waitForBytesWritten(300);return 0;}
    }
    QLocalServer::removeServer(kInstanceName);
    QLocalServer instance;instance.listen(kInstanceName);
    app.setFont(QFont("Microsoft YaHei UI",10));
    app.setStyleSheet(R"(
QWidget { background:#10181b; color:#dce8e5; font-family:"Microsoft YaHei UI"; font-size:13px; }
QLabel { background:transparent; }
#brand { font-size:19px; font-weight:600; color:#eaf5f0; }
#muted { font-size:11px; color:#7f9a93; }
#card { background:#152226; border:1px solid #2a3d3e; border-radius:10px; }
#card QLabel, #card QPushButton { background:transparent; }
#stateTitle { font-size:15px; font-weight:600; color:#eaf5f0; }
#address { font-size:11px; color:#8fb3a5; font-family:"Consolas","Microsoft YaHei UI"; }
#detail { font-size:12px; color:#a2bab3; line-height:150%; }
#section { color:#a7cdbb; font-size:12px; font-weight:600; }
#step { font-size:12px; color:#b9cdc7; }
#line { background:#243633; }
QPushButton { border:1px solid #354844; border-radius:6px; background:#1b2a2c; padding:7px 14px; }
#card QPushButton { background:#1b2a2c; }
QPushButton:hover { background:#29413e; border-color:#638c7c; }
QPushButton:pressed { background:#38564b; }
QPushButton:disabled { color:#5d726c; border-color:#26332f; }
QPushButton[accent="true"], #card QPushButton[accent="true"] { color:#10241d; background:#9dceb7; border-color:#9dceb7; font-weight:600; }
QPushButton[accent="true"]:hover { background:#bee2ce; }
QCheckBox { spacing:8px; background:transparent; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #4f6c61; border-radius:4px; background:#0d171a; }
QCheckBox::indicator:checked { background:#9acbb0; border:3px solid #547b67; }
QPlainTextEdit { background:#0b1316; border:1px solid #26383a; border-radius:6px; color:#8fa9a1; font-family:"Consolas"; font-size:11px; }
QMenu { background:#172326; border:1px solid #324743; padding:6px; }
QMenu::item { padding:7px 26px; }
QMenu::item:selected { background:#26423b; border-radius:4px; }
QMenu::item:disabled { color:#8fb3a5; }
QToolTip { background:#263e35; color:#e7f3eb; border:1px solid #486c58; padding:5px; }
)");
    const QString root=QDir(QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("..")).absolutePath();
    BridgeService service(root);
    QObject::connect(&instance,&QLocalServer::newConnection,&service,[&]{
        while(QLocalSocket* socket=instance.nextPendingConnection()){
            QObject::connect(socket,&QLocalSocket::disconnected,socket,&QObject::deleteLater);
            service.showPanel();
        }
    });
    if(!app.arguments().contains("--tray")||!QSystemTrayIcon::isSystemTrayAvailable())service.showPanel();
    service.start();
    return app.exec();
}
