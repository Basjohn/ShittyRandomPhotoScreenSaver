"""Shared scaffold helpers for visualizer mode UI builders."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ui.tabs.media.technical_controls import build_per_mode_technical_group
from ui.tabs.shared_styles import ADV_HELPER_LABEL_STYLE, add_swatch_label

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


@dataclass
class ModeScaffold:
    container: QWidget
    layout: QVBoxLayout
    preset_slider: object
    normal_widget: QWidget
    normal_layout: QVBoxLayout
    advanced_host: QWidget
    advanced_layout: QVBoxLayout
    technical_host: QWidget


def add_builder_swatch_row(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int,
) -> tuple[QWidget, QHBoxLayout, QLabel]:
    """Create a standard color-swatch row with the shared visualizer spacing."""
    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(0, 8, 0, 8)
    row_layout.setSpacing(12)
    label = add_swatch_label(row_layout, label_text, label_width)
    content = QHBoxLayout()
    content.setContentsMargins(0, 0, 0, 0)
    content.setSpacing(12)
    row_layout.addLayout(content, 1)
    parent_layout.addWidget(row_widget)
    return row_widget, content, label


def build_mode_scaffold(
    tab: "WidgetsTab",
    parent_layout: QVBoxLayout,
    *,
    mode_key: str,
    settings_container_attr: str,
    preset_slider_attr: str,
    normal_attr: str,
    advanced_host_attr: str,
    advanced_toggle_attr: str,
    advanced_helper_attr: str,
    advanced_attr: str,
) -> ModeScaffold:
    """Build the shared preset/normal/advanced/technical scaffold for a mode."""
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    setattr(tab, settings_container_attr, container)

    preset_slider = VisualizerPresetSlider(mode_key)
    preset_slider.preset_changed.connect(lambda idx: tab._on_visualizer_preset_changed(mode_key, idx))
    setattr(tab, preset_slider_attr, preset_slider)
    layout.addWidget(preset_slider)

    normal_widget = QWidget()
    normal_layout = QVBoxLayout(normal_widget)
    normal_layout.setContentsMargins(0, 0, 0, 0)
    normal_layout.setSpacing(12)
    setattr(tab, normal_attr, normal_widget)
    layout.addWidget(normal_widget)

    advanced_host = QWidget()
    advanced_host_layout = QVBoxLayout(advanced_host)
    advanced_host_layout.setContentsMargins(0, 0, 0, 12)
    advanced_host_layout.setSpacing(12)
    setattr(tab, advanced_host_attr, advanced_host)
    layout.addWidget(advanced_host)

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(8)
    toggle = QToolButton()
    toggle.setText("Advanced")
    toggle.setCheckable(True)
    default_expanded = False
    getter = getattr(tab, "get_visualizer_adv_state", None)
    if callable(getter):
        try:
            default_expanded = bool(getter(mode_key))
        except Exception:
            default_expanded = False
    toggle.setChecked(default_expanded)
    toggle.setArrowType(Qt.DownArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)
    setattr(tab, advanced_toggle_attr, toggle)
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    advanced_host_layout.addLayout(toggle_row)

    helper = QLabel("Advanced sliders still apply when hidden.")
    helper.setProperty("class", "adv-helper")
    helper.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    setattr(tab, advanced_helper_attr, helper)
    advanced_host_layout.addWidget(helper)

    advanced_widget = QWidget()
    advanced_layout = QVBoxLayout(advanced_widget)
    advanced_layout.setContentsMargins(0, 0, 0, 0)
    advanced_layout.setSpacing(12)
    setattr(tab, advanced_attr, advanced_widget)
    advanced_host_layout.addWidget(advanced_widget)

    preset_slider.set_advanced_container(advanced_host)

    def _apply_advanced_toggle_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        advanced_widget.setVisible(checked)
        helper.setVisible(not checked)
        setter = getattr(tab, "set_visualizer_adv_state", None)
        if callable(setter):
            try:
                setter(mode_key, checked)
            except Exception:
                pass

    toggle.toggled.connect(_apply_advanced_toggle_state)
    _apply_advanced_toggle_state(toggle.isChecked())

    def _handle_preset_visibility(is_custom: bool) -> None:
        normal_widget.setVisible(is_custom)
        advanced_host.setVisible(is_custom)

    preset_slider.advanced_toggled.connect(_handle_preset_visibility)
    _handle_preset_visibility(True)

    technical_host = build_per_mode_technical_group(tab, layout, mode_key)
    preset_slider.set_technical_container(technical_host)

    parent_layout.addWidget(container)
    return ModeScaffold(
        container=container,
        layout=layout,
        preset_slider=preset_slider,
        normal_widget=normal_widget,
        normal_layout=normal_layout,
        advanced_host=advanced_host,
        advanced_layout=advanced_layout,
        technical_host=technical_host,
    )
