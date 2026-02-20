"""Sine Wave visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QCheckBox, QSlider, QWidget,
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

    tab._sine_advanced = QWidget()
    _adv = QVBoxLayout(tab._sine_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    tab._sine_preset_slider.set_advanced_container(tab._sine_advanced)

    # Glow
    tab.sine_glow_enabled = QCheckBox("Enable Glow")
    tab.sine_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'sine_glow_enabled', True))
    tab.sine_glow_enabled.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.sine_glow_enabled)

    tab._sine_glow_sub_container = QWidget()
    _sine_glow_layout = QVBoxLayout(tab._sine_glow_sub_container)
    _sine_glow_layout.setContentsMargins(16, 0, 0, 0)

    sine_glow_row = QHBoxLayout()
    sine_glow_row.addWidget(QLabel("Glow Intensity:"))
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
    _sine_glow_layout.addLayout(sine_glow_row)

    sine_glow_color_row = QHBoxLayout()
    sine_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.sine_glow_color_btn = ColorSwatchButton(title="Choose Sine Wave Glow Color")
    tab.sine_glow_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_glow_color', c), tab._save_settings()))
    sine_glow_color_row.addWidget(tab.sine_glow_color_btn)
    sine_glow_color_row.addStretch()
    _sine_glow_layout.addLayout(sine_glow_color_row)

    tab.sine_reactive_glow = QCheckBox("Reactive Glow (energy-driven)")
    tab.sine_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'sine_reactive_glow', True))
    tab.sine_reactive_glow.stateChanged.connect(tab._save_settings)
    _sine_glow_layout.addWidget(tab.sine_reactive_glow)

    _adv.addWidget(tab._sine_glow_sub_container)

    def _update_sine_glow_vis(_s=None):
        tab._sine_glow_sub_container.setVisible(tab.sine_glow_enabled.isChecked())
    tab.sine_glow_enabled.stateChanged.connect(_update_sine_glow_vis)
    _update_sine_glow_vis()

    sine_line_color_row = QHBoxLayout()
    sine_line_color_row.addWidget(QLabel("Line Color:"))
    tab.sine_line_color_btn = ColorSwatchButton(title="Choose Sine Wave Line Color")
    tab.sine_line_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line_color', c), tab._save_settings()))
    sine_line_color_row.addWidget(tab.sine_line_color_btn)
    sine_line_color_row.addStretch()
    _adv.addLayout(sine_line_color_row)

    sine_sens_row = QHBoxLayout()
    sine_sens_row.addWidget(QLabel("Sensitivity:"))
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
    _adv.addLayout(sine_sens_row)

    sine_speed_row = QHBoxLayout()
    sine_speed_row.addWidget(QLabel("Speed:"))
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
    _adv.addLayout(sine_speed_row)

    sine_travel_row = QHBoxLayout()
    sine_travel_row.addWidget(QLabel("Travel:"))
    tab.sine_travel = QComboBox()
    tab.sine_travel.addItems(["None", "Scroll Left", "Scroll Right"])
    default_sine_travel = tab._default_int('spotify_visualizer', 'sine_wave_travel', 0)
    tab.sine_travel.setCurrentIndex(max(0, min(2, default_sine_travel)))
    tab.sine_travel.setToolTip("Direction the sine wave scrolls.")
    tab.sine_travel.currentIndexChanged.connect(tab._save_settings)
    sine_travel_row.addWidget(tab.sine_travel)
    sine_travel_row.addStretch()
    _adv.addLayout(sine_travel_row)

    # Wave Effect
    sine_wave_fx_row = QHBoxLayout()
    sine_wave_fx_row.addWidget(QLabel("Wave Effect:"))
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
    _adv.addLayout(sine_wave_fx_row)

    # Micro Wobble
    sine_mw_row = QHBoxLayout()
    sine_mw_row.addWidget(QLabel("Micro Wobble:"))
    tab.sine_micro_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_micro_wobble.setMinimum(0)
    tab.sine_micro_wobble.setMaximum(100)
    sine_mw_val = int(tab._default_float('spotify_visualizer', 'sine_micro_wobble', 0.0) * 100)
    tab.sine_micro_wobble.setValue(max(0, min(100, sine_mw_val)))
    tab.sine_micro_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_micro_wobble.setTickInterval(10)
    tab.sine_micro_wobble.setToolTip("Energy-reactive micro distortions along the line. Small dents/bumps that react to audio without changing core shape. Higher = sharper.")
    tab.sine_micro_wobble.valueChanged.connect(tab._save_settings)
    sine_mw_row.addWidget(tab.sine_micro_wobble)
    tab.sine_micro_wobble_label = QLabel(f"{sine_mw_val}%")
    tab.sine_micro_wobble.valueChanged.connect(
        lambda v: tab.sine_micro_wobble_label.setText(f"{v}%")
    )
    sine_mw_row.addWidget(tab.sine_micro_wobble_label)
    _adv.addLayout(sine_mw_row)

    # Width Reaction
    sine_wr_row = QHBoxLayout()
    sine_wr_row.addWidget(QLabel("Width Reaction:"))
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
    _adv.addLayout(sine_wr_row)

    # Heartbeat
    sine_hb_row = QHBoxLayout()
    sine_hb_row.addWidget(QLabel("Heartbeat:"))
    tab.sine_heartbeat = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_heartbeat.setMinimum(0)
    tab.sine_heartbeat.setMaximum(100)
    sine_hb_val = int(tab._default_float('spotify_visualizer', 'sine_heartbeat', 0.0) * 100)
    tab.sine_heartbeat.setValue(max(0, min(100, sine_hb_val)))
    tab.sine_heartbeat.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_heartbeat.setTickInterval(10)
    tab.sine_heartbeat.setToolTip(
        "Bass transient-triggered triangular bumps along the line. "
        "Bumps are largest in the travel direction, smallest opposite. "
        "0 = off, higher = more prominent bumps."
    )
    tab.sine_heartbeat.valueChanged.connect(tab._save_settings)
    sine_hb_row.addWidget(tab.sine_heartbeat)
    tab.sine_heartbeat_label = QLabel(f"{sine_hb_val}%")
    tab.sine_heartbeat.valueChanged.connect(
        lambda v: tab.sine_heartbeat_label.setText(f"{v}%")
    )
    sine_hb_row.addWidget(tab.sine_heartbeat_label)
    _adv.addLayout(sine_hb_row)

    # Vertical Shift
    sine_vshift_row = QHBoxLayout()
    sine_vshift_row.addWidget(QLabel("Vertical Shift:"))
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
    _adv.addLayout(sine_vshift_row)

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
    sine_ml_layout.setContentsMargins(16, 0, 0, 0)

    sine_lc_row = QHBoxLayout()
    sine_lc_row.addWidget(QLabel("Line Count:"))
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
    sine_ml_layout.addLayout(sine_lc_row)

    sine_ml_layout.addWidget(QLabel("Line 2:"))
    sine_l2_row = QHBoxLayout()
    tab.sine_line2_color_btn = ColorSwatchButton(title="Line 2 Color")
    tab.sine_line2_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line2_color', c), tab._save_settings()))
    sine_l2_row.addWidget(tab.sine_line2_color_btn)
    tab.sine_line2_glow_btn = ColorSwatchButton(title="Line 2 Glow Color")
    tab.sine_line2_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line2_glow_color', c), tab._save_settings()))
    sine_l2_row.addWidget(tab.sine_line2_glow_btn)
    sine_l2_row.addWidget(QLabel("Travel:"))
    tab.sine_travel_line2 = QComboBox()
    tab.sine_travel_line2.addItems(["None", "Left", "Right"])
    tab.sine_travel_line2.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line2', 0))))
    tab.sine_travel_line2.currentIndexChanged.connect(tab._save_settings)
    sine_l2_row.addWidget(tab.sine_travel_line2)
    sine_l2_row.addStretch()
    sine_ml_layout.addLayout(sine_l2_row)

    tab._sine_line3_label = QLabel("Line 3:")
    sine_ml_layout.addWidget(tab._sine_line3_label)
    tab._sine_l3_row_widget = QWidget()
    sine_l3_row = QHBoxLayout(tab._sine_l3_row_widget)
    sine_l3_row.setContentsMargins(0, 0, 0, 0)
    tab.sine_line3_color_btn = ColorSwatchButton(title="Line 3 Color")
    tab.sine_line3_color_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line3_color', c), tab._save_settings()))
    sine_l3_row.addWidget(tab.sine_line3_color_btn)
    tab.sine_line3_glow_btn = ColorSwatchButton(title="Line 3 Glow Color")
    tab.sine_line3_glow_btn.color_changed.connect(lambda c: (setattr(tab, '_sine_line3_glow_color', c), tab._save_settings()))
    sine_l3_row.addWidget(tab.sine_line3_glow_btn)
    sine_l3_row.addWidget(QLabel("Travel:"))
    tab.sine_travel_line3 = QComboBox()
    tab.sine_travel_line3.addItems(["None", "Left", "Right"])
    tab.sine_travel_line3.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line3', 0))))
    tab.sine_travel_line3.currentIndexChanged.connect(tab._save_settings)
    sine_l3_row.addWidget(tab.sine_travel_line3)
    sine_l3_row.addStretch()
    sine_ml_layout.addWidget(tab._sine_l3_row_widget)

    _adv.addWidget(tab._sine_multi_container)
    _update_sine_multi_line_visibility(tab)

    # Line Offset Bias
    sine_lob_row = QHBoxLayout()
    sine_lob_row.addWidget(QLabel("Line Offset Bias:"))
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
    _adv.addLayout(sine_lob_row)

    # Card Adaptation
    sine_adapt_row = QHBoxLayout()
    sine_adapt_row.addWidget(QLabel("Card Adaptation:"))
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
    _adv.addLayout(sine_adapt_row)

    # Card Height
    sine_growth_row = QHBoxLayout()
    sine_growth_row.addWidget(QLabel("Card Height:"))
    tab.sine_wave_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_wave_growth.setMinimum(100)
    tab.sine_wave_growth.setMaximum(500)
    sine_growth_val = int(tab._default_float('spotify_visualizer', 'sine_wave_growth', 1.0) * 100)
    tab.sine_wave_growth.setValue(max(100, min(500, sine_growth_val)))
    tab.sine_wave_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_wave_growth.setTickInterval(50)
    tab.sine_wave_growth.setToolTip("Height multiplier for the sine wave card.")
    tab.sine_wave_growth.valueChanged.connect(tab._save_settings)
    sine_growth_row.addWidget(tab.sine_wave_growth)
    tab.sine_wave_growth_label = QLabel(f"{sine_growth_val / 100.0:.1f}x")
    tab.sine_wave_growth.valueChanged.connect(
        lambda v: tab.sine_wave_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    sine_growth_row.addWidget(tab.sine_wave_growth_label)
    _adv.addLayout(sine_growth_row)

    sine_layout.addWidget(tab._sine_advanced)
    parent_layout.addWidget(tab._sine_wave_settings_container)
