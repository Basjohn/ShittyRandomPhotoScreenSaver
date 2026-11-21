#include "vulkan_context.h"

#include "job_service.h"
#include "pipeline_cache.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArrayList>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QVersionNumber>
#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>
// N3.6, checkpoint audit 11 M1 (harness only): the device-function table Qt's QRhi submits through
// (QVulkanDeviceFunctionsPrivate::m_funcs), Qt6::GuiPrivate, pinned to PySide6's exact Qt like every QRhi use.
#include <QtGui/private/qvulkanfunctions_p.h>
#include <QtQuick/QQuickGraphicsConfiguration>
#include <QtQuick/QQuickGraphicsDevice>
#include <QtQuick/QQuickWindow>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib: every entry point comes from the loader at run time
#endif
#include <vulkan/vulkan.h>

// No STL container, lock or function wrapper anywhere in the core: their code lives in msvcp140.dll, whose in-process
// copy is shiboken6's older one (rendering/native/runtime_check.py refuses a module that imports it). Qt's instead.
#include <cstring>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

namespace srpss_core {

namespace {

const char kValidationLayer[] = "VK_LAYER_KHRONOS_validation";

// vkGetPhysicalDeviceWin32PresentationSupportKHR without the platform header (VK_KHR_win32_surface); it "can be
// called prior to creating a surface".
typedef VkBool32(VKAPI_PTR *PfnWin32PresentationSupport)(VkPhysicalDevice, uint32_t);

struct Loader
{
    HMODULE library = nullptr;
    PFN_vkGetInstanceProcAddr getInstanceProcAddr = nullptr;

    Loader() = default;
    Loader(const Loader &) = delete;
    Loader &operator=(const Loader &) = delete;
    ~Loader()
    {
        if (library)
            FreeLibrary(library); // balances LoadLibraryW (Qt holds its own reference)
    }

    bool load(QString *error)
    {
        library = LoadLibraryW(L"vulkan-1.dll"); // the loader the driver installed; Qt loads the same one
        if (!library) {
            *error = QStringLiteral("vulkan-1.dll could not be loaded (Win32 error %1)").arg(GetLastError());
            return false;
        }
        getInstanceProcAddr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
            reinterpret_cast<void *>(GetProcAddress(library, "vkGetInstanceProcAddr")));
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

// Every debug-utils message, counted per phase. Qt's own QRhi filter hides two known false positives
// ("Mapping an image with layout ..." and VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307, facts E2); they are
// counted apart, never as clean, and nothing else is set aside. Errors and warnings keep their phase, thread and the
// caller's stack, so the harness attributes each to its owner (Qt's recorded defects are excused only by id there).
struct MessageStats
{
    struct Counts
    {
        int errors = 0;
        int warnings = 0;
        int info = 0;
        int qtKnownFalsePositives = 0;
    };

    QMutex mutex;
    QString phase = QStringLiteral("create");
    QStringList order { QStringLiteral("create") };
    QHash<QString, Counts> counts;
    QJsonArray entries;                 // errors and warnings with phase, thread, the caller's stack and a count
    QHash<QString, qsizetype> entryIndex; // (phase, id, severity, first caller) -> its entry
    int entriesDropped = 0;             // distinct messages beyond the entry cap

    void setPhase(const QString &p)
    {
        QMutexLocker lock(&mutex);
        phase = p;
        if (!order.contains(p))
            order.append(p);
    }

    QJsonObject toJson()
    {
        QMutexLocker lock(&mutex);
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
        o.insert(QStringLiteral("entries"), entries);
        o.insert(QStringLiteral("entries_dropped"), entriesDropped);
        return o;
    }
};

// The calling thread's description (Qt names its QThreads with SetThreadDescription) and id.
QString threadLabel()
{
    using GetDescription = HRESULT(WINAPI *)(HANDLE, PWSTR *);
    static const auto getDescription = reinterpret_cast<GetDescription>(
        reinterpret_cast<void *>(GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "GetThreadDescription")));
    QString name;
    if (getDescription) {
        PWSTR text = nullptr;
        if (SUCCEEDED(getDescription(GetCurrentThread(), &text)) && text) {
            name = QString::fromWCharArray(text);
            LocalFree(text);
        }
    }
    return QStringLiteral("%1 (tid %2)").arg(name.isEmpty() ? QStringLiteral("unnamed") : name)
        .arg(qulonglong(GetCurrentThreadId()));
}

// The caller's stack as module+offset (unwind data only, no symbols): who called the Vulkan entry point the layer
// reports on (this module, Qt6Gui.dll's QRhi, Qt6Quick.dll, the driver) is the first non-layer, non-loader frame.
QJsonArray callerStack()
{
    void *frames[48];
    const USHORT n = CaptureStackBackTrace(2, 48, frames, nullptr);
    QJsonArray out;
    for (USHORT i = 0; i < n; ++i) {
        HMODULE module = nullptr;
        QString name = QStringLiteral("?");
        quintptr offset = quintptr(frames[i]);
        if (GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                               reinterpret_cast<LPCWSTR>(frames[i]), &module)
            && module) {
            wchar_t path[MAX_PATH];
            const DWORD len = GetModuleFileNameW(module, path, MAX_PATH);
            const QString full = QString::fromWCharArray(path, int(len));
            name = full.mid(full.lastIndexOf(QLatin1Char('\\')) + 1);
            offset = quintptr(frames[i]) - reinterpret_cast<quintptr>(module);
        }
        out.append(QStringLiteral("%1+0x%2").arg(name).arg(qulonglong(offset), 0, 16));
    }
    return out;
}

VKAPI_ATTR VkBool32 VKAPI_CALL debugCallback(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
                                             VkDebugUtilsMessageTypeFlagsEXT types,
                                             const VkDebugUtilsMessengerCallbackDataEXT *data, void *user)
{
    auto *stats = static_cast<MessageStats *>(user);
    const char *message = (data && data->pMessage) ? data->pMessage : "";
    const char *id = (data && data->pMessageIdName) ? data->pMessageIdName : "";
    const bool qtKnown = std::strstr(message, "Mapping an image with layout") != nullptr
        || std::strstr(id, "VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307") != nullptr
        || std::strstr(message, "VUID-VkDescriptorSetAllocateInfo-descriptorPool-00307") != nullptr;
    const bool error = (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) != 0;
    const bool warning = (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT) != 0;
    QJsonArray stack;
    QString thread;
    if (error || warning) { // outside the lock: the stack and the thread are the caller's own
        stack = callerStack();
        thread = threadLabel();
    }
    QMutexLocker lock(&stats->mutex);
    MessageStats::Counts &c = stats->counts[stats->phase];
    if (qtKnown && (error || warning))
        ++c.qtKnownFalsePositives;
    else if (error)
        ++c.errors;
    else if (warning)
        ++c.warnings;
    else
        ++c.info;
    if (!(error || warning))
        return VK_FALSE;
    // One entry per (phase, id, severity, the first caller below the layer and the loader), with a count: a message
    // repeated every frame or every creation stays one entry, and two callers of one id stay apart.
    QString caller;
    for (qsizetype i = 0; i < stack.size(); ++i) {
        const QString text = stack.at(i).toString();
        if (!text.startsWith(QStringLiteral("VkLayer_")) && !text.startsWith(QStringLiteral("vulkan-1.dll"))) {
            caller = text.section(QStringLiteral("+0x"), 0, 0);
            break;
        }
    }
    const QString key = stats->phase + QStringLiteral("|") + QString::fromUtf8(id) + QStringLiteral("|")
        + (error ? QStringLiteral("error") : QStringLiteral("warning")) + QStringLiteral("|") + caller;
    const auto known = stats->entryIndex.constFind(key);
    if (known != stats->entryIndex.cend()) {
        QJsonObject e = stats->entries.at(known.value()).toObject();
        e.insert(QStringLiteral("count"), e.value(QStringLiteral("count")).toInt() + 1);
        stats->entries.replace(known.value(), e);
        return VK_FALSE;
    }
    if (stats->entries.size() < 400) {
        QJsonObject e;
        e.insert(QStringLiteral("count"), 1);
        e.insert(QStringLiteral("first_caller"), caller);
        e.insert(QStringLiteral("phase"), stats->phase);
        e.insert(QStringLiteral("source"), QStringLiteral("our_instance"));
        e.insert(QStringLiteral("severity"), error ? QStringLiteral("error") : QStringLiteral("warning"));
        e.insert(QStringLiteral("type"), int(types));
        e.insert(QStringLiteral("id"), QString::fromUtf8(id));
        e.insert(QStringLiteral("message"), QString::fromUtf8(message).left(4000));
        e.insert(QStringLiteral("qt_known_false_positive"), qtKnown);
        e.insert(QStringLiteral("thread"), thread);
        e.insert(QStringLiteral("stack"), stack);
        QJsonArray objects;
        for (uint32_t i = 0; data && i < data->objectCount; ++i) {
            const VkDebugUtilsObjectNameInfoEXT &obj = data->pObjects[i];
            QJsonObject ob;
            ob.insert(QStringLiteral("type"), int(obj.objectType));
            ob.insert(QStringLiteral("handle"), QStringLiteral("0x%1").arg(qulonglong(obj.objectHandle), 0, 16));
            if (obj.pObjectName)
                ob.insert(QStringLiteral("name"), QString::fromUtf8(obj.pObjectName));
            objects.append(ob);
        }
        e.insert(QStringLiteral("objects"), objects);
        stats->entryIndex.insert(key, stats->entries.size());
        stats->entries.append(e);
    } else {
        ++stats->entriesDropped; // counted by the harness as unexplained (never silently clean)
    }
    return VK_FALSE;
}

// The process instance.
struct Instance
{
    Loader loader;
    VkInstance instance = VK_NULL_HANDLE;
    VkDebugUtilsMessengerEXT messenger = VK_NULL_HANDLE;
    PFN_vkDestroyInstance destroyInstance = nullptr;
    PFN_vkDestroyDebugUtilsMessengerEXT destroyMessenger = nullptr;
    std::unique_ptr<QVulkanInstance> adopted; // adopts `instance` (QRhi and Qt Quick see this one)
    MessageStats stats;                       // outlives the messenger (deleted with the instance)
    bool validationLoaded = false;
    QAtomicInt liveDevices { 0 };
};

Instance *g_instance = nullptr;

// N3.2: each created device's facts (vulkanDeviceFacts), written on the GUI thread, read by any.
QMutex g_factsMutex;
QHash<quint64, QJsonObject> g_deviceFacts;
// N3.4, harness only: the next devices made without independentBlend (setDeviceWithoutIndependentBlend).
QAtomicInt g_withoutIndependentBlend { 0 };
// N3.6, checkpoint audit 11 M2, harness only: the next creations that fail as vkCreateDevice failing (setDeviceCreateFailures).
QAtomicInt g_createFailures { 0 };
QAtomicInteger<qint64> g_createForced { 0 };

bool takeForcedCreateFailure()
{
    int left = g_createFailures.loadAcquire();
    while (left > 0 && !g_createFailures.testAndSetOrdered(left, left - 1))
        left = g_createFailures.loadAcquire();
    if (left <= 0)
        return false;
    g_createForced.fetchAndAddRelaxed(1);
    return true;
}

QByteArrayList availableInstanceExtensions(const Loader &loader, const char *layer)
{
    auto enumerate = loader.get<PFN_vkEnumerateInstanceExtensionProperties>(
        nullptr, "vkEnumerateInstanceExtensionProperties");
    QByteArrayList names;
    if (!enumerate)
        return names;
    uint32_t n = 0;
    enumerate(layer, &n, nullptr);
    QList<VkExtensionProperties> props; // sized by resize: `props(qsizetype(n))` would declare a function
    props.resize(qsizetype(n));
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
    QList<VkLayerProperties> props;
    props.resize(qsizetype(n));
    if (n)
        enumerate(&n, props.data());
    for (uint32_t i = 0; i < n; ++i) {
        if (std::strcmp(props[i].layerName, name) == 0)
            return true;
    }
    return false;
}

QList<const char *> pointers(const QByteArrayList &list)
{
    QList<const char *> v;
    v.reserve(list.size());
    for (const QByteArray &s : list)
        v.append(s.constData());
    return v;
}

bool createVkInstance(Instance *inst, bool wantValidation, bool wantShaderAccesses, QByteArrayList *extensionsOut,
                      QByteArrayList *layersOut, QJsonObject *o)
{
    auto createInstance = inst->loader.get<PFN_vkCreateInstance>(nullptr, "vkCreateInstance");
    if (!createInstance) {
        o->insert(QStringLiteral("error"), QStringLiteral("the loader has no vkCreateInstance"));
        return false;
    }
    const QByteArrayList available = availableInstanceExtensions(inst->loader, nullptr);
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
    bool shaderAccesses = false;
    QString validation;
    if (!wantValidation) {
        validation = QStringLiteral("not requested");
    } else if (!layerAvailable(inst->loader, kValidationLayer)) {
        validation = QStringLiteral("requested, but the layer is not installed");
    } else {
        layers.append(QByteArray(kValidationLayer));
        const QByteArrayList layerExtensions = availableInstanceExtensions(inst->loader, kValidationLayer);
        if (layerExtensions.contains(QByteArrayLiteral("VK_EXT_validation_features"))) {
            extensions.append(QByteArrayLiteral("VK_EXT_validation_features"));
            syncValidation = true;
            validation = QStringLiteral("enabled with synchronisation validation");
        } else {
            validation = QStringLiteral("enabled without synchronisation validation "
                                        "(the layer offers no VK_EXT_validation_features)");
        }
#ifdef VK_EXT_layer_settings
        if (wantShaderAccesses && syncValidation
            && layerExtensions.contains(QByteArrayLiteral("VK_EXT_layer_settings"))) {
            extensions.append(QByteArrayLiteral("VK_EXT_layer_settings"));
            shaderAccesses = true;
        }
#endif
    }
    QString shaderAccessesNote;
    if (!wantShaderAccesses)
        shaderAccessesNote = QStringLiteral("not requested");
    else if (shaderAccesses)
        shaderAccessesNote = QStringLiteral("enabled (syncval_shader_accesses_heuristic)");
    else
        shaderAccessesNote = QStringLiteral("requested, but synchronisation validation or VK_EXT_layer_settings is "
                                            "unavailable");
    const bool debugUtils = extensions.contains(QByteArrayLiteral("VK_EXT_debug_utils"));

    const QList<const char *> extensionPtrs = pointers(extensions);
    const QList<const char *> layerPtrs = pointers(layers);
    VkApplicationInfo app = {};
    app.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app.pApplicationName = "srpss-native-core";
    app.apiVersion = VK_API_VERSION_1_2; // D6's baseline
    VkDebugUtilsMessengerCreateInfoEXT messengerInfo = {};
    messengerInfo.sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT;
    messengerInfo.messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_INFO_BIT_EXT
        | VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT;
    messengerInfo.messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT
        | VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT;
    messengerInfo.pfnUserCallback = debugCallback;
    messengerInfo.pUserData = &inst->stats;
    const VkValidationFeatureEnableEXT enables[] = { VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT };
    VkValidationFeaturesEXT validationFeatures = {};
    validationFeatures.sType = VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT;
    validationFeatures.enabledValidationFeatureCount = 1;
    validationFeatures.pEnabledValidationFeatures = enables;

    VkInstanceCreateInfo ci = {};
    ci.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    ci.pApplicationInfo = &app;
    ci.enabledExtensionCount = uint32_t(extensionPtrs.size());
    ci.ppEnabledExtensionNames = extensionPtrs.isEmpty() ? nullptr : extensionPtrs.constData();
    ci.enabledLayerCount = uint32_t(layerPtrs.size());
    ci.ppEnabledLayerNames = layerPtrs.isEmpty() ? nullptr : layerPtrs.constData();
    // The chained messenger sees vkCreateInstance and vkDestroyInstance themselves.
    const void **tail = &ci.pNext;
    if (debugUtils) {
        *tail = &messengerInfo;
        tail = &messengerInfo.pNext;
    }
    if (syncValidation) {
        *tail = &validationFeatures;
        tail = &validationFeatures.pNext;
    }
#ifdef VK_EXT_layer_settings
    // The layer's shader-access hazard checks are off by default (the layer says the heuristic can report false
    // positives); a harness proving barriers between compute passes needs them on to see a missing barrier at all.
    const VkBool32 shaderAccessesOn = VK_TRUE;
    VkLayerSettingEXT shaderAccessesSetting = {};
    shaderAccessesSetting.pLayerName = kValidationLayer;
    shaderAccessesSetting.pSettingName = "syncval_shader_accesses_heuristic";
    shaderAccessesSetting.type = VK_LAYER_SETTING_TYPE_BOOL32_EXT;
    shaderAccessesSetting.valueCount = 1;
    shaderAccessesSetting.pValues = &shaderAccessesOn;
    VkLayerSettingsCreateInfoEXT layerSettings = {};
    layerSettings.sType = VK_STRUCTURE_TYPE_LAYER_SETTINGS_CREATE_INFO_EXT;
    layerSettings.settingCount = 1;
    layerSettings.pSettings = &shaderAccessesSetting;
    if (shaderAccesses) {
        *tail = &layerSettings;
        tail = &layerSettings.pNext;
    }
#endif

    const VkResult created = createInstance(&ci, nullptr, &inst->instance);
    o->insert(QStringLiteral("api_version"), QStringLiteral("1.2"));
    o->insert(QStringLiteral("extensions"), byteArrayList(extensions));
    o->insert(QStringLiteral("extensions_missing"), byteArrayList(missing));
    o->insert(QStringLiteral("layers"), byteArrayList(layers));
    o->insert(QStringLiteral("validation"), validation);
    o->insert(QStringLiteral("validation_layer_loaded"), !layers.isEmpty());
    o->insert(QStringLiteral("synchronisation_validation"), syncValidation);
    o->insert(QStringLiteral("synchronisation_shader_accesses"), shaderAccesses);
    o->insert(QStringLiteral("synchronisation_shader_accesses_note"), shaderAccessesNote);
    *extensionsOut = extensions;
    *layersOut = layers;
    if (created != VK_SUCCESS) {
        inst->instance = VK_NULL_HANDLE;
        o->insert(QStringLiteral("error"), QStringLiteral("vkCreateInstance: ") + vkResultName(created));
        return false;
    }
    inst->destroyInstance = inst->loader.get<PFN_vkDestroyInstance>(inst->instance, "vkDestroyInstance");
    if (debugUtils) {
        auto createMessenger = inst->loader.get<PFN_vkCreateDebugUtilsMessengerEXT>(
            inst->instance, "vkCreateDebugUtilsMessengerEXT");
        inst->destroyMessenger = inst->loader.get<PFN_vkDestroyDebugUtilsMessengerEXT>(
            inst->instance, "vkDestroyDebugUtilsMessengerEXT");
        messengerInfo.pNext = nullptr;
        if (createMessenger)
            createMessenger(inst->instance, &messengerInfo, nullptr, &inst->messenger);
    }
    o->insert(QStringLiteral("messenger"), inst->messenger != VK_NULL_HANDLE);
    return true;
}

void destroyInstanceObjects(Instance *inst, QJsonArray *steps)
{
    if (inst->adopted) {
        inst->adopted->destroy(); // an adopted VkInstance is not destroyed by Qt
        inst->adopted.reset();
        steps->append(QStringLiteral("adopting QVulkanInstance destroyed"));
    }
    if (inst->messenger != VK_NULL_HANDLE && inst->destroyMessenger) {
        inst->destroyMessenger(inst->instance, inst->messenger, nullptr);
        inst->messenger = VK_NULL_HANDLE;
        steps->append(QStringLiteral("vkDestroyDebugUtilsMessengerEXT"));
    }
    if (inst->instance != VK_NULL_HANDLE && inst->destroyInstance) {
        inst->destroyInstance(inst->instance, nullptr);
        inst->instance = VK_NULL_HANDLE;
        steps->append(QStringLiteral("vkDestroyInstance"));
    }
}

} // namespace

QByteArray vulkanInstanceCreateJson(bool validation, bool shaderAccesses)
{
    QJsonObject root;
    if (g_instance) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), QStringLiteral("the process instance exists already"));
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    auto inst = std::make_unique<Instance>();
    QString error;
    if (!inst->loader.load(&error)) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), error);
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    QByteArrayList extensions;
    QByteArrayList layers;
    QJsonObject created;
    bool ok = createVkInstance(inst.get(), validation, shaderAccesses, &extensions, &layers, &created);
    if (ok) {
        inst->validationLoaded = !layers.isEmpty();
        // Adopt: the exact lists we enabled (Qt does not query an adopted instance) and the API version, without which
        // QRhi treats the device as Vulkan 1.0 (facts A3, A4).
        inst->adopted.reset(new QVulkanInstance);
        inst->adopted->setVkInstance(inst->instance);
        inst->adopted->setApiVersion(QVersionNumber(1, 2));
        inst->adopted->setLayers(layers);
        inst->adopted->setExtensions(extensions);
        if (!inst->adopted->create()) {
            created.insert(QStringLiteral("error"), QStringLiteral("QVulkanInstance::create (adopting) failed "
                                                                   "(VkResult %1)")
                                                        .arg(int(inst->adopted->errorCode())));
            ok = false;
        } else {
            QJsonObject adopted;
            adopted.insert(QStringLiteral("same_vk_instance"), inst->adopted->vkInstance() == inst->instance);
            adopted.insert(QStringLiteral("api_version"), inst->adopted->apiVersion().toString());
            adopted.insert(QStringLiteral("layers"), byteArrayList(inst->adopted->layers()));
            created.insert(QStringLiteral("adopted"), adopted);
        }
    }
    root.insert(QStringLiteral("instance"), created);
    root.insert(QStringLiteral("validation_layer_loaded"), created.value(QStringLiteral("validation_layer_loaded")));
    root.insert(QStringLiteral("ok"), ok);
    if (!ok) {
        QJsonArray steps;
        destroyInstanceObjects(inst.get(), &steps);
        root.insert(QStringLiteral("cleanup"), steps);
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    g_instance = inst.release();
    return QJsonDocument(root).toJson(QJsonDocument::Compact);
}

QByteArray vulkanInstanceDestroyJson()
{
    QJsonObject root;
    if (!g_instance) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), QStringLiteral("no process instance"));
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    const int live = g_instance->liveDevices.loadRelaxed();
    if (live != 0) {
        root.insert(QStringLiteral("ok"), false);
        root.insert(QStringLiteral("error"), QStringLiteral("%1 device(s) still live: windows and hidden hosts go "
                                                            "first, then their devices, then the instance")
                                                 .arg(live));
        return QJsonDocument(root).toJson(QJsonDocument::Compact);
    }
    g_instance->stats.setPhase(QStringLiteral("instance teardown"));
    QJsonArray steps;
    destroyInstanceObjects(g_instance, &steps);
    root.insert(QStringLiteral("steps"), steps);
    root.insert(QStringLiteral("messages"), g_instance->stats.toJson());
    root.insert(QStringLiteral("ok"), true);
    delete g_instance; // the loader reference (FreeLibrary) goes with it
    g_instance = nullptr;
    return QJsonDocument(root).toJson(QJsonDocument::Compact);
}

bool vulkanInstanceExists()
{
    return g_instance != nullptr;
}

void vulkanSetPhase(const QString &phase)
{
    if (g_instance)
        g_instance->stats.setPhase(phase);
}

int vulkanLiveDevices()
{
    return g_instance ? g_instance->liveDevices.loadRelaxed() : 0;
}

std::unique_ptr<VulkanDevice> VulkanDevice::create(QString *error)
{
    if (!g_instance || !g_instance->adopted) {
        *error = QStringLiteral("no Vulkan process instance: create it before a Vulkan host (D6 point 1)");
        return {};
    }
    Instance *inst = g_instance;
    const VkInstance vk = inst->instance;
    auto enumerateDevices = inst->loader.get<PFN_vkEnumeratePhysicalDevices>(vk, "vkEnumeratePhysicalDevices");
    auto getProperties = inst->loader.get<PFN_vkGetPhysicalDeviceProperties>(vk, "vkGetPhysicalDeviceProperties");
    auto getQueueFamilies = inst->loader.get<PFN_vkGetPhysicalDeviceQueueFamilyProperties>(
        vk, "vkGetPhysicalDeviceQueueFamilyProperties");
    auto getFeatures2 = inst->loader.get<PFN_vkGetPhysicalDeviceFeatures2>(vk, "vkGetPhysicalDeviceFeatures2");
    auto enumerateDeviceExtensions = inst->loader.get<PFN_vkEnumerateDeviceExtensionProperties>(
        vk, "vkEnumerateDeviceExtensionProperties");
    auto win32Present = inst->loader.get<PfnWin32PresentationSupport>(
        vk, "vkGetPhysicalDeviceWin32PresentationSupportKHR");
    auto createDevice = inst->loader.get<PFN_vkCreateDevice>(vk, "vkCreateDevice");
    if (!enumerateDevices || !getProperties || !getQueueFamilies || !getFeatures2 || !enumerateDeviceExtensions
        || !win32Present || !createDevice) {
        *error = QStringLiteral("an instance entry point is missing");
        return {};
    }

    uint32_t count = 0;
    enumerateDevices(vk, &count, nullptr);
    QList<VkPhysicalDevice> devices;
    devices.resize(qsizetype(count));
    if (count)
        enumerateDevices(vk, &count, devices.data());
    if (devices.isEmpty()) {
        *error = QStringLiteral("no physical device");
        return {};
    }
    qsizetype chosen = 0;
    for (qsizetype i = 0; i < devices.size(); ++i) {
        VkPhysicalDeviceProperties p = {};
        getProperties(devices[i], &p);
        if (p.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            chosen = i;
            break;
        }
    }
    const VkPhysicalDevice physDev = devices[chosen];
    VkPhysicalDeviceProperties props = {};
    getProperties(physDev, &props);

    uint32_t familyCount = 0;
    getQueueFamilies(physDev, &familyCount, nullptr);
    QList<VkQueueFamilyProperties> families;
    families.resize(qsizetype(familyCount));
    if (familyCount)
        getQueueFamilies(physDev, &familyCount, families.data());
    uint32_t family = 0;
    bool found = false;
    for (uint32_t f = 0; f < familyCount; ++f) {
        if ((families[f].queueFlags & VK_QUEUE_GRAPHICS_BIT) && win32Present(physDev, f) == VK_TRUE) {
            family = f;
            found = true;
            break;
        }
    }
    if (!found) {
        *error = QStringLiteral("no queue family with graphics and Win32 present");
        return {};
    }

    uint32_t extCount = 0;
    enumerateDeviceExtensions(physDev, nullptr, &extCount, nullptr);
    QList<VkExtensionProperties> extProps;
    extProps.resize(qsizetype(extCount));
    if (extCount)
        enumerateDeviceExtensions(physDev, nullptr, &extCount, extProps.data());
    QByteArrayList available;
    for (uint32_t e = 0; e < extCount; ++e)
        available.append(QByteArray(extProps[e].extensionName));
    QByteArrayList wanted = QRhiVulkanInitParams::preferredExtensionsForImportedDevice();
    if (!wanted.contains(QByteArrayLiteral("VK_KHR_swapchain")))
        wanted.append(QByteArrayLiteral("VK_KHR_swapchain"));
    wanted.append(QByteArrayLiteral("VK_EXT_device_fault")); // Qt's own device enables it; QRhi claims it on import
    QByteArrayList extensions;
    for (const QByteArray &w : wanted) {
        if (!extensions.contains(w) && available.contains(w))
            extensions.append(w);
    }

    // Qt's feature set (facts A6.2): every supported feature of the structures API 1.2 chains, plus the feature
    // structures of the extensions we enable, robustBufferAccess off. The query's output is the create's input.
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
    if (extensions.contains(QByteArrayLiteral("VK_KHR_fragment_shading_rate"))) {
        *tail = &fsr;
        tail = &fsr.pNext;
    }
    if (extensions.contains(QByteArrayLiteral("VK_EXT_vertex_attribute_divisor"))) {
        *tail = &divisor;
        tail = &divisor.pNext;
    }
    if (extensions.contains(QByteArrayLiteral("VK_EXT_device_fault"))) {
        *tail = &fault;
        tail = &fault.pNext;
    }
    getFeatures2(physDev, &f2);
    f2.features.robustBufferAccess = VK_FALSE;
    if (g_withoutIndependentBlend.loadAcquire() != 0)
        f2.features.independentBlend = VK_FALSE; // N3.4, harness only: a device that lacks the feature (D17's control)

    // N3.8 (D9 as built point 1): Qt's queue (index 0, priority 1.0) and, when the family has a second queue, the job
    // service's (index 1, priority 0.5: N0.6's layout, proved by N0.7). One queue: no service, every job in-frame.
    const float priorities[2] = { 1.0f, 0.5f };
    const uint32_t queueCount = families[family].queueCount >= 2 ? 2u : 1u;
    VkDeviceQueueCreateInfo queueInfo = {};
    queueInfo.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    queueInfo.queueFamilyIndex = family;
    queueInfo.queueCount = queueCount;
    queueInfo.pQueuePriorities = priorities;
    const QList<const char *> extensionPtrs = pointers(extensions);
    VkDeviceCreateInfo dci = {};
    dci.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    dci.pNext = &f2;
    dci.queueCreateInfoCount = 1;
    dci.pQueueCreateInfos = &queueInfo;
    dci.enabledExtensionCount = uint32_t(extensionPtrs.size());
    dci.ppEnabledExtensionNames = extensionPtrs.isEmpty() ? nullptr : extensionPtrs.constData();
    VkDevice device = VK_NULL_HANDLE;
    if (takeForcedCreateFailure()) {
        // N3.6, audit 11 M2 (harness only): vkCreateDevice failing, as it may while the driver still resets after a TDR.
        *error = QStringLiteral("vkCreateDevice: ") + vkResultName(VK_ERROR_INITIALIZATION_FAILED)
            + QStringLiteral(" (forced by the harness)");
        return {};
    }
    const VkResult created = createDevice(physDev, &dci, nullptr, &device);
    if (created != VK_SUCCESS) {
        *error = QStringLiteral("vkCreateDevice: ") + vkResultName(created);
        return {};
    }
    if (inst->validationLoaded) {
        // A debug-utils name, so that validation messages say whose object it is.
        auto setName = inst->loader.get<PFN_vkSetDebugUtilsObjectNameEXT>(vk, "vkSetDebugUtilsObjectNameEXT");
        if (setName) {
            const QByteArray text = QByteArrayLiteral("srpss native core VkDevice");
            VkDebugUtilsObjectNameInfoEXT info = {};
            info.sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_OBJECT_NAME_INFO_EXT;
            info.objectType = VK_OBJECT_TYPE_DEVICE;
            info.objectHandle = uint64_t(reinterpret_cast<quintptr>(device));
            info.pObjectName = text.constData();
            setName(device, &info);
        }
    }
    std::unique_ptr<VulkanDevice> out(new VulkanDevice);
    out->m_device = quint64(reinterpret_cast<quintptr>(device));
    {
        // N3.2 (D15 point 3): QRhi never checks these, so the core records them once from the device it made.
        QJsonObject facts;
        facts.insert(QStringLiteral("min_uniform_buffer_offset_alignment"),
                     double(props.limits.minUniformBufferOffsetAlignment));
        facts.insert(QStringLiteral("max_uniform_buffer_range"), double(props.limits.maxUniformBufferRange));
        facts.insert(QStringLiteral("max_descriptor_set_uniform_buffers_dynamic"),
                     double(props.limits.maxDescriptorSetUniformBuffersDynamic));
        facts.insert(QStringLiteral("max_storage_buffer_range"), double(props.limits.maxStorageBufferRange));
        facts.insert(QStringLiteral("multi_draw_indirect"), f2.features.multiDrawIndirect == VK_TRUE);
        facts.insert(QStringLiteral("draw_indirect_first_instance"),
                     f2.features.drawIndirectFirstInstance == VK_TRUE);
        facts.insert(QStringLiteral("shader_draw_parameters"), f11.shaderDrawParameters == VK_TRUE);
        facts.insert(QStringLiteral("device_name"), QString::fromUtf8(props.deviceName));
        // N3.3 (D16 point 6): compute needs the graphics family's compute bit (QRhi::Compute), and a storage image its
        // format's STORAGE_IMAGE feature (R16F needs the extended storage formats); read once here, never assumed.
        facts.insert(QStringLiteral("queue_family_compute"), (families[family].queueFlags & VK_QUEUE_COMPUTE_BIT) != 0);
        facts.insert(QStringLiteral("shader_storage_image_extended_formats"),
                     f2.features.shaderStorageImageExtendedFormats == VK_TRUE);
        facts.insert(QStringLiteral("max_compute_work_group_count_x"), double(props.limits.maxComputeWorkGroupCount[0]));
        facts.insert(QStringLiteral("max_compute_work_group_invocations"),
                     double(props.limits.maxComputeWorkGroupInvocations));
        auto getFormat = inst->loader.get<PFN_vkGetPhysicalDeviceFormatProperties>(vk,
                                                                                  "vkGetPhysicalDeviceFormatProperties");
        if (getFormat) {
            const struct { const char *name; VkFormat format; } storageFormats[] = {
                { "rgba8", VK_FORMAT_R8G8B8A8_UNORM }, { "rgba16f", VK_FORMAT_R16G16B16A16_SFLOAT },
                { "rgba32f", VK_FORMAT_R32G32B32A32_SFLOAT }, { "r16f", VK_FORMAT_R16_SFLOAT },
                { "r32f", VK_FORMAT_R32_SFLOAT } };
            QJsonObject storage;
            for (const auto &f : storageFormats) {
                VkFormatProperties fp = {};
                getFormat(physDev, f.format, &fp);
                storage.insert(QLatin1String(f.name), (fp.optimalTilingFeatures & VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT) != 0);
            }
            facts.insert(QStringLiteral("storage_image_formats"), storage);
            // N3.4 (D17 point 3): which target formats blend as colour attachments (QRhi never asks).
            QJsonObject blend;
            for (const auto &f : storageFormats) {
                VkFormatProperties fp = {};
                getFormat(physDev, f.format, &fp);
                blend.insert(QLatin1String(f.name),
                             (fp.optimalTilingFeatures & VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BLEND_BIT) != 0);
            }
            facts.insert(QStringLiteral("color_attachment_blend"), blend);
        }
        // N3.4 (D17 point 3): the per-attachment blend and per-sample shading features as enabled on this device.
        facts.insert(QStringLiteral("independent_blend"), f2.features.independentBlend == VK_TRUE);
        facts.insert(QStringLiteral("sample_rate_shading"), f2.features.sampleRateShading == VK_TRUE);
        QMutexLocker lock(&g_factsMutex);
        g_deviceFacts.insert(out->m_device, facts);
    }
    out->m_physicalDevice = quint64(reinterpret_cast<quintptr>(physDev));
    out->m_family = family;
    out->m_queues = queueCount;
    out->m_deviceFault = extensions.contains(QByteArrayLiteral("VK_EXT_device_fault")) && fault.deviceFault == VK_TRUE;
    out->m_name = QString::fromUtf8(props.deviceName);
    if (queueCount >= 2) {
        // The job service (N3.8): an object now; its thread and its QRhi at the first job.
        JobDevice jobDevice;
        jobDevice.instance = inst->adopted.get();
        jobDevice.physicalDevice = out->m_physicalDevice;
        jobDevice.device = out->m_device;
        jobDevice.family = family;
        jobDevice.queueIndex = 1;
        jobDevice.debugMarkers = inst->validationLoaded;
        // N3.6 (pipeline_cache.h): the core's file beside Qt Quick's, checked against this device as Qt checks its own.
        jobDevice.cacheIdentity.backend = QStringLiteral("vulkan");
        jobDevice.cacheIdentity.driverVersion = props.driverVersion;
        jobDevice.cacheIdentity.vendorId = props.vendorID;
        jobDevice.cacheIdentity.deviceId = props.deviceID;
        jobDevice.cacheIdentity.cacheUuid = QByteArray(reinterpret_cast<const char *>(props.pipelineCacheUUID),
                                                       VK_UUID_SIZE);
        jobDevice.cacheFile = pipelineCacheFile(pipelineCacheDirectory(), jobDevice.cacheIdentity.backend);
        out->m_jobs = JobService::create(createRhiUploadBackend(jobDevice), out->m_device,
                                         QStringLiteral("device %1").arg(out->m_device));
    }
    ++inst->liveDevices;
    return out;
}

VulkanDevice::~VulkanDevice()
{
    destroy();
}

void VulkanDevice::applyTo(QQuickWindow *window) const
{
    if (!window || !g_instance || !g_instance->adopted || !m_device)
        return;
    if (g_instance->validationLoaded) {
        // With validation, Qt's QRhi names its resources and labels its passes (QRhi::EnableDebugMarkers), so a
        // message names Qt's objects as well as ours. Read by createRhi for an imported device too (facts E2).
        QQuickGraphicsConfiguration config = window->graphicsConfiguration();
        config.setDebugMarkers(true);
        window->setGraphicsConfiguration(config);
    }
    window->setVulkanInstance(g_instance->adopted.get());
    window->setGraphicsDevice(QQuickGraphicsDevice::fromDeviceObjects(
        reinterpret_cast<VkPhysicalDevice>(quintptr(m_physicalDevice)), reinterpret_cast<VkDevice>(quintptr(m_device)),
        int(m_family), 0));
}

void VulkanDevice::giveDeviceTo(QQuickWindow *window) const
{
    if (!window || !m_device)
        return;
    window->setGraphicsDevice(QQuickGraphicsDevice::fromDeviceObjects(
        reinterpret_cast<VkPhysicalDevice>(quintptr(m_physicalDevice)), reinterpret_cast<VkDevice>(quintptr(m_device)),
        int(m_family), 0));
}

QJsonObject VulkanDevice::faultReport() const
{
    QJsonObject o;
    o.insert(QStringLiteral("vk_device"), QString::number(m_device));
    if (!m_device || !g_instance) {
        o.insert(QStringLiteral("queried"), false);
        o.insert(QStringLiteral("why"), QStringLiteral("no device"));
        return o;
    }
    if (!m_deviceFault) {
        o.insert(QStringLiteral("queried"), false);
        o.insert(QStringLiteral("why"), QStringLiteral("VK_EXT_device_fault (or its deviceFault feature) is not "
                                                       "enabled on this device"));
        return o;
    }
    const VkDevice device = reinterpret_cast<VkDevice>(quintptr(m_device));
    auto getDeviceProcAddr = g_instance->loader.get<PFN_vkGetDeviceProcAddr>(g_instance->instance,
                                                                            "vkGetDeviceProcAddr");
    auto getFault = getDeviceProcAddr ? reinterpret_cast<PFN_vkGetDeviceFaultInfoEXT>(
                                            getDeviceProcAddr(device, "vkGetDeviceFaultInfoEXT"))
                                      : nullptr;
    if (!getFault) {
        o.insert(QStringLiteral("queried"), false);
        o.insert(QStringLiteral("why"), QStringLiteral("vkGetDeviceFaultInfoEXT did not resolve"));
        return o;
    }
    VkDeviceFaultCountsEXT counts = {};
    counts.sType = VK_STRUCTURE_TYPE_DEVICE_FAULT_COUNTS_EXT;
    VkResult result = getFault(device, &counts, nullptr);
    o.insert(QStringLiteral("queried"), true);
    o.insert(QStringLiteral("counts_result"), int(result));
    if (result != VK_SUCCESS && result != VK_INCOMPLETE)
        return o;
    QList<VkDeviceFaultAddressInfoEXT> addresses;
    addresses.resize(qsizetype(counts.addressInfoCount));
    QList<VkDeviceFaultVendorInfoEXT> vendors;
    vendors.resize(qsizetype(counts.vendorInfoCount));
    counts.vendorBinarySize = 0; // the vendor's binary crash dump is not read (its format is the vendor's own)
    VkDeviceFaultInfoEXT info = {};
    info.sType = VK_STRUCTURE_TYPE_DEVICE_FAULT_INFO_EXT;
    info.pAddressInfos = addresses.isEmpty() ? nullptr : addresses.data();
    info.pVendorInfos = vendors.isEmpty() ? nullptr : vendors.data();
    info.pVendorBinaryData = nullptr;
    result = getFault(device, &counts, &info);
    o.insert(QStringLiteral("info_result"), int(result));
    if (result != VK_SUCCESS && result != VK_INCOMPLETE)
        return o;
    o.insert(QStringLiteral("description"), QString::fromUtf8(info.description));
    QJsonArray addressList;
    for (uint32_t i = 0; i < counts.addressInfoCount && i < uint32_t(addresses.size()); ++i) {
        QJsonObject a;
        a.insert(QStringLiteral("type"), int(addresses[qsizetype(i)].addressType));
        a.insert(QStringLiteral("address"),
                 QStringLiteral("0x%1").arg(qulonglong(addresses[qsizetype(i)].reportedAddress), 0, 16));
        a.insert(QStringLiteral("precision"), double(addresses[qsizetype(i)].addressPrecision));
        addressList.append(a);
    }
    o.insert(QStringLiteral("addresses"), addressList);
    QJsonArray vendorList;
    for (uint32_t i = 0; i < counts.vendorInfoCount && i < uint32_t(vendors.size()); ++i) {
        QJsonObject v;
        v.insert(QStringLiteral("description"), QString::fromUtf8(vendors[qsizetype(i)].description));
        v.insert(QStringLiteral("code"), QStringLiteral("0x%1").arg(qulonglong(vendors[qsizetype(i)].vendorFaultCode),
                                                                  0, 16));
        v.insert(QStringLiteral("data"), QStringLiteral("0x%1").arg(qulonglong(vendors[qsizetype(i)].vendorFaultData),
                                                                  0, 16));
        vendorList.append(v);
    }
    o.insert(QStringLiteral("vendor_faults"), vendorList);
    return o;
}

QJsonObject vulkanDeviceFacts(quint64 device)
{
    QMutexLocker lock(&g_factsMutex);
    return g_deviceFacts.value(device);
}

void setDeviceWithoutIndependentBlend(bool without)
{
    g_withoutIndependentBlend.storeRelease(without ? 1 : 0);
}

bool deviceWithoutIndependentBlend()
{
    return g_withoutIndependentBlend.loadAcquire() != 0;
}

namespace {

// ------------------------------------------------------------------ N3.6, checkpoint audit 11 (harness only)

// QVulkanDeviceFunctions keeps its table in its one private member (d_ptr). An explicit instantiation may name a
// private member ([temp.spec.general]/6): the standard's way to reach it, with no guess at the class's layout.
struct DeviceFunctionsTable
{
    using type = QScopedPointer<QVulkanDeviceFunctionsPrivate> QVulkanDeviceFunctions::*;
    friend type deviceFunctionsTable(DeviceFunctionsTable);
};
template <typename Tag, typename Tag::type Member>
struct PrivateMember
{
    friend typename Tag::type deviceFunctionsTable(Tag) { return Member; }
};
template struct PrivateMember<DeviceFunctionsTable, &QVulkanDeviceFunctions::d_ptr>;

// M1: the armed loss. Written under g_lossMutex before the table's entry is exchanged (a full barrier), read by the
// replacement entry on any thread that submits through the device's table (Qt's render thread, the job thread).
QMutex g_lossMutex;
quint64 g_lossDevice = 0;                    // under g_lossMutex
PFN_vkVoidFunction *g_lossSlot = nullptr;    // the table's vkQueueSubmit entry (under g_lossMutex)
PFN_vkQueueSubmit g_lossOriginal = nullptr;  // the driver's (the entry's value before it was exchanged)
QAtomicInteger<quintptr> g_lossQueue { 0 };   // Qt's queue (VkQueue)
QAtomicInt g_lossArmed { 0 };                // 0 off, 1 the next submit, 2 every submit (sticky)
QAtomicInt g_lossSticky { 0 };
QAtomicInteger<qint64> g_lossInjected { 0 };
QAtomicInteger<qint64> g_lossForwarded { 0 };

VKAPI_ATTR VkResult VKAPI_CALL lossQueueSubmit(VkQueue queue, uint32_t submitCount, const VkSubmitInfo *submits,
                                               VkFence fence)
{
    if (reinterpret_cast<quintptr>(queue) == g_lossQueue.loadAcquire()) {
        const int armed = g_lossArmed.loadAcquire();
        if (armed == 2 || (armed == 1 && g_lossArmed.testAndSetOrdered(1, 0))) {
            g_lossInjected.fetchAndAddRelaxed(1);
            return VK_ERROR_DEVICE_LOST; // nothing submitted, as the driver does for a lost device
        }
    }
    g_lossForwarded.fetchAndAddRelaxed(1);
    return g_lossOriginal(queue, submitCount, submits, fence);
}

// Under g_lossMutex: the table's entry back to the driver's (the device is going, or another is armed).
void restoreLossSlotLocked()
{
    if (g_lossSlot && g_lossOriginal) {
        InterlockedExchangePointer(reinterpret_cast<PVOID volatile *>(g_lossSlot),
                                   reinterpret_cast<PVOID>(g_lossOriginal));
    }
    g_lossArmed.storeRelease(0);
    g_lossQueue.storeRelease(0);
    g_lossSlot = nullptr;
    g_lossDevice = 0;
}

// Under g_lossMutex, from the device's destruction (before resetDeviceFunctions frees the table).
void disarmSubmitLoss(quint64 device)
{
    QMutexLocker lock(&g_lossMutex);
    if (g_lossDevice == device)
        restoreLossSlotLocked();
}

} // namespace

bool injectSubmitLoss(quint64 device, quint32 family, bool sticky, QString *error)
{
    if (!g_instance || !g_instance->adopted || !device) {
        *error = QStringLiteral("no Vulkan device of the module's");
        return false;
    }
    QMutexLocker lock(&g_lossMutex);
    if (g_lossDevice && g_lossDevice != device) {
        *error = QStringLiteral("another device's loss is armed");
        return false;
    }
    const VkDevice dev = reinterpret_cast<VkDevice>(quintptr(device));
    QVulkanDeviceFunctions *df = g_instance->adopted->deviceFunctions(dev); // the one Qt's QRhi holds (cached per device)
    QVulkanFunctions *f = g_instance->adopted->functions();
    if (!df || !f) {
        *error = QStringLiteral("the instance has no function table for the device");
        return false;
    }
    if (!g_lossSlot) {
        // The entry QVulkanDeviceFunctionsPrivate resolved for vkQueueSubmit (it resolves every entry through the
        // instance's vkGetDeviceProcAddr), found by value: exactly one entry must hold it.
        const PFN_vkVoidFunction real = f->vkGetDeviceProcAddr(dev, "vkQueueSubmit");
        QVulkanDeviceFunctionsPrivate *table = (df->*deviceFunctionsTable(DeviceFunctionsTable())).data();
        if (!real || !table) {
            *error = QStringLiteral("vkQueueSubmit did not resolve");
            return false;
        }
        const int entries = int(sizeof(table->m_funcs) / sizeof(table->m_funcs[0]));
        PFN_vkVoidFunction *slot = nullptr;
        int matches = 0;
        for (int i = 0; i < entries; ++i) {
            if (table->m_funcs[i] == real) {
                slot = &table->m_funcs[i];
                ++matches;
            }
        }
        if (matches != 1) {
            *error = QStringLiteral("vkQueueSubmit is %1 of the table's %2 entries, not one").arg(matches).arg(entries);
            return false;
        }
        VkQueue queue = VK_NULL_HANDLE;
        df->vkGetDeviceQueue(dev, family, 0, &queue);
        g_lossOriginal = reinterpret_cast<PFN_vkQueueSubmit>(real);
        g_lossQueue.storeRelease(reinterpret_cast<quintptr>(queue));
        g_lossSlot = slot;
        g_lossDevice = device;
        InterlockedExchangePointer(reinterpret_cast<PVOID volatile *>(slot), reinterpret_cast<PVOID>(&lossQueueSubmit));
    }
    g_lossSticky.storeRelease(sticky ? 1 : 0);
    g_lossArmed.storeRelease(sticky ? 2 : 1);
    return true;
}

QJsonObject submitLossJson()
{
    QJsonObject o;
    {
        QMutexLocker lock(&g_lossMutex);
        o.insert(QStringLiteral("device"), QString::number(g_lossDevice));
        o.insert(QStringLiteral("table_entry_replaced"), g_lossSlot != nullptr);
    }
    o.insert(QStringLiteral("armed"), g_lossArmed.loadAcquire() != 0);
    o.insert(QStringLiteral("sticky"), g_lossSticky.loadAcquire() != 0);
    o.insert(QStringLiteral("injected"), double(g_lossInjected.loadRelaxed()));
    o.insert(QStringLiteral("forwarded"), double(g_lossForwarded.loadRelaxed()));
    return o;
}

void setDeviceCreateFailures(int count)
{
    g_createFailures.storeRelease(count > 0 ? count : 0);
}

QJsonObject deviceCreateFailuresJson()
{
    QJsonObject o;
    o.insert(QStringLiteral("remaining"), g_createFailures.loadAcquire());
    o.insert(QStringLiteral("forced"), double(g_createForced.loadRelaxed()));
    return o;
}

bool VulkanDevice::markLost()
{
    if (m_lost)
        return false;
    m_lost = true;
    return true;
}

namespace {

struct RawVulkanEntry
{
    RawVulkanObject object;
    qint64 retiredAtEdge = 0;
};

QMutex g_rawMutex;
QList<RawVulkanEntry> g_raw; // under g_rawMutex
QAtomicInt g_rawPending { 0 };
QAtomicInteger<qint64> g_rawDeferred { 0 };
QAtomicInteger<qint64> g_rawReleasedAtEdges { 0 };
QAtomicInteger<qint64> g_rawReleasedAtIdle { 0 };

void destroyRaw(const RawVulkanObject &object)
{
    if (!object.functions || !object.device || !object.handle)
        return;
    const VkDevice device = reinterpret_cast<VkDevice>(quintptr(object.device));
    switch (object.kind) {
    case RawVulkanKind::QueryPool:
        object.functions->vkDestroyQueryPool(device, reinterpret_cast<VkQueryPool>(quintptr(object.handle)), nullptr);
        break;
    }
}

// Under g_rawMutex: the device's entries `due` says may go, taken out of the queue.
template <typename Due>
QList<RawVulkanObject> takeRaw(quint64 device, Due due)
{
    QList<RawVulkanObject> taken;
    for (qsizetype i = 0; i < g_raw.size();) {
        if (g_raw.at(i).object.device == device && due(g_raw.at(i))) {
            taken.append(g_raw.at(i).object);
            g_raw.removeAt(i);
        } else {
            ++i;
        }
    }
    g_rawPending.storeRelease(int(g_raw.size()));
    return taken;
}

} // namespace

void deferRawVulkanDestroy(const RawVulkanObject &object, qint64 retiredAtEdge)
{
    if (!object.handle)
        return;
    QMutexLocker lock(&g_rawMutex);
    RawVulkanEntry entry;
    entry.object = object;
    entry.retiredAtEdge = retiredAtEdge;
    g_raw.append(entry);
    g_rawPending.storeRelease(int(g_raw.size()));
    g_rawDeferred.fetchAndAddRelaxed(1);
}

int releaseRawVulkan(quint64 device, qint64 edge, int framesInFlight)
{
    if (!device || g_rawPending.loadAcquire() == 0)
        return 0;
    QList<RawVulkanObject> taken;
    {
        QMutexLocker lock(&g_rawMutex);
        taken = takeRaw(device, [edge, framesInFlight](const RawVulkanEntry &entry) {
            return edge >= entry.retiredAtEdge + qint64(framesInFlight);
        });
    }
    for (const RawVulkanObject &object : taken)
        destroyRaw(object); // their last frames completed: no wait
    g_rawReleasedAtEdges.fetchAndAddRelaxed(taken.size());
    return int(taken.size());
}

int releaseAllRawVulkan(quint64 device)
{
    if (!device || g_rawPending.loadAcquire() == 0)
        return 0;
    QList<RawVulkanObject> taken;
    {
        QMutexLocker lock(&g_rawMutex);
        taken = takeRaw(device, [](const RawVulkanEntry &) { return true; });
    }
    for (const RawVulkanObject &object : taken)
        destroyRaw(object); // the device's queues are idle
    g_rawReleasedAtIdle.fetchAndAddRelaxed(taken.size());
    return int(taken.size());
}

bool rawVulkanPending()
{
    return g_rawPending.loadAcquire() != 0;
}

QJsonObject rawVulkanCountsJson()
{
    QJsonObject o;
    o.insert(QStringLiteral("raw_vulkan_deferred"), double(g_rawDeferred.loadRelaxed()));
    o.insert(QStringLiteral("raw_vulkan_released_at_edges"), double(g_rawReleasedAtEdges.loadRelaxed()));
    o.insert(QStringLiteral("raw_vulkan_released_at_idle"), double(g_rawReleasedAtIdle.loadRelaxed()));
    o.insert(QStringLiteral("raw_vulkan_pending"), g_rawPending.loadAcquire());
    return o;
}

QStringList VulkanDevice::destroy()
{
    QStringList steps;
    if (!m_device)
        return steps;
    disarmSubmitLoss(m_device); // audit 11 M1 (harness): the table goes with resetDeviceFunctions below
    if (m_jobs) {
        // Audit 11 L2: a device its window's QRhi found lost; the job thread, parked at rest, never met the loss itself,
        // so its teardown would save the lost device's pipeline cache over the good file. Told before the stop.
        if (m_lost)
            m_jobs->deviceWasLost();
        // D9 point 6 and D1's barrier: the job thread is quiesced first (its job in flight abandoned after its own GPU
        // wait, every output destroyed, its QRhi gone), in the device's destruction, never in the GUI's close.
        const QJsonObject stopped = m_jobs->stop();
        steps << (QStringLiteral("job service stopped: ")
                  + QString::fromUtf8(QJsonDocument(stopped).toJson(QJsonDocument::Compact)));
        m_jobs.reset();
    }
    {
        QMutexLocker lock(&g_factsMutex);
        g_deviceFacts.remove(m_device);
    }
    const VkDevice device = reinterpret_cast<VkDevice>(quintptr(m_device));
    if (g_instance) {
        auto waitIdle = g_instance->loader.get<PFN_vkDeviceWaitIdle>(g_instance->instance, "vkDeviceWaitIdle");
        auto destroyDevice = g_instance->loader.get<PFN_vkDestroyDevice>(g_instance->instance, "vkDestroyDevice");
        // Every QRhi on this device is gone; the wait also covers any queue Qt's QRhi never waited on (facts A7).
        const VkResult idle = waitIdle ? waitIdle(device) : VK_ERROR_INITIALIZATION_FAILED;
        steps << (QStringLiteral("vkDeviceWaitIdle: ")
                  + (idle == VK_SUCCESS ? QStringLiteral("VK_SUCCESS") : vkResultName(idle)));
        // N3.6: raw objects still deferred (their window rendered no later edge) go now, the device idle.
        const int raw = releaseAllRawVulkan(m_device);
        if (raw)
            steps << QStringLiteral("raw Vulkan objects destroyed at idle: %1").arg(raw);
        if (destroyDevice) {
            destroyDevice(device, nullptr);
            steps << QStringLiteral("vkDestroyDevice");
        }
        if (g_instance->adopted) {
            g_instance->adopted->resetDeviceFunctions(device); // QRhi cached them; it never resets an imported device's
            steps << QStringLiteral("resetDeviceFunctions");
        }
        --g_instance->liveDevices;
    }
    m_device = 0;
    return steps;
}

} // namespace srpss_core
