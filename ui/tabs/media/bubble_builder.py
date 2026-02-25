"""Bubble visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QSlider, QWidget, QToolButton,
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

    tab._bubble_normal = QWidget()
    _normal_layout = QVBoxLayout(tab._bubble_normal)
    _normal_layout.setContentsMargins(0, 0, 0, 0)
    _normal_layout.setSpacing(6)
    layout.addWidget(tab._bubble_normal)

    tab._bubble_advanced_host = QWidget()
    _adv_host = QVBoxLayout(tab._bubble_advanced_host)
    _adv_host.setContentsMargins(0, 0, 0, 0)
    _adv_host.setSpacing(4)
    layout.addWidget(tab._bubble_advanced_host)

    _adv_toggle_row = QHBoxLayout()
    _adv_toggle_row.setContentsMargins(0, 0, 0, 0)
    _adv_toggle_row.setSpacing(4)
    tab._bubble_adv_toggle = QToolButton()
    tab._bubble_adv_toggle.setText("Advanced")
    tab._bubble_adv_toggle.setCheckable(True)
    tab._bubble_adv_toggle.setChecked(True)
    tab._bubble_adv_toggle.setArrowType(Qt.DownArrow)
    tab._bubble_adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    tab._bubble_adv_toggle.setAutoRaise(True)
    _adv_toggle_row.addWidget(tab._bubble_adv_toggle)
    _adv_toggle_row.addStretch()
    _adv_host.addLayout(_adv_toggle_row)

    tab._bubble_adv_helper = QLabel("Advanced sliders still apply when hidden.")
    tab._bubble_adv_helper.setProperty("class", "adv-helper")
    tab._bubble_adv_helper.setStyleSheet("color: rgba(220,220,220,0.6); font-size: 11px;")
    _adv_host.addWidget(tab._bubble_adv_helper)

    tab._bubble_advanced = QWidget()
    _adv_layout = QVBoxLayout(tab._bubble_advanced)
    _adv_layout.setContentsMargins(0, 0, 0, 0)
    _adv_layout.setSpacing(4)
    _adv_host.addWidget(tab._bubble_advanced)

    tab._bubble_preset_slider.set_advanced_container(tab._bubble_advanced_host)

    def _apply_bubble_adv_toggle_state(checked: bool) -> None:
        tab._bubble_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._bubble_advanced.setVisible(checked)
        tab._bubble_adv_helper.setVisible(not checked)

    tab._bubble_adv_toggle.toggled.connect(_apply_bubble_adv_toggle_state)
    _apply_bubble_adv_toggle_state(tab._bubble_adv_toggle.isChecked())

    def _handle_bubble_preset_adv(is_custom: bool) -> None:
        tab._bubble_advanced_host.setVisible(is_custom)

    tab._bubble_preset_slider.advanced_toggled.connect(_handle_bubble_preset_adv)
    _handle_bubble_preset_adv(True)

    LABEL_WIDTH = 150

    def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        label = QLabel(label_text)
        label.setFixedWidth(LABEL_WIDTH)
        row_layout.addWidget(label)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        row_layout.addLayout(content, 1)
        parent_layout.addWidget(row_widget)
        return row_widget, content

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str):
        _, content = _aligned_row_widget(parent_layout, label_text)
        return content

    # ── Audio Reactivity ──────────────────────────────────────────────
    _adv_layout.addWidget(QLabel("<b>Audio Reactivity</b>"))

    bubble_bass_row = _aligned_row(_adv_layout, "Big Bubble Bass Pulse:")
    tab.bubble_big_bass_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_bass_pulse.setMinimum(0)
    tab.bubble_big_bass_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_bass_pulse', 0.5) * 100)
    tab.bubble_big_bass_pulse.setValue(val)
    tab.bubble_big_bass_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_bass_pulse.setTickInterval(50)
    tab.bubble_big_bass_pulse.valueChanged.connect(tab._save_settings)
    bubble_bass_row.addWidget(tab.bubble_big_bass_pulse)
    tab.bubble_big_bass_pulse_label = QLabel(f"{val}%")
    tab.bubble_big_bass_pulse.valueChanged.connect(
        lambda v: tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    )
    bubble_bass_row.addWidget(tab.bubble_big_bass_pulse_label)

    bubble_freq_row = _aligned_row(_adv_layout, "Small Bubble Freq Pulse:")
    tab.bubble_small_freq_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_freq_pulse.setMinimum(0)
    tab.bubble_small_freq_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_freq_pulse', 0.5) * 100)
    tab.bubble_small_freq_pulse.setValue(val)
    tab.bubble_small_freq_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_freq_pulse.setTickInterval(50)
    tab.bubble_small_freq_pulse.valueChanged.connect(tab._save_settings)
    bubble_freq_row.addWidget(tab.bubble_small_freq_pulse)
    tab.bubble_small_freq_pulse_label = QLabel(f"{val}%")
    tab.bubble_small_freq_pulse.valueChanged.connect(
        lambda v: tab.bubble_small_freq_pulse_label.setText(f"{v}%")
    )
    bubble_freq_row.addWidget(tab.bubble_small_freq_pulse_label)

    # ── Stream Controls ───────────────────────────────────────────
    _adv_layout.addWidget(QLabel("<b>Stream Controls</b>"))

    stream_dir_row = _aligned_row(_adv_layout, "Stream Direction:")
    tab.bubble_stream_direction = QComboBox()
    tab.bubble_stream_direction.addItems(["None", "Up", "Down", "Left", "Right", "Diagonal", "Random"])
    saved_dir = tab._default_str('spotify_visualizer', 'bubble_stream_direction', 'up').lower()
    dir_map = {"none": 0, "up": 1, "down": 2, "left": 3, "right": 4, "diagonal": 5, "random": 6}
    tab.bubble_stream_direction.setCurrentIndex(dir_map.get(saved_dir, 1))
    tab.bubble_stream_direction.currentIndexChanged.connect(tab._save_settings)
    stream_dir_row.addWidget(tab.bubble_stream_direction)
    stream_dir_row.addStretch()

    stream_constant_row = _aligned_row(_adv_layout, "Stream Constant Speed:")
    tab.bubble_stream_constant_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_constant_speed.setMinimum(0)
    tab.bubble_stream_constant_speed.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_constant_speed', 0.5) * 100)
    tab.bubble_stream_constant_speed.setValue(val)
    tab.bubble_stream_constant_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_constant_speed.setTickInterval(25)
    tab.bubble_stream_constant_speed.valueChanged.connect(tab._save_settings)
    stream_constant_row.addWidget(tab.bubble_stream_constant_speed)
    tab.bubble_stream_constant_speed_label = QLabel(f"{val}%")
    tab.bubble_stream_constant_speed.valueChanged.connect(
        lambda v: tab.bubble_stream_constant_speed_label.setText(f"{v}%")
    )
    stream_constant_row.addWidget(tab.bubble_stream_constant_speed_label)

    stream_cap_row = _aligned_row(_adv_layout, "Stream Speed Cap:")
    tab.bubble_stream_speed_cap = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_speed_cap.setMinimum(50)
    tab.bubble_stream_speed_cap.setMaximum(400)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_speed_cap', 2.0) * 100)
    tab.bubble_stream_speed_cap.setValue(val)
    tab.bubble_stream_speed_cap.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_speed_cap.setTickInterval(25)
    tab.bubble_stream_speed_cap.valueChanged.connect(tab._save_settings)
    stream_cap_row.addWidget(tab.bubble_stream_speed_cap)
    tab.bubble_stream_speed_cap_label = QLabel(f"{val}%")
    tab.bubble_stream_speed_cap.valueChanged.connect(
        lambda v: tab.bubble_stream_speed_cap_label.setText(f"{v}%")
    )
    stream_cap_row.addWidget(tab.bubble_stream_speed_cap_label)

    stream_react_row = _aligned_row(_adv_layout, "Speed Reactivity:")
    tab.bubble_stream_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_reactivity.setMinimum(0)
    tab.bubble_stream_reactivity.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_reactivity', 0.5) * 100)
    tab.bubble_stream_reactivity.setValue(val)
    tab.bubble_stream_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_reactivity.setTickInterval(25)
    tab.bubble_stream_reactivity.valueChanged.connect(tab._save_settings)
    stream_react_row.addWidget(tab.bubble_stream_reactivity)
    tab.bubble_stream_reactivity_label = QLabel(f"{val}%")
    tab.bubble_stream_reactivity.valueChanged.connect(
        lambda v: tab.bubble_stream_reactivity_label.setText(f"{v}%")
    )
    stream_react_row.addWidget(tab.bubble_stream_reactivity_label)

    # ── Drift & Rotation ──────────────────────────────────────────
    _adv_layout.addWidget(QLabel("<b>Drift & Rotation</b>"))

    rotation_row = _aligned_row(_adv_layout, "Rotation Amount:")
    tab.bubble_rotation_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_rotation_amount.setMinimum(0)
    tab.bubble_rotation_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_rotation_amount', 0.5) * 100)
    tab.bubble_rotation_amount.setValue(val)
    tab.bubble_rotation_amount.valueChanged.connect(tab._save_settings)
    rotation_row.addWidget(tab.bubble_rotation_amount)
    tab.bubble_rotation_amount_label = QLabel(f"{val}%")
    tab.bubble_rotation_amount.valueChanged.connect(
        lambda v: tab.bubble_rotation_amount_label.setText(f"{v}%")
    )
    rotation_row.addWidget(tab.bubble_rotation_amount_label)

    drift_amount_row = _aligned_row(_adv_layout, "Drift Amount:")
    tab.bubble_drift_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_amount.setMinimum(0)
    tab.bubble_drift_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_amount', 0.5) * 100)
    tab.bubble_drift_amount.setValue(val)
    tab.bubble_drift_amount.valueChanged.connect(tab._save_settings)
    drift_amount_row.addWidget(tab.bubble_drift_amount)
    tab.bubble_drift_amount_label = QLabel(f"{val}%")
    tab.bubble_drift_amount.valueChanged.connect(
        lambda v: tab.bubble_drift_amount_label.setText(f"{v}%")
    )
    drift_amount_row.addWidget(tab.bubble_drift_amount_label)

    drift_speed_row = _aligned_row(_adv_layout, "Drift Speed:")
    tab.bubble_drift_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_speed.setMinimum(0)
    tab.bubble_drift_speed.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_speed', 0.5) * 100)
    tab.bubble_drift_speed.setValue(val)
    tab.bubble_drift_speed.valueChanged.connect(tab._save_settings)
    drift_speed_row.addWidget(tab.bubble_drift_speed)
    tab.bubble_drift_speed_label = QLabel(f"{val}%")
    tab.bubble_drift_speed.valueChanged.connect(
        lambda v: tab.bubble_drift_speed_label.setText(f"{v}%")
    )
    drift_speed_row.addWidget(tab.bubble_drift_speed_label)

    drift_frequency_row = _aligned_row(_adv_layout, "Drift Frequency:")
    tab.bubble_drift_frequency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_frequency.setMinimum(0)
    tab.bubble_drift_frequency.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_frequency', 0.5) * 100)
    tab.bubble_drift_frequency.setValue(val)
    tab.bubble_drift_frequency.valueChanged.connect(tab._save_settings)
    drift_frequency_row.addWidget(tab.bubble_drift_frequency)
    tab.bubble_drift_frequency_label = QLabel(f"{val}%")
    tab.bubble_drift_frequency.valueChanged.connect(
        lambda v: tab.bubble_drift_frequency_label.setText(f"{v}%")
    )
    drift_frequency_row.addWidget(tab.bubble_drift_frequency_label)

    drift_direction_row = _aligned_row(_adv_layout, "Drift Direction:")
    tab.bubble_drift_direction = QComboBox()
    drift_options = [
        ("None", "none"),
        ("Left", "left"),
        ("Right", "right"),
        ("Diagonal", "diagonal"),
        ("Swish (Horizontal)", "swish_horizontal"),
        ("Swish (Vertical)", "swish_vertical"),
        ("Random", "random"),
    ]
    for label, value in drift_options:
        tab.bubble_drift_direction.addItem(label, value)
    saved_dd = tab._default_str('spotify_visualizer', 'bubble_drift_direction', 'random').lower()
    dd_index = tab.bubble_drift_direction.findData(saved_dd)
    if dd_index < 0:
        dd_index = tab.bubble_drift_direction.findData('random')
    tab.bubble_drift_direction.setCurrentIndex(max(0, dd_index))
    tab.bubble_drift_direction.currentIndexChanged.connect(tab._save_settings)
    drift_direction_row.addWidget(tab.bubble_drift_direction)
    drift_direction_row.addStretch()

    # ── Bubble Count & Lifecycle ──────────────────────────────────
    _adv_layout.addWidget(QLabel("<b>Bubble Count & Lifecycle</b>"))

    big_size_row = _aligned_row(_adv_layout, "Big Bubble Max Size:")
    tab.bubble_big_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_size_max.setMinimum(10)
    tab.bubble_big_size_max.setMaximum(60)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_size_max', 0.038) * 1000)
    tab.bubble_big_size_max.setValue(max(10, min(60, val)))
    tab.bubble_big_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_size_max.setTickInterval(10)
    tab.bubble_big_size_max.setToolTip("Maximum radius for big bubbles (normalised UV units × 1000).")
    tab.bubble_big_size_max.valueChanged.connect(tab._save_settings)
    big_size_row.addWidget(tab.bubble_big_size_max)
    tab.bubble_big_size_max_label = QLabel(f"{val}")
    tab.bubble_big_size_max.valueChanged.connect(
        lambda v: tab.bubble_big_size_max_label.setText(str(v))
    )
    big_size_row.addWidget(tab.bubble_big_size_max_label)

    small_size_row = _aligned_row(_adv_layout, "Small Bubble Max Size:")
    tab.bubble_small_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_size_max.setMinimum(4)
    tab.bubble_small_size_max.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_size_max', 0.018) * 1000)
    tab.bubble_small_size_max.setValue(max(4, min(30, val)))
    tab.bubble_small_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_size_max.setTickInterval(5)
    tab.bubble_small_size_max.setToolTip("Maximum radius for small bubbles (normalised UV units × 1000).")
    tab.bubble_small_size_max.valueChanged.connect(tab._save_settings)
    small_size_row.addWidget(tab.bubble_small_size_max)
    tab.bubble_small_size_max_label = QLabel(f"{val}")
    tab.bubble_small_size_max.valueChanged.connect(
        lambda v: tab.bubble_small_size_max_label.setText(str(v))
    )
    small_size_row.addWidget(tab.bubble_small_size_max_label)

    big_count_row = _aligned_row(_adv_layout, "Big Bubbles:")
    tab.bubble_big_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_count.setMinimum(1)
    tab.bubble_big_count.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_count', 8))
    tab.bubble_big_count.setValue(val)
    tab.bubble_big_count.valueChanged.connect(tab._save_settings)
    big_count_row.addWidget(tab.bubble_big_count)
    tab.bubble_big_count_label = QLabel(str(val))
    tab.bubble_big_count.valueChanged.connect(
        lambda v: tab.bubble_big_count_label.setText(str(v))
    )
    big_count_row.addWidget(tab.bubble_big_count_label)

    small_count_row = _aligned_row(_adv_layout, "Small Bubbles:")
    tab.bubble_small_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_count.setMinimum(5)
    tab.bubble_small_count.setMaximum(80)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_count', 25))
    tab.bubble_small_count.setValue(val)
    tab.bubble_small_count.valueChanged.connect(tab._save_settings)
    small_count_row.addWidget(tab.bubble_small_count)
    tab.bubble_small_count_label = QLabel(str(val))
    tab.bubble_small_count.valueChanged.connect(
        lambda v: tab.bubble_small_count_label.setText(str(v))
    )
    small_count_row.addWidget(tab.bubble_small_count_label)

    surface_reach_row = _aligned_row(_adv_layout, "Surface Reach:")
    tab.bubble_surface_reach = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_surface_reach.setMinimum(0)
    tab.bubble_surface_reach.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_surface_reach', 0.6) * 100)
    tab.bubble_surface_reach.setValue(val)
    tab.bubble_surface_reach.valueChanged.connect(tab._save_settings)
    surface_reach_row.addWidget(tab.bubble_surface_reach)
    tab.bubble_surface_reach_label = QLabel(f"{val}%")
    tab.bubble_surface_reach.valueChanged.connect(
        lambda v: tab.bubble_surface_reach_label.setText(f"{v}%")
    )
    surface_reach_row.addWidget(tab.bubble_surface_reach_label)

    # ── Styling ───────────────────────────────────────────────────
    _normal_layout.addWidget(QLabel("<b>Styling</b>"))

    specular_row = _aligned_row(_normal_layout, "Specular Direction:")
    tab.bubble_specular_direction = QComboBox()
    tab.bubble_specular_direction.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
    saved_sd = tab._default_str('spotify_visualizer', 'bubble_specular_direction', 'top_left').lower()
    sd_map = {"top_left": 0, "top_right": 1, "bottom_left": 2, "bottom_right": 3}
    tab.bubble_specular_direction.setCurrentIndex(sd_map.get(saved_sd, 0))
    tab.bubble_specular_direction.currentIndexChanged.connect(tab._save_settings)
    specular_row.addWidget(tab.bubble_specular_direction)
    specular_row.addStretch()

    for attr_name, label_text, color_attr, title in (
        ("bubble_outline_color_btn", "Outline Colour", "_bubble_outline_color", "Choose Bubble Outline Color"),
        ("bubble_specular_color_btn", "Specular Colour", "_bubble_specular_color", "Choose Bubble Specular Color"),
        ("bubble_gradient_light_btn", "Gradient Light", "_bubble_gradient_light", "Choose Bubble Gradient Light"),
        ("bubble_gradient_dark_btn", "Gradient Dark", "_bubble_gradient_dark", "Choose Bubble Gradient Dark"),
        ("bubble_pop_color_btn", "Pop Colour", "_bubble_pop_color", "Choose Bubble Pop Color"),
    ):
        color_row = _aligned_row(_normal_layout, f"{label_text}:")
        btn = ColorSwatchButton(title=title)
        btn.set_color(getattr(tab, color_attr, None))
        btn.color_changed.connect(
            lambda c, attr=color_attr: (setattr(tab, attr, c), tab._save_settings())
        )
        setattr(tab, attr_name, btn)
        color_row.addWidget(btn)
        color_row.addStretch()

    # ── Card Height ─────────────────────────────────────────────────
    bubble_growth_row = _aligned_row(_adv_layout, "Card Height:")
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

    # ── Motion Trails ────────────────────────────────────────────────
    trail_row = _aligned_row(_adv_layout, "Motion Trails:")
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

    parent_layout.addWidget(tab._bubble_settings_container)
