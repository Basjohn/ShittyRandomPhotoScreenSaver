"""Focused Phase-C preservation tests for the Quick Burn renderer."""

from __future__ import annotations

import json
from types import SimpleNamespace
import subprocess
import sys

import pytest

from rendering.gl_programs.burn_program import burn_program
from rendering.quick.transitions.implementations.burn import (
    _burn_effect_time_seconds,
    _burn_parameters,
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


def _params(**updates):
    values = {
        "direction": 4,
        "jaggedness": 0.55,
        "glow_intensity": 0.72,
        "glow_color": (1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0),
        "ember_color": (230.0 / 255.0, 64.0 / 255.0, 13.0 / 255.0, 1.0),
        "char_width": 0.5,
        "smoke_enabled": True,
        "smoke_density": 0.5,
        "ash_enabled": True,
        "ash_density": 0.5,
        "seed": 321.25,
    }
    values.update(updates)
    return values


def test_burn_resolves_lazily_and_only_imports_its_surface():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'burn', enabled_transition_ids=frozenset({'burn'})
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
        "renderer": "QuickBurnRenderer",
        "mods": ["rendering.quick.transitions.implementations.burn"],
        "shader_mods": [
            "rendering.gl_programs.base_program",
            "rendering.gl_programs.burn_program",
        ],
    }


def test_burn_disabled_resolution_keeps_surface_dormant():
    report = _probe(
        """
import json
import sys
from rendering.quick.transitions.implementation_registry import resolve_quick_transition_renderer
renderer = resolve_quick_transition_renderer(
    'burn', enabled_transition_ids=frozenset()
)
mods = sorted(
    name for name in sys.modules
    if name.startswith('rendering.quick.transitions.implementations.')
)
print(json.dumps({'resolved': renderer is not None, 'mods': mods}))
"""
    )
    assert report == {"resolved": False, "mods": []}


@pytest.mark.parametrize("direction", range(6))
def test_burn_preserves_all_six_authored_directions(direction):
    assert _burn_parameters(_params(direction=direction)).direction == direction


def test_burn_rejects_unresolved_or_invalid_direction():
    with pytest.raises(ValueError, match="resolved integer parameter 'direction'"):
        _burn_parameters(_params(direction="Random"))
    with pytest.raises(ValueError, match="between 0 and 5"):
        _burn_parameters(_params(direction=6))


def test_burn_requires_normalized_user_glow_color_and_full_effect_controls():
    params = _burn_parameters(_params())
    assert params.glow_color == pytest.approx((1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0))
    assert params.ember_color == pytest.approx((230.0 / 255.0, 64.0 / 255.0, 13.0 / 255.0, 1.0))
    assert params.smoke_enabled is True
    assert params.ash_enabled is True
    with pytest.raises(ValueError, match="normalized RGBA tuple"):
        _burn_parameters(_params(glow_color=(1.0, 0.5, 0.1)))
    with pytest.raises(ValueError, match="between 0 and 1"):
        _burn_parameters(_params(glow_color=(255.0, 140.0, 30.0, 255.0)))
    with pytest.raises(ValueError, match="normalized RGBA tuple"):
        _burn_parameters(_params(ember_color=(0.9, 0.25, 0.05)))
    with pytest.raises(ValueError, match="resolved boolean parameter 'smoke_enabled'"):
        _burn_parameters(_params(smoke_enabled=1))
    with pytest.raises(ValueError, match="char_width must be between 0.1 and 1"):
        _burn_parameters(_params(char_width=0.05))


def test_burn_effect_time_is_derived_from_the_authored_run_clock():
    frame = SimpleNamespace(
        sample=SimpleNamespace(linear_progress=0.25),
        run=SimpleNamespace(request=SimpleNamespace(duration_ms=2400)),
    )
    assert _burn_effect_time_seconds(frame) == pytest.approx(0.6)


def test_burn_reuses_exact_authored_shader_and_complete_visual_stack():
    from rendering.quick.transitions.implementations import burn as quick_burn

    assert quick_burn.burn_program.fragment_source == burn_program.fragment_source
    shader = burn_program.fragment_source
    for needle in (
        "if (t <= 0.0)",
        "if (t >= 1.0)",
        "float ignition = 0.05",
        "fbm4",
        "warped_fbm",
        "distort_offset",
        "white-hot burn line",
        "Char zone",
        "smoulder",
        "Sparks / embers",
        "Falling ash",
        "Smoke wisps",
        "tail_fade",
        "u_glow_color",
        "u_ember_color",
        "u_seed",
        "u_time",
    ):
        assert needle in shader


def test_burn_quick_renderer_has_no_wall_clock_or_legacy_presenter_dependency():
    from pathlib import Path

    source = Path(
        "rendering/quick/transitions/implementations/burn.py"
    ).read_text(encoding="utf-8")
    assert "time.monotonic" not in source
    assert "GLCompositorWidget" not in source
    assert "DisplayWidget" not in source
    assert "QWidget" not in source
