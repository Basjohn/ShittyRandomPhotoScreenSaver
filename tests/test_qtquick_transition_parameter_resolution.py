"""Phase-C request-boundary resolution tests for parameterized effects."""

from __future__ import annotations

import pytest

from rendering.quick.transitions.parameter_resolution import (
    resolve_parameterized_phase_c_inputs,
)


class _Rng:
    def __init__(self) -> None:
        self.random_values = iter((0.125, 0.25, 0.375, 0.5, 0.625))
        self.choice_values: list[object] = []
        self.randint_values: list[int] = []

    def random(self) -> float:
        return next(self.random_values)

    def choice(self, seq):
        if self.choice_values:
            return self.choice_values.pop(0)
        return seq[0]

    def randint(self, a: int, b: int) -> int:
        if self.randint_values:
            return self.randint_values.pop(0)
        return a


def test_blinds_resolves_random_direction_and_ui_feather_before_request():
    rng = _Rng()
    rng.choice_values = ["Diagonal"]
    resolved = resolve_parameterized_phase_c_inputs(
        "blinds",
        {"blinds": {"direction": "Random", "feather": 2}},
        random_source=rng,
    )
    assert resolved.direction == "diagonal"
    assert resolved.parameter_dict() == {"feather": pytest.approx(0.04)}


def test_diffuse_resolves_shape_name_and_block_size():
    resolved = resolve_parameterized_phase_c_inputs(
        "diffuse",
        {"diffuse": {"block_size": 15, "shape": "Membrane"}},
        random_source=_Rng(),
    )
    assert resolved.direction is None
    assert resolved.parameter_dict() == {"block_size": 15, "shape_mode": 1}


def test_ripple_generates_seed_once_before_render_ownership():
    resolved = resolve_parameterized_phase_c_inputs(
        "ripple",
        {"ripple": {"ripple_count": 3}},
        random_source=_Rng(),
    )
    assert resolved.parameter_dict() == {
        "ripple_count": 3,
        "ripple_seed": pytest.approx(125.0),
    }


def test_crumble_preserves_current_factory_weighting_fallthroughs():
    for label, expected in (
        ("Random Choice", 3.0),
        ("Bias Old Image", 0.0),
        ("Bias New Image", 0.0),
        ("Top Weighted", 0.0),
        ("Bottom Weighted", 1.0),
        ("Random Weighted", 2.0),
        ("Age Weighted", 4.0),
    ):
        resolved = resolve_parameterized_phase_c_inputs(
            "crumble",
            {"crumble": {"piece_count": 16, "crack_complexity": 1.0, "weighting": label}},
            random_source=_Rng(),
        )
        params = resolved.parameter_dict()
        assert params["weight_mode"] == expected
        assert params["mosaic_mode"] is False


def test_particle_preserves_current_numeric_semantics_for_ui_indices():
    resolved = resolve_parameterized_phase_c_inputs(
        "particle",
        {
            "particle": {
                "mode": "Swirl",
                "direction": "Random",
                "particle_radius": 9.0,
                "overlap": 4.0,
                "trail_length": 0.15,
                "trail_strength": 0.6,
                "swirl_strength": 1.0,
                "swirl_turns": 3.0,
                "use_3d_shading": True,
                "texture_mapping": True,
                "wobble": True,
                "gloss_size": 72.0,
                "light_direction": 4,
                "swirl_order": 2,
            }
        },
        random_source=_Rng(),
    )
    params = resolved.parameter_dict()
    assert params["mode"] == 1
    # Current old factory does not recognize the UI spelling "Random" and
    # therefore feeds directional value 0. Preserve that until H0 deliberately fixes it.
    assert params["direction"] == 0
    assert params["light_direction"] == 4
    assert params["swirl_order"] == 2
    assert params["particle_radius"] == pytest.approx(9.0)


def test_particle_random_mode_is_fully_resolved_before_request():
    rng = _Rng()
    rng.choice_values = [0]
    rng.randint_values = [9]
    resolved = resolve_parameterized_phase_c_inputs(
        "particle",
        {"particle": {"mode": "Random", "direction": "Left to Right"}},
        random_source=rng,
    )
    params = resolved.parameter_dict()
    assert params["mode"] == 0
    assert params["direction"] == 9
    assert params["seed"] == pytest.approx(125.0)


def test_particle_resolution_rejects_grid_destroying_overlap():
    with pytest.raises(ValueError, match="smaller than particle diameter"):
        resolve_parameterized_phase_c_inputs(
            "particle",
            {"particle": {"particle_radius": 8.0, "overlap": 16.0}},
            random_source=_Rng(),
        )


def test_burn_normalizes_user_rgba_and_resolves_random_direction_and_seed():
    rng = _Rng()
    rng.randint_values = [5]
    resolved = resolve_parameterized_phase_c_inputs(
        "burn",
        {
            "burn": {
                "direction": "Random",
                "jaggedness": 1.0,
                "glow_intensity": 1.0,
                "glow_color": [255, 162, 0, 255],
                "char_width": 0.1,
                "smoke_enabled": True,
                "smoke_density": 0.8,
                "ash_enabled": True,
                "ash_density": 0.8,
            }
        },
        random_source=rng,
    )
    params = resolved.parameter_dict()
    assert params["direction"] == 5
    assert params["glow_color"] == pytest.approx((1.0, 162.0 / 255.0, 0.0, 1.0))
    assert params["seed"] == pytest.approx(125.0)


def test_resolution_outputs_are_deep_frozen_for_transition_request_admission():
    resolved = resolve_parameterized_phase_c_inputs(
        "burn",
        {"burn": {"glow_color": [255, 140, 30, 255]}},
        random_source=_Rng(),
    )
    assert isinstance(resolved.parameters, tuple)
    assert isinstance(resolved.parameter_dict()["glow_color"], tuple)


def test_unknown_or_unparameterized_effect_is_not_silently_defaulted():
    with pytest.raises(ValueError, match="no parameterized Phase-C resolver"):
        resolve_parameterized_phase_c_inputs(
            "crossfade",
            {},
            random_source=_Rng(),
        )
