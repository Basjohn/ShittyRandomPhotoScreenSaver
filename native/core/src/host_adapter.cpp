#include "host_adapter.h"

#include "targets.h"
#include "vulkan_context.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QCoreApplication>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QMetaObject>
#include <QtCore/QMutex>
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtCore/QThread>
#include <QtGui/QOpenGLContext>
#include <QtGui/QOpenGLFunctions>
#include <QtQuick/QQuickGraphicsConfiguration>
#include <QtQuick/QQuickItem>
#include <QtQuick/QQuickRenderControl>
#include <QtQuick/QQuickRenderTarget>
#include <QtQuick/QQuickWindow>
#include <QtQuick/QSGRendererInterface>
// N3.6: the hidden host's rebuild after a loss destroys the render control's own QRhi (resetRhi), as Qt's threaded loop
// destroys a window's; QQuickRenderControl has no public call for it (invalidate() keeps the QRhi for a later
// initialize()). Qt6::QuickPrivate, pinned to PySide6's exact Qt like every QRhi use (CMakeLists.txt's guard).
#include <QtQuick/private/qquickrendercontrol_p.h>

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

bool Host::setLoad(const LoadConfig *config, QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->setLoad(config);
    return true;
}

bool Host::setGpuTimer(const GpuTimerConfig &config, QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->setGpuTimer(config);
    return true;
}

QList<GpuTimingSample> Host::takeGpuSamples()
{
    if (m_driver)
        return m_driver->takeGpuSamples();
    return m_lastDriver ? m_lastDriver->takeGpuSamples() : QList<GpuTimingSample>();
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
//
// N3.6, device loss (research N3 section 11; Current_Plan.md item 8b): Qt's threaded loop meets the loss in beginFrame,
// endFrame or the swapchain's creation, tears its graphics down on the render thread (the scene graph invalidated, which
// emits sceneGraphInvalidated with its QRhi still alive, then its QRhi destroyed) and makes a new QRhi at the next
// frame, on the device the window was given (QQuickWindowPrivate's stored device objects). A lost VkDevice stays lost,
// so the record's sceneGraphInvalidated slot (render thread, direct) makes a new device and gives it to the window
// before Qt's next QRhi; the lost one is destroyed at the window's next sceneGraphInitialized (render thread: Qt's new
// QRhi exists, the old one is gone). Every core object is made again by its own owner from what it keeps (the items'
// nodes, their streams' last records; textures and meshes through their owners' lost edges). OpenGL has no device of
// ours: Qt's new context is the rebuild, and the loss is only counted.
struct WindowHost::WindowRecord
{
    QQuickWindow *window = nullptr; // valid while !destroyed
    bool destroyed = false;
    mutable QMutex mutex;           // guards the members below (the render thread replaces the device after a loss)
    std::unique_ptr<VulkanDevice> device;
    std::unique_ptr<VulkanDevice> lostDevice; // replaced after a loss; destroyed once Qt's QRhi on it is gone
    QJsonObject deviceFacts;
    QStringList deviceTeardown;
    QJsonArray deviceLosses;        // one record per loss the window met
};

namespace {

QHash<QQuickWindow *, std::shared_ptr<WindowHost::WindowRecord>> &windowRecords()
{
    static QHash<QQuickWindow *, std::shared_ptr<WindowHost::WindowRecord>> records;
    return records;
}

QJsonObject deviceFactsJson(const VulkanDevice &device)
{
    QJsonObject facts;
    facts.insert(QStringLiteral("vk_device"), QString::number(device.device()));
    facts.insert(QStringLiteral("queue_family"), qint64(device.family()));
    facts.insert(QStringLiteral("queues"), qint64(device.queues()));
    facts.insert(QStringLiteral("job_service"), device.jobService() != nullptr);
    facts.insert(QStringLiteral("device_fault"), device.deviceFaultEnabled());
    facts.insert(QStringLiteral("name"), device.deviceName());
    return facts;
}

// The VkDevice a QRhi runs on (0 when it is not Vulkan).
quint64 qrhiDevice(QRhi *rhi)
{
    if (!rhi || rhi->backend() != QRhi::Vulkan)
        return 0;
    const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
    return handles ? quint64(reinterpret_cast<quintptr>(handles->dev)) : 0;
}

void replaceLast(QJsonArray *list, const QJsonObject &entry)
{
    if (!list->isEmpty())
        list->replace(list->size() - 1, entry);
}

// N3.6, the render thread, in sceneGraphInvalidated after a loss (the lost device's QRhi still alive): the fault detail
// logged once for this device, then a new device made and given to the window. `device` becomes the new one and
// `lostDevice` the lost one (an earlier lost one, whose QRhi went before this one was made, is destroyed first). Fills
// the loss record; false (the device kept) when no new device could be made.
bool replaceDevice(QQuickWindow *window, bool reallyLost, std::unique_ptr<VulkanDevice> *device,
                   std::unique_ptr<VulkanDevice> *lostDevice, QJsonObject *loss)
{
    if (!*device)
        return false;
    loss->insert(QStringLiteral("old_device"), QString::number((*device)->device()));
    if (reallyLost) {
        // A forced loss (the harness) leaves the device alive: the query is for a lost device only.
        const QJsonObject fault = (*device)->faultReport();
        loss->insert(QStringLiteral("fault"), fault);
        qWarning("srpss native core: the Vulkan device %s was lost; VK_EXT_device_fault: %s",
                 QString::number((*device)->device()).toUtf8().constData(),
                 QJsonDocument(fault).toJson(QJsonDocument::Compact).constData());
    }
    if (*lostDevice) {
        loss->insert(QStringLiteral("earlier_lost_device_teardown"), stringsJson((*lostDevice)->destroy()));
        lostDevice->reset();
    }
    QString error;
    std::unique_ptr<VulkanDevice> fresh = VulkanDevice::create(&error);
    if (!fresh) {
        // Qt then re-adopts the lost device and its QRhi fails: the window stays without frames, and says why here.
        loss->insert(QStringLiteral("error"), QStringLiteral("no new device: ") + error);
        loss->insert(QStringLiteral("device_swapped"), false);
        return false;
    }
    fresh->giveDeviceTo(window);
    loss->insert(QStringLiteral("new_device"), QString::number(fresh->device()));
    loss->insert(QStringLiteral("device_swapped"), true);
    *lostDevice = std::move(*device);
    *device = std::move(fresh);
    return true;
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
            record->deviceFacts = deviceFactsJson(*record->device);
        }
        // GUI thread, after Qt's render thread released the window's scene graph and QRhi (the window's destructor
        // waits for that): the device goes now (vkDeviceWaitIdle, vkDestroyDevice, resetDeviceFunctions), and a lost one
        // whose replacement's QRhi never came.
        std::weak_ptr<WindowRecord> weak = record;
        QObject::connect(window, &QObject::destroyed, [weak, window](QObject *) {
            const std::shared_ptr<WindowRecord> r = weak.lock(); // before the registry lets go of it
            windowRecords().remove(window);
            if (r) {
                QMutexLocker lock(&r->mutex);
                r->destroyed = true;
                r->window = nullptr;
                if (r->lostDevice) {
                    r->deviceTeardown = r->lostDevice->destroy();
                    r->lostDevice.reset();
                }
                if (r->device) {
                    r->deviceTeardown += r->device->destroy();
                    r->device.reset();
                }
            }
        });
        // N3.6, the loss (render thread, direct): after Qt met a lost device, its scene graph's invalidation replaces the
        // device before Qt's next QRhi; the next initialisation destroys the lost one (its QRhi is gone by then).
        // Ordinary invalidations (a hidden window's, the window's close) find the QRhi alive and do nothing.
        QObject::connect(window, &QQuickWindow::sceneGraphInvalidated, window, [weak, window]() {
            const std::shared_ptr<WindowRecord> r = weak.lock();
            QRhi *rhi = window->rhi();
            if (!r || !rhi || !rhi->isDeviceLost())
                return;
            QJsonObject loss;
            loss.insert(QStringLiteral("reason"), QStringLiteral("lost"));
            loss.insert(QStringLiteral("backend"), QString::fromLatin1(rhi->backendName()));
            loss.insert(QStringLiteral("invalidated_thread"), QString::number(currentThreadNumber()));
            loss.insert(QStringLiteral("invalidated_on_gui_thread"), onGuiThread());
            QMutexLocker lock(&r->mutex);
            if (rhi->backend() == QRhi::Vulkan && replaceDevice(window, true, &r->device, &r->lostDevice, &loss))
                r->deviceFacts = deviceFactsJson(*r->device);
            r->deviceLosses.append(loss);
        }, Qt::DirectConnection);
        QObject::connect(window, &QQuickWindow::sceneGraphInitialized, window, [weak, window]() {
            const std::shared_ptr<WindowRecord> r = weak.lock();
            if (!r)
                return;
            QMutexLocker lock(&r->mutex);
            if (!r->lostDevice)
                return; // the window's first initialisation, or a rebuild that kept its device
            QJsonObject loss = r->deviceLosses.isEmpty() ? QJsonObject() : r->deviceLosses.last().toObject();
            const quint64 rebuiltOn = qrhiDevice(window->rhi());
            loss.insert(QStringLiteral("qrhi_device"), QString::number(rebuiltOn));
            loss.insert(QStringLiteral("rebuilt_on_new_device"), r->device && rebuiltOn == r->device->device());
            loss.insert(QStringLiteral("lost_device_teardown"), stringsJson(r->lostDevice->destroy()));
            loss.insert(QStringLiteral("lost_device_destroyed_thread"), QString::number(currentThreadNumber()));
            r->lostDevice.reset();
            replaceLast(&r->deviceLosses, loss);
        }, Qt::DirectConnection);
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
    {
        QMutexLocker lock(&m_record->mutex);
        o.insert(QStringLiteral("device"), m_record->deviceFacts);
        o.insert(QStringLiteral("device_alive"), m_record->device != nullptr);
        o.insert(QStringLiteral("lost_device_alive"), m_record->lostDevice != nullptr);
        o.insert(QStringLiteral("device_teardown"), stringsJson(m_record->deviceTeardown));
        o.insert(QStringLiteral("device_losses"), m_record->deviceLosses);
    }
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
    bool timestamps = false;
    QQuickRenderControl *control = nullptr; // owned
    QQuickWindow *window = nullptr;         // owned
    std::unique_ptr<RenderThread> thread;
    std::shared_ptr<const HostFrameSource> source;
    std::unique_ptr<VulkanDevice> device;
    ColorTarget target; // Qt Quick's own target (render thread)
    QPointer<QQuickItem> content;
    bool initialized = false;
    bool sceneGraphInvalidated = false;
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
    // N3.6, the loss (written by the GUI thread between frames, read by the render thread while the GUI thread waits).
    bool forceLoss = false;        // the harness's entry: the next frame takes the lost path
    bool swapDevice = true;        // false: the rebuild keeps the device (the control of setGraphicsDevice's effect)
    // Render thread (the GUI thread waiting), read by stateJson between frames.
    bool recovering = false;       // inside recover(): sceneGraphInvalidated is the loss's
    bool reallyLost = false;       // the QRhi reported the loss (a forced loss leaves the device alive)
    std::unique_ptr<VulkanDevice> lostDevice;
    QJsonObject loss;              // the loss being recovered
    QJsonArray losses;

    QSizeF logicalSize() const { return QSizeF(width / dpr, height / dpr); }

    // N3.6, render thread, inside recover()'s invalidation (the old QRhi alive, the GUI thread waiting): what Qt's
    // threaded loop does through WindowRecord's slot, here from the hidden host's own sceneGraphInvalidated slot on the
    // same thread: a new device given to the window before its next QRhi (setGraphicsDevice from that slot is the
    // threading this settles: the store is on the render thread, read there by initialize()).
    void onInvalidated()
    {
        if (!recovering)
            return; // an ordinary invalidation (the close, the harness's invalidateSceneGraph)
        loss.insert(QStringLiteral("invalidated_thread"), QString::number(currentThreadNumber()));
        loss.insert(QStringLiteral("invalidated_on_render_thread"), currentThreadNumber() == renderThread);
        loss.insert(QStringLiteral("invalidated_on_gui_thread"), onGuiThread());
        if (!device)
            return; // OpenGL: Qt's new context is the rebuild
        if (!swapDevice) {
            loss.insert(QStringLiteral("device_swapped"), false);
            return;
        }
        if (replaceDevice(window, reallyLost, &device, &lostDevice, &loss))
            deviceFacts = deviceFactsJson(*device);
    }

    // N3.6, render thread, outside any frame (the GUI thread waiting): the lost path. Qt's threaded loop's teardown
    // (the scene graph invalidated with its QRhi alive, then the QRhi destroyed), the lost device destroyed, then Qt's
    // QRhi made again on the window's device (the new one) and Qt Quick's target with it. Every core object comes back
    // from its owner at the next sync (the frame driver's at its next edge; the items' nodes; textures through the lost
    // edge). False with `error` when Qt's QRhi could not be made again (the host is then closed for rendering).
    bool recover(const QString &reason, QString *error)
    {
        QRhi *rhi = control->rhi();
        reallyLost = rhi && rhi->isDeviceLost();
        loss = QJsonObject();
        loss.insert(QStringLiteral("reason"), reason);
        loss.insert(QStringLiteral("qrhi_lost"), reallyLost);
        loss.insert(QStringLiteral("backend"), backend);
        loss.insert(QStringLiteral("frame"), frames);
        const quint64 before = qrhiDevice(rhi);
        recovering = true;
        window->setRenderTarget(QQuickRenderTarget());
        target.reset();               // Qt Quick's target is the host's, on the old QRhi
        control->invalidate();        // sceneGraphInvalidated: the frame driver releases, the nodes go, onInvalidated
        QQuickRenderControlPrivate::get(control)->resetRhi(window->graphicsConfiguration()); // Qt's QRhi goes
        recovering = false;
        if (lostDevice) {
            loss.insert(QStringLiteral("lost_device_teardown"), stringsJson(lostDevice->destroy()));
            lostDevice.reset();
        }
        if (!control->initialize()) {
            initialized = false;
            loss.insert(QStringLiteral("error"), QStringLiteral("QQuickRenderControl::initialize failed after the "
                                                                "loss"));
            losses.append(loss);
            *error = QStringLiteral("the hidden host's QRhi could not be made again after the loss (%1)").arg(reason);
            return false;
        }
        QRhi *fresh = control->rhi();
        const quint64 after = qrhiDevice(fresh);
        loss.insert(QStringLiteral("qrhi_device_before"), QString::number(before));
        loss.insert(QStringLiteral("qrhi_device"), QString::number(after));
        loss.insert(QStringLiteral("rebuilt_on_new_device"), device && after != 0 && after != before
                                                              && after == device->device());
        loss.insert(QStringLiteral("qrhi_recreated"), true);
        QString failure;
        if (!createColorTarget(fresh, QSize(width, height), QByteArrayLiteral("srpss hidden host Qt Quick target"),
                               &target, &failure, true)) {
            initialized = false;
            loss.insert(QStringLiteral("error"), failure);
            losses.append(loss);
            *error = failure;
            return false;
        }
        primeNote = primeForLoadOutsideFrame(fresh, target.texture.get()); // rule C, at creation
        applyRenderTarget();
        losses.append(loss);
        return true;
    }
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

std::unique_ptr<HiddenHost> HiddenHost::create(int width, int height, bool threaded, double dpr, QString *error,
                                               bool timestamps)
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
    s.timestamps = timestamps;
    if (timestamps) {
        // Read by Qt's QRhi creation at initialize() (and kept by the device's own configuration below).
        QQuickGraphicsConfiguration config = s.window->graphicsConfiguration();
        config.setTimestamps(true);
        s.window->setGraphicsConfiguration(config);
    }
    if (onVulkan()) {
        s.device = VulkanDevice::create(error);
        if (!s.device) {
            host->close();
            return {};
        }
        s.device->applyTo(s.window);
        s.deviceFacts = deviceFactsJson(*s.device);
    }
    // N3.6: the lost path's device replacement, from the scene graph's invalidation on the render thread (direct).
    State *state = &s; // the state outlives the window (close() deletes the window first)
    QObject::connect(s.window, &QQuickWindow::sceneGraphInvalidated, s.window, [state]() { state->onInvalidated(); },
                     Qt::DirectConnection);
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

bool HiddenHost::detachAtFrameEdge(QString *error)
{
    if (!m_driver) {
        *error = QStringLiteral("the host is not attached");
        return false;
    }
    m_driver->requestDetach(); // released and disconnected by its next beforeRendering, inside that frame
    m_lastDriver = m_driver;
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

bool HiddenHost::invalidateSceneGraph(QString *error)
{
    State &s = *m_state;
    if (s.closed || !s.initialized) {
        *error = QStringLiteral("the hidden host is closed or uninitialised");
        return false;
    }
    if (!s.sceneGraphInvalidated) {
        s.thread->run([&s]() {
            s.window->setRenderTarget(QQuickRenderTarget());
            s.target.reset();
            s.control->invalidate(); // actual sceneGraphInvalidated signal, not a direct driver release
        });
        s.sceneGraphInvalidated = true;
    }
    return true;
}

bool HiddenHost::readFrame(QuickReadback *out, QString *error)
{
    return renderFrames(1, out, error);
}

bool HiddenHost::forceDeviceLoss(bool swapDevice, QString *error)
{
    State &s = *m_state;
    if (s.closed || !s.initialized || s.sceneGraphInvalidated) {
        *error = QStringLiteral("the hidden host is closed, uninitialised or invalidated");
        return false;
    }
    if (!s.device && !swapDevice) {
        *error = QStringLiteral("keeping the device is a Vulkan control: this host has no device of the module's");
        return false;
    }
    s.forceLoss = true;
    s.swapDevice = swapDevice;
    return true;
}

bool HiddenHost::renderFrames(int count, QuickReadback *readLast, QString *error)
{
    State &s = *m_state;
    if (s.sceneGraphInvalidated) {
        *error = QStringLiteral("the hidden host's scene graph was invalidated; close it before rendering again");
        return false;
    }
    if (s.closed || !s.initialized) {
        *error = QStringLiteral("the hidden host is closed");
        return false;
    }
    const std::shared_ptr<FrameDriver> driver = m_driver;
    for (int i = 0; i < count; ++i) {
        s.control->polishItems(); // the calling (GUI) thread
        bool ok = true;
        QString lostError;
        QuickReadback *read = (readLast && i == count - 1) ? readLast : nullptr;
        s.thread->run([&s, &ok, &lostError, driver, read]() {
            // N3.6, the lost path, outside any frame: the harness's forced loss, or a QRhi that reported its device lost
            // (the last frame's end, or this frame's begin below).
            QRhi *previous = s.control->rhi();
            if (s.forceLoss || (previous && previous->isDeviceLost())) {
                const bool forced = s.forceLoss;
                s.forceLoss = false;
                if (!s.recover(forced ? QStringLiteral("forced") : QStringLiteral("lost"), &lostError)) {
                    ok = false;
                    return;
                }
            }
            s.control->beginFrame();
            QRhi *begun = s.control->rhi();
            if (begun && !begun->isRecordingFrame() && begun->isDeviceLost()) {
                // Lost in beginFrame (QQuickRenderControl records nothing then): rebuilt, and the frame begun again once.
                if (!s.recover(QStringLiteral("lost in beginFrame"), &lostError)) {
                    ok = false;
                    return;
                }
                s.control->beginFrame();
            }
            QRhiCommandBuffer *cb = s.control->commandBuffer();
            if (!cb || !s.control->rhi() || !s.control->rhi()->isRecordingFrame()) {
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
            s.control->endFrame(); // an offscreen frame: Vulkan's waits for the GPU, readbacks complete
            // A probe readback recorded in this frame completes now, outside the frame (QRhi::finish).
            if (read || (driver && driver->readbackPending()))
                rhi->finish();
            // R-223: QRhi's OpenGL offscreen frame only flushes, and QRhi::finish() outside a frame waits for nothing
            // either (measured on the fe718e59 module: no timer result in 1200 4K records), so with nothing throttling
            // the hidden host the CPU ran ahead of the GPU without bound (timer results 12 to 220 frames late, a timer
            // ring that never came free: "a GPU time about one frame in twenty" since N2.6). The host waits for its
            // OpenGL frame itself, so its frame is synchronous on every backend, as Vulkan's offscreen frame already was.
            if (rhi->backend() == QRhi::OpenGLES2 && rhi->makeThreadLocalNativeContextCurrent()) {
                if (QOpenGLContext *context = QOpenGLContext::currentContext())
                    context->functions()->glFinish();
            }
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
            *error = lostError.isEmpty() ? QStringLiteral("QQuickRenderControl::beginFrame failed at frame %1").arg(s.frames)
                                         : lostError;
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
                if (!s.sceneGraphInvalidated)
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
    if (s.lostDevice) { // N3.6: only when a rebuild failed between the invalidation and Qt's new QRhi
        for (const QString &step : s.lostDevice->destroy())
            deviceSteps.append(step);
        s.lostDevice.reset();
        steps.append(QStringLiteral("lost device destroyed"));
    }
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
    o.insert(QStringLiteral("qrhi_timestamps"), s.timestamps);
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
    o.insert(QStringLiteral("lost_device_alive"), s.lostDevice != nullptr);
    o.insert(QStringLiteral("device_losses"), s.losses);
    o.insert(QStringLiteral("loss_forced_pending"), s.forceLoss);
    o.insert(QStringLiteral("vulkan_live_devices"), vulkanLiveDevices());
    o.insert(QStringLiteral("has_content"), !s.content.isNull());
    o.insert(QStringLiteral("close"), s.closeRecord);
    return o;
}

} // namespace srpss_core
