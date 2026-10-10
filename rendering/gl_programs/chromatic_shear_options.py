"""Chromatic Shear Settings choices: import-safe, shared by the resolver and the Settings page."""

from __future__ import annotations

# The axis the slices shear along: Settings label -> resolved axis code.
SHEAR_DIRECTIONS = {"Horizontal": "horizontal", "Vertical": "vertical", "Diagonal": "diagonal"}
SHEAR_DIRECTION_CHOICES = (*SHEAR_DIRECTIONS, "Random")
