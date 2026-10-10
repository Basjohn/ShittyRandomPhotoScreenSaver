"""Liquid Lens Settings choices: import-safe, shared by the resolver and the Settings page."""

from __future__ import annotations

# Where the lens comes in from: the label shown in Settings -> the resolved origin code.
LIQUID_LENS_ORIGINS = {
    "Left": "left",
    "Right": "right",
    "Top": "top",
    "Bottom": "bottom",
    "Top Left": "top_left",
    "Top Right": "top_right",
    "Bottom Left": "bottom_left",
    "Bottom Right": "bottom_right",
    "Center": "center",
}
LIQUID_LENS_ORIGIN_CHOICES = (*LIQUID_LENS_ORIGINS, "Random")
