// N0.6 (D6's proof): the module owns the Vulkan instance and device and gives them to Qt Quick. Harness only;
// nothing here ships. Facts: Docs/Future_Work/Native_Core_N06_N07_Qt_Facts.md (section H is the build order).
// Every entry point returns one JSON object (UTF-8) that python/run_n06.py reads; none of them sets or reads an
// environment variable (the project forbids environment-variable flags; the driver records the ones Qt reads).
#pragma once

#include <QtCore/QByteArray>

namespace srpss_spike {

// Round 1, facts with no behaviour change. GUI thread, a QGuiApplication must exist, no window is created.
// A throwaway VkInstance of our own (no layers) enumerates the loader version, the instance layers and extensions
// (per layer too), and per physical device: properties, driver, queue families (flags, counts, Win32 present
// support without a surface), device extensions, the supported 1.0 to 1.4 feature structs by name, memory heaps.
// Then Qt's own device: a QVulkanInstance at API 1.2 with QRhi's preferred instance extensions and a QRhi that
// creates its own VkDevice; we record the family and queue index Qt chose and the QRhi feature flags it reports.
QByteArray n06VulkanFactsJson();

} // namespace srpss_spike
