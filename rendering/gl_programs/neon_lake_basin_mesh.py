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


def _reach_parts(axis: tuple[float, ...], cells: int, lead: float, trail: float, low: float, high: float
                 ) -> tuple[list[int], list[bool], list[bool]]:
    """Per lattice interval along one axis: how many equal steps bring it to the tier's own cell width (an even
    count past the origin, so it nests with the camera-side band's halves; 1 on the origin, already that fine),
    whether the painted bounds (``low`` .. ``high``, basin uv) reach it, and whether it lies past the origin."""
    inner_low, inner_high = -lead, 1.0 + trail
    steps, reached, past = [], [], []
    for a, b in zip(axis, axis[1:]):
        outside = a < inner_low - 1e-9 or b > inner_high + 1e-9
        steps.append(max(2, 2 * math.ceil((b - a) * cells / 2.0 - 1e-9)) if outside else 1)
        reached.append(b > low + 1e-9 and a < high - 1e-9)
        past.append(outside)
    return steps, reached, past


@lru_cache(maxsize=8)
def basin_mesh_vertices(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT,
                        subdivide: int = 1, fine_rows: tuple[float, float] = (-math.inf, math.inf),
                        reach: tuple[float, float, float, float] | None = None) -> tuple[float, ...]:
    """Triangles over the mark lattice. Rows inside ``fine_rows`` (basin v from, to; the camera's side of the basin)
    split every lattice cell ``subdivide`` times along both axes, so the surface (and the ridge lines drawn from its
    silhouette) follows the smooth land between marks there instead of straight segments from mark to mark, where
    the cells are largest on screen. The coarse rows either side fan to the fine rows' extra vertices, so the two
    never leave a crack; every mark stays exactly a triangle vertex.

    ``extent`` is the authored origin's reach past the basin (the mark lattice's fine part). ``reach`` is the bounds
    of what the terrain brush has painted past the origin (left, front, right, back in basin uv; None while nothing
    is): the overscan cells it covers are split to the tier's own cell width, so land painted there has triangles
    to stand on, while the marks and every triangle outside it stay exactly as they were."""
    parts = int(subdivide)
    if parts < 1:
        raise ValueError('invalid basin mesh subdivision')
    if reach is not None:
        return _grown_mesh_vertices(cells, extent, parts, fine_rows, tuple(reach))
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


def _grown_mesh_vertices(cells, extent, parts: int, fine_rows, reach) -> tuple[float, ...]:
    """The same triangles with the overscan cells under painted far land split finer (``basin_mesh_vertices``).

    Each lattice cell takes whole equal steps per axis: the camera-side band's ``parts``, the grown region's
    ``_reach_parts`` (even, so the two nest), their product where both apply. A cell whose four edges carry
    exactly its own steps is a regular patch (an unsplit one is the ordinary two triangles, a band cell the ordinary
    split); a cell beside a finer neighbour keeps its own triangles where the ordinary fan fits and otherwise fans
    from its centre to every vertex on its border, so no edge is ever left with a vertex only one side uses."""
    columns, rows = cells
    xs, ys = basin_lattice(cells, extent)
    lead_x, trail_x, lead_y, trail_y = extent
    steps_x, reached_x, past_x = _reach_parts(xs, columns, lead_x, trail_x, reach[0], reach[2])
    steps_y, reached_y, past_y = _reach_parts(ys, rows, lead_y, trail_y, reach[1], reach[3])
    half = parts // 2

    def band(j: int) -> bool:
        return parts > 1 and fine_rows[0] <= ys[j] and ys[j + 1] <= fine_rows[1]

    def steps(i: int, j: int) -> tuple[int, int]:
        if not (0 <= i < len(xs) - 1 and 0 <= j < len(ys) - 1):
            return 1, 1
        # Under the stored grid and past the origin (on either axis): the grown ring.
        grown = reached_x[i] and reached_y[j] and (past_x[i] or past_y[j])
        scale = parts if band(j) else 1
        return (steps_x[i] if grown else 1) * scale, (steps_y[j] if grown else 1) * scale

    points: list[float] = []

    def split(a: float, b: float, count: int) -> list[float]:
        return [a + (b - a) * k / count for k in range(count)] + [b]

    for j in range(len(ys) - 1):
        v0, v1 = ys[j], ys[j + 1]
        for i in range(len(xs) - 1):
            u0, u1 = xs[i], xs[i + 1]
            sx, sy = steps(i, j)
            below, above = max(sx, steps(i, j - 1)[0]), max(sx, steps(i, j + 1)[0])
            left, right = max(sy, steps(i - 1, j)[1]), max(sy, steps(i + 1, j)[1])
            if below == above == sx and left == right == sy:
                us, vs = split(u0, u1, sx), split(v0, v1, sy)
                for a, b in zip(vs, vs[1:]):
                    for c, d in zip(us, us[1:]):
                        points.extend((c, a, c, b, d, b, c, a, d, b, d, a))
                continue
            if sx == sy == 1 and left == right == 1 and sorted((below, above)) == [1, parts] and parts > 1:
                # The ordinary fan of a coarse cell beside the camera-side band.
                fine_v, coarse_v = (v0, v1) if below == parts else (v1, v0)
                edge = split(u0, u1, parts)
                for k in range(parts):
                    apex = u0 if k < half else u1
                    points.extend((edge[k], fine_v, apex, coarse_v, edge[k + 1], fine_v))
                points.extend((edge[half], fine_v, u0, coarse_v, u1, coarse_v))
                continue
            border = ([(u, v0) for u in split(u0, u1, below)[:-1]] + [(u1, v) for v in split(v0, v1, right)[:-1]]
                      + [(u, v1) for u in reversed(split(u0, u1, above)[1:])]
                      + [(u0, v) for v in reversed(split(v0, v1, left)[1:])])
            centre = (0.5 * (u0 + u1), 0.5 * (v0 + v1))
            for a, b in zip(border, border[1:] + border[:1]):
                points.extend((*centre, *b, *a))
    return tuple(points)


@lru_cache(maxsize=8)
def basin_mesh_points(cells: tuple[int, int], extent: tuple[float, float, float, float] = NO_EXTENT
                      ) -> tuple[float, ...]:
    xs, ys = basin_lattice(cells, extent)
    return tuple(value for v in ys for u in xs for value in (u, v))
