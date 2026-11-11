"""Neon Lake's framed camera: a ``FramedCameraSpec`` of the shared standard (``framed_camera``).

Neon Lake is mode id ``shockwave_grid`` (keys ``shockwave_grid_*``); its sibling owners are mapped in
``Docs/Reference/Naming.md``.

The eye orbits the basin centre and may look almost level across the lake (tilt 0 is a flat horizon) while it
never enters the land or water: its floor is the authored terrain under it, with room for detail, the music's
Terrain Reaction and the lake's ripples. Settings, flight and rendering use the same fixed basin width;
card resizing changes the observed aperture, never the terrain beneath the eye.
"""
from __future__ import annotations

import math
import struct
from functools import lru_cache
from collections.abc import Mapping

from core.constants.neon_lake_world import CONTINUATION_DESCENT, DEPTH, NOMINAL_HALF_WIDTH, TILT_RANGE, WATER_PEAK
from core.settings import framed_camera as fc

PIVOT = (0.0, 0.0, -0.5 * DEPTH)
# The eye clears the highest land within this world distance around it, not only the cell beneath it, so the
# near plane (0.04) never reaches into a slope beside the eye.
_COLLISION_RADIUS = 0.08
_DETAIL = 1.16          # the land's fixed static detail adds up to 16%
_REACTION_HEIGHT = 0.32  # Terrain Reaction's largest reshaping per unit of each lane, in Terrain Height units
_RIPPLE = WATER_PEAK + 0.01   # the lake's highest wave crest above its surface
_CONTINUATION = 0.23    # the rolling ground beyond the authored basin, in heightfield units
_DESCENT = CONTINUATION_DESCENT  # the continuation leaves the basin edge for the rolling ground over this uv distance

SPEC = fc.FramedCameraSpec(
    prefix='shockwave_grid_', pivot=PIVOT, orbit_distance=3.6,
    # Tilt 0 looks level across the lake; positive tilt looks down (eye above the pivot).
    pitch_base_degrees=0.0, pitch_span_degrees=-90.0, yaw_span=-math.pi, tilt_range=TILT_RANGE,
    eye_center=(0.0, 3.0, PIVOT[2]), eye_half=(14.0, 3.0, 14.0), clearance=0.05, offset_scale=(7.0, 2.0, 7.0),
    travel_speed=1.2, fov_range=(20.0, 62.0),
    floor_hook='core.settings.neon_lake_camera:floor',
    editor_references_hook='core.settings.neon_lake_camera:editor_references',
    context_suffixes=('terrain', 'terrain_height', 'terrain_reaction_enabled', 'terrain_reaction_strength',
                      'terrain_peaks', 'terrain_pulses', 'terrain_swell'))


def _heights(terrain: Mapping) -> tuple[int, tuple[float, ...]]:
    size = int(terrain['size'])
    if 'heights' in terrain:
        return size, tuple(float(h) for h in terrain['heights'])
    # The presentation's frozen render record: interleaved (height, bank) float32 pairs.
    return size, _packed_heights(size, terrain['data'])


@lru_cache(maxsize=4)
def _packed_heights(size: int, data: bytes) -> tuple[float, ...]:
    """The render record's heights, unpacked once per immutable payload: the renderer asks for the camera
    floor every frame, and unpacking a 121-cell extended grid each time cost about a millisecond."""
    return struct.unpack(f"<{size * size * 2}f", data)[::2]


def _smoothstep(low: float, high: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - low) / (high - low)))
    return t * t * (3.0 - 2.0 * t)


def terrain_floor(terrain: Mapping, terrain_height: float, half_width: float = NOMINAL_HALF_WIDTH,
                  reaction: float = 3.0) -> fc.Floor:
    """The highest the land or water can rise at a world x/z, for the eye's clearance.

    ``reaction`` is the music's largest lift in lane units (strength x (peaks + pulses + swell)).
    """
    from rendering.gl_programs.heightfield import heightfield_grid_transform, heightfield_origin_rect
    size, heights = _heights(terrain)
    # The render record carries its precomputed transform; a settings record derives it from its basin.
    if "grid" in terrain:
        grid_left, grid_front, grid_scale = tuple(terrain["grid"])
        origin = tuple(terrain.get("origin_rect", (0.0, 0.0, 1.0, 1.0)))
    else:
        grid_left, grid_front, grid_scale = heightfield_grid_transform(terrain)
        origin = heightfield_origin_rect(terrain)
    grown = origin != (0.0, 0.0, 1.0, 1.0)
    # The authored origin's own cells: the generated landscape past it reads no others.
    low_col, low_row, high_col, high_row = (round(value * (size - 1)) for value in origin)
    scale = max(0.0, float(terrain_height))
    lift = _REACTION_HEIGHT * max(0.0, float(reaction))

    def cell_max(u: float, v: float, bounds=(0, 0, size - 1, size - 1)) -> float:
        # The highest of the cell's four samples bounds its smooth surface.
        c_low, r_low, c_high, r_high = bounds
        col, row = max(0.0, min(1.0, u)) * (size - 1), max(0.0, min(1.0, v)) * (size - 1)
        c0, r0 = max(c_low, min(c_high, int(col))), max(r_low, min(r_high, int(row)))
        return max(heights[r * size + c] for r in (r0, min(r_high, r0 + 1)) for c in (c0, min(c_high, c0 + 1)))

    def continued(local: float, outside: float) -> float:
        # The shader's continuation: from the nearest edge down to low rolling ground (water at the
        # edge instead flows on to the horizon and stays at the ripple floor).
        if outside > 0.0 and local > 0.0:
            descent = _smoothstep(*_DESCENT, outside)
            local = max(_CONTINUATION, local * (1.0 - descent) + _CONTINUATION * descent)
        return local

    def floor(x: float, z: float) -> float:
        r = _COLLISION_RADIUS
        return max(floor_at(x + dx, z + dz) for dx, dz in ((0.0, 0.0), (r, r), (r, -r), (-r, r), (-r, -r)))

    def floor_at(x: float, z: float) -> float:
        # Basin uv, then the authored grid's uv (it may reach past the basin toward the horizon).
        u, v = ((x / half_width + 1.0) * 0.5 + grid_left) * grid_scale, (-z / DEPTH + grid_front) * grid_scale
        if not grown:
            past = math.hypot(u - max(0.0, min(1.0, u)), v - max(0.0, min(1.0, v))) / grid_scale
            local = continued(cell_max(u, v), past)
        else:
            # The generated land from the origin's edge, as before the grid grew (so growing it never moves the
            # eye); stored cells past the origin and their carry past the grid's edge can only raise the floor.
            eu, ev = max(origin[0], min(origin[2], u)), max(origin[1], min(origin[3], v))
            local = continued(cell_max(eu, ev, (low_col, low_row, high_col, high_row)),
                              math.hypot(u - eu, v - ev) / grid_scale)
            if (eu, ev) != (u, v):
                past = math.hypot(u - max(0.0, min(1.0, u)), v - max(0.0, min(1.0, v))) / grid_scale
                local = max(local, continued(cell_max(u, v), past))
        land = scale * (local * _DETAIL + (lift if local > 0.0 else 0.0))
        return max(_RIPPLE, land)

    return floor


def floor_reaction(values: Mapping[str, object]) -> float:
    """Terrain Reaction's largest lift in lane units, from the mode's settings."""
    def get(name):
        return values['shockwave_grid_' + name]
    strength = float(get('terrain_reaction_strength')) if bool(get('terrain_reaction_enabled')) else 0.0
    return strength * sum(max(0.0, float(get('terrain_' + part))) for part in ('peaks', 'pulses', 'swell'))


def floor(values: Mapping[str, object]) -> fc.Floor:
    return terrain_floor(values['shockwave_grid_terrain'], float(values['shockwave_grid_terrain_height']),
                         reaction=floor_reaction(values))


def editor_references(get) -> dict:
    """The basin's water-level outline inside the Settings editor's normalized eye box."""
    def normalized(point):
        return tuple((p - c) / h for p, c, h in zip(point, SPEC.eye_center, SPEC.eye_half))
    hw = NOMINAL_HALF_WIDTH
    corners = [(-hw, 0.0, 0.0), (hw, 0.0, 0.0), (hw, 0.0, -DEPTH), (-hw, 0.0, -DEPTH)]
    return {f'basin_{i}': (*normalized(a), *normalized(b))
            for i, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1]))}
