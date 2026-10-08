"""Persistence binding for the lazy Extruded Spectrum Settings body."""
from __future__ import annotations

from rendering.gl_programs.extruded_spectrum_options import EXTRUDED_COLOURINGS

_SLIDER_KEYS = (
    "extruded_spectrum_depth",
    "extruded_spectrum_hue_drift",
    "extruded_spectrum_gloss",
    "extruded_spectrum_reflection",
    "extruded_spectrum_face_mirror",
    "extruded_spectrum_shadow_strength",
    "extruded_spectrum_wave_amplitude",
    "extruded_spectrum_profile_floor",
    "extruded_spectrum_drop_speed",
    "extruded_spectrum_visual_smoothing",
    "extruded_spectrum_ghost_alpha",
    "extruded_spectrum_ghost_decay",
)
_CHECK_KEYS = (
    "extruded_spectrum_allow_overflow",
    "extruded_spectrum_smooth_edges",
    "extruded_spectrum_shadow_enabled",
    "extruded_spectrum_mirrored",
    "extruded_spectrum_ghosting_enabled",
    "extruded_spectrum_visual_smoothing_enabled",
    "extruded_spectrum_solid_bar_hysteresis_enabled",
)


def _resolved_colouring(tab, value) -> str:
    colouring = str(value)
    if colouring in EXTRUDED_COLOURINGS:
        return colouring
    fallback = str(tab._widget_default("spotify_visualizer", "extruded_spectrum_colouring"))
    if fallback not in EXTRUDED_COLOURINGS:
        raise ValueError(f"Canonical Extruded Spectrum colouring is invalid: {fallback!r}")
    return fallback


def load_extruded_spectrum_mode_settings(tab, config) -> None:
    def value(key):
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    for key in _SLIDER_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setValue(round(float(value(key)) * 100.0))

    # The persisted enum is a compatibility/runtime encoding only. Settings
    # presents explicit Rainbow enable + surface participation controls.
    colouring = _resolved_colouring(tab, value("extruded_spectrum_colouring"))
    control = getattr(tab, "extruded_spectrum_rainbow_enabled", None)
    if control is not None:
        control.setChecked(colouring != "Bar Colours")
    faces = getattr(tab, "extruded_spectrum_rainbow_faces", None)
    edges = getattr(tab, "extruded_spectrum_rainbow_edges", None)
    if faces is not None and edges is not None:
        if colouring == "Spectral Edges":
            edges.setChecked(True)
        else:
            faces.setChecked(True)
        enabled = colouring != "Bar Colours"
        faces.setEnabled(enabled)
        edges.setEnabled(enabled)

    reach = getattr(tab, 'extruded_spectrum_shadow_reach', None)
    if reach is not None:
        reach.setCurrentText(str(value('extruded_spectrum_shadow_reach')))
    for key in _CHECK_KEYS:
        control = getattr(tab, key, None)
        if control is not None:
            control.setChecked(bool(value(key)))
    shape_editor = getattr(tab, "extruded_spectrum_shape_editor", None)
    if shape_editor is not None:
        mirrored = bool(value("extruded_spectrum_mirrored"))
        shape_editor.set_mirrored(mirrored)
        shape_editor.set_nodes(value("extruded_spectrum_shape_nodes"))
        shape_editor.set_notch_positions(
            value("extruded_spectrum_notch_positions_mirrored"), mirrored=True
        )
        shape_editor.set_notch_positions(
            value("extruded_spectrum_notch_positions_linear"), mirrored=False
        )
        shape_editor.set_lane_strengths(
            value("extruded_spectrum_lane_strengths_mirrored"), mirrored=True
        )
        shape_editor.set_lane_strengths(
            value("extruded_spectrum_lane_strengths_linear"), mirrored=False
        )


def collect_extruded_spectrum_mode_settings(tab) -> dict:
    values: dict = {key: getattr(tab, key).value() / 100.0 for key in _SLIDER_KEYS}
    if not tab.extruded_spectrum_rainbow_enabled.isChecked():
        values["extruded_spectrum_colouring"] = "Bar Colours"
    elif tab.extruded_spectrum_rainbow_edges.isChecked():
        values["extruded_spectrum_colouring"] = "Spectral Edges"
    else:
        values["extruded_spectrum_colouring"] = "Spectral Faces"
    values.update({key: getattr(tab, key).isChecked() for key in _CHECK_KEYS})
    values['extruded_spectrum_shadow_reach'] = tab.extruded_spectrum_shadow_reach.currentText()
    shape_editor = getattr(tab, "extruded_spectrum_shape_editor", None)
    if shape_editor is not None:
        values.update(
            {
                "extruded_spectrum_shape_nodes": shape_editor.get_nodes(),
                "extruded_spectrum_notch_positions_mirrored": list(shape_editor._notches_mirrored),
                "extruded_spectrum_notch_positions_linear": list(shape_editor._notches_linear),
                "extruded_spectrum_lane_strengths_mirrored": shape_editor.get_lane_strengths(mirrored=True),
                "extruded_spectrum_lane_strengths_linear": shape_editor.get_lane_strengths(mirrored=False),
            }
        )
    return values
