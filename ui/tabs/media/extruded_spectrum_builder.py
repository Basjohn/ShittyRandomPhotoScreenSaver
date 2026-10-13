"""Bespoke parts of the lazy Extruded Spectrum spec-built Settings body."""
from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel
from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs.shared_styles import add_aligned_row_widget


def row(layout, label):
    _widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
    return content


def build_extruded_spectrum_ui(tab, parent_layout) -> None:
    from ui.tabs.media.spec_mode_builder import build_spec_mode_ui

    build_spec_mode_ui(tab, parent_layout, "extruded_spectrum")


def build_extruded_rainbow(tab, appearance) -> None:
    # The old Spectral Faces / Spectral Edges / Bar Colours combo remains only
    # as persisted/runtime compatibility state. Product authoring is explicit:
    # enable Rainbow, then choose which surface participates.
    default_colouring = tab._default_str("spotify_visualizer", "extruded_spectrum_colouring")
    content = row(appearance, "Rainbow:")
    tab.extruded_spectrum_rainbow_enabled = QCheckBox("Enable Rainbow")
    tab.extruded_spectrum_rainbow_enabled.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_enabled.setChecked(default_colouring != "Bar Colours")
    tab.extruded_spectrum_rainbow_enabled.setToolTip(
        "Off: use the authored Fill/Border colours. On: apply spectral hues to the selected bar surface."
    )
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_enabled.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_rainbow_enabled)
    content.addStretch()

    content = row(appearance, "Rainbow On:")
    tab.extruded_spectrum_rainbow_faces = QCheckBox("Faces")
    tab.extruded_spectrum_rainbow_faces.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_faces.setToolTip(
        "Apply spectral hues to the 3D bar faces while edges keep the authored Border colour."
    )
    tab.extruded_spectrum_rainbow_edges = QCheckBox("Edges")
    tab.extruded_spectrum_rainbow_edges.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_edges.setToolTip(
        "Apply spectral hues to the bar edges while faces keep the authored Fill colour."
    )
    tab._extruded_spectrum_rainbow_surface_group = QButtonGroup(tab)
    tab._extruded_spectrum_rainbow_surface_group.setExclusive(True)
    tab._extruded_spectrum_rainbow_surface_group.addButton(tab.extruded_spectrum_rainbow_faces)
    tab._extruded_spectrum_rainbow_surface_group.addButton(tab.extruded_spectrum_rainbow_edges)
    if default_colouring == "Spectral Edges":
        tab.extruded_spectrum_rainbow_edges.setChecked(True)
    else:
        tab.extruded_spectrum_rainbow_faces.setChecked(True)
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_faces.toggled, auto_switch=True)
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_edges.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_rainbow_faces)
    content.addWidget(tab.extruded_spectrum_rainbow_edges)
    content.addStretch()

    def _update_rainbow_surface_enabled(_checked=None):
        enabled = tab.extruded_spectrum_rainbow_enabled.isChecked()
        tab.extruded_spectrum_rainbow_faces.setEnabled(enabled)
        tab.extruded_spectrum_rainbow_edges.setEnabled(enabled)

    tab.extruded_spectrum_rainbow_enabled.toggled.connect(_update_rainbow_surface_enabled)
    _update_rainbow_surface_enabled()


def build_extruded_shape(tab, shape) -> None:
    content = row(shape, "Mirrored Layout:")
    tab.extruded_spectrum_mirrored = QCheckBox("Center-Out (Mirrored Shape)")
    tab.extruded_spectrum_mirrored.setProperty("circleIndicator", True)
    tab.extruded_spectrum_mirrored.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_mirrored"))
    tab.extruded_spectrum_mirrored.setToolTip(
        "On: use the center-out profile. Off: use the left-to-right profile.")
    bind_setting_signal(tab, tab.extruded_spectrum_mirrored.stateChanged, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_mirrored)
    content.addStretch()

    hint = QLabel("Left-click to add a control node (max 5). Right-click a node to remove it. Drag to reshape.")
    hint.setWordWrap(True)
    shape.addWidget(hint)
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    tab.extruded_spectrum_shape_editor = SpectrumShapeEditor(
        parent=None,
        mirrored=tab._default_bool("spotify_visualizer", "extruded_spectrum_mirrored"),
        default_nodes=tab._widget_default("spotify_visualizer", "extruded_spectrum_shape_nodes"),
        default_notches_mirrored=tab._widget_default("spotify_visualizer", "extruded_spectrum_notch_positions_mirrored"),
        default_notches_linear=tab._widget_default("spotify_visualizer", "extruded_spectrum_notch_positions_linear"),
        default_lane_strengths_mirrored=tab._widget_default("spotify_visualizer", "extruded_spectrum_lane_strengths_mirrored"),
        default_lane_strengths_linear=tab._widget_default("spotify_visualizer", "extruded_spectrum_lane_strengths_linear"),
    )
    tab.extruded_spectrum_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.extruded_spectrum_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.extruded_spectrum_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    shape.addWidget(tab.extruded_spectrum_shape_editor)
    tab.extruded_spectrum_mirrored.stateChanged.connect(
        lambda state: tab.extruded_spectrum_shape_editor.set_mirrored(bool(state))
    )


def build_extruded_smoothing(tab, response) -> None:
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls

    build_spectrum_smoothing_controls(tab, response, mode_key="extruded_spectrum")
