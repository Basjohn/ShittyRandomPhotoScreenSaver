"""Sphere's declarations preserve configure-owned state and bespoke authoring behavior."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import Slider, require_mode_settings


@pytest.mark.parametrize("key", ("sphere_finish", "sphere_light_direction"))
def test_sphere_invalid_strict_ingress_choices_remain_authority_errors(key):
    from core.settings.models import SpotifyVisualizerSettings

    with pytest.raises(ValueError, match=key.replace("_", "[ _]")):
        SpotifyVisualizerSettings.from_mapping({key: "invalid"}, apply_preset_overlay=False)


def test_sphere_each_control_installs_once_and_freezes_only_on_logical_configuration():
    from widgets.spotify_visualizer import config_applier
    from widgets.spotify_visualizer.render_state import FrozenFields

    class Owner:
        def __init__(self):
            object.__setattr__(self, "writes", {})

        def __setattr__(self, key, value):
            self.writes[key] = self.writes.get(key, 0) + 1
            object.__setattr__(self, key, value)

    spec = require_mode_settings("sphere")
    assert len(spec.logical_controls()) == 39
    assert spec.controls is spec.controls
    assert spec.logical_controls() is spec.logical_controls()
    assert spec.presentation_controls() is spec.presentation_controls()
    assert config_applier._SPHERE_PARAMETER_KEYS == tuple(control.key for control in spec.logical_controls())
    assert {control.key for control in spec.presentation_controls()} == {"sphere_mirror", "sphere_turn", "sphere_tilt"}
    assert {control.key for control in spec.authoring_controls()} == {"sphere_finish"}
    defaults = require_canonical_default("widgets.spotify_visualizer")
    values = {control.key: defaults[control.key] for control in spec.controls}
    values.update({"sphere_light_direction": " ne ", "sphere_mirror": 0.71})
    logical, presentation = Owner(), Owner()
    config_applier.apply_logical_vis_mode_kwargs(logical, values)
    config_applier.apply_presentation_vis_mode_kwargs(presentation, values)
    assert logical.writes == {**{f"_{control.key}": 1 for control in spec.logical_controls()}, "_sphere_parameters": 1}
    assert presentation.writes == {f"_{control.key}": 1 for control in spec.presentation_controls()}
    assert isinstance(logical._sphere_parameters, FrozenFields)
    assert logical._sphere_parameters["sphere_light_direction"] == "NE"
    assert isinstance(logical._sphere_fill_color, tuple)
    for owner in (logical, presentation):
        assert not hasattr(owner, "_sphere_finish")
    before = logical._sphere_parameters
    config_applier.apply_logical_vis_mode_kwargs(logical, {"sphere_finish": "Matte"})
    config_applier.apply_presentation_vis_mode_kwargs(presentation, {"sphere_mirror": 0.0})
    assert logical._sphere_parameters is before
    config_applier.apply_logical_vis_mode_kwargs(logical, {"sphere_gloss": 0.63})
    assert logical._sphere_parameters is not before
    assert logical._sphere_parameters["sphere_gloss"] == 0.63
    # Trusted runtime boolean coercion retains the existing bool(value) behavior.
    config_applier.apply_logical_vis_mode_kwargs(logical, {"sphere_shadow_enabled": "false"})
    assert logical._sphere_shadow_enabled is True


@pytest.mark.parametrize("key, value, presentation", [
    ("sphere_gloss", "invalid", False), ("sphere_gloss", float("nan"), False),
    ("sphere_fragment_strength", float("inf"), False),
    ("sphere_fill_color", [1, 2], False), ("sphere_edge_color", [1, 2, float("nan"), 255], False),
    ("sphere_spin_direction", "invalid", False), ("sphere_light_direction", "invalid", False),
    ("sphere_mirror", float("nan"), True), ("sphere_turn", "invalid", True),
])
def test_sphere_malformed_direct_runtime_values_raise_without_default_substitution(key, value, presentation):
    from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs

    apply = apply_presentation_vis_mode_kwargs if presentation else apply_logical_vis_mode_kwargs
    owner = SimpleNamespace()
    with pytest.raises(ValueError, match=key):
        apply(owner, {key: value})
    assert not hasattr(owner, f"_{key}")


