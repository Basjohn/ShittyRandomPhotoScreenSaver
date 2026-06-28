"""Oscilloscope-owned display response helpers.

These helpers intentionally live outside shared audio production. They describe
how Oscilloscope consumes already-produced waveform/transient data for display.
"""
from __future__ import annotations

from typing import Sequence

_OSC_LIVE_INPUT_GAIN = 0.42
_OSC_PHASE_SEARCH_LIMIT = 64
_OSC_PHASE_SEARCH_STEP = 4
_OSC_PHASE_SAMPLE_STEP = 4


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def resolve_waveform_blend_alpha(speed: float) -> float:
    """Return the visual waveform blend alpha for an authored Osc speed.

    The old ``speed ** 2`` mapping made common curated speeds such as ``0.18``
    resolve to ~0.03, which trails the audio by many frames. Keep low speeds
    smooth, but reserve "very slow" for genuinely tiny authored values.
    """
    resolved_speed = clamp01(speed)
    if resolved_speed >= 0.99:
        return 1.0
    if resolved_speed <= 0.0:
        return 0.0
    return max(0.035, min(0.98, 0.018 + 0.72 * (resolved_speed ** 1.55)))


def blend_waveform(previous: Sequence[float], incoming: Sequence[float], speed: float) -> list[float]:
    """Blend an incoming waveform using Oscilloscope's display-speed contract."""
    new_wf = [float(v) for v in incoming]
    if not previous or len(previous) != len(new_wf):
        return new_wf
    alpha = resolve_waveform_blend_alpha(speed)
    if alpha >= 0.99:
        return new_wf
    return [
        float(old) * (1.0 - alpha) + float(new) * alpha
        for old, new in zip(previous, new_wf)
    ]


def condition_live_waveform(previous: Sequence[float], incoming: Sequence[float]) -> list[float]:
    """Return a phase-stable live waveform for Oscilloscope display.

    Raw loopback PCM windows are not phase-coherent from frame to frame. Feeding
    them directly to a single-line visual makes playback twitch/strobe even
    when the idle procedural carrier looks correct. This is display-only input
    conditioning: spatially soften the live slice, keep amplitude in the same
    visual range as the authored line sensitivity controls, and align phase/sign
    to the previous displayed waveform before the normal speed blend runs.
    """
    shaped = _shape_live_waveform(incoming)
    if not previous or len(previous) != len(shaped):
        return shaped

    prev = [float(v) for v in previous]
    n = len(shaped)
    if n <= 1:
        return shaped

    best_score = float("inf")
    best_shift = 0
    best_sign = 1.0
    max_shift = min(_OSC_PHASE_SEARCH_LIMIT, max(0, n // 2))
    offsets = range(-max_shift, max_shift + 1, _OSC_PHASE_SEARCH_STEP)
    indices = range(0, n, _OSC_PHASE_SAMPLE_STEP)
    for sign in (1.0, -1.0):
        for shift in offsets:
            score = 0.0
            for i in indices:
                score += abs(prev[i] - (shaped[(i + shift) % n] * sign))
            if score < best_score:
                best_score = score
                best_shift = shift
                best_sign = sign

    if best_shift == 0 and best_sign > 0.0:
        return shaped
    return [shaped[(i + best_shift) % n] * best_sign for i in range(n)]


def _shape_live_waveform(incoming: Sequence[float]) -> list[float]:
    values = [max(-1.0, min(1.0, float(v))) for v in incoming]
    n = len(values)
    if n <= 2:
        return [v * _OSC_LIVE_INPUT_GAIN for v in values]

    softened: list[float] = []
    for i in range(n):
        prev2 = values[(i - 2) % n]
        prev1 = values[(i - 1) % n]
        cur = values[i]
        next1 = values[(i + 1) % n]
        next2 = values[(i + 2) % n]
        softened.append((prev2 * 0.08 + prev1 * 0.18 + cur * 0.48 + next1 * 0.18 + next2 * 0.08) * _OSC_LIVE_INPUT_GAIN)
    return softened


def advance_ghost_ring(
    ring: list[list[float]],
    write_index: int,
    current_waveform: Sequence[float],
    delay_frames: int,
) -> tuple[list[float], int]:
    """Advance the Oscilloscope ghost ring and return the visible ghost frame.

    The ring stores pre-update visible waveforms. During initial fill, the
    oldest available frame is used so the ghost never jumps to the just-written
    current frame. Once full, the next write slot is also the oldest slot.
    """
    delay = max(1, int(delay_frames))
    frame = [float(v) for v in current_waveform]
    if not frame:
        return [], write_index % delay

    if len(ring) < delay:
        ring.append(frame)
        return list(ring[0]), write_index % delay

    slot = write_index % delay
    visible_ghost = list(ring[slot])
    ring[slot] = frame
    return visible_ghost, (slot + 1) % delay


def resolve_transient_sensitivity_modulation(
    *,
    base_sensitivity: float,
    smoothed_bass: float,
    kick_event: float,
    snare_event: float,
    width_mix: float,
) -> tuple[float, float]:
    """Return ``(sensitivity, drive)`` for Oscilloscope transient width accent.

    Transients are allowed to add a visible accent, but should not become a
    second amplitude authority that strobe-scales the waveform. Continuous bass
    owns most width body; repeated event peeks are capped to a short accent.
    """
    mix = max(0.0, min(1.0, float(width_mix)))
    base = max(0.1, float(base_sensitivity))
    if mix <= 0.001:
        return base, 0.0

    continuous = max(0.0, min(1.0, float(smoothed_bass)))
    event = max(0.0, min(1.0, float(kick_event) * 0.55 + float(snare_event) * 0.15))
    drive = min(1.0, continuous * 0.88 + event * 0.12)
    multiplier = 1.0 + drive * mix * 0.16
    return min(10.0, base * multiplier), drive
