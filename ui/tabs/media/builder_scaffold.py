"""Shared scaffold helpers for visualizer mode UI builders."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from ui.tabs.media.technical_controls import build_per_mode_technical_group
from ui.tabs import shared_styles
from ui.tabs.shared_styles import add_swatch_label

if TYPE_CHECKING:
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin


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


def bind_setting_signal(
    tab: "VisualizerSettingsContextMixin",
    signal: Any,
    *,
    updater: Callable[..., None] | None = None,
    auto_switch: bool = False,
) -> None:
    """Wire a control signal into the shared visualizer save flow."""
    if updater is not None:
        signal.connect(updater)
    if auto_switch:
        signal.connect(lambda *_args: tab._force_visualizer_preset_to_custom())
    signal.connect(tab._save_settings)


def bind_color_button(
    tab: "VisualizerSettingsContextMixin",
    button: Any,
    attr_name: str,
    *,
    auto_switch: bool = False,
    initial_color: Any = None,
) -> None:
    """Bind a color swatch button to a tab attribute and save flow."""
    if initial_color is not None:
        button.set_color(initial_color)

    def _on_color(color: Any) -> None:
        setattr(tab, attr_name, color)
        if auto_switch:
            tab._force_visualizer_preset_to_custom()
        tab._save_settings()

    button.color_changed.connect(_on_color)


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


def build_collapsible_bucket(
    tab: "VisualizerSettingsContextMixin",
    target_layout: QVBoxLayout,
    *,
    mode_key: str,
    bucket_key: str,
    title: str,
    helper_text: str,
) -> tuple[QWidget, QVBoxLayout]:
    """Create a persisted collapsible bucket for a visualizer mode."""
    host = QWidget()
    host.setObjectName(f"{mode_key}_bucket_{bucket_key}")
    host.setProperty("bucketTitle", title)

    host_layout = QVBoxLayout(host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(8)

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(8)

    expanded = bool(tab.get_visualizer_bucket_state(mode_key, bucket_key))

    toggle = QToolButton()
    toggle.setText(title)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    helper = QLabel(helper_text)
    helper.setProperty("class", "adv-helper")
    shared_styles.apply_shared_label_style(helper, "ADV_HELPER_LABEL_STYLE")
    helper.setWordWrap(True)
    host_layout.addWidget(helper)

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(12)
    host_layout.addWidget(body)

    def _apply_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        body.setVisible(checked)
        helper.setVisible(not checked)
        setter = getattr(tab, "set_visualizer_bucket_state", None)
        if callable(setter):
            try:
                setter(mode_key, bucket_key, checked)
            except Exception:
                pass

    toggle.toggled.connect(_apply_state)
    _apply_state(expanded)

    target_layout.addWidget(host)
    return host, body_layout


def build_mode_scaffold(
    tab: "VisualizerSettingsContextMixin",
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

    body_object_name = f"visualizer_mode_body_{mode_key}"
    # A failed lazy-body construction must never leave a visible orphan behind.
    # Normal construction is cached by VisualizerModeBodyHost, so finding an
    # existing direct child with this marker means a previous factory attempt
    # failed before it could be committed. Remove that stale presentation body
    # before trying again; authored settings/presets live outside the QWidget.
    stale_bodies = []
    for index in range(parent_layout.count()):
        item = parent_layout.itemAt(index)
        candidate = item.widget() if item is not None else None
        if candidate is not None and candidate.objectName() == body_object_name:
            stale_bodies.append(candidate)
    for stale in stale_bodies:
        parent_layout.removeWidget(stale)
        stale.hide()
        stale.deleteLater()

    container = QWidget()
    container.setObjectName(body_object_name)
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
    default_expanded = bool(tab.get_visualizer_adv_state(mode_key))
    toggle.setChecked(default_expanded)
    toggle.setArrowType(Qt.DownArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)
    setattr(tab, advanced_toggle_attr, toggle)
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    advanced_host_layout.addLayout(toggle_row)

    helper = QLabel("Advanced Sliders Still Apply When Hidden.")
    helper.setProperty("class", "adv-helper")
    shared_styles.apply_shared_label_style(helper, "ADV_HELPER_LABEL_STYLE")
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
    # The slider is born on its first authored preset, not Custom. Do not expose
    # Custom-only controls even transiently before hydration finishes. This also
    # keeps a failed construction from presenting a bogus "Advanced" body.
    _handle_preset_visibility(
        preset_slider.preset_index() == preset_slider.custom_index()
    )

    if get_visualizer_mode_descriptor(mode_key).technical_controls:
        technical_host = build_per_mode_technical_group(tab, layout, mode_key)
    else:
        technical_host = QWidget(container)
        technical_host.setVisible(False)
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
