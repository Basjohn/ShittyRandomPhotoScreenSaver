"""Joint fixed-world camera admission: geometry, publication and bounded flight."""
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest

from core.constants.extruded_bubble_world import WORLD_HALF
from core.settings.default_contract import require_canonical_default
from core.settings.extruded_bubble_camera import (
    CAMERA_CLEARANCE, CAMERA_INPUT_KEYS, admit_camera_parameters, camera_baseline, resolve_camera_position,
)
from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module

simulation_module()
from rendering.gl_programs.extruded_bubble_scene import physical_camera
from widgets.spotify_visualizer.view_orbit import (
    FramedFlightMotion, framed_flight_position, set_framed_flight_rates, apply_view_orbit_motion,
    settle_framed_flight, stop_view_orbit_motion,
)


def defaults():
    return {key: require_canonical_default('widgets.spotify_visualizer.' + key) for key in CAMERA_INPUT_KEYS}


def test_rejected_saved_pose_admits_effective_offset_and_all_rays_cross_water():
    requested = (.320911, -1.110771, 1.90208)
    eye, offset = resolve_camera_position(.05069708824, -.2253050804, position_offset=requested)
    assert eye == pytest.approx((8.1487, -5., 15.), abs=1e-4)
    assert offset != requested
    again, admitted = resolve_camera_position(.05069708824, -.2253050804, position_offset=offset)
    assert again == pytest.approx(eye) and admitted == pytest.approx(offset)
    home = physical_camera(0., 0., 1.6)
    assert home[2] == camera_baseline(0., 0.)


def test_faces_corners_lens_and_pose_extremes_share_world_eye_and_near_containment():
    for turn, tilt, scale, pan, light in product((-.8, 0., .5), (-.5, .5), (.5, 2.), (-.5, .5), (False, True)):
        for offset in product((-8., 8.), repeat=3):
            eye, effective = resolve_camera_position(turn, tilt, scale, pan, -pan, 62., offset, light)
            axes, _, rendered, tan, _ = physical_camera(turn, tilt, 32/9, scale, pan, -pan, 62., effective, light)
            assert rendered == pytest.approx(eye)
            assert all(abs(p) <= h-CAMERA_CLEARANCE+1e-10 for p, h in zip(eye, WORLD_HALF))
            basis = np.asarray(axes).reshape(3, 3).T
            for x, y in product((-1., 0., 1.), repeat=2):
                ray = basis @ np.asarray((x*tan[0], y*tan[1], -1.))
                ray /= np.linalg.norm(ray)
                exits = [(np.copysign(h, d)-p)/d for p, h, d in zip(eye, WORLD_HALF, ray) if abs(d)>1e-12]
                assert min(exits) >= CAMERA_CLEARANCE-1e-10
                near_corner = np.asarray(eye) + basis @ np.asarray((x*tan[0]*.05, y*tan[1]*.05, -.05))
                assert np.all(np.abs(near_corner) < WORLD_HALF)


def test_complete_configuration_admits_camera_before_publication_and_partial_pose_edits():
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    settings = defaults()
    settings['extruded_bubble_camera_position'] = (8., -8., 8.)
    host = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host, settings)
    values = {k: getattr(host, '_' + k) for k in CAMERA_INPUT_KEYS}
    assert tuple(host._extruded_bubble_camera_position) == admit_camera_parameters(values)
    apply_presentation_vis_mode_kwargs(host, {'extruded_bubble_turn': -.5, 'extruded_bubble_scene_scale': .5})
    values = {k: getattr(host, '_' + k) for k in CAMERA_INPUT_KEYS}
    assert tuple(host._extruded_bubble_camera_position) == admit_camera_parameters(values)


def test_outward_hold_discards_overshoot_and_reverse_moves_immediately():
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    def reverse_after(seconds):
        host = SimpleNamespace()
        apply_presentation_vis_mode_kwargs(host, defaults())
        set_framed_flight_rates(host, 'extruded_bubble', 0., 0., 1., 0., 0.)
        at_wall = apply_view_orbit_motion(host, 'extruded_bubble', defaults(), seconds)
        set_framed_flight_rates(host, 'extruded_bubble', 0., 0., -1., 0., seconds)
        moved = apply_view_orbit_motion(host, 'extruded_bubble', defaults(), seconds+.1)
        return at_wall['extruded_bubble_camera_position'], moved['extruded_bubble_camera_position']

    a, b = reverse_after(4.), reverse_after(60.)
    assert np.asarray(a) == pytest.approx(np.asarray(b))
    assert a[0][0] - a[1][0] == pytest.approx(.55/WORLD_HALF[0])


def test_turning_flight_capture_and_settlement_agree_at_wall():
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    host = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host, defaults())
    set_framed_flight_rates(host, 'extruded_bubble', 1., -.3, 1., 1., 0.)
    captured = apply_view_orbit_motion(host, 'extruded_bubble', defaults(), 10.)
    settled = settle_framed_flight(host, 10.)
    stop_view_orbit_motion(host, 10.)
    assert settled == pytest.approx(captured['extruded_bubble_camera_position'], abs=1e-6)
    assert host._extruded_bubble_turn == pytest.approx(captured['extruded_bubble_turn'])
    assert host._extruded_bubble_tilt == pytest.approx(captured['extruded_bubble_tilt'])
    assert host._extruded_bubble_camera_position == pytest.approx(settled)


def test_curved_flight_never_leaves_box_or_accumulates_hidden_normal_offset():
    motion = FramedFlightMotion('extruded_bubble', 0., (.7, 0., 0.), 0., 0., .18, .04, 1., 1.)
    previous = None
    for t in np.linspace(0., 8., 241):
        offset = framed_flight_position(motion, float(t))
        eye, effective = resolve_camera_position(.18*t, min(.5, .04*t), position_offset=offset)
        assert effective == pytest.approx(offset)
        if previous is not None:
            assert np.linalg.norm(np.asarray(eye)-previous) < .7
        previous = np.asarray(eye)


@pytest.mark.parametrize('surface', [False, True])
@pytest.mark.parametrize('yaw,pitch', [(1/3,0.),(-2/3,0.),(1/3,2/3),(1/3,-2/3),(1e-10,0.)])
def test_long_curved_hold_matches_rebased_intervals(yaw,pitch,surface):
    from dataclasses import replace
    motion = FramedFlightMotion('extruded_bubble',0.,(.7,0.,0.),.2,0.,yaw,pitch,1.,1.,.5,.2,-.1,53.,surface)
    whole = framed_flight_position(motion,60.)
    split = motion
    for t in range(1,61):
        offset = framed_flight_position(split,float(t))
        split = replace(split,since=float(t),offset=offset,turn=motion.turn+yaw*t,
                        tilt=max(-.5,min(.5,pitch*t)))
    assert np.asarray(whole)*WORLD_HALF == pytest.approx(np.asarray(split.offset)*WORLD_HALF,abs=.001)


def test_mouse_orbit_during_flight_rebases_travel_to_new_angles():
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.view_orbit import orbit_visualizer_view
    host = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host,defaults())
    set_framed_flight_rates(host,'extruded_bubble',0.,0.,0.,1.,0.)
    orbit_visualizer_view(host,'extruded_bubble',10.,0.,.2)
    flight = host._view_framed_flight_motion
    assert flight.turn == pytest.approx(host._view_orbit_motion.turn)
    assert framed_flight_position(flight,.2) == pytest.approx(flight.offset)
    later = apply_view_orbit_motion(host,'extruded_bubble',defaults(),.3)
    settle_framed_flight(host,.3)
    stop_view_orbit_motion(host,.3)
    assert host._extruded_bubble_camera_position == pytest.approx(later['extruded_bubble_camera_position'],abs=1e-6)


@pytest.mark.parametrize('surface', [False, True])
@pytest.mark.parametrize('pitch', [-2/3, 2/3])
def test_changing_pitch_prefix_partition_error_is_below_one_thousandth_world_unit(surface,pitch):
    from dataclasses import replace
    motion = FramedFlightMotion('extruded_bubble',0.,(.7,0.,0.),.2,0.,2/3,pitch,1.,1.,.5,.2,-.1,53.,surface)
    whole = framed_flight_position(motion,.6)
    split = motion
    for i in range(1,61):
        t = i*.01
        offset = framed_flight_position(split,t)
        split = replace(split,since=t,offset=offset,turn=motion.turn+motion.turn_rate*t,
                        tilt=max(-.5,min(.5,pitch*t)))
    # Physical world units; much smaller than a pixel in the matching native view.
    assert np.linalg.norm((np.asarray(whole)-split.offset)*WORLD_HALF) < .001


def test_dolly_pan_during_held_flight_rebases_the_same_gesture_and_saved_offset():
    from unittest.mock import patch
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.view_orbit import transform_visualizer_scene
    host = SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host,defaults())
    set_framed_flight_rates(host,'extruded_bubble',0.,0.,0.,1.,0.)
    with patch('time.time',return_value=.2):
        transform_visualizer_scene(host,'extruded_bubble',{
            'extruded_bubble_scene_scale':.5,'extruded_bubble_scene_pan_x':.3})
    flight = host._view_framed_flight_motion
    assert flight.scale == .5 and flight.pan_x == .3
    assert host._extruded_bubble_camera_position == flight.offset
    captured = apply_view_orbit_motion(host,'extruded_bubble',_eb_values(host),.3)
    settle_framed_flight(host,.3)
    stop_view_orbit_motion(host,.3)
    assert host._extruded_bubble_camera_position == pytest.approx(captured['extruded_bubble_camera_position'],abs=1e-6)


def _eb_values(host):
    return {key:getattr(host,'_'+key) for key in CAMERA_INPUT_KEYS}
