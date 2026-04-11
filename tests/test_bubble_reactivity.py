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
import random
from types import SimpleNamespace

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
        assert pulse > 0.052, (
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

        assert max_big < 0.96, (
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
