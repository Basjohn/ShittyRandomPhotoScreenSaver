"""Focused C3 contract gates for the Quick Blinds transition."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from rendering.gl_programs.blinds_program import blinds_program
from rendering.quick.transitions.implementations.blinds import (
    _blinds_direction_mode,
    _blinds_feather,
    _blinds_grid,
)


ROOT = Path(__file__).resolve().parents[1]


def _probe(source: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def test_blinds_disabled_resolution_keeps_implementation_and_shader_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "blinds",
    enabled_transition_ids=frozenset(),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": renderer is not None,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": False,
        "implementation_modules": [],
        "shader_modules": [],
    }


def test_blinds_enabled_resolution_imports_only_its_lazy_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import (
    resolve_quick_transition_renderer,
)

renderer = resolve_quick_transition_renderer(
    "blinds",
    enabled_transition_ids=frozenset({"blinds"}),
)
implementation_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.quick.transitions.implementations.")
)
shader_modules = sorted(
    name for name in sys.modules
    if name.startswith("rendering.gl_programs.") and name.endswith("_program")
)
print(json.dumps({
    "renderer": type(renderer).__name__,
    "implementation_modules": implementation_modules,
    "shader_modules": shader_modules,
}))
"""
    )

    assert report == {
        "renderer": "QuickBlindsRenderer",
        "implementation_modules": [
            "rendering.quick.transitions.implementations.blinds"
        ],
        "shader_modules": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.blinds_program",
        ],
    }


@pytest.mark.parametrize(
    ("direction", "mode"),
    (
        ("Horizontal", 0),
        ("horizontal", 0),
        ("Vertical", 1),
        ("vertical", 1),
        ("Diagonal", 2),
        ("diagonal", 2),
    ),
)
def test_blinds_preserves_all_authored_direction_modes(direction, mode):
    assert _blinds_direction_mode(direction) == mode


def test_blinds_rejects_unresolved_random_or_unknown_direction():
    with pytest.raises(ValueError, match="unknown resolved Blinds direction"):
        _blinds_direction_mode("Random")
    with pytest.raises(ValueError, match="unknown resolved Blinds direction"):
        _blinds_direction_mode("sideways")


def test_blinds_requires_resolved_shader_feather():
    assert _blinds_feather({"feather": 0.04}) == pytest.approx(0.04)
    assert _blinds_feather({"feather": 0.5}) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="requires resolved numeric parameter 'feather'"):
        _blinds_feather({})
    with pytest.raises(ValueError, match="requires resolved numeric parameter 'feather'"):
        _blinds_feather({"feather": True})
    with pytest.raises(ValueError, match="must be finite"):
        _blinds_feather({"feather": math.nan})
    with pytest.raises(ValueError, match="must be between"):
        _blinds_feather({"feather": 0.0001})
    with pytest.raises(ValueError, match="must be between"):
        _blinds_feather({"feather": 0.51})


def test_blinds_grid_preserves_old_effective_14_column_aspect_mapping():
    assert _blinds_grid((1920.0, 1080.0)) == (14, 8)
    assert _blinds_grid((560.0, 315.0)) == (14, 8)
    assert _blinds_grid((1080.0, 1920.0)) == (14, 25)
    assert _blinds_grid((4000.0, 200.0)) == (14, 2)
    with pytest.raises(ValueError, match="must be positive"):
        _blinds_grid((0.0, 1080.0))


def test_blinds_reuses_the_authored_shader_without_simplifying_its_visual_stack():
    source = blinds_program.fragment_source
    assert "if (u_direction == 2)" in source
    assert "fract(diag * bands)" in source
    assert "vec2 uvLocal" in source
    assert "float half = 0.5 * w" in source
    assert "smoothstep(left - feather, left, coord)" in source
    assert "smoothstep(0.96, 1.0, t)" in source
    assert "FragColor = mix(oldColor, newColor, mixFactor);" in source


def test_quick_blinds_renderer_compiles_the_existing_authored_fragment_source():
    renderer_source = (
        ROOT
        / "rendering"
        / "quick"
        / "transitions"
        / "implementations"
        / "blinds.py"
    ).read_text(encoding="utf-8")
    assert "blinds_program.fragment_source" in renderer_source
    assert "_BLINDS_FRAGMENT_SOURCE" not in renderer_source
    assert 'uniforms["u_progress"]' in renderer_source
    assert 'uniforms["u_grid"]' in renderer_source
    assert 'uniforms["u_feather"]' in renderer_source
    assert 'uniforms["u_direction"]' in renderer_source
