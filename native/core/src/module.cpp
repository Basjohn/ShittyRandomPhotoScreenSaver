// The SRPSS native core (D5.7): the product's CPython extension module (stable ABI, abi3). It links the same Qt DLLs
// PySide6 ships and talks to PySide6 objects only through raw pointers from shiboken6.getCppPointer(), so no
// shiboken-generated binding is needed (the P1 spike's binding approach, Native_Core_P1_Spike.md).
//
// Its one Python importer is rendering/native/ (loader.py and hosts.py), which checks what runtime_info() reports (the
// Qt versions, the ABI, the MSVC runtime the process loaded) and fails in one place with one reason. N2.2: the host
// adapter (host_adapter.h: the Qt Quick window host and the hidden host) and the frame driver behind it
// (frame_driver.h), the module's Vulkan instance and devices (vulkan_context.h), and the probe pass a harness switches
// on (probe_pass.h). N2.4: the composite, a scene-graph texture node carrying the card's coverage (composite.h), and
// the surfaces the frame driver records for it (surfaces.h). N2.6: the per-pass GPU timer in the frame driver
// (gpu_timer.h) and its known-cost pass (load_pass.h). N2.3: the packet reader, the core's one consuming reader of a
// Visualizer frame stream (packet_reader.h), with the frame ABI and the native schemas generated from the Python modules
// (frame_abi_generated.h). N2.5: Spectrum on a composite (spectrum.h), its stream read by a packet reader at the
// item's sync on the render thread. The product's one caller of the module is the backend owner,
// rendering.quick.bootstrap (N2.7), on the Vulkan rehearsal path and for its one kept hidden host; the native Spectrum
// is reached from the harnesses until the port's rules pass (D10).
//
// Every entry runs on the GUI thread (a packet reader's entries on the thread that owns it). The ones that wait for the
// hidden host's render thread release the GIL while they wait; the render thread itself never takes it (D5.4).
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "abi.h"
#include "backdrop.h"
#include "composite.h"
#include "gpu_timer.h"
#include "host_adapter.h"
#include "item_notifier.h"
#include "job_service.h"
#include "mode_content.h"
#include "mode_schema.h"
#include "packet_reader.h"
#include "process_counters.h"
#include "scene_targets.h"
#include "spectrum.h"
#include "surfaces.h"
#include "vulkan_context.h"

#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QMutex>
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <QtCore/QtGlobal>
#include <QtQuick/QQuickItem>

#include <cmath>
#include <cstring>
#include <iterator>
#include <memory>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

namespace {

void put(PyObject *dict, const char *key, PyObject *value)
{
    if (!value)
        return;
    PyDict_SetItemString(dict, key, value);
    Py_DECREF(value);
}

PyObject *pyStr(const QString &s)
{
    const QByteArray u = s.toUtf8();
    return PyUnicode_FromStringAndSize(u.constData(), u.size());
}

PyObject *pyJson(const QByteArray &json)
{
    return PyUnicode_FromStringAndSize(json.constData(), json.size());
}

PyObject *pyJson(const QJsonObject &object)
{
    return pyJson(QJsonDocument(object).toJson(QJsonDocument::Compact));
}

QString loadedModulePath(const wchar_t *name)
{
    HMODULE module = GetModuleHandleW(name);
    if (!module)
        return QString();
    wchar_t buffer[MAX_PATH * 2];
    const DWORD n = GetModuleFileNameW(module, buffer, DWORD(std::size(buffer)));
    return QString::fromWCharArray(buffer, int(n));
}

QString ownModulePath()
{
    HMODULE module = nullptr;
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       reinterpret_cast<LPCWSTR>(&ownModulePath), &module);
    wchar_t buffer[MAX_PATH * 2];
    const DWORD n = GetModuleFileNameW(module, buffer, DWORD(std::size(buffer)));
    return QString::fromWCharArray(buffer, int(n));
}

// ---------------------------------------------------------------- info

PyObject *runtime_info(PyObject *, PyObject *)
{
    PyObject *d = PyDict_New();
    put(d, "module", PyUnicode_FromString("_srpss_native_core"));
    put(d, "version", PyUnicode_FromString(SRPSS_NATIVE_CORE_VERSION));
    put(d, "abi", PyLong_FromLong(SRPSS_NATIVE_CORE_ABI));
    put(d, "qt_compiled", PyUnicode_FromString(QT_VERSION_STR));
    put(d, "qt_runtime", PyUnicode_FromString(qVersion()));
    put(d, "msc_full_ver", PyLong_FromLong(_MSC_FULL_VER));
    put(d, "py_limited_api", PyLong_FromLong(Py_LIMITED_API));
    put(d, "with_quick", PyBool_FromLong(1));
    put(d, "module_path", pyStr(ownModulePath()));
    PyObject *paths = PyDict_New();
    const wchar_t *names[] = { L"Qt6Core.dll",     L"Qt6Gui.dll",       L"Qt6Qml.dll",
                               L"Qt6Quick.dll",    L"msvcp140.dll",     L"msvcp140_1.dll",
                               L"msvcp140_2.dll",  L"vcruntime140.dll", L"vcruntime140_1.dll",
                               L"python3.dll",     L"vulkan-1.dll" };
    for (const wchar_t *name : names) {
        const QString path = loadedModulePath(name);
        const QByteArray key = QString::fromWCharArray(name).toUtf8();
        put(paths, key.constData(), path.isEmpty() ? (Py_INCREF(Py_None), Py_None) : pyStr(path));
    }
    put(d, "loaded_modules", paths);
    return d;
}

PyObject *process_counters(PyObject *, PyObject *)
{
    return pyJson(srpss_core::processCountersJson());
}

// ---------------------------------------------------------------- D6: the Vulkan instance

PyObject *vulkan_instance_create(PyObject *, PyObject *args)
{
    int validation = 0;
    int shaderAccesses = 0;
    if (!PyArg_ParseTuple(args, "|pp", &validation, &shaderAccesses))
        return nullptr;
    return pyJson(srpss_core::vulkanInstanceCreateJson(validation != 0, shaderAccesses != 0));
}

PyObject *vulkan_instance_destroy(PyObject *, PyObject *)
{
    return pyJson(srpss_core::vulkanInstanceDestroyJson());
}

PyObject *vulkan_set_phase(PyObject *, PyObject *args)
{
    const char *phase = nullptr;
    if (!PyArg_ParseTuple(args, "s", &phase))
        return nullptr;
    srpss_core::vulkanSetPhase(QString::fromUtf8(phase));
    Py_RETURN_NONE;
}

// ---------------------------------------------------------------- the host adapter (D5.1) and the frame driver (D5.2)

struct Hosts
{
    qint64 next = 1;
    QHash<qint64, std::shared_ptr<srpss_core::Host>> live;
};

Hosts &hosts()
{
    static Hosts h;
    return h;
}

srpss_core::Host *hostOf(long long handle)
{
    srpss_core::Host *host = hosts().live.value(handle).get();
    if (!host)
        PyErr_Format(PyExc_KeyError, "no host %lld (closed, or never created)", handle);
    return host;
}

srpss_core::HiddenHost *hiddenOf(long long handle)
{
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    auto *hidden = dynamic_cast<srpss_core::HiddenHost *>(host);
    if (!hidden)
        PyErr_Format(PyExc_TypeError, "host %lld is not a hidden host", handle);
    return hidden;
}

PyObject *runtimeError(const QString &error)
{
    PyErr_SetString(PyExc_RuntimeError, error.toUtf8().constData());
    return nullptr;
}

PyObject *host_attach(PyObject *, PyObject *args)
{
    const char *kindText = nullptr;
    unsigned long long address = 0;
    int width = 0;
    int height = 0;
    int threaded = 1;
    double dpr = 1.0;
    int timestamps = 0;
    if (!PyArg_ParseTuple(args, "s|Kiipdp", &kindText, &address, &width, &height, &threaded, &dpr, &timestamps))
        return nullptr;
    srpss_core::HostKind kind;
    if (!srpss_core::parseHostKind(kindText, &kind)) {
        PyErr_Format(PyExc_ValueError, "unknown host kind '%s' (the hosts are 'window' and 'hidden')", kindText);
        return nullptr;
    }
    QString error;
    std::shared_ptr<srpss_core::Host> host;
    if (kind == srpss_core::HostKind::Window) {
        if (address == 0) {
            PyErr_SetString(PyExc_ValueError, "no window: a window host hands over its QQuickWindow");
            return nullptr;
        }
        if (timestamps) {
            PyErr_SetString(PyExc_ValueError, "a window's QRhi timestamps are its own graphics configuration, set "
                                              "before it is first shown (QQuickGraphicsConfiguration.setTimestamps)");
            return nullptr;
        }
        QObject *object = reinterpret_cast<QObject *>(static_cast<quintptr>(address));
        std::unique_ptr<srpss_core::WindowHost> created = srpss_core::WindowHost::create(object, &error);
        if (!created) {
            PyErr_SetString(error.startsWith(QStringLiteral("a host hands over")) ? PyExc_TypeError
                                                                                    : PyExc_RuntimeError,
                            error.toUtf8().constData());
            return nullptr;
        }
        host = std::move(created);
    } else {
        if (address != 0) {
            PyErr_SetString(PyExc_ValueError, "a hidden host owns its window: pass no window, only a size");
            return nullptr;
        }
        if (width < 1 || height < 1) {
            PyErr_SetString(PyExc_ValueError, "a hidden host needs a width and a height");
            return nullptr;
        }
        std::unique_ptr<srpss_core::HiddenHost> created;
        Py_BEGIN_ALLOW_THREADS
        created = srpss_core::HiddenHost::create(width, height, threaded != 0, dpr, &error, timestamps != 0);
        Py_END_ALLOW_THREADS
        if (!created)
            return runtimeError(error);
        host = std::move(created);
    }
    const qint64 handle = hosts().next++;
    hosts().live.insert(handle, host);
    return PyLong_FromLongLong(handle);
}

PyObject *host_reattach(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = host->attach(&error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_detach(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS // the hidden host waits for its render thread
    ok = host->detach(&error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    return pyJson(host->stateJson());
}

PyObject *host_set_content(PyObject *, PyObject *args)
{
    long long handle = 0;
    unsigned long long address = 0;
    if (!PyArg_ParseTuple(args, "LK", &handle, &address))
        return nullptr;
    srpss_core::HiddenHost *host = hiddenOf(handle);
    if (!host)
        return nullptr;
    auto *item = qobject_cast<QQuickItem *>(reinterpret_cast<QObject *>(static_cast<quintptr>(address)));
    if (address != 0 && !item) {
        PyErr_SetString(PyExc_TypeError, "the content is a QQuickItem");
        return nullptr;
    }
    QString error;
    if (!host->setContent(item, &error))
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_frames(PyObject *, PyObject *args)
{
    long long handle = 0;
    int count = 1;
    if (!PyArg_ParseTuple(args, "L|i", &handle, &count))
        return nullptr;
    srpss_core::HiddenHost *host = hiddenOf(handle);
    if (!host)
        return nullptr;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = host->frames(count, &error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_invalidate_scene_graph(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::HiddenHost *host = hiddenOf(handle);
    if (!host)
        return nullptr;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = host->invalidateSceneGraph(&error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_set_dpr(PyObject *, PyObject *args)
{
    long long handle = 0;
    double dpr = 1.0;
    if (!PyArg_ParseTuple(args, "Ld", &handle, &dpr))
        return nullptr;
    srpss_core::HiddenHost *host = hiddenOf(handle);
    if (!host)
        return nullptr;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = host->setDevicePixelRatio(dpr, &error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_read(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::HiddenHost *host = hiddenOf(handle);
    if (!host)
        return nullptr;
    srpss_core::QuickReadback read;
    QString error;
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = host->readFrame(&read, &error);
    Py_END_ALLOW_THREADS
    if (!ok)
        return runtimeError(error);
    PyObject *d = PyDict_New();
    put(d, "rgba", PyBytes_FromStringAndSize(read.rgba.constData(), Py_ssize_t(read.rgba.size())));
    put(d, "width", PyLong_FromLong(read.width));
    put(d, "height", PyLong_FromLong(read.height));
    put(d, "y_up_in_framebuffer", PyBool_FromLong(read.yUpInFramebuffer ? 1 : 0));
    put(d, "frame", PyLong_FromLongLong(read.frame));
    put(d, "prime", pyStr(read.prime));
    return d;
}

PyObject *host_close(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    std::shared_ptr<srpss_core::Host> host = hosts().live.take(handle);
    if (!host) {
        PyErr_Format(PyExc_KeyError, "no host %lld (closed, or never created)", handle);
        return nullptr;
    }
    QJsonObject record;
    Py_BEGIN_ALLOW_THREADS
    if (auto *hidden = dynamic_cast<srpss_core::HiddenHost *>(host.get())) {
        record = hidden->close();
    } else if (host->attached()) {
        QString ignored;
        host->detach(&ignored);
    }
    record.insert(QStringLiteral("state"), host->stateJson());
    host.reset();
    Py_END_ALLOW_THREADS
    return pyJson(record);
}

PyObject *host_probe(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "L|s#", &handle, &config, &length))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QString error;
    if (length == 0) {
        if (!host->setProbe(nullptr, &error))
            return runtimeError(error);
        Py_RETURN_NONE;
    }
    srpss_core::ProbeConfig parsed;
    if (!srpss_core::ProbeConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (!host->setProbe(&parsed, &error))
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_probe_readback(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QString error;
    if (!host->requestReadback(&error))
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_probe_result(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QJsonObject facts;
    QByteArray rgba;
    int width = 0;
    int height = 0;
    qint64 frame = -1;
    if (!host->takeProbeResult(&facts, &rgba, &width, &height, &frame))
        Py_RETURN_NONE;
    PyObject *d = PyDict_New();
    put(d, "facts", pyJson(facts));
    put(d, "rgba", PyBytes_FromStringAndSize(rgba.constData(), Py_ssize_t(rgba.size())));
    put(d, "width", PyLong_FromLong(width));
    put(d, "height", PyLong_FromLong(height));
    put(d, "frame", PyLong_FromLongLong(frame));
    return d;
}

// ---------------------------------------------------------------- the GPU timer (N2.6) and its known-cost pass

PyObject *host_load(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "L|s#", &handle, &config, &length))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    QString error;
    if (length == 0) {
        if (!host->setLoad(nullptr, &error))
            return runtimeError(error);
        Py_RETURN_NONE;
    }
    srpss_core::LoadConfig parsed;
    if (!srpss_core::LoadConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (!host->setLoad(&parsed, &error))
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_gpu_timer(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &config, &length))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    srpss_core::GpuTimerConfig parsed;
    QString error;
    if (!srpss_core::GpuTimerConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (!host->setGpuTimer(parsed, &error))
        return runtimeError(error);
    Py_RETURN_NONE;
}

PyObject *host_gpu_samples(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::Host *host = hostOf(handle);
    if (!host)
        return nullptr;
    const QList<srpss_core::GpuTimingSample> samples = host->takeGpuSamples();
    PyObject *list = PyList_New(Py_ssize_t(samples.size()));
    if (!list)
        return nullptr;
    for (qsizetype i = 0; i < samples.size(); ++i) {
        const srpss_core::GpuTimingSample &s = samples.at(i);
        PyObject *row = Py_BuildValue("(iLLL)", s.kind, (long long)s.frame, (long long)s.readAt,
                                      (long long)s.nanoseconds);
        if (!row) {
            Py_DECREF(list);
            return nullptr;
        }
        PyList_SetItem(list, Py_ssize_t(i), row); // steals the reference
    }
    return list;
}

PyObject *gpu_timer_live(PyObject *, PyObject *)
{
    return pyJson(srpss_core::GpuTimer::liveJson());
}

PyObject *live_hosts(PyObject *, PyObject *)
{
    return PyLong_FromLongLong(hosts().live.size());
}

// ---------------------------------------------------------------- the composite (D5.2, N2.4)

struct Composites
{
    qint64 next = 1;
    QHash<qint64, QPointer<srpss_core::CompositeItem>> live;
};

Composites &composites()
{
    static Composites c;
    return c;
}

srpss_core::CompositeItem *compositeOf(long long handle)
{
    if (!composites().live.contains(handle)) {
        PyErr_Format(PyExc_KeyError, "no composite %lld (destroyed, or never created)", handle);
        return nullptr;
    }
    srpss_core::CompositeItem *item = composites().live.value(handle).data();
    if (!item)
        PyErr_Format(PyExc_RuntimeError, "composite %lld was deleted with its parent item", handle);
    return item;
}

PyObject *composite_create(PyObject *, PyObject *args)
{
    unsigned long long address = 0;
    if (!PyArg_ParseTuple(args, "K", &address))
        return nullptr;
    auto *parent = qobject_cast<QQuickItem *>(reinterpret_cast<QObject *>(static_cast<quintptr>(address)));
    if (!address || !parent) {
        PyErr_SetString(PyExc_TypeError, "a composite is placed in a QQuickItem: pass its address");
        return nullptr;
    }
    auto *item = new srpss_core::CompositeItem(parent); // owned by its parent item (QObject parent) and deletable here
    const qint64 handle = composites().next++;
    composites().live.insert(handle, QPointer<srpss_core::CompositeItem>(item));
    return PyLong_FromLongLong(handle);
}

PyObject *composite_set(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &config, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::CompositeConfig updated = item->config();
    QString error;
    if (!srpss_core::CompositeConfig::update(QByteArray(config, qsizetype(length)), &updated, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    item->apply(updated);
    Py_RETURN_NONE;
}

PyObject *composite_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    return pyJson(item->stateJson());
}

PyObject *composite_destroy(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    if (!composites().live.contains(handle)) {
        PyErr_Format(PyExc_KeyError, "no composite %lld (destroyed, or never created)", handle);
        return nullptr;
    }
    QPointer<srpss_core::CompositeItem> item = composites().live.take(handle);
    const bool deleted = !item.isNull();
    delete item.data(); // GUI thread: Qt Quick releases its node on the render thread at the next sync
    return PyBool_FromLong(deleted ? 1 : 0);
}

PyObject *composite_live(PyObject *, PyObject *)
{
    QJsonObject o;
    o.insert(QStringLiteral("items"), srpss_core::CompositeItem::liveItems());
    o.insert(QStringLiteral("surfaces"), srpss_core::Surface::liveSurfaces());
    o.insert(QStringLiteral("surface_resources"), srpss_core::Surface::liveResourcesTotal());
    o.insert(QStringLiteral("handles"), int(composites().live.size()));
    o.insert(QStringLiteral("spectrum_sources"), srpss_core::SpectrumSource::liveSources());
    o.insert(QStringLiteral("spectrum_resources"), srpss_core::spectrumContentObjects());
    o.insert(QStringLiteral("mode_sources"), srpss_core::ModeSource::liveSources());
    o.insert(QStringLiteral("mode_resources"), srpss_core::modeContentObjects());
    // N4.a: the items' textures (QRhiTextures and their bytes), the core's copies not yet uploaded, the uploads done.
    const srpss_core::ModeTextureCounts textures = srpss_core::modeTextureCounts();
    o.insert(QStringLiteral("mode_textures"), textures.textures);
    o.insert(QStringLiteral("mode_texture_bytes"), double(textures.textureBytes));
    o.insert(QStringLiteral("mode_texture_images"), textures.images);
    o.insert(QStringLiteral("mode_texture_image_bytes"), double(textures.imageBytes));
    o.insert(QStringLiteral("mode_texture_uploads"), double(textures.uploads));
    // N5.7b: the backdrop items, their pyramids and the pyramids' QRhi objects, and the builds recorded.
    const srpss_core::BackdropCounts backdrops = srpss_core::backdropCounts();
    o.insert(QStringLiteral("backdrop_items"), backdrops.items);
    o.insert(QStringLiteral("backdrop_pyramids"), backdrops.pyramids);
    o.insert(QStringLiteral("backdrop_resources"), backdrops.resources);
    o.insert(QStringLiteral("backdrop_builds"), double(backdrops.builds));
    // N3.1: the scene targets holding objects, their textures and bytes (every sample), the allocations and steps made,
    // and the harness's readbacks QRhi has not completed.
    const srpss_core::SceneTargetCounts scenes = srpss_core::sceneTargetCounts();
    o.insert(QStringLiteral("scene_targets"), scenes.targets);
    o.insert(QStringLiteral("scene_target_textures"), scenes.textures);
    o.insert(QStringLiteral("scene_target_bytes"), double(scenes.bytes));
    o.insert(QStringLiteral("scene_target_allocations"), double(scenes.allocations));
    o.insert(QStringLiteral("scene_target_steps"), double(scenes.steps));
    o.insert(QStringLiteral("scene_target_readbacks"), scenes.readbacksPending);
    o.insert(QStringLiteral("scene_target_depth_primes"), double(scenes.depthPrimes));
    o.insert(QStringLiteral("scene_target_resolve_primes"), double(scenes.resolvePrimes));
    o.insert(QStringLiteral("scene_target_nearest_resolves"), double(scenes.nearestResolves));
    // N3.2 (D15): the meshes (resident buffers, bytes, the core's copies, uploads), the streams and arenas (buffers,
    // bytes, writes), every buffer created (the no-allocation proof), and the indirect and batched draws recorded.
    const srpss_core::MeshBufferCounts mb = srpss_core::meshBufferCounts();
    o.insert(QStringLiteral("mesh_buffers_meshes"), mb.meshes);
    o.insert(QStringLiteral("mesh_buffers_mesh_bytes"), double(mb.meshBytes));
    o.insert(QStringLiteral("mesh_buffers_mesh_images"), mb.meshImages);
    o.insert(QStringLiteral("mesh_buffers_mesh_image_bytes"), double(mb.meshImageBytes));
    o.insert(QStringLiteral("mesh_buffers_mesh_uploads"), double(mb.meshUploads));
    o.insert(QStringLiteral("mesh_buffers_streams"), mb.streams);
    o.insert(QStringLiteral("mesh_buffers_stream_bytes"), double(mb.streamBytes));
    o.insert(QStringLiteral("mesh_buffers_stream_writes"), double(mb.streamWrites));
    o.insert(QStringLiteral("mesh_buffers_stream_bytes_written"), double(mb.streamBytesWritten));
    o.insert(QStringLiteral("mesh_buffers_arenas"), mb.arenas);
    o.insert(QStringLiteral("mesh_buffers_arena_bytes"), double(mb.arenaBytes));
    o.insert(QStringLiteral("mesh_buffers_arena_writes"), double(mb.arenaWrites));
    o.insert(QStringLiteral("mesh_buffers_buffers_created"), double(mb.buffersCreated));
    o.insert(QStringLiteral("mesh_buffers_indirect_draws"), double(mb.indirectDraws));
    o.insert(QStringLiteral("mesh_buffers_batched_indirect"), double(mb.batchedIndirect));
    o.insert(QStringLiteral("mesh_buffers_batched_loop"), double(mb.batchedLoop));
    o.insert(QStringLiteral("mesh_buffers_records_timed"), double(mb.recordsTimed));
    o.insert(QStringLiteral("mesh_buffers_record_ns"), double(mb.recordNs));
    o.insert(QStringLiteral("mesh_buffers_stream_write_ns"), double(mb.streamWriteNs));
    o.insert(QStringLiteral("mesh_buffers_draws_refused"), double(mb.drawsRefused)); // audit 4 H2, M1
    // N3.3 (D16): the storage (resident buffers and images, bytes), the dispatches and compute passes recorded, the
    // entries a drawn record did not dispatch, the edge kernels, every object created (flat at rest), the states found
    // lost and the harness's readbacks in flight.
    const srpss_core::ComputeCounts cc = srpss_core::computeCounts();
    o.insert(QStringLiteral("compute_buffers"), cc.buffers);
    o.insert(QStringLiteral("compute_buffer_bytes"), double(cc.bufferBytes));
    o.insert(QStringLiteral("compute_images"), cc.images);
    o.insert(QStringLiteral("compute_image_bytes"), double(cc.imageBytes));
    o.insert(QStringLiteral("compute_dispatches"), double(cc.dispatches));
    o.insert(QStringLiteral("compute_passes"), double(cc.computePasses));
    o.insert(QStringLiteral("compute_skipped"), double(cc.skipped));
    o.insert(QStringLiteral("compute_clears"), double(cc.clears));
    o.insert(QStringLiteral("compute_copies"), double(cc.copies));
    o.insert(QStringLiteral("compute_image_zero_uploads"), double(cc.imageZeroUploads));
    o.insert(QStringLiteral("compute_objects_created"), double(cc.objectsCreated));
    o.insert(QStringLiteral("compute_states_lost"), double(cc.statesLost));
    o.insert(QStringLiteral("compute_readbacks"), cc.readbacksPending);
    // N3.4 (D17): the stages' objects (bloom chains, defocus read levels, their textures, bytes and pipelines), every
    // object a stage made (flat at rest), the records of each stage, the generated mips, the transparency fallbacks
    // noted and what the skipped-release control left behind.
    const srpss_core::StageCounts sc = srpss_core::stageCounts();
    o.insert(QStringLiteral("stage_bloom_chains"), sc.bloomChains);
    o.insert(QStringLiteral("stage_defocus_steps"), sc.defocusSteps);
    o.insert(QStringLiteral("stage_textures"), sc.textures);
    o.insert(QStringLiteral("stage_bytes"), double(sc.bytes));
    o.insert(QStringLiteral("stage_pipelines"), sc.pipelines);
    o.insert(QStringLiteral("stage_build_failures"), double(sc.buildFailures));
    o.insert(QStringLiteral("stage_rebind_failures"), double(sc.rebindFailures));
    o.insert(QStringLiteral("stage_objects_created"), double(sc.objectsCreated));
    o.insert(QStringLiteral("stage_bloom_records"), double(sc.bloomRecords));
    o.insert(QStringLiteral("stage_defocus_records"), double(sc.defocusRecords));
    o.insert(QStringLiteral("stage_transparency_resolves"), double(sc.transparencyResolves));
    o.insert(QStringLiteral("stage_generated_mips"), double(sc.generatedMips));
    o.insert(QStringLiteral("stage_fallbacks"), double(sc.fallbacks));
    o.insert(QStringLiteral("stage_left_behind"), sc.leftBehind);
    o.insert(QStringLiteral("stage_records_timed"), double(sc.recordsTimed));
    o.insert(QStringLiteral("stage_record_ns"), double(sc.recordNs));
    o.insert(QStringLiteral("stage_defocus_timed"), double(sc.defocusTimed));
    o.insert(QStringLiteral("stage_gather_gpu_ns"), double(sc.gatherGpuNs));
    o.insert(QStringLiteral("stage_sprites_gpu_ns"), double(sc.spritesGpuNs));
    o.insert(QStringLiteral("stage_defocus_time_skipped"), double(sc.defocusTimeSkipped));
    o.insert(QStringLiteral("stage_defocus_flushes"), double(sc.defocusFlushes));
    return pyJson(o);
}

// ---------------------------------------------------------------- Spectrum on a composite (N2.5)

PyObject *composite_spectrum_bind(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls|s#", &handle, &name, &config, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::PacketReaderConfig parsed;
    QString error;
    if (length && !srpss_core::PacketReaderConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (!item->bindSpectrum(QString::fromUtf8(name), parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_spectrum_unbind(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    item->unbindSpectrum();
    Py_RETURN_NONE;
}

PyObject *composite_spectrum_present(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &config, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::SpectrumPresentation presentation;
    QString error;
    if (!srpss_core::SpectrumPresentation::fromJson(QByteArray(config, qsizetype(length)), &presentation, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (!item->presentSpectrum(presentation, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_window_pixels(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    const QSize pixels = item->windowPixels();
    if (!pixels.isValid())
        Py_RETURN_NONE;
    return Py_BuildValue("(ii)", pixels.width(), pixels.height());
}

// The pack argument: bytes (a .qsb tools/regen_qrc.py --shaders baked) or None (the module's compiled-in copy, the
// harness's negative control only).
bool packArgument(PyObject *object, QByteArray *out)
{
    if (object == Py_None) {
        out->clear();
        return true;
    }
    if (!PyBytes_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "a shader pack is bytes (a .qsb) or None");
        return false;
    }
    // The limited API's function forms (the module builds against it: no PyBytes_AS_STRING / PyBytes_GET_SIZE).
    const char *data = PyBytes_AsString(object);
    const Py_ssize_t size = PyBytes_Size(object);
    if (!data || size < 0)
        return false;                         // the error is set
    *out = QByteArray(data, qsizetype(size));
    return true;
}

bool settingsArgument(const char *json, Py_ssize_t length, QJsonObject *out)
{
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(QByteArray(json, qsizetype(length)), &parse);
    if (parse.error != QJsonParseError::NoError || !document.isObject()) {
        PyErr_SetString(PyExc_ValueError, "the settings are a JSON object of name -> number or list of numbers");
        return false;
    }
    *out = document.object();
    return true;
}

PyObject *composite_spectrum_program(PyObject *, PyObject *args)
{
    long long handle = 0;
    PyObject *pack = nullptr;
    if (!PyArg_ParseTuple(args, "LO", &handle, &pack))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    QByteArray qsb;
    if (!item || !packArgument(pack, &qsb))
        return nullptr;
    QString error;
    if (!item->programSpectrum(qsb, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_spectrum_settings(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &json, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    QJsonObject settings;
    if (!item || !settingsArgument(json, length, &settings))
        return nullptr;
    QString error;
    if (!item->settingsSpectrum(settings, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

srpss_core::SpectrumSource *spectrumOf(long long handle)
{
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::SpectrumSource *source = item->spectrum();
    if (!source)
        PyErr_Format(PyExc_RuntimeError, "composite %lld has no Spectrum bound", handle);
    return source;
}

PyObject *composite_spectrum_drop(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
    source->dropRetainedFrame();
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

PyObject *composite_update(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    item->update();
    Py_RETURN_NONE;
}

PyObject *slotHeadDict(const srpss_core::SlotHead &head);

PyObject *composite_spectrum_head(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
    srpss_core::SlotHead head;
    if (!source->readHead(&head))
        Py_RETURN_NONE;
    return slotHeadDict(head);
}

PyObject *composite_spectrum_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
    return pyJson(source->stateJson());
}

PyObject *composite_spectrum_wait_paused(PyObject *, PyObject *args)
{
    long long handle = 0;
    int timeoutMs = 0;
    if (!PyArg_ParseTuple(args, "Li", &handle, &timeoutMs))
        return nullptr;
    if (!spectrumOf(handle))
        return nullptr;
    // A shared owner for the wait (audit N29 L8): a composite destroyed from another thread meanwhile cannot free the
    // source under it; its last owner may then be this thread, where no read is in progress.
    std::shared_ptr<srpss_core::SpectrumSource> source = compositeOf(handle)->spectrumShared();
    bool paused = false;
    Py_BEGIN_ALLOW_THREADS
    paused = source->waitPaused(timeoutMs);
    Py_END_ALLOW_THREADS
    return PyBool_FromLong(paused ? 1 : 0);
}

PyObject *composite_spectrum_retire(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
    source->retireCurrent(); // any thread, never waits (D1)
    Py_RETURN_NONE;
}

PyObject *composite_spectrum_resume(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
    source->resume();
    Py_RETURN_NONE;
}

PyObject *spectrum_block(PyObject *, PyObject *args)
{
    const char *record = nullptr;
    Py_ssize_t recordLength = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    PyObject *pack = nullptr;
    const char *settingsJson = "";
    Py_ssize_t settingsLength = 0;
    if (!PyArg_ParseTuple(args, "y#s#Os#", &record, &recordLength, &config, &length, &pack, &settingsJson,
                          &settingsLength))
        return nullptr;
    srpss_core::SpectrumPresentation presentation;
    QString error;
    if (!srpss_core::SpectrumPresentation::fromJson(QByteArray(config, qsizetype(length)), &presentation, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    QByteArray qsb;
    QJsonObject settings;
    if (!packArgument(pack, &qsb) || !settingsArgument(settingsJson, settingsLength, &settings))
        return nullptr;
    srpss_core::SpectrumProgram program;
    if (!srpss_core::SpectrumProgram::fromPack(qsb, &program, &error) || !program.setSettings(settings, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    QByteArray block;
    QJsonObject facts;
    QString reason;
    const bool drawn = srpss_core::spectrumBlock(QByteArray(record, qsizetype(recordLength)), presentation, program,
                                                 &block, &facts, &reason);
    facts.insert(QStringLiteral("reason"), reason);
    PyObject *bytes = nullptr;
    if (drawn) {
        bytes = PyBytes_FromStringAndSize(block.constData(), Py_ssize_t(block.size()));
    } else {
        Py_INCREF(Py_None);
        bytes = Py_None;
    }
    PyObject *result = Py_BuildValue("(NN)", bytes, pyJson(facts));
    return result;
}

PyObject *spectrum_block_layout(PyObject *, PyObject *args)
{
    PyObject *pack = Py_None;
    if (!PyArg_ParseTuple(args, "|O", &pack))
        return nullptr;
    QByteArray qsb;
    if (!packArgument(pack, &qsb))
        return nullptr;
    srpss_core::SpectrumProgram program;
    QString error;
    if (!srpss_core::SpectrumProgram::fromPack(qsb, &program, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    QJsonObject layout = program.layout.toJson();
    QJsonArray frame;
    for (const char *const *name = srpss_core::kSpectrumFrameMembers; *name; ++name)
        frame.append(QString::fromLatin1(*name));
    layout.insert(QStringLiteral("frame_members"), frame);
    return pyJson(layout);
}

// ---------------------------------------------------------------- generic mode content (N2.9)

// The passes' fragment packs: a sequence of bytes, one per declared pass, in order.
bool packsArgument(PyObject *object, QList<QByteArray> *out)
{
    out->clear();
    if (!PySequence_Check(object) || PyBytes_Check(object)) {
        PyErr_SetString(PyExc_TypeError, "the packs are a sequence of bytes (one .qsb per pass, in order)");
        return false;
    }
    const Py_ssize_t count = PySequence_Size(object);
    if (count < 0)
        return false;
    for (Py_ssize_t i = 0; i < count; ++i) {
        PyObject *item = PySequence_GetItem(object, i); // a new reference
        if (!item)
            return false;
        if (!PyBytes_Check(item)) {
            Py_DECREF(item);
            PyErr_SetString(PyExc_TypeError, "each pack is bytes (a .qsb)");
            return false;
        }
        const char *data = PyBytes_AsString(item);
        const Py_ssize_t size = PyBytes_Size(item);
        if (!data || size < 0) {
            Py_DECREF(item);
            return false;
        }
        out->append(QByteArray(data, qsizetype(size)));
        Py_DECREF(item);
    }
    return true;
}

bool programArgument(const char *json, Py_ssize_t length, PyObject *packs, srpss_core::ModeProgram *out)
{
    QList<QByteArray> bytes;
    if (!packsArgument(packs, &bytes))
        return false;
    QString error;
    if (!srpss_core::ModeProgram::fromJson(QByteArray(json, qsizetype(length)), bytes, out, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return false;
    }
    return true;
}

QSharedPointer<const srpss_core::RuntimeSchema> schemaArgument(const char *json, Py_ssize_t length)
{
    QString error;
    QSharedPointer<const srpss_core::RuntimeSchema> schema =
        srpss_core::RuntimeSchema::fromJson(QByteArray(json, qsizetype(length)), &error);
    if (!schema)
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
    return schema;
}

srpss_core::ModeSource *modeOf(long long handle)
{
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::ModeSource *source = item->mode();
    if (!source)
        PyErr_Format(PyExc_RuntimeError, "composite %lld draws no generic mode", handle);
    return source;
}

PyObject *composite_mode_bind(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    const char *schemaJson = "";
    Py_ssize_t schemaLength = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Lss#|s#", &handle, &name, &schemaJson, &schemaLength, &config, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    srpss_core::PacketReaderConfig parsed;
    QString error;
    if (length && !srpss_core::PacketReaderConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    parsed.runtimeSchema = schemaArgument(schemaJson, schemaLength);
    if (!parsed.runtimeSchema)
        return nullptr;
    if (!item->bindMode(QString::fromUtf8(name), parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

bool cardArgument(const char *json, Py_ssize_t length, srpss_core::ModeCard *out)
{
    QString error;
    if (!srpss_core::ModeCard::fromJson(QByteArray(json, qsizetype(length)), out, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return false;
    }
    return true;
}

PyObject *composite_mode_card(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &json, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    srpss_core::ModeCard card;
    if (!item || !cardArgument(json, length, &card))
        return nullptr;
    QString error;
    if (!item->cardMode(card, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

// N4.a: an item's texture from pixels Python holds (RGBA8, rows top first, tight); copied once into the core.
PyObject *composite_mode_texture(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    int width = 0;
    int height = 0;
    PyObject *pixels = nullptr;
    int mips = 0;
    int inFrame = 0; // N3.8, a harness control: the in-frame form where the device has a job service
    if (!PyArg_ParseTuple(args, "Ls(ii)O|pp", &handle, &name, &width, &height, &pixels, &mips, &inFrame))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    if (!PyBytes_Check(pixels)) {
        PyErr_SetString(PyExc_TypeError, "a texture's pixels are bytes (RGBA8, rows top first, tight)");
        return nullptr;
    }
    const char *data = PyBytes_AsString(pixels);
    const Py_ssize_t size = PyBytes_Size(pixels);
    if (!data || size < 0)
        return nullptr;
    QString error;
    if (!item->textureMode(QByteArray(name), QByteArray(data, qsizetype(size)), QSize(width, height), mips != 0,
                           &error, inFrame != 0)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

// N3.8: the owner's side of the lost edge, a Python callable called on the GUI thread with the lost names. Held, called
// and released on the GUI thread only (ItemNotifier), each time with the GIL taken there; never on the render or the job
// thread (D5.4).
class PyTexturesLostListener final : public srpss_core::TexturesLostListener
{
public:
    explicit PyTexturesLostListener(PyObject *callable) : m_callable(callable) { Py_INCREF(m_callable); }
    ~PyTexturesLostListener() override
    {
        if (!Py_IsInitialized())
            return; // the interpreter went first: nothing of it may be touched
        const PyGILState_STATE state = PyGILState_Ensure();
        Py_DECREF(m_callable);
        PyGILState_Release(state);
    }
    void texturesLost(const QStringList &names) override
    {
        if (!Py_IsInitialized())
            return;
        const PyGILState_STATE state = PyGILState_Ensure();
        PyObject *list = PyList_New(Py_ssize_t(names.size()));
        if (list) {
            for (qsizetype i = 0; i < names.size(); ++i)
                PyList_SetItem(list, Py_ssize_t(i), pyStr(names.at(i)));
            PyObject *result = PyObject_CallFunctionObjArgs(m_callable, list, nullptr);
            if (!result)
                PyErr_WriteUnraisable(m_callable); // an owner's error never escapes into Qt's event loop
            else
                Py_DECREF(result);
            Py_DECREF(list);
        } else {
            PyErr_Clear();
        }
        PyGILState_Release(state);
    }

private:
    PyObject *m_callable;
};

PyObject *composite_mode_on_lost(PyObject *, PyObject *args)
{
    long long handle = 0;
    PyObject *callable = nullptr;
    if (!PyArg_ParseTuple(args, "LO", &handle, &callable))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    if (callable != Py_None && !PyCallable_Check(callable)) {
        PyErr_SetString(PyExc_TypeError, "the lost-texture listener is a callable taking the list of names, or None");
        return nullptr;
    }
    std::shared_ptr<srpss_core::TexturesLostListener> listener;
    if (callable != Py_None)
        listener = std::make_shared<PyTexturesLostListener>(callable);
    QString error;
    if (!item->texturesLostListener(listener, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

// ---------------------------------------------------------------- the job service (N3.8, D9)

QJsonObject jobCountsObject()
{
    QJsonObject o = srpss_core::jobCountsJson();
    o.insert(QStringLiteral("job_images_retiring"), srpss_core::WindowSurfaces::retiringTotal());
    o.insert(QStringLiteral("job_images_left_to_services"), double(srpss_core::WindowSurfaces::leftToServicesTotal()));
    return o;
}

// Audit N38 M1, GPU-free: a window's frame count with two drivers' edges in one frame (a second host on the window, or
// one detached and not yet released), as WindowSurfaces counts them: frame 1 (two edges), frame 2 (two edges).
PyObject *window_edges_self_test(PyObject *, PyObject *)
{
    srpss_core::WindowSurfaces surfaces;
    QJsonArray edges;
    edges.append(double(surfaces.noteEdge())); // frame 1, the first driver
    edges.append(double(surfaces.noteEdge())); // frame 1, the second driver
    surfaces.frameRendered();                  // the window's afterRendering
    edges.append(double(surfaces.noteEdge())); // frame 2
    edges.append(double(surfaces.noteEdge()));
    surfaces.frameRendered();
    QJsonObject o;
    o.insert(QStringLiteral("edges"), edges);
    o.insert(QStringLiteral("total"), double(surfaces.edges()));
    return pyJson(o);
}

PyObject *job_counts(PyObject *, PyObject *)
{
    return pyJson(jobCountsObject());
}

// R-223, GPU-free: the GPU timer's ring over `frames` edges whose results arrive `lag` edges late (< 0: never), with or
// without abandoning a slot unread for longer than the ring.
PyObject *gpu_timer_ring_simulation(PyObject *, PyObject *args)
{
    int ring = 0, frames = 0, lag = 0, abandon = 1;
    if (!PyArg_ParseTuple(args, "iiip", &ring, &frames, &lag, &abandon))
        return nullptr;
    const srpss_core::GpuRingSimulation s = srpss_core::simulateGpuRing(ring, frames, lag, abandon != 0);
    QJsonObject o;
    o.insert(QStringLiteral("timed"), s.timed);
    o.insert(QStringLiteral("results"), s.results);
    o.insert(QStringLiteral("busy"), s.busy);
    o.insert(QStringLiteral("abandoned"), s.abandoned);
    o.insert(QStringLiteral("ring_frames"), srpss_core::GpuTimer::kRingFrames);
    return pyJson(o);
}

PyObject *job_services_state(PyObject *, PyObject *args)
{
    int withLog = 0;
    if (!PyArg_ParseTuple(args, "|p", &withLog))
        return nullptr;
    QJsonObject o;
    o.insert(QStringLiteral("services"), srpss_core::JobService::allStatesJson(withLog != 0));
    o.insert(QStringLiteral("counts"), jobCountsObject());
    return pyJson(o);
}

PyObject *job_services_wait_idle(PyObject *, PyObject *args)
{
    int timeoutMs = 5000;
    if (!PyArg_ParseTuple(args, "|i", &timeoutMs))
        return nullptr;
    bool idle = false;
    Py_BEGIN_ALLOW_THREADS
    idle = srpss_core::JobService::waitAllIdle(qMax(0, timeoutMs));
    Py_END_ALLOW_THREADS
    return PyBool_FromLong(idle ? 1 : 0);
}

PyObject *job_service_self_test(PyObject *, PyObject *args)
{
    const char *script = nullptr;
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "s#", &script, &length))
        return nullptr;
    const QByteArray scriptJson(script, qsizetype(length));
    QByteArray result;
    Py_BEGIN_ALLOW_THREADS
    result = srpss_core::jobServiceSelfTestJson(scriptJson);
    Py_END_ALLOW_THREADS
    return pyJson(result);
}

PyObject *composite_mode_texture_remove(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    if (!PyArg_ParseTuple(args, "Ls", &handle, &name))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    QString error;
    if (!item->removeTextureMode(QByteArray(name), &error)) {
        PyErr_SetString(PyExc_KeyError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

bool intsArgument(PyObject *object, QList<int> *out, const char *what); // defined below

// N3.2 (D15 point 2): an item's mesh from bytes Python holds (interleaved f32 records); copied once into the core.
PyObject *composite_mode_mesh(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    const char *declaration = "";
    Py_ssize_t declarationLength = 0;
    PyObject *vertices = nullptr;
    PyObject *instances = nullptr;
    if (!PyArg_ParseTuple(args, "Lss#O|O", &handle, &name, &declaration, &declarationLength, &vertices, &instances))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    if (!PyBytes_Check(vertices) || (instances && instances != Py_None && !PyBytes_Check(instances))) {
        PyErr_SetString(PyExc_TypeError, "a mesh's vertices (and instances) are bytes (interleaved f32 records)");
        return nullptr;
    }
    const QByteArray v(PyBytes_AsString(vertices), qsizetype(PyBytes_Size(vertices)));
    const QByteArray i = (instances && instances != Py_None)
        ? QByteArray(PyBytes_AsString(instances), qsizetype(PyBytes_Size(instances)))
        : QByteArray();
    QString error;
    if (!item->meshMode(QByteArray(name), QByteArray(declaration, qsizetype(declarationLength)), v, i, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_mode_mesh_remove(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    if (!PyArg_ParseTuple(args, "Ls", &handle, &name))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    QString error;
    if (!item->removeMeshMode(QByteArray(name), &error)) {
        PyErr_SetString(PyExc_KeyError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

// N3.2, harness: the proofs' negative controls (mesh_buffers.h), each process-wide; a key left out keeps its value.
PyObject *mesh_buffer_control(PyObject *, PyObject *args)
{
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "s#", &json, &length))
        return nullptr;
    const QJsonObject o = QJsonDocument::fromJson(QByteArray(json, qsizetype(length))).object();
    static const QStringList keys = { QStringLiteral("hide_draw_parameters"), QStringLiteral("direct_first_instance"),
                                      QStringLiteral("recreate_streams"), QStringLiteral("skip_mesh_release"),
                                      QStringLiteral("instances_past_used") };
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!keys.contains(it.key())) {
            PyErr_Format(PyExc_ValueError, "unknown control '%s' (%s)", it.key().toUtf8().constData(),
                         keys.join(QStringLiteral(", ")).toUtf8().constData());
            return nullptr;
        }
    }
    if (o.contains(QStringLiteral("hide_draw_parameters")))
        srpss_core::setHideDrawParameters(o.value(QStringLiteral("hide_draw_parameters")).toBool());
    if (o.contains(QStringLiteral("direct_first_instance")))
        srpss_core::setDirectFirstInstance(quint32(qMax(0, o.value(QStringLiteral("direct_first_instance")).toInt())));
    if (o.contains(QStringLiteral("recreate_streams")))
        srpss_core::setRecreateStreams(o.value(QStringLiteral("recreate_streams")).toBool());
    if (o.contains(QStringLiteral("skip_mesh_release")))
        srpss_core::setSkipMeshRelease(o.value(QStringLiteral("skip_mesh_release")).toBool());
    if (o.contains(QStringLiteral("instances_past_used")))
        srpss_core::setInstancesPastUsed(o.value(QStringLiteral("instances_past_used")).toBool());
    Py_RETURN_NONE;
}

// GPU-free: D15 point 3's arena layout (offsets, size) for block sizes at an alignment.
PyObject *mesh_buffer_arena_layout(PyObject *, PyObject *args)
{
    PyObject *sizes = nullptr;
    int alignment = 1;
    if (!PyArg_ParseTuple(args, "Oi", &sizes, &alignment))
        return nullptr;
    QList<int> values;
    if (!intsArgument(sizes, &values, "the block sizes"))
        return nullptr;
    QList<quint32> list;
    for (const int v : values)
        list.append(quint32(qMax(0, v)));
    const srpss_core::ArenaLayout layout = srpss_core::arenaLayout(list, alignment);
    PyObject *offsets = PyList_New(Py_ssize_t(layout.offsets.size()));
    if (!offsets)
        return nullptr;
    for (qsizetype k = 0; k < layout.offsets.size(); ++k)
        PyList_SetItem(offsets, Py_ssize_t(k), PyLong_FromUnsignedLong(layout.offsets.at(k)));
    return Py_BuildValue("(Nk)", offsets, (unsigned long)layout.size);
}

// N3.2: a device's facts (the core's Vulkan device's limits and draw features), by its VkDevice handle.
PyObject *vulkan_device_facts(PyObject *, PyObject *args)
{
    unsigned long long device = 0;
    if (!PyArg_ParseTuple(args, "K", &device))
        return nullptr;
    return pyJson(srpss_core::vulkanDeviceFacts(quint64(device)));
}

PyObject *mode_core_members(PyObject *, PyObject *)
{
    QJsonArray rows;
    for (int i = 0; i < srpss_core::kModeCoreMemberCount; ++i) {
        const srpss_core::ModeCoreMember &member = srpss_core::kModeCoreMembers[i];
        rows.append(QJsonArray { QLatin1String(member.name), member.components, member.fromCard });
    }
    QJsonObject o;
    o.insert(QStringLiteral("members"), rows);
    return pyJson(o);
}

PyObject *mode_core_values(PyObject *, PyObject *args)
{
    const char *name = nullptr;
    const char *cardJson = nullptr;
    Py_ssize_t cardLength = 0;
    int targetWidth = 0;
    int targetHeight = 0;
    if (!PyArg_ParseTuple(args, "ss#(ii)", &name, &cardJson, &cardLength, &targetWidth, &targetHeight))
        return nullptr;
    srpss_core::ModeCard card;
    if (!cardArgument(cardJson, cardLength, &card))
        return nullptr;
    double values[16];
    int count = 0;
    if (!srpss_core::modeCoreValues(QByteArray(name), card, QSize(targetWidth, targetHeight), values, &count)) {
        PyErr_Format(PyExc_KeyError, "'%s' is not a core member the core fills", name);
        return nullptr;
    }
    PyObject *list = PyList_New(count);
    if (!list)
        return nullptr;
    for (int i = 0; i < count; ++i)
        PyList_SetItem(list, i, PyFloat_FromDouble(values[i]));
    return list;
}

PyObject *composite_content_status(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    const srpss_core::StreamSource *source = item->spectrum();
    if (!source)
        source = item->mode();
    if (!source)
        Py_RETURN_NONE;
    const srpss_core::ContentStatus s = source->status();
    return Py_BuildValue("(LLLO)", (long long)s.draws, (long long)s.failures, (long long)s.refusedRun,
                         s.failing ? Py_True : Py_False);
}

PyObject *composite_mode_unbind(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    item->unbindMode();
    Py_RETURN_NONE;
}

PyObject *composite_mode_program(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *json = "";
    Py_ssize_t length = 0;
    PyObject *packs = nullptr;
    const char *settingsJson = nullptr;
    Py_ssize_t settingsLength = 0;
    if (!PyArg_ParseTuple(args, "Ls#O|z#", &handle, &json, &length, &packs, &settingsJson, &settingsLength))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    srpss_core::ModeProgram program;
    if (!item || !programArgument(json, length, packs, &program))
        return nullptr;
    QJsonObject settings;
    if (settingsJson && !settingsArgument(settingsJson, settingsLength, &settings))
        return nullptr;
    QString error;
    if (!item->programMode(program, settingsJson ? &settings : nullptr, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_mode_settings(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &json, &length))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    QJsonObject settings;
    if (!item || !settingsArgument(json, length, &settings))
        return nullptr;
    QString error;
    if (!item->settingsMode(settings, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *composite_mode_drop(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    source->dropRetainedFrame();
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

PyObject *composite_mode_head(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    srpss_core::SlotHead head;
    if (!source->readHead(&head))
        Py_RETURN_NONE;
    return slotHeadDict(head);
}

PyObject *composite_mode_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    return pyJson(source->stateJson());
}

PyObject *composite_mode_retire(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    source->retireCurrent();
    // Audit N38 L4: the owner's lost-texture listener goes with its retire (GUI thread), so no lost edge reaches a
    // retired owner and the core holds no reference to it until the item's deletion.
    source->notifier()->setListener(nullptr);
    Py_RETURN_NONE;
}

// N5.7a: the generic mode drawn as a still (no stream; mode_content.h "Stills"): the background layer's photo.
PyObject *composite_mode_still(PyObject *, PyObject *args)
{
    long long handle = 0;
    int still = 0;
    if (!PyArg_ParseTuple(args, "Lp", &handle, &still))
        return nullptr;
    srpss_core::CompositeItem *item = compositeOf(handle);
    if (!item)
        return nullptr;
    QString error;
    if (!item->stillMode(still != 0, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

// ---------------------------------------------------------------- scene targets (N3.1, D14)

// An explicit-size target's size, with no new program (the allocation follows at the next record).
PyObject *composite_mode_target_size(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    int width = 0;
    int height = 0;
    if (!PyArg_ParseTuple(args, "Ls(ii)", &handle, &name, &width, &height))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    QString error;
    if (!source->setTargetSize(QByteArray(name), QSize(width, height), &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

// Harness: a readback of every scene target's readable texture at the next record.
PyObject *composite_mode_target_read(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    source->requestTargetRead();
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

// Harness: the readback's pixels once QRhi completed it (None before), each {"name", "size", "content", "format",
// "samples", "level", "data"} (rows in the texture's memory order: the image's top first).
PyObject *composite_mode_target_pixels(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    QList<srpss_core::SceneTargetPixels> pixels;
    if (!source->takeTargetPixels(&pixels))
        Py_RETURN_NONE;
    PyObject *list = PyList_New(0);
    if (!list)
        return nullptr;
    for (const srpss_core::SceneTargetPixels &p : pixels) {
        PyObject *d = PyDict_New();
        if (!d) {
            Py_DECREF(list);
            return nullptr;
        }
        put(d, "name", pyStr(p.name));
        put(d, "size", Py_BuildValue("(ii)", p.size.width(), p.size.height()));
        put(d, "content", Py_BuildValue("(ii)", p.content.width(), p.content.height()));
        put(d, "format", pyStr(p.format));
        put(d, "samples", PyLong_FromLong(p.samples));
        put(d, "level", PyLong_FromLong(p.level)); // N3.4: a mipped target's level ("<name>@<level>" past 0)
        put(d, "data", PyBytes_FromStringAndSize(p.data.constData(), Py_ssize_t(p.data.size())));
        if (PyList_Append(list, d) < 0) {
            Py_DECREF(d);
            Py_DECREF(list);
            return nullptr;
        }
        Py_DECREF(d);
    }
    return list;
}

// ---------------------------------------------------------------- compute passes (N3.3, D16)

// A storage image's size ([w, h] or [w, h, d]) with no new program (the image is made again at the next record).
PyObject *composite_mode_image_size(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *name = nullptr;
    PyObject *size = nullptr;
    if (!PyArg_ParseTuple(args, "LsO", &handle, &name, &size))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    QList<int> values;
    if (!intsArgument(size, &values, "an image's size"))
        return nullptr;
    if (values.size() != 2 && values.size() != 3) {
        PyErr_SetString(PyExc_ValueError, "an image's size is (w, h) or (w, h, d)");
        return nullptr;
    }
    const int sides[3] = { values.at(0), values.at(1), values.size() == 3 ? values.at(2) : 1 };
    QString error;
    if (!source->setImageSize(QByteArray(name), sides, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

// Harness: a readback of every storage buffer and image at the next record (it dispatches nothing).
PyObject *composite_mode_storage_read(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    source->requestStorageRead();
    compositeOf(handle)->update();
    Py_RETURN_NONE;
}

// Harness: the storage readback once QRhi completed it (None before), each {"name", "kind", "format", "size", "data"}
// (a buffer's bytes; an image's texels as stored, rows top first, slices in order).
PyObject *composite_mode_storage_data(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::ModeSource *source = modeOf(handle);
    if (!source)
        return nullptr;
    QList<srpss_core::StoragePixels> items;
    if (!source->takeStoragePixels(&items))
        Py_RETURN_NONE;
    PyObject *list = PyList_New(0);
    if (!list)
        return nullptr;
    for (const srpss_core::StoragePixels &p : items) {
        PyObject *d = PyDict_New();
        if (!d) {
            Py_DECREF(list);
            return nullptr;
        }
        put(d, "name", pyStr(p.name));
        put(d, "kind", pyStr(p.kind));
        put(d, "format", pyStr(p.format));
        put(d, "size", Py_BuildValue("(iii)", p.size[0], p.size[1], p.size[2]));
        put(d, "data", PyBytes_FromStringAndSize(p.data.constData(), Py_ssize_t(p.data.size())));
        if (PyList_Append(list, d) < 0) {
            Py_DECREF(d);
            Py_DECREF(list);
            return nullptr;
        }
        Py_DECREF(d);
    }
    return list;
}

// N3.3, harness: the proofs' negative controls (compute_passes.h), each process-wide; a key left out keeps its value.
PyObject *compute_control(PyObject *, PyObject *args)
{
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "s#", &json, &length))
        return nullptr;
    const QJsonObject o = QJsonDocument::fromJson(QByteArray(json, qsizetype(length))).object();
    static const QStringList keys = { QStringLiteral("write_as_read"), QStringLiteral("single_pass"),
                                      QStringLiteral("trigger_every_record"), QStringLiteral("skip_storage_release") };
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!keys.contains(it.key())) {
            PyErr_Format(PyExc_ValueError, "unknown control '%s' (%s)", it.key().toUtf8().constData(),
                         keys.join(QStringLiteral(", ")).toUtf8().constData());
            return nullptr;
        }
    }
    if (o.contains(QStringLiteral("write_as_read")))
        srpss_core::setComputeWriteAsRead(o.value(QStringLiteral("write_as_read")).toBool());
    if (o.contains(QStringLiteral("single_pass")))
        srpss_core::setComputeSinglePass(o.value(QStringLiteral("single_pass")).toBool());
    if (o.contains(QStringLiteral("trigger_every_record")))
        srpss_core::setComputeTriggerEveryRecord(o.value(QStringLiteral("trigger_every_record")).toBool());
    if (o.contains(QStringLiteral("skip_storage_release")))
        srpss_core::setSkipStorageRelease(o.value(QStringLiteral("skip_storage_release")).toBool());
    Py_RETURN_NONE;
}

// A sequence of ints (the limited API's calls only).
bool intsArgument(PyObject *object, QList<int> *out, const char *what)
{
    if (!PySequence_Check(object)) {
        PyErr_Format(PyExc_TypeError, "%s are a sequence of ints", what);
        return false;
    }
    const Py_ssize_t n = PySequence_Size(object);
    if (n < 0)
        return false;
    for (Py_ssize_t i = 0; i < n; ++i) {
        PyObject *item = PySequence_GetItem(object, i); // a new reference
        if (!item)
            return false;
        const long value = PyLong_AsLong(item);
        Py_DECREF(item);
        if (value == -1 && PyErr_Occurred())
            return false;
        out->append(int(value));
    }
    return true;
}

// Harness: the clamp's control (D14 point 7's negative control): sample counts taken out of every device's set.
PyObject *scene_target_control(PyObject *, PyObject *args)
{
    const char *name = nullptr;
    int value = 0;
    if (!PyArg_ParseTuple(args, "si", &name, &value))
        return nullptr;
    if (!srpss_core::setSceneTargetControl(QByteArray(name), value)) {
        PyErr_SetString(PyExc_ValueError, "unknown scene-target control or invalid value");
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *scene_sample_counts_control(PyObject *, PyObject *args)
{
    PyObject *removed = nullptr;
    if (!PyArg_ParseTuple(args, "O", &removed))
        return nullptr;
    QList<int> counts;
    if (!intsArgument(removed, &counts, "the removed sample counts"))
        return nullptr;
    srpss_core::setRemovedSampleCounts(counts);
    Py_RETURN_NONE;
}

// Harness: rule C for depth switched off (its negative control under synchronisation validation), or on again.
PyObject *scene_depth_prime_control(PyObject *, PyObject *args)
{
    int skip = 0;
    if (!PyArg_ParseTuple(args, "p", &skip))
        return nullptr;
    srpss_core::setSkipDepthPrime(skip != 0);
    Py_RETURN_NONE;
}

// Harness: the resolves' prime before each run switched off (audit 2, H1: its negative control under synchronisation
// validation), or on again.
PyObject *scene_resolve_prime_control(PyObject *, PyObject *args)
{
    int skip = 0;
    if (!PyArg_ParseTuple(args, "p", &skip))
        return nullptr;
    srpss_core::setSkipResolvePrime(skip != 0);
    Py_RETURN_NONE;
}

// Harness: the nearest resolve's negative control (sample 0 instead of the minimum), read when a content builds.
PyObject *scene_nearest_first_sample_control(PyObject *, PyObject *args)
{
    int firstOnly = 0;
    if (!PyArg_ParseTuple(args, "p", &firstOnly))
        return nullptr;
    srpss_core::setNearestFirstSample(firstOnly != 0);
    Py_RETURN_NONE;
}

// Harness: N3.4's (D17) negative controls by name, each on or off; False for an unknown name.
PyObject *stage_control(PyObject *, PyObject *args)
{
    const char *name = nullptr;
    PyObject *argument = nullptr;
    if (!PyArg_ParseTuple(args, "sO", &name, &argument))
        return nullptr;
    const QByteArray control(name);
    if (control == "fail_allocation" || control == "fail_build") {
        if (!PyLong_Check(argument) || PyBool_Check(argument)) {
            PyErr_Format(PyExc_TypeError, "%s requires an integer attempt (0: off)", name);
            return nullptr;
        }
        const long attempt = PyLong_AsLong(argument);
        if (attempt == -1 && PyErr_Occurred())
            return nullptr;
        const int limit = control == "fail_allocation" ? srpss_core::kMaxStageAllocationAttempts
                                                       : srpss_core::kMaxStageBuildAttempts;
        if (attempt < 0 || attempt > limit) {
            PyErr_Format(PyExc_ValueError, "%s attempt must be between 0 and %d", name, limit);
            return nullptr;
        }
        if (control == "fail_allocation")
            srpss_core::setStageAllocationFailure(int(attempt));
        else
            srpss_core::setStageBuildFailure(int(attempt));
        Py_RETURN_TRUE;
    }
    const int on = PyObject_IsTrue(argument); // preserve every existing boolean control's truth/error semantics
    if (on < 0)
        return nullptr;
    const bool value = on != 0;
    if (control == "skip_blend_gate")
        srpss_core::setSkipBlendGate(value);
    else if (control == "blend_formats_missing")
        srpss_core::setBlendFormatsMissing(value);
    else if (control == "sample_shading_missing")
        srpss_core::setSampleShadingMissing(value);
    else if (control == "transparency_first_sample")
        srpss_core::setTransparencyFirstSample(value);
    else if (control == "skip_bloom_prime")
        srpss_core::setSkipBloomPrime(value);
    else if (control == "bloom_same_texture")
        srpss_core::setBloomSameTexture(value);
    else if (control == "skip_stage_release")
        srpss_core::setSkipStageRelease(value);
    else if (control == "device_without_independent_blend")
        srpss_core::setDeviceWithoutIndependentBlend(value);
    else if (control == "skip_read_chain")
        srpss_core::setSkipReadChain(value);
    else if (control == "time_defocus_draws")
        srpss_core::setTimeDefocusDraws(value);
    else if (control == "flush_defocus_draws")
        srpss_core::setFlushDefocusDraws(value);
    else if (control == "flush_defocus_before_gather")
        srpss_core::setFlushDefocusBoundary(0, value);
    else if (control == "flush_defocus_between_draws")
        srpss_core::setFlushDefocusBoundary(1, value);
    else if (control == "flush_defocus_after_sprites")
        srpss_core::setFlushDefocusBoundary(2, value);
    else
        Py_RETURN_FALSE;
    Py_RETURN_TRUE;
}

// GPU-free: D14 point 2's allocation rule, ((w, h), reason) for a current allocation ((0, 0): none) and a needed size.
PyObject *scene_target_next_allocation(PyObject *, PyObject *args)
{
    int cw = 0, ch = 0, nw = 0, nh = 0;
    if (!PyArg_ParseTuple(args, "(ii)(ii)", &cw, &ch, &nw, &nh))
        return nullptr;
    QString reason;
    const QSize next = srpss_core::nextAllocation(QSize(cw, ch), QSize(nw, nh), &reason);
    return Py_BuildValue("((ii)N)", next.width(), next.height(), pyStr(reason));
}

// GPU-free: D14 point 2's content viewport (QRhi's x, y from the framebuffer's bottom-left, w, h).
PyObject *scene_target_viewport(PyObject *, PyObject *args)
{
    int yUp = 0, aw = 0, ah = 0, cw = 0, ch = 0;
    if (!PyArg_ParseTuple(args, "p(ii)(ii)", &yUp, &aw, &ah, &cw, &ch))
        return nullptr;
    const QRect v = srpss_core::contentViewport(yUp != 0, QSize(aw, ah), QSize(cw, ch));
    return Py_BuildValue("(iiii)", v.x(), v.y(), v.width(), v.height());
}

// GPU-free: D14 point 7's clamp.
PyObject *scene_target_clamp(PyObject *, PyObject *args)
{
    PyObject *supported = nullptr;
    int requested = 1;
    if (!PyArg_ParseTuple(args, "Oi", &supported, &requested))
        return nullptr;
    QList<int> counts;
    if (!intsArgument(supported, &counts, "the supported sample counts"))
        return nullptr;
    return PyLong_FromLong(srpss_core::clampSamples(counts, requested));
}

PyObject *mode_blocks(PyObject *, PyObject *args)
{
    const char *schemaJson = "";
    Py_ssize_t schemaLength = 0;
    const char *json = "";
    Py_ssize_t length = 0;
    PyObject *packs = nullptr;
    const char *settingsJson = "";
    Py_ssize_t settingsLength = 0;
    const char *record = nullptr;
    Py_ssize_t recordLength = 0;
    const char *cardJson = nullptr;
    Py_ssize_t cardLength = 0;
    int targetWidth = 0;
    int targetHeight = 0;
    PyObject *correctionArgument = nullptr;   // N3.2: an optional clip correction (16 floats, column-major)
    if (!PyArg_ParseTuple(args, "s#s#Os#y#z#(ii)|O", &schemaJson, &schemaLength, &json, &length, &packs, &settingsJson,
                          &settingsLength, &record, &recordLength, &cardJson, &cardLength, &targetWidth, &targetHeight,
                          &correctionArgument))
        return nullptr;
    float correction[16] = {};
    const bool corrected = correctionArgument && correctionArgument != Py_None;
    if (corrected) {
        // The limited API's function forms (the module builds against it), as the other sequence arguments here.
        if (!PySequence_Check(correctionArgument) || PySequence_Size(correctionArgument) != 16) {
            PyErr_SetString(PyExc_ValueError, "a clip correction is 16 numbers (column-major)");
            return nullptr;
        }
        for (Py_ssize_t k = 0; k < 16; ++k) {
            PyObject *item = PySequence_GetItem(correctionArgument, k); // a new reference
            if (!item)
                return nullptr;
            const double value = PyFloat_AsDouble(item);
            Py_DECREF(item);
            if (PyErr_Occurred())
                return nullptr;
            correction[k] = float(value);
        }
    }
    const QSharedPointer<const srpss_core::RuntimeSchema> schema = schemaArgument(schemaJson, schemaLength);
    srpss_core::ModeProgram program;
    QJsonObject settings;
    srpss_core::ModeCard card;
    if (!schema || !programArgument(json, length, packs, &program)
        || !settingsArgument(settingsJson, settingsLength, &settings) || (cardJson && !cardArgument(cardJson, cardLength, &card)))
        return nullptr;
    QList<QByteArray> blocks;
    QJsonObject facts;
    QString reason;
    if (!srpss_core::modeBlocks(*schema, program, settings, card, QSize(targetWidth, targetHeight),
                                QByteArray(record, qsizetype(recordLength)), &blocks, &facts, &reason,
                                corrected ? correction : nullptr)) {
        PyErr_SetString(PyExc_ValueError, reason.toUtf8().constData());
        return nullptr;
    }
    PyObject *list = PyList_New(0);
    if (!list)
        return nullptr;
    for (const QByteArray &block : blocks) {
        PyObject *bytes = PyBytes_FromStringAndSize(block.constData(), Py_ssize_t(block.size()));
        if (!bytes || PyList_Append(list, bytes) < 0) {
            Py_XDECREF(bytes);
            Py_DECREF(list);
            return nullptr;
        }
        Py_DECREF(bytes);
    }
    facts.insert(QStringLiteral("program"), program.toJson());
    facts.insert(QStringLiteral("schema"), schema->toJson());
    return Py_BuildValue("(NN)", list, pyJson(facts));
}

PyObject *mode_program_layout(PyObject *, PyObject *args)
{
    const char *json = "";
    Py_ssize_t length = 0;
    PyObject *packs = nullptr;
    if (!PyArg_ParseTuple(args, "s#O", &json, &length, &packs))
        return nullptr;
    srpss_core::ModeProgram program;
    if (!programArgument(json, length, packs, &program))
        return nullptr;
    return pyJson(program.toJson());
}

// Audit 14 Nov, L2: one block of a pack packed from name -> numbers, as the core packs it (GPU-free).
PyObject *program_block_pack(PyObject *, PyObject *args)
{
    PyObject *pack = nullptr;
    const char *blockName = nullptr;
    const char *json = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Oss#", &pack, &blockName, &json, &length))
        return nullptr;
    QByteArray qsb;
    QJsonObject values;
    if (!packArgument(pack, &qsb) || !settingsArgument(json, length, &values))
        return nullptr;
    if (qsb.isEmpty()) {
        PyErr_SetString(PyExc_ValueError, "a pack is the bytes of a .qsb");
        return nullptr;
    }
    const srpss_core::BlockLayout layout = srpss_core::BlockLayout::reflect(QShader::fromSerialized(qsb),
                                                                            QByteArray(blockName));
    if (!layout.valid()) {
        PyErr_Format(PyExc_ValueError, "the pack holds no block named %s", blockName);
        return nullptr;
    }
    srpss_core::BlockValues block(layout);
    QString error;
    if (!block.setJson(values, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    QJsonObject facts;
    facts.insert(QStringLiteral("layout"), layout.toJson());
    facts.insert(QStringLiteral("unfilled"), QJsonArray::fromStringList(block.unfilled()));
    return Py_BuildValue("(y#N)", block.bytes().constData(), Py_ssize_t(block.bytes().size()), pyJson(facts));
}

// ---------------------------------------------------------------- the packet reader (N2.3: D1, D2, the transport rule)

// A reader behind a handle is owned by its references: the handle's own and one per read in progress (a read with the
// pause_in_copy hook runs with the GIL released, so another Python thread may close the handle meanwhile). A close only
// retires the reader and drops the handle's reference; whoever drops the last one (the reading thread, when a read was
// in progress) releases and deletes it there, so a close never unmaps a view a read is copying (audit, 14 Nov:
// fix-soon 3; the render-thread retire job is the bound stream's form of the same rule, spectrum.h).
struct ReaderEntry
{
    srpss_core::PacketReader *reader = nullptr;
    qint64 handle = 0;
    QAtomicInt refs { 1 };
};

struct Readers
{
    qint64 next = 1;
    QHash<qint64, ReaderEntry *> live;     // the handles Python holds (the GIL guards them)
    QMutex closingMutex;                   // guards `closing` (the last reference may drop without the GIL)
    QHash<qint64, ReaderEntry *> closing;  // closed while a read held them: reachable only for the hook's resume
};

Readers &readers()
{
    static Readers r;
    return r;
}

ReaderEntry *entryOf(long long handle)
{
    ReaderEntry *entry = readers().live.value(handle, nullptr);
    if (!entry)
        PyErr_Format(PyExc_KeyError, "no packet reader %lld (closed, or never created)", handle);
    return entry;
}

srpss_core::PacketReader *readerOf(long long handle)
{
    ReaderEntry *entry = entryOf(handle);
    return entry ? entry->reader : nullptr;
}

// Drops one reference; the last one releases the reader on this thread (its consumer's) and deletes it.
void dropReference(ReaderEntry *entry)
{
    if (entry->refs.deref())
        return;
    {
        QMutexLocker lock(&readers().closingMutex);
        readers().closing.remove(entry->handle);
    }
    entry->reader->retire();
    entry->reader->release();
    delete entry->reader;
    delete entry;
}

PyObject *pyU32(quint32 value)
{
    return PyLong_FromUnsignedLong(static_cast<unsigned long>(value));
}

PyObject *pyU64(quint64 value)
{
    return PyLong_FromUnsignedLongLong(static_cast<unsigned long long>(value));
}

PyObject *slotHeadDict(const srpss_core::SlotHead &head)
{
    PyObject *d = PyDict_New();
    if (!d)
        return nullptr;
    put(d, "sequence", pyU64(head.sequence));
    put(d, "payload_bytes", pyU32(head.payloadBytes));
    put(d, "payload_schema", pyU32(head.payloadSchema));
    put(d, "logical_timestamp", PyFloat_FromDouble(head.logicalTimestamp));
    if (std::isnan(head.sourceTimestamp)) {
        Py_INCREF(Py_None);
        put(d, "source_timestamp", Py_None);
    } else {
        put(d, "source_timestamp", PyFloat_FromDouble(head.sourceTimestamp));
    }
    put(d, "flags", pyU32(head.flags));
    put(d, "protected_edge_mask", pyU32(head.protectedEdgeMask));
    put(d, "runtime_generation", pyU32(head.runtimeGeneration));
    put(d, "engine_generation", pyU32(head.engineGeneration));
    put(d, "activation_id", pyU32(head.activationId));
    put(d, "mode_code", pyU32(head.modeCode));
    put(d, "publish_ns", pyU64(head.publishNs));
    return d;
}

double recordF64(const char *data, quint32 offset)
{
    double value;
    std::memcpy(&value, data + offset, sizeof value);
    return value;
}

quint32 recordU32(const char *data, quint32 offset)
{
    quint32 value;
    std::memcpy(&value, data + offset, sizeof value);
    return value;
}

// One element of a field (a u32, an f64, or an f64x4 as a 4-tuple), as the reference decoder's struct.unpack gives it.
PyObject *recordElement(const char *data, srpss_core::frame_abi::FieldKind kind, quint32 offset)
{
    using srpss_core::frame_abi::FieldKind;
    switch (kind) {
    case FieldKind::U32:
        return pyU32(recordU32(data, offset));
    case FieldKind::F64:
        return PyFloat_FromDouble(recordF64(data, offset));
    case FieldKind::F64x4: {
        PyObject *tuple = PyTuple_New(4);
        if (!tuple)
            return nullptr;
        for (Py_ssize_t i = 0; i < 4; ++i)
            PyTuple_SetItem(tuple, i, PyFloat_FromDouble(recordF64(data, offset + quint32(i) * 8))); // steals
        return tuple;
    }
    case FieldKind::F32: { // D15 choice B: one float of a stream's bytes
        float value = 0.0f;
        std::memcpy(&value, data + offset, sizeof(value));
        return PyFloat_FromDouble(static_cast<double>(value));
    }
    }
    Py_RETURN_NONE;
}

quint32 elementBytes(srpss_core::frame_abi::FieldKind kind)
{
    using srpss_core::frame_abi::FieldKind;
    return kind == FieldKind::U32 || kind == FieldKind::F32 ? 4u : kind == FieldKind::F64 ? 8u : 32u;
}

// The record's fields by name in the reference decoder's order (header words excluded): the C++ decode the parity
// harness compares bit for bit with spectrum_native_schema.decode.
PyObject *recordFields(const srpss_core::frame_abi::Schema &schema, const QByteArray &record)
{
    PyObject *d = PyDict_New();
    if (!d)
        return nullptr;
    const char *data = record.constData();
    for (quint32 i = 0; i < schema.fieldCount; ++i) {
        const srpss_core::frame_abi::Field &field = schema.fields[i];
        PyObject *value = nullptr;
        if (field.count == 1) {
            value = recordElement(data, field.kind, field.offset);
        } else {
            value = PyTuple_New(Py_ssize_t(field.count));
            for (quint32 j = 0; value && j < field.count; ++j)
                PyTuple_SetItem(value, Py_ssize_t(j),
                                recordElement(data, field.kind, field.offset + j * elementBytes(field.kind)));
        }
        if (!value) {
            Py_DECREF(d);
            return nullptr;
        }
        put(d, field.name, value);
    }
    return d;
}

PyObject *packet_reader_open(PyObject *, PyObject *args)
{
    const char *name = nullptr;
    const char *config = "";
    Py_ssize_t length = 0;
    const char *schemaJson = "";
    Py_ssize_t schemaLength = 0;
    if (!PyArg_ParseTuple(args, "s|s#s#", &name, &config, &length, &schemaJson, &schemaLength))
        return nullptr;
    srpss_core::PacketReaderConfig parsed;
    QString error;
    if (length && !srpss_core::PacketReaderConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    if (schemaLength) { // N2.9: a generic mode's schema, admitted beside the compiled table
        parsed.runtimeSchema = srpss_core::RuntimeSchema::fromJson(QByteArray(schemaJson, qsizetype(schemaLength)),
                                                                   &error);
        if (!parsed.runtimeSchema) {
            PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
            return nullptr;
        }
    }
    srpss_core::PacketReader *reader = srpss_core::PacketReader::open(QString::fromUtf8(name), parsed, &error);
    if (!reader) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    const qint64 handle = readers().next++;
    auto *entry = new ReaderEntry;
    entry->reader = reader;
    entry->handle = handle;
    readers().live.insert(handle, entry);
    return PyLong_FromLongLong(handle);
}

PyObject *packet_reader_read(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    ReaderEntry *entry = entryOf(handle);
    if (!entry)
        return nullptr;
    entry->refs.ref(); // the read's own reference: a close meanwhile leaves the release to this thread
    srpss_core::PacketReader *reader = entry->reader;
    srpss_core::ReadResult result = srpss_core::ReadResult::Nothing;
    if (reader->pausesInCopy()) {
        // The D1 hook holds the read until another Python thread resumes it (that thread never closes this handle).
        Py_BEGIN_ALLOW_THREADS
        result = reader->read();
        Py_END_ALLOW_THREADS
    } else {
        result = reader->read();
    }
    dropReference(entry);
    const char *name = srpss_core::readResultName(result);
    return PyUnicode_FromString(name);
}

PyObject *packet_reader_wait_paused(PyObject *, PyObject *args)
{
    long long handle = 0;
    int timeoutMs = 0;
    if (!PyArg_ParseTuple(args, "Li", &handle, &timeoutMs))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    bool paused = false;
    Py_BEGIN_ALLOW_THREADS
    paused = reader->waitPaused(timeoutMs);
    Py_END_ALLOW_THREADS
    return PyBool_FromLong(paused ? 1 : 0);
}

PyObject *packet_reader_resume(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    if (ReaderEntry *entry = readers().live.value(handle, nullptr)) {
        entry->reader->resume();
        Py_RETURN_NONE;
    }
    {
        // A handle closed while its read was paused: still resumable until that read lets go of it.
        QMutexLocker lock(&readers().closingMutex);
        if (ReaderEntry *entry = readers().closing.value(handle, nullptr)) {
            entry->reader->resume();
            Py_RETURN_NONE;
        }
    }
    PyErr_Format(PyExc_KeyError, "no packet reader %lld (closed, or never created)", handle);
    return nullptr;
}

PyObject *packet_reader_head(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    srpss_core::SlotHead head;
    if (!reader->readHead(&head))
        Py_RETURN_NONE;
    return slotHeadDict(head);
}

PyObject *packet_reader_frame(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    srpss_core::SlotHead head;
    const QByteArray *record = nullptr;
    if (!reader->retained(&head, &record))
        Py_RETURN_NONE;
    PyObject *d = slotHeadDict(head);
    if (!d)
        return nullptr;
    put(d, "payload", PyBytes_FromStringAndSize(record->constData(), Py_ssize_t(record->size())));
    const srpss_core::frame_abi::Schema *schema = reader->retainedSchema();
    if (schema) {
        PyObject *fields = recordFields(*schema, *record);
        if (!fields) {
            Py_DECREF(d);
            return nullptr;
        }
        put(d, "fields", fields);
    } else {
        Py_INCREF(Py_None);
        put(d, "fields", Py_None);
    }
    return d;
}

PyObject *packet_reader_drop(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    reader->dropRetainedFrame();
    Py_RETURN_NONE;
}

PyObject *packet_reader_retire(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    reader->retire();
    Py_RETURN_NONE;
}

PyObject *packet_reader_release(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    reader->release();
    Py_RETURN_NONE;
}

PyObject *packet_reader_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    return pyJson(reader->stateJson());
}

PyObject *packet_reader_close(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    ReaderEntry *entry = readers().live.take(handle);
    if (!entry) {
        PyErr_Format(PyExc_KeyError, "no packet reader %lld (closed, or never created)", handle);
        return nullptr;
    }
    // Retiring at once (no copy starts after it); the release is the last reference's (a read in progress keeps it).
    entry->reader->retire();
    QJsonObject state = entry->reader->stateJson();
    bool readInProgress = false;
    {
        QMutexLocker lock(&readers().closingMutex);
        readInProgress = entry->refs.loadAcquire() > 1;
        if (readInProgress)
            readers().closing.insert(entry->handle, entry);
    }
    state.insert(QStringLiteral("released_by"), readInProgress ? QStringLiteral("the reading thread")
                                                               : QStringLiteral("the closing thread"));
    dropReference(entry);
    return pyJson(state);
}

PyObject *packet_reader_live(PyObject *, PyObject *)
{
    QJsonObject o = srpss_core::PacketReader::liveJson();
    o.insert(QStringLiteral("handles"), int(readers().live.size()));
    QMutexLocker lock(&readers().closingMutex);
    o.insert(QStringLiteral("closing"), int(readers().closing.size()));
    return pyJson(o);
}

PyObject *frame_schemas(PyObject *, PyObject *)
{
    namespace fa = srpss_core::frame_abi;
    QJsonObject o;
    o.insert(QStringLiteral("abi_version"), int(fa::kAbiVersion));
    o.insert(QStringLiteral("mapping_prefix"), QLatin1String(fa::kMappingPrefix));
    QJsonObject modes;
    for (const fa::ModeCode &mode : fa::kModeCodes)
        modes.insert(QLatin1String(mode.modeId), double(mode.code));
    o.insert(QStringLiteral("mode_codes"), modes);
    QJsonArray schemas;
    static const char *kinds[] = { "u32", "f64", "f64x4", "f32" };
    static const char *checks[] = { "", "at_most", "boolean", "enum" };
    for (const fa::Schema &schema : fa::kSchemas) {
        QJsonObject s;
        s.insert(QStringLiteral("schema_id"), double(schema.schemaId));
        s.insert(QStringLiteral("mode_id"), QLatin1String(schema.modeId));
        s.insert(QStringLiteral("mode_code"), double(schema.modeCode));
        s.insert(QStringLiteral("version"), double(schema.version));
        s.insert(QStringLiteral("record_bytes"), double(schema.recordBytes));
        s.insert(QStringLiteral("fingerprint"), QLatin1String(schema.fingerprint));
        QJsonArray fields;
        for (quint32 i = 0; i < schema.fieldCount; ++i) {
            const fa::Field &f = schema.fields[i];
            fields.append(QJsonArray { QLatin1String(f.name), QLatin1String(kinds[int(f.kind)]), double(f.count),
                                       double(f.offset), QLatin1String(checks[int(f.check)]), double(f.limit) });
        }
        s.insert(QStringLiteral("fields"), fields);
        QJsonArray order;
        for (quint32 i = 0; i < schema.checkCount; ++i)
            order.append(double(schema.checkOrder[i]));
        s.insert(QStringLiteral("check_order"), order);
        schemas.append(s);
    }
    o.insert(QStringLiteral("schemas"), schemas);
    return pyJson(o);
}

// ---------------------------------------------------------------- the backdrop pyramid (N5.7b, backdrop.h)

struct Backdrops
{
    qint64 next = 1;
    QHash<qint64, QPointer<srpss_core::BackdropItem>> live;
};

Backdrops &backdrops()
{
    static Backdrops b;
    return b;
}

srpss_core::BackdropItem *backdropOf(long long handle)
{
    if (!backdrops().live.contains(handle)) {
        PyErr_Format(PyExc_KeyError, "no backdrop %lld (destroyed, or never created)", handle);
        return nullptr;
    }
    srpss_core::BackdropItem *item = backdrops().live.value(handle).data();
    if (!item)
        PyErr_Format(PyExc_RuntimeError, "backdrop %lld was deleted with its parent item", handle);
    return item;
}

PyObject *backdrop_create(PyObject *, PyObject *args)
{
    unsigned long long address = 0;
    int parked = 0;
    if (!PyArg_ParseTuple(args, "K|p", &address, &parked))
        return nullptr;
    auto *parent = qobject_cast<QQuickItem *>(reinterpret_cast<QObject *>(static_cast<quintptr>(address)));
    if (!address || !parent) {
        PyErr_SetString(PyExc_TypeError, "a backdrop is placed in a QQuickItem: pass its address");
        return nullptr;
    }
    auto *item = new srpss_core::BackdropItem(parent); // owned by its parent item (QObject parent) and deletable here
    if (parked)
        item->setParked(true);
    const qint64 handle = backdrops().next++;
    backdrops().live.insert(handle, QPointer<srpss_core::BackdropItem>(item));
    // The item's address, for the Python face's wrapper (shiboken6.wrapInstance as a QQuickItem: QML binds it as a
    // card's backdrop, MaterialSurface's texture provider).
    return Py_BuildValue("(LK)", handle, static_cast<unsigned long long>(quintptr(item)));
}

PyObject *backdrop_set(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *config = "";
    Py_ssize_t length = 0;
    if (!PyArg_ParseTuple(args, "Ls#", &handle, &config, &length))
        return nullptr;
    srpss_core::BackdropItem *item = backdropOf(handle);
    if (!item)
        return nullptr;
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(QByteArray(config, qsizetype(length)), &parse);
    if (parse.error != QJsonParseError::NoError || !document.isObject()) {
        PyErr_SetString(PyExc_ValueError, "the backdrop's configuration is a JSON object");
        return nullptr;
    }
    const QJsonObject o = document.object();
    for (auto it = o.constBegin(); it != o.constEnd(); ++it) {
        if (it.key() != QLatin1String("parked") && it.key() != QLatin1String("dimming")) {
            PyErr_Format(PyExc_ValueError, "unknown backdrop option '%s' (parked, dimming)",
                         it.key().toUtf8().constData());
            return nullptr;
        }
    }
    if (o.contains(QStringLiteral("dimming"))) {
        const double dimming = o.value(QStringLiteral("dimming")).toDouble(-1.0);
        if (!(dimming >= 0.0 && dimming <= 1.0)) {
            PyErr_SetString(PyExc_ValueError, "dimming is 0 to 1");
            return nullptr;
        }
        item->setDimming(dimming);
    }
    if (o.contains(QStringLiteral("parked"))) {
        const QJsonValue parked = o.value(QStringLiteral("parked"));
        if (!parked.isBool()) {
            PyErr_SetString(PyExc_ValueError, "parked is true or false");
            return nullptr;
        }
        item->setParked(parked.toBool());
    }
    Py_RETURN_NONE;
}

PyObject *backdrop_build(PyObject *, PyObject *args)
{
    long long handle = 0;
    int readback = 0;
    if (!PyArg_ParseTuple(args, "L|p", &handle, &readback))
        return nullptr;
    srpss_core::BackdropItem *item = backdropOf(handle);
    if (!item)
        return nullptr;
    if (readback)
        item->requestReadback();
    else
        item->requestBuild();
    Py_RETURN_NONE;
}

PyObject *backdrop_levels(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::BackdropItem *item = backdropOf(handle);
    if (!item)
        return nullptr;
    QList<srpss_core::BackdropLevelPixels> levels;
    if (!item->takeLevels(&levels))
        Py_RETURN_NONE;
    PyObject *list = PyList_New(0);
    for (const srpss_core::BackdropLevelPixels &level : levels) {
        const QByteArray name = level.name.toUtf8();
        PyObject *entry = Py_BuildValue("(s#iiy#)", name.constData(), Py_ssize_t(name.size()), level.size.width(),
                                        level.size.height(), level.rgba.constData(), Py_ssize_t(level.rgba.size()));
        if (!entry) {
            Py_DECREF(list);
            return nullptr;
        }
        PyList_Append(list, entry);
        Py_DECREF(entry);
    }
    return list;
}

PyObject *backdrop_state(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::BackdropItem *item = backdropOf(handle);
    if (!item)
        return nullptr;
    return pyJson(item->stateJson());
}

PyObject *backdrop_destroy(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    if (!backdrops().live.contains(handle)) {
        PyErr_Format(PyExc_KeyError, "no backdrop %lld (destroyed, or never created)", handle);
        return nullptr;
    }
    QPointer<srpss_core::BackdropItem> item = backdrops().live.take(handle);
    const bool deleted = !item.isNull();
    delete item.data(); // GUI thread: Qt Quick releases its node (and the pyramid) on the render thread at the next sync
    return PyBool_FromLong(deleted ? 1 : 0);
}

PyObject *backdrop_pyramid_sizes(PyObject *, PyObject *args)
{
    int width = 0;
    int height = 0;
    if (!PyArg_ParseTuple(args, "ii", &width, &height))
        return nullptr;
    QJsonArray sizes;
    for (const QSize &s : srpss_core::backdropPyramidSizes(QSize(width, height)))
        sizes.append(QJsonArray { s.width(), s.height() });
    QJsonArray names;
    for (int i = 0; i < int(srpss_core::BackdropLevel::Count); ++i)
        names.append(srpss_core::backdropLevelName(srpss_core::BackdropLevel(i)));
    QJsonObject o;
    o.insert(QStringLiteral("sizes"), sizes);
    o.insert(QStringLiteral("levels"), names);
    return pyJson(o);
}

PyMethodDef methods[] = {
    { "runtime_info", runtime_info, METH_NOARGS,
      "() -> dict: version, ABI, the compiled and running Qt, the compiler, the loaded Qt and MSVC runtime DLLs." },
    { "process_counters", process_counters, METH_NOARGS,
      "() -> JSON str: handles, GDI and USER objects, threads, private bytes, working set (lifecycle proofs)." },
    { "vulkan_instance_create", vulkan_instance_create, METH_VARARGS,
      "(validation=False) -> JSON str: the process's Vulkan instance (D6); validation only in a harness." },
    { "vulkan_instance_destroy", vulkan_instance_destroy, METH_NOARGS,
      "() -> JSON str: destroys it after every device; the steps and the validation messages per phase." },
    { "vulkan_set_phase", vulkan_set_phase, METH_VARARGS,
      "(phase) -> None: the phase the validation messages that follow are counted under." },
    { "host_attach", host_attach, METH_VARARGS,
      "(kind 'window', quick_window_address) | ('hidden', 0, width, height, threaded=True, dpr=1.0, timestamps=False) "
      "-> int handle: a host with its frame driver attached (D5.1, D5.2); a hidden host's size is device pixels; "
      "timestamps: its QRhi times whole frames (EnableTimestamps)." },
    { "host_set_dpr", host_set_dpr, METH_VARARGS,
      "(handle, dpr) -> None: the hidden host renders its device pixels at this device pixel ratio." },
    { "host_read", host_read, METH_VARARGS,
      "(handle) -> dict: the hidden host renders one frame and reads Qt Quick's target back (raw rows, size, "
      "y_up_in_framebuffer, frame)." },
    { "host_reattach", host_reattach, METH_VARARGS, "(handle) -> None: a new frame driver on the host's window." },
    { "host_detach", host_detach, METH_VARARGS,
      "(handle) -> None: the frame driver stops and releases on the render thread." },
    { "host_state", host_state, METH_VARARGS, "(handle) -> JSON str: the host and its frame drivers." },
    { "host_set_content", host_set_content, METH_VARARGS,
      "(handle, quick_item_address) -> None: the hidden host renders this item (0: none)." },
    { "host_frames", host_frames, METH_VARARGS, "(handle, count=1) -> None: the hidden host renders frames." },
    { "host_invalidate_scene_graph", host_invalidate_scene_graph, METH_VARARGS,
      "(handle) -> None: harness; invalidate the hidden host's actual scene graph on its render thread; close next." },
    { "host_close", host_close, METH_VARARGS,
      "(handle) -> JSON str: detaches; a hidden host also tears down its window and device." },
    { "host_probe", host_probe, METH_VARARGS,
      "(handle, config_json='') -> None: the probe pass from the next frame; empty removes it." },
    { "host_probe_readback", host_probe_readback, METH_VARARGS,
      "(handle) -> None: the next recorded probe pass reads its target back." },
    { "host_probe_result", host_probe_result, METH_VARARGS,
      "(handle) -> dict | None: the last completed probe readback (facts JSON, raw RGBA rows, size, frame)." },
    { "host_load", host_load, METH_VARARGS,
      "(handle, config_json='') -> None: the known-cost pass (width, height, draws, iterations, timing 'pass' or "
      "'before') from the next frame; empty removes it." },
    { "host_gpu_timer", host_gpu_timer, METH_VARARGS,
      "(handle, config_json) -> None: the GPU timer on or off from the next frame (enabled; keep_when_off and "
      "wait_for_results are negative controls)." },
    { "host_gpu_samples", host_gpu_samples, METH_VARARGS,
      "(handle) -> list of (kind, frame, read_at, nanoseconds): the timer's results read since the last call." },
    { "gpu_timer_live", gpu_timer_live, METH_NOARGS,
      "() -> JSON str: GPU timers alive in the process and their query objects (pools, queries)." },
    { "live_hosts", live_hosts, METH_NOARGS, "() -> int: hosts not closed." },
    { "composite_create", composite_create, METH_VARARGS,
      "(parent_quick_item_address) -> int handle: a composite item (D5.2) in that item, its surface drawn by the "
      "window's frame driver." },
    { "composite_set", composite_set, METH_VARARGS,
      "(handle, config_json) -> None: rect, coverage ({rect, radius} or null), quarters, pattern, visible, opacity; "
      "missing keys keep their values." },
    { "composite_state", composite_state, METH_VARARGS,
      "(handle) -> JSON str: the item's configuration, its node's last sync and draws, its surface." },
    { "composite_destroy", composite_destroy, METH_VARARGS,
      "(handle) -> bool: deletes the item (False when its parent deleted it first)." },
    { "composite_live", composite_live, METH_NOARGS,
      "() -> JSON str: composite items, surfaces and their QRhi objects alive in the process, Spectrum sources and "
      "their QRhi objects." },
    { "composite_update", composite_update, METH_VARARGS,
      "(handle) -> None: asks Qt for a frame of the item (a wake's present request)." },
    { "composite_spectrum_bind", composite_spectrum_bind, METH_VARARGS,
      "(handle, mapping_name, reader_config_json='') -> None: the item draws Spectrum from this frame stream, read at "
      "its sync on the render thread (the previous stream retires); ValueError for a mapping that is not a frame "
      "buffer." },
    { "composite_spectrum_unbind", composite_spectrum_unbind, METH_VARARGS,
      "(handle) -> None: the stream retires at once; the render thread releases it at the next sync." },
    { "composite_spectrum_present", composite_spectrum_present, METH_VARARGS,
      "(handle, presentation_json) -> None: the card as shown (rendering/native/spectrum.py spectrum_presentation)." },
    { "composite_spectrum_program", composite_spectrum_program, METH_VARARGS,
      "(handle, qsb_bytes | None) -> None: the fragment pack (tools/regen_qrc.py --shaders; None: the compiled-in "
      "copy, a harness control); ValueError when it does not load or holds no SpectrumDraw." },
    { "composite_spectrum_settings", composite_spectrum_settings, METH_VARARGS,
      "(handle, settings_json) -> None: the Settings- and card-derived members by name; ValueError on an unknown name, "
      "a wrong size or a per-frame member." },
    { "composite_spectrum_drop", composite_spectrum_drop, METH_VARARGS,
      "(handle) -> None: the drop edge (R-184), applied by the next read." },
    { "composite_spectrum_head", composite_spectrum_head, METH_VARARGS,
      "(handle) -> dict | None: the bound stream's newest whole slot head; consumes nothing (D2's head read)." },
    { "composite_spectrum_state", composite_spectrum_state, METH_VARARGS,
      "(handle) -> JSON str: the stream, its reader, the card, syncs, accepted frames, records and draws." },
    { "composite_spectrum_wait_paused", composite_spectrum_wait_paused, METH_VARARGS,
      "(handle, timeout_ms) -> bool: the pause_in_copy hook: the bound reader is paused inside a copy." },
    { "composite_spectrum_retire", composite_spectrum_retire, METH_VARARGS,
      "(handle) -> None: the bound stream stores Retiring at once (any thread; D1); unbind releases it." },
    { "composite_spectrum_resume", composite_spectrum_resume, METH_VARARGS,
      "(handle) -> None: the pause_in_copy hook: the paused read goes on." },
    { "spectrum_block", spectrum_block, METH_VARARGS,
      "(record_bytes, presentation_json, qsb_bytes | None, settings_json) -> (bytes | None, facts JSON str): the "
      "SpectrumDraw block the native Spectrum uploads for this record, card and program (GPU-free; None when nothing "
      "is drawn, with the reason; facts' 'unfilled' names members no side filled)." },
    { "spectrum_block_layout", spectrum_block_layout, METH_VARARGS,
      "(qsb_bytes | None = None) -> JSON str: SpectrumDraw as the pack reflects it (size, binding, members) and the "
      "members the core fills per frame ('frame_members')." },
    { "composite_mode_bind", composite_mode_bind, METH_VARARGS,
      "(handle, mapping_name, schema_json, reader_config_json='') -> None: the item draws a generic mode (N2.9) from this "
      "frame stream, admitted by the mode's schema (its table, handed over), read at the item's sync on the render "
      "thread; ValueError for a refused schema, a program that cannot draw its records, or a mapping that is not a "
      "frame buffer." },
    { "composite_mode_card", composite_mode_card, METH_VARARGS,
      "(handle, card_json) -> None: the item as shown (rendering/native/mode.py mode_card), which the core's members "
      "read." },
    { "composite_mode_texture", composite_mode_texture, METH_VARARGS,
      "(handle, name, (width, height), pixels_bytes, mips=False, in_frame=False) -> None: the item's texture of that "
      "name (N4.a): RGBA8 rows top first, tight, copied once into the core and uploaded from the next record (mips "
      "generated on the GPU): by the device's job service where it has one (N3.8), else in the frame; in_frame is the "
      "harness control of the in-frame form. ValueError for a bad name, size or byte count, too many textures, or mips "
      "the program samples that it lacks." },
    { "composite_mode_texture_remove", composite_mode_texture_remove, METH_VARARGS,
      "(handle, name) -> None: the texture goes; the render thread releases it at the next record. KeyError when the "
      "item holds no such texture." },
    { "composite_mode_on_lost", composite_mode_on_lost, METH_VARARGS,
      "(handle, callable|None) -> None: N3.8, the owner's lost-texture edge: called on the GUI thread with the list of "
      "names once each is found lost (a node made again, a texture that could not be created)." },
    { "window_edges_self_test", window_edges_self_test, METH_NOARGS,
      "() -> JSON str: audit N38 M1, GPU-free: a window's frame count with two drivers' edges in each of two frames "
      "(edges seen, total): one per frame." },
    { "gpu_timer_ring_simulation", gpu_timer_ring_simulation, METH_VARARGS,
      "(ring, frames, lag, abandon) -> JSON str: R-223, GPU-free: the GPU timer's ring over frames whose results "
      "arrive lag edges late (< 0: never), with or without abandoning a slot unread longer than the ring "
      "({timed, results, busy, abandoned, ring_frames})." },
    { "job_counts", job_counts, METH_NOARGS,
      "() -> JSON str: N3.8, the job services' process-wide counts (services, threads, jobs queued and running, images "
      "held and their bytes, releases pending, wake-ups) and the windows' retiring images." },
    { "job_services_state", job_services_state, METH_VARARGS,
      "(with_log=False) -> JSON str: every device's job service (its QRhi's facts, counts, and the last jobs' times)." },
    { "job_services_wait_idle", job_services_wait_idle, METH_VARARGS,
      "(timeout_ms=5000) -> bool: a harness's wait (GIL released) until every job service has nothing queued, running "
      "or waiting for release." },
    { "job_service_self_test", job_service_self_test, METH_VARARGS,
      "(script_json) -> JSON str: N3.8's GPU-free test of the job service's thread, latch, cancellation and teardown "
      "under a scripted backend (tests/test_native_core_jobs.py)." },
    { "mode_core_members", mode_core_members, METH_NOARGS,
      "() -> JSON str: the core's conventions, the members it fills for every mode ([name, components, from_card])." },
    { "mode_core_values", mode_core_values, METH_VARARGS,
      "(name, card_json, (target_w, target_h)) -> list of float: the core member's numbers for this card and target "
      "(its own row's values); KeyError for a name the core does not fill." },
    { "composite_content_status", composite_content_status, METH_VARARGS,
      "(handle) -> (draws, failures, refused_run, failing) | None: the item's content health, read without JSON (the "
      "route's failure edge, N29 round 2 M4 and M5): records that drew, build failures, frames refused since the last "
      "drawn one, and whether a build failed with nothing recorded since. None when the item draws no mode." },
    { "composite_window_pixels", composite_window_pixels, METH_VARARGS,
      "(handle) -> (width, height) | None: the item's window's framebuffer, from Qt's swapchain or redirect target." },
    { "composite_mode_unbind", composite_mode_unbind, METH_VARARGS,
      "(handle) -> None: the mode's stream retires at once; the render thread releases it at the next sync." },
    { "composite_mode_program", composite_mode_program, METH_VARARGS,
      "(handle, program_json, packs, settings_json=None) -> None: the passes ({\"passes\": [{name, blend, samplers?: "
      "[{name, texture, filter, wrap, mips}]}]}) and one fragment pack each; with settings (else the ones given "
      "before) packed by name; ValueError when refused (an unbound, unknown or doubly bound sampler among the "
      "reasons)." },
    { "composite_mode_settings", composite_mode_settings, METH_VARARGS,
      "(handle, settings_json) -> None: the ModeSettings members by name; ValueError on an unknown name, a wrong size or "
      "an unfilled member." },
    { "composite_mode_drop", composite_mode_drop, METH_VARARGS,
      "(handle) -> None: the drop edge (R-184), applied by the next read." },
    { "composite_mode_head", composite_mode_head, METH_VARARGS,
      "(handle) -> dict | None: the mode stream's newest whole slot head; consumes nothing." },
    { "composite_mode_state", composite_mode_state, METH_VARARGS,
      "(handle) -> JSON str: the stream, its schema and reader, the program, the settings, syncs, records and draws." },
    { "composite_mode_retire", composite_mode_retire, METH_VARARGS,
      "(handle) -> None: the mode's stream stores Retiring at once (D1); unbind releases it. The owner's lost-texture "
      "listener goes with it (audit N38 L4; the GUI thread's call)." },
    { "composite_mode_still", composite_mode_still, METH_VARARGS,
      "(handle, still) -> None: N5.7a, the item draws as a still (no stream: its textures, settings and card are its "
      "frame; it records only when what it draws changed). ValueError while a stream is bound or when the program "
      "cannot be drawn so." },
    { "composite_mode_target_size", composite_mode_target_size, METH_VARARGS,
      "(handle, name, (w, h)) -> None: N3.1, an explicit-size scene target's size with no new program (Bubble's "
      "ambient target follows its card). ValueError for a target the program does not declare with an explicit size." },
    { "composite_mode_target_read", composite_mode_target_read, METH_VARARGS,
      "(handle) -> None: N3.1, harness: a readback of every scene target's readable texture at the next record." },
    { "composite_mode_target_pixels", composite_mode_target_pixels, METH_VARARGS,
      "(handle) -> list | None: N3.1, harness: the readback once complete, each {name, size, content, format, samples, "
      "data} (rows top first on every backend)." },
    { "composite_mode_mesh", composite_mode_mesh, METH_VARARGS,
      "(handle, name, declaration_json, vertices_bytes, instances_bytes | None) -> None: N3.2 (D15), an item's mesh "
      "(interleaved f32 records; declaration {\"vertices\": layout, \"instances\"?: layout}), copied once and uploaded "
      "once at the next record. ValueError when refused." },
    { "composite_mode_mesh_remove", composite_mode_mesh_remove, METH_VARARGS,
      "(handle, name) -> None: N3.2, the mesh goes (its buffers at the next record). KeyError when there is none." },
    { "composite_mode_image_size", composite_mode_image_size, METH_VARARGS,
      "composite_mode_image_size(handle, name, (w, h[, d])): N3.3, a storage image's size (made again at the next "
      "record)" },
    { "composite_mode_storage_read", composite_mode_storage_read, METH_VARARGS,
      "composite_mode_storage_read(handle): N3.3 harness, read every storage buffer and image back at the next record" },
    { "composite_mode_storage_data", composite_mode_storage_data, METH_VARARGS,
      "composite_mode_storage_data(handle) -> list | None: N3.3 harness, the storage readback once completed" },
    { "compute_control", compute_control, METH_VARARGS,
      "compute_control(json): N3.3 harness, the compute proofs' negative controls (write_as_read, single_pass, "
      "trigger_every_record, skip_storage_release)" },
    { "mesh_buffer_control", mesh_buffer_control, METH_VARARGS,
      "(controls_json) -> None: N3.2, harness: the proofs' negative controls (hide_draw_parameters, "
      "direct_first_instance, recreate_streams, skip_mesh_release, instances_past_used), process-wide." },
    { "mesh_buffer_arena_layout", mesh_buffer_arena_layout, METH_VARARGS,
      "([block sizes], alignment) -> ([offsets], size): D15 point 3's block arena layout (GPU-free)." },
    { "vulkan_device_facts", vulkan_device_facts, METH_VARARGS,
      "(vk_device_handle) -> dict: N3.2, the limits and draw features of a device the core created ({} otherwise)." },
    { "scene_target_control", scene_target_control, METH_VARARGS,
      "(name, value) -> None: harness content_at_top, one_pixel_bucket, oversize_viewport, skip_scissor (0/1), "
      "allocation_steps (0..32; 0: all)." },
    { "scene_sample_counts_control", scene_sample_counts_control, METH_VARARGS,
      "([counts]) -> None: N3.1, harness: sample counts taken out of every device's supported set (the clamp's "
      "negative control); [] restores them." },
    { "stage_control", stage_control, METH_VARARGS,
      "(name, on) -> bool: N3.4, harness: a D17 negative control by name (skip_blend_gate, blend_formats_missing, "
      "sample_shading_missing, transparency_first_sample, skip_bloom_prime, bloom_same_texture, skip_stage_release, "
      "skip_read_chain, time_defocus_draws, flush_defocus_draws, flush_defocus_before_gather, "
      "flush_defocus_between_draws, flush_defocus_after_sprites (OpenGL), device_without_independent_blend: read at the next device's "
      "creation); False for an unknown "
      "name. fail_allocation (texture/target sync) and fail_build (sampler/bindings/pipeline build or rebind) accept "
      "integer create-attempt ordinals (0: off), bounded by the stage limits." },
    { "scene_depth_prime_control", scene_depth_prime_control, METH_VARARGS,
      "(skip) -> None: N3.1, harness: the depth's rule C prime skipped (its negative control under synchronisation "
      "validation); False restores it." },
    { "scene_resolve_prime_control", scene_resolve_prime_control, METH_VARARGS,
      "(skip) -> None: N3.1 audit 2 (H1), harness: the resolves' prime before each run skipped (its negative control "
      "under synchronisation validation); False restores it." },
    { "scene_nearest_first_sample_control", scene_nearest_first_sample_control, METH_VARARGS,
      "(first_only) -> None: N3.1 (D14 point 10), harness: the nearest resolve takes sample 0 instead of the minimum "
      "(its negative control) in contents built after the call; False restores it." },
    { "scene_target_next_allocation", scene_target_next_allocation, METH_VARARGS,
      "((current_w, current_h), (needed_w, needed_h)) -> ((w, h), reason): D14's allocation rule (GPU-free)." },
    { "scene_target_viewport", scene_target_viewport, METH_VARARGS,
      "(y_up_in_framebuffer, (alloc_w, alloc_h), (content_w, content_h)) -> (x, y, w, h): D14's content viewport in "
      "QRhi's convention (GPU-free)." },
    { "scene_target_clamp", scene_target_clamp, METH_VARARGS,
      "([supported counts], requested) -> int: D14's sample clamp (GPU-free)." },
    { "mode_blocks", mode_blocks, METH_VARARGS,
      "(schema_json, program_json, packs, settings_json, record_bytes, card_json | None, (target_w, target_h)) -> "
      "([block bytes per pass], facts JSON str): what a generic mode uploads for this record (GPU-free); ValueError "
      "with the reason when refused (an unknown or unfilled member, a name with two owners, a field that does not "
      "fit, a value with no defined conversion)." },
    { "mode_program_layout", mode_program_layout, METH_VARARGS,
      "(program_json, packs) -> JSON str: the program's passes, blends, uv inputs, samplers and reflected blocks." },
    { "program_block_pack", program_block_pack, METH_VARARGS,
      "(qsb_bytes, block_name, values_json) -> (bytes, facts JSON str): one reflected block packed by name (GPU-free; "
      "facts: layout, unfilled); ValueError when a value is refused." },
    { "packet_reader_open", packet_reader_open, METH_VARARGS,
      "(mapping_name, config_json='', schema_json='') -> int handle: the core's reader of a frame stream on its own view "
      "of the named mapping (D1); config: expect (the stream's identity), controls (negative controls); schema: a "
      "generic mode's table admitted beside the compiled ones (N2.9). A name that does not open gives a retired reader; "
      "a mapping that is not a frame buffer raises ValueError." },
    { "packet_reader_read", packet_reader_read, METH_VARARGS,
      "(handle) -> str: the consuming read at the frame edge (nothing, accepted, torn, stale, foreign, refused, failed, "
      "retiring, retired); an accepted frame is retained and acknowledged (D2)." },
    { "packet_reader_wait_paused", packet_reader_wait_paused, METH_VARARGS,
      "(handle, timeout_ms) -> bool: the pause_in_copy hook (D1's close during copy): a read is paused inside its "
      "copy." },
    { "packet_reader_resume", packet_reader_resume, METH_VARARGS,
      "(handle) -> None: the pause_in_copy hook: the paused read goes on." },
    { "packet_reader_head", packet_reader_head, METH_VARARGS,
      "(handle) -> dict | None: the newest whole slot's head; consumes nothing (D2's head read)." },
    { "packet_reader_frame", packet_reader_frame, METH_VARARGS,
      "(handle) -> dict | None: the retained frame: its head, its record bytes and its fields decoded by the C++ table." },
    { "packet_reader_drop", packet_reader_drop, METH_VARARGS,
      "(handle) -> None: the drop edge, applied by the next read (no frame at or below the watermark comes back)." },
    { "packet_reader_retire", packet_reader_retire, METH_VARARGS,
      "(handle) -> None: retiring, at once; no copy starts after it (D1)." },
    { "packet_reader_release", packet_reader_release, METH_VARARGS,
      "(handle) -> None: the retire job: the retained frame and the reader's pin on its view go; retired." },
    { "packet_reader_state", packet_reader_state, METH_VARARGS,
      "(handle) -> JSON str: state, counters, the refusal, the liveness block (copies started and finished)." },
    { "packet_reader_close", packet_reader_close, METH_VARARGS,
      "(handle) -> JSON str: retires, releases and forgets the reader; its last state." },
    { "packet_reader_live", packet_reader_live, METH_NOARGS,
      "() -> JSON str: packet readers alive, views mapped, handles (lifecycle proofs)." },
    { "frame_schemas", frame_schemas, METH_NOARGS,
      "() -> JSON str: the frame ABI version, the mode codes and every native schema compiled in (fields, offsets, "
      "range rules, fingerprints)." },
    { "backdrop_create", backdrop_create, METH_VARARGS,
      "(parent_address, parked=False) -> (handle, item_address): a backdrop pyramid's item (a texture provider) in the "
      "QQuickItem at parent_address (N5.7b)." },
    { "backdrop_set", backdrop_set, METH_VARARGS,
      "(handle, json) -> None: {parked: bool (demand 0: every QRhi object goes), dimming: 0 to 1}." },
    { "backdrop_build", backdrop_build, METH_VARARGS,
      "(handle, readback=False) -> None: a build at the next frame (harness), with a readback of every level." },
    { "backdrop_levels", backdrop_levels, METH_VARARGS,
      "(handle) -> [(name, width, height, rgba bytes)] or None: the last readback's levels, once complete (taken)." },
    { "backdrop_state", backdrop_state, METH_VARARGS,
      "(handle) -> JSON str: parked, dimming, the node's last sync and the pyramid (builds, clears, reason, sizes)." },
    { "backdrop_destroy", backdrop_destroy, METH_VARARGS,
      "(handle) -> bool: deletes the item (its node and pyramid go on the render thread)." },
    { "backdrop_pyramid_sizes", backdrop_pyramid_sizes, METH_VARARGS,
      "(width, height) -> JSON str: the level sizes of a window (the Python pyramid_sizes) and the level names." },
    { nullptr, nullptr, 0, nullptr }
};

PyModuleDef moduleDef = {
    PyModuleDef_HEAD_INIT, "_srpss_native_core",
    "SRPSS native core: the product's native QRhi module (imported only by rendering.native).", -1, methods,
    nullptr, nullptr, nullptr, nullptr
};

} // namespace

PyMODINIT_FUNC PyInit__srpss_native_core(void)
{
    // The exact-Qt import guard (carried over from native/spike_p1): QRhi carries limited compatibility guarantees,
    // so refuse to run against any Qt other than the exact one this module was compiled for.
    if (std::strcmp(qVersion(), QT_VERSION_STR) != 0) {
        PyErr_Format(PyExc_ImportError, "_srpss_native_core was built for Qt %s but the process runs Qt %s",
                     QT_VERSION_STR, qVersion());
        return nullptr;
    }
    PyObject *module = PyModule_Create(&moduleDef);
    if (!module)
        return nullptr;
    if (PyModule_AddIntConstant(module, "ABI", SRPSS_NATIVE_CORE_ABI) < 0
        || PyModule_AddStringConstant(module, "QT_VERSION", QT_VERSION_STR) < 0
        || PyModule_AddStringConstant(module, "__version__", SRPSS_NATIVE_CORE_VERSION) < 0) {
        Py_DECREF(module);
        return nullptr;
    }
    return module;
}
