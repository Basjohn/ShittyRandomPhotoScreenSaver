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
# dissolving), alpha, nominal radius, then the trail's lead direction (behind the bubble's recent motion) and its
# settle direction (behind its older motion), both world unit vectors.
WAKE_STRIDE = 14
