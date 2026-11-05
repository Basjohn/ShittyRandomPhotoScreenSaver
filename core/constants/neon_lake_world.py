"""Neon Lake Basin's fixed world dimensions, shared by rendering and its framed camera (pure imports)."""
from __future__ import annotations

DEPTH = 2.4    # the basin's length into the distance, in field heights
# The water's physical crest is a soft cap (tanh) at this height. 0.18 squashed every full-height authored wave to
# the same crest, so a big hit looked like an ordinary one (2026-10-24).
WATER_PEAK = 0.36


# The physical width at the accepted basic 1.5 rectangle. Edge resize now
# reveals/crops this world instead of stretching terrain/events and moving its floor.
NOMINAL_HALF_WIDTH = 2.1

# Beyond the authored grid the land rolls on toward the horizon: past the near continuation it settles into
# broad far hills (FAR_HILLS: base, amplitude and frequencies on basin uv), and the whole distant world
# curves away only gently (DISTANT_CURVATURE per basin uv squared past DISTANT_FLAT), so a real
# terrain/sky tangency remains as the horizon line while land reaches tens of units out.
FAR_HILLS = (0.10, 0.05, 0.9, 0.6, 0.7, 0.5)
DISTANT_FLAT = 0.20
# The grid's edge continuation leaves the boundary for rolling ground over this basin-uv distance. A long
# descent extruded every edge ridge into a straight band running out of the grid (drawn as a long straight
# skyline streak wherever the camera looks along an edge), so it settles within about a third of the basin.
CONTINUATION_DESCENT = (0.02, 0.30)
DISTANT_CURVATURE = 0.22
# How far the overscan mesh reaches past the basin (left, right, front, back) in basin uv.
FAR_OVERSCAN = (12.0, 12.0, 8.0, 20.0)   # the eye box reaches about 5.3 basin uv in front
# The camera's far plane, in scene units: beyond the farthest overscan seen from the loosest eye.
FAR_PLANE = 120.0
# Since the land reaches the horizon (2026-11-05) the view may look a little above the level and further down and
# turn further round; collision with the land and water (the camera floor), not tighter clamps, bounds the eye.
TILT_RANGE = (-0.15, 0.70)
TURN_RANGE = (-0.75, 0.75)
