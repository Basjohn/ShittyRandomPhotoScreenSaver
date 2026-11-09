"""Keyboard Studio camera navigation on the *existing* framed-camera trajectory.

Only evaluated on input/frame events, never loaded as a new runtime engine or timer.
The Studio's one camera pose owns the result. Production's flight solver enforces
bounds, floors, grounded orbit and the same W/A/S/D/Q/E/Shift-W/S semantics.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.settings.framed_camera import spec_for_mode
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from widgets.spotify_visualizer.view_orbit import (
    FramedFlightMotion, ViewOrbitMotion, VIEW_ORBIT_STEPS_PER_SECOND,
    framed_flight_position, orbit_motion_values,
)


def make_flight(mode: str, values: Mapping[str, Any], held: frozenset[str],
                shifted: bool, now: float) -> FramedFlightMotion | None:
    spec = spec_for_mode(mode)
    if spec is None:
        return None
    needed = spec.input_keys
    if any(key not in values for key in needed):
        return None
    # Production policy: Q/E yaw, Shift+W/S pitch, unshifted W/S travel,
    # A/D strafe. Grounded modes trade strafe for orbit (the same as runtime).
    yaw = float(("e" in held) - ("q" in held))
    pitch = float(("w" in held) - ("s" in held)) if shifted else 0.0
    strafe = float(("d" in held) - ("a" in held))
    travel = 0.0 if shifted else float(("w" in held) - ("s" in held))
    if spec.grounded_orbit is not None:
        yaw -= strafe
        strafe = 0.0
    d = get_visualizer_mode_descriptor(mode)
    return FramedFlightMotion(
        mode, now, tuple(values[spec.key("camera_position")]),
        float(values[spec.key("turn")]), float(values[spec.key("tilt")]),
        yaw * d.view_orbit_steps[0] * VIEW_ORBIT_STEPS_PER_SECOND,
        pitch * d.view_orbit_steps[1] * VIEW_ORBIT_STEPS_PER_SECOND,
        strafe, travel, float(values[spec.key("scene_scale")]),
        float(values[spec.key("scene_pan_x")]), float(values[spec.key("scene_pan_y")]),
        float(values[spec.key("camera_fov")]), spec.surface_bound(values), spec.floor(values),
    )


def flight_pose(motion: FramedFlightMotion, now: float) -> dict[str, object]:
    from widgets.spotify_visualizer.view_orbit import view_orbit_settings
    turn, tilt = view_orbit_settings(motion.mode_id)
    orbit = orbit_motion_values(ViewOrbitMotion(motion.mode_id, motion.turn, motion.tilt,
                                                motion.turn_rate, motion.tilt_rate,
                                                motion.since), now)
    spec = spec_for_mode(motion.mode_id)
    return {**orbit, spec.key("camera_position"): tuple(framed_flight_position(motion, now))}


def orbit_pose(mode: str, values: Mapping[str, Any], held: frozenset[str], dt: float) -> dict[str, float]:
    """Original WASD orbit for non-framed camera modes (no new camera system)."""
    from widgets.spotify_visualizer.view_orbit import view_orbit_settings
    turn, tilt = view_orbit_settings(mode)
    d = get_visualizer_mode_descriptor(mode)
    moment = ViewOrbitMotion(mode, float(values[turn]), float(values[tilt]),
                             float(("d" in held) - ("a" in held)) * d.view_orbit_steps[0]
                             * VIEW_ORBIT_STEPS_PER_SECOND,
                             float(("w" in held) - ("s" in held)) * d.view_orbit_steps[1]
                             * VIEW_ORBIT_STEPS_PER_SECOND, 0.0)
    return orbit_motion_values(moment, dt)
