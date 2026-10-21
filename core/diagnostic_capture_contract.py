"""Pure, one-shot diagnostic screen-capture geometry and build admission.

No Qt import, monitor polling, or runtime-lifetime owner lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re


@dataclass(frozen=True)
class CaptureRect:
    x: int
    y: int
    width: int
    height: int


def crop_pixels(
    logical_rect: tuple[float, float, float, float] | None,
    screen_origin: tuple[float, float],
    logical_screen_size: tuple[float, float],
    pixel_size: tuple[int, int],
) -> CaptureRect | None:
    """Clip a scene rectangle to the captured monitor using measured DPR per axis.

    QScreen.grabWindow(0) returns monitor pixels; the measured image dimensions
    are authoritative even when Qt reports a fractional or unexpected DPR.
    ``None`` means capture the entire display, not an invalid/empty crop.
    """
    if logical_rect is None:
        return None
    from math import ceil, floor, isfinite

    sx, sy = screen_origin
    lw, lh = logical_screen_size
    pw, ph = pixel_size
    x, y, w, h = logical_rect
    if not all(isfinite(float(v)) for v in (sx, sy, lw, lh, pw, ph, x, y, w, h)):
        return None
    if min(lw, lh, pw, ph, w, h) <= 0:
        return None
    kx, ky = pw / lw, ph / lh
    left = max(0, min(pw, floor((x - sx) * kx)))
    top = max(0, min(ph, floor((y - sy) * ky)))
    right = max(0, min(pw, ceil((x + w - sx) * kx)))
    bottom = max(0, min(ph, ceil((y + h - sy) * ky)))
    if left >= right or top >= bottom:
        return None
    return CaptureRect(left, top, right - left, bottom - top)


def capture_filename(*, moment: datetime, screen_index: int, region: str, suffix: int) -> str:
    safe = re.sub(r"[^a-z0-9_-]+", "-", str(region).lower()).strip("-")[:42] or "display"
    return (f"{moment:%Y-%m-%d_%H-%M-%S}_{moment.microsecond:06d}_"
            f"display{int(screen_index)}_{safe}_{int(suffix):x}.png")
