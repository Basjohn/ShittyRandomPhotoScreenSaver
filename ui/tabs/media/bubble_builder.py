"""Bubble visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QWidget,
)
from PySide6.QtCore import Qt

from ui.styled_popup import ColorSwatchButton

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_bubble_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Bubble visualizer settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._bubble_settings_container = QWidget()
    layout = QVBoxLayout(tab._bubble_settings_container)
    layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._bubble_preset_slider = VisualizerPresetSlider("bubble")
    tab._bubble_preset_slider.preset_changed.connect(tab._save_settings)
    layout.addWidget(tab._bubble_preset_slider)

    tab._bubble_advanced = QWidget()
    _adv = QVBoxLayout(tab._bubble_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    tab._bubble_preset_slider.set_advanced_container(tab._bubble_advanced)

    # ── Audio Reactivity ──────────────────────────────────────────────
    _adv.addWidget(QLabel("<b>Audio Reactivity</b>"))

    # Big Bubble Bass Pulse
    row = QHBoxLayout()
    row.addWidget(QLabel("Big Bubble Bass Pulse:"))
    tab.bubble_big_bass_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_bass_pulse.setMinimum(0)
    tab.bubble_big_bass_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_bass_pulse', 0.5) * 100)
    tab.bubble_big_bass_pulse.setValue(val)
    tab.bubble_big_bass_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_bass_pulse.setTickInterval(50)
    tab.bubble_big_bass_pulse.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_big_bass_pulse)
    tab.bubble_big_bass_pulse_label = QLabel(f"{val}%")
    tab.bubble_big_bass_pulse.valueChanged.connect(
        lambda v: tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_big_bass_pulse_label)
    _adv.addLayout(row)

    # Small Bubble Freq Pulse
    row = QHBoxLayout()
    row.addWidget(QLabel("Small Bubble Freq Pulse:"))
    tab.bubble_small_freq_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_freq_pulse.setMinimum(0)
    tab.bubble_small_freq_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_freq_pulse', 0.5) * 100)
    tab.bubble_small_freq_pulse.setValue(val)
    tab.bubble_small_freq_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_freq_pulse.setTickInterval(50)
    tab.bubble_small_freq_pulse.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_small_freq_pulse)
    tab.bubble_small_freq_pulse_label = QLabel(f"{val}%")
    tab.bubble_small_freq_pulse.valueChanged.connect(
        lambda v: tab.bubble_small_freq_pulse_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_small_freq_pulse_label)
    _adv.addLayout(row)

    # ── Stream Controls ───────────────────────────────────────────
    _adv.addWidget(QLabel("<b>Stream Controls</b>"))

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
    _adv.addLayout(row)

    # Stream Constant Speed
    row = QHBoxLayout()
    row.addWidget(QLabel("Stream Constant Speed:"))
    tab.bubble_stream_constant_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_constant_speed.setMinimum(0)
    tab.bubble_stream_constant_speed.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_constant_speed', 0.5) * 100)
    tab.bubble_stream_constant_speed.setValue(val)
    tab.bubble_stream_constant_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_constant_speed.setTickInterval(25)
    tab.bubble_stream_constant_speed.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_stream_constant_speed)
    tab.bubble_stream_constant_speed_label = QLabel(f"{val}%")
    tab.bubble_stream_constant_speed.valueChanged.connect(
        lambda v: tab.bubble_stream_constant_speed_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_stream_constant_speed_label)
    _adv.addLayout(row)

    # Stream Speed Cap
    row = QHBoxLayout()
    row.addWidget(QLabel("Stream Speed Cap:"))
    tab.bubble_stream_speed_cap = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_speed_cap.setMinimum(50)
    tab.bubble_stream_speed_cap.setMaximum(250)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_speed_cap', 2.0) * 100)
    tab.bubble_stream_speed_cap.setValue(val)
    tab.bubble_stream_speed_cap.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_speed_cap.setTickInterval(25)
    tab.bubble_stream_speed_cap.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_stream_speed_cap)
    tab.bubble_stream_speed_cap_label = QLabel(f"{val}%")
    tab.bubble_stream_speed_cap.valueChanged.connect(
        lambda v: tab.bubble_stream_speed_cap_label.setText(f"{v}%")
    )
    row.addWidget(tab.bubble_stream_speed_cap_label)
    _adv.addLayout(row)

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
    _adv.addLayout(row)

    # ── Drift & Rotation ──────────────────────────────────────────
    _adv.addWidget(QLabel("<b>Drift & Rotation</b>"))

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

    # ── Bubble Count & Lifecycle ──────────────────────────────────
    _adv.addWidget(QLabel("<b>Bubble Count & Lifecycle</b>"))

    # Big Bubble Size Max (stored as 0.010–0.060 normalised UV, slider 10–60)
    row = QHBoxLayout()
    row.addWidget(QLabel("Big Bubble Max Size:"))
    tab.bubble_big_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_size_max.setMinimum(10)
    tab.bubble_big_size_max.setMaximum(60)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_size_max', 0.038) * 1000)
    tab.bubble_big_size_max.setValue(max(10, min(60, val)))
    tab.bubble_big_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_size_max.setTickInterval(10)
    tab.bubble_big_size_max.setToolTip("Maximum radius for big bubbles (normalised UV units × 1000).")
    tab.bubble_big_size_max.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_big_size_max)
    tab.bubble_big_size_max_label = QLabel(f"{val}")
    tab.bubble_big_size_max.valueChanged.connect(
        lambda v: tab.bubble_big_size_max_label.setText(str(v))
    )
    row.addWidget(tab.bubble_big_size_max_label)
    _adv.addLayout(row)

    # Small Bubble Size Max (stored as 0.004–0.030 normalised UV, slider 4–30)
    row = QHBoxLayout()
    row.addWidget(QLabel("Small Bubble Max Size:"))
    tab.bubble_small_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_size_max.setMinimum(4)
    tab.bubble_small_size_max.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_size_max', 0.018) * 1000)
    tab.bubble_small_size_max.setValue(max(4, min(30, val)))
    tab.bubble_small_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_size_max.setTickInterval(5)
    tab.bubble_small_size_max.setToolTip("Maximum radius for small bubbles (normalised UV units × 1000).")
    tab.bubble_small_size_max.valueChanged.connect(tab._save_settings)
    row.addWidget(tab.bubble_small_size_max)
    tab.bubble_small_size_max_label = QLabel(f"{val}")
    tab.bubble_small_size_max.valueChanged.connect(
        lambda v: tab.bubble_small_size_max_label.setText(str(v))
    )
    row.addWidget(tab.bubble_small_size_max_label)
    _adv.addLayout(row)

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

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
    _adv.addLayout(row)

    # ── Styling ───────────────────────────────────────────────────
    _adv.addWidget(QLabel("<b>Styling</b>"))

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
    _adv.addLayout(row)

    # Colour pickers
    for attr_name, label_text, color_attr, title in (
        ("bubble_outline_color_btn", "Outline Colour", "_bubble_outline_color", "Choose Bubble Outline Color"),
        ("bubble_specular_color_btn", "Specular Colour", "_bubble_specular_color", "Choose Bubble Specular Color"),
        ("bubble_gradient_light_btn", "Gradient Light", "_bubble_gradient_light", "Choose Bubble Gradient Light"),
        ("bubble_gradient_dark_btn", "Gradient Dark", "_bubble_gradient_dark", "Choose Bubble Gradient Dark"),
        ("bubble_pop_color_btn", "Pop Colour", "_bubble_pop_color", "Choose Bubble Pop Color"),
    ):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label_text}:"))
        btn = ColorSwatchButton(title=title)
        btn.set_color(getattr(tab, color_attr, None))
        btn.color_changed.connect(
            lambda c, attr=color_attr: (setattr(tab, attr, c), tab._save_settings())
        )
        setattr(tab, attr_name, btn)
        row.addWidget(btn)
        row.addStretch()
        _adv.addLayout(row)

    # ── Card Height ─────────────────────────────────────────────────
    bubble_growth_row = QHBoxLayout()
    bubble_growth_row.addWidget(QLabel("Card Height:"))
    tab.bubble_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_growth.setMinimum(100)
    tab.bubble_growth.setMaximum(500)
    bubble_growth_val = int(tab._default_float('spotify_visualizer', 'bubble_growth', 3.0) * 100)
    tab.bubble_growth.setValue(max(100, min(500, bubble_growth_val)))
    tab.bubble_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_growth.setTickInterval(50)
    tab.bubble_growth.setToolTip("Height multiplier for the bubble card.")
    tab.bubble_growth.valueChanged.connect(tab._save_settings)
    bubble_growth_row.addWidget(tab.bubble_growth)
    tab.bubble_growth_label = QLabel(f"{bubble_growth_val / 100.0:.1f}x")
    tab.bubble_growth.valueChanged.connect(
        lambda v: tab.bubble_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    bubble_growth_row.addWidget(tab.bubble_growth_label)
    _adv.addLayout(bubble_growth_row)

    # ── Motion Trails ────────────────────────────────────────────────
    trail_row = QHBoxLayout()
    trail_row.addWidget(QLabel("Motion Trails:"))
    tab.bubble_trail_strength = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_trail_strength.setMinimum(0)
    tab.bubble_trail_strength.setMaximum(150)
    tab.bubble_trail_strength.setValue(0)
    tab.bubble_trail_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_trail_strength.setTickInterval(10)
    tab.bubble_trail_strength.setEnabled(False)
    tab.bubble_trail_strength.setToolTip(
        "Disabled while bubble trails are being reworked for gradient tapering."
    )
    trail_row.addWidget(tab.bubble_trail_strength)
    tab.bubble_trail_strength_label = QLabel("0%")
    tab.bubble_trail_strength_label.setEnabled(False)
    trail_row.addWidget(tab.bubble_trail_strength_label)
    disabled_msg = QLabel("(Temporarily unavailable – trails need gradient rework)")
    disabled_msg.setObjectName("bubbleTrailDisabledLabel")
    disabled_msg.setStyleSheet("color: rgba(255,255,255,110);")
    trail_row.addWidget(disabled_msg)
    _adv.addLayout(trail_row)

    layout.addWidget(tab._bubble_advanced)
    parent_layout.addWidget(tab._bubble_settings_container)
