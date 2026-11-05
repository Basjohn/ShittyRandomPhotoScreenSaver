"""Bubble's world on a card of any shape: one isotropic unit, and density that follows area.

Bubble is authored on the canonical 420x280 card. Its simulation works in that card's units: one
unit across is the canonical width and one unit down is the canonical height, so every authored
speed, drift, swirl, margin, collision gap and radius is a literal from that card. A card of any
other extent simply has more (or fewer) of those units: the world is ``extent / canonical`` units
wide and tall. Nothing is a fraction of the current card, so a tall card does not stream faster and
a wide one does not stream slower; at equal uniform visual scale every shape moves and sizes exactly
like the canonical card. Only the population follows the card's area.

The renderer holds at most :data:`BUBBLE_RENDER_CAPACITY` heroes, and that includes bubbles whose
heads have left the card while their trails drain (measured at up to ~1.5x the live population on
the curated presets). A card larger than the canonical one therefore grows its live population only
up to :data:`BUBBLE_LIVE_CAPACITY` (or the authored population, if that is already larger); past
that the whole world zooms by ``world_scale`` instead (bubbles, speeds and distances together,
exactly like a larger uniform scale), so density and look stay those of the canonical card. On the
canonical card and anything no larger, ``world_scale`` is exactly 1.

The world is pure geometry: resolved only when the committed extent or the authored population
changes, never per tick, and it owns no clock, audio state or polling.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from widgets.spotify_visualizer.render_state import (
    CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
)

# Uniform arrays in the Bubble shader (u_bubbles_pos[110] ...) and the simulation's population cap.
BUBBLE_RENDER_CAPACITY = 110
# Live heroes a larger-than-canonical card may grow to: the render capacity less room for draining
# trails (110 / 1.52, the largest drained-to-live ratio measured on the curated presets).
BUBBLE_LIVE_CAPACITY = 72

# Stroke tuning is expressed in *physical half-stroke pixels*.  The shader owns
# the final SDF conversion.
BUBBLE_BASE_HALF_STROKE_PX = 0.80
BUBBLE_MAX_HALF_STROKE_PX = 2.35
BUBBLE_MAX_EXTRA_HALF_STROKE_PX = 1.25

# The outline firms gently as heroes grow larger than the canonical card's (only the capacity zoom
# can do that now); a canonical-size hero keeps the canonical stroke on every shape.
_ZOOM_FIRMNESS_START = 1.15
_ZOOM_FIRMNESS_FULL = 2.35


def _smoothstep01(value: float) -> float:
    x = max(0.0, min(1.0, float(value)))
    return x * x * (3.0 - 2.0 * x)


def bubble_stroke_extra_half_px(world_scale: float) -> float:
    """Extra physical half-stroke for heroes drawn ``world_scale`` times the canonical size."""

    scale = float(world_scale)
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("Bubble world scale must be finite and positive")
    firmness = _smoothstep01(
        (scale - _ZOOM_FIRMNESS_START) / (_ZOOM_FIRMNESS_FULL - _ZOOM_FIRMNESS_START)
    )
    return BUBBLE_MAX_EXTRA_HALF_STROKE_PX * firmness


@dataclass(frozen=True, slots=True)
class BubbleWorld:
    """One resolved card world, cached by the simulation and carried to the renderer."""

    width: float
    height: float
    # World size in canonical-card units (zoomed by ``world_scale``): 1x1 on the canonical card.
    domain_w: float
    domain_h: float
    world_scale: float
    # Canonical cards' worth of area: authored counts are multiplied by this.
    population_scale: float


def _extent(viewport_extent: Sequence[object] | None, baseline: tuple[float, float]) -> tuple[float, float]:
    if viewport_extent is None:
        return baseline
    try:
        width = float(viewport_extent[0])  # type: ignore[index]
        height = float(viewport_extent[1])  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return baseline
    if not (math.isfinite(width) and math.isfinite(height) and width > 0.0 and height > 0.0):
        return baseline
    return width, height


def resolve_bubble_world(
    viewport_extent: Sequence[object] | None,
    *,
    authored_population: int,
    baseline_viewport_size: Sequence[object] = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE,
) -> BubbleWorld:
    """Resolve the world for a committed extent and the authored hero population (big + small)."""

    baseline_w = float(baseline_viewport_size[0])
    baseline_h = float(baseline_viewport_size[1])
    if not (math.isfinite(baseline_w) and math.isfinite(baseline_h) and baseline_w > 0.0 and baseline_h > 0.0):
        raise ValueError("Bubble baseline viewport geometry must be positive")
    width, height = _extent(viewport_extent, (baseline_w, baseline_h))
    cards_w = width / baseline_w
    cards_h = height / baseline_h
    population = max(0, int(authored_population))
    needed = population * cards_w * cards_h
    capacity = max(population, BUBBLE_LIVE_CAPACITY)
    world_scale = 1.0
    if cards_w * cards_h > 1.0 and needed > capacity:
        world_scale = math.sqrt(needed / capacity)
    domain_w = cards_w / world_scale
    domain_h = cards_h / world_scale
    return BubbleWorld(
        width=width,
        height=height,
        domain_w=domain_w,
        domain_h=domain_h,
        world_scale=world_scale,
        population_scale=domain_w * domain_h,
    )


def scale_bubble_population(big: int, small: int, population_scale: float) -> tuple[int, int]:
    """Authored big/small counts at this world's density (exact on a canonical-area world)."""

    big = max(0, int(big))
    small = max(0, int(small))
    if population_scale == 1.0:
        return big, small
    scaled_big = min(BUBBLE_RENDER_CAPACITY, int(math.floor(big * population_scale + 0.5)))
    scaled_small = int(math.floor(small * population_scale + 0.5))
    return scaled_big, min(scaled_small, BUBBLE_RENDER_CAPACITY - scaled_big)


__all__ = [
    "BUBBLE_BASE_HALF_STROKE_PX",
    "BUBBLE_MAX_HALF_STROKE_PX",
    "BUBBLE_MAX_EXTRA_HALF_STROKE_PX",
    "BUBBLE_LIVE_CAPACITY",
    "BUBBLE_RENDER_CAPACITY",
    "BubbleWorld",
    "bubble_stroke_extra_half_px",
    "resolve_bubble_world",
    "scale_bubble_population",
]
