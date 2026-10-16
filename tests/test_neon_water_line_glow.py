"""Neon Lake's water lines glow in their own colour and strength, through the production renderer."""
from dataclasses import replace

import numpy as np
import pytest

from tests.test_neon_lake_renderer import _snapshot, target  # noqa: F401  (pytest fixture)


def _scene(**parameters):
    # Lines and their glow only: no land art, vertices, sky, body, shore light or reflections.
    snapshot = _snapshot(**{**dict(
        scene3d_detail="High", shockwave_grid_glow=0.8, shockwave_grid_wire_display="Vertices",
        shockwave_grid_vertex_color=[0, 0, 0, 0], shockwave_grid_vertex_accent_color=[0, 0, 0, 0],
        shockwave_grid_vertex_outline_color=[0, 0, 0, 0], shockwave_grid_sky_enabled=False,
        shockwave_grid_sun_enabled=False, shockwave_grid_floor=0.0, shockwave_grid_water_reflection=0.0,
        shockwave_grid_horizon_thickness=0.0, shockwave_grid_horizon=0.0, shockwave_grid_terrain_reactivity=0.0,
        shockwave_grid_line_color=[120, 200, 255, 255], shockwave_grid_crest_color=[120, 200, 255, 255],
        shockwave_grid_water_detail=1.0, shockwave_grid_scroll=0.0, shockwave_grid_idle=0.0), **parameters})
    state = snapshot.logical.mode_state
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=replace(state, events=())))


def _light(image):
    return image[..., :3].astype(np.float64)


def test_water_lines_glow_by_their_own_strength_and_colour(target):
    capture, host = target

    def render(strength, colour):
        return _light(capture.render(host, _scene(shockwave_grid_water_line_glow=strength,
                                                  shockwave_grid_water_line_glow_color=colour)))

    plain = [255, 30, 20, 0]
    render(0.0, plain)                  # warm: comparisons are between settled frames
    none, normal, bright = (render(strength, plain) for strength in (0.0, 1.0, 3.0))
    # The strength adds light around the water lines, in proportion.
    assert none.sum() < normal.sum() < bright.sum()
    assert (bright - none).sum() > 2.0 * (normal - none).sum()
    # Alpha 0 keeps the ripple colours; alpha 1 makes the added glow the chosen red.
    red = render(3.0, [255, 30, 20, 255]) - none
    ripple = bright - none
    assert red[..., 0].sum() > red[..., 2].sum()
    assert ripple[..., 2].sum() > ripple[..., 0].sum()


def test_water_line_glow_follows_surface_glow(target):
    capture, host = target
    off = _scene(shockwave_grid_glow=0.0, shockwave_grid_water_line_glow=3.0,
                 shockwave_grid_water_line_glow_color=[255, 30, 20, 255])
    reference = _scene(shockwave_grid_glow=0.0, shockwave_grid_water_line_glow=0.0)
    # The renderer's frames already differ by up to one level on a pixel or two between draws.
    difference = np.abs(capture.render(host, off).astype(int) - capture.render(host, reference).astype(int))
    assert difference.max() <= 1, "with Surface Glow at zero nothing glows"
