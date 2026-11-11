"""Neon Lake terrain beyond its basin: the CPU mirror of the shader's continuation, and the grid's growth.

The authored grid may reach past the scene's basin toward the horizon (``heightfield_basin``). It grows two ways,
both keeping every existing cell exactly:

* ``extend_heightfield`` (the Studio's **Extend Toward Horizon**): the new cells are seeded from the continuation and
  the whole grid becomes ordinary authored land, with its detail and glow; the generated landscape then starts at
  the new edge.
* ``grow_heightfield`` (the terrain brush reaching past the grid): the growth is invisible. The new cells take the
  drawn landscape's own heights and the record keeps its authored origin (``heightfield_origin``), so the generated
  land beyond, the distant curvature and the fade of detail and glow stay where they were until the brush paints.

Where the grid's edge is water, the continuation keeps it water outward: a stream painted to the edge flows on to the
horizon instead of stopping at rolling land.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from core.constants.neon_lake_world import CONTINUATION_DESCENT, FAR_HILLS
from rendering.gl_programs.heightfield import (
    HEIGHTFIELD_MAX_SIZE, heightfield_basin, heightfield_grid_transform, heightfield_origin, heightfield_origin_rect,
    normalize_heightfield, sample_heightfield,
)

# One Extend step: half the basin's depth further back, a quarter of its width on each side (square cells).
MAX_GRID_SIZE = HEIGHTFIELD_MAX_SIZE
# The brush grows the grid by whole steps of this many cells, so a stroke travelling outward regrows it rarely.
GROW_STEP = 16
# Cells kept between a brush footprint and a grown edge: the cubic surface's support.
GROW_MARGIN = 2


def _smoothstep(low: float, high: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - low) / (high - low)))
    return t * t * (3.0 - 2.0 * t)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sign(x: float) -> float:
    return (x > 0.0) - (x < 0.0)


def _whole_origin(data: Mapping) -> bool:
    return heightfield_origin(data) == (0, 0, int(data["size"]) - 1)


def basin_continuation(data: Mapping, u: float, v: float) -> float:
    """Mirror of ``basinBase`` (neon_lake_basin_program) at basin uv: the stored height inside the grid, the generated
    landscape past it."""
    left, front, scale = heightfield_grid_transform(data)
    gu, gv = (u + left) * scale, (v + front) * scale
    if not _whole_origin(data):
        import numpy as np
        from rendering.gl_programs.neon_terrain_surface import scene_heights
        n = int(data["size"])
        grid = np.asarray(data["heights"], dtype=np.float64).reshape(n, n)
        base, _curve, _outside = scene_heights(grid, heightfield_basin(data), np.array(gu), np.array(gv),
                                               heightfield_origin(data))
        return float(base)
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
    descent = _smoothstep(*CONTINUATION_DESCENT, distance)
    background = (0.12 + 0.065 * math.sin(2.7 * u + 1.7 * v) * math.cos(2.4 * v - 0.8 * u)
                  + 0.040 * math.sin(1.1 * v - 2.3 * u))
    rolling = max(0.025, (boundary + near_slope) * (1.0 - descent) + background * descent)
    far = _smoothstep(1.1, 2.2, distance)
    return rolling * (1.0 - far) + far_hills(u, v) * far


def far_hills(u: float, v: float) -> float:
    """Mirror of ``basinFarHills``: the broad hills the land settles into toward the horizon."""
    base, amplitude, a, b, c, d = FAR_HILLS
    return base + amplitude * math.sin(a * u + b * v) * math.cos(c * v - d * u)


def _checked(record: Mapping, left: int, right: int, front: int, back: int) -> int:
    if min(left, right, front, back) < 0 or left + right != front + back:
        raise ValueError("terrain extension must add the same number of columns as rows")
    size = int(record["size"]) + left + right
    if size > MAX_GRID_SIZE:
        raise ValueError(f"terrain grid cannot exceed {MAX_GRID_SIZE} samples a side")
    return size


def extend_heightfield(data: Mapping, left: int, right: int, front: int, back: int) -> dict:
    """The grid grown by whole cells on each side (left + right == front + back, keeping cells square), as ordinary
    authored land: the generated landscape then starts at the new edge."""
    import numpy as np
    from rendering.gl_programs.neon_terrain_surface import scene_heights

    record = normalize_heightfield(data)
    size = _checked(record, left, right, front, back)
    n = record["size"]
    x0, y0, cells = heightfield_basin(record)
    old = np.asarray(record["heights"], dtype=np.float64).reshape(n, n)
    columns, rows = (np.arange(size) - left) / (n - 1), (np.arange(size) - front) / (n - 1)
    gu, gv = np.meshgrid(columns, rows)
    # The continuation's own heights (``basinBase``), every new cell at once: the Studio asks for this record on
    # every inspector rebuild to know whether Extend is on offer.
    base, _curve, _outside = scene_heights(old, (x0, y0, cells), gu, gv, heightfield_origin(record))
    values = np.where(base == 0.0, 0.0, np.clip(base, 1e-6, 1.0))
    values[front:front + n, left:left + n] = old
    return normalize_heightfield({"version": 1, "size": size, "heights": values.ravel().tolist(),
                                  "basin": [x0 + left, y0 + front, cells]})


def grow_heightfield(data: Mapping, left: int, right: int, front: int, back: int) -> dict:
    """The grid grown by whole cells on each side without changing what the scene draws: every existing cell is kept
    exactly, the authored origin stays where it was, and each new cell stores the height the scene already draws at
    its point (zero where it has water). The scene adds only a cell's departure from the generated landscape
    (``neon_terrain_surface.terrain_delta``), which is nothing for these cells until the brush paints them.
    """
    import numpy as np
    from rendering.gl_programs.neon_terrain_surface import scene_heights, seed_heights

    record = normalize_heightfield(data)
    size = _checked(record, left, right, front, back)
    n = record["size"]
    if size == n:
        return record
    x0, y0, cells = heightfield_basin(record)
    ox, oy, span = heightfield_origin(record)
    old = np.asarray(record["heights"], dtype=np.float64).reshape(n, n)
    columns, rows = (np.arange(size) - left) / (n - 1), (np.arange(size) - front) / (n - 1)
    gu, gv = np.meshgrid(columns, rows)
    base, curve, _outside = scene_heights(old, (x0, y0, cells), gu, gv, (ox, oy, span))
    values = seed_heights(base, curve)
    values[front:front + n, left:left + n] = old
    heights = values.ravel().tolist()
    return normalize_heightfield({"version": 1, "size": size, "heights": heights,
                                  "basin": [x0 + left, y0 + front, cells],
                                  "origin": [ox + left, oy + front, span]})


def overlay_fields(data: Mapping) -> dict:
    """What the renderer needs of a grown grid besides its cells: ``origin_rect`` (the authored origin in grid uv:
    left, front, right, back), ``delta`` (float32 texels, each cell's stored height
    minus the generated landscape's; zero where unpainted), ``painted`` (the painted cells' bounds in basin uv,
    left / front / right / back, stepped out to whole ``GROW_STEP`` cells so strokes rarely move it; None while
    nothing is painted) and ``maximum`` (the authored summit: the origin's and the painted cells' highest, so an
    unpainted growth leaves it where it was). Empty for a grid that never grew."""
    if _whole_origin(data):
        return {}
    import numpy as np
    from rendering.gl_programs.neon_terrain_surface import terrain_delta

    n = int(data["size"])
    x0, y0, cells = heightfield_basin(data)
    ox, oy, span = heightfield_origin(data)
    grid = np.asarray(data["heights"], dtype=np.float64).reshape(n, n)
    delta = terrain_delta(grid, (x0, y0, cells), (ox, oy, span))
    touched = delta != 0.0
    maximum = float(grid[oy:oy + span + 1, ox:ox + span + 1].max())
    painted = None
    if touched.any():
        maximum = max(maximum, float(grid[touched].max()))
        rows, columns = np.flatnonzero(touched.any(axis=1)), np.flatnonzero(touched.any(axis=0))

        def stepped(low: int, high: int) -> tuple[int, int]:
            low, high = low - GROW_MARGIN, high + GROW_MARGIN
            return (max(0, GROW_STEP * (low // GROW_STEP)), min(n - 1, GROW_STEP * -(-high // GROW_STEP)))

        (c0, c1), (r0, r1) = stepped(int(columns[0]), int(columns[-1])), stepped(int(rows[0]), int(rows[-1]))
        painted = [(c0 - x0) / cells, (r0 - y0) / cells, (c1 - x0) / cells, (r1 - y0) / cells]
    return {"origin_rect": list(heightfield_origin_rect(data)), "delta": delta.astype("<f4").tobytes(),
            "painted": painted, "maximum": maximum}


def growth_cells(data: Mapping, u: float, v: float, reach: float) -> tuple[int, int, int, int] | None:
    """Whole cells (left, right, front, back) the grid must grow by for a brush of ``reach`` (grid uv) at grid uv
    ``(u, v)``; (0, 0, 0, 0) when it already fits, None when the point itself lies past what the largest grid
    (``MAX_GRID_SIZE``) can still reach.

    Cells stay square, so both axes grow by the same total: the axis that needs less takes the rest toward the
    back (rows) or evenly on both sides (columns). The total is a whole number of ``GROW_STEP`` cells while the cap
    allows, with ``GROW_MARGIN`` cells kept round the footprint; at the cap the footprint is clipped, not refused.
    """
    n = int(data["size"])
    n1 = n - 1
    room = MAX_GRID_SIZE - n

    def need(position: float, extent: float) -> tuple[int, int]:
        low = max(0, math.ceil((extent - position) * n1 - 1e-9))
        high = max(0, math.ceil((position + extent - 1.0) * n1 - 1e-9))
        return low, high

    centre = need(u, 0.0) + need(v, 0.0)
    if max(centre[0] + centre[1], centre[2] + centre[3]) > room:
        return None
    wanted = [side + GROW_MARGIN if side else 0 for side in need(u, reach) + need(v, reach)]
    total = max(wanted[0] + wanted[1], wanted[2] + wanted[3])
    if total == 0:
        return 0, 0, 0, 0
    total = min(room, GROW_STEP * math.ceil(total / GROW_STEP))
    out = []
    for low, high, low_centre, high_centre, toward_high in ((wanted[0], wanted[1], centre[0], centre[1], False),
                                                           (wanted[2], wanted[3], centre[2], centre[3], True)):
        if low + high > total:
            # At the cap: the point itself first, the rest of the footprint as far as the room goes.
            spare = total - low_centre - high_centre
            extra_low, extra_high = low - low_centre, high - high_centre
            give_low = min(extra_low, round(spare * extra_low / max(1, extra_low + extra_high)))
            low, high = low_centre + give_low, high_centre + min(extra_high, spare - give_low)
        spare = total - low - high
        if low and not high:
            low += spare
        elif high and not low:
            high += spare
        elif toward_high and not low and not high:
            high += spare                               # rows nothing asked for: toward the horizon
        else:
            low += spare // 2
            high += spare - spare // 2
        out.extend((low, high))
    return out[0], out[1], out[2], out[3]


def horizon_extension_cells(data: Mapping) -> tuple[int, int, int, int] | None:
    """One Extend step (left, right, front, back), or None when the grid is already at its largest."""
    _x0, _y0, cells = heightfield_basin(data)
    back = max(2, cells // 2)
    side = back // 2
    back = 2 * side
    if int(data["size"]) + back > MAX_GRID_SIZE:
        return None
    return side, side, 0, back
