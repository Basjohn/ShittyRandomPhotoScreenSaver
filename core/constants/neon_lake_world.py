"""Neon Lake Basin's fixed world dimensions, shared by rendering and its framed camera (pure imports)."""
from __future__ import annotations

DEPTH = 2.4    # the basin's length into the distance, in field heights


def half_width(aspect: float) -> float:
    """The basin's half width for a field ``aspect`` times wider than tall (wide enough that
    its sides leave the view when it is turned)."""
    return 0.8 * max(1.0, float(aspect)) + 0.9


NOMINAL_HALF_WIDTH = half_width(16.0 / 9.0)
