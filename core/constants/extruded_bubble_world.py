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
# dissolving), alpha, nominal radius, trails (1 / 0), the trail's length (world), then from WAKE_PATH its path:
# WAKE_POINTS world points evenly spaced from just behind the bubble back along the water it has passed through.
WAKE_POINTS = 16
WAKE_PATH = 10
WAKE_STRIDE = WAKE_PATH + 3 * WAKE_POINTS
