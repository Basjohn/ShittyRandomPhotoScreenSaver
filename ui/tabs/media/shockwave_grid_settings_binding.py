"""Persistence of Neon Lake's terrain brush, the one section its Settings body keeps."""
from __future__ import annotations


def load_terrain_section(tab, config) -> None:
    key = "shockwave_grid_terrain"
    tab.shockwave_grid_terrain_editor.set_heightfield(config.get(key, tab._widget_default("spotify_visualizer", key)))
    from ui.tabs.media.shockwave_grid_builder import SCENE_PREVIEW_KEYS
    # The 3/4 view shows the values being loaded (every Studio commit reloads the body, so it follows them).
    from core.settings.visualizer_mode_settings import read_control_value, require_mode_settings
    spec = require_mode_settings("shockwave_grid")
    scene = {}
    for key in SCENE_PREVIEW_KEYS:
        control = spec.control(key)
        default = tab._widget_default("spotify_visualizer", key)
        scene[key] = control.admit(read_control_value(control, config.get, default), default)
    tab.shockwave_grid_terrain_editor.set_scene(scene)


def collect_terrain_section(tab) -> dict:
    return {"shockwave_grid_terrain": tab.shockwave_grid_terrain_editor.get_heightfield()}
