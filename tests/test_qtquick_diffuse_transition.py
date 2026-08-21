"""Focused Phase-C contract tests for the Quick Diffuse renderer."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from rendering.gl_programs.diffuse_program import diffuse_program
from rendering.quick.transitions.implementations.diffuse import (
    _diffuse_block_size,
    _diffuse_grid,
    _diffuse_shape_mode,
)


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


def test_diffuse_resolves_lazily_without_importing_other_transition_surfaces():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'diffuse', enabled_transition_ids=frozenset({'diffuse'})
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
        "renderer": "QuickDiffuseRenderer",
        "mods": ["rendering.quick.transitions.implementations.diffuse"],
        "shader_mods": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.diffuse_program",
        ],
    }


def test_diffuse_disabled_resolution_keeps_implementation_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'diffuse', enabled_transition_ids=frozenset()
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
print(json.dumps({'resolved': renderer is not None, 'mods': mods}))
"""
    )
    assert report == {"resolved": False, "mods": []}


def test_diffuse_requires_resolved_integer_block_size_and_shape_mode():
    assert _diffuse_block_size({"block_size": 15}) == 15
    assert _diffuse_shape_mode({"shape_mode": 5}) == 5
    with pytest.raises(ValueError, match="resolved integer parameter 'block_size'"):
        _diffuse_block_size({})
    with pytest.raises(ValueError, match="resolved integer parameter 'shape_mode'"):
        _diffuse_shape_mode({"shape_mode": "Random"})
    with pytest.raises(ValueError, match="between 0 and 5"):
        _diffuse_shape_mode({"shape_mode": 6})


def test_diffuse_grid_preserves_old_block_size_geometry():
    assert _diffuse_grid((1920.0, 1080.0), 50) == (39, 22)
    assert _diffuse_grid((2560.0, 1440.0), 15) == (171, 96)
    assert _diffuse_grid((10.0, 10.0), 50) == (1, 1)


def test_diffuse_reuses_exact_authored_shader_and_shape_stack():
    from rendering.quick.transitions.implementations import diffuse as quick_diffuse

    assert quick_diffuse.diffuse_program.fragment_source == diffuse_program.fragment_source
    shader = diffuse_program.fragment_source
    assert "u_shapeMode == 1" in shader
    assert "u_shapeMode == 2" in shader
    assert "u_shapeMode == 3" in shader
    assert "u_shapeMode == 4" in shader
    assert "u_shapeMode == 5" in shader
    assert "smoothstep(0.92, 1.0, t)" in shader
    assert "smoothstep(0.88, 1.0, t)" in shader
    assert "smoothstep(0.96, 1.0, t)" in shader


def test_diffuse_quick_renderer_has_no_old_presenter_dependency():
    from pathlib import Path

    source = Path(
        "rendering/quick/transitions/implementations/diffuse.py"
    ).read_text(encoding="utf-8")
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source
    assert "QWidget" not in source
