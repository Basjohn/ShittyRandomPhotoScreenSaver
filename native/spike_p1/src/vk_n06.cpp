#include "vk_n06.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QByteArrayList>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <QtCore/QVersionNumber>
#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib: every entry point comes from the loader at run time
#endif
#include <vulkan/vulkan.h>

#ifdef SPIKE_WITH_QUICK
#include <QtQuick/QQuickGraphicsDevice>
#include <QtQuick/QQuickWindow>
#endif

#include <cstddef>
#include <cstring>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <vector>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace srpss_spike {

namespace {

// ------------------------------------------------------------------ loader

// vkGetPhysicalDeviceWin32PresentationSupportKHR without the platform header (VK_KHR_win32_surface); it "can be
// called prior to creating a surface".
typedef VkBool32(VKAPI_PTR *PfnWin32PresentationSupport)(VkPhysicalDevice, uint32_t);

struct Loader
{
    HMODULE library = nullptr;
    PFN_vkGetInstanceProcAddr getInstanceProcAddr = nullptr;

    bool load(QString *error)
    {
        library = LoadLibraryW(L"vulkan-1.dll"); // the loader the driver installed; Qt loads the same one
        if (!library) {
            *error = QStringLiteral("vulkan-1.dll could not be loaded (Win32 error %1)").arg(GetLastError());
            return false;
        }
        getInstanceProcAddr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
            GetProcAddress(library, "vkGetInstanceProcAddr"));
        if (!getInstanceProcAddr) {
            *error = QStringLiteral("vulkan-1.dll exports no vkGetInstanceProcAddr");
            return false;
        }
        return true;
    }

    template <typename F>
    F get(VkInstance instance, const char *name) const
    {
        return reinterpret_cast<F>(getInstanceProcAddr(instance, name));
    }
};

QString versionString(uint32_t v)
{
    return QStringLiteral("%1.%2.%3")
        .arg(VK_API_VERSION_MAJOR(v))
        .arg(VK_API_VERSION_MINOR(v))
        .arg(VK_API_VERSION_PATCH(v));
}

QJsonArray byteArrayList(const QByteArrayList &list)
{
    QJsonArray a;
    for (const QByteArray &s : list)
        a.append(QString::fromUtf8(s));
    return a;
}

QString vkResultName(VkResult r)
{
    return QStringLiteral("VkResult %1").arg(int(r));
}

// ------------------------------------------------------------------ feature tables
// Names come from the members themselves (a misspelt name does not compile). At run time each table is checked
// for completeness and order: every member is a VkBool32 laid out back to back, so entry i must sit at
// header + 4 * i, and the count must equal the count the specification gives for that structure.

struct FeatureName
{
    const char *name;
    std::size_t offset;
};

#define N06_F(S, m) FeatureName{ #m, offsetof(S, m) }

const FeatureName kFeatures10[] = {
    N06_F(VkPhysicalDeviceFeatures, robustBufferAccess),
    N06_F(VkPhysicalDeviceFeatures, fullDrawIndexUint32),
    N06_F(VkPhysicalDeviceFeatures, imageCubeArray),
    N06_F(VkPhysicalDeviceFeatures, independentBlend),
    N06_F(VkPhysicalDeviceFeatures, geometryShader),
    N06_F(VkPhysicalDeviceFeatures, tessellationShader),
    N06_F(VkPhysicalDeviceFeatures, sampleRateShading),
    N06_F(VkPhysicalDeviceFeatures, dualSrcBlend),
    N06_F(VkPhysicalDeviceFeatures, logicOp),
    N06_F(VkPhysicalDeviceFeatures, multiDrawIndirect),
    N06_F(VkPhysicalDeviceFeatures, drawIndirectFirstInstance),
    N06_F(VkPhysicalDeviceFeatures, depthClamp),
    N06_F(VkPhysicalDeviceFeatures, depthBiasClamp),
    N06_F(VkPhysicalDeviceFeatures, fillModeNonSolid),
    N06_F(VkPhysicalDeviceFeatures, depthBounds),
    N06_F(VkPhysicalDeviceFeatures, wideLines),
    N06_F(VkPhysicalDeviceFeatures, largePoints),
    N06_F(VkPhysicalDeviceFeatures, alphaToOne),
    N06_F(VkPhysicalDeviceFeatures, multiViewport),
    N06_F(VkPhysicalDeviceFeatures, samplerAnisotropy),
    N06_F(VkPhysicalDeviceFeatures, textureCompressionETC2),
    N06_F(VkPhysicalDeviceFeatures, textureCompressionASTC_LDR),
    N06_F(VkPhysicalDeviceFeatures, textureCompressionBC),
    N06_F(VkPhysicalDeviceFeatures, occlusionQueryPrecise),
    N06_F(VkPhysicalDeviceFeatures, pipelineStatisticsQuery),
    N06_F(VkPhysicalDeviceFeatures, vertexPipelineStoresAndAtomics),
    N06_F(VkPhysicalDeviceFeatures, fragmentStoresAndAtomics),
    N06_F(VkPhysicalDeviceFeatures, shaderTessellationAndGeometryPointSize),
    N06_F(VkPhysicalDeviceFeatures, shaderImageGatherExtended),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageImageExtendedFormats),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageImageMultisample),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageImageReadWithoutFormat),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageImageWriteWithoutFormat),
    N06_F(VkPhysicalDeviceFeatures, shaderUniformBufferArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceFeatures, shaderSampledImageArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageBufferArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceFeatures, shaderStorageImageArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceFeatures, shaderClipDistance),
    N06_F(VkPhysicalDeviceFeatures, shaderCullDistance),
    N06_F(VkPhysicalDeviceFeatures, shaderFloat64),
    N06_F(VkPhysicalDeviceFeatures, shaderInt64),
    N06_F(VkPhysicalDeviceFeatures, shaderInt16),
    N06_F(VkPhysicalDeviceFeatures, shaderResourceResidency),
    N06_F(VkPhysicalDeviceFeatures, shaderResourceMinLod),
    N06_F(VkPhysicalDeviceFeatures, sparseBinding),
    N06_F(VkPhysicalDeviceFeatures, sparseResidencyBuffer),
    N06_F(VkPhysicalDeviceFeatures, sparseResidencyImage2D),
    N06_F(VkPhysicalDeviceFeatures, sparseResidencyImage3D),
    N06_F(VkPhysicalDeviceFeatures, sparseResidency2Samples),
    N06_F(VkPhysicalDeviceFeatures, sparseResidency4Samples),
    N06_F(VkPhysicalDeviceFeatures, sparseResidency8Samples),
    N06_F(VkPhysicalDeviceFeatures, sparseResidency16Samples),
    N06_F(VkPhysicalDeviceFeatures, sparseResidencyAliased),
    N06_F(VkPhysicalDeviceFeatures, variableMultisampleRate),
    N06_F(VkPhysicalDeviceFeatures, inheritedQueries),
};

const FeatureName kFeatures11[] = {
    N06_F(VkPhysicalDeviceVulkan11Features, storageBuffer16BitAccess),
    N06_F(VkPhysicalDeviceVulkan11Features, uniformAndStorageBuffer16BitAccess),
    N06_F(VkPhysicalDeviceVulkan11Features, storagePushConstant16),
    N06_F(VkPhysicalDeviceVulkan11Features, storageInputOutput16),
    N06_F(VkPhysicalDeviceVulkan11Features, multiview),
    N06_F(VkPhysicalDeviceVulkan11Features, multiviewGeometryShader),
    N06_F(VkPhysicalDeviceVulkan11Features, multiviewTessellationShader),
    N06_F(VkPhysicalDeviceVulkan11Features, variablePointersStorageBuffer),
    N06_F(VkPhysicalDeviceVulkan11Features, variablePointers),
    N06_F(VkPhysicalDeviceVulkan11Features, protectedMemory),
    N06_F(VkPhysicalDeviceVulkan11Features, samplerYcbcrConversion),
    N06_F(VkPhysicalDeviceVulkan11Features, shaderDrawParameters),
};

const FeatureName kFeatures12[] = {
    N06_F(VkPhysicalDeviceVulkan12Features, samplerMirrorClampToEdge),
    N06_F(VkPhysicalDeviceVulkan12Features, drawIndirectCount),
    N06_F(VkPhysicalDeviceVulkan12Features, storageBuffer8BitAccess),
    N06_F(VkPhysicalDeviceVulkan12Features, uniformAndStorageBuffer8BitAccess),
    N06_F(VkPhysicalDeviceVulkan12Features, storagePushConstant8),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderBufferInt64Atomics),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderSharedInt64Atomics),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderFloat16),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderInt8),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderInputAttachmentArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderUniformTexelBufferArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderStorageTexelBufferArrayDynamicIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderUniformBufferArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderSampledImageArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderStorageBufferArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderStorageImageArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderInputAttachmentArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderUniformTexelBufferArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderStorageTexelBufferArrayNonUniformIndexing),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingUniformBufferUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingSampledImageUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingStorageImageUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingStorageBufferUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingUniformTexelBufferUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingStorageTexelBufferUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingUpdateUnusedWhilePending),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingPartiallyBound),
    N06_F(VkPhysicalDeviceVulkan12Features, descriptorBindingVariableDescriptorCount),
    N06_F(VkPhysicalDeviceVulkan12Features, runtimeDescriptorArray),
    N06_F(VkPhysicalDeviceVulkan12Features, samplerFilterMinmax),
    N06_F(VkPhysicalDeviceVulkan12Features, scalarBlockLayout),
    N06_F(VkPhysicalDeviceVulkan12Features, imagelessFramebuffer),
    N06_F(VkPhysicalDeviceVulkan12Features, uniformBufferStandardLayout),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderSubgroupExtendedTypes),
    N06_F(VkPhysicalDeviceVulkan12Features, separateDepthStencilLayouts),
    N06_F(VkPhysicalDeviceVulkan12Features, hostQueryReset),
    N06_F(VkPhysicalDeviceVulkan12Features, timelineSemaphore),
    N06_F(VkPhysicalDeviceVulkan12Features, bufferDeviceAddress),
    N06_F(VkPhysicalDeviceVulkan12Features, bufferDeviceAddressCaptureReplay),
    N06_F(VkPhysicalDeviceVulkan12Features, bufferDeviceAddressMultiDevice),
    N06_F(VkPhysicalDeviceVulkan12Features, vulkanMemoryModel),
    N06_F(VkPhysicalDeviceVulkan12Features, vulkanMemoryModelDeviceScope),
    N06_F(VkPhysicalDeviceVulkan12Features, vulkanMemoryModelAvailabilityVisibilityChains),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderOutputViewportIndex),
    N06_F(VkPhysicalDeviceVulkan12Features, shaderOutputLayer),
    N06_F(VkPhysicalDeviceVulkan12Features, subgroupBroadcastDynamicId),
};

const FeatureName kFeatures13[] = {
    N06_F(VkPhysicalDeviceVulkan13Features, robustImageAccess),
    N06_F(VkPhysicalDeviceVulkan13Features, inlineUniformBlock),
    N06_F(VkPhysicalDeviceVulkan13Features, descriptorBindingInlineUniformBlockUpdateAfterBind),
    N06_F(VkPhysicalDeviceVulkan13Features, pipelineCreationCacheControl),
    N06_F(VkPhysicalDeviceVulkan13Features, privateData),
    N06_F(VkPhysicalDeviceVulkan13Features, shaderDemoteToHelperInvocation),
    N06_F(VkPhysicalDeviceVulkan13Features, shaderTerminateInvocation),
    N06_F(VkPhysicalDeviceVulkan13Features, subgroupSizeControl),
    N06_F(VkPhysicalDeviceVulkan13Features, computeFullSubgroups),
    N06_F(VkPhysicalDeviceVulkan13Features, synchronization2),
    N06_F(VkPhysicalDeviceVulkan13Features, textureCompressionASTC_HDR),
    N06_F(VkPhysicalDeviceVulkan13Features, shaderZeroInitializeWorkgroupMemory),
    N06_F(VkPhysicalDeviceVulkan13Features, dynamicRendering),
    N06_F(VkPhysicalDeviceVulkan13Features, shaderIntegerDotProduct),
    N06_F(VkPhysicalDeviceVulkan13Features, maintenance4),
};

const FeatureName kFeatures14[] = {
    N06_F(VkPhysicalDeviceVulkan14Features, globalPriorityQuery),
    N06_F(VkPhysicalDeviceVulkan14Features, shaderSubgroupRotate),
    N06_F(VkPhysicalDeviceVulkan14Features, shaderSubgroupRotateClustered),
    N06_F(VkPhysicalDeviceVulkan14Features, shaderFloatControls2),
    N06_F(VkPhysicalDeviceVulkan14Features, shaderExpectAssume),
    N06_F(VkPhysicalDeviceVulkan14Features, rectangularLines),
    N06_F(VkPhysicalDeviceVulkan14Features, bresenhamLines),
    N06_F(VkPhysicalDeviceVulkan14Features, smoothLines),
    N06_F(VkPhysicalDeviceVulkan14Features, stippledRectangularLines),
    N06_F(VkPhysicalDeviceVulkan14Features, stippledBresenhamLines),
    N06_F(VkPhysicalDeviceVulkan14Features, stippledSmoothLines),
    N06_F(VkPhysicalDeviceVulkan14Features, vertexAttributeInstanceRateDivisor),
    N06_F(VkPhysicalDeviceVulkan14Features, vertexAttributeInstanceRateZeroDivisor),
    N06_F(VkPhysicalDeviceVulkan14Features, indexTypeUint8),
    N06_F(VkPhysicalDeviceVulkan14Features, dynamicRenderingLocalRead),
    N06_F(VkPhysicalDeviceVulkan14Features, maintenance5),
    N06_F(VkPhysicalDeviceVulkan14Features, maintenance6),
    N06_F(VkPhysicalDeviceVulkan14Features, pipelineProtectedAccess),
    N06_F(VkPhysicalDeviceVulkan14Features, pipelineRobustness),
    N06_F(VkPhysicalDeviceVulkan14Features, hostImageCopy),
    N06_F(VkPhysicalDeviceVulkan14Features, pushDescriptor),
};

#undef N06_F

// The member counts the Vulkan specification gives for each structure.
constexpr std::size_t kSpecCount10 = 55;
constexpr std::size_t kSpecCount11 = 12;
constexpr std::size_t kSpecCount12 = 47;
constexpr std::size_t kSpecCount13 = 15;
constexpr std::size_t kSpecCount14 = 21;

QJsonObject featureRecord(const void *structure, const FeatureName *table, std::size_t count,
                          std::size_t headerBytes, std::size_t specCount)
{
    QJsonObject values;
    bool tableComplete = count == specCount;
    int supported = 0;
    for (std::size_t i = 0; i < count; ++i) {
        if (table[i].offset != headerBytes + i * sizeof(VkBool32))
            tableComplete = false;
        VkBool32 v = VK_FALSE;
        std::memcpy(&v, static_cast<const char *>(structure) + table[i].offset, sizeof(v));
        values.insert(QLatin1String(table[i].name), v == VK_TRUE);
        if (v == VK_TRUE)
            ++supported;
    }
    QJsonObject o;
    o.insert(QStringLiteral("table_complete"), tableComplete);
    o.insert(QStringLiteral("supported_count"), supported);
    o.insert(QStringLiteral("member_count"), qint64(count));
    o.insert(QStringLiteral("values"), values);
    return o;
}

QJsonArray queueFlagNames(VkQueueFlags flags)
{
    struct Bit { VkQueueFlags bit; const char *name; };
    const Bit bits[] = {
        { VK_QUEUE_GRAPHICS_BIT, "graphics" }, { VK_QUEUE_COMPUTE_BIT, "compute" },
        { VK_QUEUE_TRANSFER_BIT, "transfer" }, { VK_QUEUE_SPARSE_BINDING_BIT, "sparse_binding" },
        { VK_QUEUE_PROTECTED_BIT, "protected" }, { 0x20, "video_decode" }, { 0x40, "video_encode" },
        { 0x100, "optical_flow" },
    };
    QJsonArray a;
    for (const Bit &b : bits) {
        if (flags & b.bit)
            a.append(QLatin1String(b.name));
    }
    return a;
}

QString deviceTypeName(VkPhysicalDeviceType t)
{
    switch (t) {
    case VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU: return QStringLiteral("integrated");
    case VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU: return QStringLiteral("discrete");
    case VK_PHYSICAL_DEVICE_TYPE_VIRTUAL_GPU: return QStringLiteral("virtual");
    case VK_PHYSICAL_DEVICE_TYPE_CPU: return QStringLiteral("cpu");
    default: return QStringLiteral("other");
    }
}

// ------------------------------------------------------------------ facts: our throwaway instance

QJsonObject instanceFacts(const Loader &loader)
{
    QJsonObject o;
    auto enumerateVersion = loader.get<PFN_vkEnumerateInstanceVersion>(nullptr, "vkEnumerateInstanceVersion");
    uint32_t loaderVersion = VK_API_VERSION_1_0;
    if (enumerateVersion)
        enumerateVersion(&loaderVersion);
    o.insert(QStringLiteral("loader_api_version"), versionString(loaderVersion));

    auto enumerateLayers = loader.get<PFN_vkEnumerateInstanceLayerProperties>(
        nullptr, "vkEnumerateInstanceLayerProperties");
    auto enumerateExtensions = loader.get<PFN_vkEnumerateInstanceExtensionProperties>(
        nullptr, "vkEnumerateInstanceExtensionProperties");
    auto createInstance = loader.get<PFN_vkCreateInstance>(nullptr, "vkCreateInstance");
    if (!enumerateLayers || !enumerateExtensions || !createInstance) {
        o.insert(QStringLiteral("error"), QStringLiteral("the loader lacks a global entry point"));
        return o;
    }

    auto extensionList = [&](const char *layer) {
        uint32_t n = 0;
        enumerateExtensions(layer, &n, nullptr);
        std::vector<VkExtensionProperties> props(n);
        if (n)
            enumerateExtensions(layer, &n, props.data());
        QJsonArray a;
        for (uint32_t i = 0; i < n; ++i)
            a.append(QString::fromUtf8(props[i].extensionName));
        return a;
    };

    uint32_t layerCount = 0;
    enumerateLayers(&layerCount, nullptr);
    std::vector<VkLayerProperties> layers(layerCount);
    if (layerCount)
        enumerateLayers(&layerCount, layers.data());
    QJsonArray layerArray;
    bool validationPresent = false;
    for (uint32_t i = 0; i < layerCount; ++i) {
        QJsonObject l;
        l.insert(QStringLiteral("name"), QString::fromUtf8(layers[i].layerName));
        l.insert(QStringLiteral("spec_version"), versionString(layers[i].specVersion));
        l.insert(QStringLiteral("implementation_version"), qint64(layers[i].implementationVersion));
        l.insert(QStringLiteral("description"), QString::fromUtf8(layers[i].description));
        l.insert(QStringLiteral("extensions"), extensionList(layers[i].layerName));
        layerArray.append(l);
        if (std::strcmp(layers[i].layerName, "VK_LAYER_KHRONOS_validation") == 0)
            validationPresent = true;
    }
    o.insert(QStringLiteral("layers"), layerArray);
    o.insert(QStringLiteral("validation_layer_present"), validationPresent);
    const QJsonArray instanceExtensions = extensionList(nullptr);
    o.insert(QStringLiteral("extensions"), instanceExtensions);

    // The facts instance: the loader's own version, the surface extensions (for the present query), no layers.
    std::vector<const char *> enable;
    for (const char *want : { "VK_KHR_surface", "VK_KHR_win32_surface" }) {
        if (instanceExtensions.contains(QLatin1String(want)))
            enable.push_back(want);
    }
    VkApplicationInfo app = {};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "srpss-n06-facts";
    app.apiVersion = loaderVersion;
    VkInstanceCreateInfo ci = {};
    ci.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo = &app;
    ci.enabledExtensionCount = uint32_t(enable.size());
    ci.ppEnabledExtensionNames = enable.empty() ? nullptr : enable.data();
    VkInstance instance = VK_NULL_HANDLE;
    const VkResult created = createInstance(&ci, nullptr, &instance);
    if (created != VK_SUCCESS) {
        o.insert(QStringLiteral("error"), QStringLiteral("vkCreateInstance: ") + vkResultName(created));
        return o;
    }
    o.insert(QStringLiteral("facts_instance_api_version"), versionString(loaderVersion));

    auto destroyInstance = loader.get<PFN_vkDestroyInstance>(instance, "vkDestroyInstance");
    auto enumerateDevices = loader.get<PFN_vkEnumeratePhysicalDevices>(instance, "vkEnumeratePhysicalDevices");
    auto getProperties = loader.get<PFN_vkGetPhysicalDeviceProperties>(instance, "vkGetPhysicalDeviceProperties");
    auto getProperties2 = loader.get<PFN_vkGetPhysicalDeviceProperties2>(instance, "vkGetPhysicalDeviceProperties2");
    auto getFeatures = loader.get<PFN_vkGetPhysicalDeviceFeatures>(instance, "vkGetPhysicalDeviceFeatures");
    auto getFeatures2 = loader.get<PFN_vkGetPhysicalDeviceFeatures2>(instance, "vkGetPhysicalDeviceFeatures2");
    auto getQueueFamilies = loader.get<PFN_vkGetPhysicalDeviceQueueFamilyProperties>(
        instance, "vkGetPhysicalDeviceQueueFamilyProperties");
    auto enumerateDeviceExtensions = loader.get<PFN_vkEnumerateDeviceExtensionProperties>(
        instance, "vkEnumerateDeviceExtensionProperties");
    auto getMemory = loader.get<PFN_vkGetPhysicalDeviceMemoryProperties>(
        instance, "vkGetPhysicalDeviceMemoryProperties");
    auto win32Present = loader.get<PfnWin32PresentationSupport>(
        instance, "vkGetPhysicalDeviceWin32PresentationSupportKHR");

    uint32_t deviceCount = 0;
    if (enumerateDevices)
        enumerateDevices(instance, &deviceCount, nullptr);
    std::vector<VkPhysicalDevice> devices(deviceCount);
    if (deviceCount)
        enumerateDevices(instance, &deviceCount, devices.data());

    QJsonArray deviceArray;
    for (uint32_t d = 0; d < deviceCount; ++d) {
        VkPhysicalDevice pd = devices[d];
        QJsonObject dev;
        VkPhysicalDeviceProperties props = {};
        getProperties(pd, &props);
        const uint32_t effective = props.apiVersion < loaderVersion ? props.apiVersion : loaderVersion;
        dev.insert(QStringLiteral("index"), qint64(d));
        dev.insert(QStringLiteral("name"), QString::fromUtf8(props.deviceName));
        dev.insert(QStringLiteral("type"), deviceTypeName(props.deviceType));
        dev.insert(QStringLiteral("api_version"), versionString(props.apiVersion));
        dev.insert(QStringLiteral("effective_api_version"), versionString(effective));
        dev.insert(QStringLiteral("driver_version_raw"), qint64(props.driverVersion));
        dev.insert(QStringLiteral("vendor_id"), qint64(props.vendorID));
        dev.insert(QStringLiteral("device_id"), qint64(props.deviceID));
        dev.insert(QStringLiteral("timestamp_period_ns"), double(props.limits.timestampPeriod));
        dev.insert(QStringLiteral("timestamp_compute_and_graphics"),
                   props.limits.timestampComputeAndGraphics == VK_TRUE);

        if (getProperties2 && effective >= VK_API_VERSION_1_2) {
            VkPhysicalDeviceDriverProperties driver = {};
            driver.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES;
            VkPhysicalDeviceProperties2 props2 = {};
            props2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2;
            props2.pNext = &driver;
            getProperties2(pd, &props2);
            QJsonObject drv;
            drv.insert(QStringLiteral("driver_id"), qint64(driver.driverID));
            drv.insert(QStringLiteral("driver_name"), QString::fromUtf8(driver.driverName));
            drv.insert(QStringLiteral("driver_info"), QString::fromUtf8(driver.driverInfo));
            drv.insert(QStringLiteral("conformance_version"),
                       QStringLiteral("%1.%2.%3.%4")
                           .arg(int(driver.conformanceVersion.major))
                           .arg(int(driver.conformanceVersion.minor))
                           .arg(int(driver.conformanceVersion.subminor))
                           .arg(int(driver.conformanceVersion.patch)));
            dev.insert(QStringLiteral("driver"), drv);
        }

        uint32_t familyCount = 0;
        getQueueFamilies(pd, &familyCount, nullptr);
        std::vector<VkQueueFamilyProperties> families(familyCount);
        if (familyCount)
            getQueueFamilies(pd, &familyCount, families.data());
        QJsonArray familyArray;
        for (uint32_t f = 0; f < familyCount; ++f) {
            QJsonObject fam;
            fam.insert(QStringLiteral("index"), qint64(f));
            fam.insert(QStringLiteral("flags"), queueFlagNames(families[f].queueFlags));
            fam.insert(QStringLiteral("flags_raw"), qint64(families[f].queueFlags));
            fam.insert(QStringLiteral("queue_count"), qint64(families[f].queueCount));
            fam.insert(QStringLiteral("timestamp_valid_bits"), qint64(families[f].timestampValidBits));
            if (win32Present)
                fam.insert(QStringLiteral("win32_present"), win32Present(pd, f) == VK_TRUE);
            else
                fam.insert(QStringLiteral("win32_present"), QJsonValue());
            familyArray.append(fam);
        }
        dev.insert(QStringLiteral("queue_families"), familyArray);

        uint32_t extCount = 0;
        enumerateDeviceExtensions(pd, nullptr, &extCount, nullptr);
        std::vector<VkExtensionProperties> exts(extCount);
        if (extCount)
            enumerateDeviceExtensions(pd, nullptr, &extCount, exts.data());
        QJsonArray extArray;
        for (uint32_t e = 0; e < extCount; ++e)
            extArray.append(QString::fromUtf8(exts[e].extensionName));
        dev.insert(QStringLiteral("extensions"), extArray);

        // Supported features, every structure the effective version admits (Qt chains the same structures when
        // its own API version reaches them; at the D6 baseline of 1.2 that is 1.0, 1.1 and 1.2).
        QJsonObject features;
        if (getFeatures2 && effective >= VK_API_VERSION_1_2) {
            VkPhysicalDeviceVulkan11Features f11 = {};
            f11.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES;
            VkPhysicalDeviceVulkan12Features f12 = {};
            f12.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES;
            VkPhysicalDeviceVulkan13Features f13 = {};
            f13.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES;
            VkPhysicalDeviceVulkan14Features f14 = {};
            f14.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_4_FEATURES;
            VkPhysicalDeviceFeatures2 f2 = {};
            f2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2;
            f2.pNext = &f11;
            f11.pNext = &f12;
            if (effective >= VK_API_VERSION_1_3) {
                f12.pNext = &f13;
                if (effective >= VK_API_VERSION_1_4)
                    f13.pNext = &f14;
            }
            getFeatures2(pd, &f2);
            features.insert(QStringLiteral("vulkan10"),
                            featureRecord(&f2.features, kFeatures10, std::size(kFeatures10), 0, kSpecCount10));
            features.insert(QStringLiteral("vulkan11"),
                            featureRecord(&f11, kFeatures11, std::size(kFeatures11),
                                          offsetof(VkPhysicalDeviceVulkan11Features, storageBuffer16BitAccess),
                                          kSpecCount11));
            features.insert(QStringLiteral("vulkan12"),
                            featureRecord(&f12, kFeatures12, std::size(kFeatures12),
                                          offsetof(VkPhysicalDeviceVulkan12Features, samplerMirrorClampToEdge),
                                          kSpecCount12));
            if (effective >= VK_API_VERSION_1_3)
                features.insert(QStringLiteral("vulkan13"),
                                featureRecord(&f13, kFeatures13, std::size(kFeatures13),
                                              offsetof(VkPhysicalDeviceVulkan13Features, robustImageAccess),
                                              kSpecCount13));
            if (effective >= VK_API_VERSION_1_4)
                features.insert(QStringLiteral("vulkan14"),
                                featureRecord(&f14, kFeatures14, std::size(kFeatures14),
                                              offsetof(VkPhysicalDeviceVulkan14Features, globalPriorityQuery),
                                              kSpecCount14));
        } else if (getFeatures) {
            VkPhysicalDeviceFeatures f10 = {};
            getFeatures(pd, &f10);
            features.insert(QStringLiteral("vulkan10"),
                            featureRecord(&f10, kFeatures10, std::size(kFeatures10), 0, kSpecCount10));
        }
        dev.insert(QStringLiteral("supported_features"), features);

        VkPhysicalDeviceMemoryProperties memory = {};
        getMemory(pd, &memory);
        QJsonArray heaps;
        for (uint32_t h = 0; h < memory.memoryHeapCount; ++h) {
            QJsonObject heap;
            heap.insert(QStringLiteral("size_mib"), double(memory.memoryHeaps[h].size) / (1024.0 * 1024.0));
            heap.insert(QStringLiteral("device_local"),
                        (memory.memoryHeaps[h].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) != 0);
            heaps.append(heap);
        }
        dev.insert(QStringLiteral("memory_heaps"), heaps);
        deviceArray.append(dev);
    }
    o.insert(QStringLiteral("physical_devices"), deviceArray);
    if (destroyInstance)
        destroyInstance(instance, nullptr);
    return o;
}

// ------------------------------------------------------------------ facts: Qt's own device

QJsonObject rhiFeatureFlags(QRhi *rhi)
{
    // Keyed by the enum's integer value (1 .. ShaderDrawParameters on Qt 6.12); the driver names them from
    // PySide6's QRhi.Feature, which is the same enum.
    QJsonObject o;
    const int last = int(QRhi::ShaderDrawParameters);
    for (int i = 1; i <= last; ++i)
        o.insert(QString::number(i), rhi->isFeatureSupported(static_cast<QRhi::Feature>(i)));
    return o;
}

QJsonObject qtOwnDeviceFacts()
{
    QJsonObject o;
    QVulkanInstance inst;
    inst.setApiVersion(QVersionNumber(1, 2)); // the D6 baseline; Qt's default is 1.0
    inst.setExtensions(QRhiVulkanInitParams::preferredInstanceExtensions());
    if (!inst.create()) {
        o.insert(QStringLiteral("error"),
                 QStringLiteral("QVulkanInstance::create failed (VkResult %1)").arg(int(inst.errorCode())));
        return o;
    }
    o.insert(QStringLiteral("preferred_instance_extensions"),
             byteArrayList(QRhiVulkanInitParams::preferredInstanceExtensions()));
    o.insert(QStringLiteral("preferred_extensions_for_imported_device"),
             byteArrayList(QRhiVulkanInitParams::preferredExtensionsForImportedDevice()));
    o.insert(QStringLiteral("instance_api_version"), inst.apiVersion().toString());
    o.insert(QStringLiteral("instance_extensions"), byteArrayList(inst.extensions()));
    o.insert(QStringLiteral("instance_layers"), byteArrayList(inst.layers()));
    {
        QRhiVulkanInitParams params;
        params.inst = &inst;
        std::unique_ptr<QRhi> rhi(QRhi::create(QRhi::Vulkan, &params));
        if (!rhi) {
            o.insert(QStringLiteral("error"), QStringLiteral("QRhi::create(Vulkan) on Qt's own device failed"));
            return o;
        }
        const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
        VkPhysicalDeviceProperties props = {};
        inst.functions()->vkGetPhysicalDeviceProperties(handles->physDev, &props);
        o.insert(QStringLiteral("device_name"), QString::fromUtf8(props.deviceName));
        o.insert(QStringLiteral("vendor_id"), qint64(props.vendorID));
        o.insert(QStringLiteral("device_id"), qint64(props.deviceID));
        o.insert(QStringLiteral("queue_family_index"), qint64(handles->gfxQueueFamilyIdx));
        o.insert(QStringLiteral("queue_index"), qint64(handles->gfxQueueIdx));
        o.insert(QStringLiteral("rhi_driver_device_name"), QString::fromUtf8(rhi->driverInfo().deviceName));
        o.insert(QStringLiteral("rhi_feature_flags"), rhiFeatureFlags(rhi.get()));
        // What Qt enabled on this device is not readable back from a VkDevice; Qt's rule, from QRhiVulkan::create
        // on the 6.12 branch (facts A6): every supported feature of each chained structure, except
        // robustBufferAccess and (1.3) robustImageAccess. The driver joins this with the supported set.
        o.insert(QStringLiteral("enabled_feature_rule"),
                 QStringLiteral("supported minus robustBufferAccess, robustImageAccess; structures up to the "
                                "instance API version"));
    }
    return o;
}

// ------------------------------------------------------------------ round 2: our instance and device

const char kValidationLayer[] = "VK_LAYER_KHRONOS_validation";

// Every debug-utils message, counted per phase. Qt's own QRhi filter hides two known false positives
// ("Mapping an image with layout ..." and VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307, facts E2); they
// are counted apart, never as clean, and nothing else is set aside.
struct MessageStats
{
    struct Counts
    {
        int errors = 0;
        int warnings = 0;
        int info = 0;
        int qtKnownFalsePositives = 0;
    };

    std::mutex mutex;
    QString phase = QStringLiteral("create");
    QStringList order { QStringLiteral("create") };
    std::map<QString, Counts> counts;
    QStringList samples; // the first error and warning texts

    void setPhase(const QString &p)
    {
        std::lock_guard<std::mutex> lock(mutex);
        phase = p;
        if (!order.contains(p))
            order.append(p);
    }

    QJsonObject toJson()
    {
        std::lock_guard<std::mutex> lock(mutex);
        QJsonObject perPhase;
        int errors = 0;
        int warnings = 0;
        for (const QString &p : order) {
            const Counts c = counts[p];
            QJsonObject o;
            o.insert(QStringLiteral("errors"), c.errors);
            o.insert(QStringLiteral("warnings"), c.warnings);
            o.insert(QStringLiteral("info"), c.info);
            o.insert(QStringLiteral("qt_known_false_positives"), c.qtKnownFalsePositives);
            perPhase.insert(p, o);
            errors += c.errors;
            warnings += c.warnings;
        }
        QJsonObject o;
        o.insert(QStringLiteral("per_phase"), perPhase);
        o.insert(QStringLiteral("errors"), errors);
        o.insert(QStringLiteral("warnings"), warnings);
        o.insert(QStringLiteral("samples"), QJsonArray::fromStringList(samples));
        return o;
    }
};

VKAPI_ATTR VkBool32 VKAPI_CALL n06DebugCallback(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
                                                VkDebugUtilsMessageTypeFlagsEXT types,
                                                const VkDebugUtilsMessengerCallbackDataEXT *data, void *user)
{
    auto *stats = static_cast<MessageStats *>(user);
    const char *message = (data && data->pMessage) ? data->pMessage : "";
    const char *id = (data && data->pMessageIdName) ? data->pMessageIdName : "";
    const bool qtKnown = std::strstr(message, "Mapping an image with layout") != nullptr
        || std::strstr(id, "VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307") != nullptr
        || std::strstr(message, "VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307") != nullptr;
    std::lock_guard<std::mutex> lock(stats->mutex);
    MessageStats::Counts &c = stats->counts[stats->phase];
    const bool error = (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) != 0;
    const bool warning = (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT) != 0;
    if (qtKnown && (error || warning)) {
        ++c.qtKnownFalsePositives;
    } else if (error) {
        ++c.errors;
    } else if (warning) {
        ++c.warnings;
    } else {
        ++c.info;
    }
    if ((error || warning) && stats->samples.size() < 40) {
        stats->samples.append(QStringLiteral("[%1][%2][type %3] %4 %5")
                                  .arg(stats->phase, error ? QStringLiteral("error") : QStringLiteral("warning"))
                                  .arg(int(types))
                                  .arg(QString::fromUtf8(id), QString::fromUtf8(message)));
    }
    return VK_FALSE;
}

struct Context
{
    Loader loader;
    VkInstance instance = VK_NULL_HANDLE;
    VkDebugUtilsMessengerEXT messenger = VK_NULL_HANDLE;
    PFN_vkDestroyInstance destroyInstance = nullptr;
    PFN_vkDestroyDebugUtilsMessengerEXT destroyMessenger = nullptr;
    PFN_vkDestroyDevice destroyDevice = nullptr;
    PFN_vkDeviceWaitIdle deviceWaitIdle = nullptr;
    VkPhysicalDevice physDev = VK_NULL_HANDLE;
    VkDevice device = VK_NULL_HANDLE;
    uint32_t family = 0;
    std::unique_ptr<QVulkanInstance> ours;      // adopts `instance`
    std::unique_ptr<QVulkanInstance> reference; // Qt creates its own instance and, per window, its own device
    MessageStats stats;                         // outlives the messengers (deleted with the context)
};

Context *g_context = nullptr;

QByteArrayList availableInstanceExtensions(const Loader &loader, const char *layer)
{
    auto enumerate = loader.get<PFN_vkEnumerateInstanceExtensionProperties>(
        nullptr, "vkEnumerateInstanceExtensionProperties");
    QByteArrayList names;
    if (!enumerate)
        return names;
    uint32_t n = 0;
    enumerate(layer, &n, nullptr);
    std::vector<VkExtensionProperties> props(n);
    if (n)
        enumerate(layer, &n, props.data());
    for (uint32_t i = 0; i < n; ++i)
        names.append(QByteArray(props[i].extensionName));
    return names;
}

bool layerAvailable(const Loader &loader, const char *name)
{
    auto enumerate = loader.get<PFN_vkEnumerateInstanceLayerProperties>(nullptr,
                                                                         "vkEnumerateInstanceLayerProperties");
    if (!enumerate)
        return false;
    uint32_t n = 0;
    enumerate(&n, nullptr);
    std::vector<VkLayerProperties> props(n);
    if (n)
        enumerate(&n, props.data());
    for (uint32_t i = 0; i < n; ++i) {
        if (std::strcmp(props[i].layerName, name) == 0)
            return true;
    }
    return false;
}

std::vector<const char *> pointers(const QByteArrayList &list)
{
    std::vector<const char *> v;
    v.reserve(std::size_t(list.size()));
    for (const QByteArray &s : list)
        v.push_back(s.constData());
    return v;
}

// Our VkInstance (route ii) and the QVulkanInstance that adopts it. Fills `o`; false on failure with o["error"].
bool createOurInstance(Context *ctx, bool wantValidation, QJsonObject *o)
{
    auto createInstance = ctx->loader.get<PFN_vkCreateInstance>(nullptr, "vkCreateInstance");
    if (!createInstance) {
        o->insert(QStringLiteral("error"), QStringLiteral("the loader has no vkCreateInstance"));
        return false;
    }
    const QByteArrayList available = availableInstanceExtensions(ctx->loader, nullptr);
    QByteArrayList wanted = { QByteArrayLiteral("VK_KHR_surface"), QByteArrayLiteral("VK_KHR_win32_surface") };
    wanted += QRhiVulkanInitParams::preferredInstanceExtensions();
    wanted.append(QByteArrayLiteral("VK_EXT_debug_utils"));
    QByteArrayList extensions;
    QByteArrayList missing;
    for (const QByteArray &w : wanted) {
        if (extensions.contains(w))
            continue;
        if (available.contains(w))
            extensions.append(w);
        else
            missing.append(w);
    }

    QByteArrayList layers;
    bool syncValidation = false;
    QString validation;
    const bool layerPresent = layerAvailable(ctx->loader, kValidationLayer);
    if (!wantValidation) {
        validation = QStringLiteral("not requested");
    } else if (!layerPresent) {
        validation = QStringLiteral("validation owed (layer not installed)");
    } else {
        layers.append(QByteArray(kValidationLayer));
        const QByteArrayList layerExtensions = availableInstanceExtensions(ctx->loader, kValidationLayer);
        if (layerExtensions.contains(QByteArrayLiteral("VK_EXT_validation_features"))) {
            extensions.append(QByteArrayLiteral("VK_EXT_validation_features"));
            syncValidation = true;
            validation = QStringLiteral("enabled with synchronisation validation");
        } else {
            validation = QStringLiteral("enabled without synchronisation validation "
                                        "(the layer offers no VK_EXT_validation_features)");
        }
    }
    const bool debugUtils = extensions.contains(QByteArrayLiteral("VK_EXT_debug_utils"));

    const std::vector<const char *> extensionPtrs = pointers(extensions);
    const std::vector<const char *> layerPtrs = pointers(layers);
    VkApplicationInfo app = {};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "srpss-n06";
    app.apiVersion = VK_API_VERSION_1_2; // D6's baseline
    VkDebugUtilsMessengerCreateInfoEXT messengerInfo = {};
    messengerInfo.sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT;
    messengerInfo.messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
        | VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
    messengerInfo.messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT
        | VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;
    messengerInfo.pfnUserCallback = n06DebugCallback;
    messengerInfo.pUserData = &ctx->stats;
    const VkValidationFeatureEnableEXT enables[] = { VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT };
    VkValidationFeaturesEXT validationFeatures = {};
    validationFeatures.sType = VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT;
    validationFeatures.enabledValidationFeatureCount = 1;
    validationFeatures.pEnabledValidationFeatures = enables;

    VkInstanceCreateInfo ci = {};
    ci.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo = &app;
    ci.enabledExtensionCount = uint32_t(extensionPtrs.size());
    ci.ppEnabledExtensionNames = extensionPtrs.empty() ? nullptr : extensionPtrs.data();
    ci.enabledLayerCount = uint32_t(layerPtrs.size());
    ci.ppEnabledLayerNames = layerPtrs.empty() ? nullptr : layerPtrs.data();
    // The chained messenger sees vkCreateInstance and vkDestroyInstance themselves.
    const void **tail = &ci.pNext;
    if (debugUtils) {
        *tail = &messengerInfo;
        tail = &messengerInfo.pNext;
    }
    if (syncValidation)
        *tail = &validationFeatures;

    const VkResult created = createInstance(&ci, nullptr, &ctx->instance);
    o->insert(QStringLiteral("api_version"), QStringLiteral("1.2"));
    o->insert(QStringLiteral("extensions"), byteArrayList(extensions));
    o->insert(QStringLiteral("extensions_missing"), byteArrayList(missing));
    o->insert(QStringLiteral("layers"), byteArrayList(layers));
    o->insert(QStringLiteral("validation"), validation);
    o->insert(QStringLiteral("validation_layer_loaded"), !layers.isEmpty());
    o->insert(QStringLiteral("synchronisation_validation"), syncValidation);
    if (created != VK_SUCCESS) {
        ctx->instance = VK_NULL_HANDLE;
        o->insert(QStringLiteral("error"), QStringLiteral("vkCreateInstance: ") + vkResultName(created));
        return false;
    }
    ctx->destroyInstance = ctx->loader.get<PFN_vkDestroyInstance>(ctx->instance, "vkDestroyInstance");
    if (debugUtils) {
        auto createMessenger = ctx->loader.get<PFN_vkCreateDebugUtilsMessengerEXT>(
            ctx->instance, "vkCreateDebugUtilsMessengerEXT");
        ctx->destroyMessenger = ctx->loader.get<PFN_vkDestroyDebugUtilsMessengerEXT>(
            ctx->instance, "vkDestroyDebugUtilsMessengerEXT");
        messengerInfo.pNext = nullptr;
        if (createMessenger)
            createMessenger(ctx->instance, &messengerInfo, nullptr, &ctx->messenger);
    }
    o->insert(QStringLiteral("messenger"), ctx->messenger != VK_NULL_HANDLE);

    // Adopt: the exact lists we enabled (Qt does not query an adopted instance) and the API version, without
    // which QRhi treats the device as Vulkan 1.0 (facts A3, A4).
    ctx->ours.reset(new QVulkanInstance);
    ctx->ours->setVkInstance(ctx->instance);
    ctx->ours->setApiVersion(QVersionNumber(1, 2));
    ctx->ours->setLayers(layers);
    ctx->ours->setExtensions(extensions);
    if (!ctx->ours->create()) {
        o->insert(QStringLiteral("error"), QStringLiteral("QVulkanInstance::create (adopting) failed (VkResult %1)")
                                               .arg(int(ctx->ours->errorCode())));
        return false;
    }
    QJsonObject adopted;
    adopted.insert(QStringLiteral("same_vk_instance"), ctx->ours->vkInstance() == ctx->instance);
    adopted.insert(QStringLiteral("api_version"), ctx->ours->apiVersion().toString());
    adopted.insert(QStringLiteral("extensions"), byteArrayList(ctx->ours->extensions()));
    adopted.insert(QStringLiteral("layers"), byteArrayList(ctx->ours->layers()));
    o->insert(QStringLiteral("adopted"), adopted);
    return true;
}

// Our VkDevice with Qt's feature set and one graphics+present queue. Fills `o`.
bool createOurDevice(Context *ctx, QJsonObject *o)
{
    const VkInstance inst = ctx->instance;
    auto enumerateDevices = ctx->loader.get<PFN_vkEnumeratePhysicalDevices>(inst, "vkEnumeratePhysicalDevices");
    auto getProperties = ctx->loader.get<PFN_vkGetPhysicalDeviceProperties>(inst, "vkGetPhysicalDeviceProperties");
    auto getQueueFamilies = ctx->loader.get<PFN_vkGetPhysicalDeviceQueueFamilyProperties>(
        inst, "vkGetPhysicalDeviceQueueFamilyProperties");
    auto getFeatures2 = ctx->loader.get<PFN_vkGetPhysicalDeviceFeatures2>(inst, "vkGetPhysicalDeviceFeatures2");
    auto enumerateDeviceExtensions = ctx->loader.get<PFN_vkEnumerateDeviceExtensionProperties>(
        inst, "vkEnumerateDeviceExtensionProperties");
    auto win32Present = ctx->loader.get<PfnWin32PresentationSupport>(
        inst, "vkGetPhysicalDeviceWin32PresentationSupportKHR");
    auto createDevice = ctx->loader.get<PFN_vkCreateDevice>(inst, "vkCreateDevice");
    ctx->destroyDevice = ctx->loader.get<PFN_vkDestroyDevice>(inst, "vkDestroyDevice");
    ctx->deviceWaitIdle = ctx->loader.get<PFN_vkDeviceWaitIdle>(inst, "vkDeviceWaitIdle");
    if (!enumerateDevices || !getProperties || !getQueueFamilies || !getFeatures2 || !enumerateDeviceExtensions
        || !win32Present || !createDevice || !ctx->destroyDevice || !ctx->deviceWaitIdle) {
        o->insert(QStringLiteral("error"), QStringLiteral("an instance entry point is missing"));
        return false;
    }

    uint32_t count = 0;
    enumerateDevices(inst, &count, nullptr);
    std::vector<VkPhysicalDevice> devices(count);
    if (count)
        enumerateDevices(inst, &count, devices.data());
    if (devices.empty()) {
        o->insert(QStringLiteral("error"), QStringLiteral("no physical device"));
        return false;
    }
    std::size_t chosen = 0;
    for (std::size_t i = 0; i < devices.size(); ++i) {
        VkPhysicalDeviceProperties p = {};
        getProperties(devices[i], &p);
        if (p.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            chosen = i;
            break;
        }
    }
    ctx->physDev = devices[chosen];
    VkPhysicalDeviceProperties props = {};
    getProperties(ctx->physDev, &props);
    o->insert(QStringLiteral("physical_device_index"), qint64(chosen));
    o->insert(QStringLiteral("name"), QString::fromUtf8(props.deviceName));
    o->insert(QStringLiteral("vendor_id"), qint64(props.vendorID));
    o->insert(QStringLiteral("device_id"), qint64(props.deviceID));

    uint32_t familyCount = 0;
    getQueueFamilies(ctx->physDev, &familyCount, nullptr);
    std::vector<VkQueueFamilyProperties> families(familyCount);
    if (familyCount)
        getQueueFamilies(ctx->physDev, &familyCount, families.data());
    bool found = false;
    for (uint32_t f = 0; f < familyCount; ++f) {
        if ((families[f].queueFlags & VK_QUEUE_GRAPHICS_BIT) && win32Present(ctx->physDev, f) == VK_TRUE) {
            ctx->family = f;
            found = true;
            break;
        }
    }
    if (!found) {
        o->insert(QStringLiteral("error"), QStringLiteral("no queue family with graphics and Win32 present"));
        return false;
    }
    o->insert(QStringLiteral("queue_family_index"), qint64(ctx->family));
    o->insert(QStringLiteral("queue_family_flags"), queueFlagNames(families[ctx->family].queueFlags));
    o->insert(QStringLiteral("queue_count_created"), 1);

    uint32_t extCount = 0;
    enumerateDeviceExtensions(ctx->physDev, nullptr, &extCount, nullptr);
    std::vector<VkExtensionProperties> extProps(extCount);
    if (extCount)
        enumerateDeviceExtensions(ctx->physDev, nullptr, &extCount, extProps.data());
    QByteArrayList available;
    for (uint32_t e = 0; e < extCount; ++e)
        available.append(QByteArray(extProps[e].extensionName));
    QByteArrayList wanted = QRhiVulkanInitParams::preferredExtensionsForImportedDevice();
    if (!wanted.contains(QByteArrayLiteral("VK_KHR_swapchain")))
        wanted.append(QByteArrayLiteral("VK_KHR_swapchain"));
    wanted.append(QByteArrayLiteral("VK_EXT_device_fault")); // Qt's own device enables it; QRhi claims it on import
    QByteArrayList extensions;
    QByteArrayList missing;
    for (const QByteArray &w : wanted) {
        if (extensions.contains(w))
            continue;
        if (available.contains(w))
            extensions.append(w);
        else
            missing.append(w);
    }
    o->insert(QStringLiteral("extensions"), byteArrayList(extensions));
    o->insert(QStringLiteral("extensions_missing"), byteArrayList(missing));

    // Qt's feature set (facts A6.2): every supported feature of the structures API 1.2 chains, plus the feature
    // structures of the extensions we enable, robustBufferAccess off (robustImageAccess is a 1.3 member and is not
    // chained at 1.2). The query's output is the create's input.
    VkPhysicalDeviceVulkan11Features f11 = {};
    f11.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES;
    VkPhysicalDeviceVulkan12Features f12 = {};
    f12.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES;
    VkPhysicalDeviceFragmentShadingRateFeaturesKHR fsr = {};
    fsr.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FRAGMENT_SHADING_RATE_FEATURES_KHR;
    VkPhysicalDeviceVertexAttributeDivisorFeaturesEXT divisor = {};
    divisor.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VERTEX_ATTRIBUTE_DIVISOR_FEATURES_EXT;
    VkPhysicalDeviceFaultFeaturesEXT fault = {};
    fault.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FAULT_FEATURES_EXT;
    VkPhysicalDeviceFeatures2 f2 = {};
    f2.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2;
    f2.pNext = &f11;
    f11.pNext = &f12;
    void **tail = &f12.pNext;
    QJsonArray chained = { QStringLiteral("VkPhysicalDeviceFeatures"), QStringLiteral("VkPhysicalDeviceVulkan11Features"),
                           QStringLiteral("VkPhysicalDeviceVulkan12Features") };
    if (extensions.contains(QByteArrayLiteral("VK_KHR_fragment_shading_rate"))) {
        *tail = &fsr;
        tail = &fsr.pNext;
        chained.append(QStringLiteral("VkPhysicalDeviceFragmentShadingRateFeaturesKHR"));
    }
    if (extensions.contains(QByteArrayLiteral("VK_EXT_vertex_attribute_divisor"))) {
        *tail = &divisor;
        tail = &divisor.pNext;
        chained.append(QStringLiteral("VkPhysicalDeviceVertexAttributeDivisorFeaturesEXT"));
    }
    if (extensions.contains(QByteArrayLiteral("VK_EXT_device_fault"))) {
        *tail = &fault;
        tail = &fault.pNext;
        chained.append(QStringLiteral("VkPhysicalDeviceFaultFeaturesEXT"));
    }
    getFeatures2(ctx->physDev, &f2);
    const bool robustSupported = f2.features.robustBufferAccess == VK_TRUE;
    f2.features.robustBufferAccess = VK_FALSE;
    o->insert(QStringLiteral("feature_structures"), chained);
    o->insert(QStringLiteral("robust_buffer_access_supported_and_left_off"), robustSupported);
    QJsonObject enabled;
    enabled.insert(QStringLiteral("vulkan10"),
                   featureRecord(&f2.features, kFeatures10, std::size(kFeatures10), 0, kSpecCount10));
    enabled.insert(QStringLiteral("vulkan11"),
                   featureRecord(&f11, kFeatures11, std::size(kFeatures11),
                                 offsetof(VkPhysicalDeviceVulkan11Features, storageBuffer16BitAccess), kSpecCount11));
    enabled.insert(QStringLiteral("vulkan12"),
                   featureRecord(&f12, kFeatures12, std::size(kFeatures12),
                                 offsetof(VkPhysicalDeviceVulkan12Features, samplerMirrorClampToEdge), kSpecCount12));
    o->insert(QStringLiteral("enabled_features"), enabled);

    const float priority = 1.0f;
    VkDeviceQueueCreateInfo queueInfo = {};
    queueInfo.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    queueInfo.queueFamilyIndex = ctx->family;
    queueInfo.queueCount = 1;
    queueInfo.pQueuePriorities = &priority;
    const std::vector<const char *> extensionPtrs = pointers(extensions);
    VkDeviceCreateInfo dci = {};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.pNext = &f2;
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &queueInfo;
    dci.enabledExtensionCount = uint32_t(extensionPtrs.size());
    dci.ppEnabledExtensionNames = extensionPtrs.empty() ? nullptr : extensionPtrs.data();
    const VkResult created = createDevice(ctx->physDev, &dci, nullptr, &ctx->device);
    if (created != VK_SUCCESS) {
        ctx->device = VK_NULL_HANDLE;
        o->insert(QStringLiteral("error"), QStringLiteral("vkCreateDevice: ") + vkResultName(created));
        return false;
    }
    o->insert(QStringLiteral("vk_device"), qint64(reinterpret_cast<quintptr>(ctx->device)));
    o->insert(QStringLiteral("vk_physical_device"), qint64(reinterpret_cast<quintptr>(ctx->physDev)));
    return true;
}

} // namespace

QByteArray n06VulkanFactsJson()
{
    QJsonObject root;
    root.insert(QStringLiteral("round"), QStringLiteral("facts"));
    Loader loader;
    QString error;
    if (!loader.load(&error)) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), error);
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    root.insert(QStringLiteral("instance"), instanceFacts(loader));
    root.insert(QStringLiteral("qt_own_device"), qtOwnDeviceFacts());
    root.insert(QStringLiteral("ok"), true);
    return QJsonDocument(root).toJson(QJsonDocument::Compact);
}

QByteArray n06ContextCreateJson(bool wantValidation)
{
    QJsonObject root;
    root.insert(QStringLiteral("round"), QStringLiteral("device"));
    if (g_context) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), QStringLiteral("a context exists already"));
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    auto ctx = std::make_unique<Context>();
    QString error;
    if (!ctx->loader.load(&error)) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), error);
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    QJsonObject instance;
    const bool instanceOk = createOurInstance(ctx.get(), wantValidation, &instance);
    root.insert(QStringLiteral("instance"), instance);
    QJsonObject device;
    const bool deviceOk = instanceOk && createOurDevice(ctx.get(), &device);
    root.insert(QStringLiteral("device"), device);

    QJsonObject reference;
    if (deviceOk) {
        ctx->reference.reset(new QVulkanInstance);
        ctx->reference->setApiVersion(QVersionNumber(1, 2));
        ctx->reference->setExtensions(QRhiVulkanInitParams::preferredInstanceExtensions());
        if (ctx->reference->create()) {
            reference.insert(QStringLiteral("api_version"), ctx->reference->apiVersion().toString());
            reference.insert(QStringLiteral("extensions"), byteArrayList(ctx->reference->extensions()));
        } else {
            reference.insert(QStringLiteral("error"), QStringLiteral("QVulkanInstance::create failed (VkResult %1)")
                                                          .arg(int(ctx->reference->errorCode())));
        }
    }
    root.insert(QStringLiteral("reference_instance"), reference);
    const bool ok = deviceOk && !reference.contains(QStringLiteral("error"));
    root.insert(QStringLiteral("ok"), ok);
    g_context = ctx.release(); // kept even on failure so that destroy() releases whatever was created
    return QJsonDocument(root).toJson(QJsonDocument::Compact);
}

void n06SetPhase(const QString &phase)
{
    if (g_context)
        g_context->stats.setPhase(phase);
}

QByteArray n06ContextDestroyJson()
{
    QJsonObject root;
    if (!g_context) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), QStringLiteral("no context"));
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    Context *ctx = g_context;
    ctx->stats.setPhase(QStringLiteral("teardown"));
    QJsonArray steps;
    if (ctx->device != VK_NULL_HANDLE) {
        // The windows are gone; this wait also covers any queue Qt's QRhi never waited on (facts A7).
        const VkResult idle = ctx->deviceWaitIdle(ctx->device);
        steps.append(QStringLiteral("vkDeviceWaitIdle: ") + (idle == VK_SUCCESS ? QStringLiteral("VK_SUCCESS")
                                                                               : vkResultName(idle)));
        ctx->destroyDevice(ctx->device, nullptr);
        steps.append(QStringLiteral("vkDestroyDevice"));
        if (ctx->ours) {
            ctx->ours->resetDeviceFunctions(ctx->device); // QRhi cached them; it never resets an imported device's
            steps.append(QStringLiteral("resetDeviceFunctions"));
        }
        root.insert(QStringLiteral("device_wait_idle_ok"), idle == VK_SUCCESS);
        ctx->device = VK_NULL_HANDLE;
    }
    if (ctx->reference) {
        ctx->reference->destroy();
        ctx->reference.reset();
        steps.append(QStringLiteral("reference QVulkanInstance destroyed"));
    }
    if (ctx->ours) {
        ctx->ours->destroy(); // an adopted VkInstance is not destroyed by Qt
        ctx->ours.reset();
        steps.append(QStringLiteral("adopting QVulkanInstance destroyed"));
    }
    if (ctx->messenger != VK_NULL_HANDLE && ctx->destroyMessenger) {
        ctx->destroyMessenger(ctx->instance, ctx->messenger, nullptr);
        ctx->messenger = VK_NULL_HANDLE;
        steps.append(QStringLiteral("vkDestroyDebugUtilsMessengerEXT"));
    }
    if (ctx->instance != VK_NULL_HANDLE && ctx->destroyInstance) {
        ctx->destroyInstance(ctx->instance, nullptr);
        ctx->instance = VK_NULL_HANDLE;
        steps.append(QStringLiteral("vkDestroyInstance"));
    }
    root.insert(QStringLiteral("steps"), steps);
    root.insert(QStringLiteral("messages"), ctx->stats.toJson());
    root.insert(QStringLiteral("ok"), true);
    delete ctx;
    g_context = nullptr;
    return QJsonDocument(root).toJson(QJsonDocument::Compact);
}

#ifdef SPIKE_WITH_QUICK
bool n06AttachQuickWindow(QQuickWindow *window, bool ours, QString *error)
{
    if (!window || !g_context || !g_context->ours || !g_context->reference || g_context->device == VK_NULL_HANDLE) {
        *error = QStringLiteral("no window, or no complete N0.6 context");
        return false;
    }
    if (ours) {
        window->setVulkanInstance(g_context->ours.get());
        window->setGraphicsDevice(QQuickGraphicsDevice::fromDeviceObjects(
            g_context->physDev, g_context->device, int(g_context->family), 0));
    } else {
        window->setVulkanInstance(g_context->reference.get());
    }
    return true;
}
#endif

} // namespace srpss_spike
