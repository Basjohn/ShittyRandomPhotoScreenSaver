"""Focused Phase-C contract tests for the Quick Ripple/Raindrops renderer."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from rendering.gl_programs.raindrops_program import raindrops_program
from rendering.quick.transitions.implementations.ripple import (
    _ripple_count,
    _ripple_seed,
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


def test_ripple_resolves_lazily_and_only_imports_its_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'ripple', enabled_transition_ids=frozenset({'ripple'})
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
        "renderer": "QuickRippleRenderer",
        "mods": ["rendering.quick.transitions.implementations.ripple"],
        "shader_mods": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.raindrops_program",
        ],
    }


def test_ripple_disabled_resolution_keeps_surface_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'ripple', enabled_transition_ids=frozenset()
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
print(json.dumps({'resolved': renderer is not None, 'mods': mods}))
"""
    )
    assert report == {"resolved": False, "mods": []}


def test_ripple_requires_resolved_count_and_seed():
    assert _ripple_count({"ripple_count": 3}) == 3
    assert _ripple_seed({"ripple_seed": 123.5}) == pytest.approx(123.5)
    with pytest.raises(ValueError, match="resolved integer parameter 'ripple_count'"):
        _ripple_count({"ripple_count": 3.0})
    with pytest.raises(ValueError, match="between 1 and 8"):
        _ripple_count({"ripple_count": 9})
    with pytest.raises(ValueError, match="resolved numeric parameter 'ripple_seed'"):
        _ripple_seed({})
    with pytest.raises(ValueError, match="must be finite"):
        _ripple_seed({"ripple_seed": float("nan")})


def test_ripple_reuses_exact_authored_shader_and_multi_source_behavior():
    from rendering.quick.transitions.implementations import ripple as quick_ripple

    assert quick_ripple.raindrops_program.fragment_source == raindrops_program.fragment_source
    shader = raindrops_program.fragment_source
    assert "if (i == 0)" in shader
    assert "center = vec2(0.5, 0.5)" in shader
    assert "u_ripple_seed" in shader
    assert "totalWave += wave" in shader
    assert "bestRingMask" in shader
    assert "smoothstep(0.78, 0.95, t)" in shader


def test_ripple_quick_renderer_has_no_legacy_presenter_fallback():
    from pathlib import Path

    source = Path(
        "rendering/quick/transitions/implementations/ripple.py"
    ).read_text(encoding="utf-8")
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source
    assert "QWidget" not in source
