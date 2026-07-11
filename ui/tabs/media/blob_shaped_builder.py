"""Shaped Blob-specific settings UI builder."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

from ui.tabs.media.blob_shape_editor import BlobShapeEditor
from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.shared_styles import add_aligned_row_widget
from ui.widgets import StyledComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_shaped_controls(
    tab: "WidgetsTab",
    parent_layout: QVBoxLayout,
    *,
    label_width: int,
) -> QWidget:
    """Build and return the controls owned exclusively by Shaped Blob."""
    from ui.tabs.widgets_tab import NoWheelSlider

    container = QWidget()
    container.setObjectName("blobShapedControls")
    tab._blob_shaped_container = container
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

    _base_row, base_layout = _row("Authored Shape:")
    tab.blob_shaper_base_strength = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_shaper_base_strength.setMinimum(0)
    tab.blob_shaper_base_strength.setMaximum(100)
    value = int(tab._default_float("spotify_visualizer", "blob_shaper_base_strength", 0.5) * 100)
    tab.blob_shaper_base_strength.setValue(max(0, min(100, value)))
    tab.blob_shaper_base_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_shaper_base_strength.setTickInterval(10)
    tab.blob_shaper_base_strength.setToolTip(
        "How strongly Shaped Blob follows the authored base silhouette. Even 0% retains a protected amount of shape relief."
    )
    tab.blob_shaper_base_strength_label = QLabel(f"{value}%")
    bind_setting_signal(
        tab,
        tab.blob_shaper_base_strength.valueChanged,
        updater=lambda v: tab.blob_shaper_base_strength_label.setText(f"{v}%"),
    )
    base_layout.addWidget(tab.blob_shaper_base_strength)
    base_layout.addWidget(tab.blob_shaper_base_strength_label)
    reaction_row, reaction_layout = _row("React Strength:")
    tab.blob_shaper_react_strength = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_shaper_react_strength.setMinimum(0)
    tab.blob_shaper_react_strength.setMaximum(100)
    value = int(tab._default_float("spotify_visualizer", "blob_shaper_react_strength", 0.5) * 100)
    tab.blob_shaper_react_strength.setValue(max(0, min(100, value)))
    tab.blob_shaper_react_strength.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_shaper_react_strength.setTickInterval(10)
    tab.blob_shaper_react_strength.setToolTip(
        "How strongly music can pull the contour toward the authored reaction silhouette."
    )
    tab.blob_shaper_react_strength_label = QLabel(f"{value}%")
    bind_setting_signal(
        tab,
        tab.blob_shaper_react_strength.valueChanged,
        updater=lambda v: tab.blob_shaper_react_strength_label.setText(f"{v}%"),
    )
    reaction_layout.addWidget(tab.blob_shaper_react_strength)
    reaction_layout.addWidget(tab.blob_shaper_react_strength_label)

    living_row, living_layout = _row("Living Wobble:")
    tab._blob_shaper_idle_motion_row = living_row
    tab.blob_shaper_idle_motion = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_shaper_idle_motion.setMinimum(0)
    tab.blob_shaper_idle_motion.setMaximum(200)
    value = int(tab._default_float("spotify_visualizer", "blob_shaper_idle_motion", 0.18) * 100)
    tab.blob_shaper_idle_motion.setValue(max(0, min(200, value)))
    tab.blob_shaper_idle_motion.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_shaper_idle_motion.setTickInterval(25)
    tab.blob_shaper_idle_motion.setToolTip(
        "Always-on contour motion that keeps the authored Shaped Blob silhouette alive."
    )
    tab.blob_shaper_idle_motion_label = QLabel(f"{value}%")
    bind_setting_signal(
        tab,
        tab.blob_shaper_idle_motion.valueChanged,
        updater=lambda v: tab.blob_shaper_idle_motion_label.setText(f"{v}%"),
    )
    living_layout.addWidget(tab.blob_shaper_idle_motion)
    living_layout.addWidget(tab.blob_shaper_idle_motion_label)

    mutation_row, mutation_layout = _row("Music Mutation:")
    tab._blob_shaper_audio_motion_row = mutation_row
    tab.blob_shaper_audio_motion = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_shaper_audio_motion.setMinimum(0)
    tab.blob_shaper_audio_motion.setMaximum(300)
    value = int(tab._default_float("spotify_visualizer", "blob_shaper_audio_motion", 1.20) * 100)
    tab.blob_shaper_audio_motion.setValue(max(0, min(300, value)))
    tab.blob_shaper_audio_motion.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_shaper_audio_motion.setTickInterval(25)
    tab.blob_shaper_audio_motion.setToolTip(
        "Music-driven local deviations that return cleanly to the authored goal shape."
    )
    tab.blob_shaper_audio_motion_label = QLabel(f"{value}%")
    bind_setting_signal(
        tab,
        tab.blob_shaper_audio_motion.valueChanged,
        updater=lambda v: tab.blob_shaper_audio_motion_label.setText(f"{v}%"),
    )
    mutation_layout.addWidget(tab.blob_shaper_audio_motion)
    mutation_layout.addWidget(tab.blob_shaper_audio_motion_label)

    topology_row, topology_layout = _row("Topology:")
    tab._blob_topology_row = topology_row
    tab.blob_topology_combo = StyledComboBox()
    tab.blob_topology_combo.addItems(["Circle (Filled)", "Ring (Hollow)"])
    default = tab._default_str("spotify_visualizer", "blob_topology", "circle")
    tab.blob_topology_combo.setCurrentIndex(1 if str(default).lower() == "ring" else 0)
    tab.blob_topology_combo.setToolTip("Choose a filled contour or a hollow ring goal shape.")
    bind_setting_signal(tab, tab.blob_topology_combo.currentIndexChanged, auto_switch=True)
    topology_layout.addWidget(tab.blob_topology_combo)

    ring_row, ring_layout = _row("Ring Thickness:")
    tab._blob_ring_thickness_row = ring_row
    tab.blob_ring_thickness = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_ring_thickness.setMinimum(5)
    tab.blob_ring_thickness.setMaximum(100)
    value = int(tab._default_float("spotify_visualizer", "blob_ring_thickness", 0.3) * 100)
    tab.blob_ring_thickness.setValue(max(5, min(100, value)))
    tab.blob_ring_thickness.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_ring_thickness.setTickInterval(10)
    tab.blob_ring_thickness.setToolTip("Wall thickness of the authored ring as a fraction of its radius.")
    tab.blob_ring_thickness_label = QLabel(f"{value}%")
    bind_setting_signal(
        tab,
        tab.blob_ring_thickness.valueChanged,
        updater=lambda v: tab.blob_ring_thickness_label.setText(f"{v}%"),
    )
    ring_layout.addWidget(tab.blob_ring_thickness)
    ring_layout.addWidget(tab.blob_ring_thickness_label)

    tab.blob_shape_editor = BlobShapeEditor()
    bind_setting_signal(tab, tab.blob_shape_editor.nodes_changed, auto_switch=True)
    layout.addWidget(tab.blob_shape_editor)

    def _sync_ring_mode(*_args) -> None:
        is_ring = tab.blob_topology_combo.currentIndex() == 1
        thickness = tab.blob_ring_thickness.value() / 100.0
        ring_row.setVisible(is_ring)
        ring_row.setEnabled(is_ring)
        tab.blob_shape_editor.set_ring_mode(is_ring, thickness)

    tab.blob_topology_combo.currentIndexChanged.connect(_sync_ring_mode)
    tab.blob_ring_thickness.valueChanged.connect(_sync_ring_mode)
    tab._sync_blob_shaped_ring_mode = _sync_ring_mode
    _sync_ring_mode()

    parent_layout.addWidget(container)
    return container
