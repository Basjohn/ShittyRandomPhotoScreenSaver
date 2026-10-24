"""Settings side of the shared framed physical camera (``core.settings.framed_camera``).

One Camera Position editor for every framed 3D mode: it reads the live pose the body was hydrated with, composes the
orbit/pan baseline through the mode's ``FramedCameraSpec``, admits the eye offset with the mode's own bounds, and
aims by rotating the camera in place. Nothing here branches on a mode id; the spec and the mode's settings carry
everything. Values come from a section-lazy cache when the mode keeps one (EB), else from the live widget or the
saved settings.
"""
from __future__ import annotations

from core.settings.framed_camera import (
    FramedCameraSpec, admit_camera_parameters, camera_baseline, ceiling_for, spec_for_mode,
)
from core.settings.visualizer_mode_settings import require_mode_settings
from ui.widgets.edit_history import EditHistory
from ui.widgets.visual_controls import SceneVolumeMapper

POSE_SUFFIXES = ('turn', 'tilt', 'scene_scale', 'scene_pan_x', 'scene_pan_y', 'camera_fov')


def _settings_prefix(mode_id: str) -> str:
    return require_mode_settings(mode_id).prefix


def pose_attr(mode_id: str) -> str:
    return f'_{_settings_prefix(mode_id)}_loaded_camera_pose'


def aim_dirty_attr(mode_id: str) -> str:
    return f'_{_settings_prefix(mode_id)}_aim_dirty'


def _history_attr(mode_id: str) -> str:
    return f'_{_settings_prefix(mode_id)}_camera_history'


def _saved(tab, key):
    return tab._settings.get('widgets.spotify_visualizer.' + key, tab._widget_default('spotify_visualizer', key))


def live_value(tab, mode_id: str, key: str):
    """The body's current value of ``key``: its editor, the section-lazy cache, else the saved setting."""
    widget = getattr(tab, key, None)
    if isinstance(widget, SceneVolumeMapper):
        return tuple(widget.value())
    if widget is not None and hasattr(widget, 'currentText'):
        # A plain string Choice persists its text (labelled or indexed choices persist data/index).
        try:
            control = require_mode_settings(mode_id).control(key)
        except KeyError:
            control = None
        if control is not None and not getattr(control, 'labels', ()) and not getattr(control, 'indexed', False):
            return widget.currentText()
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
    setattr(tab, _history_attr(mode_id), EditHistory(camera_state(tab, mode_id)))


def camera_state(tab, mode_id: str) -> tuple:
    """What one camera action changes: the Camera Position offset and the aimed turn/tilt."""
    spec = spec_for_mode(mode_id)
    offset = tuple(float(v) for v in live_value(tab, mode_id, spec.key('camera_position')))
    return (offset, *camera_angles(tab, mode_id))


def note_committed(tab, mode_id: str) -> None:
    """A camera gesture ended: remember its result for Ctrl+Z."""
    history = getattr(tab, _history_attr(mode_id), None)
    if history is not None:
        history.record(camera_state(tab, mode_id))


def undo(tab, mode_id: str) -> bool:
    history = getattr(tab, _history_attr(mode_id), None)
    return _restore(tab, mode_id, history.undo() if history is not None else None)


def redo(tab, mode_id: str) -> bool:
    history = getattr(tab, _history_attr(mode_id), None)
    return _restore(tab, mode_id, history.redo() if history is not None else None)


def _restore(tab, mode_id: str, state) -> bool:
    pose = getattr(tab, pose_attr(mode_id), None)
    if state is None or pose is None:
        return False
    spec = spec_for_mode(mode_id)
    offset, turn, tilt = state
    pose[spec.key('turn')], pose[spec.key('tilt')] = turn, tilt
    setattr(tab, aim_dirty_attr(mode_id), True)
    _store_offset(tab, mode_id, list(admit_offset(tab, mode_id, offset)))
    refresh_editors(tab, mode_id)
    tab._save_settings()
    return True


def _pose(tab, mode_id: str) -> dict:
    return getattr(tab, pose_attr(mode_id), {})


def _fov(tab, spec: FramedCameraSpec, pose) -> float:
    widget = getattr(tab, spec.key('camera_fov'), None)
    if widget is not None and hasattr(widget, 'value'):
        return float(widget.value())   # FOV edits also change the world width of pan
    return float(pose.get(spec.key('camera_fov'), _saved(tab, spec.key('camera_fov'))))


def _values(tab, mode_id: str, spec: FramedCameraSpec, **overrides) -> dict:
    pose = _pose(tab, mode_id)
    values = {key: pose[key] if key in pose else live_value(tab, mode_id, key) for key in spec.input_keys}
    values[spec.key('camera_fov')] = _fov(tab, spec, pose)
    values.update(overrides)
    return values


def base_eye(tab, mode_id: str) -> tuple[float, float, float]:
    """The orbit/pan baseline, before the Camera Position offset the editor authors."""
    spec = spec_for_mode(mode_id)
    values = _values(tab, mode_id, spec)

    def get(suffix):
        return float(values[spec.key(suffix)])
    return camera_baseline(spec, get('turn'), get('tilt'), get('scene_scale'), get('scene_pan_x'),
                           get('scene_pan_y'), get('camera_fov'), ceiling_for(spec, values))


def admit_offset(tab, mode_id: str, offset) -> tuple[float, float, float]:
    spec = spec_for_mode(mode_id)
    return admit_camera_parameters(spec, _values(tab, mode_id, spec, **{spec.key('camera_position'): offset}))


def _store_offset(tab, mode_id: str, value) -> None:
    spec = spec_for_mode(mode_id)
    cache = getattr(tab, f'_{_settings_prefix(mode_id)}_lazy_values', None)
    if cache is not None:
        cache[spec.key('camera_position')] = list(value)
    widget = getattr(tab, spec.key('camera_position'), None)
    if isinstance(widget, SceneVolumeMapper) and tuple(widget.value()) != tuple(value):
        blocked = widget.blockSignals(True)
        try:
            widget.setValue(value)
        finally:
            widget.blockSignals(blocked)
        label = getattr(tab, spec.key('camera_position') + '_label', None)
        if label is not None:
            label.setText(require_mode_settings(mode_id).control(spec.key('camera_position')).text(value))


def set_offset(tab, mode_id: str, offset, *, commit: bool) -> None:
    """Camera diamond gestures use the existing Settings persistence owner."""
    spec = spec_for_mode(mode_id)
    control = require_mode_settings(mode_id).control(spec.key('camera_position'))
    value = list(admit_offset(tab, mode_id, control.admit(offset, (0., 0., 0.))))
    _store_offset(tab, mode_id, value)
    refresh_editors(tab, mode_id)
    if commit:
        # Camera movement is a live pose adjustment, not curated preset artwork.
        tab._save_settings()
        note_committed(tab, mode_id)


def set_aim(tab, mode_id: str, angles, *, commit: bool) -> None:
    """Aiming edits the live turn/tilt by rotating the camera in place (the eye does not move)."""
    pose = getattr(tab, pose_attr(mode_id), None)
    if pose is None:
        return
    spec = spec_for_mode(mode_id)
    half = spec.offset_scale
    offset_before = tuple(float(v) for v in live_value(tab, mode_id, spec.key('camera_position')))
    base_before = base_eye(tab, mode_id)
    physical_eye = tuple(base_before[i] + offset_before[i] * half[i] for i in range(3))
    settings = require_mode_settings(mode_id)
    for suffix, angle in zip(('turn', 'tilt'), angles):
        key = spec.key(suffix)
        pose[key] = settings.control(key).admit(angle, tab._widget_default('spotify_visualizer', key))
    base_after = base_eye(tab, mode_id)
    set_offset(tab, mode_id, tuple((physical_eye[i] - base_after[i]) / half[i] for i in range(3)), commit=False)
    if commit:
        setattr(tab, aim_dirty_attr(mode_id), True)
    refresh_editors(tab, mode_id)
    if commit:
        tab._save_settings()
        note_committed(tab, mode_id)


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


def normalized_base(tab, mode_id: str) -> tuple[float, float, float]:
    spec = spec_for_mode(mode_id)
    return tuple((p - c) / h for p, c, h in zip(base_eye(tab, mode_id), spec.eye_center, spec.eye_half))


def camera_angles(tab, mode_id: str) -> tuple[float, float]:
    spec = spec_for_mode(mode_id)
    pose = _pose(tab, mode_id)
    return float(pose.get(spec.key('turn'), 0.0)), float(pose.get(spec.key('tilt'), 0.0))


def refresh_editors(tab, mode_id: str) -> None:
    """Repaint every editor showing this camera: the mode's own refresher when it registered one
    (EB also repaints its stream/light/ray volume editors), else the Camera Position editor."""
    own = getattr(tab, f'_{_settings_prefix(mode_id)}_camera_refresh', None)
    if own is not None:
        own(tab)
    else:
        refresh(tab, mode_id)


def refresh(tab, mode_id: str, *, references=None) -> tuple[float, float, float] | None:
    """Repaint the Camera Position editor (when built); return the admitted offset."""
    spec = spec_for_mode(mode_id)
    if spec is None:
        return None
    camera = admit_offset(tab, mode_id, live_value(tab, mode_id, spec.key('camera_position')))
    _store_offset(tab, mode_id, camera)
    widget = getattr(tab, spec.key('camera_position'), None)
    if isinstance(widget, SceneVolumeMapper):
        from PySide6.QtGui import QColor
        # The mode's own scene guides (e.g. Neon Lake's basin outline) read clearly over the eye box.
        widget.setCameraModel(spec, reference_colour=QColor(94, 196, 236, 170))
        widget.setSceneReferences(paths=references if references is not None else _scene_references(tab, mode_id),
                                  base_eye=normalized_base(tab, mode_id), camera_offset=camera,
                                  camera_angles=camera_angles(tab, mode_id))
    return camera


def _scene_references(tab, mode_id: str) -> dict:
    """Faint guides of the mode's scene inside the eye box, from its own optional hook."""
    hook = getattr(spec_for_mode(mode_id), 'editor_references_hook', '')
    if not hook:
        return {}
    module, _, name = hook.partition(':')
    import importlib
    return getattr(importlib.import_module(module), name)(lambda key: live_value(tab, mode_id, key))


def framed_mode_of(key: str) -> str | None:
    """The framed-camera mode whose settings own ``key``."""
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    for descriptor in iter_all_visualizer_mode_descriptors():
        if descriptor.framed_camera and key.startswith(spec_for_mode(descriptor.mode_id).prefix):
            return descriptor.mode_id
    return None
