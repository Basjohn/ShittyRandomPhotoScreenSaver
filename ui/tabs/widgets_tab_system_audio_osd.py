"""Lazy Widgets-tab settings for the independently enabled system-audio OSD.

Only canonical widgets.system_audio_osd is persisted here. Construction never
subscribes to audio, creates a source, or instantiates a retained Quick item.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QSpinBox, QVBoxLayout, QWidget
from PySide6.QtGui import QFont

from rendering.widget_descriptors import get_widget_position_option_labels
from ui.tabs.shared_styles import add_aligned_row, style_group_box
from ui.widgets import StyledComboBox, StyledFontComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


_TEXT_CHOICES = (
    ("Left of Bar", "left_of_bar"),
    ("Inside Bar", "inside_bar"),
    ("Right of Bar", "right_of_bar"),
    ("No Text", "none"),
    ("Numbers Only", "numbers_only"),
)


def _selected_text_position(combo: StyledComboBox) -> str:
    data = combo.currentData()
    return str(data) if data in {value for _, value in _TEXT_CHOICES} else "right_of_bar"


def _choose_text_position(combo: StyledComboBox, value: object) -> None:
    index = combo.findData(str(value))
    combo.setCurrentIndex(index if index >= 0 else combo.findData("right_of_bar"))


def _set_controls_visible(tab: "WidgetsTab") -> None:
    area = getattr(tab, "_system_audio_osd_controls", None)
    if area is not None:
        area.setVisible(bool(tab.system_audio_osd_enabled.isChecked()))


def build_system_audio_osd_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    group = QGroupBox("System Volume / Mute OSD")
    style_group_box(group)
    root = QVBoxLayout(group)
    root.setContentsMargins(16, 18, 16, 16)
    root.setSpacing(12)

    tab.system_audio_osd_enabled = QCheckBox("Enable System Volume OSD")
    tab.system_audio_osd_enabled.setProperty("circleIndicator", True)
    tab.system_audio_osd_enabled.setChecked(tab._default_bool("system_audio_osd", "enabled"))
    tab.system_audio_osd_enabled.setToolTip(
        "Show master-volume and mute changes from the shared Windows audio source. "
        "Independent of Media; no OSD polling."
    )
    tab.system_audio_osd_enabled.stateChanged.connect(tab._save_settings)
    root.addWidget(tab.system_audio_osd_enabled)

    tab._system_audio_osd_controls = QWidget()
    controls = QVBoxLayout(tab._system_audio_osd_controls)
    controls.setContentsMargins(0, 0, 0, 6)
    controls.setSpacing(10)

    def row(label: str) -> QHBoxLayout:
        line, _ = add_aligned_row(controls, label, label_width=150)
        return line

    position_row = row("Position:")
    tab.system_audio_osd_position = StyledComboBox()
    tab.system_audio_osd_position.addItems(
        list(get_widget_position_option_labels("system_audio_osd"))
    )
    tab._set_combo_text(
        tab.system_audio_osd_position, tab._default_str("system_audio_osd", "position")
    )
    tab.system_audio_osd_position.currentTextChanged.connect(tab._save_settings)
    position_row.addWidget(tab.system_audio_osd_position)
    position_row.addStretch()

    monitor_row = row("Display:")
    tab.system_audio_osd_monitor_combo = StyledComboBox(size_variant="compact")
    tab.system_audio_osd_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab._set_combo_text(
        tab.system_audio_osd_monitor_combo,
        str(tab._widget_default("system_audio_osd", "monitor")),
    )
    tab.system_audio_osd_monitor_combo.currentTextChanged.connect(tab._save_settings)
    monitor_row.addWidget(tab.system_audio_osd_monitor_combo)
    monitor_row.addStretch()

    delay_row = row("Hide After:")
    tab.system_audio_osd_inactivity_ms = QSpinBox()
    tab.system_audio_osd_inactivity_ms.setRange(500, 12000)
    tab.system_audio_osd_inactivity_ms.setSingleStep(100)
    tab.system_audio_osd_inactivity_ms.setSuffix(" ms")
    tab.system_audio_osd_inactivity_ms.setValue(tab._default_int("system_audio_osd", "inactivity_ms"))
    tab.system_audio_osd_inactivity_ms.valueChanged.connect(tab._save_settings)
    delay_row.addWidget(tab.system_audio_osd_inactivity_ms)
    delay_row.addStretch()

    text_row = row("Text:")
    tab.system_audio_osd_text_position = StyledComboBox()
    for label, value in _TEXT_CHOICES:
        tab.system_audio_osd_text_position.addItem(label, value)
    _choose_text_position(
        tab.system_audio_osd_text_position,
        tab._default_str("system_audio_osd", "text_position"),
    )
    tab.system_audio_osd_text_position.currentIndexChanged.connect(tab._save_settings)
    text_row.addWidget(tab.system_audio_osd_text_position)
    text_row.addStretch()

    font_row = row("Font:")
    tab.system_audio_osd_font_family = StyledFontComboBox(size_variant="hero")
    tab.system_audio_osd_font_family.setCurrentFont(
        QFont(tab._default_str("system_audio_osd", "font_family"))
    )
    tab.system_audio_osd_font_family.currentFontChanged.connect(tab._save_settings)
    font_row.addWidget(tab.system_audio_osd_font_family)
    font_row.addStretch()

    for key_name, label, minimum, maximum, step in (
        ("font_size", "Text Size:", 11, 56, 1),
        ("bar_thickness", "Bar Height:", 3, 32, 1),
        ("preferred_width", "Width:", 180, 900, 10),
        ("preferred_height", "Height:", 48, 220, 4),
    ):
        line = row(label)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSingleStep(step)
        spin.setValue(tab._default_int("system_audio_osd", key_name))
        spin.valueChanged.connect(tab._save_settings)
        setattr(tab, f"system_audio_osd_{key_name}", spin)
        line.addWidget(spin)
        line.addStretch()

    root.addWidget(tab._system_audio_osd_controls)
    tab.system_audio_osd_enabled.stateChanged.connect(lambda *_: _set_controls_visible(tab))
    _set_controls_visible(tab)

    container = QWidget()
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 20, 0, 0)
    outer.addWidget(group)
    return container


def load_system_audio_osd_settings(tab: "WidgetsTab", widgets: Mapping[str, Any]) -> None:
    values = widgets.get("system_audio_osd", {})
    if not isinstance(values, Mapping):
        values = {}
    tab.system_audio_osd_enabled.setChecked(tab._config_bool("system_audio_osd", values, "enabled"))
    tab._set_combo_text(tab.system_audio_osd_position,
                        tab._config_str("system_audio_osd", values, "position"))
    tab._set_combo_text(tab.system_audio_osd_monitor_combo,
                        str(values.get("monitor", tab._widget_default("system_audio_osd", "monitor"))))
    tab.system_audio_osd_inactivity_ms.setValue(
        tab._config_int("system_audio_osd", values, "inactivity_ms"))
    _choose_text_position(tab.system_audio_osd_text_position,
                          values.get("text_position", tab._widget_default("system_audio_osd", "text_position")))
    tab.system_audio_osd_font_family.setCurrentFont(
        QFont(tab._config_str("system_audio_osd", values, "font_family"))
    )
    for key_name in ("font_size", "bar_thickness", "preferred_width", "preferred_height"):
        getattr(tab, f"system_audio_osd_{key_name}").setValue(
            tab._config_int("system_audio_osd", values, key_name)
        )
    _set_controls_visible(tab)


def save_system_audio_osd_settings(tab: "WidgetsTab") -> dict[str, Any]:
    defaults = tab._widget_defaults.get("system_audio_osd")
    if not isinstance(defaults, Mapping):
        raise KeyError("Canonical widgets.system_audio_osd defaults are missing")
    result = dict(defaults)
    result.update({
        "enabled": bool(tab.system_audio_osd_enabled.isChecked()),
        "position": tab.system_audio_osd_position.currentText(),
        "monitor": tab._monitor_value_from_combo("system_audio_osd", tab.system_audio_osd_monitor_combo),
        "inactivity_ms": int(tab.system_audio_osd_inactivity_ms.value()),
        "text_position": _selected_text_position(tab.system_audio_osd_text_position),
        "font_family": tab.system_audio_osd_font_family.currentFont().family(),
        "font_size": int(tab.system_audio_osd_font_size.value()),
        "bar_thickness": int(tab.system_audio_osd_bar_thickness.value()),
        "preferred_width": int(tab.system_audio_osd_preferred_width.value()),
        "preferred_height": int(tab.system_audio_osd_preferred_height.value()),
    })
    return result
