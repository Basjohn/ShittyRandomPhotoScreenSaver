"""Waveform's fixed floor and forward clipping contract for the shared framed camera.

The spec remains with the authored scene. Admission, flight and raster rendering
all consume this floor through its spec hook; projection never admits geometry
behind the eye, including in Orthographic.
"""
from __future__ import annotations
import itertools
import numpy as np
import math
from core.settings.framed_camera import GroundedOrbitSpec

FLOOR_Y = 0.0
NEAR = 0.3
FAR = 200.0
YAW_SPAN = math.radians(35.)
# Low grounded eye with a physical near-level tilt endpoint; keep the floor in view.
# The closer radius also stays outside the maximum deformed sheet's transverse domain at either yaw limit.
GROUNDED_ORBIT = GroundedOrbitSpec(radius_range=(8.5,16.),eye_height=2.6,minimum_downward_pitch_degrees=.5)


def floor_height(x: float, z: float) -> float:
    return FLOOR_Y


def floor(values):
    """The fixed world floor, independent of viewport, camera and audio."""
    return floor_height


def floor_coverage_bounds(view, projection) -> tuple[float, float, float, float]:
    """World ``(min_x, min_z, max_x, max_z)`` covering the clipped physical view.

    ``view`` and ``projection`` are finite row-major 4x4 matrices, as returned
    by the production physical camera. Unproject all eight OpenGL clip corners
    at near/far NDC z=-1/+1. Their XZ AABB contains the whole convex frustum,
    hence every visible intersection with the fixed floor at FLOOR_Y. It may
    overdraw when the floor occupies only part of the view.

    These are mesh coverage bounds only. Floor height, world texture coordinates
    and physical scene geometry keep their existing world positions. Outward
    float32 rounding keeps uniform upload from shrinking the coverage rectangle.
    """
    view, projection = np.asarray(view, float), np.asarray(projection, float)
    if view.shape != (4,4) or projection.shape != (4,4) or not np.isfinite((view,projection)).all():
        raise ValueError('Floor coverage needs finite 4x4 physical camera matrices')
    try:
        inverse = np.linalg.inv(projection @ view)
    except np.linalg.LinAlgError as error:
        raise ValueError('Floor coverage needs an invertible physical camera') from error
    clip = np.array([(*corner,1.) for corner in itertools.product((-1.,1.),repeat=3)])
    world = clip @ inverse.T
    if not np.isfinite(world).all() or (np.abs(world[:,3]) < 1e-12).any():
        raise ValueError('Floor coverage needs a finite clipped physical frustum')
    # Consistent homogeneous signs are required for the convex finite frustum;
    # crossing w=0 would put an unbounded region between otherwise finite corners.
    if world[:,3].min() < 0. < world[:,3].max():
        raise ValueError('Floor coverage cannot cross projective infinity')
    xz = (world[:,:3] / world[:,3,None])[:,(0,2)]
    low = np.nextafter(xz.min(axis=0).astype(np.float32),np.float32(-np.inf)).astype(float)
    high = np.nextafter(xz.max(axis=0).astype(np.float32),np.float32(np.inf)).astype(float)
    if not np.isfinite((low,high)).all():
        raise ValueError('Floor coverage exceeds finite world-coordinate uniforms')
    return float(low[0]),float(low[1]),float(high[0]),float(high[1])
