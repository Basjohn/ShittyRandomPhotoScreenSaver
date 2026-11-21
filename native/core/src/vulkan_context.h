// D6: the native module creates the Vulkan instance and the devices and gives them to Qt Quick (decided 12 Nov 2026,
// proved by the N0.6 harness: Docs/Future_Work/Native_Core_P3_Decisions.md D6 "As proved"; the facts behind each step
// are Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md section A and E). Ported from the harness (native/spike_p1
// vk_n06.cpp), without its fact records; N3.8 added its second queue for D9's job service (job_service.h).
//
// - One instance for the process: our VkInstance at API 1.2 (route ii) with the surface extensions, QRhi's preferred
//   instance extensions and VK_EXT_debug_utils; with validation and synchronisation validation in code when the caller
//   asks for it and the layer is installed (harness only; no environment variable is read or set here). A
//   QVulkanInstance adopts it with the exact lists and setApiVersion(1, 2). Our debug messenger counts every message
//   per phase, with the calling thread and the caller's stack, so a harness can attribute it.
// - One device per window (D6 point 4): the first discrete GPU (else the first), the first family with graphics and
//   Win32 present support, Qt's queue (index 0) and, when the family has one, the job queue (index 1; the device's job
//   service, created with it and stopped first by destroy()), QRhi's preferred imported-device extensions plus
//   VK_EXT_device_fault where
//   available, and Qt's feature set (every supported feature of the 1.0, 1.1 and 1.2 structures and of the enabled
//   extensions' structures, robustBufferAccess off; facts A6.2).
// - Teardown (facts A7): windows first (their QRhi is gone), then each device (vkDeviceWaitIdle, vkDestroyDevice,
//   resetDeviceFunctions), then the instance (the adopting QVulkanInstance, our messenger, vkDestroyInstance).
// - Device loss (N3.6, Current_Plan.md item 8b; research N3 section 11): Qt's recovery re-adopts the device it was given,
//   so after a loss the host makes a new device here and hands it to the window (giveDeviceTo) from the window's
//   sceneGraphInvalidated, on the render thread, before Qt's next QRhi; the lost one is destroyed once Qt's QRhi on it is
//   gone. faultReport() reads VK_EXT_device_fault's detail of a lost device (logged once per lost device).
// Every function here runs on the GUI thread except the messenger callback, which any thread may call, and the device
// loss path (create, giveDeviceTo, faultReport, destroy), which the render thread runs while the window's frame is
// stopped (host_adapter.cpp).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QString>
#include <QtCore/QStringList>

#include <memory>

class QQuickWindow;
class QVulkanDeviceFunctions;
class QVulkanInstance;

namespace srpss_core {

class JobService;

// Creates the process instance. validation: enable the Khronos layer and synchronisation validation when installed
// (the JSON says whether it loaded; a harness that requires it fails closed on that). shaderAccesses (harness only, with
// validation): also turn on the layer's shader-access hazard checks (syncval_shader_accesses_heuristic, off by default
// in the layer), through VK_EXT_layer_settings when the layer offers it; the JSON says whether it did. Returns one JSON
// object.
QByteArray vulkanInstanceCreateJson(bool validation, bool shaderAccesses = false);
// Destroys the process instance; refused while a device lives. Returns the steps and the message counts.
QByteArray vulkanInstanceDestroyJson();
bool vulkanInstanceExists();
// The phase the debug messages that follow are counted under (any thread may log; the counters are guarded).
void vulkanSetPhase(const QString &phase);
int vulkanLiveDevices();
// N3.2 (D15 point 3): the facts of the device the core created, read once at its creation (any thread; empty
// for a device the core did not create): minUniformBufferOffsetAlignment, maxUniformBufferRange,
// maxDescriptorSetUniformBuffersDynamic, and the multiDrawIndirect, drawIndirectFirstInstance and
// shaderDrawParameters features it enabled (every supported one: Qt's feature set).
QJsonObject vulkanDeviceFacts(quint64 device);
// N3.4 (D17 point 3): the facts also hold independent_blend and sample_rate_shading (the features as enabled) and
// color_attachment_blend (per target format: VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BLEND_BIT, optimal tiling).
// Harness only (D17's negative control): the next devices are created with independentBlend off and their fact false,
// a device that lacks the feature; false restores it. Read at each device's creation.
void setDeviceWithoutIndependentBlend(bool without);
bool deviceWithoutIndependentBlend();

// N3.6, checkpoint audit 11 (harness only; no environment variable is read or set): the device-loss proofs on a real
// loss Qt's own QRhi reports, with no TDR.
// M1: Qt's queue of `device` (queue 0 of `family`) answers its next vkQueueSubmit with VK_ERROR_DEVICE_LOST (`sticky`:
// every later one too, as a really lost device does, until the device is destroyed). It goes through the adopting
// instance's device-function table, the one Qt's QRhi submits through (QVulkanDeviceFunctions, its private part from
// Qt6::GuiPrivate), so QRhi itself sets deviceLost; the job queue (queue 1) is untouched. Any thread, between frames.
// False with the reason when the table's vkQueueSubmit is not found exactly once, or another device is armed.
bool injectSubmitLoss(quint64 device, quint32 family, bool sticky, QString *error);
// The injection's counts: armed, sticky, injected (submits answered lost), forwarded (passed to the driver).
QJsonObject submitLossJson();
// M2: the next `count` VulkanDevice::create calls fail as a failed vkCreateDevice does (the reason says forced). 0 stops.
void setDeviceCreateFailures(int count);
// remaining (failures still to come) and forced (creations failed so far).
QJsonObject deviceCreateFailuresJson();

// N3.6, release timing (research N3 section 12): a raw Vulkan object the core made itself (never QRhi's, whose deferred
// release QRhi runs), retired while a frame in flight may still use it. QRhi's own rule applied by the core: the object
// is stamped with the window's frame edge of its retirement and destroyed at the first frame edge at least
// FramesInFlight later (Qt's beginFrame of that frame waited for its slot's fence, so the GPU is done with it), or at
// once after its device's queue is idle (QRhi::finish outside a frame, the device's vkDeviceWaitIdle at teardown).
// Never a wait inside a frame. One device per window (D6), so a device's stamps are its window's edges.
enum class RawVulkanKind {
    QueryPool = 0, // the GPU timer's timestamp pool (gpu_timer.cpp)
};
struct RawVulkanObject
{
    quint64 device = 0;                        // VkDevice
    QVulkanDeviceFunctions *functions = nullptr; // the adopting instance's for that device
    RawVulkanKind kind = RawVulkanKind::QueryPool;
    quint64 handle = 0;                        // the object (a non-dispatchable handle)
};
// Any thread: queued, to go at the window edge `retiredAtEdge + framesInFlight` or at the device's idle.
void deferRawVulkanDestroy(const RawVulkanObject &object, qint64 retiredAtEdge);
// Render thread, at the frame edge `edge` of the device's window: the entries whose frames completed go. Returns how many.
int releaseRawVulkan(quint64 device, qint64 edge, int framesInFlight);
// After the device's queues are idle (QRhi::finish() outside a frame, vkDeviceWaitIdle): every entry of the device goes.
int releaseAllRawVulkan(quint64 device);
// One atomic: whether any entry waits (the frame edge's test at rest).
bool rawVulkanPending();
// The process's counts: deferred, released at edges, released at idle, pending.
QJsonObject rawVulkanCountsJson();

// One VkDevice for one Qt Quick window, on the process instance.
class VulkanDevice
{
public:
    // Null with `error` when there is no process instance or the device cannot be created.
    static std::unique_ptr<VulkanDevice> create(QString *error);
    ~VulkanDevice();
    VulkanDevice(const VulkanDevice &) = delete;
    VulkanDevice &operator=(const VulkanDevice &) = delete;

    // Before the window's scene graph is initialised: our QVulkanInstance and this device
    // (QQuickGraphicsDevice::fromDeviceObjects, family, queue 0); with validation, Qt's QRhi names its objects.
    void applyTo(QQuickWindow *window) const;
    // N3.6, after a device loss: only this device for the window's next QRhi (QQuickWindow::setGraphicsDevice, a plain
    // store Qt reads when it creates its QRhi again). The render thread, from the window's sceneGraphInvalidated.
    void giveDeviceTo(QQuickWindow *window) const;
    // N3.6: VK_EXT_device_fault's detail (the description, each fault address and vendor fault code) of this device,
    // for a device that was lost; {"queried": false, "why": ...} without the extension or its feature. Any thread.
    QJsonObject faultReport() const;
    bool deviceFaultEnabled() const { return m_deviceFault; }
    // N3.6 (checkpoint audit 11, M2 and L2): a window's QRhi reported this device lost. True the first time only (the
    // fault detail is logged once per lost device, however often a retried replacement meets it again). The device's
    // destruction then tells its job service the device was lost before stop(), so the job teardown never saves a lost
    // device's pipeline cache (the job thread, parked at rest, never met the loss itself). The thread that owns the
    // device's record (the render thread in the loss path).
    bool markLost();
    bool lost() const { return m_lost; }
    // vkDeviceWaitIdle, vkDestroyDevice, resetDeviceFunctions (idempotent). Only after every QRhi on the device is gone.
    QStringList destroy();

    quint64 device() const { return m_device; }
    quint64 physicalDevice() const { return m_physicalDevice; }
    quint32 family() const { return m_family; }
    quint32 queues() const { return m_queues; } // of Qt's family: 2 when the job queue exists (N3.8)
    QString deviceName() const { return m_name; }
    // The device's job service (N3.8, D9; null without a second queue). Contents find it by the VkDevice
    // (JobService::forDevice); destroy() stops it first.
    const std::shared_ptr<JobService> &jobService() const { return m_jobs; }

private:
    VulkanDevice() = default;
    quint64 m_device = 0;         // VkDevice
    quint64 m_physicalDevice = 0; // VkPhysicalDevice
    quint32 m_family = 0;
    quint32 m_queues = 1;
    bool m_deviceFault = false;   // VK_EXT_device_fault and its deviceFault feature enabled
    bool m_lost = false;          // markLost()
    QString m_name;
    std::shared_ptr<JobService> m_jobs;
};

} // namespace srpss_core
