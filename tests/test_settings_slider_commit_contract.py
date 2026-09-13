"""Static guard for release-time Settings slider persistence."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _function_block(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}")
    end = source.index(f"    def {next_name}", start)
    return source[start:end]


def test_shared_slider_exposes_event_driven_release_commit_without_timer() -> None:
    source = _source("ui/tabs/shared_styles.py")
    block = source[source.index("class NoWheelSlider"):source.index("class RecommendedMarkSlider")]
    assert "valueCommitted = Signal(int)" in block
    assert "sliderPressed.connect(self._begin_commit_drag)" in block
    assert "sliderReleased.connect(self._finish_commit_drag)" in block
    assert "self.valueChanged.connect(self._observe_commit_value)" in block
    assert "self.valueCommitted.emit" in block
    assert "Timer" not in block
    assert "single_shot" not in block


def test_accessibility_sliders_keep_live_labels_but_save_only_on_commit() -> None:
    source = _source("ui/tabs/accessibility_tab.py")
    assert "dimming_opacity_slider.valueChanged.connect(self._on_dimming_opacity_changed)" in source
    assert "dimming_opacity_slider.valueCommitted.connect(self._commit_dimming_opacity)" in source
    assert "pixel_shift_rate_slider.valueChanged.connect(self._on_pixel_shift_rate_changed)" in source
    assert "pixel_shift_rate_slider.valueCommitted.connect(self._commit_pixel_shift_rate)" in source
    dimming = _function_block(source, "_on_dimming_opacity_changed", "_commit_dimming_opacity")
    shift = _function_block(source, "_on_pixel_shift_rate_changed", "_commit_pixel_shift_rate")
    assert "_settings.set" not in dimming
    assert "_settings.set" not in shift
    assert '"accessibility.dimming.opacity"' in _function_block(source, "_commit_dimming_opacity", "_on_pixel_shift_enabled_changed")
    assert '"accessibility.pixel_shift.rate"' in _function_block(source, "_commit_pixel_shift_rate", "_update_dimming_controls_state")


def test_other_immediate_settings_sliders_use_commit_boundary() -> None:
    display = _source("ui/tabs/display_tab.py")
    assert "widget_glow_intensity_slider.valueCommitted.connect(self._save_settings)" in display
    assert "widget_glow_distance_slider.valueCommitted.connect(self._save_settings)" in display
    assert "widget_glow_intensity_slider.valueChanged.connect(self._save_settings)" not in display
    assert "widget_glow_distance_slider.valueChanged.connect(self._save_settings)" not in display

    sources = _source("ui/tabs/sources_tab.py")
    assert "ratio_slider.valueCommitted.connect(self._save_ratio)" in sources
    ratio = _function_block(sources, "_on_ratio_slider_changed", "_save_ratio")
    assert "_save_ratio(" not in ratio

    transitions = _source("ui/tabs/transitions_tab.py")
    slider_names = (
        "duration_slider",
        "blinds_feather_slider",
        "burn_jaggedness_slider",
        "burn_glow_intensity_slider",
        "burn_char_width_slider",
        "burn_smoke_density_slider",
        "burn_ash_density_slider",
    )
    for name in slider_names:
        assert f"{name}.valueCommitted.connect(self._save_settings)" in transitions
        assert f"{name}.valueChanged.connect(self._save_settings)" not in transitions
    duration = transitions[transitions.index("    def _on_duration_changed"):]
    assert "_save_settings()" not in duration
