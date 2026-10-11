"""Persistence binding for the lazy Sine Waves Settings body: its spec's controls, plus the extra
lines' section (``sine_wave_builder.build_lines_section``)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtGui import QColor

from core.settings.visualizer_mode_settings import Colour
from ui.color_utils import qcolor_to_list
from ui.tabs.media.sine_wave_builder import LINES, shift_text, update_line_visibility
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_sine_wave_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "sine_wave", config)


def collect_sine_wave_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "sine_wave")


def _value(tab, config: Mapping[str, Any], key: str):
    return config.get(key, tab._widget_default("spotify_visualizer", key))


def _number(tab, config: Mapping[str, Any], key: str, cast):
    try:
        return cast(_value(tab, config, key))
    except (TypeError, ValueError):
        return cast(tab._widget_default("spotify_visualizer", key))


def load_lines_section(tab, config) -> None:
    """Show ``config``'s extra lines (canonical defaults for missing values) without saving."""
    config = config if isinstance(config, Mapping) else {}
    count = _number(tab, config, "sine_line_count", int)
    widgets = [tab.sine_multi_line, tab.sine_line_count_slider]
    for line in LINES:
        widgets += [getattr(tab, f"sine_travel_line{line}"), getattr(tab, f"sine_ghost_line{line}_enabled"),
                    getattr(tab, f"sine_line{line}_shift")]
    for widget in widgets:
        widget.blockSignals(True)
    try:
        tab.sine_multi_line.setChecked(count > 1)
        tab.sine_line_count_slider.setValue(max(2, min(6, count)))
        tab.sine_line_count_label.setText(str(tab.sine_line_count_slider.value()))
        for line in LINES:
            for kind, button in (("color", "color"), ("glow_color", "glow")):
                key = f"sine_line{line}_{kind}"
                default = tab._widget_default("spotify_visualizer", key)
                # Admitted as every spec colour is: a malformed value shows the canonical default.
                colour = QColor(*Colour(key, "", "").admit(_value(tab, config, key), default))
                setattr(tab, f"_{key}", colour)
                getattr(tab, f"sine_line{line}_{button}_btn").set_color(colour)
            getattr(tab, f"sine_travel_line{line}").setCurrentIndex(
                max(0, min(2, _number(tab, config, f"sine_travel_line{line}", int))))
            getattr(tab, f"sine_ghost_line{line}_enabled").setChecked(
                bool(_value(tab, config, f"sine_ghost_line{line}_enabled")))
            shift = getattr(tab, f"sine_line{line}_shift")
            shift.setValue(max(-100, min(100, round(_number(tab, config, f"sine_line{line}_shift", float) * 100))))
            getattr(tab, f"sine_line{line}_shift_label").setText(shift_text(shift.value()))
    finally:
        for widget in widgets:
            widget.blockSignals(False)
    update_line_visibility(tab)


def collect_lines_section(tab) -> dict[str, Any]:
    values: dict[str, Any] = {
        "sine_line_count": tab.sine_line_count_slider.value() if tab.sine_multi_line.isChecked() else 1,
    }
    for line in LINES:
        for kind in ("color", "glow_color"):
            key = f"sine_line{line}_{kind}"
            values[key] = qcolor_to_list(getattr(tab, f"_{key}", None), tab._widget_default("spotify_visualizer", key))
        values[f"sine_travel_line{line}"] = getattr(tab, f"sine_travel_line{line}").currentIndex()
        values[f"sine_ghost_line{line}_enabled"] = getattr(tab, f"sine_ghost_line{line}_enabled").isChecked()
        values[f"sine_line{line}_shift"] = getattr(tab, f"sine_line{line}_shift").value() / 100.0
    return values
