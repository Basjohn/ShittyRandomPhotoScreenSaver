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
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)

MAX_BUBBLES = 110


TRAIL_STEPS = 3  # number of ghost trail positions stored per bubble


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
    popping: bool = False
    pop_timer: float = 0.0
    pulse_energy: float = 0.0  # smoothed energy for size pulse (attack fast, decay slow)
    spec_size_mut: float = 1.0   # per-bubble specular size mutation (0.7–1.4)
    spec_ox: float = 0.0         # per-bubble specular offset X mutation (-0.08..0.08)
    spec_oy: float = 0.0         # per-bubble specular offset Y mutation (-0.08..0.08)
    trail: List[Tuple[float, float]] = field(default_factory=list)  # previous (x, y) positions


# Direction vectors for stream directions
_DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "none": (0.0, 0.0),
    "up": (0.0, 1.0),
    "down": (0.0, -1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "diagonal": (0.707, 0.707),  # placeholder; actual direction chosen per-spawn
}

_DIAGONAL_VECTORS: Tuple[Tuple[float, float], ...] = (
    ( 0.707,  0.707),  # up-right
    (-0.707,  0.707),  # up-left
    ( 0.707, -0.707),  # down-right
    (-0.707, -0.707),  # down-left
)


def _random_direction() -> Tuple[float, float]:
    angle = random.uniform(0.0, math.tau)
    return (math.cos(angle), math.sin(angle))


def _get_stream_vector(direction: str) -> Tuple[float, float]:
    if direction == "random":
        return _random_direction()
    if direction == "diagonal":
        return random.choice(_DIAGONAL_VECTORS)
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
    elif direction == "diagonal":
        # Pick a random diagonal; spawn at the opposite corner/edge
        diag = random.choice(_DIAGONAL_VECTORS)
        dx, dy = diag
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


class BubbleSimulation:
    """Lightweight bubble particle system."""

    def __init__(self) -> None:
        self._bubbles: List[BubbleState] = []
        self._time: float = 0.0
        self._big_size_max: float = 0.038
        self._small_size_max: float = 0.018
        self._diag_tick_count: int = 0
        self._smoothed_speed_energy: float = 0.0  # smoothed bass for travel speed reactivity
        self._trail_accumulator: float = 0.0  # time accumulator for trail sampling

    @property
    def count(self) -> int:
        return len(self._bubbles)

    def tick(self, dt: float, energy_bands: Optional[object], settings: Dict) -> None:
        """Advance simulation by *dt* seconds."""
        if dt <= 0.0 or dt > 1.0:
            return

        self._time += dt

        # Read settings
        big_target = int(settings.get("bubble_big_count", 8))
        small_target = int(settings.get("bubble_small_count", 25))
        surface_reach = float(settings.get("bubble_surface_reach", 0.6))
        stream_dir = str(settings.get("bubble_stream_direction", "up"))
        stream_speed = float(settings.get("bubble_stream_speed", 1.0))
        stream_reactivity = float(settings.get("bubble_stream_reactivity", 0.5))
        rotation_amount = float(settings.get("bubble_rotation_amount", 0.5))
        drift_amount = float(settings.get("bubble_drift_amount", 0.5))
        drift_speed = float(settings.get("bubble_drift_speed", 0.5))
        drift_freq = float(settings.get("bubble_drift_frequency", 0.5))
        drift_dir = str(settings.get("bubble_drift_direction", "random"))
        self._big_size_max = float(settings.get("bubble_big_size_max", 0.038))
        self._small_size_max = float(settings.get("bubble_small_size_max", 0.018))
        trail_strength = float(settings.get("bubble_trail_strength", 0.0))
        # big_bass_pulse / small_freq_pulse are read in snapshot(), not tick()

        # Energy — accept both object (EnergyBands) and dict snapshots
        if energy_bands is None:
            bass = mid = high = overall = 0.0
        elif isinstance(energy_bands, dict):
            bass = float(energy_bands.get('bass', 0.0))
            mid = float(energy_bands.get('mid', 0.0))
            high = float(energy_bands.get('high', 0.0))
            overall = float(energy_bands.get('overall', 0.0))
        else:
            bass = getattr(energy_bands, 'bass', 0.0)
            mid = getattr(energy_bands, 'mid', 0.0)
            high = getattr(energy_bands, 'high', 0.0)
            overall = getattr(energy_bands, 'overall', 0.0)

        # Diagnostic: log energy values. First 10 ticks at INFO level, then every 60.
        self._diag_tick_count += 1
        if self._diag_tick_count <= 10 or self._diag_tick_count % 60 == 0:
            # Find max pulse_energy among existing bubbles
            max_pe = max((b.pulse_energy for b in self._bubbles), default=0.0)
            logger.info(
                "[BUBBLE_SIM] tick=%d dt=%.3f bass=%.3f mid=%.3f overall=%.3f "
                "bubbles=%d max_pe=%.3f spd_e=%.3f speed=%.2f react=%.2f",
                self._diag_tick_count, dt, bass, mid, overall,
                len(self._bubbles), max_pe, self._smoothed_speed_energy,
                stream_speed, stream_reactivity,
            )

        # Travel speed uses SMOOTHED mid/high so it flows with the melody.
        # Raw mid/high would jerk on every transient.
        smooth_mid = float(energy_bands.get('smooth_mid', mid)) if isinstance(energy_bands, dict) else mid
        smooth_high = float(energy_bands.get('smooth_high', high)) if isinstance(energy_bands, dict) else high
        vocal_speed = smooth_mid * 0.7 + smooth_high * 0.3
        if vocal_speed > self._smoothed_speed_energy:
            self._smoothed_speed_energy += (vocal_speed - self._smoothed_speed_energy) * min(1.0, dt * 18.0)
        else:
            self._smoothed_speed_energy += (vocal_speed - self._smoothed_speed_energy) * min(1.0, dt * 1.5)
        # At max reactivity: speed ranges from 0.15x (silence) to 1.0x (loud vocal).
        # At zero reactivity: speed is constant at stream_speed.
        speed_energy = min(1.0, self._smoothed_speed_energy)
        speed_scale = (1.0 - stream_reactivity) + stream_reactivity * (0.15 + 0.85 * speed_energy)
        effective_speed = stream_speed * speed_scale
        base_vel = effective_speed * 0.35  # normalised units/sec

        # --- Update existing bubbles ---
        to_remove: List[int] = []
        for i, b in enumerate(self._bubbles):
            b.age += dt

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
                if b.pop_timer < 0.1:
                    # Expand phase
                    b.radius += b.radius * 0.2 * (dt / 0.1)
                elif b.pop_timer < 0.25:
                    # Fade phase
                    b.alpha = max(0.0, b.alpha - dt / 0.15)
                else:
                    b.alpha = 0.0

                if b.alpha <= 0.01:
                    to_remove.append(i)
                    continue

            # Stream velocity
            use_stored = stream_dir in ("random", "diagonal")
            sv = _get_stream_vector(stream_dir) if not use_stored else (b.vx, b.vy)
            if use_stored and b.vx == 0.0 and b.vy == 0.0:
                if stream_dir == "diagonal":
                    dv = random.choice(_DIAGONAL_VECTORS)
                    b.vx, b.vy = dv
                else:
                    rd = _random_direction()
                    b.vx, b.vy = rd
                sv = (b.vx, b.vy)

            move_x = sv[0] * base_vel * dt
            move_y = sv[1] * base_vel * dt

            # Drift (sinusoidal lateral wander)
            drift_phase = b.phase + self._time * drift_speed * 2.0
            drift_noise = math.sin(drift_phase * (1.0 + drift_freq * 3.0))
            drift_bias_val = b.drift_bias * drift_amount * 0.05
            drift_offset = drift_noise * drift_amount * 0.03 + drift_bias_val

            # Apply drift perpendicular to stream direction
            if abs(sv[0]) > abs(sv[1]) if stream_dir != "random" else True:
                move_y += drift_offset * dt
            else:
                move_x += drift_offset * dt

            b.x += move_x
            b.y -= move_y  # Y is inverted in UV space (0=top, 1=bottom)

            # Record trail position (sampled every ~80ms)
            if trail_strength > 0.001 and not b.popping:
                b.trail.append((b.x, b.y))
                if len(b.trail) > TRAIL_STEPS:
                    b.trail.pop(0)

            # Pulse energy: smooth per-bubble energy for visible beat-sync thump.
            raw_energy = bass if b.is_big else (mid * 0.6 + high * 0.4)
            raw_energy = min(1.0, max(0.0, raw_energy))
            # Small bubbles below ~6px rendered radius flicker between dot and
            # outline when pulsing rapidly.  Use much slower decay for them.
            is_tiny = (not b.is_big) and b.radius < 0.008
            if raw_energy > b.pulse_energy:
                # Fast attack: ramp up in ~80ms (dt*12)
                b.pulse_energy += (raw_energy - b.pulse_energy) * min(1.0, dt * 12.0)
            else:
                # Decay: fast for big/normal, very slow for tiny to avoid flicker
                decay_rate = 1.2 if is_tiny else 4.0
                b.pulse_energy += (raw_energy - b.pulse_energy) * min(1.0, dt * decay_rate)

            # Rotation (wobble)
            vocal_energy = mid * 0.7 + bass * 0.2 + high * 0.1
            b.rotation += vocal_energy * rotation_amount * 2.0 * dt

            # Check if bubble exited the card
            margin = 0.1
            if (b.x < -margin or b.x > 1.0 + margin or
                    b.y < -margin or b.y > 1.0 + margin):
                if b.reaches_surface:
                    to_remove.append(i)

        # Remove dead bubbles (reverse order)
        for i in sorted(to_remove, reverse=True):
            if i < len(self._bubbles):
                self._bubbles.pop(i)

        # --- Spawn new bubbles to maintain targets ---
        big_count = sum(1 for b in self._bubbles if b.is_big)
        small_count = sum(1 for b in self._bubbles if not b.is_big)

        is_initial = self._time < 0.5
        while big_count < big_target and len(self._bubbles) < MAX_BUBBLES:
            if is_initial:
                bx = random.uniform(0.08, 0.92)
                by = random.uniform(0.08, 0.92)
                self._spawn_bubble_at(True, bx, by, stream_dir, surface_reach, drift_dir,
                                      initial_fill=True)
            else:
                self._spawn_bubble(True, stream_dir, surface_reach, drift_dir)
            big_count += 1

        while small_count < small_target and len(self._bubbles) < MAX_BUBBLES:
            # Cluster spawning: 20% chance to spawn 2-3 near each other
            is_initial = self._time < 0.5
            cluster = random.random() < 0.2
            count = random.randint(2, 3) if cluster else 1
            if is_initial:
                # First fill: scatter across card area
                base_x = random.uniform(0.05, 0.95)
                base_y = random.uniform(0.05, 0.95)
            else:
                base_x, base_y = _spawn_position(stream_dir, False)
            for c in range(count):
                if small_count >= small_target or len(self._bubbles) >= MAX_BUBBLES:
                    break
                cx = base_x + (random.uniform(-0.07, 0.07) if c > 0 else 0.0)
                cy = base_y + (random.uniform(-0.07, 0.07) if c > 0 else 0.0)
                self._spawn_bubble_at(False, cx, cy, stream_dir, surface_reach, drift_dir,
                                      initial_fill=is_initial)
                small_count += 1

    def _spawn_bubble(self, is_big: bool, stream_dir: str,
                      surface_reach: float, drift_dir: str) -> None:
        x, y = _spawn_position(stream_dir, is_big)
        self._spawn_bubble_at(is_big, x, y, stream_dir, surface_reach, drift_dir)

    def _overlaps_existing(self, x: float, y: float, radius: float,
                            min_gap: float = 0.018) -> bool:
        """Return True if (x, y, radius) overlaps any existing bubble."""
        for b in self._bubbles:
            dist = math.hypot(b.x - x, b.y - y)
            if dist < b.radius + radius + min_gap:
                return True
        return False

    def _spawn_bubble_at(self, is_big: bool, x: float, y: float,
                         stream_dir: str, surface_reach: float,
                         drift_dir: str, *,
                         initial_fill: bool = False) -> None:
        if is_big:
            radius = random.uniform(0.015, max(0.016, self._big_size_max))
        else:
            radius = random.uniform(0.004, max(0.005, self._small_size_max))

        # Overlap prevention: retry up to 15 times with increasing jitter
        for _attempt in range(15):
            if not self._overlaps_existing(x, y, radius):
                break
            spread = 0.08 + _attempt * 0.015
            x = x + random.uniform(-spread, spread)
            y = y + random.uniform(-spread, spread)
            x = max(-0.05, min(1.05, x))
            y = max(-0.05, min(1.05, y))
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
        else:  # none
            drift_bias = random.uniform(-0.3, 0.3)

        # Per-bubble velocity for random and diagonal stream directions
        vx, vy = 0.0, 0.0
        if stream_dir == "random":
            rd = _random_direction()
            vx, vy = rd
        elif stream_dir == "diagonal":
            dv = random.choice(_DIAGONAL_VECTORS)
            vx, vy = dv

        # Initial fill: pre-age and start transparent for fade-in
        age = 0.0
        alpha = 1.0
        if initial_fill:
            age = random.uniform(0.0, max_age * 0.3) if max_age < 900.0 else random.uniform(0.0, 3.0)
            alpha = 0.0  # will fade in via age-based ramp

        # Per-bubble specular mutation: slight random variation so bubbles look distinct
        spec_size_mut = random.uniform(0.85, 1.2)
        spec_ox = random.uniform(-0.03, 0.03)
        spec_oy = random.uniform(-0.02, 0.02)

        b = BubbleState(
            x=x, y=y, radius=radius, is_big=is_big,
            reaches_surface=reaches, phase=phase,
            age=age, max_age=max_age, alpha=alpha,
            drift_bias=drift_bias, rotation=0.0,
            vx=vx, vy=vy,
            spec_size_mut=spec_size_mut, spec_ox=spec_ox, spec_oy=spec_oy,
        )
        self._bubbles.append(b)

    def snapshot(self, bass: float = 0.0, mid_high: float = 0.0,
                 big_bass_pulse: float = 0.5,
                 small_freq_pulse: float = 0.5) -> Tuple[List[float], List[float], List[float]]:
        """Return flat lists for uniform upload.

        Returns:
            pos_data:   [x, y, radius, alpha] × count (vec4 per bubble)
            extra_data: [spec_size_factor, rotation, spec_ox, spec_oy] × count (vec4 per bubble)
            trail_data: [x0,y0, x1,y1, x2,y2] × count (TRAIL_STEPS xy pairs per bubble, 0,0 if no history)
        """
        pos_data: List[float] = []
        extra_data: List[float] = []
        trail_data: List[float] = []
        _snap_diag = (self._diag_tick_count <= 5 or self._diag_tick_count % 60 == 0)

        for b in self._bubbles:
            # Pulse: smoothed energy drives visible size thump.
            # Multipliers: big 4.0x, small 3.0x at max slider (slider 0-1).
            # Small bubbles below tiny threshold: suppress pulse to avoid
            # flicker between dot and outline rendering.
            is_tiny = (not b.is_big) and b.radius < 0.008
            if b.is_big:
                pulse_factor = 1.0 + b.pulse_energy * big_bass_pulse * 4.0
            elif is_tiny:
                # Tiny bubbles: minimal pulse to avoid dot/outline flicker
                pulse_factor = 1.0 + b.pulse_energy * small_freq_pulse * 0.5
            else:
                pulse_factor = 1.0 + b.pulse_energy * small_freq_pulse * 3.0

            r = b.radius * pulse_factor

            # Specular pulses at slightly less than half the bubble outline rate.
            # Base specular size (spec_size_mut) is unchanged; only the
            # pulse-driven delta is scaled (0.475 = half rate minus 5%).
            spec_pulse = (pulse_factor - 1.0) * 0.475
            spec_factor = b.spec_size_mut * (1.0 + spec_pulse)

            pos_data.extend([b.x, b.y, r, b.alpha])
            extra_data.extend([spec_factor, b.rotation, b.spec_ox, b.spec_oy])

            # Trail: emit TRAIL_STEPS (x, y) pairs; pad with (0, 0) if no history yet
            trail = b.trail
            for step in range(TRAIL_STEPS):
                idx = len(trail) - TRAIL_STEPS + step
                if idx >= 0 and idx < len(trail):
                    trail_data.extend([trail[idx][0], trail[idx][1]])
                else:
                    trail_data.extend([b.x, b.y])

        # Diagnostic: log first big bubble's pulse details
        if _snap_diag and self._bubbles:
            fb = next((b for b in self._bubbles if b.is_big), self._bubbles[0])
            pf = 1.0 + fb.pulse_energy * (big_bass_pulse if fb.is_big else small_freq_pulse) * (4.0 if fb.is_big else 3.0)
            logger.info(
                "[BUBBLE_SIM] snapshot: big_bass_pulse=%.2f small_freq_pulse=%.2f "
                "first_big: pe=%.3f pf=%.3f base_r=%.4f final_r=%.4f",
                big_bass_pulse, small_freq_pulse,
                fb.pulse_energy, pf, fb.radius, fb.radius * pf,
            )

        return pos_data, extra_data, trail_data
