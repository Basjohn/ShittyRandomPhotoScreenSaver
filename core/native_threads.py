"""Native thread-pool policy for third-party libraries.

numpy's bundled OpenBLAS starts one worker thread per logical CPU when numpy is
imported. On Windows each of those threads commits its own ~32 MB buffer
(``VirtualAlloc(MEM_COMMIT)``) whether or not BLAS is ever used: about 700 MB
of private commit per process on the operator's 24-thread CPU, in the main
process and again in the ImageWorker (R-99). SRPSS's only BLAS use is tiny
vector math in Glass shatter physics, which OpenBLAS never parallelizes, so one
thread costs nothing.

OpenBLAS reads its thread count once, at library load, and only from the
environment; no API releases threads it has already started. This is therefore
the one sanctioned environment write for a third-party load-time setting (the
Qt render-loop bootstrap is the other precedent). It runs before numpy is
imported, and spawned worker processes inherit it.

Qt 6 scales and converts large ``QImage`` objects on a private pool
(``QGuiApplicationPrivate::qtGuiThreadPool``, at most 8 threads) whose idle
threads exit after 30 s. The wallpaper rotates every 40 s, so every image
created the pool's threads again. The NVIDIA OpenGL driver keeps ~70 KB of
per-thread state for every thread a process with a GL context ever creates and
never returns it, so that churn alone was ~43 MB/h of private commit (R-97).
``retain_qt_gui_pool_threads`` keeps the pool's bounded threads instead.
"""
from __future__ import annotations

import os
import sys

OPENBLAS_THREADS = "1"

# public: static class QThreadPool * __cdecl QGuiApplicationPrivate::qtGuiThreadPool(void)
_QT_GUI_POOL_ACCESSOR = "?qtGuiThreadPool@QGuiApplicationPrivate@@SAPEAVQThreadPool@@XZ"
# public: void __cdecl QThreadPool::setExpiryTimeout(int)
_QT_POOL_SET_EXPIRY = "?setExpiryTimeout@QThreadPool@@QEAAXH@Z"
# public: int __cdecl QThreadPool::expiryTimeout(void) const
_QT_POOL_GET_EXPIRY = "?expiryTimeout@QThreadPool@@QEBAHXZ"


def configure_native_thread_pools() -> None:
    """Size native BLAS pools before the first numpy import in this process."""

    os.environ["OPENBLAS_NUM_THREADS"] = OPENBLAS_THREADS


def _loaded_module(ctypes, name: str):
    """A Qt module this process has already loaded, found by handle, or None."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    handle = kernel32.GetModuleHandleW(name)
    return ctypes.WinDLL(name, handle=handle) if handle else None


def _qt_gui_pool_expiry_functions():
    """(pool pointer, getter, setter) for Qt's private image pool, or None."""

    import ctypes

    gui = _loaded_module(ctypes, "Qt6Gui.dll")
    core = _loaded_module(ctypes, "Qt6Core.dll")
    if gui is None or core is None:
        return None
    try:
        accessor = getattr(gui, _QT_GUI_POOL_ACCESSOR)
        set_expiry = getattr(core, _QT_POOL_SET_EXPIRY)
        get_expiry = getattr(core, _QT_POOL_GET_EXPIRY)
    except AttributeError:
        return None
    accessor.restype = ctypes.c_void_p
    accessor.argtypes = []
    set_expiry.restype = None
    set_expiry.argtypes = [ctypes.c_void_p, ctypes.c_int]
    get_expiry.restype = ctypes.c_int
    get_expiry.argtypes = [ctypes.c_void_p]
    pool = accessor()
    if not pool:
        return None
    return pool, get_expiry, set_expiry


def retain_qt_gui_pool_threads() -> bool:
    """Keep Qt's image-pool threads alive once created (after QGuiApplication exists).

    Only the idle expiry changes: the pool keeps its own maximum (8), so this is
    a bounded one-time cost instead of new threads on every image. Returns
    False, and changes nothing, when the Qt build does not export the pool.
    """

    if sys.platform != "win32":
        return False
    resolved = _qt_gui_pool_expiry_functions()
    if resolved is None:
        return False
    pool, get_expiry, set_expiry = resolved
    set_expiry(pool, -1)
    return get_expiry(pool) == -1


def qt_gui_pool_expiry_ms() -> int | None:
    """The private image pool's current idle expiry (diagnostics and tests)."""

    if sys.platform != "win32":
        return None
    resolved = _qt_gui_pool_expiry_functions()
    if resolved is None:
        return None
    pool, get_expiry, _set_expiry = resolved
    return int(get_expiry(pool))


__all__ = [
    "OPENBLAS_THREADS",
    "configure_native_thread_pools",
    "qt_gui_pool_expiry_ms",
    "retain_qt_gui_pool_threads",
]
