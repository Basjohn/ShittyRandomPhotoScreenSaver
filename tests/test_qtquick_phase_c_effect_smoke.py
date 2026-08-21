"""Static gates for the focused Phase-C real-GL effect smoke wrapper."""

from __future__ import annotations

import pytest

from tools import qtquick_phase_c_effect_smoke as phase_c_smoke
from tools import qtquick_render_node_smoke as smoke


# Deterministic synthetic ARGB samples used to prove the strengthened midpoint
# oracles are effect-discriminative. These never touch OpenGL; the real-GL
# harness still owns actual rendering (see C-T9). Their only job is to prove the
# discriminator logic rejects generic wipe/crossfade fallbacks and accepts the
# effect-specific spatial signature.
_SRC = "#ff0c2078"   # blue-dominant  -> "source"
_DST = "#ff78180c"   # red-dominant   -> "destination"
_DARK = "#ff101010"  # near-black     -> "dark-effect"
_MIX = "#ff643c64"   # red==blue, not dark -> "mixed-effect"
_COORDS = smoke._TRANSITION_SAMPLE_COORDINATES
_N = len(_COORDS)


def _pure_source() -> list[str]:
    return [_SRC] * _N


def _pure_destination() -> list[str]:
    return [_DST] * _N


def _wipe_midpoint(axis_name: str, progress: float = 0.5) -> list[str]:
    axis_for = smoke._WIPE_AXES[axis_name]
    return [_DST if axis_for(x, y) < progress else _SRC for (x, y) in _COORDS]


def _crossfade_midpoint() -> list[str]:
    return [_MIX] * _N


def _scattered_blocks() -> list[str]:
    # Interleaved per-block ownership that no single wipe axis can separate.
    return [_SRC if (i % 5 + i // 5) % 2 == 0 else _DST for i in range(_N)]


def _radial_ripple() -> list[str]:
    # Centre and its immediate neighbours in the arriving domain, outer ring in
    # the old domain: radial arrival, not a monotonic linear reveal.
    samples = _pure_source()
    for idx in (12, 7, 11, 13, 17):
        samples[idx] = _DST
    return samples


def _effect_scatter_with_dark() -> list[str]:
    # Scattered ownership plus effect-colored pixels (cracks/char/shading).
    samples = _scattered_blocks()
    samples[6] = _DARK
    samples[18] = _DARK
    samples[8] = _MIX
    return samples


def _oracle(effect: str):
    return phase_c_smoke._ORACLES[effect]


def _run(effect: str, midpoint, case: str) -> bool:
    return _oracle(effect)(
        _pure_source(), _pure_destination(), midpoint, 0.5, case
    )


def test_phase_c_smoke_exposes_all_remaining_parameterized_effects():
    assert tuple(phase_c_smoke._CASES) == (
        "diffuse",
        "ripple",
        "crumble",
        "particle",
        "burn",
    )
    assert len(phase_c_smoke._CASES["diffuse"]) == 6
    assert len(phase_c_smoke._PARTICLE_DIRECTIONS) == 10
    assert len(phase_c_smoke._CASES["particle"]) == 12
    assert len(phase_c_smoke._BURN_DIRECTIONS) == 6
    assert len(phase_c_smoke._CASES["burn"]) == 9
    assert phase_c_smoke._CASES["particle"][-2:] == ("swirl", "converge")


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

    particle = phase_c_smoke._parameters("particle", "diag-br-tl")
    assert particle["mode"] == 0
    assert particle["direction"] == 7
    assert particle["use_3d_shading"] is True
    assert particle["texture_mapping"] is True
    assert particle["wobble"] is True
    assert phase_c_smoke._parameters("particle", "random-direction")["direction"] == 8
    assert phase_c_smoke._parameters("particle", "random-placement")["direction"] == 9
    assert phase_c_smoke._parameters("particle", "swirl")["mode"] == 1
    assert phase_c_smoke._parameters("particle", "converge")["mode"] == 2

    burn = phase_c_smoke._parameters("burn", "diag-tr-bl")
    assert burn["direction"] == 5
    assert burn["smoke_enabled"] is True
    assert burn["ash_enabled"] is True
    assert burn["glow_color"] == pytest.approx((1.0, 140.0 / 255.0, 30.0 / 255.0, 1.0))
    assert phase_c_smoke._parameters("burn", "no-smoke")["smoke_enabled"] is False
    assert phase_c_smoke._parameters("burn", "no-smoke")["ash_enabled"] is True
    assert phase_c_smoke._parameters("burn", "no-ash")["smoke_enabled"] is True
    assert phase_c_smoke._parameters("burn", "no-ash")["ash_enabled"] is False
    neither = phase_c_smoke._parameters("burn", "no-smoke-or-ash")
    assert neither["smoke_enabled"] is False
    assert neither["ash_enabled"] is False


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


# --- C-T1: midpoint oracles must be effect-discriminative ------------------

_ALL_WIPE_AXES = tuple(smoke._WIPE_AXES)


@pytest.mark.parametrize(
    ("effect", "case"),
    (
        ("diffuse", "rectangle"),
        ("ripple", "count3"),
        ("crumble", "top"),
        ("particle", "converge"),
        ("burn", "left-to-right"),
    ),
)
@pytest.mark.parametrize("axis_name", _ALL_WIPE_AXES)
def test_effect_oracles_reject_a_plain_wipe_fallback(effect, case, axis_name):
    # A plain monotonic wipe (only pure source/destination, separable by one
    # axis) must not satisfy any strengthened effect oracle.
    assert _run(effect, _wipe_midpoint(axis_name), case) is False


@pytest.mark.parametrize(
    ("effect", "case"),
    (
        ("diffuse", "rectangle"),
        ("ripple", "count3"),
        ("crumble", "top"),
        ("particle", "converge"),
        ("burn", "left-to-right"),
    ),
)
def test_effect_oracles_reject_a_uniform_crossfade_fallback(effect, case):
    assert _run(effect, _crossfade_midpoint(), case) is False


def test_diffuse_oracle_accepts_scattered_block_ownership():
    # A scattered, non-separable block dissolve is the Diffuse signature.
    assert _run("diffuse", _scattered_blocks(), "rectangle") is True


def test_ripple_oracle_accepts_radial_centre_arrival_only():
    ripple = _radial_ripple()
    assert _run("ripple", ripple, "count3") is True
    # A radial pattern whose centre is still the old image is not a valid
    # ripple midpoint (the first authored ripple is centred).
    old_centre = _pure_source()
    old_centre[7] = _DST
    old_centre[11] = _DST
    old_centre[13] = _DST
    old_centre[17] = _DST
    assert _run("ripple", old_centre, "count3") is False


@pytest.mark.parametrize("effect", ("crumble", "particle", "burn"))
def test_effect_oracles_accept_effect_colored_scatter(effect):
    # Cracks / shaded particles / char produce effect-colored pixels that a
    # plain two-domain wipe never shows.
    assert _run(effect, _effect_scatter_with_dark(), "top") is True


@pytest.mark.parametrize("effect", ("crumble", "particle", "burn"))
def test_effect_oracles_reject_two_domain_scatter_without_effect_pixels(effect):
    # Even a scattered (non-wipe) two-domain reveal must be rejected by
    # Crumble/Particle/Burn because they require effect-colored pixels.
    assert _run(effect, _scattered_blocks(), "top") is False


# --- C-T2: selected smoke parameters must materially change the request ----

def test_ripple_count_cases_resolve_to_materially_different_counts():
    counts = {
        case: phase_c_smoke._parameters("ripple", case)["ripple_count"]
        for case in ("count1", "count3", "count8")
    }
    assert counts == {"count1": 1, "count3": 3, "count8": 8}
    assert len(set(counts.values())) == 3
    # The deterministic seed is held fixed so ripple_count is the only variable.
    seeds = {
        phase_c_smoke._parameters("ripple", case)["ripple_seed"]
        for case in ("count1", "count3", "count8")
    }
    assert seeds == {123.5}


def test_crumble_weighting_modes_resolve_to_distinct_weight_modes():
    modes = {
        case: phase_c_smoke._parameters("crumble", case)["weight_mode"]
        for case in ("top", "bottom", "random-weighted", "random-choice", "age-weighted")
    }
    assert modes == {
        "top": 0.0,
        "bottom": 1.0,
        "random-weighted": 2.0,
        "random-choice": 3.0,
        "age-weighted": 4.0,
    }
    assert len(set(modes.values())) == 5


def test_particle_direction_and_mode_cases_resolve_distinctly():
    directions = {
        case: phase_c_smoke._parameters("particle", case)["direction"]
        for case in phase_c_smoke._PARTICLE_DIRECTIONS
    }
    # Every authored direction case resolves to its own shader direction index.
    assert set(directions.values()) == set(range(10))
    # Mode cases select distinct authored modes with a stable direction.
    swirl = phase_c_smoke._parameters("particle", "swirl")
    converge = phase_c_smoke._parameters("particle", "converge")
    assert swirl["mode"] == 1
    assert converge["mode"] == 2
    assert swirl["mode"] != converge["mode"]


def test_burn_toggle_cases_resolve_to_distinct_smoke_ash_combinations():
    combos = {
        case: (
            phase_c_smoke._parameters("burn", case)["smoke_enabled"],
            phase_c_smoke._parameters("burn", case)["ash_enabled"],
        )
        for case in ("left-to-right", "no-smoke", "no-ash", "no-smoke-or-ash")
    }
    assert combos["left-to-right"] == (True, True)
    assert combos["no-smoke"] == (False, True)
    assert combos["no-ash"] == (True, False)
    assert combos["no-smoke-or-ash"] == (False, False)
    assert len(set(combos.values())) == 4
