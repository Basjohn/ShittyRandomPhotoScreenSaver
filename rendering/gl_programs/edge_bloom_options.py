"""Edge Bloom Reveal's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module (``edge_bloom_program``)
loads only when Edge Bloom Reveal renders.
"""

from __future__ import annotations

# Where the glow's colour comes from: the chosen colour, the next picture's accent colour for every
# line, or each picture's own accent for its own lines (``rendering/gl_programs/photo_colour``).
EDGE_BLOOM_COLOUR_SOURCES = {
    "Custom": "custom",
    "Next Picture": "next",
    "Each Picture": "each",
}
EDGE_BLOOM_COLOUR_SOURCE_CHOICES = tuple(EDGE_BLOOM_COLOUR_SOURCES)
