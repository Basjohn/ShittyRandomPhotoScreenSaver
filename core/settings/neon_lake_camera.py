"""Neon Lake Basin's framed camera: a ``FramedCameraSpec`` of the shared standard (``framed_camera``).

The eye orbits the basin centre and may look almost level across the lake (tilt 0 is a flat horizon) while it
never enters the land or water: its floor is the authored terrain under it, with room for detail, the music's
Terrain Reaction and the lake's ripples. Card aspect widens the basin; Settings and flight use the nominal 16:9
width and the renderer re-bounds the eye with the card's exact width.
"""
from __future__ import annotations

import math
import struct
from collections.abc import Mapping

from core.constants.neon_lake_world import DEPTH, NOMINAL_HALF_WIDTH
from core.settings import framed_camera as fc

PIVOT = (0.0, 0.0, -0.5 * DEPTH)
_DETAIL = 1.16          # the land's fixed static detail adds up to 16%
_REACTION_HEIGHT = 0.32  # Terrain Reaction's largest reshaping per unit of each lane, in Terrain Height units
_RIPPLE = 0.19          # the lake's wave crest above its surface
_CONTINUATION = 0.23    # the rolling ground beyond the authored basin, in heightfield units
_DESCENT = (0.04, 0.68)  # the continuation leaves the basin edge for the rolling ground over this uv distance

SPEC = fc.FramedCameraSpec(
    prefix='shockwave_grid_', pivot=PIVOT, orbit_distance=3.6,
    # Tilt 0 looks level across the lake; positive tilt looks down (eye above the pivot).
    pitch_base_degrees=0.0, pitch_span_degrees=-90.0, yaw_span=-math.pi, tilt_range=(-0.10, 0.58),
    eye_center=(0.0, 2.0, PIVOT[2]), eye_half=(7.0, 2.0, 7.0), clearance=0.05, offset_scale=(7.0, 2.0, 7.0),
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
    return size, struct.unpack(f"<{size * size * 2}f", terrain['data'])[::2]


def _smoothstep(low: float, high: float, x: float) -> float:
    t = max(0.0, min(1.0, (x - low) / (high - low)))
    return t * t * (3.0 - 2.0 * t)


def terrain_floor(terrain: Mapping, terrain_height: float, half_width: float = NOMINAL_HALF_WIDTH,
                  reaction: float = 3.0) -> fc.Floor:
    """The highest the land or water can rise at a world x/z, for the eye's clearance.

    ``reaction`` is the music's largest lift in lane units (strength x (peaks + pulses + swell)).
    """
    size, heights = _heights(terrain)
    scale = max(0.0, float(terrain_height))
    lift = _REACTION_HEIGHT * max(0.0, float(reaction))

    def cell_max(u: float, v: float) -> float:
        # The highest of the cell's four samples bounds its smooth surface.
        col, row = max(0.0, min(1.0, u)) * (size - 1), max(0.0, min(1.0, v)) * (size - 1)
        c0, r0 = int(col), int(row)
        return max(heights[r * size + c] for r in (r0, min(size - 1, r0 + 1)) for c in (c0, min(size - 1, c0 + 1)))

    def floor(x: float, z: float) -> float:
        u, v = (x / half_width + 1.0) * 0.5, -z / DEPTH
        local = cell_max(u, v)
        outside = math.hypot(u - max(0.0, min(1.0, u)), v - max(0.0, min(1.0, v)))
        if outside > 0.0:
            # The shader's continuation: from the nearest edge down to low rolling ground.
            descent = _smoothstep(*_DESCENT, outside)
            local = max(_CONTINUATION, local * (1.0 - descent) + _CONTINUATION * descent)
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
