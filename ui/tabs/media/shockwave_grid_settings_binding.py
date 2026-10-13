"""Custom terrain and audio-profile persistence for Neon Lake Basin Settings."""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker

from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_shockwave_grid_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "shockwave_grid", config)


def collect_shockwave_grid_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "shockwave_grid")


def load_terrain_section(tab, config) -> None:
    key = "shockwave_grid_terrain"
    tab.shockwave_grid_terrain_editor.set_heightfield(config.get(key, tab._widget_default("spotify_visualizer", key)))


def collect_terrain_section(tab) -> dict:
    return {"shockwave_grid_terrain": tab.shockwave_grid_terrain_editor.get_heightfield()}


def load_response_section(tab, config) -> None:
    def value(suffix):
        key = f"shockwave_grid_{suffix}"
        return config.get(key, tab._widget_default("spotify_visualizer", key))

    editor = tab.shockwave_grid_shape_editor
    blockers = [QSignalBlocker(editor), QSignalBlocker(tab.shockwave_grid_mirrored)]
    mirrored = bool(value("mirrored"))
    tab.shockwave_grid_mirrored.setChecked(mirrored)
    editor.set_mirrored(mirrored)
    editor.set_nodes(value("shape_nodes"))
    for mirror, suffix in ((True, "mirrored"), (False, "linear")):
        editor.set_notch_positions(value(f"notch_positions_{suffix}"), mirrored=mirror)
        editor.set_lane_strengths(value(f"lane_strengths_{suffix}"), mirrored=mirror)
    del blockers


def collect_response_section(tab) -> dict:
    editor = tab.shockwave_grid_shape_editor
    return {
        "shockwave_grid_mirrored": tab.shockwave_grid_mirrored.isChecked(),
        "shockwave_grid_shape_nodes": editor.get_nodes(),
        "shockwave_grid_notch_positions_mirrored": list(editor._notches_mirrored),
        "shockwave_grid_notch_positions_linear": list(editor._notches_linear),
        "shockwave_grid_lane_strengths_mirrored": editor.get_lane_strengths(mirrored=True),
        "shockwave_grid_lane_strengths_linear": editor.get_lane_strengths(mirrored=False),
    }


def load_smoothing_section(tab, config) -> None:
    keys = ("shockwave_grid_visual_smoothing_enabled", "shockwave_grid_visual_smoothing",
            "shockwave_grid_solid_bar_hysteresis_enabled")
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


def collect_smoothing_section(tab) -> dict:
    return {
        "shockwave_grid_visual_smoothing_enabled": tab.shockwave_grid_visual_smoothing_enabled.isChecked(),
        "shockwave_grid_visual_smoothing": tab.shockwave_grid_visual_smoothing.value() / 100.0,
        "shockwave_grid_solid_bar_hysteresis_enabled": tab.shockwave_grid_solid_bar_hysteresis_enabled.isChecked(),
    }
