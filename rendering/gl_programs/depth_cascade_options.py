"""Depth Card Cascade Settings choices: import-safe, shared by the resolver and the Settings page."""

from __future__ import annotations

# The way the cascade travels across the picture: Settings label -> resolved sweep code.
CASCADE_SWEEPS = {
    "Left to Right": "right",
    "Right to Left": "left",
    "Top to Bottom": "down",
    "Bottom to Top": "up",
}
CASCADE_SWEEP_CHOICES = (*CASCADE_SWEEPS, "Random")
# World (y up) unit vectors of each sweep.
CASCADE_SWEEP_VECTORS = {"right": (1.0, 0.0), "left": (-1.0, 0.0), "down": (0.0, -1.0), "up": (0.0, 1.0)}
