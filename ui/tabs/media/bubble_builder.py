"""Bubble visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QWidget, QCheckBox,
)
from PySide6.QtCore import Qt

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import (
    add_aligned_row,
    add_aligned_row_widget,
)
from ui.widgets import StyledComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_bubble_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Bubble visualizer settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="bubble",
        settings_container_attr="_bubble_settings_container",
        preset_slider_attr="_bubble_preset_slider",
        normal_attr="_bubble_normal",
        advanced_host_attr="_bubble_advanced_host",
        advanced_toggle_attr="_bubble_adv_toggle",
        advanced_helper_attr="_bubble_adv_helper",
        advanced_attr="_bubble_advanced",
    )
    _normal_layout = scaffold.normal_layout
    _adv_layout = scaffold.advanced_layout

    _, appearance_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="bubble",
        bucket_key="appearance",
        title="Appearance",
        helper_text="Bubble shading, gradient direction, and color styling still apply when hidden.",
        default_expanded=True,
    )
    _, motion_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="bubble",
        bucket_key="motion",
        title="Motion",
        helper_text="Streaming, drift, swirl, and motion-tail controls still apply when hidden.",
        default_expanded=True,
    )
    _, bounce_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="bubble",
        bucket_key="bounce",
        title="Bounce",
        helper_text="Adjust collision rebound probability and speed by bubble class.",
        default_expanded=True,
    )
    _, reactivity_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="bubble",
        bucket_key="reactivity",
        title="Reactivity",
        helper_text="Audio-driven pulse behavior still applies when hidden.",
        default_expanded=False,
    )
    _, population_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="bubble",
        bucket_key="population",
        title="Population",
        helper_text="Bubble counts, size limits, and lifecycle controls still apply when hidden.",
        default_expanded=False,
    )
    _, layout_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="bubble",
        bucket_key="layout",
        title="Layout",
        helper_text="Card sizing still applies when hidden.",
        default_expanded=False,
    )
    _, ghost_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="bubble",
        bucket_key="ghost",
        title="Ghost",
        helper_text="Bubble ghosting still applies when hidden.",
        default_expanded=False,
    )

    LABEL_WIDTH = 150

    def _aligned_row_widget(
        parent_layout: QVBoxLayout,
        label_text: str,
        *,
        wrap: bool = True,
    ):
        row_widget, content, _ = add_aligned_row_widget(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
            wrap=wrap,
        )
        return row_widget, content

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str, *, wrap: bool = True):
        content, _ = add_aligned_row(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
            wrap=wrap,
        )
        return content

    def _swatch_row(parent_layout: QVBoxLayout, label_text: str):
        _, content, _ = add_builder_swatch_row(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return content

    bubble_bass_row = _aligned_row(reactivity_bucket, "Big Bubble Bass Pulse:")
    tab.bubble_big_bass_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_bass_pulse.setMinimum(0)
    tab.bubble_big_bass_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_bass_pulse', 0.5) * 100)
    tab.bubble_big_bass_pulse.setValue(val)
    tab.bubble_big_bass_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_bass_pulse.setTickInterval(50)
    bind_setting_signal(
        tab,
        tab.bubble_big_bass_pulse.valueChanged,
        updater=lambda v: tab.bubble_big_bass_pulse_label.setText(f"{v}%"),
    )
    bubble_bass_row.addWidget(tab.bubble_big_bass_pulse)
    tab.bubble_big_bass_pulse_label = QLabel(f"{val}%")
    bubble_bass_row.addWidget(tab.bubble_big_bass_pulse_label)

    bubble_freq_row = _aligned_row(reactivity_bucket, "Small Bubble Freq Pulse:")
    tab.bubble_small_freq_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_freq_pulse.setMinimum(0)
    tab.bubble_small_freq_pulse.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_freq_pulse', 0.5) * 100)
    tab.bubble_small_freq_pulse.setValue(val)
    tab.bubble_small_freq_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_freq_pulse.setTickInterval(50)
    bind_setting_signal(
        tab,
        tab.bubble_small_freq_pulse.valueChanged,
        updater=lambda v: tab.bubble_small_freq_pulse_label.setText(f"{v}%"),
    )
    bubble_freq_row.addWidget(tab.bubble_small_freq_pulse)
    tab.bubble_small_freq_pulse_label = QLabel(f"{val}%")
    bubble_freq_row.addWidget(tab.bubble_small_freq_pulse_label)

    tab._bubble_stream_direction_row_widget, stream_dir_row = _aligned_row_widget(motion_bucket, "Stream Direction:")
    tab.bubble_stream_direction = StyledComboBox(size_variant="compact")
    tab.bubble_stream_direction.addItems(["None", "Up", "Down", "Left", "Right", "Diagonal", "Random"])
    saved_dir = tab._default_str('spotify_visualizer', 'bubble_stream_direction', 'up').lower()
    dir_map = {"none": 0, "up": 1, "down": 2, "left": 3, "right": 4, "diagonal": 5, "random": 6}
    tab.bubble_stream_direction.setCurrentIndex(dir_map.get(saved_dir, 1))
    bind_setting_signal(tab, tab.bubble_stream_direction.currentIndexChanged)
    stream_dir_row.addWidget(tab.bubble_stream_direction)
    stream_dir_row.addStretch()

    stream_constant_row = _aligned_row(motion_bucket, "Stream Constant Speed:")
    tab.bubble_stream_constant_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_constant_speed.setMinimum(0)
    tab.bubble_stream_constant_speed.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_constant_speed', 0.5) * 100)
    tab.bubble_stream_constant_speed.setValue(val)
    tab.bubble_stream_constant_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_constant_speed.setTickInterval(25)
    bind_setting_signal(
        tab,
        tab.bubble_stream_constant_speed.valueChanged,
        updater=lambda v: tab.bubble_stream_constant_speed_label.setText(f"{v}%"),
    )
    stream_constant_row.addWidget(tab.bubble_stream_constant_speed)
    tab.bubble_stream_constant_speed_label = QLabel(f"{val}%")
    stream_constant_row.addWidget(tab.bubble_stream_constant_speed_label)

    stream_cap_row = _aligned_row(motion_bucket, "Stream Speed Cap:")
    tab.bubble_stream_speed_cap = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_speed_cap.setMinimum(50)
    tab.bubble_stream_speed_cap.setMaximum(400)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_speed_cap', 2.0) * 100)
    tab.bubble_stream_speed_cap.setValue(val)
    tab.bubble_stream_speed_cap.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_speed_cap.setTickInterval(25)
    bind_setting_signal(
        tab,
        tab.bubble_stream_speed_cap.valueChanged,
        updater=lambda v: tab.bubble_stream_speed_cap_label.setText(f"{v}%"),
    )
    stream_cap_row.addWidget(tab.bubble_stream_speed_cap)
    tab.bubble_stream_speed_cap_label = QLabel(f"{val}%")
    stream_cap_row.addWidget(tab.bubble_stream_speed_cap_label)

    stream_react_row = _aligned_row(motion_bucket, "Speed Reactivity:")
    tab.bubble_stream_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_stream_reactivity.setMinimum(0)
    tab.bubble_stream_reactivity.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_stream_reactivity', 0.5) * 100)
    tab.bubble_stream_reactivity.setValue(val)
    tab.bubble_stream_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_stream_reactivity.setTickInterval(50)
    bind_setting_signal(
        tab,
        tab.bubble_stream_reactivity.valueChanged,
        updater=lambda v: tab.bubble_stream_reactivity_label.setText(f"{v}%"),
    )
    stream_react_row.addWidget(tab.bubble_stream_reactivity)
    tab.bubble_stream_reactivity_label = QLabel(f"{val}%")
    stream_react_row.addWidget(tab.bubble_stream_reactivity_label)

    rotation_row = _aligned_row(motion_bucket, "Rotation Amount:")
    tab.bubble_rotation_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_rotation_amount.setMinimum(0)
    tab.bubble_rotation_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_rotation_amount', 0.5) * 100)
    tab.bubble_rotation_amount.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_rotation_amount.valueChanged,
        updater=lambda v: tab.bubble_rotation_amount_label.setText(f"{v}%"),
    )
    rotation_row.addWidget(tab.bubble_rotation_amount)
    tab.bubble_rotation_amount_label = QLabel(f"{val}%")
    rotation_row.addWidget(tab.bubble_rotation_amount_label)

    drift_amount_row = _aligned_row(motion_bucket, "Drift Amount:")
    tab.bubble_drift_amount = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_amount.setMinimum(0)
    tab.bubble_drift_amount.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_amount', 0.5) * 100)
    tab.bubble_drift_amount.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_drift_amount.valueChanged,
        updater=lambda v: tab.bubble_drift_amount_label.setText(f"{v}%"),
    )
    drift_amount_row.addWidget(tab.bubble_drift_amount)
    tab.bubble_drift_amount_label = QLabel(f"{val}%")
    drift_amount_row.addWidget(tab.bubble_drift_amount_label)

    drift_speed_row = _aligned_row(motion_bucket, "Drift Speed:")
    tab.bubble_drift_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_speed.setMinimum(0)
    tab.bubble_drift_speed.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_speed', 0.5) * 100)
    tab.bubble_drift_speed.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_drift_speed.valueChanged,
        updater=lambda v: tab.bubble_drift_speed_label.setText(f"{v}%"),
    )
    drift_speed_row.addWidget(tab.bubble_drift_speed)
    tab.bubble_drift_speed_label = QLabel(f"{val}%")
    drift_speed_row.addWidget(tab.bubble_drift_speed_label)

    drift_frequency_row = _aligned_row(motion_bucket, "Drift Frequency:")
    tab.bubble_drift_frequency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_drift_frequency.setMinimum(0)
    tab.bubble_drift_frequency.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_drift_frequency', 0.5) * 100)
    tab.bubble_drift_frequency.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_drift_frequency.valueChanged,
        updater=lambda v: tab.bubble_drift_frequency_label.setText(f"{v}%"),
    )
    drift_frequency_row.addWidget(tab.bubble_drift_frequency)
    tab.bubble_drift_frequency_label = QLabel(f"{val}%")
    drift_frequency_row.addWidget(tab.bubble_drift_frequency_label)

    tab._bubble_drift_direction_row_widget, drift_direction_row = _aligned_row_widget(motion_bucket, "Drift Direction:")
    tab.bubble_drift_direction = StyledComboBox(size_variant="compact")
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
    # If stored value is a swirl direction, default drift combo to "none"
    if saved_dd in ('swirl_cw', 'swirl_ccw'):
        dd_index = tab.bubble_drift_direction.findData('none')
    else:
        dd_index = tab.bubble_drift_direction.findData(saved_dd)
    if dd_index < 0:
        dd_index = tab.bubble_drift_direction.findData('random')
    tab.bubble_drift_direction.setCurrentIndex(max(0, dd_index))
    bind_setting_signal(tab, tab.bubble_drift_direction.currentIndexChanged)
    drift_direction_row.addWidget(tab.bubble_drift_direction)
    drift_direction_row.addStretch()

    swirl_row = _aligned_row(motion_bucket, "Swirl Mode:")
    tab.bubble_swirl_enabled = QCheckBox("Enable")
    tab.bubble_swirl_enabled.setProperty("circleIndicator", True)
    tab.bubble_swirl_enabled.setChecked(saved_dd in ('swirl_cw', 'swirl_ccw'))
    swirl_row.addWidget(tab.bubble_swirl_enabled)
    swirl_row.addStretch()

    tab._bubble_swirl_direction_row_widget, swirl_combo_row = _aligned_row_widget(motion_bucket, "", wrap=False)
    tab.bubble_swirl_direction = StyledComboBox(size_variant="compact")
    tab.bubble_swirl_direction.addItem("Clockwise", "swirl_cw")
    tab.bubble_swirl_direction.addItem("Counter-Clockwise", "swirl_ccw")
    if saved_dd == 'swirl_ccw':
        tab.bubble_swirl_direction.setCurrentIndex(1)
    else:
        tab.bubble_swirl_direction.setCurrentIndex(0)
    tab.bubble_swirl_direction.setEnabled(saved_dd in ('swirl_cw', 'swirl_ccw'))
    bind_setting_signal(tab, tab.bubble_swirl_direction.currentIndexChanged)
    swirl_combo_row.addWidget(tab.bubble_swirl_direction)
    swirl_combo_row.addStretch()

    def _on_swirl_toggled(checked: bool) -> None:
        tab.bubble_swirl_direction.setEnabled(checked)
        tab.bubble_drift_direction.setEnabled(not checked)
        tab.bubble_stream_direction.setEnabled(not checked)
        if hasattr(tab, "_bubble_swirl_direction_row_widget"):
            tab._bubble_swirl_direction_row_widget.setVisible(bool(checked))
        if hasattr(tab, "_bubble_drift_direction_row_widget"):
            tab._bubble_drift_direction_row_widget.setVisible(not checked)
        if hasattr(tab, "_bubble_stream_direction_row_widget"):
            tab._bubble_stream_direction_row_widget.setVisible(not checked)
        tab._save_settings()

    tab.bubble_swirl_enabled.toggled.connect(_on_swirl_toggled)
    # Apply initial enable/disable state
    _on_swirl_toggled(tab.bubble_swirl_enabled.isChecked())

    big_size_row = _aligned_row(population_bucket, "Big Bubble Size:")
    tab.bubble_big_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_size_max.setMinimum(10)
    tab.bubble_big_size_max.setMaximum(60)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_size_max', 0.038) * 1000)
    tab.bubble_big_size_max.setValue(max(10, min(60, val)))
    tab.bubble_big_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_size_max.setTickInterval(10)
    tab.bubble_big_size_max.setToolTip("Base starting radius for big bubbles. Actual size varies ±40% around this value.")
    bind_setting_signal(
        tab,
        tab.bubble_big_size_max.valueChanged,
        updater=lambda v: tab.bubble_big_size_max_label.setText(str(v)),
    )
    big_size_row.addWidget(tab.bubble_big_size_max)
    tab.bubble_big_size_max_label = QLabel(f"{val}")
    big_size_row.addWidget(tab.bubble_big_size_max_label)

    small_size_row = _aligned_row(population_bucket, "Small Bubble Size:")
    tab.bubble_small_size_max = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_size_max.setMinimum(4)
    tab.bubble_small_size_max.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_size_max', 0.018) * 1000)
    tab.bubble_small_size_max.setValue(max(4, min(30, val)))
    tab.bubble_small_size_max.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_small_size_max.setTickInterval(5)
    tab.bubble_small_size_max.setToolTip("Base starting radius for small bubbles. Actual size varies ±45% around this value.")
    bind_setting_signal(
        tab,
        tab.bubble_small_size_max.valueChanged,
        updater=lambda v: tab.bubble_small_size_max_label.setText(str(v)),
    )
    small_size_row.addWidget(tab.bubble_small_size_max)
    tab.bubble_small_size_max_label = QLabel(f"{val}")
    small_size_row.addWidget(tab.bubble_small_size_max_label)

    specular_max_row = _aligned_row(population_bucket, "Specular Max Size:")
    tab.bubble_big_specular_max_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_specular_max_size.setMinimum(50)
    tab.bubble_big_specular_max_size.setMaximum(500)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_specular_max_size', 2.5) * 100)
    tab.bubble_big_specular_max_size.setValue(max(50, min(500, val)))
    tab.bubble_big_specular_max_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_specular_max_size.setTickInterval(50)
    tab.bubble_big_specular_max_size.setToolTip(
        "Maximum specular highlight scale for big bubbles. "
        "Caps pulse-driven specular growth so highlights stay visually sane at large radii."
    )
    bind_setting_signal(
        tab,
        tab.bubble_big_specular_max_size.valueChanged,
        updater=lambda v: tab.bubble_big_specular_max_size_label.setText(f"{v / 100.0:.1f}x"),
    )
    specular_max_row.addWidget(tab.bubble_big_specular_max_size)
    tab.bubble_big_specular_max_size_label = QLabel(f"{val / 100.0:.1f}x")
    specular_max_row.addWidget(tab.bubble_big_specular_max_size_label)

    clamp_row = _aligned_row(population_bucket, "Max Pulse Clamp:")
    tab.bubble_big_size_clamp = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_size_clamp.setMinimum(150)
    tab.bubble_big_size_clamp.setMaximum(800)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_size_clamp', 4.0) * 100)
    tab.bubble_big_size_clamp.setValue(max(150, min(800, val)))
    tab.bubble_big_size_clamp.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_size_clamp.setTickInterval(50)
    tab.bubble_big_size_clamp.setToolTip(
        "Maximum pulse multiplier for big bubbles. Caps how large a bubble can grow "
        "during bass hits (e.g. 4.0x = bubble can grow up to 4× its base radius)."
    )
    bind_setting_signal(
        tab,
        tab.bubble_big_size_clamp.valueChanged,
        updater=lambda v: tab.bubble_big_size_clamp_label.setText(f"{v / 100.0:.1f}x"),
    )
    clamp_row.addWidget(tab.bubble_big_size_clamp)
    tab.bubble_big_size_clamp_label = QLabel(f"{val / 100.0:.1f}x")
    clamp_row.addWidget(tab.bubble_big_size_clamp_label)

    contraction_row = _aligned_row(population_bucket, "Contraction Bias:")
    tab.bubble_big_contraction_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_contraction_bias.setMinimum(0)
    tab.bubble_big_contraction_bias.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_contraction_bias', 1.0) * 100)
    tab.bubble_big_contraction_bias.setValue(max(0, min(100, val)))
    tab.bubble_big_contraction_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_big_contraction_bias.setTickInterval(10)
    tab.bubble_big_contraction_bias.setToolTip(
        "How much big bubbles shrink during quiet passages. "
        "100% = no contraction (default). Lower values make bubbles visibly breathe."
    )
    bind_setting_signal(
        tab,
        tab.bubble_big_contraction_bias.valueChanged,
        updater=lambda v: tab.bubble_big_contraction_bias_label.setText(f"{v}%"),
    )
    contraction_row.addWidget(tab.bubble_big_contraction_bias)
    tab.bubble_big_contraction_bias_label = QLabel(f"{val}%")
    contraction_row.addWidget(tab.bubble_big_contraction_bias_label)

    big_count_row = _aligned_row(population_bucket, "Big Bubbles:")
    tab.bubble_big_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_big_count.setMinimum(1)
    tab.bubble_big_count.setMaximum(30)
    val = int(tab._default_float('spotify_visualizer', 'bubble_big_count', 8))
    tab.bubble_big_count.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_big_count.valueChanged,
        updater=lambda v: tab.bubble_big_count_label.setText(str(v)),
    )
    big_count_row.addWidget(tab.bubble_big_count)
    tab.bubble_big_count_label = QLabel(str(val))
    big_count_row.addWidget(tab.bubble_big_count_label)

    small_count_row = _aligned_row(population_bucket, "Small Bubbles:")
    tab.bubble_small_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_small_count.setMinimum(5)
    tab.bubble_small_count.setMaximum(80)
    val = int(tab._default_float('spotify_visualizer', 'bubble_small_count', 25))
    tab.bubble_small_count.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_small_count.valueChanged,
        updater=lambda v: tab.bubble_small_count_label.setText(str(v)),
    )
    small_count_row.addWidget(tab.bubble_small_count)
    tab.bubble_small_count_label = QLabel(str(val))
    small_count_row.addWidget(tab.bubble_small_count_label)

    surface_reach_row = _aligned_row(population_bucket, "Surface Reach:")
    tab.bubble_surface_reach = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_surface_reach.setMinimum(0)
    tab.bubble_surface_reach.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_surface_reach', 0.6) * 100)
    tab.bubble_surface_reach.setValue(val)
    bind_setting_signal(
        tab,
        tab.bubble_surface_reach.valueChanged,
        updater=lambda v: tab.bubble_surface_reach_label.setText(f"{v}%"),
    )
    surface_reach_row.addWidget(tab.bubble_surface_reach)
    tab.bubble_surface_reach_label = QLabel(f"{val}%")
    surface_reach_row.addWidget(tab.bubble_surface_reach_label)

    bounce_big_pct_row = _aligned_row(bounce_bucket, "Big Bounce Chance:")
    tab.bubble_bounce_big_pct = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_bounce_big_pct.setMinimum(0)
    tab.bubble_bounce_big_pct.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_bounce_big_pct', 70))
    tab.bubble_bounce_big_pct.setValue(max(0, min(100, val)))
    tab.bubble_bounce_big_pct.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_bounce_big_pct.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.bubble_bounce_big_pct.valueChanged,
        updater=lambda v: tab.bubble_bounce_big_pct_label.setText(f"{v}%"),
    )
    bounce_big_pct_row.addWidget(tab.bubble_bounce_big_pct)
    tab.bubble_bounce_big_pct_label = QLabel(f"{val}%")
    bounce_big_pct_row.addWidget(tab.bubble_bounce_big_pct_label)

    bounce_small_pct_row = _aligned_row(bounce_bucket, "Small Bounce Chance:")
    tab.bubble_bounce_small_pct = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_bounce_small_pct.setMinimum(0)
    tab.bubble_bounce_small_pct.setMaximum(100)
    val = int(tab._default_float('spotify_visualizer', 'bubble_bounce_small_pct', 30))
    tab.bubble_bounce_small_pct.setValue(max(0, min(100, val)))
    tab.bubble_bounce_small_pct.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_bounce_small_pct.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.bubble_bounce_small_pct.valueChanged,
        updater=lambda v: tab.bubble_bounce_small_pct_label.setText(f"{v}%"),
    )
    bounce_small_pct_row.addWidget(tab.bubble_bounce_small_pct)
    tab.bubble_bounce_small_pct_label = QLabel(f"{val}%")
    bounce_small_pct_row.addWidget(tab.bubble_bounce_small_pct_label)

    bounce_big_speed_row = _aligned_row(bounce_bucket, "Big Bounce Speed:")
    tab.bubble_bounce_big_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_bounce_big_speed.setMinimum(0)
    tab.bubble_bounce_big_speed.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_bounce_big_speed', 0.8) * 100)
    tab.bubble_bounce_big_speed.setValue(max(0, min(200, val)))
    tab.bubble_bounce_big_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_bounce_big_speed.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.bubble_bounce_big_speed.valueChanged,
        updater=lambda v: tab.bubble_bounce_big_speed_label.setText(f"{v / 100.0:.2f}x"),
    )
    bounce_big_speed_row.addWidget(tab.bubble_bounce_big_speed)
    tab.bubble_bounce_big_speed_label = QLabel(f"{val / 100.0:.2f}x")
    bounce_big_speed_row.addWidget(tab.bubble_bounce_big_speed_label)

    bounce_small_speed_row = _aligned_row(bounce_bucket, "Small Bounce Speed:")
    tab.bubble_bounce_small_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_bounce_small_speed.setMinimum(0)
    tab.bubble_bounce_small_speed.setMaximum(200)
    val = int(tab._default_float('spotify_visualizer', 'bubble_bounce_small_speed', 0.5) * 100)
    tab.bubble_bounce_small_speed.setValue(max(0, min(200, val)))
    tab.bubble_bounce_small_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_bounce_small_speed.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.bubble_bounce_small_speed.valueChanged,
        updater=lambda v: tab.bubble_bounce_small_speed_label.setText(f"{v / 100.0:.2f}x"),
    )
    bounce_small_speed_row.addWidget(tab.bubble_bounce_small_speed)
    tab.bubble_bounce_small_speed_label = QLabel(f"{val / 100.0:.2f}x")
    bounce_small_speed_row.addWidget(tab.bubble_bounce_small_speed_label)

    specular_row = _aligned_row(appearance_bucket, "Specular Direction:")
    tab.bubble_specular_direction = StyledComboBox(size_variant="mini")
    tab.bubble_gradient_direction = StyledComboBox(size_variant="mini")
    direction_options = [
        ("Top", "top"),
        ("Bottom", "bottom"),
        ("Left", "left"),
        ("Right", "right"),
        ("Top Left", "top_left"),
        ("Top Right", "top_right"),
        ("Bottom Left", "bottom_left"),
        ("Bottom Right", "bottom_right"),
    ]
    for label, key in direction_options:
        tab.bubble_specular_direction.addItem(label, key)
        tab.bubble_gradient_direction.addItem(label, key)
    tab.bubble_gradient_direction.addItem("Center Out", "center_out")
    tab.bubble_gradient_direction.addItem("Center Out Reverse", "center_out_reverse")

    saved_sd = tab._default_str('spotify_visualizer', 'bubble_specular_direction', 'top_left').lower()
    idx = tab.bubble_specular_direction.findData(saved_sd)
    if idx < 0:
        idx = 0
    tab.bubble_specular_direction.setCurrentIndex(idx)
    tab.bubble_specular_direction.currentIndexChanged.connect(tab._save_settings)
    specular_row.addWidget(tab.bubble_specular_direction)

    gradient_row = _aligned_row(appearance_bucket, "Gradient Direction:")
    saved_gd = tab._default_str('spotify_visualizer', 'bubble_gradient_direction', 'top').lower()
    gidx = tab.bubble_gradient_direction.findData(saved_gd)
    if gidx < 0:
        gidx = tab.bubble_gradient_direction.findData('top')
    if gidx < 0:
        gidx = 0
    tab.bubble_gradient_direction.setCurrentIndex(gidx)
    tab.bubble_gradient_direction.currentIndexChanged.connect(tab._save_settings)
    gradient_row.addWidget(tab.bubble_gradient_direction)
    gradient_row.addStretch()
    specular_row.addStretch()

    for attr_name, label_text, color_attr, title in (
        ("bubble_outline_color_btn", "Outline Colour", "_bubble_outline_color", "Choose Bubble Outline Color"),
        ("bubble_specular_color_btn", "Specular Colour", "_bubble_specular_color", "Choose Bubble Specular Color"),
        ("bubble_gradient_light_btn", "Gradient Light", "_bubble_gradient_light", "Choose Bubble Gradient Light"),
        ("bubble_gradient_dark_btn", "Gradient Dark", "_bubble_gradient_dark", "Choose Bubble Gradient Dark"),
        ("bubble_pop_color_btn", "Pop Colour", "_bubble_pop_color", "Choose Bubble Pop Color"),
    ):
        color_row = _swatch_row(appearance_bucket, f"{label_text}:")
        btn = ColorSwatchButton(title=title)
        bind_color_button(
            tab,
            btn,
            color_attr,
            initial_color=getattr(tab, color_attr, None),
        )
        setattr(tab, attr_name, btn)
        color_row.addWidget(btn)
        color_row.addStretch()

    bubble_growth_row = _aligned_row(layout_bucket, "Card Height:")
    tab.bubble_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_growth.setMinimum(100)
    tab.bubble_growth.setMaximum(500)
    bubble_growth_val = int(tab._default_float('spotify_visualizer', 'bubble_growth', 3.0) * 100)
    tab.bubble_growth.setValue(max(100, min(500, bubble_growth_val)))
    tab.bubble_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_growth.setTickInterval(50)
    tab.bubble_growth.setToolTip("Height multiplier for the bubble card.")
    bind_setting_signal(
        tab,
        tab.bubble_growth.valueChanged,
        updater=lambda v: tab.bubble_growth_label.setText(f"{v / 100.0:.1f}x"),
    )
    bubble_growth_row.addWidget(tab.bubble_growth)
    tab.bubble_growth_label = QLabel(f"{bubble_growth_val / 100.0:.1f}x")
    bubble_growth_row.addWidget(tab.bubble_growth_label)

    tail_len_row = _aligned_row(motion_bucket, "Tail Length:")
    tab.bubble_trail_strength = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_trail_strength.setMinimum(0)
    tab.bubble_trail_strength.setMaximum(150)
    tab.bubble_trail_strength.setValue(0)
    tab.bubble_trail_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_trail_strength.setTickInterval(10)
    tab.bubble_trail_strength.setToolTip(
        "How long the motion tail stretches behind each bubble (0 = off)."
    )
    bind_setting_signal(
        tab,
        tab.bubble_trail_strength.valueChanged,
        updater=lambda v: tab.bubble_trail_strength_label.setText(f"{v}%"),
    )
    tail_len_row.addWidget(tab.bubble_trail_strength)
    tab.bubble_trail_strength_label = QLabel("0%")
    tail_len_row.addWidget(tab.bubble_trail_strength_label)

    tail_opa_row = _aligned_row(motion_bucket, "Tail Opacity:")
    tab.bubble_tail_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_tail_opacity.setMinimum(0)
    tab.bubble_tail_opacity.setMaximum(85)
    tab.bubble_tail_opacity.setValue(0)
    tab.bubble_tail_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_tail_opacity.setTickInterval(5)
    tab.bubble_tail_opacity.setToolTip(
        "Maximum opacity of the tail gradient (0 = off). Always somewhat translucent."
    )
    bind_setting_signal(
        tab,
        tab.bubble_tail_opacity.valueChanged,
        updater=lambda v: tab.bubble_tail_opacity_label.setText(f"{v}%"),
    )
    tail_opa_row.addWidget(tab.bubble_tail_opacity)
    tab.bubble_tail_opacity_label = QLabel("0%")
    tail_opa_row.addWidget(tab.bubble_tail_opacity_label)

    bubble_ghost_toggle_row = _aligned_row(ghost_bucket, "")
    tab.bubble_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.bubble_ghost_enabled.setProperty("circleIndicator", True)
    tab.bubble_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'bubble_ghosting_enabled', False)
    )
    tab.bubble_ghost_enabled.setToolTip(
        "Show a fading afterimage trail behind moving bubbles."
    )
    bind_setting_signal(tab, tab.bubble_ghost_enabled.stateChanged)
    bubble_ghost_toggle_row.addWidget(tab.bubble_ghost_enabled)
    bubble_ghost_toggle_row.addStretch()

    tab._bubble_ghost_sub = QWidget()
    _bubble_ghost_layout = QVBoxLayout(tab._bubble_ghost_sub)
    _bubble_ghost_layout.setContentsMargins(0, 0, 0, 12)
    _bubble_ghost_layout.setSpacing(12)

    bg_opa_widget, bg_opa_row = _aligned_row_widget(_bubble_ghost_layout, "Ghost Opacity:")
    tab.bubble_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_ghost_opacity.setMinimum(0)
    tab.bubble_ghost_opacity.setMaximum(100)
    _bg_alpha_pct = int(tab._default_float('spotify_visualizer', 'bubble_ghost_alpha', 0.0) * 100)
    tab.bubble_ghost_opacity.setValue(max(0, min(100, _bg_alpha_pct)))
    tab.bubble_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_ghost_opacity.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.bubble_ghost_opacity.valueChanged,
        updater=lambda v: tab.bubble_ghost_opacity_label.setText(f"{v}%"),
    )
    bg_opa_row.addWidget(tab.bubble_ghost_opacity)
    tab.bubble_ghost_opacity_label = QLabel(f"{_bg_alpha_pct}%")
    bg_opa_row.addWidget(tab.bubble_ghost_opacity_label)

    bg_dec_widget, bg_dec_row = _aligned_row_widget(_bubble_ghost_layout, "Ghost Decay:")
    tab.bubble_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.bubble_ghost_decay_slider.setMinimum(10)
    tab.bubble_ghost_decay_slider.setMaximum(100)
    _bg_decay_pct = int(tab._default_float('spotify_visualizer', 'bubble_ghost_decay', 0.4) * 100)
    tab.bubble_ghost_decay_slider.setValue(max(10, min(100, _bg_decay_pct)))
    tab.bubble_ghost_decay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.bubble_ghost_decay_slider.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.bubble_ghost_decay_slider.valueChanged,
        updater=lambda v: tab.bubble_ghost_decay_label.setText(f"{v / 100.0:.2f}x"),
    )
    bg_dec_row.addWidget(tab.bubble_ghost_decay_slider)
    tab.bubble_ghost_decay_label = QLabel(f"{tab.bubble_ghost_decay_slider.value() / 100.0:.2f}x")
    bg_dec_row.addWidget(tab.bubble_ghost_decay_label)

    ghost_bucket.addWidget(tab._bubble_ghost_sub)

    def _update_bubble_ghost_vis(_s=None):
        tab._bubble_ghost_sub.setVisible(tab.bubble_ghost_enabled.isChecked())
    tab.bubble_ghost_enabled.stateChanged.connect(_update_bubble_ghost_vis)
    _update_bubble_ghost_vis()

