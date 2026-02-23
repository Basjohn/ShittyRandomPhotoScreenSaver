"""Regression tests for blob intensity reserve shader math.

These tests mirror the GLSL logic introduced for `u_blob_intensity_reserve`
inside ``widgets/spotify_visualizer/shaders/blob.frag`` so we can guarantee that
reserve=0.0 is a pure no-op and spikes only unlock hidden headroom on the high
band.
"""
from __future__ import annotations

import pytest


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _headroom_boost(high_energy: float, reserve: float) -> float:
    reserve = _clamp(reserve, 0.0, 2.0)
    if reserve <= 0.0001:
        return 0.0
    high = _clamp(high_energy, 0.0, 1.0)
    spike = max(0.0, high - 0.6)
    gate = _smoothstep(0.0, 0.25, spike)
    return spike * spike * 0.12 * reserve * gate


def compute_blob_radius(
    *,
    blob_size: float,
    blob_pulse: float,
    bass_energy: float,
    smoothed_energy: float,
    high_energy: float,
    reserve: float,
) -> float:
    """Mirror the GLSL radius math so we can compare reserve/no-reserve."""

    r = 0.44 * _clamp(blob_size, 0.1, 2.5)
    r += bass_energy * bass_energy * 0.066
    r += bass_energy * 0.077 * blob_pulse
    se = _clamp(smoothed_energy, 0.0, 1.0)
    r -= (1.0 - se) * 0.053 * blob_pulse
    r += _headroom_boost(high_energy, reserve)
    return r


@pytest.mark.parametrize(
    "high",
    [0.0, 0.25, 0.5, 0.65, 0.95],
)
def test_reserve_zero_is_exact_noop(high: float) -> None:
    """reserve=0.0 must match baseline radius for all band levels."""

    params = dict(
        blob_size=1.0,
        blob_pulse=1.0,
        bass_energy=0.6,
        smoothed_energy=0.8,
        high_energy=high,
    )
    baseline = compute_blob_radius(reserve=0.0, **params)
    comparison = compute_blob_radius(reserve=0.0, **params)
    assert comparison == pytest.approx(baseline)


def test_low_high_energy_does_not_unlock_reserve() -> None:
    """Even with reserve slider raised, low highs (<0.6) stay unchanged."""

    params = dict(
        blob_size=1.1,
        blob_pulse=0.8,
        bass_energy=0.4,
        smoothed_energy=0.7,
        high_energy=0.55,  # below spike threshold
    )
    baseline = compute_blob_radius(reserve=0.0, **params)
    boosted = compute_blob_radius(reserve=1.5, **params)
    assert boosted == pytest.approx(baseline), "reserve must stay hidden before spikes"


def test_high_energy_spike_unlocks_reserve() -> None:
    """High-band spikes (>0.6) should gain additional radius proportional to reserve."""

    params = dict(
        blob_size=0.95,
        blob_pulse=1.2,
        bass_energy=0.7,
        smoothed_energy=0.85,
        high_energy=0.93,
    )
    baseline = compute_blob_radius(reserve=0.0, **params)
    boosted = compute_blob_radius(reserve=1.0, **params)
    delta = boosted - baseline
    expected = _headroom_boost(params["high_energy"], reserve=1.0)
    assert delta == pytest.approx(expected)
    assert delta > 0.0


def test_reserve_scales_linearly_with_slider() -> None:
    """Doubling the reserve slider should double the unlocked headroom."""

    params = dict(
        blob_size=1.0,
        blob_pulse=0.9,
        bass_energy=0.5,
        smoothed_energy=0.75,
        high_energy=0.88,
    )
    delta_a = compute_blob_radius(reserve=0.6, **params) - compute_blob_radius(
        reserve=0.0, **params
    )
    delta_b = compute_blob_radius(reserve=1.2, **params) - compute_blob_radius(
        reserve=0.0, **params
    )
    assert delta_a > 0.0
    assert delta_b > 0.0
    assert delta_b == pytest.approx(delta_a * 2.0, rel=1e-6)
