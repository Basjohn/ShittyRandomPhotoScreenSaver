"""Qt-free source/coordinate checks for R34. Native Qt and GL pixels still [~]."""
from __future__ import annotations

from pathlib import Path
import math

from core.constants.extruded_bubble_world import WORLD_CENTER, WORLD_HALF, WATER_SURFACE_Y
from core.settings.extruded_bubble_camera import CAMERA_CLEARANCE
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings
from tools.visualizer_replay.eb_simulation_support import simulation_module

simulation_module()
from rendering.gl_programs.extruded_bubble_scene import camera, physical_camera, scene_knobs

ROOT = Path(__file__).resolve().parents[1]


def _parameter_defaults():
    return {entry.key: require_canonical_default('widgets.spotify_visualizer.' + entry.key)
            for entry in require_mode_settings('extruded_bubble').entries
            if entry.key.startswith('extruded_bubble_')}


def test_bubble_and_particle_spread_have_independent_authored_controls():
    spec = require_mode_settings('extruded_bubble')
    for key, bucket in [('extruded_bubble_bubble_spread', 'bubbles'),
                        ('extruded_bubble_particle_spread', 'particles')]:
        descriptor = spec.control(key)
        assert descriptor.bucket == bucket
        default = require_canonical_default('widgets.spotify_visualizer.' + key)
        assert descriptor.admit(default, default) == default
        assert descriptor.admit(4.0, 1.0) == 4.0
    mod = simulation_module()
    path = (0., -1., 0., 0., 1., 0.)
    direction = (0., 1., 0.)
    low = mod.ExtrudedBubbleSimulation(32)
    wide = mod.ExtrudedBubbleSimulation(32)
    same = dict(stream_path=path, columns=0., collision_scope='off')
    low._spawn(True, mod.ExtrudedBubbleControls(**same, bubble_spread=0.0), direction, anywhere=False)
    wide._spawn(True, mod.ExtrudedBubbleControls(**same, bubble_spread=3.0), direction, anywhere=False)
    a, b = low._bubbles[0], wide._bubbles[0]
    assert (a.x, a.z) == (0., 0.)
    assert abs(b.x) + abs(b.z) > 0.01
    assert -WORLD_HALF[1] - 1 <= a.y <= -WORLD_HALF[1] + 1
    assert -WORLD_HALF[1] - 1 <= b.y <= -WORLD_HALF[1] + 1


def test_both_light_modes_bound_the_actual_eye_without_moving_projection():
    # Deep Light no longer grants permission to exit the populated physical
    # world. Both modes share the world-box clearance; Surface additionally
    # constrains its *baseline orbit* to remain below the water ceiling.
    surface = physical_camera(0., 0., 16/9, position_offset=(0., 2., 0.), surface_bound=True)
    deep = physical_camera(0., 0., 16/9, position_offset=(0., 2., 0.), surface_bound=False)
    for view in (surface, deep):
        for value, centre, half in zip(view[2], WORLD_CENTER, WORLD_HALF):
            assert centre - half + CAMERA_CLEARANCE <= value <= centre + half - CAMERA_CLEARANCE
    assert surface[2][1] <= WATER_SURFACE_Y - .5
    assert surface[0] == deep[0] and surface[1] == deep[1]
    assert surface[3] == deep[3] and surface[4] == deep[4]


def test_deep_visible_emitter_and_shaft_origin_share_world_position_with_distinct_ray_end():
    params = _parameter_defaults()
    params['extruded_bubble_light_type'] = 'Deep Light'
    params['extruded_bubble_light_direction'] = (-.8, .2, .25, .8, -.7, .9)
    params['extruded_bubble_ray_path'] = (.4, -.5, -.2, .5, .6, -.6)
    knobs = scene_knobs(params)
    assert knobs['light_source'] == knobs['ray_source']
    assert knobs['ray_end'] != knobs['light_end']
    assert knobs['ray_end'] != knobs['ray_source']
    params['extruded_bubble_light_type'] = 'Sunlit Surface'
    surface = scene_knobs(params)
    assert surface['ray_source'] != surface['light_source']


def test_camera_editor_retains_shared_mapper_and_uses_existing_yaw_pitch_not_fov():
    code = (ROOT/'ui/widgets/visual_controls.py').read_text(encoding='utf-8')
    builder = (ROOT/'ui/tabs/media/spec_mode_builder.py').read_text(encoding='utf-8')
    assert 'class ScenePathMapper(_VisualControl):' in code
    assert 'cameraAimCommitted = Signal(tuple)' in code
    assert 'linkedSourceCommitted = Signal(tuple)' in code
    assert 'self._camera_angles = angles' in code
    # The aim/offset logic is the shared framed-camera editor (every framed 3D mode, EB included).
    editor = (ROOT/'ui/tabs/media/framed_camera_editor.py').read_text(encoding='utf-8')
    assert "pose[key] = settings.control(key).admit(angle" in editor
    assert "for suffix in ('turn', 'tilt'):" in editor
    assert "_aim_dirty'" in editor
    assert "def _fov(" in editor and 'camera_fov' in editor  # FOV only widens pan; aim never changes it
    assert 'cameraAimCommitted.connect' in builder and 'fce.set_aim(' in builder


def test_r34_aim_roundtrip_preserves_world_eye_with_camera_translation_precision():
    """TEST INPUT, NOT A DEFAULT GOLDEN: turn in place; 4 decimals loses >0.0001 world units."""
    defaults = _parameter_defaults()
    def eye(turn, tilt):
        return physical_camera(turn, tilt, 1.,
            scale=float(defaults['extruded_bubble_scene_scale']),
            pan_x=float(defaults['extruded_bubble_scene_pan_x']),
            pan_y=float(defaults['extruded_bubble_scene_pan_y']),
            fov_y_degrees=float(defaults['extruded_bubble_camera_fov']),
            surface_bound=defaults['extruded_bubble_light_type'] == 'Sunlit Surface')[2]
    old_eye = eye(float(defaults['extruded_bubble_turn']), float(defaults['extruded_bubble_tilt']))
    new_eye = eye(0.18, -0.11)
    control = require_mode_settings('extruded_bubble').control('extruded_bubble_camera_position')
    offset = control.admit([(old_eye[i] - new_eye[i]) / WORLD_HALF[i] for i in range(3)], (0., 0., 0.))
    reconstructed_eye = [new_eye[i] + offset[i] * WORLD_HALF[i] for i in range(3)]
    assert reconstructed_eye == __import__('pytest').approx(old_eye, abs=1e-4)


def test_particle_width_maps_both_shader_populations_but_not_parent_fizz():
    shaders = (ROOT/'rendering/gl_programs/extruded_bubble_program.py').read_text()
    render = (ROOT/'rendering/quick/visualizer/implementations/extruded_bubble.py').read_text()
    assert shaders.count('uniform float uParticleSpread;') == 2
    for fragment in ('* 0.28 * uParticleSpread', '* 0.46 * uParticleSpread', '* 0.52 * uParticleSpread'):
        assert fragment in shaders
    assert 'spread = nominalRadius * (0.15 + along_ / reach * 0.8)' in shaders
    assert render.count('"uParticleSpread": float(parameter(parameters, "extruded_bubble_particle_spread"))') == 2
