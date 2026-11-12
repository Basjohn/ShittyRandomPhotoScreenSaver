"""N0.6 round 6 helpers: a real Qt Quick window kept off screen by the project's invisible-window pattern
(tests/_invisible_windows.py: opacity 0, transparent for input, a tool window), and the Win32 reads that need no
visible pixel: the window's extended style, DWM calls and their HRESULTs, and PrintWindow(PW_RENDERFULLCONTENT),
which asks DWM for the window's own composed content rather than reading the screen.

Harness only. Nothing here is product code; the project's backdrop owner (core.windows.dwm_blur) is called, not
copied.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

GWL_EXSTYLE = -20
EXSTYLE_BITS = {"WS_EX_LAYERED": 0x00080000, "WS_EX_TRANSPARENT": 0x00000020, "WS_EX_TOOLWINDOW": 0x00000080,
                "WS_EX_NOREDIRECTIONBITMAP": 0x00200000, "WS_EX_TOPMOST": 0x00000008}
PW_RENDERFULLCONTENT = 0x00000002
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMSBT_TRANSIENTWINDOW = 3  # the system's Acrylic
SENTINEL = 0x5A

# The scene's three regions, as fractions of the window: nothing drawn (the window colour), opaque blue, and
# 50 percent red. Sampled at their centres. A 4 px square in the top-left corner animates so the window keeps
# presenting (a static scene renders once and stops); it is far from every sampled patch.
SCENE_QML = b"""
import QtQuick
Item {
    Rectangle { x: 0; y: parent.height / 2; width: parent.width / 2; height: parent.height / 2; color: "#0000ff" }
    Rectangle { x: parent.width / 2; y: 0; width: parent.width / 2; height: parent.height; color: "#80ff0000" }
    Rectangle {
        x: 0; y: 0; width: 4; height: 4
        SequentialAnimation on color {
            loops: Animation.Infinite
            ColorAnimation { to: "#00ff00"; duration: 250 }
            ColorAnimation { to: "#ff00ff"; duration: 250 }
        }
    }
}
"""
REGIONS = {"empty_top_left": (0.25, 0.25), "opaque_blue_bottom_left": (0.25, 0.75), "half_red_right": (0.75, 0.5)}


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class _MARGINS(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int), ("top", ctypes.c_int), ("bottom", ctypes.c_int)]


def _user32():
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetDC.restype = wintypes.HDC
    u.GetDC.argtypes = [wintypes.HWND]
    u.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    u.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    u.PrintWindow.restype = wintypes.BOOL
    return u


def _gdi32():
    g = ctypes.WinDLL("gdi32", use_last_error=True)
    g.CreateCompatibleDC.restype = wintypes.HDC
    g.CreateCompatibleDC.argtypes = [wintypes.HDC]
    g.CreateDIBSection.restype = wintypes.HBITMAP
    g.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]
    g.SelectObject.restype = wintypes.HGDIOBJ
    g.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    g.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    g.DeleteDC.argtypes = [wintypes.HDC]
    return g


def extended_style(hwnd: int) -> dict:
    value = int(_user32().GetWindowLongPtrW(wintypes.HWND(hwnd), GWL_EXSTYLE))
    return {"raw": value, **{name: bool(value & bit) for name, bit in EXSTYLE_BITS.items()}}


def client_size(hwnd: int) -> tuple[int, int]:
    rect = wintypes.RECT()
    _user32().GetClientRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    return rect.right - rect.left, rect.bottom - rect.top


def print_window(hwnd: int) -> dict:
    """PrintWindow(PW_RENDERFULLCONTENT) into a 32-bit top-down DIB pre-filled with a sentinel byte, so an alpha
    channel the call never wrote is visible as the sentinel. Returns the BGRA bytes and the size."""
    user32, gdi32 = _user32(), _gdi32()
    w, h = client_size(hwnd)
    if w <= 0 or h <= 0:
        return {"ok": False, "error": f"client size {w}x{h}"}
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    header = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(mem_dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    try:
        if not bitmap or not bits.value:
            return {"ok": False, "error": "CreateDIBSection failed"}
        ctypes.memset(bits, SENTINEL, w * h * 4)
        old = gdi32.SelectObject(mem_dc, bitmap)
        ok = bool(user32.PrintWindow(wintypes.HWND(hwnd), mem_dc, PW_RENDERFULLCONTENT))
        data = ctypes.string_at(bits, w * h * 4)
        gdi32.SelectObject(mem_dc, old)
        return {"ok": ok, "width": w, "height": h, "bgra": data}
    finally:
        if bitmap:
            gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)


def sample_bgra(data: bytes, w: int, h: int, fx: float, fy: float, half: int = 4) -> dict:
    """Mean RGBA of a (2 half + 1)^2 patch of BGRA bytes, and how many alpha bytes still hold the sentinel."""
    cx, cy = int(fx * w), int(fy * h)
    sums = [0, 0, 0, 0]
    sentinel = 0
    n = 0
    for y in range(max(0, cy - half), min(h, cy + half + 1)):
        for x in range(max(0, cx - half), min(w, cx + half + 1)):
            i = (y * w + x) * 4
            b, g, r, a = data[i], data[i + 1], data[i + 2], data[i + 3]
            sums[0] += r
            sums[1] += g
            sums[2] += b
            sums[3] += a
            sentinel += a == SENTINEL
            n += 1
    return {"rgba": [round(s / max(1, n), 1) for s in sums], "alpha_bytes_still_sentinel": sentinel, "patch": n}


def sample_qimage(image, fx: float, fy: float, half: int = 4) -> dict:
    from PySide6.QtGui import QImage

    img = image.convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = img.width(), img.height()
    data = bytes(img.constBits())[: img.bytesPerLine() * h]
    stride = img.bytesPerLine()
    cx, cy = int(fx * w), int(fy * h)
    sums = [0, 0, 0, 0]
    n = 0
    for y in range(max(0, cy - half), min(h, cy + half + 1)):
        for x in range(max(0, cx - half), min(w, cx + half + 1)):
            i = y * stride + x * 4
            for c in range(4):
                sums[c] += data[i + c]
            n += 1
    return {"rgba": [round(s / max(1, n), 1) for s in sums], "patch": n}


def save_bgra_png(data: bytes, w: int, h: int, path) -> None:
    from PySide6.QtGui import QImage

    image = QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32)  # BGRA bytes = ARGB32 on little-endian
    image.copy().save(str(path), "PNG")


def dwm_system_backdrop(hwnd: int) -> dict:
    """The DWM system backdrop (Acrylic, DWMSBT_TRANSIENTWINDOW) with the frame extended into the whole client
    area, as the plan box names it; the HRESULTs are the finding."""
    dwm = ctypes.WinDLL("dwmapi")
    margins = _MARGINS(-1, -1, -1, -1)
    extend = int(dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref(margins)))
    value = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
    backdrop = int(dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(value),
                                             ctypes.sizeof(value)))
    return {"DwmExtendFrameIntoClientArea_hresult": extend & 0xFFFFFFFF,
            "DwmSetWindowAttribute_SYSTEMBACKDROP_TYPE_hresult": backdrop & 0xFFFFFFFF}


def accent_glass(hwnd: int, repo_root) -> dict:
    """The project's own backdrop owner (AccentPolicy blur-behind, the Glass path, no tint values involved)."""
    import sys

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from core.windows.dwm_blur import enable_glass_blur

    return {"enable_glass_blur": bool(enable_glass_blur(hwnd))}


def pump(predicate, seconds: float) -> bool:
    """Process GUI events until predicate() or the bound runs out (harness only: a bounded wait on frames)."""
    from PySide6.QtCore import QCoreApplication, QEventLoop

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        QCoreApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        if predicate():
            return True
    return predicate()
