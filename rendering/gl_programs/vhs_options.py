"""VHS Distortion's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module (``vhs_program``)
loads only when VHS Distortion renders.
"""

from __future__ import annotations

# The way the picture rolls: the label says where the new picture comes in. Random picks one per run.
VHS_DIRECTIONS = {
    "Top to Bottom": "down",
    "Bottom to Top": "up",
}
VHS_DIRECTION_CHOICES = (*VHS_DIRECTIONS, "Random")
