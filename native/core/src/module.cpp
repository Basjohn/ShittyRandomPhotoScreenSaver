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
#include "composite.h"
#include "host_adapter.h"
#include "packet_reader.h"
#include "process_counters.h"
#include "spectrum.h"
#include "surfaces.h"
#include "vulkan_context.h"

#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtCore/QString>
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
    if (!PyArg_ParseTuple(args, "|p", &validation))
        return nullptr;
    return pyJson(srpss_core::vulkanInstanceCreateJson(validation != 0));
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
    item->presentSpectrum(presentation);
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
    srpss_core::SpectrumSource *source = spectrumOf(handle);
    if (!source)
        return nullptr;
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
    if (!PyArg_ParseTuple(args, "y#s#", &record, &recordLength, &config, &length))
        return nullptr;
    srpss_core::SpectrumPresentation presentation;
    QString error;
    if (!srpss_core::SpectrumPresentation::fromJson(QByteArray(config, qsizetype(length)), &presentation, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    QByteArray block;
    QJsonObject facts;
    QString reason;
    const bool drawn = srpss_core::spectrumBlock(QByteArray(record, qsizetype(recordLength)), presentation, &block,
                                                 &facts, &reason);
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

PyObject *spectrum_block_layout(PyObject *, PyObject *)
{
    return pyJson(srpss_core::SpectrumBlockLayout::instance().toJson());
}

// ---------------------------------------------------------------- the packet reader (N2.3: D1, D2, the transport rule)

struct Readers
{
    qint64 next = 1;
    QHash<qint64, srpss_core::PacketReader *> live;
};

Readers &readers()
{
    static Readers r;
    return r;
}

srpss_core::PacketReader *readerOf(long long handle)
{
    srpss_core::PacketReader *reader = readers().live.value(handle, nullptr);
    if (!reader)
        PyErr_Format(PyExc_KeyError, "no packet reader %lld (closed, or never created)", handle);
    return reader;
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
    }
    Py_RETURN_NONE;
}

quint32 elementBytes(srpss_core::frame_abi::FieldKind kind)
{
    using srpss_core::frame_abi::FieldKind;
    return kind == FieldKind::U32 ? 4u : kind == FieldKind::F64 ? 8u : 32u;
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
    if (!PyArg_ParseTuple(args, "s|s#", &name, &config, &length))
        return nullptr;
    srpss_core::PacketReaderConfig parsed;
    QString error;
    if (length && !srpss_core::PacketReaderConfig::fromJson(QByteArray(config, qsizetype(length)), &parsed, &error)) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    srpss_core::PacketReader *reader = srpss_core::PacketReader::open(QString::fromUtf8(name), parsed, &error);
    if (!reader) {
        PyErr_SetString(PyExc_ValueError, error.toUtf8().constData());
        return nullptr;
    }
    const qint64 handle = readers().next++;
    readers().live.insert(handle, reader);
    return PyLong_FromLongLong(handle);
}

PyObject *packet_reader_read(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    srpss_core::ReadResult result = srpss_core::ReadResult::Nothing;
    if (reader->pausesInCopy()) {
        // The D1 hook holds the read until another Python thread resumes it (that thread never closes this handle).
        Py_BEGIN_ALLOW_THREADS
        result = reader->read();
        Py_END_ALLOW_THREADS
    } else {
        result = reader->read();
    }
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
    srpss_core::PacketReader *reader = readerOf(handle);
    if (!reader)
        return nullptr;
    reader->resume();
    Py_RETURN_NONE;
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
    srpss_core::PacketReader *reader = readers().live.take(handle);
    if (!reader) {
        PyErr_Format(PyExc_KeyError, "no packet reader %lld (closed, or never created)", handle);
        return nullptr;
    }
    reader->retire();
    reader->release();
    const QJsonObject state = reader->stateJson();
    delete reader;
    return pyJson(state);
}

PyObject *packet_reader_live(PyObject *, PyObject *)
{
    QJsonObject o = srpss_core::PacketReader::liveJson();
    o.insert(QStringLiteral("handles"), int(readers().live.size()));
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
    static const char *kinds[] = { "u32", "f64", "f64x4" };
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
      "(record_bytes, presentation_json) -> (bytes | None, facts JSON str): the SpectrumDraw block the native "
      "Spectrum uploads for this record and card (GPU-free; None when nothing is drawn, with the reason)." },
    { "spectrum_block_layout", spectrum_block_layout, METH_NOARGS,
      "() -> JSON str: SpectrumDraw as the baked spectrum.frag reflects it (size, binding, members)." },
    { "packet_reader_open", packet_reader_open, METH_VARARGS,
      "(mapping_name, config_json='') -> int handle: the core's reader of a frame stream on its own view of the named "
      "mapping (D1); config: expect (the stream's identity), controls (negative controls). A name that does not open "
      "gives a retired reader; a mapping that is not a frame buffer raises ValueError." },
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
