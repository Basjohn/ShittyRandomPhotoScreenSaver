"""Neon Lake Basin's fixed world dimensions, shared by rendering and its framed camera (pure imports)."""
from __future__ import annotations

DEPTH = 2.4    # the basin's length into the distance, in field heights
# The water's physical crest is a soft cap (tanh) at this height. 0.18 squashed every full-height authored wave to
# the same crest, so a big hit looked like an ordinary one (2026-10-24).
WATER_PEAK = 0.36


# The physical width at the accepted basic 1.5 rectangle. Edge resize now
# reveals/crops this world instead of stretching terrain/events and moving its floor.
NOMINAL_HALF_WIDTH = 2.1
