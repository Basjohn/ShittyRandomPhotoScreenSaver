"""Focused Phase-C contract tests for the Quick Crumble renderer."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from rendering.gl_programs.crumble_program import crumble_program
from rendering.quick.transitions.implementations.crumble import _crumble_parameters


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
        "seed": 123.25,
        "piece_count": 14,
        "crack_complexity": 1.0,
        "mosaic_mode": False,
        "weight_mode": 3.0,
    }
    values.update(updates)
    return values


def test_crumble_resolves_lazily_and_only_imports_its_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'crumble', enabled_transition_ids=frozenset({'crumble'})
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
        "renderer": "QuickCrumbleRenderer",
        "mods": ["rendering.quick.transitions.implementations.crumble"],
        "shader_mods": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.crumble_program",
        ],
    }


def test_crumble_disabled_resolution_keeps_surface_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'crumble', enabled_transition_ids=frozenset()
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
print(json.dumps({'resolved': renderer is not None, 'mods': mods}))
"""
    )
    assert report == {"resolved": False, "mods": []}


def test_crumble_requires_fully_resolved_authored_parameters():
    assert _crumble_parameters(_params()) == (123.25, 14, 1.0, False, 3.0)
    with pytest.raises(ValueError, match="resolved numeric parameter 'seed'"):
        _crumble_parameters(_params(seed=None))
    with pytest.raises(ValueError, match="resolved integer parameter 'piece_count'"):
        _crumble_parameters(_params(piece_count=14.0))
    with pytest.raises(ValueError, match="at least 4"):
        _crumble_parameters(_params(piece_count=3))
    with pytest.raises(ValueError, match="between 0.5 and 2.0"):
        _crumble_parameters(_params(crack_complexity=2.1))
    with pytest.raises(ValueError, match="resolved boolean parameter 'mosaic_mode'"):
        _crumble_parameters(_params(mosaic_mode=0))
    with pytest.raises(ValueError, match="one of 0, 1, 2, 3, 4"):
        _crumble_parameters(_params(weight_mode=4.5))


def test_crumble_reuses_exact_authored_shader_and_physics_stack():
    from rendering.quick.transitions.implementations import crumble as quick_crumble

    assert quick_crumble.crumble_program.fragment_source == crumble_program.fragment_source
    shader = crumble_program.fragment_source
    assert "vec4 voronoi" in shader
    assert "getPieceTransform" in shader
    assert "pieceFall * pieceFall * pieceFall" in shader
    assert "float rotAngle" in shader
    assert "if (t < 0.05)" in shader
    assert "if (t >= 0.995)" in shader
    assert "u_weight_mode" in shader


def test_crumble_quick_renderer_has_no_legacy_presenter_dependency():
    from pathlib import Path

    source = Path(
        "rendering/quick/transitions/implementations/crumble.py"
    ).read_text(encoding="utf-8")
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source
    assert "QWidget" not in source
