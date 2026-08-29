"""Sine Line 4 integration through the current lazy WidgetsTab builder.

This replaces the retired ``build_sine_wave_tab``/standalone-swatch fixture with
an owner-shaped test: the visualizer section is hydrated through WidgetsTab,
then the shared swatches and shift control persist through the real save path.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
import pytest

from core.settings.visualizer_presets import get_custom_preset_index
from ui.styled_popup import ColorSwatchButton
from ui.tabs.widgets_tab import WidgetsTab


def _configure_sine_mode(settings_manager) -> None:
    widgets = settings_manager.get("widgets", {}) or {}
    widgets = dict(widgets)
    visualizer = dict(widgets.get("spotify_visualizer", {}) or {})
    visualizer.update(
        {
            "visualizers_enabled": True,
            "enabled": True,
            "mode": "sine_wave",
        }
    )
    widgets["spotify_visualizer"] = visualizer
    settings_manager.set("widgets", widgets)


@pytest.mark.qt
def test_lazy_visualizer_builder_persists_line4_color_glow_and_shift(
    qt_app,
    settings_manager,
):
    _configure_sine_mode(settings_manager)
    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "visualizers"},
    )
    try:
        assert isinstance(tab.sine_line4_color_btn, ColorSwatchButton)
        assert isinstance(tab.sine_line4_glow_btn, ColorSwatchButton)
        assert tab.vis_mode_combo.currentData() == "sine_wave"

        line = QColor(0, 255, 255, 230)
        glow = QColor(30, 60, 255, 180)
        tab.sine_line4_color_btn.set_color(line)
        tab.sine_line4_color_btn.color_changed.emit(line)
        tab.sine_line4_glow_btn.set_color(glow)
        tab.sine_line4_glow_btn.color_changed.emit(glow)
        tab.sine_line4_shift.setValue(40)

        # Flush through the real current save owner rather than waiting for the
        # debounce timer in this deterministic integration test.
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {})["spotify_visualizer"]
        assert saved["sine_line4_color"] == [0, 255, 255, 230]
        assert saved["sine_line4_glow_color"] == [30, 60, 255, 180]
        assert saved["sine_line4_shift"] == pytest.approx(0.40)
    finally:
        tab.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_line4_values_round_trip_through_lazy_visualizer_hydration(
    qt_app,
    settings_manager,
):
    _configure_sine_mode(settings_manager)
    widgets = settings_manager.get("widgets", {}) or {}
    visualizer = dict(widgets.get("spotify_visualizer", {}) or {})
    # Arbitrary user-authored mode values are authoritative only in the
    # trailing Custom slot. Curated presets intentionally overlay their authored
    # values during Settings hydration, matching runtime preset semantics.
    visualizer.update(
        {
            "preset_sine_wave": get_custom_preset_index("sine_wave"),
            "sine_line4_color": [11, 22, 33, 230],
            "sine_line4_glow_color": [44, 55, 66, 180],
            "sine_line4_shift": 0.37,
        }
    )
    widgets["spotify_visualizer"] = visualizer
    settings_manager.set("widgets", widgets)

    tab = WidgetsTab(
        settings_manager,
        lazy_sections=True,
        initial_view_state={"subtab_id": "visualizers"},
    )
    try:
        assert tab._sine_line4_color.getRgb() == (11, 22, 33, 230)
        assert tab._sine_line4_glow_color.getRgb() == (44, 55, 66, 180)
        assert tab.sine_line4_color_btn.color().getRgb() == (11, 22, 33, 230)
        assert tab.sine_line4_glow_btn.color().getRgb() == (44, 55, 66, 180)
        assert tab.sine_line4_shift.value() == 37
    finally:
        tab.deleteLater()
        qt_app.processEvents()
