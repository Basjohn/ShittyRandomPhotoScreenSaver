"""Admission and strict-parameter contracts for the Quick Crumble renderer."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

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
        "weight_mode": 3.0,
        "depth": 0.85,
        "thickness": 0.65,
        "debris": 0.65,
    }
    values.update(updates)
    return values


def test_crumble_resolves_lazily_and_only_imports_its_surface():
    report = _probe("""
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer('crumble', enabled_transition_ids=frozenset({'crumble'}))
print(json.dumps({
 'renderer': type(renderer).__name__,
 'mods': sorted(name for name in sys.modules if name.startswith('rendering.quick.transitions.implementations.')),
 'shader_mods': sorted(name for name in sys.modules if name.startswith('rendering.gl_programs.') and name.endswith('_program')),
}))
""")
    assert report == {
        "renderer": "QuickCrumbleRenderer",
        "mods": ["rendering.quick.transitions.implementations.crumble"],
        "shader_mods": ["rendering.gl_programs.crumble_program"],
    }


def test_crumble_disabled_resolution_keeps_surface_dormant():
    report = _probe("""
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer('crumble', enabled_transition_ids=frozenset())
print(json.dumps({'resolved': renderer is not None, 'mods': sorted(name for name in sys.modules if name.startswith('rendering.quick.transitions.implementations.'))}))
""")
    assert report == {"resolved": False, "mods": []}


def test_crumble_requires_fully_resolved_volume_parameters():
    assert _crumble_parameters(_params()) == (123.25, 14, 1.0, 3.0, 0.85, 0.65, 0.65)
    for field, value in (
        ("seed", None),
        ("depth", None),
        ("thickness", float("nan")),
        ("debris", 1.1),
    ):
        with pytest.raises(ValueError):
            _crumble_parameters(_params(**{field: value}))
    with pytest.raises(ValueError, match="integer between 4 and 128"):
        _crumble_parameters(_params(piece_count=129))
    with pytest.raises(ValueError, match="between 0.5 and 2.0"):
        _crumble_parameters(_params(crack_complexity=2.1))
    with pytest.raises(ValueError, match="between 0.0 and 4.0"):
        _crumble_parameters(_params(weight_mode=4.5))


def test_crumble_quick_renderer_has_no_legacy_presenter_or_flat_shader_dependency():
    from pathlib import Path

    source = Path("rendering/quick/transitions/implementations/crumble.py").read_text(
        encoding="utf-8"
    )
    assert all(
        term not in source
        for term in ("GLCompositorWidget", "DisplayWidget", "QWidget", "BaseGLProgram")
    )
