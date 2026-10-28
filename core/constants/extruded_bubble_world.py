"""Single fixed world-volume dimensions for Extruded Bubble.

Pure imports, shared by Settings endpoint admission, logical simulation and GPU
projection. No camera scale, viewport, preset or mode-specific copy owns geometry.
"""
WORLD_UNIT = 9.0
WORLD_CENTER = (0.0, 0.0, 0.0)
WORLD_HALF = (18.0, 8.0, 18.0)
WORLD_MARGIN = 0.25 * WORLD_UNIT
WATER_SURFACE_Y = 9.0
SPECKS_FULL = 216000
SNOW_FULL = 2500


def particle_amount(emission: float) -> float:
    """Canonical resolved free-particle amount (the authored follower may overshoot its handles)."""
    return max(0.,min(1.,float(emission)))


def speck_density(emission: float) -> float:
    return particle_amount(emission) ** 2
# One wake emitter's record (simulation -> GPU): x, y, z, reacted radius, stable ident, retirement (-1 live, 0..1
# dissolving), alpha, nominal radius, trails (1 / 0), then the trail's spacing (world distance between its points),
# its point count, the bubble's water index (spacings travelled; the water c spacings behind it stays put), its lead
# (spacings past its newest point), its size followed slowly, then from WAKE_PATH its path: WAKE_POINTS world points
# newest first, laid one spacing apart along the water the bubble has passed through (the bubble itself is the head).
WAKE_POINTS = 12
WAKE_SPACING = 9
WAKE_COUNT = 10
WAKE_WATER = 11
WAKE_LEAD = 12
WAKE_RADIUS = 13
WAKE_PATH = 14
WAKE_STRIDE = WAKE_PATH + 3 * WAKE_POINTS
