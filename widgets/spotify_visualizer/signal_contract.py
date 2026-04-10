"""Shared signal-contract helpers for mode-owned continuous vs burst drive."""
from __future__ import annotations


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def soft_ceiling(
    value: float,
    *,
    knee: float,
    ceiling: float,
    max_input: float = 1.0,
    curve: float = 1.35,
) -> float:
    """Compress the upper range without flattening the lower range.

    Below ``knee`` the value is unchanged. Above it, the signal is gently
    squeezed toward ``ceiling`` so sustained moderate passages do not live in
    the same range reserved for true accents/overdrive.
    """

    x = clamp(value, 0.0, max_input)
    knee = clamp(knee, 0.0, max_input)
    ceiling = clamp(ceiling, knee, max_input)
    if x <= knee or max_input <= knee:
        return x
    t = (x - knee) / max(1e-6, (max_input - knee))
    shaped = 1.0 - (1.0 - t) ** max(1.0, curve)
    return knee + (ceiling - knee) * shaped


def burst_authority(
    *,
    envelope: float,
    delta: float = 0.0,
    event: float = 0.0,
    envelope_weight: float = 0.85,
    delta_weight: float = 1.0,
    event_weight: float = 0.70,
    ceiling: float = 1.0,
) -> float:
    """Return a short-lived burst-driving signal separate from sustained support."""

    drive = (
        max(0.0, float(envelope)) * envelope_weight
        + max(0.0, float(delta)) * delta_weight
        + max(0.0, float(event)) * event_weight
    )
    return clamp(drive, 0.0, ceiling)
