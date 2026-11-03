"""Bubble ambient-layer invariants: separate RNG, hard caps and glow-only reaction.

Native Qt Quick draw/performance acceptance is deliberately separate; these
are deterministic control and authored-geometry contracts.
"""
from __future__ import annotations

import random

import pytest

from widgets.spotify_visualizer.bubble_ambient import (
    BubbleAmbientSimulation,
    MAX_MICROBUBBLES,
    MAX_PARTICLES,
    RECORD_STRIDE,
)
from core.settings.default_contract import require_canonical_default
from core.settings.visualizer_mode_settings import require_mode_settings


def _settings(**updates):
    defaults = require_canonical_default("widgets.spotify_visualizer")
    keys = ("bubble_stream_direction", "bubble_drift_direction", "bubble_drift_amount",
            "bubble_drift_speed", "bubble_drift_frequency")
    settings = {key: defaults[key] for key in keys}
    settings.update({entry.key: defaults[entry.key] for entry in
                     require_mode_settings("bubble").controls if entry.bucket == "particles"})
    settings.update(updates)
    return settings


def _records(payload):
    assert len(payload) % RECORD_STRIDE == 0
    return [payload[i:i+RECORD_STRIDE] for i in range(0,len(payload),RECORD_STRIDE)]


def test_defaults_are_all_inert_and_never_allocate_ambient_points():
    settings = _settings()
    sim = BubbleAmbientSimulation()
    assert not sim.enabled(settings)
    assert sim.advance(.02, settings, resolved_stream_velocity=.2, small_bubble_breathing=1) == ()
    assert not sim._micro and not sim._particles


def test_particle_breathing_response_changes_only_glow_not_size_or_placement():
    settings = _settings(bubble_particle_glow=True, bubble_particle_density=.8,
                         bubble_particle_stream=False, bubble_particle_drift=False,
                         bubble_particle_glow_reactivity=1.5)
    sim = BubbleAmbientSimulation()
    quiet = _records(sim.advance(.02,settings,resolved_stream_velocity=.04,small_bubble_breathing=0))
    loud = _records(sim.advance(.02,settings,resolved_stream_velocity=.04,small_bubble_breathing=1))
    assert len(quiet) == len(loud) > 0
    assert all(q[:4] == p[:4] and q[5] == p[5] == 1.0 for q,p in zip(quiet,loud))
    assert all(q[4] < p[4] for q,p in zip(quiet,loud))


def test_microbubbles_ignore_breathing_signal():
    settings = _settings(bubble_microbubble_stream=True,bubble_microbubble_density=.8,
                         bubble_particle_density=0,bubble_stream_direction="none")
    a,b = BubbleAmbientSimulation(),BubbleAmbientSimulation()
    quiet = a.advance(.02,settings,resolved_stream_velocity=.05,small_bubble_breathing=0)
    loud = b.advance(.02,settings,resolved_stream_velocity=.05,small_bubble_breathing=1)
    assert quiet == loud
    assert all(point[4] == point[5] == 0. for point in _records(quiet))


def test_layers_are_independent_and_bounded():
    settings = _settings(bubble_microbubble_stream=True,bubble_particle_stream=True,
                         bubble_particle_glow=True,bubble_microbubble_density=1,
                         bubble_particle_density=1,bubble_stream_direction="up")
    sim = BubbleAmbientSimulation()
    points = _records(sim.advance(.016,settings,resolved_stream_velocity=.08,small_bubble_breathing=.8))
    assert len(points) == MAX_MICROBUBBLES + MAX_PARTICLES
    assert sum(p[5] == 0. for p in points) == MAX_MICROBUBBLES
    assert sum(p[5] == 1. for p in points) == MAX_PARTICLES
    assert all(0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p in points)
    settings["bubble_microbubble_stream"] = False
    settings["bubble_particle_stream"] = False
    settings["bubble_particle_glow"] = False
    assert sim.advance(.016,settings,resolved_stream_velocity=.08,small_bubble_breathing=1) == ()


def test_never_consumes_global_bubble_random_sequence():
    state = random.getstate()
    try:
        random.seed(717)
        expected = random.random()
        random.seed(717)
        settings = _settings(bubble_microbubble_drift=True,bubble_particle_drift=True,
                             bubble_microbubble_density=1,bubble_particle_density=1,
                             bubble_drift_direction="swirl_cw")
        BubbleAmbientSimulation().advance(.02,settings,resolved_stream_velocity=.2,small_bubble_breathing=.5)
        assert random.random() == expected
    finally:
        random.setstate(state)


def test_each_layer_has_independent_seed_and_inherits_speed_without_size_reactivity():
    settings = _settings(bubble_particle_stream=True,bubble_particle_density=.5,
                         bubble_particle_glow=True,bubble_stream_direction="right")
    slow,fast = BubbleAmbientSimulation(),BubbleAmbientSimulation()
    initial = slow.advance(.02,settings,resolved_stream_velocity=0,small_bubble_breathing=.7)
    moving = fast.advance(.02,settings,resolved_stream_velocity=.4,small_bubble_breathing=.7)
    assert [p[2:] for p in _records(initial)] == [p[2:] for p in _records(moving)]
    assert any(a[0] != b[0] for a,b in zip(_records(initial),_records(moving)))
