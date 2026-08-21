"""Focused Phase-C contract tests for the Quick Particle renderer."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from rendering.gl_programs.particle_program import particle_program
from rendering.quick.transitions.implementations.particle import _particle_parameters


def _probe(source: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", source],
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _params(**updates):
    values = {
        "seed": 12.5,
        "mode": 1,
        "direction": 8,
        "particle_radius": 10.0,
        "overlap": 4.0,
        "trail_length": 0.15,
        "trail_strength": 0.6,
        "swirl_strength": 1.0,
        "swirl_turns": 3.0,
        "use_3d_shading": True,
        "texture_mapping": True,
        "wobble": True,
        "gloss_size": 72.0,
        "light_direction": 1,
        "swirl_order": 0,
    }
    values.update(updates)
    return values


def test_particle_resolves_lazily_and_only_imports_its_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'particle', enabled_transition_ids=frozenset({'particle'})
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
shader_mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.gl_programs.') and name.endswith('_program')
)
print(json.dumps({
    'renderer': type(renderer).__name__,
    'mods': mods,
    'shader_mods': shader_mods,
}))
"""
    )
    assert report == {
        "renderer": "QuickParticleRenderer",
        "mods": ["rendering.quick.transitions.implementations.particle"],
        "shader_mods": ["rendering.gl_programs.particle_program"],
    }


def test_particle_disabled_resolution_keeps_surface_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'particle', enabled_transition_ids=frozenset()
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
print(json.dumps({'resolved': renderer is not None, 'mods': mods}))
"""
    )
    assert report == {"resolved": False, "mods": []}


def test_particle_requires_random_mode_to_be_resolved_before_rendering():
    params = _particle_parameters(_params())
    assert params.mode == 1
    assert params.direction == 8
    with pytest.raises(ValueError, match="resolved to 0, 1, or 2"):
        _particle_parameters(_params(mode=3))


def test_particle_validates_full_authored_parameter_surface():
    params = _particle_parameters(_params())
    assert params.particle_radius == pytest.approx(10.0)
    assert params.trail_strength == pytest.approx(0.6)
    assert params.use_3d_shading is True
    assert params.texture_mapping is True
    assert params.wobble is True
    assert params.gloss_size == pytest.approx(72.0)
    assert params.light_direction == 1
    with pytest.raises(ValueError, match="smaller than particle diameter"):
        _particle_parameters(_params(overlap=20.0))
    with pytest.raises(ValueError, match="between 0 and 1"):
        _particle_parameters(_params(trail_length=1.1))
    with pytest.raises(ValueError, match="between 16 and 128"):
        _particle_parameters(_params(gloss_size=150.0))
    with pytest.raises(ValueError, match="resolved boolean parameter 'wobble'"):
        _particle_parameters(_params(wobble=1))


def test_particle_reuses_full_authored_shader_instead_of_flat_reveal():
    from rendering.quick.transitions.implementations import particle as quick_particle

    assert quick_particle.particle_program.fragment_source == particle_program.fragment_source
    shader = particle_program.fragment_source
    assert "getSpawnDirection" in shader
    assert "getSwirlOrderKey" in shader
    assert "getConvergeOrderKey" in shader
    assert "shade3DBall" in shader
    assert "u_trail_length" in shader
    assert "u_wobble" in shader
    assert "u_gloss_size" in shader
    assert "u_texture_map" in shader
    assert "if (t <= 0.0)" in shader
    assert "if (t >= FINAL_BLEND_END)" in shader
    assert "smoothstep(FINAL_BLEND_START, FINAL_BLEND_END, t)" in shader


def test_particle_quick_renderer_has_no_legacy_presenter_dependency():
    from pathlib import Path

    source = Path(
        "rendering/quick/transitions/implementations/particle.py"
    ).read_text(encoding="utf-8")
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source
    assert "QWidget" not in source
