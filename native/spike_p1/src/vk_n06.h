// N0.6 (D6's proof): the module owns the Vulkan instance and device and gives them to Qt Quick. Harness only;
// nothing here ships. Facts: Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (section H is the build order).
// Every entry point returns one JSON object (UTF-8) that python/run_n06.py reads; none of them sets or reads an
// environment variable (the project forbids environment-variable flags; the driver records the ones Qt reads).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QString>

class QQuickWindow;

namespace srpss_spike {

// Round 1, facts with no behaviour change. GUI thread, a QGuiApplication must exist, no window is created.
// A throwaway VkInstance of our own (no layers) enumerates the loader version, the instance layers and extensions
// (per layer too), and per physical device: properties, driver, queue families (flags, counts, Win32 present
// support without a surface), device extensions, the supported 1.0 to 1.4 feature structs by name, memory heaps.
// Then Qt's own device: a QVulkanInstance at API 1.2 with QRhi's preferred instance extensions and a QRhi that
// creates its own VkDevice; we record the family and queue index Qt chose and the QRhi feature flags it reports.
QByteArray n06VulkanFactsJson();

// Round 2, the module's own instance and device (one process-wide context; GUI thread only).
// Create: our VkInstance at API 1.2 (route ii of facts A3) with the surface extensions, QRhi's preferred instance
// extensions and VK_EXT_debug_utils; with the Khronos validation layer when it is installed (and synchronisation
// validation chained through VkValidationFeaturesEXT), otherwise "validation owed". Our debug messenger counts
// every message per phase. A QVulkanInstance adopts it (setVkInstance, the exact layer and extension lists,
// setApiVersion(1, 2)). Then our VkDevice: the first discrete GPU (else the first), the first family with
// graphics and Win32 present support, one queue, QRhi's preferred imported-device extensions (plus
// VK_EXT_device_fault, which Qt's own device enables) where available, and Qt's feature set (every supported
// feature of the 1.0, 1.1 and 1.2 structures and of the enabled extensions' structures, robustBufferAccess off).
// Also a reference QVulkanInstance (Qt creates it, API 1.2, preferred extensions) for hosts on Qt's own device.
// queueMode (rounds 3 and 4): "one" = the graphics queue only (round 2); "second" = also a second queue, found
// the D9 way (same family as the graphics queue first, index 1; else another family with compute; else none, and
// D9's in-frame form runs), created at a lower priority and proved with an empty submit and a fence;
// "force_absent" = the negative control: the same finder is given a forced shape (the graphics family with one
// queue, no other family), must report none, and the device is created with the graphics queue only.
// parts (round 5, attributing growth to its owner): "full" = our instance, Qt's adoption, our device and the
// reference instance (rounds 2 to 4); "raw_instance" = our VkInstance and messenger only; "instance" = plus Qt's
// adoption; "device" = plus our device; "reference" = only the reference QVulkanInstance (Qt's own device then).
// The process handle count after every create step is returned ("create_handles"), and destroy returns it after
// every teardown step ("teardown_handles").
QByteArray n06ContextCreateJson(bool wantValidation, const QString &queueMode = QStringLiteral("one"),
                                const QString &parts = QStringLiteral("full"));
// The process handle count alone (cheap: no GPU query, no snapshot), for step deltas in the driver.
qint64 n06HandleCount();
// Process counters for the create/destroy cycles: handles, GDI and USER objects, threads, private bytes, working
// set, and per memory heap the process's GPU usage (VK_EXT_memory_budget, read through a small probe instance of
// its own that lives until process exit, so it is part of every reading alike). GUI thread.
QByteArray n06ProcessCountersJson();
// Attributes the debug messages that follow to this phase (any thread may log; the counters are atomic).
void n06SetPhase(const QString &phase);
// Tears down in the order of facts A7 (the caller has destroyed every window and render control first):
// vkDeviceWaitIdle, vkDestroyDevice, resetDeviceFunctions, the adopting QVulkanInstance, the reference instance,
// our messenger, vkDestroyInstance. Returns the result of each step and the message counts per phase.
QByteArray n06ContextDestroyJson();

#ifdef SPIKE_WITH_QUICK
// Before the window's scene graph is initialised (QQuickRenderControl::initialize). ours = true: our
// QVulkanInstance and setGraphicsDevice(QQuickGraphicsDevice::fromDeviceObjects(our device)); ours = false: the
// reference QVulkanInstance only, so Qt creates its own device.
bool n06AttachQuickWindow(QQuickWindow *window, bool ours, QString *error);
#endif

} // namespace srpss_spike
