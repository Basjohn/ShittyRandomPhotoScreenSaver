"""Bubble Settings body built from its typed spec, with one-key Swirl composition."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox

from core.settings.visualizer_mode_settings import require_mode_settings
from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.shared_styles import add_aligned_row_widget
from ui.widgets import StyledComboBox


def build_bubble_ui(tab, parent_layout) -> None:
    from ui.tabs.media.spec_mode_builder import build_spec_mode_ui

    build_spec_mode_ui(tab, parent_layout, "bubble")
    # Existing view/test names are aliases of the canonical widgets, not owners.
    tab.bubble_ghost_enabled = tab.bubble_ghosting_enabled
    tab.bubble_ghost_opacity = tab.bubble_ghost_alpha
    tab.bubble_ghost_opacity_label = tab.bubble_ghost_alpha_label
    tab.bubble_ghost_decay_slider = tab.bubble_ghost_decay
    tab._bubble_stream_direction_row_widget = tab._bubble_rows["bubble_stream_direction"]
    tab._bubble_apply_swirl()


def build_bubble_swirl(tab, layout) -> None:
    """Project the authored drift choice into Drift plus the existing Swirl UI."""
    spec = require_mode_settings("bubble")
    control = spec.control("bubble_drift_direction")
    default = tab._widget_default("spotify_visualizer", control.key)
    current = control.admit(default, default)

    def row(label, *, wrap=True):
        widget, content, _ = add_aligned_row_widget(
            layout, label, label_width=150, wrap=wrap)
        return widget, content

    tab._bubble_drift_direction_row_widget, content = row("Drift Direction:")
    tab.bubble_drift_direction = StyledComboBox(size_variant="compact")
    for value, label in zip(control.choices, control.labels):
        if not value.startswith("swirl_"):
            tab.bubble_drift_direction.addItem(label, value)
    tab.bubble_drift_direction.setCurrentIndex(
        tab.bubble_drift_direction.findData("none" if current.startswith("swirl_") else current))
    bind_setting_signal(tab, tab.bubble_drift_direction.currentIndexChanged, auto_switch=spec.auto_switch)
    content.addWidget(tab.bubble_drift_direction)
    content.addStretch()

    _, content = row("Swirl Mode:")
    tab.bubble_swirl_enabled = QCheckBox("Enable")
    tab.bubble_swirl_enabled.setProperty("circleIndicator", True)
    tab.bubble_swirl_enabled.setChecked(current.startswith("swirl_"))
    content.addWidget(tab.bubble_swirl_enabled)
    content.addStretch()

    tab._bubble_swirl_direction_row_widget, content = row("", wrap=False)
    tab.bubble_swirl_direction = StyledComboBox(size_variant="compact")
    for value, label in zip(control.choices, control.labels):
        if value.startswith("swirl_"):
            tab.bubble_swirl_direction.addItem(label, value)
    tab.bubble_swirl_direction.setCurrentIndex(
        tab.bubble_swirl_direction.findData(current if current.startswith("swirl_") else "swirl_cw"))
    bind_setting_signal(tab, tab.bubble_swirl_direction.currentIndexChanged, auto_switch=spec.auto_switch)
    content.addWidget(tab.bubble_swirl_direction)
    content.addStretch()

    def apply(*_args):
        enabled = tab.bubble_swirl_enabled.isChecked()
        tab.bubble_swirl_direction.setEnabled(enabled)
        tab.bubble_drift_direction.setEnabled(not enabled)
        tab.bubble_stream_direction.setEnabled(not enabled)
        tab._bubble_swirl_direction_row_widget.setVisible(enabled)
        tab._bubble_drift_direction_row_widget.setVisible(not enabled)
        stream_row = getattr(tab, "_bubble_stream_direction_row_widget", None)
        if stream_row is not None:
            stream_row.setVisible(not enabled)

    tab._bubble_apply_swirl = apply
    tab.bubble_swirl_enabled.toggled.connect(apply)
    bind_setting_signal(tab, tab.bubble_swirl_enabled.toggled, auto_switch=spec.auto_switch)


def load_bubble_swirl(tab, config) -> None:
    control = require_mode_settings("bubble").control("bubble_drift_direction")
    default = tab._widget_default("spotify_visualizer", control.key)
    value = control.admit(config.get(control.key, default), default)
    values = (
        (tab.bubble_drift_direction, "none" if value.startswith("swirl_") else value),
        (tab.bubble_swirl_direction, value if value.startswith("swirl_") else "swirl_cw"),
    )
    for widget, selected in values:
        previous = widget.blockSignals(True)
        try:
            index = widget.findData(selected)
            if index < 0:
                raise ValueError(f"Bubble drift UI does not represent {selected!r}")
            widget.setCurrentIndex(index)
        finally:
            widget.blockSignals(previous)
    previous = tab.bubble_swirl_enabled.blockSignals(True)
    try:
        tab.bubble_swirl_enabled.setChecked(value.startswith("swirl_"))
    finally:
        tab.bubble_swirl_enabled.blockSignals(previous)
    tab._bubble_apply_swirl()


def collect_bubble_swirl(tab) -> dict:
    widget = tab.bubble_swirl_direction if tab.bubble_swirl_enabled.isChecked() else tab.bubble_drift_direction
    value = widget.currentData()
    control = require_mode_settings("bubble").control("bubble_drift_direction")
    if value not in control.choices:
        raise ValueError(f"Bubble drift UI has no authored direction: {value!r}")
    return {control.key: value}

