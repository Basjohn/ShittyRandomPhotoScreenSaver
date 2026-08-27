"""Windows DWM acrylic blur-behind for translucent dialogs.

This module is the Windows platform adapter for Settings acrylic. It owns how
SRPSS talks to DWM; callers own the visual request: whether acrylic is enabled,
its tint colour, and its tint strength.

Uses the undocumented SetWindowCompositionAttribute API to enable acrylic blur
behind a window. Works on Windows 10 1803+ and Windows 11.

Falls back gracefully (no blur) on unsupported platforms or if the API call
fails.
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


def _validate_byte(name: str, value: int) -> int:
    """Return one validated 8-bit integer channel."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int in 0..255")
    if value < 0 or value > 255:
        raise ValueError(f"{name} must be in 0..255, got {value}")
    return value


def _pack_abgr(r: int, g: int, b: int, a: int) -> int:
    """Pack validated RGBA channels into ABGR uint32 for GradientColor."""
    r = _validate_byte("r", r)
    g = _validate_byte("g", g)
    b = _validate_byte("b", b)
    a = _validate_byte("a", a)
    return (a << 24) | (b << 16) | (g << 8) | r


def enable_acrylic_blur(
    hwnd: int,
    *,
    tint_r: int,
    tint_g: int,
    tint_b: int,
    tint_alpha: int,
) -> bool:
    """Enable acrylic blur-behind on a window.

    The caller must provide the complete visual request. This platform adapter
    intentionally has no SRPSS theme defaults.

    Args:
        hwnd: Native window handle (HWND).
        tint_r/g/b: RGB tint colour overlaid on the blur (0-255).
        tint_alpha: Tint strength (1-255). Higher values produce a more opaque
            tint and reveal less of the background through the acrylic.

    Returns:
        True if acrylic was enabled, False on unsupported platforms or if the
        native API call fails.

    Raises:
        TypeError: If a tint channel is not an integer.
        ValueError: If a tint channel is outside 0..255, or if tint_alpha is
            zero. Use :func:`disable_blur` when acrylic should be off.
    """
    tint_r = _validate_byte("tint_r", tint_r)
    tint_g = _validate_byte("tint_g", tint_g)
    tint_b = _validate_byte("tint_b", tint_b)
    tint_alpha = _validate_byte("tint_alpha", tint_alpha)
    if tint_alpha == 0:
        raise ValueError(
            "tint_alpha=0 is not a supported acrylic-off state; "
            "use disable_blur(hwnd)"
        )

    if sys.platform != "win32":
        logger.debug("Acrylic blur unavailable (not Windows)")
        return False

    try:
        user32 = ctypes.windll.user32
        set_wca = user32.SetWindowCompositionAttribute
        set_wca.restype = ctypes.c_bool
        set_wca.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA),
        ]

        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2  # ACCENT_FLAG_DRAW_ALL
        accent.GradientColor = _pack_abgr(
            tint_r,
            tint_g,
            tint_b,
            tint_alpha,
        )
        accent.AnimationId = 0

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        ok = set_wca(hwnd, ctypes.byref(data))
        if ok:
            logger.info(
                "Acrylic blur enabled (tint rgba(%d,%d,%d,%d))",
                tint_r,
                tint_g,
                tint_b,
                tint_alpha,
            )
        else:
            logger.warning(
                "SetWindowCompositionAttribute returned False – acrylic not applied"
            )
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
        set_wca.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.POINTER(_WINDOWCOMPOSITIONATTRIBDATA),
        ]

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
