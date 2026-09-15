"""Native best-effort thread scheduling contract used by background diagnostics/work.

Production SRPSS targets Windows. A caller that depends on demotion must fail
closed when ``applied`` is false on Windows; non-Windows callers may execute for
test portability but must not claim a native priority contract.
"""

from __future__ import annotations

import ctypes
import os


def apply_best_effort_thread_priority() -> tuple[bool, str, int | None]:
    """Demote the current Windows thread and disable dynamic priority boosts.

    Returns ``(applied, mode, native_priority)``. ``THREAD_PRIORITY_BELOW_NORMAL``
    is deliberately conservative: best-effort work remains able to complete while
    yielding scheduler preference to Qt Quick/render/input work. Disabling boost
    prevents a worker waking from a condition/event wait from being temporarily
    promoted back toward interactive priority.
    """

    if os.name != "nt":
        return False, "unsupported_non_windows", None

    try:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_current_thread = kernel32.GetCurrentThread
        get_current_thread.argtypes = []
        get_current_thread.restype = wintypes.HANDLE

        set_thread_priority = kernel32.SetThreadPriority
        set_thread_priority.argtypes = [wintypes.HANDLE, ctypes.c_int]
        set_thread_priority.restype = wintypes.BOOL

        set_thread_priority_boost = kernel32.SetThreadPriorityBoost
        set_thread_priority_boost.argtypes = [wintypes.HANDLE, wintypes.BOOL]
        set_thread_priority_boost.restype = wintypes.BOOL

        get_thread_priority = kernel32.GetThreadPriority
        get_thread_priority.argtypes = [wintypes.HANDLE]
        get_thread_priority.restype = ctypes.c_int

        thread_priority_below_normal = -1
        handle = get_current_thread()
        if not set_thread_priority(handle, thread_priority_below_normal):
            return False, f"set_priority_failed:{int(ctypes.get_last_error())}", None

        # bDisablePriorityBoost=TRUE.
        if not set_thread_priority_boost(handle, True):
            return False, f"disable_boost_failed:{int(ctypes.get_last_error())}", None

        current_priority = int(get_thread_priority(handle))
        return (
            current_priority == thread_priority_below_normal,
            "windows_below_normal_no_boost",
            current_priority,
        )
    except Exception as exc:  # pragma: no cover - Windows API failure path
        return False, f"priority_exception:{type(exc).__name__}", None


__all__ = ["apply_best_effort_thread_priority"]
