"""Ensure an active Bubble decoration setting reaches its real owning consumer.

A missing Glow Spread in the immutable render frame crashed --perf users on
Slice 11. Auditing only default/preset round trips cannot find this problem.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings


_ROOT = Path(__file__).resolve().parents[1]


def _dispatch_keys() -> set[str]:
    tree = ast.parse((_ROOT / 'widgets/spotify_visualizer/tick_pipeline.py').read_text())
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            continue
        if (call.func.attr != 'update' or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != 'sim_settings' or not call.args):
            continue
        source = call.args[0]
        if isinstance(source, ast.Dict):
            return {key.value for key in source.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    raise AssertionError('Could not find Bubble authored sim_settings dispatch')


def test_every_logical_ambient_control_is_forwarded_to_the_bubble_runtime():
    spec = require_mode_settings('bubble')
    expected = {control.key for control in spec.controls
                if control.bucket == 'particles' and control.logical}
    missing = expected - _dispatch_keys()
    assert not missing, f'Ambient controls silently ignored by Bubble tick: {sorted(missing)}'


def test_glow_spread_is_renderer_owned_and_release_is_simulation_owned():
    spec = require_mode_settings('bubble')
    assert spec.control('bubble_particle_glow_spread') in spec.presentation_controls()
    assert spec.control('bubble_particle_glow_spread') not in spec.logical_controls()
    assert spec.control('bubble_particle_glow_release_ms') in spec.logical_controls()
    assert 'bubble_particle_glow_release_ms' in _dispatch_keys()


def test_rendered_glow_spread_reaches_the_immutable_frame_parameter_path():
    from widgets.spotify_visualizer.config_applier import (
        _apply_spec_controls, spec_mode_parameters,
    )
    from rendering.quick.visualizer.implementation_values import parameter

    defaults = require_canonical_default('widgets.spotify_visualizer')
    spec = require_mode_settings('bubble')
    owner = SimpleNamespace()
    # This is the production presentation applier and the exact production
    # immutable-frame parameter extractor, not a synthetic substitute for them.
    _apply_spec_controls(owner, dict(defaults), logical=False)
    for authored in (0.6, 1.0, 2.0):
        _apply_spec_controls(owner, {'bubble_particle_glow_spread': authored}, logical=False)
        params = spec_mode_parameters(owner, spec.mode_id)
        assert float(parameter(params, 'bubble_particle_glow_spread')) == authored
