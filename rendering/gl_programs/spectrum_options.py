"""Spectrum's decorative Settings choices.

Import-safe for Settings and the typed model. The Quick Spectrum shader receives a choice as its position in these
tuples, so the order is part of the shader contract (append; never reorder).
"""

from __future__ import annotations

# Where the falling peak ghosts take their colour while Rainbow Ghost is off.
SPECTRUM_GHOST_COLOUR_SOURCES = ("Bar Colour", "Custom")

# A second-colour pattern over the bar fill, fixed to the bar baseline and each bar's own width.
SPECTRUM_PATTERNS = ("Off", "Horizontal Bands", "Scanlines", "Dots", "Diagonal Stripes", "Grid", "Chevrons")

# Per Bar: each bar carries its own copy of the pattern (columns fitted to its width, chevrons centred on it).
# Shared: one sheet laid over the whole bar field, continuous across bars and gaps, seen through the bar fills.
SPECTRUM_PATTERN_ANCHORS = ("Per Bar", "Shared")
