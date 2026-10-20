#pragma once
#include "mpv_api.h"
#include "settings.h"
#include "gpupixel_pipeline.h"
#include <QOpenGLWidget>
#include <QOpenGLFunctions_3_3_Core>
#include <QOpenGLFramebufferObject>
#include <QOpenGLShaderProgram>
#include <QProcess>
#include <QElapsedTimer>
#include <QTimer>
#include <QJsonArray>
#include <QVector2D>
#include <QVariant>
#include <QHash>
#include <array>
#include <deque>
#include <memory>
#include <vector>

class VideoWidget final : public QOpenGLWidget, protected QOpenGLFunctions_3_3_Core {
    Q_OBJECT
    Q_DISABLE_COPY_MOVE(VideoWidget)
public:
    explicit VideoWidget(const QString& root, QWidget* parent = nullptr);
    ~VideoWidget() override;
    void loadFile(const QString& path);
    void command(const QStringList& args);
    void property(const QString& name, const QString& value);
    double number(const char* name, double fallback = 0.) const;
    QString text(const char* name) const;
    QJsonArray tracks() const;
    void seek(double seconds, bool relative = false);
    void setBeauty(const QJsonObject& values);
    void setBeautyEnabled(bool enabled);
    void setBeautyEngine(const QString& engine);
    void setCompare(bool compare);
    void setOriginalPreview(bool value);
    void setSwapEnabled(bool enabled);
    void setSwapSource(const QString& path);
    void setSwapOptions(const QString& target, int feather, int strength);
    void setSyncDisplay(bool enabled);
    void invalidateFaces(bool keepFrames = false);
    QJsonObject diagnostics() const;
    void saveFrame(const QString& path);
    void shutdown();
    bool hasMedia() const { return loaded_; }
    bool isReady() const { return handle_ != nullptr && context_ != nullptr; }
signals:
    void ready();
    void fileLoaded();
    void playbackChanged();
    void ended();
    void errorOccurred(const QString&);
    void analysisStatus(const QString&);
    void swapStatus(const QString&);
    void doubleClicked();
    void clicked();
protected:
    void initializeGL() override;
    void paintGL() override;
    void mouseDoubleClickEvent(QMouseEvent*) override;
    void mouseReleaseEvent(QMouseEvent*) override;
private:
    void pollEvents();
    void renderUpdate();
    void startWorker();
    void workerOutput();
    void submitAnalysis();
    void uploadMask();
    void resetGLBoundary();
    void applyAudioDelay(double ms);
    // Synchronised display: mpv frames are kept in a short ring and shown a constant delay later
    // (audio delayed to match), so every shown frame lies between two finished analyses and effect
    // geometry is interpolated from measurements instead of extrapolated into the future.
    struct FrameSlot { std::unique_ptr<QOpenGLFramebufferObject> fbo; double pts = 0., at = -1e9; int id = -1, epoch = -1; };
    struct Result {
        double at = -1e9, pts = -999.; int generation = -1, faceCount = 0, swapFaces = 0;
        std::array<QVector2D,32> points{}; std::array<QVector2D,4> velocities{}; std::array<float,4> weights{}; std::array<int,4> ids{};
        QImage mask, swap; GLuint maskTexture = 0, swapTexture = 0; bool uploaded = false;
    };
    std::vector<FrameSlot> slots_;
    std::array<Result,4> results_;
    int newestSlot_ = -1, resultCursor_ = 0, frameEpoch_ = 0, shownSlot_ = -1;
    bool syncDisplay_ = true, syncActive_ = false;
    double syncDelayMs_ = 110., audioDelayMs_ = 0., displayPts_ = 0., displayLagMs_ = 0., rtEstimateMs_ = 60.;
    double lastResultAt_ = -1e9, cutAt_ = -1e9, delayTargetMs_ = 110.;
    std::deque<double> roundTrips_, cutCandidates_;
    std::deque<bool> bracketed_;
    int lastShownId_ = -1;
    double playingSince_ = 0.;
    std::array<QVector2D,2> drawnEyes_{};
    QTimer syncWake_;
    QString root_;
    MpvApi api_;
    mpv_handle* handle_ = nullptr;
    mpv_render_context* context_ = nullptr;
    std::unique_ptr<QOpenGLFramebufferObject> frame_;
    std::unique_ptr<QOpenGLFramebufferObject> analysis_;
    std::unique_ptr<QOpenGLFramebufferObject> composite_;
    std::unique_ptr<QOpenGLFramebufferObject> cutSample_;
    std::unique_ptr<QOpenGLShaderProgram> shader_;
    GLuint vao_ = 0, maskTexture_ = 0, swapTexture_ = 0;
    QProcess* worker_ = nullptr;
    QTimer analysisTimer_;
    QByteArray workerBuffer_;
    QImage mask_, swapImage_;
    bool sourceBusy_ = false, swapPending_ = false;
    double swapMs_ = 0., swapAgeMs_ = 0.;
    QString swapError_;
    bool swapEnabled_ = false, swapSourceReady_ = false, sourcePending_ = false;
    QString sourcePath_, swapTarget_ = "largest";
    int swapFeather_ = 35, swapStrength_ = 100, swapFaces_ = 0;
    bool maskDirty_ = true, beautyEnabled_ = true, compare_ = false;
    bool originalPreview_ = false;
    bool fallbackNotice_=false;
    QImage previousCutSample_;
    int cuts_=0;
    double trackingWeight_=0.;
    QJsonArray faceSignals_;
    std::array<float,4> effectWeights_{};
    QTimer transitionTimer_;
    qint64 beautyChangedAt_=0;
    QJsonObject displayedBeauty_=defaultBeauty();
    QJsonObject transitionFromBeauty_=defaultBeauty();
    bool beautyTransitionPending_=false;
    int cutReadbackSamples_=0;
    double cutReadbackMs_=0.,cutReadbackMaxMs_=0.;
    bool glFunctionsReady_ = false, eofSignaled_ = false;
    bool awaitingPlayback_ = false;
    bool needFrame_ = true, loaded_ = false, workerReady_ = false, busy_ = false, stopping_ = false;
    int generation_ = 0, requestId_ = 0, faceCount_ = 0, rendered_ = 0;
    int resultGeneration_ = -1, submittedFrame_ = -1, resultFrame_ = -1;
    double resultPts_ = -999., analysisMs_ = 0.;
    qint64 submittedAt_ = 0;
    QElapsedTimer clock_;
    std::array<QVector2D,32> points_{};
    QJsonObject beauty_ = defaultBeauty();
    GPUPixelPipeline gpupixel_;
    QString beautyEngine_="gpupixel",gpupixelError_;
    bool gpupixelReady_=false,gpupixelDirty_=true;
    GLuint gpupixelTexture_=0;
    int gpupixelFrame_=-1,analysisCompleted_=0;
    double resultSampleTime_=0.,roundTripMs_=0.;
    QString trackingMode_;
    std::array<QVector2D,4> velocities_{};
    QHash<QString,QVariant> properties_;
    QJsonArray tracks_;
    QString pendingFile_, workerError_, glError_;
};
