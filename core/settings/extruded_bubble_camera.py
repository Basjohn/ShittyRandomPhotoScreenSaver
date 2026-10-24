"""Extruded Bubble's framed camera: the first ``FramedCameraSpec`` of the shared standard (``framed_camera``).

The world stays fixed. A three-unit water clearance bounds the actual eye, not
the offset slider: it preserves the canonical home and guarantees at least that
much populated-domain path in every direction. This is geometry, not a promise
of perceptual density or readable subpixel materials.
"""
from __future__ import annotations

from collections.abc import Mapping

from core.constants.extruded_bubble_world import WORLD_CENTER, WORLD_HALF, WATER_SURFACE_Y
from core.settings import framed_camera as fc

ORBIT_DISTANCE = 15.0
ORBIT_PIVOT = WORLD_CENTER
CAMERA_CLEARANCE = 3.0

SPEC = fc.FramedCameraSpec(
    prefix='extruded_bubble_', pivot=ORBIT_PIVOT, orbit_distance=ORBIT_DISTANCE,
    # Looking up toward the surface by an authored 16 degrees; tilt +-0.5 pitches +-45 degrees beyond it.
    pitch_base_degrees=16.0, pitch_span_degrees=90.0, yaw_span=fc.math.pi, tilt_range=(-0.5, 0.5),
    eye_center=WORLD_CENTER, eye_half=WORLD_HALF, clearance=CAMERA_CLEARANCE, offset_scale=WORLD_HALF,
    travel_speed=5.5, surface_ceiling=WATER_SURFACE_Y - .5,
    surface_bound_hook='core.settings.extruded_bubble_camera:surface_bound', context_suffixes=('light_type',))
CAMERA_INPUT_KEYS = SPEC.input_keys


def surface_bound(values: Mapping[str, object]) -> bool:
    return values['extruded_bubble_light_type'] == 'Sunlit Surface'


def camera_axes(turn: float, tilt: float) -> tuple[float, ...]:
    return fc.camera_axes(SPEC, turn, tilt)


def camera_baseline(turn: float, tilt: float, scale: float = 1., pan_x: float = 0., pan_y: float = 0.,
                    fov_y_degrees: float = 45., surface_bound: bool = True, *, axes=None):
    """Orbit/pan reference before the independent XYZ offset; never a second eye."""
    return fc.camera_baseline(SPEC, turn, tilt, scale, pan_x, pan_y, fov_y_degrees,
                              SPEC.surface_ceiling if surface_bound else None, axes=axes)


def bound_camera_eye(eye):
    return fc.bound_eye(SPEC, eye)


def resolve_camera_position(turn: float, tilt: float, scale: float = 1., pan_x: float = 0., pan_y: float = 0.,
                            fov_y_degrees: float = 45., position_offset=(0., 0., 0.),
                            surface_bound: bool = True, *, axes=None):
    """Return bounded world eye AND its effective existing normalized offset."""
    return fc.resolve_camera_position(SPEC, turn, tilt, scale, pan_x, pan_y, fov_y_degrees, position_offset,
                                      SPEC.surface_ceiling if surface_bound else None, axes=axes)


def admit_camera_parameters(parameters: Mapping[str, object]) -> tuple[float, float, float]:
    """Joint admission; caller supplies the complete existing camera settings."""
    return fc.admit_camera_parameters(SPEC, parameters)
