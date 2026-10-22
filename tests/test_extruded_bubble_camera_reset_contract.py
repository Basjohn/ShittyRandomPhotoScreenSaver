"""Qt-free checks: one reset semantics, signed physical pan, and generation-scoped UI routing.

These are source-contract and preset metadata gates, NOT installed gesture/visual acceptance.
"""
from pathlib import Path

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_presets import get_custom_preset_index, get_presets
from core.settings.visualizer_view_orbit import starting_camera_pose
from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module

simulation_module()
from rendering.gl_programs.extruded_bubble_scene import physical_camera

ROOT = Path(__file__).resolve().parents[1]
MODE = 'extruded_bubble'


def test_reset_home_uses_existing_curated_starting_poses_without_mutation():
    for index, preset in enumerate(get_presets(MODE)):
        if index == get_custom_preset_index(MODE):
            continue
        before = dict(preset.starting_view)
        assert starting_camera_pose(MODE, index) == before
        assert preset.starting_view == before
        assert set(before) == {
            'extruded_bubble_turn', 'extruded_bubble_tilt', 'extruded_bubble_scene_scale',
            'extruded_bubble_scene_pan_x', 'extruded_bubble_scene_pan_y'}


def test_custom_reset_has_canonical_home_and_starting_view_excludes_lens_intrinsics():
    result = starting_camera_pose(MODE, get_custom_preset_index(MODE))
    assert result == {k: require_canonical_default('widgets.spotify_visualizer.' + k)
                      for k in result}
    assert require_canonical_default('widgets.spotify_visualizer.extruded_bubble_camera_fov') == 45.0
    # Starting-view metadata owns pose only. Camera FOV is a separately admitted
    # mode control, which the operator may author in the normal preset snapshot.
    import json
    for path in (ROOT / 'presets/visualizer_modes/extruded_bubble').glob('*.json'):
        assert 'extruded_bubble_camera_fov' not in json.loads(path.read_text()).get('starting_view', {})
        controls = json.loads(path.read_text())['snapshot']['widgets']['spotify_visualizer']
        if 'extruded_bubble_camera_fov' in controls:
            from core.settings.visualizer_mode_settings import require_mode_settings
            control = require_mode_settings(MODE).control('extruded_bubble_camera_fov')
            assert control.coerce(controls[control.key]) == controls[control.key]


def test_physical_pan_screen_axes_match_alt_right_drag():
    import numpy as np

    def ndc(pose, world):
        vtw, wtv, eye, tan, _ = pose
        xyz = np.asarray(wtv).reshape(3,3).T @ (np.asarray(world) - np.asarray(eye))
        return float(xyz[0] / (-xyz[2]*tan[0])), float(xyz[1] / (-xyz[2]*tan[1]))

    original = physical_camera(0,0,16/9)
    panned = physical_camera(0,0,16/9,pan_x=.1,pan_y=.1)
    for world in ((0,0,-7),(0,0,-30)):
        a, b = ndc(original,world), ndc(panned,world)
        assert b[0] > a[0], 'drag right must move the subject right'
        assert b[1] < a[1], 'drag down must move the subject down in screen coordinates'


def test_key_and_glyph_one_reset_signal_and_single_persistence_authority():
    inp = (ROOT / 'rendering/runtime_input.py').read_text()
    rt = (ROOT / 'rendering/quick/runtime.py').read_text()
    scene = (ROOT / 'rendering/quick/scene_controller.py').read_text()
    manager = (ROOT / 'engine/display_manager.py').read_text()
    qml = (ROOT / 'rendering/quick/qml/VisualizerPresentation.qml').read_text()
    assert 'Qt.Key.Key_R' in inp and 'not event.isAutoRepeat()' in inp
    assert 'view_camera_reset_requested.emit()' in inp
    assert 'visualizer_camera_reset_requested.connect(self.view_camera_reset_requested.emit)' in rt
    assert 'cameraResetRequested()' in qml and 'visualizerCameraResetGlyph' in qml
    assert 'self._visualizer_camera_reset_available' in scene
    assert 'visualizer_camera_reset_requested.emit' in scene
    assert 'callback=self._reset_quick_visualizer_camera' in manager
    assert 'resolve_visualizer_view_orbit({**section, **lens}, custom, mode=mode, values=home)' in manager
    assert 'self._quick_scene_view_gesture = None' in manager


def test_idle_motion_ten_percent_more_without_changing_surface_phase():
    from widgets.spotify_visualizer.extruded_bubble_simulation import (
        ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
    )
    ctl = ExtrudedBubbleControls(collision_scope='off')
    sim = ExtrudedBubbleSimulation(510)
    for i in range(240):
        snap = sim.advance(MusicInput(1/60, False), ctl)
    idle_rate = 0.03 + 0.06 * ctl.idle
    assert sim._motion_rate == pytest.approx(idle_rate)
    assert snap.motion_phase == pytest.approx(4.0 * idle_rate)
    # Snapshot speed is in world units. Use its actual world scalar, not a
    # camera-dependent screen displacement for the resting-boost gate.
    from widgets.spotify_visualizer.extruded_bubble_geometry import WORLD_UNIT
    assert snap.stream_speed == pytest.approx(ctl.stream_speed[0] * idle_rate * 1.10 * WORLD_UNIT)
    assert snap.shimmer == pytest.approx(4.0 * idle_rate * 1.10)
