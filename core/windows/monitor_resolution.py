"""A display's resolution in device pixels, for anything shown to people.

Qt geometry is logical: a 2560x1440 monitor at 150% is 1706.67 logical pixels
wide, which Qt rounds to 1707. Layout stays logical (the saver and Arrange both
place widgets in Qt logical pixels, from ``QScreen.geometry()``); only
resolution text needs the monitor's own device size. It is read on demand from
the screen's HMONITOR, the same ``rcMonitor`` the saver's window placement uses
(``rendering/quick/window.py``), never derived from the rounded logical size.
"""
from __future__ import annotations

import sys
from typing import Any


def screen_device_size(screen: Any) -> tuple[int, int] | None:
    """The monitor's width/height in device pixels, or None when unavailable."""

    if sys.platform != "win32" or screen is None:
        return None
    try:
        handle = int(screen.nativeInterface().handle())
    except Exception:
        return None
    if not handle:
        return None
    import ctypes
    from ctypes import wintypes

    class _MonitorInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.windll.user32
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(_MonitorInfo)
    if not user32.GetMonitorInfoW(wintypes.HANDLE(handle), ctypes.byref(info)):
        return None
    rect = info.rcMonitor
    width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
    return (width, height) if width > 0 and height > 0 else None


def describe_screen_resolution(screen: Any) -> str:
    """``2560 × 1440 · 150%``: the resolution Windows shows, and its scale."""

    ratio = float(screen.devicePixelRatio() or 1.0)
    size = screen_device_size(screen)
    if size is None:
        geometry = screen.geometry()
        # Off Windows the device size is only known to rounding; say so.
        return f"≈{round(geometry.width() * ratio)} × {round(geometry.height() * ratio)} · {round(ratio * 100)}%"
    return f"{size[0]} × {size[1]} · {round(ratio * 100)}%"


__all__ = ["describe_screen_resolution", "screen_device_size"]
