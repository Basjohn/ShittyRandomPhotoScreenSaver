"""Spectrum's decorative Settings choices.

Import-safe for Settings and the typed model. The Quick Spectrum shader receives a choice as its position in these
tuples, so the order is part of the shader contract (append; never reorder).
"""

from __future__ import annotations

# Where the falling peak ghosts take their colour while Rainbow Ghost is off. Bar Colour: the bar border colour.
# Custom: their own colour. Bar Fill: the bar's own fill surface where the ghost is (fill and its gradient, Rainbow
# Fill, a pattern or flag sheet, gloss), so a ghost continues its bar's own colours and fades out.
SPECTRUM_GHOST_COLOUR_SOURCES = ("Bar Colour", "Custom", "Bar Fill")

# A second-colour pattern over the bar fill, fixed to the bar baseline and each bar's own width.
SPECTRUM_GEOMETRIC_PATTERNS = ("Horizontal Bands", "Scanlines", "Dots", "Diagonal Stripes", "Grid", "Chevrons")
# A flag laid over the whole bar field in its own colours and seen through the bars as they rise, waving gently.
SPECTRUM_FLAG_PATTERNS = ("USA Flag", "Japan Flag", "UK Flag", "Jamaica Flag", "Brazil Flag")
SPECTRUM_PATTERNS = ("Off", *SPECTRUM_GEOMETRIC_PATTERNS, *SPECTRUM_FLAG_PATTERNS)

# Per Bar: each bar carries its own copy of the pattern (columns fitted to its width, chevrons centred on it).
# Shared: one sheet laid over the whole bar field, continuous across bars and gaps, seen through the bar fills.
SPECTRUM_PATTERN_ANCHORS = ("Per Bar", "Shared")
