"""Backward-compatible height helper for Spotify visualizer cards.

The full outer-card geometry policy now lives in
``widgets.spotify_visualizer.card_geometry``. This module stays as a thin
compatibility wrapper for existing imports and tests that only need the
preferred-height helper.
"""
from __future__ import annotations

from widgets.spotify_visualizer.card_geometry import (
    DEFAULT_GROWTH,
    MAX_HEIGHT,
    MIN_HEIGHT,
    resolve_card_metrics,
)


def preferred_height(
    vis_mode: str,
    base_height: int = 80,
    growth_factor: float | None = None,
    max_available: int | None = None,
) -> int:
    """Return the ideal card height for *vis_mode*.

    Parameters
    ----------
    vis_mode:
        One of ``spectrum``, ``oscilloscope``, ``blob``, ``sine_wave``,
        ``bubble``.
    base_height:
        The widget's default (spectrum) height in logical pixels.
    growth_factor:
        User-configurable multiplier.  ``None`` means use the built-in
        default for that mode.
    max_available:
        If provided, the result is clamped so the card does not exceed
        this many pixels (e.g. remaining screen space above the media
        widget).

    Returns
    -------
    int
        Clamped height in logical pixels.
    """
    growth_map = dict(DEFAULT_GROWTH)
    if growth_factor is not None:
        growth_map[vis_mode] = float(growth_factor)
    metrics = resolve_card_metrics(
        vis_mode,
        base_height,
        growth_map,
        max_available=max_available,
    )
    return metrics.preferred_height


