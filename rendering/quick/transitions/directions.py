"""Resolved mesh-transition direction vectors (pure; no GL).

Screen convention: x right, y down. Shared by the GL renderers and by build-time
geometry work that must reproduce a renderer's motion off the render thread.
"""
from __future__ import annotations

import math

_DIRECTIONS = {
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "up": (0.0, -1.0), "down": (0.0, 1.0),
    "diag_tl_br": (1.0, 1.0), "diag_tr_bl": (-1.0, 1.0),
    "diag_bl_tr": (1.0, -1.0), "diag_br_tl": (-1.0, -1.0),
}


def direction_vector(direction: object) -> tuple[float, float]:
    value = _DIRECTIONS.get(str(direction))
    if value is None:
        raise ValueError(f"unresolved mesh transition direction: {direction!r}")
    length = math.hypot(*value)
    return value[0] / length, value[1] / length
