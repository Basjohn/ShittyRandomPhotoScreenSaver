"""Enum types and helper functions shared across settings models."""
from __future__ import annotations

from enum import Enum
from typing import Any


class DisplayMode(Enum):
    """Display scaling mode."""
    FILL = "fill"
    FIT = "fit"
    SHRINK = "shrink"


class TransitionType(Enum):
    """Available transition types."""
    CROSSFADE = "Crossfade"
    SLIDE = "Slide"
    WIPE = "Wipe"
    DIFFUSE = "Diffuse"
    BLOCK_PUZZLE_FLIP = "Block Puzzle Flip"
    BLINDS = "Blinds"
    BLOCK_SPINS = "3D Block Spins"
    RIPPLE = "Ripple"
    WARP_DISSOLVE = "Warp Dissolve"
    CRUMBLE = "Crumble"
    PARTICLE = "Particle"
    BURN = "Burn"


class WidgetPosition(Enum):
    """Standard widget positions."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


def coerce_widget_position(value: Any, fallback: WidgetPosition) -> WidgetPosition:
    """
    DEPRECATED: Use core.settings.normalization.normalize_widget_position() instead.
    
    Normalize a persisted widget position into a WidgetPosition enum.
    Handles legacy strings such as "WidgetPosition.TOP_LEFT" or "Top Left".
    """
    # Import here to avoid circular dependency
    from core.settings.normalization import normalize_widget_position
    return normalize_widget_position(value, fallback)
