from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest
from PySide6.QtCore import QObject, QPoint, QRect, Qt

from core.settings.visualizer_presets import (
    VISUALIZER_CUSTOM_STORAGE_KEY,
    get_custom_preset_index,
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
