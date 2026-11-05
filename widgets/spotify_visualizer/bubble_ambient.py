"""Opt-in, bounded visual-only specks and microbubble streams for 2D Bubble.

This is deliberately *not* a second Bubble simulation. It owns no collisions,
hero positions, random globals, reactivity ingress or clock: it advances only
when the authoritative BubbleFrameRuntime advances. Stream velocity comes from
the existing Bubble solver, and particle *glow*, never size, follows the
already-resolved small-bubble breathing response.

Positions are card fractions, but every authored distance and speed is in the
hero world's canonical-card units (``BubbleWorld``), so decor moves alike on
every card shape; only its count follows the card's area.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Mapping

MAX_MICROBUBBLES = 96
MAX_PARTICLES = 96
RECORD_STRIDE = 6  # normalized x/y, point diameter px, alpha, glow, kind

# Match Bubble's authored cardinal/diagonal stream vocabulary. This layer
# deliberately uses its own RNG, so changing density never reshuffles Bubble.
_DIRECTIONS = {
    "none": (0.0, 0.0), "up": (0.0, 1.0), "down": (0.0, -1.0),
    "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "top_left": (-0.70710678, 0.70710678),
    "top_right": (0.70710678, 0.70710678),
    "bottom_left": (-0.70710678, -0.70710678),
    "bottom_right": (0.70710678, -0.70710678),
}


def _unit(value: object) -> float:
    return max(0.0, min(1.0, float(value)))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass(slots=True)
class _Dot:
    x: float
    y: float
    size_factor: float
    phase: float
    speed_factor: float
    opacity: float
    tangent: tuple[float, float]
    # Deterministic within-chain offsets for live clump -> column sculpting.
    column_dx: float = 0.0
    column_dy: float = 0.0


class BubbleAmbientSimulation:
    """Independently seeded layers with strictly optional CPU/GPU work."""

    def __init__(self) -> None:
        self._micro_rng = random.Random(0xB0B1E5)
        self._particle_rng = random.Random(0xA38F03)
        self._micro: list[_Dot] = []
        self._particles: list[_Dot] = []
        self._time = 0.0
        self._glow_envelope = 0.0
        self._micro_columnarity = 0.0

    def reset(self) -> None:
        self.__init__()

    @staticmethod
    def enabled(settings: Mapping[str, object]) -> bool:
        return any(bool(settings.get(name, False)) for name in (
            "bubble_microbubble_stream", "bubble_microbubble_drift",
            "bubble_particle_stream", "bubble_particle_drift", "bubble_particle_glow",
        ))

    @staticmethod
    def _populate(
        pool: list[_Dot], rng: random.Random, count: int, *,
        chained: bool, columnarity: float = 0.0,
        domain: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        if len(pool) > count:
            del pool[count:]
        columnarity = _unit(columnarity)
        # Seed short offset chains in independently randomized stream locations.
        # Keep the *same* RNG draw sequence regardless of the column slider.
        # Per-bead adjustment derivatives let existing chains morph in place
        # when the slider moves, rather than resetting/teleporting the field.
        while len(pool) < count:
            index = len(pool)
            column_dx = column_dy = 0.0
            if chained and index % 8 and pool:
                previous = pool[-1]
                horizontal_step = rng.uniform(-0.020, 0.020)
                vertical_seed = rng.random()
                vertical_clump = -0.027 + vertical_seed * 0.045
                vertical_column = -0.052 + vertical_seed * 0.0565
                column_dx = previous.column_dx - horizontal_step * 0.825
                column_dy = previous.column_dy + vertical_column - vertical_clump
                x = previous.x + horizontal_step * (1.0 - 0.825 * columnarity) / domain[0]
                y = previous.y + _lerp(vertical_clump, vertical_column, columnarity) / domain[1]
            else:
                x = rng.uniform(0.07, 0.93)
                y = rng.uniform(0.07, 0.93)
            angle = rng.uniform(0.0, math.tau)
            pool.append(_Dot(
                x=x % 1.0, y=y % 1.0,
                size_factor=rng.uniform(0.62, 1.25),
                phase=angle,
                speed_factor=rng.uniform(0.86, 1.16),
                opacity=rng.uniform(0.46, 0.92),
                tangent=(math.cos(angle), math.sin(angle)),
                column_dx=column_dx, column_dy=column_dy,
            ))

    @staticmethod
    def _advance_pool(
        pool: list[_Dot], dt: float, *, velocity: float,
        stream: bool, drift: bool, stream_direction: str,
        drift_direction: str, drift_amount: float, drift_speed: float,
        drift_frequency: float, time_s: float, direction_mode: str,
        group_motion: tuple[float, float, float] = (0.0, 0.0, 0.0),
        domain: tuple[float, float] = (1.0, 1.0),
    ) -> None:
        if not (stream or drift) or dt <= 0.0:
            return
        vector = _DIRECTIONS.get(stream_direction, (0.0, 0.0))
        has_group_motion = drift and any(abs(component) > 1e-12 for component in group_motion)
        # Slice 3 accidentally produced the opposite transport from Bubble's
        # visible motion. Correct that as the "same" default and preserve the
        # old accidental look as the explicit "reversed" stylistic option.
        motion_sign = -1.0 if direction_mode == "same" else 1.0
        domain_w, domain_h = domain
        for dot in pool:
            vx, vy = vector
            if stream_direction == "random":
                vx, vy = dot.tangent
            dx = vx * velocity * dot.speed_factor * dt if stream else 0.0
            dy = vy * velocity * dot.speed_factor * dt if stream else 0.0
            if has_group_motion:
                # The Group Drift carrier is already musically shaped by the
                # hero solver. Each decorative bead takes the same shared
                # direction plus its OWN phase, retaining the accepted 49/51
                # cohesion without competing with heroes or touching their RNG.
                shared_x, shared_y, local_rate = group_motion
                heading = dot.phase + time_s * (0.30 + drift_speed * 3.0)
                dx += (shared_x + math.cos(heading) * local_rate) * dt * dot.speed_factor
                dy += (shared_y + math.sin(heading) * local_rate) * dt * dot.speed_factor
            elif drift and drift_amount > 0.0:
                phase = dot.phase + time_s * (0.30 + drift_speed * 3.0)
                wobble = math.sin(phase * (1.0 + 2.0 * drift_frequency))
                lateral = wobble * drift_amount * (0.012 + 0.024 * drift_speed) * dt
                if drift_direction in {"swirl_cw", "swirl_ccw"}:
                    # Small clockwise/counterclockwise circulation around the
                    # same 2D centre. Never alters the parent Bubble drift.
                    # The stored UV Y axis points down. Ordinary stream
                    # transport is sign-corrected below, but the 2D swirl
                    # tangent was already authored in screen space. Counter
                    # that extra sign here so SAME matches Bubble's actual
                    # CW/CCW winding; REVERSED remains its deliberate inverse.
                    sign = -1.0 if drift_direction == "swirl_cw" else 1.0
                    orbit = sign * drift_amount * (0.12 + drift_speed * 0.8) * dt
                    cx, cy = (dot.x - 0.5) * domain_w, (dot.y - 0.5) * domain_h
                    dx += -cy * orbit + lateral * 0.3
                    dy += cx * orbit + lateral * 0.3
                elif drift_direction == "swish_horizontal":
                    dx += lateral
                elif drift_direction == "swish_vertical":
                    dy += lateral
                elif drift_direction == "left":
                    dx -= abs(lateral)
                elif drift_direction == "right":
                    dx += abs(lateral)
                elif drift_direction == "diagonal":
                    dx += lateral * 0.7
                    dy -= lateral * 0.7
                elif abs(vx) >= abs(vy):
                    dy += lateral
                else:
                    dx += lateral
            dx *= motion_sign
            dy *= motion_sign
            dot.x = (dot.x + dx / domain_w) % 1.0
            dot.y = (dot.y + dy / domain_h) % 1.0

    def advance(
        self, dt: float, settings: Mapping[str, object], *,
        resolved_stream_velocity: float, small_bubble_breathing: float,
        resolved_group_motion: tuple[float, float, float] = (0.0, 0.0, 0.0),
        world=None,
    ) -> tuple[float, ...]:
        """Return immutable-ready packed points. Empty, without RNG work, if off."""
        if not self.enabled(settings):
            self._micro.clear()
            self._particles.clear()
            return ()
        dt = max(0.0, min(0.1, float(dt)))
        self._time += dt
        micro_stream = bool(settings.get("bubble_microbubble_stream", False))
        micro_drift = bool(settings.get("bubble_microbubble_drift", False))
        particle_stream = bool(settings.get("bubble_particle_stream", False))
        particle_drift = bool(settings.get("bubble_particle_drift", False))
        particle_glow = bool(settings.get("bubble_particle_glow", False))
        # The hero world (BubbleWorld): its canonical-card units and its area in canonical cards.
        domain = (1.0, 1.0) if world is None else (float(world.domain_w), float(world.domain_h))
        area = 1.0 if world is None else float(world.population_scale)
        micro_count = (min(MAX_MICROBUBBLES, round(MAX_MICROBUBBLES * _unit(settings["bubble_microbubble_density"]) * area))
                       if micro_stream or micro_drift else 0)
        particle_count = (min(MAX_PARTICLES, round(MAX_PARTICLES * _unit(settings["bubble_particle_density"]) * area))
                          if particle_stream or particle_drift or particle_glow else 0)
        next_columnarity = _unit(settings.get("bubble_microbubble_columnarity", 0.0))
        change = next_columnarity - self._micro_columnarity
        if change:
            for dot in self._micro:
                dot.x = (dot.x + change * dot.column_dx / domain[0]) % 1.0
                dot.y = (dot.y + change * dot.column_dy / domain[1]) % 1.0
            self._micro_columnarity = next_columnarity
        self._populate(
            self._micro,
            self._micro_rng,
            micro_count,
            chained=True,
            columnarity=next_columnarity,
            domain=domain,
        )
        self._populate(self._particles, self._particle_rng, particle_count, chained=False, domain=domain)
        # Glow smoothing is light-only. Hero Bubble pulse-energy decay is
        # intentionally longer, and must never be changed for decoration.
        if particle_glow:
            target = _unit(small_bubble_breathing)
            tau = (0.045 if target >= self._glow_envelope
                   else max(0.06, float(settings.get("bubble_particle_glow_release_ms", 160)) / 1000.0))
            self._glow_envelope += (target - self._glow_envelope) * (1.0 - math.exp(-dt / tau))
        else:
            self._glow_envelope = 0.0
        common = dict(
            group_motion=resolved_group_motion if bool(settings.get("bubble_group_drift", False)) else (0.0, 0.0, 0.0),
            velocity=(0.0 if str(settings["bubble_drift_direction"]) in {"swirl_cw", "swirl_ccw"}
                      else max(0.0, float(resolved_stream_velocity))),
            stream_direction=str(settings["bubble_stream_direction"]),
            drift_direction=str(settings["bubble_drift_direction"]),
            drift_amount=_unit(settings["bubble_drift_amount"]),
            drift_speed=_unit(settings["bubble_drift_speed"]),
            drift_frequency=_unit(settings["bubble_drift_frequency"]),
            time_s=self._time,
            domain=domain,
        )
        self._advance_pool(
            self._micro,
            dt,
            stream=micro_stream,
            drift=micro_drift,
            direction_mode=str(settings.get("bubble_microbubble_direction_mode", "same")),
            **common,
        )
        self._advance_pool(
            self._particles,
            dt,
            stream=particle_stream,
            drift=particle_drift,
            direction_mode=str(settings.get("bubble_particle_direction_mode", "same")),
            **common,
        )
        result: list[float] = []
        micro_size = float(settings["bubble_microbubble_size"])
        particle_size = float(settings["bubble_particle_size"])
        # This is the existing small-bubble *breathing response*, consumed only
        # as a glow-intensity envelope. It MUST NOT change particle diameter.
        breathing = _unit(self._glow_envelope)
        glow_reactivity = max(0.0, float(settings["bubble_particle_glow_reactivity"]))
        glow_intensity = max(0.0, float(settings["bubble_particle_glow_intensity"]))
        for dot in self._micro:
            # Fade before an independent edge-wrap; never flash/teleport at card boundaries.
            edge = min(dot.x * domain[0], dot.y * domain[1], (1.0-dot.x) * domain[0], (1.0-dot.y) * domain[1])
            alpha = dot.opacity * min(1.0, max(0.0, edge / 0.055))
            result.extend((dot.x, dot.y, micro_size * dot.size_factor,
                           alpha, 0.0, 0.0))
        for dot in self._particles:
            if particle_glow:
                # An understated steady glimmer, plus genuine musical light.
                # No pulse-size modulation and no long inherited size-release.
                glow = glow_intensity * (0.10 + glow_reactivity * breathing * 0.95)
            else:
                glow = 0.0
            edge = min(dot.x * domain[0], dot.y * domain[1], (1.0-dot.x) * domain[0], (1.0-dot.y) * domain[1])
            alpha = dot.opacity * min(1.0, max(0.0, edge / 0.055))
            result.extend((dot.x, dot.y, particle_size * dot.size_factor,
                           alpha, min(6.0, glow), 1.0))
        return tuple(result)


__all__ = ["BubbleAmbientSimulation", "MAX_MICROBUBBLES", "MAX_PARTICLES", "RECORD_STRIDE"]
