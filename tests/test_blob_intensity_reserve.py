"""Regression tests for staged blob core sizing.

These tests mirror the staging helper used by ``blob.frag`` via
``widgets.spotify_visualizer.blob_math`` to guarantee Stage Gain/Core Scale stay
predictable and monotonic.
"""
from __future__ import annotations

import pytest

from widgets.spotify_visualizer.blob_math import compute_blob_radius_preview


def _radius(**overrides: float) -> float:
    base = dict(
        blob_size=1.0,
        blob_pulse=1.0,
        bass_energy=0.5,
        mid_energy=0.45,
        high_energy=0.35,
        overall_energy=0.5,
        smoothed_energy=0.8,
        stage_gain=1.0,
        core_scale=1.0,
    )
    base.update(overrides)
    return compute_blob_radius_preview(**base)


def _baseline_radius(**overrides: float) -> float:
    params = dict(
        blob_size=1.0,
        blob_pulse=1.0,
        bass_energy=0.5,
        smoothed_energy=0.8,
    )
    params.update(overrides)
    blob_size = max(0.1, min(2.5, params["blob_size"]))
    bass = max(0.0, min(1.0, params["bass_energy"]))
    pulse = max(0.0, params["blob_pulse"])
    se = max(0.0, min(1.0, params["smoothed_energy"]))
    r = 0.44 * blob_size
    r += bass * bass * 0.066
    r += bass * 0.077 * pulse
    r -= (1.0 - se) * 0.053 * pulse
    return r


@pytest.mark.parametrize(
    "energies",
    [
        dict(bass_energy=0.2, mid_energy=0.15, high_energy=0.12, overall_energy=0.18),
        dict(bass_energy=0.45, mid_energy=0.38, high_energy=0.35, overall_energy=0.4),
        dict(bass_energy=0.7, mid_energy=0.6, high_energy=0.55, overall_energy=0.62),
    ],
)
def test_stage_gain_zero_is_exact_noop(energies: dict[str, float]) -> None:
    """stage_gain=0 must match the baseline radius regardless of energy mix."""

    base = _baseline_radius(**energies)
    staged = _radius(stage_gain=0.0, **energies)
    assert staged == pytest.approx(base)


def test_stage_gain_scales_linearly() -> None:
    """Doubling Stage Gain should approximately double the staged offset."""

    params = dict(
        bass_energy=0.7,
        mid_energy=0.55,
        high_energy=0.65,
        overall_energy=0.75,
    )
    baseline = _radius(stage_gain=0.0, **params)
    delta_a = _radius(stage_gain=0.8, **params) - baseline
    delta_b = _radius(stage_gain=1.6, **params) - baseline
    assert delta_a > 0.0
    assert delta_b == pytest.approx(delta_a * 2.0, rel=1e-6)


def test_core_scale_multiplies_all_stages() -> None:
    """Core Scale should uniformly grow/shrink the staged offsets."""

    params = dict(
        bass_energy=0.65,
        mid_energy=0.5,
        high_energy=0.6,
        overall_energy=0.7,
    )
    base = _radius(stage_gain=1.0, core_scale=1.0, **params)
    boosted = _radius(stage_gain=1.0, core_scale=1.5, **params)
    shrunk = _radius(stage_gain=1.0, core_scale=0.5, **params)
    assert boosted > base
    assert shrunk < base


def test_stage_thresholds_increase_monotonically() -> None:
    """Higher weighted energy should climb to larger stages."""

    gain_params = dict(stage_gain=1.0, core_scale=1.0)
    stage0 = _radius(overall_energy=0.04, bass_energy=0.05, mid_energy=0.03, high_energy=0.04, **gain_params)
    stage1 = _radius(overall_energy=0.30, bass_energy=0.22, mid_energy=0.20, high_energy=0.22, **gain_params)
    stage2 = _radius(overall_energy=0.58, bass_energy=0.48, mid_energy=0.40, high_energy=0.45, **gain_params)
    stage3 = _radius(overall_energy=0.82, bass_energy=0.75, mid_energy=0.68, high_energy=0.9, **gain_params)
    assert stage0 < stage1 < stage2 < stage3
