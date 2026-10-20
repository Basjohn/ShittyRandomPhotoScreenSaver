"""Qt-free world-camera/editor contract checks. Native Qt drag and GL pixels stay [~]."""
from pathlib import Path

import pytest

from core.constants.extruded_bubble_world import WORLD_HALF, WATER_SURFACE_Y
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import (
    SceneVolumePath, SceneCameraPosition, require_mode_settings,
)
from core.settings.visualizer_paths import admit_path, world_point
from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module
simulation_module()  # import pure GL camera without requiring the GUI Spotify runtime
from rendering.gl_programs.extruded_bubble_scene import physical_camera


ROOT = Path(require_mode_settings.__code__.co_filename).resolve().parents[2]


def test_3d_editor_consumes_original_path_values_without_rewriting_presets():
    spec = require_mode_settings('extruded_bubble')
    for key in ('extruded_bubble_light_direction', 'extruded_bubble_ray_path',
                'extruded_bubble_stream_direction'):
        control = spec.control(key)
        assert isinstance(control, SceneVolumePath)
        default = require_canonical_default('widgets.spotify_visualizer.' + key)
        assert control.admit(default, default) == list(admit_path(default, default, control.legacy_kind))
    assert spec.control('extruded_bubble_camera_position').admit((0,0,0),(0,0,0)) == [0,0,0]


def test_physical_camera_can_reach_stream_sources_without_fov_change():
    normal = physical_camera(0., 0., 16/9, fov_y_degrees=45.)
    base = normal[2]
    for destination in ((-15., -7., 13.), (16., 7.5, -15.), (0.,0.,0.)):
        offset = tuple((destination[i] - base[i]) / WORLD_HALF[i] for i in range(3))
        assert all(-8 <= x <= 8 for x in offset)
        moved = physical_camera(0.,0.,16/9, fov_y_degrees=45.,position_offset=offset)
        assert moved[2] == pytest.approx(destination)
        assert moved[3] == pytest.approx(normal[3])
        assert moved[4] == pytest.approx(normal[4])
        assert moved[0] == pytest.approx(normal[0])
        assert moved[1] == pytest.approx(normal[1])
    # Even the most distant accepted orbit can translate to both extremes
    # of the authored scene, without a second lens or a camera-bound emitter.
    from core.settings.visualizer_mode_settings import require_mode_settings
    offset_descriptor=require_mode_settings('extruded_bubble').control('extruded_bubble_camera_position')
    for turn in (-1.,-.5,0.,.5,1.):
        for tilt in (-.5,0.,.5):
            for scale in (.5,1.,2.):
                eye=physical_camera(turn,tilt,16/9,scale=scale,pan_x=.5,pan_y=-.5)[2]
                for target in ((-18.,-8.,-18.),(18.,8.,18.)):
                    offset=tuple((target[i]-eye[i])/WORLD_HALF[i] for i in range(3))
                    assert offset_descriptor.admit(offset,offset)==pytest.approx(offset,abs=1e-4)
    # Water ceiling remains a physical bound, not a lens manipulation.
    raised = physical_camera(0.,0.,1.,position_offset=(0.,2.,0.))
    assert raised[2][1] <= WATER_SURFACE_Y - .5


def test_pan_is_physical_and_card_aspect_independent():
    a = physical_camera(.21,.13,1.0,pan_x=.22,pan_y=-.15)
    b = physical_camera(.21,.13,16/9,pan_x=.22,pan_y=-.15)
    assert a[2] == pytest.approx(b[2])
    assert a[3] != pytest.approx(b[3])


def test_preset_camera_starts_are_unchanged_and_home_resets_new_position():
    manager = (ROOT/'engine/display_manager.py').read_text(encoding='utf-8')
    assert '"extruded_bubble_camera_position"' in manager
    assert 'lens["extruded_bubble_camera_position"] = list(require_canonical_default(' in manager
    assert require_canonical_default('widgets.spotify_visualizer.extruded_bubble_camera_position') == [0.,0.,0.]
    assert require_canonical_default('widgets.spotify_visualizer.extruded_bubble_camera_fov') == 45.


def test_original_scene_path_mapper_kept_for_other_visualizers():
    source = (ROOT/'ui/widgets/visual_controls.py').read_text(encoding='utf-8')
    builder = (ROOT/'ui/tabs/media/spec_mode_builder.py').read_text(encoding='utf-8')
    assert 'class ScenePathMapper(_VisualControl):' in source
    assert 'class SceneVolumeMapper(_VisualControl):' in source
    assert 'ScenePathMapper()' in builder
    assert 'SceneVolumeMapper(camera_only=' in builder
    assert 'cameraOffsetCommitted' in source and 'cameraOffsetCommitted.connect' in builder
