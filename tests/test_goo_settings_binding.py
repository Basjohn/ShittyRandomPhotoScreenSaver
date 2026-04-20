from __future__ import annotations

from PySide6.QtGui import QColor

from ui.tabs.media.goo_settings_binding import (
    collect_goo_mode_settings,
    load_goo_mode_settings,
)


class _Slider:
    def __init__(self) -> None:
        self._value = 0

    def setValue(self, value: int) -> None:
        self._value = int(value)

    def value(self) -> int:
        return int(self._value)


class _Label:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = str(text)


class _Check:
    def __init__(self) -> None:
        self._checked = False

    def setChecked(self, checked: bool) -> None:
        self._checked = bool(checked)

    def isChecked(self) -> bool:
        return bool(self._checked)


class _Tab:
    def __init__(self) -> None:
        self.goo_ghost_enabled = _Check()
        self.goo_ghost_opacity = _Slider()
        self.goo_ghost_opacity_label = _Label()
        self.goo_ghost_decay_slider = _Slider()
        self.goo_ghost_decay_label = _Label()
        self.goo_outline_width = _Slider()
        self.goo_outline_width_label = _Label()
        self.goo_shadow_strength = _Slider()
        self.goo_shadow_strength_label = _Label()
        self.goo_specular_density = _Slider()
        self.goo_specular_density_label = _Label()
        self.goo_void_floor = _Slider()
        self.goo_void_floor_label = _Label()
        self.goo_advance_speed = _Slider()
        self.goo_advance_speed_label = _Label()
        self.goo_retreat_speed = _Slider()
        self.goo_retreat_speed_label = _Label()
        self.goo_source_count = _Slider()
        self.goo_source_count_label = _Label()
        self.goo_growth = _Slider()
        self.goo_growth_label = _Label()
        self._goo_color = QColor(0, 140, 220, 230)
        self._goo_outline_color = QColor(255, 255, 255, 255)
        self._goo_shadow_color = QColor(0, 60, 110, 180)

    def _config_bool(self, _section, config, key, default):
        return bool(config.get(key, default))

    def _config_float(self, _section, config, key, default):
        return float(config.get(key, default))

    def _config_int(self, _section, config, key, default):
        return int(config.get(key, default))


def test_load_goo_mode_settings_populates_source_and_growth_controls():
    tab = _Tab()
    seen_sync = []
    load_goo_mode_settings(
        tab,
        {
            "goo_source_count": 48,
            "goo_growth": 4.2,
            "goo_advance_speed": 1.5,
        },
        sync_color_button=lambda btn, attr: seen_sync.append((btn, attr)),
    )

    assert tab.goo_source_count.value() == 48
    assert tab.goo_growth.value() == 420
    assert tab.goo_advance_speed.value() == 150
    assert ("goo_color_btn", "_goo_color") in seen_sync


def test_collect_goo_mode_settings_includes_unified_field_keys():
    tab = _Tab()
    tab.goo_source_count.setValue(48)
    tab.goo_growth.setValue(420)

    payload = collect_goo_mode_settings(tab)
    assert payload["goo_source_count"] == 48
    assert payload["goo_growth"] == 4.2
    assert "goo_gap_min" not in payload
    assert "goo_edge_pressure" not in payload
    assert "goo_core_pressure" not in payload

