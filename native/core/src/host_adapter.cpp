#include "host_adapter.h"

#include "targets.h"
#include "vulkan_context.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QCoreApplication>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QMetaObject>
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtCore/QThread>
#include <QtGui/QOpenGLContext>
#include <QtQuick/QQuickItem>
#include <QtQuick/QQuickRenderControl>
#include <QtQuick/QQuickRenderTarget>
#include <QtQuick/QQuickWindow>
#include <QtQuick/QSGRendererInterface>

#include <cmath>
#include <cstring>
#include <utility>

namespace srpss_core {

bool parseHostKind(const char *text, HostKind *kind)
{
    if (!text || !kind)
        return false;
    if (std::strcmp(text, "window") == 0) {
        *kind = HostKind::Window;
        return true;
    }
    if (std::strcmp(text, "hidden") == 0) {
        *kind = HostKind::Hidden;
        return true;
    }
    return false;
}

namespace {

QString graphicsApiName()
{
    switch (QQuickWindow::graphicsApi()) {
    case QSGRendererInterface::OpenGL:
        return QStringLiteral("opengl");
    case QSGRendererInterface::Vulkan:
        return QStringLiteral("vulkan");
    case QSGRendererInterface::Direct3D11:
        return QStringLiteral("d3d11");
    case QSGRendererInterface::Direct3D12:
        return QStringLiteral("d3d12");
    case QSGRendererInterface::Metal:
        return QStringLiteral("metal");
    default:
        return QStringLiteral("other");
    }
}

bool onVulkan()
{
    return QQuickWindow::graphicsApi() == QSGRendererInterface::Vulkan;
}

QJsonArray stringsJson(const QStringList &list)
{
    QJsonArray a;
    for (const QString &s : list)
        a.append(s);
    return a;
}

// The Qt Quick window's frame (render thread, inside beforeRendering): Qt's QRhi and this frame's command buffer, the
// swapchain's for a window Qt presents, the redirected one for a window rendering into a QQuickRenderTarget.
class WindowFrameSource final : public HostFrameSource
{
public:
    explicit WindowFrameSource(QQuickWindow *window) : m_window(window) {}
    QRhi *rhi() const override { return m_window->rhi(); }
    QRhiCommandBuffer *commandBuffer() const override
    {
        QSGRendererInterface *rif = m_window->rendererInterface();
        if (!rif)
            return nullptr;
        auto *swapchain = static_cast<QRhiSwapChain *>(
            rif->getResource(m_window, QSGRendererInterface::RhiSwapchainResource));
        if (swapchain)
            return swapchain->currentFrameCommandBuffer();
        return static_cast<QRhiCommandBuffer *>(
            rif->getResource(m_window, QSGRendererInterface::RhiRedirectCommandBuffer));
    }

private:
    QQuickWindow *m_window; // valid whenever the window emits (the only time this is called)
};

// The render control's frame (the hidden host's render thread).
class ControlFrameSource final : public HostFrameSource
{
public:
    explicit ControlFrameSource(QQuickRenderControl *control) : m_control(control) {}
    QRhi *rhi() const override { return m_control->rhi(); }
    QRhiCommandBuffer *commandBuffer() const override { return m_control->commandBuffer(); }

private:
    QQuickRenderControl *m_control; // valid while the host's window emits (the host deletes both together)
};

} // namespace

// ------------------------------------------------------------------------------------------------- Host

Host::~Host() = default;

bool Host::setProbe(const ProbeConfig *config, QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->setProbe(config);
    return true;
}

bool Host::requestReadback(QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->requestReadback();
    return true;
}

bool Host::takeProbeResult(QJsonObject *facts, QByteArray *rgba, int *width, int *height, qint64 *frame)
{
    return m_driver && m_driver->takeProbeResult(facts, rgba, width, height, frame);
}

QJsonObject Host::stateJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("kind"), kind() == HostKind::Window ? QStringLiteral("window") : QStringLiteral("hidden"));
    o.insert(QStringLiteral("graphics_api"), graphicsApiName());
    o.insert(QStringLiteral("attached"), m_driver != nullptr);
    o.insert(QStringLiteral("attachments"), m_attachments);
    o.insert(QStringLiteral("driver"), m_driver ? QJsonValue(m_driver->stateJson()) : QJsonValue());
    o.insert(QStringLiteral("previous_driver"), m_lastDriver ? QJsonValue(m_lastDriver->stateJson()) : QJsonValue());
    o.insert(QStringLiteral("gui_thread"), QString::number(currentThreadNumber()));
    return o;
}

// ------------------------------------------------------------------------------------------------- WindowHost

// What the core keeps per Qt Quick window, from its first host to the window's destruction: the module's device on
// Vulkan (it must outlive the QQuickWindow object, facts A7) and whether the window still exists.
struct WindowHost::WindowRecord
{
    QQuickWindow *window = nullptr; // valid while !destroyed
    bool destroyed = false;
    std::unique_ptr<VulkanDevice> device;
    QJsonObject deviceFacts;
    QStringList deviceTeardown;
};

namespace {

QHash<QQuickWindow *, std::shared_ptr<WindowHost::WindowRecord>> &windowRecords()
{
    static QHash<QQuickWindow *, std::shared_ptr<WindowHost::WindowRecord>> records;
    return records;
}

} // namespace

std::unique_ptr<WindowHost> WindowHost::create(QObject *object, QString *error)
{
    auto *window = qobject_cast<QQuickWindow *>(object);
    if (!window) {
        *error = QStringLiteral("a host hands over a QQuickWindow; this object is not one");
        return {};
    }
    std::shared_ptr<WindowRecord> record = windowRecords().value(window);
    if (!record) {
        record = std::make_shared<WindowRecord>();
        record->window = window;
        if (onVulkan()) {
            // D6: the module's device, given to Qt Quick before the scene graph initialises; refused afterwards (Qt
            // would already render on a device of its own).
            if (window->isSceneGraphInitialized() || window->rhi()) {
                *error = QStringLiteral("on Vulkan a window is hosted before it is first shown: its scene graph runs on "
                                        "a device that is not the module's (D6)");
                return {};
            }
            record->device = VulkanDevice::create(error);
            if (!record->device)
                return {};
            record->device->applyTo(window);
            record->deviceFacts.insert(QStringLiteral("vk_device"), QString::number(record->device->device()));
            record->deviceFacts.insert(QStringLiteral("queue_family"), qint64(record->device->family()));
            record->deviceFacts.insert(QStringLiteral("name"), record->device->deviceName());
        }
        // GUI thread, after Qt's render thread released the window's scene graph and QRhi (the window's destructor
        // waits for that): the device goes now (vkDeviceWaitIdle, vkDestroyDevice, resetDeviceFunctions).
        std::weak_ptr<WindowRecord> weak = record;
        QObject::connect(window, &QObject::destroyed, [weak, window](QObject *) {
            const std::shared_ptr<WindowRecord> r = weak.lock(); // before the registry lets go of it
            windowRecords().remove(window);
            if (r) {
                r->destroyed = true;
                r->window = nullptr;
                if (r->device) {
                    r->deviceTeardown = r->device->destroy();
                    r->device.reset();
                }
            }
        });
        windowRecords().insert(window, record);
    }
    std::unique_ptr<WindowHost> host(new WindowHost(record));
    if (!host->attach(error))
        return {};
    return host;
}

WindowHost::WindowHost(std::shared_ptr<WindowRecord> record)
    : m_record(std::move(record)), m_source(std::make_shared<WindowFrameSource>(m_record->window))
{
}

WindowHost::~WindowHost()
{
    QString ignored;
    if (m_driver)
        detach(&ignored);
}

bool WindowHost::attach(QString *error)
{
    if (m_record->destroyed) {
        *error = QStringLiteral("the window was destroyed");
        return false;
    }
    if (m_driver) {
        *error = QStringLiteral("the host is attached already");
        return false;
    }
    m_driver = std::make_shared<FrameDriver>(m_source);
    m_driver->connectTo(m_record->window);
    ++m_attachments;
    m_record->window->update(); // the first edge comes with the next frame
    return true;
}

bool WindowHost::detach(QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->requestDetach();
    m_lastDriver = m_driver;
    m_driver.reset();
    // The release happens on Qt's render thread at the next frame edge (or at the scene graph's invalidation): ask for
    // that frame. A window that renders no more frames releases when its scene graph goes.
    if (!m_record->destroyed && m_record->window)
        m_record->window->update();
    return true;
}

QJsonObject WindowHost::stateJson() const
{
    QJsonObject o = Host::stateJson();
    o.insert(QStringLiteral("window_destroyed"), m_record->destroyed);
    o.insert(QStringLiteral("device"), m_record->deviceFacts);
    o.insert(QStringLiteral("device_alive"), m_record->device != nullptr);
    o.insert(QStringLiteral("device_teardown"), stringsJson(m_record->deviceTeardown));
    if (!m_record->destroyed && m_record->window)
        o.insert(QStringLiteral("scene_graph_initialized"), m_record->window->isSceneGraphInitialized());
    return o;
}

// ------------------------------------------------------------------------------------------------- HiddenHost

// Runs work on the hidden host's render thread while the calling thread waits, as Qt's threaded render loop blocks the
// GUI thread during sync (native/spike_p1's RenderThreadHost). Not threaded: the work runs on the calling thread.
class HiddenHost::RenderThread
{
public:
    explicit RenderThread(bool threaded) : m_threaded(threaded)
    {
        if (!m_threaded)
            return;
        m_thread.reset(new QThread);
        m_thread->setObjectName(QStringLiteral("srpss-core-hidden-render"));
        m_context = new QObject;
        m_context->moveToThread(m_thread.get());
        m_thread->start();
    }

    ~RenderThread()
    {
        if (!m_threaded)
            return;
        QObject *context = m_context;
        QMetaObject::invokeMethod(context, [context]() { delete context; }, Qt::BlockingQueuedConnection);
        m_thread->quit();
        m_thread->wait();
    }

    QThread *thread() const { return m_thread.get(); }
    bool threaded() const { return m_threaded; }

    // A template, not std::function (whose call path lives in msvcp140.dll, which the core never imports).
    template <typename Work>
    void run(Work work)
    {
        if (!m_threaded) {
            work();
            return;
        }
        QMetaObject::invokeMethod(m_context, std::move(work), Qt::BlockingQueuedConnection);
    }

private:
    bool m_threaded;
    std::unique_ptr<QThread> m_thread;
    QObject *m_context = nullptr;
};

struct HiddenHost::State
{
    int width = 0;  // device pixels
    int height = 0;
    double dpr = 1.0;
    QQuickRenderControl *control = nullptr; // owned
    QQuickWindow *window = nullptr;         // owned
    std::unique_ptr<RenderThread> thread;
    std::shared_ptr<const HostFrameSource> source;
    std::unique_ptr<VulkanDevice> device;
    ColorTarget target; // Qt Quick's own target (render thread)
    QPointer<QQuickItem> content;
    bool initialized = false;
    bool closed = false;
    qint64 frames = 0;
    QString backend;
    QString deviceName;
    QString primeNote;
    quint64 guiThread = 0;
    quint64 renderThread = 0;
    QJsonObject deviceFacts;
    QJsonObject closeRecord;
    qint64 readbacks = 0;

    QSizeF logicalSize() const { return QSizeF(width / dpr, height / dpr); }
    // Render thread (the GUI thread waiting): Qt Quick's target with the device pixel ratio it renders at.
    void applyRenderTarget()
    {
        QQuickRenderTarget quickTarget = QQuickRenderTarget::fromRhiRenderTarget(target.renderTarget.get());
        quickTarget.setDevicePixelRatio(dpr);
        window->setRenderTarget(quickTarget);
    }
    // GUI thread: the scene's logical size.
    void applyLogicalSize()
    {
        const QSizeF logical = logicalSize();
        window->setGeometry(0, 0, int(std::lround(logical.width())), int(std::lround(logical.height())));
        window->contentItem()->setSize(logical);
        if (content)
            content->setSize(logical);
    }
};

HiddenHost::HiddenHost() : m_state(new State) {}

HiddenHost::~HiddenHost()
{
    close();
}

std::unique_ptr<HiddenHost> HiddenHost::create(int width, int height, bool threaded, double dpr, QString *error)
{
    if (width < 1 || height < 1) {
        *error = QStringLiteral("a hidden host has a size");
        return {};
    }
    if (!(dpr >= 0.25 && dpr <= 8.0)) {
        *error = QStringLiteral("a hidden host's device pixel ratio is 0.25 to 8");
        return {};
    }
    std::unique_ptr<HiddenHost> host(new HiddenHost);
    State &s = *host->m_state;
    s.width = width;
    s.height = height;
    s.dpr = dpr;
    s.guiThread = currentThreadNumber();
    s.control = new QQuickRenderControl;
    s.window = new QQuickWindow(s.control); // never shown
    s.applyLogicalSize();
    if (onVulkan()) {
        s.device = VulkanDevice::create(error);
        if (!s.device) {
            host->close();
            return {};
        }
        s.device->applyTo(s.window);
        s.deviceFacts.insert(QStringLiteral("vk_device"), QString::number(s.device->device()));
        s.deviceFacts.insert(QStringLiteral("queue_family"), qint64(s.device->family()));
        s.deviceFacts.insert(QStringLiteral("name"), s.device->deviceName());
    }
    s.thread.reset(new RenderThread(threaded));
    if (threaded)
        s.control->prepareThread(s.thread->thread());
    s.source = std::make_shared<ControlFrameSource>(s.control);
    QString failure;
    s.thread->run([&s, &failure]() {
        s.renderThread = currentThreadNumber();
        if (!s.control->initialize()) {
            failure = QStringLiteral("QQuickRenderControl::initialize failed");
            return;
        }
        s.initialized = true;
        QRhi *rhi = s.control->rhi();
        s.backend = QString::fromLatin1(rhi->backendName());
        s.deviceName = QString::fromUtf8(rhi->driverInfo().deviceName);
        // With a depth-stencil buffer: Qt Quick draws its opaque items front to back against it and clips with the
        // stencil (N2.4 build round 1: without one an opaque item vanished under its opaque parent on every backend).
        if (!createColorTarget(rhi, QSize(s.width, s.height), QByteArrayLiteral("srpss hidden host Qt Quick target"),
                               &s.target, &failure, true))
            return;
        s.primeNote = primeForLoadOutsideFrame(rhi, s.target.texture.get()); // rule C, at creation
        s.applyRenderTarget();
    });
    if (!failure.isEmpty()) {
        *error = failure;
        host->close();
        return {};
    }
    if (!host->attach(error)) {
        host->close();
        return {};
    }
    return host;
}

bool HiddenHost::attach(QString *error)
{
    State &s = *m_state;
    if (s.closed || !s.initialized) {
        *error = QStringLiteral("the hidden host is closed");
        return false;
    }
    if (m_driver) {
        *error = QStringLiteral("the host is attached already");
        return false;
    }
    m_driver = std::make_shared<FrameDriver>(s.source);
    m_driver->connectTo(s.window);
    ++m_attachments;
    return true;
}

bool HiddenHost::detach(QString *error)
{
    State &s = *m_state;
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    const std::shared_ptr<FrameDriver> driver = m_driver;
    driver->requestDetach();
    // The hidden host owns its render thread: the release runs there now, outside any frame.
    s.thread->run([&s, driver]() { driver->releaseOutsideFrame(s.control->rhi(), QStringLiteral("detached")); });
    m_lastDriver = driver;
    m_driver.reset();
    return true;
}

bool HiddenHost::setContent(QQuickItem *item, QString *error)
{
    State &s = *m_state;
    if (s.closed) {
        *error = QStringLiteral("the hidden host is closed");
        return false;
    }
    if (s.content)
        s.content->setParentItem(nullptr);
    s.content = item;
    if (item) {
        item->setParentItem(s.window->contentItem());
        item->setSize(s.logicalSize());
    }
    return true;
}

bool HiddenHost::setDevicePixelRatio(double dpr, QString *error)
{
    State &s = *m_state;
    if (s.closed || !s.initialized) {
        *error = QStringLiteral("the hidden host is closed");
        return false;
    }
    if (!(dpr >= 0.25 && dpr <= 8.0)) {
        *error = QStringLiteral("a hidden host's device pixel ratio is 0.25 to 8");
        return false;
    }
    s.dpr = dpr;
    s.applyLogicalSize();                       // the GUI thread
    s.thread->run([&s]() { s.applyRenderTarget(); });
    return true;
}

bool HiddenHost::frames(int count, QString *error)
{
    return renderFrames(count, nullptr, error);
}

bool HiddenHost::readFrame(QuickReadback *out, QString *error)
{
    return renderFrames(1, out, error);
}

bool HiddenHost::renderFrames(int count, QuickReadback *readLast, QString *error)
{
    State &s = *m_state;
    if (s.closed || !s.initialized) {
        *error = QStringLiteral("the hidden host is closed");
        return false;
    }
    const std::shared_ptr<FrameDriver> driver = m_driver;
    for (int i = 0; i < count; ++i) {
        s.control->polishItems(); // the calling (GUI) thread
        bool ok = true;
        QuickReadback *read = (readLast && i == count - 1) ? readLast : nullptr;
        s.thread->run([&s, &ok, driver, read]() {
            s.control->beginFrame();
            QRhiCommandBuffer *cb = s.control->commandBuffer();
            if (!cb) {
                ok = false;
                return;
            }
            s.control->sync();   // the GUI thread is blocked here, as with Qt's threaded render loop
            s.control->render(); // emits beforeRendering: the frame driver records here
            QRhi *rhi = s.control->rhi();
            QRhiReadbackResult result;
            if (read) {
                // Qt Quick's target at the end of its pass, in this frame (outside any pass).
                QRhiResourceUpdateBatch *batch = rhi->nextResourceUpdateBatch();
                batch->readBackTexture(QRhiReadbackDescription(s.target.texture.get()), &result);
                cb->resourceUpdate(batch);
            }
            s.control->endFrame(); // an offscreen frame: waits for the GPU, readbacks complete
            // A probe readback recorded in this frame completes now, outside the frame (QRhi::finish).
            if (read || (driver && driver->readbackPending()))
                rhi->finish();
            if (read) {
                read->rgba = result.data;
                read->width = result.pixelSize.width();
                read->height = result.pixelSize.height();
                read->yUpInFramebuffer = rhi->isYUpInFramebuffer();
                read->frame = s.frames + 1;
                // Rule C: the readback left the target in a transfer layout and its next pass loads it.
                read->prime = primeForLoadOutsideFrame(rhi, s.target.texture.get());
            }
        });
        if (!ok) {
            *error = QStringLiteral("QQuickRenderControl::beginFrame failed at frame %1").arg(s.frames);
            return false;
        }
        ++s.frames;
        if (read) {
            ++s.readbacks;
            if (read->rgba.isEmpty()) {
                *error = QStringLiteral("Qt Quick's target was not read back at frame %1").arg(s.frames);
                return false;
            }
        }
    }
    return true;
}

QJsonObject HiddenHost::close()
{
    State &s = *m_state;
    if (s.closed)
        return s.closeRecord;
    s.closed = true;
    QJsonArray steps;
    if (s.content) {
        s.content->setParentItem(nullptr); // the caller's item survives the window
        s.content = nullptr;
        steps.append(QStringLiteral("content handed back"));
    }
    const std::shared_ptr<FrameDriver> driver = m_driver;
    if (driver)
        driver->requestDetach();
    QThread *guiThread = QCoreApplication::instance() ? QCoreApplication::instance()->thread() : nullptr;
    if (s.thread) {
        s.thread->run([&s, driver, guiThread]() {
            if (s.initialized) {
                QRhi *rhi = s.control->rhi();
                if (driver)
                    driver->releaseOutsideFrame(rhi, QStringLiteral("hidden host closed"));
                s.window->setRenderTarget(QQuickRenderTarget());
                s.target.reset();
                s.control->invalidate(); // sceneGraphInvalidated: anything still connected releases now
                // OpenGL: the QRhi's context is affine to this render thread, which quits next, and the render control
                // (with its QRhi) is deleted on the GUI thread: hand the context back first (native/spike_p1's order).
                if (rhi && guiThread && rhi->backend() == QRhi::OpenGLES2) {
                    const auto *handles = static_cast<const QRhiGles2NativeHandles *>(rhi->nativeHandles());
                    if (handles && handles->context) {
                        handles->context->doneCurrent();
                        if (handles->context->thread() != guiThread)
                            handles->context->moveToThread(guiThread);
                    }
                }
            }
        });
        steps.append(QStringLiteral("driver released and scene graph invalidated on the render thread"));
        s.thread.reset();
        steps.append(QStringLiteral("render thread quit"));
    }
    if (driver) {
        m_lastDriver = driver;
        m_driver.reset();
    }
    delete s.control; // Qt's QRhi on this window goes with it
    s.control = nullptr;
    steps.append(QStringLiteral("render control deleted (Qt's QRhi)"));
    delete s.window;
    s.window = nullptr;
    steps.append(QStringLiteral("window deleted"));
    QJsonArray deviceSteps;
    if (s.device) {
        for (const QString &step : s.device->destroy())
            deviceSteps.append(step);
        s.device.reset();
        steps.append(QStringLiteral("device destroyed"));
    }
    s.closeRecord.insert(QStringLiteral("steps"), steps);
    s.closeRecord.insert(QStringLiteral("device_teardown"), deviceSteps);
    return s.closeRecord;
}

QJsonObject HiddenHost::stateJson() const
{
    const State &s = *m_state;
    QJsonObject o = Host::stateJson();
    o.insert(QStringLiteral("size"), QJsonArray { s.width, s.height });
    o.insert(QStringLiteral("dpr"), s.dpr);
    o.insert(QStringLiteral("logical_size"), QJsonArray { s.logicalSize().width(), s.logicalSize().height() });
    o.insert(QStringLiteral("effective_dpr"), s.window ? double(s.window->effectiveDevicePixelRatio()) : 0.0);
    o.insert(QStringLiteral("quick_readbacks"), s.readbacks);
    o.insert(QStringLiteral("threaded"), s.thread ? s.thread->threaded() : false);
    o.insert(QStringLiteral("initialized"), s.initialized);
    o.insert(QStringLiteral("closed"), s.closed);
    o.insert(QStringLiteral("frames"), s.frames);
    o.insert(QStringLiteral("backend"), s.backend);
    o.insert(QStringLiteral("device_name"), s.deviceName);
    o.insert(QStringLiteral("quick_target_prime"), s.primeNote);
    o.insert(QStringLiteral("host_gui_thread"), QString::number(s.guiThread));
    o.insert(QStringLiteral("render_thread"), QString::number(s.renderThread));
    o.insert(QStringLiteral("device"), s.deviceFacts);
    o.insert(QStringLiteral("device_alive"), s.device != nullptr);
    o.insert(QStringLiteral("has_content"), !s.content.isNull());
    o.insert(QStringLiteral("close"), s.closeRecord);
    return o;
}

} // namespace srpss_core
