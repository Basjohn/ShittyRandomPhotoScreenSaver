"""Qt-free pixel-to-curated-factor mapping for Fullscreen Now Playing artwork handles.

A parent side gesture owns the actual artwork border. Take its factor and pixel size at
pointer-down, and use the frame's delta from the same origin for every intermediate sample.
The surrounding text can reflow independently without feeding back into the gesture.
"""
from __future__ import annotations

import math

from core.settings.fullscreen_overlays import SCALE_MAX, SCALE_MIN


def artwork_factor_after_frame_delta(start_factor: float, start_pixels: float, frame_delta: float) -> float:
    """Resulting authored axis factor (the canonical artwork scale domain), with no Qt dependency."""
    values = (start_factor, start_pixels, frame_delta)
    if not all(math.isfinite(float(value)) for value in values) or start_pixels <= 0.0:
        raise ValueError("Artwork resize requires a finite, positive starting size")
    desired = max(1.0, float(start_pixels) + float(frame_delta))
    return round(max(SCALE_MIN, min(SCALE_MAX, float(start_factor) * desired / float(start_pixels))), 4)


__all__ = ["artwork_factor_after_frame_delta"]
