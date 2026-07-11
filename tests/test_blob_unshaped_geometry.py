"""Regression tests for the Mighty Blob procedural contour."""

from __future__ import annotations

import math

import pytest

from widgets.spotify_visualizer.blob_math import (
    build_unshaped_blob_target_profile,
    compute_unshaped_motion_offsets,
    compute_unshaped_organic_base_multiplier,
    compute_unshaped_radius_multiplier,
    solve_unshaped_blob_profile_step,
)


def _harmonic_amplitude(profile: list[float], harmonic: int) -> float:
    mean = math.fsum(profile) / len(profile)
    cosine = math.fsum(
        (value - mean) * math.cos(math.tau * harmonic * idx / len(profile))
        for idx, value in enumerate(profile)
    ) * 2.0 / len(profile)
    sine = math.fsum(
        (value - mean) * math.sin(math.tau * harmonic * idx / len(profile))
        for idx, value in enumerate(profile)
    ) * 2.0 / len(profile)
    return math.hypot(cosine, sine)


def test_mighty_blob_organic_base_wraps_cleanly_at_seam() -> None:
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


def test_mighty_blob_organic_base_is_meaningfully_non_circular_at_rest() -> None:
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


def test_mighty_blob_organic_base_changes_smoothly_between_neighboring_angles() -> None:
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


def test_mighty_blob_organic_base_wrap_stays_smooth_as_time_drifts() -> None:
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


def test_mighty_blob_solver_smooths_rich_harmonics_under_strong_motion() -> None:
    profile_bundle, _velocity = solve_unshaped_blob_profile_step(
        previous_profile=None,
        previous_velocity=None,
        previous_target_profile=None,
        sample_count=64,
        time_seconds=11.0,
        dt=0.016,
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
        playing=True,
        seed=0.3,
    )
    _base, _raw_target, _target, samples = profile_bundle

    max_step = max(
        abs(samples[idx] - samples[(idx + 1) % len(samples)])
        for idx in range(len(samples))
    )

    assert max_step < 0.032
    assert min(samples) >= 0.84
    assert max(samples) > 1.15


def test_mighty_blob_music_tendrils_are_outward_biased_and_zero_mean() -> None:
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

    assert abs(math.fsum(offsets) / len(offsets)) < 1e-6
    assert max(offsets) > 0.08
    assert max(offsets) > abs(min(offsets)) * 1.5
    peak_index = max(range(len(offsets)), key=offsets.__getitem__)
    peak = offsets[peak_index]
    assert offsets[(peak_index - 1) % len(offsets)] > peak * 0.84
    assert offsets[(peak_index + 1) % len(offsets)] > peak * 0.84
    assert sum(value > peak * 0.70 for value in offsets) >= 5


def test_mighty_blob_mid_vocals_drive_visible_outline_wobble() -> None:
    def _reactive_wobble(mid: float, high: float, overall: float, smoothed: float) -> list[float]:
        return [
            compute_unshaped_motion_offsets(
                angle_frac=idx / 128.0,
                time_seconds=3.7,
                bass_energy=0.12,
                mid_energy=mid,
                high_energy=high,
                overall_energy=overall,
                smoothed_energy=smoothed,
                reactive_deformation=1.0,
                constant_wobble=0.0,
                reactive_wobble=1.0,
                stretch_tendency=0.0,
                stretch_inner=0.0,
                stretch_outer=0.5,
            )[1]
            for idx in range(128)
        ]

    quiet = _reactive_wobble(0.0, 0.0, 0.0, 0.04)
    vocal = _reactive_wobble(0.85, 0.10, 0.55, 0.50)
    quiet_rms = math.sqrt(math.fsum(value * value for value in quiet) / len(quiet))
    vocal_rms = math.sqrt(math.fsum(value * value for value in vocal) / len(vocal))

    assert max(vocal) - min(vocal) > 0.24
    assert vocal_rms > 0.055
    assert vocal_rms > quiet_rms * 20.0


def test_mighty_blob_idle_solver_never_exposes_a_perfect_circle() -> None:
    profile_bundle, _velocity = solve_unshaped_blob_profile_step(
        previous_profile=None,
        previous_velocity=None,
        previous_target_profile=None,
        sample_count=64,
        time_seconds=5.4,
        dt=0.016,
        bass_energy=0.0,
        mid_energy=0.0,
        high_energy=0.0,
        overall_energy=0.0,
        smoothed_energy=0.0,
        reactive_deformation=0.0,
        constant_wobble=0.0,
        reactive_wobble=0.0,
        stretch_tendency=0.0,
        stretch_inner=0.0,
        stretch_outer=0.0,
        core_floor_bias=0.0,
        stage1_t=0.0,
        stage2_t=0.0,
        stage3_t=0.0,
        playing=False,
        seed=0.2,
    )
    base, _raw, _target, solved = profile_bundle

    assert max(base) - min(base) > 0.08
    assert max(solved) - min(solved) > 0.08
    assert min(solved) >= 0.84
    assert abs(math.fsum(solved) / len(solved) - 1.0) < 0.01


def test_mighty_blob_pocket_reactions_still_locally_enrich_radius() -> None:
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


def test_mighty_blob_restores_rich_constant_and_reactive_harmonics() -> None:
    common = dict(
        sample_count=64,
        time_seconds=7.2,
        reactive_deformation=1.0,
        constant_wobble=1.0,
        reactive_wobble=1.0,
        stretch_tendency=0.70,
        stretch_inner=0.0,
        stretch_outer=0.70,
        core_floor_bias=0.35,
        stage1_t=0.80,
        stage2_t=0.60,
        stage3_t=0.30,
        playing=True,
        seed=0.3,
    )
    _calm_base, _calm_raw, calm = build_unshaped_blob_target_profile(
        bass_energy=0.0,
        mid_energy=0.0,
        high_energy=0.0,
        overall_energy=0.0,
        smoothed_energy=0.08,
        **common,
    )
    _hot_base, _hot_raw, hot = build_unshaped_blob_target_profile(
        bass_energy=0.75,
        mid_energy=0.95,
        high_energy=0.80,
        overall_energy=0.86,
        smoothed_energy=0.82,
        **common,
    )

    constant_detail = _harmonic_amplitude(calm, 5) + _harmonic_amplitude(calm, 7)
    reactive_detail = sum(_harmonic_amplitude(hot, harmonic) for harmonic in (4, 5, 7, 9, 11))

    assert constant_detail > 0.025
    assert reactive_detail > 0.10


def test_mighty_blob_keeps_body_mean_stable_while_tendrils_extend_outward() -> None:
    common = dict(
        sample_count=64,
        time_seconds=4.0,
        reactive_deformation=1.0,
        constant_wobble=0.85,
        reactive_wobble=1.10,
        stretch_tendency=0.72,
        stretch_inner=0.0,
        stretch_outer=0.72,
        core_floor_bias=0.35,
        stage1_t=0.76,
        stage2_t=0.52,
        stage3_t=0.24,
        playing=True,
        seed=0.41,
    )
    base, _raw, hot = build_unshaped_blob_target_profile(
        bass_energy=0.82,
        mid_energy=0.94,
        high_energy=0.72,
        overall_energy=0.84,
        smoothed_energy=0.80,
        **common,
    )
    calm_offsets = [
        sum(compute_unshaped_motion_offsets(
            angle_frac=idx / 128.0,
            time_seconds=4.0,
            bass_energy=0.0,
            mid_energy=0.0,
            high_energy=0.0,
            overall_energy=0.0,
            smoothed_energy=0.08,
            reactive_deformation=1.0,
            constant_wobble=0.85,
            reactive_wobble=1.10,
            stretch_tendency=0.72,
            stretch_inner=0.0,
            stretch_outer=0.72,
        ))
        for idx in range(128)
    ]
    hot_offsets = [
        sum(compute_unshaped_motion_offsets(
            angle_frac=idx / 128.0,
            time_seconds=4.0,
            bass_energy=0.82,
            mid_energy=0.94,
            high_energy=0.72,
            overall_energy=0.84,
            smoothed_energy=0.80,
            reactive_deformation=1.0,
            constant_wobble=0.85,
            reactive_wobble=1.10,
            stretch_tendency=0.72,
            stretch_inner=0.0,
            stretch_outer=0.72,
        ))
        for idx in range(128)
    ]

    assert math.fsum(hot) / len(hot) == pytest.approx(math.fsum(base) / len(base), abs=0.006)
    assert min(hot) >= 0.84
    assert max(hot_offsets) > max(calm_offsets) + 0.12
