"""Device-pixel geometry for the R-63 compatibility window (pure, Qt-free).

Qt sizes windows in whole logical pixels. At a fractional DPR a monitor's device
extent is often not a whole number of logical pixels (2560 px at 150% is
1706.67), so any logical rectangle rounds to a device rectangle that is a pixel
wider or narrower than the monitor: the shared edge then overshoots into the
neighbouring display (R-63 mixed-DPR follow-up). The window's native rectangle
is therefore derived here in device pixels from the real monitor and virtual
desktop rectangles: exactly the monitor, plus the R-63 overscan on one exterior
edge only.

The scene is then laid out on the window's on-desktop part (``visible_rect_in_window``),
which for the display window is exactly its monitor, so the wallpaper, startup
capture and widgets map 1:1 to the monitor's pixels instead of being stretched
over the off-screen overscan.

Rectangles are ``(left, top, right, bottom)`` in device pixels, right/bottom
exclusive (the Win32 ``RECT`` convention).
"""
from __future__ import annotations

import math

Rect = tuple[int, int, int, int]

# Exterior-edge preference, matching the logical R-63 policy: top, bottom,
# left, right; a display with no exterior edge falls back to top.
_EDGES = ("top", "bottom", "left", "right")


def _qt_round(value: float) -> int:
    """``qRound`` for non-negative values (half rounds up)."""
    return int(math.floor(value + 0.5))


def survives_logical_rounding(extent: int, dpr: float) -> bool:
    """True when Qt's whole-logical-pixel size maps back to exactly ``extent``.

    Qt derives the window's logical size by rounding the native extent and its
    surface size by scaling that back. For the axis that carries the overscan
    the two must agree, or Qt's idea of the surface differs from the real one
    by a pixel (vertically that shifts the whole scene by a pixel).
    """
    return _qt_round(_qt_round(extent / dpr) * dpr) == extent


def overscan_amount(extent: int, dpr: float) -> int:
    """Smallest overscan (>= 1 device px) whose extended extent Qt represents exactly."""
    for amount in range(1, 8):
        if survives_logical_rounding(extent + amount, dpr):
            return amount
    return max(1, math.ceil(dpr))


def compat_native_rect(monitor: Rect, virtual: Rect, dpr: float) -> Rect:
    """The R-63 window in device pixels: the monitor plus one exterior-edge overscan.

    Never exact cover (Windows would promote an exact-cover borderless window
    to Legacy Flip and flash); never extends past the monitor on any other
    edge, so a neighbouring display is never overdrawn.
    """
    left, top, right, bottom = monitor
    v_left, v_top, v_right, v_bottom = virtual
    width, height = right - left, bottom - top
    if width <= 0 or height <= 0 or dpr <= 0.0:
        raise ValueError(f"invalid monitor rectangle {monitor} at DPR {dpr}")
    exterior = {
        "top": top <= v_top,
        "bottom": bottom >= v_bottom,
        "left": left <= v_left,
        "right": right >= v_right,
    }
    edge = next((name for name in _EDGES if exterior[name]), "top")
    if edge in ("top", "bottom"):
        amount = overscan_amount(height, dpr)
    else:
        amount = overscan_amount(width, dpr)
    if edge == "top":
        return (left, top - amount, right, bottom)
    if edge == "bottom":
        return (left, top, right, bottom + amount)
    if edge == "left":
        return (left - amount, top, right, bottom)
    return (left, top, right + amount, bottom)


def visible_rect_in_window(window: Rect, virtual: Rect, dpr: float) -> tuple[float, float, float, float] | None:
    """The part of the window on the virtual desktop, in window logical coordinates.

    ``(x, y, width, height)``, or ``None`` when the window lies wholly off the
    desktop. The R-63 overscan sits off an exterior edge, so for the display
    window this is exactly its monitor; every value times ``dpr`` is a whole
    device pixel, so a scene laid out on it lands on the monitor's pixels. A
    window resized or moved elsewhere keeps all of its on-desktop area.
    """
    if dpr <= 0.0:
        raise ValueError(f"invalid DPR {dpr}")
    left, top = max(window[0], virtual[0]), max(window[1], virtual[1])
    right, bottom = min(window[2], virtual[2]), min(window[3], virtual[3])
    if right <= left or bottom <= top:
        return None
    return (
        (left - window[0]) / dpr,
        (top - window[1]) / dpr,
        (right - left) / dpr,
        (bottom - top) / dpr,
    )


__all__ = [
    "Rect",
    "compat_native_rect",
    "overscan_amount",
    "survives_logical_rounding",
    "visible_rect_in_window",
]
