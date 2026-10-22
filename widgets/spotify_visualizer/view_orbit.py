"""Live 3D view control: freeform WASD orbit, EB Q/E yaw and camera-facing WASD flight,
plus shared Alt + left drag. No second camera, clock, or FOV manipulation.

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

Legacy freeform keys orbit as before. EB instead flies along its actual forward/right
basis with W/A/S/D; Q/E yaw and Shift+W/S pitch. A drag still orbits the scene. Both
forms use one capture clock and a single persistence owner (rendering/runtime_input.py).

Framed-camera policy (turn wrap or clamp, release inertia, scene pan envelope, Auto Rotate) is declared on each
mode's descriptor; nothing here branches on a mode id. Auto Rotate is one immutable ``AutoRotate`` record the GUI
thread publishes (armed at startup/swap completion and when orbiting stops, dropped by any camera input); the
logical capture evaluates it at its frame time, so the swivel costs no timer, polling or per-frame write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor

# A held key's pace, in its mode's steps per second (2 degree steps: 60 degrees a second).
VIEW_ORBIT_STEPS_PER_SECOND = 30.0
# Constant world-space EB flight speed; the camera FOV, scene scale and zoom stay unchanged.
FRAMED_CAMERA_TRAVEL_UNITS_PER_SECOND = 5.5
_FLIGHT = "_view_framed_flight_motion"
# The presentation-state attribute holding the live motion (absent or None when keys are idle).
_MOTION = "_view_orbit_motion"
_DRAG = "_view_orbit_drag_velocity"
_INERTIA = "_view_orbit_inertia"
_AUTO = "_view_orbit_auto_rotate"
# Presentation-only release tail, sampled by the existing logical frame clock (modes with
# ``view_orbit_inertia``). The normal Sphere shader's continuous base rotation is independent of this view pose.
VIEW_ORBIT_INERTIA_SECONDS = 0.9
VIEW_ORBIT_INERTIA_MAX_AGE = 0.18


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
    turn_key, tilt_key = view_orbit_settings(inertia.mode_id)
    return {turn_key: _turn_for_mode(inertia.mode_id, turn_key, inertia.turn_start + inertia.turn_delta * portion),
            tilt_key: _clamped(tilt_key, inertia.tilt_start + inertia.tilt_delta * portion)}


@dataclass(frozen=True, slots=True)
class AutoRotate:
    """The view of ``mode_id`` swivels from ``turn`` at ``rate`` (turn units per second) from ``start``
    (logical-clock seconds) on; before ``start`` it holds still."""

    mode_id: str
    turn: float
    rate: float
    start: float


def auto_rotate_turn(record: AutoRotate, turn_key: str, now: float) -> float:
    return _wrap(record.turn + record.rate * max(0.0, float(now) - record.start))



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


@dataclass(frozen=True, slots=True)
class FramedFlightMotion:
    """One immutable keyboard gesture for the EB physical camera, evaluated on capture time."""
    mode_id: str
    since: float
    offset: tuple[float, float, float]
    turn: float
    tilt: float
    turn_rate: float
    tilt_rate: float
    strafe: float
    travel: float
    scale: float = 1.
    pan_x: float = 0.
    pan_y: float = 0.
    fov: float = 45.
    surface_bound: bool = True
    pitch_limit_offset: tuple[float, float, float] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        limit = _pitch_limit_time(self)
        if limit > 0.:
            # This endpoint depends only on the immutable gesture, not frame
            # time. Resolve once at publication, not on every later capture.
            object.__setattr__(self, 'pitch_limit_offset', _changing_pitch_flight(self, limit))


def _flight_geometry(host):
    values = _eb_camera_values(host)
    return (values['extruded_bubble_scene_scale'], values['extruded_bubble_scene_pan_x'],
            values['extruded_bubble_scene_pan_y'], values['extruded_bubble_camera_fov'],
            values['extruded_bubble_light_type'] == 'Sunlit Surface')


def _eb_camera_values(host, values=None):
    from core.settings.default_contract import require_canonical_default
    from core.settings.extruded_bubble_camera import CAMERA_INPUT_KEYS
    result = {}
    for key in CAMERA_INPUT_KEYS:
        value = getattr(host, '_' + key, None)
        result[key] = require_canonical_default('widgets.spotify_visualizer.' + key) if value is None else value
    result.update(values or {})
    return result


def _bounded_eb_values(host, values):
    from core.settings.extruded_bubble_camera import admit_camera_parameters
    return {**values, 'extruded_bubble_camera_position': admit_camera_parameters(_eb_camera_values(host, values))}


def _constant_pitch_flight(motion, offset, start, end, strafe, travel):
    """Exact box saturation along circular horizontal motion, bounded for long holds.

    Split at coordinate extrema. A full zero-net cycle's translated-clamp map is
    idempotent, so repeated cycles need only one evaluation. Y saturates linearly.
    """
    from core.constants.extruded_bubble_world import WORLD_HALF
    from core.settings.extruded_bubble_camera import camera_baseline, bound_camera_eye
    pitch = math.radians(16. + 90.*max(-.5, min(.5, motion.tilt+motion.tilt_rate*start)))
    cp, sp = math.cos(pitch), math.sin(pitch)
    def baseline(t):
        return camera_baseline(motion.turn+motion.turn_rate*t,
            max(-.5, min(.5, motion.tilt+motion.tilt_rate*t)), motion.scale,
            motion.pan_x, motion.pan_y, motion.fov, motion.surface_bound)
    base = baseline(start)
    eye = list(bound_camera_eye(tuple(base[i]+offset[i]*WORLD_HALF[i] for i in range(3))))
    duration, speed = end-start, FRAMED_CAMERA_TRAVEL_UNITS_PER_SECOND
    omega = math.pi*motion.turn_rate
    theta = math.remainder(math.pi*(motion.turn+motion.turn_rate*start), math.tau)
    if abs(omega) < 1e-14:
        moved = (strafe*math.cos(theta)-travel*cp*math.sin(theta), travel*sp,
                 -strafe*math.sin(theta)-travel*cp*math.cos(theta))
        eye = list(bound_camera_eye(tuple(eye[i]+speed*duration*moved[i] for i in range(3))))
    else:
        period = math.tau/abs(omega)
        remainder = duration % period
        if min(remainder, period-remainder) < period*1e-12:
            remainder = 0.
        span = duration if duration < period else period+remainder
        # Baseline X=B*sin(theta)+P*cos(theta), Z=B*cos(theta)-P*sin(theta).
        b = base[0]*math.sin(theta)+base[2]*math.cos(theta)
        p = base[0]*math.cos(theta)-base[2]*math.sin(theta)
        a, d = b*omega+speed*strafe, p*omega+speed*travel*cp
        phases = (math.atan2(a, d), math.atan2(-d, a))
        for axis, phase in zip((0, 2), phases):
            low, high = sorted((theta, theta+omega*span))
            events = [0., span]
            for k in range(math.floor((low-phase)/math.pi), math.ceil((high-phase)/math.pi)+1):
                t = (phase+k*math.pi-theta)/omega
                if 0. < t < span:
                    events.append(t)
            events.sort()
            for first, last in zip(events, events[1:]):
                half = omega*(last-first)*.5
                mid = theta+omega*(first+last)*.5
                sh, sm, cm = math.sin(half), math.sin(mid), math.cos(mid)
                sinc = math.sin(half)/half if abs(half)>1e-8 else 1.-half*half/6.
                distance = speed*(last-first)*sinc
                delta = (2.*sh*(b*cm-p*sm)+distance*(strafe*cm-travel*cp*sm) if axis==0 else
                         2.*sh*(-b*sm-p*cm)+distance*(-strafe*sm-travel*cp*cm))
                proposed = list(eye)
                proposed[axis] += delta
                eye[axis] = bound_camera_eye(proposed)[axis]
        eye[1] = bound_camera_eye((eye[0], eye[1]+speed*duration*travel*sp, eye[2]))[1]
    final_base = baseline(end)
    return tuple((eye[i]-final_base[i])/WORLD_HALF[i] for i in range(3))


def _pitch_limit_time(motion):
    return max(0., ((.5 if motion.tilt_rate>0 else -.5)-motion.tilt)/motion.tilt_rate) if motion.tilt_rate else 0.


def _flight_offset(motion, offset, t):
    from core.settings.extruded_bubble_camera import resolve_camera_position
    return resolve_camera_position(motion.turn + motion.turn_rate*t,
        max(-.5, min(.5, motion.tilt + motion.tilt_rate*t)), motion.scale, motion.pan_x,
        motion.pan_y, motion.fov, offset, motion.surface_bound)[1]


def _changing_pitch_flight(motion, duration):
    from core.constants.extruded_bubble_world import WORLD_HALF
    offset = _flight_offset(motion, motion.offset, 0.)
    magnitude = math.hypot(motion.strafe, motion.travel)
    strafe, travel = motion.strafe / max(1.0, magnitude), motion.travel / max(1.0, magnitude)
    # Production Shift+W/S reaches a pitch limit within 1.5s. The .015rad
    # subdivision is independent of frame rate; 512 bounds synthetic slow rates.
    spans = min(512, max(1, math.ceil(duration*math.pi*(abs(motion.turn_rate)+.5*abs(motion.tilt_rate))/.015)))
    portion = duration / spans
    for i in range(spans):
        t = (i + 0.5) * portion
        yaw = math.pi * (motion.turn + motion.turn_rate * t)
        # EB's canonical tilt is [-0.5, 0.5]; no Qt/config imports on the capture path.
        tilt = max(-0.5, min(0.5, motion.tilt + motion.tilt_rate * t))
        pitch = math.radians(16.0 + 90.0 * tilt)
        sy, cy = math.sin(yaw), math.cos(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        # Same world axes as extruded_bubble_scene.camera: right and -back.
        moved = (strafe * cy - travel * sy * cp, travel * sp, -strafe * sy - travel * cy * cp)
        requested = tuple(offset[j] + portion*moved[j]*FRAMED_CAMERA_TRAVEL_UNITS_PER_SECOND/WORLD_HALF[j]
                          for j in range(3))
        # Discard outward travel at every segment, including the orbit baseline's
        # movement; never accumulate hidden overshoot during a long wall hold.
        offset = _flight_offset(motion, requested, (i+1)*portion)
    return offset


def framed_flight_position(motion: FramedFlightMotion, now: float) -> tuple[float, float, float]:
    """Bounded flight on the existing capture clock, without per-frame state writes."""
    dt = max(0., float(now)-motion.since)
    limit = _pitch_limit_time(motion)
    if not dt:
        return _flight_offset(motion, motion.offset, 0.)
    if dt < limit:
        return _changing_pitch_flight(motion, dt)
    offset = motion.pitch_limit_offset if limit>0. else _flight_offset(motion, motion.offset, 0.)
    assert offset is not None
    magnitude = max(1., math.hypot(motion.strafe, motion.travel))
    return _constant_pitch_flight(motion, offset, limit, dt, motion.strafe/magnitude, motion.travel/magnitude)


def set_framed_flight_rates(host: Any, mode_id: str, yaw: float, pitch: float,
                            strafe: float, travel: float, now: float) -> Dict[str, float]:
    """One GUI-thread publication per key edge; all held motion is capture-clock owned."""
    if mode_id != 'extruded_bubble':
        return {}
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    old = getattr(host, _FLIGHT, None)
    if isinstance(old, FramedFlightMotion) and old.mode_id == mode_id:
        offset = framed_flight_position(old, now)
    else:
        offset = tuple(float(x) for x in getattr(host, '_extruded_bubble_camera_position'))
    # Resolve the old orbit before changing its rate, even if travel and yaw are held together.
    turns = view_orbit_values(host, mode_id, now)
    apply_presentation_vis_mode_kwargs(host, {**turns, 'extruded_bubble_camera_position': list(offset)})
    values = set_view_orbit_rates(host, mode_id, yaw, pitch, now)
    turn_step, tilt_step = get_visualizer_mode_descriptor(mode_id).view_orbit_steps
    setattr(host, _FLIGHT, FramedFlightMotion(
        mode_id, float(now), offset, turns['extruded_bubble_turn'], turns['extruded_bubble_tilt'],
        float(yaw) * turn_step * VIEW_ORBIT_STEPS_PER_SECOND,
        float(pitch) * tilt_step * VIEW_ORBIT_STEPS_PER_SECOND,
        float(strafe), float(travel), *_flight_geometry(host)))
    return values


def settle_framed_flight(host: Any, now: float) -> tuple[float, float, float] | None:
    motion = getattr(host, _FLIGHT, None)
    if not isinstance(motion, FramedFlightMotion):
        return None
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    offset = framed_flight_position(motion, now)
    turns = view_orbit_values(host, motion.mode_id, now)
    # Freeze first so an intervening capture can never see a half-written value.
    setattr(host, _FLIGHT, FramedFlightMotion(motion.mode_id, now, offset,
            turns['extruded_bubble_turn'], turns['extruded_bubble_tilt'], 0., 0., 0., 0.,
            motion.scale, motion.pan_x, motion.pan_y, motion.fov, motion.surface_bound))
    apply_presentation_vis_mode_kwargs(host, {**turns, 'extruded_bubble_camera_position': list(offset)})
    setattr(host, _FLIGHT, None)
    return tuple(host._extruded_bubble_camera_position)


def rebase_framed_flight_on_drag(host: Any, now: float) -> None:
    """Settle/rebase held flight at a GUI gesture edge, including new orbit/pan/dolly."""
    motion = getattr(host, _FLIGHT, None)
    if not isinstance(motion, FramedFlightMotion):
        return
    offset = framed_flight_position(motion, now)
    turns = view_orbit_values(host, motion.mode_id, now)
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    apply_presentation_vis_mode_kwargs(host, {**turns, 'extruded_bubble_camera_position': offset})
    offset = tuple(host._extruded_bubble_camera_position)
    setattr(host, _FLIGHT, FramedFlightMotion(motion.mode_id, now, offset,
            turns['extruded_bubble_turn'], turns['extruded_bubble_tilt'],
            motion.turn_rate, motion.tilt_rate, motion.strafe, motion.travel, *_flight_geometry(host)))


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


def _turn_for_mode(mode_id: str, key: str, value: float) -> float:
    # A mode whose turn does not wrap (a landscape) clamps it to its range.
    return _wrap(value) if get_visualizer_mode_descriptor(mode_id).view_orbit_turn_wraps else _clamped(key, value)


def bounded_scene_pan(envelope: tuple[float, ...], scale: float, pan_x: float, pan_y: float) -> tuple[float, float]:
    """A framed scene's pan kept inside its declared envelope at this zoom.

    The scene is scaled about the interior centre, so pan bounds depend on zoom. Horizontally the anchor stays
    between left and right; vertically the anchor stays above the bottom margin and the upper reference below the
    top one, so looking up may move the anchor below the card while the upper reference stays (Neon Lake: the lake
    and an upper-sky reference; keeping the lake central in both directions prevented framing the Sun). This is
    mode-only presentation admission, not editor/card geometry.
    """
    anchor_x, anchor_y, upper_y, left, right = envelope
    projected_x = 0.5 + (anchor_x - 0.5) * scale
    projected_y = 0.5 + (anchor_y - 0.5) * scale
    projected_upper_y = 0.5 + (upper_y - 0.5) * scale
    return (max(left-projected_x, min(right-projected_x, pan_x)),
            max(left-projected_y, min(right-projected_upper_y, pan_y)))


def orbit_motion_values(motion: ViewOrbitMotion, now: float) -> Dict[str, float]:
    """The view ``motion`` has reached at ``now``."""
    turn_key, tilt_key = view_orbit_settings(motion.mode_id)
    elapsed = max(0.0, float(now) - motion.since)
    return {turn_key: _turn_for_mode(motion.mode_id, turn_key, motion.turn + motion.turn_rate * elapsed),
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
    if isinstance(inertia, OrbitInertia) and now is not None and inertia.mode_id == mode_id:
        return inertia_pose(inertia, now)
    values = {key: float(getattr(host, f"_{key}")) for key in view_orbit_settings(mode_id)}
    auto = getattr(host, _AUTO, None)
    if isinstance(auto, AutoRotate) and now is not None and auto.mode_id == mode_id and values:
        turn_key = view_orbit_settings(mode_id)[0]
        values[turn_key] = auto_rotate_turn(auto, turn_key, now)
    return values


def view_pose_values(host: Any, mode_id: str, now: float | None = None) -> Dict[str, float]:
    """The complete persistent view, including optional framed scene transform."""
    descriptor = get_visualizer_mode_descriptor(mode_id)
    return {**view_orbit_values(host, mode_id, now),
            **{key: float(getattr(host, f"_{key}")) for key in descriptor.scene_transform_settings}}


def transform_visualizer_scene(host: Any, mode_id: str, values: Mapping[str, float]) -> Dict[str, float]:
    """Apply an admitted internal pose through the canonical presentation spec."""
    descriptor = get_visualizer_mode_descriptor(mode_id)
    keys = frozenset(descriptor.scene_transform_settings)
    if not keys or not set(values) <= keys:
        return {}
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    import time as _time
    now = _time.time()
    if mode_id == 'extruded_bubble':
        rebase_framed_flight_on_drag(host, now)
    _take_auto_rotation(host, mode_id, now)
    apply_presentation_vis_mode_kwargs(host, {key: _clamped(key, float(value)) for key, value in values.items()})
    if mode_id == 'extruded_bubble':
        rebase_framed_flight_on_drag(host, now)
    return view_pose_values(host, mode_id)


def apply_view_orbit_motion(host: Any, mode_id: str, values: Mapping[str, object], now: float) -> Dict[str, object]:
    """A capture's ``values`` with the held-key or auto-rotating view at ``now`` (logical thread; read only)."""
    motion = _motion(host, mode_id)
    flight = getattr(host, _FLIGHT, None)
    if isinstance(flight, FramedFlightMotion) and flight.mode_id == mode_id:
        values = {**values, 'extruded_bubble_camera_position': framed_flight_position(flight, now)}
    if motion is not None:
        values = {**values, **orbit_motion_values(motion, now)}
    auto = getattr(host, _AUTO, None)
    if motion is None and isinstance(auto, AutoRotate) and auto.mode_id == mode_id:
        turn_key = view_orbit_settings(mode_id)[0]
        values = {**values, turn_key: auto_rotate_turn(auto, turn_key, now)}
    return _bounded_eb_values(host, values) if mode_id == 'extruded_bubble' else dict(values)


def _take_auto_rotation(host: Any, mode_id: str, now: float | None) -> None:
    """Camera input arrived (GUI thread): the swivelled view becomes the settled view and the swivel stops."""
    auto = getattr(host, _AUTO, None)
    if not isinstance(auto, AutoRotate):
        return
    setattr(host, _AUTO, None)
    if auto.mode_id != mode_id or now is None or float(now) <= auto.start:
        return
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    turn_key = view_orbit_settings(mode_id)[0]
    apply_presentation_vis_mode_kwargs(host, {turn_key: auto_rotate_turn(auto, turn_key, now)})


def arm_view_auto_rotate(host: Any, mode_id: str, now: float, *, immediate: bool) -> AutoRotate | None:
    """Publish (GUI thread) the swivel ``mode_id`` starts when its Auto Rotate is on: at once for a completed
    startup or mode/preset swap (``immediate``), else after its Auto Rotate After seconds without camera input.
    Off, or a mode without Auto Rotate or whose turn does not wrap: the record is dropped."""
    try:
        descriptor = get_visualizer_mode_descriptor(mode_id)
    except (KeyError, ValueError):
        setattr(host, _AUTO, None)
        return None
    keys = descriptor.view_auto_rotate_settings
    if not keys or not descriptor.view_orbit_turn_wraps or not descriptor.view_orbit_settings:
        setattr(host, _AUTO, None)
        return None
    if len(keys) == 3:
        if not bool(getattr(host, f"_{keys[0]}", False)):
            setattr(host, _AUTO, None)
            return None
        keys = keys[1:]
    after_key, speed_key = keys
    after = float(getattr(host, f"_{after_key}", 0.0) or 0.0)
    speed = float(getattr(host, f"_{speed_key}", 0.0) or 0.0)
    if after <= 0.0 or speed == 0.0:
        setattr(host, _AUTO, None)
        return None
    turn_key = descriptor.view_orbit_settings[0]
    record = AutoRotate(mode_id, float(getattr(host, f"_{turn_key}")), speed / 180.0,
                        float(now) if immediate else float(now) + after)
    setattr(host, _AUTO, record)
    return record


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
    _take_auto_rotation(host, mode_id, now)
    values = view_orbit_values(host, mode_id, now)
    setattr(host, _INERTIA, None)  # held keys take over from the exact live view
    setattr(host, _DRAG, None)  # a later key release is not a mouse flick
    if get_visualizer_mode_descriptor(mode_id).view_orbit_inertia:
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
    flight = getattr(host, _FLIGHT, None)
    if isinstance(flight, FramedFlightMotion):
        turn_key, tilt_key = view_orbit_settings(flight.mode_id)
        setattr(host, _FLIGHT, FramedFlightMotion(flight.mode_id, now,
                tuple(float(x) for x in getattr(host, '_extruded_bubble_camera_position')),
                float(getattr(host, f'_{turn_key}')), float(getattr(host, f'_{tilt_key}')),
                flight.turn_rate, flight.tilt_rate, flight.strafe, flight.travel, *_flight_geometry(host)))
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
    if mode_id == 'extruded_bubble' and now is not None:
        rebase_framed_flight_on_drag(host, now)
    motion = _motion(host, mode_id)
    if motion is not None and now is not None:
        values = orbit_motion_values(motion, now)
        setattr(host, _MOTION, ViewOrbitMotion(
            mode_id, _turn_for_mode(mode_id, turn_key, values[turn_key] + turn_step * float(turn_steps)),
            _clamped(tilt_key, values[tilt_key] + tilt_step * float(tilt_steps)),
            motion.turn_rate, motion.tilt_rate, float(now)))
        if mode_id == 'extruded_bubble':
            rebase_framed_flight_on_drag(host, now)
        return view_orbit_values(host, mode_id, now)
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs

    _take_auto_rotation(host, mode_id, now)
    values = view_orbit_values(host, mode_id, now)
    setattr(host, _INERTIA, None)
    turn_delta = turn_step * float(turn_steps)
    tilt_delta = tilt_step * float(tilt_steps)
    if get_visualizer_mode_descriptor(mode_id).view_orbit_inertia and now is not None and (turn_delta or tilt_delta):
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
        turn_key: _turn_for_mode(mode_id, turn_key, values[turn_key] + turn_delta),
        tilt_key: values[tilt_key] + tilt_delta,
    })
    if mode_id == 'extruded_bubble' and now is not None:
        rebase_framed_flight_on_drag(host, now)
    return view_orbit_values(host, mode_id, now)


def release_view_orbit_inertia(host: Any, mode_id: str, now: float) -> Dict[str, float] | None:
    """Settle a drag of a mode with ``view_orbit_inertia`` onto the existing presentation clock, no timer.

    Persist the analytic endpoint once at release. Until the tail finishes, captures
    read its intermediate view, then naturally read the identical saved endpoint.
    """
    sample = getattr(host, _DRAG, None)
    setattr(host, _DRAG, None)
    if (not isinstance(sample, OrbitDragVelocity) or sample.mode_id != mode_id
            or not get_visualizer_mode_descriptor(mode_id).view_orbit_inertia
            or not 0 <= float(now) - sample.time <= VIEW_ORBIT_INERTIA_MAX_AGE):
        return None
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    turn_key, tilt_key = view_orbit_settings(mode_id)
    start = view_orbit_values(host, mode_id, now)
    turn_delta = max(-0.16, min(0.16, sample.turn_rate * VIEW_ORBIT_INERTIA_SECONDS / 3))
    tilt_delta = max(-0.12, min(0.12, sample.tilt_rate * VIEW_ORBIT_INERTIA_SECONDS / 3))
    if abs(turn_delta) + abs(tilt_delta) < 0.0005:
        return None
    inertia = OrbitInertia(mode_id, float(now), VIEW_ORBIT_INERTIA_SECONDS,
                           start[turn_key], start[tilt_key], turn_delta, tilt_delta)
    final = inertia_pose(inertia, float(now) + VIEW_ORBIT_INERTIA_SECONDS)
    apply_presentation_vis_mode_kwargs(host, final)
    setattr(host, _INERTIA, inertia)
    return final
