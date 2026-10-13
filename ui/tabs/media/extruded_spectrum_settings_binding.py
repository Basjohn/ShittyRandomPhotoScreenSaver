"""Bespoke persistence hooks for the Extruded Spectrum spec-built Settings body."""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker

from core.settings.visualizer_mode_settings import require_mode_settings
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_extruded_spectrum_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "extruded_spectrum", config)


def collect_extruded_spectrum_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "extruded_spectrum")


def load_extruded_rainbow(tab, config) -> None:
    key = "extruded_spectrum_colouring"
    default = tab._widget_default("spotify_visualizer", key)
    colouring = require_mode_settings("extruded_spectrum").control(key).admit(config.get(key, default), default)
    controls = (tab.extruded_spectrum_rainbow_enabled, tab.extruded_spectrum_rainbow_faces,
                tab.extruded_spectrum_rainbow_edges)
    blockers = [QSignalBlocker(control) for control in controls]
    enabled, faces, edges = controls
    enabled.setChecked(colouring != "Bar Colours")
    (edges if colouring == "Spectral Edges" else faces).setChecked(True)
    faces.setEnabled(enabled.isChecked())
    edges.setEnabled(enabled.isChecked())
    del blockers


def collect_extruded_rainbow(tab) -> dict:
    return {"extruded_spectrum_colouring": (
        "Bar Colours" if not tab.extruded_spectrum_rainbow_enabled.isChecked()
        else "Spectral Edges" if tab.extruded_spectrum_rainbow_edges.isChecked()
        else "Spectral Faces"
    )}


def load_extruded_shape(tab, config) -> None:
    def value(suffix):
        key = f"extruded_spectrum_{suffix}"
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    editor = tab.extruded_spectrum_shape_editor
    blockers = [QSignalBlocker(editor), QSignalBlocker(tab.extruded_spectrum_mirrored)]
    mirrored = bool(value("mirrored"))
    tab.extruded_spectrum_mirrored.setChecked(mirrored)
    editor.set_mirrored(mirrored)
    editor.set_nodes(value("shape_nodes"))
    for mirror, suffix in ((True, "mirrored"), (False, "linear")):
        editor.set_notch_positions(value(f"notch_positions_{suffix}"), mirrored=mirror)
        editor.set_lane_strengths(value(f"lane_strengths_{suffix}"), mirrored=mirror)
    del blockers


def collect_extruded_shape(tab) -> dict:
    editor = tab.extruded_spectrum_shape_editor
    return {
        "extruded_spectrum_mirrored": tab.extruded_spectrum_mirrored.isChecked(),
        "extruded_spectrum_shape_nodes": editor.get_nodes(),
        "extruded_spectrum_notch_positions_mirrored": list(editor._notches_mirrored),
        "extruded_spectrum_notch_positions_linear": list(editor._notches_linear),
        "extruded_spectrum_lane_strengths_mirrored": editor.get_lane_strengths(mirrored=True),
        "extruded_spectrum_lane_strengths_linear": editor.get_lane_strengths(mirrored=False),
    }


def load_extruded_smoothing(tab, config) -> None:
    keys = ("extruded_spectrum_visual_smoothing_enabled", "extruded_spectrum_visual_smoothing",
            "extruded_spectrum_solid_bar_hysteresis_enabled")
    enabled, strength, stabilization = [getattr(tab, key) for key in keys]
    blockers = [QSignalBlocker(control) for control in (enabled, strength, stabilization)]
    for key, control in zip(keys, (enabled, strength, stabilization)):
        value = config.get(key, tab._widget_default("spotify_visualizer", key))
        if control is strength:
            control.setValue(round(float(value) * 100.0))
            getattr(tab, f"{key}_label").setText(f"{control.value()}%")
        else:
            control.setChecked(bool(value))
    strength.parentWidget().setVisible(enabled.isChecked())
    del blockers


def collect_extruded_smoothing(tab) -> dict:
    return {
        "extruded_spectrum_visual_smoothing_enabled": tab.extruded_spectrum_visual_smoothing_enabled.isChecked(),
        "extruded_spectrum_visual_smoothing": tab.extruded_spectrum_visual_smoothing.value() / 100.0,
        "extruded_spectrum_solid_bar_hysteresis_enabled": tab.extruded_spectrum_solid_bar_hysteresis_enabled.isChecked(),
    }
