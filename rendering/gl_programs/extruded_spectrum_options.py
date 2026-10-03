"""Extruded Spectrum's Settings choices.

Import-safe for Settings and the typed model: the shader module
(``extruded_spectrum_program``) loads only when the mode renders.
"""

from __future__ import annotations

# Spectral Faces: each bar's body takes its hue across the spectrum, edges in Spectrum's border
# colour. Spectral Edges: Spectrum's (dark) bar body with glowing spectral edges, the look of
# Spectrum's Organs preset. Bar Colours: Spectrum's fill and border colours.
EXTRUDED_COLOURINGS = ("Spectral Faces", "Spectral Edges", "Bar Colours")
