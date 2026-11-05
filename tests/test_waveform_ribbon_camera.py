"""Production camera transforms, floor admission and capture-clock flight.

These checks establish geometry, not native scene likeness or hidden endpoints.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import FAR, FLOOR_Y, NEAR
from core.waveform_ribbon_scene import SPEC
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from widgets.spotify_visualizer.view_orbit import FramedFlightMotion, framed_flight_position


def camera(**changes):
    values = dict(turn=0., tilt=0., scene_scale=1., scene_pan_x=0., scene_pan_y=0., camera_fov=3.,
                  camera_position=(0., 0., 0.))
    values.update(changes)
    return {SPEC.key(key): value for key, value in values.items()}


def test_perspective_projection_retains_positive_near_and_behind_eye_rejection():
    values = camera()
    view, projection, eye, lens = physical_view(values, 1.5)
    inverse = np.linalg.inv(view)
    for depth, expected in ((NEAR, -1.), (FAR, 1.)):
        world = inverse @ np.array((0., 0., -depth, 1.))
        clip = projection @ view @ world
        assert clip[2] / clip[3] == pytest.approx(expected)
    # The physical Perspective eye remains a pinhole with a positive clip interval.
    for depth in (-40., -.1, NEAR / 2):
        world = inverse @ np.array((0., 0., -depth, 1.))
        clip = projection @ view @ world
        assert not (-clip[3] <= clip[2] <= clip[3] and clip[3] > 0.)


def test_saved_pose_admission_and_render_use_one_above_floor_eye():
    assert fc.spec_for_mode('waveform_ribbon') is SPEC
    floor = SPEC.floor(camera())
    assert floor is not None
    for turn, tilt, scale, pan, position in itertools.product(
            (-1., -.5, 0., .5, 1.), (-.5, 0., .5), (.25, 1., 4.), (-1., 1.),
            ((-1., -1., -1.), (1., 1., 1.))):
        values = camera(turn=turn, tilt=tilt, scene_scale=scale, scene_pan_x=pan, scene_pan_y=pan,
                        camera_position=position)
        eye, offset = fc.resolve_from_values(SPEC, values)
        admitted = {**values, SPEC.key('camera_position'): offset}
        view, matrix, rendered_eye, _ = physical_view(admitted, 1.5)
        assert rendered_eye == pytest.approx(eye)
        assert rendered_eye[1] >= FLOOR_Y + SPEC.clearance - 1e-12
        assert floor(eye[0], eye[2]) == FLOOR_Y
        assert view @ np.array((*eye, 1.)) == pytest.approx((0., 0., 0., 1.))
        assert np.isfinite(matrix).all()
        assert fc.admit_camera_parameters(SPEC, admitted) == pytest.approx(offset)


@pytest.mark.parametrize('turn', (-.5, 0., .5))
@pytest.mark.parametrize('tilt_rate', (-.3, 0., .3))
def test_end_on_and_long_held_flight_stays_above_fixed_floor(turn, tilt_rate):
    values = camera(turn=turn, tilt=.5, camera_position=(.9, -.9, .9))
    offset = fc.admit_camera_parameters(SPEC, values)
    motion = FramedFlightMotion('waveform_ribbon', 0., offset, turn, .5, .23, tilt_rate, .7, 1.,
                               1., 0., 0., 45., False, SPEC.floor(values))
    for elapsed in (0., .001, .1, 1., 3., 100., 10000.):
        offset = framed_flight_position(motion, elapsed)
        resolved = camera(turn=turn + motion.turn_rate * elapsed,
                          tilt=max(-.5, min(.5, .5 + tilt_rate * elapsed)), camera_position=offset)
        eye, _ = fc.resolve_from_values(SPEC, resolved)
        assert all(math.isfinite(v) for v in (*offset, *eye))
        assert eye[1] >= FLOOR_Y + SPEC.clearance - 1e-12
        for p, c, h in zip(eye, SPEC.eye_center, SPEC.eye_half):
            assert c - h + SPEC.clearance - 1e-10 <= p <= c + h - SPEC.clearance + 1e-10
        assert framed_flight_position(motion, elapsed) == offset


def test_orbit_basis_remains_orthonormal_at_every_admitted_pitch_and_end_on_angle():
    for turn, tilt in itertools.product((-1., -.5, 0., .5, 1.), (-100., -.5, 0., .5, 100.)):
        axes = np.asarray(fc.camera_axes(SPEC, turn, tilt)).reshape(3, 3)
        assert axes @ axes.T == pytest.approx(np.identity(3), abs=1e-12)
        assert np.linalg.det(axes) == pytest.approx(1.)
