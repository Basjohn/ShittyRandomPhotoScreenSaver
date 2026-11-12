#include "quick_offscreen.h"

#include "image_stats.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QCoreApplication>
#include <QtCore/QElapsedTimer>
#include <QtCore/QMetaObject>
#include <QtCore/QObject>
#include <QtCore/QThread>
#include <QtGui/QOpenGLContext>
#include <QtQuick/QQuickRenderControl>
#include <QtQuick/QQuickRenderTarget>
#include <QtQuick/QQuickWindow>

#include <functional>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002 // Windows 10 1803 and later
#endif

namespace srpss_spike {

// Runs work on the render thread while the GUI thread waits: the GUI thread is
// blocked during sync exactly as with Qt's threaded render loop.
class RenderThreadHost
{
public:
    explicit RenderThreadHost(bool threaded) : m_threaded(threaded)
    {
        if (!m_threaded)
            return;
        m_thread.reset(new QThread);
        m_thread->setObjectName(QStringLiteral("srpss-spike-quick-render"));
        m_context = new QObject;
        m_context->moveToThread(m_thread.get());
        m_thread->start();
    }

    ~RenderThreadHost()
    {
        if (!m_threaded)
            return;
        QObject *context = m_context;
        QMetaObject::invokeMethod(context, [context]() { delete context; },
                                  Qt::BlockingQueuedConnection);
        m_thread->quit();
        m_thread->wait();
    }

    QThread *thread() const { return m_thread.get(); }

    void runBlocking(const std::function<void()> &work)
    {
        if (!m_threaded) {
            work();
            return;
        }
        QMetaObject::invokeMethod(m_context, work, Qt::BlockingQueuedConnection);
    }

private:
    bool m_threaded;
    std::unique_ptr<QThread> m_thread;
    QObject *m_context = nullptr;
};

QuickOffscreenSession::QuickOffscreenSession(QQuickRenderControl *control, QQuickWindow *window,
                                             int width, int height, bool threaded)
    : m_control(control), m_window(window), m_width(width), m_height(height),
      m_host(new RenderThreadHost(threaded))
{
    m_guiThread = quintptr(QThread::currentThreadId());
    if (threaded)
        m_control->prepareThread(m_host->thread());
}

QuickOffscreenSession::~QuickOffscreenSession()
{
    end();
}

bool QuickOffscreenSession::begin()
{
    if (m_window->graphicsApi() == QSGRendererInterface::Vulkan && !m_window->vulkanInstance()) {
        if (!attachVulkanInstance(m_window, &m_error))
            return false;
    }
    m_host->runBlocking([this]() {
        m_renderThread = quintptr(QThread::currentThreadId());
        if (!m_control->initialize()) {
            m_error = QStringLiteral("QQuickRenderControl::initialize failed");
            return;
        }
        QRhi *rhi = m_control->rhi();
        m_backendName = QString::fromLatin1(rhi->backendName());
        m_deviceName = QString::fromUtf8(rhi->driverInfo().deviceName);
        if (rhi->backend() == QRhi::Vulkan) {
            // N0.6: which VkDevice and queue this session's QRhi really runs on (ours, or one Qt created).
            const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
            if (handles) {
                m_vkDevice = quint64(reinterpret_cast<quintptr>(handles->dev));
                m_vkQueueFamily = int(handles->gfxQueueFamilyIdx);
                m_vkQueueIndex = int(handles->gfxQueueIdx);
            }
        }
        if (!createOffscreenTarget(rhi, m_width, m_height, &m_target, &m_error))
            return;
        m_window->setRenderTarget(QQuickRenderTarget::fromRhiRenderTarget(m_target.renderTarget));
        m_begun = true;
    });
    return m_begun;
}

QuickFramesResult QuickOffscreenSession::frames(QObject *animated, int count, const QString &pngPath)
{
    QuickFramesResult res;
    if (!m_begun) {
        res.error = QStringLiteral("session not begun");
        return res;
    }
    QRhiReadbackResult readback;
    bool yUp = false;
    QElapsedTimer timer;
    for (int i = 0; i < count; ++i) {
        timer.start();
        if (animated)
            animated->setProperty("time", double(m_frameIndex++) / 60.0);
        m_control->polishItems(); // GUI thread
        const bool last = i == count - 1;
        m_host->runBlocking([&]() {
            m_control->beginFrame();
            m_control->sync(); // GUI thread is blocked here
            m_control->render();
            if (last && !pngPath.isEmpty()) {
                QRhi *rhi = m_control->rhi();
                yUp = rhi->isYUpInFramebuffer();
                QRhiResourceUpdateBatch *batch = rhi->nextResourceUpdateBatch();
                batch->readBackTexture(QRhiReadbackDescription(m_target.texture), &readback);
                m_control->commandBuffer()->resourceUpdate(batch);
            }
            m_control->endFrame(); // offscreen frame: completes synchronously
        });
        res.frameMs << double(timer.nsecsElapsed()) / 1.0e6;
    }
    if (!pngPath.isEmpty()) {
        const QImage image = imageFromReadback(readback.data, readback.pixelSize, yUp);
        const ImageStats stats = imageStats(image);
        res.litPixels = stats.litPixels;
        res.pixelChecksum = stats.checksum;
        if (image.isNull())
            res.error = QStringLiteral("readback returned no pixels");
        else if (!image.save(pngPath, "PNG"))
            res.error = QStringLiteral("PNG save failed: ") + pngPath;
    }
    res.ok = res.error.isEmpty();
    return res;
}

bool QuickOffscreenSession::resize(int width, int height)
{
    if (!m_begun) {
        m_error = QStringLiteral("session not begun");
        return false;
    }
    bool ok = false;
    m_host->runBlocking([&]() {
        // The old target is released through QRhi's deferred release (a frame in flight keeps it alive).
        m_window->setRenderTarget(QQuickRenderTarget());
        destroyOffscreenTarget(&m_target);
        if (!createOffscreenTarget(m_control->rhi(), width, height, &m_target, &m_error))
            return;
        m_window->setRenderTarget(QQuickRenderTarget::fromRhiRenderTarget(m_target.renderTarget));
        ok = true;
    });
    if (ok) {
        m_width = width;
        m_height = height;
    }
    return ok;
}

namespace {

// A waitable timer the GUI thread blocks on until a frame's grid point (high resolution where Windows offers it;
// the default timer resolution of 15.6 ms would make a 60 Hz grid meaningless).
class GridTimer
{
public:
    GridTimer()
    {
        m_timer = CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
        m_highResolution = m_timer != nullptr;
        if (!m_timer)
            m_timer = CreateWaitableTimerExW(nullptr, nullptr, 0, TIMER_ALL_ACCESS);
    }
    GridTimer(const GridTimer &) = delete;
    GridTimer &operator=(const GridTimer &) = delete;
    ~GridTimer()
    {
        if (m_timer)
            CloseHandle(m_timer);
    }
    bool highResolution() const { return m_highResolution; }
    void waitMs(double ms)
    {
        if (ms <= 0.0 || !m_timer)
            return;
        LARGE_INTEGER due;
        due.QuadPart = -LONGLONG(ms * 10000.0); // relative, in 100 ns units
        if (SetWaitableTimer(m_timer, &due, 0, nullptr, nullptr, FALSE))
            WaitForSingleObject(m_timer, INFINITE);
    }

private:
    HANDLE m_timer = nullptr;
    bool m_highResolution = false;
};

} // namespace

PacedFramesResult QuickOffscreenSession::pacedFrames(QObject *animated, int count, double periodMs,
                                                     FrameHooks *hooks)
{
    PacedFramesResult res;
    res.periodMs = periodMs;
    if (!m_begun) {
        res.error = QStringLiteral("session not begun");
        return res;
    }
    if (periodMs <= 0.0) {
        res.error = QStringLiteral("the period must be positive");
        return res;
    }
    GridTimer timer;
    res.highResolutionTimer = timer.highResolution();
    QElapsedTimer clock;
    clock.start();
    auto nowMs = [&clock]() { return double(clock.nsecsElapsed()) / 1.0e6; };
    double scheduled = 0.0;
    for (int i = 0; i < count; ++i) {
        timer.waitMs(scheduled - nowMs());
        const double start = nowMs();
        if (animated)
            animated->setProperty("time", double(m_frameIndex++) / 60.0);
        m_control->polishItems(); // GUI thread
        double complete = 0.0;
        bool ok = true;
        m_host->runBlocking([&]() {
            QRhi *rhi = m_control->rhi();
            m_control->beginFrame();
            QRhiCommandBuffer *cb = m_control->commandBuffer(); // null when the frame did not begin
            if (!rhi || !cb) {
                ok = false;
                return;
            }
            if (hooks)
                hooks->frameStart(rhi, cb, i);
            m_control->sync(); // GUI thread is blocked here
            m_control->render();
            m_control->endFrame();
            rhi->finish(); // vkQueueWaitIdle on this QRhi's queue: the frame's GPU work is complete
            complete = nowMs();
            if (hooks)
                hooks->frameEnd(rhi, i);
        });
        if (!ok) {
            res.error = QStringLiteral("QQuickRenderControl::beginFrame failed at frame %1").arg(i);
            return res;
        }
        res.scheduledMs << scheduled;
        res.startMs << start;
        res.completeMs << complete;
        scheduled += periodMs;
        const double after = nowMs();
        while (scheduled < after) { // the frame overran: the grid points it covered are missed
            scheduled += periodMs;
            ++res.missedPeriods;
        }
    }
    res.ok = true;
    return res;
}

bool QuickOffscreenSession::runOnRenderThread(const std::function<void(QRhi *)> &work)
{
    if (!m_begun)
        return false;
    m_host->runBlocking([&]() { work(m_control->rhi()); });
    return true;
}

void QuickOffscreenSession::end()
{
    if (!m_host)
        return;
    QThread *guiThread = QCoreApplication::instance() ? QCoreApplication::instance()->thread() : nullptr;
    m_host->runBlocking([this, guiThread]() {
        if (m_begun)
            m_window->setRenderTarget(QQuickRenderTarget());
        destroyOffscreenTarget(&m_target);
        m_control->invalidate();
        // OpenGL only: the QRhi's context was created on, and is affine to, this render thread, which quits next. The
        // render control (and its QRhi) is destroyed later on the GUI thread, which could not make the context
        // current there (a fail-fast at exit, 8 Nov). Release it and hand it back to the GUI thread first, as Qt's
        // threaded render-control pattern does. D3D and Vulkan devices have no thread affinity.
        QRhi *rhi = m_control->rhi();
        if (rhi && guiThread && rhi->backend() == QRhi::OpenGLES2) {
            const auto *handles = static_cast<const QRhiGles2NativeHandles *>(rhi->nativeHandles());
            if (handles && handles->context) {
                handles->context->doneCurrent();
                handles->context->moveToThread(guiThread);
            }
        }
    });
    m_begun = false;
    m_host.reset();
}

} // namespace srpss_spike
