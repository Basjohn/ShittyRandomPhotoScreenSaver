// The SRPSS native core (D5.7): the product's CPython extension module (stable ABI, abi3). It links the same Qt DLLs
// PySide6 ships and talks to PySide6 objects only through raw pointers from shiboken6.getCppPointer(), so no
// shiboken-generated binding is needed (the P1 spike's binding approach, Native_Core_P1_Spike.md).
//
// Its one Python importer is rendering/native/ (loader.py and hosts.py), which checks what runtime_info() reports (the
// Qt versions, the ABI, the MSVC runtime the process loaded) and fails in one place with one reason. N2.2: the host
// adapter (host_adapter.h: the Qt Quick window host and the hidden host) and the frame driver behind it
// (frame_driver.h), the module's Vulkan instance and devices (vulkan_context.h), and the probe pass a harness switches
// on (probe_pass.h). Nothing in the product calls them yet (N2.7 adds the backend owner).
//
// Every entry runs on the GUI thread. The ones that wait for the hidden host's render thread release the GIL while
// they wait; the render thread itself never takes it (D5.4).
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "abi.h"
#include "host_adapter.h"
#include "process_counters.h"
#include "vulkan_context.h"

#include <QtCore/QHash>
#include <QtCore/QJsonDocument>
#include <QtCore/QObject>
#include <QtCore/QString>
#include <QtCore/QtGlobal>
#include <QtQuick/QQuickItem>

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
    if (!PyArg_ParseTuple(args, "s|Kiip", &kindText, &address, &width, &height, &threaded))
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
        created = srpss_core::HiddenHost::create(width, height, threaded != 0, &error);
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

PyObject *live_hosts(PyObject *, PyObject *)
{
    return PyLong_FromLongLong(hosts().live.size());
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
      "(kind 'window', quick_window_address) | ('hidden', 0, width, height, threaded=True) -> int handle: a host "
      "with its frame driver attached (D5.1, D5.2)." },
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
    { "live_hosts", live_hosts, METH_NOARGS, "() -> int: hosts not closed." },
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
