"""Sphere's real cube vertices use the single shared Scene3D projective camera."""
from __future__ import annotations
import itertools
import math
import pytest

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from rendering.gl_programs.scene3d import (
    SCENE3D_GLSL, SCENE3D_SPHERE_CAMERA_GLSL, scene3d_sphere_item_position,
)


def test_resting_pose_preserves_accepted_item_pixels():
    for geometry, p, strength in itertools.product(
        ((160.,100.,45.),(360.,240.,100.),(400.,150.,72.)),
        ((-1.,.4,-.6),(.5,-.8,.7),(0.,0.,0.),(.2,.5,1.)),
        (0.,.5,1.),
    ):
        w=(4.8 - p[2]*strength)/4.8
        expected=(geometry[0]+p[0]*geometry[2]/w,geometry[1]-p[1]*geometry[2]/w)
        assert scene3d_sphere_item_position(p,geometry,strength) == pytest.approx(expected,abs=1e-9)


def test_orbit_changes_projected_world_without_mutating_animated_shell_or_default_pose():
    geometry=(210.,140.,70.)
    point=(1.,.5,.25)
    resting=scene3d_sphere_item_position(point,geometry,1.)
    yawed=scene3d_sphere_item_position(point,geometry,1.,view=(math.pi/2.,0.))
    tilted=scene3d_sphere_item_position(point,geometry,1.,view=(0.,math.pi/4.))
    assert resting != yawed != tilted
    descriptor=get_visualizer_mode_descriptor('sphere')
    assert descriptor.geometry_kind=='freeform_3d'
    assert descriptor.layout_profile=='3d:sphere'
    assert descriptor.view_orbit_settings==('sphere_turn','sphere_tilt')
    assert 'sceneProjectAt' in SCENE3D_GLSL
    assert 'sceneProjectAt' in SCENE3D_SPHERE_CAMERA_GLSL


def test_sphere_view_keys_are_not_part_of_curated_presets():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes" / "sphere"
    for path in root.glob("preset_*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        settings = payload["snapshot"]["widgets"]["spotify_visualizer"]
        assert "sphere_turn" not in settings and "sphere_tilt" not in settings


def test_extruded_body_alpha_is_not_an_authored_setting_or_a_second_gl_alpha():
    from core.settings.default_contract import get_raw_default_settings
    from rendering.gl_programs.extruded_spectrum_program import EXTRUDED_FRAGMENT_SOURCE
    import json
    from pathlib import Path
    from core.settings.models import SpotifyVisualizerSettings

    default = get_raw_default_settings()["widgets"]["spotify_visualizer"]
    assert "extruded_spectrum_body_alpha" not in default
    assert "extruded_spectrum_body_alpha" not in SpotifyVisualizerSettings.__dataclass_fields__
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes" / "extruded_spectrum"
    for path in root.glob("preset_*.json"):
        settings = json.loads(path.read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]
        assert "extruded_spectrum_body_alpha" not in settings
    assert "uBodyAlpha" not in EXTRUDED_FRAGMENT_SOURCE
    assert "surfaceAlpha = uFill.a + (1.0 - uFill.a) * edgeAlpha;" in EXTRUDED_FRAGMENT_SOURCE


@pytest.mark.qt
def test_shared_scene3d_sphere_projection_matches_real_gpu(qt_app):
    """Compare the production shared camera's GLSL clip divide with CPU pixels.

    Also exercises view tilt/yaw, not merely the historically unchanged resting
    pose: a private Sphere projection could otherwise accidentally survive.
    """
    from tests.test_scene3d_glsl_mirrors import _GlslProbe, _check
    cases = [
        ((.3, .6, .1, 1.0), (210., 140., 70., 0.0), (0., 0.)),
        ((-.9, .8, -.3, .8), (400., 150., 72., .4), (.2, 0.)),
        ((1.1, -.5, .6, .5), (160., 100., 45., -.7), (.2, 1.)),
        ((.4, .2, .6, 1.0), (320., 200., 93., 0.0), (0., .3)),
    ]
    probe = _GlslProbe()
    try:
        result = probe.run(
            'vec4 a=arg(0), b=arg(1), c=arg(2);'
            'vec4 clip = sceneProjectSphere(mat4(1.0), vec2(800., 600.), a.xyz,'
            ' b.xyz, a.w, vec2(0.0), 1.0, vec2(b.w, c.x));'
            'FragColor = vec4(clip.xy/clip.w, 0.0, 1.0);',
            [[a, b, (tilt, 0., 0., 0.)] for a, b, (tilt, _) in cases],
            declarations=SCENE3D_SPHERE_CAMERA_GLSL,
        )
        expected = []
        for a, b, (tilt, _) in cases:
            px, py = scene3d_sphere_item_position(
                a[:3], b[:3], a[3], view=(b[3], tilt),
            )
            expected.append((px, py, 0., 1.))
        _check(result, expected)
    finally:
        probe.close()


def test_spin_direction_preserves_original_default_and_does_not_reverse_phase_clock():
    from core.settings.default_contract import get_raw_default_settings
    from rendering.quick.visualizer.implementations.sphere_voxel import _VERTEX_SOURCE
    defaults = get_raw_default_settings()['widgets']['spotify_visualizer']
    assert defaults['sphere_spin_direction'] == 'Default'
    assert "uSpinMode == 1 ? vec3(-0.21, -0.57, -0.29)" in _VERTEX_SOURCE
    assert "vec3(0.21, 0.57, 0.29)" in _VERTEX_SOURCE
    assert 'uRotationPhase * axes' in _VERTEX_SOURCE

def test_sphere_edit_cage_uses_live_presentation_orbit_even_with_accepted_logical_frame():
    import inspect
    from engine.display_manager import DisplayManager
    source = inspect.getsource(DisplayManager._refresh_quick_visualizer_edit_content_envelope)
    assert "logical.mode_id == 'sphere'" in source
    assert "if accepted_parameters is not None and logical.mode_id == 'sphere':" in source
    assert 'accepted_parameters.update(view_orbit_values(' in source
