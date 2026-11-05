"""Optional Dynamic Zoom: sustained heavy passages widen the view quickly, soft/idle ones narrow it slowly.

Test-owned controls only; never preset values. The zoom is logical state on the sole clock and scales only the
visible extent, never the physical eye.
"""
from types import SimpleNamespace
import numpy as np
from core.settings.visualizer_mode_settings import require_mode_settings
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from widgets.spotify_visualizer.view_orbit import view_camera_operated
from tests.test_waveform_ribbon_dynamics import controls, primed

HEAVY = dict(bands=(.85, .8, .7), intensity=.95, presence=1.)
SOFT = dict(bands=(.2, .12, .05), intensity=.1, presence=1.)
SILENT = dict(bands=(0., 0., 0.), intensity=0., presence=0.)


def run(model, seconds, inputs, **zoom):
    for _ in range(round(seconds*90)):
        snapshot = model.advance(1/90, **inputs, **zoom)
    return snapshot


def test_off_by_default_and_never_moves_the_framing():
    assert run(primed(), 8., HEAVY).zoom == 1.
    control = next(c for c in require_mode_settings('waveform_ribbon').controls if c.key.endswith('dynamic_zoom'))
    assert control.bucket == 'camera'


def test_heavy_sustained_passage_zooms_out_quickly_and_soft_idle_zooms_in_slowly():
    model = primed()
    heavy = run(model, 6., HEAVY, dynamic_zoom=True).zoom
    assert 1.15 < heavy <= 1.2 + 1e-9
    early = run(model, 3., SILENT, dynamic_zoom=True).zoom
    assert early > 1.05  # slow way in: three seconds of silence barely start the return
    late = run(model, 45., SILENT, dynamic_zoom=True).zoom
    assert .8 - 1e-9 <= late < .83
    soft = run(primed(), 45., SOFT, dynamic_zoom=True).zoom
    assert soft < .9


def test_a_single_loud_hit_does_not_pump_the_camera():
    model = primed()
    run(model, 6., SOFT, dynamic_zoom=True)
    before = model.zoom
    after = run(model, .3, HEAVY, dynamic_zoom=True).zoom
    assert abs(after-before) < .03


def test_camera_operation_freezes_and_switching_off_eases_back_without_a_jump():
    model = primed()
    held = run(model, 6., HEAVY, dynamic_zoom=True).zoom
    assert run(model, 3., SILENT, dynamic_zoom=True, zoom_hold=True).zoom == held
    values = []
    for _ in range(270):
        values.append(model.advance(1/90, **HEAVY, dynamic_zoom=False).zoom)
    assert max(abs(np.diff(values))) < .01 and values[-1] < values[0]


def test_zoom_scales_the_visible_extent_only():
    parameters = {key: value for key, value in (
        ('waveform_ribbon_turn', 0.), ('waveform_ribbon_tilt', 0.), ('waveform_ribbon_scene_scale', 1.),
        ('waveform_ribbon_scene_pan_x', 0.), ('waveform_ribbon_scene_pan_y', 0.), ('waveform_ribbon_camera_fov', 5),
        ('waveform_ribbon_camera_position', [0., 0., 0.]))}
    view, _, eye, lens = physical_view(parameters, 2.)
    zoomed_view, _, zoomed_eye, zoomed_lens = physical_view(parameters, 2., zoom=1.2)
    np.testing.assert_array_equal(view, zoomed_view)
    np.testing.assert_array_equal(eye, zoomed_eye)
    np.testing.assert_allclose(np.asarray(zoomed_lens[:2]), 1.2*np.asarray(lens[:2]))


def test_camera_operation_is_read_from_orbit_motion_or_flight():
    assert not view_camera_operated(SimpleNamespace(), 'waveform_ribbon')
    host = SimpleNamespace(_view_orbit_motion=SimpleNamespace(mode_id='waveform_ribbon'))
    assert view_camera_operated(host, 'waveform_ribbon')
    assert not view_camera_operated(host, 'extruded_bubble')
