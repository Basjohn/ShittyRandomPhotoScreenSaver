"""Tests for bubble simulation reactivity with simulated audio data.

Covers key scenarios:
  1. Rapid beat clusters (4+ kicks in 2s) — burst detection + promoted bubbles
  2. Sustained loud sections with periodic beats — sustained floor holds
  3. Quiet→loud→quiet transitions — attack/decay behaviour
  4. Single isolated kick — delta component fires correctly
  5. Burst mode small→big promotion — small bubbles react to bass during bursts

All tests use synthetic energy dicts fed into BubbleSimulation.tick().
"""
from __future__ import annotations

import copy
import random

from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_settings(**overrides):
    """Return a minimal settings dict suitable for BubbleSimulation.tick()."""
    base = {
        "bubble_big_count": 6,
        "bubble_small_count": 15,
        "bubble_surface_reach": 0.8,
        "bubble_stream_direction": "up",
        "bubble_stream_constant_speed": 0.5,
        "bubble_stream_speed_cap": 2.0,
        "bubble_stream_reactivity": 0.5,
        "bubble_rotation_amount": 0.3,
        "bubble_drift_amount": 0.3,
        "bubble_drift_speed": 0.3,
        "bubble_drift_frequency": 0.5,
        "bubble_drift_direction": "random",
        "bubble_big_size_max": 0.038,
        "bubble_small_size_max": 0.018,
        "bubble_trail_strength": 0.0,
    }
    base.update(overrides)
    return base


def _energy(bass=0.0, mid=0.0, high=0.0, overall=None):
    """Build a synthetic energy_bands dict."""
    if overall is None:
        overall = bass * 0.5 + mid * 0.3 + high * 0.2
    return {"bass": bass, "mid": mid, "high": high, "overall": overall}


def _warm_up(sim, settings, frames=30, dt=1 / 60):
    """Run quiet ticks to let bubbles spawn and running averages settle."""
    quiet = _energy(bass=0.15, mid=0.10, high=0.05)
    for _ in range(frames):
        sim.tick(dt, quiet, settings)


def _big_bubbles(sim):
    return [b for b in sim._bubbles if b.is_big and not b.exiting]


def _small_bubbles(sim):
    return [b for b in sim._bubbles if not b.is_big and not b.exiting]


def _max_big_pulse(sim):
    bigs = _big_bubbles(sim)
    return max((b.pulse_energy for b in bigs), default=0.0)


def _max_small_pulse(sim):
    smalls = _small_bubbles(sim)
    return max((b.pulse_energy for b in smalls), default=0.0)


# ---------------------------------------------------------------------------
# 1. Rapid beat cluster — burst detection
# ---------------------------------------------------------------------------

class TestRapidBeatCluster:
    """When 4 bass kicks arrive within 2 seconds, burst mode should activate
    and subsequent beats should still produce visible pulse responses."""

    def test_burst_mode_activates_on_rapid_beats(self):
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        # Deliver 4 rapid kicks spaced ~0.4s apart
        dt = 1 / 60
        kick = _energy(bass=0.75, mid=0.20, high=0.10)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        for beat_idx in range(4):
            # 4 frames of kick (~67ms)
            for _ in range(4):
                sim.tick(dt, kick, settings)
            # 20 frames of quiet (~333ms) between kicks
            for _ in range(20):
                sim.tick(dt, quiet, settings)

        assert sim._burst_active or sim._burst_cooldown > 0, (
            "Burst mode should be active or in cooldown after 4 rapid beats"
        )

    def test_subsequent_beats_still_produce_pulse(self):
        """Each beat in a rapid cluster should produce a visible pulse,
        not just the first one."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        kick = _energy(bass=0.75, mid=0.20, high=0.10)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        peak_pulses = []
        for beat_idx in range(4):
            # Deliver kick
            for _ in range(4):
                sim.tick(dt, kick, settings)
            peak_pulses.append(_max_big_pulse(sim))
            # Decay between beats
            for _ in range(20):
                sim.tick(dt, quiet, settings)

        # All 4 beats should produce meaningful pulse (>0.05)
        for i, pe in enumerate(peak_pulses):
            assert pe > 0.05, f"Beat {i+1} peak pulse {pe:.4f} too low"

        # The 4th beat should still be at least 30% of the 1st beat's strength
        # (without burst mode, running avg catches up and kills subsequent beats)
        ratio = peak_pulses[3] / max(peak_pulses[0], 1e-6)
        assert ratio > 0.30, (
            f"4th beat ({peak_pulses[3]:.4f}) is only {ratio:.1%} of 1st beat "
            f"({peak_pulses[0]:.4f}) — rapid beats not compensated"
        )


# ---------------------------------------------------------------------------
# 2. Sustained loud section with periodic beats
# ---------------------------------------------------------------------------

class TestSustainedLoudSection:
    """During a loud chorus with periodic beats, the sustained floor should
    keep bubbles inflated while delta catches individual kicks."""

    def test_sustained_floor_holds_during_chorus(self):
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        # Simulate 3 seconds of loud chorus with periodic kicks every 0.5s
        loud_base = _energy(bass=0.60, mid=0.50, high=0.30)
        kick_on_loud = _energy(bass=0.85, mid=0.55, high=0.35)

        # Run 3s of chorus
        for sec in range(6):  # 6 × 0.5s segments
            # Kick frames (4 frames)
            for _ in range(4):
                sim.tick(dt, kick_on_loud, settings)
            # Sustained frames (26 frames = ~0.43s)
            for _ in range(26):
                sim.tick(dt, loud_base, settings)

        # After sustained loud section, big bubble pulse should be meaningful
        pulse = _max_big_pulse(sim)
        assert pulse > 0.10, (
            f"Sustained loud chorus pulse {pulse:.4f} too low — "
            "sustained floor not holding"
        )


# ---------------------------------------------------------------------------
# 3. Quiet → Loud → Quiet transition
# ---------------------------------------------------------------------------

class TestQuietLoudTransition:
    def test_loud_section_raises_pulse(self):
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)
        loud = _energy(bass=0.80, mid=0.50, high=0.30)

        # Quiet baseline
        for _ in range(30):
            sim.tick(dt, quiet, settings)
        quiet_pulse = _max_big_pulse(sim)

        # Loud section
        for _ in range(30):
            sim.tick(dt, loud, settings)
        loud_pulse = _max_big_pulse(sim)

        assert loud_pulse > quiet_pulse + 0.05, (
            f"Loud pulse {loud_pulse:.4f} not meaningfully higher than "
            f"quiet pulse {quiet_pulse:.4f}"
        )

    def test_pulse_decays_after_loud_section(self):
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)
        loud = _energy(bass=0.80, mid=0.50, high=0.30)

        # Build up pulse
        for _ in range(30):
            sim.tick(dt, loud, settings)
        peak = _max_big_pulse(sim)

        # Decay back to quiet
        for _ in range(120):  # 2 seconds
            sim.tick(dt, quiet, settings)
        after_decay = _max_big_pulse(sim)

        assert after_decay < peak * 0.5, (
            f"Pulse didn't decay enough: peak={peak:.4f} after_decay={after_decay:.4f}"
        )


# ---------------------------------------------------------------------------
# 4. Single isolated kick
# ---------------------------------------------------------------------------

class TestSingleKick:
    def test_single_kick_produces_pulse(self):
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        # Record baseline
        for _ in range(10):
            sim.tick(dt, quiet, settings)
        baseline = _max_big_pulse(sim)

        # Single kick (6 frames = 100ms)
        kick = _energy(bass=0.80, mid=0.25, high=0.10)
        for _ in range(6):
            sim.tick(dt, kick, settings)
        kick_pulse = _max_big_pulse(sim)

        assert kick_pulse > baseline + 0.10, (
            f"Single kick pulse {kick_pulse:.4f} not raised above "
            f"baseline {baseline:.4f}"
        )


# ---------------------------------------------------------------------------
# 5. Small→big promotion during bursts
# ---------------------------------------------------------------------------

class TestSmallBubblePromotion:
    def test_promoted_bubbles_react_to_bass(self):
        """During a beat burst, some small bubbles should be promoted
        and react to bass energy."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        kick = _energy(bass=0.75, mid=0.20, high=0.10)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        # Trigger burst mode with rapid beats
        for _ in range(4):
            for _ in range(4):
                sim.tick(dt, kick, settings)
            for _ in range(20):
                sim.tick(dt, quiet, settings)

        # Check that some small bubbles are promoted
        promoted = [b for b in sim._bubbles if b.promoted]
        assert len(promoted) > 0, "No small bubbles promoted during burst"

        # Deliver another kick and check promoted bubbles have pulse
        for _ in range(6):
            sim.tick(dt, kick, settings)

        promoted_with_pulse = [b for b in sim._bubbles if b.promoted and b.pulse_energy > 0.02]
        assert len(promoted_with_pulse) > 0, (
            "Promoted bubbles should have visible pulse_energy after bass kick"
        )

    def test_promotion_expires(self):
        """Promoted status should expire after the promotion timer runs out."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        kick = _energy(bass=0.75, mid=0.20, high=0.10)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        # Trigger burst
        for _ in range(4):
            for _ in range(4):
                sim.tick(dt, kick, settings)
            for _ in range(20):
                sim.tick(dt, quiet, settings)

        promoted_count = sum(1 for b in sim._bubbles if b.promoted)
        assert promoted_count > 0, "Should have promoted bubbles"

        # Run quiet for 2 seconds (burst cools down + promotion expires at 1.2s)
        for _ in range(120):
            sim.tick(dt, quiet, settings)

        remaining = sum(1 for b in sim._bubbles if b.promoted)
        assert remaining == 0, (
            f"Promotion should have expired but {remaining} bubbles still promoted"
        )


# ---------------------------------------------------------------------------
# 6. Stream speed reactivity
# ---------------------------------------------------------------------------

class TestStreamSpeedReactivity:
    def test_reactivity_increases_bubble_displacement(self):
        seed = 1337
        dt = 1 / 60
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)
        vocal = {
            "bass": 0.12,
            "mid": 0.82,
            "high": 0.68,
            "overall": 0.46,
            "smooth_mid": 0.82,
            "smooth_high": 0.68,
        }

        base_settings = _default_settings(
            bubble_stream_constant_speed=0.18,
            bubble_stream_speed_cap=1.9,
        )
        high_settings = _default_settings(
            bubble_stream_constant_speed=0.18,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.0,
        )
        low_settings = _default_settings(
            bubble_stream_constant_speed=0.18,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=0.0,
        )

        random.seed(seed)
        sim_low = BubbleSimulation()
        _warm_up(sim_low, base_settings, frames=60)

        random.seed(seed)
        sim_high = BubbleSimulation()
        _warm_up(sim_high, base_settings, frames=60)

        sim_high._bubbles = copy.deepcopy(sim_low._bubbles)

        low_before = [b.y for b in sim_low._bubbles if not b.exiting]
        high_before = [b.y for b in sim_high._bubbles if not b.exiting]

        for _ in range(12):
            sim_low.tick(dt, quiet, low_settings)
            sim_high.tick(dt, vocal, high_settings)

        low_after = [b.y for b in sim_low._bubbles if not b.exiting]
        high_after = [b.y for b in sim_high._bubbles if not b.exiting]

        low_displacement = sum(abs(a - b) for a, b in zip(low_after, low_before))
        high_displacement = sum(abs(a - b) for a, b in zip(high_after, high_before))

        assert sim_high._smoothed_speed_energy > sim_low._smoothed_speed_energy + 0.05, (
            "High stream reactivity should build more speed energy than the low-reactivity case"
        )
        assert high_displacement > low_displacement * 1.35, (
            f"High-reactivity stream displacement {high_displacement:.4f} should exceed "
            f"low-reactivity displacement {low_displacement:.4f}"
        )
