"""Static, mode-owned landscape overscan lattice for Neon Lake.

The authored rectangle stays an exact 0..1 sub-lattice. The continuation extends
on every side with geometrically growing cell widths, so density is preserved
at the seam without tessellating the entire distant world at editor resolution.
Both triangles and point markers consume the exact same coordinates.
"""
from __future__ import annotations

import math
from functools import lru_cache

from core.constants.neon_lake_world import FAR_OVERSCAN

# Outside the authored domain the land reaches on toward the horizon (left, right, front, back in UV units).
BASIN_OVERSCAN = FAR_OVERSCAN


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
            # Cells grow with distance (an even share of the view), so the far ring stays cheap.
            stride = min(0.04 + 0.12 * distance, stride * 1.20)
        return positions

    low, high = first / cells, last / cells
    return tuple([low - v for v in reversed(extension(before))] +
                 [index / cells for index in range(first, last + 1)] +
                 [high + v for v in extension(after)])


NO_EXTENT = (0.0, 0.0, 0.0, 0.0)
# On the camera's side of the basin (basin v rows BASIN_MESH_FINE_ROWS: the authored land in front of it, where the
# starting views stand) the surface triangles split each mark-lattice cell this many times per axis (marks
# unchanged): straight segments from mark to mark kinked every dune and ridge line there, where cells are largest
# on screen. Farther cells are a few pixels across; the overscan behind the eye is never seen up close.
BASIN_MESH_SUBDIVISION = 2
BASIN_MESH_FINE_ROWS = (-0.8, 0.0)


@lru_cache(maxsize=8)
def basin_lattice(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                  ) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """``extent`` (left, right, front, back): how far the authored grid reaches past the basin, in basin uv."""
    columns, rows = cells
    left, right, front, back = BASIN_OVERSCAN
    lead_x, trail_x, lead_y, trail_y = extent
    return _axis(columns, left, right, lead_x, trail_x), _axis(rows, front, back, lead_y, trail_y)


def _subdivided(axis: tuple[float, ...], parts: int) -> tuple[float, ...]:
    """The axis with each interval split into ``parts`` equal steps; every original position is kept exactly."""
    if parts <= 1:
        return axis
    out = []
    for a, b in zip(axis, axis[1:]):
        out.extend(a + (b - a) * k / parts for k in range(parts))
    out.append(axis[-1])
    return tuple(out)


@lru_cache(maxsize=8)
def basin_mesh_vertices(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT,
                        subdivide: int = 1, fine_rows: tuple[float, float] = (-math.inf, math.inf)
                        ) -> tuple[float, ...]:
    """Triangles over the mark lattice. Rows inside ``fine_rows`` (basin v from, to; the camera's side of the basin)
    split every lattice cell ``subdivide`` times along both axes, so the surface (and the ridge lines drawn from its
    silhouette) follows the smooth land between marks there instead of straight segments from mark to mark, where
    the cells are largest on screen. The coarse rows either side fan to the fine rows' extra vertices, so the two
    never leave a crack; every mark stays exactly a triangle vertex."""
    parts = int(subdivide)
    if parts < 1:
        raise ValueError('invalid basin mesh subdivision')
    xs, ys = basin_lattice(cells, extent)
    fine_xs = _subdivided(xs, parts)
    points = []

    def quads(us, v0, v1):
        for u0, u1 in zip(us, us[1:]):
            points.extend((u0, v0, u0, v1, u1, v1, u0, v0, u1, v1, u1, v0))

    def fan(fine_v, coarse_v):
        # A coarse cell whose edge at fine_v carries the fine row's extra vertices.
        half = parts // 2
        for u0, u1 in zip(xs, xs[1:]):
            edge = [u0 + (u1 - u0) * k / parts for k in range(parts)] + [u1]
            for k in range(parts):
                apex = u0 if k < half else u1
                points.extend((edge[k], fine_v, apex, coarse_v, edge[k + 1], fine_v))
            points.extend((edge[half], fine_v, u0, coarse_v, u1, coarse_v))

    def fine(v0, v1):
        return parts > 1 and fine_rows[0] <= v0 and v1 <= fine_rows[1]

    rows = list(zip(ys, ys[1:]))
    for index, (v0, v1) in enumerate(rows):
        if fine(v0, v1):
            sub = _subdivided((v0, v1), parts)
            for a, b in zip(sub, sub[1:]):
                quads(fine_xs, a, b)
        elif index > 0 and fine(*rows[index - 1]):
            fan(v0, v1)
        elif index + 1 < len(rows) and fine(*rows[index + 1]):
            fan(v1, v0)
        else:
            quads(xs, v0, v1)
    return tuple(points)


@lru_cache(maxsize=8)
def basin_mesh_points(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                      ) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells, extent)
    return tuple(value for v in ys for u in xs for value in (u, v))
