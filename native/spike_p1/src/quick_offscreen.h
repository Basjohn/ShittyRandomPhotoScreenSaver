// P1 spike, part B driver: renders a Python-built Qt Quick scene offscreen
// through QQuickRenderControl. With `threaded`, sync and render run on a
// dedicated render QThread while the GUI thread blocks during sync, which is
// the shape of Qt's threaded render loop. No window is ever shown.
#pragma once

#include "gui_helpers.h"

#include <QtCore/QList>
#include <QtCore/QString>

#include <functional>
#include <memory>

class QObject;
class QQuickRenderControl;
class QQuickWindow;
class QRhi;
class QRhiCommandBuffer;

namespace srpss_spike {

class RenderThreadHost;

// N0.7: a frame driver's hooks, called on the session's render thread inside every frame of pacedFrames().
class FrameHooks
{
public:
    virtual ~FrameHooks() = default;
    // After beginFrame (the frame's command buffer is recording, no pass is open), before sync and render.
    virtual void frameStart(QRhi *rhi, QRhiCommandBuffer *cb, int index) = 0;
    // After endFrame and QRhi::finish() (the frame's GPU work is complete, its readbacks are filled).
    virtual void frameEnd(QRhi *rhi, int index) = 0;
};

// N0.7: frames at a fixed period, as a display would take them. Every frame is scheduled on the period grid; a
// frame that completes after its next grid point makes the following frame start at the first grid point after
// its completion (the periods in between are missed, as with vsync). Times in ms from the run's start.
struct PacedFramesResult
{
    bool ok = false;
    QString error;
    double periodMs = 0.0;
    bool highResolutionTimer = false;
    QList<double> scheduledMs; // each frame's grid point
    QList<double> startMs;     // when it really started (after the wait)
    QList<double> completeMs;  // when its GPU work was complete (QRhi::finish() returned)
    int missedPeriods = 0;
};

struct QuickFramesResult
{
    bool ok = false;
    QString error;
    QList<double> frameMs;
    int litPixels = 0;
    quint64 pixelChecksum = 0;
};

// One render-control session: begin() once, frames() any number of times
// (each call with the GIL released), end() once. GUI thread only.
class QuickOffscreenSession
{
public:
    // preserveColor: the offscreen target is created with PreserveColorContents (gui_helpers.h says why).
    QuickOffscreenSession(QQuickRenderControl *control, QQuickWindow *window, int width,
                          int height, bool threaded, bool preserveColor = false);
    ~QuickOffscreenSession();

    bool begin();
    QuickFramesResult frames(QObject *animated, int count, const QString &pngPath);
    // N0.6: a new offscreen target of this size replaces the old one (the caller resizes the window and the
    // scene on the GUI thread before the next frames()).
    bool resize(int width, int height);
    // N0.7: `count` frames paced at `periodMs` (GUI thread waits on a high-resolution waitable timer between
    // frames, no polling), each completed with QRhi::finish() on the render thread so its completion time is
    // known; `hooks` (may be null) runs inside every frame on the render thread.
    PacedFramesResult pacedFrames(QObject *animated, int count, double periodMs, FrameHooks *hooks);
    // N0.7: runs `work` on the render thread outside any frame (resource release); false if not begun.
    bool runOnRenderThread(const std::function<void(QRhi *)> &work);
    void end();

    QString error() const { return m_error; }
    // With preserveColor on Vulkan: what the first-use transition of the target did (quick_offscreen.cpp).
    QString primeNote() const { return m_primeNote; }
    QString backendName() const { return m_backendName; }
    QString deviceName() const { return m_deviceName; }
    quintptr guiThread() const { return m_guiThread; }
    quintptr renderThread() const { return m_renderThread; }
    // Vulkan only (0 / -1 otherwise): the session QRhi's VkDevice and graphics queue (family, index).
    quint64 vkDevice() const { return m_vkDevice; }
    int vkQueueFamily() const { return m_vkQueueFamily; }
    int vkQueueIndex() const { return m_vkQueueIndex; }

private:
    QQuickRenderControl *m_control;
    QQuickWindow *m_window;
    int m_width;
    int m_height;
    std::unique_ptr<RenderThreadHost> m_host;
    bool m_preserveColor = false;
    QString m_primeNote;
    OffscreenTarget m_target;
    bool m_begun = false;
    int m_frameIndex = 0;
    QString m_error;
    QString m_backendName;
    QString m_deviceName;
    quintptr m_guiThread = 0;
    quintptr m_renderThread = 0;
    quint64 m_vkDevice = 0;
    int m_vkQueueFamily = -1;
    int m_vkQueueIndex = -1;
};

} // namespace srpss_spike
