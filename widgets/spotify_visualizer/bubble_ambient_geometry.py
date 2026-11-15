"""Pure viewport projection for opt-in 2D Bubble decorations.

The ambient texture follows the committed content rect (not screen or card
origin), preserving its shape in ordinary, tall, wide, enlarged and rotated
cards. No decoration can extend beyond this rectangular texture; the canonical
Bubble shader and Quick clip host enforce the actual rounded/stencilled edge.
"""
from __future__ import annotations

import math

MAX_AMBIENT_TEXTURE_EDGE = 2048


def ambient_target_size(content_rect: tuple[float, float, float, float], dpr: float,
                        limit: int = MAX_AMBIENT_TEXTURE_EDGE) -> tuple[int, int, float]:
    """Return texture width/height and texels per content-logical pixel.

    Both axes always use the same scale; the 2048 cap is *not* a stretch.
    Small and ordinary viewports retain their native DPR; the largest views
    downsample uniformly to avoid unbounded GPU allocation/per-frame fill.
    """
    if limit <= 0:
        raise ValueError('Bubble ambient texture cap must be positive')
    width, height = float(content_rect[2]), float(content_rect[3])
    dpr = float(dpr)
    if not all(math.isfinite(x) and x > 0 for x in (width, height, dpr)):
        raise ValueError('Bubble ambient needs positive finite content size and DPR')
    scale = min(dpr, float(limit) / max(width, height))
    return max(1, round(width * scale)), max(1, round(height * scale)), scale


def ambient_sprite_scale(effect_scale: float) -> float:
    """Modest equal-area growth, never stretch with card aspect changes.

    Matches the renderer's equal-area Bubble viewport response principle.
    Decorations remain secondary: even large expansions only grow them 2x.
    """
    if not math.isfinite(float(effect_scale)) or effect_scale <= 0:
        raise ValueError('Bubble ambient response scale must be finite and positive')
    return min(2.0, max(0.75, math.sqrt(effect_scale)))


def select_ambient_occluders(bubbles, positions) -> tuple[float, ...]:
    """Snapshot-indexed, *actual* rendered bubble masks, not guessed cutoffs.

    `positions` is the frozen flat 4-float hero payload from the SAME snapshot.
    Bubble objects are only read here; neither the simulation nor hero payload
    is changed. Called only when decorations are enabled. Any visibly rendered
    bubble may occlude the optional ambience layer beneath it.
    """
    if len(positions) % 4 or len(bubbles) * 4 != len(positions):
        raise ValueError('Bubble ambient occluder indices do not match the rendered population')
    return tuple(
        value
        for i, _bubble in enumerate(bubbles)
        if positions[i * 4 + 3] > 0.0
        for value in positions[i * 4:i * 4 + 4]
    )


__all__ = ['ambient_target_size', 'ambient_sprite_scale', 'select_ambient_occluders',
           'MAX_AMBIENT_TEXTURE_EDGE']
