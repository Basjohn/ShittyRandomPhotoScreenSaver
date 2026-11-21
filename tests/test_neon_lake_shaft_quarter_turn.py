"""Neon Lake's light shafts converge on the drawn Sun at every content quarter turn.

The scene is drawn in the quarter-turn's oriented frame; the shaft light's item point is in that frame's coordinates,
so the shafts pass must map it with the oriented frame, not with the physical output frame the composites use.
"""
from dataclasses import replace

import numpy as np
import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.offscreen_target import OffscreenRenderTarget
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from tests._visualizer_presentation import resolve_presentation
from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

MODE = "shockwave_grid"
CANVAS, ORIGIN, ITEM = 480, 60, 360


def _centroid(mask, xs, ys):
    assert mask.sum() > 20
    return float((xs * mask).sum() / mask.sum()), float((ys * mask).sum() / mask.sum())


@pytest.mark.qt
@pytest.mark.parametrize("quarter", [0, 1, 2, 3])
def test_shafts_converge_on_the_drawn_sun_at_every_quarter(qt_app, quarter):
    from OpenGL import GL as gl

    target = OffscreenRenderTarget(CANVAS, CANVAS)
    host = QuickVisualizerRenderHost()
    base = frozen_visualizer_settings(MODE)
    base.update(shockwave_grid_sun_orbit_enabled=False, shockwave_grid_sun_mode="Sun",
                shockwave_grid_sun_rays_strength=1.0, shockwave_grid_sky_enabled=True,
                shockwave_grid_sun_x=0.6, shockwave_grid_sun_y=0.7, shockwave_grid_sun_z=-3.0,
                shockwave_grid_sun_size=0.5)

    def draw(**over):
        snapshot = _build_spectrum_preview_snapshot(width=ITEM, height=ITEM, mode=MODE, settings={**base, **over})
        presentation = resolve_presentation(policy=get_visualizer_presentation_policy(MODE),
            display_size=(CANVAS, CANVAS), outer_origin=(ORIGIN, ORIGIN), viewport_extent=(ITEM, ITEM),
            content_rotation_quarters=quarter)
        target.bind()
        gl.glDisable(gl.GL_SCISSOR_TEST)
        host.render(snapshot=replace(snapshot, presentation=presentation), viewport=(0, 0, CANVAS, CANVAS),
                    logical_size=(float(ITEM), float(ITEM)),
                    matrix_values=(2 / CANVAS, 0, 0, 0, 0, -2 / CANVAS, 0, 0, 0, 0, 1, 0,
                                   -1 + 2 * ORIGIN / CANVAS, 1 - 2 * ORIGIN / CANVAS, 0, 1))
        return target.read_rgba().astype(np.float32)[..., :3]   # premultiplied over nothing

    try:
        off = draw(shockwave_grid_sun_enabled=False, shockwave_grid_sun_rays_enabled=False)
        sun = draw(shockwave_grid_sun_enabled=True, shockwave_grid_sun_rays_enabled=False)
        rays = draw(shockwave_grid_sun_enabled=True, shockwave_grid_sun_rays_enabled=True)
        ys, xs = np.mgrid[0:CANVAS, 0:CANVAS]
        inside = (xs >= ORIGIN) & (xs < ORIGIN + ITEM) & (ys >= ORIGIN) & (ys < ORIGIN + ITEM)
        disc = (np.abs(sun - off).max(axis=2) > 40) & inside
        added = np.maximum((rays - sun) @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32), 0) * inside
        assert added.max() > 20, "the rays drew nothing"
        sun_at = _centroid(disc, xs, ys)
        rays_at = _centroid(added >= 0.85 * added.max(), xs, ys)
        distance = float(np.hypot(sun_at[0] - rays_at[0], sun_at[1] - rays_at[1]))
        assert distance < 0.04 * ITEM, (quarter, sun_at, rays_at, distance)
    finally:
        target.make_current()
        host.release_resources()
        target.close()
