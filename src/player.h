#pragma once
#include "video.h"
#include <QMainWindow>
#include <QSlider>
#include <QLabel>
#include <QListWidget>
#include <QSpinBox>
#include <QDoubleSpinBox>
#include <QPushButton>
#include <QCheckBox>
#include <QTabWidget>
#include <QTimer>
#include <QMap>
#include <QCloseEvent>
#include <QDropEvent>
#include <QComboBox>
#include <QSplitter>
#include <QVBoxLayout>
#include <QPointer>
#include <QScreen>

class SeekSlider final: public QSlider {
    Q_OBJECT
public:
    explicit SeekSlider(QWidget* parent=nullptr):QSlider(Qt::Horizontal,parent) {}
protected:
    void mousePressEvent(QMouseEvent*) override;
    void mouseMoveEvent(QMouseEvent*) override;
    void mouseReleaseEvent(QMouseEvent*) override;
private:
    int at(const QMouseEvent*) const;
};
class PlayerWindow final: public QMainWindow {
    Q_OBJECT
    Q_DISABLE_COPY_MOVE(PlayerWindow)
public:
    explicit PlayerWindow(const QString& root,const QString& controlDir=QString(),QWidget* parent=nullptr);
    void openFiles(const QStringList& files);
    void openFile(const QString& file);
protected:
    void closeEvent(QCloseEvent*) override;
    void dragEnterEvent(QDragEnterEvent*) override;
    void dropEvent(QDropEvent*) override;
    bool eventFilter(QObject*,QEvent*) override;
private:
    void buildUi();
    void buildMenus();
    void buildSwapPanel();
    void chooseSwapSource();
    void setBridgeEnabled(bool enabled);
    void updatePlayback();
    void saveSettings();
    void loadSettings();
    void applyBeauty(const QJsonObject&);
    void rememberPicture();
    void restorePicture(int scope);
    void resetPicture();
    QString settingsPath() const;
    void toggleSeparateView();
    void reuniteView(bool pause);
    void previewOriginal(bool value);
    void toggleFullscreen();
    void openDialog();
    void jumpDialog();
    void subtitleDialog();
    void screenshot();
    void nextFile(int delta);
    void testTick();
    QString root_,controlDir_,currentFile_,lastDirectory_,displayedCodec_;
    VideoWidget* video_=nullptr;
    QWidget *header_=nullptr,*footer_=nullptr;
    QTabWidget* side_=nullptr;
    QListWidget* playlist_=nullptr;
    SeekSlider* timeline_=nullptr;
    QLabel *timeLabel_=nullptr,*fileLabel_=nullptr,*status_=nullptr,*analysisLabel_=nullptr;
    QPushButton* play_=nullptr;
    QDoubleSpinBox* speed_=nullptr;
    QSlider* volume_=nullptr;
    QCheckBox *beautyToggle_=nullptr,*compareToggle_=nullptr,*mute_=nullptr;
    QMap<QString,QSpinBox*> fields_;
    QCheckBox *swapToggle_=nullptr,*bridgeToggle_=nullptr;
    QLabel *sourceLabel_=nullptr,*swapLabel_=nullptr,*bridgeLabel_=nullptr;
    QComboBox* swapTarget_=nullptr;
    QSpinBox *swapStrength_=nullptr,*swapFeather_=nullptr;
    QProcess* bridge_=nullptr;
    QByteArray bridgeOutput_;
    QJsonObject beauty_=defaultBeauty(),positions_;
    QJsonObject defaults_{{"beauty",defaultBeauty()},{"enabled",true}},mediaSettings_;
    QString mediaKey_,settingsNotice_;
    bool loadedEnabled_=true,settingsWritable_=true,closing_=false,originalHeld_=false;
    QComboBox* pictureScope_=nullptr;
    QLabel* pictureStatus_=nullptr;
    QPushButton* holdOriginal_=nullptr;
    QMainWindow* controlsWindow_=nullptr;
    QPointer<QScreen> displayScreen_;
    QSplitter* middle_=nullptr;
    QVBoxLayout* mainLayout_=nullptr;
    QMenuBar* menus_=nullptr;
    QByteArray dockedGeometry_;
    bool dockedMaximized_=false;
    QTimer tick_,seekDebounce_,saveDebounce_,testTimer_;
    bool applying_=false,wasMaximized_=false,sideBeforeFull_=true;
    qint64 testCommandId_=-1;
    double duration_=0., resumeAt_=0.;
    bool resumePending_=false;
};
