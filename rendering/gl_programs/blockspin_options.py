"""3D Block Spins' Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``blockspin_program``) itself loads only when Block Spins renders.
"""

from __future__ import annotations

# Edge Glass: the slab's edges as polished glass showing the next image.
BLOCK_SPIN_EDGE_GLASS_CHOICES = ("Off", "Reflection", "Refraction", "Both")
