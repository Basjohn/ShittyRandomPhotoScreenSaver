#include "frame_driver.h"

#include "surfaces.h"

#include <rhi/qrhi.h>

#include <QtQuick/QQuickWindow>

namespace srpss_core {

FrameDriver::FrameDriver(std::shared_ptr<const HostFrameSource> source) : m_source(std::move(source)) {}

FrameDriver::~FrameDriver() = default;

void FrameDriver::connectTo(QQuickWindow *window)
{
    // The window's composited surfaces: their nodes draw only while a driver is connected to record their content.
    m_surfaces = WindowSurfaces::forWindow(window);
    m_surfaces->driverAttached();
    // C++ direct connections (D5.2): the slot runs on the thread that emits, Qt's render thread for a window, the hidden
    // host's own render thread for a render control; no Python is involved. The lambdas own the driver, so it lives as
    // long as it is connected; the window as context removes them when the window is destroyed.
    const std::shared_ptr<FrameDriver> self = shared_from_this();
    m_beforeRendering = QObject::connect(window, &QQuickWindow::beforeRendering, window,
                                         [self]() { self->onBeforeRendering(); }, Qt::DirectConnection);
    m_invalidated = QObject::connect(window, &QQuickWindow::sceneGraphInvalidated, window,
                                     [self]() { self->onSceneGraphInvalidated(); }, Qt::DirectConnection);
}

void FrameDriver::requestDetach()
{
    m_detach.storeRelease(1);
}

void FrameDriver::setProbe(const ProbeConfig *config)
{
    {
        QMutexLocker lock(&m_mutex);
        m_wantProbe = config != nullptr;
        if (config)
            m_probeConfig = *config;
    }
    m_probeGeneration.fetchAndAddOrdered(1);
}

void FrameDriver::requestReadback()
{
    m_readbackRequested.storeRelease(1);
}

bool FrameDriver::takeProbeResult(QJsonObject *facts, QByteArray *rgba, int *width, int *height, qint64 *frame)
{
    std::shared_ptr<ProbePass> pass;
    {
        QMutexLocker lock(&m_mutex);
        pass = m_pass;
    }
    return pass && pass->takeResult(facts, rgba, width, height, frame);
}

bool FrameDriver::readbackPending() const
{
    std::shared_ptr<ProbePass> pass;
    {
        QMutexLocker lock(&m_mutex);
        pass = m_pass;
    }
    return pass && pass->readbackPending();
}

void FrameDriver::setError(const QString &error)
{
    QMutexLocker lock(&m_mutex);
    m_error = error;
}

void FrameDriver::disconnectEdges()
{
    if (m_disconnected.testAndSetOrdered(0, 1)) {
        QObject::disconnect(m_beforeRendering);
        QObject::disconnect(m_invalidated);
        if (m_surfaces)
            m_surfaces->driverDetached();
    }
}

bool FrameDriver::releaseAll(QRhi *rhi, bool outsideFrame, const QString &reason)
{
    std::shared_ptr<ProbePass> pass;
    {
        QMutexLocker lock(&m_mutex);
        pass = m_pass;
    }
    const int live = pass ? pass->liveResources() : 0;
    if (pass && !pass->release(rhi, outsideFrame))
        return false; // a readback in flight: the QRhi still writes into it
    QMutexLocker lock(&m_mutex);
    m_releaseReason = reason;
    m_releaseThread = currentThreadNumber();
    m_releasedOnGuiThread = onGuiThread();
    m_releaseLiveBefore = live;
    return true;
}

void FrameDriver::releaseOutsideFrame(QRhi *rhi, const QString &reason)
{
    if (m_released.loadAcquire())
        return;
    if (!releaseAll(rhi, true, reason)) {
        setError(QStringLiteral("%1: a readback was still in flight and no QRhi completed it").arg(reason));
        return;
    }
    if (m_detach.loadAcquire()) {
        {
            QMutexLocker lock(&m_mutex);
            m_pass.reset();
        }
        m_released.storeRelease(1);
        disconnectEdges();
    }
}

void FrameDriver::applyProbeChange(QRhi *rhi, bool outsideFrame)
{
    const int generation = m_probeGeneration.loadAcquire();
    std::shared_ptr<ProbePass> old;
    bool want = false;
    ProbeConfig config;
    {
        QMutexLocker lock(&m_mutex);
        old = m_pass;
        want = m_wantProbe;
        config = m_probeConfig;
    }
    if (old && !old->release(rhi, outsideFrame))
        return; // its readback is in flight: the change is applied at a later edge
    std::shared_ptr<ProbePass> next = want ? std::make_shared<ProbePass>(config) : nullptr;
    {
        QMutexLocker lock(&m_mutex);
        m_pass = next; // its resources are created by its first recording, on this thread
    }
    m_appliedGeneration = generation;
}

void FrameDriver::onBeforeRendering()
{
    m_probe.hit();
    const qint64 edge = m_edges.fetchAndAddRelaxed(1) + 1;
    if (m_released.loadAcquire())
        return; // detached and released; the disconnection is under way
    QRhi *rhi = m_source->rhi();
    if (m_detach.loadAcquire()) {
        m_edgesAfterDetach.fetchAndAddRelaxed(1);
        if (rhi && releaseAll(rhi, false, QStringLiteral("detached: released at the frame edge"))) {
            {
                QMutexLocker lock(&m_mutex);
                m_pass.reset();
            }
            m_released.storeRelease(1);
            disconnectEdges();
        }
        return;
    }
    if (m_probeGeneration.loadAcquire() != m_appliedGeneration)
        applyProbeChange(rhi, false);
    std::shared_ptr<ProbePass> pass;
    {
        QMutexLocker lock(&m_mutex);
        pass = m_pass;
    }
    const QList<std::shared_ptr<Surface>> surfaces = m_surfaces ? m_surfaces->dirtySurfaces()
                                                                : QList<std::shared_ptr<Surface>>();
    if (!pass && surfaces.isEmpty())
        return; // at rest: nothing to record, nothing recorded
    QRhiCommandBuffer *cb = m_source->commandBuffer();
    if (!rhi || !cb) {
        m_edgesWithoutCommandBuffer.fetchAndAddRelaxed(1);
        return;
    }
    // In dependency order (D5.2: background layer, backdrop pyramid, Visualizer scene, overlays): the probe, then the
    // composited surfaces (Qt Quick samples those in its own pass, after this edge).
    bool recorded = false;
    if (pass) {
        const bool readback = !pass->readbackPending() && m_readbackRequested.testAndSetOrdered(1, 0);
        QString error;
        if (pass->record(rhi, cb, readback, edge, &error)) {
            recorded = true;
            m_passesRecorded.fetchAndAddRelaxed(1);
            if (readback)
                m_readbacksStarted.fetchAndAddRelaxed(1);
        } else {
            // The probe is dropped through the ordinary change at the next edge (released there, once nothing is in
            // flight), never retried every frame.
            setError(QStringLiteral("probe pass: ") + error);
            {
                QMutexLocker lock(&m_mutex);
                m_wantProbe = false;
            }
            m_probeGeneration.fetchAndAddOrdered(1);
        }
    }
    for (const std::shared_ptr<Surface> &surface : surfaces) {
        bool surfaceRecorded = false;
        QString error;
        if (!surface->record(rhi, cb, &surfaceRecorded, &error)) {
            setError(QStringLiteral("surface: ") + error);
            continue;
        }
        if (surfaceRecorded) {
            recorded = true;
            m_surfacePassesRecorded.fetchAndAddRelaxed(1);
        }
    }
    if (recorded)
        m_framesRecorded.fetchAndAddRelaxed(1);
}

void FrameDriver::onSceneGraphInvalidated()
{
    // Render thread, outside any frame, the QRhi still alive: everything the core holds on it goes now.
    releaseOutsideFrame(m_source->rhi(), QStringLiteral("scene graph invalidated"));
}

QJsonObject FrameDriver::stateJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("edges"), m_edges.loadRelaxed());
    o.insert(QStringLiteral("edges_on_gui_thread"), m_probe.callsOnGuiThread.loadRelaxed());
    o.insert(QStringLiteral("edges_with_python_thread_state"), m_probe.callsWithPythonThreadState.loadRelaxed());
    o.insert(QStringLiteral("edge_thread"), QString::number(m_probe.lastThread.loadRelaxed()));
    o.insert(QStringLiteral("edges_without_command_buffer"), m_edgesWithoutCommandBuffer.loadRelaxed());
    o.insert(QStringLiteral("frames_recorded"), m_framesRecorded.loadRelaxed());
    o.insert(QStringLiteral("passes_recorded"), m_passesRecorded.loadRelaxed());
    o.insert(QStringLiteral("surface_passes_recorded"), m_surfacePassesRecorded.loadRelaxed());
    o.insert(QStringLiteral("window_surfaces"), m_surfaces ? m_surfaces->count() : 0);
    o.insert(QStringLiteral("readbacks_started"), m_readbacksStarted.loadRelaxed());
    o.insert(QStringLiteral("edges_after_detach"), m_edgesAfterDetach.loadRelaxed());
    o.insert(QStringLiteral("detach_requested"), m_detach.loadRelaxed() != 0);
    o.insert(QStringLiteral("released"), m_released.loadRelaxed() != 0);
    o.insert(QStringLiteral("disconnected"), m_disconnected.loadRelaxed() != 0);
    QMutexLocker lock(&m_mutex);
    o.insert(QStringLiteral("probe"), m_wantProbe ? QJsonValue(m_probeConfig.toJson()) : QJsonValue());
    o.insert(QStringLiteral("probe_live_resources"), m_pass ? m_pass->liveResources() : 0);
    o.insert(QStringLiteral("error"), m_error);
    o.insert(QStringLiteral("release_reason"), m_releaseReason);
    o.insert(QStringLiteral("release_thread"), QString::number(m_releaseThread));
    o.insert(QStringLiteral("released_on_gui_thread"), m_releasedOnGuiThread);
    o.insert(QStringLiteral("live_resources_before_release"), m_releaseLiveBefore);
    return o;
}

} // namespace srpss_core
