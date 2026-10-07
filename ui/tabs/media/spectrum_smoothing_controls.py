"""Shared controls for the existing Spectrum-family temporal evaluator."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QSlider

from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget


def build_spectrum_smoothing_controls(tab, layout, *, mode_key: str) -> None:
    """Build lazily in the admitted mode body; ownership follows its namespace."""
    auto_switch = mode_key != "spectrum"
    enabled_key = f"{mode_key}_visual_smoothing_enabled"
    strength_key = f"{mode_key}_visual_smoothing"
    _, row, _ = add_aligned_row_widget(layout, "", label_width=150)
    enabled = QCheckBox("Smooth Sudden Bar Changes")
    enabled.setProperty("circleIndicator", True)
    enabled.setChecked(tab._default_bool("spotify_visualizer", enabled_key))
    enabled.setToolTip("Interpolate bar heights on the existing visualizer tick. Audio analysis remains unchanged.")
    setattr(tab, enabled_key, enabled)
    bind_setting_signal(tab, enabled.stateChanged, auto_switch=auto_switch)
    row.addWidget(enabled)
    row.addStretch()

    container, row, _ = add_aligned_row_widget(layout, "Smoothing Strength:", label_width=150)
    strength = NoWheelSlider(Qt.Orientation.Horizontal)
    strength.setRange(0, 100)
    default = max(0, min(100, int(tab._default_float("spotify_visualizer", strength_key) * 100)))
    strength.setValue(default)
    strength.setTickPosition(QSlider.TickPosition.TicksBelow)
    strength.setTickInterval(10)
    strength.setToolTip("Higher values soften one-tick spikes and drops more strongly. The evaluator snaps to source after a UI stall.")
    label = QLabel(f"{default}%")
    setattr(tab, strength_key, strength)
    setattr(tab, f"{strength_key}_label", label)
    bind_setting_signal(tab, strength.valueChanged, auto_switch=auto_switch,
                        updater=lambda value: label.setText(f"{value}%"))
    row.addWidget(strength)
    row.addWidget(label)
    enabled.stateChanged.connect(lambda *_: container.setVisible(enabled.isChecked()))
    container.setVisible(enabled.isChecked())

    if auto_switch:
        key = f"{mode_key}_solid_bar_hysteresis_enabled"
        _, row, _ = add_aligned_row_widget(layout, "", label_width=150)
        stabilization = QCheckBox("Stabilize Bar Heights")
        stabilization.setProperty("circleIndicator", True)
        stabilization.setChecked(tab._default_bool("spotify_visualizer", key))
        stabilization.setToolTip("Use the shared bar evaluator's hysteresis to suppress tiny height fluctuations.")
        setattr(tab, key, stabilization)
        bind_setting_signal(tab, stabilization.stateChanged, auto_switch=True)
        row.addWidget(stabilization)
        row.addStretch()
