"""Jigsaw Piece Flip's Settings choices.

Import-safe for the Settings UI and the request resolver: the shader module
(``jigsaw_program``) and the piece-layout builder load only when Jigsaw Piece Flip renders.
"""

from __future__ import annotations

# The order the pieces flip in. A corner starts there and the flips spread across the picture;
# Random Start spreads from a random piece; Unordered flips the pieces in a shuffled order.
# Random picks one of these per run.
JIGSAW_ORDERS = {
    "Top Left": "top_left",
    "Top Right": "top_right",
    "Bottom Left": "bottom_left",
    "Bottom Right": "bottom_right",
    "Random Start": "random_start",
    "Unordered": "unordered",
}
JIGSAW_ORDER_CHOICES = (*JIGSAW_ORDERS, "Random")
JIGSAW_PIECES_RANGE = (12, 150)
