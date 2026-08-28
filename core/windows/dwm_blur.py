"""Windows composition backdrops for translucent Settings dialogs.

This module is the Windows platform adapter for Settings native backdrop
materials. Callers own the visual request; this module owns the exact Windows
composition mechanics.

Both visual materials deliberately use SetWindowCompositionAttribute's
AccentPolicy path. Settings is a Qt WA_TranslucentBackground top-level widget,
which Windows presents as a layered HWND; keeping both materials on the same
layered-window composition family avoids mixing that surface with DWM system
backdrop/redirection-bitmap state.

Theme-facing materials:

* Acrylic: ACCENT_ENABLE_ACRYLICBLURBEHIND with the theme's native tint.
* Glass: ACCENT_ENABLE_BLURBEHIND with no native tint; Qt semantic surfaces
  own the Glass colour and opacity.
* Off: ACCENT_DISABLED.

ACCENT_ENABLE_BLURBEHIND is an undocumented AccentPolicy state. It is distinct
from the documented DwmEnableBlurBehindWindow API whose Windows 8+ behavior is
different; do not conflate those two mechanisms.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

from core.logging.logger import get_logger

logger = get_logger(__name__)

# AccentPolicy states used by SetWindowCompositionAttribute.
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_BLURBEHIND = 3
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

_WCA_ACCENT_POLICY = 19
_ACCENT_FLAG_DRAW_ALL = 2


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


def enable_acrylic_blur(
    hwnd: int,
    *,
    tint_r: int,
    tint_g: int,
    tint_b: int,
    tint_alpha: int,
) -> bool:
    """Enable tintable Acrylic on the layered Settings HWND."""

    tint_r = _validate_byte("tint_r", tint_r)
    tint_g = _validate_byte("tint_g", tint_g)
    tint_b = _validate_byte("tint_b", tint_b)
    tint_alpha = _validate_byte("tint_alpha", tint_alpha)
    if tint_alpha == 0:
        raise ValueError(
            "tint_alpha=0 is not a supported Acrylic state; "
            "use disable_blur(hwnd) or the Glass backdrop instead"
        )

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


def enable_glass_blur(hwnd: int) -> bool:
    """Enable untinted Aero-style blur on the layered Settings HWND.

    Glass intentionally uses AccentPolicy state 3 with a fresh zeroed policy:
    no native GradientColor and no Acrylic tint/noise recipe. The Qt semantic
    surfaces already carry all theme-specific Glass RGB/alpha values.
    """

    ok = _apply_accent_policy(
        hwnd,
        accent_state=_ACCENT_ENABLE_BLURBEHIND,
    )
    if ok:
        logger.info(
            "Glass backdrop enabled via AccentPolicy blur-behind "
            "(state=3; Qt surfaces own tint/opacity)"
        )
    elif sys.platform == "win32":
        logger.warning("Glass backdrop was not applied")
    return ok


def disable_blur(hwnd: int) -> bool:
    """Disable the Settings AccentPolicy backdrop."""

    return _apply_accent_policy(
        hwnd,
        accent_state=_ACCENT_DISABLED,
    )


__all__ = [
    "disable_blur",
    "enable_acrylic_blur",
    "enable_glass_blur",
]
