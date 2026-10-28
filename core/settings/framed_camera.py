"""The standard physical camera for framed 3D Visualizer modes (operator 2026-10-24).

Extruded Bubble's camera is the standard; every framed 3D mode declares a ``FramedCameraSpec`` (its pivot, orbit
distance, pitch/yaw mapping, admitted eye box and optional floor/ceiling) through its descriptor's
``framed_camera`` and shares everything else: orbit axes, the orbit/pan/dolly baseline, the editable eye offset,
bounds, flight, reset and the GLSL projection (``rendering.gl_programs.scene3d``).

The world stays fixed. Orbit turns the eye around the pivot; Scene Scale dollies it toward the pivot without
changing the focal angle; Scene Pan translates the eye in the image plane; Camera Position is an extra
translation, normalized by the spec's ``offset_scale``. Bounds act on the actual eye, never on a slider, so a
view may approach a flat horizon while the eye itself never enters the scene's solid geometry.

Pure and Qt-free: admission, flight on the capture clock, Settings editors and renderers all call it.
"""
from __future__ import annotations

import functools
import importlib
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass

Vec3 = tuple[float, float, float]
Floor = Callable[[float, float], float]
CAMERA_SUFFIXES = ('turn', 'tilt', 'scene_scale', 'scene_pan_x', 'scene_pan_y', 'camera_fov', 'camera_position')
FOV_RANGE = (35.0, 62.0)


@dataclass(frozen=True, slots=True)
class FramedCameraSpec:
    prefix: str                     # the mode's settings prefix, e.g. 'extruded_bubble_'
    pivot: Vec3                     # orbit pivot in world units
    orbit_distance: float           # eye distance at Scene Scale 1
    pitch_base_degrees: float       # pitch at tilt 0; positive pitch puts the eye below the pivot, looking up
    pitch_span_degrees: float       # pitch change per unit of tilt
    yaw_span: float                 # radians of yaw per unit of turn
    tilt_range: tuple[float, float]
    eye_center: Vec3                # admitted eye box (the clearance is kept inside it)
    eye_half: Vec3
    clearance: float
    offset_scale: Vec3              # Camera Position units per world unit, per axis
    travel_speed: float             # keyboard flight, world units per second
    fov_range: tuple[float, float] = FOV_RANGE
    surface_ceiling: float | None = None   # orbit/pan baseline ceiling while the mode's surface bound applies
    # Optional mode hooks, as "module:function" (lazy, so the spec stays importable from Qt-free code):
    # surface_bound(values) -> bool, floor(values) -> Floor | None, context_suffixes extra settings they read.
    surface_bound_hook: str = ''
    floor_hook: str = ''
    context_suffixes: tuple[str, ...] = ()
    # Optional "module:function"(get) -> {role: six normalized coords}: faint scene guides for the Settings editor.
    editor_references_hook: str = ''

    def key(self, suffix: str) -> str:
        return self.prefix + suffix

    @property
    def input_keys(self) -> tuple[str, ...]:
        return tuple(self.prefix + s for s in (*CAMERA_SUFFIXES, *self.context_suffixes))

    def surface_bound(self, values: Mapping[str, object]) -> bool:
        return bool(_hook(self.surface_bound_hook)(values)) if self.surface_bound_hook else False

    def floor(self, values: Mapping[str, object]) -> Floor | None:
        return _hook(self.floor_hook)(values) if self.floor_hook else None


def _hook(path: str):
    module, _, name = path.partition(':')
    return getattr(importlib.import_module(module), name)


@functools.lru_cache(maxsize=None)
def spec_for_mode(mode_id: str) -> FramedCameraSpec | None:
    """The mode's declared framed camera, or None when it has none (descriptors are static)."""
    from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
    try:
        path = get_visualizer_mode_descriptor(mode_id).framed_camera
    except (KeyError, ValueError):
        return None
    return _hook(path) if path else None


@functools.lru_cache(maxsize=1)
def FRAMED_CAMERA_SPECS() -> tuple[FramedCameraSpec, ...]:
    """Every registered mode's framed camera."""
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(_hook(d.framed_camera) for d in iter_all_visualizer_mode_descriptors() if d.framed_camera)


def pitch_radians(spec: FramedCameraSpec, tilt: float) -> float:
    low, high = spec.tilt_range
    return math.radians(spec.pitch_base_degrees + spec.pitch_span_degrees * max(low, min(high, float(tilt))))


def camera_axes(spec: FramedCameraSpec, turn: float, tilt: float) -> tuple[float, ...]:
    """(right, up, back) world axes, column order; the eye looks along -back."""
    pitch = pitch_radians(spec, tilt)
    yaw = spec.yaw_span * float(turn)
    cp, sp, cy, sy = math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    right = (cy, 0.0, -sy)
    back = (sy * cp, -sp, cy * cp)
    up = (back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2],
          back[0] * right[1] - back[1] * right[0])
    return (*right, *up, *back)


def tan_half_fov(fov_y_degrees: float, fov_range: tuple[float, float] = FOV_RANGE) -> float:
    return math.tan(math.radians(max(fov_range[0], min(fov_range[1], float(fov_y_degrees)))) / 2.0)


def camera_baseline(spec: FramedCameraSpec, turn: float, tilt: float, scale: float = 1., pan_x: float = 0.,
                    pan_y: float = 0., fov_y_degrees: float = 45., ceiling: float | None = None, *, axes=None):
    """Orbit/pan reference before the independent position offset; never a second eye."""
    axes = camera_axes(spec, turn, tilt) if axes is None else axes
    right, up, back = axes[:3], axes[3:6], axes[6:9]
    pivot = spec.pivot
    distance = spec.orbit_distance / max(float(scale), 1e-3)
    if ceiling is not None and back[1] > 1e-9:
        distance = min(distance, max(1., (ceiling - pivot[1]) / back[1]))
    tan_y = tan_half_fov(fov_y_degrees, spec.fov_range)
    dx, dy = -2. * distance * tan_y * float(pan_x), 2. * distance * tan_y * float(pan_y)
    y = pivot[1] + distance * back[1] + dx * right[1] + dy * up[1]
    if ceiling is not None and y > ceiling and up[1] > 1e-9:
        dy -= (y - ceiling) / up[1]
    return tuple(pivot[i] + distance * back[i] + dx * right[i] + dy * up[i] for i in range(3))


def bound_eye(spec: FramedCameraSpec, eye, floor: Floor | None = None) -> Vec3:
    """The eye inside the admitted box (clearance kept) and, with a floor, at least ``clearance`` above it."""
    x, y, z = (max(c - h + spec.clearance, min(c + h - spec.clearance, float(p)))
               for p, c, h in zip(eye, spec.eye_center, spec.eye_half))
    if floor is not None:
        y = min(spec.eye_center[1] + spec.eye_half[1] - spec.clearance, max(y, floor(x, z) + spec.clearance))
    return x, y, z


def resolve_camera_position(spec: FramedCameraSpec, turn: float, tilt: float, scale: float = 1.,
                            pan_x: float = 0., pan_y: float = 0., fov_y_degrees: float = 45.,
                            position_offset=(0., 0., 0.), ceiling: float | None = None,
                            floor: Floor | None = None, *, axes=None):
    """The bounded world eye AND its effective normalized offset."""
    base = camera_baseline(spec, turn, tilt, scale, pan_x, pan_y, fov_y_degrees, ceiling, axes=axes)
    scale_xyz = spec.offset_scale
    requested = tuple(base[i] + float(position_offset[i]) * scale_xyz[i] for i in range(3))
    eye = bound_eye(spec, requested, floor)
    # Preserve exact legal input values, avoiding repeated normalize/round-trip churn.
    offset = (tuple(position_offset) if eye == requested
              else tuple((eye[i] - base[i]) / scale_xyz[i] for i in range(3)))
    return eye, offset


def ceiling_for(spec: FramedCameraSpec, values: Mapping[str, object]) -> float | None:
    return spec.surface_ceiling if spec.surface_ceiling is not None and spec.surface_bound(values) else None


def resolve_from_values(spec: FramedCameraSpec, values: Mapping[str, object], *, axes=None):
    """(eye, offset) from the mode's complete camera settings."""
    def get(name):
        return values[spec.key(name)]
    return resolve_camera_position(spec, get('turn'), get('tilt'), get('scene_scale'), get('scene_pan_x'),
                                   get('scene_pan_y'), get('camera_fov'), get('camera_position'),
                                   ceiling_for(spec, values), spec.floor(values), axes=axes)


def admit_camera_parameters(spec: FramedCameraSpec, values: Mapping[str, object]) -> Vec3:
    """Joint admission of the Camera Position offset; the caller supplies the complete camera settings."""
    return resolve_from_values(spec, values)[1]


def viewport_tangents(fov_y_degrees: float, aspect: float, aperture_scale: float = 1.,
                      fov_range: tuple[float, float] = FOV_RANGE) -> tuple[float, float]:
    """Centred aperture through the authored lens; aspect always matches the real target."""
    if not math.isfinite(aspect) or aspect <= 0 or not math.isfinite(aperture_scale) or aperture_scale <= 0:
        raise ValueError('Framed aperture dimensions must be finite and positive')
    tan_y = tan_half_fov(fov_y_degrees, fov_range) * aperture_scale
    return tan_y * aspect, tan_y


def perspective_matrix(tan: tuple[float, float], near: float, far: float):
    """Projection from the very same aperture used by ray, optical and landmark consumers."""
    return (1. / tan[0], 0., 0., 0., 0., 1. / tan[1], 0., 0., 0., 0.,
            (far + near) / (near - far), -1., 0., 0., 2. * far * near / (near - far), 0.)


def view_matrices(spec: FramedCameraSpec, turn: float, tilt: float, aspect: float, fov_y_degrees: float,
                  near: float, far: float, *, aperture_scale: float = 1.):
    """(view_to_world, world_to_view) column-major mat3s, (tan x, tan y), and the GL mat4 projection."""
    view_to_world = camera_axes(spec, turn, tilt)
    right, up, back = view_to_world[:3], view_to_world[3:6], view_to_world[6:9]
    world_to_view = (right[0], up[0], back[0], right[1], up[1], back[1], right[2], up[2], back[2])
    tan = viewport_tangents(fov_y_degrees, aspect, aperture_scale, spec.fov_range)
    return view_to_world, world_to_view, tan, perspective_matrix(tan, near, far)


def project_point(spec: FramedCameraSpec, point, eye, turn: float, tilt: float, aspect: float,
                  fov_y_degrees: float, *, axes=None) -> tuple[float, float, float] | None:
    """Normalized device x, y (y up) and view depth of a world point; None behind the eye."""
    axes = camera_axes(spec, turn, tilt) if axes is None else axes
    right, up, back = axes[:3], axes[3:6], axes[6:9]
    rel = tuple(p - e for p, e in zip(point, eye))
    depth = -sum(a * b for a, b in zip(rel, back))
    if depth <= 1e-6:
        return None
    tan_y = tan_half_fov(fov_y_degrees, spec.fov_range)
    x = sum(a * b for a, b in zip(rel, right)) / (depth * tan_y * aspect)
    y = sum(a * b for a, b in zip(rel, up)) / (depth * tan_y)
    return x, y, depth
