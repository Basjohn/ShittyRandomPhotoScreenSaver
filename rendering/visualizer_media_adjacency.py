"""Ordinary (non-CUSTOM) Visualizer placement relative to the Media card.

One pure rule shared by the saver (``DisplayManager``) and Settings Arrange, so
the Settings canvas shows the Visualizer exactly where the saver docks it.
Coordinates are display-local; no Qt object, timer or settings access.
"""
from __future__ import annotations

from typing import Sequence

VISUALIZER_MEDIA_GAP = 20.0


def resolve_visualizer_media_origin(
    media_rect: Sequence[float],
    visualizer_size: Sequence[float],
    display_size: Sequence[float],
    *,
    gap: float = VISUALIZER_MEDIA_GAP,
) -> tuple[float, float, bool]:
    """Return ``(x, y, overfull)`` for a Visualizer docked to Media.

    Prefers the vertical side with more usable space (top Media -> below,
    bottom Media -> above). Horizontal adjacency is only a fallback when
    neither vertical side fits. ``overfull`` reports a pair that fits on no
    side; the result is then clamped on the larger vertical side.
    """

    media_x, media_y, media_width, media_height = (float(value) for value in media_rect)
    vis_width, vis_height = (float(value) for value in visualizer_size)
    width, height = (float(value) for value in display_size)
    below_space = height - (media_y + media_height)
    above_space = media_y

    x = max(0.0, min(media_x, width - vis_width))
    below_y = media_y + media_height + gap
    above_y = media_y - gap - vis_height
    below_fits = below_y + vis_height <= height
    above_fits = above_y >= 0.0
    if below_fits or above_fits:
        if below_fits and (not above_fits or below_space >= above_space):
            return x, below_y, False
        return x, above_y, False

    # Exceptional very-tall pair: keep adjacency by trying horizontal free
    # space before conceding that the display is genuinely overfull.
    right_x = media_x + media_width + gap
    left_x = media_x - gap - vis_width
    right_space = width - (media_x + media_width)
    left_space = media_x
    y = max(0.0, min(media_y, height - vis_height))
    if right_x + vis_width <= width or left_x >= 0.0:
        if right_x + vis_width <= width and (left_x < 0.0 or right_space >= left_space):
            return right_x, y, False
        return left_x, y, False
    y = (
        max(0.0, min(below_y, height - vis_height))
        if below_space >= above_space
        else max(0.0, min(above_y, height - vis_height))
    )
    return x, y, True


__all__ = ["VISUALIZER_MEDIA_GAP", "resolve_visualizer_media_origin"]
