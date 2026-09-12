"""Settings surface for the experimental retained System Stats card."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rendering.widget_descriptors import get_widget_position_option_labels
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    add_aligned_row,
    build_bucket_toggle,
    finalize_bucket_body,
    style_group_box,
)
from ui.widgets import StyledComboBox, StyledFontComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _set_controls_visible(tab: "WidgetsTab") -> None:
    controls = getattr(tab, "_system_stats_controls_container", None)
    enabled = getattr(tab, "system_stats_enabled", None)
    if controls is not None:
        controls.setVisible(bool(enabled and enabled.isChecked()))


def build_system_stats_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    """Build the small, intentionally knob-light System Stats section."""

    group = QGroupBox("System Stats")
    style_group_box(group)
    root = QVBoxLayout(group)
    root.setContentsMargins(16, 18, 16, 16)
    root.setSpacing(14)

    tab.system_stats_enabled = QCheckBox("Enable System Stats")
    tab.system_stats_enabled.setProperty("circleIndicator", True)
    tab.system_stats_enabled.setChecked(tab._default_bool("system_stats", "enabled"))
    tab.system_stats_enabled.setToolTip(
        "Show the retained whole-system CPU and memory card. Sampling exists only while a card is admitted."
    )
    tab.system_stats_enabled.stateChanged.connect(tab._save_settings)
    tab.system_stats_enabled.stateChanged.connect(tab._update_stack_status)
    root.addWidget(tab.system_stats_enabled)

    info = QLabel(
        "Experimental: one shared low-cost CPU/RAM sample every 10 seconds. GPU and VRAM are omitted from v1 because "
        "an honest low-cost system aggregate did not pass admission. No process list or diagnostic usage collector is used."
    )
    info.setWordWrap(True)
    root.addWidget(info)

    tab._system_stats_controls_container = QWidget()
    controls = QVBoxLayout(tab._system_stats_controls_container)
    controls.setContentsMargins(0, 0, 0, 8)
    controls.setSpacing(12)

    layout_toggle, layout_body, layout_controls = build_bucket_toggle(
        controls,
        "Layout & Typography",
        expanded=tab.get_widget_bucket_state("system_stats", "layout"),
        on_toggle=lambda checked: tab.set_widget_bucket_state(
            "system_stats", "layout", checked
        ),
        defer_initial_visibility=True,
    )

    def aligned_row(label: str) -> QHBoxLayout:
        row, _label = add_aligned_row(layout_controls, label, label_width=140)
        return row

    position_row = aligned_row("Position:")
    tab.system_stats_position = StyledComboBox()
    tab.system_stats_position.addItems(
        list(get_widget_position_option_labels("system_stats"))
    )
    tab._set_combo_text(
        tab.system_stats_position, tab._default_str("system_stats", "position")
    )
    tab.system_stats_position.setMinimumWidth(150)
    tab.system_stats_position.currentTextChanged.connect(tab._save_settings)
    tab.system_stats_position.currentTextChanged.connect(tab._update_stack_status)
    position_row.addWidget(tab.system_stats_position)
    tab.system_stats_stack_status = QLabel("")
    tab.system_stats_stack_status.setMinimumWidth(100)
    tab.system_stats_stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    position_row.addWidget(tab.system_stats_stack_status)
    position_row.addStretch()

    monitor_row = aligned_row("Display:")
    tab.system_stats_monitor_combo = StyledComboBox(size_variant="compact")
    tab.system_stats_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab._set_combo_text(
        tab.system_stats_monitor_combo,
        str(tab._widget_default("system_stats", "monitor")),
    )
    tab.system_stats_monitor_combo.setMinimumWidth(120)
    tab.system_stats_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.system_stats_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    monitor_row.addWidget(tab.system_stats_monitor_combo)
    monitor_row.addStretch()

    font_row = aligned_row("Font:")
    tab.system_stats_font_family = StyledFontComboBox(size_variant="hero")
    tab.system_stats_font_family.setCurrentFont(
        QFont(tab._default_str("system_stats", "font_family"))
    )
    tab.system_stats_font_family.setMinimumWidth(220)
    tab.system_stats_font_family.currentFontChanged.connect(tab._save_settings)
    font_row.addWidget(tab.system_stats_font_family)
    font_row.addStretch()

    font_size_row = aligned_row("Font Size:")
    tab.system_stats_font_size = QSpinBox()
    tab.system_stats_font_size.setRange(10, 72)
    tab.system_stats_font_size.setValue(tab._default_int("system_stats", "font_size"))
    tab.system_stats_font_size.valueChanged.connect(tab._save_settings)
    tab.system_stats_font_size.valueChanged.connect(tab._update_stack_status)
    font_size_row.addWidget(tab.system_stats_font_size)
    font_size_row.addWidget(QLabel("px"))
    font_size_row.addStretch()

    finalize_bucket_body(layout_toggle, layout_body)

    root.addWidget(tab._system_stats_controls_container)
    tab.system_stats_enabled.stateChanged.connect(lambda: _set_controls_visible(tab))
    _set_controls_visible(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(group)
    return container


def load_system_stats_settings(tab: "WidgetsTab", widgets: Mapping[str, Any]) -> None:
    values = widgets.get("system_stats", {})
    if not isinstance(values, Mapping):
        values = {}
    tab.system_stats_enabled.setChecked(
        tab._config_bool("system_stats", values, "enabled")
    )
    tab._set_combo_text(
        tab.system_stats_position,
        tab._config_str("system_stats", values, "position"),
    )
    tab._set_combo_text(
        tab.system_stats_monitor_combo,
        str(values.get("monitor", tab._widget_default("system_stats", "monitor"))),
    )
    tab.system_stats_font_family.setCurrentFont(
        QFont(tab._config_str("system_stats", values, "font_family"))
    )
    tab.system_stats_font_size.setValue(
        tab._config_int("system_stats", values, "font_size")
    )
    _set_controls_visible(tab)


def save_system_stats_settings(tab: "WidgetsTab") -> dict[str, Any]:
    defaults = tab._widget_defaults.get("system_stats")
    if not isinstance(defaults, Mapping):
        raise KeyError("Canonical widget defaults are missing widgets.system_stats")
    payload = dict(defaults)
    payload.update(
        {
            "enabled": bool(tab.system_stats_enabled.isChecked()),
            "position": tab.system_stats_position.currentText(),
            "monitor": tab._monitor_value_from_combo(
                "system_stats", tab.system_stats_monitor_combo
            ),
            "font_family": tab.system_stats_font_family.currentFont().family(),
            "font_size": int(tab.system_stats_font_size.value()),
        }
    )
    return payload


__all__ = [
    "build_system_stats_ui",
    "load_system_stats_settings",
    "save_system_stats_settings",
]
