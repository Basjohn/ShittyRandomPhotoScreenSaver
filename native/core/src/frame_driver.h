// The frame driver (D5.2): one per attached window, it owns the core's per-frame edge. It is connected in C++, with a
// direct connection, to the window's beforeRendering signal (Qt's render thread, after the frame's command buffer began
// recording and before Qt Quick's own pass), so no Python slot and no GIL is ever on that edge (D5.4); it records all of
// the core's work for the frame there, in dependency order: the probe pass and the known-cost pass (only while a harness
// asks for them), then the window's composited surfaces whose content changed (surfaces.h; Qt Quick samples them in its
// own pass, after this edge). With nothing to record it records nothing: a frame at rest costs one call, a few atomics
// and one look at the window's surfaces.
//
// The GPU timer (gpu_timer.h, N2.6) lives here because this is where every pass of the core is recorded: while it is on,
// each pass above is bracketed whole, outside any render pass, and the results are read at later edges into the driver's
// queue (takeGpuSamples). While it is off the driver holds no timer: no query object, no call per frame.
//
// Its GPU resources are created and released on the render thread only: at a frame edge, at the window's
// sceneGraphInvalidated (the QRhi still exists; Qt's render thread or the hidden host's), or by the hidden host's close.
// Detaching stops the recording at once; the release then follows at the next edge that has no readback in flight (or at
// the scene graph's invalidation, whichever comes first), after which the driver disconnects itself.
#pragma once

#include "gpu_timer.h"
#include "load_pass.h"
#include "probe_pass.h"
#include "thread_probe.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QJsonObject>
#include <QtCore/QMetaObject>
#include <QtCore/QMutex>
#include <QtCore/QString>

#include <memory>

class QQuickWindow;
class QRhi;
class QRhiCommandBuffer;

namespace srpss_core {

class WindowSurfaces;

// What a host gives the core each frame (D5.1): the device and this frame's command buffer. Called on the render
// thread inside the frame edge only. The Qt Quick window host and the hidden host each implement it.
class HostFrameSource
{
public:
    virtual ~HostFrameSource() = default;
    virtual QRhi *rhi() const = 0;
    virtual QRhiCommandBuffer *commandBuffer() const = 0;
};

class FrameDriver : public std::enable_shared_from_this<FrameDriver>
{
public:
    explicit FrameDriver(std::shared_ptr<const HostFrameSource> source);
    ~FrameDriver();
    FrameDriver(const FrameDriver &) = delete;
    FrameDriver &operator=(const FrameDriver &) = delete;

    // GUI thread, once: the C++ direct connections to the window's frame edge and its scene graph invalidation.
    void connectTo(QQuickWindow *window);

    // GUI thread: stop recording now; the resources go at the next edge without a readback in flight, or at the
    // scene graph's invalidation.
    void requestDetach();
    bool detachRequested() const { return m_detach.loadAcquire() != 0; }
    // Render thread, outside any frame (the hidden host's close, a scene graph invalidation): release everything now.
    void releaseOutsideFrame(QRhi *rhi, const QString &reason);

    // GUI thread: the probe pass with this configuration from the next frame (null: none); its readback request.
    void setProbe(const ProbeConfig *config);
    void requestReadback();
    // Any thread: the last completed probe readback (see ProbePass::takeResult).
    bool takeProbeResult(QJsonObject *facts, QByteArray *rgba, int *width, int *height, qint64 *frame);

    // GUI thread: the known-cost pass (load_pass.h) with this configuration from the next frame (null: none).
    void setLoad(const LoadConfig *config);
    // GUI thread: the GPU timer switched on or off (gpu_timer.h) from the next frame.
    void setGpuTimer(const GpuTimerConfig &config);
    // Any thread: the timer's results read since the last call, oldest first.
    QList<GpuTimingSample> takeGpuSamples();

    bool released() const { return m_released.loadAcquire() != 0; }
    bool readbackPending() const;
    QJsonObject stateJson() const;

    // The frame edge (render thread, the direct connection).
    void onBeforeRendering();
    void onSceneGraphInvalidated();

private:
    void applyProbeChange(QRhi *rhi, bool outsideFrame);
    void applyPassChanges(QRhi *rhi, qint64 edge);
    bool releaseAll(QRhi *rhi, bool outsideFrame, const QString &reason);
    void releaseLoadAndTimer(QRhi *rhi, bool outsideFrame);
    void disconnectEdges();
    void setError(const QString &error);
    int timerBegin(QRhi *rhi, QRhiCommandBuffer *cb, GpuPassKind kind);
    void timerEnd(QRhi *rhi, QRhiCommandBuffer *cb, int scope);

    std::shared_ptr<const HostFrameSource> m_source;
    std::shared_ptr<WindowSurfaces> m_surfaces; // the window's composited surfaces (set once, at connectTo)
    QMetaObject::Connection m_beforeRendering;
    QMetaObject::Connection m_invalidated;

    ThreadProbe m_probe;                          // every edge
    QAtomicInteger<qint64> m_edges { 0 };
    QAtomicInteger<qint64> m_edgesWithoutCommandBuffer { 0 };
    QAtomicInteger<qint64> m_framesRecorded { 0 }; // edges that recorded core work
    QAtomicInteger<qint64> m_passesRecorded { 0 };  // probe passes
    QAtomicInteger<qint64> m_surfacePassesRecorded { 0 };
    QAtomicInteger<qint64> m_edgesAfterDetach { 0 };
    QAtomicInteger<qint64> m_readbacksStarted { 0 };
    QAtomicInteger<int> m_detach { 0 };
    QAtomicInteger<int> m_released { 0 };
    QAtomicInteger<int> m_disconnected { 0 };
    QAtomicInteger<int> m_readbackRequested { 0 };
    QAtomicInteger<int> m_probeGeneration { 0 };   // bumped by setProbe (GUI); applied at the edge
    int m_appliedGeneration = 0;                   // render thread

    QAtomicInteger<qint64> m_loadPassesRecorded { 0 };
    QAtomicInteger<qint64> m_timerEdges { 0 };     // edges at which a timer existed (zero while it is off)
    QAtomicInteger<int> m_passGeneration { 0 };    // bumped by setLoad and setGpuTimer (GUI); applied at the edge
    int m_appliedPassGeneration = 0;               // render thread

    // The GPU timer: created, used and destroyed on the render thread; read by stateJson under m_timerMutex. Null while
    // the timer is off (the render thread tests the pointer alone then; no lock is taken).
    mutable QMutex m_timerMutex;
    std::unique_ptr<GpuTimer> m_timer;
    QJsonObject m_lastTimerState; // the last timer's record, once its objects went
    std::shared_ptr<GpuSampleQueue> m_samples;

    mutable QMutex m_mutex; // guards the members below
    bool m_wantProbe = false;
    ProbeConfig m_probeConfig;
    std::shared_ptr<ProbePass> m_pass;  // swapped on the render thread; read (shared) by takeProbeResult
    bool m_wantLoad = false;
    LoadConfig m_loadConfig;
    std::shared_ptr<LoadPass> m_load;   // swapped on the render thread
    GpuTimerConfig m_timerConfig;
    QString m_error;
    QString m_releaseReason;
    quint64 m_releaseThread = 0;
    bool m_releasedOnGuiThread = false;
    qint64 m_releaseLiveBefore = -1;
};

} // namespace srpss_core
