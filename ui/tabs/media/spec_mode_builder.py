"""Settings bodies built, loaded and saved from a Visualizer mode's spec
(``core/settings/visualizer_mode_settings.py``).

Widgets keep the names the hand-written bodies used: a slider, checkbox or drop-down is
``tab.<key>``; a colour is the QColor ``tab._<key>`` with its swatch ``tab.<key>_btn``. Every edit
moves a curated preset to Custom and saves, as the hand-written bodies did. A control with a ``when``
shows only while the control it names holds the value, following it live and on load.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QLabel, QSlider

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_mode_settings import (
    Choice,
    Colour,
    Custom,
    ModeSettings,
    Slider,
    Toggle,
    require_mode_settings,
    read_control_value,
)
from ui.color_utils import qcolor_to_list
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, RecommendedMarkSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

_LABEL_WIDTH = 150


def _resolve(path: str):
    module, _, name = path.partition(":")
    return getattr(import_module(module), name)


def container_attr(mode_id: str) -> str:
    return f"_{require_mode_settings(mode_id).prefix}_settings_container"


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
    rows = {}
    toggle_groups = {}
    for entry in spec.entries:
        if not entry.bucket:
            continue          # set elsewhere (live orbit), not from the body
        layout = layouts[entry.bucket]
        if isinstance(entry, Custom):
            _resolve(entry.build)(tab, layout)
        else:
            if isinstance(entry, Toggle) and entry.row_group:
                group = (entry.bucket, entry.row_group)
                if group not in toggle_groups:
                    toggle_groups[group] = _row(layout, entry.label)
                else:
                    toggle_groups[group][1].addSpacing(16)
                rows[entry.key] = _build_control(tab, layout, entry, toggle_groups[group], auto_switch=spec.auto_switch)
            else:
                rows[entry.key] = _build_control(tab, layout, entry, auto_switch=spec.auto_switch)
    for _row_widget, content in toggle_groups.values():
        content.addStretch()
    setattr(tab, f"_{prefix}_rows", rows)
    _bind_conditions(tab, spec, rows)


def _bind_conditions(tab, spec: ModeSettings, rows) -> None:
    """Show each conditional row only while its condition holds; re-applied after a load."""
    conditional = [(rows[control.key], control.when) for control in spec.controls
                   if control.when and control.key in rows]
    enabled = [(getattr(tab, control.key), control) for control in spec.controls
               if getattr(control, "enabled_when", ()) and hasattr(tab, control.key)]
    if not conditional and not enabled:
        return

    def apply(*_args) -> None:
        for row, (key, value) in conditional:
            row.setVisible(_current_value(tab, spec.control(key)) == value)
        for widget, control in enabled:
            key, value = control.enabled_when
            available = not control.availability or bool(_resolve(control.availability[0]))
            widget.setEnabled(available and _current_value(tab, spec.control(key)) == value)

    setattr(tab, f"_{spec.prefix}_apply_conditions", apply)
    condition_keys = {key for _row, (key, _value) in conditional}
    condition_keys.update(control.enabled_when[0] for _widget, control in enabled)
    for key in condition_keys:
        control = spec.control(key)
        widget = getattr(tab, control.key)
        signal = (widget.toggled if isinstance(control, Toggle) else widget.valueChanged
                  if isinstance(control, Slider) else widget.currentIndexChanged)
        signal.connect(apply)
    apply()


def _current_value(tab, control):
    widget = getattr(tab, control.key)
    if isinstance(control, Toggle):
        return widget.isChecked()
    if isinstance(control, Slider):
        return control.admit(widget.value() / control.scale, control.low)
    return widget.currentIndex() if control.indexed else widget.currentText()


def _row(layout, label: str):
    widget, content, _ = add_aligned_row_widget(layout, label, label_width=_LABEL_WIDTH)
    return widget, content


def _build_control(tab, layout, control, shared_row=None, *, auto_switch=True):
    """Build one control's row; returns the row widget (hidden with the control)."""
    default = tab._widget_default("spotify_visualizer", control.key)
    if isinstance(control, Colour):
        if control.swatch_row:
            row, content, _label = add_builder_swatch_row(layout, control.label, label_width=_LABEL_WIDTH)
        else:
            row, content = _row(layout, control.label)
        colour = QColor(*control.admit(default, default))
        setattr(tab, f"_{control.key}", colour)
        button = ColorSwatchButton(title=control.title, show_alpha=control.alpha)
        button.setToolTip(control.tooltip)
        _apply_availability(button, control)
        bind_color_button(tab, button, f"_{control.key}", auto_switch=auto_switch, initial_color=colour)
        setattr(tab, f"{control.key}_btn", button)
        content.addWidget(button)
        content.addStretch()
        return row
    if shared_row is not None:
        row, content = shared_row
    elif isinstance(control, Toggle) and not control.label:
        row = widget = QCheckBox(control.text)       # stands alone across the bucket
        layout.addWidget(widget)
    else:
        row, content = _row(layout, control.label)
    if isinstance(control, Slider):
        widget = (NoWheelSlider(Qt.Orientation.Horizontal) if control.recommended is None
                  else RecommendedMarkSlider(Qt.Orientation.Horizontal))
        widget.setRange(round(control.low * control.scale), round(control.high * control.scale))
        widget.setValue(control.position(control.admit(default, default)))
        if control.recommended is not None:
            widget.set_recommended_value(control.position(control.recommended))
        if control.tick:
            widget.setTickPosition(QSlider.TickPosition.TicksBelow)
            widget.setTickInterval(control.tick)
        value = QLabel()
        value.setText(control.text(widget.value()))
        setattr(tab, f"{control.key}_label", value)
        widget.valueChanged.connect(lambda position, c=control, label=value: label.setText(c.text(position)))
        bind_setting_signal(tab, widget.valueChanged, auto_switch=auto_switch)
        content.addWidget(widget)
        content.addWidget(value)
    elif isinstance(control, Toggle):
        if control.label or shared_row is not None:
            widget = QCheckBox(control.text)
            content.addWidget(widget)
            if shared_row is None:
                content.addStretch()
        widget.setProperty("circleIndicator", True)
        widget.setChecked(control.admit(default, default))
        bind_setting_signal(tab, widget.toggled, auto_switch=auto_switch)
    else:
        widget = StyledComboBox(size_variant="compact") if control.compact else StyledComboBox()
        widget.addItems(list(control.choices))
        if control.indexed:
            widget.setCurrentIndex(control.admit(default, default))
            bind_setting_signal(tab, widget.currentIndexChanged, auto_switch=auto_switch)
        else:
            widget.setCurrentText(control.admit(default, default))
            bind_setting_signal(tab, widget.currentTextChanged, auto_switch=auto_switch)
        content.addWidget(widget)
        content.addStretch()
    widget.setToolTip(control.tooltip)
    if isinstance(control, Slider) and control.bottom_padding:
        margins = row.layout().contentsMargins()
        row.layout().setContentsMargins(margins.left(), margins.top(), margins.right(),
                                       margins.bottom() + control.bottom_padding)
    _apply_availability(widget, control)
    setattr(tab, control.key, widget)
    return row


def _apply_availability(widget, control) -> None:
    if control.availability:
        flag, unavailable_tooltip = control.availability
        available = bool(_resolve(flag))
        widget.setEnabled(available)
        widget.setToolTip(control.tooltip if available else unavailable_tooltip)


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
        value = entry.admit(read_control_value(entry, config.get, default), default)
        if isinstance(entry, Colour):
            colour = QColor(*value)
            setattr(tab, f"_{entry.key}", colour)
            button = getattr(tab, f"{entry.key}_btn", None)
            if button is not None:
                button.set_color(colour)
                _apply_availability(button, entry)
            continue
        widget = getattr(tab, entry.key, None)
        if widget is None:
            continue
        previous = widget.blockSignals(True)
        try:
            if isinstance(entry, Slider):
                widget.setValue(entry.position(value))
            elif isinstance(entry, Toggle):
                widget.setChecked(value)
            elif entry.indexed:
                widget.setCurrentIndex(value)
            else:
                widget.setCurrentText(value)
        finally:
            widget.blockSignals(previous)
        if isinstance(entry, Slider):
            # Its value label follows valueChanged, which was blocked.
            getattr(tab, f"{entry.key}_label").setText(entry.text(widget.value()))
        _apply_availability(widget, entry)
    # Conditions follow their controls' signals, which were blocked.
    apply = getattr(tab, f"_{spec.prefix}_apply_conditions", None)
    if apply is not None:
        apply()


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
        values[entry.key] = _current_value(tab, entry)
    return values


__all__ = ["build_spec_mode_ui", "collect_spec_mode_settings", "container_attr", "load_spec_mode_settings"]
