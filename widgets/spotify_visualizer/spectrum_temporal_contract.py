"""Spectrum viewport-temporal contract shared by authored logical presentation.

Spectrum bar values live in a normalized 0..1 domain, but the visible motion is
vertical.  A wide CUSTOM viewport changes bar width/distribution without making a
bar value travel farther vertically; a tall CUSTOM viewport does.  Temporal
smoothing therefore scales from *viewport height only*.  Width must never enter
this contract.

The scaling is intentionally conservative: the existing authored one-pole time
constant is multiplied by the expanded vertical bar-field ratio.  This preserves
canonical/wide behavior exactly while reducing the growth of per-tick pixel jumps
on tall cards without compressing bar amplitude, source energy, cadence, or the
renderer height transfer.
"""
from __future__ import annotations

import math

from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)


SPECTRUM_MIN_TIME_CONSTANT_SECONDS = 0.002
SPECTRUM_MAX_TIME_CONSTANT_SECONDS = 0.014
SPECTRUM_STALL_SNAP_SECONDS = 0.100
SPECTRUM_SETTLED_EPSILON = 1.0e-4

# Paused Spectrum owns a deliberately gentle handoff into its resting scene.
# This is presentation-only state advanced by the existing logical clock; it
# never retunes BeatEngine/DSP decay and therefore cannot affect a natural
# low-energy passage while playback remains active.
SPECTRUM_PAUSE_TO_IDLE_SECONDS = 1.60
SPECTRUM_IDLE_TRAVEL_BARS_PER_SECOND = 0.90
SPECTRUM_IDLE_TRAVEL_AMPLITUDE = 0.030

# Spectrum's shader reserves 6 authored px at both top and bottom of the bar
# field.  Use the same logical span here rather than raw card height so the
# temporal ratio tracks the distance a bar can actually traverse.
_SPECTRUM_VERTICAL_MARGIN_TOTAL = 12.0
_MAX_VERTICAL_TEMPORAL_RATIO = 4.0

# Idle Spectrum baseline, as a fraction of full bar value (pre-upload).  These
# values are intentionally presentation-owned and deterministic.
_IDLE_BASELINE_MIN = 0.08
_IDLE_BASELINE_MAX = 0.24


def _clamp01(value: object, *, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if not math.isfinite(number):
        number = float(default)
    return max(0.0, min(1.0, number))


def idle_spectrum_baseline(bar_count: int) -> list[float]:
    """Return the deterministic resting Spectrum scene for idle presentation."""

    count = max(0, int(bar_count))
    if count <= 0:
        return []
    if count == 1:
        return [(_IDLE_BASELINE_MIN + _IDLE_BASELINE_MAX) * 0.5]
    span = _IDLE_BASELINE_MAX - _IDLE_BASELINE_MIN
    return [
        _IDLE_BASELINE_MIN + span * math.sin((index / (count - 1)) * math.pi)
        for index in range(count)
    ]


def idle_spectrum_travel_scene(
    bar_count: int,
    travel_position: object,
) -> list[float]:
    """Return the resting scene plus one very gentle left-to-right energy pulse.

    ``travel_position`` is measured in bar indices.  A one-bar cosine bell means
    the next bar begins to rise as the current bar falls.  The caller advances
    the position from the existing Spectrum logical clock; no timer or secondary
    cadence owner is introduced here.
    """

    baseline = idle_spectrum_baseline(bar_count)
    if not baseline:
        return baseline
    try:
        position = float(travel_position)
    except (TypeError, ValueError):
        position = -1.0
    if not math.isfinite(position):
        position = -1.0

    resolved: list[float] = []
    for index, floor in enumerate(baseline):
        distance = abs(float(index) - position)
        if distance >= 1.0:
            pulse = 0.0
        else:
            pulse = 0.5 * (1.0 + math.cos(math.pi * distance))
        resolved.append(
            _clamp01(floor + SPECTRUM_IDLE_TRAVEL_AMPLITUDE * pulse)
        )
    return resolved


def advance_idle_spectrum_travel_position(
    current_position: object,
    *,
    bar_count: int,
    dt_seconds: object,
) -> float:
    """Advance the paused idle pulse without owning cadence or wall-clock work."""

    count = max(0, int(bar_count))
    if count <= 0:
        return -1.0
    try:
        position = float(current_position)
    except (TypeError, ValueError):
        position = -1.0
    if not math.isfinite(position):
        position = -1.0
    try:
        dt = float(dt_seconds)
    except (TypeError, ValueError):
        dt = 0.0
    if not math.isfinite(dt) or dt <= 0.0 or dt >= 1.0:
        return position

    position += dt * SPECTRUM_IDLE_TRAVEL_BARS_PER_SECOND
    # One authored empty-bar margin on each end gives the last bar time to fall
    # before the left edge starts its next very slow rise.
    cycle_span = float(count + 2)
    while position > float(count):
        position -= cycle_span
    return position


def spectrum_vertical_temporal_ratio(viewport_height: object) -> float:
    """Return tall-only temporal compensation for Spectrum bar motion.

    The ratio is exactly ``1`` at canonical height and for any shorter viewport.
    Width is deliberately absent: doubling width does not increase vertical bar
    travel and therefore must not slow Spectrum response.
    """

    baseline_height = float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1])
    baseline_span = max(1.0, baseline_height - _SPECTRUM_VERTICAL_MARGIN_TOTAL)
    try:
        height = float(viewport_height)
    except (TypeError, ValueError):
        return 1.0
    if not math.isfinite(height) or height <= 0.0:
        return 1.0
    current_span = max(1.0, height - _SPECTRUM_VERTICAL_MARGIN_TOTAL)
    ratio = current_span / baseline_span
    return max(1.0, min(_MAX_VERTICAL_TEMPORAL_RATIO, ratio))


def spectrum_visual_time_constant(
    smoothing_strength: object,
    *,
    viewport_height: object,
) -> float:
    """Resolve the authored Spectrum one-pole constant for one viewport.

    This changes only temporal easing.  It never changes bar magnitude, renderer
    boost, BeatEngine/DSP smoothing, logical cadence, or publication cadence.
    """

    strength = _clamp01(smoothing_strength, default=0.5)
    base = SPECTRUM_MIN_TIME_CONSTANT_SECONDS + (
        SPECTRUM_MAX_TIME_CONSTANT_SECONDS - SPECTRUM_MIN_TIME_CONSTANT_SECONDS
    ) * strength
    return base * spectrum_vertical_temporal_ratio(viewport_height)


def spectrum_visual_alpha(
    dt_seconds: object,
    smoothing_strength: object,
    *,
    viewport_height: object,
) -> float:
    """Return the one-tick Spectrum presentation blend coefficient."""

    try:
        dt = max(0.0, float(dt_seconds))
    except (TypeError, ValueError):
        dt = 0.0
    tau = spectrum_visual_time_constant(
        smoothing_strength,
        viewport_height=viewport_height,
    )
    if dt <= 0.0:
        return 0.0
    return 1.0 - math.exp(-dt / max(tau, 1.0e-6))


__all__ = [
    "SPECTRUM_IDLE_TRAVEL_AMPLITUDE",
    "SPECTRUM_IDLE_TRAVEL_BARS_PER_SECOND",
    "SPECTRUM_MAX_TIME_CONSTANT_SECONDS",
    "SPECTRUM_MIN_TIME_CONSTANT_SECONDS",
    "SPECTRUM_PAUSE_TO_IDLE_SECONDS",
    "SPECTRUM_SETTLED_EPSILON",
    "SPECTRUM_STALL_SNAP_SECONDS",
    "advance_idle_spectrum_travel_position",
    "idle_spectrum_baseline",
    "idle_spectrum_travel_scene",
    "spectrum_vertical_temporal_ratio",
    "spectrum_visual_alpha",
    "spectrum_visual_time_constant",
]
