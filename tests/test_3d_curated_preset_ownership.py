"""Curated 3D snapshots explicitly own every consumed profile value."""
from __future__ import annotations

import dataclasses
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from core.settings.default_contract import get_raw_default_settings
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_presets import (
    apply_preset_to_config, get_custom_preset_index, get_preset_file_path,
    get_presets, resolve_visualizer_activation_payload,
    build_normalized_custom_snapshot, restore_visualizer_snapshot,
)
from core.settings.visualizer_settings_snapshot import normalize_visualizer_mode_payload
from tests.test_qtquick_extruded_spectrum import _snapshot, target
from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config
from widgets.spotify_visualizer.config_applier import apply_logical_vis_mode_kwargs


_BASE = get_raw_default_settings()["widgets"]["spotify_visualizer"]
_MODES = ("extruded_spectrum", "shockwave_grid")
_CASES = tuple((mode, index) for mode in _MODES for index, preset in enumerate(get_presets(mode)) if not preset.is_custom)


def _owned(mode):
    return {key for key in _BASE if key.startswith(mode + "_")}


def _raw(mode, index):
    path = get_preset_file_path(mode, index)
    assert path is not None
    assert path.resolve().is_relative_to((Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes").resolve())
    return json.loads(path.read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]


@pytest.mark.parametrize(("mode", "index"), _CASES)
def test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace(mode, index):
    raw = _raw(mode, index)
    assert set(raw) == _owned(mode) | {"mode"}
    assert raw["mode"] == mode
    # The loader may validate current types/ranges, but cannot be the author of
    # missing curated colours, response, material, ghost or source-shape state.
    assert normalize_visualizer_mode_payload(mode, raw) == get_presets(mode)[index].settings


@pytest.mark.parametrize(("mode", "index"), _CASES)
def test_curated_3d_apply_model_activation_and_source_projection_ignore_poisoned_custom_and_spectrum(mode, index):
    raw = _raw(mode, index)
    original = deepcopy(_BASE)
    original.update(mode=mode)
    original[f"preset_{mode}"] = index
    original["preset_spectrum"] = get_custom_preset_index("spectrum")
    # A previously edited Custom profile and its former Spectrum lender are
    # deliberately far from every curated 3D reaction/colour profile.
    for family in (mode, "spectrum"):
        original.update({
            f"{family}_bar_count": 61,
            f"{family}_manual_floor": 0.72,
            f"{family}_sensitivity": 0.03,
            f"{family}_input_gain": 0.25,
            f"{family}_shape_nodes": [[0.0, 0.05], [1.0, 0.05]],
            f"{family}_wave_amplitude": 0.01,
            f"{family}_mirrored": False,
        })
    if mode == "extruded_spectrum":
        original.update({
            "extruded_spectrum_bar_fill_color": [241, 37, 91, 23],
            "extruded_spectrum_bar_border_color": [11, 72, 31, 19],
            "extruded_spectrum_ghost_decay": 0.94,
            "extruded_spectrum_body_alpha": 0.12,
            "extruded_spectrum_shadow_enabled": True,
        })
    untouched = deepcopy(original)
    applied = apply_preset_to_config(mode, index, original)
    assert original == untouched
    for key in _owned(mode):
        assert applied[key] == raw[key], key
    for key in _owned("spectrum"):
        assert applied[key] == original[key], key

    model = SpotifyVisualizerSettings.from_mapping(original)
    serialized = model.to_dict()
    activation = resolve_visualizer_activation_payload(original)
    assert activation.mode == mode and activation.preset_index == index
    for key in _owned(mode):
        assert serialized[f"widgets.spotify_visualizer.{key}"] == raw[key], key
        assert activation.resolved_config[key] == raw[key], key
    projected = resolve_mode_source_config(mode, activation.resolved_config)
    for suffix in ("mirrored", "shape_nodes", "notch_positions_mirrored", "notch_positions_linear",
                   "lane_strengths_mirrored", "lane_strengths_linear", "wave_amplitude", "profile_floor", "drop_speed"):
        assert projected[f"spectrum_{suffix}"] == raw[f"{mode}_{suffix}"], suffix
    if mode == "extruded_spectrum":
        for suffix in ("bar_fill_color", "bar_border_color", "bar_border_opacity"):
            assert projected[suffix] == raw[f"{mode}_{suffix}"]
        for suffix in ("ghosting_enabled", "ghost_alpha", "ghost_decay"):
            assert projected[f"spectrum_{suffix}"] == raw[f"{mode}_{suffix}"]


@pytest.mark.parametrize(("mode", "index"), _CASES)
def test_raw_curated_3d_normalization_cannot_borrow_changed_spectrum_catalogue(mode, index, monkeypatch):
    import core.settings.visualizer_presets as catalog

    before = normalize_visualizer_mode_payload(mode, _raw(mode, index))
    read = catalog.get_preset_settings

    def hostile_lender(selected_mode, preset_index):
        if selected_mode == "spectrum":
            # Section normalization may migrate absent *other* modes while
            # constructing its full model. None of these changed lender values
            # may enter the already-complete target curated payload.
            changed = deepcopy(read(selected_mode, preset_index))
            changed.update(
                spectrum_bar_count=61, spectrum_manual_floor=0.72,
                spectrum_shape_nodes=[[0.0, 0.02], [1.0, 0.02]],
                spectrum_wave_amplitude=0.01, spectrum_input_gain=0.25,
                spectrum_bar_fill_color=[237, 19, 83, 61],
            )
            return changed
        return read(selected_mode, preset_index)

    monkeypatch.setattr(catalog, "get_preset_settings", hostile_lender)
    assert normalize_visualizer_mode_payload(mode, _raw(mode, index)) == before


def test_extruded_presets_restore_different_authored_shapes_response_and_colour_paths():
    first, second = (_raw("extruded_spectrum", index) for index in (0, 1))
    assert first["extruded_spectrum_shape_nodes"] != second["extruded_spectrum_shape_nodes"]
    assert first["extruded_spectrum_wave_amplitude"] != second["extruded_spectrum_wave_amplitude"]
    assert first["extruded_spectrum_colouring"] != second["extruded_spectrum_colouring"]
    assert first["extruded_spectrum_mirrored"] != second["extruded_spectrum_mirrored"]


@pytest.mark.parametrize("mode", _MODES)
def test_custom_source_colour_and_material_state_survives_all_curated_round_trips(mode):
    current = deepcopy(_BASE)
    current.update(mode=mode)
    current[f"preset_{mode}"] = get_custom_preset_index(mode)
    current[f"{mode}_shape_nodes"] = [[0.0, 0.18], [0.4, 0.84], [1.0, 0.29]]
    current[f"{mode}_input_gain"] = 0.71
    current[f"{mode}_mirrored"] = False
    if mode == "extruded_spectrum":
        current.update(
            extruded_spectrum_bar_fill_color=[21, 97, 172, 101],
            extruded_spectrum_body_alpha=0.38, extruded_spectrum_ghost_alpha=0.16,
        )
    custom = build_normalized_custom_snapshot(mode, current)
    preserved = deepcopy(custom)
    sibling = next(other for other in _MODES if other != mode)
    sibling_values = {key: deepcopy(current[key]) for key in _owned(sibling)}
    for index, preset in enumerate(get_presets(mode)):
        if preset.is_custom:
            continue
        current = apply_preset_to_config(mode, index, current)
        current[f"preset_{mode}"] = index
        assert {key: current[key] for key in sibling_values} == sibling_values
        assert restore_visualizer_snapshot(mode, current, custom)
        current[f"preset_{mode}"] = get_custom_preset_index(mode)
        activation = resolve_visualizer_activation_payload(current)
        assert activation.is_custom
        assert {key: activation.resolved_config[key] for key in _owned(mode)} == {
            key: preserved[key] for key in _owned(mode)
        }
        assert custom == preserved


@pytest.mark.parametrize("mode", _MODES)
def test_each_3d_mode_owns_the_smoothing_values_consumed_by_the_shared_frame_runtime(mode):
    keys = (f"{mode}_visual_smoothing_enabled", f"{mode}_visual_smoothing")
    assert all(key in _BASE for key in keys), "Consumed smoothing must have a 3D-owned canonical namespace"
    config = deepcopy(_BASE)
    config.update({
        "mode": mode, f"preset_{mode}": get_custom_preset_index(mode),
        keys[0]: False, keys[1]: 0.17,
        "preset_spectrum": get_custom_preset_index("spectrum"),
        "spectrum_visual_smoothing_enabled": True, "spectrum_visual_smoothing": 0.91,
    })
    activation = resolve_visualizer_activation_payload(config)
    projected = resolve_mode_source_config(mode, activation.resolved_config)
    state = SimpleNamespace()
    apply_logical_vis_mode_kwargs(state, projected)
    # These exact fields are consumed by _capture_spectrum_family; checking
    # only newly added UI/default keys would miss a missing projection caller.
    assert state._spectrum_visual_smoothing_enabled is False
    assert state._spectrum_visual_smoothing == pytest.approx(0.17)


@pytest.mark.parametrize("mode", _MODES)
def test_persisted_startup_promotes_missing_owned_temporal_and_profile_keys_before_default_fill(mode, tmp_path, qt_app):
    from core.settings.json_store import determine_storage_path
    from core.settings.settings_manager import SettingsManager
    app = "Owned3DProfile"
    path = determine_storage_path(app, base_dir=tmp_path)
    path.parent.mkdir(parents=True)
    source_index = 1
    legacy = {"mode": mode, "preset_spectrum": source_index,
              f"preset_{mode}": get_custom_preset_index(mode),
              f"{mode}_visual_smoothing": 0.23}
    expected = apply_preset_to_config("spectrum", source_index, deepcopy(legacy))
    path.write_text(json.dumps({"version": 2, "snapshot": {
        "widgets": {"spotify_visualizer": legacy}}}), encoding="utf-8")
    manager = SettingsManager(application=app, storage_base_dir=tmp_path)
    current = manager.get("widgets.spotify_visualizer")
    for suffix in ("bar_count", "audio_block_size", "shape_nodes", "visual_smoothing_enabled"):
        assert current[f"{mode}_{suffix}"] == expected[f"spectrum_{suffix}"]
    assert current[f"{mode}_visual_smoothing"] == pytest.approx(0.23)
    assert current[f"{mode}_solid_bar_hysteresis_enabled"] == (expected["spectrum_render_mode"] == "bars")
    owned = {key: deepcopy(current[key]) for key in _owned(mode)}
    current.update(preset_spectrum=get_custom_preset_index("spectrum"),
                   spectrum_render_mode="segment", spectrum_visual_smoothing=0.99,
                   spectrum_bar_count=61)
    manager.set("widgets.spotify_visualizer", current)
    assert manager.flush()
    # Force disk reload before constructing another production manager.
    manager._settings.load()
    reopened = SettingsManager(application=app, storage_base_dir=tmp_path)
    assert {key: reopened.get("widgets.spotify_visualizer")[key] for key in owned} == owned


@pytest.mark.parametrize("mode", _MODES)
def test_missing_custom_stabilization_preserves_segmented_spectrum_once(mode):
    from core.settings.visualizer_settings_contract import migrate_profile_lender_owned_settings
    source = {"preset_spectrum": get_custom_preset_index("spectrum"),
              "spectrum_render_mode": "segment", "spectrum_visual_smoothing_enabled": False,
              "spectrum_visual_smoothing": 0.82}
    migrated = migrate_profile_lender_owned_settings(source)
    assert migrated[f"{mode}_solid_bar_hysteresis_enabled"] is False
    assert migrated[f"{mode}_visual_smoothing_enabled"] is False
    assert migrated[f"{mode}_visual_smoothing"] == pytest.approx(0.82)
    migrated["spectrum_render_mode"] = "bars"
    assert migrate_profile_lender_owned_settings(migrated)[f"{mode}_solid_bar_hysteresis_enabled"] is False


@pytest.mark.parametrize("mode", _MODES)
def test_replay_real_capture_consumes_owned_temporal_state_and_engine_shape(mode, monkeypatch, qt_app):
    from tools.visualizer_replay.driver import replay_clip
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from tests.test_visualizer_replay_real_scale import _frame
    from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime
    from tools.visualizer_replay.engine import ReplayBeatEngine
    calls = []
    original = SpectrumFrameRuntime.resolve
    def observe(runtime, bars, **kwargs):
        calls.append(kwargs)
        return original(runtime, bars, **kwargs)
    monkeypatch.setattr(SpectrumFrameRuntime, "resolve", observe)
    shapes = []
    shape_method = ReplayBeatEngine.set_spectrum_shape_nodes
    def shape(engine, nodes):
        shapes.append(deepcopy(nodes))
        return shape_method(engine, nodes)
    monkeypatch.setattr(ReplayBeatEngine, "set_spectrum_shape_nodes", shape)
    config = deepcopy(_BASE)
    config.update({"mode": mode, f"preset_{mode}": get_custom_preset_index(mode),
                   f"{mode}_visual_smoothing_enabled": False,
                   f"{mode}_visual_smoothing": 0.17,
                   f"{mode}_solid_bar_hysteresis_enabled": False,
                   f"{mode}_shape_nodes": [[0, 0.2], [1, 0.8]],
                   "spectrum_visual_smoothing_enabled": True, "spectrum_visual_smoothing": 0.94,
                   "spectrum_render_mode": "bars", "spectrum_ghosting_enabled": True,
                   "spectrum_shape_nodes": [[0, 0.9], [1, 0.1]]})
    clip = FeatureClip("owned_3d_temporal", tuple(_frame(index, loudness=9.0, presence=1.0) for index in range(3)))
    result = replay_clip(clip, mode, settings=config)
    assert len(result["logical_series"]) == 3
    assert calls and all(not call["smoothing_enabled"] and not call["single_piece"]
                         and call["smoothing_strength"] == pytest.approx(0.17) for call in calls)
    assert shapes == [config[f"{mode}_shape_nodes"]]
    if mode == "shockwave_grid":
        assert all(call["ghosting_enabled"] is False for call in calls)


def test_recorder_applies_source_projection_before_its_engine_configuration(monkeypatch, qt_app):
    from tools.visualizer_replay import record
    from widgets.spotify_visualizer import source_config_applier
    monkeypatch.setattr("core.settings.settings_manager.SettingsManager", lambda: SimpleNamespace(
        get=lambda _: deepcopy(_BASE),
    ))
    projected = []
    original = source_config_applier.resolve_mode_source_config
    expected_nodes = [[0.0, 0.13], [1.0, 0.71]]
    def observe(mode, values):
        projected.append(mode)
        resolved = original(mode, values)
        resolved["spectrum_shape_nodes"] = expected_nodes
        return resolved
    monkeypatch.setattr(source_config_applier, "resolve_mode_source_config", observe)
    controller, engine = record._configured_engine()
    try:
        assert projected == ["sphere"]
        assert engine._audio_worker._spectrum_shape_nodes == expected_nodes
    finally:
        record._close_configured_engine(controller, engine)


@pytest.mark.parametrize("mode", ("spectrum", *_MODES))
def test_shared_temporal_ui_uses_owned_values_and_custom_save_flow(mode, qt_app):
    from PySide6.QtWidgets import QWidget, QVBoxLayout
    from tests._settings_context_stub import CanonicalWidgetDefaultsStub
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls
    class Tab(CanonicalWidgetDefaultsStub):
        def __init__(self):
            super().__init__()
            self.saved = 0
            self.custom = 0
        def _save_settings(self, *_):
            self.saved += 1
        def _force_visualizer_preset_to_custom(self):
            self.custom += 1
    tab = Tab()
    host = QWidget()
    layout = QVBoxLayout(host)
    # Dormant body has no controls or signal connections before its builder.
    assert not hasattr(tab, f"{mode}_visual_smoothing")
    build_spectrum_smoothing_controls(tab, layout, mode_key=mode)
    enabled = getattr(tab, f"{mode}_visual_smoothing_enabled")
    strength = getattr(tab, f"{mode}_visual_smoothing")
    strength.setValue(17)
    enabled.setChecked(False)
    assert tab.saved == 2
    assert tab.custom == (0 if mode == "spectrum" else 2)
    assert getattr(tab, f"{mode}_visual_smoothing_label").text() == "17%"
    assert strength.parentWidget().isHidden()
    if mode != "spectrum":
        stabilization = getattr(tab, f"{mode}_solid_bar_hysteresis_enabled")
        stabilization.setChecked(False)
        assert tab.saved == 3 and tab.custom == 3


@pytest.mark.qt
@pytest.mark.parametrize("colouring", ("Spectral Faces", "Spectral Edges", "Bar Colours"))
def test_existing_extruded_rainbow_colour_field_is_consumed_only_by_spectral_colouring(target, colouring):
    capture, host = target
    descriptor = get_visualizer_mode_descriptor("extruded_spectrum")
    assert descriptor.rainbow_controls is False
    assert "extruded_spectrum_rainbow_enabled" not in _BASE
    common = {
        "extruded_spectrum_colouring": colouring, "extruded_spectrum_hue_drift": 1.0,
        "extruded_spectrum_face_mirror": 0.0, "extruded_spectrum_reflection": 0.0,
        "extruded_spectrum_shadow_enabled": False, "extruded_spectrum_body_alpha": 1.0,
    }
    snapshot = _snapshot(**common)
    def at_animation(seconds):
        mode_state = dataclasses.replace(snapshot.logical.mode_state, animation_time=seconds)
        return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=mode_state))
    initial = capture.render(host, at_animation(0.0))
    drifted = capture.render(host, at_animation(1.0))
    if colouring == "Bar Colours":
        assert np.array_equal(initial, drifted)
    else:
        assert (np.abs(initial[..., :3] - drifted[..., :3]).max(axis=2) > 8).sum() > 200
        state = dataclasses.replace(snapshot.logical.mode_state, parameters={
            **dict(snapshot.logical.mode_state.parameters), "extruded_spectrum_hue_drift": 0.0,
        })
        snapshot = dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
        assert np.array_equal(capture.render(host, at_animation(0.0)), capture.render(host, at_animation(1.0)))
