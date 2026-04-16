"""Regression tests for the unshaped Blob organic base field."""

from __future__ import annotations

import pytest

from widgets.spotify_visualizer.blob_math import (
    compute_unshaped_motion_offsets,
    compute_unshaped_organic_base_multiplier,
    compute_unshaped_radius_multiplier,
)


def test_unshaped_blob_organic_base_wraps_cleanly_at_seam() -> None:
    left = compute_unshaped_organic_base_multiplier(
        angle_frac=0.0,
        time_seconds=12.5,
        smoothed_energy=0.32,
        overall_energy=0.28,
    )
    right = compute_unshaped_organic_base_multiplier(
        angle_frac=1.0,
        time_seconds=12.5,
        smoothed_energy=0.32,
        overall_energy=0.28,
    )
    just_left = compute_unshaped_organic_base_multiplier(
        angle_frac=0.999,
        time_seconds=12.5,
        smoothed_energy=0.32,
        overall_energy=0.28,
    )
    just_right = compute_unshaped_organic_base_multiplier(
        angle_frac=0.001,
        time_seconds=12.5,
        smoothed_energy=0.32,
        overall_energy=0.28,
    )

    assert left == pytest.approx(right, rel=1e-7, abs=1e-7)
    assert abs(just_left - just_right) < 0.0025


def test_unshaped_blob_organic_base_is_meaningfully_non_circular_at_rest() -> None:
    samples = [
        compute_unshaped_organic_base_multiplier(
            angle_frac=idx / 64.0,
            time_seconds=7.0,
            smoothed_energy=0.10,
            overall_energy=0.08,
        )
        for idx in range(64)
    ]

    spread = max(samples) - min(samples)

    assert spread > 0.08
    assert min(samples) >= 0.88
    assert max(samples) <= 1.16


def test_unshaped_blob_organic_base_changes_smoothly_between_neighboring_angles() -> None:
    samples = [
        compute_unshaped_organic_base_multiplier(
            angle_frac=idx / 128.0,
            time_seconds=9.5,
            smoothed_energy=0.34,
            overall_energy=0.26,
        )
        for idx in range(128)
    ]

    max_step = max(
        abs(samples[idx] - samples[(idx + 1) % len(samples)])
        for idx in range(len(samples))
    )

    assert max_step < 0.012


def test_unshaped_blob_organic_base_wrap_stays_smooth_as_time_drifts() -> None:
    for time_seconds in (0.0, 3.5, 17.25, 41.0):
        just_left = compute_unshaped_organic_base_multiplier(
            angle_frac=0.9985,
            time_seconds=time_seconds,
            smoothed_energy=0.22,
            overall_energy=0.19,
        )
        just_right = compute_unshaped_organic_base_multiplier(
            angle_frac=0.0015,
            time_seconds=time_seconds,
            smoothed_energy=0.22,
            overall_energy=0.19,
        )

        assert abs(just_left - just_right) < 0.004


def test_unshaped_blob_full_radius_profile_stays_smooth_under_strong_motion() -> None:
    samples = [
        compute_unshaped_radius_multiplier(
            angle_frac=idx / 128.0,
            time_seconds=11.0,
            bass_energy=0.74,
            mid_energy=0.92,
            high_energy=0.38,
            overall_energy=0.80,
            smoothed_energy=0.76,
            reactive_deformation=1.1,
            constant_wobble=0.85,
            reactive_wobble=1.15,
            stretch_tendency=0.64,
            stretch_inner=0.0,
            stretch_outer=0.58,
            core_floor_bias=0.35,
            stage1_t=0.78,
            stage2_t=0.54,
            stage3_t=0.26,
        )
        for idx in range(128)
    ]

    max_step = max(
        abs(samples[idx] - samples[(idx + 1) % len(samples)])
        for idx in range(len(samples))
    )

    assert max_step < 0.028
    assert min(samples) >= 0.84


def test_unshaped_blob_motion_offsets_bias_toward_outward_fluid_motion() -> None:
    offsets = [
        compute_unshaped_motion_offsets(
            angle_frac=idx / 96.0,
            time_seconds=6.2,
            bass_energy=0.42,
            mid_energy=0.88,
            high_energy=0.30,
            overall_energy=0.63,
            smoothed_energy=0.58,
            reactive_deformation=1.0,
            constant_wobble=0.80,
            reactive_wobble=1.0,
            stretch_tendency=0.60,
            stretch_inner=0.0,
            stretch_outer=0.55,
        )[0]
        for idx in range(96)
    ]

    assert min(offsets) > -0.022
    assert max(offsets) > 0.024


def test_unshaped_blob_pocket_reactions_still_locally_enrich_radius() -> None:
    pocketed = compute_unshaped_radius_multiplier(
        angle_frac=0.25,
        time_seconds=5.0,
        bass_energy=0.64,
        mid_energy=0.52,
        high_energy=0.18,
        overall_energy=0.56,
        smoothed_energy=0.50,
        reactive_deformation=1.0,
        constant_wobble=0.70,
        reactive_wobble=0.95,
        stretch_tendency=0.50,
        stretch_inner=0.0,
        stretch_outer=0.52,
        core_floor_bias=0.35,
        stage1_t=0.52,
        stage2_t=0.24,
        stage3_t=0.0,
        pocket_component=0.70,
    )
    plain = compute_unshaped_radius_multiplier(
        angle_frac=0.25,
        time_seconds=5.0,
        bass_energy=0.64,
        mid_energy=0.52,
        high_energy=0.18,
        overall_energy=0.56,
        smoothed_energy=0.50,
        reactive_deformation=1.0,
        constant_wobble=0.70,
        reactive_wobble=0.95,
        stretch_tendency=0.50,
        stretch_inner=0.0,
        stretch_outer=0.52,
        core_floor_bias=0.35,
        stage1_t=0.52,
        stage2_t=0.24,
        stage3_t=0.0,
        pocket_component=0.0,
    )

    assert pocketed > plain + 0.012
