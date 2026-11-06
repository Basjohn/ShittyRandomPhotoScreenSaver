"""Neon Lake's Settings body: the preset row, the Studio launcher and the terrain brush.

Every Neon Lake control except the terrain brush is edited in the Studio (parity+:
``tests/test_visualizer_studio_parity.py``). The Studio carries the authored heightfield (undo, save, Extend Toward
Horizon, Reset Terrain) but has no brush instrument, so the heightfield is painted here (operator decision on the
Neon Lake Studio's acceptance)."""
from __future__ import annotations

from ui.tabs.media.spec_mode_builder import build_studio_owned_mode_ui

INTRO = "Paint the terrain here; the water, sky, light, camera and reactivity are edited live in the Studio."


def build_shockwave_grid_ui(tab, parent_layout) -> None:
    build_studio_owned_mode_ui(tab, parent_layout, "shockwave_grid", INTRO, settings_sections=("terrain",))


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


def place_celestial_body(tab, position: dict) -> None:
    """The Sun / Moon dragged in the terrain editor's 3/4 view: set its Position X / Y / Z like any edit."""
    from core.settings.visualizer_mode_settings import require_mode_settings
    spec = require_mode_settings("shockwave_grid")
    cache = tab._shockwave_grid_lazy_values
    for axis in ("x", "y", "z"):
        key = "shockwave_grid_sun_" + axis
        # One placement is one edit: the three values change, then one Custom + save below.
        cache[key] = spec.control(key).admit(position[axis], cache[key])
    tab._force_visualizer_preset_to_custom("shockwave_grid")
    tab._save_settings()
