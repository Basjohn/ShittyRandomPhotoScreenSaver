// D6: the native module creates the Vulkan instance and the devices and gives them to Qt Quick (decided 12 Nov 2026,
// proved by the N0.6 harness: Docs/Future_Work/Native_Core_P3_Decisions.md D6 "As proved"; the facts behind each step
// are Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md section A and E). Ported from the harness (native/spike_p1
// vk_n06.cpp), without its fact records and without the second queue (D9's job service, N3.8, adds it).
//
// - One instance for the process: our VkInstance at API 1.2 (route ii) with the surface extensions, QRhi's preferred
//   instance extensions and VK_EXT_debug_utils; with validation and synchronisation validation in code when the caller
//   asks for it and the layer is installed (harness only; no environment variable is read or set here). A
//   QVulkanInstance adopts it with the exact lists and setApiVersion(1, 2). Our debug messenger counts every message
//   per phase, with the calling thread and the caller's stack, so a harness can attribute it.
// - One device per window (D6 point 4): the first discrete GPU (else the first), the first family with graphics and
//   Win32 present support, one queue, QRhi's preferred imported-device extensions plus VK_EXT_device_fault where
//   available, and Qt's feature set (every supported feature of the 1.0, 1.1 and 1.2 structures and of the enabled
//   extensions' structures, robustBufferAccess off; facts A6.2).
// - Teardown (facts A7): windows first (their QRhi is gone), then each device (vkDeviceWaitIdle, vkDestroyDevice,
//   resetDeviceFunctions), then the instance (the adopting QVulkanInstance, our messenger, vkDestroyInstance).
// Every function here runs on the GUI thread except the messenger callback, which any thread may call.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QString>
#include <QtCore/QStringList>

#include <memory>

class QQuickWindow;
class QVulkanInstance;

namespace srpss_core {

// Creates the process instance. validation: enable the Khronos layer and synchronisation validation when installed
// (the JSON says whether it loaded; a harness that requires it fails closed on that). Returns one JSON object.
QByteArray vulkanInstanceCreateJson(bool validation);
// Destroys the process instance; refused while a device lives. Returns the steps and the message counts.
QByteArray vulkanInstanceDestroyJson();
bool vulkanInstanceExists();
// The phase the debug messages that follow are counted under (any thread may log; the counters are guarded).
void vulkanSetPhase(const QString &phase);
int vulkanLiveDevices();

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
    QString deviceName() const { return m_name; }

private:
    VulkanDevice() = default;
    quint64 m_device = 0;         // VkDevice
    quint64 m_physicalDevice = 0; // VkPhysicalDevice
    quint32 m_family = 0;
    QString m_name;
};

} // namespace srpss_core
