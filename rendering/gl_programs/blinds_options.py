"""Blinds' Settings choices.

Import-safe for the Settings UI and the request resolver: the 3D Slats shader module
(``blinds_slats_program``) loads only when Blinds renders.
"""

from __future__ import annotations

# Flat: the authored 2D bands. 3D Slats: each stripe is a solid slat that turns over, the
# old picture on its front and the new one on its back.
BLINDS_STYLE_CHOICES = ("Flat", "3D Slats")
BLINDS_STYLE_CODES = {"Flat": "flat", "3D Slats": "slats"}
BLINDS_SLATS_RANGE = (6, 48)
