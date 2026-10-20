"""Qt-free contract for EB's physical camera and per-pass eye ownership.

Run on a machine without Qt using a test runner with --noconftest, after the
simulator's dependency-light package bootstrap (see extruded_bubble_startup_probe).
Native GPU render, Windows gesture and operator visual acceptance are separate.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module
simulation_module()
from rendering.gl_programs.extruded_bubble_scene import ORBIT_DISTANCE, ORBIT_PIVOT, physical_camera


ROOT = Path(__file__).resolve().parents[1]


def _camera_point(pose, point):
    _axes, wtv, eye, _tan, _projection = pose
    return np.asarray(wtv).reshape(3, 3).T @ (np.asarray(point) - np.asarray(eye))


def test_default_physical_camera_preserves_historical_world_eye_and_centered_lens():
    pose = physical_camera(0.0, 0.0, 16 / 9)
    assert pose[2] == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert pose[4][8] == pose[4][9] == 0.0
    assert _camera_point(pose, ORBIT_PIVOT)[2] == pytest.approx(-ORBIT_DISTANCE)


@pytest.mark.parametrize('pan_x,pan_y', [(0.2, 0.0), (0.0, -0.2), (0.2, -0.2)])
def test_pan_translates_eye_not_orientation_fov_or_world(pan_x, pan_y):
    original = physical_camera(0.0, 0.0, 16 / 9)
    panned = physical_camera(0.0, 0.0, 16 / 9, pan_x=pan_x, pan_y=pan_y)
    assert panned[:2] == original[:2]
    assert panned[3:] == original[3:]
    assert panned[2] != original[2]


def test_dolly_preserves_fov_and_moves_eye_depth():
    far = physical_camera(0, 0, 16 / 9, scale=0.5)
    near = physical_camera(0, 0, 16 / 9, scale=2.0)
    assert near[:2] == far[:2]
    assert near[3:] == far[3:]
    assert math.dist(near[2], ORBIT_PIVOT) == pytest.approx(ORBIT_DISTANCE / 2)
    assert math.dist(far[2], ORBIT_PIVOT) == pytest.approx(ORBIT_DISTANCE * 2)


def test_orbit_changes_eye_and_axes_while_preserving_fixed_world_pivot():
    a = physical_camera(0, 0, 16 / 9)
    b = physical_camera(0.3, 0.1, 16 / 9)
    assert a[0] != b[0] and a[2] != b[2]
    assert math.dist(a[2], ORBIT_PIVOT) == pytest.approx(ORBIT_DISTANCE)
    assert math.dist(b[2], ORBIT_PIVOT) == pytest.approx(ORBIT_DISTANCE)
    for pose in (a, b):
        assert _camera_point(pose, ORBIT_PIVOT) == pytest.approx((0, 0, -ORBIT_DISTANCE))


def test_camera_pan_moves_near_more_than_far():
    a = physical_camera(0, 0, 16 / 9)
    b = physical_camera(0, 0, 16 / 9, pan_x=0.1)
    for z, expected in ((-6, 0.5), (-24, 0.125)):
        # Camera translation at reference depth yields depth-dependent movement.
        world = (0, 0, z)
        a_view, b_view = _camera_point(a, world), _camera_point(b, world)
        delta = (b_view[0] / -b_view[2] - a_view[0] / -a_view[2]) / a[3][0]
        assert delta > 0
        if z == -6:
            near_delta = abs(delta)
        else:
            assert near_delta > abs(delta) * 3.0


def test_all_render_pass_world_positions_use_same_physical_eye():
    shader = (ROOT / 'rendering/gl_programs/extruded_bubble_program.py').read_text()
    owner = (ROOT / 'rendering/quick/visualizer/implementations/extruded_bubble.py').read_text()
    assert 'physical_camera(' in owner
    assert 'camera_look_pan' not in owner
    assert 'lens_shift(' not in owner
    assert '"uEye": _floats(eye)' in owner
    assert 'uWorldToView * (aSphere.xyz - uEye)' in shader
    assert 'uWorldToView * (world[i].xyz - uEye)' in shader
    assert 'uWorldToView * (centre - uEye)' in shader
    assert 'toView * (aPoint.xyz - uEye)' in shader
    assert 'uWorldToView * (p - uEye)' in shader
    assert 'vec3 p = uEye + ray * s;' in shader
    assert 'float distance_ = (SURFACE_Y - uEye.y) / ray.y;' in shader
    assert 'vec2 hit = uEye.xz + (ray * distance_).xz;' in shader
    assert '"uNearCoc": 22.0 * height / 941.0}' in owner
    assert 'shift = (0.0, 0.0)' in owner


def test_lazy_first_open_hydrates_only_new_bucket_not_prior_controls():
    builder = (ROOT / 'ui/tabs/media/spec_mode_builder.py').read_text()
    assert 'only_buckets=frozenset((key,))' in builder
    assert 'if only_buckets is not None and entry.bucket not in only_buckets:' in builder
    assert 'if lazy_built is not None and only_buckets is None:' in builder


def test_pan_follow_screen_pointer_sign_is_not_inverted_again():
    # Scene Pan is screen-normalised with Y down: Qt Alt-right drag right/down
    # MUST carry the visible world right/down. The previous physical-camera
    # candidate accidentally negated X (and its initial implementation Y).
    original = physical_camera(0, 0, 16/9)
    panned = physical_camera(0, 0, 16/9, pan_x=0.1, pan_y=0.1)
    world = (0, 0, -10)
    before = _camera_point(original, world)
    after = _camera_point(panned, world)
    assert after[0]/-after[2] > before[0]/-before[2]
    assert after[1]/-after[2] < before[1]/-before[2]  # negative NDC Y = down
