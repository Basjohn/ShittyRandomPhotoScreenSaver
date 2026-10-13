"""Terrain persistence, configuration packing, source ownership and real lazy Settings."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from rendering.gl_programs.heightfield import normalize_heightfield


FIELD = {"version": 1, "size": 3, "heights": [0.0, 0.25, 0.5, 0.0, 0.0, 0.75, 0.1, 0.0, 1.0]}


def test_old_profiles_get_default_terrain_and_explicit_terrain_is_strict_and_detached():
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    from core.settings.visualizer_presets import build_normalized_custom_snapshot, normalize_visualizer_custom_snapshot_cache

    old = {"mode": "shockwave_grid", "shockwave_grid_allow_overflow": True,
           "shockwave_grid_shape_nodes": [[0.0, 0.31], [1.0, 0.68]],
           "shockwave_grid_wave_amplitude": 0.61, "shockwave_grid_profile_floor": 0.22,
           "shockwave_grid_drop_speed": 1.77, "shockwave_grid_input_gain": 0.81,
           "shockwave_grid_manual_floor": 0.17, "shockwave_grid_mirrored": False}
    normalized = normalize_visualizer_section_mapping(old, apply_preset_overlay=False)
    canonical = require_canonical_default("widgets.spotify_visualizer.shockwave_grid_terrain")
    assert normalized["shockwave_grid_terrain"] == canonical
    assert "shockwave_grid_allow_overflow" not in normalized
    for key, value in old.items():
        if key != "shockwave_grid_allow_overflow":
            assert normalized[key] == value
    cached = normalize_visualizer_custom_snapshot_cache({"shockwave_grid": old})["shockwave_grid"]
    assert cached["shockwave_grid_terrain"] == canonical
    assert cached["shockwave_grid_shape_nodes"] == old["shockwave_grid_shape_nodes"]
    assert "shockwave_grid_allow_overflow" not in cached
    authored = deepcopy(FIELD)
    model = SpotifyVisualizerSettings.from_mapping({**old, "shockwave_grid_terrain": authored}, apply_preset_overlay=False)
    authored["heights"][0] = 0.91
    saved = model.to_dict()["widgets.spotify_visualizer.shockwave_grid_terrain"]
    assert saved == FIELD
    saved["heights"][0] = 0.99
    assert model.shockwave_grid_terrain == FIELD
    snapshot = build_normalized_custom_snapshot("shockwave_grid", {**old, "shockwave_grid_terrain": FIELD})
    assert snapshot["shockwave_grid_terrain"] == FIELD
    for bad in (None, {"version": 1, "size": 3, "heights": [0.0] * 8}):
        with pytest.raises(ValueError, match="heightfield"):
            SpotifyVisualizerSettings.from_mapping({"shockwave_grid_terrain": bad}, apply_preset_overlay=False)


def test_terrain_is_packed_on_configuration_and_reused_by_identity_in_every_capture(monkeypatch):
    from rendering.gl_programs import heightfield
    from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs, shockwave_grid_parameters
    from widgets.spotify_visualizer.render_state import FrozenFields, freeze_render_fields

    calls = []
    original = heightfield.heightfield_surface_bytes
    monkeypatch.setattr(heightfield, "heightfield_surface_bytes", lambda data: (calls.append(data["size"]), original(data))[1])
    owner = SimpleNamespace()
    defaults = require_canonical_default("widgets.spotify_visualizer")
    apply_presentation_vis_mode_kwargs(owner, defaults)
    owner._scene3d_detail = "High"
    assert len(calls) == 1
    apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_terrain": FIELD})
    frozen = owner._shockwave_grid_terrain
    assert isinstance(frozen, FrozenFields)
    assert dict(frozen) == {"size": 3, "data": original(FIELD), "maximum": 1.0}
    for _ in range(20):
        parameters = shockwave_grid_parameters(owner)
        assert parameters["shockwave_grid_terrain"] is frozen
        assert freeze_render_fields(parameters)["shockwave_grid_terrain"] is frozen
    configured_sizes = [defaults["shockwave_grid_terrain"]["size"], 3]
    assert calls == configured_sizes  # only the two configure edges; never a frame
    apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_sky_strength": 0.43})
    assert owner._shockwave_grid_terrain is frozen and calls == configured_sizes
    with pytest.raises(ValueError):
        apply_presentation_vis_mode_kwargs(owner, {"shockwave_grid_terrain": {"version": 1, "size": 2, "heights": [float("nan")] * 4}})


def test_response_controls_project_to_existing_source_without_unused_private_attributes():
    from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs, apply_presentation_vis_mode_kwargs
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config

    values = {"shockwave_grid_wave_amplitude": 0.71, "shockwave_grid_profile_floor": 0.23, "shockwave_grid_drop_speed": 2.31}
    projected = resolve_mode_source_config("shockwave_grid", values)
    logical, presentation = SimpleNamespace(), SimpleNamespace()
    apply_logical_vis_mode_kwargs(logical, projected)
    apply_presentation_vis_mode_kwargs(presentation, projected)
    for key, value in values.items():
        assert projected[key.replace("shockwave_grid_", "spectrum_")] == value
        assert not hasattr(logical, f"_{key}") and not hasattr(presentation, f"_{key}")


def test_real_terrain_body_silent_roundtrip_reset_and_stroke_save_batch(qt_app, settings_manager, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    from core.settings.visualizer_presets import get_custom_preset_index
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings
    from ui.tabs.visualizers_tab import VisualizersTab

    pose = {"shockwave_grid_turn": 0.37, "shockwave_grid_tilt": 0.63,
            "shockwave_grid_scene_scale": 1.75, "shockwave_grid_scene_pan_x": -0.41, "shockwave_grid_scene_pan_y": 0.23}
    settings_manager.set("widgets", {"spotify_visualizer": {
        "enabled": True, "visualizers_enabled": True, "mode": "shockwave_grid",
        "mode_activation": build_visualizer_mode_activation(["shockwave_grid"]),
        "preset_shockwave_grid": get_custom_preset_index("shockwave_grid"), **pose,
        "shockwave_grid_terrain": FIELD,
    }})
    tab = VisualizersTab(settings_manager)
    try:
        tab._select_mode_page("shockwave_grid")
        calls = []
        monkeypatch.setattr(tab, "_save_settings", lambda: calls.append("save"))
        monkeypatch.setattr(tab, "_force_visualizer_preset_to_custom", lambda mode: calls.append(mode))
        load_spec_mode_settings(tab, "shockwave_grid", {
            **require_canonical_default("widgets.spotify_visualizer"), "shockwave_grid_terrain": FIELD,
            "shockwave_grid_sky_enabled": False,
        })
        assert calls == []
        assert not tab.shockwave_grid_sky_color_btn.isEnabled() and not tab.shockwave_grid_sky_strength.isEnabled()
        payload = collect_spec_mode_settings(tab, "shockwave_grid")
        assert payload["shockwave_grid_terrain"] == FIELD
        assert not set(pose) & set(payload) and "shockwave_grid_allow_overflow" not in payload
        for key in pose:
            assert not hasattr(tab, key)
        editor = tab.shockwave_grid_terrain_editor
        canvas = editor.canvas
        canvas.resize(500, 300)
        rect = canvas.field_rect()
        point = QPoint(round(rect.center().x()), round(rect.center().y()))
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=point)
        assert calls == []
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=point)
        assert calls == ["shockwave_grid", "save"]
        edited = collect_spec_mode_settings(tab, "shockwave_grid")["shockwave_grid_terrain"]
        assert edited != FIELD and normalize_heightfield(edited) == edited
        calls.clear()
        load_spec_mode_settings(tab, "shockwave_grid", {**payload, "shockwave_grid_terrain": edited})
        assert calls == [] and editor.get_heightfield() == edited
        editor.reset_button.click()
        assert calls == ["shockwave_grid", "save"]
        assert editor.get_heightfield() == require_canonical_default("widgets.spotify_visualizer.shockwave_grid_terrain")
        # Real Settings save/reopen retains terrain and independent internal view state.
        editor.set_heightfield(edited)
        tab._save_settings_now()
        stored = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert stored["shockwave_grid_terrain"] == edited
        assert all(stored[key] == value for key, value in pose.items())
    finally:
        tab.deleteLater()
        qt_app.processEvents()
    reopened = VisualizersTab(settings_manager)
    try:
        reopened._select_mode_page("shockwave_grid")
        assert reopened.shockwave_grid_terrain_editor.get_heightfield() == edited
    finally:
        reopened.deleteLater()
        qt_app.processEvents()


def test_test_owned_preset_cycle_preserves_custom_terrain_old_frequency_profile_and_view_pose(monkeypatch):
    from core.settings import visualizer_presets as presets
    from core.settings.visualizer_mode_registry import get_visualizer_view_pose_keys

    art = {"shockwave_grid_terrain": FIELD, "shockwave_grid_glow": 0.23}
    catalog = [presets.VisualizerPreset("Test Art", "Test-owned", art), presets.VisualizerPreset("Custom", "", {}, True)]
    monkeypatch.setattr(presets, "get_presets", lambda _mode: catalog)
    pose = {"shockwave_grid_turn": 0.2, "shockwave_grid_tilt": 0.3, "shockwave_grid_scene_scale": 1.6,
            "shockwave_grid_scene_pan_x": -0.4, "shockwave_grid_scene_pan_y": 0.7}
    live = {**require_canonical_default("widgets.spotify_visualizer"), **pose,
            "mode": "shockwave_grid", "shockwave_grid_terrain": {"version": 1, "size": 2, "heights": [0.0, 0.1, 0.0, 0.2]},
            "shockwave_grid_wave_amplitude": 0.72, "shockwave_grid_input_gain": 0.83,
            "shockwave_grid_shape_nodes": [[0.0, 0.31], [1.0, 0.68]], "position": "Custom"}
    assert set(pose) <= set(get_visualizer_view_pose_keys("shockwave_grid"))
    custom = presets.build_normalized_custom_snapshot("shockwave_grid", live)
    assert not set(pose) & set(custom)
    resolved = presets.apply_preset_to_config("shockwave_grid", 0, live)
    assert resolved["shockwave_grid_terrain"] == FIELD
    assert all(resolved[key] == value for key, value in pose.items())
    assert presets.restore_visualizer_snapshot("shockwave_grid", resolved, custom)
    assert resolved["shockwave_grid_terrain"] == live["shockwave_grid_terrain"]
    assert resolved["shockwave_grid_shape_nodes"] == live["shockwave_grid_shape_nodes"]
    assert resolved["shockwave_grid_input_gain"] == 0.83 and resolved["position"] == "Custom"
    assert all(resolved[key] == value for key, value in pose.items())
