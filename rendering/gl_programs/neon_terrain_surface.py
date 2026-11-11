"""Neon Lake's drawn land on the CPU: the scene's surface at any grid uv, inside the authored grid or past it.

``scene_surface`` is the CPU mirror of the basin shaders' ``basinBase`` / ``basinCurve`` / ``basinLandHeight``: the
smooth cubic land with its soft banks (at Terrain Height 1, without the music's reaction or the fine detail), water
where the scene has it, and past the grid the scene's generated landscape toward the horizon. ``world_points`` places
grid uv in the scene's world (its width the nominal card's, its depth ``DEPTH``). The Studio's terrain brush picks and
draws its footprint on this surface (``ui/studio/shockwave_grid_adapter.py``). Pure numpy: no Qt, no GL.

The generated landscape belongs to the **authored origin** (``heightfield.heightfield_origin``): the square of cells
the grid had before the brush grew it, the whole grid otherwise. Its continuation, far hills, distant curvature and
the fade of detail are all measured from the origin's edge and read only the origin's own cells.

Stored cells past the origin are an overlay on that landscape. A grown cell stores the drawn height at its point;
what the scene adds to the generated land is the cell's **delta** (``terrain_delta``: stored minus generated, exactly
zero for a cell the brush never touched), smoothed by the same cubic as the land. An unpainted growth therefore draws
the generated landscape itself, bit for bit; past the grid's edge the edge's delta eases out over the continuation's
descent (``carry``), so a painted edge never ends in a wall.
"""
from __future__ import annotations

import numpy as np

from core.constants.neon_lake_world import (
    CONTINUATION_DESCENT, DEPTH, DISTANT_CURVATURE, DISTANT_FLAT, FAR_HILLS, NOMINAL_HALF_WIDTH,
)

_LAND_FLOOR = 1e-6      # carried land never becomes authored water (exactly zero)
# A grown cell within this of its seed was never painted: above a record saved to six decimals, far below anything
# a stroke leaves that could be seen (a thousandth of a pixel at any admitted view).
_UNPAINTED = 2e-6


def world_points(size: int, basin, u: np.ndarray, v: np.ndarray, height: np.ndarray) -> np.ndarray:
    """World positions of grid uv points (u right, v toward the back) at world ``height``."""
    x0, y0, cells = basin
    n1 = size - 1
    x = ((u * n1 - x0) / cells - 0.5) * 2.0 * NOMINAL_HALF_WIDTH
    z = -((v * n1 - y0) / cells) * DEPTH
    return np.stack([x, np.broadcast_to(height, np.shape(x)), z], axis=-1)


def _smoothstep(low, high, x):
    t = np.clip((x - low) / (high - low), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _bilinear(grid: np.ndarray, gu, gv):
    n1 = grid.shape[0] - 1
    x, y = np.clip(gu, 0.0, 1.0) * n1, np.clip(gv, 0.0, 1.0) * n1
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, n1), np.minimum(y0 + 1, n1)
    fx, fy = x - x0, y - y0
    near = grid[y0, x0] * (1.0 - fx) + grid[y0, x1] * fx
    far = grid[y1, x0] * (1.0 - fx) + grid[y1, x1] * fx
    return near * (1.0 - fy) + far * fy


def _cubic(grid: np.ndarray, gu, gv):
    """The scene's positive cubic B-spline surface (``sceneHeightfieldCurve``)."""
    n1 = grid.shape[0] - 1
    x, y = np.clip(gu, 0.0, 1.0) * n1, np.clip(gv, 0.0, 1.0) * n1
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)

    def weights(t):
        t2, t3 = t * t, t * t * t
        return ((1.0 - t) ** 3 / 6.0, (3.0 * t3 - 6.0 * t2 + 4.0) / 6.0, (-3.0 * t3 + 3.0 * t2 + 3.0 * t + 1.0) / 6.0,
                t3 / 6.0)

    wx, wy = weights(x - ix), weights(y - iy)
    total = np.zeros(np.shape(x))
    for b in range(4):
        rows = np.clip(iy + b - 1, 0, n1)
        for a in range(4):
            total = total + wx[a] * wy[b] * grid[rows, np.clip(ix + a - 1, 0, n1)]
    return total


def far_hills(bu, bv):
    """``basinFarHills`` at basin uv: the broad hills the land settles into toward the horizon."""
    base, amplitude, a, b, c, d = FAR_HILLS
    return base + amplitude * np.sin(a * bu + b * bv) * np.cos(c * bv - d * bu)


def _generated(grid: np.ndarray, basin, gu, gv):
    """(base, curve, outside) of the landscape one square grid generates at its own grid uv: its stored bilinear /
    cubic cells inside, and past its edge the continuation (``basinContinuation`` / ``basinCurve``): the edge carried
    outward, easing into low rolling land and then the far hills; water at the edge stays water outward. ``outside``
    is the distance past the grid in basin uv."""
    n1 = grid.shape[0] - 1
    x0, y0, cells = basin
    scale = cells / n1
    eu, ev = np.clip(gu, 0.0, 1.0), np.clip(gv, 0.0, 1.0)
    du, dv = gu - eu, gv - ev
    outside = np.hypot(du, dv) / scale
    boundary = _bilinear(grid, eu, ev)
    interior = _bilinear(grid, np.clip(eu - np.sign(du) / n1, 0.0, 1.0), np.clip(ev - np.sign(dv) / n1, 0.0, 1.0))
    slope = np.clip((boundary - interior) * n1 * scale, -0.8, 0.8)
    near_slope = 0.20 * slope * np.minimum(outside, 0.16)
    descent = _smoothstep(*CONTINUATION_DESCENT, outside)
    bu, bv = gu / scale - x0 / cells, gv / scale - y0 / cells          # basin uv
    background = (0.12 + 0.065 * np.sin(2.7 * bu + 1.7 * bv) * np.cos(2.4 * bv - 0.8 * bu)
                  + 0.040 * np.sin(1.1 * bv - 2.3 * bu))
    rolling = np.maximum(0.025, (boundary + near_slope) * (1.0 - descent) + background * descent)
    hills = far_hills(bu, bv)
    far = _smoothstep(1.1, 2.2, outside)
    continued = rolling * (1.0 - far) + hills * far
    continued = np.where(boundary == 0.0, 0.0, continued)
    inside = outside < 1e-9
    base = np.where(inside, boundary, continued)
    edge_curve = _cubic(grid, eu, ev)
    curve = np.where(inside, edge_curve, np.maximum(0.0, edge_curve + continued - boundary))
    curve = np.where(inside, curve, curve * (1.0 - far) + hills * far)
    curve = np.where(~inside & (boundary == 0.0), 0.0, curve)          # a stream past the edge is water, not land
    return base, curve, outside


def _whole(grid: np.ndarray, origin) -> bool:
    return origin is None or tuple(origin) == (0, 0, grid.shape[0] - 1)


def _origin_generated(grid: np.ndarray, basin, origin, gu, gv):
    """``_generated`` of the origin's own square, at the whole grid's uv."""
    n1 = grid.shape[0] - 1
    x0, y0, cells = basin
    ox, oy, span = origin
    return _generated(grid[oy:oy + span + 1, ox:ox + span + 1], (x0 - ox, y0 - oy, cells),
                      (gu * n1 - ox) / span, (gv * n1 - oy) / span)


def seed_heights(base, curve):
    """What a grown cell stores for the landscape drawn at its point: the drawn height (kept land: never exactly
    zero, which is authored water), or zero where the scene has water."""
    return np.where(base == 0.0, 0.0, np.clip(curve, _LAND_FLOOR, 1.0))


def terrain_delta(grid, basin, origin):
    """Per cell, stored minus generated: what the brush has made of each cell past the authored origin. Zero on the
    origin (its cells are the generated landscape's own source) and on every grown cell still as seeded; None for a
    grid that never grew."""
    grid = np.asarray(grid, dtype=np.float64)
    if _whole(grid, origin):
        return None
    n = grid.shape[0]
    ox, oy, span = origin
    gu, gv = np.meshgrid(np.arange(n) / (n - 1), np.arange(n) / (n - 1))
    base, curve, _outside = _origin_generated(grid, basin, origin, gu, gv)
    delta = grid - seed_heights(base, curve)
    # A cell still as seeded is exactly unpainted, whatever the last bits of two evaluations of the same land say.
    delta[np.abs(delta) < _UNPAINTED] = 0.0
    delta[oy:oy + span + 1, ox:ox + span + 1] = 0.0
    return delta


def scene_heights(grid, basin, gu, gv, origin=None, delta=None):
    """(base, curve, outside) of the scene at grid uv: ``base`` classifies water (exactly zero) and the banks,
    ``curve`` is the smooth drawn land (Terrain Height 1, before the banks and the distant curvature) and ``outside``
    the distance past the authored origin in basin uv. ``origin`` (column, row, span) defaults to the whole grid;
    ``delta`` is its ``terrain_delta`` when the caller already has it."""
    grid = np.asarray(grid, dtype=np.float64)
    gu, gv = np.asarray(gu, dtype=np.float64), np.asarray(gv, dtype=np.float64)
    if _whole(grid, origin):
        return _generated(grid, basin, gu, gv)
    if delta is None:
        delta = terrain_delta(grid, basin, origin)
    n1 = grid.shape[0] - 1
    base, curve, outside = _origin_generated(grid, basin, origin, gu, gv)
    eu, ev = np.clip(gu, 0.0, 1.0), np.clip(gv, 0.0, 1.0)
    past = np.hypot(gu - eu, gv - ev) * n1 / basin[2]                  # past the stored grid, in basin uv
    carry = 1.0 - _smoothstep(*CONTINUATION_DESCENT, past)
    on_origin, stored = outside < 1e-9, past < 1e-9
    # Water: the stored cells' own (bilinear zero) on the grid, the generated landscape's past it.
    water = np.where(stored, _bilinear(grid, eu, ev) == 0.0, base == 0.0)
    overlaid = np.maximum(_LAND_FLOOR, base + carry * _bilinear(delta, eu, ev))
    base = np.where(on_origin, base, np.where(water, 0.0, overlaid))
    lifted = np.maximum(0.0, curve + carry * _cubic(delta, eu, ev))
    curve = np.where(~stored & water, curve, lifted)
    return base, curve, outside


def scene_surface(grid, basin, gu, gv, origin=None, delta=None):
    """(land height at Terrain Height 1, water) of the scene at grid uv, inside the grid or past it: the CPU mirror
    of ``basinBase`` / ``basinCurve`` / ``basinLandHeight`` (without the music's reaction or fine detail)."""
    base, curve, outside = scene_heights(grid, basin, gu, gv, origin, delta)
    water = base == 0.0
    land = curve * _smoothstep(0.0, 0.015, base)
    # The scene's shallow convex distant world: land and water alike fall away toward a real horizon.
    drop = DISTANT_CURVATURE * np.maximum(0.0, outside - DISTANT_FLAT) ** 2
    return np.where(water, -drop, land - drop), water


def surface_points(size: int, heights, basin, u, v, terrain_height: float = 1.0, origin=None) -> np.ndarray:
    """World positions of grid uv points resting on the scene's surface."""
    grid = np.asarray(heights, dtype=np.float64).reshape(size, size)
    land, _water = scene_surface(grid, basin, u, v, origin)
    return world_points(size, basin, np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64),
                        land * float(terrain_height))


__all__ = ["far_hills", "scene_heights", "scene_surface", "seed_heights", "surface_points", "terrain_delta",
           "world_points"]
