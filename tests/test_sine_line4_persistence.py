"""Sine Line 4 settings binding against the current mode contract.

Line 4 colour/glow are attribute-backed; horizontal phase shift is owned by the
``sine_line4_shift`` control and persisted as normalized cycles (slider 25 ->
0.25).  This replaces the retired ``_sine_line4_horizontal_shift`` fixture.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
import pytest

from ui.tabs.media.sine_wave_settings_binding import (
    collect_lines_section,
    load_lines_section,
)
from ui.tabs.media.sine_wave_builder import shift_text


class _Slider:
    def __init__(self, value=0):
        self._value = int(value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = int(value)

    def blockSignals(self, _blocked):
        return None


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)


class _Check:
    def __init__(self, checked=False):
        self._checked = bool(checked)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        self._checked = bool(checked)

    def blockSignals(self, _blocked):
        return None


class _Combo:
    def __init__(self, index=0):
        self._index = int(index)

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, index):
        self._index = int(index)

    def blockSignals(self, _blocked):
        return None


class _Swatch:
    def __init__(self):
        self.color = None

    def set_color(self, color):
        self.color = color


def _canonical_widget_default(section, key):
    from core.settings.default_contract import require_canonical_default
    return require_canonical_default(f"widgets.{section}.{key}")


class _CanonicalDefaultsMixin:
    """Mirror the production settings-binding canonical default helpers."""

    def _widget_default(self, section, key):
        return _canonical_widget_default(section, key)

    def _default_int(self, section, key):
        return int(self._widget_default(section, key))

    def _default_float(self, section, key):
        return float(self._widget_default(section, key))

    def _default_bool(self, section, key):
        return bool(self._widget_default(section, key))

    def _config_bool(self, section, config, key):
        default = self._default_bool(section, key)
        raw = config.get(key, default) if isinstance(config, dict) else default
        return bool(raw)

    def _config_float(self, section, config, key):
        default = self._default_float(section, key)
        raw = config.get(key, default) if isinstance(config, dict) else default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default


class _LinesTab(_CanonicalDefaultsMixin):
    def __init__(self):
        default_count = int(self._widget_default("spotify_visualizer", "sine_line_count"))
        self.sine_multi_line = _Check(default_count > 1)
        self.sine_line_count_slider = _Slider(max(2, min(6, default_count)))
        self.sine_line_count_label = _Label()
        for line in range(2, 7):
            for kind in ("color", "glow_color"):
                key = f"sine_line{line}_{kind}"
                setattr(self, f"_{key}", QColor(*self._widget_default("spotify_visualizer", key)))
                button_name = "glow" if kind == "glow_color" else "color"
                setattr(self, f"sine_line{line}_{button_name}_btn", _Swatch())
            travel_key = f"sine_travel_line{line}"
            self_value = int(self._widget_default("spotify_visualizer", travel_key))
            setattr(self, travel_key, _Combo(self_value))
            ghost_key = f"sine_ghost_line{line}_enabled"
            setattr(self, ghost_key, _Check(self._widget_default("spotify_visualizer", ghost_key)))
            shift_key = f"sine_line{line}_shift"
            shift = float(self._widget_default("spotify_visualizer", shift_key))
            setattr(self, shift_key, _Slider(round(shift * 100)))
            setattr(self, f"{shift_key}_label", _Label())


class _CollectTab(_LinesTab):
    def __init__(self):
        super().__init__()
        self._sine_line4_color = QColor(0, 255, 255, 230)
        self._sine_line4_glow_color = QColor(0, 255, 255, 180)
        self.sine_line4_shift = _Slider(25)


class _LoadTab(_LinesTab):
    def __init__(self):
        super().__init__()


def test_line4_collects_current_colors_and_normalized_shift():
    collected = collect_lines_section(_CollectTab())

    assert collected["sine_line4_color"] == [0, 255, 255, 230]
    assert collected["sine_line4_glow_color"] == [0, 255, 255, 180]
    assert collected["sine_line4_shift"] == pytest.approx(0.25)


def test_malformed_line_colour_loads_the_canonical_default():
    tab = _LoadTab()
    load_lines_section(tab, {"sine_line4_color": ["red", 0, 0, 255]})
    default = tab._widget_default("spotify_visualizer", "sine_line4_color")
    assert list(tab._sine_line4_color.getRgb()) == [int(c) for c in default] + [255] * (4 - len(default))


def test_line4_load_restores_colors_and_shift_for_collection():
    tab = _LoadTab()

    load_lines_section(
        tab,
        {
            "sine_line4_color": [11, 22, 33, 230],
            "sine_line4_glow_color": [44, 55, 66, 180],
            "sine_line4_shift": 0.37,
        },
    )

    assert tab._sine_line4_color.getRgb() == (11, 22, 33, 230)
    assert tab._sine_line4_glow_color.getRgb() == (44, 55, 66, 180)
    assert tab.sine_line4_color_btn.color.getRgb() == (11, 22, 33, 230)
    assert tab.sine_line4_glow_btn.color.getRgb() == (44, 55, 66, 180)
    assert tab.sine_line4_shift.value() == 37
    assert tab.sine_line4_shift_label.text == shift_text(tab.sine_line4_shift.value())

    collected = collect_lines_section(tab)
    assert collected["sine_line4_color"] == [11, 22, 33, 230]
    assert collected["sine_line4_glow_color"] == [44, 55, 66, 180]
    assert collected["sine_line4_shift"] == pytest.approx(0.37)
