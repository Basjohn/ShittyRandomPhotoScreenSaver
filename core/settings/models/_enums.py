"""Enum types and helper functions shared across settings models."""
from __future__ import annotations

from enum import Enum
from typing import Any

from core.settings.enum_parsing import parse_enum_strict


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
    MEMBRANE_TURNOVER = "Membrane Turnover"
    SURFACE_TENSION = "Surface Tension Merge"
    CHROMATIC_SHEAR = "Chromatic Shear"
    DEPTH_CASCADE = "Depth Card Cascade"
    CAPILLARY_BLOOM = "Capillary Bloom"


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

    return parse_enum_strict(value, WidgetPosition)


def normalize_widget_position(value: Any, fallback: WidgetPosition) -> WidgetPosition:
    """Repair a persisted widget position through ``core.settings.normalization`` (logging, statistics).

    The models are the lower layer: ``normalization`` imports them at module level, so the models reach it only
    when a persisted value is repaired, never at import or class definition."""

    from core.settings.normalization import normalize_widget_position as repair

    return repair(value, fallback)
