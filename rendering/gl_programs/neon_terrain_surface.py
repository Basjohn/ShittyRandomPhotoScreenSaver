"""Neon Lake's drawn land on the CPU: the scene's surface at any grid uv, inside the authored grid or past it.

``scene_surface`` is the CPU mirror of the basin shaders' ``basinBase`` / ``basinCurve`` / ``basinLandHeight``: the
smooth cubic land with its soft banks (at Terrain Height 1, without the music's reaction or the fine detail), water
where the scene has it, and past the grid the scene's continuation toward the horizon. ``world_points`` places grid
uv in the scene's world (its width the nominal card's, its depth ``DEPTH``). The Studio's terrain brush picks and
draws its footprint on this surface (``ui/studio/shockwave_grid_adapter.py``). Pure numpy: no Qt, no GL.
"""
from __future__ import annotations

import numpy as np

from core.constants.neon_lake_world import (
    CONTINUATION_DESCENT, DEPTH, DISTANT_CURVATURE, DISTANT_FLAT, FAR_HILLS, NOMINAL_HALF_WIDTH,
)


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


def scene_surface(grid, basin, gu, gv):
    """(land height at Terrain Height 1, water) of the scene at grid uv, inside the grid or past it: the CPU mirror
    of ``basinBase`` / ``basinCurve`` / ``basinLandHeight`` (without the music's reaction or fine detail)."""
    grid = np.asarray(grid, dtype=np.float64)
    n1 = grid.shape[0] - 1
    x0, y0, cells = basin
    scale = cells / n1
    gu, gv = np.asarray(gu, dtype=np.float64), np.asarray(gv, dtype=np.float64)
    eu, ev = np.clip(gu, 0.0, 1.0), np.clip(gv, 0.0, 1.0)
    du, dv = gu - eu, gv - ev
    outside = np.hypot(du, dv) / scale
    boundary = _bilinear(grid, eu, ev)
    # basinContinuation: the edge carried outward, easing into low rolling land (water stays water).
    interior = _bilinear(grid, np.clip(eu - np.sign(du) / n1, 0.0, 1.0), np.clip(ev - np.sign(dv) / n1, 0.0, 1.0))
    slope = np.clip((boundary - interior) * n1 * scale, -0.8, 0.8)
    near_slope = 0.20 * slope * np.minimum(outside, 0.16)
    descent = _smoothstep(*CONTINUATION_DESCENT, outside)
    bu, bv = gu / scale - x0 / cells, gv / scale - y0 / cells          # basin uv
    background = (0.12 + 0.065 * np.sin(2.7 * bu + 1.7 * bv) * np.cos(2.4 * bv - 0.8 * bu)
                  + 0.040 * np.sin(1.1 * bv - 2.3 * bu))
    rolling = np.maximum(0.025, (boundary + near_slope) * (1.0 - descent) + background * descent)
    base_far, amplitude, a, b, c, d = FAR_HILLS
    far_hills = base_far + amplitude * np.sin(a * bu + b * bv) * np.cos(c * bv - d * bu)
    continued = rolling * (1.0 - _smoothstep(1.1, 2.2, outside)) + far_hills * _smoothstep(1.1, 2.2, outside)
    continued = np.where(boundary == 0.0, 0.0, continued)
    inside = outside < 1e-9
    base = np.where(inside, boundary, continued)
    edge_curve = _cubic(grid, eu, ev)
    curve = np.where(inside, edge_curve, np.maximum(0.0, edge_curve + continued - boundary))
    curve = np.where(inside, curve,
                     curve * (1.0 - _smoothstep(1.1, 2.2, outside)) + far_hills * _smoothstep(1.1, 2.2, outside))
    water = base == 0.0
    land = curve * _smoothstep(0.0, 0.015, base)
    # The scene's shallow convex distant world: land and water alike fall away toward a real horizon.
    drop = DISTANT_CURVATURE * np.maximum(0.0, outside - DISTANT_FLAT) ** 2
    return np.where(water, -drop, land - drop), water


def surface_points(size: int, heights, basin, u, v, terrain_height: float = 1.0) -> np.ndarray:
    """World positions of grid uv points resting on the scene's surface."""
    grid = np.asarray(heights, dtype=np.float64).reshape(size, size)
    land, _water = scene_surface(grid, basin, u, v)
    return world_points(size, basin, np.asarray(u, dtype=np.float64), np.asarray(v, dtype=np.float64),
                        land * float(terrain_height))


__all__ = ["scene_surface", "surface_points", "world_points"]
