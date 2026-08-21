"""Static gates for the focused Phase-C real-GL effect smoke wrapper."""

from __future__ import annotations

import pytest

from tools import qtquick_phase_c_effect_smoke as phase_c_smoke


def test_phase_c_smoke_exposes_all_remaining_parameterized_effects():
    assert tuple(phase_c_smoke._CASES) == (
        "diffuse",
        "ripple",
        "crumble",
        "particle",
        "burn",
    )
    assert len(phase_c_smoke._CASES["diffuse"]) == 6
    assert len(phase_c_smoke._CASES["burn"]) == 6
    assert phase_c_smoke._CASES["particle"] == (
        "directional",
        "swirl",
        "converge",
    )


def test_phase_c_smoke_parameters_are_fully_resolved_and_deterministic():
    assert phase_c_smoke._parameters("diffuse", "membrane") == {
        "block_size": 48,
        "shape_mode": 1,
    }
    assert phase_c_smoke._parameters("ripple", "count8") == {
        "ripple_count": 8,
        "ripple_seed": 123.5,
    }
    assert phase_c_smoke._parameters("crumble", "age-weighted")["weight_mode"] == 4.0
    particle = phase_c_smoke._parameters("particle", "converge")
    assert particle["mode"] == 2
    assert particle["use_3d_shading"] is True
    assert particle["texture_mapping"] is True
    assert particle["wobble"] is True
    burn = phase_c_smoke._parameters("burn", "diag-tr-bl")
    assert burn["direction"] == 5
    assert burn["smoke_enabled"] is True
    assert burn["ash_enabled"] is True
    assert burn["glow_color"] == pytest.approx((1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0))


def test_phase_c_smoke_domain_classifier_distinguishes_fixture_ownership():
    assert phase_c_smoke._domain("#ff0c2078") == "source"
    assert phase_c_smoke._domain("#ff78180c") == "destination"
    assert phase_c_smoke._domain("#ff101010") == "dark-effect"


def test_phase_c_smoke_install_is_scoped_to_requested_effect_and_case():
    phase_c_smoke._install_contract("burn", "diag-tl-br")
    assert "burn" in phase_c_smoke.smoke._TRANSITION_IDS
    assert phase_c_smoke.smoke._TRANSITION_SMOKE_PARAMETERS["burn"]["direction"] == 4
    assert phase_c_smoke.smoke._TRANSITION_SMOKE_DURATIONS_MS["burn"] == 900
    assert phase_c_smoke.smoke._TRANSITION_MIDPOINT_ORACLES["burn"] is phase_c_smoke._matches_burn


def test_phase_c_smoke_rejects_unknown_effect_parameters():
    with pytest.raises(ValueError, match="unknown Phase-C smoke effect"):
        phase_c_smoke._parameters("unknown", "default")
