"""Lazy Settings body for the Shockwave Grid visualizer.

The body comes from Shockwave Grid's spec (``core/settings/visualizer_mode_settings.py``); only its
Terrain editor and Advanced Frequency Response/smoothing hooks are built here.
"""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QLabel

from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.media.spec_mode_builder import build_spec_mode_ui
from ui.tabs.shared_styles import add_aligned_row_widget

def build_shockwave_grid_ui(tab, parent_layout) -> None:
    """Build Shockwave Grid's body and its consumed source/technical profile."""

    build_spec_mode_ui(tab, parent_layout, "shockwave_grid")


def _row(layout, label):
    _widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
    return content


def build_response_section(tab, response) -> None:
    """Preserve the independently authored audio-frequency shape and lane routing."""

    content = _row(response, "Mirrored Layout:")
    tab.shockwave_grid_mirrored = QCheckBox("Center-Out (Mirrored Shape)")
    tab.shockwave_grid_mirrored.setProperty("circleIndicator", True)
    tab.shockwave_grid_mirrored.setChecked(
        tab._default_bool("spotify_visualizer", "shockwave_grid_mirrored"))
    tab.shockwave_grid_mirrored.setToolTip(
        "On: use the center-out profile. Off: use the left-to-right profile.")
    bind_setting_signal(tab, tab.shockwave_grid_mirrored.stateChanged, auto_switch=True)
    content.addWidget(tab.shockwave_grid_mirrored)
    content.addStretch()

    hint = QLabel("Left-click to add a control node (max 5). Right-click a node to remove it. Drag to reshape.")
    hint.setWordWrap(True)
    response.addWidget(hint)
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    tab.shockwave_grid_shape_editor = SpectrumShapeEditor(
        parent=None,
        mirrored=tab._default_bool("spotify_visualizer", "shockwave_grid_mirrored"),
        default_nodes=tab._widget_default("spotify_visualizer", "shockwave_grid_shape_nodes"),
        default_notches_mirrored=tab._widget_default("spotify_visualizer", "shockwave_grid_notch_positions_mirrored"),
        default_notches_linear=tab._widget_default("spotify_visualizer", "shockwave_grid_notch_positions_linear"),
        default_lane_strengths_mirrored=tab._widget_default("spotify_visualizer", "shockwave_grid_lane_strengths_mirrored"),
        default_lane_strengths_linear=tab._widget_default("spotify_visualizer", "shockwave_grid_lane_strengths_linear"),
    )
    tab.shockwave_grid_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.shockwave_grid_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.shockwave_grid_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    response.addWidget(tab.shockwave_grid_shape_editor)
    tab.shockwave_grid_mirrored.stateChanged.connect(
        lambda state: tab.shockwave_grid_shape_editor.set_mirrored(bool(state))
    )


def build_smoothing_section(tab, response) -> None:
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls
    build_spectrum_smoothing_controls(tab, response, mode_key="shockwave_grid")


def build_terrain_section(tab, layout) -> None:
    from ui.tabs.media.terrain_editor import TerrainEditor

    tab.shockwave_grid_terrain_editor = TerrainEditor(tab._widget_default("spotify_visualizer", "shockwave_grid_terrain"))
    def changed(_terrain):
        tab._force_visualizer_preset_to_custom("shockwave_grid")
        tab._save_settings()

    tab.shockwave_grid_terrain_editor.terrain_changed.connect(changed)
    layout.addWidget(tab.shockwave_grid_terrain_editor)
