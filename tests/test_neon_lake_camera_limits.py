"""Neon Lake's loosened camera (2026-11-05): wider tilt/turn/eye box, bounded by collision with land and water.

At every extreme pose, pushed down hard with Camera Position, the eye stays above everything the shader can draw
within the near plane's reach around it: the land (its static detail and the music's largest lift included),
its continuation past the grid and the lake's highest crest.
"""
import itertools
import math

import pytest

from core.constants.neon_lake_world import DEPTH, NOMINAL_HALF_WIDTH, TILT_RANGE, TURN_RANGE, WATER_PEAK
from core.settings import framed_camera as fc
from core.settings.neon_lake_camera import SPEC, floor_reaction
from rendering.gl_programs.heightfield import normalize_heightfield, sample_heightfield
from rendering.gl_programs.neon_terrain_extent import basin_continuation

NEAR_PLANE = 0.04


def _spiky_terrain(size=33):
    """A test-owned basin: a lake in the middle and steep spikes beside it, the worst case for a near plane."""
    heights = []
    for row in range(size):
        for col in range(size):
            u, v = col / (size - 1), row / (size - 1)
            lake = math.hypot(u - 0.5, v - 0.45) < 0.22
            spike = max(0.0, 1.0 - math.hypot(u - 0.78, v - 0.7) / 0.08) + max(0.0, 1.0 - math.hypot(u - 0.2, v - 0.2) / 0.06)
            heights.append(0.0 if lake else min(1.0, 0.08 + spike))
    return normalize_heightfield({"version": 1, "size": size, "heights": heights})


def _values(terrain, **extra):
    values = {SPEC.key(name): value for name, value in (
        ("turn", 0.0), ("tilt", 0.2), ("scene_scale", 1.0), ("scene_pan_x", 0.0), ("scene_pan_y", 0.0),
        ("camera_fov", 30.0), ("camera_position", (0.0, 0.0, 0.0)))}
    values.update({"shockwave_grid_terrain": terrain, "shockwave_grid_terrain_height": 1.5,
                   "shockwave_grid_terrain_reaction_enabled": True, "shockwave_grid_terrain_reaction_strength": 1.0,
                   "shockwave_grid_terrain_peaks": 1.0, "shockwave_grid_terrain_pulses": 1.0,
                   "shockwave_grid_terrain_swell": 1.0})
    values.update(extra)
    return values


def _highest_surface(terrain, values, x, z):
    """The highest any surface can be drawn at world x/z: land with detail and the full musical lift, or a crest."""
    u, v = x / (2.0 * NOMINAL_HALF_WIDTH) + 0.5, -z / DEPTH
    base = basin_continuation(terrain, u, v)
    lift = 0.32 * floor_reaction(values) if base > 0.0 else 0.0
    return max(WATER_PEAK, float(values["shockwave_grid_terrain_height"]) * (base * 1.16 + lift))


@pytest.mark.parametrize("turn,tilt,scale", itertools.product(
    (TURN_RANGE[0], 0.0, TURN_RANGE[1]), (TILT_RANGE[0], 0.3, TILT_RANGE[1]), (0.25, 1.0, 4.0)))
def test_the_eye_never_reaches_land_or_water_at_the_loosened_limits(turn, tilt, scale):
    terrain = _spiky_terrain()
    for position in ((0.0, -1.0, 0.0), (0.4, -1.0, -0.3), (-0.6, -1.0, 0.5), (0.25, -1.0, 0.35)):
        values = _values(terrain, **{SPEC.key("turn"): turn, SPEC.key("tilt"): tilt,
                                     SPEC.key("scene_scale"): scale, SPEC.key("camera_position"): position})
        eye, _offset = fc.resolve_from_values(SPEC, values)
        for angle in range(0, 360, 30):
            for reach in (0.0, NEAR_PLANE, 2 * NEAR_PLANE):
                x = eye[0] + reach * math.cos(math.radians(angle))
                z = eye[2] + reach * math.sin(math.radians(angle))
                assert eye[1] - _highest_surface(terrain, values, x, z) >= NEAR_PLANE, (turn, tilt, scale, position)


def test_the_limits_really_were_loosened_and_stay_in_the_settings_spec():
    from core.settings.visualizer_mode_settings import require_mode_settings

    assert TILT_RANGE[0] < -0.10 and TILT_RANGE[1] > 0.58 and TURN_RANGE[1] > 0.5
    assert SPEC.tilt_range == TILT_RANGE
    controls = {control.key: control for control in require_mode_settings("shockwave_grid").controls}
    for key, (low, high) in (("shockwave_grid_tilt", TILT_RANGE), ("shockwave_grid_turn", TURN_RANGE)):
        slider = controls[key]
        assert (slider.low, slider.high) == (low, high)
