"""Oscilloscope visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
)
from ui.styled_popup import ColorSwatchButton
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _update_osc_multi_line_visibility(tab) -> None:
    enabled = getattr(tab, 'osc_multi_line', None) and tab.osc_multi_line.isChecked()
    container = getattr(tab, '_osc_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    line_count = getattr(tab, 'osc_line_count', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_osc_line3_label', None), getattr(tab, '_osc_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


def build_oscilloscope_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Oscilloscope settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._osc_settings_container = QWidget()
    osc_layout = QVBoxLayout(tab._osc_settings_container)
    osc_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._osc_preset_slider = VisualizerPresetSlider("oscilloscope")
    tab._osc_preset_slider.preset_changed.connect(tab._save_settings)
    osc_layout.addWidget(tab._osc_preset_slider)

    tab._osc_advanced = QWidget()
    _adv = QVBoxLayout(tab._osc_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    tab._osc_preset_slider.set_advanced_container(tab._osc_advanced)

    tab.osc_glow_enabled = QCheckBox("Enable Glow")
    tab.osc_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'osc_glow_enabled', True))
    tab.osc_glow_enabled.setToolTip("Draw a soft glow halo around the waveform line.")
    tab.osc_glow_enabled.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.osc_glow_enabled)

    tab._osc_glow_sub_container = QWidget()
    _osc_glow_layout = QVBoxLayout(tab._osc_glow_sub_container)
    _osc_glow_layout.setContentsMargins(16, 0, 0, 0)

    osc_glow_row = QHBoxLayout()
    osc_glow_row.addWidget(QLabel("Glow Intensity:"))
    tab.osc_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_glow_intensity.setMinimum(0)
    tab.osc_glow_intensity.setMaximum(100)
    osc_glow_val = int(tab._default_float('spotify_visualizer', 'osc_glow_intensity', 0.5) * 100)
    tab.osc_glow_intensity.setValue(osc_glow_val)
    tab.osc_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_glow_intensity.setTickInterval(10)
    tab.osc_glow_intensity.valueChanged.connect(tab._save_settings)
    osc_glow_row.addWidget(tab.osc_glow_intensity)
    tab.osc_glow_intensity_label = QLabel(f"{osc_glow_val}%")
    tab.osc_glow_intensity.valueChanged.connect(
        lambda v: tab.osc_glow_intensity_label.setText(f"{v}%")
    )
    osc_glow_row.addWidget(tab.osc_glow_intensity_label)
    _osc_glow_layout.addLayout(osc_glow_row)

    tab.osc_reactive_glow = QCheckBox("Reactive Glow (bass-driven)")
    tab.osc_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'osc_reactive_glow', True))
    tab.osc_reactive_glow.setToolTip("Glow intensity pulses with bass energy.")
    tab.osc_reactive_glow.stateChanged.connect(tab._save_settings)
    _osc_glow_layout.addWidget(tab.osc_reactive_glow)

    _adv.addWidget(tab._osc_glow_sub_container)

    def _update_osc_glow_vis(_s=None):
        tab._osc_glow_sub_container.setVisible(tab.osc_glow_enabled.isChecked())
    tab.osc_glow_enabled.stateChanged.connect(_update_osc_glow_vis)
    _update_osc_glow_vis()

    # --- Ghost Trail ---
    tab.osc_ghost_enabled = QCheckBox("Ghost Trail")
    tab.osc_ghost_enabled.setChecked(tab._default_bool('spotify_visualizer', 'osc_ghosting_enabled', False))
    tab.osc_ghost_enabled.setToolTip("Show a faded trail of the previous waveform behind the current one.")
    tab.osc_ghost_enabled.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.osc_ghost_enabled)

    tab._osc_ghost_sub_container = QWidget()
    _osc_ghost_layout = QVBoxLayout(tab._osc_ghost_sub_container)
    _osc_ghost_layout.setContentsMargins(16, 0, 0, 0)
    osc_ghost_row = QHBoxLayout()
    osc_ghost_row.addWidget(QLabel("Ghost Intensity:"))
    tab.osc_ghost_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_ghost_intensity.setMinimum(5)
    tab.osc_ghost_intensity.setMaximum(100)
    osc_gi_val = int(tab._default_float('spotify_visualizer', 'osc_ghost_intensity', 0.4) * 100)
    tab.osc_ghost_intensity.setValue(max(5, min(100, osc_gi_val)))
    tab.osc_ghost_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_ghost_intensity.setTickInterval(10)
    tab.osc_ghost_intensity.setToolTip("How visible the ghost trail is. Higher = more opaque trail.")
    tab.osc_ghost_intensity.valueChanged.connect(tab._save_settings)
    osc_ghost_row.addWidget(tab.osc_ghost_intensity)
    tab.osc_ghost_intensity_label = QLabel(f"{osc_gi_val}%")
    tab.osc_ghost_intensity.valueChanged.connect(
        lambda v: tab.osc_ghost_intensity_label.setText(f"{v}%")
    )
    osc_ghost_row.addWidget(tab.osc_ghost_intensity_label)
    _osc_ghost_layout.addLayout(osc_ghost_row)
    _adv.addWidget(tab._osc_ghost_sub_container)

    def _update_osc_ghost_vis(_s=None):
        tab._osc_ghost_sub_container.setVisible(tab.osc_ghost_enabled.isChecked())
    tab.osc_ghost_enabled.stateChanged.connect(_update_osc_ghost_vis)
    _update_osc_ghost_vis()

    osc_sens_row = QHBoxLayout()
    osc_sens_row.addWidget(QLabel("Sensitivity:"))
    tab.osc_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_sensitivity.setMinimum(5)
    tab.osc_sensitivity.setMaximum(100)
    osc_sens_val = int(tab._default_float('spotify_visualizer', 'osc_sensitivity', 3.0) * 10)
    tab.osc_sensitivity.setValue(max(5, min(100, osc_sens_val)))
    tab.osc_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_sensitivity.setTickInterval(10)
    tab.osc_sensitivity.valueChanged.connect(tab._save_settings)
    osc_sens_row.addWidget(tab.osc_sensitivity)
    tab.osc_sensitivity_label = QLabel(f"{osc_sens_val / 10.0:.1f}x")
    tab.osc_sensitivity.valueChanged.connect(
        lambda v: tab.osc_sensitivity_label.setText(f"{v / 10.0:.1f}x")
    )
    osc_sens_row.addWidget(tab.osc_sensitivity_label)
    _adv.addLayout(osc_sens_row)

    osc_smooth_row = QHBoxLayout()
    osc_smooth_row.addWidget(QLabel("Smoothing:"))
    tab.osc_smoothing = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_smoothing.setMinimum(0)
    tab.osc_smoothing.setMaximum(100)
    osc_smooth_val = int(tab._default_float('spotify_visualizer', 'osc_smoothing', 0.7) * 100)
    tab.osc_smoothing.setValue(max(0, min(100, osc_smooth_val)))
    tab.osc_smoothing.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_smoothing.setTickInterval(10)
    tab.osc_smoothing.valueChanged.connect(tab._save_settings)
    osc_smooth_row.addWidget(tab.osc_smoothing)
    tab.osc_smoothing_label = QLabel(f"{osc_smooth_val}%")
    tab.osc_smoothing.valueChanged.connect(
        lambda v: tab.osc_smoothing_label.setText(f"{v}%")
    )
    osc_smooth_row.addWidget(tab.osc_smoothing_label)
    _adv.addLayout(osc_smooth_row)

    osc_speed_row = QHBoxLayout()
    osc_speed_row.addWidget(QLabel("Speed:"))
    tab.osc_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_speed.setMinimum(1)
    tab.osc_speed.setMaximum(100)
    osc_speed_val = int(tab._default_float('spotify_visualizer', 'osc_speed', 1.0) * 100)
    tab.osc_speed.setValue(max(1, min(100, osc_speed_val)))
    tab.osc_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_speed.setTickInterval(10)
    tab.osc_speed.setToolTip("Controls how quickly the waveform updates. 100% = real-time, lower = smoother/slower transitions.")
    tab.osc_speed.valueChanged.connect(tab._save_settings)
    osc_speed_row.addWidget(tab.osc_speed)
    tab.osc_speed_label = QLabel(f"{osc_speed_val}%")
    tab.osc_speed.valueChanged.connect(
        lambda v: tab.osc_speed_label.setText(f"{v}%")
    )
    osc_speed_row.addWidget(tab.osc_speed_label)
    _adv.addLayout(osc_speed_row)

    tab.osc_line_dim = QCheckBox("Dim Lines 2/3 Glow")
    tab.osc_line_dim.setChecked(tab._default_bool('spotify_visualizer', 'osc_line_dim', False))
    tab.osc_line_dim.setToolTip("When enabled, lines 2 and 3 have slightly reduced glow to let the primary line stand out.")
    tab.osc_line_dim.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.osc_line_dim)

    osc_lob_row = QHBoxLayout()
    osc_lob_row.addWidget(QLabel("Line Offset Bias:"))
    tab.osc_line_offset_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_offset_bias.setMinimum(0)
    tab.osc_line_offset_bias.setMaximum(100)
    osc_lob_val = int(tab._default_float('spotify_visualizer', 'osc_line_offset_bias', 0.0) * 100)
    tab.osc_line_offset_bias.setValue(osc_lob_val)
    tab.osc_line_offset_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_offset_bias.setTickInterval(10)
    tab.osc_line_offset_bias.setToolTip(
        "Increases base vertical spread between lines and per-band energy reliance "
        "(bass/mid/treble). Multi-line mode only. 0% = energy-only spacing, "
        "100% = maximum spread with strong per-band separation."
    )
    tab.osc_line_offset_bias.valueChanged.connect(tab._save_settings)
    osc_lob_row.addWidget(tab.osc_line_offset_bias)
    tab.osc_line_offset_bias_label = QLabel(f"{osc_lob_val}%")
    tab.osc_line_offset_bias.valueChanged.connect(
        lambda v: tab.osc_line_offset_bias_label.setText(f"{v}%")
    )
    osc_lob_row.addWidget(tab.osc_line_offset_bias_label)
    _adv.addLayout(osc_lob_row)

    osc_vshift_row = QHBoxLayout()
    osc_vshift_row.addWidget(QLabel("Vertical Shift:"))
    tab.osc_vertical_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_vertical_shift.setMinimum(-50)
    tab.osc_vertical_shift.setMaximum(200)
    osc_vshift_val = int(tab._default_int('spotify_visualizer', 'osc_vertical_shift', 0))
    tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vshift_val)))
    tab.osc_vertical_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_vertical_shift.setTickInterval(25)
    tab.osc_vertical_shift.setToolTip(
        "Controls vertical spread between lines. 0 = all aligned, "
        "100 = default spread, 200 = max spread, negative = lines cross. Multi-line only."
    )
    tab.osc_vertical_shift.valueChanged.connect(tab._save_settings)
    osc_vshift_row.addWidget(tab.osc_vertical_shift)
    tab.osc_vertical_shift_label = QLabel(f"{osc_vshift_val}")
    tab.osc_vertical_shift.valueChanged.connect(
        lambda v: tab.osc_vertical_shift_label.setText(f"{v}")
    )
    osc_vshift_row.addWidget(tab.osc_vertical_shift_label)
    _adv.addLayout(osc_vshift_row)

    osc_line_color_row = QHBoxLayout()
    osc_line_color_row.addWidget(QLabel("Line Color:"))
    tab.osc_line_color_btn = ColorSwatchButton(title="Choose Oscilloscope Line Color")
    tab.osc_line_color_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_line_color', c), tab._save_settings()))
    osc_line_color_row.addWidget(tab.osc_line_color_btn)
    osc_line_color_row.addStretch()
    _adv.addLayout(osc_line_color_row)

    osc_glow_color_row = QHBoxLayout()
    osc_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.osc_glow_color_btn = ColorSwatchButton(title="Choose Oscilloscope Glow Color")
    tab.osc_glow_color_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_glow_color', c), tab._save_settings()))
    osc_glow_color_row.addWidget(tab.osc_glow_color_btn)
    osc_glow_color_row.addStretch()
    _adv.addLayout(osc_glow_color_row)

    tab.osc_multi_line = QCheckBox("Multi-Line Mode (up to 3 lines)")
    tab.osc_multi_line.setChecked(tab._default_int('spotify_visualizer', 'osc_line_count', 1) > 1)
    tab.osc_multi_line.setToolTip("Enable additional waveform lines with different oscillation distributions.")
    tab.osc_multi_line.stateChanged.connect(tab._save_settings)
    tab.osc_multi_line.stateChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    _adv.addWidget(tab.osc_multi_line)

    tab._osc_multi_container = QWidget()
    ml_layout = QVBoxLayout(tab._osc_multi_container)
    ml_layout.setContentsMargins(16, 0, 0, 0)

    osc_line_count_row = QHBoxLayout()
    osc_line_count_row.addWidget(QLabel("Line Count:"))
    tab.osc_line_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_count.setMinimum(2)
    tab.osc_line_count.setMaximum(3)
    tab.osc_line_count.setValue(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1)))
    tab.osc_line_count.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_count.setTickInterval(1)
    tab.osc_line_count.valueChanged.connect(tab._save_settings)
    tab.osc_line_count.valueChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    osc_line_count_row.addWidget(tab.osc_line_count)
    tab.osc_line_count_label = QLabel(str(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1))))
    tab.osc_line_count.valueChanged.connect(
        lambda v: tab.osc_line_count_label.setText(str(v))
    )
    osc_line_count_row.addWidget(tab.osc_line_count_label)
    ml_layout.addLayout(osc_line_count_row)

    ml_layout.addWidget(QLabel("Line 2:"))
    osc_l2_row = QHBoxLayout()
    tab.osc_line2_color_btn = ColorSwatchButton(title="Line 2 Color")
    tab.osc_line2_color_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_line2_color', c), tab._save_settings()))
    osc_l2_row.addWidget(tab.osc_line2_color_btn)
    tab.osc_line2_glow_btn = ColorSwatchButton(title="Line 2 Glow Color")
    tab.osc_line2_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_line2_glow_color', c), tab._save_settings()))
    osc_l2_row.addWidget(tab.osc_line2_glow_btn)
    osc_l2_row.addStretch()
    ml_layout.addLayout(osc_l2_row)

    tab._osc_line3_label = QLabel("Line 3:")
    ml_layout.addWidget(tab._osc_line3_label)
    tab._osc_l3_row_widget = QWidget()
    osc_l3_row = QHBoxLayout(tab._osc_l3_row_widget)
    osc_l3_row.setContentsMargins(0, 0, 0, 0)
    tab.osc_line3_color_btn = ColorSwatchButton(title="Line 3 Color")
    tab.osc_line3_color_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_line3_color', c), tab._save_settings()))
    osc_l3_row.addWidget(tab.osc_line3_color_btn)
    tab.osc_line3_glow_btn = ColorSwatchButton(title="Line 3 Glow Color")
    tab.osc_line3_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_osc_line3_glow_color', c), tab._save_settings()))
    osc_l3_row.addWidget(tab.osc_line3_glow_btn)
    osc_l3_row.addStretch()
    ml_layout.addWidget(tab._osc_l3_row_widget)

    _adv.addWidget(tab._osc_multi_container)
    _update_osc_multi_line_visibility(tab)

    osc_growth_row = QHBoxLayout()
    osc_growth_row.addWidget(QLabel("Card Height:"))
    tab.osc_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_growth.setMinimum(100)
    tab.osc_growth.setMaximum(500)
    osc_growth_val = int(tab._default_float('spotify_visualizer', 'osc_growth', 1.0) * 100)
    tab.osc_growth.setValue(max(100, min(500, osc_growth_val)))
    tab.osc_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_growth.setTickInterval(50)
    tab.osc_growth.setToolTip("Height multiplier for the oscilloscope card.")
    tab.osc_growth.valueChanged.connect(tab._save_settings)
    osc_growth_row.addWidget(tab.osc_growth)
    tab.osc_growth_label = QLabel(f"{osc_growth_val / 100.0:.1f}x")
    tab.osc_growth.valueChanged.connect(
        lambda v: tab.osc_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    osc_growth_row.addWidget(tab.osc_growth_label)
    _adv.addLayout(osc_growth_row)

    osc_layout.addWidget(tab._osc_advanced)
    parent_layout.addWidget(tab._osc_settings_container)
