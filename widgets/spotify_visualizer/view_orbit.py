"""Live view orbiting for 3D freeform Visualizer modes (W/A/S/D, Alt + left drag).

A mode opts in through its descriptor's ``view_orbit_settings`` (its turn and tilt
presentation settings; turn spans -1..1 as a full circle and wraps, tilt clamps to its
canonical range) and ``view_orbit_steps`` (one step of each: a drag's unit, and a held key's
rate is ``VIEW_ORBIT_STEPS_PER_SECOND`` of them).

Held keys turn the view at a steady rate on the logical clock, never per OS key repeat (which
stops for an older key when another is pressed): the GUI thread publishes one immutable
``ViewOrbitMotion`` (the view at a moment, and its rates) whenever the held keys change, and the
logical capture evaluates it at its own frame time (``apply_view_orbit_motion``). The GUI thread
is the only writer; the record is replaced whole, so the capture never sees half an update. A
drag steps the view directly. Nothing here saves: the caller persists once, when orbiting stops
(``resolve_visualizer_view_orbit`` in ``core.settings.visualizer_view_orbit``).

Keys move the camera around the scene: W up over it, S down, A to the left, D to the right
(the near end of the row then swings toward the side the camera went); a drag turns the scene
toward it (rendering/runtime_input.py).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

# A held key's pace, in its mode's steps per second (2 degree steps: 60 degrees a second).
VIEW_ORBIT_STEPS_PER_SECOND = 30.0
# The presentation-state attribute holding the live motion (absent or None when keys are idle).
_MOTION = "_view_orbit_motion"
_DRAG = "_view_orbit_drag_velocity"
_INERTIA = "_view_orbit_inertia"
# Presentation-only release tail, sampled by the existing logical frame clock.
# The normal Sphere shader's continuous base rotation is independent of this view pose.
SPHERE_INERTIA_SECONDS = 0.9
SPHERE_INERTIA_MAX_AGE = 0.18


@dataclass(frozen=True, slots=True)
class OrbitDragVelocity:
    mode_id: str
    time: float
    turn_rate: float
    tilt_rate: float


@dataclass(frozen=True, slots=True)
class OrbitInertia:
    mode_id: str
    since: float
    duration: float
    turn_start: float
    tilt_start: float
    turn_delta: float
    tilt_delta: float


def inertia_pose(inertia: OrbitInertia, now: float) -> Dict[str, float]:
    """Finite smooth deceleration, ending at exactly the once-persisted final view."""
    progress = max(0.0, min(1.0, (float(now) - inertia.since) / inertia.duration))
    portion = 1.0 - (1.0 - progress) ** 3
    return {"sphere_turn": _wrap(inertia.turn_start + inertia.turn_delta * portion),
            "sphere_tilt": _clamped("sphere_tilt", inertia.tilt_start + inertia.tilt_delta * portion)}



@dataclass(frozen=True, slots=True)
class ViewOrbitMotion:
    """The view of ``mode_id`` at ``since`` (logical-clock seconds, ``time.time()``) and how fast
    it is turning (setting units per second)."""

    mode_id: str
    turn: float
    tilt: float
    turn_rate: float
    tilt_rate: float
    since: float


def view_orbit_settings(mode_id: str) -> tuple[str, str] | tuple[()]:
    """The (turn, tilt) settings orbiting adjusts for ``mode_id``, or () when it has none."""
    try:
        return get_visualizer_mode_descriptor(mode_id).view_orbit_settings
    except (KeyError, ValueError):
        return ()


def _wrap(turn: float) -> float:
    return (turn + 1.0) % 2.0 - 1.0                              # a full circle: round and round


def _clamped(key: str, value: float) -> float:
    from widgets.spotify_visualizer.config_applier import presentation_setting_range

    low, high = presentation_setting_range(key)
    return max(low, min(high, value))


def orbit_motion_values(motion: ViewOrbitMotion, now: float) -> Dict[str, float]:
    """The view ``motion`` has reached at ``now``."""
    turn_key, tilt_key = view_orbit_settings(motion.mode_id)
    elapsed = max(0.0, float(now) - motion.since)
    return {turn_key: _wrap(motion.turn + motion.turn_rate * elapsed),
            tilt_key: _clamped(tilt_key, motion.tilt + motion.tilt_rate * elapsed)}


def _motion(host: Any, mode_id: str) -> ViewOrbitMotion | None:
    motion = getattr(host, _MOTION, None)
    return motion if motion is not None and motion.mode_id == mode_id else None


def view_orbit_values(host: Any, mode_id: str, now: float | None = None) -> Dict[str, float]:
    """The live turn and tilt of ``mode_id``: the held-key motion's view at ``now`` if one is on,
    else the presentation state's settings."""
    motion = _motion(host, mode_id)
    if motion is not None and now is not None:
        return orbit_motion_values(motion, now)
    inertia = getattr(host, _INERTIA, None)
    if mode_id == 'sphere' and isinstance(inertia, OrbitInertia) and now is not None and inertia.mode_id == mode_id:
        return inertia_pose(inertia, now)
    return {key: float(getattr(host, f"_{key}")) for key in view_orbit_settings(mode_id)}


def apply_view_orbit_motion(host: Any, mode_id: str, values: Mapping[str, object], now: float) -> Dict[str, object]:
    """A capture's ``values`` with the held-key view at ``now`` (logical thread; read only)."""
    motion = _motion(host, mode_id)
    return dict(values) if motion is None else {**values, **orbit_motion_values(motion, now)}


def set_view_orbit_rates(host: Any, mode_id: str, turn_steps: float, tilt_steps: float,
                         now: float) -> Dict[str, float]:
    """Held keys changed (GUI thread): continue from the view reached at ``now`` at the new rates
    (in steps, each ``VIEW_ORBIT_STEPS_PER_SECOND`` a second). Returns that view ({} when the
    mode cannot orbit)."""
    keys = view_orbit_settings(mode_id)
    if not keys:
        return {}
    turn_step, tilt_step = get_visualizer_mode_descriptor(mode_id).view_orbit_steps
    turn_key, tilt_key = keys
    values = view_orbit_values(host, mode_id, now)
    setattr(host, _INERTIA, None)  # held keys take over from the exact live view
    setattr(host, _DRAG, None)  # a later key release is not a mouse flick
    if mode_id == 'sphere':
        from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
        apply_presentation_vis_mode_kwargs(host, values)
    setattr(host, _MOTION, ViewOrbitMotion(
        mode_id, values[turn_key], values[tilt_key],
        turn_step * VIEW_ORBIT_STEPS_PER_SECOND * float(turn_steps),
        tilt_step * VIEW_ORBIT_STEPS_PER_SECOND * float(tilt_steps), float(now)))
    return values


def stop_view_orbit_motion(host: Any, now: float) -> tuple[str, Dict[str, float]] | None:
    """No key is held any more (GUI thread): settle the view reached at ``now`` into the
    presentation settings and drop the motion. Returns (mode id, view), or None if none was on."""
    motion = getattr(host, _MOTION, None)
    if motion is None:
        return None
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    values = orbit_motion_values(motion, now)
    turn_key, tilt_key = view_orbit_settings(motion.mode_id)
    # Freeze the record, write the settings, then drop the record: a capture between any two of
    # these steps sees the same settled view.
    setattr(host, _MOTION, ViewOrbitMotion(motion.mode_id, values[turn_key], values[tilt_key], 0.0, 0.0,
                                           float(now)))
    apply_presentation_vis_mode_kwargs(host, values)
    setattr(host, _MOTION, None)
    return motion.mode_id, values


def rebase_view_orbit_motion(host: Any, now: float) -> None:
    """A preset has replaced the view (GUI thread): keys still held carry on turning from it."""
    # A preset changes the authored pose even when no orbit keys are held.
    # Never let a pending drag tail overwrite the newly activated pose.
    setattr(host, _INERTIA, None)
    setattr(host, _DRAG, None)
    motion = getattr(host, _MOTION, None)
    if motion is None:
        return
    turn_key, tilt_key = view_orbit_settings(motion.mode_id)
    setattr(host, _MOTION, ViewOrbitMotion(motion.mode_id, float(getattr(host, f"_{turn_key}")),
                                           float(getattr(host, f"_{tilt_key}")), motion.turn_rate,
                                           motion.tilt_rate, float(now)))


def orbit_visualizer_view(host: Any, mode_id: str, turn_steps: float, tilt_steps: float,
                          now: float | None = None) -> Dict[str, float]:
    """Step the live view by (fractional) steps, as a drag does; returns the new values ({} when
    the mode cannot orbit). While keys are held the steps shift their motion instead."""
    keys = view_orbit_settings(mode_id)
    if not keys:
        return {}
    turn_key, tilt_key = keys
    turn_step, tilt_step = get_visualizer_mode_descriptor(mode_id).view_orbit_steps
    motion = _motion(host, mode_id)
    if motion is not None and now is not None:
        values = orbit_motion_values(motion, now)
        setattr(host, _MOTION, ViewOrbitMotion(
            mode_id, _wrap(values[turn_key] + turn_step * float(turn_steps)),
            _clamped(tilt_key, values[tilt_key] + tilt_step * float(tilt_steps)),
            motion.turn_rate, motion.tilt_rate, float(now)))
        return view_orbit_values(host, mode_id, now)
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    values = view_orbit_values(host, mode_id, now)
    setattr(host, _INERTIA, None)
    turn_delta = turn_step * float(turn_steps)
    tilt_delta = tilt_step * float(tilt_steps)
    if mode_id == 'sphere' and now is not None and (turn_delta or tilt_delta):
        previous = getattr(host, _DRAG, None)
        # A new gesture must not borrow velocity from an earlier gesture.
        dt = (float(now) - previous.time if isinstance(previous, OrbitDragVelocity)
              and previous.mode_id == mode_id and 0 < float(now) - previous.time < 0.18 else 1 / 60)
        dt = max(dt, 1 / 120)
        turn_rate = max(-0.85, min(0.85, turn_delta / dt))
        tilt_rate = max(-0.7, min(0.7, tilt_delta / dt))
        if isinstance(previous, OrbitDragVelocity) and 0 < float(now) - previous.time < 0.18:
            turn_rate = 0.65 * turn_rate + 0.35 * previous.turn_rate
            tilt_rate = 0.65 * tilt_rate + 0.35 * previous.tilt_rate
        setattr(host, _DRAG, OrbitDragVelocity(mode_id, float(now), turn_rate, tilt_rate))
    apply_presentation_vis_mode_kwargs(host, {
        turn_key: _wrap(values[turn_key] + turn_delta),
        tilt_key: values[tilt_key] + tilt_delta,
    })
    return view_orbit_values(host, mode_id, now)


def release_sphere_orbit_inertia(host: Any, now: float) -> Dict[str, float] | None:
    """Settle a Sphere drag onto the existing presentation clock, no additional timer.

    Persist the analytic endpoint once at release. Until the tail finishes, captures
    read its intermediate view, then naturally read the identical saved endpoint.
    """
    sample = getattr(host, _DRAG, None)
    setattr(host, _DRAG, None)
    if (not isinstance(sample, OrbitDragVelocity) or sample.mode_id != 'sphere'
            or not 0 <= float(now) - sample.time <= SPHERE_INERTIA_MAX_AGE):
        return None
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    start = view_orbit_values(host, 'sphere', now)
    turn_delta = max(-0.16, min(0.16, sample.turn_rate * SPHERE_INERTIA_SECONDS / 3))
    tilt_delta = max(-0.12, min(0.12, sample.tilt_rate * SPHERE_INERTIA_SECONDS / 3))
    if abs(turn_delta) + abs(tilt_delta) < 0.0005:
        return None
    inertia = OrbitInertia('sphere', float(now), SPHERE_INERTIA_SECONDS,
                           start['sphere_turn'], start['sphere_tilt'], turn_delta, tilt_delta)
    final = inertia_pose(inertia, float(now) + SPHERE_INERTIA_SECONDS)
    apply_presentation_vis_mode_kwargs(host, final)
    setattr(host, _INERTIA, inertia)
    return final
