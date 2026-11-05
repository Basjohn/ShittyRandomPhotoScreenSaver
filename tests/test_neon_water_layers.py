"""Neon Lake's layered water through the production renderer: Water Shine is the water's own surface (land is
untouched); the rejected Splashes stay retired."""
from dataclasses import replace

import numpy as np
import pytest

from rendering.gl_programs.heightfield import heightfield_surface_bytes
from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)

def _scene(height, events=(), **parameters):
    """A flat basin that is all water (height 0) or all land, seen from above; no reflections or idle swell."""
    snapshot = _snapshot(**{**dict(
        scene3d_detail="High", shockwave_grid_wire_display="Vertices", shockwave_grid_water_reflection=0.0,
        shockwave_grid_idle=0.0, shockwave_grid_scroll=0.0, shockwave_grid_terrain_reaction_enabled=False,
        shockwave_grid_tilt=0.35, shockwave_grid_turn=0.0, shockwave_grid_scene_pan_x=0.0,
        shockwave_grid_scene_pan_y=0.0), **parameters})
    state = snapshot.logical.mode_state
    terrain = dict(state.parameters["shockwave_grid_terrain"])
    size = terrain["size"]
    terrain.update(data=heightfield_surface_bytes({"size": size, "heights": [height] * size ** 2}), maximum=height)
    for key in ("basin", "grid", "extent"):
        terrain.pop(key, None)
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, events=tuple(events), parameters={**dict(state.parameters), "shockwave_grid_terrain": terrain})))


def _difference(capture, host, a, b):
    capture.render(host, a)          # warm: comparisons are between settled frames
    first = capture.render(host, a).astype(int)
    capture.render(host, b)
    return np.abs(first - capture.render(host, b).astype(int)).sum(axis=-1)


def test_water_shine_changes_the_water_and_never_the_land(target):
    capture, host = target
    water = _difference(capture, host, _scene(0.0, shockwave_grid_water_shine=0.0),
                        _scene(0.0, shockwave_grid_water_shine=1.0))
    assert (water > 24).mean() > 0.05, "the water's own surface replaces its dotted lattice"
    land = _difference(capture, host, _scene(0.4, shockwave_grid_water_shine=0.0),
                       _scene(0.4, shockwave_grid_water_shine=1.0))
    assert not (land > 24).any(), "land keeps its own material"


def test_the_mirror_shows_only_land_never_the_waters_own_level(target):
    """Swell troughs lie below the water's rest level; the mirror's land march once counted that level as land, so
    a trough mirrored 'land' all round it (Preset 3's dark blob mid-lake, pass 6). An all-water basin under heavy
    waves has no land to mirror near the camera, so turning Water Reflection on changes almost nothing."""
    capture, host = target
    events = ((0.6, 0.0, -1.2, 1.4), (1.1, -0.3, -0.9, 1.2), (0.3, 0.3, -1.5, 1.2))
    waves = dict(shockwave_grid_water_shine=1.0, shockwave_grid_wave_height=0.2, shockwave_grid_idle=1.0,
                 shockwave_grid_tilt=0.05)   # a low view, where mirror rays graze the water as in Preset 3
    mirrored = _difference(capture, host, _scene(0.0, events, shockwave_grid_water_reflection=0.0, **waves),
                           _scene(0.0, events, shockwave_grid_water_reflection=1.0, **waves))
    assert (mirrored > 24).mean() < 0.01


def test_splashes_are_retired():
    """Droplets on heavy hits were rejected (2026-11-05): no control, default, preset key or program remains."""
    from core.settings.default_settings import DEFAULT_SETTINGS
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings
    import rendering.gl_programs.neon_lake_basin_program as program

    assert "shockwave_grid_splashes" not in require_mode_settings("shockwave_grid").keys()
    assert "shockwave_grid_splashes" not in str(DEFAULT_SETTINGS)
    assert not any("SPLASH" in name for name in dir(program))
    assert "shockwave_grid_splashes" not in strip_retired_visualizer_settings({"shockwave_grid_splashes": 0.6})
