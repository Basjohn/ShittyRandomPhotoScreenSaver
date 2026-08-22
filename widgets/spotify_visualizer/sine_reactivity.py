"""Presentation-neutral authored reactivity math for Sine Wave."""

from __future__ import annotations

import math
from collections.abc import Mapping


_SMOOTHED_FIELDS = (
    "overall_energy",
    "bass_energy",
    "mid_energy",
    "high_energy",
    "beat_drive",
    "event_drive",
    "width_reaction",
    "sensitivity",
    "heartbeat_intensity",
    "wave_effect_gate",
)

_ATTACK_RELEASE_MS = {
    "overall_energy": (28.0, 140.0),
    "bass_energy": (24.0, 125.0),
    "mid_energy": (28.0, 150.0),
    "high_energy": (28.0, 150.0),
    "beat_drive": (24.0, 150.0),
    "event_drive": (18.0, 170.0),
    "width_reaction": (24.0, 185.0),
    "sensitivity": (22.0, 175.0),
    "heartbeat_intensity": (16.0, 210.0),
    "wave_effect_gate": (36.0, 240.0),
}


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge1 <= edge0:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _attack_release_step(
    current: float,
    target: float,
    dt: float,
    *,
    attack_ms: float,
    release_ms: float,
) -> float:
    if dt <= 0.0:
        return target
    tau_ms = attack_ms if target >= current else release_ms
    if tau_ms <= 0.0:
        return target
    alpha = 1.0 - math.exp(-dt / (tau_ms / 1000.0))
    return current + (target - current) * alpha


def compute_sine_reactivity_targets(
    *,
    smoothed_bass: float,
    smoothed_mid: float,
    smoothed_high: float,
    overall_energy: float,
    kick_event: float,
    snare_event: float,
    transient_width_mix: float,
    base_width_reaction: float,
    base_sensitivity: float,
    base_heartbeat: float,
    heartbeat_slider: float,
) -> dict[str, float]:
    """Derive Sine-only beat-assist targets from current logical inputs."""

    base_bass = max(0.0, float(smoothed_bass))
    base_mid = max(0.0, float(smoothed_mid))
    base_high = max(0.0, float(smoothed_high))
    kick = max(0.0, float(kick_event))
    snare = max(0.0, float(snare_event))
    width_mix = max(0.0, min(1.0, float(transient_width_mix)))
    base_overall = max(0.0, float(overall_energy))

    continuous_support = min(
        1.0,
        max(
            base_bass,
            base_overall * 0.98,
            base_mid * 0.52 + base_high * 0.22,
        ),
    )
    kick_support = min(kick, 0.10 + continuous_support * 0.85)
    snare_support = min(snare, 0.08 + continuous_support * 0.70)
    raw_event_drive = min(1.25, kick * 1.00 + snare * 0.55)
    event_drive = min(raw_event_drive, 0.16 + continuous_support * 0.82)
    beat_drive = min(
        1.0,
        max(
            base_bass * 1.08,
            continuous_support * 0.78
            + kick_support * 0.22
            + snare_support * 0.10,
        ),
    )

    boosted_bass = min(
        1.0,
        max(base_bass, base_bass + kick_support * 0.28 + snare_support * 0.09),
    )
    boosted_mid = min(
        1.0,
        max(base_mid, base_mid + snare_support * 0.20 + kick_support * 0.07),
    )
    boosted_high = min(
        1.0,
        max(base_high, base_high + snare_support * 0.15),
    )
    boosted_overall = min(
        1.0,
        max(
            base_overall,
            boosted_bass * 0.58
            + boosted_mid * 0.27
            + boosted_high * 0.15,
        ),
    )

    base_width = max(0.0, min(1.0, float(base_width_reaction)))
    width_boost = width_mix * (
        beat_drive * 0.55 + kick_support * 0.22 + snare_support * 0.11
    )
    width_reaction = min(
        1.0,
        max(base_width, base_width * (1.0 + continuous_support * 0.25))
        + width_boost,
    )

    raw_sensitivity = max(0.1, float(base_sensitivity))
    sensitivity = min(
        5.0,
        raw_sensitivity
        * (
            1.0
            + continuous_support * 0.18
            + kick_support * 0.26
            + snare_support * 0.12
        ),
    )

    heartbeat = max(0.0, float(base_heartbeat))
    heartbeat_amount = max(0.0, min(1.0, float(heartbeat_slider)))
    heartbeat_assist_cap = min(
        0.36,
        0.05 + continuous_support * 0.28 + heartbeat_amount * 0.12,
    )
    heartbeat_assist = min(
        heartbeat_assist_cap,
        kick_support * 0.30 + snare_support * 0.14,
    )
    heartbeat_intensity = min(1.0, max(heartbeat, heartbeat_assist))
    motion_support = min(
        1.0,
        max(
            base_overall * 1.30,
            base_bass * 1.15,
            beat_drive * 0.92,
            base_mid * 0.42 + base_high * 0.24,
            heartbeat_intensity * 0.78,
        ),
    )
    wave_effect_gate = 0.06 + _smoothstep(0.10, 0.42, motion_support) * 0.94

    return {
        "overall_energy": boosted_overall,
        "bass_energy": boosted_bass,
        "mid_energy": boosted_mid,
        "high_energy": boosted_high,
        "beat_drive": beat_drive,
        "event_drive": event_drive,
        "width_reaction": width_reaction,
        "sensitivity": sensitivity,
        "heartbeat_intensity": heartbeat_intensity,
        "wave_effect_gate": wave_effect_gate,
        "_diag_kick_evt": kick,
        "_diag_snare_evt": snare,
        "_diag_raw_event_drive": raw_event_drive,
        "_diag_continuous_support": continuous_support,
        "_diag_base_heartbeat": heartbeat,
        "_diag_heartbeat_assist": heartbeat_assist,
        "_diag_raw_sensitivity": raw_sensitivity,
        "_diag_base_width_reaction": base_width,
        "_diag_motion_support": motion_support,
    }


def advance_sine_reactivity(
    previous: Mapping[str, float] | None,
    targets: Mapping[str, float],
    *,
    dt: float,
) -> dict[str, float]:
    """Advance authored fast-attack/slow-release outputs once logically."""

    prior = previous or {}
    resolved: dict[str, float] = {}
    for name in _SMOOTHED_FIELDS:
        target = float(targets[name])
        attack_ms, release_ms = _ATTACK_RELEASE_MS[name]
        resolved[name] = _attack_release_step(
            float(prior.get(name, target)),
            target,
            float(dt),
            attack_ms=attack_ms,
            release_ms=release_ms,
        )
    return resolved


__all__ = ["advance_sine_reactivity", "compute_sine_reactivity_targets"]
