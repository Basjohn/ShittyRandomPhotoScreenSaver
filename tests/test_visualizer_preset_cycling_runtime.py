from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest
from PySide6.QtCore import QObject, QPoint, QRect, Qt

from core.settings.visualizer_presets import (
    VISUALIZER_CUSTOM_STORAGE_KEY,
    get_custom_preset_index,
    get_preset_settings,
    get_preset_count,
)
from rendering.input_handler import InputHandler
from rendering.widget_manager import WidgetManager
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget


class _DummyParent(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.settings_manager = MagicMock()
        self.settings_manager.get.return_value = False
        self._coordinator = MagicMock()
        self._coordinator.ctrl_held = False


def _make_widget_manager_parent():
    parent = MagicMock()
    parent.screen_index = 0
    type(parent)._has_rendered_first_frame = PropertyMock(return_value=True)
    return parent


def test_widget_manager_cycle_visualizer_preset_updates_settings(settings_manager):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg["mode"] = "spectrum"
    spotify_cfg["preset_spectrum"] = 0
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("spectrum", 1) is True

    updated_widgets = settings_manager.get("widgets", {}) or {}
    updated_vis = updated_widgets.get("spotify_visualizer", {}) or {}
    assert int(updated_vis.get("preset_spectrum", -1)) == 1


def test_widget_manager_cycle_visualizer_preset_wraps_backward(settings_manager):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    custom_index = get_custom_preset_index("spectrum")
    assert custom_index >= 1

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg["mode"] = "spectrum"
    spotify_cfg["preset_spectrum"] = 0
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("spectrum", -1) is True

    updated_widgets = settings_manager.get("widgets", {}) or {}
    updated_vis = updated_widgets.get("spotify_visualizer", {}) or {}
    assert int(updated_vis.get("preset_spectrum", -1)) == custom_index


def test_widget_manager_cycle_visualizer_preset_restores_custom_snapshot(settings_manager, monkeypatch):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    custom_index = get_custom_preset_index("spectrum")

    def _fake_apply(mode, index, config):
        merged = dict(config)
        if index != custom_index:
            merged["spectrum_glow_intensity"] = 0.91
            merged["spectrum_growth"] = 5.25
        return merged

    monkeypatch.setattr("rendering.widget_manager.apply_preset_to_config", _fake_apply)

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update({
        "mode": "spectrum",
        "preset_spectrum": custom_index,
        "spectrum_glow_intensity": 0.17,
        "spectrum_growth": 1.75,
    })
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("spectrum", 1) is True

    custom_cache = settings_manager.get(VISUALIZER_CUSTOM_STORAGE_KEY, {}) or {}
    assert custom_cache["spectrum"]["spectrum_glow_intensity"] == pytest.approx(0.17)
    assert custom_cache["spectrum"]["spectrum_growth"] == pytest.approx(1.75)

    after_curated = (settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}
    assert after_curated["preset_spectrum"] == 0
    assert after_curated["spectrum_glow_intensity"] == pytest.approx(0.91)
    assert after_curated["spectrum_growth"] == pytest.approx(5.25)

    assert wm.cycle_visualizer_preset("spectrum", -1) is True

    restored = (settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}
    assert restored["preset_spectrum"] == custom_index
    assert restored["spectrum_glow_intensity"] == pytest.approx(0.17)
    assert restored["spectrum_growth"] == pytest.approx(1.75)


def test_widget_manager_cycle_visualizer_preset_defers_disk_save(settings_manager, monkeypatch):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg["mode"] = "spectrum"
    spotify_cfg["preset_spectrum"] = 0
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    scheduled: list[tuple[int, int]] = []
    save_calls: list[str] = []

    def _fake_single_shot(delay_ms, func, token):
        scheduled.append((int(delay_ms), int(token)))

    def _fake_save():
        save_calls.append("save")

    monkeypatch.setattr("rendering.widget_manager.ThreadManager.single_shot", _fake_single_shot)
    monkeypatch.setattr(settings_manager, "save", _fake_save)

    assert wm.cycle_visualizer_preset("spectrum", 1) is True

    assert save_calls == []
    assert scheduled == [(wm.PRESET_PERSIST_DELAY_MS, 1)]


def test_widget_manager_refresh_applies_curated_contract_for_hotswap(settings_manager):
    from core.settings.models import SpotifyVisualizerSettings

    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)

    class _FakeVis:
        def __init__(self):
            self.model = None

        def set_settings_model(self, model):
            self.model = model

        def apply_vis_mode_config(self, **kwargs):
            self.kwargs = dict(kwargs)

    fake_vis = _FakeVis()
    wm._widgets["spotify_visualizer"] = fake_vis

    cfg = {
        "spotify_visualizer": {
            "mode": "bubble",
            "preset_bubble": 0,
            # Deliberately conflicting runtime values that should not override curated.
            "bubble_manual_floor": 0.31,
            "bubble_audio_block_size": 256,
        }
    }

    wm._refresh_spotify_visualizer_config(cfg)

    baseline = SpotifyVisualizerSettings.from_mapping({"mode": "bubble", "preset_bubble": 0})
    assert fake_vis.model is not None
    assert fake_vis.model.resolve_manual_floor("bubble") == pytest.approx(
        baseline.resolve_manual_floor("bubble")
    )
    assert fake_vis.model.resolve_audio_block_size("bubble") == baseline.resolve_audio_block_size("bubble")


def test_widget_manager_preset_cycle_forces_runtime_activation_reset(settings_manager):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)

    class _FakeVis:
        def __init__(self):
            self.reset_reasons: list[str] = []

        def set_settings_model(self, model):
            self.model = model

        def apply_vis_mode_config(self, **kwargs):
            self.kwargs = dict(kwargs)

        def reset_runtime_activation_state(self, *, reason: str = "activation"):
            self.reset_reasons.append(reason)

    fake_vis = _FakeVis()
    wm._widgets["spotify_visualizer"] = fake_vis

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg["mode"] = "spectrum"
    spotify_cfg["preset_spectrum"] = 0
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("spectrum", 1) is True

    assert fake_vis.reset_reasons == ["preset_cycle"]


def test_widget_manager_deferred_visualizer_preset_save_skips_stale_tokens(settings_manager, monkeypatch):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)

    save_calls: list[str] = []
    monkeypatch.setattr(settings_manager, "save", lambda: save_calls.append("save"))

    wm._visualizer_preset_save_token = 2
    wm._flush_visualizer_preset_save(1)
    assert save_calls == []

    wm._flush_visualizer_preset_save(2)
    assert save_calls == ["save"]


@pytest.mark.qt
def test_spotify_visualizer_handle_mouse_button_cycles_and_resets(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    wm = MagicMock()
    wm.cycle_visualizer_preset.return_value = True
    widget._widget_manager = wm
    widget._reset_visualizer_state = MagicMock()
    widget._request_latency_probe = MagicMock()

    assert widget.handle_mouse_button(Qt.MouseButton.MiddleButton) is True
    wm.cycle_visualizer_preset.assert_called_once_with("spectrum", 1)
    widget._reset_visualizer_state.assert_called_once_with(
        clear_overlay=False,
        replay_cached=False,
    )
    widget._request_latency_probe.assert_called_once_with("preset_cycle")


@pytest.mark.qt
def test_spotify_visualizer_handle_mouse_button_back_button_cycles_previous(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    wm = MagicMock()
    wm.cycle_visualizer_preset.return_value = True
    widget._widget_manager = wm
    widget._reset_visualizer_state = MagicMock()
    widget._request_latency_probe = MagicMock()

    assert widget.handle_mouse_button(Qt.MouseButton.XButton1) is True
    wm.cycle_visualizer_preset.assert_called_once_with("spectrum", -1)
    widget._reset_visualizer_state.assert_called_once()
    widget._request_latency_probe.assert_called_once_with("preset_cycle")


def test_input_handler_routes_visualizer_middle_click_only_on_hit():
    handler = InputHandler(_DummyParent())

    event = MagicMock()
    event.pos.return_value = QPoint(10, 10)
    event.button.return_value = Qt.MouseButton.MiddleButton

    vis = MagicMock()
    vis.isVisible.return_value = True
    vis.geometry.return_value = QRect(0, 0, 100, 100)
    vis.handle_mouse_button.return_value = True

    handled, reddit_handled, reddit_url = handler.route_widget_click(
        event,
        None,
        None,
        None,
        None,
        None,
        None,
        vis,
    )

    assert handled is True
    assert reddit_handled is False
    assert reddit_url is None
    vis.handle_mouse_button.assert_called_once_with(Qt.MouseButton.MiddleButton)

    vis.handle_mouse_button.reset_mock()
    event.pos.return_value = QPoint(200, 200)

    handled, _, _ = handler.route_widget_click(
        event,
        None,
        None,
        None,
        None,
        None,
        None,
        vis,
    )

    assert handled is False
    vis.handle_mouse_button.assert_not_called()


def test_input_handler_routes_visualizer_back_button():
    handler = InputHandler(_DummyParent())

    event = MagicMock()
    event.pos.return_value = QPoint(5, 5)
    event.button.return_value = Qt.MouseButton.XButton1

    vis = MagicMock()
    vis.isVisible.return_value = True
    vis.geometry.return_value = QRect(0, 0, 25, 25)
    vis.handle_mouse_button.return_value = True

    handled, _, _ = handler.route_widget_click(
        event,
        None,
        None,
        None,
        None,
        None,
        None,
        vis,
    )

    assert handled is True
    vis.handle_mouse_button.assert_called_once_with(Qt.MouseButton.XButton1)


def test_runtime_cycle_purges_stale_mode_keys_on_preset_switch(settings_manager, monkeypatch):
    """Cycling from a preset with extra mode keys to one without must purge stale keys.

    Regression test for the call-site MERGE bug: apply_preset_to_config correctly
    CLEAR+APPLYs on its copy, but the caller used .update() which never removed
    keys absent from the applied result. This caused custom-only keys like
    blob_shaper_enabled to persist across preset switches.
    """
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    custom_index = get_custom_preset_index("blob")
    preset_count = get_preset_count("blob")
    assert preset_count >= 2

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update({
        "mode": "blob",
        "preset_blob": custom_index,
        "blob_shaper_enabled": True,
        "blob_stretch": 0.5,
        "blob_color": [255, 0, 128, 255],
        "blob_some_custom_only_key": 42,
    })
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("blob", 1) is True

    updated_widgets = settings_manager.get("widgets", {}) or {}
    updated_vis = updated_widgets.get("spotify_visualizer", {}) or {}

    assert updated_vis.get("preset_blob") == 0

    assert "blob_some_custom_only_key" not in updated_vis, (
        "Stale custom-only blob key survived preset switch — "
        "call-site merge bug is back"
    )

    curated_has_shaper = "blob_shaper_enabled" in updated_vis
    if curated_has_shaper:
        pass
    else:
        assert "blob_shaper_enabled" not in updated_vis, (
            "blob_shaper_enabled survived from Custom into a curated preset "
            "that does not declare it — call-site merge bug is back"
        )


def test_runtime_cycle_custom_roundtrip_preserves_known_custom_keys(settings_manager, monkeypatch):
    """Custom → Curated → Custom must restore real custom keys via snapshot."""
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    custom_index = get_custom_preset_index("blob")

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update({
        "mode": "blob",
        "preset_blob": custom_index,
        "blob_stretch": 0.33,
        "blob_constant_wobble": 1.42,
    })
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset("blob", 1) is True

    assert wm.cycle_visualizer_preset("blob", -1) is True

    restored = (settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}
    assert restored.get("preset_blob") == custom_index
    assert restored.get("blob_stretch") == pytest.approx(0.33), (
        "Custom snapshot should restore blob_stretch after round-trip"
    )
    assert restored.get("blob_constant_wobble") == pytest.approx(1.42), (
        "Custom snapshot should restore blob_constant_wobble after round-trip"
    )


def test_runtime_cycle_enforces_curated_spectrum_technical_keys_without_losing_custom(settings_manager):
    wm = WidgetManager(_make_widget_manager_parent(), resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._refresh_spotify_visualizer_config = MagicMock()

    mode = "spectrum"
    custom_index = get_custom_preset_index(mode)
    curated = get_preset_settings(mode, 0)
    assert curated, "Expected at least one curated spectrum preset"
    assert "spectrum_dynamic_floor" in curated
    assert "spectrum_manual_floor" in curated

    curated_dynamic_floor = bool(curated["spectrum_dynamic_floor"])
    curated_manual_floor = float(curated["spectrum_manual_floor"])
    custom_dynamic_floor = not curated_dynamic_floor
    custom_manual_floor = 0.11 if abs(curated_manual_floor - 0.11) > 1e-9 else 0.89

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update(
        {
            "mode": mode,
            "preset_spectrum": custom_index,
            "spectrum_dynamic_floor": custom_dynamic_floor,
            "spectrum_manual_floor": custom_manual_floor,
            "spectrum_growth": 1.42,
        }
    )
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    assert wm.cycle_visualizer_preset(mode, 1) is True
    after_curated = (settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}
    assert after_curated.get("preset_spectrum") == 0
    assert bool(after_curated.get("spectrum_dynamic_floor")) is curated_dynamic_floor
    assert float(after_curated.get("spectrum_manual_floor")) == pytest.approx(curated_manual_floor)

    assert wm.cycle_visualizer_preset(mode, -1) is True
    restored = (settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}
    assert restored.get("preset_spectrum") == custom_index
    assert bool(restored.get("spectrum_dynamic_floor")) is custom_dynamic_floor
    assert float(restored.get("spectrum_manual_floor")) == pytest.approx(custom_manual_floor)
