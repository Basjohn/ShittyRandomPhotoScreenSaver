"""Bubble visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QSlider, QWidget,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_bubble_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Bubble visualizer settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider

    tab._bubble_settings_container = QWidget()
    layout = QVBoxLayout(tab._bubble_settings_container)
    layout.setContentsMargins(0, 0, 0, 0)

    # ── Audio Reactivity ──────────────────────────────────────────
    layout.addWidget(QLabel("<b>Audio Reactivity</b>"))

    # Big Bubble Bass Pulse
    row = QHBoxLayout()
    row.addWidget(QLabel("Big Bubble Bass Pulse:"))
    tab.bubble_big_bass_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_bass_pulse.setMinimum(0)
    tab.bubble_big_bass_pulse.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_bass_pulse', 0.5) * 100)
    tab.bubble_big_bass_pulse.setValue(val)
    tab.bubble_big_bass_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_bass_pulse.setTickInterval(25)
    tab.bubble_big_bass_pulse.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_big_bass_pulse)
    tab.bubble_big_bass_pulse_label = QLabel(f"{val}%")
    tab.bubble_big_bass_pulse.valueChanged.connect(
        lambda v: tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_big_bass_pulse_label)
    layout.addLayout(row)

    # Small Bubble Freq Pulse
    row = QHBoxLayout()
    row.addWidget(QLabel("Small Bubble Freq Pulse:"))
    tab.bubble_small_freq_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_freq_pulse.setMinimum(0)
    tab.bubble_small_freq_pulse.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_freq_pulse', 0.5) * 100)
    tab.bubble_small_freq_pulse.setValue(val)
    tab.bubble_small_freq_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_freq_pulse.setTickInterval(25)
    tab.bubble_small_freq_pulse.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_small_freq_pulse)
    tab.bubble_small_freq_pulse_label = QLabel(f"{val}%")
    tab.bubble_small_freq_pulse.valueChanged.connect(
        lambda v: tab.bubble_small_freq_pulse_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_small_freq_pulse_label)
    layout.addLayout(row)

    # ── Stream Controls ───────────────────────────────────────────
    layout.addWidget(QLabel("<b>Stream Controls</b>"))

    # Stream Direction
    row = QHBoxLayout()
    row.addWidget(QLabel("Stream Direction:"))
    tab.bubble_stream_direction = QComboBox()
    tab.bubble_stream_direction.addItems(["None", "Up", "Down", "Left", "Right", "Diagonal", "Random"])
    saved_dir = tab._default_str('spotify_visualizer', 'bubble_stream_direction', 'up').lower()
    dir_map = {"none": 0, "up": 1, "down": 2, "left": 3, "right": 4, "diagonal": 5, "random": 6}
    tab.bubble_stream_direction.setCurrentIndex(dir_map.get(saved_dir, 1))
    tab.bubble_stream_direction.currentIndexChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_stream_direction)
    row.addStretch()
    layout.addLayout(row)

    # Stream Speed
    row = QHBoxLayout()
    row.addWidget(QLabel("Stream Speed:"))
    tab.bubble_stream_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_speed.setMinimum(0)
    tab.bubble_stream_speed.setMaximum(150)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_speed', 1.0) * 100)
    tab.bubble_stream_speed.setValue(val)
    tab.bubble_stream_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_speed.setTickInterval(25)
    tab.bubble_stream_speed.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_stream_speed)
    tab.bubble_stream_speed_label = QLabel(f"{val}%")
    tab.bubble_stream_speed.valueChanged.connect(
        lambda v: tab.bubble_stream_speed_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_stream_speed_label)
    layout.addLayout(row)

    # Stream Speed Reactivity
    row = QHBoxLayout()
    row.addWidget(QLabel("Speed Reactivity:"))
    tab.bubble_stream_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_reactivity.setMinimum(0)
    tab.bubble_stream_reactivity.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_reactivity', 0.5) * 100)
    tab.bubble_stream_reactivity.setValue(val)
    tab.bubble_stream_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_reactivity.setTickInterval(25)
    tab.bubble_stream_reactivity.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_stream_reactivity)
    tab.bubble_stream_reactivity_label = QLabel(f"{val}%")
    tab.bubble_stream_reactivity.valueChanged.connect(
        lambda v: tab.bubble_stream_reactivity_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_stream_reactivity_label)
    layout.addLayout(row)

    # ── Drift & Rotation ──────────────────────────────────────────
    layout.addWidget(QLabel("<b>Drift & Rotation</b>"))

    # Rotation Amount
    row = QHBoxLayout()
    row.addWidget(QLabel("Rotation Amount:"))
    tab.bubble_rotation_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_rotation_amount.setMinimum(0)
    tab.bubble_rotation_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_rotation_amount', 0.5) * 100)
    tab.bubble_rotation_amount.setValue(val)
    tab.bubble_rotation_amount.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_rotation_amount)
    tab.bubble_rotation_amount_label = QLabel(f"{val}%")
    tab.bubble_rotation_amount.valueChanged.connect(
        lambda v: tab.bubble_rotation_amount_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_rotation_amount_label)
    layout.addLayout(row)

    # Drift Amount
    row = QHBoxLayout()
    row.addWidget(QLabel("Drift Amount:"))
    tab.bubble_drift_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_amount.setMinimum(0)
    tab.bubble_drift_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_amount', 0.5) * 100)
    tab.bubble_drift_amount.setValue(val)
    tab.bubble_drift_amount.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_drift_amount)
    tab.bubble_drift_amount_label = QLabel(f"{val}%")
    tab.bubble_drift_amount.valueChanged.connect(
        lambda v: tab.bubble_drift_amount_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_drift_amount_label)
    layout.addLayout(row)

    # Drift Speed
    row = QHBoxLayout()
    row.addWidget(QLabel("Drift Speed:"))
    tab.bubble_drift_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_speed.setMinimum(0)
    tab.bubble_drift_speed.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_speed', 0.5) * 100)
    tab.bubble_drift_speed.setValue(val)
    tab.bubble_drift_speed.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_drift_speed)
    tab.bubble_drift_speed_label = QLabel(f"{val}%")
    tab.bubble_drift_speed.valueChanged.connect(
        lambda v: tab.bubble_drift_speed_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_drift_speed_label)
    layout.addLayout(row)

    # Drift Frequency
    row = QHBoxLayout()
    row.addWidget(QLabel("Drift Frequency:"))
    tab.bubble_drift_frequency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_frequency.setMinimum(0)
    tab.bubble_drift_frequency.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_frequency', 0.5) * 100)
    tab.bubble_drift_frequency.setValue(val)
    tab.bubble_drift_frequency.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_drift_frequency)
    tab.bubble_drift_frequency_label = QLabel(f"{val}%")
    tab.bubble_drift_frequency.valueChanged.connect(
        lambda v: tab.bubble_drift_frequency_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_drift_frequency_label)
    layout.addLayout(row)

    # Drift Direction
    row = QHBoxLayout()
    row.addWidget(QLabel("Drift Direction:"))
    tab.bubble_drift_direction = QComboBox()
    tab.bubble_drift_direction.addItems(["None", "Left", "Right", "Diagonal", "Random"])
    saved_dd = tab._default_str('spotify_visualizer', 'bubble_drift_direction', 'random').lower()
    dd_map = {"none": 0, "left": 1, "right": 2, "diagonal": 3, "random": 4}
    tab.bubble_drift_direction.setCurrentIndex(dd_map.get(saved_dd, 4))
    tab.bubble_drift_direction.currentIndexChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_drift_direction)
    row.addStretch()
    layout.addLayout(row)

    # ── Bubble Count & Lifecycle ──────────────────────────────────
    layout.addWidget(QLabel("<b>Bubble Count & Lifecycle</b>"))

    # Big Bubble Count
    row = QHBoxLayout()
    row.addWidget(QLabel("Big Bubbles:"))
    tab.bubble_big_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_count.setMinimum(1)
    tab.bubble_big_count.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_count', 8))
    tab.bubble_big_count.setValue(val)
    tab.bubble_big_count.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_big_count)
    tab.bubble_big_count_label = QLabel(str(val))
    tab.bubble_big_count.valueChanged.connect(
        lambda v: tab.bubble_big_count_label.setText(str(v))
    )
    row.addWidget(tab.bubble_big_count_label)
    layout.addLayout(row)

    # Small Bubble Count
    row = QHBoxLayout()
    row.addWidget(QLabel("Small Bubbles:"))
    tab.bubble_small_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_count.setMinimum(5)
    tab.bubble_small_count.setMaximum(80)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_count', 25))
    tab.bubble_small_count.setValue(val)
    tab.bubble_small_count.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_small_count)
    tab.bubble_small_count_label = QLabel(str(val))
    tab.bubble_small_count.valueChanged.connect(
        lambda v: tab.bubble_small_count_label.setText(str(v))
    )
    row.addWidget(tab.bubble_small_count_label)
    layout.addLayout(row)

    # Surface Reach %
    row = QHBoxLayout()
    row.addWidget(QLabel("Surface Reach:"))
    tab.bubble_surface_reach = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_surface_reach.setMinimum(0)
    tab.bubble_surface_reach.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_surface_reach', 0.6) * 100)
    tab.bubble_surface_reach.setValue(val)
    tab.bubble_surface_reach.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_surface_reach)
    tab.bubble_surface_reach_label = QLabel(f"{val}%")
    tab.bubble_surface_reach.valueChanged.connect(
        lambda v: tab.bubble_surface_reach_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_surface_reach_label)
    layout.addLayout(row)

    # ── Styling ───────────────────────────────────────────────────
    layout.addWidget(QLabel("<b>Styling</b>"))

    # Specular Direction
    row = QHBoxLayout()
    row.addWidget(QLabel("Specular Direction:"))
    tab.bubble_specular_direction = QComboBox()
    tab.bubble_specular_direction.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
    saved_sd = tab._default_str('spotify_visualizer', 'bubble_specular_direction', 'top_left').lower()
    sd_map = {"top_left": 0, "top_right": 1, "bottom_left": 2, "bottom_right": 3}
    tab.bubble_specular_direction.setCurrentIndex(sd_map.get(saved_sd, 0))
    tab.bubble_specular_direction.currentIndexChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_specular_direction)
    row.addStretch()
    layout.addLayout(row)

    # Colour pickers
    for attr_name, label_text in (
        ("bubble_outline_color_btn", "Outline Colour"),
        ("bubble_specular_color_btn", "Specular Colour"),
        ("bubble_gradient_light_btn", "Gradient Light"),
        ("bubble_gradient_dark_btn", "Gradient Dark"),
        ("bubble_pop_color_btn", "Pop Colour"),
    ):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label_text}:"))
        btn = QPushButton("Choose...")
        setattr(tab, attr_name, btn)
        method_name = f"_choose_{attr_name.replace('_btn', '')}"
        btn.clicked.connect(lambda checked=False, m=method_name: getattr(tab, m, lambda: None)())
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)

    parent_layout.addWidget(tab._bubble_settings_container)
