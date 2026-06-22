"""CPU-side bubble particle simulation for the Bubble visualizer mode.

Manages a pool of bubbles with spawning, movement, drift, wobble, pulse,
and lifecycle (surface-reach vs pop/fade). The simulation runs on the UI
thread inside ``_on_tick()`` — at ≤110 bubbles the update is <0.1ms.

The public API is:
    sim = BubbleSimulation()
    sim.tick(dt, energy_bands, settings_dict)
    pos_data, extra_data = sim.snapshot()   # lists ready for uniform upload
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.logging.logger import (
    get_logger,
    is_verbose_logging,
    is_viz_diagnostics_enabled,
)
from widgets.spotify_visualizer.signal_contract import burst_authority, soft_ceiling

_SWIRL_DIRECTIONS = {"swirl_cw", "swirl_ccw"}

logger = get_logger(__name__)

MAX_BUBBLES = 110


TRAIL_STEPS = 3  # uniform layout still reserves 3 vec3 slots per bubble
# Smear tail behaviour: trail_tail slowly chases each bubble, forming a streak
TRAIL_SMEAR_FOLLOW_RATE = 0.65   # how quickly tails chase heads (per second) — lower = longer streaks
TRAIL_SMEAR_FOLLOW_MAX = 0.18   # clamp per-tick lerp to keep visible lag
TRAIL_SMEAR_DECAY_PER_SEC = 0.9  # how fast strength fades when slowing
TRAIL_SMEAR_STRENGTH_FROM_DISTANCE = 35.0  # convert offset distance → brightness (higher = brighter sooner)
TRAIL_SMEAR_MAX_LENGTH = 0.55   # cap streak length to avoid card wrap
IMPULSE_DAMPING_PER_SEC = 10.5
MAX_IMPULSE_SPEED = 0.22


@dataclass
class BubbleState:
    x: float = 0.5
    y: float = 0.5
    radius: float = 0.02
    is_big: bool = False
    reaches_surface: bool = True
    phase: float = 0.0
    age: float = 0.0
    max_age: float = 999.0
    alpha: float = 1.0
    drift_bias: float = 0.0
    rotation: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    impulse_vx: float = 0.0
    impulse_vy: float = 0.0
    speed_mult: float = 1.0
    popping: bool = False
    pop_timer: float = 0.0
    pulse_energy: float = 0.0  # smoothed energy for size pulse (attack fast, decay slow)
    spec_size_mut: float = 1.0   # per-bubble specular size mutation (0.7–1.4)
    spec_ox: float = 0.0         # per-bubble specular offset X mutation (-0.08..0.08)
    spec_oy: float = 0.0         # per-bubble specular offset Y mutation (-0.08..0.08)
    trail_tail_x: float = 0.5
    trail_tail_y: float = 0.5
    trail_strength: float = 0.0
    trail_ready: bool = False
    promoted: bool = False      # temporarily promoted small→big during beat bursts
    promote_timer: float = 0.0   # remaining promotion duration (seconds)
    exiting: bool = False       # bubble head left the card; trail draining out
    exit_timer: float = 0.0     # time since exit began (safety destroy after grace)
    bounce_glide: float = 0.0   # short post-collision window where drift/stream are damped
    display_radius: float = 0.0  # display-only hero radius smoothing state
    size_gate_energy: float = 0.0  # unsmoothed size gate used by hero render seam


# Direction vectors for stream directions
_DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "none": (0.0, 0.0),
    "up": (0.0, 1.0),
    "down": (0.0, -1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "top_left": (-0.707, 0.707),
    "top_right": (0.707, 0.707),
    "bottom_left": (-0.707, -0.707),
    "bottom_right": (0.707, -0.707),
}

_DIAGONAL_STREAM_VECTORS: Tuple[Tuple[float, float], ...] = (
    ( 0.707,  0.707),  # up-right
    (-0.707,  0.707),  # up-left
    ( 0.707, -0.707),  # down-right
    (-0.707, -0.707),  # down-left
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _shape_authored_bubble_control(
    value: float,
    *,
    low_power: float,
    high_power: float,
) -> float:
    """Give low authored values more subtlety and high values more authority."""
    x = _clamp01(value)
    if x <= 0.5:
        return 0.5 * ((x / 0.5) ** low_power)
    return 0.5 + 0.5 * (((x - 0.5) / 0.5) ** high_power)


def _random_direction() -> Tuple[float, float]:
    angle = random.uniform(0.0, math.tau)
    return (math.cos(angle), math.sin(angle))


def _get_stream_vector(direction: str) -> Tuple[float, float]:
    if direction == "random":
        return _random_direction()
    if direction == "diagonal":
        # Legacy compatibility: old single "diagonal" mode becomes random
        # diagonal direction.
        return random.choice(_DIAGONAL_STREAM_VECTORS)
    return _DIRECTION_VECTORS.get(direction, (0.0, 1.0))


def _spawn_position(direction: str, is_big: bool) -> Tuple[float, float]:
    """Spawn at the opposite edge of the stream direction."""
    margin = 0.05 if is_big else 0.02
    if direction == "up":
        return (random.uniform(margin, 1.0 - margin), 1.0 + margin)
    elif direction == "down":
        return (random.uniform(margin, 1.0 - margin), -margin)
    elif direction == "left":
        return (1.0 + margin, random.uniform(margin, 1.0 - margin))
    elif direction == "right":
        return (-margin, random.uniform(margin, 1.0 - margin))
    elif direction in {"top_left", "top_right", "bottom_left", "bottom_right", "diagonal"}:
        dx, dy = _get_stream_vector(direction)
        # Spawn on the edge opposite to the travel direction
        if random.random() < 0.5:
            # Spawn on the horizontal edge opposite to dy
            edge_y = (1.0 + margin) if dy > 0 else -margin
            return (random.uniform(margin, 1.0 - margin), edge_y)
        else:
            # Spawn on the vertical edge opposite to dx
            edge_x = (-margin) if dx > 0 else (1.0 + margin)
            return (edge_x, random.uniform(margin, 1.0 - margin))
    elif direction == "none":
        return (random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))
    else:  # random
        return (random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))


def _stream_mode_uses_in_card_initial_fill(stream_dir: str, drift_dir: str) -> bool:
    """Return True for the accepted cold-start contract.

    Bubble looked healthier when every mode booted into a partly established
    field instead of exposing a visible entry-lane build-up. We keep the newer
    runtime refill/overdrive work, but the startup shape returns to an in-card
    bootstrap across stream families rather than axis-specific birth queues.
    """
    return True


def _directional_entry_position(
    direction: str,
    is_big: bool,
    *,
    startup: bool = False,
) -> Tuple[float, float]:
    """Spawn off-card with randomized depth so directional streams avoid columns.

    Directional startup should still come from the real entry side, but if every
    bubble is born on the same side plane and then travels at nearly the same
    speed, the simulation naturally quantizes into visible columns. Varying the
    off-card depth preserves side-entry semantics while helping the stream read
    as a flowing field rather than synchronized lanes.
    """
    x, y = _spawn_position(direction, is_big)
    if direction in {"none", "random"}:
        return (x, y)

    dx, dy = _get_stream_vector(direction)
    if startup:
        extra_depth = random.uniform(0.02, 0.10)
    else:
        extra_depth = random.uniform(0.01, 0.06)
    return (x + dx * extra_depth, y - dy * extra_depth)


def _bubble_behaves_big(bubble: BubbleState) -> bool:
    return bool(bubble.is_big or bubble.promoted)


class BubbleSimulation:
    """Lightweight bubble particle system."""

    def __init__(self) -> None:
        self._bubbles: List[BubbleState] = []
        self._time: float = 0.0
        self._last_tick_dt: float = 0.016
        self._big_size_max: float = 0.038
        self._small_size_max: float = 0.018
        self._diag_tick_count: int = 0
        self._smoothed_speed_energy: float = 0.0  # smoothed bass for travel speed reactivity
        self._sustained_loud_energy: float = 0.0  # Bubble loudness proxy; may exceed 1.0 for supra-unit hot windows
        self._render_body_energy: float = 0.0  # clean body proxy for visible hero sizing
        self._hot_crest_energy: float = 0.0
        self._bass_running_avg: float = 0.0   # slow-tracking bass average for delta pulse
        self._midhi_running_avg: float = 0.0  # slow-tracking mid+high average for delta pulse
        self._overdrive_active: bool = False
        self._overdrive_hold_timer: float = 0.0
        self._overdrive_consec_frames: int = 0
        self._overdrive_last_log_state: Optional[str] = None
        self._overdrive_last_log_ts: float = 0.0
        self._last_drift_diag_log_ts: float = 0.0
        self._burst_active: bool = False
        self._burst_cooldown: float = 0.0
        self._prev_bass: float = 0.0  # previous frame bass for slope detection
        self._stream_burst_envelope: float = 0.0
        self._pair_bounce_cooldowns: Dict[Tuple[int, int], float] = {}
        self._last_big_lane_diag: Dict[str, float] = {}
        self._last_big_render_diag: Dict[str, float] = {}
        self._last_perf_diag: Dict[str, float] = {}
        self._group_drift_dx: float = 0.0
        self._group_drift_dy: float = 0.0
        self._group_drift_from_dx: float = 0.0
        self._group_drift_from_dy: float = 0.0
        self._group_drift_target_dx: float = 0.0
        self._group_drift_target_dy: float = 0.0
        self._group_drift_remaining: float = 0.0
        self._group_drift_turn_elapsed: float = 0.0
        self._group_drift_turn_duration: float = 0.0
        self._group_drift_arc_x: float = 0.0
        self._group_drift_arc_y: float = 0.0
        self._group_drift_arc_sign: float = 1.0

    def reset(self) -> None:
        """Clear all accumulated state for a clean cold-start on mode re-entry."""
        self._bubbles.clear()
        self._time = 0.0
        self._last_tick_dt = 0.016
        self._diag_tick_count = 0
        self._smoothed_speed_energy = 0.0
        self._sustained_loud_energy = 0.0
        self._render_body_energy = 0.0
        self._hot_crest_energy = 0.0
        self._bass_running_avg = 0.0
        self._midhi_running_avg = 0.0
        self._overdrive_active = False
        self._overdrive_hold_timer = 0.0
        self._overdrive_consec_frames = 0
        self._overdrive_last_log_state = None
        self._overdrive_last_log_ts = 0.0
        self._last_drift_diag_log_ts = 0.0
        self._burst_active = False
        self._burst_cooldown = 0.0
        self._prev_bass = 0.0
        self._stream_burst_envelope = 0.0
        self._pair_bounce_cooldowns.clear()
        self._last_big_lane_diag = {}
        self._last_big_render_diag = {}
        self._last_perf_diag = {}
        self._group_drift_dx = 0.0
        self._group_drift_dy = 0.0
        self._group_drift_from_dx = 0.0
        self._group_drift_from_dy = 0.0
        self._group_drift_target_dx = 0.0
        self._group_drift_target_dy = 0.0
        self._group_drift_remaining = 0.0
        self._group_drift_turn_elapsed = 0.0
        self._group_drift_turn_duration = 0.0
        self._group_drift_arc_x = 0.0
        self._group_drift_arc_y = 0.0
        self._group_drift_arc_sign = 1.0

    @property
    def count(self) -> int:
        return len(self._bubbles)

    def get_big_lane_diagnostics(self) -> Dict[str, float]:
        """Compatibility diagnostics for the stricter Bubble oracle."""
        return dict(self._last_big_lane_diag)

    def get_big_render_diagnostics(self) -> Dict[str, float]:
        """Compatibility diagnostics for the stricter Bubble oracle."""
        return dict(self._last_big_render_diag)

    def get_perf_diagnostics(self) -> Dict[str, float]:
        """Return the latest Bubble-owned perf breakdown for audit logging."""
        return dict(self._last_perf_diag)

    def tick(self, dt: float, energy_bands: Optional[object], settings: Dict) -> None:
        """Advance simulation by *dt* seconds."""
        if dt <= 0.0 or dt > 1.0:
            return
        self._last_tick_dt = dt
        tick_start = time.perf_counter()

        self._time += dt

        # Read settings
        big_target = int(settings.get("bubble_big_count", 8))
        small_target = int(settings.get("bubble_small_count", 25))
        surface_reach = float(settings.get("bubble_surface_reach", 0.6))
        stream_dir = str(settings.get("bubble_stream_direction", "up"))
        stream_const = float(settings.get(
            "bubble_stream_constant_speed",
            settings.get("bubble_stream_speed", 0.5),
        ))
        stream_cap = float(settings.get(
            "bubble_stream_speed_cap",
            settings.get("bubble_stream_speed", 2.0),
        ))
        stream_reactivity = float(settings.get("bubble_stream_reactivity", 0.5))
        rotation_amount = float(settings.get("bubble_rotation_amount", 0.5))
        drift_amount_authored = float(settings.get("bubble_drift_amount", 0.5))
        group_drift = bool(settings.get("bubble_group_drift", False))
        drift_speed_authored = float(settings.get("bubble_drift_speed", 0.5))
        drift_freq_authored = float(settings.get("bubble_drift_frequency", 0.5))
        drift_dir = str(settings.get("bubble_drift_direction", "random"))
        drift_amount = _shape_authored_bubble_control(
            drift_amount_authored,
            low_power=1.95,
            high_power=0.78,
        )
        drift_speed = _shape_authored_bubble_control(
            drift_speed_authored,
            low_power=2.05,
            high_power=0.76,
        )
        drift_freq = _shape_authored_bubble_control(
            drift_freq_authored,
            low_power=3.20,
            high_power=0.70,
        )
        big_bass_pulse = float(settings.get("bubble_big_bass_pulse", 0.5))
        small_freq_pulse = float(settings.get("bubble_small_freq_pulse", 0.5))
        big_contraction_bias = float(settings.get("bubble_big_contraction_bias", 1.0))
        big_size_clamp = float(settings.get("bubble_big_size_clamp", 4.0))
        bounce_big_pct = max(0.0, min(100.0, float(settings.get("bubble_bounce_big_pct", 70.0))))
        bounce_small_pct = max(0.0, min(100.0, float(settings.get("bubble_bounce_small_pct", 30.0))))
        bounce_big_speed = max(0.0, min(2.0, float(settings.get("bubble_bounce_big_speed", 0.8))))
        bounce_small_speed = max(0.0, min(2.0, float(settings.get("bubble_bounce_small_speed", 0.5))))
        bounce_same_only = bool(settings.get("bubble_bounce_same_only", False))
        collision_pop_mode = str(settings.get("bubble_collision_pop_mode", "off")).strip().lower()
        if collision_pop_mode not in {"off", "one", "all"}:
            collision_pop_mode = "off"
        self._big_size_max = float(settings.get("bubble_big_size_max", 0.038))
        self._small_size_max = float(settings.get("bubble_small_size_max", 0.018))
        trail_strength = float(settings.get("bubble_trail_strength", 0.0))
        # big_bass_pulse / small_freq_pulse are read in snapshot(), not tick()

        trail_enabled = trail_strength > 0.001

        # Energy — accept both object (EnergyBands) and dict snapshots
        if energy_bands is None:
            bass = mid = high = overall = 0.0
        elif isinstance(energy_bands, dict):
            bass = max(0.0, float(energy_bands.get('bass', 0.0) or 0.0))
            mid = max(0.0, float(energy_bands.get('mid', 0.0) or 0.0))
            high = max(0.0, float(energy_bands.get('high', 0.0) or 0.0))
            overall = max(0.0, float(energy_bands.get('overall', 0.0) or 0.0))
            pulse_bass = max(0.0, float(energy_bands.get('pulse_bass', bass) or 0.0))
            pulse_mid = max(0.0, float(energy_bands.get('pulse_mid', mid) or 0.0))
            pulse_high = max(0.0, float(energy_bands.get('pulse_high', high) or 0.0))
            pulse_overall = max(0.0, float(energy_bands.get('pulse_overall', overall) or 0.0))
        else:
            bass = max(0.0, float(getattr(energy_bands, 'bass', 0.0) or 0.0))
            mid = max(0.0, float(getattr(energy_bands, 'mid', 0.0) or 0.0))
            high = max(0.0, float(getattr(energy_bands, 'high', 0.0) or 0.0))
            overall = max(0.0, float(getattr(energy_bands, 'overall', 0.0) or 0.0))
            pulse_bass = max(0.0, float(getattr(energy_bands, 'pulse_bass', bass) or 0.0))
            pulse_mid = max(0.0, float(getattr(energy_bands, 'pulse_mid', mid) or 0.0))
            pulse_high = max(0.0, float(getattr(energy_bands, 'pulse_high', high) or 0.0))
            pulse_overall = max(0.0, float(getattr(energy_bands, 'pulse_overall', overall) or 0.0))

        # Diagnostic: only log during verbose runs to avoid spamming main logs.
        self._diag_tick_count += 1
        if is_verbose_logging():
            should_log = self._diag_tick_count <= 10 or self._diag_tick_count % 60 == 0
            if should_log:
                max_pe = max((b.pulse_energy for b in self._bubbles), default=0.0)
                logger.debug(
                    "[BUBBLE_SIM] tick=%d dt=%.3f bass=%.3f mid=%.3f overall=%.3f "
                    "bubbles=%d max_pe=%.3f spd_e=%.3f burst=%.3f base=%.2f cap=%.2f react=%.2f",
                    self._diag_tick_count, dt, bass, mid, overall,
                    len(self._bubbles), max_pe, self._smoothed_speed_energy,
                    self._stream_burst_envelope,
                    stream_const, stream_cap, stream_reactivity,
                )

        big_lane_diag = {
            "big_count": 0.0,
            "active_big_count": 0.0,
            "dormant_big_count": 0.0,
            "max_big_raw_src": 0.0,
            "max_big_gated_energy": 0.0,
            "max_big_pulse_after": 0.0,
            "sustained_loud_energy": max(0.0, max(bass, overall)),
            "speed_energy": 0.0,
            "drift_drive": 0.0,
            "drift_phase_boost": 1.0,
            "drift_amplitude_boost": 1.0,
            "group_drift_configured": 0.0,
            "group_drift_active": 0.0,
            "small_vocal_body": 0.0,
            "small_hot_body_authority": 0.0,
        }

        # --- Beat detection (§2.4 scheduler-first, delta fallback) ---
        # Event micro-scheduler provides consume-once kick events so each
        # detected beat drives exactly one promotion batch.  Falls back to
        # the legacy delta heuristic only when no scheduler is available
        # (engine not yet started / startup race).
        _scheduler = settings.get("_event_scheduler")
        beat_detected = False
        beat_strength = 0.0
        if _scheduler is not None:
            _kick_evt = _scheduler.consume_next("kick", max_age_s=0.3)
            if _kick_evt is not None:
                beat_detected = True
                beat_strength = _kick_evt.strength
        else:
            # Legacy fallback: simple delta threshold
            bass_delta = max(0.0, pulse_bass - self._bass_running_avg)
            beat_threshold = 0.05
            beat_detected = bass_delta > beat_threshold and pulse_bass > self._prev_bass + 0.025
            beat_strength = min(1.0, bass_delta * 5.0) if beat_detected else 0.0
        self._prev_bass = pulse_bass

        # Update running averages for delta-based pulse detection.
        avg_attack = min(1.0, dt * 1.8)   # slower rise (~0.55s) so real beats create bigger deltas
        avg_release = min(1.0, dt * 4.0)  # moderate fall (~0.25s)
        if pulse_bass > self._bass_running_avg:
            self._bass_running_avg += (pulse_bass - self._bass_running_avg) * avg_attack
        else:
            self._bass_running_avg += (pulse_bass - self._bass_running_avg) * avg_release
        midhi_prev_avg = self._midhi_running_avg
        midhi = pulse_mid * 0.6 + pulse_high * 0.4
        if midhi > self._midhi_running_avg:
            self._midhi_running_avg += (midhi - self._midhi_running_avg) * avg_attack
        else:
            self._midhi_running_avg += (midhi - self._midhi_running_avg) * avg_release
        self._sustained_loud_energy = max(0.0, max(pulse_bass, pulse_overall))
        self._render_body_energy = max(
            self._sustained_loud_energy,
            pulse_bass + pulse_mid * 0.12 + pulse_high * 0.06,
        )

        # --- Small→big promotion on every beat ---
        if beat_detected:
            self._burst_cooldown = max(self._burst_cooldown, 0.60)
            small_pool = [b for b in self._bubbles if not b.is_big and not b.promoted and not b.popping and not b.exiting]
            big_pool = [b for b in self._bubbles if b.is_big and not b.popping and not b.exiting]
            big_hotness = max((b.pulse_energy for b in big_pool), default=0.0)
            swirl_like = drift_dir in _SWIRL_DIRECTIONS

            # Promotions are still useful as an "extra voice" when the main
            # big-bubble lane is already busy, but ordinary stream modes should
            # stay conservative so they do not counterfeit a second big-bubble
            # population across the whole card.
            if swirl_like:
                if beat_strength > 0.6:
                    promote_frac = 0.18
                elif beat_strength > 0.3:
                    promote_frac = 0.12
                else:
                    promote_frac = 0.08
                promote_count = min(2, max(1, int(len(small_pool) * promote_frac)))
                promote_duration = 0.45 + 0.12 * beat_strength
            else:
                if big_hotness < 0.45:
                    promote_count = 0
                else:
                    promote_count = 1
                promote_duration = 0.24 + 0.08 * beat_strength
            if promote_count > 0:
                small_pool.sort(key=lambda bb: bb.radius, reverse=True)
                for bb in small_pool[:promote_count]:
                    bb.promoted = True
                    bb.promote_timer = promote_duration
        # Tick down promotion timers
        for b in self._bubbles:
            if b.promoted:
                b.promote_timer = max(0.0, b.promote_timer - dt)
                if b.promote_timer <= 0.0:
                    b.promoted = False

        # Travel speed uses SMOOTHED mid/high so it flows with the melody.
        # Raw mid/high would jerk on every transient.
        smooth_mid = _clamp01(energy_bands.get('smooth_mid', mid)) if isinstance(energy_bands, dict) else mid
        smooth_high = _clamp01(energy_bands.get('smooth_high', high)) if isinstance(energy_bands, dict) else high
        crest = _clamp01(energy_bands.get('crest', 0.0)) if isinstance(energy_bands, dict) else 0.0
        if crest > self._hot_crest_energy:
            self._hot_crest_energy += (crest - self._hot_crest_energy) * min(1.0, dt * 18.0)
        else:
            self._hot_crest_energy += (crest - self._hot_crest_energy) * min(1.0, dt * 11.0)

        # Perceptual curve: keep quiet passages visibly mobile while still
        # reserving extra headroom for loud vocal passages.
        vocal_raw = smooth_mid * 0.65 + smooth_high * 0.35
        vocal_speed = min(1.0, max(0.0, vocal_raw)) ** 1.1
        # Bubble should not go motion-dead just because a hot section is
        # bass-dominant and the vocal/mid lane thins out.
        bass_dominant_speed = soft_ceiling(
            max(0.0, bass - 0.92),
            knee=0.0,
            ceiling=0.52,
            max_input=1.10,
            curve=1.0,
        )
        bass_dominant_speed *= soft_ceiling(
            max(0.0, overall - 0.42),
            knee=0.0,
            ceiling=1.0,
            max_input=0.52,
            curve=1.0,
        )
        speed_vocal_gap = 1.0 - soft_ceiling(
            max(0.0, vocal_raw - 0.24),
            knee=0.0,
            ceiling=0.82,
            max_input=0.34,
            curve=1.0,
        )
        speed_vocal_gap = speed_vocal_gap ** 1.35
        bass_dominant_speed *= speed_vocal_gap
        vocal_speed = max(vocal_speed, bass_dominant_speed * 0.74)
        vocal_delta = max(0.0, vocal_raw - midhi_prev_avg)
        vocal_burst_target = min(0.85, vocal_delta * 1.1)
        snare_evt = None
        vocal_evt = None
        if _scheduler is not None:
            try:
                vocal_evt = _scheduler.consume_next("vocal_swell", max_age_s=0.24)
            except Exception:
                vocal_evt = None
            try:
                snare_evt = _scheduler.consume_next("snare", max_age_s=0.18)
            except Exception:
                snare_evt = None
            vocal_burst_target = max(
                vocal_burst_target,
                float(getattr(vocal_evt, "strength", 0.0) or 0.0) * 0.55,
                float(getattr(snare_evt, "strength", 0.0) or 0.0) * 0.10,
            )

        # Smoother: extremely fast attack/decay so travel speed mirrors music timing.
        if vocal_speed > self._smoothed_speed_energy:
            self._smoothed_speed_energy += (vocal_speed - self._smoothed_speed_energy) * min(1.0, dt * 6.0)
        else:
            self._smoothed_speed_energy += (vocal_speed - self._smoothed_speed_energy) * min(1.0, dt * 9.0)
        if vocal_burst_target > self._stream_burst_envelope:
            self._stream_burst_envelope += (
                vocal_burst_target - self._stream_burst_envelope
            ) * min(1.0, dt * 4.0)
        else:
            self._stream_burst_envelope += (
                vocal_burst_target - self._stream_burst_envelope
            ) * min(1.0, dt * 7.0)

        sustained_speed = soft_ceiling(
            self._smoothed_speed_energy,
            knee=0.28,
            ceiling=0.82,
            max_input=1.0,
            curve=1.28,
        )
        burst_speed = burst_authority(
            envelope=self._stream_burst_envelope,
            delta=vocal_delta,
            event=float(getattr(snare_evt, "strength", 0.0) or 0.0) if _scheduler is not None else 0.0,
            envelope_weight=0.70,
            delta_weight=1.05,
            event_weight=0.16,
        )
        speed_energy = min(
            1.0,
            max(
                0.0,
                sustained_speed * 0.94 + burst_speed * 0.28,
            ),
        )
        bass_lane_speed = soft_ceiling(
            max(0.0, max(bass, overall) - 0.82),
            knee=0.0,
            ceiling=0.42,
            max_input=1.10,
            curve=1.0,
        )
        bass_lane_speed *= speed_vocal_gap
        speed_energy = max(speed_energy, bass_lane_speed * 1.18)
        big_lane_diag["speed_energy"] = speed_energy
        bass_drift_gate = soft_ceiling(
            max(0.0, bass - 0.30),
            knee=0.0,
            ceiling=1.0,
            max_input=0.74,
            curve=1.0,
        )
        base_drift_drive = soft_ceiling(
            max(0.0, self._sustained_loud_energy - 0.48),
            knee=0.0,
            ceiling=0.10,
            max_input=0.34,
            curve=1.0,
        )
        body_drift_bonus = soft_ceiling(
            max(0.0, self._render_body_energy - 0.54),
            knee=0.0,
            ceiling=0.82,
            max_input=0.58,
            curve=1.0,
        )
        loud_drift_drive = min(
            1.0,
            base_drift_drive + body_drift_bonus * (0.44 + bass_drift_gate * 0.70),
        )
        big_lane_diag["drift_drive"] = loud_drift_drive
        big_lane_diag["drift_amount_authored"] = drift_amount_authored
        big_lane_diag["drift_amount_effective"] = drift_amount
        big_lane_diag["drift_speed_authored"] = drift_speed_authored
        big_lane_diag["drift_speed_effective"] = drift_speed
        big_lane_diag["drift_frequency_authored"] = drift_freq_authored
        big_lane_diag["drift_frequency_effective"] = drift_freq
        drift_phase_boost = 1.0 + loud_drift_drive * (0.44 + drift_speed * 0.78)
        drift_amplitude_boost = 1.0 + loud_drift_drive * (0.90 + drift_amount * 1.20)
        big_lane_diag["drift_phase_boost"] = drift_phase_boost
        big_lane_diag["drift_amplitude_boost"] = drift_amplitude_boost
        group_drift_active = group_drift and drift_dir not in _SWIRL_DIRECTIONS and drift_dir != "none"
        big_lane_diag["group_drift_configured"] = 1.0 if group_drift else 0.0
        big_lane_diag["group_drift_active"] = 1.0 if group_drift_active else 0.0
        if is_viz_diagnostics_enabled():
            now = time.time()
            if (
                self._diag_tick_count <= 6
                or (
                    loud_drift_drive >= 0.02
                    and (now - self._last_drift_diag_log_ts) >= 1.0
                )
            ):
                logger.info(
                    "[SPOTIFY_VIS][BUBBLE][DRIFT] bass=%.3f overall=%.3f speed=%.3f drive=%.3f phase=%.3f amp=%.3f dir=%s group_cfg=%s group_active=%s authored(amount=%.3f speed=%.3f freq=%.3f) effective(amount=%.3f speed=%.3f freq=%.3f)",
                    bass,
                    overall,
                    speed_energy,
                    loud_drift_drive,
                    drift_phase_boost,
                    drift_amplitude_boost,
                    drift_dir,
                    group_drift,
                    group_drift_active,
                    drift_amount_authored,
                    drift_speed_authored,
                    drift_freq_authored,
                    drift_amount,
                    drift_speed,
                    drift_freq,
                )
                self._last_drift_diag_log_ts = now
        cap = max(0.1, stream_cap)
        baseline = max(0.05, min(cap, stream_const))
        reactivity_cap = 2.0
        reactivity_raw = max(0.0, min(reactivity_cap, stream_reactivity))
        overdrive_margin = max(0.0, reactivity_raw - 1.0)
        overdrive_norm = overdrive_margin / (reactivity_cap - 1.0) if reactivity_cap > 1.0 else 0.0
        reactivity = min(1.0, reactivity_raw)

        # --- Simplified speed mapping ---
        # Direct power-curve from energy to speed factor.
        # Reactivity controls the exponent: high reactivity → linear (every
        # dB of energy maps to speed), low reactivity → steep curve (only
        # loud passages push speed up significantly).
        if speed_energy <= 0.0 or reactivity <= 0.0:
            energy_factor = 0.0
        else:
            curve_exp = 1.75 - reactivity * 1.15  # 1.75 at react=0 → 0.60 at react=1.0
            curved = speed_energy ** max(0.35, curve_exp)
            linear_floor = speed_energy * (0.35 + 0.30 * reactivity)
            burst_floor = burst_speed * (0.16 + 0.12 * reactivity)
            energy_factor = min(1.0, max(curved, linear_floor, burst_floor))

        # Blend: at zero reactivity we sit at baseline; at full reactivity
        # the energy factor drives the full baseline→cap range.
        effective_speed = baseline + (cap - baseline) * energy_factor * reactivity

        # --- Overdrive band (reactivity slider 101-200%) ---
        # Overdrive is a true emergency lane for "everything is already pinned",
        # not a normal accompaniment to everyday hot passages.
        overdrive_threshold_gate = 0.72
        overdrive_gate_signal = burst_authority(
            envelope=self._stream_burst_envelope,
            delta=vocal_delta,
            event=float(getattr(snare_evt, "strength", 0.0) or 0.0) if _scheduler is not None else 0.0,
            envelope_weight=0.55,
            delta_weight=0.95,
            event_weight=0.18,
        )
        if overdrive_margin <= 0.0:
            if self._overdrive_active:
                self._log_overdrive_state("release", reactivity_raw, energy_factor)
            self._overdrive_active = False
            self._overdrive_hold_timer = 0.0
            self._overdrive_consec_frames = 0
        else:
            if overdrive_gate_signal >= overdrive_threshold_gate:
                self._overdrive_consec_frames += 1
            else:
                if not self._overdrive_active:
                    self._overdrive_consec_frames = 0
            if (not self._overdrive_active) and self._overdrive_consec_frames >= 5:
                self._overdrive_active = True
                self._overdrive_hold_timer = 0.05
                self._log_overdrive_state("enter", reactivity_raw, overdrive_gate_signal)

            if self._overdrive_active:
                if overdrive_gate_signal >= overdrive_threshold_gate:
                    self._overdrive_hold_timer = 0.05
                else:
                    self._overdrive_hold_timer = max(0.0, self._overdrive_hold_timer - dt)
                    if self._overdrive_hold_timer <= 0.0:
                        self._overdrive_active = False
                        self._overdrive_consec_frames = 0
                        self._log_overdrive_state("release", reactivity_raw, overdrive_gate_signal)

        self._burst_cooldown = max(0.0, self._burst_cooldown - dt)
        self._burst_active = self._burst_cooldown > 0.0

        if self._overdrive_active:
            overdrive_boost = 0.10 + 0.30 * overdrive_norm
            effective_speed = min(cap, effective_speed * (1.0 + overdrive_boost))
            if is_viz_diagnostics_enabled():
                now = time.time()
                if now - self._overdrive_last_log_ts >= 0.5:
                    self._log_overdrive_state("hold", reactivity_raw, overdrive_gate_signal)
                    self._overdrive_last_log_ts = now
        base_vel = effective_speed * 0.35  # normalised units/sec

        group_drift_dx, group_drift_dy = self._update_group_drift_carrier(
            drift_dir,
            drift_freq,
            dt,
            active=group_drift_active,
        )

        # --- Update existing bubbles ---
        to_remove: List[int] = []
        for i, b in enumerate(self._bubbles):
            b.age += dt
            if b.bounce_glide > 0.0:
                b.bounce_glide = max(0.0, b.bounce_glide - dt)

            # Fade-in ramp for initial-fill bubbles (alpha starts at 0)
            if b.alpha < 1.0 and not b.popping:
                b.alpha = min(1.0, b.alpha + dt / 1.5)

            # Lifecycle: check if should start popping
            if not b.reaches_surface and not b.popping and b.age >= b.max_age:
                b.popping = True
                b.pop_timer = 0.0

            # Pop animation
            if b.popping:
                b.pop_timer += dt
                if b.pop_timer < 0.12:
                    # Expand phase
                    b.radius += b.radius * 0.18 * (dt / 0.12)
                elif b.pop_timer < 0.45:
                    # Fade phase (gentler, ~0.33s)
                    b.alpha = max(0.0, b.alpha - dt / 0.33)
                else:
                    b.alpha = 0.0

                if b.alpha <= 0.01:
                    to_remove.append(i)
                    continue

            # Stream velocity
            use_stored = stream_dir == "random"
            sv = _get_stream_vector(stream_dir) if not use_stored else (b.vx, b.vy)
            if use_stored and b.vx == 0.0 and b.vy == 0.0:
                rd = _random_direction()
                b.vx, b.vy = rd
                sv = (b.vx, b.vy)

            # Swirl modes: suppress stream velocity so orbits stay centred
            is_swirl = drift_dir in _SWIRL_DIRECTIONS
            stream_scale = 0.0 if is_swirl else 1.0
            # Post-bounce glide: briefly reduce stream/drift so rebound
            # trajectory is visible instead of immediately being re-steered.
            glide_t = min(1.0, b.bounce_glide / 0.18) if b.bounce_glide > 0.0 else 0.0
            stream_follow = 1.0 - 0.75 * glide_t
            drift_follow = 1.0 - 0.85 * glide_t
            bubble_vel = base_vel * b.speed_mult
            move_x = sv[0] * bubble_vel * dt * stream_scale * stream_follow
            move_y = sv[1] * bubble_vel * dt * stream_scale * stream_follow

            # Drift (sinusoidal lateral wander)
            drift_phase = b.phase + self._time * drift_speed * drift_phase_boost * 2.0
            local_drift_noise = math.sin(drift_phase * (1.0 + drift_freq * 3.0))
            drift_bias_val = b.drift_bias * drift_amount * 0.05 * drift_amplitude_boost
            drift_offset = (
                local_drift_noise * drift_amount * 0.03 * drift_amplitude_boost + drift_bias_val
            ) * drift_follow

            # Apply drift; Swish modes force an axis, swirl modes orbit around centre,
            # otherwise stay perpendicular to stream
            if group_drift_active:
                drift_gain = 0.82 + 0.42 * abs(b.drift_bias)
                group_loud_lift = 1.0 + loud_drift_drive * (0.92 + drift_amount * 0.42)
                lag_spread = max(0.72, min(1.28, 1.0 + b.drift_bias * 0.24))
                group_mag = (
                    (0.056 + drift_amount * 0.096)
                    * (0.84 + drift_speed * 1.46)
                    * drift_amplitude_boost
                    * drift_gain
                    * group_loud_lift
                    * lag_spread
                    * drift_follow
                )
                bias_slip = (
                    b.drift_bias
                    * drift_amount
                    * (0.010 + 0.010 * abs(b.drift_bias))
                    * (0.88 + loud_drift_drive * 0.24)
                    * drift_follow
                )
                soft_wander_scale = 0.20 + 0.55 * loud_drift_drive
                soft_wander = (
                    local_drift_noise
                    * drift_amount
                    * 0.0045
                    * soft_wander_scale
                    * drift_follow
                )
                if drift_dir == "swish_horizontal":
                    carrier_align = group_drift_dx * b.drift_bias
                    lead_align = max(0.0, carrier_align)
                    lag_align = max(0.0, -carrier_align)
                    carrier_mag = group_mag * (1.0 + lead_align * 0.12 - lag_align * 0.54)
                    straggler_slip = bias_slip
                    straggler_slip -= group_drift_dx * group_mag * lag_align * (0.16 + drift_amount * 0.07)
                    move_x += (group_drift_dx * carrier_mag + straggler_slip) * dt
                    move_y += (group_drift_dy * group_mag * (0.56 + lead_align * 0.08) + soft_wander) * dt
                elif drift_dir == "swish_vertical":
                    carrier_align = group_drift_dy * b.drift_bias
                    lead_align = max(0.0, carrier_align)
                    lag_align = max(0.0, -carrier_align)
                    carrier_mag = group_mag * (1.0 + lead_align * 0.12 - lag_align * 0.54)
                    straggler_slip = bias_slip
                    straggler_slip -= group_drift_dy * group_mag * lag_align * (0.16 + drift_amount * 0.07)
                    move_y += (group_drift_dy * carrier_mag + straggler_slip) * dt
                    move_x += (group_drift_dx * group_mag * (0.56 + lead_align * 0.08) + soft_wander) * dt
                else:
                    local_jitter = local_drift_noise * group_mag * 0.010
                    move_x += (group_drift_dx * group_mag + local_jitter) * dt
                    move_y += (group_drift_dy * group_mag + local_jitter * 0.45) * dt
            elif drift_dir == "swish_horizontal":
                move_x += drift_offset * dt
            elif drift_dir == "swish_vertical":
                move_y += drift_offset * dt
            elif is_swirl:
                swirl_dx, swirl_dy = self._swirl_motion(b, drift_dir, drift_amount, drift_speed, dt, base_vel)
                move_x += swirl_dx * drift_follow
                move_y += swirl_dy * drift_follow
            else:
                if abs(sv[0]) > abs(sv[1]) if stream_dir != "random" else True:
                    move_y += drift_offset * dt
                else:
                    move_x += drift_offset * dt

            b.x += move_x
            b.y -= move_y  # Y is inverted in UV space (0=top, 1=bottom)
            if b.impulse_vx != 0.0 or b.impulse_vy != 0.0:
                b.x += b.impulse_vx * dt
                b.y -= b.impulse_vy * dt
                damp = max(0.0, 1.0 - dt * IMPULSE_DAMPING_PER_SEC)
                b.impulse_vx *= damp
                b.impulse_vy *= damp
                if abs(b.impulse_vx) < 1e-5:
                    b.impulse_vx = 0.0
                if abs(b.impulse_vy) < 1e-5:
                    b.impulse_vy = 0.0

            if trail_enabled:
                self._update_trail_smear(b, dt, move_x, -move_y)
            else:
                self._bleed_trail_smear(b, dt)

            # Pulse energy: clean body authority only.
            # Motion owns transient/onset excitement. Bubble size uses the
            # sustained body signal plus its non-transient body-delta, so
            # loud passages do not collapse after transient-rich feeds ceiling
            # and soft vocal/body passages still breathe responsively.
            #
            # Promoted small bubbles temporarily react to bass (like big bubbles)
            # with scaled-down sensitivity, adding visual density during bursts.
            use_bass = b.is_big or b.promoted
            if use_bass:
                # Big bubbles should open up on clean vocal/body support too,
                # not only on sustained bass. Keep the contribution bounded,
                # but strong enough to matter in real mixed passages.
                big_vocal_body = pulse_mid * 0.28 + pulse_high * 0.10
                raw_src = pulse_bass + big_vocal_body
                running_avg = self._bass_running_avg
                if b.is_big:
                    size_range = max(0.001, self._big_size_max - 0.015)
                    size_t = min(1.0, max(0.0, (b.radius - 0.015) / size_range))
                    # The stricter sustain path fixed easy ceilinging, but it
                    # also made big-bubble life too brittle: tiny authored
                    # changes could collapse the whole big lane into a dead
                    # state. Keep the improved overdrive/release behavior, but
                    # restore more of the older big-lane sustain authority.
                    delta_sens = 3.05 - size_t * 0.9
                    sustained_knee = 0.46 + size_t * 0.16
                    sustained_scale = 0.36 - size_t * 0.10
                    attack_rate = 11.0 - size_t * 3.0
                    decay_rate = 2.85 + size_t * 1.0
                else:
                    # Promoted smalls should add a brief extra accent when the
                    # main big bubbles are already busy, not become a durable
                    # second big-bubble class.
                    size_t = 0.5
                    delta_sens = 1.95
                    sustained_knee = 0.60
                    sustained_scale = 0.10
                    attack_rate = 15.0
                    decay_rate = 7.2
                hot_hold_support = soft_ceiling(
                    max(0.0, pulse_bass - (0.62 + size_t * 0.10)),
                    knee=0.0,
                    ceiling=0.20 - size_t * 0.03,
                    max_input=0.36,
                    curve=1.0,
                )
                supra_hold_support = soft_ceiling(
                    max(0.0, max(pulse_bass, pulse_overall) - (1.20 + size_t * 0.08)),
                    knee=0.0,
                    ceiling=0.06 - size_t * 0.01,
                    max_input=0.42,
                    curve=1.0,
                )
            else:
                running_avg = self._midhi_running_avg
                size_range = max(0.001, self._small_size_max - 0.004)
                size_t = min(1.0, max(0.0, (b.radius - 0.004) / size_range))
                vocal_body = max(
                    pulse_mid * 0.64 + pulse_high * 0.30,
                    pulse_mid * 0.54 + pulse_high * 0.40,
                )
                big_lane_diag["small_vocal_body"] = max(big_lane_diag["small_vocal_body"], vocal_body)
                vocal_presence = soft_ceiling(
                    max(0.0, vocal_body - (0.15 + size_t * 0.025)),
                    knee=0.0,
                    ceiling=0.92,
                    max_input=0.22,
                    curve=1.0,
                )
                vocal_gap = (1.0 - vocal_presence) ** 1.35
                hot_field_support = soft_ceiling(
                    max(0.0, max(pulse_bass, pulse_overall) - (0.38 + size_t * 0.03)),
                    knee=0.0,
                    ceiling=0.22 - size_t * 0.02,
                    max_input=0.42,
                    curve=1.0,
                )
                bass_body_support = soft_ceiling(
                    max(0.0, pulse_bass - (0.36 + size_t * 0.04)),
                    knee=0.0,
                    ceiling=0.38 - size_t * 0.03,
                    max_input=0.50,
                    curve=1.0,
                )
                hot_field_support *= (0.92 + vocal_gap * 0.20)
                bass_body_support *= (0.82 + vocal_gap * 0.42)
                loud_body_authority = soft_ceiling(
                    max(0.0, max(pulse_bass, pulse_overall) - (0.76 + size_t * 0.05)),
                    knee=0.0,
                    ceiling=0.32 - size_t * 0.03,
                    max_input=0.90,
                    curve=1.0,
                )
                loud_body_authority *= (0.90 + vocal_gap * 0.16)
                raw_src = (
                    vocal_body
                    + hot_field_support
                    + bass_body_support
                    + loud_body_authority
                )
                delta_sens = 3.5 - size_t * 1.0  # 3.5x tiniest → 2.5x largest
                sustained_knee = max(0.18, 0.25 + size_t * 0.15 - vocal_gap * 0.08)
                sustained_scale = 0.56 - size_t * 0.04 + vocal_gap * 0.04
                attack_rate = 14.0 - size_t * 3.0
                decay_rate = 1.2 if b.radius < 0.008 else (3.5 + size_t * 1.5)
                if max(hot_field_support, bass_body_support, loud_body_authority) > 0.0:
                    decay_rate = min(decay_rate, 1.95 + size_t * 0.85)

            # Body-delta component: responsiveness from the clean non-transient
            # size feed, not from transient bus / crest injections.
            delta = max(0.0, raw_src - running_avg)
            delta_gate = 0.015 if use_bass else 0.012
            delta = max(0.0, delta - delta_gate)
            delta_component = min(1.0, delta * delta_sens)

            # Sustained component: absolute energy through perceptual curve
            # Below knee → near-zero; above knee → gentle ramp to sustained_scale
            perceptual_src = raw_src
            if perceptual_src <= sustained_knee:
                sustained_component = 0.0
            else:
                t = (perceptual_src - sustained_knee) / max(0.01, 1.0 - sustained_knee)
                sustained_component = min(sustained_scale, t * sustained_scale)

            if use_bass:
                combined_big_hold = hot_hold_support * 0.72 + supra_hold_support * 0.60
                sustained_component = max(
                    sustained_component,
                    combined_big_hold,
                )
            else:
                combined_small_body = soft_ceiling(
                    hot_field_support + bass_body_support + loud_body_authority,
                    knee=0.0,
                    ceiling=0.62 - size_t * 0.05,
                    max_input=0.58,
                    curve=1.0,
                )
                big_lane_diag["small_hot_body_authority"] = max(
                    big_lane_diag["small_hot_body_authority"],
                    combined_small_body,
                )
                sustained_component = max(
                    sustained_component,
                    combined_small_body,
                )

            gated_energy = min(1.0, max(delta_component, sustained_component))

            if gated_energy > b.pulse_energy:
                b.pulse_energy += (gated_energy - b.pulse_energy) * min(1.0, dt * attack_rate)
            else:
                b.pulse_energy += (gated_energy - b.pulse_energy) * min(1.0, dt * decay_rate)
            b.size_gate_energy = gated_energy

            if b.is_big:
                big_lane_diag["big_count"] += 1.0
                big_lane_diag["max_big_raw_src"] = max(big_lane_diag["max_big_raw_src"], raw_src)
                big_lane_diag["max_big_gated_energy"] = max(big_lane_diag["max_big_gated_energy"], gated_energy)
                big_lane_diag["max_big_pulse_after"] = max(big_lane_diag["max_big_pulse_after"], b.pulse_energy)
                if b.pulse_energy > 0.04:
                    big_lane_diag["active_big_count"] += 1.0

            # Rotation (wobble)
            vocal_energy = mid * 0.7 + bass * 0.2 + high * 0.1
            b.rotation += vocal_energy * rotation_amount * 2.0 * dt

            # Check if bubble exited the card
            margin = 0.1
            head_outside = (b.x < -margin or b.x > 1.0 + margin or
                            b.y < -margin or b.y > 1.0 + margin)

            if head_outside and b.reaches_surface and not b.exiting:
                # Bubble head left the visible area — start exit phase.
                # Don't destroy yet: let the trail tail drift out of frame.
                b.exiting = True
                b.exit_timer = 0.0

            if b.exiting:
                b.exit_timer += dt
                # Accelerate trail fade so it drains away smoothly
                b.trail_strength = max(0.0, b.trail_strength - dt * 2.5)
                # Check if trail tail is also outside the card (primary exit)
                tail_outside = (b.trail_tail_x < -margin or b.trail_tail_x > 1.0 + margin or
                                b.trail_tail_y < -margin or b.trail_tail_y > 1.0 + margin)
                # Destroy when: trail tail is offscreen OR trail fully faded,
                # OR grace period exceeded (safety net, ~0.8s)
                if tail_outside or b.trail_strength <= 0.001 or b.exit_timer > 0.8:
                    to_remove.append(i)

        big_lane_diag["dormant_big_count"] = max(
            0.0,
            big_lane_diag["big_count"] - big_lane_diag["active_big_count"],
        )
        self._last_big_lane_diag = big_lane_diag

        self._apply_bubble_collision_response(
            dt,
            bounce_big_pct=bounce_big_pct,
            bounce_small_pct=bounce_small_pct,
            bounce_big_speed=bounce_big_speed,
            bounce_small_speed=bounce_small_speed,
            bounce_same_only=bounce_same_only,
            collision_pop_mode=collision_pop_mode,
            big_bass_pulse=big_bass_pulse,
            small_freq_pulse=small_freq_pulse,
            big_contraction_bias=big_contraction_bias,
            big_size_clamp=big_size_clamp,
        )

        # Remove dead bubbles (reverse order)
        for i in sorted(to_remove, reverse=True):
            if i < len(self._bubbles):
                self._bubbles.pop(i)

        # --- Spawn new bubbles to maintain targets ---
        # Exiting bubbles are draining out and shouldn't hold spawn slots.
        big_count = sum(1 for b in self._bubbles if b.is_big and not b.exiting)
        small_count = sum(1 for b in self._bubbles if not b.is_big and not b.exiting)

        allow_initial_fill = self._time < 0.5 and _stream_mode_uses_in_card_initial_fill(stream_dir, drift_dir)
        if allow_initial_fill:
            big_spawn_budget = big_target
        else:
            big_spawn_budget = 2
        while (
            big_count < big_target
            and len(self._bubbles) < MAX_BUBBLES
            and big_spawn_budget > 0
        ):
            if allow_initial_fill:
                bx = random.uniform(0.08, 0.92)
                by = random.uniform(0.08, 0.92)
                self._spawn_bubble_at(True, bx, by, stream_dir, surface_reach, drift_dir,
                                      initial_fill=True)
            else:
                self._spawn_bubble(True, stream_dir, surface_reach, drift_dir)
            big_count += 1
            big_spawn_budget -= 1

        if allow_initial_fill:
            small_spawn_budget = small_target
        else:
            small_spawn_budget = 3
        while (
            small_count < small_target
            and len(self._bubbles) < MAX_BUBBLES
            and small_spawn_budget > 0
        ):
            is_initial = allow_initial_fill
            cluster = (not is_initial) and random.random() < 0.18
            count = random.randint(2, 3) if cluster else 1
            if is_initial:
                # First fill: scatter across card area
                base_x = random.uniform(0.05, 0.95)
                base_y = random.uniform(0.05, 0.95)
            elif drift_dir in _SWIRL_DIRECTIONS:
                # Swirl: spawn near center so bubbles spiral outward
                _angle = random.uniform(0.0, math.tau)
                _spawn_r = random.uniform(0.02, 0.10)
                base_x = 0.5 + math.cos(_angle) * _spawn_r
                base_y = 0.5 + math.sin(_angle) * _spawn_r
            else:
                base_x, base_y = _directional_entry_position(stream_dir, False, startup=False)
            for c in range(count):
                if (
                    small_count >= small_target
                    or len(self._bubbles) >= MAX_BUBBLES
                    or small_spawn_budget <= 0
                ):
                    break
                cx = base_x + (random.uniform(-0.07, 0.07) if c > 0 else 0.0)
                cy = base_y + (random.uniform(-0.07, 0.07) if c > 0 else 0.0)
                self._spawn_bubble_at(False, cx, cy, stream_dir, surface_reach, drift_dir,
                                      initial_fill=is_initial)
                small_count += 1
                small_spawn_budget -= 1

        tick_ms = (time.perf_counter() - tick_start) * 1000.0
        perf_diag = dict(self._last_perf_diag)
        perf_diag.update(
            {
                "tick_ms": tick_ms,
                "active_bubbles": float(sum(1 for b in self._bubbles if not b.popping and not b.exiting)),
                "total_bubbles": float(len(self._bubbles)),
            }
        )
        self._last_perf_diag = perf_diag

    def _spawn_bubble(self, is_big: bool, stream_dir: str,
                      surface_reach: float, drift_dir: str) -> None:
        if drift_dir in _SWIRL_DIRECTIONS:
            # Swirl: spawn near center so bubbles spiral outward.
            angle = random.uniform(0.0, math.tau)
            spawn_r = random.uniform(0.02, 0.10)
            x = 0.5 + math.cos(angle) * spawn_r
            y = 0.5 + math.sin(angle) * spawn_r
        else:
            x, y = _directional_entry_position(stream_dir, is_big, startup=False)
        self._spawn_bubble_at(is_big, x, y, stream_dir, surface_reach, drift_dir)

    def _predict_stream_position(
        self,
        x: float,
        y: float,
        stream_dir: str,
        *,
        vx: float = 0.0,
        vy: float = 0.0,
        distance: float = 0.16,
    ) -> Tuple[float, float]:
        """Project a bubble forward along stream travel for entry-lane checks."""
        if stream_dir == "random":
            dx, dy = (vx, vy) if (vx != 0.0 or vy != 0.0) else _random_direction()
        else:
            dx, dy = _get_stream_vector(stream_dir)
        return (x + dx * distance, y - dy * distance)

    @staticmethod
    def _trigger_collision_pop(bubble: BubbleState) -> None:
        if bubble.popping or bubble.exiting:
            return
        bubble.popping = True
        bubble.pop_timer = 0.0
        bubble.impulse_vx = 0.0
        bubble.impulse_vy = 0.0
        bubble.bounce_glide = 0.0

    def _apply_bubble_collision_response(
        self,
        dt: float,
        *,
        bounce_big_pct: float,
        bounce_small_pct: float,
        bounce_big_speed: float,
        bounce_small_speed: float,
        bounce_same_only: bool = False,
        collision_pop_mode: str = "off",
        big_bass_pulse: float = 0.5,
        small_freq_pulse: float = 0.5,
        big_contraction_bias: float = 1.0,
        big_size_clamp: float = 4.0,
    ) -> None:
        """Separate overlapping bubbles by visual class.

        Big bubbles are the readable hero layer and should resist overlap with
        other big/promoted bubbles strongly. Small bubbles remain the permissive
        texture/noise layer and may nestle or overlap lightly.
        """
        active = [b for b in self._bubbles if not b.popping and not b.exiting]
        count = len(active)
        perf_start = time.perf_counter()
        pair_checks = 0
        overlap_hits = 0
        if count < 2:
            perf_diag = dict(self._last_perf_diag)
            perf_diag.update(
                {
                    "collision_ms": 0.0,
                    "collision_pairs": 0.0,
                    "collision_overlaps": 0.0,
                    "collision_passes": 0.0,
                }
            )
            self._last_perf_diag = perf_diag
            return

        max_bounce_pct = max(bounce_big_pct, bounce_small_pct)
        max_bounce_speed = max(bounce_big_speed, bounce_small_speed)
        passes = 1
        if max_bounce_pct >= 88.0 and max_bounce_speed >= 0.85:
            passes += 1
        if max_bounce_pct >= 98.0 and max_bounce_speed >= 1.5:
            passes += 2

        dt_scale = min(1.0, dt * 60.0)
        max_speed_norm = max(0.0, min(1.0, max_bounce_speed / 2.0))
        smooth_mode = max_speed_norm < 0.45
        view_margin = 0.02
        if collision_pop_mode not in {"off", "one", "all"}:
            collision_pop_mode = "off"

        def _pair_policy(
            *,
            gap_factor: float,
            gap_bias: float,
            softness: float,
            max_push: float,
            bounce_pct: float,
            bounce_speed: float,
        ) -> tuple[float, float, float, float, float, float, float, float]:
            bounce_strength = max(0.0, min(1.0, bounce_pct / 100.0))
            speed_norm = max(0.0, min(1.0, bounce_speed / 2.0))
            strict_gap_factor = 0.92 + 0.08 * bounce_strength
            strict_gap_bias = 0.0015 if bounce_strength >= 0.85 else 0.0
            return (
                gap_factor,
                gap_bias,
                softness,
                max_push,
                bounce_strength,
                speed_norm,
                strict_gap_factor,
                strict_gap_bias,
            )

        big_policy = _pair_policy(
            gap_factor=1.12,
            gap_bias=0.008,
            softness=0.22,
            max_push=0.022,
            bounce_pct=bounce_big_pct,
            bounce_speed=bounce_big_speed,
        )
        mixed_policy = _pair_policy(
            gap_factor=0.90,
            gap_bias=0.0,
            softness=0.08,
            max_push=0.012,
            bounce_pct=bounce_big_pct,
            bounce_speed=bounce_big_speed,
        )
        small_policy = _pair_policy(
            gap_factor=0.78,
            gap_bias=0.0,
            softness=0.045,
            max_push=0.007,
            bounce_pct=bounce_small_pct,
            bounce_speed=bounce_small_speed,
        )

        def _in_view(bubble: BubbleState) -> bool:
            return (
                -view_margin <= bubble.x <= 1.0 + view_margin
                and -view_margin <= bubble.y <= 1.0 + view_margin
            )

        for _ in range(passes):
            pending_dx = [0.0] * count if smooth_mode else []
            pending_dy = [0.0] * count if smooth_mode else []
            collision_radii = [
                self._effective_collision_radius(
                    bubble,
                    big_bass_pulse=big_bass_pulse,
                    small_freq_pulse=small_freq_pulse,
                    big_contraction_bias=big_contraction_bias,
                    big_size_clamp=big_size_clamp,
                )
                for bubble in active
            ]
            active_big_flags = [_bubble_behaves_big(bubble) for bubble in active]
            if not collision_radii:
                continue
            max_collision_radius = max(collision_radii)
            max_gap_factor = max(
                big_policy[0],
                mixed_policy[0],
                small_policy[0],
                big_policy[6],
                mixed_policy[6],
                small_policy[6],
            )
            max_gap_bias = max(
                big_policy[1],
                mixed_policy[1],
                small_policy[1],
                big_policy[7],
                mixed_policy[7],
                small_policy[7],
            )
            sorted_indices = sorted(range(count), key=lambda idx: active[idx].x)
            for sorted_pos, i in enumerate(sorted_indices):
                a = active[i]
                if a.popping or a.exiting:
                    continue
                a_radius = collision_radii[i]
                max_possible_gap = (a_radius + max_collision_radius) * max_gap_factor + max_gap_bias
                for next_pos in range(sorted_pos + 1, count):
                    j = sorted_indices[next_pos]
                    b = active[j]
                    dx = b.x - a.x
                    if dx > max_possible_gap:
                        break
                    pair_checks += 1
                    if b.popping or b.exiting:
                        continue
                    b_radius = collision_radii[j]
                    dy = b.y - a.y
                    a_big = active_big_flags[i]
                    b_big = active_big_flags[j]
                    if a_big and b_big:
                        (
                            gap_factor,
                            gap_bias,
                            softness,
                            max_push,
                            bounce_strength,
                            speed_norm,
                            strict_gap_factor,
                            strict_gap_bias,
                        ) = big_policy
                    elif a_big or b_big:
                        if bounce_same_only:
                            continue
                        (
                            gap_factor,
                            gap_bias,
                            softness,
                            max_push,
                            bounce_strength,
                            speed_norm,
                            strict_gap_factor,
                            strict_gap_bias,
                        ) = mixed_policy
                    else:
                        (
                            gap_factor,
                            gap_bias,
                            softness,
                            max_push,
                            bounce_strength,
                            speed_norm,
                            strict_gap_factor,
                            strict_gap_bias,
                        ) = small_policy

                    radii_sum = a_radius + b_radius
                    target_gap = radii_sum * gap_factor + gap_bias
                    strict_gap = radii_sum * strict_gap_factor + strict_gap_bias
                    target_gap = max(target_gap, strict_gap)
                    target_gap_sq = target_gap * target_gap

                    dist_sq = dx * dx + dy * dy
                    if dist_sq >= target_gap_sq:
                        continue
                    overlap_hits += 1

                    if dist_sq < 1e-10:
                        angle = random.uniform(0.0, math.tau)
                        nx = math.cos(angle)
                        ny = math.sin(angle)
                        dist = 0.0
                    else:
                        dist = math.sqrt(dist_sq)
                        inv = 1.0 / dist
                        nx = dx * inv
                        ny = dy * inv

                    overlap = target_gap - dist
                    a_in_view = _in_view(a)
                    b_in_view = _in_view(b)
                    both_in_view = a_in_view and b_in_view
                    push_softness = softness * (0.60 + 0.52 * speed_norm) + bounce_strength * 0.03
                    push_cap = max_push * (0.25 + 0.75 * speed_norm + bounce_strength * 0.15)
                    if speed_norm >= 0.80 and bounce_strength >= 0.90:
                        push_softness *= 1.70
                        push_cap *= 2.00
                    push = min(push_cap, overlap * push_softness * dt_scale)
                    if speed_norm >= 0.80 and bounce_strength >= 0.90:
                        push = max(push, overlap * 0.34)

                    # Entry stability: resolve overlap before it becomes visible.
                    # When only one bubble is on-card, move the off-card bubble
                    # far more than the visible one to prevent snap-shifts.
                    if not both_in_view:
                        if a_in_view != b_in_view:
                            push *= 0.70
                        else:
                            push = min(push_cap * 1.35, push * 1.35)

                    if a_in_view and not b_in_view:
                        weight_a, weight_b = 0.14, 0.86
                    elif b_in_view and not a_in_view:
                        weight_a, weight_b = 0.86, 0.14
                    else:
                        weight_a, weight_b = 0.5, 0.5
                    total_push = push * 2.0
                    ax = -nx * total_push * weight_a
                    ay = -ny * total_push * weight_a
                    bx = nx * total_push * weight_b
                    by = ny * total_push * weight_b

                    if smooth_mode:
                        pending_dx[i] += ax
                        pending_dy[i] += ay
                        pending_dx[j] += bx
                        pending_dy[j] += by
                    else:
                        a.x += ax
                        a.y += ay
                        b.x += bx
                        b.y += by

                    if collision_pop_mode == "all":
                        self._trigger_collision_pop(a)
                        self._trigger_collision_pop(b)
                        continue
                    if collision_pop_mode == "one":
                        # Mixed-class policy: big bubbles always win when
                        # same-class-only filtering is disabled.
                        if a_big != b_big:
                            if a_big:
                                self._trigger_collision_pop(b)
                            else:
                                self._trigger_collision_pop(a)
                        elif random.random() < 0.5:
                            self._trigger_collision_pop(a)
                        else:
                            self._trigger_collision_pop(b)
                        continue

                    bounce_prob = bounce_strength
                    pair_key = (min(id(a), id(b)), max(id(a), id(b)))
                    cooldown_until = self._pair_bounce_cooldowns.get(pair_key, 0.0)
                    in_pair_cooldown = self._time < cooldown_until
                    if (
                        bounce_prob > 0.0
                        and speed_norm > 0.0
                        and both_in_view
                        and (not in_pair_cooldown)
                        and random.random() <= bounce_prob
                    ):
                        rel_vx = b.impulse_vx - a.impulse_vx
                        rel_vy = b.impulse_vy - a.impulse_vy
                        sep_speed = rel_vx * nx + rel_vy * ny
                        if sep_speed <= -0.004 or overlap > target_gap * 0.07:
                            restitution = speed_norm
                            impulse = (-(1.0 + restitution) * sep_speed) * 0.5
                            floor_kick = min(
                                MAX_IMPULSE_SPEED * (0.03 + 0.22 * speed_norm),
                                overlap * (0.25 + 0.95 * speed_norm) * speed_norm,
                            )
                            impulse = max(impulse, floor_kick)
                            local_cap = MAX_IMPULSE_SPEED * (0.18 + 0.82 * speed_norm)

                            a.impulse_vx -= nx * impulse
                            a.impulse_vy -= ny * impulse
                            b.impulse_vx += nx * impulse
                            b.impulse_vy += ny * impulse
                            glide_window = 0.10 + 0.10 * speed_norm
                            a.bounce_glide = max(a.bounce_glide, glide_window)
                            b.bounce_glide = max(b.bounce_glide, glide_window)
                            self._pair_bounce_cooldowns[pair_key] = self._time + (0.10 + 0.07 * speed_norm)

                            a_speed = math.hypot(a.impulse_vx, a.impulse_vy)
                            if a_speed > local_cap:
                                scale = local_cap / a_speed
                                a.impulse_vx *= scale
                                a.impulse_vy *= scale
                            b_speed = math.hypot(b.impulse_vx, b.impulse_vy)
                            if b_speed > local_cap:
                                scale = local_cap / b_speed
                                b.impulse_vx *= scale
                                b.impulse_vy *= scale

            if smooth_mode:
                # Prevent one-frame "snap" shifts in dense pulse clusters by
                # capping accumulated positional correction per bubble.
                max_disp = 0.0010 + 0.0030 * max_speed_norm + 0.0060 * max_speed_norm * max_speed_norm
                if max_bounce_pct >= 95.0:
                    max_disp += 0.0015 * max_speed_norm
                    if max_speed_norm >= 0.80:
                        max_disp = max(max_disp, 0.014 + 0.010 * max_speed_norm)
                for i, bubble in enumerate(active):
                    dx = pending_dx[i]
                    dy = pending_dy[i]
                    mag = math.hypot(dx, dy)
                    if _in_view(bubble):
                        max_disp *= 0.72
                    if mag > max_disp and mag > 1e-8:
                        scale = max_disp / mag
                        dx *= scale
                        dy *= scale
                    bubble.x += dx
                    bubble.y += dy

        if self._pair_bounce_cooldowns:
            now = self._time
            stale = [k for k, t in self._pair_bounce_cooldowns.items() if t <= now]
            for key in stale:
                self._pair_bounce_cooldowns.pop(key, None)
        perf_diag = dict(self._last_perf_diag)
        perf_diag.update(
            {
                "collision_ms": (time.perf_counter() - perf_start) * 1000.0,
                "collision_pairs": float(pair_checks),
                "collision_overlaps": float(overlap_hits),
                "collision_passes": float(passes),
            }
        )
        self._last_perf_diag = perf_diag

    def _effective_collision_radius(
        self,
        bubble: BubbleState,
        *,
        big_bass_pulse: float,
        small_freq_pulse: float,
        big_contraction_bias: float,
        big_size_clamp: float,
    ) -> float:
        """Approximate rendered radius so collision and visuals stay aligned."""
        big_hold_boost, big_crest_boost = self._compute_big_render_boosts(bubble)
        if bubble.is_big:
            pulse_factor = self._big_render_pulse_factor(
                bubble.pulse_energy,
                gate_energy=bubble.size_gate_energy,
                big_bass_pulse=big_bass_pulse,
                big_hold_boost=big_hold_boost,
                big_crest_boost=big_crest_boost,
            )
        else:
            pulse_factor = self._small_render_pulse_factor(
                bubble,
                small_freq_pulse=small_freq_pulse,
            )

        r = bubble.radius * pulse_factor
        if bubble.is_big and big_contraction_bias < 1.0:
            quiet = 1.0 - min(1.0, bubble.pulse_energy)
            quiet_curve = quiet ** 0.85
            shrink = 1.0 - (1.0 - big_contraction_bias) * quiet_curve * 0.70
            r *= max(0.60, shrink)

        if bubble.is_big and big_size_clamp > 0.0:
            r = min(r, self._resolve_big_clamp_limit(bubble.radius, big_size_clamp))

        return max(0.001, r)

    @staticmethod
    def _big_render_pulse_factor(
        pulse_energy: float,
        *,
        gate_energy: float,
        big_bass_pulse: float,
        big_hold_boost: float,
        big_crest_boost: float,
    ) -> float:
        """Map hero pulse into visible size without flattening all hot windows.

        Ordinary hot passages were reaching the authored clamp too early because
        the raw pulse multiplier alone could push them there. Compress the top
        of the pulse band slightly so sustained loudness can create the final
        visible separation between restrained-hot and truly loud phrases.
        """
        pulse = max(0.0, float(pulse_energy))
        gate = _clamp01(gate_energy)
        if gate < pulse:
            pulse = pulse * 0.62 + gate * 0.38
        if pulse <= 0.54:
            shaped_pulse = pulse
        else:
            shaped_pulse = 0.54 + (pulse - 0.54) * 0.42
        quiet_contraction = ((1.0 - min(1.0, pulse)) ** 0.90) * 0.78
        return (
            1.0
            + shaped_pulse * big_bass_pulse * 4.45
            + big_hold_boost
            + big_crest_boost
            - quiet_contraction
        )

    def _compute_big_render_boosts(self, bubble: BubbleState) -> tuple[float, float]:
        """Keep big-bubble render sizing on the sustained body contract."""
        render_body_energy = max(0.0, self._render_body_energy)
        big_hold_boost = soft_ceiling(
            max(0.0, render_body_energy - 0.84),
            knee=0.0,
            ceiling=0.11,
            max_input=0.22,
            curve=1.0,
        )
        big_hold_boost += soft_ceiling(
            max(0.0, render_body_energy - 1.06),
            knee=0.0,
            ceiling=0.06,
            max_input=0.24,
            curve=1.0,
        )
        big_crest_boost = soft_ceiling(
            max(0.0, bubble.pulse_energy - 0.91),
            knee=0.0,
            ceiling=0.42,
            max_input=0.07,
            curve=1.0,
        ) * soft_ceiling(
            max(0.0, render_body_energy - 0.82),
            knee=0.0,
            ceiling=1.0,
            max_input=0.22,
            curve=1.0,
        )
        return big_hold_boost, big_crest_boost

    def _small_render_pulse_factor(
        self,
        bubble: BubbleState,
        *,
        small_freq_pulse: float,
    ) -> float:
        """Open tiny-small render authority only when the passage is truly hot.

        Tiny authored bubbles need a quieter render multiplier in soft passages
        so they do not chatter between dot and outline states. The earlier hard
        0.5x cap, however, stayed in force even when Bubble was already carrying
        legitimate loud-section body via `pulse_energy`, which made the tiniest
        field look under-participatory compared with soft passages.
        """
        pulse = max(0.0, float(bubble.pulse_energy))
        loud_body = soft_ceiling(
            max(0.0, self._render_body_energy - 0.78),
            knee=0.0,
            ceiling=0.36,
            max_input=0.92,
            curve=1.0,
        )
        if bubble.radius >= 0.008:
            gain = 3.15 + loud_body * 1.35
            return 1.0 + pulse * small_freq_pulse * gain

        loud_hold = soft_ceiling(
            max(0.0, self._render_body_energy - 0.66),
            knee=0.0,
            ceiling=1.0,
            max_input=0.92,
            curve=1.0,
        )
        hot_pulse = soft_ceiling(
            max(0.0, pulse - 0.24),
            knee=0.0,
            ceiling=1.0,
            max_input=0.56,
            curve=1.0,
        )
        loud_blend = max(0.0, min(1.0, loud_hold * 0.96 + hot_pulse * 0.48 + loud_body * 0.52))
        tiny_gain = 0.68 + (2.70 - 0.68) * loud_blend
        return 1.0 + pulse * small_freq_pulse * tiny_gain

    def _resolve_big_clamp_limit(self, base_radius: float, big_size_clamp: float) -> float:
        """Give truly loud hero sections a little authored-clamp headroom.

        This stays tied to the existing `big_size_clamp` control rather than
        creating a second separate limit. Ordinary hot passages still respect
        the authored clamp; only supra-loud sections get a small amount of
        extra headroom so they do not flatten into the same visible size.
        """
        clamp_factor = max(1.5, float(big_size_clamp))
        loud_headroom = soft_ceiling(
            max(0.0, self._render_body_energy - 0.78),
            knee=0.0,
            ceiling=0.36,
            max_input=0.34,
            curve=1.0,
        )
        supra_headroom = soft_ceiling(
            max(0.0, self._render_body_energy - 0.92),
            knee=0.0,
            ceiling=0.34,
            max_input=0.34,
            curve=1.0,
        )
        return base_radius * clamp_factor * (1.0 + loud_headroom + supra_headroom)

    def _apply_big_display_radius_smoothing(
        self,
        bubble: BubbleState,
        target_radius: float,
        visual_smoothing: float,
    ) -> float:
        """Smooth only the rendered hero radius; audio/pulse authority stays raw."""
        if not bubble.is_big:
            bubble.display_radius = target_radius
            return target_radius

        amount = _clamp01(visual_smoothing)
        if amount <= 0.001:
            bubble.display_radius = target_radius
            return target_radius

        # Loud passages still need fast truthful size authority, but completely
        # disabling smoothing this early makes the authored setting feel like a
        # lie. Blend smoothing down instead of hard-bypassing it.
        hot_blend = _clamp01(
            max(
                (self._sustained_loud_energy - 0.64) / 0.26,
                (bubble.pulse_energy - 0.74) / 0.22,
            )
        )
        hot_smoothing_floor = 0.62 + amount * 0.16
        amount *= max(hot_smoothing_floor, 1.0 - hot_blend * 0.24)
        if amount <= 0.001:
            bubble.display_radius = target_radius
            return target_radius

        current = bubble.display_radius if bubble.display_radius > 0.0 else target_radius
        dt = min(0.05, max(1.0 / 240.0, float(self._last_tick_dt or 0.016)))

        if amount <= 0.5:
            t = amount / 0.5
            rise_hz = 196.0 + (112.0 - 196.0) * t
            micro_rise_hz = 28.0 + (14.0 - 28.0) * t
            sharp_drop_hz = 92.0 + (42.0 - 92.0) * t
            soft_drop_hz = 42.0 + (18.0 - 42.0) * t
            micro_drop_hz = 20.0 + (9.0 - 20.0) * t
            micro_drop_ratio = 0.018 + (0.070 - 0.018) * t
            settle_band_abs = 0.00032 + (0.00120 - 0.00032) * t
            settle_band_ratio = 0.020 + (0.060 - 0.020) * t
            snap_abs = 0.00035 + (0.0010 - 0.00035) * t
            snap_ratio = 0.008 + (0.032 - 0.008) * t
        else:
            t = (amount - 0.5) / 0.5
            rise_hz = 112.0 + (40.0 - 112.0) * t
            micro_rise_hz = 14.0 + (4.0 - 14.0) * t
            sharp_drop_hz = 42.0 + (22.0 - 42.0) * t
            soft_drop_hz = 18.0 + (8.0 - 18.0) * t
            micro_drop_hz = 9.0 + (3.0 - 9.0) * t
            micro_drop_ratio = 0.070 + (0.150 - 0.070) * t
            settle_band_abs = 0.00120 + (0.00340 - 0.00120) * t
            settle_band_ratio = 0.060 + (0.160 - 0.060) * t
            snap_abs = 0.0010 + (0.0015 - 0.0010) * t
            snap_ratio = 0.032 + (0.055 - 0.032) * t

        delta = target_radius - current
        delta_abs = abs(delta)
        settle_band = max(settle_band_abs, max(bubble.radius, current) * settle_band_ratio)
        hold_band = settle_band * (0.82 + amount * 0.38)

        if delta_abs <= hold_band:
            bubble.display_radius = max(0.001, current)
            return bubble.display_radius

        if delta >= 0.0:
            if delta_abs <= settle_band:
                rate = min(1.0, dt * micro_rise_hz)
            else:
                rate = min(1.0, dt * rise_hz)
        else:
            drop_ratio = (current - target_radius) / max(current, 1e-6)
            if delta_abs <= settle_band or drop_ratio <= micro_drop_ratio:
                rate = min(1.0, dt * micro_drop_hz)
            else:
                rate = min(1.0, dt * (sharp_drop_hz if drop_ratio >= 0.22 else soft_drop_hz))

        current += (target_radius - current) * rate
        if (
            amount < 0.45
            and target_radius < current
            and (current - target_radius) <= max(snap_abs, bubble.radius * snap_ratio)
        ):
            current = target_radius
        bubble.display_radius = max(0.001, current)
        return bubble.display_radius

    @staticmethod
    def _group_drift_period(drift_freq: float) -> float:
        freq = _clamp01(drift_freq)
        return 2.40 + (1.0 - freq) * 5.20

    @staticmethod
    def _resolve_group_drift_turn_duration(drift_freq: float, drift_dir: str, period: float) -> float:
        freq = _clamp01(drift_freq)
        if drift_dir in {"swish_horizontal", "swish_vertical"}:
            portion = 0.20 + (1.0 - freq) * 0.08
        else:
            portion = 0.28 + (1.0 - freq) * 0.10
        return max(0.18, min(period * 0.44, period * portion))

    @staticmethod
    def _normalize_group_drift_vector(dx: float, dy: float) -> tuple[float, float]:
        mag = math.hypot(dx, dy)
        if mag <= 1e-6:
            return (0.0, 0.0)
        return (dx / mag, dy / mag)

    def _pick_group_drift_vector(self, drift_dir: str) -> tuple[float, float]:
        previous = self._normalize_group_drift_vector(
            self._group_drift_target_dx or self._group_drift_dx,
            self._group_drift_target_dy or self._group_drift_dy,
        )
        if drift_dir == "swish_horizontal":
            if previous != (0.0, 0.0):
                return (-previous[0], 0.0)
            candidates = [(-1.0, 0.0), (1.0, 0.0)]
        elif drift_dir == "swish_vertical":
            if previous != (0.0, 0.0):
                return (0.0, -previous[1])
            candidates = [(0.0, -1.0), (0.0, 1.0)]
        elif drift_dir == "diagonal":
            candidates = list(_DIAGONAL_STREAM_VECTORS)
        else:
            candidates = [_random_direction() for _ in range(4)]
        if previous != (0.0, 0.0) and drift_dir not in {"swish_horizontal", "swish_vertical"}:
            non_opposites = [
                cand
                for cand in candidates
                if cand[0] * previous[0] + cand[1] * previous[1] > -0.35
            ]
            if non_opposites:
                candidates = non_opposites
        return random.choice(candidates)

    def _update_group_drift_carrier(
        self,
        drift_dir: str,
        drift_freq: float,
        dt: float,
        *,
        active: bool,
    ) -> tuple[float, float]:
        if not active:
            self._group_drift_dx = 0.0
            self._group_drift_dy = 0.0
            self._group_drift_from_dx = 0.0
            self._group_drift_from_dy = 0.0
            self._group_drift_target_dx = 0.0
            self._group_drift_target_dy = 0.0
            self._group_drift_remaining = 0.0
            self._group_drift_turn_elapsed = 0.0
            self._group_drift_turn_duration = 0.0
            self._group_drift_arc_x = 0.0
            self._group_drift_arc_y = 0.0
            return (0.0, 0.0)
        self._group_drift_remaining = max(0.0, self._group_drift_remaining - dt)
        period = self._group_drift_period(drift_freq)
        if (
            self._group_drift_remaining <= 0.0
            or (self._group_drift_dx == 0.0 and self._group_drift_dy == 0.0)
        ):
            next_dx, next_dy = self._pick_group_drift_vector(drift_dir)
            if self._group_drift_dx == 0.0 and self._group_drift_dy == 0.0:
                self._group_drift_dx = next_dx
                self._group_drift_dy = next_dy
                self._group_drift_target_dx = next_dx
                self._group_drift_target_dy = next_dy
                self._group_drift_from_dx = next_dx
                self._group_drift_from_dy = next_dy
                self._group_drift_turn_elapsed = 0.0
                self._group_drift_turn_duration = 0.0
            else:
                self._group_drift_from_dx = self._group_drift_dx
                self._group_drift_from_dy = self._group_drift_dy
                self._group_drift_target_dx = next_dx
                self._group_drift_target_dy = next_dy
                self._group_drift_turn_elapsed = 0.0
                self._group_drift_turn_duration = self._resolve_group_drift_turn_duration(
                    drift_freq,
                    drift_dir,
                    period,
                )
                self._group_drift_arc_sign = random.choice((-1.0, 1.0))
                if is_viz_diagnostics_enabled():
                    logger.info(
                        "[SPOTIFY_VIS][BUBBLE][GROUP_DRIFT] dir=%s target=(%.3f,%.3f) period=%.3fs turn=%.3fs freq=%.3f",
                        drift_dir,
                        next_dx,
                        next_dy,
                        period,
                        self._group_drift_turn_duration,
                        drift_freq,
                    )
            self._group_drift_remaining = period * random.uniform(0.98, 1.06)
        if self._group_drift_turn_duration > 0.0:
            self._group_drift_turn_elapsed = min(
                self._group_drift_turn_duration,
                self._group_drift_turn_elapsed + dt,
            )
            blend = self._group_drift_turn_elapsed / max(1e-6, self._group_drift_turn_duration)
            eased = blend * blend * blend * (blend * (blend * 6.0 - 15.0) + 10.0)
            mixed_dx = self._group_drift_from_dx + (
                self._group_drift_target_dx - self._group_drift_from_dx
            ) * eased
            mixed_dy = self._group_drift_from_dy + (
                self._group_drift_target_dy - self._group_drift_from_dy
            ) * eased
            if drift_dir in {"swish_horizontal", "swish_vertical"}:
                self._group_drift_dx = mixed_dx
                self._group_drift_dy = mixed_dy
                arc_wave = math.sin(math.pi * blend)
                arc_strength = 0.032 + (1.0 - _clamp01(drift_freq)) * 0.022
                if drift_dir == "swish_horizontal":
                    self._group_drift_arc_x = 0.0
                    self._group_drift_arc_y = self._group_drift_arc_sign * arc_strength * arc_wave
                else:
                    self._group_drift_arc_x = self._group_drift_arc_sign * arc_strength * arc_wave
                    self._group_drift_arc_y = 0.0
            else:
                self._group_drift_dx, self._group_drift_dy = self._normalize_group_drift_vector(
                    mixed_dx,
                    mixed_dy,
                )
                self._group_drift_arc_x = 0.0
                self._group_drift_arc_y = 0.0
            if self._group_drift_turn_elapsed >= self._group_drift_turn_duration:
                self._group_drift_dx = self._group_drift_target_dx
                self._group_drift_dy = self._group_drift_target_dy
                self._group_drift_turn_duration = 0.0
                self._group_drift_arc_x = 0.0
                self._group_drift_arc_y = 0.0
        else:
            if self._group_drift_target_dx != 0.0 or self._group_drift_target_dy != 0.0:
                self._group_drift_dx = self._group_drift_target_dx
                self._group_drift_dy = self._group_drift_target_dy
            self._group_drift_arc_x = 0.0
            self._group_drift_arc_y = 0.0
        return (
            self._group_drift_dx + self._group_drift_arc_x,
            self._group_drift_dy + self._group_drift_arc_y,
        )

    def _overlaps_existing(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        candidate_is_big: bool,
        stream_dir: str = "none",
        candidate_vx: float = 0.0,
        candidate_vy: float = 0.0,
    ) -> bool:
        """Return True if (x, y, radius) overlaps any existing bubble."""
        for b in self._bubbles:
            existing_big = _bubble_behaves_big(b)
            if candidate_is_big and existing_big:
                min_gap = max(0.010, (radius + b.radius) * 0.10)
            elif candidate_is_big or existing_big:
                min_gap = 0.001
            else:
                min_gap = -min(radius, b.radius) * 0.10
            if candidate_is_big and existing_big and stream_dir not in {"none", "random"}:
                # Entry-lane guard: directional streams can otherwise spawn
                # big bubbles too close outside the viewport and they enter as
                # sticky overlap groups.
                min_gap = max(min_gap, (radius + b.radius) * 0.22 + 0.010)
            dist = math.hypot(b.x - x, b.y - y)
            if dist < b.radius + radius + min_gap:
                return True

            # Pre-entry lane guard: keep big bubbles from spawning into future
            # overlap when they are still outside the viewport.
            if candidate_is_big and existing_big and stream_dir not in {"none"}:
                cand_px, cand_py = self._predict_stream_position(
                    x,
                    y,
                    stream_dir,
                    vx=candidate_vx,
                    vy=candidate_vy,
                )
                existing_px, existing_py = self._predict_stream_position(
                    b.x,
                    b.y,
                    stream_dir,
                    vx=b.vx,
                    vy=b.vy,
                )
                future_gap = max(0.014, (radius + b.radius) * 0.16)
                if math.hypot(existing_px - cand_px, existing_py - cand_py) < (b.radius + radius + future_gap):
                    return True
        return False

    def _spawn_bubble_at(self, is_big: bool, x: float, y: float,
                         stream_dir: str, surface_reach: float,
                         drift_dir: str, *,
                         initial_fill: bool = False) -> None:
        if is_big:
            center = max(0.016, self._big_size_max)
            if initial_fill:
                lo = center * 0.82
                hi = center * 1.10
            else:
                lo = center * 0.68
                hi = center * 1.30
            radius = random.uniform(lo, hi)
        else:
            center = max(0.005, self._small_size_max)
            lo = center * 0.55
            hi = center * 1.45
            radius = random.uniform(lo, hi)

        # Per-bubble velocity for random stream direction.
        vx, vy = 0.0, 0.0
        if stream_dir == "random":
            rd = _random_direction()
            vx, vy = rd
        elif stream_dir == "diagonal":
            # Legacy compatibility for previously persisted single diagonal key.
            dv = random.choice(_DIAGONAL_STREAM_VECTORS)
            vx, vy = dv

        # Overlap prevention: retry up to 15 times with increasing jitter
        for _attempt in range(15):
            if not self._overlaps_existing(
                x,
                y,
                radius,
                candidate_is_big=is_big,
                stream_dir=stream_dir,
                candidate_vx=vx,
                candidate_vy=vy,
            ):
                break
            spread = 0.08 + _attempt * 0.015
            x = x + random.uniform(-spread, spread)
            y = y + random.uniform(-spread, spread)
            x = max(-0.25, min(1.25, x))
            y = max(-0.25, min(1.25, y))
        # If still overlapping after 15 attempts, skip spawn entirely
        else:
            return

        reaches = random.random() < surface_reach
        max_age = 999.0 if reaches else random.uniform(2.0, 8.0)
        phase = random.uniform(0.0, math.tau)

        # Drift bias
        if drift_dir == "random":
            drift_bias = random.uniform(-1.0, 1.0)
        elif drift_dir == "left":
            drift_bias = -0.7 + random.uniform(-0.3, 0.3)
        elif drift_dir == "right":
            drift_bias = 0.7 + random.uniform(-0.3, 0.3)
        elif drift_dir == "diagonal":
            drift_bias = 0.5 + random.uniform(-0.3, 0.3)
        elif drift_dir == "swish_horizontal":
            drift_bias = random.uniform(-0.9, 0.9)
        elif drift_dir == "swish_vertical":
            drift_bias = random.uniform(-0.9, 0.9)
        elif drift_dir in _SWIRL_DIRECTIONS:
            drift_bias = random.uniform(-1.0, 1.0)
        else:  # none
            drift_bias = random.uniform(-0.3, 0.3)

        if stream_dir in {"up", "down", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right", "diagonal"}:
            if is_big:
                speed_mult = random.uniform(0.90, 1.12)
            else:
                speed_mult = random.uniform(0.84, 1.18)
        else:
            speed_mult = 1.0

        # Initial fill or swirl: start transparent for fade-in
        age = 0.0
        alpha = 1.0
        if initial_fill:
            age = random.uniform(0.0, max_age * 0.3) if max_age < 900.0 else random.uniform(0.0, 3.0)
            alpha = 0.0  # will fade in via age-based ramp
        elif drift_dir in _SWIRL_DIRECTIONS:
            alpha = 0.0  # swirl bubbles fade in from center spawn

        # Per-bubble specular mutation: slight random variation so bubbles look distinct
        spec_size_mut = random.uniform(0.85, 1.2)
        spec_ox = random.uniform(-0.03, 0.03)
        spec_oy = random.uniform(-0.02, 0.02)

        b = BubbleState(
            x=x, y=y, radius=radius, is_big=is_big,
            reaches_surface=reaches, phase=phase,
            age=age, max_age=max_age, alpha=alpha,
            drift_bias=drift_bias, rotation=0.0,
            vx=vx, vy=vy, speed_mult=speed_mult,
            spec_size_mut=spec_size_mut, spec_ox=spec_ox, spec_oy=spec_oy,
            trail_tail_x=x, trail_tail_y=y,
        )
        self._bubbles.append(b)

    def _swirl_motion(
        self,
        bubble: BubbleState,
        drift_dir: str,
        drift_amount: float,
        drift_speed: float,
        dt: float,
        base_vel: float = 0.0,
    ) -> Tuple[float, float]:
        """Return (move_x, move_y) for expanding-spiral motion.

        **Coordinate convention**: the caller applies the returned values as
        ``b.x += move_x; b.y -= move_y`` (Y-inverted screen space).  All
        vector math here uses standard math-Y-up so that rotation formulas
        are correct, then flips ``out_y`` at the end to compensate for the
        caller's negation.

        Bubbles spawn near the center, trace an Archimedean spiral outward,
        and die when they leave the card bounds.

        *base_vel* is the audio-reactive travel speed (normalised units/sec)
        computed by the main tick loop.  It drives both angular velocity and
        radial push so the Stream Reactivity slider works in swirl mode.
        """
        # Vector from centre in screen space (0,0 = top-left).
        sx = bubble.x - 0.5
        sy = bubble.y - 0.5

        # Flip to math-Y-up for rotation math.
        mx =  sx
        my = -sy

        dist = math.hypot(mx, my)
        if dist < 1e-4:
            angle = random.uniform(0.0, math.tau)
            mx = math.cos(angle) * 0.01
            my = math.sin(angle) * 0.01
            dist = math.hypot(mx, my)

        inv = 1.0 / dist
        nx = mx * inv
        ny = my * inv

        # Tangent perpendicular to radial (standard math rotation).
        if drift_dir == "swirl_cw":
            tx =  ny
            ty = -nx
        else:
            tx = -ny
            ty =  nx

        swirl_drive = min(1.0, max(0.0, base_vel / 0.70))
        audio_mult = 0.30 + 1.20 * (swirl_drive ** 2.6)

        angular_speed = (0.16 + drift_amount * 0.42) * (0.35 + drift_speed * 0.75)
        per_bubble_var = 0.8 + 0.4 * abs(bubble.drift_bias)
        force = angular_speed * per_bubble_var * audio_mult

        out_x = tx * force
        out_y = ty * force

        radial_push = (0.018 + drift_amount * 0.055) * per_bubble_var * (0.40 + 1.05 * (swirl_drive ** 2.2))
        out_x += nx * radial_push
        out_y += ny * radial_push

        # Convert back: caller does b.x += move_x, b.y -= move_y,
        # so move_y = -screen_dy.  Since out_y is in math-Y-up and
        # screen_dy = -out_y, move_y = -(-out_y) = out_y.  No extra flip.
        return out_x * dt, out_y * dt

    def _bleed_trail_smear(self, b: BubbleState, dt: float) -> None:
        if b.trail_strength <= 0.0:
            b.trail_tail_x = b.x
            b.trail_tail_y = b.y
            b.trail_ready = False
            return
        decay = TRAIL_SMEAR_DECAY_PER_SEC * 3.0 * dt
        b.trail_strength = max(0.0, b.trail_strength - decay)
        if b.trail_strength <= 0.0:
            b.trail_tail_x = b.x
            b.trail_tail_y = b.y
            b.trail_ready = False

    def _log_overdrive_state(self, state: str, slider: float, gate: float) -> None:
        if not is_viz_diagnostics_enabled():
            return
        if state != "hold" and state == self._overdrive_last_log_state:
            return
        logger.debug(
            "[SPOTIFY_VIS][BUBBLE][OVERDRIVE] state=%s react=%.2f gate=%.2f",
            state,
            slider,
            gate,
        )
        self._overdrive_last_log_state = state

    def _update_trail_smear(self, b: BubbleState, dt: float,
                             move_dx: float, move_dy: float) -> None:
        if b.popping:
            self._bleed_trail_smear(b, dt)
            return

        if not b.trail_ready:
            init_len = min(TRAIL_SMEAR_MAX_LENGTH,
                           math.hypot(move_dx, move_dy) * 22.0)
            if init_len > 1e-4:
                mv = math.hypot(move_dx, move_dy)
                inv = 1.0 / mv if mv > 1e-4 else 0.0
                dir_x = move_dx * inv
                dir_y = move_dy * inv
                b.trail_tail_x = b.x - dir_x * init_len
                b.trail_tail_y = b.y - dir_y * init_len
            else:
                b.trail_tail_x = b.x
                b.trail_tail_y = b.y
            b.trail_ready = True

        dx = b.x - b.trail_tail_x
        dy = b.y - b.trail_tail_y
        dist = math.hypot(dx, dy)
        if dist > TRAIL_SMEAR_MAX_LENGTH and dist > 1e-4:
            excess = dist - TRAIL_SMEAR_MAX_LENGTH
            shrink = excess / dist
            b.trail_tail_x += dx * shrink
            b.trail_tail_y += dy * shrink
            dx = b.x - b.trail_tail_x
            dy = b.y - b.trail_tail_y
            dist = TRAIL_SMEAR_MAX_LENGTH

        follow = min(TRAIL_SMEAR_FOLLOW_MAX, TRAIL_SMEAR_FOLLOW_RATE * dt)
        b.trail_tail_x += dx * follow
        b.trail_tail_y += dy * follow

        dx = b.x - b.trail_tail_x
        dy = b.y - b.trail_tail_y
        dist = math.hypot(dx, dy)

        target_strength = min(1.0, dist * TRAIL_SMEAR_STRENGTH_FROM_DISTANCE)
        if target_strength > b.trail_strength:
            attack = min(1.0, dt * 9.0)
            b.trail_strength += (target_strength - b.trail_strength) * attack
        else:
            decay = TRAIL_SMEAR_DECAY_PER_SEC * dt
            b.trail_strength = max(0.0, b.trail_strength - decay)

    def snapshot(self, bass: float = 0.0, mid_high: float = 0.0,
                 big_bass_pulse: float = 0.5,
                 small_freq_pulse: float = 0.5,
                 big_specular_max_size: float = 2.5,
                 big_visual_smoothing: float = 0.5,
                 big_contraction_bias: float = 1.0,
                 big_size_clamp: float = 4.0) -> Tuple[List[float], List[float], List[float]]:
        """Return flat lists for uniform upload.

        Returns:
            pos_data:   [x, y, radius, alpha] × count (vec4 per bubble)
            extra_data: [spec_size_factor, rotation, spec_ox, spec_oy] × count (vec4 per bubble)
            trail_data: [tail.xy,str, mid.xy,str, head.xy,str] × count representing smear streak samples
        """
        snap_start = time.perf_counter()
        bubble_count = len(self._bubbles)
        trail_payload_active = any(
            b.trail_strength > 0.001 and b.trail_ready
            for b in self._bubbles
        )
        pos_data: List[float] = [0.0] * (bubble_count * 4)
        extra_data: List[float] = [0.0] * (bubble_count * 4)
        trail_data: List[float] = [0.0] * (bubble_count * 9) if trail_payload_active else []
        _snap_diag = (self._diag_tick_count <= 5 or self._diag_tick_count % 60 == 0)
        big_render_diag = {
            "big_render_count": 0.0,
            "big_clamp_hits": 0.0,
            "max_big_render_radius": 0.0,
            "max_big_render_delta": 0.0,
            "avg_big_render_radius": 0.0,
        }

        for idx, b in enumerate(self._bubbles):
            # Pulse: smoothed energy drives visible size thump.
            # Multipliers: big 4.0x, small 3.0x at max slider (slider 0-1).
            # Small bubbles below tiny threshold: suppress pulse to avoid
            # flicker between dot and outline rendering.
            big_hold_boost, big_crest_boost = self._compute_big_render_boosts(b)
            if b.is_big:
                pulse_factor = self._big_render_pulse_factor(
                    b.pulse_energy,
                    gate_energy=b.size_gate_energy,
                    big_bass_pulse=big_bass_pulse,
                    big_hold_boost=big_hold_boost,
                    big_crest_boost=big_crest_boost,
                )
            else:
                pulse_factor = self._small_render_pulse_factor(
                    b,
                    small_freq_pulse=small_freq_pulse,
                )

            target_radius = b.radius * pulse_factor

            # Contraction bias: during quiet passages (low pulse_energy),
            # big bubbles shrink slightly below base radius.  bias=1.0 means
            # no contraction; bias<1.0 contracts proportionally.
            if b.is_big and big_contraction_bias < 1.0:
                quiet = 1.0 - min(1.0, b.pulse_energy)
                quiet_curve = quiet ** 0.85
                shrink = 1.0 - (1.0 - big_contraction_bias) * quiet_curve * 0.70
                target_radius *= max(0.60, shrink)

            # Max size clamp: cap the pulsed radius to base_radius * clamp
            if b.is_big and big_size_clamp > 0.0:
                clamp_limit = self._resolve_big_clamp_limit(b.radius, big_size_clamp)
                if target_radius >= clamp_limit - 1e-5:
                    big_render_diag["big_clamp_hits"] += 1.0
                target_radius = min(target_radius, clamp_limit)

            r = self._apply_big_display_radius_smoothing(
                b,
                max(0.001, target_radius),
                big_visual_smoothing,
            )

            if b.is_big:
                big_render_diag["big_render_count"] += 1.0
                big_render_diag["max_big_render_radius"] = max(big_render_diag["max_big_render_radius"], r)
                big_render_diag["max_big_render_delta"] = max(
                    big_render_diag["max_big_render_delta"],
                    max(0.0, r - b.radius),
                )
                big_render_diag["avg_big_render_radius"] += r

            # Specular size should follow the rendered bubble radius itself.
            # Let pulse make the bubble larger, but do not let specular size
            # double-count that growth or a few bubbles will balloon far beyond
            # the intended relative highlight size.
            spec_growth = min(0.14, max(0.0, pulse_factor - 1.0) * 0.085)
            if b.is_big:
                big_size_authority = _clamp01((r - 0.024) / 0.020)
                spec_growth += big_size_authority * 0.055
            spec_factor = b.spec_size_mut + spec_growth
            spec_cap = 1.32
            if b.is_big:
                spec_cap = min(spec_cap, big_specular_max_size)
            spec_factor = min(spec_factor, spec_cap)

            pos_base = idx * 4
            pos_data[pos_base] = b.x
            pos_data[pos_base + 1] = b.y
            pos_data[pos_base + 2] = r
            pos_data[pos_base + 3] = b.alpha
            extra_data[pos_base] = spec_factor
            extra_data[pos_base + 1] = b.rotation
            extra_data[pos_base + 2] = b.spec_ox
            extra_data[pos_base + 3] = b.spec_oy

            # Smear trail: emit interpolated samples from tail -> head
            if trail_payload_active and b.trail_strength > 0.001 and b.trail_ready:
                dx = b.x - b.trail_tail_x
                dy = b.y - b.trail_tail_y
                trail_base = idx * 9
                for step in range(TRAIL_STEPS):
                    if TRAIL_STEPS > 1:
                        seg_t = float(step) / float(TRAIL_STEPS - 1)
                    else:
                        seg_t = 1.0
                    sample_x = b.trail_tail_x + dx * seg_t
                    sample_y = b.trail_tail_y + dy * seg_t
                    falloff = 0.45 + 0.55 * seg_t
                    step_base = trail_base + step * 3
                    trail_data[step_base] = sample_x
                    trail_data[step_base + 1] = sample_y
                    trail_data[step_base + 2] = b.trail_strength * falloff

        if big_render_diag["big_render_count"] > 0.0:
            big_render_diag["avg_big_render_radius"] /= big_render_diag["big_render_count"]
        self._last_big_render_diag = big_render_diag

        # Diagnostic: log first big bubble's pulse details
        if _snap_diag and self._bubbles and is_verbose_logging():
            fb = next((b for b in self._bubbles if b.is_big), self._bubbles[0])
            if fb.is_big:
                hold_boost, crest_boost = self._compute_big_render_boosts(fb)
                pf = self._big_render_pulse_factor(
                    fb.pulse_energy,
                    gate_energy=fb.size_gate_energy,
                    big_bass_pulse=big_bass_pulse,
                    big_hold_boost=hold_boost,
                    big_crest_boost=crest_boost,
                )
            else:
                pf = 1.0 + fb.pulse_energy * small_freq_pulse * 3.0
            logger.debug(
                "[BUBBLE_SIM] snapshot: big_bass_pulse=%.2f small_freq_pulse=%.2f "
                "first_big: pe=%.3f pf=%.3f base_r=%.4f final_r=%.4f",
                big_bass_pulse, small_freq_pulse,
                fb.pulse_energy, pf, fb.radius, fb.radius * pf,
            )

        perf_diag = dict(self._last_perf_diag)
        perf_diag.update(
            {
                "snapshot_ms": (time.perf_counter() - snap_start) * 1000.0,
                "snapshot_trail_payload_active": 1.0 if trail_payload_active else 0.0,
                "snapshot_trail_floats": float(len(trail_data)),
                "snapshot_pos_floats": float(len(pos_data)),
                "snapshot_extra_floats": float(len(extra_data)),
            }
        )
        self._last_perf_diag = perf_diag
        return pos_data, extra_data, trail_data
