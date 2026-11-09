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
