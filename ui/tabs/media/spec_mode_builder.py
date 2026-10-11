"""Settings bodies built, loaded and saved from a Visualizer mode's spec
(``core/settings/visualizer_mode_settings.py``).

Widgets keep the names the hand-written bodies used: a slider, checkbox or drop-down is
``tab.<key>``; a colour is the QColor ``tab._<key>`` with its swatch ``tab.<key>_btn``. Every edit
moves a curated preset to Custom and saves, as the hand-written bodies did.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QLabel

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_mode_settings import (
    Choice,
    Colour,
    Custom,
    ModeSettings,
    Slider,
    Toggle,
    require_mode_settings,
)
from ui.color_utils import qcolor_to_list
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

_LABEL_WIDTH = 150


def _resolve(path: str):
    module, _, name = path.partition(":")
    return getattr(import_module(module), name)


def container_attr(mode_id: str) -> str:
    return f"_{require_mode_settings(mode_id).prefix}_settings_container"


def _slider_text(control: Slider, position: int) -> str:
    return f"{position / control.scale:.{control.decimals}f}{control.suffix}"


def build_spec_mode_ui(tab, parent_layout, mode_id: str) -> None:
    """Build ``mode_id``'s body: the shared preset/advanced/technical scaffold, then each bucket
    with its controls in the spec's order."""
    spec = require_mode_settings(mode_id)
    prefix = spec.prefix
    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key=mode_id,
        settings_container_attr=f"_{prefix}_settings_container",
        preset_slider_attr=get_visualizer_mode_descriptor(mode_id).preset_slider_attr,
        normal_attr=f"_{prefix}_normal",
        advanced_host_attr=f"_{prefix}_advanced_host",
        advanced_toggle_attr=f"_{prefix}_adv_toggle",
        advanced_helper_attr=f"_{prefix}_adv_helper",
        advanced_attr=f"_{prefix}_advanced",
    )
    layouts = {}
    for bucket in spec.buckets:
        _host, layouts[bucket.key] = build_collapsible_bucket(
            tab, scaffold.advanced_layout if bucket.advanced else scaffold.normal_layout,
            mode_key=mode_id, bucket_key=bucket.key, title=bucket.title, helper_text=bucket.helper,
        )
    for entry in spec.entries:
        if not entry.bucket:
            continue          # set elsewhere (live orbit), not from the body
        layout = layouts[entry.bucket]
        if isinstance(entry, Custom):
            _resolve(entry.build)(tab, layout)
        else:
            _build_control(tab, layout, entry)


def _row(layout, label: str):
    _widget, content, _ = add_aligned_row_widget(layout, label, label_width=_LABEL_WIDTH)
    return content


def _build_control(tab, layout, control) -> None:
    default = tab._widget_default("spotify_visualizer", control.key)
    if isinstance(control, Colour):
        content = _row(layout, control.label)
        colour = QColor(*control.admit(default, default))
        setattr(tab, f"_{control.key}", colour)
        button = ColorSwatchButton(title=control.title, show_alpha=control.alpha)
        button.setToolTip(control.tooltip)
        bind_color_button(tab, button, f"_{control.key}", auto_switch=True, initial_color=colour)
        setattr(tab, f"{control.key}_btn", button)
        content.addWidget(button)
        content.addStretch()
        return
    content = _row(layout, control.label)
    if isinstance(control, Slider):
        widget = NoWheelSlider(Qt.Orientation.Horizontal)
        widget.setRange(round(control.low * control.scale), round(control.high * control.scale))
        widget.setValue(round(control.admit(default, default) * control.scale))
        value = QLabel()
        value.setText(_slider_text(control, widget.value()))
        setattr(tab, f"{control.key}_label", value)
        widget.valueChanged.connect(lambda position, c=control, label=value: label.setText(_slider_text(c, position)))
        bind_setting_signal(tab, widget.valueChanged, auto_switch=True)
        content.addWidget(widget)
        content.addWidget(value)
    elif isinstance(control, Toggle):
        widget = QCheckBox(control.text)
        widget.setProperty("circleIndicator", True)
        widget.setChecked(control.admit(default, default))
        bind_setting_signal(tab, widget.toggled, auto_switch=True)
        content.addWidget(widget)
        content.addStretch()
    else:
        widget = StyledComboBox(size_variant="compact")
        widget.addItems(list(control.choices))
        widget.setCurrentText(control.admit(default, default))
        bind_setting_signal(tab, widget.currentTextChanged, auto_switch=True)
        content.addWidget(widget)
        content.addStretch()
    widget.setToolTip(control.tooltip)
    setattr(tab, control.key, widget)


def load_spec_mode_settings(tab, mode_id: str, config) -> None:
    """Show ``config``'s values (canonical defaults for missing ones), repaired as the model
    repairs them. Signals are blocked so loading saves nothing and switches no preset."""
    spec = require_mode_settings(mode_id)
    config = config if isinstance(config, dict) else {}
    for entry in spec.entries:
        if not entry.bucket:
            continue
        if isinstance(entry, Custom):
            if entry.load:
                _resolve(entry.load)(tab, config)
            continue
        default = tab._widget_default("spotify_visualizer", entry.key)
        value = entry.admit(config.get(entry.key, default), default)
        if isinstance(entry, Colour):
            colour = QColor(*value)
            setattr(tab, f"_{entry.key}", colour)
            button = getattr(tab, f"{entry.key}_btn", None)
            if button is not None:
                button.set_color(colour)
            continue
        widget = getattr(tab, entry.key, None)
        if widget is None:
            continue
        widget.blockSignals(True)
        try:
            if isinstance(entry, Slider):
                widget.setValue(round(value * entry.scale))
            elif isinstance(entry, Toggle):
                widget.setChecked(value)
            else:
                widget.setCurrentText(value)
        finally:
            widget.blockSignals(False)
        if isinstance(entry, Slider):
            # Its value label follows valueChanged, which was blocked.
            getattr(tab, f"{entry.key}_label").setText(_slider_text(entry, widget.value()))


def collect_spec_mode_settings(tab, mode_id: str) -> dict[str, Any]:
    """The body's values as persisted (sliders unscaled, colours as RGBA lists)."""
    spec: ModeSettings = require_mode_settings(mode_id)
    values: dict[str, Any] = {}
    for entry in spec.entries:
        if not entry.bucket:
            continue
        if isinstance(entry, Custom):
            if entry.collect:
                values.update(_resolve(entry.collect)(tab))
            continue
        if isinstance(entry, Colour):
            values[entry.key] = qcolor_to_list(getattr(tab, f"_{entry.key}", None),
                                               tab._widget_default("spotify_visualizer", entry.key))
            continue
        widget = getattr(tab, entry.key)
        if isinstance(entry, Slider):
            values[entry.key] = widget.value() / entry.scale
        elif isinstance(entry, Toggle):
            values[entry.key] = widget.isChecked()
        elif isinstance(entry, Choice):
            values[entry.key] = widget.currentText()
    return values


__all__ = ["build_spec_mode_ui", "collect_spec_mode_settings", "container_attr", "load_spec_mode_settings"]
