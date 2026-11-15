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
// Every function here runs on the GUI thread except the messenger callback, which any thread may call.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QString>
#include <QtCore/QStringList>

#include <memory>

class QQuickWindow;
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
    QString m_name;
    std::shared_ptr<JobService> m_jobs;
};

} // namespace srpss_core
