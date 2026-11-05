"""Windows console display power notifications through one message-only window.

``RegisterPowerSettingNotification(GUID_CONSOLE_DISPLAY_STATE)`` makes Windows send
``WM_POWERBROADCAST`` / ``PBT_POWERSETTINGCHANGE`` to the registered window whenever the
console display turns off (0), on (1) or dims (2), and once immediately with the current
state. The window is message-only (``HWND_MESSAGE``): it has no pixels, takes no input,
sits on no desktop and does not depend on any display runtime generation, so it lives as
long as its process-scoped owner (``core.display_power.DisplayPowerAuthority``).

The notification is delivered on the thread that created the window, through that
thread's ordinary message pump (Qt's GUI event loop). Nothing here polls, waits or runs a
timer. Windows exposes no per-monitor equivalent: this is the console (session) display
state, which follows the power plan's "turn off the display" and the monitor-power
broadcast. A monitor switched off at its own button usually disappears from the topology
instead (handled by the display reconciler through binding loss).

Windows-only: callers select it with ``sys.platform == "win32"``; this module still
imports elsewhere because ctypes Windows symbols are resolved only when started.
"""
from __future__ import annotations

import ctypes
import itertools
import os
import sys
from collections.abc import Callable
from ctypes import wintypes

from core.logging.logger import get_logger

logger = get_logger(__name__)

WM_POWERBROADCAST = 0x0218
PBT_POWERSETTINGCHANGE = 0x8013
DEVICE_NOTIFY_WINDOW_HANDLE = 0x0
HWND_MESSAGE = -3

CONSOLE_DISPLAY_OFF = 0
CONSOLE_DISPLAY_ON = 1
CONSOLE_DISPLAY_DIMMED = 2

# Class names carry this prefix so diagnostics (tools/visualizer_live_check.py --display-off)
# can find this process's window and inject the real message through the real procedure.
WINDOW_CLASS_PREFIX = "SRPSSDisplayPower"

_instance_serial = itertools.count(1)


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(data1: int, data2: int, data3: int, data4: tuple[int, ...]) -> GUID:
    return GUID(data1, data2, data3, (ctypes.c_ubyte * 8)(*data4))


# {6FE69556-704A-47A0-8F24-C28D936FDA47}
GUID_CONSOLE_DISPLAY_STATE = _guid(0x6FE69556, 0x704A, 0x47A0, (0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47))


class POWERBROADCAST_SETTING(ctypes.Structure):
    """The fixed-size form of the payload Windows sends for a DWORD setting."""

    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", wintypes.DWORD),
        ("Data", wintypes.DWORD),
    ]


def display_state_payload(state: int, *, setting: GUID | None = None) -> POWERBROADCAST_SETTING:
    """The exact ``lParam`` structure Windows sends for a console display state (tests and probes)."""

    return POWERBROADCAST_SETTING(setting or GUID_CONSOLE_DISPLAY_STATE, 4, int(state))


def parse_console_display_state(wparam: int, lparam: int) -> int | None:
    """Return the console display state carried by one ``WM_POWERBROADCAST``, or None."""

    if int(wparam) != PBT_POWERSETTINGCHANGE or not lparam:
        return None
    setting = ctypes.cast(ctypes.c_void_p(int(lparam)), ctypes.POINTER(POWERBROADCAST_SETTING)).contents
    if bytes(setting.PowerSetting) != bytes(GUID_CONSOLE_DISPLAY_STATE) or setting.DataLength < 4:
        return None
    return int(setting.Data)


if sys.platform == "win32":
    _LRESULT = ctypes.c_ssize_t
    _WNDPROC = ctypes.WINFUNCTYPE(_LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class _WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", _WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]


def _user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = _LRESULT
    user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.RegisterPowerSettingNotification.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), wintypes.DWORD]
    user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
    user32.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
    return user32


class WindowsDisplayPowerNotifier:
    """Own one message-only window registered for the console display state."""

    name = "windows_console_display_state"

    def __init__(self, on_state: Callable[[int], None]) -> None:
        if not callable(on_state):
            raise TypeError("display power notifier needs a state callback")
        self._on_state = on_state
        self._hwnd = None
        self._registration = None
        self._class_name = f"{WINDOW_CLASS_PREFIX}_{os.getpid()}_{next(_instance_serial)}"
        self._instance = None
        self._wndproc = None          # the ctypes thunk must outlive the window
        self._user32 = None
        self.received = 0

    @property
    def hwnd(self) -> int:
        return int(self._hwnd or 0)

    @property
    def registered(self) -> bool:
        return bool(self._registration)

    def start(self) -> bool:
        if self._hwnd:
            return self.registered
        user32 = self._user32 = _user32()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self._instance = kernel32.GetModuleHandleW(None)
        self._wndproc = _WNDPROC(self._window_procedure)
        window_class = _WNDCLASSW()
        window_class.lpfnWndProc = self._wndproc
        window_class.hInstance = self._instance
        window_class.lpszClassName = self._class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            logger.warning("[DISPLAY_POWER] RegisterClassW failed error=%s", ctypes.get_last_error())
            self._wndproc = None
            return False
        hwnd = user32.CreateWindowExW(0, self._class_name, self._class_name, 0, 0, 0, 0, 0,
                                      wintypes.HWND(HWND_MESSAGE), None, self._instance, None)
        if not hwnd:
            logger.warning("[DISPLAY_POWER] Message window creation failed error=%s", ctypes.get_last_error())
            user32.UnregisterClassW(self._class_name, self._instance)
            self._wndproc = None
            return False
        self._hwnd = hwnd
        registration = user32.RegisterPowerSettingNotification(
            hwnd, ctypes.byref(GUID_CONSOLE_DISPLAY_STATE), DEVICE_NOTIFY_WINDOW_HANDLE)
        if not registration:
            logger.warning("[DISPLAY_POWER] RegisterPowerSettingNotification failed error=%s",
                           ctypes.get_last_error())
            self.close()
            return False
        self._registration = registration
        logger.info("[DISPLAY_POWER] Registered for console display state (hwnd=%#x)", int(hwnd))
        return True

    def close(self) -> None:
        user32 = self._user32
        if user32 is None:
            return
        registration, self._registration = self._registration, None
        if registration:
            if not user32.UnregisterPowerSettingNotification(registration):
                logger.warning("[DISPLAY_POWER] UnregisterPowerSettingNotification failed error=%s",
                               ctypes.get_last_error())
        hwnd, self._hwnd = self._hwnd, None
        if hwnd:
            user32.DestroyWindow(hwnd)
            user32.UnregisterClassW(self._class_name, self._instance)
            logger.info("[DISPLAY_POWER] Unregistered console display state (hwnd=%#x)", int(hwnd))
        self._wndproc = None
        self._user32 = None

    def _window_procedure(self, hwnd, message, wparam, lparam):
        if message == WM_POWERBROADCAST:
            try:
                state = parse_console_display_state(wparam, lparam)
                if state is not None:
                    self.received += 1
                    self._on_state(state)
                    return 1
            except Exception:
                # A window procedure must never raise into the native pump.
                logger.exception("[DISPLAY_POWER] Console display notification handling failed")
        return self._user32.DefWindowProcW(hwnd, message, wparam, lparam)


__all__ = [
    "CONSOLE_DISPLAY_DIMMED",
    "CONSOLE_DISPLAY_OFF",
    "CONSOLE_DISPLAY_ON",
    "GUID_CONSOLE_DISPLAY_STATE",
    "PBT_POWERSETTINGCHANGE",
    "POWERBROADCAST_SETTING",
    "WINDOW_CLASS_PREFIX",
    "WM_POWERBROADCAST",
    "WindowsDisplayPowerNotifier",
    "display_state_payload",
    "parse_console_display_state",
]
