"""Windows DWM acrylic blur-behind for translucent dialogs.

Uses the undocumented SetWindowCompositionAttribute API to enable
acrylic blur behind a window. Works on Windows 10 1803+ and Windows 11.

Falls back gracefully (no blur) on unsupported platforms or if the API
call fails.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from core.logging.logger import get_logger

logger = get_logger(__name__)

# ── AccentState enum ────────────────────────────────────────────────
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_GRADIENT = 1
_ACCENT_ENABLE_TRANSPARENTGRADIENT = 2
_ACCENT_ENABLE_BLURBEHIND = 3
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# ── WindowCompositionAttribute enum ────────────────────────────────
_WCA_ACCENT_POLICY = 19


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    ]


def _pack_abgr(r: int, g: int, b: int, a: int) -> int:
    """Pack RGBA into ABGR uint32 for GradientColor."""
    return ((a & 0xFF) << 24) | ((b & 0xFF) << 16) | ((g & 0xFF) << 8) | (r & 0xFF)


def enable_acrylic_blur(
    hwnd: int,
    tint_r: int = 24,
    tint_g: int = 24,
    tint_b: int = 24,
    tint_alpha: int = 80,
) -> bool:
    """Enable acrylic blur-behind on a window.

    Args:
        hwnd: Native window handle (HWND).
        tint_r/g/b: RGB tint colour overlaid on the blur (0-255).
        tint_alpha: Tint opacity (0-255). Higher = more opaque tint,
                    less background visible through blur.

    Returns:
        True if acrylic was enabled, False on failure.
    """
    if sys.platform != "win32":
        logger.debug("Acrylic blur unavailable (not Windows)")
        return False

    try:
        user32 = ctypes.windll.user32
        set_wca = user32.SetWindowCompositionAttribute
        set_wca.restype = ctypes.c_bool
        set_wca.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA)]

        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2  # ACCENT_FLAG_DRAW_ALL
        accent.GradientColor = _pack_abgr(tint_r, tint_g, tint_b, tint_alpha)
        accent.AnimationId = 0

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ok = set_wca(hwnd, ctypes.byref(data))
        if ok:
            logger.info("Acrylic blur enabled (tint rgba(%d,%d,%d,%d))",
                        tint_r, tint_g, tint_b, tint_alpha)
        else:
            logger.warning("SetWindowCompositionAttribute returned False – acrylic not applied")
        return bool(ok)

    except Exception:
        logger.debug("Failed to enable acrylic blur", exc_info=True)
        return False


def disable_blur(hwnd: int) -> bool:
    """Remove blur-behind from a window (restore default composition)."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        set_wca = user32.SetWindowCompositionAttribute
        set_wca.restype = ctypes.c_bool
        set_wca.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA)]

        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_DISABLED

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        return bool(set_wca(hwnd, ctypes.byref(data)))
    except Exception:
        logger.debug("Failed to disable blur", exc_info=True)
        return False
