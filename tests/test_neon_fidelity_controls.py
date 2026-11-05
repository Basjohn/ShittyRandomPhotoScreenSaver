"""Neon Lake's Depth Scale, Shore Glow and Sun / Moon Path through the production renderer.

Each is off at 0 (the earlier picture), and each touches only what it names: marks and ridge lines grow toward
the camera, the edge glow stays along the visible shoreline, and the glitter path lies on water only.
"""
from dataclasses import replace

import numpy as np

from rendering.gl_programs.heightfield import heightfield_surface_bytes
from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)
from tests.test_neon_water_layers import _difference, _scene


def _lake_scene(**parameters):
    """Water on the left half of the basin, flat land at 0.4 on the right; no events, seen from above."""
    snapshot = _scene(0.0, **parameters)
    state = snapshot.logical.mode_state
    terrain = dict(state.parameters["shockwave_grid_terrain"])
    size = terrain["size"]
    heights = [0.0 if col < size // 2 else 0.4 for _row in range(size) for col in range(size)]
    terrain.update(data=heightfield_surface_bytes({"size": size, "heights": heights}), maximum=0.4)
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(
        state, parameters={**dict(state.parameters), "shockwave_grid_terrain": terrain})))


def test_depth_scale_grows_near_marks_more_than_far_ones(target):
    capture, host = target
    base = dict(shockwave_grid_vertex_color=[255, 255, 255, 255], shockwave_grid_vertex_accent_color=[255, 255, 255, 255],
                shockwave_grid_sky_enabled=False, shockwave_grid_sun_enabled=False, shockwave_grid_floor=0.0,
                shockwave_grid_tilt=0.12, shockwave_grid_scene_scale=1.6)
    flat = _difference(capture, host, _scene(0.4, **base, shockwave_grid_depth_scale=0.0),
                       _scene(0.4, **base, shockwave_grid_depth_scale=0.0))
    assert not (flat > 24).any(), "the same settings draw the same picture"
    grown = _difference(capture, host, _scene(0.4, **base, shockwave_grid_depth_scale=0.0),
                        _scene(0.4, **base, shockwave_grid_depth_scale=1.0))
    rows = grown.shape[0]
    near, far = (grown[2 * rows // 3:] > 24).mean(), (grown[: rows // 3] > 24).mean()
    assert near > 0.02, "marks near the camera grow"
    assert near > 2.0 * far, "far marks keep (nearly) their on-screen size"


def test_shore_glow_lights_the_shoreline_and_never_open_land(target):
    capture, host = target
    off = _lake_scene(shockwave_grid_shore_glow=0.0, shockwave_grid_glow=0.8)
    on = _lake_scene(shockwave_grid_shore_glow=2.0, shockwave_grid_shore_glow_color=[0, 255, 0, 255],
                     shockwave_grid_glow=0.8)
    glow = _difference(capture, host, off, on)
    assert (glow > 24).sum() > 200, "the water's edge glows"
    columns = np.nonzero((glow > 24).any(axis=0))[0]
    width = glow.shape[1]
    # Bloom aside, the glow hugs one shoreline (the basin's middle), never the far land or open water edges.
    assert columns.max() - columns.min() < 0.6 * width
    assert not (glow[:, -width // 8:] > 24).any(), "dry land far from the water is untouched"


def test_shore_glow_takes_its_colour_by_alpha(target):
    capture, host = target
    plain = capture.render(host, _lake_scene(shockwave_grid_shore_glow=1.5,
                                             shockwave_grid_shore_glow_color=[0, 255, 0, 0])).astype(int)
    capture.render(host, _lake_scene(shockwave_grid_shore_glow=1.5, shockwave_grid_shore_glow_color=[0, 255, 0, 255]))
    green = capture.render(host, _lake_scene(shockwave_grid_shore_glow=1.5,
                                             shockwave_grid_shore_glow_color=[0, 255, 0, 255])).astype(int)
    changed = np.abs(green - plain).max(axis=-1) > 24
    assert changed.any(), "alpha moves the glow toward its own colour"
    shift = (green[changed][:, :3] - plain[changed][:, :3]).mean(axis=0)
    assert shift[1] > 0 and shift[1] > shift[0] and shift[1] > shift[2], "the glow turns toward green"


def test_sun_moon_path_lies_on_water_only(target):
    capture, host = target
    body = dict(shockwave_grid_sun_enabled=True, shockwave_grid_sun_mode="Moon", shockwave_grid_sun_x=0.0,
                shockwave_grid_sun_y=0.6, shockwave_grid_sun_z=-4.0, shockwave_grid_sun_size=0.3,
                shockwave_grid_tilt=0.05, shockwave_grid_moon_color=[255, 255, 255, 255])
    water = _difference(capture, host, _scene(0.0, **body, shockwave_grid_water_glint=0.0),
                        _scene(0.0, **body, shockwave_grid_water_glint=1.0))
    assert (water > 24).sum() > 100, "the glitter path lies on the water below the body"
    land = _difference(capture, host, _scene(0.4, **body, shockwave_grid_water_glint=0.0),
                       _scene(0.4, **body, shockwave_grid_water_glint=1.0))
    assert not (land > 24).any(), "land never glitters"
    hidden = _difference(capture, host, _scene(0.0, **{**body, "shockwave_grid_sun_enabled": False},
                                               shockwave_grid_water_glint=0.0),
                         _scene(0.0, **{**body, "shockwave_grid_sun_enabled": False}, shockwave_grid_water_glint=1.0))
    assert not (hidden > 24).any(), "no body, no path"
