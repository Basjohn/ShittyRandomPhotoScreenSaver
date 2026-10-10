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
    BLINDS = "Blinds"
    BLOCK_SPINS = "3D Block Spins"
    RIPPLE = "Ripple"
    WARP_DISSOLVE = "Warp Dissolve"
    CRUMBLE = "Crumble"
    PARTICLE = "Particle"
    BURN = "Burn"
    GLASS_SHATTER = "Glass Shatter"
    EXPLODING_TILES = "Exploding Tiles"
    PIXEL_ACCRETION = "Directional Pixel Accretion"
    MELT_DRIP = "Melt Drip"
    PAGE_CURL = "Page Curl"
    DISINTEGRATE = "Disintegrate"
    CUBE_TURN = "Cube Turn"
    BEAM = "Beam"
    JIGSAW = "Jigsaw Piece Flip"
    VOLUMETRIC_DISSOLVE = "Volumetric Dissolve"
    VHS_DISTORTION = "VHS Distortion"
    EDGE_BLOOM = "Edge Bloom Reveal"
    LIQUID_LENS = "Liquid Lens"


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
    CUSTOM = "custom"


def parse_widget_position(value: Any) -> WidgetPosition:
    """Parse a canonical widget position and fail if the schema is invalid."""

    # Import lazily to avoid the models <-> normalization module cycle.
    from core.settings.normalization import parse_enum_strict

    return parse_enum_strict(value, WidgetPosition)
