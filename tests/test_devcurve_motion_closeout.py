"""Focused DevCurve travel-continuity and Quick stroke closeout regressions."""
from __future__ import annotations

import math

import pytest

from widgets.spotify_visualizer.devcurve_runtime import (
    DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE,
    DEVCURVE_MATERIAL_TRAVEL_VARIATION,
    DEVCURVE_PASSAGE_USUAL,
    DevCurveRuntimeState,
    solve_devcurve_frame,
)
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands


_LAYERS = ("bass", "vocals", "mids", "transients")


def _settings():
    return {
        name: {"enabled": True, "power": 1.0, "offset": 0.0, "order": i + 1}
        for i, name in enumerate(_LAYERS)
    }


def _shapes():
    nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
    return {name: [list(node) for node in nodes] for name in _LAYERS}


def _solve(state: DevCurveRuntimeState, *, now: float, energy: float, passage: float = DEVCURVE_PASSAGE_USUAL):
    return solve_devcurve_frame(
        state,
        dt=0.016,
        now_ts=now,
        playing=True,
        energy_bands=EnergyBands(
            bass=energy,
            mid=energy,
            high=energy,
            overall=energy,
        ),
        transient_bus=TransientEnergyBands(
            bass_transient=energy,
            mid_transient=energy,
            high_transient=energy,
        ),
        layer_shape_nodes=_shapes(),
        base_level=0.58,
        motion_power=1.65,
        idle_motion=0.2,
        # Shipped presets historically use 0.1 here. Material travel must no
        # longer collapse to ~0.014 units/s merely because contour idle speed
        # is low.
        idle_speed=0.1,
        smoothness=0.55,
        layer_settings=_settings(),
        passage_intensity=passage,
    )


def test_devcurve_material_travel_is_gently_bounded_not_energy_throttled():
    state = DevCurveRuntimeState()
    low = _solve(state, now=1000.0, energy=0.0)
    rates = [float(low["foreground_travel_rate"])]

    # Hammer the energy target between its extremes. The material cruise may
    # breathe, but it must never return to the old ~12x 0.014->0.170 throttle.
    for i in range(1, 90):
        frame = _solve(state, now=1000.0 + i * 0.016, energy=2.0 if i % 2 else 0.0)
        rates.append(float(frame["foreground_travel_rate"]))
        assert frame["foreground_travel_rate"] == pytest.approx(
            frame["specular_travel_rate"]
        )

    cruise = DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE
    variation = DEVCURVE_MATERIAL_TRAVEL_VARIATION
    assert min(rates) >= cruise * (1.0 - variation) - 1e-12
    assert max(rates) <= cruise * (1.0 + variation) + 1e-12
    assert max(abs(b - a) for a, b in zip(rates, rates[1:])) < cruise * 0.02


def test_devcurve_material_position_integrates_smoothed_rate_without_rephasing():
    state = DevCurveRuntimeState()
    first = _solve(state, now=12345.0, energy=0.0)
    second = _solve(state, now=12345.016, energy=2.0)

    p0 = float(first["foreground_travel_pos"])
    p1 = float(second["foreground_travel_pos"])
    expected = (p0 + 0.016 * float(second["foreground_travel_rate"])) % 1.0
    assert p1 == pytest.approx(expected, abs=1e-12)
    # Absolute wall-clock magnitude must not enter the phase calculation.
    assert 0.0 <= p0 < 1.0
    assert 0.0 <= p1 < 1.0


def _settle(passage: float, seconds: float = 12.0):
    state = DevCurveRuntimeState()
    frame = None
    for i in range(int(seconds / 0.016)):
        frame = _solve(state, now=500.0 + i * 0.016, energy=0.6, passage=passage)
    return state, frame


def test_devcurve_travel_speed_and_swing_follow_the_passage():
    """Operator 2026-10-04: DevCurve must not keep one speed and slope whatever the music does.
    A loud passage travels faster and swings steeper than a quiet one at the same per-frame energy."""
    _, quiet = _settle(0.0)
    _, usual = _settle(DEVCURVE_PASSAGE_USUAL)
    _, loud = _settle(1.0)
    assert quiet["foreground_travel_rate"] < usual["foreground_travel_rate"] < loud["foreground_travel_rate"]
    assert loud["foreground_travel_rate"] >= 2.0 * quiet["foreground_travel_rate"]
    assert loud["active_amplitude"] >= 2.0 * quiet["active_amplitude"]

    def phase_speed(passage):
        state, _ = _settle(passage)
        before = state.reactive_phase
        _solve(state, now=10_000.0, energy=0.6, passage=passage)
        return state.reactive_phase - before

    assert phase_speed(1.0) >= 2.0 * phase_speed(0.0)


def test_devcurve_passage_changes_ease_in_without_jumps():
    """A passage flipping every frame never jitters travel, and a real quiet->loud change eases
    in over seconds: no frame moves the rate or the curves by a visible jump."""
    state, _ = _settle(0.0)
    rates, curves = [], []
    for i in range(400):
        frame = _solve(state, now=900.0 + i * 0.016, energy=0.6, passage=1.0 if i % 2 else 0.0)
        rates.append(float(frame["foreground_travel_rate"]))
    assert max(abs(b - a) for a, b in zip(rates, rates[1:])) < 0.01 * DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE
    state, _ = _settle(0.0)
    for i in range(400):
        frame = _solve(state, now=1900.0 + i * 0.016, energy=0.6, passage=1.0)
        rates.append(float(frame["foreground_travel_rate"]))
        curves.append(frame["layers"]["bass"])
    steps = [abs(b - a) for a, b in zip(rates[400:], rates[401:])]
    assert max(steps) < 0.02 * DEVCURVE_MATERIAL_TRAVEL_CRUISE_RATE
    assert max(max(abs(b - a) for a, b in zip(c0, c1)) for c0, c1 in zip(curves, curves[1:])) < 0.02
