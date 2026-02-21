"""Blob visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
)
from PySide6.QtCore import Qt

from ui.styled_popup import ColorSwatchButton

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Blob settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._blob_settings_container = QWidget()
    blob_layout = QVBoxLayout(tab._blob_settings_container)
    blob_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._blob_preset_slider = VisualizerPresetSlider("blob")
    tab._blob_preset_slider.preset_changed.connect(tab._save_settings)
    blob_layout.addWidget(tab._blob_preset_slider)

    tab._blob_advanced = QWidget()
    _adv = QVBoxLayout(tab._blob_advanced)
    _adv.setContentsMargins(0, 0, 0, 0)
    _adv.setSpacing(4)
    tab._blob_preset_slider.set_advanced_container(tab._blob_advanced)

    blob_pulse_row = QHBoxLayout()
    blob_pulse_row.addWidget(QLabel("Pulse Intensity:"))
    tab.blob_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_pulse.setMinimum(0)
    tab.blob_pulse.setMaximum(200)
    blob_pulse_val = int(tab._default_float('spotify_visualizer', 'blob_pulse', 1.0) * 100)
    tab.blob_pulse.setValue(blob_pulse_val)
    tab.blob_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_pulse.setTickInterval(25)
    tab.blob_pulse.valueChanged.connect(tab._save_settings)
    blob_pulse_row.addWidget(tab.blob_pulse)
    tab.blob_pulse_label = QLabel(f"{blob_pulse_val / 100.0:.2f}x")
    tab.blob_pulse.valueChanged.connect(
        lambda v: tab.blob_pulse_label.setText(f"{v / 100.0:.2f}x")
    )
    blob_pulse_row.addWidget(tab.blob_pulse_label)
    _adv.addLayout(blob_pulse_row)

    tab.blob_reactive_glow = QCheckBox("Reactive Glow")
    tab.blob_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'blob_reactive_glow', True))
    tab.blob_reactive_glow.setToolTip("Outer glow pulses with audio energy.")
    tab.blob_reactive_glow.stateChanged.connect(tab._save_settings)
    _adv.addWidget(tab.blob_reactive_glow)

    tab._blob_glow_sub_container = QWidget()
    _blob_glow_layout = QVBoxLayout(tab._blob_glow_sub_container)
    _blob_glow_layout.setContentsMargins(16, 0, 0, 0)

    blob_glow_color_row = QHBoxLayout()
    blob_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.blob_glow_color_btn = ColorSwatchButton(title="Choose Blob Glow Color")
    tab.blob_glow_color_btn.set_color(getattr(tab, '_blob_glow_color', None))
    tab.blob_glow_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_blob_glow_color', c), tab._save_settings())
    )
    blob_glow_color_row.addWidget(tab.blob_glow_color_btn)
    blob_glow_color_row.addStretch()
    _blob_glow_layout.addLayout(blob_glow_color_row)

    _adv.addWidget(tab._blob_glow_sub_container)

    def _update_blob_glow_vis(_s=None):
        tab._blob_glow_sub_container.setVisible(tab.blob_reactive_glow.isChecked())
    tab.blob_reactive_glow.stateChanged.connect(_update_blob_glow_vis)
    _update_blob_glow_vis()

    blob_fill_color_row = QHBoxLayout()
    blob_fill_color_row.addWidget(QLabel("Fill Color:"))
    tab.blob_fill_color_btn = ColorSwatchButton(title="Choose Blob Fill Color")
    tab.blob_fill_color_btn.set_color(getattr(tab, '_blob_color', None))
    tab.blob_fill_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_blob_color', c), tab._save_settings())
    )
    blob_fill_color_row.addWidget(tab.blob_fill_color_btn)
    blob_fill_color_row.addStretch()
    _adv.addLayout(blob_fill_color_row)

    blob_edge_color_row = QHBoxLayout()
    blob_edge_color_row.addWidget(QLabel("Edge Color:"))
    tab.blob_edge_color_btn = ColorSwatchButton(title="Choose Blob Edge Color")
    tab.blob_edge_color_btn.set_color(getattr(tab, '_blob_edge_color', None))
    tab.blob_edge_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_blob_edge_color', c), tab._save_settings())
    )
    blob_edge_color_row.addWidget(tab.blob_edge_color_btn)
    blob_edge_color_row.addStretch()
    _adv.addLayout(blob_edge_color_row)

    blob_outline_color_row = QHBoxLayout()
    blob_outline_color_row.addWidget(QLabel("Outline Color:"))
    tab.blob_outline_color_btn = ColorSwatchButton(title="Choose Blob Outline Color")
    tab.blob_outline_color_btn.set_color(getattr(tab, '_blob_outline_color', None))
    tab.blob_outline_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_blob_outline_color', c), tab._save_settings())
    )
    blob_outline_color_row.addWidget(tab.blob_outline_color_btn)
    blob_outline_color_row.addStretch()
    _adv.addLayout(blob_outline_color_row)

    blob_width_row = QHBoxLayout()
    blob_width_row.addWidget(QLabel("Card Width:"))
    tab.blob_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_width.setMinimum(30)
    tab.blob_width.setMaximum(100)
    blob_width_val = int(tab._default_float('spotify_visualizer', 'blob_width', 1.0) * 100)
    tab.blob_width.setValue(blob_width_val)
    tab.blob_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_width.setTickInterval(10)
    tab.blob_width.valueChanged.connect(tab._save_settings)
    blob_width_row.addWidget(tab.blob_width)
    tab.blob_width_label = QLabel(f"{blob_width_val}%")
    tab.blob_width.valueChanged.connect(
        lambda v: tab.blob_width_label.setText(f"{v}%")
    )
    blob_width_row.addWidget(tab.blob_width_label)
    _adv.addLayout(blob_width_row)

    blob_size_row = QHBoxLayout()
    blob_size_row.addWidget(QLabel("Blob Size:"))
    tab.blob_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_size.setMinimum(30)
    tab.blob_size.setMaximum(200)
    blob_size_val = int(tab._default_float('spotify_visualizer', 'blob_size', 1.0) * 100)
    tab.blob_size.setValue(blob_size_val)
    tab.blob_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_size.setTickInterval(20)
    tab.blob_size.setToolTip("Scale of the blob relative to the card. 100% = default.")
    tab.blob_size.valueChanged.connect(tab._save_settings)
    blob_size_row.addWidget(tab.blob_size)
    tab.blob_size_label = QLabel(f"{blob_size_val}%")
    tab.blob_size.valueChanged.connect(
        lambda v: tab.blob_size_label.setText(f"{v}%")
    )
    blob_size_row.addWidget(tab.blob_size_label)
    _adv.addLayout(blob_size_row)

    blob_gi_row = QHBoxLayout()
    blob_gi_row.addWidget(QLabel("Glow Intensity:"))
    tab.blob_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_intensity.setMinimum(0)
    tab.blob_glow_intensity.setMaximum(100)
    blob_gi_val = int(tab._default_float('spotify_visualizer', 'blob_glow_intensity', 0.5) * 100)
    tab.blob_glow_intensity.setValue(blob_gi_val)
    tab.blob_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_intensity.setTickInterval(10)
    tab.blob_glow_intensity.setToolTip("Controls the size and brightness of the glow around the blob.")
    tab.blob_glow_intensity.valueChanged.connect(tab._save_settings)
    blob_gi_row.addWidget(tab.blob_glow_intensity)
    tab.blob_glow_intensity_label = QLabel(f"{blob_gi_val}%")
    tab.blob_glow_intensity.valueChanged.connect(
        lambda v: tab.blob_glow_intensity_label.setText(f"{v}%")
    )
    blob_gi_row.addWidget(tab.blob_glow_intensity_label)
    _adv.addLayout(blob_gi_row)

    blob_rd_row = QHBoxLayout()
    blob_rd_row.addWidget(QLabel("Reactive Deformation:"))
    tab.blob_reactive_deformation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_deformation.setMinimum(0)
    tab.blob_reactive_deformation.setMaximum(300)
    blob_rd_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_deformation', 1.0) * 100)
    tab.blob_reactive_deformation.setValue(blob_rd_val)
    tab.blob_reactive_deformation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_deformation.setTickInterval(50)
    tab.blob_reactive_deformation.setToolTip(
        "Scales overall outward energy-driven growth. "
        "0% = no deformation, 100% = default, 300% = extreme."
    )
    tab.blob_reactive_deformation.valueChanged.connect(tab._save_settings)
    blob_rd_row.addWidget(tab.blob_reactive_deformation)
    tab.blob_reactive_deformation_label = QLabel(f"{blob_rd_val}%")
    tab.blob_reactive_deformation.valueChanged.connect(
        lambda v: tab.blob_reactive_deformation_label.setText(f"{v}%")
    )
    blob_rd_row.addWidget(tab.blob_reactive_deformation_label)
    _adv.addLayout(blob_rd_row)

    blob_cw_row = QHBoxLayout()
    blob_cw_row.addWidget(QLabel("Constant Wobble:"))
    tab.blob_constant_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_constant_wobble.setMinimum(0)
    tab.blob_constant_wobble.setMaximum(200)
    blob_cw_val = int(tab._default_float('spotify_visualizer', 'blob_constant_wobble', 1.0) * 100)
    tab.blob_constant_wobble.setValue(blob_cw_val)
    tab.blob_constant_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_constant_wobble.setTickInterval(25)
    tab.blob_constant_wobble.setToolTip(
        "Base wobble amplitude present even during silence. "
        "0% = flat, 100% = default organic motion, 200% = exaggerated."
    )
    tab.blob_constant_wobble.valueChanged.connect(tab._save_settings)
    blob_cw_row.addWidget(tab.blob_constant_wobble)
    tab.blob_constant_wobble_label = QLabel(f"{blob_cw_val}%")
    tab.blob_constant_wobble.valueChanged.connect(
        lambda v: tab.blob_constant_wobble_label.setText(f"{v}%")
    )
    blob_cw_row.addWidget(tab.blob_constant_wobble_label)
    _adv.addLayout(blob_cw_row)

    blob_rw_row = QHBoxLayout()
    blob_rw_row.addWidget(QLabel("Reactive Wobble:"))
    tab.blob_reactive_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_wobble.setMinimum(0)
    tab.blob_reactive_wobble.setMaximum(200)
    blob_rw_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_wobble', 1.0) * 100)
    tab.blob_reactive_wobble.setValue(blob_rw_val)
    tab.blob_reactive_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_wobble.setTickInterval(25)
    tab.blob_reactive_wobble.setToolTip(
        "Energy-driven wobble amplitude (mostly vocals/mid). "
        "0% = no audio reaction, 100% = default, 200% = exaggerated."
    )
    tab.blob_reactive_wobble.valueChanged.connect(tab._save_settings)
    blob_rw_row.addWidget(tab.blob_reactive_wobble)
    tab.blob_reactive_wobble_label = QLabel(f"{blob_rw_val}%")
    tab.blob_reactive_wobble.valueChanged.connect(
        lambda v: tab.blob_reactive_wobble_label.setText(f"{v}%")
    )
    blob_rw_row.addWidget(tab.blob_reactive_wobble_label)
    _adv.addLayout(blob_rw_row)

    blob_st_row = QHBoxLayout()
    blob_st_row.addWidget(QLabel("Stretch Tendency:"))
    tab.blob_stretch_tendency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch_tendency.setMinimum(0)
    tab.blob_stretch_tendency.setMaximum(100)
    blob_st_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_tendency', 0.0) * 100)
    tab.blob_stretch_tendency.setValue(max(0, min(100, blob_st_val)))
    tab.blob_stretch_tendency.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_tendency.setTickInterval(10)
    tab.blob_stretch_tendency.setToolTip(
        "Bias deformation toward horizontal stretching rather than uniform growth. "
        "0% = uniform (default), 100% = fully horizontal stretch."
    )
    tab.blob_stretch_tendency.valueChanged.connect(tab._save_settings)
    blob_st_row.addWidget(tab.blob_stretch_tendency)
    tab.blob_stretch_tendency_label = QLabel(f"{blob_st_val}%")
    tab.blob_stretch_tendency.valueChanged.connect(
        lambda v: tab.blob_stretch_tendency_label.setText(f"{v}%")
    )
    blob_st_row.addWidget(tab.blob_stretch_tendency_label)
    _adv.addLayout(blob_st_row)

    blob_layout.addWidget(tab._blob_advanced)
    parent_layout.addWidget(tab._blob_settings_container)


def build_blob_growth(tab: "WidgetsTab") -> None:
    """Append height growth slider to the blob advanced container."""
    from ui.tabs.widgets_tab import NoWheelSlider

    blob_layout = tab._blob_advanced.layout()
    blob_growth_row = QHBoxLayout()
    blob_growth_row.addWidget(QLabel("Card Height:"))
    tab.blob_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_growth.setMinimum(100)
    tab.blob_growth.setMaximum(500)
    blob_growth_val = int(tab._default_float('spotify_visualizer', 'blob_growth', 2.5) * 100)
    tab.blob_growth.setValue(blob_growth_val)
    tab.blob_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_growth.setTickInterval(50)
    tab.blob_growth.valueChanged.connect(tab._save_settings)
    blob_growth_row.addWidget(tab.blob_growth)
    tab.blob_growth_label = QLabel(f"{blob_growth_val / 100.0:.1f}x")
    tab.blob_growth.valueChanged.connect(
        lambda v: tab.blob_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    blob_growth_row.addWidget(tab.blob_growth_label)
    blob_layout.addLayout(blob_growth_row)
