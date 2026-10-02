"""Cube Turn's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``cube_turn_program``) loads only when Cube Turn renders.
"""

from __future__ import annotations

# The way the box turns: its front moves toward this side. Random picks one per run.
CUBE_TURN_DIRECTIONS = {"Left": "left", "Right": "right", "Up": "up", "Down": "down"}
CUBE_TURN_DIRECTION_CHOICES = (*CUBE_TURN_DIRECTIONS, "Random")
