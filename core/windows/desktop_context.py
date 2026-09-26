"""Windows desktop identity checks for attended account setup."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Protocol

_UOI_NAME = 2


class DesktopWin32(Protocol):
    def current_thread_desktop_name(self) -> str | None: ...


class _NativeDesktopWin32:
    """Small adapter around the exact desktop APIs, isolated for fake-Win32 tests."""

    def current_thread_desktop_name(self) -> str | None:
        if not hasattr(ctypes, "WinDLL"):
            return None
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_current_thread_id = kernel32.GetCurrentThreadId
        get_current_thread_id.restype = wintypes.DWORD
        get_thread_desktop = user32.GetThreadDesktop
        get_thread_desktop.argtypes = [wintypes.DWORD]
        get_thread_desktop.restype = wintypes.HANDLE
        get_user_object_information = user32.GetUserObjectInformationW
        get_user_object_information.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_user_object_information.restype = wintypes.BOOL

        desktop = get_thread_desktop(get_current_thread_id())
        if not desktop:
            return None
        needed = wintypes.DWORD(0)
        get_user_object_information(desktop, _UOI_NAME, None, 0, ctypes.byref(needed))
        if not needed.value:
            return None
        buffer = ctypes.create_unicode_buffer(max(1, needed.value // ctypes.sizeof(ctypes.c_wchar)))
        if not get_user_object_information(
            desktop, _UOI_NAME, buffer, ctypes.sizeof(buffer), ctypes.byref(needed)
        ):
            return None
        return buffer.value


def is_interactive_user_desktop(win32: DesktopWin32 | None = None) -> bool:
    """Return True only when this thread is attached to the user's ``Default`` desktop.

    Unknown desktop state is intentionally denied.  This is independent of the
    process launch mode and never consults environment variables.
    """
    api = win32 or _NativeDesktopWin32()
    try:
        return api.current_thread_desktop_name() == "Default"
    except Exception:
        return False
