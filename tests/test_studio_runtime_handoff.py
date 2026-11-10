"""Studio launch targets are camera-only, transient and never select another mode.

These are pure Settings-target and production-flight contracts. Native QQuickWindow
and installed taskbar icon acceptance remain operator-visible Windows checks.
"""
from __future__ import annotations

import pytest

from core.settings.defaults import get_default_settings
from core.settings.framed_camera import spec_for_mode
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from ui.settings_launch_targets import make_studio_launch_target, resolve_settings_launch_target
from ui.studio.camera_keyboard import make_flight, flight_pose


@pytest.mark.parametrize("mode", ["extruded_bubble", "waveform_ribbon", "shockwave_grid"])
def test_studio_launch_preserves_active_pose_in_a_transient_mode_target(mode):
    descriptor = get_visualizer_mode_descriptor(mode)
    spec = spec_for_mode(mode)
    defaults = get_default_settings()["widgets"]["spotify_visualizer"]
    camera = {key: defaults[key] for key in (*descriptor.view_orbit_settings,
                                            *descriptor.scene_transform_settings)}
    camera[spec.key("camera_position")] = (0.5, -0.25, 0.75)
    camera[spec.key("camera_fov")] = 68.25

    target = make_studio_launch_target(mode, camera)
    selection = resolve_settings_launch_target(target)
    assert selection is not None
    assert selection.tab_key == "visualizers"
    assert selection.view_state["mode_id"] == selection.studio_mode == mode
    assert tuple(selection.studio_pose[spec.key("camera_position")]) == (0.5, -0.25, 0.75)
    assert selection.studio_pose[spec.key("camera_fov")] == 68.25
    assert "preset_index" not in selection.studio_pose
    with pytest.raises(TypeError):
        selection.studio_pose[spec.key("camera_fov")] = 1.0


def test_studio_launch_rejects_garbage_and_existing_settings_targets_still_work():
    assert resolve_settings_launch_target("studio:unregistered:eyJ4IjoxfQ") is None
    assert resolve_settings_launch_target("studio:extruded_bubble:ZmFrZQ") is None
    assert resolve_settings_launch_target("weather_location").tab_key == "widgets"
    assert resolve_settings_launch_target("gmail_authorization").tab_key == "widgets"


@pytest.mark.parametrize("mode", ["extruded_bubble", "waveform_ribbon", "shockwave_grid"])
def test_studio_keyboard_uses_production_framed_flight_geometry(mode):
    values = dict(get_default_settings()["widgets"]["spotify_visualizer"])
    spec = spec_for_mode(mode)
    pose = make_flight(mode, values, frozenset({"w"}), False, 1000.0)
    assert pose is not None
    first = flight_pose(pose, 1000.0)
    second = flight_pose(pose, 1000.4)
    assert spec.key("camera_position") in first
    assert len(second[spec.key("camera_position")]) == 3
    assert second[spec.key("camera_position")] != first[spec.key("camera_position")]
    assert spec.key("camera_fov") not in second  # flight never edits lens/FOV


def test_no_studio_navigation_clocks_or_widgets_in_runtime_target_module():
    import inspect
    import ui.settings_launch_targets as targets
    source = inspect.getsource(targets)
    assert "PySide6" not in source and "QtWidgets" not in source
    assert "QTimer" not in source

@pytest.mark.qt
def test_runtime_studio_launch_builds_the_lazy_mode_body_before_save_camera(qt_app, tmp_path, monkeypatch):
    """The live S route restores a mode id but not its Settings body; Save Camera must still work.

    The real Settings dialog, VisualizersTab, Studio entry and Store are exercised. Only the actual Studio
    QQuickWindow is replaced by a non-rendering controller, so no GL context or authored preset file is touched.
    """
    from copy import deepcopy
    from PySide6.QtCore import QObject, Signal
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.settings_dialog import SettingsDialog
    from ui.studio import controller as studio_controller
    from ui.studio import theme as studio_theme_module

    mode = "shockwave_grid"
    spec = spec_for_mode(mode)
    manager = SettingsManager(organization="SRPSSFocusedTests", application="RuntimeStudioLazyCamera",
                              storage_base_dir=tmp_path / "profile")
    widgets = deepcopy(manager.get("widgets", {}))
    visual = dict(widgets.get("spotify_visualizer", {}))
    visual.update({"enabled": True, "visualizers_enabled": True, "mode": mode,
                   "mode_activation": build_visualizer_mode_activation([mode]),
                   f"preset_{mode}": get_custom_preset_index(mode)})
    widgets["spotify_visualizer"] = visual
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    launch_pose = {spec.key("camera_position"): [0.3, -0.2, 0.4], spec.key("camera_fov"): 63.0}
    target = make_studio_launch_target(mode, launch_pose)

    opened = []

    class QuietStudio(QObject):
        closed = Signal()
        failed = Signal(str)

        @staticmethod
        def active():
            return None

        def __init__(self, _adapter, store, _presence, _surface_factory, **kwargs):
            super().__init__()
            self.store = store
            self.initial_pose = kwargs.get("initial_pose")
            opened.append(self)

        def open(self):
            pass

        def close_for_settings_gone(self, *_args):
            pass

        def close_for_quit(self, *_args):
            pass

    monkeypatch.setattr(studio_controller, "StudioController", QuietStudio)
    monkeypatch.setattr(studio_theme_module, "subscribe_studio_theme", lambda _callback: (lambda: None))
    dialog = SettingsDialog(manager, AnimationManager(), initial_target=target)
    try:
        tab = dialog.visualizers_tab
        assert tab._get_active_visualizer_mode() == mode
        assert not tab._vis_body_host.is_constructed(mode)  # the actual runtime-entry failure precondition
        dialog.open_initial_studio()
        assert len(opened) == 1
        assert tab._vis_body_host.is_constructed(mode)
        assert tab._vis_body_host.selected_mode == mode
        assert isinstance(getattr(tab, "_shockwave_grid_lazy_values"), dict)
        assert opened[0].initial_pose[spec.key("camera_fov")] == 63.0

        values = opened[0].store.snapshot()
        values[spec.key("camera_position")] = [0.3, -0.2, 0.4]
        values[spec.key("camera_fov")] = 63.0
        assert "Saved camera" in opened[0].store.save_camera(values)
        assert manager.get(f"widgets.spotify_visualizer.{spec.key('camera_fov')}") == pytest.approx(63.0)
    finally:
        if opened:
            opened[0].closed.emit()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()
        assert manager.flush(timeout=5.0)
