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
from tools.transition_contact_sheet import TransitionCapture


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
    particles = [tier.particles for tier in tiers]
    assert particles == sorted(particles, reverse=True) and particles[-1] > 0.0
    with pytest.raises(ValueError):
        scene3d_detail("Ultra")


@pytest.mark.qt
@pytest.mark.parametrize("detail", SCENE3D_DETAIL_NAMES)
def test_every_tier_keeps_exact_endpoints_and_restores_the_framebuffer(qt_app, detail):
    capture = TransitionCapture(256, 144)
    try:
        run = capture.run("exploding_tiles", direction="center_out", parameters={"detail": detail})
        source, destination = (np.asarray(image, dtype=np.int16) for image in capture.images)
        near_start = np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16)
        middle = np.asarray(capture.render(run, 0.2)[0], dtype=np.int16)
        bound = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
        near_end = np.asarray(capture.render(run, 0.9999)[0], dtype=np.int16)
        assert np.abs(near_start - source).mean() < 0.5
        assert np.abs(near_end - destination).mean() < 0.5
        assert np.abs(middle - source).mean() > 2 and np.abs(middle - destination).mean() > 2
        assert bound == capture.fbo
    finally:
        capture.close()


@pytest.mark.qt
def test_high_multisamples_the_same_scene_and_park_drops_only_the_target(qt_app):
    capture = TransitionCapture(256, 144)
    try:
        frames = {}
        for detail in ("High", "Balanced"):
            run = capture.run("exploding_tiles", direction="center_out", parameters={"detail": detail})
            frames[detail] = np.asarray(capture.render(run, 0.2)[0], dtype=np.int16)
        difference = np.abs(frames["High"] - frames["Balanced"])
        # Same scene, smoother silhouettes: only edge pixels change.
        assert 0.0 < difference.mean() < 3.0
        assert (difference.max(axis=2) > 24).mean() < 0.08

        renderer = capture.host._implementations["exploding_tiles"]
        run = capture.run("exploding_tiles", direction="center_out", parameters={"detail": "High"})
        capture.render(run, 0.2)
        assert renderer._target.has_resources
        capture.host.park()
        assert not renderer._target.has_resources
        assert renderer.has_resources  # programs and the slab mesh stay warm
        # The next run allocates again and still renders the same frame.
        assert np.array_equal(np.asarray(capture.render(run, 0.2)[0], dtype=np.int16), frames["High"])
    finally:
        capture.close()


def test_parking_the_background_node_parks_the_transition_host(qt_app, monkeypatch):
    from rendering.quick.render import background_node
    from rendering.quick.render.telemetry import RenderNodeTelemetry

    node = background_node.BackgroundRenderNode(RenderNodeTelemetry(gui_thread_id=1), screen_index=0)

    class _Host:
        has_resources = True
        parks = 0

        def park(self):
            self.parks += 1

        def release_resources(self):
            self.has_resources = False

    host = _Host()
    node._transition_renderer = host
    monkeypatch.setattr(background_node.QOpenGLContext, "currentContext", staticmethod(lambda: object()))
    node.release_presentation_textures()
    assert host.parks == 1


_MIGRATED = (("glass_shatter", "center_out"), ("crumble", None), ("pixel_accretion", "left"), ("block_spins", "left"))


@pytest.mark.qt
@pytest.mark.parametrize("effect,direction", _MIGRATED)
def test_every_3d_transition_honours_the_tiers_and_parks(qt_app, effect, direction):
    capture = TransitionCapture(256, 144)
    try:
        source, destination = (np.asarray(image, dtype=np.int16) for image in capture.images)
        frames = {}
        for detail in SCENE3D_DETAIL_NAMES:
            run = capture.run(effect, direction=direction, parameters={"detail": detail}, duration_ms=8000)
            assert np.abs(np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16) - source).mean() < 0.5
            assert np.abs(np.asarray(capture.render(run, 0.9999)[0], dtype=np.int16) - destination).mean() < 0.5
            frames[detail] = np.asarray(capture.render(run, 0.45)[0], dtype=np.int16)
            assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        # High multisamples the same scene: only edge pixels differ from a direct draw.
        difference = np.abs(frames["High"] - frames["Balanced"])
        assert difference.mean() < 3.0
        assert (difference.max(axis=2) > 24).mean() < 0.08
        renderer = capture.host._implementations[effect]
        run = capture.run(effect, direction=direction, parameters={"detail": "High"}, duration_ms=8000)
        capture.render(run, 0.45)
        assert renderer._target.has_resources
        capture.host.park()
        assert not renderer._target.has_resources and renderer.has_resources
    finally:
        capture.close()
