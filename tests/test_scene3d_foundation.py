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
    # Reflections refresh less often down the tiers and are off at the cheapest.
    refresh = [tier.backdrop_refresh for tier in tiers]
    assert all(value > 0 for value in refresh[:-1]) and refresh[:-1] == sorted(refresh[:-1])
    assert refresh[-1] == 0
    with pytest.raises(ValueError):
        scene3d_detail("Ultra")


@pytest.mark.qt
@pytest.mark.parametrize("detail", SCENE3D_DETAIL_NAMES)
def test_every_tier_keeps_exact_endpoints_and_restores_the_framebuffer(qt_app, detail):
    capture = TransitionCapture(256, 144)
    try:
        run = capture.run("exploding_tiles", direction="center_out", settings={"detail_3d": detail})
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
            # Bloom off: this compares multisampling alone.
            run = capture.run("exploding_tiles", direction="center_out",
                              settings={"detail_3d": detail, "exploding_tiles": {"bloom": "Off"}})
            frames[detail] = np.asarray(capture.render(run, 0.2)[0], dtype=np.int16)
        difference = np.abs(frames["High"] - frames["Balanced"])
        # Same scene, smoother silhouettes: only edge pixels change.
        assert 0.0 < difference.mean() < 3.0
        assert (difference.max(axis=2) > 24).mean() < 0.08

        renderer = capture.host._implementations["exploding_tiles"]
        run = capture.run("exploding_tiles", direction="center_out",
                          settings={"detail_3d": "High", "exploding_tiles": {"bloom": "Off"}})
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
            run = capture.run(effect, direction=direction, settings={"detail_3d": detail}, duration_ms=8000)
            assert np.abs(np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16) - source).mean() < 0.5
            assert np.abs(np.asarray(capture.render(run, 0.9999)[0], dtype=np.int16) - destination).mean() < 0.5
            frames[detail] = np.asarray(capture.render(run, 0.45)[0], dtype=np.int16)
            assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        # High multisamples the same scene: only edge pixels differ from a direct draw.
        difference = np.abs(frames["High"] - frames["Balanced"])
        assert difference.mean() < 3.0
        assert (difference.max(axis=2) > 24).mean() < 0.08
        renderer = capture.host._implementations[effect]
        run = capture.run(effect, direction=direction, settings={"detail_3d": "High"}, duration_ms=8000)
        capture.render(run, 0.45)
        assert renderer._target.has_resources
        capture.host.park()
        assert not renderer._target.has_resources and renderer.has_resources
    finally:
        capture.close()


@pytest.mark.qt
def test_bloom_glows_emitted_light_only_and_follows_the_transition_setting(qt_app):
    capture = TransitionCapture(256, 144)
    try:
        def frame(detail, bloom, progress):
            section = {"bloom": bloom, "bloom_strength": 1.0}
            run = capture.run("exploding_tiles", direction="center_out", duration_ms=8000,
                              settings={"detail_3d": detail, "exploding_tiles": section})
            return np.asarray(capture.render(run, progress)[0], dtype=np.int16)

        # Late in the run nothing emits (no sparks, cracks, embers or flash): the photographs never bloom.
        assert np.abs(frame("High", "On", 0.6) - frame("High", "Off", 0.6)).max() <= 1
        # Around the detonation sparks and glowing cracks do.
        assert np.abs(frame("High", "On", 0.12) - frame("High", "Off", 0.12)).mean() > 0.3
        # Auto: Balanced blooms (through a single-sample target), Performance does not...
        assert np.abs(frame("Balanced", "Auto", 0.12) - frame("Balanced", "Off", 0.12)).mean() > 0.3
        assert np.array_equal(frame("Performance", "Auto", 0.12), frame("Performance", "Off", 0.12))
        # ...unless the transition itself says On: its setting is authoritative.
        assert np.abs(frame("Performance", "On", 0.12) - frame("Performance", "Off", 0.12)).mean() > 0.3
        # Balanced's bloom target is single-sample and draws like a direct draw: once nothing emits the
        # frames match (a 1-sample multisampled renderbuffer rasterised the tiles up to 144 levels apart).
        assert np.abs(frame("Balanced", "Auto", 0.35) - frame("Balanced", "Off", 0.35)).max() <= 1
        assert np.array_equal(frame("Balanced", "Auto", 0.6), frame("Balanced", "Off", 0.6))
    finally:
        capture.close()


@pytest.mark.qt
def test_the_bloom_pass_takes_only_the_alpha_marked_light(qt_app):
    """A white field marked non-emissive stays put; a small emissive spot spreads a glow."""
    from types import SimpleNamespace

    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.target import SceneTarget

    capture = TransitionCapture(256, 144)
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


@pytest.mark.qt
@pytest.mark.parametrize("effect,direction", _MIGRATED)
def test_a_transitions_anti_aliasing_choice_decides_the_scene_target(qt_app, effect, direction):
    capture = TransitionCapture(256, 144)
    try:
        section = "blockspin" if effect == "block_spins" else effect
        renderer = None
        # Anti-aliasing alone decides the target while motion blur is off; motion blur needs one too.
        for tier, choice, motion_blur, expected in (("Performance", "4x", "Off", True), ("High", "Off", "Off", False),
                                                    ("High", "Auto", "Off", True), ("Performance", "Off", "On", True)):
            run = capture.run(effect, direction=direction, duration_ms=8000,
                              settings={"detail_3d": tier, section: {"antialiasing": choice, "motion_blur": motion_blur}})
            capture.render(run, 0.45)
            renderer = capture.host._implementations[effect]
            assert renderer._target.has_resources is expected, (tier, choice, motion_blur)
            capture.host.park()
    finally:
        capture.close()


@pytest.mark.qt
def test_motion_blur_blurs_only_moving_tiles_and_follows_the_transition_setting(qt_app):
    capture = TransitionCapture(256, 144)
    try:
        def frame(detail, motion_blur, progress):
            section = {"motion_blur": motion_blur}
            run = capture.run("exploding_tiles", direction="center_out", duration_ms=3000,
                              settings={"detail_3d": detail, "exploding_tiles": section})
            return np.asarray(capture.render(run, progress)[0], dtype=np.int16)

        # Before anything moves the frame is exact; at the detonation the flying tiles blur.
        assert np.array_equal(frame("High", "On", 0.005), frame("High", "Off", 0.005))
        assert np.abs(frame("High", "On", 0.13) - frame("High", "Off", 0.13)).mean() > 0.5
        # Auto follows the tier's post effects; the transition's own choice wins over it.
        assert np.abs(frame("High", "Auto", 0.13) - frame("High", "Off", 0.13)).mean() > 0.5
        assert np.array_equal(frame("Performance", "Auto", 0.13), frame("Performance", "Off", 0.13))
        assert np.abs(frame("Performance", "On", 0.13) - frame("Performance", "Off", 0.13)).mean() > 0.5
        # Its textures are per run: the host's park drops them with the target.
        renderer = capture.host._implementations["exploding_tiles"]
        assert renderer._target.has_resources
        capture.host.park()
        assert not renderer._target.has_resources
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("effect,direction", _MIGRATED)
def test_every_3d_transition_blurs_its_motion_and_stays_exact_when_nothing_moves(qt_app, effect, direction):
    """Motion blur for Glass Shatter, Crumble, Directional Pixel Accretion and 3D Block Spins."""
    capture = TransitionCapture(256, 144)
    try:
        section = "blockspin" if effect == "block_spins" else effect

        def frame(motion_blur, progress, duration_ms):
            run = capture.run(effect, direction=direction, duration_ms=duration_ms,
                              settings={"detail_3d": "High", section: {"motion_blur": motion_blur}})
            return np.asarray(capture.render(run, progress)[0], dtype=np.int16)

        # When its pieces move fastest, at a short duration, they blur...
        progress = {"glass_shatter": 0.3, "crumble": 0.6}.get(effect, 0.45)
        moving = np.abs(frame("On", progress, 1500) - frame("Off", progress, 1500))
        assert moving.mean() > 0.05 and moving.max() > 16, effect
        # ...and over a very long run a shutter moves nothing by half a pixel: exact.
        assert np.array_equal(frame("On", progress, 600_000), frame("Off", progress, 600_000)), effect
        renderer = capture.host._implementations[effect]
        capture.host.park()
        assert not renderer._target.has_resources
    finally:
        capture.close()


def test_the_shared_orbit_reproduces_each_3d_visualizers_former_projection():
    """``scene3d_orbit_project`` (H6) is the one orbit/perspective both 3D Visualizers use; each
    mode's former inline projection, kept here as the reference, must come out unchanged."""
    import math
    import random

    from rendering.gl_programs.extruded_spectrum_program import EXTRUDED_CAMERA, EXTRUDED_PIVOT, extruded_project
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_DEPTH, shockwave_project

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
        assert shockwave_project(point, tilt, turn, camera) == pytest.approx(
            former_shockwave(point, tilt, turn, camera), abs=1e-12)
