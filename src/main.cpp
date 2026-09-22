#include "player.h"
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFont>
#include <QSurfaceFormat>
#include <QPainter>
#include <QIcon>
int main(int argc,char** argv) {
    QSurfaceFormat format;format.setVersion(3,3);format.setProfile(QSurfaceFormat::CompatibilityProfile);
    format.setSwapInterval(1);QSurfaceFormat::setDefaultFormat(format);
    QApplication app(argc,argv);
    QPixmap logo(64,64);logo.fill(QColor("#152c25"));
    {QPainter p(&logo);p.setRenderHint(QPainter::Antialiasing);p.setPen(Qt::NoPen);p.setBrush(QColor("#b0dbc1"));p.drawEllipse(8,8,48,48);p.setBrush(QColor("#183c2c"));p.drawPolygon(QPolygonF({QPointF(26,19),QPointF(45,32),QPointF(26,45)}));}
    app.setWindowIcon(QIcon(logo));
    app.setApplicationName("映澈");app.setOrganizationName("BeautyPlayer");
    app.setFont(QFont("Microsoft YaHei UI",10));
    app.setStyleSheet(R"(
QWidget { background:#10181b; color:#dce8e5; font-family:"Microsoft YaHei UI"; font-size:13px; }
QMainWindow { background:#0c1215; }
QLabel { background:transparent; }
QMenuBar { background:#10181b; color:#859995; padding:3px 12px; }
QMenuBar::item:selected,QMenu::item:selected { background:#26423b; border-radius:4px; }
QMenu { background:#172326; border:1px solid #324743; padding:6px; }
QMenu::item { padding:7px 26px; }
#header { background:#142024; border-bottom:1px solid #263638; }
#brand { font-size:23px; font-weight:600; color:#eaf5f0; background:transparent; }
#tag { font-size:10px; letter-spacing:2px; color:#6a9589; background:transparent; }
#fileTitle { color:#93a7a1; background:transparent; }
QPushButton { border:1px solid #354844; border-radius:6px; background:#1b2a2c; padding:7px 12px; }
QPushButton:hover { background:#29413e; border-color:#638c7c; }
QPushButton:pressed { background:#38564b; }
QPushButton[accent="true"] { color:#10241d; background:#9dceb7; border-color:#9dceb7; font-weight:600; }
QPushButton[accent="true"]:hover { background:#bee2ce; }
#footer { background:#142024; border-top:1px solid #273b3c; }
#statusLabel,#analysisLabel { font-size:11px; color:#809b94; background:transparent; }
#timeLabel { color:#a4bcb3; background:transparent; font-size:12px; }
QTabWidget::pane { border:0; background:#131f22; }
QTabBar::tab { background:#172528; padding:10px 23px; border-bottom:2px solid transparent; color:#78938a; }
QTabBar::tab:selected { color:#d4ebdf; border-bottom:2px solid #a1d1b9; }
QScrollArea,QScrollArea>QWidget>QWidget { background:#131f22; }
#sectionLabel { color:#a7cdbb; font-size:12px; font-weight:600; padding-top:10px; }
#muted { color:#6f8d84; font-size:11px; }
QSpinBox,QDoubleSpinBox,QLineEdit { background:#0d171a; border:1px solid #304541; border-radius:4px; padding:4px; selection-background-color:#426b58; }
QSlider::groove:horizontal { height:4px; background:#2b3f3c; border-radius:2px; }
QSlider::sub-page:horizontal { background:#82b99e; border-radius:2px; }
QSlider::handle:horizontal { background:#c4e4ce; border:1px solid #83b297; width:10px; height:10px; margin:-4px 0; border-radius:6px; }
QSlider { min-height:18px; }
#timeline::handle:horizontal { width:12px; margin:-5px 0; border-radius:7px; }
QCheckBox { spacing:8px; background:transparent; }
QCheckBox::indicator { width:15px; height:15px; border:1px solid #4f6c61; border-radius:4px; background:#0d171a; }
QCheckBox::indicator:checked { background:#9acbb0; border:3px solid #547b67; }
QListWidget { border:0; background:#111d20; padding:8px; }
QListWidget::item { padding:12px; border-radius:5px; }
QListWidget::item:selected { background:#29463b; color:#d9eee0; }
QSplitter::handle { background:#243633; width:1px; }
QScrollBar:vertical { width:8px; background:#131f22; }
QScrollBar::handle:vertical { background:#354f44; min-height:30px; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0px; }
QToolTip { background:#263e35; color:#e7f3eb; border:1px solid #486c58; padding:5px; }
)");
    const QString root=QDir(QCoreApplication::applicationDirPath()).absoluteFilePath("..");
    QString control;QStringList files;
    const QStringList arguments=app.arguments();
    for(int i=1;i<arguments.size();i++){
        const QString arg=arguments[i];
        if(arg=="--control-dir"&&i+1<arguments.size())control=arguments[++i];
        else if(!arg.startsWith("--"))files.append(arg);
    }
    PlayerWindow window(QDir(root).absolutePath(),control);
    window.show();
    if(!files.isEmpty())QTimer::singleShot(0,&window,[&window,files]{window.openFiles(files);});
    return app.exec();
}
