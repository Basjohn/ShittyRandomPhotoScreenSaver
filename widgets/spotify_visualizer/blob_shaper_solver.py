"""Contour-space solver helpers for Blob Shaper runtime motion."""
from __future__ import annotations

import math
from typing import Sequence


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def build_contour_residual_profile(
    *,
    sample_count: int,
    time_value: float,
    idle_motion: float,
    audio_motion: float,
    overall_energy: float,
    vocal_energy: float,
    high_energy: float,
    playing: bool,
    seed: float = 0.0,
) -> list[float]:
    """Return a subtle organic contour residual in profile space.

    This operates before SDF evaluation so the fill, band, edge, and glow all
    remain attached to the same solved contour.
    """
    if sample_count <= 0 or not playing:
        return [0.0] * max(0, sample_count)

    idle = _clamp(idle_motion, 0.0, 2.0)
    audio = _clamp(audio_motion, 0.0, 3.0)
    overall = _clamp(overall_energy, 0.0, 1.0)
    vocal = _clamp(vocal_energy, 0.0, 1.0)
    high = _clamp(high_energy, 0.0, 1.0)

    drift = math.sin(time_value * 0.17 + seed * 0.73) * (0.09 * overall + 0.05 * vocal)
    drift += math.sin(time_value * 0.07 + seed * 1.11) * 0.03

    amp = idle * (0.0014 + overall * 0.0018)
    amp += audio * (0.0018 + vocal * 0.0085 + overall * 0.0035 + high * 0.0012)
    amp = min(0.028, amp)

    out: list[float] = []
    for idx in range(sample_count):
        theta = (idx / sample_count) * math.tau + drift
        noise = 0.0
        noise += math.sin(theta + time_value * 0.42 + seed * 0.9) * 0.54
        noise += math.sin(theta * 2.0 - time_value * 0.31 + seed * 1.7) * 0.28
        noise += math.sin(theta * 3.0 + time_value * 0.67 - seed * 0.4) * 0.14
        noise += math.sin(theta * 4.0 - time_value * 0.18 + seed * 2.1) * (0.06 * vocal)
        out.append(noise * amp)
    return out


def slew_profile_toward_target(
    *,
    previous_target: Sequence[float] | None,
    current_target: Sequence[float],
    base_profile: Sequence[float],
    dt: float,
    attack_hz: float = 16.0,
    release_hz: float = 3.4,
) -> list[float]:
    """Apply asymmetric target slew to contour motion.

    Blob Shaper reads better when pushes toward the authored reaction limit are
    responsive, but the return toward base is much slower and softer. This
    keeps authored directional pulls from looking like high-frequency flicker.
    """
    count = len(current_target)
    if count <= 0:
        return []

    prev = list(previous_target or ())
    if len(prev) != count:
        return [float(v) for v in current_target]

    clamped_dt = _clamp(dt, 1.0 / 240.0, 0.05)
    attack_mix = 1.0 - math.exp(-max(0.01, attack_hz) * clamped_dt)
    release_mix = 1.0 - math.exp(-max(0.01, release_hz) * clamped_dt)

    slewed: list[float] = []
    for idx in range(count):
        base = float(base_profile[idx]) if idx < len(base_profile) else 1.0
        prev_val = float(prev[idx])
        cur_val = float(current_target[idx])
        prev_delta = abs(prev_val - base)
        cur_delta = abs(cur_val - base)
        mix = attack_mix if cur_delta >= prev_delta else release_mix
        slewed.append(prev_val + (cur_val - prev_val) * mix)
    return slewed


def solve_profile_step(
    *,
    current_profile: Sequence[float],
    current_velocity: Sequence[float],
    target_profile: Sequence[float],
    min_profile: Sequence[float],
    max_profile: Sequence[float],
    dt: float,
    stiffness: float = 18.0,
    damping: float = 10.5,
    neighbor_strength: float = 13.0,
    smoothing_passes: int = 2,
) -> tuple[list[float], list[float]]:
    """Advance a cyclic spring-smoothed contour toward its targets."""
    count = len(target_profile)
    if count <= 0:
        return ([], [])

    clamped_dt = _clamp(dt, 1.0 / 240.0, 0.05)
    profile = [
        float(current_profile[idx]) if idx < len(current_profile) else float(target_profile[idx])
        for idx in range(count)
    ]
    velocity = [
        float(current_velocity[idx]) if idx < len(current_velocity) else 0.0
        for idx in range(count)
    ]

    next_profile = [0.0] * count
    next_velocity = [0.0] * count
    for idx in range(count):
        cur = profile[idx]
        tgt = float(target_profile[idx])
        prev_cur = profile[(idx - 1) % count]
        next_cur = profile[(idx + 1) % count]
        laplacian = ((prev_cur + next_cur) * 0.5) - cur
        accel = (tgt - cur) * stiffness + laplacian * neighbor_strength
        vel = velocity[idx] + accel * clamped_dt
        vel /= 1.0 + damping * clamped_dt
        nxt = cur + vel * clamped_dt
        nxt = _clamp(nxt, float(min_profile[idx]), float(max_profile[idx]))
        next_profile[idx] = nxt
        next_velocity[idx] = vel

    for _ in range(max(0, int(smoothing_passes))):
        smoothed = next_profile[:]
        for idx in range(count):
            prev_val = next_profile[(idx - 1) % count]
            cur_val = next_profile[idx]
            next_val = next_profile[(idx + 1) % count]
            tgt = float(target_profile[idx])
            blended = cur_val * 0.52 + (prev_val + next_val) * 0.24
            smoothed[idx] = _clamp(blended * 0.92 + tgt * 0.08, float(min_profile[idx]), float(max_profile[idx]))
        next_profile = smoothed

    return next_profile, next_velocity
