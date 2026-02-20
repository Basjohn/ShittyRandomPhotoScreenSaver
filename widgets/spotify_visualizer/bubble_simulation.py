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
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.logging.logger import get_logger

logger = get_logger(__name__)

MAX_BUBBLES = 110


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


# Direction vectors for stream directions
_DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "none": (0.0, 0.0),
    "up": (0.0, 1.0),
    "down": (0.0, -1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "diagonal": (0.707, 0.707),
}


def _random_direction() -> Tuple[float, float]:
    angle = random.uniform(0.0, math.tau)
    return (math.cos(angle), math.sin(angle))


def _get_stream_vector(direction: str) -> Tuple[float, float]:
    if direction == "random":
        return _random_direction()
    return _DIRECTION_VECTORS.get(direction, (0.0, 1.0))


def _spawn_position(direction: str, is_big: bool) -> Tuple[float, float]:
    """Spawn at the opposite edge of the stream direction."""
    margin = 0.05 if is_big else 0.02
    if direction == "up":
        return (random.uniform(margin, 1.0 - margin), -margin)
    elif direction == "down":
        return (random.uniform(margin, 1.0 - margin), 1.0 + margin)
    elif direction == "left":
        return (1.0 + margin, random.uniform(margin, 1.0 - margin))
    elif direction == "right":
        return (-margin, random.uniform(margin, 1.0 - margin))
    elif direction == "diagonal":
        # Spawn at bottom-left edge
        if random.random() < 0.5:
            return (-margin, random.uniform(0.3, 1.0 + margin))
        else:
            return (random.uniform(-margin, 0.7), 1.0 + margin)
    elif direction == "none":
        return (random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))
    else:  # random
        return (random.uniform(0.1, 0.9), random.uniform(0.1, 0.9))


class BubbleSimulation:
    """Lightweight bubble particle system."""

    def __init__(self) -> None:
        self._bubbles: List[BubbleState] = []
        self._time: float = 0.0

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

        # Effective speed with reactivity
        effective_speed = stream_speed * (1.0 - stream_reactivity + stream_reactivity * overall)
        base_vel = effective_speed * 0.15  # normalised units/sec

        # --- Update existing bubbles ---
        to_remove: List[int] = []
        for i, b in enumerate(self._bubbles):
            b.age += dt

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
            sv = _get_stream_vector(stream_dir) if stream_dir != "random" else (b.vx, b.vy)
            if stream_dir == "random" and b.vx == 0.0 and b.vy == 0.0:
                rd = _random_direction()
                b.vx, b.vy = rd

            move_x = (sv[0] if stream_dir != "random" else b.vx) * base_vel * dt
            move_y = (sv[1] if stream_dir != "random" else b.vy) * base_vel * dt

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

        while big_count < big_target and len(self._bubbles) < MAX_BUBBLES:
            self._spawn_bubble(True, stream_dir, surface_reach, drift_dir)
            big_count += 1

        while small_count < small_target and len(self._bubbles) < MAX_BUBBLES:
            # Cluster spawning: 20% chance to spawn 2-3 near each other
            cluster = random.random() < 0.2
            count = random.randint(2, 3) if cluster else 1
            base_x, base_y = _spawn_position(stream_dir, False)
            for c in range(count):
                if small_count >= small_target or len(self._bubbles) >= MAX_BUBBLES:
                    break
                cx = base_x + (random.uniform(-0.03, 0.03) if c > 0 else 0.0)
                cy = base_y + (random.uniform(-0.03, 0.03) if c > 0 else 0.0)
                self._spawn_bubble_at(False, cx, cy, stream_dir, surface_reach, drift_dir)
                small_count += 1

    def _spawn_bubble(self, is_big: bool, stream_dir: str,
                      surface_reach: float, drift_dir: str) -> None:
        x, y = _spawn_position(stream_dir, is_big)
        self._spawn_bubble_at(is_big, x, y, stream_dir, surface_reach, drift_dir)

    def _spawn_bubble_at(self, is_big: bool, x: float, y: float,
                         stream_dir: str, surface_reach: float,
                         drift_dir: str) -> None:
        if is_big:
            radius = random.uniform(0.025, 0.055)
        else:
            radius = random.uniform(0.005, 0.018)

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

        # Random initial velocity for "random" stream direction
        vx, vy = 0.0, 0.0
        if stream_dir == "random":
            rd = _random_direction()
            vx, vy = rd

        b = BubbleState(
            x=x, y=y, radius=radius, is_big=is_big,
            reaches_surface=reaches, phase=phase,
            age=0.0, max_age=max_age, alpha=1.0,
            drift_bias=drift_bias, rotation=0.0,
            vx=vx, vy=vy,
        )
        self._bubbles.append(b)

    def snapshot(self, bass: float = 0.0, mid_high: float = 0.0,
                 big_bass_pulse: float = 0.5,
                 small_freq_pulse: float = 0.5) -> Tuple[List[float], List[float]]:
        """Return flat lists for uniform upload.

        Returns:
            pos_data: [x, y, radius, alpha, ...] × count (vec4 per bubble)
            extra_data: [specular_size_factor, rotation, ...] × count (vec2 per bubble)
        """
        pos_data: List[float] = []
        extra_data: List[float] = []

        for b in self._bubbles:
            # Pulse: big bubbles pulse to bass, small to mid/high
            if b.is_big:
                pulse_factor = 1.0 + bass * big_bass_pulse * 0.3
            else:
                pulse_factor = 1.0 + mid_high * small_freq_pulse * 0.2

            r = b.radius * pulse_factor

            # Specular size scales with pulse
            spec_factor = pulse_factor

            pos_data.extend([b.x, b.y, r, b.alpha])
            extra_data.extend([spec_factor, b.rotation])

        return pos_data, extra_data
