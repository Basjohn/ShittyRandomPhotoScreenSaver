"""Tests for Widgets tab UI.

Verifies that WidgetsTab integrates correctly with the canonical nested
`widgets` settings structure (clock + weather) and that defaults and
roundtrips behave as expected.
"""
from pathlib import Path

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
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
)

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

    def test_secondary_line_ghost_toggles_persist(self, qt_app, settings_manager):
        first_tab = WidgetsTab(settings_manager)
        first_tab.osc_ghost_line2_enabled.setChecked(False)
        first_tab.osc_ghost_line3_enabled.setChecked(True)
        first_tab.sine_ghost_line2_enabled.setChecked(True)
        first_tab.sine_ghost_line3_enabled.setChecked(False)
        first_tab._save_settings_now()
        first_tab.deleteLater()

        reloaded_tab = WidgetsTab(settings_manager)
        try:
            assert reloaded_tab.osc_ghost_line2_enabled.isChecked() is False
            assert reloaded_tab.osc_ghost_line3_enabled.isChecked() is True
            assert reloaded_tab.sine_ghost_line2_enabled.isChecked() is True
            assert reloaded_tab.sine_ghost_line3_enabled.isChecked() is False
        finally:
            reloaded_tab.deleteLater()

    def test_visualizer_advanced_edit_switches_to_custom(self, qt_app, settings_manager):
        tab = WidgetsTab(settings_manager)
        try:
            tab._load_settings()
            tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("bubble"))
            preset_slider = getattr(tab, "_bubble_preset_slider", None)
            assert preset_slider is not None

            preset_slider.set_preset_index(0)  # curated preset without emitting
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.setdefault('spotify_visualizer', {})
            spotify_vis['preset_bubble'] = 0
            tab._settings.set('widgets', widgets_cfg)
            tab._settings.save()

            pulse_slider = getattr(tab, "bubble_big_bass_pulse", None)
            assert pulse_slider is not None
            pulse_slider.setValue(min(pulse_slider.maximum(), pulse_slider.value() + 5))
            qt_app.processEvents()
            tab._save_settings_now()

            assert preset_slider.preset_index() == preset_slider.custom_index()
            widgets_cfg = tab._settings.get('widgets', {}) or {}
            spotify_vis = widgets_cfg.get('spotify_visualizer', {})
            assert spotify_vis.get('preset_bubble') == preset_slider.custom_index()
        finally:
            tab.deleteLater()


def test_visualizer_bucket_toggles_use_standard_circle_checkbox_spacing():
    src = Path(r"F:\Programming\Apps\ShittyRandomPhotoScreenSaver\ui\tabs\media\technical_controls.py").read_text(encoding="utf-8")
    toggle_block_start = src.index("def _build_visibility_toggle(")
    toggle_block_end = src.index("def _aligned_row_widget(", toggle_block_start)
    toggle_block = src[toggle_block_start:toggle_block_end]
    assert 'toggle.setProperty("circleIndicator", True)' in toggle_block
    assert 'toggle.setProperty("tightSpacing", True)' not in toggle_block


def test_sine_curated_preset_survives_save_and_reload(qt_app, settings_manager):
    """Selecting a curated Sine preset must not silently fall back to Custom."""

    tab = WidgetsTab(settings_manager)
    try:
        mode = "sine_wave"
        curated_index = 0
        slider = tab._sine_preset_slider
        custom_index = slider.custom_index()

        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider.set_preset_index(custom_index)
        slider._slider.setValue(curated_index)
        qt_app.processEvents()
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("preset_sine_wave") == curated_index
        assert slider.preset_index() == curated_index
        assert slider.preset_index() != custom_index
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        reloaded._load_settings()
        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("preset_sine_wave") == curated_index
        assert reloaded._sine_preset_slider.preset_index() == curated_index
        assert reloaded._sine_preset_slider.preset_index() != reloaded._sine_preset_slider.custom_index()
    finally:
        reloaded.deleteLater()


def test_visualizer_mode_builders_keep_preset_scaffold_wiring(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        for descriptor in iter_visualizer_mode_descriptors():
            slider = getattr(tab, descriptor.preset_slider_attr)
            assert slider._advanced_container is not None, descriptor.mode_id
            assert slider._technical_container is not None, descriptor.mode_id
            assert slider._advanced_container.parent() is not None, descriptor.mode_id
            assert slider._technical_container.parent() is not None, descriptor.mode_id
    finally:
        tab.deleteLater()


def test_visualizer_sparse_mapping_uses_first_preset_fallback(qt_app, settings_manager):
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    widgets_cfg["spotify_visualizer"] = {
        "mode": "sine_wave",
    }
    settings_manager.set("widgets", widgets_cfg)

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        assert tab._sine_preset_slider.preset_index() == 0
        assert tab._blob_preset_slider.preset_index() == 0
        assert tab._bubble_preset_slider.preset_index() == 0
    finally:
        tab.deleteLater()


def test_visualizer_mode_roundtrip_uses_shared_binding_contract(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("bubble"))
        qt_app.processEvents()
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("mode") == "bubble"
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        reloaded._load_settings()
        assert reloaded.vis_mode_combo.currentData() == "bubble"
    finally:
        reloaded.deleteLater()


def test_visualizer_unknown_saved_mode_falls_back_to_registry_default(qt_app, settings_manager):
    widgets_cfg = settings_manager.get("widgets", {}) or {}
    widgets_cfg["spotify_visualizer"] = {
        "mode": "not_a_real_mode",
    }
    settings_manager.set("widgets", widgets_cfg)

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        assert tab.vis_mode_combo.currentData() == get_default_visualizer_mode_id()
    finally:
        tab.deleteLater()


def test_visualizer_block_size_roundtrip_preserves_non_auto_values(qt_app, settings_manager):
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()

        sine_controls = get_per_mode_controls_for_mode(tab, "sine_wave")
        osc_controls = get_per_mode_controls_for_mode(tab, "oscilloscope")
        assert sine_controls is not None
        assert osc_controls is not None

        sine_combo = sine_controls["block_size"]
        osc_combo = osc_controls["block_size"]

        sine_combo.setCurrentIndex(sine_combo.findData(128))
        osc_combo.setCurrentIndex(osc_combo.findData(512))
        qt_app.processEvents()
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("sine_wave_audio_block_size") == 128
        assert saved.get("oscilloscope_audio_block_size") == 512
    finally:
        tab.deleteLater()

    reloaded = WidgetsTab(settings_manager)
    try:
        reloaded._load_settings()
        sine_controls = get_per_mode_controls_for_mode(reloaded, "sine_wave")
        osc_controls = get_per_mode_controls_for_mode(reloaded, "oscilloscope")
        assert sine_controls is not None
        assert osc_controls is not None
        assert sine_controls["block_size"].currentData() == 128
        assert osc_controls["block_size"].currentData() == 512
    finally:
        reloaded.deleteLater()


def test_blob_normal_edit_switches_curated_preset_to_custom(qt_app, settings_manager):
    """Blob normal-layout controls should keep their explicit Custom handoff."""

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData("blob"))
        slider = getattr(tab, "_blob_preset_slider", None)
        assert slider is not None

        slider.set_preset_index(0)
        widgets_cfg = tab._settings.get('widgets', {}) or {}
        spotify_vis = widgets_cfg.setdefault('spotify_visualizer', {})
        spotify_vis['preset_blob'] = 0
        tab._settings.set('widgets', widgets_cfg)
        tab._settings.save()

        tab.blob_pulse.setValue(min(tab.blob_pulse.maximum(), tab.blob_pulse.value() + 5))
        qt_app.processEvents()
        tab._save_settings_now()

        assert slider.preset_index() == slider.custom_index()
        saved = tab._settings.get('widgets', {}).get('spotify_visualizer', {})
        assert saved.get('preset_blob') == slider.custom_index()
    finally:
        tab.deleteLater()

def test_visualizer_custom_preset_roundtrip(qt_app, settings_manager):
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

def test_spectrum_custom_roundtrip_preserves_broad_state(qt_app, settings_manager):
    """Spectrum Custom should restore broad advanced + technical state without curated bleed."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        mode = "spectrum"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = tab._spectrum_preset_slider
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_spectrum": custom_index,
            "spectrum_growth": 3.1,
            "spectrum_single_piece": False,
            "spectrum_border_radius": 1.0,
            "spectrum_glow_enabled": False,
            "spectrum_glow_intensity": 0.55,
            "spectrum_glow_color": [110, 220, 255, 235],
            "spectrum_mirrored": True,
            "spectrum_bar_count": 33,
            "spectrum_sensitivity": 0.50,
            "spectrum_manual_floor": 0.12,
            "spectrum_agc_strength": 0.50,
            "spectrum_kick_lane_gain": 1.0,
            "spectrum_lane_transient_mix": 0.65,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        tab._spotify_vis_fill_color = QColor(12, 122, 210, 211)
        tab._spotify_vis_border_color = QColor(220, 180, 80, 255)
        tab.vis_border_opacity.setValue(73)
        tab.vis_ghost_enabled.setChecked(False)
        tab.vis_ghost_opacity_slider.setValue(33)
        tab.vis_ghost_decay_slider.setValue(71)
        tab.spectrum_growth.setValue(370)
        tab.spectrum_single_piece.setChecked(True)
        tab.spectrum_rainbow_per_bar.setChecked(True)
        tab.spectrum_border_radius.setValue(7)
        tab.spectrum_glow_enabled.setChecked(True)
        tab.spectrum_glow_intensity.setValue(94)
        tab._spectrum_glow_color = QColor(15, 230, 255, 210)
        tab.spectrum_mirrored.setChecked(False)
        tab.spectrum_bass_emphasis.setValue(81)
        tab.spectrum_vocal_position.setValue(57)
        tab.spectrum_mid_suppression.setValue(22)
        tab.spectrum_wave_amplitude.setValue(93)
        tab.spectrum_profile_floor.setValue(17)
        tab.spectrum_drop_speed.setValue(241)
        if hasattr(tab, "spectrum_shape_editor"):
            tab.spectrum_shape_editor.set_nodes([[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]])

        controls = get_per_mode_controls_for_mode(tab, mode)
        assert controls is not None
        controls["bar_count"].setValue(44)
        controls["sensitivity_slider"].setValue(77)
        controls["manual_floor"].setValue(26)
        controls["agc_strength_slider"].setValue(61)
        controls["kick_gain_slider"].setValue(155)
        controls["mix_slider"].setValue(88)

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        snapshot = cache[mode]
        assert snapshot["bar_fill_color"] == [12, 122, 210, 211]
        assert snapshot["bar_border_color"] == [220, 180, 80, 255]
        assert snapshot["spectrum_growth"] == pytest.approx(3.7)
        assert snapshot["spectrum_single_piece"] is True
        assert snapshot["spectrum_border_radius"] == pytest.approx(7.0)
        assert snapshot["spectrum_glow_enabled"] is True
        assert snapshot["spectrum_glow_intensity"] == pytest.approx(0.94)
        assert snapshot["spectrum_glow_color"] == [15, 230, 255, 210]
        assert snapshot["spectrum_mirrored"] is False
        assert snapshot["spectrum_shape_nodes"] == [[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]]
        assert snapshot["spectrum_bar_count"] == 44
        assert snapshot["spectrum_sensitivity"] == pytest.approx(0.77)
        assert snapshot["spectrum_manual_floor"] == pytest.approx(0.26)
        assert snapshot["spectrum_agc_strength"] == pytest.approx(0.61)
        assert snapshot["spectrum_kick_lane_gain"] == pytest.approx(1.55)
        assert snapshot["spectrum_lane_transient_mix"] == pytest.approx(0.88)

        slider.set_preset_index(custom_index)
        tab._on_visualizer_preset_changed(mode, custom_index)

        restored = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert restored.get("bar_fill_color") == [12, 122, 210, 211]
        assert restored.get("bar_border_color") == [220, 180, 80, 255]
        assert restored.get("spectrum_growth") == pytest.approx(3.7)
        assert restored.get("spectrum_single_piece") is True
        assert restored.get("spectrum_border_radius") == pytest.approx(7.0)
        assert restored.get("spectrum_glow_enabled") is True
        assert restored.get("spectrum_glow_intensity") == pytest.approx(0.94)
        assert restored.get("spectrum_glow_color") == [15, 230, 255, 210]
        assert restored.get("spectrum_mirrored") is False
        assert restored.get("spectrum_shape_nodes") == [[0.0, 0.10], [0.4, 0.85], [1.0, 0.65]]
        assert restored.get("spectrum_bar_count") == 44
        assert restored.get("spectrum_sensitivity") == pytest.approx(0.77)
        assert restored.get("spectrum_manual_floor") == pytest.approx(0.26)
        assert restored.get("spectrum_agc_strength") == pytest.approx(0.61)
        assert restored.get("spectrum_kick_lane_gain") == pytest.approx(1.55)
        assert restored.get("spectrum_lane_transient_mix") == pytest.approx(0.88)
    finally:
        tab.deleteLater()

def test_bubble_custom_snapshot_uses_live_ui_state_for_colors(qt_app, settings_manager):
    """Leaving Bubble custom snapshots current swatches even before an explicit save."""

    def _rgba_tuple(color: QColor) -> tuple[int, int, int, int]:
        return color.red(), color.green(), color.blue(), color.alpha()

    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_gradient_light": [20, 30, 40, 255],
            "bubble_stream_reactivity": 0.2,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        live_color = QColor(171, 122, 77, 240)
        tab._bubble_gradient_light = live_color

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        assert cache[mode]["bubble_gradient_light"] == list(_rgba_tuple(live_color))
    finally:
        tab.deleteLater()

def test_bubble_custom_snapshot_uses_live_ui_state_for_reactive_speed(qt_app, settings_manager):
    """Leaving Bubble custom snapshots the current reactive-speed slider value."""

    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        tab.vis_mode_combo.setCurrentIndex(tab.vis_mode_combo.findData(mode))
        slider = getattr(tab, "_bubble_preset_slider", None)
        assert slider is not None
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": custom_index,
            "bubble_stream_reactivity": 0.15,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        tab._save_settings = tab._save_settings_now

        tab.bubble_stream_reactivity.setValue(95)

        slider.set_preset_index(0)
        tab._on_visualizer_preset_changed(mode, 0)

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert isinstance(cache, dict)
        assert cache[mode]["bubble_stream_reactivity"] == pytest.approx(0.95)
    finally:
        tab.deleteLater()

def test_bubble_stream_reactivity_load_clamps_to_200(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis["bubble_stream_reactivity"] = 2.75
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_stream_reactivity.maximum() == 200
        assert tab.bubble_stream_reactivity.value() == 200
        assert tab.bubble_stream_reactivity_label.text() == "200%"
    finally:
        tab.deleteLater()


def test_bubble_legacy_gradient_direction_loads_as_canonical_label_and_saves_version(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.pop("bubble_gradient_semantics_version", None)
        spotify_vis.update({
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_gradient_direction": "left",
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_gradient_direction.currentData() == "right"

        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("bubble_gradient_direction") == "right"
        assert saved.get("bubble_gradient_semantics_version") == 2
    finally:
        tab.deleteLater()


def test_bubble_center_out_reverse_round_trips_through_widgets_tab(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": "bubble",
            "preset_bubble": custom_index,
            "bubble_gradient_direction": "center_out_reverse",
            "bubble_gradient_semantics_version": 2,
        })
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.bubble_gradient_direction.currentData() == "center_out_reverse"

        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("bubble_gradient_direction") == "center_out_reverse"
        assert saved.get("bubble_gradient_semantics_version") == 2
    finally:
        tab.deleteLater()


def test_blob_pulse_controls_load_and_roundtrip(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis["blob_pulse_cap"] = 0.42
        spotify_vis["blob_pulse_release_ms"] = 480
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()

        assert tab.blob_pulse_cap.value() == 42
        assert tab.blob_pulse_cap_label.text() == "42%"
        assert tab.blob_pulse_release_ms.value() == 480
        assert tab.blob_pulse_release_ms_label.text() == "0.48s"

        tab.blob_pulse_cap.setValue(65)
        tab.blob_pulse_release_ms.setValue(260)
        tab._save_settings_now()

        saved = settings_manager.get("widgets", {}).get("spotify_visualizer", {})
        assert saved.get("blob_pulse_cap") == pytest.approx(0.65)
        assert saved.get("blob_pulse_release_ms") == 260
    finally:
        tab.deleteLater()

def test_move_to_custom_preserves_current_visualizer_colors(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        tab._save_settings = tab._save_settings_now
        mode = "bubble"
        slider = tab._bubble_preset_slider
        custom_index = slider.custom_index()

        widgets_cfg = settings_manager.get("widgets", {}) or {}
        spotify_vis = widgets_cfg.setdefault("spotify_visualizer", {})
        spotify_vis.update({
            "mode": mode,
            "preset_bubble": 0,
            "bubble_gradient_light": [10, 20, 30, 255],
            "bubble_gradient_dark": [40, 50, 60, 255],
            "bubble_outline_color": [70, 80, 90, 255],
        })
        settings_manager.set("widgets", widgets_cfg)
        settings_manager.set("visualizer_custom_presets", {
            mode: {
                "mode": mode,
                "bubble_gradient_light": [200, 1, 2, 255],
                "bubble_gradient_dark": [201, 3, 4, 255],
                "bubble_outline_color": [202, 5, 6, 255],
            }
        })

        tab._load_settings()

        assert [tab._bubble_gradient_light.red(), tab._bubble_gradient_light.green(), tab._bubble_gradient_light.blue()] == [10, 20, 30]

        slider.set_preset_index(0)
        slider._move_to_custom()

        cache = settings_manager.get("visualizer_custom_presets", {})
        assert cache[mode]["bubble_gradient_light"] == [10, 20, 30, 255]
        assert cache[mode]["bubble_gradient_dark"] == [40, 50, 60, 255]
        assert cache[mode]["bubble_outline_color"] == [70, 80, 90, 255]
        assert [tab._bubble_gradient_light.red(), tab._bubble_gradient_light.green(), tab._bubble_gradient_light.blue()] == [10, 20, 30]
    finally:
        tab.deleteLater()


def test_build_visualizer_preset_payload_normalizes_mode_snapshot(qt_app, settings_manager):
    tab = WidgetsTab(settings_manager)
    try:
        mode = "bubble"
        custom_index = tab._bubble_preset_slider.custom_index()
        widgets_cfg = settings_manager.get("widgets", {}) or {}
        widgets_cfg["spotify_visualizer"] = {
            "mode": mode,
            "preset_bubble": custom_index,
            "manual_floor": 0.28,
            "input_gain": 0.81,
            "bubble_growth": 3.4,
            "bubble_rainbow_enabled": True,
            "bubble_rainbow_speed": 0.62,
        }
        settings_manager.set("widgets", widgets_cfg)

        tab._load_settings()
        payload = tab.build_visualizer_preset_payload(mode)
        assert payload

        snapshot = payload["snapshot"]["widgets"]["spotify_visualizer"]
        assert snapshot["bubble_manual_floor"] == pytest.approx(0.28)
        assert snapshot["bubble_input_gain"] == pytest.approx(0.81)
        assert snapshot["bubble_growth"] == pytest.approx(3.4)
        assert snapshot["bubble_rainbow_enabled"] is True
        assert snapshot["bubble_rainbow_speed"] == pytest.approx(0.62)
        assert "manual_floor" not in snapshot
        assert "input_gain" not in snapshot
    finally:
        tab.deleteLater()

def test_spinbox_stylesheet_attached(qt_app, settings_manager):
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

def test_visualizers_toggle_gates_controls(qt_app, settings_manager):
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

def test_visualizer_technical_bucket_visibility_roundtrip(qt_app, settings_manager):
    """Technical subsection visibility toggles should persist per mode."""
    from ui.tabs.media.technical_controls import get_per_mode_controls_for_mode

    tab = WidgetsTab(settings_manager)
    try:
        tab._load_settings()
        controls = get_per_mode_controls_for_mode(tab, "spectrum")
        assert controls is not None

        agc_toggle = controls.get("agc_visibility_toggle")
        transient_toggle = controls.get("transient_visibility_toggle")
        assert agc_toggle is not None
        assert transient_toggle is not None

        agc_toggle.setChecked(True)
        transient_toggle.setChecked(False)
        qt_app.processEvents()

        assert tab.get_visualizer_tech_bucket_state("spectrum", "agc", False) is True
        assert tab.get_visualizer_tech_bucket_state("spectrum", "transient", True) is False

        tab.deleteLater()

        reloaded = WidgetsTab(settings_manager)
        try:
            reloaded._load_settings()
            reloaded_controls = get_per_mode_controls_for_mode(reloaded, "spectrum")
            assert reloaded_controls is not None
            reloaded_agc = reloaded_controls.get("agc_visibility_toggle")
            reloaded_transient = reloaded_controls.get("transient_visibility_toggle")
            assert reloaded_agc is not None
            assert reloaded_transient is not None
            assert reloaded_agc.isChecked() is True
            assert reloaded_transient.isChecked() is False
        finally:
            reloaded.deleteLater()
    finally:
        pass
