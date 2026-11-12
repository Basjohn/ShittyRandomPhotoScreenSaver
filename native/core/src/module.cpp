// The SRPSS native core (D5.7): the product's CPython extension module (stable ABI, abi3). It links the same Qt DLLs
// PySide6 ships and talks to PySide6 objects only through raw pointers from shiboken6.getCppPointer(), so no
// shiboken-generated binding is needed (the P1 spike's binding approach, Native_Core_P1_Spike.md).
//
// Its one Python importer is rendering/native/ (loader.py), which checks what runtime_info() reports (the Qt
// versions, the ABI, the MSVC runtime the process loaded) and fails in one place with one reason. N2.1: no rendering
// yet; the host adapter's entry (host_attach) is a no-op behind which N2.2 builds the frame driver.
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "abi.h"
#include "host_adapter.h"

#include <QtCore/QObject>
#include <QtCore/QString>
#include <QtCore/QtGlobal>

#include <cstring>
#include <iterator>

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
                               L"python3.dll" };
    for (const wchar_t *name : names) {
        const QString path = loadedModulePath(name);
        const QByteArray key = QString::fromWCharArray(name).toUtf8();
        put(paths, key.constData(), path.isEmpty() ? (Py_INCREF(Py_None), Py_None) : pyStr(path));
    }
    put(d, "loaded_modules", paths);
    return d;
}

// ---------------------------------------------------------------- the host adapter (D5.1)

PyObject *host_attach(PyObject *, PyObject *args)
{
    const char *kindText = nullptr;
    unsigned long long address = 0;
    if (!PyArg_ParseTuple(args, "sK", &kindText, &address))
        return nullptr;
    srpss_core::HostKind kind;
    if (!srpss_core::parseHostKind(kindText, &kind)) {
        PyErr_Format(PyExc_ValueError, "unknown host kind '%s' (the hosts are 'window' and 'hidden')", kindText);
        return nullptr;
    }
    if (address == 0) {
        PyErr_SetString(PyExc_ValueError, "no window: a host hands over its QQuickWindow");
        return nullptr;
    }
    QObject *object = reinterpret_cast<QObject *>(static_cast<quintptr>(address));
    if (!srpss_core::attachHost(kind, object)) {
        PyErr_SetString(PyExc_TypeError, "a host hands over a QQuickWindow; this object is not one");
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyMethodDef methods[] = {
    { "runtime_info", runtime_info, METH_NOARGS,
      "() -> dict: version, ABI, the compiled and running Qt, the compiler, the loaded Qt and MSVC runtime DLLs." },
    { "host_attach", host_attach, METH_VARARGS,
      "(kind 'window'|'hidden', quick_window_address) -> None: the host adapter's entry; a no-op until N2.2." },
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
