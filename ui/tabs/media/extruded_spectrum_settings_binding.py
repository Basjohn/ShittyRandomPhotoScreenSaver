"""Persistence binding for the lazy Extruded Spectrum Settings body."""
from __future__ import annotations

_SLIDER_KEYS = (
    "extruded_spectrum_depth",
    "extruded_spectrum_tilt",
    "extruded_spectrum_turn",
    "extruded_spectrum_hue_drift",
    "extruded_spectrum_gloss",
    "extruded_spectrum_reflection",
)


def load_extruded_spectrum_mode_settings(tab, config) -> None:
    def value(key):
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    for key in _SLIDER_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setValue(round(float(value(key)) * 100.0))
    control = getattr(tab, "extruded_spectrum_colouring", None)
    if control is not None:
        control.setCurrentText(str(value("extruded_spectrum_colouring")))
    control = getattr(tab, "extruded_spectrum_allow_overflow", None)
    if control is not None:
        control.setChecked(bool(value("extruded_spectrum_allow_overflow")))


def collect_extruded_spectrum_mode_settings(tab) -> dict:
    values: dict = {key: getattr(tab, key).value() / 100.0 for key in _SLIDER_KEYS}
    values["extruded_spectrum_colouring"] = tab.extruded_spectrum_colouring.currentText()
    values["extruded_spectrum_allow_overflow"] = tab.extruded_spectrum_allow_overflow.isChecked()
    return values
