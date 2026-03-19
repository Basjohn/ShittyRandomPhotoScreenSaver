"""Tests for Widgets tab UI.

Verifies that WidgetsTab integrates correctly with the canonical nested
`widgets` settings structure (clock + weather) and that defaults and
roundtrips behave as expected.
"""
import pytest
# Some CI environments install the wheel without sip stubs; guard the import.
try:  # pragma: no cover - only for environments with sip installed separately
    import sip  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    sip = None  # WidgetsTab tests do not use sip directly
import uuid

from PySide6.QtGui import QColor

from ui.tabs.widgets_tab import WidgetsTab
from ui.tabs.shared_styles import SPINBOX_STYLE
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
        # analogue mode with the background frame OFF to match new defaults snapshot.
        assert tab.clock_enabled.isChecked() is True
        assert tab.clock_position.currentText() == "Top Right"
        assert tab.clock_format.currentText() == "24 Hour"
        assert tab.clock_seconds.isChecked() is True
        assert tab.clock_show_background.isChecked() is False
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

    def test_spectrum_swatch_persistence(self, qt_app, settings_manager):
        """Spectrum bar fill/border swatches persist and hydrate swatch buttons."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)

        custom_fill = QColor(90, 200, 145, 210)
        custom_border = QColor(30, 60, 90, 255)
        first_tab._spotify_vis_fill_color = custom_fill
        first_tab._spotify_vis_border_color = custom_border
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._spotify_vis_fill_color) == _rgba_tuple(custom_fill)
            assert _rgba_tuple(reloaded_tab._spotify_vis_border_color) == _rgba_tuple(custom_border)
            assert _rgba_tuple(reloaded_tab.vis_fill_color_btn.color()) == _rgba_tuple(custom_fill)
            assert _rgba_tuple(reloaded_tab.vis_border_color_btn.color()) == _rgba_tuple(custom_border)
        finally:
            reloaded_tab.deleteLater()

    def test_oscilloscope_swatch_persistence(self, qt_app, settings_manager):
        """Oscilloscope glow + line swatches persist through save/load and sync button UI."""

        def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
            return color.red(), color.green(), color.blue(), color.alpha()

        first_tab = WidgetsTab(settings_manager)

        custom_glow = QColor(33, 77, 190, 210)
        custom_line = QColor(240, 245, 250, 180)
        first_tab._osc_glow_color = custom_glow
        first_tab._osc_line_color = custom_line
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert _rgba_tuple(reloaded_tab._osc_glow_color) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab._osc_line_color) == _rgba_tuple(custom_line)
            assert _rgba_tuple(reloaded_tab.osc_glow_color_btn.color()) == _rgba_tuple(custom_glow)
            assert _rgba_tuple(reloaded_tab.osc_line_color_btn.color()) == _rgba_tuple(custom_line)
        finally:
            reloaded_tab.deleteLater()

    def test_visualizer_advanced_edit_switches_to_custom(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            tab._load_settings()
            def _instant_save() -> None:
                tab._auto_switch_preset_to_custom()
                tab._save_settings_now()
            tab._save_settings = _instant_save
            tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("bubble"))
            preset_slider = getattr(tab, "_bubble_preset_slider", None)
            assert preset_slider is not None

            preset_slider.set_preset_index(0)  # curated preset without emitting
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.setdefault('spotify_visualizer', {})
            spotify_vis['preset_bubble'] = 0
            tab._settings.set('widgets', widgets_cfg)
            tab._settings.save()

            gradient_combo = getattr(tab, "bubble_gradient_direction", None)
            assert gradient_combo is not None
            gradient_combo.setCurrentText("Bottom")
            gradient_combo.currentTextChanged.emit("Bottom")
            tab._save_settings()
            qt_app.processEvents()

            assert preset_slider.preset_index() == preset_slider.custom_index()
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.get('spotify_visualizer', {})
            assert spotify_vis.get('preset_bubble') == preset_slider.custom_index()
        finally:
            tab.deleteLater()

    def test_visualizer_custom_preset_roundtrip(self, qt_app, settings_manager):
        """Custom visualizer config survives curated preset switches and restores UI state."""

        tab = WidgetsTab(settings_manager)
        try:
            mode = "spectrum"
            tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
            slider = getattr(tab, "_spectrum_preset_slider", None)
            assert slider is not None
            custom_index = slider.custom_index()

            custom_snapshot = {
                "mode": mode,
                "preset_spectrum": custom_index,
                "monitor": "PRIMARY",
                "spectrum_growth": 3.7,
                "spectrum_wave_amplitude": 0.82,
                "spectrum_shape_nodes": [[0.0, 0.15], [0.4, 0.85], [1.0, 0.55]],
                "spectrum_profile_floor": 0.08,
            }

            widgets_cfg = settings_manager.get("widgets", {}) or {}
            widgets_cfg["spotify_visualizer"] = custom_snapshot.copy()
            settings_manager.set("widgets", widgets_cfg)

            tab._load_settings()
            # Save immediately during preset changes to avoid timer-based debounce in tests.
            tab._save_settings = tab._save_settings_now

            # Switch to curated preset slot 0 (should snapshot custom state first).
            slider.set_preset_index(0)
            tab._on_visualizer_preset_changed(mode, 0)

            cache = settings_manager.get("visualizer_custom_presets", {})
            assert isinstance(cache, dict)
            assert mode in cache
            assert cache[mode]["spectrum_growth"] == pytest.approx(3.7)

            # Switch back to Custom and expect the snapshot to restore values.
            slider.set_preset_index(custom_index)
            tab._on_visualizer_preset_changed(mode, custom_index)

            restored = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
            assert restored.get("preset_spectrum") == custom_index
            assert restored.get("spectrum_growth") == pytest.approx(3.7)
            assert restored.get("spectrum_wave_amplitude") == pytest.approx(0.82)
            assert restored.get("spectrum_profile_floor") == pytest.approx(0.08)
        finally:
            tab.deleteLater()

    def test_spinbox_stylesheet_attached(self, qt_app, settings_manager):
        """WidgetsTab stylesheet must keep the shared QSpinBox skin."""

        tab = WidgetsTab(settings_manager)
        try:
            css = tab.styleSheet()
            assert css, "WidgetsTab stylesheet should not be empty"
            assert "QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox" in css
            assert "QSpinBox::up-button" in css
            expected_token = "background-color: #282828"
            assert SPINBOX_STYLE.strip() in css or expected_token in css
        finally:
            tab.deleteLater()

    def test_visualizers_toggle_gates_controls(self, qt_app, settings_manager):
        """Master + Beat Visualizer toggles should persist state changes in settings."""

        tab = WidgetsTab(settings_manager)
        try:
            tab._load_settings()
            tab._save_settings = tab._save_settings_now

            master_initial = tab.visualizers_enabled.isChecked()
            tab.visualizers_enabled.setChecked(not master_initial)
            tab._save_settings_now()
            cfg = tab._settings.get('widgets', {}).get('spotify_visualizer', {})
            assert cfg.get('visualizers_enabled') is (not master_initial)

            beat_initial = tab.vis_enabled_checkbox.isChecked()
            tab.vis_enabled_checkbox.setChecked(not beat_initial)
            tab._save_settings_now()
            cfg = tab._settings.get('widgets', {}).get('spotify_visualizer', {})
            assert cfg.get('enabled') is (not beat_initial)

            # Disable both to verify persisted reload state
            tab.visualizers_enabled.setChecked(False)
            tab.vis_enabled_checkbox.setChecked(False)
            tab._save_settings_now()
            tab.deleteLater()

            reloaded = WidgetsTab(settings_manager)
            try:
                reloaded._load_settings()
                qt_app.processEvents()
                cfg = reloaded._settings.get('widgets', {}).get('spotify_visualizer', {})
                assert cfg.get('visualizers_enabled') is False
                assert cfg.get('enabled') is False
            finally:
                reloaded.deleteLater()
        finally:
            pass
