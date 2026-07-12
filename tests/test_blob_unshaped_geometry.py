"""Regression tests for the Mighty Blob procedural contour."""

from __future__ import annotations

import math

import pytest

from widgets.spotify_visualizer.blob_math import (
    build_unshaped_blob_target_profile,
    compute_unshaped_motion_offsets,
    compute_unshaped_organic_base_multiplier,
    compute_unshaped_radius_multiplier,
    compute_stage_floor_fraction,
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


def test_mighty_blob_solver_keeps_strong_motion_rounded_without_radial_cuts() -> None:
    profile_bundle, _velocity = solve_unshaped_blob_profile_step(
        previous_profile=None,
        previous_velocity=None,
        previous_target_profile=None,
        sample_count=128,
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
    max_curvature = max(
        abs(samples[(idx - 1) % len(samples)] - 2.0 * samples[idx] + samples[(idx + 1) % len(samples)])
        for idx in range(len(samples))
    )

    assert max_step < 0.040
    assert max_curvature < 0.015
    assert min(samples) >= 0.84
    assert max(samples) - min(samples) > 0.24


def test_mighty_blob_music_tendrils_have_broad_zero_slope_shoulders() -> None:
    offsets = [
        compute_unshaped_motion_offsets(
            angle_frac=idx / 128.0,
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
        for idx in range(128)
    ]

    # The local tendril lane is intentionally outward-only; the complete
    # profile is re-centred later so this does not inflate the whole body.
    assert min(offsets) >= 0.0
    assert max(offsets) > 0.04
    peak_index = max(range(len(offsets)), key=offsets.__getitem__)
    peak = offsets[peak_index]
    assert offsets[(peak_index - 1) % len(offsets)] > peak * 0.84
    assert offsets[(peak_index + 1) % len(offsets)] > peak * 0.84
    assert sum(value > peak * 0.70 for value in offsets) >= 8
    assert max(
        abs(offsets[idx] - offsets[(idx + 1) % len(offsets)])
        for idx in range(len(offsets))
    ) < 0.015
    assert max(
        abs(offsets[(idx - 1) % len(offsets)] - 2.0 * offsets[idx] + offsets[(idx + 1) % len(offsets)])
        for idx in range(len(offsets))
    ) < 0.008


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


def test_mighty_core_floor_bias_materially_preserves_the_organic_base() -> None:
    common = dict(
        time_seconds=5.2,
        bass_energy=0.82,
        mid_energy=0.94,
        high_energy=0.72,
        overall_energy=0.84,
        smoothed_energy=0.80,
        reactive_deformation=1.20,
        constant_wobble=0.80,
        reactive_wobble=2.00,
        stretch_tendency=0.75,
        stretch_inner=0.0,
        stretch_outer=0.75,
        stage1_t=0.80,
        stage2_t=0.50,
        stage3_t=0.20,
    )
    open_floor = [
        compute_unshaped_radius_multiplier(
            angle_frac=idx / 128.0,
            core_floor_bias=0.0,
            **common,
        )
        for idx in range(128)
    ]
    protected_floor = [
        compute_unshaped_radius_multiplier(
            angle_frac=idx / 128.0,
            core_floor_bias=0.42,
            **common,
        )
        for idx in range(128)
    ]

    assert compute_stage_floor_fraction(
        core_floor_bias=0.42,
        stage1_t=0.80,
        stage2_t=0.50,
        stage3_t=0.20,
    ) > compute_stage_floor_fraction(
        core_floor_bias=0.0,
        stage1_t=0.80,
        stage2_t=0.50,
        stage3_t=0.20,
    ) + 0.08
    assert min(protected_floor) > min(open_floor) + 0.025
    assert max(
        protected - open_value
        for protected, open_value in zip(protected_floor, open_floor)
    ) > 0.06
    # The control braces inward valleys; it does not resize outward tendrils
    # or replace the living contour with a circular support radius.
    assert max(protected_floor) == pytest.approx(max(open_floor), abs=0.002)
    assert max(protected_floor) - min(protected_floor) > 0.30


def test_mighty_blob_prefers_broad_body_motion_with_bounded_reactive_detail() -> None:
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

    broad_idle = sum(_harmonic_amplitude(calm, harmonic) for harmonic in (1, 2, 3))
    reactive_detail = sum(_harmonic_amplitude(hot, harmonic) for harmonic in (4, 5, 7))
    phrase_delta_rms = math.sqrt(
        math.fsum((hot[idx] - calm[idx]) ** 2 for idx in range(len(hot))) / len(hot)
    )

    assert broad_idle > 0.13
    assert reactive_detail > 0.035
    assert reactive_detail < broad_idle
    assert phrase_delta_rms > 0.055


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


def test_mighty_blob_sustained_phrase_breathes_in_place_instead_of_orbiting() -> None:
    common = dict(
        sample_count=128,
        bass_energy=1.30,
        mid_energy=1.05,
        high_energy=1.10,
        overall_energy=1.25,
        smoothed_energy=1.20,
        reactive_deformation=0.92,
        constant_wobble=0.62,
        reactive_wobble=2.15,
        stretch_tendency=0.74,
        stretch_inner=0.0,
        stretch_outer=0.74,
        core_floor_bias=0.42,
        stage1_t=0.80,
        stage2_t=0.55,
        stage3_t=0.30,
        playing=True,
        seed=0.3,
    )
    profile: list[float] | None = None
    velocity: list[float] | None = None
    target: list[float] | None = None
    captured: dict[float, list[float]] = {}
    capture_times = (2.0, 2.4, 3.2, 3.6)
    for step in range(33):
        time_value = 2.0 + step * 0.05
        bundle, velocity = solve_unshaped_blob_profile_step(
            previous_profile=profile,
            previous_velocity=velocity,
            previous_target_profile=target,
            time_seconds=time_value,
            dt=0.05,
            **common,
        )
        _base, _raw, target, profile = bundle
        for capture_time in capture_times:
            if abs(time_value - capture_time) < 1e-9:
                captured[capture_time] = list(profile)
    profiles = [captured[time_value] for time_value in capture_times]

    def _mse(left: list[float], right: list[float], shift: int = 0) -> float:
        return math.fsum(
            (left[idx] - right[(idx + shift) % len(right)]) ** 2
            for idx in range(len(left))
        ) / len(left)

    for previous, current in zip(profiles, profiles[1:]):
        zero_shift_error = _mse(previous, current)
        best_orbit_error = min(
            _mse(previous, current, shift)
            for shift in range(-8, 9)
            if shift != 0
        )
        # A tiny centre sway is allowed, but a circular shift must not explain
        # the motion materially better than the same anchored contour.
        assert best_orbit_error >= zero_shift_error * 0.75

    spreads = [max(profile) - min(profile) for profile in profiles]
    fixed_angle_motion = max(
        max(profile[idx] for profile in profiles) - min(profile[idx] for profile in profiles)
        for idx in range(len(profiles[0]))
    )
    assert max(spreads) - min(spreads) > 0.03
    assert fixed_angle_motion > 0.08


def test_mighty_blob_hot_live_range_remains_dynamic_above_one() -> None:
    common = dict(
        sample_count=64,
        time_seconds=3.2,
        reactive_deformation=0.92,
        constant_wobble=0.62,
        reactive_wobble=2.15,
        stretch_tendency=0.74,
        stretch_inner=0.0,
        stretch_outer=0.74,
        core_floor_bias=0.42,
        stage1_t=0.80,
        stage2_t=0.55,
        stage3_t=0.30,
        playing=True,
        seed=0.3,
    )
    moderate = build_unshaped_blob_target_profile(
        bass_energy=0.80,
        mid_energy=0.68,
        high_energy=0.56,
        overall_energy=0.72,
        smoothed_energy=0.70,
        **common,
    )[2]
    hot = build_unshaped_blob_target_profile(
        bass_energy=1.40,
        mid_energy=1.19,
        high_energy=0.98,
        overall_energy=1.26,
        smoothed_energy=1.23,
        **common,
    )[2]

    deltas = [abs(left - right) for left, right in zip(moderate, hot)]
    assert max(deltas) > 0.04
    assert math.fsum(deltas) / len(deltas) > 0.015


def test_mighty_near_max_controls_retain_target_motion_through_solver() -> None:
    """Guard the live failure where a strong target became a muted runtime curve."""

    common = dict(
        sample_count=128,
        time_seconds=6.2,
        reactive_deformation=1.52,
        constant_wobble=0.82,
        reactive_wobble=2.82,
        stretch_tendency=0.94,
        stretch_inner=0.0,
        stretch_outer=0.94,
        core_floor_bias=0.42,
        stage1_t=1.0,
        stage2_t=1.0,
        stage3_t=1.0,
        playing=True,
        seed=0.37,
    )
    quiet_energy = dict(
        bass_energy=0.70,
        mid_energy=0.52,
        high_energy=0.65,
        overall_energy=0.73,
        smoothed_energy=0.86,
    )
    hot_energy = dict(
        bass_energy=1.40,
        mid_energy=1.10,
        high_energy=1.20,
        overall_energy=1.25,
        smoothed_energy=1.30,
    )

    def _settled(
        energy: dict[str, float],
    ) -> tuple[list[float], list[float], list[float]]:
        profile: list[float] | None = None
        velocity: list[float] | None = None
        target: list[float] | None = None
        for _ in range(240):
            bundle, velocity = solve_unshaped_blob_profile_step(
                previous_profile=profile,
                previous_velocity=velocity,
                previous_target_profile=target,
                dt=1.0 / 60.0,
                **common,
                **energy,
            )
            _base, _raw, target, profile = bundle
        assert target is not None
        assert profile is not None
        assert velocity is not None
        return target, profile, velocity

    quiet_target, quiet_runtime, quiet_velocity = _settled(quiet_energy)
    hot_target, hot_runtime, _hot_velocity = _settled(hot_energy)

    def _rms_delta(left: list[float], right: list[float]) -> float:
        return math.sqrt(
            math.fsum((a - b) ** 2 for a, b in zip(left, right)) / len(left)
        )

    target_audio_delta = _rms_delta(quiet_target, hot_target)
    runtime_audio_delta = _rms_delta(quiet_runtime, hot_runtime)
    hot_target_error = _rms_delta(hot_target, hot_runtime)
    max_runtime_audio_delta = max(
        abs(quiet - hot) for quiet, hot in zip(quiet_runtime, hot_runtime)
    )

    # Target containment plus per-sample solver bounds are the only fit.  A
    # second tanh fit or angle-varying hard floor loses 20-60% here and makes
    # the stress vector look like scalar size motion instead of contour work.
    assert target_audio_delta > 0.08
    assert runtime_audio_delta > target_audio_delta * 0.95
    assert hot_target_error < 0.002
    assert max_runtime_audio_delta > 0.18
    assert max(hot_runtime) - min(hot_runtime) > 0.50
    assert min(hot_runtime) >= 0.84
    assert max(hot_runtime) <= 1.58

    no_stretch = build_unshaped_blob_target_profile(
        **{**common, "stretch_tendency": 0.0, "stretch_outer": 0.0},
        **hot_energy,
    )[2]
    assert max(
        stretched - plain for stretched, plain in zip(hot_target, no_stretch)
    ) > 0.15

    profile = list(quiet_runtime)
    velocity = list(quiet_velocity)
    previous_target = list(quiet_target)
    attack_progress: list[float] = []
    for _ in range(30):
        bundle, velocity = solve_unshaped_blob_profile_step(
            previous_profile=profile,
            previous_velocity=velocity,
            previous_target_profile=previous_target,
            dt=1.0 / 60.0,
            **common,
            **hot_energy,
        )
        _base, _raw, previous_target, profile = bundle
        attack_progress.append(_rms_delta(quiet_runtime, profile) / runtime_audio_delta)

    # The stress response must be plainly visible within a third of a second,
    # but it must not snap on the first few frames or overshoot without bound.
    assert attack_progress[4] < 0.20
    assert attack_progress[19] > 0.85
    assert max(attack_progress) < 1.25

    release_remaining: list[float] = []
    for _ in range(30):
        bundle, velocity = solve_unshaped_blob_profile_step(
            previous_profile=profile,
            previous_velocity=velocity,
            previous_target_profile=previous_target,
            dt=1.0 / 60.0,
            **common,
            **quiet_energy,
        )
        _base, _raw, previous_target, profile = bundle
        release_remaining.append(_rms_delta(quiet_runtime, profile) / runtime_audio_delta)

    assert release_remaining[0] > 0.80
    assert release_remaining[29] < 0.15
    assert max(release_remaining) < 1.25
