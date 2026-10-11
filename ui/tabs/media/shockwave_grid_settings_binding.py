"""Persistence binding for the lazy Shockwave Grid Settings body.

Its spec'd controls load and save through ``ui/tabs/media/spec_mode_builder.py``; the Bar Response
section (Spectrum's shape editor, response sliders, smoothing toggles) through the functions here.
"""
from __future__ import annotations

from ui.tabs.media.shockwave_grid_builder import RESPONSE_SLIDERS
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings

_RESPONSE_SLIDER_KEYS = tuple(key for key, *_ in RESPONSE_SLIDERS) + ("shockwave_grid_visual_smoothing",)
_TEMPORAL_CHECK_KEYS = ("shockwave_grid_visual_smoothing_enabled", "shockwave_grid_solid_bar_hysteresis_enabled")


def load_shockwave_grid_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "shockwave_grid", config)


def collect_shockwave_grid_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "shockwave_grid")


def load_response_section(tab, config) -> None:
    def value(key):
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    for key in _RESPONSE_SLIDER_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setValue(round(float(value(key)) * 100.0))
    control = getattr(tab, "shockwave_grid_mirrored", None)
    if control is not None:
        control.setChecked(bool(value("shockwave_grid_mirrored")))
    for key in _TEMPORAL_CHECK_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setChecked(bool(value(key)))
    shape_editor = getattr(tab, "shockwave_grid_shape_editor", None)
    if shape_editor is not None:
        mirrored = bool(value("shockwave_grid_mirrored"))
        shape_editor.set_mirrored(mirrored)
        shape_editor.set_nodes(value("shockwave_grid_shape_nodes"))
        shape_editor.set_notch_positions(value("shockwave_grid_notch_positions_mirrored"), mirrored=True)
        shape_editor.set_notch_positions(value("shockwave_grid_notch_positions_linear"), mirrored=False)
        shape_editor.set_lane_strengths(value("shockwave_grid_lane_strengths_mirrored"), mirrored=True)
        shape_editor.set_lane_strengths(value("shockwave_grid_lane_strengths_linear"), mirrored=False)


def collect_response_section(tab) -> dict:
    values: dict = {key: getattr(tab, key).value() / 100.0 for key in _RESPONSE_SLIDER_KEYS}
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
