"""Tests for Widgets tab UI.

Verifies that WidgetsTab integrates correctly with the canonical nested
`widgets` settings structure (clock + weather) and that defaults and
roundtrips behave as expected.
"""
import pytest
import uuid

from PySide6.QtGui import QColor

from ui.tabs.widgets_tab import WidgetsTab
from core.settings import SettingsManager


@pytest.fixture
def widgets_tab(qt_app, settings_manager):
    """Create WidgetsTab for testing."""
    tab = WidgetsTab(settings_manager)
    yield tab
    tab.deleteLater()


class TestWidgetsTab:
    """Tests for Widgets tab UI component."""

    def test_widgets_tab_creation(self, qt_app, settings_manager):
        """WidgetsTab can be created and wired to SettingsManager."""
        tab = WidgetsTab(settings_manager)
        assert tab is not None
        assert tab._settings is settings_manager
        tab.deleteLater()

    def test_widgets_tab_default_values(self, qt_app, tmp_path):
        """Default widget settings match canonical SettingsManager defaults."""
        mgr = SettingsManager(organization="Test", application=f"WidgetsTabTest_{uuid.uuid4().hex}", storage_base_dir=tmp_path)
        # Ensure a clean slate and then re-apply canonical defaults so the
        # nested `widgets` map reflects SettingsManager._set_defaults().
        mgr.reset_to_defaults()

        tab = WidgetsTab(mgr)

        # Clock defaults: enabled on all monitors, Top Right, 24h, seconds on,
        # analogue mode with background frame enabled at 70% opacity.
        assert tab.clock_enabled.isChecked() is True
        assert tab.clock_position.currentText() == "Top Right"
        assert tab.clock_format.currentText() == "24 Hour"
        assert tab.clock_seconds.isChecked() is True
        assert tab.clock_show_background.isChecked() is True
        assert tab.clock_bg_opacity.value() == 60
        # Monitor selection uses canonical 'ALL' default so combo reflects that
        assert tab.clock_monitor_combo.currentText() == "ALL"

        # Weather defaults: enabled on monitor 1 with a Top Left layout and a
        # non-empty location (placeholder "New York" or a timezone-derived
        # city), styled with background enabled at 70% opacity.
        assert tab.weather_enabled.isChecked() is True
        assert tab.weather_position.currentText() == "Top Left"
        loc = tab.weather_location.text()
        assert isinstance(loc, str) and loc
        assert tab.weather_show_forecast.isChecked() is True  # Default is True per defaults.py
        assert tab.weather_show_background.isChecked() is True
        assert tab.weather_bg_opacity.value() == 60

        tab.deleteLater()


    def test_widgets_tab_saves_and_roundtrips(self, qt_app, widgets_tab):
        """Changing widget controls and saving updates nested `widgets` config."""
        tab = widgets_tab

        # Mutate some clock settings through the UI
        tab.clock_enabled.setChecked(True)
        tab.clock_position.setCurrentText("Bottom Left")
        tab.clock_show_background.setChecked(True)
        tab.clock_bg_opacity.setValue(75)  # 75%
        tab.clock_monitor_combo.setCurrentText("ALL")

        # Mutate some weather settings
        tab.weather_enabled.setChecked(True)
        tab.weather_location.setText("Johannesburg")
        tab.weather_position.setCurrentText("Bottom Left")
        tab.weather_monitor_combo.setCurrentText("ALL")
        tab.weather_show_forecast.setChecked(True)
        tab.weather_show_background.setChecked(True)
        tab.weather_bg_opacity.setValue(80)  # 80%

        # Persist settings (call _now directly; _save_settings is debounced)
        tab._save_settings_now()

        widgets_cfg = tab._settings.get("widgets", {})
        assert isinstance(widgets_cfg, dict)

        clock_cfg = widgets_cfg.get("clock", {})
        assert clock_cfg.get("enabled") is True
        assert clock_cfg.get("position") == "Bottom Left"
        assert clock_cfg.get("show_background") is True
        assert pytest.approx(clock_cfg.get("bg_opacity", 0.0)) == 0.75
        # Monitor stored as "ALL" string when combo shows ALL
        assert clock_cfg.get("monitor") == "ALL"

        weather_cfg = widgets_cfg.get("weather", {})
        assert weather_cfg.get("enabled") is True
        assert weather_cfg.get("location") == "Johannesburg"
        assert weather_cfg.get("position") == "Bottom Left"
        assert weather_cfg.get("show_forecast") is True
        assert weather_cfg.get("show_background") is True
        assert pytest.approx(weather_cfg.get("bg_opacity", 0.0)) == 0.80
        assert weather_cfg.get("monitor") == "ALL"

    def test_sine_wave_swatch_persistence(self, qt_app, settings_manager):
        """Glow + line swatch selections persist through save/load and update buttons."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)

        custom_glow = QColor(12, 34, 56, 200)
        custom_line = QColor(210, 180, 150, 128)
        first_tab._sine_glow_color = custom_glow
        first_tab._sine_line_color = custom_line
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._sine_glow_color) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab._sine_line_color) == _rgba_tuple(custom_line)
            assert _rgba_tuple(reloaded_tab.sine_glow_color_btn.color()) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab.sine_line_color_btn.color()) == _rgba_tuple(custom_line)
        finally:
            reloaded_tab.deleteLater()

    def test_visualizer_advanced_edit_switches_to_custom(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            # Force Spotify tab visible and preset slider available
            tab.spotify_vis_type_combo.setCurrentIndex(tab.spotify_vis_type_combo.findData("bubble"))
            preset_slider = getattr(tab, "_bubble_preset_slider", None)
            assert preset_slider is not None

            preset_slider.set_preset_index(0)  # curated preset
            assert preset_slider.preset_index() == 0

            # Simulate editing an advanced control (gradient direction combo lives in advanced container)
            gradient_combo = getattr(tab, "bubble_gradient_direction", None)
            assert gradient_combo is not None
            gradient_combo.setCurrentText("Bottom")
            gradient_combo.currentTextChanged.emit("Bottom")

            assert preset_slider.preset_index() == preset_slider.custom_index()
        finally:
            tab.deleteLater()
