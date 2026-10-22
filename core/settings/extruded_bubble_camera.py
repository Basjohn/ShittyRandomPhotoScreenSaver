"""Pure EB camera geometry shared by admission, motion, editors and projection.

The world stays fixed. A three-unit water clearance bounds the actual eye, not
the offset slider: it preserves the canonical home and guarantees at least that
much populated-domain path in every direction. This is geometry, not a promise
of perceptual density or readable subpixel materials.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from core.constants.extruded_bubble_world import WORLD_CENTER, WORLD_HALF, WATER_SURFACE_Y

ORBIT_DISTANCE = 15.0
ORBIT_PIVOT = WORLD_CENTER
CAMERA_CLEARANCE = 3.0
CAMERA_INPUT_KEYS = tuple('extruded_bubble_' + name for name in (
    'turn', 'tilt', 'scene_scale', 'scene_pan_x', 'scene_pan_y',
    'camera_fov', 'camera_position', 'light_type'))


def camera_axes(turn: float, tilt: float) -> tuple[float, ...]:
    pitch = math.radians(16.0 + 90.0 * float(tilt))
    yaw = math.pi * float(turn)
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    right = (cy, 0.0, -sy)
    back = (sy * cp, -sp, cy * cp)
    up = (back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2],
          back[0] * right[1] - back[1] * right[0])
    return (*right, *up, *back)


def camera_baseline(turn: float, tilt: float, scale: float = 1., pan_x: float = 0., pan_y: float = 0.,
                    fov_y_degrees: float = 45., surface_bound: bool = True, *, axes=None):
    """Orbit/pan reference before the independent XYZ offset; never a second eye."""
    axes = camera_axes(turn, tilt) if axes is None else axes
    right, up, back = axes[:3], axes[3:6], axes[6:9]
    distance = ORBIT_DISTANCE / max(float(scale), 1e-3)
    ceiling = WATER_SURFACE_Y - .5
    # Retain the authored orbit/pan calibration. The joint world bound below
    # applies after offset composition, equally to Surface and Deep cameras.
    if surface_bound and back[1] > 1e-9:
        distance = min(distance, max(1., (ceiling - ORBIT_PIVOT[1]) / back[1]))
    tan_y = math.tan(math.radians(max(35., min(62., float(fov_y_degrees)))) / 2.)
    dx, dy = -2. * distance * tan_y * float(pan_x), 2. * distance * tan_y * float(pan_y)
    y = ORBIT_PIVOT[1] + distance * back[1] + dx * right[1] + dy * up[1]
    if surface_bound and y > ceiling and up[1] > 1e-9:
        dy -= (y - ceiling) / up[1]
    return tuple(ORBIT_PIVOT[i] + distance * back[i] + dx * right[i] + dy * up[i] for i in range(3))


def bound_camera_eye(eye):
    return tuple(max(c - h + CAMERA_CLEARANCE, min(c + h - CAMERA_CLEARANCE, float(p)))
                 for p, c, h in zip(eye, WORLD_CENTER, WORLD_HALF))


def resolve_camera_position(turn: float, tilt: float, scale: float = 1., pan_x: float = 0., pan_y: float = 0.,
                            fov_y_degrees: float = 45., position_offset=(0., 0., 0.),
                            surface_bound: bool = True, *, axes=None):
    """Return bounded world eye AND its effective existing normalized offset."""
    base = camera_baseline(turn, tilt, scale, pan_x, pan_y, fov_y_degrees, surface_bound, axes=axes)
    requested = tuple(base[i] + float(position_offset[i]) * WORLD_HALF[i] for i in range(3))
    eye = bound_camera_eye(requested)
    # Preserve exact legal input values, avoiding repeated normalize/round-trip churn.
    offset = tuple(position_offset) if eye == requested else tuple((eye[i] - base[i]) / WORLD_HALF[i] for i in range(3))
    return eye, offset


def admit_camera_parameters(parameters: Mapping[str, object]) -> tuple[float, float, float]:
    """Joint admission; caller supplies the complete existing camera settings."""
    def get(name):
        return parameters['extruded_bubble_' + name]
    return resolve_camera_position(get('turn'), get('tilt'), get('scene_scale'),
        get('scene_pan_x'), get('scene_pan_y'), get('camera_fov'), get('camera_position'),
        get('light_type') == 'Sunlit Surface')[1]
