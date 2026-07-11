"""Mighty Blob-specific settings UI builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.shared_styles import add_aligned_row_widget

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_mighty_controls(
    tab: "WidgetsTab",
    parent_layout: QVBoxLayout,
    *,
    label_width: int,
) -> QWidget:
    """Build and return the controls owned exclusively by Mighty Blob."""
    from ui.tabs.widgets_tab import NoWheelSlider

    container = QWidget()
    container.setObjectName("blobMightyControls")
    tab._blob_mighty_container = container
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 4, 0, 0)
    layout.setSpacing(4)

    def _row(label_text: str):
        row_widget, content, _ = add_aligned_row_widget(
            layout,
            label_text,
            label_width=label_width,
        )
        return row_widget, content

    rd_row, rd_layout = _row("Shape Reactivity:")
    tab._blob_shape_reactivity_row = rd_row
    tab.blob_reactive_deformation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_deformation.setMinimum(0)
    tab.blob_reactive_deformation.setMaximum(300)
    value = int(tab._default_float("spotify_visualizer", "blob_reactive_deformation", 1.0) * 100)
    tab.blob_reactive_deformation.setValue(max(0, min(300, value)))
    tab.blob_reactive_deformation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_deformation.setTickInterval(50)
    tab.blob_reactive_deformation.setToolTip(
        "Scales Mighty Blob's overall outward music-driven deformation."
    )
    tab.blob_reactive_deformation_label = QLabel(f"{tab.blob_reactive_deformation.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_reactive_deformation.valueChanged,
        updater=lambda v: tab.blob_reactive_deformation_label.setText(f"{v}%"),
    )
    rd_layout.addWidget(tab.blob_reactive_deformation)
    rd_layout.addWidget(tab.blob_reactive_deformation_label)

    wobble_row, wobble_layout = _row("Idle Edge Motion:")
    tab._blob_idle_edge_motion_row = wobble_row
    tab.blob_constant_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_constant_wobble.setMinimum(0)
    tab.blob_constant_wobble.setMaximum(200)
    value = int(tab._default_float("spotify_visualizer", "blob_constant_wobble", 1.0) * 100)
    tab.blob_constant_wobble.setValue(max(0, min(200, value)))
    tab.blob_constant_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_constant_wobble.setTickInterval(25)
    tab.blob_constant_wobble.setToolTip(
        "Subtle always-on living motion for Mighty Blob, even when audio is calm."
    )
    tab.blob_constant_wobble_label = QLabel(f"{tab.blob_constant_wobble.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_constant_wobble.valueChanged,
        updater=lambda v: tab.blob_constant_wobble_label.setText(f"{v}%"),
    )
    wobble_layout.addWidget(tab.blob_constant_wobble)
    wobble_layout.addWidget(tab.blob_constant_wobble_label)

    music_row, music_layout = _row("Audio Edge Motion:")
    tab._blob_audio_edge_motion_row = music_row
    tab.blob_reactive_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_wobble.setMinimum(0)
    tab.blob_reactive_wobble.setMaximum(300)
    value = int(tab._default_float("spotify_visualizer", "blob_reactive_wobble", 1.0) * 100)
    tab.blob_reactive_wobble.setValue(max(0, min(300, value)))
    tab.blob_reactive_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_wobble.setTickInterval(25)
    tab.blob_reactive_wobble.setToolTip(
        "Music-driven organic edge motion layered over Mighty Blob's living wobble."
    )
    tab.blob_reactive_wobble_label = QLabel(f"{tab.blob_reactive_wobble.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_reactive_wobble.valueChanged,
        updater=lambda v: tab.blob_reactive_wobble_label.setText(f"{v}%"),
    )
    music_layout.addWidget(tab.blob_reactive_wobble)
    music_layout.addWidget(tab.blob_reactive_wobble_label)

    stretch_row, stretch_layout = _row("Stretch:")
    tab._blob_stretch_row = stretch_row
    tab.blob_stretch = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch.setMinimum(0)
    tab.blob_stretch.setMaximum(100)
    value = int(tab._default_float("spotify_visualizer", "blob_stretch", 0.35) * 100)
    tab.blob_stretch.setValue(max(0, min(100, value)))
    tab.blob_stretch.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch.setTickInterval(10)
    tab.blob_stretch.setToolTip(
        "How far music can extend Mighty Blob into smooth outward tendrils."
    )
    tab.blob_stretch_label = QLabel(f"{tab.blob_stretch.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_stretch.valueChanged,
        updater=lambda v: tab.blob_stretch_label.setText(f"{v}%"),
    )
    stretch_layout.addWidget(tab.blob_stretch)
    stretch_layout.addWidget(tab.blob_stretch_label)

    parent_layout.addWidget(container)
    return container
