"""Neon Lake Basin's fixed world dimensions, shared by rendering and its framed camera (pure imports)."""
from __future__ import annotations

DEPTH = 2.4    # the basin's length into the distance, in field heights
# The water's physical crest is a soft cap (tanh) at this height. 0.18 squashed every full-height authored wave to
# the same crest, so a big hit looked like an ordinary one (2026-10-24).
WATER_PEAK = 0.36


def half_width(aspect: float) -> float:
    """The basin's half width for a field ``aspect`` times wider than tall (wide enough that
    its sides leave the view when it is turned)."""
    return 0.8 * max(1.0, float(aspect)) + 0.9


NOMINAL_HALF_WIDTH = half_width(16.0 / 9.0)
