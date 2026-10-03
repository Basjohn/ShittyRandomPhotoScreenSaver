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
from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

# A held key's pace, in its mode's steps per second (2 degree steps: 60 degrees a second).
VIEW_ORBIT_STEPS_PER_SECOND = 30.0
# The presentation-state attribute holding the live motion (absent or None when keys are idle).
_MOTION = "_view_orbit_motion"


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

    values = view_orbit_values(host, mode_id)
    apply_presentation_vis_mode_kwargs(host, {
        turn_key: _wrap(values[turn_key] + turn_step * float(turn_steps)),
        tilt_key: values[tilt_key] + tilt_step * float(tilt_steps),
    })
    return view_orbit_values(host, mode_id)
