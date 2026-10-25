"""Single fixed world-volume dimensions for Extruded Bubble.

Pure imports, shared by Settings endpoint admission, logical simulation and GPU
projection. No camera scale, viewport, preset or mode-specific copy owns geometry.
"""
WORLD_UNIT = 9.0
WORLD_CENTER = (0.0, 0.0, 0.0)
WORLD_HALF = (18.0, 8.0, 18.0)
WORLD_MARGIN = 0.25 * WORLD_UNIT
WATER_SURFACE_Y = 9.0
# One wake emitter's record (simulation -> GPU): x, y, z, reacted radius, stable ident, retirement (-1 live, 0..1
# dissolving), alpha, nominal radius, trails (1 / 0), the trail's length (world), its span (segments drawn from the
# bubble back), then from WAKE_PATH its path: WAKE_POINTS world points newest first, laid down evenly along the water
# the bubble has passed through (the bubble itself is the head; the GPU draws from it).
WAKE_POINTS = 12
WAKE_SPAN = 10
WAKE_PATH = 11
WAKE_STRIDE = WAKE_PATH + 3 * WAKE_POINTS
