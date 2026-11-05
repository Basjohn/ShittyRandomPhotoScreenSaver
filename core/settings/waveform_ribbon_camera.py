"""Waveform's fixed floor and forward clipping contract for the shared framed camera.

The spec remains with the authored scene. Admission, flight and raster rendering
all consume this floor through its spec hook. Perspective (the only projection)
retains positive clips; the infinite ground has its own world-plane intersection.
"""
from __future__ import annotations
import math
from core.settings.framed_camera import GroundedOrbitSpec

FLOOR_Y = 0.0
NEAR = 0.3
FAR = 200.0
FOV_RANGE = (2.,35.)
YAW_SPAN = math.radians(35.)
# Low grounded eye with a physical near-level tilt endpoint; keep the floor in view.
# The closer radius also stays outside the maximum deformed sheet's transverse domain at either yaw limit.
GROUNDED_ORBIT = GroundedOrbitSpec(radius_range=(64.,104.),eye_height=4.5,minimum_downward_pitch_degrees=.5)


def floor_height(x: float, z: float) -> float:
    return FLOOR_Y


def floor(values):
    """The fixed world floor, independent of viewport, camera and audio."""
    return floor_height
