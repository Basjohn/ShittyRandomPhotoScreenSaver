"""Tests for bubble simulation reactivity with simulated audio data.

Covers key scenarios:
  1. Rapid beat clusters (4+ kicks in 2s) — burst detection + promoted bubbles
  2. Sustained loud sections with periodic beats — sustained floor holds
  3. Quiet→loud→quiet transitions — attack/decay behaviour
  4. Single isolated kick — delta component fires correctly
  5. Burst mode promotions stay conservative in ordinary stream modes
  6. Bubble startup/grouping contracts preserve broad startup spread and protect big bubbles from ugly stackups

All tests use synthetic energy dicts fed into BubbleSimulation.tick().
"""
from __future__ import annotations

import copy
import math
import pathlib
import random
import subprocess
import sys
from types import SimpleNamespace
import types

import pytest

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
        "bubble_bounce_big_pct": 70,
        "bubble_bounce_small_pct": 30,
        "bubble_bounce_big_speed": 0.8,
        "bubble_bounce_small_speed": 0.5,
        "bubble_bounce_same_only": False,
        "bubble_collision_pop_mode": "off",
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


def _snapshot_big_radii(
    sim,
    *,
    big_bass_pulse=0.9,
    small_freq_pulse=0.5,
    big_specular_max_size=1.5,
    big_contraction_bias=0.55,
    big_size_clamp=3.14,
):
    pos_data, _extra, _trail = sim.snapshot(
        bass=0.0,
        mid_high=0.0,
        big_bass_pulse=big_bass_pulse,
        small_freq_pulse=small_freq_pulse,
        big_specular_max_size=big_specular_max_size,
        big_contraction_bias=big_contraction_bias,
        big_size_clamp=big_size_clamp,
    )
    radii = []
    for idx, bubble in enumerate(sim._bubbles):
        if bubble.is_big and not bubble.exiting:
            radii.append(pos_data[idx * 4 + 2])
    return radii


def _snapshot_max_radius(
    sim,
    *,
    bass: float,
    mid_high: float,
    big_bass_pulse=0.9,
    small_freq_pulse=0.5,
):
    pos_data, _extra, _trail = sim.snapshot(
        bass=bass,
        mid_high=mid_high,
        big_bass_pulse=big_bass_pulse,
        small_freq_pulse=small_freq_pulse,
    )
    return max((pos_data[i] for i in range(2, len(pos_data), 4)), default=0.0)


def _snapshot_small_max_radius(
    sim,
    *,
    big_bass_pulse=0.9,
    small_freq_pulse=0.5,
):
    pos_data, _extra, _trail = sim.snapshot(
        bass=0.0,
        mid_high=0.0,
        big_bass_pulse=big_bass_pulse,
        small_freq_pulse=small_freq_pulse,
    )
    radii = []
    for idx, bubble in enumerate(sim._bubbles):
        if (not bubble.is_big) and not bubble.exiting:
            radii.append(pos_data[idx * 4 + 2])
    return max(radii, default=0.0)


def _big_lane_metrics(
    sim,
    *,
    big_bass_pulse=0.9,
    small_freq_pulse=0.5,
    big_specular_max_size=1.5,
    big_contraction_bias=0.55,
    big_size_clamp=3.14,
):
    pos_data, _extra, _trail = sim.snapshot(
        bass=0.0,
        mid_high=0.0,
        big_bass_pulse=big_bass_pulse,
        small_freq_pulse=small_freq_pulse,
        big_specular_max_size=big_specular_max_size,
        big_contraction_bias=big_contraction_bias,
        big_size_clamp=big_size_clamp,
    )
    big_active = 0
    big_count = 0
    big_radius_deltas = []
    small_radius_deltas = []
    for idx, bubble in enumerate(sim._bubbles):
        if bubble.exiting:
            continue
        render_radius = pos_data[idx * 4 + 2]
        delta = max(0.0, render_radius - bubble.radius)
        if bubble.is_big:
            big_count += 1
            if bubble.pulse_energy > 0.04:
                big_active += 1
            big_radius_deltas.append(delta)
        else:
            small_radius_deltas.append(delta)
    diag = sim.get_big_lane_diagnostics()
    return {
        "big_count": big_count,
        "big_active": big_active,
        "big_active_ratio": (big_active / big_count) if big_count else 0.0,
        "max_big_delta": max(big_radius_deltas, default=0.0),
        "avg_big_delta": (sum(big_radius_deltas) / len(big_radius_deltas)) if big_radius_deltas else 0.0,
        "max_small_delta": max(small_radius_deltas, default=0.0),
        "max_big_pulse": float(diag.get("max_big_pulse_after", 0.0)),
        "max_big_gated": float(diag.get("max_big_gated_energy", 0.0)),
    }


def _render_lane_metrics(
    sim,
    *,
    big_bass_pulse=0.9,
    small_freq_pulse=0.5,
    big_contraction_bias=0.55,
    big_size_clamp=3.14,
):
    pos_data, _extra, _trail = sim.snapshot(
        bass=0.0,
        mid_high=0.0,
        big_bass_pulse=big_bass_pulse,
        small_freq_pulse=small_freq_pulse,
        big_contraction_bias=big_contraction_bias,
        big_size_clamp=big_size_clamp,
    )
    big_render = []
    small_render = []
    for idx, bubble in enumerate(sim._bubbles):
        if bubble.exiting:
            continue
        render_radius = pos_data[idx * 4 + 2]
        row = (bubble.radius, render_radius, max(0.0, render_radius - bubble.radius))
        if bubble.is_big:
            big_render.append(row)
        else:
            small_render.append(row)
    render_diag = sim.get_big_render_diagnostics() if hasattr(sim, "get_big_render_diagnostics") else {}
    return {
        "big_max_render": max((r for _b, r, _d in big_render), default=0.0),
        "big_avg_render": (sum(r for _b, r, _d in big_render) / len(big_render)) if big_render else 0.0,
        "big_max_delta": max((d for _b, _r, d in big_render), default=0.0),
        "small_max_render": max((r for _b, r, _d in small_render), default=0.0),
        "small_avg_render": (sum(r for _b, r, _d in small_render) / len(small_render)) if small_render else 0.0,
        "small_max_delta": max((d for _b, _r, d in small_render), default=0.0),
        "clamp_hits": float(render_diag.get("big_clamp_hits", 0.0)),
    }


def test_snapshot_omits_trail_payload_when_no_visible_trails_exist():
    sim = BubbleSimulation()
    settings = _default_settings(
        bubble_big_count=4,
        bubble_small_count=10,
        bubble_trail_strength=0.0,
    )
    _warm_up(sim, settings, frames=30)

    pos_data, extra_data, trail_data = sim.snapshot()

    assert len(pos_data) == len(sim._bubbles) * 4
    assert len(extra_data) == len(sim._bubbles) * 4
    assert trail_data == []


def test_snapshot_keeps_full_trail_layout_when_any_visible_trail_exists():
    sim = BubbleSimulation()
    settings = _default_settings(
        bubble_big_count=2,
        bubble_small_count=4,
        bubble_trail_strength=1.0,
    )
    _warm_up(sim, settings, frames=30)
    moving = _energy(bass=0.55, mid=0.32, high=0.14)
    for _ in range(12):
        sim.tick(1 / 60, moving, settings)

    pos_data, extra_data, trail_data = sim.snapshot()

    assert len(pos_data) == len(sim._bubbles) * 4
    assert len(extra_data) == len(sim._bubbles) * 4
    assert len(trail_data) == len(sim._bubbles) * 9


def _load_historical_bubble_module(rev: str):
    root = pathlib.Path(__file__).resolve().parents[1]
    src = subprocess.check_output(
        ["git", "show", f"{rev}:widgets/spotify_visualizer/bubble_simulation.py"],
        cwd=root,
        text=True,
    )
    name = f"bubble_{rev}"
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    exec(src, mod.__dict__)
    return mod


class _SingleShotScheduler:
    def __init__(self, *, kick_strength=0.0, snare_strength=0.0, vocal_strength=0.0):
        self._events = {
            "kick": [SimpleNamespace(strength=kick_strength)] if kick_strength > 0.0 else [],
            "snare": [SimpleNamespace(strength=snare_strength)] if snare_strength > 0.0 else [],
            "vocal_swell": [SimpleNamespace(strength=vocal_strength)] if vocal_strength > 0.0 else [],
        }

    def consume_next(self, event_type, max_age_s=0.5):
        queue = self._events.get(event_type, [])
        if queue:
            return queue.pop(0)
        return None

    def peek_latest(self, event_type, max_age_s=0.3):
        queue = self._events.get(event_type, [])
        if queue:
            return queue[-1]
        return None


class _ConsumeOnlyScheduler(_SingleShotScheduler):
    def peek_latest(self, event_type, max_age_s=0.3):
        raise AssertionError(
            "Bubble burst/overdrive should consume scheduler edges once, not poll them with peek_latest()."
        )


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
        assert pulse > 0.042, (
            f"Sustained loud chorus pulse {pulse:.4f} too low — "
            "sustained floor not holding"
        )

    def test_hot_start_chorus_still_reacts(self):
        """Starting directly in a loud chorus must not dead-start bubbles."""
        sim = BubbleSimulation()
        settings = _default_settings()
        dt = 1 / 60

        # Start hot immediately (no quiet warm-up), with mild variation.
        chorus_frames = [
            _energy(bass=0.92, mid=0.88, high=0.24),
            _energy(bass=0.78, mid=0.73, high=0.20),
            _energy(bass=0.95, mid=0.90, high=0.28),
            _energy(bass=0.81, mid=0.76, high=0.22),
        ]

        peaks = []
        for i in range(48):
            sim.tick(dt, chorus_frames[i % len(chorus_frames)], settings)
            peaks.append(_max_big_pulse(sim))

        assert max(peaks) > 0.09, (
            "Hot-start chorus failed to generate meaningful big-bubble pulse energy"
        )

    def test_hot_chorus_variation_not_flatlined(self):
        """Sustained hot passages should keep visible pulse variance."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=30)
        dt = 1 / 60

        chorus_frames = [
            _energy(bass=0.96, mid=0.91, high=0.23),
            _energy(bass=0.82, mid=0.78, high=0.17),
            _energy(bass=0.94, mid=0.88, high=0.25),
            _energy(bass=0.79, mid=0.74, high=0.18),
        ]

        pulse_series = []
        for i in range(160):
            sim.tick(dt, chorus_frames[i % len(chorus_frames)], settings)
            pulse_series.append(_max_big_pulse(sim))

        spread = max(pulse_series) - min(pulse_series)
        assert spread > 0.035, (
            f"Hot-chorus pulse variance collapsed (spread={spread:.4f})"
        )

    def test_live_energy_raises_rendered_big_bubble_size(self):
        """Louder live energy should grow rendered big bubbles, not invert them."""
        sim = BubbleSimulation()
        settings = _default_settings(bubble_big_count=4, bubble_small_count=10)
        _warm_up(sim, settings, frames=24)

        dt = 1 / 60
        quiet = _energy(bass=0.18, mid=0.10, high=0.05)
        loud = _energy(bass=0.74, mid=0.28, high=0.12)

        for _ in range(18):
            sim.tick(dt, quiet, settings)
        low = _snapshot_max_radius(sim, bass=0.0, mid_high=0.0)

        for _ in range(12):
            sim.tick(dt, loud, settings)
        high = _snapshot_max_radius(sim, bass=0.0, mid_high=0.0)

        assert high > low + 0.008, (
            f"Loud live energy only changed Bubble max radius by {high - low:.4f}; "
            "the visible big-bubble lane is still too flat or inverted."
        )

    def test_live_energy_raises_rendered_small_bubble_size(self):
        """Small bubbles should not stay visually dormant during live energy."""
        sim = BubbleSimulation()
        settings = _default_settings(bubble_big_count=4, bubble_small_count=12)
        _warm_up(sim, settings, frames=24)

        dt = 1 / 60
        quiet = _energy(bass=0.14, mid=0.08, high=0.04)
        loud = _energy(bass=0.22, mid=0.58, high=0.36)

        for _ in range(18):
            sim.tick(dt, quiet, settings)
        low = _snapshot_small_max_radius(
            sim,
            big_bass_pulse=0.9,
            small_freq_pulse=0.6,
        )

        for _ in range(12):
            sim.tick(dt, loud, settings)
        high = _snapshot_small_max_radius(
            sim,
            big_bass_pulse=0.9,
            small_freq_pulse=0.6,
        )

        assert high > low + 0.0015, (
            f"Loud live energy only changed small-bubble max radius by {high - low:.4f}; "
            "the small-bubble lane is still too dormant."
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
    def test_stream_mode_promotions_only_appear_when_big_lane_is_hot(self):
        """Ordinary stream modes should not spray promoted pseudo-big bubbles
        during every beat. Promotions are only useful once the real big lane is
        already running hot."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        kick = _energy(bass=0.75, mid=0.20, high=0.10)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)

        # Cold/medium burst should not promote in an ordinary stream mode.
        for _ in range(8):
            sim.tick(dt, kick, settings)
        promoted = [b for b in sim._bubbles if b.promoted]
        assert len(promoted) == 0, (
            "Ordinary stream mode promoted bubbles before the big-bubble lane was even hot."
        )

        # After a hot run the lane is allowed a very small promotion assist.
        loud = _energy(bass=0.92, mid=0.28, high=0.12)
        for _ in range(40):
            sim.tick(dt, loud, settings)
        sim.tick(dt, kick, settings)

        promoted = [b for b in sim._bubbles if b.promoted]
        assert len(promoted) <= 1, (
            f"Ordinary stream mode promoted {len(promoted)} bubbles at once; "
            "that is enough to counterfeit a second big-bubble population."
        )

    def test_stream_mode_promotion_expires_quickly(self):
        """Ordinary stream-mode promotions should be short accents, not a
        durable pseudo-big state."""
        sim = BubbleSimulation()
        settings = _default_settings()
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        loud = _energy(bass=0.95, mid=0.30, high=0.12)
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        for _ in range(40):
            sim.tick(dt, loud, settings)
        hot_settings = _default_settings(_event_scheduler=_SingleShotScheduler(kick_strength=0.9))
        sim.tick(dt, loud, hot_settings)

        promoted_count = sum(1 for b in sim._bubbles if b.promoted)
        assert promoted_count > 0, "Should have promoted bubbles"

        for _ in range(24):
            sim.tick(dt, quiet, settings)

        remaining = sum(1 for b in sim._bubbles if b.promoted)
        assert remaining == 0, (
            f"Promotion should have expired but {remaining} bubbles still promoted"
        )


class TestInitialFillContract:
    def test_ordinary_stream_mode_cold_start_begins_with_a_broad_in_card_field(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=15,
            bubble_stream_direction="up",
            bubble_drift_direction="random",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        sim.tick(1 / 60, quiet, settings)

        active = [b for b in sim._bubbles if not b.exiting]
        inside = [b for b in active if 0.0 <= b.x <= 1.0 and 0.0 <= b.y <= 1.0]
        assert len(inside) >= 10, (
            f"Ordinary stream cold start only produced {len(inside)} visible bubbles; "
            "the field should begin in a partially established in-card state."
        )
        x_span = max((b.x for b in inside), default=0.0) - min((b.x for b in inside), default=0.0)
        y_span = max((b.y for b in inside), default=0.0) - min((b.y for b in inside), default=0.0)
        assert x_span > 0.45 and y_span > 0.35, (
            f"Cold-start spread is still too column-like (x_span={x_span:.3f}, y_span={y_span:.3f})."
        )

    def test_swirl_mode_may_still_use_in_card_initial_fill(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=15,
            bubble_stream_direction="up",
            bubble_drift_direction="swirl_cw",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        sim.tick(1 / 60, quiet, settings)

        inside = [
            b for b in sim._bubbles
            if not b.exiting and 0.0 <= b.x <= 1.0 and 0.0 <= b.y <= 1.0
        ]
        assert len(inside) >= 6, (
            "Swirl mode should still be allowed to cold-start with an in-card population."
        )

    def test_directional_stream_cold_start_avoids_single_lane_boot_columns(self):
        random.seed(1337)
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=8,
            bubble_small_count=18,
            bubble_stream_direction="left",
            bubble_drift_direction="random",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        sim.tick(1 / 60, quiet, settings)
        visible = [
            b for b in sim._bubbles
            if not b.exiting and 0.0 <= b.x <= 1.0 and 0.0 <= b.y <= 1.0
        ]
        assert len(visible) >= 10, "Directional cold start should visibly establish a field immediately."
        y_span = max((b.y for b in visible), default=0.0) - min((b.y for b in visible), default=0.0)
        assert y_span > 0.35, (
            f"Directional startup visible y-span was only {y_span:.3f}; "
            "the opening state is still bunching into a narrow lane."
        )

    def test_directional_stream_assigns_non_uniform_travel_speeds(self):
        random.seed(7331)
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=15,
            bubble_stream_direction="left",
            bubble_drift_direction="random",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        for _ in range(25):
            sim.tick(1 / 60, quiet, settings)

        moving = [
            b.speed_mult for b in sim._bubbles
            if not b.exiting and (b.is_big or 0.0 <= b.x <= 1.0)
        ]
        assert moving, "Expected directional stream bubbles to exist."
        assert max(moving) - min(moving) > 0.12, (
            "Directional stream bubbles are still sharing nearly identical travel speeds, "
            "which makes the field quantize into visible columns."
        )

    def test_explicit_diagonal_stream_direction_moves_across_both_axes(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=0,
            bubble_small_count=1,
            bubble_stream_direction="top_left",
            bubble_drift_direction="none",
            bubble_stream_constant_speed=0.8,
            bubble_stream_speed_cap=0.8,
            bubble_stream_reactivity=1.0,
            bubble_drift_amount=0.0,
            bubble_drift_speed=0.0,
            bubble_drift_frequency=0.0,
            bubble_rotation_amount=0.0,
        )
        _warm_up(sim, settings, frames=3)

        bubble = next((b for b in sim._bubbles if not b.exiting), None)
        assert bubble is not None
        start_x, start_y = bubble.x, bubble.y

        for _ in range(10):
            sim.tick(1 / 60, _energy(bass=0.15, mid=0.1, high=0.05), settings)

        assert bubble.x < start_x, "Top-left stream should move bubble left."
        assert bubble.y < start_y, "Top-left stream should move bubble upward on screen."

    def test_big_bubbles_do_not_spawn_tightly_clustered(self):
        random.seed(404)
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=8,
            bubble_small_count=12,
            bubble_stream_direction="left",
            bubble_drift_direction="random",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        for _ in range(20):
            sim.tick(1 / 60, quiet, settings)

        bigs = [b for b in sim._bubbles if b.is_big and not b.exiting]
        violations = 0
        for i, a in enumerate(bigs):
            for b in bigs[i + 1:]:
                if math.hypot(b.x - a.x, b.y - a.y) < (a.radius + b.radius) * 1.02:
                    violations += 1
        assert violations == 0, (
            f"Found {violations} overly tight big-big pair(s); big bubbles still cluster too readily."
        )

    def test_runtime_overlap_guard_reduces_severe_transparent_stackups(self):
        random.seed(505)
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=8,
            bubble_small_count=18,
            bubble_stream_direction="left",
            bubble_drift_direction="random",
        )
        quiet = _energy(bass=0.10, mid=0.08, high=0.04)

        for _ in range(90):
            sim.tick(1 / 60, quiet, settings)

        severe = 0
        active = [b for b in sim._bubbles if not b.exiting]
        for i, a in enumerate(active):
            for b in active[i + 1:]:
                a_big = a.is_big or a.promoted
                b_big = b.is_big or b.promoted
                threshold = (a.radius + b.radius) * (0.94 if (a_big and b_big) else (0.78 if (a_big or b_big) else 0.68))
                if math.hypot(b.x - a.x, b.y - a.y) < threshold:
                    severe += 1
        assert severe <= 3, (
            f"Found {severe} severe transparent overlap pair(s); runtime separation is still too weak."
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

    def test_sustained_bass_heavy_sections_drive_motion_even_with_calm_vocal_lane(self):
        seed = 1441
        dt = 1 / 60
        quiet = {
            "bass": 0.12,
            "mid": 0.12,
            "high": 0.05,
            "overall": 0.11,
            "smooth_mid": 0.12,
            "smooth_high": 0.05,
        }
        sustained_hot = {
            "bass": 0.92,
            "mid": 0.14,
            "high": 0.05,
            "overall": 0.42,
            "smooth_mid": 0.14,
            "smooth_high": 0.05,
        }
        settings = _default_settings(
            bubble_stream_constant_speed=0.18,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=0.95,
        )

        random.seed(seed)
        sim_quiet = BubbleSimulation()
        _warm_up(sim_quiet, settings, frames=60)

        random.seed(seed)
        sim_hot = BubbleSimulation()
        _warm_up(sim_hot, settings, frames=60)
        sim_hot._bubbles = copy.deepcopy(sim_quiet._bubbles)

        quiet_before = [(b.x, b.y) for b in sim_quiet._bubbles if not b.exiting]
        hot_before = [(b.x, b.y) for b in sim_hot._bubbles if not b.exiting]

        for _ in range(18):
            sim_quiet.tick(dt, quiet, settings)
            sim_hot.tick(dt, sustained_hot, settings)

        quiet_after = [(b.x, b.y) for b in sim_quiet._bubbles if not b.exiting]
        hot_after = [(b.x, b.y) for b in sim_hot._bubbles if not b.exiting]

        quiet_displacement = sum(
            math.hypot(ax - bx, ay - by)
            for (bx, by), (ax, ay) in zip(quiet_before, quiet_after)
        )
        hot_displacement = sum(
            math.hypot(ax - bx, ay - by)
            for (bx, by), (ax, ay) in zip(hot_before, hot_after)
        )

        assert sim_hot._sustained_loud_energy >= 0.22, (
            f"Sustained loud envelope only reached {sim_hot._sustained_loud_energy:.3f} on a bass-heavy hot section."
        )
        assert hot_displacement > quiet_displacement * 1.05, (
            f"Bass-heavy sustained loud motion {hot_displacement:.4f} should exceed quiet motion "
            f"{quiet_displacement:.4f} even when the vocal lane stays calm."
        )

    def test_sustained_loud_motion_releases_quickly_after_the_drop(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.18,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=0.95,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        sustained_hot = {
            "bass": 0.90,
            "mid": 0.16,
            "high": 0.06,
            "overall": 0.43,
            "smooth_mid": 0.16,
            "smooth_high": 0.06,
        }
        quiet = {
            "bass": 0.12,
            "mid": 0.10,
            "high": 0.05,
            "overall": 0.10,
            "smooth_mid": 0.10,
            "smooth_high": 0.05,
        }

        for _ in range(30):
            sim.tick(dt, sustained_hot, settings)
        hot_energy = sim._sustained_loud_energy

        for _ in range(18):
            sim.tick(dt, quiet, settings)

        assert hot_energy >= 0.24, (
            f"Expected the hot section to build a meaningful loud-motion envelope, got {hot_energy:.3f}."
        )
        assert sim._sustained_loud_energy < hot_energy * 0.76, (
            "Sustained loud motion is still lingering too long after the section drops."
        )
        assert sim._sustained_loud_energy < 0.26, (
            f"Sustained loud motion only decayed to {sim._sustained_loud_energy:.3f}; Bubble still feels too sticky."
        )


class TestBubblePlateauGuardrails:
    def test_medium_vocal_run_does_not_latch_overdrive_for_entire_phrase(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.22,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.25,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        # Log-shaped alternating material: medium-strength vocal-heavy phrases
        # with short breathers between them. This should breathe, not park
        # Bubble in overdrive for almost the entire phrase.
        phrase = (
            {
                "bass": 0.20,
                "mid": 0.58,
                "high": 0.26,
                "overall": 0.33,
                "smooth_mid": 0.58,
                "smooth_high": 0.26,
            },
            {
                "bass": 0.18,
                "mid": 0.56,
                "high": 0.24,
                "overall": 0.31,
                "smooth_mid": 0.56,
                "smooth_high": 0.24,
            },
            {
                "bass": 0.12,
                "mid": 0.20,
                "high": 0.08,
                "overall": 0.14,
                "smooth_mid": 0.20,
                "smooth_high": 0.08,
            },
            {
                "bass": 0.21,
                "mid": 0.62,
                "high": 0.27,
                "overall": 0.35,
                "smooth_mid": 0.62,
                "smooth_high": 0.27,
            },
            {
                "bass": 0.14,
                "mid": 0.24,
                "high": 0.10,
                "overall": 0.16,
                "smooth_mid": 0.24,
                "smooth_high": 0.10,
            },
            {
                "bass": 0.18,
                "mid": 0.52,
                "high": 0.22,
                "overall": 0.29,
                "smooth_mid": 0.52,
                "smooth_high": 0.22,
            },
        )

        active_frames = 0
        release_frames = 0
        transition_count = 0
        prev_active = sim._overdrive_active
        for idx in range(300):
            sim.tick(dt, phrase[idx % len(phrase)], settings)
            if sim._overdrive_active:
                active_frames += 1
            else:
                release_frames += 1
            if sim._overdrive_active != prev_active:
                transition_count += 1
                prev_active = sim._overdrive_active

        assert active_frames < 180, (
            f"Bubble stayed in overdrive for {active_frames} / 300 frames on an alternating "
            "medium-vocal run; the gate is still latching instead of breathing."
        )
        assert release_frames > 36, (
            f"Bubble only spent {release_frames} frames out of overdrive on the same run; "
            "the speed path still has almost no real release windows."
        )
        assert transition_count <= 4, (
            f"Bubble changed overdrive state {transition_count} time(s) on a medium-vocal run; "
            "the emergency lane is still chattering instead of staying rare."
        )

    def test_sustained_hot_section_does_not_pin_big_bubbles_near_ceiling(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.22,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.25,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        hot = {
            "bass": 0.55,
            "mid": 0.52,
            "high": 0.28,
            "overall": 0.44,
            "smooth_mid": 0.52,
            "smooth_high": 0.28,
        }

        plateau_frames = 0
        max_big = 0.0
        for _ in range(150):
            sim.tick(dt, hot, settings)
            pulse = _max_big_pulse(sim)
            max_big = max(max_big, pulse)
            if pulse >= 0.88:
                plateau_frames += 1

        assert max_big < 0.98, (
            f"Big-bubble pulse peaked at {max_big:.3f}, which is too close to a hard ceiling "
            "for an ordinary sustained loud passage."
        )
        assert plateau_frames < 24, (
            f"Big bubbles spent {plateau_frames} frames pinned near the ceiling; Bubble is still "
            "living in an overdrive/plateau state instead of breathing."
        )

    def test_big_bubbles_get_a_real_quiet_breath_window_after_hot_section(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.22,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.25,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        hot = {
            "bass": 0.55,
            "mid": 0.50,
            "high": 0.24,
            "overall": 0.42,
            "smooth_mid": 0.50,
            "smooth_high": 0.24,
        }
        quiet = {
            "bass": 0.10,
            "mid": 0.08,
            "high": 0.04,
            "overall": 0.09,
            "smooth_mid": 0.08,
            "smooth_high": 0.04,
        }

        for _ in range(90):
            sim.tick(dt, hot, settings)
        hot_radii = _snapshot_big_radii(sim)

        for _ in range(75):
            sim.tick(dt, quiet, settings)
        quiet_radii = _snapshot_big_radii(sim)

        base_radii = [b.radius for b in _big_bubbles(sim)]
        assert hot_radii and quiet_radii and base_radii, "Need live big bubbles to measure breathing."

        hot_avg = sum(hot_radii) / len(hot_radii)
        quiet_avg = sum(quiet_radii) / len(quiet_radii)
        base_avg = sum(base_radii) / len(base_radii)

        assert quiet_avg < base_avg * 0.92, (
            f"Quiet section only fell to average big radius {quiet_avg:.4f} from base {base_avg:.4f}; "
            "Bubble still lacks a real breathing contraction."
        )
        assert hot_avg > quiet_avg * 1.16, (
            f"Hot average {hot_avg:.4f} stayed too close to quiet average {quiet_avg:.4f}; "
            "the pulse side still is not clearly separating from the breathing window."
        )
        assert quiet_avg < hot_avg * 0.86, (
            f"Quiet average {quiet_avg:.4f} stayed too close to hot average {hot_avg:.4f}; "
            "big bubbles are still hovering instead of taking a deep breath."
        )

    def test_bubble_speed_recovers_without_long_overdrive_hold_after_hot_phrase(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.22,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.25,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        hot = {
            "bass": 0.52,
            "mid": 0.50,
            "high": 0.24,
            "overall": 0.41,
            "smooth_mid": 0.50,
            "smooth_high": 0.24,
        }
        quiet = {
            "bass": 0.12,
            "mid": 0.11,
            "high": 0.06,
            "overall": 0.10,
            "smooth_mid": 0.11,
            "smooth_high": 0.06,
        }

        for _ in range(90):
            sim.tick(dt, hot, settings)

        quiet_hold_frames = 0
        for _ in range(60):
            sim.tick(dt, quiet, settings)
            if sim._overdrive_active:
                quiet_hold_frames += 1

        assert quiet_hold_frames < 18, (
            f"Bubble stayed in overdrive for {quiet_hold_frames} quiet frames after the phrase; "
            "speed is still too sticky and likely to feel jerky/stuck."
        )
        assert sim._smoothed_speed_energy < 0.36, (
            f"Speed energy only decayed to {sim._smoothed_speed_energy:.3f}; Bubble travel is "
            "still carrying too much stale pressure after the hot section."
        )

    def test_bubble_burst_path_consumes_scheduler_edges(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_stream_constant_speed=0.22,
            bubble_stream_speed_cap=1.9,
            bubble_stream_reactivity=1.25,
            _event_scheduler=_ConsumeOnlyScheduler(snare_strength=0.9, vocal_strength=0.75),
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        quiet = {
            "bass": 0.12,
            "mid": 0.11,
            "high": 0.06,
            "overall": 0.10,
            "smooth_mid": 0.11,
            "smooth_high": 0.06,
        }

        sim.tick(dt, quiet, settings)
        for _ in range(6):
            sim.tick(dt, quiet, settings)

        assert not sim._overdrive_active, (
            "Bubble overdrive stayed active after a one-shot scheduler event on quiet audio."
        )

    def test_big_bubble_lane_does_not_go_dead_from_conservative_stream_preset_values(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=5,
            bubble_small_count=30,
            bubble_stream_direction="down",
            bubble_stream_constant_speed=0.10,
            bubble_stream_speed_cap=1.0,
            bubble_stream_reactivity=1.5,
            bubble_drift_direction="random",
            bubble_big_size_max=0.042,
            bubble_small_size_max=0.009,
        )
        _warm_up(sim, settings, frames=45)

        dt = 1 / 60
        phrase = _energy(bass=0.58, mid=0.20, high=0.08)
        kick = _energy(bass=0.82, mid=0.24, high=0.10)

        peaks = []
        for _ in range(4):
            for _ in range(5):
                sim.tick(dt, kick, settings)
            peaks.append(_max_big_pulse(sim))
            for _ in range(18):
                sim.tick(dt, phrase, settings)

        assert max(peaks) > 0.10, (
            f"Big-bubble lane only reached {max(peaks):.3f}; "
            "it is still too easy for conservative stream presets to lose big-bubble pulse authority."
        )
        assert peaks[-1] > 0.06, (
            f"Later big-bubble pulse collapsed to {peaks[-1]:.3f}; "
            "tiny authored changes can still kick Bubble into a dead-feeling state."
        )

    def test_big_bubble_lane_participates_in_soft_and_hot_phrases(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=45,
            bubble_big_size_max=0.035,
            bubble_small_size_max=0.012,
            bubble_big_bass_pulse=0.8,
            bubble_small_freq_pulse=0.6,
            bubble_big_contraction_bias=0.5,
            bubble_big_size_clamp=3.0,
            bubble_stream_constant_speed=0.15,
            bubble_stream_speed_cap=1.8,
            bubble_stream_reactivity=0.9,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        soft = _energy(bass=0.28, mid=0.14, high=0.05)
        hot = _energy(bass=0.72, mid=0.28, high=0.09)

        soft_metrics = []
        hot_metrics = []
        for _ in range(90):
            sim.tick(dt, soft, settings)
            soft_metrics.append(_big_lane_metrics(sim))
        for _ in range(90):
            sim.tick(dt, hot, settings)
            hot_metrics.append(_big_lane_metrics(sim))

        assert soft_metrics and hot_metrics
        soft_active_peak = max(m["big_active_ratio"] for m in soft_metrics)
        hot_active_peak = max(m["big_active_ratio"] for m in hot_metrics)
        soft_delta_peak = max(m["max_big_delta"] for m in soft_metrics)
        hot_delta_peak = max(m["max_big_delta"] for m in hot_metrics)
        soft_pulse_peak = max(m["max_big_pulse"] for m in soft_metrics)
        hot_pulse_peak = max(m["max_big_pulse"] for m in hot_metrics)

        assert soft_metrics[0]["big_count"] >= 6, "Expected the authored Deep Sea-style big population to be present."
        assert soft_active_peak >= 0.50, (
            f"Soft phrase only activated {soft_active_peak:.2f} of the big-bubble lane at its best; "
            "the hero lane is still effectively dead while small bubbles can move."
        )
        assert soft_delta_peak > 0.004, (
            f"Soft phrase only produced {soft_delta_peak:.4f} of visible big-bubble growth."
        )
        assert hot_active_peak >= 0.83, (
            f"Hot phrase only activated {hot_active_peak:.2f} of the big-bubble lane."
        )
        assert hot_delta_peak > soft_delta_peak * 1.35, (
            "Hot phrase still is not growing the hero lane clearly beyond the soft phrase."
        )
        assert hot_pulse_peak > soft_pulse_peak * 1.30, (
            "Hot phrase pulse authority is not clearly separating from the soft phrase in the big lane."
        )

    def test_small_lane_reactivity_cannot_mask_dead_big_bubbles(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=45,
            bubble_big_size_max=0.04,
            bubble_small_size_max=0.012,
            bubble_big_bass_pulse=1.01,
            bubble_small_freq_pulse=0.6,
            bubble_big_contraction_bias=0.5,
            bubble_big_size_clamp=5.61,
            bubble_stream_constant_speed=0.15,
            bubble_stream_speed_cap=1.8,
            bubble_stream_reactivity=0.9,
        )
        _warm_up(sim, settings, frames=60)

        dt = 1 / 60
        phrase = _energy(bass=0.34, mid=0.18, high=0.06)
        metrics_series = []
        for _ in range(120):
            sim.tick(dt, phrase, settings)
            metrics_series.append(_big_lane_metrics(sim))

        assert metrics_series
        max_small_delta = max(m["max_small_delta"] for m in metrics_series)
        max_big_active = max(m["big_active_ratio"] for m in metrics_series)
        max_big_avg_delta = max(m["avg_big_delta"] for m in metrics_series)
        max_big_pulse = max(m["max_big_pulse"] for m in metrics_series)

        assert max_small_delta > 0.002, "Need a live small lane for this regression guard."
        assert max_big_active >= 0.50, (
            f"Small bubbles stayed live, but only {max_big_active:.2f} of big bubbles participated."
        )
        assert max_big_avg_delta > max_small_delta * 0.55, (
            "Small-bubble reactivity is still masking an almost dormant big-bubble lane."
        )
        assert max_big_pulse > 0.08, (
            f"Conservative phrase only pushed big-bubble pulse to {max_big_pulse:.4f}."
        )

    def test_hot_preset_1_big_render_stays_near_510520e_shape(self):
        random.seed(1014)
        payload = {
            "bubble_big_count": 6,
            "bubble_small_count": 45,
            "bubble_surface_reach": 0.75,
            "bubble_stream_direction": "up",
            "bubble_stream_constant_speed": 0.15,
            "bubble_stream_speed_cap": 1.8,
            "bubble_stream_reactivity": 0.9,
            "bubble_rotation_amount": 0.15,
            "bubble_drift_amount": 0.5,
            "bubble_drift_speed": 0.3,
            "bubble_drift_frequency": 0.5,
            "bubble_drift_direction": "swish_horizontal",
            "bubble_big_size_max": 0.035,
            "bubble_small_size_max": 0.012,
            "bubble_trail_strength": 0.8,
            "bubble_bounce_big_pct": 0.0,
            "bubble_bounce_small_pct": 5.0,
            "bubble_bounce_big_speed": 0.2,
            "bubble_bounce_small_speed": 0.4,
            "bubble_bounce_same_only": True,
            "bubble_collision_pop_mode": "off",
            "bubble_big_bass_pulse": 0.8,
            "bubble_small_freq_pulse": 0.6,
            "bubble_big_contraction_bias": 0.5,
            "bubble_big_size_clamp": 3.0,
        }
        settings = _default_settings(**payload)
        quiet = _energy(bass=0.15, mid=0.10, high=0.05)
        hot = _energy(bass=1.55, mid=0.65, high=0.16)

        current = BubbleSimulation()
        _warm_up(current, settings, frames=80)
        for _ in range(24):
            current.tick(1 / 60, hot, settings)
        current_metrics = _render_lane_metrics(
            current,
            big_bass_pulse=payload["bubble_big_bass_pulse"],
            small_freq_pulse=payload["bubble_small_freq_pulse"],
            big_contraction_bias=payload["bubble_big_contraction_bias"],
            big_size_clamp=payload["bubble_big_size_clamp"],
        )

        hist_mod = _load_historical_bubble_module("510520e")
        random.seed(1014)
        historical = hist_mod.BubbleSimulation()
        for _ in range(80):
            historical.tick(1 / 60, quiet, settings)
        for _ in range(24):
            historical.tick(1 / 60, hot, settings)
        historical_metrics = _render_lane_metrics(
            historical,
            big_bass_pulse=payload["bubble_big_bass_pulse"],
            small_freq_pulse=payload["bubble_small_freq_pulse"],
            big_contraction_bias=payload["bubble_big_contraction_bias"],
            big_size_clamp=payload["bubble_big_size_clamp"],
        )

        assert current_metrics["big_max_render"] >= historical_metrics["big_max_render"] * 0.97, (
            "Current Bubble still renders the Deep Sea hero lane smaller than the 510520e anchor "
            f"({current_metrics['big_max_render']:.4f} vs {historical_metrics['big_max_render']:.4f})."
        )
        assert current_metrics["big_avg_render"] >= historical_metrics["big_avg_render"] * 0.97, (
            "Current Bubble still renders the average Deep Sea big-bubble lane below the 510520e anchor "
            f"({current_metrics['big_avg_render']:.4f} vs {historical_metrics['big_avg_render']:.4f})."
        )

    def test_live_big_size_edits_increase_big_render_authority(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=45,
            bubble_big_size_max=0.035,
            bubble_small_size_max=0.012,
            bubble_big_bass_pulse=0.8,
            bubble_small_freq_pulse=0.6,
            bubble_big_contraction_bias=0.5,
            bubble_big_size_clamp=3.0,
            bubble_stream_constant_speed=0.15,
            bubble_stream_speed_cap=1.8,
            bubble_stream_reactivity=0.9,
        )
        _warm_up(sim, settings, frames=80)
        hot = _energy(bass=1.55, mid=0.65, high=0.16)

        for _ in range(24):
            sim.tick(1 / 60, hot, settings)
        before = _render_lane_metrics(
            sim,
            big_bass_pulse=settings["bubble_big_bass_pulse"],
            small_freq_pulse=settings["bubble_small_freq_pulse"],
            big_contraction_bias=settings["bubble_big_contraction_bias"],
            big_size_clamp=settings["bubble_big_size_clamp"],
        )

        boosted = copy.deepcopy(settings)
        boosted["bubble_big_size_max"] = 0.045
        boosted["bubble_big_size_clamp"] = 4.8
        boosted["bubble_big_bass_pulse"] = 0.95
        for _ in range(36):
            sim.tick(1 / 60, hot, boosted)
        after = _render_lane_metrics(
            sim,
            big_bass_pulse=boosted["bubble_big_bass_pulse"],
            small_freq_pulse=boosted["bubble_small_freq_pulse"],
            big_contraction_bias=boosted["bubble_big_contraction_bias"],
            big_size_clamp=boosted["bubble_big_size_clamp"],
        )

        assert after["big_max_render"] >= 0.065, (
            "Restored Bubble baseline still cannot keep the hero lane visibly alive after big-size edits."
        )
        assert after["big_avg_render"] >= 0.050, (
            "Restored Bubble baseline still lets the average hero lane sag too low after big-size edits."
        )

    def test_sustained_bass_hot_keeps_small_lane_alive(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=45,
            bubble_big_size_max=0.035,
            bubble_small_size_max=0.012,
            bubble_big_bass_pulse=0.8,
            bubble_small_freq_pulse=0.6,
            bubble_big_contraction_bias=0.5,
            bubble_big_size_clamp=3.0,
            bubble_stream_constant_speed=0.15,
            bubble_stream_speed_cap=1.8,
            bubble_stream_reactivity=0.9,
        )
        _warm_up(sim, settings, frames=80)

        sustained_bass_hot = _energy(bass=1.60, mid=0.15, high=0.03)
        for _ in range(60):
            sim.tick(1 / 60, sustained_bass_hot, settings)
        metrics = _render_lane_metrics(
            sim,
            big_bass_pulse=settings["bubble_big_bass_pulse"],
            small_freq_pulse=settings["bubble_small_freq_pulse"],
            big_contraction_bias=settings["bubble_big_contraction_bias"],
            big_size_clamp=settings["bubble_big_size_clamp"],
        )

        assert metrics["small_max_render"] > 0.020, (
            "Small bubbles still collapse too far during sustained bass-heavy loud passages."
        )
        assert metrics["small_avg_render"] > 0.013, (
            "Small bubbles still look too dormant on sustained loud passages."
        )

    def test_post_initial_refill_does_not_spawn_a_backlog_wave_in_one_tick(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=15,
            bubble_stream_direction="up",
        )
        _warm_up(sim, settings, frames=60)

        # Simulate a post-startup tick where many small bubbles have just
        # transitioned into exit/drain state. The refill path should not dump
        # the whole missing count back in immediately at one entry edge.
        sim._time = 2.0
        active_big = [b for b in sim._bubbles if b.is_big][:6]
        sim._bubbles = active_big

        quiet = _energy(bass=0.10, mid=0.08, high=0.04)
        sim.tick(1 / 60, quiet, settings)

        active_small = [b for b in sim._bubbles if not b.is_big and not b.exiting]
        assert len(active_small) <= 3, (
            f"Post-initial refill spawned {len(active_small)} small bubbles in one tick; "
            "Bubble is still allowed to dump a visible backlog wave at the entry edge."
        )

    def test_post_initial_refill_caps_big_bubble_backlog_too(self):
        sim = BubbleSimulation()
        settings = _default_settings(
            bubble_big_count=6,
            bubble_small_count=15,
            bubble_stream_direction="up",
        )
        _warm_up(sim, settings, frames=60)

        sim._time = 2.0
        active_small = [b for b in sim._bubbles if not b.is_big][:15]
        sim._bubbles = active_small

        quiet = _energy(bass=0.10, mid=0.08, high=0.04)
        sim.tick(1 / 60, quiet, settings)

        active_big = [b for b in sim._bubbles if b.is_big and not b.exiting]
        assert len(active_big) <= 2, (
            f"Post-initial refill spawned {len(active_big)} big bubbles in one tick; "
            "Bubble can still dump a visible big-bubble backlog wave at the entry edge."
        )


class TestBubbleBouncePhysics:
    def _pair(self, *, left_big=False, right_big=False):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        left = BubbleState(x=0.50, y=0.50, radius=0.06, is_big=left_big)
        right = BubbleState(x=0.56, y=0.50, radius=0.06, is_big=right_big)
        return left, right

    def test_full_bounce_applies_impulse_response(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        sim._bubbles = [a, b]

        random.seed(7)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=0.0,
            bounce_big_speed=2.0,
            bounce_small_speed=0.0,
        )

        assert abs(a.impulse_vx) > 1e-5
        assert abs(b.impulse_vx) > 1e-5
        assert a.impulse_vx < 0.0
        assert b.impulse_vx > 0.0

    def test_zero_bounce_uses_soft_separation_without_impulse(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        start_dist = math.hypot(b.x - a.x, b.y - a.y)
        sim._bubbles = [a, b]

        random.seed(3)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=0.0,
            bounce_small_pct=0.0,
            bounce_big_speed=2.0,
            bounce_small_speed=2.0,
        )
        end_dist = math.hypot(b.x - a.x, b.y - a.y)

        assert end_dist > start_dist
        assert a.impulse_vx == 0.0 and a.impulse_vy == 0.0
        assert b.impulse_vx == 0.0 and b.impulse_vy == 0.0

    def test_mixed_pair_uses_big_dominant_bounce_policy(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=False)
        sim._bubbles = [a, b]

        random.seed(11)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=0.0,
            bounce_big_speed=1.5,
            bounce_small_speed=0.0,
        )
        assert abs(a.impulse_vx) > 0.0 or abs(b.impulse_vx) > 0.0

        a2, b2 = self._pair(left_big=True, right_big=False)
        sim._bubbles = [a2, b2]
        random.seed(11)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=0.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=2.0,
        )
        assert a2.impulse_vx == 0.0 and a2.impulse_vy == 0.0
        assert b2.impulse_vx == 0.0 and b2.impulse_vy == 0.0

    def test_impulse_damps_over_time_without_permanent_velocity_drift(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        a.impulse_vx = 0.26
        sim._bubbles = [a, b]

        settings = _default_settings(
            bubble_big_count=0,
            bubble_small_count=0,
            bubble_stream_direction="none",
            bubble_stream_constant_speed=0.0,
            bubble_stream_speed_cap=0.1,
            bubble_stream_reactivity=0.0,
            bubble_drift_amount=0.0,
            bubble_drift_speed=0.0,
            bubble_drift_frequency=0.0,
            bubble_rotation_amount=0.0,
            bubble_bounce_big_pct=0,
            bubble_bounce_small_pct=0,
        )

        sim.tick(1 / 60, _energy(), settings)
        after_one = a.impulse_vx
        sim.tick(1 / 60, _energy(), settings)
        after_two = a.impulse_vx

        assert abs(after_one) < 0.26
        assert abs(after_two) < abs(after_one)
        assert abs(after_two) < 0.26

    def test_dense_overlap_remains_finite_under_high_bounce(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        sim = BubbleSimulation()
        sim._bubbles = [
            BubbleState(
                x=0.50 + (i % 4) * 0.005,
                y=0.50 + (i // 4) * 0.005,
                radius=0.05,
                is_big=(i % 2 == 0),
            )
            for i in range(10)
        ]

        random.seed(19)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=2.0,
            bounce_small_speed=2.0,
        )

        for bubble in sim._bubbles:
            assert math.isfinite(bubble.x)
            assert math.isfinite(bubble.y)
            assert math.isfinite(bubble.impulse_vx)
            assert math.isfinite(bubble.impulse_vy)

        worst_overlap = 0.0
        for i, a in enumerate(sim._bubbles):
            for b in sim._bubbles[i + 1:]:
                dist = math.hypot(b.x - a.x, b.y - a.y)
                overlap = max(0.0, (a.radius + b.radius) - dist)
                worst_overlap = max(worst_overlap, overlap)
        assert worst_overlap < 0.022, (
            f"Dense bounce enforcement left too much overlap ({worst_overlap:.4f}) at 100%/100% settings."
        )

    def test_collision_uses_effective_pulsed_radius_not_base_radius_only(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        sim = BubbleSimulation()
        a = BubbleState(x=0.45, y=0.5, radius=0.04, is_big=True, pulse_energy=1.0)
        b = BubbleState(x=0.57, y=0.5, radius=0.04, is_big=True, pulse_energy=1.0)
        sim._bubbles = [a, b]
        start_dist = math.hypot(b.x - a.x, b.y - a.y)

        random.seed(9)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=0.0,
            bounce_big_speed=1.6,
            bounce_small_speed=0.0,
            big_bass_pulse=1.0,
            small_freq_pulse=0.5,
            big_contraction_bias=1.0,
            big_size_clamp=2.2,
        )
        end_dist = math.hypot(b.x - a.x, b.y - a.y)
        assert end_dist > start_dist, (
            "Pulsed big bubbles did not separate despite visual size inflation; "
            "collision still appears to be using base radius only."
        )

    def test_same_bounce_only_allows_mixed_pairs_to_pass_through(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=False)
        sim._bubbles = [a, b]
        start_a = (a.x, a.y)
        start_b = (b.x, b.y)

        random.seed(21)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            bounce_same_only=True,
        )

        assert (a.x, a.y) == start_a
        assert (b.x, b.y) == start_b
        assert a.impulse_vx == 0.0 and a.impulse_vy == 0.0
        assert b.impulse_vx == 0.0 and b.impulse_vy == 0.0

    def test_same_bounce_only_keeps_same_class_collisions_active(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        sim._bubbles = [a, b]

        random.seed(22)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            bounce_same_only=True,
        )

        assert abs(a.impulse_vx) > 0.0 or abs(b.impulse_vx) > 0.0

    def test_collision_pop_mode_all_pops_both_bubbles(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        sim._bubbles = [a, b]

        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            collision_pop_mode="all",
        )

        assert a.popping is True
        assert b.popping is True
        assert a.pop_timer == pytest.approx(0.0)
        assert b.pop_timer == pytest.approx(0.0)

    def test_collision_pop_mode_one_pops_single_bubble(self):
        sim = BubbleSimulation()
        a, b = self._pair(left_big=True, right_big=True)
        sim._bubbles = [a, b]

        random.seed(123)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            collision_pop_mode="one",
        )

        popped_count = int(a.popping) + int(b.popping)
        assert popped_count == 1

    def test_collision_pop_mode_one_mixed_pair_big_always_wins(self):
        sim = BubbleSimulation()
        big_b, small_b = self._pair(left_big=True, right_big=False)
        sim._bubbles = [big_b, small_b]

        random.seed(124)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            bounce_same_only=False,
            collision_pop_mode="one",
        )

        assert big_b.popping is False
        assert small_b.popping is True

    def test_collision_pop_mode_respects_same_only_for_mixed_pairs(self):
        sim = BubbleSimulation()
        big_b, small_b = self._pair(left_big=True, right_big=False)
        start_big = (big_b.x, big_b.y)
        start_small = (small_b.x, small_b.y)
        sim._bubbles = [big_b, small_b]

        random.seed(125)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.5,
            bounce_small_speed=1.5,
            bounce_same_only=True,
            collision_pop_mode="all",
        )

        assert big_b.popping is False
        assert small_b.popping is False
        assert (big_b.x, big_b.y) == start_big
        assert (small_b.x, small_b.y) == start_small

    def test_pair_cooldown_prevents_immediate_rebounce(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        sim = BubbleSimulation()
        a = BubbleState(x=0.48, y=0.5, radius=0.05, is_big=True)
        b = BubbleState(x=0.54, y=0.5, radius=0.05, is_big=True)
        sim._bubbles = [a, b]

        random.seed(77)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.2,
            bounce_small_speed=1.2,
        )
        first = (a.impulse_vx, a.impulse_vy, b.impulse_vx, b.impulse_vy)
        assert any(abs(v) > 0.0 for v in first)

        # Force immediate re-overlap and attempt a second response in the same
        # simulation time instant; pair cooldown should block re-bounce impulse.
        a.x, b.x = 0.49, 0.53
        random.seed(78)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.2,
            bounce_small_speed=1.2,
        )
        second = (a.impulse_vx, a.impulse_vy, b.impulse_vx, b.impulse_vy)
        assert second == first

    def test_post_bounce_glide_temporarily_dampens_stream_drift(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        base_settings = _default_settings(
            bubble_big_count=0,
            bubble_small_count=0,
            bubble_stream_direction="right",
            bubble_stream_constant_speed=0.8,
            bubble_stream_speed_cap=0.8,
            bubble_stream_reactivity=1.0,
            bubble_drift_direction="swish_horizontal",
            bubble_drift_amount=1.0,
            bubble_drift_speed=0.8,
            bubble_drift_frequency=0.5,
        )

        ctrl = BubbleSimulation()
        glided = BubbleSimulation()
        ctrl_b = BubbleState(x=0.50, y=0.50, radius=0.015, is_big=False, phase=0.0, drift_bias=0.7)
        glide_b = BubbleState(x=0.50, y=0.50, radius=0.015, is_big=False, phase=0.0, drift_bias=0.7, bounce_glide=0.18)
        ctrl._bubbles = [ctrl_b]
        glided._bubbles = [glide_b]

        e = _energy(bass=0.3, mid=0.2, high=0.1)
        ctrl.tick(1 / 60, e, base_settings)
        glided.tick(1 / 60, e, base_settings)

        ctrl_dx = abs(ctrl_b.x - 0.50)
        glide_dx = abs(glide_b.x - 0.50)
        assert glide_dx < ctrl_dx

    def test_entry_overlap_biases_correction_offscreen_without_impulse(self):
        from widgets.spotify_visualizer.bubble_simulation import BubbleState

        sim = BubbleSimulation()
        # a is visible, b is just outside left edge; they overlap.
        a = BubbleState(x=0.01, y=0.50, radius=0.05, is_big=True)
        b = BubbleState(x=-0.03, y=0.50, radius=0.05, is_big=True)
        sim._bubbles = [a, b]

        start_a_x = a.x
        start_b_x = b.x
        random.seed(79)
        sim._apply_bubble_collision_response(
            1 / 60,
            bounce_big_pct=100.0,
            bounce_small_pct=100.0,
            bounce_big_speed=1.2,
            bounce_small_speed=1.2,
        )

        # Entry contacts should resolve mostly by moving the offscreen bubble.
        moved_a = abs(a.x - start_a_x)
        moved_b = abs(b.x - start_b_x)
        assert moved_b > moved_a * 2.5
        # No bounce impulse while pair is not fully in view.
        assert a.impulse_vx == 0.0 and a.impulse_vy == 0.0
        assert b.impulse_vx == 0.0 and b.impulse_vy == 0.0
