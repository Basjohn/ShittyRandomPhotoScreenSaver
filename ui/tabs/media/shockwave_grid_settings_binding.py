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
)
_COLOUR_KEYS = ("shockwave_grid_line_color", "shockwave_grid_crest_color")


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


def collect_shockwave_grid_mode_settings(tab) -> dict:
    values: dict = {key: getattr(tab, key).value() / 100.0 for key in _SLIDER_KEYS}
    for key in _COLOUR_KEYS:
        values[key] = qcolor_to_list(getattr(tab, f"_{key}", None), tab._widget_default("spotify_visualizer", key))
    values["shockwave_grid_allow_overflow"] = tab.shockwave_grid_allow_overflow.isChecked()
    return values
