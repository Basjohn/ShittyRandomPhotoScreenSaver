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
        self.goo_inward_outline_width = _Slider()
        self.goo_inward_outline_width_label = _Label()
        self.goo_shadow_strength = _Slider()
        self.goo_shadow_strength_label = _Label()
        self.goo_specular_density = _Slider()
        self.goo_specular_density_label = _Label()
        self.goo_core_size = _Slider()
        self.goo_core_size_label = _Label()
        self.goo_edge_inward_depth = _Slider()
        self.goo_edge_inward_depth_label = _Label()
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
            "goo_core_size": 0.24,
            "goo_edge_inward_depth": 0.26,
            "goo_inward_outline_width": 0.006,
        },
        sync_color_button=lambda btn, attr: seen_sync.append((btn, attr)),
    )

    assert tab.goo_core_size.value() == 24
    assert tab.goo_edge_inward_depth.value() == 26
    assert tab.goo_inward_outline_width.value() == 6
    assert ("goo_color_btn", "_goo_color") in seen_sync


def test_collect_goo_mode_settings_includes_unified_field_keys():
    tab = _Tab()
    tab.goo_core_size.setValue(24)
    tab.goo_edge_inward_depth.setValue(26)
    tab.goo_inward_outline_width.setValue(7)

    payload = collect_goo_mode_settings(tab)
    assert payload["goo_core_size"] == 0.24
    assert payload["goo_edge_inward_depth"] == 0.26
    assert payload["goo_inward_outline_width"] == 0.007
    assert "goo_gap_min" not in payload
    assert "goo_edge_pressure" not in payload
    assert "goo_core_pressure" not in payload
