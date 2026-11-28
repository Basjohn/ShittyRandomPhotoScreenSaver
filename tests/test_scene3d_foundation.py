"""The shared 3D scene foundation: pure math mirrors, 3D Detail tiers, the
multisampled scene target and its per-run lifetime (park after every run).

GL cases render through the production transition host into an offscreen
framebuffer; no window is shown.
"""
from __future__ import annotations

import random

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.scene3d import (
    SCENE3D_DETAIL_NAMES,
    SCENE3D_DETAIL_TIERS,
    SCENE3D_KEY_LIGHT,
    scene3d_cast_on_plane,
    scene3d_departure_travel,
    scene3d_detail,
    scene3d_impulse,
    scene3d_screen_uv,
)
from tools.labs.render_target import OffscreenRenderTarget


def _inside(point, half_box) -> bool:
    return abs(point[0]) < half_box[0] and abs(point[1]) < half_box[1]


def test_departure_travel_clears_the_box_for_good():
    rng = random.Random(5)
    half_box = (0.95, 0.55)
    for _ in range(2000):
        start = (rng.uniform(-2.0, 2.0), rng.uniform(-1.5, 1.5))
        angle = rng.uniform(0.0, 6.283185307)
        heading = (np.cos(angle), np.sin(angle))
        travel = scene3d_departure_travel(start, heading, half_box)
        assert travel >= 0.0
        for extra in (0.0, 0.01, 0.3, 2.0):
            s = travel + extra + 1e-6
            assert not _inside((start[0] + heading[0] * s, start[1] + heading[1] * s), half_box)
        if _inside(start, half_box):
            assert travel > 0.0
    # Parallel to an axis and already outside it: nothing to clear.
    assert scene3d_departure_travel((2.0, 0.0), (0.0, 1.0), half_box) == 0.0


def test_impulse_is_zero_at_rest_and_front_loaded():
    assert scene3d_impulse(0.0, 20.0, 0.15) == 0.0
    early = scene3d_impulse(0.02, 20.0, 0.15) / 0.02
    late = (scene3d_impulse(0.9, 20.0, 0.15) - scene3d_impulse(0.5, 20.0, 0.15)) / 0.4
    assert early > 3.0 * late > 0.0


def test_projection_and_shadows_follow_the_camera_and_key_light():
    assert scene3d_screen_uv((0.0, 0.0, 0.0), 16 / 9) == (0.5, 0.5)
    # On the photograph plane a point lands exactly on its own pixel.
    assert scene3d_screen_uv((-8 / 9, 0.5, 0.0), 16 / 9) == pytest.approx((0.0, 0.0))
    # Nearer the camera, the same offset spreads further from the centre.
    near = scene3d_screen_uv((0.4, 0.0, 1.0), 16 / 9)
    assert near[0] > scene3d_screen_uv((0.4, 0.0, 0.0), 16 / 9)[0]
    assert scene3d_cast_on_plane((0.1, 0.2, 0.0), 0.0) == pytest.approx((0.1, 0.2))
    cast = scene3d_cast_on_plane((0.0, 0.0, 0.5), 0.0)
    # The shadow falls away from the light.
    assert cast[0] * SCENE3D_KEY_LIGHT[0] < 0 and cast[1] * SCENE3D_KEY_LIGHT[1] < 0


def test_detail_tiers_trade_cost_monotonically():
    tiers = [SCENE3D_DETAIL_TIERS[name] for name in SCENE3D_DETAIL_NAMES]
    assert [tier.name for tier in tiers] == list(SCENE3D_DETAIL_NAMES)
    assert tiers[0].samples > 1 and tiers[0].shadows
    assert tiers[-1].samples == 0 and not tiers[-1].shadows
    # Every cost lever only falls from tier to tier: post effects (Bloom, Motion Blur, a
    # Visualizer's glow), particles, grid density, overlay multisampling; the best tier has
    # them all and the cheapest none of the optional ones.
    post = [tier.post_effects for tier in tiers]
    assert post == sorted(post, reverse=True) and post[0] and not post[-1]
    for lever in ("particles", "grid_cells", "overlay_samples"):
        values = [getattr(tier, lever) for tier in tiers]
        assert values == sorted(values, reverse=True), lever
    assert tiers[-1].particles > 0.0 and tiers[-1].grid_cells >= 2
    assert tiers[0].overlay_samples > 1 and tiers[-1].overlay_samples == 0
    # Reflections (Mirror Faces) on every tier but the cheapest.
    assert all(tier.reflections for tier in tiers[:-1]) and not tiers[-1].reflections
    with pytest.raises(ValueError):
        scene3d_detail("Ultra")


_MIGRATED = (("glass_shatter", "center_out"), ("crumble", None), ("pixel_accretion", "left"), ("block_spins", "left"))


@pytest.mark.qt
def test_the_bloom_pass_takes_only_the_alpha_marked_light(qt_app):
    """A white field marked non-emissive stays put; a small emissive spot spreads a glow."""
    from types import SimpleNamespace

    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget

    capture = OffscreenRenderTarget(256, 144)
    resources, target = MeshResources("bloom test"), SceneTarget("bloom test")
    texture = int(gl.glGenTextures(1))
    try:
        image = np.zeros((144, 256, 4), dtype=np.uint8)
        image[..., :3] = 40
        image[:, :96, :3] = 255                       # a white field, alpha 0: not emitted
        image[60:84, 180:204] = (255, 140, 40, 255)    # an orange spot, alpha 1: emitted
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, 256, 144, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, image)
        frame = SimpleNamespace(viewport=(0, 0, 256, 144), logical_size=(256.0, 144.0),
                                matrix_values=(2 / 256, 0, 0, 0, 0, -2 / 144, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                quad_vao=capture.vao)

        def draw(bloom):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, 256, 144)
            with target.scope(frame, 1, resources, bloom=bloom):
                resources.draw_image(frame, texture)
            pixels = gl.glReadPixels(0, 0, 256, 144, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return np.flipud(np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(144, 256, 4)).astype(np.int16)

        plain, glowing = draw(0.0), draw(1.0)
        added = (glowing - plain)[..., :3].max(axis=2)
        assert added[72, 170] > 10          # beside the emissive spot: glow
        assert added[72, 110] <= 1          # beside the white field: nothing
        assert (glowing[..., 3] == 255).all()   # Quick always gets opaque pixels
    finally:
        gl.glDeleteTextures([texture])
        target.release()
        resources.release_resources()
        capture.close()


def test_the_shared_orbit_reproduces_each_3d_visualizers_former_projection():
    """``scene3d_orbit_project`` (H6) is the one orbit/perspective helper; each former inline
    projection, kept here as the reference, must come out unchanged. (Neon Lake moved to the shared
    framed physical camera in 2026-10; its former pivoted form still checks the helper's pivot.)"""
    import math
    import random

    from rendering.gl_programs.extruded_spectrum_program import EXTRUDED_CAMERA, EXTRUDED_PIVOT, extruded_project
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DEPTH
    from rendering.gl_programs.scene3d import scene3d_orbit_project

    def former_extruded(point, tilt, turn):
        x, y, z = point
        ct, st = math.cos(turn), math.sin(turn)
        x, z = x * ct + z * st, -x * st + z * ct
        c, s = math.cos(tilt), math.sin(tilt)
        y -= EXTRUDED_PIVOT
        raised, toward = y * c - z * s + EXTRUDED_PIVOT, y * s + z * c
        scale = EXTRUDED_CAMERA / (EXTRUDED_CAMERA - toward)
        return x * scale, raised * scale, toward

    def former_shockwave(point, tilt, turn, camera):
        x, y, z = point[0], point[1], point[2] + 0.5 * SHOCKWAVE_DEPTH
        ct, st = math.cos(turn), math.sin(turn)
        x, z = x * ct + z * st, -x * st + z * ct
        c, s = math.cos(tilt), math.sin(tilt)
        raised, toward = y * c - z * s, y * s + z * c
        scale = camera / (camera - toward)
        return x * scale, raised * scale, toward

    rng = random.Random(6)
    for _ in range(500):
        point = (rng.uniform(-3, 3), rng.uniform(-1, 1), rng.uniform(-2.4, 0))
        tilt, turn, camera = rng.uniform(0, math.pi / 2), rng.uniform(-math.pi, math.pi), rng.uniform(2.6, 6)
        assert extruded_project(point, tilt, turn) == pytest.approx(former_extruded(point, tilt, turn), abs=1e-12)
        assert scene3d_orbit_project(point, tilt, turn, camera=camera, pivot=(0.0, 0.0, -0.5 * SHOCKWAVE_DEPTH))             == pytest.approx(former_shockwave(point, tilt, turn, camera), abs=1e-12)
