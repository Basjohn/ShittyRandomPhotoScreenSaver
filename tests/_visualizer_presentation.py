"""Shared neutral card/shadow inputs for visualizer-presentation tests.

Production assembles the visualizer card's border/background/shadow inputs from
the widget theme and shadow settings in ``engine/display_manager.py`` and passes
them explicitly into ``resolve_visualizer_presentation`` /
``QuickDisplayVisualizerOwner``.  The card contract is:

* ``outer_rect``, ``viewport_extent``, ``uniform_visual_scale`` and the baseline
  aspect are derived from display/extent/scale alone -- card inputs never move
  them;
* border/inset/shadow only affect ``content_rect``, ``border_width`` and
  ``shell_style``.

Tests that exercise pure geometry therefore supply a *neutral* card (no border,
no shadow) so results isolate the geometry contract, while tests that exercise
the card itself override just the fields they care about.  This is test
scaffolding, not a second production authority for card defaults.
"""
from __future__ import annotations

from typing import Any, Mapping


NEUTRAL_CARD_SHADOW_KWARGS: dict[str, Any] = {
    "border_width": 0.0,
    "corner_radius": 0.0,
    "content_inset": 0.0,
    "background_color": (0, 0, 0, 0),
    "border_color": (255, 255, 255, 255),
    "shadow_enabled": False,
    "shadow_color": (0, 0, 0, 0),
    "shadow_blur": 0.0,
    "shadow_offset": (0.0, 0.0),
    "shadow_spread": 0.0,
    "shadow_extensions": (0.0, 0.0, 0.0, 0.0),
}


def neutral_card_shadow_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return a complete card/shadow kwargs mapping, neutral unless overridden."""
    merged = dict(NEUTRAL_CARD_SHADOW_KWARGS)
    merged.update(overrides)
    return merged


def resolve_presentation(**kwargs: Any):
    """Call the production resolver, filling any unspecified card fields neutrally."""
    from widgets.spotify_visualizer.presentation_geometry import (
        resolve_visualizer_presentation,
    )

    merged = dict(NEUTRAL_CARD_SHADOW_KWARGS)
    merged.update(kwargs)
    return resolve_visualizer_presentation(**merged)
