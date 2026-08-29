"""Sine Line 4 settings binding against the current mode contract.

Line 4 colour/glow are attribute-backed; horizontal phase shift is owned by the
``sine_line4_shift`` control and persisted as normalized cycles (slider 25 ->
0.25).  This replaces the retired ``_sine_line4_horizontal_shift`` fixture.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
import pytest

from ui.tabs.media.sine_wave_settings_binding import (
    collect_sine_wave_mode_settings,
    load_sine_wave_mode_settings,
)


class _Slider:
    def __init__(self, value=0):
        self._value = int(value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._value = int(value)


class _Label:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = str(value)


class _CollectTab:
    def __init__(self):
        self._sine_line4_color = QColor(0, 255, 255, 230)
        self._sine_line4_glow_color = QColor(0, 255, 255, 180)
        self.sine_line4_shift = _Slider(25)


class _LoadTab:
    def __init__(self):
        self.sine_line4_shift = _Slider()
        self.sine_line4_shift_label = _Label()

    def _config_float(self, _section, config, key, default):
        return float(config.get(key, default))

    def _config_bool(self, _section, config, key, default):
        return bool(config.get(key, default))

    def _default_float(self, _section, _key, default):
        return float(default)


def test_line4_collects_current_colors_and_normalized_shift():
    collected = collect_sine_wave_mode_settings(_CollectTab())

    assert collected["sine_line4_color"] == [0, 255, 255, 230]
    assert collected["sine_line4_glow_color"] == [0, 255, 255, 180]
    assert collected["sine_line4_shift"] == pytest.approx(0.25)


def test_line4_load_restores_colors_shift_and_requests_swatch_sync():
    tab = _LoadTab()
    synced = []
    visibility = []

    load_sine_wave_mode_settings(
        tab,
        {
            "sine_line4_color": [11, 22, 33, 230],
            "sine_line4_glow_color": [44, 55, 66, 180],
            "sine_line4_shift": 0.37,
        },
        sync_color_button=lambda button_attr, color_attr: synced.append(
            (button_attr, color_attr)
        ),
        update_multi_line_visibility=lambda host: visibility.append(host),
    )

    assert tab._sine_line4_color.getRgb() == (11, 22, 33, 230)
    assert tab._sine_line4_glow_color.getRgb() == (44, 55, 66, 180)
    assert tab.sine_line4_shift.value() == 37
    assert tab.sine_line4_shift_label.text == "0.37 cycles"
    assert ("sine_line4_color_btn", "_sine_line4_color") in synced
    assert ("sine_line4_glow_btn", "_sine_line4_glow_color") in synced
    assert visibility == [tab]
