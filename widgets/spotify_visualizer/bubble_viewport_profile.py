"""Cached geometry profile for Bubble presentation adjustments.

The profile is pure geometry: no clocks, audio state, polling or mutable render
ownership.  Callers resolve it only when committed viewport geometry changes,
then consume the cached scalars on normal ticks/renders.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)

# Stroke tuning is expressed in *physical half-stroke pixels*.  The shader owns
# the final SDF conversion.  This avoids the old ``bonus * effect_scale`` curve,
# which stayed dormant too long and then accelerated toward a very heavy edge.
BUBBLE_BASE_HALF_STROKE_PX = 0.80
BUBBLE_MAX_HALF_STROKE_PX = 2.35
BUBBLE_MAX_EXTRA_HALF_STROKE_PX = 1.25

# Gentle stroke firmness starts much earlier than population compensation.
_AREA_FIRMNESS_START = 1.15
_AREA_FIRMNESS_FULL = 2.35
_WIDE_FIRMNESS_START_ASPECT = 1.75
_WIDE_FIRMNESS_FULL_ASPECT = 4.00
_TALL_FIRMNESS_START_H_OVER_W = 1.10
_TALL_FIRMNESS_FULL_H_OVER_W = 2.50

# Population/travel compensation stays confined to genuinely extreme shapes.
# The old wide tail started near 3.375:1 and was full near 5.25:1.  Move the
# gradient earlier, while retaining a wide dead-zone around ordinary cards.
_WIDE_TAIL_START_ASPECT = 2.50
_WIDE_TAIL_FULL_ASPECT = 5.00
_TALL_TAIL_START_H_OVER_W = 1.50
_TALL_TAIL_FULL_H_OVER_W = 3.00


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _smoothstep01(value: float) -> float:
    x = _clamp01(value)
    return x * x * (3.0 - 2.0 * x)


def _ramp(value: float, start: float, full: float) -> float:
    if full <= start:
        return 1.0 if value >= full else 0.0
    return _smoothstep01((value - start) / (full - start))


@dataclass(frozen=True, slots=True)
class BubbleViewportProfile:
    """One resolved viewport gradient consumed by Bubble runtime + renderer."""

    width: float
    height: float
    aspect_ratio: float
    area_scale: float
    area_firmness: float
    wide_firmness: float
    tall_firmness: float
    stroke_firmness: float
    stroke_extra_half_px: float
    wide_tail: float
    tall_tail: float
    wide_stream_scale: float
    tall_stream_cap_scale: float


def resolve_bubble_viewport_profile(
    viewport_extent: Sequence[object] | None,
    *,
    baseline_viewport_size: Sequence[object] = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
) -> BubbleViewportProfile:
    """Resolve Bubble's continuous shape profile from committed geometry only."""

    if len(baseline_viewport_size) != 2:
        raise ValueError("Bubble baseline viewport geometry is incomplete")
    baseline_w = float(baseline_viewport_size[0])
    baseline_h = float(baseline_viewport_size[1])
    if (
        not math.isfinite(baseline_w)
        or not math.isfinite(baseline_h)
        or baseline_w <= 0.0
        or baseline_h <= 0.0
    ):
        raise ValueError("Bubble baseline viewport geometry must be positive")

    if viewport_extent is None:
        width, height = baseline_w, baseline_h
    else:
        if len(viewport_extent) != 2:
            raise ValueError("Bubble viewport geometry is incomplete")
        width = float(viewport_extent[0])
        height = float(viewport_extent[1])
        if (
            not math.isfinite(width)
            or not math.isfinite(height)
            or width <= 0.0
            or height <= 0.0
        ):
            width, height = baseline_w, baseline_h

    aspect = width / height
    h_over_w = height / width
    area_scale = math.sqrt((width * height) / (baseline_w * baseline_h))

    area_firmness = _ramp(area_scale, _AREA_FIRMNESS_START, _AREA_FIRMNESS_FULL)
    wide_firmness = _ramp(
        aspect,
        _WIDE_FIRMNESS_START_ASPECT,
        _WIDE_FIRMNESS_FULL_ASPECT,
    )
    tall_firmness = _ramp(
        h_over_w,
        _TALL_FIRMNESS_START_H_OVER_W,
        _TALL_FIRMNESS_FULL_H_OVER_W,
    )
    shape_firmness = max(wide_firmness, tall_firmness)

    # Smooth-union area authority with a bounded shape-only contribution.
    # A very thin shape therefore becomes firmer even if its total area is not
    # large, but geometry extremity alone can never drive the full heavy edge.
    stroke_firmness = 1.0 - (1.0 - area_firmness) * (1.0 - 0.58 * shape_firmness)
    stroke_firmness = _clamp01(stroke_firmness)
    stroke_extra_half_px = BUBBLE_MAX_EXTRA_HALF_STROKE_PX * stroke_firmness

    wide_tail = _ramp(aspect, _WIDE_TAIL_START_ASPECT, _WIDE_TAIL_FULL_ASPECT)
    tall_tail = _ramp(
        h_over_w,
        _TALL_TAIL_START_H_OVER_W,
        _TALL_TAIL_FULL_H_OVER_W,
    )

    return BubbleViewportProfile(
        width=width,
        height=height,
        aspect_ratio=aspect,
        area_scale=area_scale,
        area_firmness=area_firmness,
        wide_firmness=wide_firmness,
        tall_firmness=tall_firmness,
        stroke_firmness=stroke_firmness,
        stroke_extra_half_px=stroke_extra_half_px,
        wide_tail=wide_tail,
        tall_tail=tall_tail,
        wide_stream_scale=1.0 + 0.20 * wide_tail,
        tall_stream_cap_scale=1.0 - 0.30 * tall_tail,
    )


__all__ = [
    "BUBBLE_BASE_HALF_STROKE_PX",
    "BUBBLE_MAX_HALF_STROKE_PX",
    "BUBBLE_MAX_EXTRA_HALF_STROKE_PX",
    "BubbleViewportProfile",
    "resolve_bubble_viewport_profile",
]
