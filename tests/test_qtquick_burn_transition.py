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
        "flames": False,
        "ember_veins": False,
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


def test_burn_requires_resolved_flame_and_vein_switches():
    params = _burn_parameters(_params(flames=True))
    assert params.flames is True and params.ember_veins is False
    with pytest.raises(ValueError, match="resolved boolean parameter 'flames'"):
        _burn_parameters(_params(flames=1))
    with pytest.raises(ValueError, match="resolved boolean parameter 'ember_veins'"):
        _burn_parameters(_params(ember_veins=None))


def _burn_frames(capture, progress, **switches):
    import numpy as np

    settings = {"burn": {"direction": "Top to Bottom", "smoke_enabled": False, "ash_enabled": False,
                         "char_width": 0.8, **switches}}
    run = capture.run("burn", settings=settings, duration_ms=8000)
    return np.asarray(capture.render(run, progress)[0].convert("RGB"), dtype=np.int16)


@pytest.mark.qt
def test_flames_rise_from_the_burning_edge_and_veins_glow_only_in_the_char(qt_app):
    import numpy as np
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(320, 180)
    try:
        source, destination = (np.asarray(image.convert("RGB"), dtype=np.int16) for image in capture.images)
        plain = _burn_frames(capture, 0.45)
        # The burning band: neither picture (glow, line and char).
        band = (np.abs(plain - source).max(axis=2) > 2) & (np.abs(plain - destination).max(axis=2) > 2)
        rows = np.nonzero(band.any(axis=1))[0]
        assert rows.size
        flames = _burn_frames(capture, 0.45, flames=True)
        changed = np.abs(flames - plain).max(axis=2) > 0
        assert changed.any()
        # Top to Bottom: flames rise from the edge into the burned picture above it, never
        # below the burning band; and they reach above the band.
        changed_rows = np.nonzero(changed.any(axis=1))[0]
        assert changed_rows.max() <= rows.max() + 2
        assert changed_rows.min() < rows.min()
        veins = _burn_frames(capture, 0.45, ember_veins=True)
        vein_changes = np.abs(veins - plain).max(axis=2) > 0
        assert vein_changes.any() and not (vein_changes & ~band).any()
        for progress in (0.002, 0.998):
            both = _burn_frames(capture, progress, flames=True, ember_veins=True)
            target = source if progress < 0.5 else destination
            assert np.abs(both - target).mean() < 0.5
    finally:
        capture.close()
