"""Persistence binding for the lazy Shockwave Grid Settings body."""
from __future__ import annotations

from PySide6.QtGui import QColor

from ui.color_utils import qcolor_to_list

_SLIDER_KEYS = (
    "shockwave_grid_wave_height",
    "shockwave_grid_wave_speed",
    "shockwave_grid_horizon",
    "shockwave_grid_tilt",
    "shockwave_grid_turn",
    "shockwave_grid_density",
    "shockwave_grid_glow",
    "shockwave_grid_floor",
    "shockwave_grid_idle",
    "shockwave_grid_scroll",
    "shockwave_grid_wave_amplitude",
    "shockwave_grid_profile_floor",
    "shockwave_grid_drop_speed",
    "shockwave_grid_visual_smoothing",
)
_COLOUR_KEYS = ("shockwave_grid_line_color", "shockwave_grid_crest_color")
_TEMPORAL_CHECK_KEYS = ("shockwave_grid_visual_smoothing_enabled", "shockwave_grid_solid_bar_hysteresis_enabled")


def load_shockwave_grid_mode_settings(tab, config) -> None:
    def value(key):
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    for key in _SLIDER_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setValue(round(float(value(key)) * 100.0))
    for key in _COLOUR_KEYS:
        try:
            colour = QColor(*value(key))
        except Exception:
            colour = QColor(*tab._widget_default("spotify_visualizer", key))
        setattr(tab, f"_{key}", colour)
        button = getattr(tab, f"{key}_btn", None)
        if button is not None:
            button.set_color(colour)
    control = getattr(tab, "shockwave_grid_allow_overflow", None)
    if control is not None:
        control.setChecked(bool(value("shockwave_grid_allow_overflow")))
    control = getattr(tab, "shockwave_grid_mirrored", None)
    if control is not None:
        control.setChecked(bool(value("shockwave_grid_mirrored")))
    shape_editor = getattr(tab, "shockwave_grid_shape_editor", None)
    for key in _TEMPORAL_CHECK_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setChecked(bool(value(key)))
    if shape_editor is not None:
        mirrored = bool(value("shockwave_grid_mirrored"))
        shape_editor.set_mirrored(mirrored)
        shape_editor.set_nodes(value("shockwave_grid_shape_nodes"))
        shape_editor.set_notch_positions(value("shockwave_grid_notch_positions_mirrored"), mirrored=True)
        shape_editor.set_notch_positions(value("shockwave_grid_notch_positions_linear"), mirrored=False)
        shape_editor.set_lane_strengths(value("shockwave_grid_lane_strengths_mirrored"), mirrored=True)
        shape_editor.set_lane_strengths(value("shockwave_grid_lane_strengths_linear"), mirrored=False)


def collect_shockwave_grid_mode_settings(tab) -> dict:
    values: dict = {key: getattr(tab, key).value() / 100.0 for key in _SLIDER_KEYS}
    for key in _COLOUR_KEYS:
        values[key] = qcolor_to_list(getattr(tab, f"_{key}", None), tab._widget_default("spotify_visualizer", key))
    values["shockwave_grid_allow_overflow"] = tab.shockwave_grid_allow_overflow.isChecked()
    values["shockwave_grid_mirrored"] = tab.shockwave_grid_mirrored.isChecked()
    values.update({key: getattr(tab, key).isChecked() for key in _TEMPORAL_CHECK_KEYS})
    shape_editor = getattr(tab, "shockwave_grid_shape_editor", None)
    if shape_editor is not None:
        values.update(
            {
                "shockwave_grid_shape_nodes": shape_editor.get_nodes(),
                "shockwave_grid_notch_positions_mirrored": list(shape_editor._notches_mirrored),
                "shockwave_grid_notch_positions_linear": list(shape_editor._notches_linear),
                "shockwave_grid_lane_strengths_mirrored": shape_editor.get_lane_strengths(mirrored=True),
                "shockwave_grid_lane_strengths_linear": shape_editor.get_lane_strengths(mirrored=False),
            }
        )
    return values
