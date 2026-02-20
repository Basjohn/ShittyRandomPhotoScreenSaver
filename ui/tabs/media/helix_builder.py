"""Helix visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QCheckBox, QPushButton, QSlider, QWidget,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_helix_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Helix settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._helix_settings_container = QWidget()
    helix_layout = QVBoxLayout(tab._helix_settings_container)
    helix_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._helix_preset_slider = VisualizerPresetSlider("helix")
    tab._helix_preset_slider.preset_changed.connect(tab._save_settings)
    helix_layout.addWidget(tab._helix_preset_slider)

    tab._helix_advanced = QWidget()
    _adv = QVBoxLayout(tab._helix_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    tab._helix_preset_slider.set_advanced_container(tab._helix_advanced)

    helix_turns_row = QHBoxLayout()
    helix_turns_row.addWidget(QLabel("Turns:"))
    tab.helix_turns = QSpinBox()
    tab.helix_turns.setRange(2, 12)
    tab.helix_turns.setValue(tab._default_int('spotify_visualizer', 'helix_turns', 4))
    tab.helix_turns.setToolTip("Number of helix turns visible across the card width.")
    tab.helix_turns.valueChanged.connect(tab._save_settings)
    helix_turns_row.addWidget(tab.helix_turns)
    helix_turns_row.addStretch()
    _adv.addLayout(helix_turns_row)

    tab.helix_double = QCheckBox("Double Helix (DNA)")
    tab.helix_double.setChecked(tab._default_bool('spotify_visualizer', 'helix_double', True))
    tab.helix_double.setToolTip("Show a second strand and cross-rungs for a DNA-like appearance.")
    tab.helix_double.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.helix_double)

    helix_speed_row = QHBoxLayout()
    helix_speed_row.addWidget(QLabel("Rotation Speed:"))
    tab.helix_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_speed.setMinimum(0)
    tab.helix_speed.setMaximum(200)
    helix_speed_val = int(tab._default_float('spotify_visualizer', 'helix_speed', 1.0) * 100)
    tab.helix_speed.setValue(helix_speed_val)
    tab.helix_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_speed.setTickInterval(25)
    tab.helix_speed.valueChanged.connect(tab._save_settings)
    helix_speed_row.addWidget(tab.helix_speed)
    tab.helix_speed_label = QLabel(f"{helix_speed_val / 100.0:.2f}x")
    tab.helix_speed.valueChanged.connect(
        lambda v: tab.helix_speed_label.setText(f"{v / 100.0:.2f}x")
    )
    helix_speed_row.addWidget(tab.helix_speed_label)
    _adv.addLayout(helix_speed_row)

    tab.helix_glow_enabled = QCheckBox("Enable Glow")
    tab.helix_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'helix_glow_enabled', True))
    tab.helix_glow_enabled.setToolTip("Draw a soft glow halo around the helix strands.")
    tab.helix_glow_enabled.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.helix_glow_enabled)

    tab._helix_glow_sub_container = QWidget()
    _helix_glow_layout = QVBoxLayout(tab._helix_glow_sub_container)
    _helix_glow_layout.setContentsMargins(16, 0, 0, 0)

    helix_glow_row = QHBoxLayout()
    helix_glow_row.addWidget(QLabel("Glow Intensity:"))
    tab.helix_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_glow_intensity.setMinimum(0)
    tab.helix_glow_intensity.setMaximum(100)
    helix_glow_val = int(tab._default_float('spotify_visualizer', 'helix_glow_intensity', 0.5) * 100)
    tab.helix_glow_intensity.setValue(helix_glow_val)
    tab.helix_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_glow_intensity.setTickInterval(10)
    tab.helix_glow_intensity.valueChanged.connect(tab._save_settings)
    helix_glow_row.addWidget(tab.helix_glow_intensity)
    tab.helix_glow_intensity_label = QLabel(f"{helix_glow_val}%")
    tab.helix_glow_intensity.valueChanged.connect(
        lambda v: tab.helix_glow_intensity_label.setText(f"{v}%")
    )
    helix_glow_row.addWidget(tab.helix_glow_intensity_label)
    _helix_glow_layout.addLayout(helix_glow_row)

    helix_glow_color_row = QHBoxLayout()
    helix_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.helix_glow_color_btn = QPushButton("Choose Color...")
    tab.helix_glow_color_btn.clicked.connect(tab._choose_helix_glow_color)
    helix_glow_color_row.addWidget(tab.helix_glow_color_btn)
    helix_glow_color_row.addStretch()
    _helix_glow_layout.addLayout(helix_glow_color_row)

    tab.helix_reactive_glow = QCheckBox("Reactive Glow")
    tab.helix_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'helix_reactive_glow', True))
    tab.helix_reactive_glow.setToolTip("Glow intensity pulses with audio energy.")
    tab.helix_reactive_glow.stateChanged.connect(tab._save_settings)
    _helix_glow_layout.addWidget(tab.helix_reactive_glow)

    _adv.addWidget(tab._helix_glow_sub_container)

    def _update_helix_glow_vis(_s=None):
        tab._helix_glow_sub_container.setVisible(tab.helix_glow_enabled.isChecked())
    tab.helix_glow_enabled.stateChanged.connect(_update_helix_glow_vis)
    _update_helix_glow_vis()

    helix_growth_row = QHBoxLayout()
    helix_growth_row.addWidget(QLabel("Card Height:"))
    tab.helix_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_growth.setMinimum(100)
    tab.helix_growth.setMaximum(500)
    helix_growth_val = int(tab._default_float('spotify_visualizer', 'helix_growth', 2.0) * 100)
    tab.helix_growth.setValue(helix_growth_val)
    tab.helix_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_growth.setTickInterval(50)
    tab.helix_growth.valueChanged.connect(tab._save_settings)
    helix_growth_row.addWidget(tab.helix_growth)
    tab.helix_growth_label = QLabel(f"{helix_growth_val / 100.0:.1f}x")
    tab.helix_growth.valueChanged.connect(
        lambda v: tab.helix_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    helix_growth_row.addWidget(tab.helix_growth_label)
    _adv.addLayout(helix_growth_row)

    helix_layout.addWidget(tab._helix_advanced)
    parent_layout.addWidget(tab._helix_settings_container)
