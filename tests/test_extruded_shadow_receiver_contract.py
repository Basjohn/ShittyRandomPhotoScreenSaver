"""Extruded shadow styles: real silhouettes and real-height casts, not footprint sheets."""
from __future__ import annotations

import itertools
import math
import pytest

from rendering.gl_programs.extruded_spectrum_program import (
    EXTRUDED_CEILING, EXTRUDED_MAX_TILT, EXTRUDED_MAX_TURN,
    EXTRUDED_SHADOW_CAST_REACH, EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE,
    EXTRUDED_SHADOW_NEAR_DROP_SCALE,
    EXTRUDED_VERTEX_SOURCE, _PROJECTION_GLSL,
    extruded_project, extruded_shadow_project,
)


def test_nearby_is_offset_of_actual_view_silhouette_without_ground_sweep():
    for tilt, turn, y, z in itertools.product((0.0, 0.4, 1.3), (-2.0, 0.0, 1.7),
                                              (0.0, 0.14, EXTRUDED_CEILING), (-0.3, 0.0)):
        point = (0.6, y, z)
        base = extruded_project(point, tilt, turn)
        near = extruded_shadow_project(point, tilt, turn, (0.045, 0.045), 'Nearby')
        assert near == pytest.approx((base[0] + 0.045 * EXTRUDED_SHADOW_NEAR_DROP_SCALE,
                                      base[1] - 0.045 * EXTRUDED_SHADOW_NEAR_DROP_SCALE,
                                      base[2]))
        # DIFFERENT y values preserve exactly the bar silhouette shape.


def test_distant_sweep_starts_at_foot_and_tracks_true_bar_height():
    for tilt, turn, x, z in itertools.product((0.0, 0.35, EXTRUDED_MAX_TILT),
                                              (-EXTRUDED_MAX_TURN, 0.0, EXTRUDED_MAX_TURN),
                                              (-1.0, 0.6), (-0.32, 0.0)):
        foot = extruded_project((x, 0.0, z), tilt, turn)
        base = extruded_shadow_project((x, 0.0, z), tilt, turn, (0.22, 0.22))
        quiet = extruded_shadow_project((x, 0.2, z), tilt, turn, (0.22, 0.22))
        loud = extruded_shadow_project((x, 0.8, z), tilt, turn, (0.22, 0.22))
        assert base == pytest.approx(foot)
        assert quiet[1] > loud[1]
        assert loud[1] - quiet[1] == pytest.approx(-0.6 * 0.22 * EXTRUDED_SHADOW_CAST_REACH)
        assert loud[0] - quiet[0] == pytest.approx(
            0.6 * 0.22 * EXTRUDED_SHADOW_CAST_REACH * EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE)
        assert quiet[2] == pytest.approx(foot[2]) == loud[2]


def test_diagonal_distant_cast_does_not_shift_row_sideways_into_large_slab():
    assert 0.0 < EXTRUDED_SHADOW_DIAGONAL_LATERAL_SCALE < 0.25
    for sign_x, sign_y in itertools.product((-1, 0, 1), repeat=2):
        point = (0.4, EXTRUDED_CEILING, -0.25)
        tilt, turn = 0.4, 0.9
        base = extruded_shadow_project((point[0], 0.0, point[2]), tilt, turn,
                                       (0.22*sign_x, 0.22*sign_y))
        cast = extruded_shadow_project(point, tilt, turn, (0.22*sign_x, 0.22*sign_y))
        dx, dy = cast[0]-base[0], cast[1]-base[1]
        if sign_x == 0:
            assert dx == pytest.approx(0)
        if sign_y == 0:
            assert dy == pytest.approx(0)
        if sign_x and sign_y:
            assert abs(dx) < abs(dy) / 4
        if sign_x:
            assert math.copysign(1, dx) == sign_x
        if sign_y:
            assert math.copysign(1, dy) == -sign_y


def test_distant_receiver_retains_front_and_back_depth_and_orbit():
    for tilt, turn in itertools.product((0, 0.3, 1.2), (-1.0, 0, 2.1)):
        for y in (0.0, 0.3, EXTRUDED_CEILING):
            p = (0.3, y, -0.4)
            q = (0.3, y, 0.0)
            a = extruded_shadow_project(p, tilt, turn, (0.22, 0.22))
            b = extruded_shadow_project(q, tilt, turn, (0.22, 0.22))
            foot_a = extruded_project((p[0], 0, p[2]), tilt, turn)
            foot_b = extruded_project((q[0], 0, q[2]), tilt, turn)
            assert a[0]-b[0] == pytest.approx(foot_a[0]-foot_b[0])
            assert a[1]-b[1] == pytest.approx(foot_a[1]-foot_b[1])


def test_shader_has_two_distinct_geometry_paths_and_uses_live_height():
    branch = EXTRUDED_VERTEX_SOURCE.split('if (uPass == 4)', 1)[1].split('vWorld =', 1)[0]
    assert 'extrudedShadowProject(world, uShadowVector, uView, uShadowMode)' in branch
    assert 'EXTRUDED_CEILING * local.y' not in branch
    assert 'vec3 silhouette = extrudedProject(p, view);' in _PROJECTION_GLSL
    assert 'vec3 foot = extrudedProject(vec3(p.x, 0.0, p.z), view);' in _PROJECTION_GLSL
    assert 'uShadowMode' in EXTRUDED_VERTEX_SOURCE
    import re
    assert not re.search(r'\b(?:vec[234]|float|int)\s+cast\b', EXTRUDED_VERTEX_SOURCE)


def test_edit_footprint_and_target_bound_both_shadow_styles_at_all_yaws():
    from rendering.gl_programs.extruded_spectrum_program import (
        extruded_fit, extruded_footprint, extruded_reach, extruded_height,
    )
    field, centre, half_span, depth = (0.0, 0.0, 640.0, 220.0), 320.0, 1.5, 0.12
    levels = (0.25, 0.8, 0.48, 0.3)
    peaks = levels
    first, step, half_width = -1.2, 0.8, 0.055
    height_scale = 1.0
    for mode, tilt, turn, direction in itertools.product(
        ('Nearby', 'Distant'), (0.0, 0.4, 1.4), (-2.0, -0.3, 0.4, 2.0),
        ((0.045, 0.045), (-0.22, 0.22), (0.22, -0.22), (0, 0.22), (0.22, 0)),
    ):
        fit = extruded_fit(half_span, depth, tilt, 0.0, field[2]/field[3], turn, True)
        edit = extruded_footprint(
            field, centre, first, step, half_width, depth, tilt, turn, fit,
            levels, peaks, height_scale, body_visible=False, ghost_alpha=0.0,
            reflection=0.0, shadow_vector=direction, shadow_mode=mode,
        )
        target = extruded_reach(field, centre, half_span, depth, tilt, turn, fit, 0.0,
                                shadow_vector=direction, shadow_mode=mode)
        assert edit is not None
        for index, level in enumerate(levels):
            h = extruded_height(level, height_scale)
            for x, z, y in itertools.product(
                (first + index*step-half_width, first + index*step+half_width),
                (-depth, 0.0), (0.0, h),
            ):
                a, b, _ = extruded_shadow_project((x, y, z), tilt, turn, direction, mode)
                px = centre+a*field[3]*fit[0]
                py = field[1]+field[3]-(fit[1]+b*fit[0])*field[3]
                for bounds in (edit,target):
                    assert bounds[0]-1e-7 <= px <= bounds[2]+1e-7
                    assert bounds[1]-1e-7 <= py <= bounds[3]+1e-7
