"""Drift musical authority without changing Group Drift's established carrier."""
from __future__ import annotations

import random

import pytest

from core.settings.default_contract import require_canonical_default
from widgets.spotify_visualizer import bubble_simulation as sim_module


def test_normal_drift_music_gain_has_a_quiet_floor_and_meaningful_midrange():
    gain = sim_module._normal_drift_music_gain
    assert gain(0, 0) == 1.0
    assert gain(0, .04) == 1.0
    assert gain(0, .267) > 6.0
    assert gain(.5, .487) > 10.0
    assert gain(10, 10) == pytest.approx(15.0)


def _run(grouped: bool, energy: float):
    # A fixed synthetic passage is sufficient for this control-route gate.
    # Native musical/pixel performance acceptance remains separate.
    random.seed(1138)
    sim = sim_module.BubbleSimulation()
    settings = dict(require_canonical_default('widgets.spotify_visualizer'))
    settings.update(bubble_group_drift=grouped, bubble_drift_amount=.55,
                    bubble_drift_speed=.55, bubble_drift_frequency=.45,
                    bubble_drift_direction='swish_horizontal',
                    bubble_big_count=8, bubble_small_count=40)
    frame = dict(bass=energy,mid=energy*.7,high=energy*.5,overall=energy,
                 pulse_bass=energy,pulse_mid=energy*.7,
                 pulse_high=energy*.5,pulse_overall=energy)
    for _ in range(90):
        sim.tick(1/60, frame, settings)
    return tuple((b.x, b.y) for b in sim._bubbles)


def test_multiplier_is_not_used_for_group_drift(monkeypatch):
    before = _run(True, .9)
    monkeypatch.setattr(sim_module, '_normal_drift_music_gain',
                        lambda _drift, _speed: 1000.)
    assert _run(True, .9) == before


def test_multiplier_does_affect_regular_drift(monkeypatch):
    before = _run(False, .9)
    monkeypatch.setattr(sim_module, '_normal_drift_music_gain',
                        lambda _drift, _speed: 1.)
    assert _run(False, .9) != before
