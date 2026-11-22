"""Save a camera into a preset, Reset Camera, get that camera back: every orbiting mode (operator, 22 Nov).

Preset 9's Reset Camera came back somewhere other than where the Studio saved it: the save wrote the pose
(``starting_view``) AND the lens and eye offset (``camera_fov``, ``camera_position``) into the preset, while Reset took
the pose from the preset and the lens from the canonical defaults. One owner now holds the home
(``core.settings.framed_camera.home_view``); Reset, preset selection and the in-saver live save all read or write
that one record. The saved camera is derived from each mode's own control ranges and its current home, never a
preset value; writes go to a tmp copy of the curated tree, so no authored file is touched. Nothing is shown.
"""
from __future__ import annotations

import shutil
import uuid

import pytest

from core.settings import visualizer_presets as vp
from core.settings import visualizer_preset_file as preset_file
from core.settings.framed_camera import spec_for_mode
from core.settings.visualizer_mode_registry import (
    get_visualizer_view_pose_keys, iter_visualizer_mode_descriptors,
)

ORBITING = tuple(d.mode_id for d in iter_visualizer_mode_descriptors() if d.view_orbit_settings)


@pytest.fixture
def preset_root(tmp_path, monkeypatch):
    root = tmp_path / "presets"
    shutil.copytree(vp.get_visualizer_presets_dir(), root)
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    vp.reload_presets()
    yield root
    monkeypatch.undo()
    vp.reload_presets()


@pytest.fixture
def manager(qt_app, tmp_path, preset_root):
    from core.settings import SettingsManager
    from tests._display_manager_doubles import bare_display_manager, visualizer_owner_double
    settings = SettingsManager(application=f"CameraHome_{uuid.uuid4().hex}", storage_base_dir=tmp_path / "profile")
    manager = bare_display_manager(settings_manager=settings, _widgets_config_snapshot={})
    manager._refresh_quick_visualizer_edit_content_envelope = lambda *a: None
    manager._refresh_all_quick_context_menus = lambda: None
    manager._quick_view_orbit_admitted = lambda: True

    def own(mode_id, preset_index):
        from widgets.spotify_visualizer.presentation_state import install_default_presentation_state
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
        widgets = settings.get_widgets_map()
        widgets["spotify_visualizer"].update({"enabled": True, "mode": mode_id, f"preset_{mode_id}": preset_index})
        settings.set_widgets_map(widgets)
        controller = VisualizerRuntimeController(runtime_generation=0, initial_mode=mode_id,
                                                 engine_factory=lambda _n: None)
        install_default_presentation_state(controller.presentation_state)
        manager._quick_visualizer_owner = visualizer_owner_double(controller)
        return controller
    manager.own = own
    return manager


def _flat(camera: dict) -> dict:
    """pytest.approx compares flat mappings only: the eye offset's axes become their own entries."""
    out = {}
    for key, value in camera.items():
        if isinstance(value, (list, tuple)):
            out.update({f"{key}[{i}]": float(v) for i, v in enumerate(value)})
        else:
            out[key] = float(value)
    return out


def _close(camera: dict):
    """Saved settings keep six decimals and the eye is re-admitted on apply: equal to well under any visible step."""
    return pytest.approx(_flat(camera), abs=1e-5)


def _curated_slot(mode: str) -> int:
    custom = vp.get_custom_preset_index(mode)
    for index in range(vp.get_preset_count(mode)):
        if index != custom and vp.get_preset_file_path(mode, index) is not None:
            return index
    pytest.skip(f"{mode} has no curated preset file")


def _between(low: float, high: float, current: float) -> float:
    """A value inside [low, high] well away from ``current``."""
    a, b = low + 0.3 * (high - low), low + 0.7 * (high - low)
    return a if abs(a - current) > abs(b - current) else b


def _moved_camera(mode: str, home: dict) -> dict:
    """A different, admitted camera: every pose leaf and, for a framed camera, the lens and the eye offset."""
    from core.settings.framed_camera import admit_camera_parameters, spec_for_mode
    from core.settings.visualizer_mode_settings import require_mode_settings
    settings = require_mode_settings(mode)
    pose_keys = set(get_visualizer_view_pose_keys(mode))
    moved = {}
    for key in pose_keys:
        control = settings.control(key)
        moved[key] = float(control.admit(_between(control.low, control.high, float(home[key])), home[key]))
    spec = spec_for_mode(mode)
    if spec is not None:
        fov = spec.key("camera_fov")
        # Lens values pass the mode's own controls, as every Settings/Studio save does.
        moved[fov] = float(settings.control(fov).admit(_between(*spec.fov_range, float(home[fov])), home[fov]))
        position = spec.key("camera_position")
        requested = [float(v) + d for v, d in zip(home[position], (0.11, -0.07, 0.05))]
        context = {spec.key(s): moved.get(spec.key(s), home.get(spec.key(s))) for s in ("turn", "tilt")}
        from core.settings.default_contract import require_canonical_default
        values = {key: require_canonical_default("widgets.spotify_visualizer." + key) for key in spec.input_keys}
        values.update(home)
        values.update(moved)
        values.update(context)
        values[position] = requested
        admitted = settings.control(position).admit(list(admit_camera_parameters(spec, values)), home[position])
        moved[position] = [float(v) for v in admitted]
    assert all(moved[key] != home[key] for key in moved), f"{mode}: the saved camera must differ from the home"
    return moved


def _save_into_preset(mode: str, index: int, camera: dict) -> None:
    """The Studio's Save To Preset write (``SettingsLink._write_preset``): lens as settings, pose as starting_view."""
    pose_keys = set(get_visualizer_view_pose_keys(mode))
    changes = {key: value for key, value in camera.items() if key not in pose_keys}
    preset_file.save_changes_to_preset(mode, index, changes,
                                       starting_view={key: camera[key] for key in pose_keys})


def _live_camera(controller, mode: str, keys) -> dict:
    from widgets.spotify_visualizer.view_orbit import view_pose_values
    state = controller.presentation_state
    pose = view_pose_values(state, mode)
    pose_keys = set(get_visualizer_view_pose_keys(mode))
    out = {}
    for key in keys:
        value = pose[key] if key in pose_keys else getattr(state, "_" + key)
        out[key] = float(value) if isinstance(value, (int, float)) else [float(v) for v in value]
    return out


@pytest.mark.parametrize("mode", ORBITING)
def test_reset_camera_returns_to_the_camera_saved_into_the_preset(manager, mode):
    from core.settings.framed_camera import home_view
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    index = _curated_slot(mode)
    saved = _moved_camera(mode, home_view(mode, index))
    _save_into_preset(mode, index, saved)
    assert _flat(home_view(mode, index)) == _close((saved)), f"{mode}: the home is not the record the save wrote"

    controller = manager.own(mode, index)
    elsewhere = _moved_camera(mode, saved)              # the viewer flies away from the saved camera
    apply_presentation_vis_mode_kwargs(controller.presentation_state, elsewhere)
    assert _flat(_live_camera(controller, mode, saved)) != _close((saved))
    manager._reset_quick_visualizer_camera()
    assert _flat(_live_camera(controller, mode, saved)) == _close((saved)), \
        f"{mode}: Reset Camera did not return to the camera saved into the preset"
    persisted = manager.settings_manager.get("widgets.spotify_visualizer")
    assert _flat({key: persisted[key] for key in saved}) == _close((saved)), f"{mode}: reset persisted another camera"


@pytest.mark.parametrize("mode", ORBITING)
def test_selecting_the_preset_seeds_the_same_home_as_reset(preset_root, mode):
    from core.settings.framed_camera import home_view
    index = _curated_slot(mode)
    saved = _moved_camera(mode, home_view(mode, index))
    _save_into_preset(mode, index, saved)
    seeded = vp.apply_preset_starting_view(mode, index, {})
    assert _flat({key: seeded[key] for key in saved}) == _close((saved)), \
        f"{mode}: preset selection seeds another camera than its home"


@pytest.mark.parametrize("mode", ORBITING)
def test_custom_home_is_the_canonical_camera(preset_root, mode):
    from core.settings.default_contract import require_canonical_default
    from core.settings.framed_camera import home_view
    home = home_view(mode, vp.get_custom_preset_index(mode))
    canonical = {key: require_canonical_default("widgets.spotify_visualizer." + key) for key in home}
    assert _flat(home) == _close((canonical))


@pytest.mark.parametrize("mode", ORBITING)
def test_the_in_saver_save_writes_the_flown_camera_and_leaves_the_home(manager, mode):
    """A finished gesture saves what it moves (pose and eye offset; the lens is never a gesture's) into the live view,
    never into the curated preset, and Reset still returns to the preset's home."""
    from core.settings.framed_camera import home_view
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
    index = _curated_slot(mode)
    home = home_view(mode, index)
    controller = manager.own(mode, index)
    pose_keys = set(get_visualizer_view_pose_keys(mode))
    spec = spec_for_mode(mode)
    flown = {key: value for key, value in _moved_camera(mode, home).items()
             if key in pose_keys or spec is not None and key == spec.key("camera_position")}
    apply_presentation_vis_mode_kwargs(controller.presentation_state, flown)
    manager._quick_view_orbit_pending = (mode, {key: flown[key] for key in pose_keys})
    manager._persist_quick_visualizer_view(settle_motion=False)
    persisted = manager.settings_manager.get("widgets.spotify_visualizer")
    assert _flat({key: persisted[key] for key in flown}) == _close((_live_camera(controller, mode, flown))), \
        f"{mode}: the in-saver save left part of the flown camera unsaved"
    assert _flat(home_view(mode, index)) == _close((home)), f"{mode}: a gesture moved the preset's home"
    manager._reset_quick_visualizer_camera()
    assert _flat(_live_camera(controller, mode, home)) == _close((home))


FRAMED = tuple(mode for mode in ORBITING if spec_for_mode(mode) is not None)


@pytest.mark.parametrize("mode", FRAMED)
def test_a_preset_saved_without_its_view_keeps_its_lens_but_no_eye_offset(preset_root, mode):
    """Save Preset As with "Include current camera view" off drops the starting view; the eye offset is relative to
    that view, so the home is the canonical pose and offset, and only the lens comes from the preset."""
    import json
    from core.settings.default_contract import require_canonical_default
    from core.settings.framed_camera import home_view
    spec = spec_for_mode(mode)
    index = _curated_slot(mode)
    saved = _moved_camera(mode, home_view(mode, index))
    _save_into_preset(mode, index, saved)
    path = vp.get_preset_file_path(mode, index)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("starting_view")
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    vp.reload_presets(mode)
    home = home_view(mode, index)
    canonical = {key: require_canonical_default("widgets.spotify_visualizer." + key) for key in home}
    fov = spec.key("camera_fov")
    assert home[fov] == pytest.approx(saved[fov]), f"{mode}: the preset's lens was dropped"
    canonical[fov] = saved[fov]
    assert _flat(home) == _close(canonical), f"{mode}: a view-less preset kept an eye offset from another view"
