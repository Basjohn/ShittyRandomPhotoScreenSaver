"""Visual-only display easing for Spectrum solid bars.

This module intentionally lives at the overlay/display seam. It must not
change FFT/audio behavior, shared beat-engine smoothing, or per-mode floor
contracts. The helper converts continuous Spectrum bar values into a smooth
display-space body that suppresses small boundary chatter without snapping the
visible bar height to rigid segment steps.
"""
from __future__ import annotations

import math
from typing import Any, List, Sequence

_SPECTRUM_BASE_HEIGHT = 80.0
_SPECTRUM_UPLOAD_SCALE = 0.55
_SPECTRUM_CURVE_POWER = 1.15
_SPECTRUM_MAX_BOOST = 0.95
_SPECTRUM_DEFAULT_DT_S = 1.0 / 60.0
_SPECTRUM_MAX_DT_S = 0.10
_SPECTRUM_MICRO_ZONE_SEG = 0.45
_SPECTRUM_NORMAL_ZONE_SEG = 1.40
_SPECTRUM_MICRO_RATE_HZ = 8.0
_SPECTRUM_NORMAL_RISE_HZ = 20.0
_SPECTRUM_NORMAL_FALL_HZ = 24.0
_SPECTRUM_FAST_RISE_HZ = 90.0
_SPECTRUM_FAST_FALL_HZ = 84.0
_SPECTRUM_SNAP_EPSILON_SEG = 0.025


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


def spectrum_bar_to_segment_float(
    bar_value: float,
    *,
    segments: int,
    height_scale: float,
) -> float:
    segs = max(1, int(segments))
    boosted = spectrum_bar_to_boosted(bar_value, height_scale=height_scale)
    return max(0.0, min(float(segs), boosted * float(segs)))


def segment_float_to_spectrum_bar(
    segment_value: float,
    *,
    segments: int,
    height_scale: float,
) -> float:
    segs = max(1, int(segments))
    clamped = max(0.0, min(float(segs), float(segment_value)))
    boosted = clamped / float(segs)
    return boosted_to_spectrum_bar(boosted, height_scale=height_scale)


def reset_overlay_spectrum_solid_hysteresis_state(overlay: Any) -> None:
    overlay._spectrum_solid_display_segments = []
    overlay._spectrum_solid_display_segment_values = []
    overlay._spectrum_solid_last_update_ts = []
    overlay._spectrum_solid_hysteresis_segments = 0
    overlay._spectrum_solid_hysteresis_bar_count = 0


def _ensure_overlay_hysteresis_state(overlay: Any, *, count: int, segments: int) -> None:
    if (
        len(getattr(overlay, "_spectrum_solid_display_segments", [])) != count
        or len(getattr(overlay, "_spectrum_solid_display_segment_values", [])) != count
        or len(getattr(overlay, "_spectrum_solid_last_update_ts", [])) != count
        or int(getattr(overlay, "_spectrum_solid_hysteresis_segments", 0) or 0) != segments
        or int(getattr(overlay, "_spectrum_solid_hysteresis_bar_count", 0) or 0) != count
    ):
        overlay._spectrum_solid_display_segments = [-1] * count
        overlay._spectrum_solid_display_segment_values = [-1.0] * count
        overlay._spectrum_solid_last_update_ts = [0.0] * count
        overlay._spectrum_solid_hysteresis_segments = segments
        overlay._spectrum_solid_hysteresis_bar_count = count


def _alpha_for_rate(rate_hz: float, dt_s: float) -> float:
    return 1.0 - math.exp(-max(0.0, float(rate_hz)) * max(0.0, float(dt_s)))


def _resolve_display_rate(abs_diff_seg: float, diff_seg: float) -> float:
    if abs_diff_seg <= _SPECTRUM_MICRO_ZONE_SEG:
        return _SPECTRUM_MICRO_RATE_HZ
    if abs_diff_seg <= _SPECTRUM_NORMAL_ZONE_SEG:
        return _SPECTRUM_NORMAL_RISE_HZ if diff_seg >= 0.0 else _SPECTRUM_NORMAL_FALL_HZ
    return _SPECTRUM_FAST_RISE_HZ if diff_seg >= 0.0 else _SPECTRUM_FAST_FALL_HZ


def apply_overlay_spectrum_solid_hysteresis(
    overlay: Any,
    bars: Sequence[float],
    *,
    segments: int,
    render_height: float,
    now_ts: float,
) -> List[float]:
    count = len(bars)
    segs = max(1, int(segments))
    _ensure_overlay_hysteresis_state(overlay, count=count, segments=segs)
    height_scale = compute_spectrum_height_scale(render_height)

    display_segments = overlay._spectrum_solid_display_segments
    display_segment_values = overlay._spectrum_solid_display_segment_values
    last_update_ts = overlay._spectrum_solid_last_update_ts
    output: List[float] = []

    for idx, raw_bar in enumerate(bars):
        target_segment_value = spectrum_bar_to_segment_float(
            raw_bar,
            segments=segs,
            height_scale=height_scale,
        )
        current_segment_value = float(display_segment_values[idx])
        last_ts = float(last_update_ts[idx] or 0.0)

        if current_segment_value < 0.0 or current_segment_value > float(segs):
            current_segment_value = target_segment_value
        else:
            dt_s = float(now_ts) - last_ts if last_ts > 0.0 else _SPECTRUM_DEFAULT_DT_S
            dt_s = max(0.0, min(_SPECTRUM_MAX_DT_S, dt_s))
            if dt_s <= 0.0:
                dt_s = _SPECTRUM_DEFAULT_DT_S

            diff_seg = target_segment_value - current_segment_value
            abs_diff_seg = abs(diff_seg)
            if abs_diff_seg <= _SPECTRUM_SNAP_EPSILON_SEG:
                current_segment_value = target_segment_value
            else:
                rate_hz = _resolve_display_rate(abs_diff_seg, diff_seg)
                alpha = _alpha_for_rate(rate_hz, dt_s)
                current_segment_value = current_segment_value + (diff_seg * alpha)
                current_segment_value = max(0.0, min(float(segs), current_segment_value))

        display_segment_values[idx] = current_segment_value
        last_update_ts[idx] = float(now_ts)
        display_segments[idx] = int(round(current_segment_value))
        output.append(
            segment_float_to_spectrum_bar(
                current_segment_value,
                segments=segs,
                height_scale=height_scale,
            )
        )

    return output
