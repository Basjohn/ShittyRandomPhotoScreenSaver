// P1 spike: the CPython extension module (stable ABI, abi3) that our
// PySide6 process imports. It links the same Qt 6.11.2 DLLs PySide6 ships and
// talks to PySide6 objects only through raw pointers from
// shiboken6.getCppPointer(), so no shiboken-generated binding is needed.
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "gui_helpers.h"
#include "image_stats.h"
#include "quadfield.h"
#include "rhi_offscreen.h"
#include "thread_probe.h"
#include "vk_n06.h"

#ifdef SPIKE_WITH_QUICK
#include "quick_item.h"
#include "quick_offscreen.h"
#include <QtQuick/QQuickRenderControl>
#include <QtQuick/QQuickWindow>
#endif

#include <rhi/qrhi.h>

#include <QtCore/QHash>
#include <QtCore/QtGlobal>
#include <QtGui/QMatrix4x4>
#include <QtGui/QWindow>

#include <cstring>
#include <iterator>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

using namespace srpss_spike;

namespace {

ThreadProbe &hybridProbe()
{
    static ThreadProbe probe;
    return probe;
}

struct Registry
{
    qint64 next = 1;
    QHash<qint64, OffscreenRun *> runs;
    QHash<qint64, QuadField *> fields;
    QHash<qint64, OffscreenTarget> targets;
    QHash<qint64, QRhiReadbackResult *> readbacks;
};

Registry &registry()
{
    static Registry r;
    return r;
}

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

PyObject *pyFloatList(const QList<double> &values)
{
    PyObject *list = PyList_New(values.size());
    for (qsizetype i = 0; i < values.size(); ++i)
        PyList_SetItem(list, i, PyFloat_FromDouble(values.at(i)));
    return list;
}

PyObject *pyProbe(const ThreadProbe &p)
{
    PyObject *d = PyDict_New();
    put(d, "calls", PyLong_FromLong(p.calls.loadRelaxed()));
    put(d, "calls_on_gui_thread", PyLong_FromLong(p.callsOnGuiThread.loadRelaxed()));
    put(d, "calls_with_python_thread_state",
        PyLong_FromLong(p.callsWithPythonThreadState.loadRelaxed()));
    put(d, "last_thread_id", PyLong_FromUnsignedLongLong(p.lastThread.loadRelaxed()));
    return d;
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
    GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS
                           | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       reinterpret_cast<LPCWSTR>(&ownModulePath), &module);
    wchar_t buffer[MAX_PATH * 2];
    const DWORD n = GetModuleFileNameW(module, buffer, DWORD(std::size(buffer)));
    return QString::fromWCharArray(buffer, int(n));
}

template <typename T>
T *ptr(unsigned long long address)
{
    return reinterpret_cast<T *>(static_cast<quintptr>(address));
}

// ---------------------------------------------------------------- info

PyObject *runtime_info(PyObject *, PyObject *)
{
    PyObject *d = PyDict_New();
    put(d, "qt_compiled", PyUnicode_FromString(QT_VERSION_STR));
    put(d, "qt_runtime", PyUnicode_FromString(qVersion()));
    put(d, "msc_full_ver", PyLong_FromLong(_MSC_FULL_VER));
    put(d, "py_limited_api", PyLong_FromLong(Py_LIMITED_API));
#ifdef SPIKE_WITH_QUICK
    put(d, "with_quick", PyBool_FromLong(1));
#else
    put(d, "with_quick", PyBool_FromLong(0));
#endif
    put(d, "module_path", pyStr(ownModulePath()));
    PyObject *paths = PyDict_New();
    const wchar_t *names[] = { L"Qt6Core.dll", L"Qt6Gui.dll", L"Qt6Qml.dll", L"Qt6Quick.dll",
                               L"msvcp140.dll", L"vcruntime140.dll", L"vcruntime140_1.dll",
                               L"python3.dll", L"vulkan-1.dll", L"d3d11.dll", L"d3d12.dll" };
    for (const wchar_t *name : names) {
        const QString path = loadedModulePath(name);
        const QByteArray key = QString::fromWCharArray(name).toUtf8();
        put(paths, key.constData(), path.isEmpty() ? (Py_INCREF(Py_None), Py_None) : pyStr(path));
    }
    put(d, "loaded_modules", paths);
    return d;
}

// ---------------------------------------------------------------- part A

PyObject *offscreenResultDict(const OffscreenResult &r)
{
    PyObject *d = PyDict_New();
    put(d, "ok", PyBool_FromLong(r.ok));
    put(d, "error", pyStr(r.error));
    put(d, "backend", pyStr(r.backendName));
    put(d, "device", pyStr(r.deviceName));
    put(d, "frame_ms", pyFloatList(r.frameMs));
    put(d, "render_thread_id", PyLong_FromUnsignedLongLong(r.renderThread));
    put(d, "caller_thread_id", PyLong_FromUnsignedLongLong(r.callerThread));
    put(d, "frames_with_python_thread_state", PyLong_FromLong(r.framesWithPythonThreadState));
    put(d, "lit_pixels", PyLong_FromLong(r.litPixels));
    put(d, "pixel_checksum", PyLong_FromUnsignedLongLong(r.pixelChecksum));
    return d;
}

PyObject *rhi_offscreen_start(PyObject *, PyObject *args)
{
    const char *backend = nullptr;
    const char *png = nullptr;
    OffscreenRequest req;
    int gilPerFrame = 0;
    if (!PyArg_ParseTuple(args, "siiiis|p", &backend, &req.width, &req.height, &req.frames,
                          &req.instances, &png, &gilPerFrame))
        return nullptr;
    bool ok = false;
    req.backend = backendFromName(QString::fromUtf8(backend), &ok);
    if (!ok) {
        PyErr_SetString(PyExc_ValueError, "backend must be d3d11, d3d12, vulkan, opengl or null");
        return nullptr;
    }
    req.pngPath = QString::fromUtf8(png);
    req.gilPerFrame = gilPerFrame != 0;
    auto *run = new OffscreenRun(req);
    if (!run->start()) {
        const QByteArray err = run->result().error.toUtf8();
        delete run;
        PyErr_SetString(PyExc_RuntimeError, err.constData());
        return nullptr;
    }
    const qint64 handle = registry().next++;
    registry().runs.insert(handle, run);
    return PyLong_FromLongLong(handle);
}

PyObject *rhi_offscreen_done(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    OffscreenRun *run = registry().runs.value(handle);
    if (!run) {
        PyErr_SetString(PyExc_KeyError, "unknown run");
        return nullptr;
    }
    return PyBool_FromLong(run->isFinished());
}

PyObject *rhi_offscreen_join(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    OffscreenRun *run = registry().runs.take(handle);
    if (!run) {
        PyErr_SetString(PyExc_KeyError, "unknown run");
        return nullptr;
    }
    Py_BEGIN_ALLOW_THREADS
    run->wait();
    Py_END_ALLOW_THREADS
    PyObject *d = offscreenResultDict(run->result());
    delete run;
    return d;
}

// ---------------------------------------------------------------- hybrid
// A PySide6 QSGRenderNode subclass delegates prepare()/render() here, passing
// Qt Quick's own QRhi, command buffer and render target as raw pointers.

PyObject *hybrid_new(PyObject *, PyObject *args)
{
    int instances = 4096;
    if (!PyArg_ParseTuple(args, "|i", &instances))
        return nullptr;
    const qint64 handle = registry().next++;
    registry().fields.insert(handle, new QuadField(instances));
    return PyLong_FromLongLong(handle);
}

PyObject *hybrid_prepare(PyObject *, PyObject *args)
{
    long long handle = 0;
    unsigned long long rhiPtr = 0, cbPtr = 0, rtPtr = 0;
    const char *matrix = nullptr;
    Py_ssize_t matrixLen = 0;
    float time = 0.f, aspect = 1.f;
    if (!PyArg_ParseTuple(args, "LKKKy#ff", &handle, &rhiPtr, &cbPtr, &rtPtr, &matrix,
                          &matrixLen, &time, &aspect))
        return nullptr;
    QuadField *field = registry().fields.value(handle);
    if (!field || matrixLen != 16 * Py_ssize_t(sizeof(float))) {
        PyErr_SetString(PyExc_ValueError, "unknown node or matrix is not 16 floats");
        return nullptr;
    }
    hybridProbe().hit();
    QRhi *rhi = ptr<QRhi>(rhiPtr);
    QRhiCommandBuffer *cb = ptr<QRhiCommandBuffer>(cbPtr);
    QRhiRenderTarget *rt = ptr<QRhiRenderTarget>(rtPtr);
    float m[16];
    std::memcpy(m, matrix, sizeof(m));
    const QMatrix4x4 unitToClip = QMatrix4x4(m).transposed(); // column-major in, row-major ctor
    QRhiResourceUpdateBatch *updates = rhi->nextResourceUpdateBatch();
    const bool ok = field->ensure(rhi, rt->renderPassDescriptor(), rt->sampleCount(), updates);
    if (ok)
        field->update(updates, unitToClip, time, aspect);
    cb->resourceUpdate(updates);
    return PyBool_FromLong(ok);
}

PyObject *hybrid_render(PyObject *, PyObject *args)
{
    long long handle = 0;
    unsigned long long cbPtr = 0, rtPtr = 0;
    if (!PyArg_ParseTuple(args, "LKK", &handle, &cbPtr, &rtPtr))
        return nullptr;
    QuadField *field = registry().fields.value(handle);
    if (!field) {
        PyErr_SetString(PyExc_KeyError, "unknown node");
        return nullptr;
    }
    hybridProbe().hit();
    QRhiRenderTarget *rt = ptr<QRhiRenderTarget>(rtPtr);
    const QSize px = rt->pixelSize();
    field->record(ptr<QRhiCommandBuffer>(cbPtr),
                  QRhiViewport(0, 0, float(px.width()), float(px.height())));
    Py_RETURN_NONE;
}

PyObject *hybrid_release(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    QuadField *field = registry().fields.value(handle);
    if (field)
        field->release(); // the node may be prepared again later
    Py_RETURN_NONE;
}

PyObject *hybrid_free(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    delete registry().fields.take(handle);
    Py_RETURN_NONE;
}

PyObject *target_new(PyObject *, PyObject *args)
{
    unsigned long long rhiPtr = 0;
    int w = 0, h = 0;
    if (!PyArg_ParseTuple(args, "Kii", &rhiPtr, &w, &h))
        return nullptr;
    OffscreenTarget target;
    QString error;
    if (!createOffscreenTarget(ptr<QRhi>(rhiPtr), w, h, &target, &error)) {
        PyErr_SetString(PyExc_RuntimeError, error.toUtf8().constData());
        return nullptr;
    }
    const qint64 handle = registry().next++;
    registry().targets.insert(handle, target);
    return Py_BuildValue("(LK)", handle,
                         static_cast<unsigned long long>(quintptr(target.renderTarget)));
}

PyObject *target_free(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    OffscreenTarget target = registry().targets.take(handle);
    destroyOffscreenTarget(&target);
    Py_RETURN_NONE;
}

PyObject *readback_enqueue(PyObject *, PyObject *args)
{
    unsigned long long rhiPtr = 0, cbPtr = 0;
    long long targetHandle = 0;
    if (!PyArg_ParseTuple(args, "KKL", &rhiPtr, &cbPtr, &targetHandle))
        return nullptr;
    if (!registry().targets.contains(targetHandle)) {
        PyErr_SetString(PyExc_KeyError, "unknown target");
        return nullptr;
    }
    QRhi *rhi = ptr<QRhi>(rhiPtr);
    auto *result = new QRhiReadbackResult;
    QRhiResourceUpdateBatch *batch = rhi->nextResourceUpdateBatch();
    batch->readBackTexture(QRhiReadbackDescription(registry().targets.value(targetHandle).texture),
                           result);
    ptr<QRhiCommandBuffer>(cbPtr)->resourceUpdate(batch);
    const qint64 handle = registry().next++;
    registry().readbacks.insert(handle, result);
    return PyLong_FromLongLong(handle);
}

PyObject *readback_save(PyObject *, PyObject *args)
{
    long long handle = 0;
    const char *png = nullptr;
    int yUp = 0;
    if (!PyArg_ParseTuple(args, "Lsp", &handle, &png, &yUp))
        return nullptr;
    QRhiReadbackResult *result = registry().readbacks.take(handle);
    if (!result) {
        PyErr_SetString(PyExc_KeyError, "unknown readback");
        return nullptr;
    }
    const QImage image = imageFromReadback(result->data, result->pixelSize, yUp != 0);
    delete result;
    const ImageStats stats = imageStats(image);
    const bool saved = !image.isNull() && image.save(QString::fromUtf8(png), "PNG");
    PyObject *d = PyDict_New();
    put(d, "saved", PyBool_FromLong(saved));
    put(d, "width", PyLong_FromLong(stats.width));
    put(d, "height", PyLong_FromLong(stats.height));
    put(d, "lit_pixels", PyLong_FromLong(stats.litPixels));
    put(d, "pixel_checksum", PyLong_FromUnsignedLongLong(stats.checksum));
    return d;
}

PyObject *vulkan_attach(PyObject *, PyObject *args)
{
    unsigned long long windowPtr = 0;
    if (!PyArg_ParseTuple(args, "K", &windowPtr))
        return nullptr;
    // A QQuickWindow derives from QWindow alone, so the addresses coincide.
    QString error;
    if (!attachVulkanInstance(ptr<QWindow>(windowPtr), &error)) {
        PyErr_SetString(PyExc_RuntimeError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *probe_stats(PyObject *, PyObject *args)
{
    const char *which = "hybrid";
    if (!PyArg_ParseTuple(args, "|s", &which))
        return nullptr;
#ifdef SPIKE_WITH_QUICK
    if (std::strcmp(which, "native") == 0)
        return pyProbe(nativeNodeProbe());
#endif
    return pyProbe(hybridProbe());
}

PyObject *probe_reset(PyObject *, PyObject *)
{
    hybridProbe().reset();
#ifdef SPIKE_WITH_QUICK
    nativeNodeProbe().reset();
#endif
    Py_RETURN_NONE;
}

// ---------------------------------------------------------------- N0.6 (D6's proof)

PyObject *pyJson(const QByteArray &json)
{
    return PyUnicode_FromStringAndSize(json.constData(), json.size());
}

PyObject *n06_facts(PyObject *, PyObject *)
{
    // GUI thread, synchronous, keeps the GIL: Qt may log through a message handler a Python caller installed.
    return pyJson(n06VulkanFactsJson());
}

PyObject *n06_context_create(PyObject *, PyObject *args)
{
    int validation = 1;
    const char *queueMode = "one";
    const char *parts = "full";
    if (!PyArg_ParseTuple(args, "|pss", &validation, &queueMode, &parts))
        return nullptr;
    return pyJson(n06ContextCreateJson(validation != 0, QString::fromUtf8(queueMode), QString::fromUtf8(parts)));
}

PyObject *n06_handle_count(PyObject *, PyObject *)
{
    return PyLong_FromLongLong(n06HandleCount());
}

PyObject *n06_process_counters(PyObject *, PyObject *)
{
    return pyJson(n06ProcessCountersJson());
}

PyObject *n06_set_phase(PyObject *, PyObject *args)
{
    const char *phase = nullptr;
    if (!PyArg_ParseTuple(args, "s", &phase))
        return nullptr;
    n06SetPhase(QString::fromUtf8(phase));
    Py_RETURN_NONE;
}

PyObject *n06_context_destroy(PyObject *, PyObject *)
{
    return pyJson(n06ContextDestroyJson());
}

#ifdef SPIKE_WITH_QUICK
PyObject *n06_attach_window(PyObject *, PyObject *args)
{
    unsigned long long windowPtr = 0;
    int ours = 1;
    if (!PyArg_ParseTuple(args, "Kp", &windowPtr, &ours))
        return nullptr;
    QString error;
    if (!n06AttachQuickWindow(ptr<QQuickWindow>(windowPtr), ours != 0, &error)) {
        PyErr_SetString(PyExc_RuntimeError, error.toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *n06_window_surface(PyObject *, PyObject *args)
{
    unsigned long long windowPtr = 0;
    if (!PyArg_ParseTuple(args, "K", &windowPtr))
        return nullptr;
    return pyJson(n06WindowSurfaceJson(ptr<QQuickWindow>(windowPtr)));
}
#endif

// ---------------------------------------------------------------- part B

#ifdef SPIKE_WITH_QUICK
QHash<qint64, QuickOffscreenSession *> &sessions()
{
    static QHash<qint64, QuickOffscreenSession *> s;
    return s;
}

PyObject *quick_session_begin(PyObject *, PyObject *args)
{
    unsigned long long rcPtr = 0, windowPtr = 0;
    int w = 0, h = 0, threaded = 1;
    if (!PyArg_ParseTuple(args, "KKii|p", &rcPtr, &windowPtr, &w, &h, &threaded))
        return nullptr;
    auto *session = new QuickOffscreenSession(ptr<QQuickRenderControl>(rcPtr),
                                              ptr<QQuickWindow>(windowPtr), w, h, threaded != 0);
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = session->begin();
    Py_END_ALLOW_THREADS
    if (!ok) {
        const QByteArray err = session->error().toUtf8();
        Py_BEGIN_ALLOW_THREADS
        delete session;
        Py_END_ALLOW_THREADS
        PyErr_SetString(PyExc_RuntimeError, err.constData());
        return nullptr;
    }
    const qint64 handle = registry().next++;
    sessions().insert(handle, session);
    PyObject *d = PyDict_New();
    put(d, "handle", PyLong_FromLongLong(handle));
    put(d, "backend", pyStr(session->backendName()));
    put(d, "device", pyStr(session->deviceName()));
    put(d, "gui_thread_id", PyLong_FromUnsignedLongLong(session->guiThread()));
    put(d, "render_thread_id", PyLong_FromUnsignedLongLong(session->renderThread()));
    put(d, "vk_device", PyLong_FromUnsignedLongLong(session->vkDevice()));
    put(d, "vk_queue_family", PyLong_FromLong(session->vkQueueFamily()));
    put(d, "vk_queue_index", PyLong_FromLong(session->vkQueueIndex()));
    return d;
}

PyObject *quick_session_frames(PyObject *, PyObject *args)
{
    long long handle = 0;
    unsigned long long animatedPtr = 0;
    int count = 0;
    const char *png = "";
    if (!PyArg_ParseTuple(args, "LKi|s", &handle, &animatedPtr, &count, &png))
        return nullptr;
    QuickOffscreenSession *session = sessions().value(handle);
    if (!session) {
        PyErr_SetString(PyExc_KeyError, "unknown session");
        return nullptr;
    }
    const QString pngPath = QString::fromUtf8(png);
    QuickFramesResult r;
    Py_BEGIN_ALLOW_THREADS
    r = session->frames(ptr<QObject>(animatedPtr), count, pngPath);
    Py_END_ALLOW_THREADS
    PyObject *d = PyDict_New();
    put(d, "ok", PyBool_FromLong(r.ok));
    put(d, "error", pyStr(r.error));
    put(d, "frame_ms", pyFloatList(r.frameMs));
    put(d, "lit_pixels", PyLong_FromLong(r.litPixels));
    put(d, "pixel_checksum", PyLong_FromUnsignedLongLong(r.pixelChecksum));
    return d;
}

PyObject *quick_session_resize(PyObject *, PyObject *args)
{
    long long handle = 0;
    int w = 0, h = 0;
    if (!PyArg_ParseTuple(args, "Lii", &handle, &w, &h))
        return nullptr;
    QuickOffscreenSession *session = sessions().value(handle);
    if (!session) {
        PyErr_SetString(PyExc_KeyError, "unknown session");
        return nullptr;
    }
    bool ok = false;
    Py_BEGIN_ALLOW_THREADS
    ok = session->resize(w, h);
    Py_END_ALLOW_THREADS
    if (!ok) {
        PyErr_SetString(PyExc_RuntimeError, session->error().toUtf8().constData());
        return nullptr;
    }
    Py_RETURN_NONE;
}

PyObject *quick_session_end(PyObject *, PyObject *args)
{
    long long handle = 0;
    if (!PyArg_ParseTuple(args, "L", &handle))
        return nullptr;
    QuickOffscreenSession *session = sessions().take(handle);
    Py_BEGIN_ALLOW_THREADS
    delete session;
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}
#endif

PyMethodDef methods[] = {
    { "runtime_info", runtime_info, METH_NOARGS, "Qt versions, compiler and loaded DLL paths." },
    { "rhi_offscreen_start", rhi_offscreen_start, METH_VARARGS,
      "(backend, w, h, frames, instances, png[, gil_per_frame]) -> handle" },
    { "rhi_offscreen_done", rhi_offscreen_done, METH_VARARGS, "(handle) -> bool" },
    { "rhi_offscreen_join", rhi_offscreen_join, METH_VARARGS, "(handle) -> dict" },
    { "hybrid_new", hybrid_new, METH_VARARGS, "([instances]) -> handle" },
    { "hybrid_prepare", hybrid_prepare, METH_VARARGS,
      "(handle, rhi, cb, rt, matrix16f_bytes, time, aspect) -> bool" },
    { "hybrid_render", hybrid_render, METH_VARARGS, "(handle, cb, rt)" },
    { "hybrid_release", hybrid_release, METH_VARARGS, "(handle)" },
    { "hybrid_free", hybrid_free, METH_VARARGS, "(handle)" },
    { "target_new", target_new, METH_VARARGS, "(rhi, w, h) -> (handle, render_target_ptr)" },
    { "target_free", target_free, METH_VARARGS, "(handle)" },
    { "readback_enqueue", readback_enqueue, METH_VARARGS, "(rhi, cb, target) -> handle" },
    { "readback_save", readback_save, METH_VARARGS, "(handle, png, y_up) -> dict" },
    { "vulkan_attach", vulkan_attach, METH_VARARGS, "(window_ptr)" },
    { "probe_stats", probe_stats, METH_VARARGS, "(['hybrid'|'native']) -> dict" },
    { "probe_reset", probe_reset, METH_NOARGS, "()" },
    { "n06_facts", n06_facts, METH_NOARGS,
      "() -> JSON str: N0.6 round 1, Vulkan facts and Qt's own device (GUI thread, QGuiApplication)" },
    { "n06_context_create", n06_context_create, METH_VARARGS,
      "([validation=True[, queue_mode='one'|'second'|'force_absent']]) -> JSON str: N0.6 our VkInstance (adopted "
      "by Qt) and VkDevice, and a reference instance" },
    { "n06_handle_count", n06_handle_count, METH_NOARGS, "() -> int: the process handle count" },
    { "n06_process_counters", n06_process_counters, METH_NOARGS,
      "() -> JSON str: handles, GDI/USER objects, threads, private bytes, GPU heap usage" },
    { "n06_set_phase", n06_set_phase, METH_VARARGS, "(phase) attributes later debug messages to it" },
    { "n06_context_destroy", n06_context_destroy, METH_NOARGS,
      "() -> JSON str: teardown steps and the debug message counts per phase (windows destroyed first)" },
#ifdef SPIKE_WITH_QUICK
    { "n06_attach_window", n06_attach_window, METH_VARARGS,
      "(quick_window_ptr, ours) our instance + device, or the reference instance (Qt's own device)" },
    { "n06_window_surface", n06_window_surface, METH_VARARGS,
      "(quick_window_ptr) -> JSON str: the shown Vulkan window's surface capabilities (composite alpha, ...)" },
    { "quick_session_begin", quick_session_begin, METH_VARARGS,
      "(rc, window, w, h[, threaded]) -> dict with handle" },
    { "quick_session_frames", quick_session_frames, METH_VARARGS,
      "(handle, animated, count[, png]) -> dict" },
    { "quick_session_resize", quick_session_resize, METH_VARARGS, "(handle, w, h) new offscreen target size" },
    { "quick_session_end", quick_session_end, METH_VARARGS, "(handle)" },
#endif
    { nullptr, nullptr, 0, nullptr }
};

PyModuleDef moduleDef = {
    PyModuleDef_HEAD_INIT, "_srpss_native_spike",
    "SRPSS P1 spike: native QRhi rendering hosted by PySide6's Qt.", -1, methods,
    nullptr, nullptr, nullptr, nullptr
};

} // namespace

PyMODINIT_FUNC PyInit__srpss_native_spike(void)
{
    // QRhi carries limited compatibility guarantees: refuse to run against any
    // Qt other than the exact one this module was compiled for.
    if (std::strcmp(qVersion(), QT_VERSION_STR) != 0) {
        PyErr_Format(PyExc_ImportError,
                     "_srpss_native_spike was built for Qt %s but the process runs Qt %s",
                     QT_VERSION_STR, qVersion());
        return nullptr;
    }
#ifdef SPIKE_WITH_QUICK
    srpss_spike::registerQmlTypes(); // QML: import SrpssNativeSpike 1.0; QuadField {}
#endif
    return PyModule_Create(&moduleDef);
}
