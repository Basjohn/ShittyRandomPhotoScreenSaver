"""Visual-only hysteresis for Spectrum solid-bar display quantization.

This module intentionally lives at the overlay/display seam. It must not
change FFT/audio behavior, shared beat-engine smoothing, or per-mode floor
contracts. The helper converts continuous Spectrum bar values into a stable
solid-bar body that suppresses one-segment chatter while keeping larger moves
responsive.
"""
from __future__ import annotations

import math
from typing import Any, List, Sequence

SPECTRUM_SOLID_HYSTERESIS_DWELL_S = 0.055
_SPECTRUM_BASE_HEIGHT = 80.0
_SPECTRUM_UPLOAD_SCALE = 0.55
_SPECTRUM_CURVE_POWER = 1.15
_SPECTRUM_MAX_BOOST = 0.95
_SPECTRUM_SEGMENT_EPSILON = 0.001


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def compute_spectrum_height_scale(render_height: float) -> float:
    raw_hs = max(1.0, float(render_height) / _SPECTRUM_BASE_HEIGHT)
    height_scale = 1.0 + (math.sqrt(raw_hs) - 1.0) * 1.0
    return min(1.85, height_scale)


def spectrum_bar_to_boosted(bar_value: float, *, height_scale: float) -> float:
    uploaded = _clamp01(bar_value) * _SPECTRUM_UPLOAD_SCALE
    curved = uploaded ** _SPECTRUM_CURVE_POWER
    return min(_SPECTRUM_MAX_BOOST, curved * max(1.0, float(height_scale)))


def boosted_to_spectrum_bar(boosted: float, *, height_scale: float) -> float:
    hs = max(1.0, float(height_scale))
    curved = _clamp01(min(_SPECTRUM_MAX_BOOST, boosted) / hs)
    if curved <= 0.0:
        return 0.0
    uploaded = curved ** (1.0 / _SPECTRUM_CURVE_POWER)
    return _clamp01(uploaded / _SPECTRUM_UPLOAD_SCALE)


def spectrum_bar_to_segment_index(
    bar_value: float,
    *,
    segments: int,
    height_scale: float,
) -> int:
    segs = max(1, int(segments))
    boosted = spectrum_bar_to_boosted(bar_value, height_scale=height_scale)
    return max(0, min(segs, int(round(boosted * segs))))


def segment_index_to_spectrum_bar(
    segment_index: int,
    *,
    segments: int,
    height_scale: float,
) -> float:
    segs = max(1, int(segments))
    idx = max(0, min(segs, int(segment_index)))
    boosted = float(idx) / float(segs)
    return boosted_to_spectrum_bar(boosted, height_scale=height_scale)


def _segment_band_bounds(segment_index: int, segments: int) -> tuple[float, float]:
    segs = max(1, int(segments))
    idx = max(0, min(segs, int(segment_index)))
    lower = max(0.0, (float(idx) - 0.5) / float(segs))
    upper = min(1.0, (float(idx) + 0.5) / float(segs))
    return lower, upper


def _clamp_boosted_to_segment_band(
    boosted: float,
    *,
    accepted_segments: int,
    segments: int,
) -> float:
    lower, upper = _segment_band_bounds(accepted_segments, segments)
    # Keep subtle continuous motion inside the currently accepted band so the
    # solid bars do not read as robotic block snaps while still suppressing
    # one-step chatter across segment boundaries.
    if accepted_segments > 0:
        lower = min(1.0, lower + _SPECTRUM_SEGMENT_EPSILON)
    if accepted_segments < max(1, int(segments)):
        upper = max(0.0, upper - _SPECTRUM_SEGMENT_EPSILON)
    if upper < lower:
        midpoint = (lower + upper) * 0.5
        lower = midpoint
        upper = midpoint
    return max(lower, min(upper, float(boosted)))


def reset_overlay_spectrum_solid_hysteresis_state(overlay: Any) -> None:
    overlay._spectrum_solid_display_segments = []
    overlay._spectrum_solid_pending_down_segments = []
    overlay._spectrum_solid_pending_down_started_ts = []
    overlay._spectrum_solid_hysteresis_segments = 0
    overlay._spectrum_solid_hysteresis_bar_count = 0


def _ensure_overlay_hysteresis_state(overlay: Any, *, count: int, segments: int) -> None:
    if (
        len(getattr(overlay, "_spectrum_solid_display_segments", [])) != count
        or len(getattr(overlay, "_spectrum_solid_pending_down_segments", [])) != count
        or len(getattr(overlay, "_spectrum_solid_pending_down_started_ts", [])) != count
        or int(getattr(overlay, "_spectrum_solid_hysteresis_segments", 0) or 0) != segments
        or int(getattr(overlay, "_spectrum_solid_hysteresis_bar_count", 0) or 0) != count
    ):
        overlay._spectrum_solid_display_segments = [-1] * count
        overlay._spectrum_solid_pending_down_segments = [-1] * count
        overlay._spectrum_solid_pending_down_started_ts = [0.0] * count
        overlay._spectrum_solid_hysteresis_segments = segments
        overlay._spectrum_solid_hysteresis_bar_count = count


def apply_overlay_spectrum_solid_hysteresis(
    overlay: Any,
    bars: Sequence[float],
    *,
    segments: int,
    render_height: float,
    now_ts: float,
    dwell_s: float = SPECTRUM_SOLID_HYSTERESIS_DWELL_S,
) -> List[float]:
    count = len(bars)
    segs = max(1, int(segments))
    _ensure_overlay_hysteresis_state(overlay, count=count, segments=segs)
    height_scale = compute_spectrum_height_scale(render_height)

    display_segments = overlay._spectrum_solid_display_segments
    pending_down_segments = overlay._spectrum_solid_pending_down_segments
    pending_down_started_ts = overlay._spectrum_solid_pending_down_started_ts
    output: List[float] = []

    for idx, raw_bar in enumerate(bars):
        raw_boosted = spectrum_bar_to_boosted(raw_bar, height_scale=height_scale)
        target_segments = spectrum_bar_to_segment_index(
            raw_bar,
            segments=segs,
            height_scale=height_scale,
        )
        current_segments = int(display_segments[idx])
        if current_segments < 0 or current_segments > segs:
            current_segments = target_segments
            display_segments[idx] = target_segments
            pending_down_segments[idx] = -1
            pending_down_started_ts[idx] = 0.0

        diff = target_segments - current_segments
        if diff >= 2:
            current_segments = target_segments
            pending_down_segments[idx] = -1
            pending_down_started_ts[idx] = 0.0
        elif diff == 1:
            pending_down_segments[idx] = -1
            pending_down_started_ts[idx] = 0.0
        elif diff <= -2:
            current_segments = target_segments
            pending_down_segments[idx] = -1
            pending_down_started_ts[idx] = 0.0
        elif diff == -1:
            if pending_down_segments[idx] != target_segments:
                pending_down_segments[idx] = target_segments
                pending_down_started_ts[idx] = now_ts
            elif (now_ts - float(pending_down_started_ts[idx] or 0.0)) >= dwell_s:
                current_segments = target_segments
                pending_down_segments[idx] = -1
                pending_down_started_ts[idx] = 0.0
        else:
            pending_down_segments[idx] = -1
            pending_down_started_ts[idx] = 0.0

        display_segments[idx] = current_segments
        visible_boosted = _clamp_boosted_to_segment_band(
            raw_boosted,
            accepted_segments=current_segments,
            segments=segs,
        )
        output.append(
            boosted_to_spectrum_bar(
                visible_boosted,
                height_scale=height_scale,
            )
        )

    return output
