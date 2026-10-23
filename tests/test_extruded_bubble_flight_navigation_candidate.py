"""EB framed-camera candidate: Qt-free geometry and source routing checks.

Native key event, Settings construction, on-screen travel and lifecycle remain [~].
"""
from __future__ import annotations

from pathlib import Path
import math
import sys
from types import ModuleType, SimpleNamespace

from tools.visualizer_replay.eb_simulation_support import simulation_module
simulation_module()

from widgets.spotify_visualizer.view_orbit import (
    FramedFlightMotion, apply_view_orbit_motion, framed_flight_position,
    set_framed_flight_rates, settle_framed_flight,
)
from core.constants.extruded_bubble_world import WORLD_HALF

ROOT = Path(__file__).resolve().parents[1]


def test_forward_and_strafe_are_camera_relative_not_fov_or_scene_zoom():
    forward = FramedFlightMotion('extruded_bubble', 0, (0., 0., 0.),
                                 0., 0., 0., 0., 0., 1.)
    a = framed_flight_position(forward, 0.5)
    b = framed_flight_position(forward, 1.0)
    assert b[2] < a[2] < 0.0
    assert b[1] > a[1] > 0.0  # travel follows the camera's 16-degree upward view
    right = FramedFlightMotion('extruded_bubble', 0, (0., 0., 0.),
                               0., 0., 0., 0., 1., 0.)
    assert framed_flight_position(right, 1.) == (5.5 / WORLD_HALF[0], 0., 0.)
    yawed = FramedFlightMotion('extruded_bubble', 0, (0., 0., 0.),
                               0.5, 0., 0., 0., 0., 1.)
    assert framed_flight_position(yawed, 1.)[0] < -0.1  # forward turned camera-left
    assert framed_flight_position(yawed, 1.)[2] > -0.01
    reverse = FramedFlightMotion('extruded_bubble', 0, (0., 0., 0.),
                                 0., 0., 0., 0., 0., -1.)
    # Compare before either path hits the newly contracted physical camera bound.
    for x, y in zip(framed_flight_position(forward, .1), framed_flight_position(reverse, .1)):
        assert abs(x + y) < 1e-10


def test_combined_turn_travel_is_continuous_and_frame_rate_independent():
    motion = FramedFlightMotion('extruded_bubble', 10., (.2, 0., -.2),
                                0., 0., .18, .05, -.5, 1.)
    samples = [framed_flight_position(motion, 10. + k / 120) for k in range(121)]
    assert samples[0] == (.2, 0., -.2)
    assert samples[-1] == framed_flight_position(motion, 11.)
    assert all(math.dist(a, b) < .05 for a, b in zip(samples, samples[1:]))
    assert all(math.isfinite(x) for p in samples for x in p)
    # The motion path is expressed in physical coordinates, not today's authored lens default.


def test_persistent_single_owner_motion_and_other_modes_untouched():
    fake = ModuleType('widgets.spotify_visualizer.config_applier')
    def apply(host, values):
        for key, value in values.items():
            setattr(host, '_' + key, value)
    fake.apply_presentation_vis_mode_kwargs = apply
    fake.presentation_setting_range = lambda key: ((-0.5, 0.5) if key.endswith('_tilt') else (-1., 1.))
    old = sys.modules.get(fake.__name__)
    sys.modules[fake.__name__] = fake
    try:
        host = SimpleNamespace(_extruded_bubble_turn=0., _extruded_bubble_tilt=0.,
                               _extruded_bubble_camera_position=[0., 0., 0.])
        assert set_framed_flight_rates(host, 'sphere', 0., 0., 0., 1., 10.) == {}
        set_framed_flight_rates(host, 'extruded_bubble', 0., 0., 0., 1., 10.)
        first = apply_view_orbit_motion(host, 'extruded_bubble',
               {'extruded_bubble_camera_position': [0., 0., 0.]}, 11.)['extruded_bubble_camera_position']
        assert first[2] < -.2
        set_framed_flight_rates(host, 'extruded_bubble', 1., 0., 0., 1., 11.)
        turning = apply_view_orbit_motion(host, 'extruded_bubble',
               {'extruded_bubble_camera_position': [0., 0., 0.]}, 11.5)
        assert turning['extruded_bubble_turn'] > 0.
        assert turning['extruded_bubble_camera_position'][2] < first[2]
        set_framed_flight_rates(host, 'extruded_bubble', 0., 0., 0., 0., 11.5)
        final = settle_framed_flight(host, 11.5)
        assert final == tuple(turning['extruded_bubble_camera_position'])
        assert host._extruded_bubble_camera_position == list(final)
        assert getattr(host, '_view_framed_flight_motion') is None
    finally:
        if old is None:
            del sys.modules[fake.__name__]
        else:
            sys.modules[fake.__name__] = old


def test_input_and_settings_crash_contracts_are_explicit_and_mode_scoped():
    inp = (ROOT/'rendering/runtime_input.py').read_text(encoding='utf-8')
    rt = (ROOT/'rendering/quick/runtime.py').read_text(encoding='utf-8')
    manager = (ROOT/'engine/display_manager.py').read_text(encoding='utf-8')
    builder = (ROOT/'ui/tabs/media/spec_mode_builder.py').read_text(encoding='utf-8')
    assert 'self._framed_flight_enabled' in inp
    assert 'Qt.Key.Key_Escape:' in inp and 'if key == Qt.Key.Key_Q:\n            return False' in inp
    assert 'self._framed_shift' in inp and 'view_framed_flight_rates_changed.emit' in inp
    assert 'self._input.view_framed_flight_rates_changed.connect' in rt
    # Mode isolation is proved by the state/motion test above; require the
    # real display-manager input gate, not the old equality spelling in one
    # particular branch (which now rightly rejects non-EB modes with !=).
    assert 'set_framed_flight_enabled(bool(admitted and mode == "extruded_bubble"))' in manager
    assert "config['extruded_bubble_camera_position']" in manager
    # Formatters must exist before branching, and each volume mapper must receive
    # its admitted value. Exact source-line formatting is not the acceptance gate.
    import ast
    tree = ast.parse(builder)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_build_visual_control')
    assignments = [(i, n) for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)]
    formatter_at = next(i for i, n in assignments
                        if any(isinstance(t, ast.Name) and t.id == 'describe' for t in n.targets)
                        and isinstance(n.value, ast.Attribute) and n.value.attr == 'text')
    branch_at = next(i for i, n in enumerate(fn.body) if isinstance(n, ast.If))
    assert formatter_at < branch_at
    assert 'widget.setValue(value)' in builder
    assert 'label = QLabel(describe(widget.value()))' in builder
