"""Settings side of the shared framed physical camera (``core.settings.framed_camera``).

Every framed 3D mode is edited in its Studio, which flies the camera through the shared framed camera; Settings keeps
only the camera's persistence: the live pose the body was hydrated with (orbit and pan are not body controls), the
Studio's aimed turn/tilt (``aim_dirty``), and the Camera Position offset admitted with the mode's own bounds before it
is saved. Nothing here branches on a mode id; the spec and the mode's settings carry everything. Values come from the
mode body's section-lazy cache, else the saved settings.
"""
from __future__ import annotations

from core.settings.framed_camera import FramedCameraSpec, admit_camera_parameters, spec_for_mode
from core.settings.visualizer_mode_settings import require_mode_settings

POSE_SUFFIXES = ('turn', 'tilt', 'scene_scale', 'scene_pan_x', 'scene_pan_y', 'camera_fov')


def _settings_prefix(mode_id: str) -> str:
    return require_mode_settings(mode_id).prefix


def pose_attr(mode_id: str) -> str:
    return f'_{_settings_prefix(mode_id)}_loaded_camera_pose'


def aim_dirty_attr(mode_id: str) -> str:
    return f'_{_settings_prefix(mode_id)}_aim_dirty'


def _saved(tab, key):
    return tab._settings.get('widgets.spotify_visualizer.' + key, tab._widget_default('spotify_visualizer', key))


def live_value(tab, mode_id: str, key: str):
    """The body's current value of ``key``: the section-lazy cache, else the saved setting."""
    cache = getattr(tab, f'_{_settings_prefix(mode_id)}_lazy_values', None)
    if cache is not None and key in cache:
        return cache[key]
    return _saved(tab, key)


def hydrate_pose(tab, mode_id: str, config) -> None:
    """Remember the live pose the body was loaded with (orbit keys are not body controls)."""
    spec = spec_for_mode(mode_id)
    setattr(tab, aim_dirty_attr(mode_id), False)
    setattr(tab, pose_attr(mode_id), {spec.key(s): config.get(spec.key(s), _saved(tab, spec.key(s)))
                                      for s in POSE_SUFFIXES})


def _pose(tab, mode_id: str) -> dict:
    return getattr(tab, pose_attr(mode_id), {})


def _values(tab, mode_id: str, spec: FramedCameraSpec, **overrides) -> dict:
    pose = _pose(tab, mode_id)
    values = {key: pose[key] if key in pose else live_value(tab, mode_id, key) for key in spec.input_keys}
    fov = spec.key('camera_fov')
    values[fov] = float(live_value(tab, mode_id, fov))          # the body's lens (pan's world width follows it)
    values.update(overrides)
    return values


def admit_offset(tab, mode_id: str, offset) -> tuple[float, float, float]:
    spec = spec_for_mode(mode_id)
    return admit_camera_parameters(spec, _values(tab, mode_id, spec, **{spec.key('camera_position'): offset}))


def refresh_editors(tab, mode_id: str) -> tuple[float, float, float] | None:
    """Admit the held Camera Position for the current pose and lens, and hold the admitted offset."""
    spec = spec_for_mode(mode_id)
    if spec is None:
        return None
    key = spec.key('camera_position')
    camera = admit_offset(tab, mode_id, live_value(tab, mode_id, key))
    cache = getattr(tab, f'_{_settings_prefix(mode_id)}_lazy_values', None)
    if cache is not None:
        cache[key] = list(camera)
    return camera


def collected(tab, mode_id: str, values: dict) -> dict:
    """Persisted values with the aimed turn/tilt and an admitted Camera Position."""
    spec = spec_for_mode(mode_id)
    if getattr(tab, aim_dirty_attr(mode_id), False):
        pose = _pose(tab, mode_id)
        for suffix in ('turn', 'tilt'):
            values[spec.key(suffix)] = pose[spec.key(suffix)]
    key = spec.key('camera_position')
    if key in values:
        values[key] = list(admit_offset(tab, mode_id, values[key]))
    return values
