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


def build_reaction_shaper_section(tab, layout) -> None:
    """The shared shape editor along the land's height: where the music reshapes it, and which
    part of the spectrum moves which elevation. Shown with React to Music."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor

    default = tab._widget_default("spotify_visualizer", "shockwave_grid_terrain_shaper")
    host = QWidget()
    column = QVBoxLayout(host)
    column.setContentsMargins(0, 0, 0, 0)
    hint = QLabel("Left: shoreline. Right: summits. The curve sets how much each height moves; drag the "
                  "lane labels to choose which part of the spectrum moves which height, and the top arrows "
                  "for each lane's strength.")
    hint.setWordWrap(True)
    column.addWidget(hint)
    editor = SpectrumShapeEditor(
        parent=None, mirrored=False, default_nodes=default["nodes"],
        default_notches_mirrored=default["notches"], default_notches_linear=default["notches"],
        default_lane_strengths_mirrored=default["lanes"], default_lane_strengths_linear=default["lanes"])
    editor.setToolTip("Left-click: add node (max 5)\nRight-click node: remove\nDrag node: how much each "
                      "height moves\nDrag bottom labels: which lane moves which height\nDrag top arrows: "
                      "each lane's strength")

    def changed(*_args) -> None:
        tab._force_visualizer_preset_to_custom("shockwave_grid")
        tab._save_settings()

    for signal in (editor.nodes_changed, editor.notch_positions_changed, editor.lane_strengths_changed):
        signal.connect(changed)
    column.addWidget(editor)
    layout.addWidget(host)
    tab.shockwave_grid_terrain_shaper_editor = editor
    tab._shockwave_grid_terrain_shaper_host = host
    toggle = tab.shockwave_grid_terrain_reaction_enabled
    toggle.toggled.connect(host.setVisible)
    host.setVisible(toggle.isChecked())


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
    tab.shockwave_grid_terrain_editor.celestial_changed.connect(lambda position: place_celestial_body(tab, position))
    layout.addWidget(tab.shockwave_grid_terrain_editor)


# What the terrain editor's 3/4 view draws from Settings: the scene's colours and its Sun / Moon.
SCENE_PREVIEW_KEYS = tuple("shockwave_grid_" + key for key in (
    "sky_color", "terrain_fill_color", "water_color", "line_color", "crest_color", "sun_color", "moon_color",
    "sun_enabled", "sun_mode", "sun_x", "sun_y", "sun_z", "sun_size", "moon_phase", "terrain_height"))


def refresh_scene_preview(tab) -> None:
    """Hand the terrain editor's 3/4 view the scene's current colours and Sun / Moon."""
    editor = getattr(tab, "shockwave_grid_terrain_editor", None)
    if editor is None:
        return
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings
    values = collect_spec_mode_settings(tab, "shockwave_grid")
    editor.set_scene({key: values[key] for key in SCENE_PREVIEW_KEYS if key in values})


def connect_scene_preview(tab) -> None:
    """Follow every Setting the 3/4 view draws (once; the controls exist once the mode body is built)."""
    if getattr(tab, "_shockwave_grid_scene_preview_connected", False):
        return
    for key in SCENE_PREVIEW_KEYS:
        widget = getattr(tab, key + "_btn", None) or getattr(tab, key, None)
        for name in ("color_changed", "valueChanged", "toggled", "currentTextChanged"):
            signal = getattr(widget, name, None)
            if signal is not None:
                signal.connect(lambda *_: refresh_scene_preview(tab))
                break
    tab._shockwave_grid_scene_preview_connected = True


def place_celestial_body(tab, position: dict) -> None:
    """The Sun / Moon dragged in the terrain editor's 3/4 view: set its Position X / Y / Z like any edit."""
    from core.settings.visualizer_mode_settings import require_mode_settings
    spec = require_mode_settings("shockwave_grid")
    for axis in ("x", "y", "z"):
        key = "shockwave_grid_sun_" + axis
        control = spec.control(key)
        widget = getattr(tab, key, None)
        if widget is None:
            continue
        # One placement is one edit: the three controls change silently, then one Custom + save below.
        blocked = widget.blockSignals(True)
        try:
            widget.setValue(round(float(control.admit(position[axis], control.low)) * control.scale))
        finally:
            widget.blockSignals(blocked)
        label = getattr(tab, key + "_label", None)
        if label is not None:
            label.setText(control.text(widget.value()))
    tab._force_visualizer_preset_to_custom("shockwave_grid")
    tab._save_settings()
