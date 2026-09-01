"""Spectrum-owned presentation smoothing on the authoritative UI tick.

The filter in this module deliberately has no timer, Qt paint callback, or
repaint authority.  ``tick_pipeline.push_gpu_frame`` calls it once per normal
visualizer tick and decides whether the resulting presentation changed.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)


_MIN_TIME_CONSTANT_SECONDS = 0.002
_MAX_TIME_CONSTANT_SECONDS = 0.014
_STALL_SNAP_SECONDS = 0.100
_SETTLED_EPSILON = 1.0e-4

# Idle Spectrum baseline, as a fraction of full bar value (pre-upload). These are
# bar *values*, not pixels: the renderer scales each by 0.55, applies pow(1.15)
# and the card height-scale, so a value that looks large here still renders as a
# calm resting hump. The intentional resting-scene contract is that the tallest
# idle bar is a clearly perceptible height - at least ~5 rendered pixels on the
# smallest supported card and roughly 10-18% of card height on larger cards -
# while the edges taper to a low floor.
#
# The previous 0.010-0.030 range rendered the tallest bar at ~1px on an 80px card
# and only ~4px on the installed enlarged card in single-piece mode (value 0.030
# -> 0.0165 uploaded -> pow(1.15) -> sub-pixel active height), so the first
# installed run reported the idle scene as visually absent. These values are
# calibrated against a real offscreen GL render across the single-piece and
# segmented paths; see `tests/test_p2_gate1_spectrum_idle_pixels.py`.
_IDLE_BASELINE_MIN = 0.08
_IDLE_BASELINE_MAX = 0.24


def idle_spectrum_baseline(bar_count: int) -> list[float]:
    """Return the deterministic resting Spectrum scene for an idle visualizer.

    This is presentation state, not synthetic audio. It never reaches audio
    capture, the BeatEngine, source bars, source generations, or the
    energy/transient/onset buses, so nothing downstream can mistake it for a
    real reaction.

    It is a pure function of the bar count with no time term and no randomness,
    so a steady idle settles to a single scene revision and the existing
    unchanged-scene suppression keeps its physical cost near zero.
    """

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


def reset_widget_spectrum_presentation_smoothing(widget: Any) -> None:
    """Discard presentation-only Spectrum history without touching source bars."""
    widget._spectrum_presentation_bars = []
    widget._spectrum_presentation_last_ts = 0.0
    widget._spectrum_presentation_identity = None
    widget._spectrum_presentation_pending = False


def _clamp_strength(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.5




def _viewport_smoothing_multiplier(widget: Any) -> float:
    """Increase Spectrum presentation smoothing on very large viewports.

    A bar value traverses more physical pixels when CUSTOM stretches either
    viewport axis, so the same authored one-pole constant becomes visibly
    steppy on both extreme-tall and extreme-wide cards even though logical
    cadence is unchanged. Scale the existing filter by the larger axis ratio;
    this adds no timer, interpolation pass, or paint authority and remains 1.0
    at/below canonical extent. Using ``max`` rather than multiplying axes avoids
    over-smoothing a viewport that is large in both dimensions.
    """
    controller = getattr(widget, "runtime_controller", None)
    extent = getattr(controller, "presentation_viewport_extent", None)
    try:
        width = float(extent[0])
        height = float(extent[1])
        baseline_width = float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[0])
        baseline_height = float(CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE[1])
    except (TypeError, ValueError, IndexError):
        return 1.0
    if (
        width <= 0.0
        or height <= 0.0
        or baseline_width <= 0.0
        or baseline_height <= 0.0
    ):
        return 1.0
    extent_ratio = max(width / baseline_width, height / baseline_height)
    return max(1.0, min(4.0, extent_ratio))


def _presentation_identity(widget: Any, strength: float) -> tuple[Any, ...]:
    return (
        int(getattr(widget, "_display_bars_source_generation", -1) or -1),
        int(getattr(widget, "_display_bars_source_activation", -1) or -1),
        int(getattr(widget, "_bar_count", 0) or 0),
        bool(getattr(widget, "_spectrum_single_piece", False)),
        round(strength, 4),
    )


def resolve_widget_spectrum_presentation(
    widget: Any,
    source_bars: Sequence[float],
    *,
    now_ts: float,
    first_frame: bool = False,
) -> tuple[list[float], bool]:
    """Return Spectrum bars for the current authoritative presentation tick.

    The second return value reports whether the filtered presentation changed
    since the preceding tick.  This lets the normal tick publish the remaining
    one-pole settling steps without introducing another scheduler or paint loop.
    First frames, identity changes, disabled/paused states, and long UI stalls
    snap directly to source so stale history cannot add startup or recovery lag.
    """
    values = [max(0.0, min(1.0, float(value))) for value in source_bars]
    enabled = bool(getattr(widget, "_spectrum_visual_smoothing_enabled", True))
    strength = _clamp_strength(getattr(widget, "_spectrum_visual_smoothing", 0.5))

    is_spectrum = str(getattr(widget, "_vis_mode_str", "") or "").lower() == "spectrum"
    playing = bool(getattr(widget, "_spotify_playing", False))
    if is_spectrum and not playing:
        # Idle Spectrum has a resting scene instead of nothing to present. Any
        # residual real value still wins where it exceeds the floor, so the
        # arrival of real playback replaces these bars in place - no card
        # recreation, no cold startup stage, no second clock.
        count = len(values) or max(0, int(getattr(widget, "_bar_count", 0) or 0))
        baseline = idle_spectrum_baseline(count)
        if values:
            values = [max(value, floor) for value, floor in zip(values, baseline)]
        else:
            values = baseline
        previous = getattr(widget, "_spectrum_presentation_bars", []) or []
        changed = len(previous) != len(values) or any(
            abs(current - prior) > _SETTLED_EPSILON
            for current, prior in zip(values, previous)
        )
        widget._spectrum_presentation_bars = list(values)
        try:
            widget._spectrum_presentation_last_ts = float(now_ts)
        except (TypeError, ValueError):
            widget._spectrum_presentation_last_ts = 0.0
        widget._spectrum_presentation_identity = _presentation_identity(widget, strength)
        widget._spectrum_presentation_pending = False
        return list(values), changed

    active = (
        str(getattr(widget, "_vis_mode_str", "") or "").lower() == "spectrum"
        and bool(getattr(widget, "_spotify_playing", False))
        and enabled
        and strength > 0.0
    )
    if not active:
        reset_widget_spectrum_presentation_smoothing(widget)
        return values, False

    identity = _presentation_identity(widget, strength)
    previous = getattr(widget, "_spectrum_presentation_bars", []) or []
    previous_identity = getattr(widget, "_spectrum_presentation_identity", None)
    try:
        last_ts = float(getattr(widget, "_spectrum_presentation_last_ts", 0.0) or 0.0)
        current_ts = float(now_ts)
    except (TypeError, ValueError):
        last_ts = 0.0
        current_ts = 0.0

    reset_boundary = (
        first_frame
        or previous_identity != identity
        or len(previous) != len(values)
    )
    dt = current_ts - last_ts
    if reset_boundary or dt <= 0.0 or dt >= _STALL_SNAP_SECONDS:
        changed = len(previous) == len(values) and any(
            abs(current - prior) > _SETTLED_EPSILON
            for current, prior in zip(values, previous)
        )
        widget._spectrum_presentation_bars = list(values)
        widget._spectrum_presentation_last_ts = current_ts
        widget._spectrum_presentation_identity = identity
        widget._spectrum_presentation_pending = False
        return values, changed

    time_constant = (
        _MIN_TIME_CONSTANT_SECONDS
        + (_MAX_TIME_CONSTANT_SECONDS - _MIN_TIME_CONSTANT_SECONDS) * strength
    ) * _viewport_smoothing_multiplier(widget)
    alpha = 1.0 - math.exp(-dt / max(time_constant, 1.0e-6))

    resolved: list[float] = []
    changed = False
    pending = False
    for prior, target in zip(previous, values):
        next_value = prior + (target - prior) * alpha
        if abs(target - next_value) <= _SETTLED_EPSILON:
            next_value = target
        else:
            pending = True
        if abs(next_value - prior) > _SETTLED_EPSILON:
            changed = True
        resolved.append(next_value)

    widget._spectrum_presentation_bars = resolved
    widget._spectrum_presentation_last_ts = current_ts
    widget._spectrum_presentation_identity = identity
    widget._spectrum_presentation_pending = pending
    return list(resolved), changed
