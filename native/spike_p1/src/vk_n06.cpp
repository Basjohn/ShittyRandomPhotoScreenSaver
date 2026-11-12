#include "vk_n06.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QByteArrayList>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QString>
#include <QtCore/QVersionNumber>
#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib: every entry point comes from the loader at run time
#endif
#include <vulkan/vulkan.h>

#include <cstddef>
#include <cstring>
#include <iterator>
#include <memory>
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

} // namespace srpss_spike
