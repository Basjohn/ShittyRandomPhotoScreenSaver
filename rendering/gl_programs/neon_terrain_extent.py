"""Neon Lake terrain beyond its basin: the CPU mirror of the shader's continuation, and grid extension.

The authored grid may reach past the scene's basin toward the horizon (``heightfield_basin``). Extending it keeps
every existing cell exactly and fills the new cells with the continuation's heights, so the landforms keep their
shape (the new ground becomes ordinary authored land, with its detail and glow) until the user paints. Where the grid's edge is water, the continuation keeps it water outward: a stream
painted to the edge flows on to the horizon instead of stopping at rolling land.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from rendering.gl_programs.heightfield import (
    heightfield_basin, heightfield_grid_transform, normalize_heightfield, sample_heightfield,
)

# One Extend step: half the basin's depth further back, a quarter of its width on each side (square cells).
MAX_GRID_SIZE = 257


def _smoothstep(low: float, high: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - low) / (high - low)))
    return t * t * (3.0 - 2.0 * t)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sign(x: float) -> float:
    return (x > 0.0) - (x < 0.0)


def basin_continuation(data: Mapping, u: float, v: float) -> float:
    """Mirror of ``basinContinuation`` (neon_lake_basin_program) at basin uv; the authored height inside the grid."""
    left, front, scale = heightfield_grid_transform(data)
    gu, gv = (u + left) * scale, (v + front) * scale
    eu, ev = _clamp01(gu), _clamp01(gv)
    du, dv = gu - eu, gv - ev
    distance = math.hypot(du, dv) / scale
    boundary = sample_heightfield(data, eu, ev)
    if distance < 1e-6:
        return boundary
    if boundary == 0.0:
        return 0.0
    n = int(data["size"])
    interior = sample_heightfield(data, _clamp01(eu - _sign(du) / (n - 1)), _clamp01(ev - _sign(dv) / (n - 1)))
    slope = max(-0.8, min(0.8, (boundary - interior) * (n - 1) * scale))
    near_slope = 0.20 * slope * min(distance, 0.16)
    descent = _smoothstep(0.04, 0.68, distance)
    background = (0.12 + 0.065 * math.sin(2.7 * u + 1.7 * v) * math.cos(2.4 * v - 0.8 * u)
                  + 0.040 * math.sin(1.1 * v - 2.3 * u))
    rolling = max(0.025, (boundary + near_slope) * (1.0 - descent) + background * descent)
    far = _smoothstep(1.1, 2.2, distance)
    return rolling * (1.0 - far) + 0.065 * far


def extend_heightfield(data: Mapping, left: int, right: int, front: int, back: int) -> dict:
    """The grid grown by whole cells on each side (left + right == front + back, keeping cells square)."""
    record = normalize_heightfield(data)
    if min(left, right, front, back) < 0 or left + right != front + back:
        raise ValueError("terrain extension must add the same number of columns as rows")
    n = record["size"]
    size = n + left + right
    if size > MAX_GRID_SIZE:
        raise ValueError(f"terrain grid cannot exceed {MAX_GRID_SIZE} samples a side")
    x0, y0, cells = heightfield_basin(record)
    heights = record["heights"]
    old_left, old_front, _scale = heightfield_grid_transform(record)
    new_left, new_front = (x0 + left) / cells, (y0 + front) / cells
    out = []
    for row in range(size):
        for col in range(size):
            source_col, source_row = col - left, row - front
            if 0 <= source_col < n and 0 <= source_row < n:
                out.append(heights[source_row * n + source_col])
                continue
            u, v = col / cells - new_left, row / cells - new_front
            value = _clamp01(basin_continuation(record, u, v))
            out.append(0.0 if value == 0.0 else max(value, 1e-6))
    return normalize_heightfield({"version": 1, "size": size, "heights": out,
                                  "basin": [x0 + left, y0 + front, cells]})


def horizon_extension_cells(data: Mapping) -> tuple[int, int, int, int] | None:
    """One Extend step (left, right, front, back), or None when the grid is already at its largest."""
    _x0, _y0, cells = heightfield_basin(data)
    back = max(2, cells // 2)
    side = back // 2
    back = 2 * side
    if int(data["size"]) + back > MAX_GRID_SIZE:
        return None
    return side, side, 0, back
