"""Windows composition backdrops for translucent Settings dialogs.

This module is the Windows platform adapter for Settings native backdrop
materials. Callers own the visual request; this module owns the exact Windows
composition mechanics.

Supported theme-facing materials:

* Acrylic: the existing tintable AccentPolicy Acrylic path.
* Glass: Windows 11 Desktop Acrylic via ``DWMWA_SYSTEMBACKDROP_TYPE`` /
  ``DWMSBT_TRANSIENTWINDOW``.
* Off: clears both modern system backdrop and legacy AccentPolicy state.

The old ``ACCENT_ENABLE_BLURBEHIND`` state is intentionally not used as the
Glass implementation. Microsoft documents the older blur-behind behavior as no
longer producing the intended blur beginning with Windows 8.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from core.logging.logger import get_logger

logger = get_logger(__name__)

# ── AccentState enum ────────────────────────────────────────────────
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

# ── WindowCompositionAttribute enum ────────────────────────────────
_WCA_ACCENT_POLICY = 19
_ACCENT_FLAG_DRAW_ALL = 2

# ── DWM window attributes / backdrop enum ──────────────────────────
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38

_DWMSBT_AUTO = 0
_DWMSBT_NONE = 1
_DWMSBT_MAINWINDOW = 2
_DWMSBT_TRANSIENTWINDOW = 3
_DWMSBT_TABBEDWINDOW = 4

_MIN_SYSTEM_BACKDROP_BUILD = 22621


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


def _windows_build() -> int:
    """Best-effort current Windows build, or zero off Windows."""

    if sys.platform != "win32":
        return 0
    try:
        return int(sys.getwindowsversion().build)
    except Exception:
        return 0


def _apply_accent_policy(
    hwnd: int,
    *,
    accent_state: int,
    accent_flags: int = 0,
    gradient_color: int = 0,
) -> bool:
    """Apply one fully prepared SetWindowCompositionAttribute AccentPolicy."""

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
        accent.AccentState = accent_state
        accent.AccentFlags = accent_flags
        accent.GradientColor = gradient_color
        accent.AnimationId = 0

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.Data = ctypes.addressof(accent)
        data.SizeOfData = ctypes.sizeof(accent)

        return bool(set_wca(hwnd, ctypes.byref(data)))
    except Exception:
        logger.debug("Failed to apply Windows AccentPolicy", exc_info=True)
        return False


def _set_dwm_int_attribute(hwnd: int, attribute: int, value: int) -> bool:
    """Set one integer-valued DWM window attribute."""

    if sys.platform != "win32":
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        setter = dwmapi.DwmSetWindowAttribute
        setter.restype = ctypes.c_long
        setter.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.wintypes.DWORD,
        ]

        native_value = ctypes.c_int(int(value))
        hr = setter(
            ctypes.wintypes.HWND(hwnd),
            ctypes.wintypes.DWORD(attribute),
            ctypes.byref(native_value),
            ctypes.wintypes.DWORD(ctypes.sizeof(native_value)),
        )
        return hr >= 0
    except Exception:
        logger.debug(
            "Failed to set DWM window attribute %d=%d",
            attribute,
            value,
            exc_info=True,
        )
        return False


def _clear_system_backdrop(hwnd: int) -> bool:
    """Clear the Windows 11 system backdrop when that API is available."""

    if _windows_build() < _MIN_SYSTEM_BACKDROP_BUILD:
        return False
    return _set_dwm_int_attribute(
        hwnd,
        _DWMWA_SYSTEMBACKDROP_TYPE,
        _DWMSBT_NONE,
    )


def enable_acrylic_blur(
    hwnd: int,
    *,
    tint_r: int,
    tint_g: int,
    tint_b: int,
    tint_alpha: int,
) -> bool:
    """Enable the existing tintable Acrylic AccentPolicy material."""

    tint_r = _validate_byte("tint_r", tint_r)
    tint_g = _validate_byte("tint_g", tint_g)
    tint_b = _validate_byte("tint_b", tint_b)
    tint_alpha = _validate_byte("tint_alpha", tint_alpha)
    if tint_alpha == 0:
        raise ValueError(
            "tint_alpha=0 is not a supported Acrylic state; "
            "use disable_blur(hwnd) or the Glass backdrop instead"
        )

    # Do not let a previously selected modern Glass backdrop remain under the
    # legacy Acrylic AccentPolicy when switching themes live.
    _clear_system_backdrop(hwnd)

    ok = _apply_accent_policy(
        hwnd,
        accent_state=_ACCENT_ENABLE_ACRYLICBLURBEHIND,
        accent_flags=_ACCENT_FLAG_DRAW_ALL,
        gradient_color=_pack_abgr(
            tint_r,
            tint_g,
            tint_b,
            tint_alpha,
        ),
    )
    if ok:
        logger.info(
            "Acrylic backdrop enabled (tint rgba(%d,%d,%d,%d))",
            tint_r,
            tint_g,
            tint_b,
            tint_alpha,
        )
    elif sys.platform == "win32":
        logger.warning("Acrylic backdrop was not applied")
    return ok


def enable_glass_blur(
    hwnd: int,
    *,
    tint_r: int,
    tint_g: int,
    tint_b: int,
    tint_alpha: int,
) -> bool:
    """Enable the supported Windows 11 whole-window frosted backdrop.

    Theme-facing ``Glass`` maps to ``DWMSBT_TRANSIENTWINDOW`` (Desktop
    Acrylic/background Acrylic). The native material owns blur/noise; semantic
    Qt surfaces above it own the theme's tint and opacity.

    On pre-22621 Windows, fall back to the already-proven tintable Acrylic path
    rather than invoking the obsolete state-3 blur path.
    """

    tint_r = _validate_byte("tint_r", tint_r)
    tint_g = _validate_byte("tint_g", tint_g)
    tint_b = _validate_byte("tint_b", tint_b)
    tint_alpha = _validate_byte("tint_alpha", tint_alpha)

    build = _windows_build()
    if build < _MIN_SYSTEM_BACKDROP_BUILD:
        fallback_alpha = max(1, tint_alpha)
        logger.info(
            "Modern Glass backdrop unavailable; falling back to Acrylic "
            "(Windows build %d)",
            build,
        )
        return enable_acrylic_blur(
            hwnd,
            tint_r=tint_r,
            tint_g=tint_g,
            tint_b=tint_b,
            tint_alpha=fallback_alpha,
        )

    # Clear any previously selected legacy AccentPolicy first. Mixing both
    # composition mechanisms is a good route to black/flickering surfaces.
    _apply_accent_policy(hwnd, accent_state=_ACCENT_DISABLED)

    # Keep the system material in dark presentation while Qt supplies the
    # actual semantic colour/tint on top.
    _set_dwm_int_attribute(
        hwnd,
        _DWMWA_USE_IMMERSIVE_DARK_MODE,
        1,
    )

    ok = _set_dwm_int_attribute(
        hwnd,
        _DWMWA_SYSTEMBACKDROP_TYPE,
        _DWMSBT_TRANSIENTWINDOW,
    )
    if ok:
        logger.info(
            "Glass backdrop enabled via Windows Desktop Acrylic "
            "(DWMSBT_TRANSIENTWINDOW)"
        )
    else:
        logger.warning("Windows Desktop Acrylic Glass backdrop was not applied")
    return ok


def disable_blur(hwnd: int) -> bool:
    """Disable both supported native backdrop mechanisms."""

    modern_cleared = _clear_system_backdrop(hwnd)
    accent_cleared = _apply_accent_policy(
        hwnd,
        accent_state=_ACCENT_DISABLED,
    )
    return modern_cleared or accent_cleared


__all__ = [
    "disable_blur",
    "enable_acrylic_blur",
    "enable_glass_blur",
]
