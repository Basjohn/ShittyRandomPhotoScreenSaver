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


def _axis(cells: int, before: float, after: float) -> tuple[float, ...]:
    if cells < 2 or not all(math.isfinite(v) and v > 0.0 for v in (before, after)):
        raise ValueError('invalid basin mesh geometry')
    step = 1.0 / cells

    def extension(limit: float) -> list[float]:
        positions = []
        distance = 0.0
        stride = step
        while distance < limit:
            distance = min(limit, distance + stride)
            positions.append(distance)
            stride = min(0.28, stride * 1.20)
        return positions

    return tuple([-v for v in reversed(extension(before))] +
                 [index / cells for index in range(cells + 1)] +
                 [1.0 + v for v in extension(after)])


@lru_cache(maxsize=8)
def basin_lattice(cells: tuple[int, int]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    columns, rows = cells
    left, right, front, back = BASIN_OVERSCAN
    return _axis(columns, left, right), _axis(rows, front, back)


@lru_cache(maxsize=8)
def basin_mesh_vertices(cells: tuple[int, int]) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells)
    points = []
    for v0, v1 in zip(ys, ys[1:]):
        for u0, u1 in zip(xs, xs[1:]):
            points.extend((u0, v0, u0, v1, u1, v1, u0, v0, u1, v1, u1, v0))
    return tuple(points)


@lru_cache(maxsize=8)
def basin_mesh_points(cells: tuple[int, int]) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells)
    return tuple(value for v in ys for u in xs for value in (u, v))
