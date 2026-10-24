"""Static, mode-owned landscape overscan lattice for Neon Lake Basin.

The authored rectangle stays an exact 0..1 sub-lattice. The continuation extends
on every side with geometrically growing cell widths, so density is preserved
at the seam without tessellating the entire distant world at editor resolution.
Both triangles and point markers consume the exact same coordinates.
"""
from __future__ import annotations

import math
from functools import lru_cache

# Outside the authored domain, visibility fades to sky before the final ring.
BASIN_OVERSCAN = (2.3, 3.0, 1.4, 3.4)  # left, right, front, back in UV units


def _axis(cells: int, before: float, after: float, lead: float = 0.0, trail: float = 0.0) -> tuple[float, ...]:
    """Fine cells across the authored grid (the basin's 0..1 plus ``lead``/``trail`` it reaches past it), then
    geometrically growing overscan."""
    if cells < 2 or not all(math.isfinite(v) and v > 0.0 for v in (before, after)) or min(lead, trail) < 0.0:
        raise ValueError('invalid basin mesh geometry')
    step = 1.0 / cells
    first, last = -math.ceil(lead * cells - 1e-9), cells + math.ceil(trail * cells - 1e-9)

    def extension(limit: float) -> list[float]:
        positions = []
        distance = 0.0
        stride = step
        while distance < limit:
            distance = min(limit, distance + stride)
            positions.append(distance)
            stride = min(0.28, stride * 1.20)
        return positions

    low, high = first / cells, last / cells
    return tuple([low - v for v in reversed(extension(before))] +
                 [index / cells for index in range(first, last + 1)] +
                 [high + v for v in extension(after)])


NO_EXTENT = (0.0, 0.0, 0.0, 0.0)


@lru_cache(maxsize=8)
def basin_lattice(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                  ) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """``extent`` (left, right, front, back): how far the authored grid reaches past the basin, in basin uv."""
    columns, rows = cells
    left, right, front, back = BASIN_OVERSCAN
    lead_x, trail_x, lead_y, trail_y = extent
    return _axis(columns, left, right, lead_x, trail_x), _axis(rows, front, back, lead_y, trail_y)


@lru_cache(maxsize=8)
def basin_mesh_vertices(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                        ) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells, extent)
    points = []
    for v0, v1 in zip(ys, ys[1:]):
        for u0, u1 in zip(xs, xs[1:]):
            points.extend((u0, v0, u0, v1, u1, v1, u0, v0, u1, v1, u1, v0))
    return tuple(points)


@lru_cache(maxsize=8)
def basin_mesh_points(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                      ) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells, extent)
    return tuple(value for v in ys for u in xs for value in (u, v))
