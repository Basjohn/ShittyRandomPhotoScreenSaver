"""Neon Lake's layered water through the production renderer: Water Shine is the water's own surface (land is
untouched) and Splashes rise only where heavy onsets land on water."""
from dataclasses import replace

import numpy as np
import pytest

from rendering.gl_programs.heightfield import heightfield_surface_bytes
from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)

_HEAVY = (0.3, 0.0, -1.2, 2.0)   # (age, x share, z, strength): mid-flight, mid-basin, at full strength


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


def test_splashes_rise_only_from_heavy_onsets_on_water(target):
    capture, host = target
    splash = _difference(capture, host, _scene(0.0, (_HEAVY,), shockwave_grid_splashes=0.0),
                         _scene(0.0, (_HEAVY,), shockwave_grid_splashes=1.0))
    assert (splash > 24).sum() > 40, "a heavy hit on water throws droplets"
    light = (_HEAVY[0], _HEAVY[1], _HEAVY[2], 0.8)
    quiet = _difference(capture, host, _scene(0.0, (light,), shockwave_grid_splashes=0.0),
                        _scene(0.0, (light,), shockwave_grid_splashes=1.0))
    assert not (quiet > 24).any(), "ordinary onsets only ripple"
    dry = _difference(capture, host, _scene(0.4, (_HEAVY,), shockwave_grid_splashes=0.0),
                      _scene(0.4, (_HEAVY,), shockwave_grid_splashes=1.0))
    assert not (dry > 24).any(), "land never splashes"


def test_splashes_off_builds_nothing(target):
    capture, host = target
    capture.render(host, _scene(0.0, (_HEAVY,), shockwave_grid_splashes=0.0))
    resources = host._implementations["shockwave_grid"]._resources
    assert not resources.has_program("splash")
    assert not resources.has_mesh("splash slots")
