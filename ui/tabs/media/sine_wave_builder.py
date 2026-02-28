"""Sine Wave visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider, QWidget, QToolButton,
)
from ui.styled_popup import ColorSwatchButton
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _update_sine_multi_line_visibility(tab) -> None:
    enabled = getattr(tab, 'sine_multi_line', None) and tab.sine_multi_line.isChecked()
    container = getattr(tab, '_sine_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    line_count = getattr(tab, 'sine_line_count_slider', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_sine_line3_label', None), getattr(tab, '_sine_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


def build_sine_wave_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Sine Wave settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._sine_wave_settings_container = QWidget()
    sine_layout = QVBoxLayout(tab._sine_wave_settings_container)
    sine_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._sine_preset_slider = VisualizerPresetSlider("sine_wave")
    tab._sine_preset_slider.preset_changed.connect(tab._save_settings)
    sine_layout.addWidget(tab._sine_preset_slider)

    tab._sine_normal = QWidget()
    _normal = QVBoxLayout(tab._sine_normal)
    _normal.setContentsMargins(0, 0, 0, 0)
    _normal.setSpacing(4)
    sine_layout.addWidget(tab._sine_normal)

    tab._sine_advanced_host = QWidget()
    _adv_host = QVBoxLayout(tab._sine_advanced_host)
    _adv_host.setContentsMargins(0, 0, 0, 0)
    _adv_host.setSpacing(4)
    sine_layout.addWidget(tab._sine_advanced_host)

    _adv_toggle_row = QHBoxLayout()
    _adv_toggle_row.setContentsMargins(0, 0, 0, 0)
    _adv_toggle_row.setSpacing(4)
    tab._sine_adv_toggle = QToolButton()
    tab._sine_adv_toggle.setText("Advanced")
    tab._sine_adv_toggle.setCheckable(True)
    tab._sine_adv_toggle.setChecked(True)
    tab._sine_adv_toggle.setArrowType(Qt.DownArrow)
    tab._sine_adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    tab._sine_adv_toggle.setAutoRaise(True)
    _adv_toggle_row.addWidget(tab._sine_adv_toggle)
    _adv_toggle_row.addStretch()
    _adv_host.addLayout(_adv_toggle_row)

    tab._sine_adv_helper = QLabel("Advanced sliders still apply when hidden.")
    tab._sine_adv_helper.setProperty("class", "adv-helper")
    tab._sine_adv_helper.setStyleSheet("color: rgba(220,220,220,0.6); font-size: 11px;")
    _adv_host.addWidget(tab._sine_adv_helper)

    tab._sine_advanced = QWidget()
    _adv = QVBoxLayout(tab._sine_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    _adv_host.addWidget(tab._sine_advanced)

    tab._sine_preset_slider.set_advanced_container(tab._sine_advanced_host)

    def _apply_sine_adv_toggle_state(checked: bool) -> None:
        tab._sine_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._sine_advanced.setVisible(checked)
        tab._sine_adv_helper.setVisible(not checked)

    tab._sine_adv_toggle.toggled.connect(_apply_sine_adv_toggle_state)
    _apply_sine_adv_toggle_state(tab._sine_adv_toggle.isChecked())

    def _handle_sine_preset_adv(is_custom: bool) -> None:
        tab._sine_advanced_host.setVisible(is_custom)

    tab._sine_preset_slider.advanced_toggled.connect(_handle_sine_preset_adv)
    _handle_sine_preset_adv(True)

    LABEL_WIDTH = 150

    def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str) -> tuple[QWidget, QHBoxLayout]:
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

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str) -> QHBoxLayout:
        _, content = _aligned_row_widget(parent_layout, label_text)
        return content

    # Glow
    tab.sine_glow_enabled = QCheckBox("Enable Glow")
    tab.sine_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'sine_glow_enabled', True))
    tab.sine_glow_enabled.stateChanged.connect(tab._save_settings)
    _normal.addWidget(tab.sine_glow_enabled)

    tab._sine_glow_widgets: list[QWidget] = []

    glow_intensity_widget, sine_glow_row = _aligned_row_widget(_normal, "Glow Intensity:")
    tab._sine_glow_widgets.append(glow_intensity_widget)
    tab.sine_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_glow_intensity.setMinimum(0)
    tab.sine_glow_intensity.setMaximum(100)
    sine_glow_val = int(tab._default_float('spotify_visualizer', 'sine_glow_intensity', 0.5) * 100)
    tab.sine_glow_intensity.setValue(sine_glow_val)
    tab.sine_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_glow_intensity.setTickInterval(10)
    tab.sine_glow_intensity.valueChanged.connect(tab._save_settings)
    sine_glow_row.addWidget(tab.sine_glow_intensity)
    tab.sine_glow_intensity_label = QLabel(f"{sine_glow_val}%")
    tab.sine_glow_intensity.valueChanged.connect(
        lambda v: tab.sine_glow_intensity_label.setText(f"{v}%")
    )
    sine_glow_row.addWidget(tab.sine_glow_intensity_label)

    glow_color_widget, sine_glow_color_row = _aligned_row_widget(_normal, "Glow Color:")
    tab._sine_glow_widgets.append(glow_color_widget)
    tab.sine_glow_color_btn = ColorSwatchButton(title="Choose Sine Wave Glow Color")
    tab.sine_glow_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_glow_color', c), tab._save_settings()))
    sine_glow_color_row.addWidget(tab.sine_glow_color_btn)
    sine_glow_color_row.addStretch()

    tab.sine_reactive_glow = QCheckBox("Reactive Glow (energy-driven)")
    tab.sine_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'sine_reactive_glow', True))
    tab.sine_reactive_glow.stateChanged.connect(tab._save_settings)
    _normal.addWidget(tab.sine_reactive_glow)
    tab._sine_glow_widgets.append(tab.sine_reactive_glow)

    def _update_sine_glow_vis(_s=None):
        visible = tab.sine_glow_enabled.isChecked()
        for widget in getattr(tab, '_sine_glow_widgets', []):
            widget.setVisible(visible)
    tab.sine_glow_enabled.stateChanged.connect(_update_sine_glow_vis)
    _update_sine_glow_vis()

    sine_line_color_row = _aligned_row(_normal, "Line Color:")
    tab.sine_line_color_btn = ColorSwatchButton(title="Choose Sine Wave Line Color")
    tab.sine_line_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line_color', c), tab._save_settings()))
    sine_line_color_row.addWidget(tab.sine_line_color_btn)
    sine_line_color_row.addStretch()

    sine_sens_row = _aligned_row(_normal, "Sensitivity:")
    tab.sine_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_sensitivity.setMinimum(10)
    tab.sine_sensitivity.setMaximum(500)
    sine_sens_val = int(tab._default_float('spotify_visualizer', 'sine_sensitivity', 1.0) * 100)
    tab.sine_sensitivity.setValue(max(10, min(500, sine_sens_val)))
    tab.sine_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_sensitivity.setTickInterval(50)
    tab.sine_sensitivity.setToolTip("How much audio energy affects sine wave amplitude.")
    tab.sine_sensitivity.valueChanged.connect(tab._save_settings)
    sine_sens_row.addWidget(tab.sine_sensitivity)
    tab.sine_sensitivity_label = QLabel(f"{sine_sens_val / 100.0:.2f}x")
    tab.sine_sensitivity.valueChanged.connect(
        lambda v: tab.sine_sensitivity_label.setText(f"{v / 100.0:.2f}x")
    )
    sine_sens_row.addWidget(tab.sine_sensitivity_label)

    sine_speed_row = _aligned_row(_normal, "Speed:")
    tab.sine_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_speed.setMinimum(10)
    tab.sine_speed.setMaximum(100)
    sine_speed_val = int(tab._default_float('spotify_visualizer', 'sine_speed', 1.0) * 100)
    tab.sine_speed.setValue(max(10, min(100, sine_speed_val)))
    tab.sine_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_speed.setTickInterval(10)
    tab.sine_speed.setToolTip("Wave animation speed multiplier.")
    tab.sine_speed.valueChanged.connect(tab._save_settings)
    sine_speed_row.addWidget(tab.sine_speed)
    tab.sine_speed_label = QLabel(f"{sine_speed_val / 100.0:.2f}x")
    tab.sine_speed.valueChanged.connect(
        lambda v: tab.sine_speed_label.setText(f"{v / 100.0:.2f}x")
    )
    sine_speed_row.addWidget(tab.sine_speed_label)

    sine_travel_row = _aligned_row(_normal, "Travel:")
    tab.sine_travel = QComboBox()
    tab.sine_travel.addItems(["None", "Scroll Left", "Scroll Right"])
    default_sine_travel = tab._default_int('spotify_visualizer', 'sine_wave_travel', 0)
    tab.sine_travel.setCurrentIndex(max(0, min(2, default_sine_travel)))
    tab.sine_travel.setToolTip("Direction the sine wave scrolls.")
    tab.sine_travel.currentIndexChanged.connect(tab._save_settings)
    sine_travel_row.addWidget(tab.sine_travel)
    sine_travel_row.addStretch()

    # Wave Effect
    sine_wave_fx_row = _aligned_row(_normal, "Wave Effect:")
    tab.sine_wave_effect = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_wave_effect.setMinimum(0)
    tab.sine_wave_effect.setMaximum(100)
    sine_wave_fx_val = int(tab._default_float('spotify_visualizer', 'sine_wave_effect',
                           tab._default_float('spotify_visualizer', 'sine_wobble_amount', 0.0)) * 100)
    tab.sine_wave_effect.setValue(max(0, min(100, sine_wave_fx_val)))
    tab.sine_wave_effect.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_wave_effect.setTickInterval(10)
    tab.sine_wave_effect.setToolTip("Adds a wave-like positional undulation along the sine lines. Higher = more movement.")
    tab.sine_wave_effect.valueChanged.connect(tab._save_settings)
    sine_wave_fx_row.addWidget(tab.sine_wave_effect)
    tab.sine_wave_effect_label = QLabel(f"{sine_wave_fx_val}%")
    tab.sine_wave_effect.valueChanged.connect(
        lambda v: tab.sine_wave_effect_label.setText(f"{v}%")
    )
    sine_wave_fx_row.addWidget(tab.sine_wave_effect_label)

    # Micro Wobble (legacy)
    sine_mw_row = _aligned_row(_normal, "Micro Wobble:")
    tab.sine_micro_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_micro_wobble.setMinimum(0)
    tab.sine_micro_wobble.setMaximum(100)
    sine_mw_val = int(tab._default_float('spotify_visualizer', 'sine_micro_wobble', 0.0) * 100)
    tab.sine_micro_wobble.setValue(max(0, min(100, sine_mw_val)))
    tab.sine_micro_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_micro_wobble.setTickInterval(10)
    tab.sine_micro_wobble.setToolTip(
        "Legacy jagged wobble effect (energy-reactive dents). Leave at 0% if using Crawl."
    )
    tab.sine_micro_wobble.valueChanged.connect(tab._save_settings)
    sine_mw_row.addWidget(tab.sine_micro_wobble)
    tab.sine_micro_wobble_label = QLabel(f"{sine_mw_val}%")
    tab.sine_micro_wobble.valueChanged.connect(
        lambda v: tab.sine_micro_wobble_label.setText(f"{v}%")
    )
    sine_mw_row.addWidget(tab.sine_micro_wobble_label)

    # Crawl (new sine slider)
    sine_crawl_row = _aligned_row(_normal, "Crawl:")
    tab.sine_crawl_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_crawl_slider.setMinimum(0)
    tab.sine_crawl_slider.setMaximum(100)
    sine_crawl_val = int(tab._default_float('spotify_visualizer', 'sine_crawl_amount', 0.25) * 100)
    tab.sine_crawl_slider.setValue(max(0, min(100, sine_crawl_val)))
    tab.sine_crawl_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_crawl_slider.setTickInterval(10)
    tab.sine_crawl_slider.setToolTip(
        "Gentle horizontal dents that crawl across the lines in response to vocals. Higher = more visible crawl."
    )
    tab.sine_crawl_slider.valueChanged.connect(tab._save_settings)
    sine_crawl_row.addWidget(tab.sine_crawl_slider)
    tab.sine_crawl_label = QLabel(f"{sine_crawl_val}%")
    tab.sine_crawl_slider.valueChanged.connect(
        lambda v: tab.sine_crawl_label.setText(f"{v}%")
    )
    sine_crawl_row.addWidget(tab.sine_crawl_label)

    # Width Reaction
    sine_wr_row = _aligned_row(_normal, "Width Reaction:")
    tab.sine_width_reaction = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_width_reaction.setMinimum(0)
    tab.sine_width_reaction.setMaximum(100)
    sine_wr_val = int(tab._default_float('spotify_visualizer', 'sine_width_reaction', 0.0) * 100)
    tab.sine_width_reaction.setValue(max(0, min(100, sine_wr_val)))
    tab.sine_width_reaction.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_width_reaction.setTickInterval(10)
    tab.sine_width_reaction.setToolTip(
        "Bass-driven line width stretching. All lines stretch wider in reaction to bass. "
        "0 = off (2px lines), higher = thicker lines on bass hits (up to ~8px). "
        "Lines still resemble a sine wave at maximum."
    )
    tab.sine_width_reaction.valueChanged.connect(tab._save_settings)
    sine_wr_row.addWidget(tab.sine_width_reaction)
    tab.sine_width_reaction_label = QLabel(f"{sine_wr_val}%")
    tab.sine_width_reaction.valueChanged.connect(
        lambda v: tab.sine_width_reaction_label.setText(f"{v}%")
    )
    sine_wr_row.addWidget(tab.sine_width_reaction_label)

    # Density (cycles across card)
    sine_density_row = _aligned_row(_adv, "Density:")
    tab.sine_density = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_density.setMinimum(25)
    tab.sine_density.setMaximum(300)
    sine_density_val = int(tab._default_float('spotify_visualizer', 'sine_density', 1.0) * 100)
    tab.sine_density.setValue(max(25, min(300, sine_density_val)))
    tab.sine_density.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_density.setTickInterval(25)
    tab.sine_density.setToolTip(
        "Temporarily disabled — density slider currently has no visual effect for an unknown reason."
    )
    tab.sine_density.setEnabled(False)
    tab.sine_density.valueChanged.connect(tab._save_settings)
    sine_density_row.addWidget(tab.sine_density)
    tab.sine_density_label = QLabel("Disabled (no effect)")
    tab.sine_density.valueChanged.connect(
        lambda v: tab.sine_density_label.setText(f"{v / 100.0:.2f}×")
    )
    sine_density_row.addWidget(tab.sine_density_label)

    # Heartbeat
    sine_hb_row = _aligned_row(_adv, "Heartbeat:")
    tab.sine_heartbeat = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_heartbeat.setMinimum(0)
    tab.sine_heartbeat.setMaximum(100)
    tab.sine_heartbeat.setValue(0)
    tab.sine_heartbeat.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_heartbeat.setTickInterval(10)
    tab.sine_heartbeat.setEnabled(False)
    tab.sine_heartbeat.setToolTip(
        "Temporarily disabled — heartbeat requires a redesign before returning."
    )
    sine_hb_row.addWidget(tab.sine_heartbeat)
    tab.sine_heartbeat_label = QLabel("Disabled")
    sine_hb_row.addWidget(tab.sine_heartbeat_label)

    # Multi-line displacement (reactive offset)
    sine_disp_row = _aligned_row(_adv, "Displacement:")
    tab.sine_displacement = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_displacement.setMinimum(0)
    tab.sine_displacement.setMaximum(100)
    tab.sine_displacement.setValue(0)
    tab.sine_displacement.setEnabled(False)
    tab.sine_displacement.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_displacement.setTickInterval(10)
    tab.sine_displacement.setToolTip(
        "Displacement is disabled (legacy feature)."
    )
    sine_disp_row.addWidget(tab.sine_displacement)
    tab.sine_displacement_label = QLabel("Disabled")
    sine_disp_row.addWidget(tab.sine_displacement_label)

    # Vertical Shift
    sine_vshift_row = _aligned_row(_adv, "Vertical Shift:")
    tab.sine_vertical_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_vertical_shift.setMinimum(-50)
    tab.sine_vertical_shift.setMaximum(200)
    sine_vshift_val = int(tab._default_int('spotify_visualizer', 'sine_vertical_shift', 0))
    tab.sine_vertical_shift.setValue(max(-50, min(200, sine_vshift_val)))
    tab.sine_vertical_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_vertical_shift.setTickInterval(25)
    tab.sine_vertical_shift.setToolTip("Controls vertical spread between lines. 0 = all aligned, 100 = default spread, 200 = max spread, negative = lines cross. Multi-line only.")
    tab.sine_vertical_shift.valueChanged.connect(tab._save_settings)
    sine_vshift_row.addWidget(tab.sine_vertical_shift)
    tab.sine_vertical_shift_label = QLabel(f"{sine_vshift_val}")
    tab.sine_vertical_shift.valueChanged.connect(
        lambda v: tab.sine_vertical_shift_label.setText(f"{v}")
    )
    sine_vshift_row.addWidget(tab.sine_vertical_shift_label)

    # Line 1 Horizontal Shift
    sine_l1_shift_row = _aligned_row(_adv, "Line 1 Horizontal Shift:")
    tab.sine_line1_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line1_shift.setMinimum(-100)
    tab.sine_line1_shift.setMaximum(100)
    sine_l1_shift_val = int(tab._default_float('spotify_visualizer', 'sine_line1_shift', 0.0) * 100)
    tab.sine_line1_shift.setValue(max(-100, min(100, sine_l1_shift_val)))
    tab.sine_line1_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line1_shift.setTickInterval(10)
    tab.sine_line1_shift.setToolTip(
        "Phase offset for the primary sine line. Negative values lead, positive values lag."
    )
    tab.sine_line1_shift.valueChanged.connect(tab._save_settings)
    sine_l1_shift_row.addWidget(tab.sine_line1_shift)
    tab.sine_line1_shift_label = QLabel(f"{sine_l1_shift_val / 100.0:.2f} cycles")
    tab.sine_line1_shift.valueChanged.connect(
        lambda v: tab.sine_line1_shift_label.setText(f"{v / 100.0:.2f} cycles")
    )
    sine_l1_shift_row.addWidget(tab.sine_line1_shift_label)

    # Multi-line
    tab.sine_multi_line = QCheckBox("Multi-Line Mode (up to 3 lines)")
    tab.sine_multi_line.setChecked(
        tab._default_int('spotify_visualizer', 'sine_line_count', 1) > 1
    )
    tab.sine_multi_line.setToolTip("Enable additional sine waves with different frequency distributions.")
    tab.sine_multi_line.stateChanged.connect(tab._save_settings)
    tab.sine_multi_line.stateChanged.connect(lambda: _update_sine_multi_line_visibility(tab))
    _adv.addWidget(tab.sine_multi_line)

    tab._sine_multi_container = QWidget()
    sine_ml_layout = QVBoxLayout(tab._sine_multi_container)
    sine_ml_layout.setContentsMargins(0, 0, 0, 0)

    sine_lc_row = _aligned_row(sine_ml_layout, "Line Count:")
    tab.sine_line_count_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line_count_slider.setMinimum(2)
    tab.sine_line_count_slider.setMaximum(3)
    tab.sine_line_count_slider.setValue(max(2, tab._default_int('spotify_visualizer', 'sine_line_count', 2)))
    tab.sine_line_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line_count_slider.setTickInterval(1)
    tab.sine_line_count_slider.valueChanged.connect(tab._save_settings)
    tab.sine_line_count_slider.valueChanged.connect(lambda: _update_sine_multi_line_visibility(tab))
    sine_lc_row.addWidget(tab.sine_line_count_slider)
    tab.sine_line_count_label = QLabel(str(max(2, tab._default_int('spotify_visualizer', 'sine_line_count', 2))))
    tab.sine_line_count_slider.valueChanged.connect(
        lambda v: tab.sine_line_count_label.setText(str(v))
    )
    sine_lc_row.addWidget(tab.sine_line_count_label)

    sine_l2_row = _aligned_row(sine_ml_layout, "Line 2:")
    sine_l2_color_col = QVBoxLayout()
    sine_l2_color_label = QLabel("Line Color")
    sine_l2_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l2_color_col.addWidget(sine_l2_color_label)
    tab.sine_line2_color_btn = ColorSwatchButton(title="Line 2 Color")
    tab.sine_line2_color_btn.setToolTip("Sine wave line 2 colour")
    tab.sine_line2_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line2_color', c), tab._save_settings()))
    sine_l2_color_col.addWidget(tab.sine_line2_color_btn)
    sine_l2_row.addLayout(sine_l2_color_col)

    sine_l2_glow_col = QVBoxLayout()
    sine_l2_glow_label = QLabel("Glow Color")
    sine_l2_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l2_glow_col.addWidget(sine_l2_glow_label)
    tab.sine_line2_glow_btn = ColorSwatchButton(title="Line 2 Glow Color")
    tab.sine_line2_glow_btn.setToolTip("Sine wave line 2 glow colour")
    tab.sine_line2_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line2_glow_color', c), tab._save_settings()))
    sine_l2_glow_col.addWidget(tab.sine_line2_glow_btn)
    sine_l2_row.addLayout(sine_l2_glow_col)
    sine_l2_travel_col = QVBoxLayout()
    sine_l2_travel_label = QLabel("Travel")
    sine_l2_travel_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l2_travel_col.addWidget(sine_l2_travel_label)
    tab.sine_travel_line2 = QComboBox()
    tab.sine_travel_line2.addItems(["None", "Left", "Right"])
    tab.sine_travel_line2.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line2', 0))))
    tab.sine_travel_line2.currentIndexChanged.connect(tab._save_settings)
    sine_l2_travel_col.addWidget(tab.sine_travel_line2)
    sine_l2_row.addLayout(sine_l2_travel_col)

    sine_l2_row.addStretch()

    # Line 2 horizontal shift
    sine_l2_shift_row = _aligned_row(sine_ml_layout, "Line 2 Horizontal Shift:")
    tab.sine_line2_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line2_shift.setMinimum(-100)
    tab.sine_line2_shift.setMaximum(100)
    sine_l2_shift_val = int(tab._default_float('spotify_visualizer', 'sine_line2_shift', 0.0) * 100)
    tab.sine_line2_shift.setValue(max(-100, min(100, sine_l2_shift_val)))
    tab.sine_line2_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line2_shift.setTickInterval(10)
    tab.sine_line2_shift.setToolTip(
        "Phase offset for line 2 relative to card width (negative = lead, positive = lag)."
    )
    tab.sine_line2_shift.valueChanged.connect(tab._save_settings)
    tab.sine_line2_shift_label = QLabel(f"{sine_l2_shift_val / 100.0:.2f} cycles")
    tab.sine_line2_shift.valueChanged.connect(
        lambda v: tab.sine_line2_shift_label.setText(f"{v / 100.0:.2f} cycles")
    )
    sine_l2_shift_row.addWidget(tab.sine_line2_shift)
    sine_l2_shift_row.addWidget(tab.sine_line2_shift_label)

    tab._sine_l3_row_widget = QWidget()
    sine_ml_layout.addWidget(tab._sine_l3_row_widget)
    sine_l3_row = QHBoxLayout(tab._sine_l3_row_widget)
    sine_l3_row.setContentsMargins(0, 0, 0, 0)
    sine_l3_row.setSpacing(8)
    tab._sine_line3_label = QLabel("Line 3:")
    tab._sine_line3_label.setFixedWidth(LABEL_WIDTH)
    sine_l3_row.addWidget(tab._sine_line3_label)
    sine_l3_content = QHBoxLayout()
    sine_l3_content.setContentsMargins(0, 0, 0, 0)
    sine_l3_content.setSpacing(8)
    sine_l3_row.addLayout(sine_l3_content, 1)

    sine_l3_color_col = QVBoxLayout()
    sine_l3_color_label = QLabel("Line Color")
    sine_l3_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l3_color_col.addWidget(sine_l3_color_label)
    tab.sine_line3_color_btn = ColorSwatchButton(title="Line 3 Color")
    tab.sine_line3_color_btn.setToolTip("Sine wave line 3 colour")
    tab.sine_line3_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line3_color', c), tab._save_settings()))
    sine_l3_color_col.addWidget(tab.sine_line3_color_btn)
    sine_l3_content.addLayout(sine_l3_color_col)

    sine_l3_glow_col = QVBoxLayout()
    sine_l3_glow_label = QLabel("Glow Color")
    sine_l3_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l3_glow_col.addWidget(sine_l3_glow_label)
    tab.sine_line3_glow_btn = ColorSwatchButton(title="Line 3 Glow Color")
    tab.sine_line3_glow_btn.setToolTip("Sine wave line 3 glow colour")
    tab.sine_line3_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line3_glow_color', c), tab._save_settings()))
    sine_l3_glow_col.addWidget(tab.sine_line3_glow_btn)
    sine_l3_content.addLayout(sine_l3_glow_col)

    sine_l3_travel_col = QVBoxLayout()
    sine_l3_travel_label = QLabel("Travel")
    sine_l3_travel_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    sine_l3_travel_col.addWidget(sine_l3_travel_label)
    tab.sine_travel_line3 = QComboBox()
    tab.sine_travel_line3.addItems(["None", "Left", "Right"])
    tab.sine_travel_line3.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line3', 0))))
    tab.sine_travel_line3.currentIndexChanged.connect(tab._save_settings)
    sine_l3_travel_col.addWidget(tab.sine_travel_line3)
    sine_l3_content.addLayout(sine_l3_travel_col)

    sine_l3_content.addStretch()

    # Line 3 horizontal shift
    sine_l3_shift_row = _aligned_row(sine_ml_layout, "Line 3 Horizontal Shift:")
    tab.sine_line3_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line3_shift.setMinimum(-100)
    tab.sine_line3_shift.setMaximum(100)
    sine_l3_shift_val = int(tab._default_float('spotify_visualizer', 'sine_line3_shift', 0.0) * 100)
    tab.sine_line3_shift.setValue(max(-100, min(100, sine_l3_shift_val)))
    tab.sine_line3_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line3_shift.setTickInterval(10)
    tab.sine_line3_shift.setToolTip(
        "Phase offset for line 3 relative to card width (negative = lead, positive = lag)."
    )
    tab.sine_line3_shift.valueChanged.connect(tab._save_settings)
    tab.sine_line3_shift_label = QLabel(f"{sine_l3_shift_val / 100.0:.2f} cycles")
    tab.sine_line3_shift.valueChanged.connect(
        lambda v: tab.sine_line3_shift_label.setText(f"{v / 100.0:.2f} cycles")
    )
    sine_l3_shift_row.addWidget(tab.sine_line3_shift)
    sine_l3_shift_row.addWidget(tab.sine_line3_shift_label)

    _adv.addWidget(tab._sine_multi_container)
    _update_sine_multi_line_visibility(tab)

    # Line Offset Bias
    sine_lob_row = _aligned_row(_adv, "Line Offset Bias:")
    tab.sine_line_offset_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line_offset_bias.setMinimum(0)
    tab.sine_line_offset_bias.setMaximum(100)
    sine_lob_val = int(tab._default_float('spotify_visualizer', 'sine_line_offset_bias', 0.0) * 100)
    tab.sine_line_offset_bias.setValue(max(0, min(100, sine_lob_val)))
    tab.sine_line_offset_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line_offset_bias.setTickInterval(10)
    tab.sine_line_offset_bias.setToolTip("Vertical spread between lines in multi-line mode.")
    tab.sine_line_offset_bias.valueChanged.connect(tab._save_settings)
    sine_lob_row.addWidget(tab.sine_line_offset_bias)
    tab.sine_line_offset_bias_label = QLabel(f"{sine_lob_val}%")
    tab.sine_line_offset_bias.valueChanged.connect(
        lambda v: tab.sine_line_offset_bias_label.setText(f"{v}%")
    )
    sine_lob_row.addWidget(tab.sine_line_offset_bias_label)

    # Card Adaptation
    sine_adapt_row = _aligned_row(_adv, "Card Adaptation:")
    tab.sine_card_adaptation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_card_adaptation.setMinimum(3)
    tab.sine_card_adaptation.setMaximum(100)
    sine_adapt_val = int(tab._default_float('spotify_visualizer', 'sine_card_adaptation', 0.3) * 100)
    tab.sine_card_adaptation.setValue(max(3, min(100, sine_adapt_val)))
    tab.sine_card_adaptation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_card_adaptation.setTickInterval(10)
    tab.sine_card_adaptation.setToolTip("How much of the card height the sine wave uses. Lower = less vertical stretch.")
    tab.sine_card_adaptation.valueChanged.connect(tab._save_settings)
    sine_adapt_row.addWidget(tab.sine_card_adaptation)
    tab.sine_card_adaptation_label = QLabel(f"{sine_adapt_val}%")
    tab.sine_card_adaptation.valueChanged.connect(
        lambda v: tab.sine_card_adaptation_label.setText(f"{v}%")
    )
    sine_adapt_row.addWidget(tab.sine_card_adaptation_label)

    # Card Height
    sine_growth_row = _aligned_row(_adv, "Card Height:")
    tab.sine_wave_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_wave_growth.setMinimum(100)
    tab.sine_wave_growth.setMaximum(500)
    tab.sine_wave_growth.setSingleStep(5)
    tab.sine_wave_growth.setTickInterval(50)
    sine_growth_val = int(tab._default_float('spotify_visualizer', 'sine_wave_growth', 1.0) * 100)
    tab.sine_wave_growth.setValue(max(100, min(500, sine_growth_val)))
    tab.sine_wave_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_wave_growth.setToolTip("Height multiplier for the sine wave card.")
    tab.sine_wave_growth.valueChanged.connect(tab._save_settings)
    sine_growth_row.addWidget(tab.sine_wave_growth)
    tab.sine_wave_growth_label = QLabel(f"{sine_growth_val / 100.0:.1f}x")
    tab.sine_wave_growth.valueChanged.connect(
        lambda v: tab.sine_wave_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    sine_growth_row.addWidget(tab.sine_wave_growth_label)
    parent_layout.addWidget(tab._sine_wave_settings_container)
