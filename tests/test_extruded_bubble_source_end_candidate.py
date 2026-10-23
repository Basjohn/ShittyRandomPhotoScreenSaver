"""Qt-free, unaccepted source/end semantics; no visual or native GL acceptance.

Run: py -3.14 -m pytest tests/test_extruded_bubble_source_end_candidate.py -q
"""
from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import ScenePath, require_mode_settings
from core.settings.visualizer_paths import (admit_path, direction_of, world_point, square_to_disc, disc_to_square)
from tools.visualizer_replay.extruded_bubble_startup_probe import simulation_module


def test_legacy_eb_preset_angles_migrate_without_clobbering_presets():
    import hashlib
    spec = require_mode_settings('extruded_bubble')
    for number in range(1, 8):
        path = next((ROOT / 'presets/visualizer_modes/extruded_bubble').glob(f'preset_{number}_*.json'))
        old = path.read_bytes()
        values = json.loads(old)['snapshot']['widgets']['spotify_visualizer']
        for key in ('extruded_bubble_light_direction', 'extruded_bubble_stream_direction'):
            control = spec.control(key)
            assert isinstance(control, ScenePath)
            points = control.admit(values[key], values[key])
            assert len(points) == 6
            assert max(abs(coord) for coord in points) <= 1.0
            norm = math.sqrt(sum(x*x for x in direction_of(points)))
            assert abs(norm - 1.0) < 1e-9
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(old).digest()


def test_square_disc_projection_reaches_all_source_boundaries():
    for x, y in ((-1, -1), (1, 1), (1, -0.5), (-0.5, 1), (0, -1), (0, 0), (0.77, -0.33)):
        u, v = square_to_disc(x, y)
        assert math.hypot(u, v) <= 1.0000001
        xx, yy = disc_to_square(u, v)
        assert abs(x - xx) < 1e-9 and abs(y - yy) < 1e-9


def test_scene_path_is_six_coordinates_and_rejects_coincident_or_nonfinite_inputs():
    src, end = (0, -1, 0), (0, 1, 0)
    assert admit_path((*src, *end), [0, 0]) == (*src, *end)
    assert world_point(src)[1] == -8.0
    assert world_point(end)[1] == 8.0
    assert admit_path([0, 0, 0, 0, 0, 0], [0, 0]) == admit_path([0, 0], [0, 0])
    assert admit_path([math.nan, 2], [0, 0]) == admit_path([0, 0], [0, 0])


def test_floor_or_ceiling_source_is_real_and_activation_has_no_halfway_population():
    mod = simulation_module()
    for floor in (-1, 1):
        controls = mod.ExtrudedBubbleControls(
            large_count=(5, 5), mid_count=(5, 5),
            stream_path=(0, floor, 0, 0, -floor, 0),
            stream_speed=(0, 0), drift=(0, 0), sway=0,
            collision_scope='off')
        sim = mod.ExtrudedBubbleSimulation(123)
        sim.advance(mod.MusicInput(0, False), controls)
        assert not sim._bubbles  # no mature half-filled volume on activation
        # Zero-speed inflow has the physical resting budget .4 births/s/class,
        # not the old target-sized startup burst: first credit matures at2.5s.
        for _ in range(224):
            sim.advance(mod.MusicInput(1 / 90, False), controls)
            assert not sim._bubbles
        sim.advance(mod.MusicInput(1 / 90, False), controls)
        assert sim._bubbles
        assert all(abs(b.y - floor * 8.0) <= 1.0 for b in sim._bubbles)
        assert all(b.alpha <= 1. for b in sim._bubbles)


def test_stream_direction_obeys_author_defined_two_ends():
    mod = simulation_module()
    controls = mod.ExtrudedBubbleControls(
        large_count=(0, 0), mid_count=(0, 0),
        stream_path=(-1, 0, 0, 1, 0, 0),
        stream_speed=(0, 0), drift=(0, 0), collision_scope='off')
    snapshot = mod.ExtrudedBubbleSimulation(3).advance(mod.MusicInput(1/60, False), controls)
    assert snapshot.stream[0] > 0.999 and abs(snapshot.stream[1]) < 1e-5


def _knobs_module():
    """Use real imports under native pytest; isolate Qt-free stubs to this call."""
    import importlib
    try:
        return importlib.import_module('rendering.gl_programs.extruded_bubble_scene'), lambda: None
    except ModuleNotFoundError as exc:
        if exc.name not in ('PySide6', 'OpenGL'):
            raise
    saved = {k: v for k, v in sys.modules.items() if k == 'rendering' or k.startswith('rendering.')}
    for name, folder in (('rendering', ROOT / 'rendering'), ('rendering.quick', ROOT / 'rendering/quick'),
                         ('rendering.quick.scene3d', ROOT / 'rendering/quick/scene3d')):
        package = types.ModuleType(name)
        package.__path__ = [str(folder)]
        sys.modules[name] = package
    for suffix, var in (('defocus', 'SCENE_DEFOCUS_GLSL'), ('probe', 'SCENE3D_PROBE_GLSL'),
                        ('target', 'SCENE_OIT_GLSL')):
        name = 'rendering.quick.scene3d.' + suffix
        module = types.ModuleType(name)
        setattr(module, var, '')
        sys.modules[name] = module
    result = importlib.import_module('rendering.gl_programs.extruded_bubble_scene')

    def cleanup():
        for key in tuple(sys.modules):
            if key == 'rendering' or key.startswith('rendering.'):
                if key not in saved:
                    del sys.modules[key]
                else:
                    sys.modules[key] = saved[key]
    return result, cleanup


def test_light_position_and_ray_endpoints_are_real_scene_knobs():
    scene, cleanup = _knobs_module()
    defaults = require_canonical_default('widgets.spotify_visualizer')
    v = {**defaults, 'extruded_bubble_light_type': 'Deep Light'}
    base = scene.scene_knobs(v)
    v['extruded_bubble_light_direction'] = [0.2, 0.5, 0.0, 0.2, -0.5, 0.0]
    moved = scene.scene_knobs(v)
    assert moved['light_source'] != base['light_source']
    assert moved['light_end'] != base['light_end']
    v['extruded_bubble_ray_path'] = [0.5, 1, 0, -0.5, -1, 0.3]
    beam = scene.scene_knobs(v)
    # R34: Deep Light shafts and visible emitter MUST share the single real
    # source; changing Ray End remains independent and physically authored.
    assert beam['ray_source'] == beam['light_source'] == (3.6, 4.0, 0.0)
    assert beam['ray_end'] == (-9.0, -8.0, 5.3999999999999995)
    v['extruded_bubble_light_type'] = 'Sunlit Surface'
    surface = scene.scene_knobs(v)
    assert surface['ray_source'] == (9.0, 8.0, 0.0)
    assert surface['ray_source'] != surface['light_source']
    cleanup()


def test_ray_shader_uses_physical_path_and_bounded_opaque_proxy():
    shader = (ROOT/'rendering/gl_programs/extruded_bubble_program.py').read_text()
    render = (ROOT/'rendering/quick/visualizer/implementations/extruded_bubble.py').read_text()
    for uniform in ('uRaySource', 'uRayEnd', 'uBlock0', 'uParticleAtten'):
        assert uniform in shader and (uniform in render or (uniform == 'uBlock0' and 'f"uBlock{i}"' in render))
    assert 'acceptedBeamExtent(p)' in shader and 'sceneTransmittance' in shader
    assert '[:4]' in render and '0.08 * float(state.emission)' in render
