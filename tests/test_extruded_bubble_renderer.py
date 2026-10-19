"""Extruded Bubble's scene mapping (pure) and its renderer's resource contract through the production render host on
an offscreen context (no window). No pixel goldens: looks are judged against the operator's mocks in the lab."""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from rendering.gl_programs import extruded_bubble_scene as scene
from tests._visualizer_frozen_settings import frozen_visualizer_settings

SETTINGS = frozen_visualizer_settings("extruded_bubble")


def _record(x=0.0, y=0.0, z=0.5, radius=0.1, alpha=1.0, ident=1.0, cluster=-1.0):
    return (x, y, z, radius, alpha, 0.0, ident, cluster)


@pytest.mark.parametrize("turn, tilt", [(0.0, 0.0), (0.37, -0.3), (-0.8, 0.45), (1.0, 0.0)])
def test_the_camera_is_a_rotation_pitched_up_and_turned_about_the_vertical(turn, tilt):
    view_to_world, world_to_view, tan, projection = scene.camera(turn, tilt, 16 / 9)
    axes = np.asarray(view_to_world).reshape(3, 3)                    # rows: right, up, back
    assert np.allclose(axes @ axes.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(axes) == pytest.approx(1.0)
    assert np.allclose(np.asarray(world_to_view).reshape(3, 3), axes.T)
    assert axes[0][1] == pytest.approx(0.0)                           # the horizon stays level (no roll)
    pitch = math.degrees(math.asin(-axes[2][1]))                      # looking along -back
    assert pitch == pytest.approx(16.0 + 90.0 * tilt)
    assert tan[0] / tan[1] == pytest.approx(16 / 9)
    assert projection[5] == pytest.approx(1.0 / tan[1])


def test_scene_scale_zooms_without_turning_the_view():
    plain, zoomed = scene.camera(0.2, 0.1, 1.5), scene.camera(0.2, 0.1, 1.5, scale=2.0)
    assert zoomed[0] == plain[0]
    assert zoomed[2][1] == pytest.approx(plain[2][1] / 2.0)


def test_scene_pan_shifts_everything_on_screen_alike_without_turning_the_view():
    """Scene Pan is an off-axis frustum: every point (and the light's screen position) moves by the same screen
    distance, in the card's units (x right, y down), and nothing turns."""
    shift = scene.lens_shift(0.15, 0.1)
    plain, panned = scene.camera(0.2, 0.1, 1.6), scene.camera(0.2, 0.1, 1.6, shift=shift)
    assert panned[0] == plain[0] and panned[2] == plain[2]
    for point in ((0.3, -0.2, -5.0), (-2.0, 1.0, -20.0)):
        clip = [np.asarray(m).reshape(4, 4).T @ np.array((*point, 1.0)) for m in (plain[3], panned[3])]
        moved = clip[1][:2] / clip[1][3] - clip[0][:2] / clip[0][3]
        assert moved == pytest.approx((0.3, -0.2))                   # right and down by the pan (NDC: y up)
    light = (0.2, 0.5, -0.8)
    before = scene.light_on_screen(light, plain[1], plain[3], (1000, 600))
    after = scene.light_on_screen(light, panned[1], panned[3], (1000, 600))
    assert (after[0] - before[0], after[1] - before[1]) == pytest.approx((150.0, -60.0))

def test_a_bubble_keeps_its_share_of_the_view_at_any_depth_and_fades_by_shrinking():
    _v, _w, tan, _p = scene.camera(0.3, 0.2, 1.6)
    rows = scene.bubble_instances(_record(z=0.0) + _record(z=1.0, ident=2.0) + _record(alpha=0.25, ident=3.0),
                                  tan, (0.3, 0.2))
    assert len(rows) == 3
    for row, z, alpha in zip(rows, (0.0, 1.0, 0.5), (1.0, 1.0, 0.25)):
        depth = scene.DEPTH_NEAR + scene.DEPTH_SPAN * z
        assert np.linalg.norm(row[:3]) >= depth * (1 - 1e-6)          # at least its depth from the eye
        assert row[3] / (tan[1] * depth) == pytest.approx(0.1 * math.sqrt(alpha), rel=1e-5)
        assert row[5] == 0.0


def test_fused_members_and_faded_bubbles_are_not_shells_and_clusters_carry_their_members():
    _v, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    records = _record(x=-0.1, cluster=0.0) + _record(x=0.1, ident=2.0, cluster=0.0) + _record(alpha=0.0, ident=3.0)
    assert len(scene.bubble_instances(records, tan)) == 0
    clusters = scene.cluster_instances(records, (2.0, 0.0, 1.0, -1.0), tan)
    assert clusters.shape == (1, scene.CLUSTER_FLOATS)
    assert clusters[0, 12] == 2.0 and clusters[0, 8:12].tolist() == [0.0] * 4    # two members, third unused


def test_ordinary_shells_are_world_fixed_and_no_synthetic_near_population_is_generated():
    _v, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    record = _record(x=0.17, y=-0.31, z=0.0, radius=0.15, alpha=0.8)
    now = scene.bubble_instances(record, tan, (0.0, 0.0))
    turned = scene.bubble_instances(record, tan, (0.03, 0.0))
    assert now.shape == (1, scene.SHELL_FLOATS) and now[0, 5] == 0.0
    assert np.allclose(now[:, :4], turned[:, :4], atol=1e-4)
    x0, _y0 = _on_screen(now, (0.0, 0.0), 1.6)
    x1, _y1 = _on_screen(turned, (0.03, 0.0), 1.6)
    assert abs(x0[0] - x1[0]) > 0.02
    assert scene.bubble_instances((), tan).shape == (0, scene.SHELL_FLOATS)


def test_only_authentic_foreground_bubbles_are_eligible_for_depth_based_shared_defocus():
    _v, view, tan, _p = scene.camera(0.0, 0.0, 16 / 9)
    near = scene.bubble_instances(_record(z=0.05, radius=0.17), tan)
    far = scene.bubble_instances(_record(z=0.5, radius=0.17, ident=2.0), tan)
    to_view = np.asarray(view).reshape(3, 3)
    def front_depth(shell):
        return -(shell[:3] @ to_view)[2] - shell[3]
    def circle(shell, focus):
        return 22.0 * max(focus - front_depth(shell), 0.0) / max(focus - 2.5, 0.1)
    assert near.shape == (1, scene.SHELL_FLOATS) and near[0, 5] == 0.0
    assert scene.DEPTH_NEAR < 6.0                     # physically extends the ordinary population toward the lens
    assert scene.DEPTH_NEAR + scene.DEPTH_SPAN == pytest.approx(32.0)  # far plane/scene retained
    assert circle(near[0], 4.0) > 1.5                # normal camera focus can defocus an authentic close bubble
    assert circle(near[0], 5.5) > circle(near[0], 4.0)
    assert circle(far[0], 5.5) == 0.0               # distant bubbles do not enter the near layer


def test_glint_proxies_follow_bubbles_toward_the_light():
    view_to_world, _w, tan, _p = scene.camera(0.0, 0.0, 1.6)
    shells = scene.bubble_instances(_record(), tan)
    proxies = scene.glint_proxies(shells, (0.0, 1.0, 0.0), 3.0)
    assert len(proxies) == 1                                          # no invented foreground cohort
    assert proxies[0, 1] > shells[0, 1] and proxies[0, 4] == 3.0


def _on_screen(world, pose, aspect):
    _v, world_to_view, _t, projection = scene.camera(*pose, aspect)
    view = np.asarray(world)[:, :3] @ np.asarray(world_to_view).reshape(3, 3)
    front = view[:, 2] < 0.0
    return (np.where(front, projection[0] * view[:, 0] / -view[:, 2], 9.0),
            np.where(front, projection[5] * view[:, 1] / -view[:, 2], 9.0))


def test_bubbles_stay_fixed_in_the_world_as_the_camera_turns():
    _v, _w, tan, _p = scene.camera(0.0, 0.1, 16 / 9)
    record = _record(x=0.3, y=0.1)
    start = scene.bubble_instances(record, tan, (0.0, 0.1))[0, :3]
    for turn in (0.02, -0.05, 0.08):                                 # small turns: no wrap yet
        assert np.allclose(scene.bubble_instances(record, tan, (turn, 0.1))[0, :3], start, atol=1e-4)
    x0, _y0 = _on_screen(scene.bubble_instances(record, tan, (0.0, 0.1)), (0.0, 0.1), 16 / 9)
    x1, _y1 = _on_screen(scene.bubble_instances(record, tan, (0.05, 0.1)), (0.05, 0.1), 16 / 9)
    assert x1[0] != pytest.approx(x0[0], abs=0.02)                   # and so it moves across the view


@pytest.mark.parametrize("aspect, tilt", [(16 / 9, 0.0), (16 / 9, 0.45), (1.0, -0.4), (3.0, 0.3)])
def test_turning_a_full_circle_never_wraps_a_bubble_on_screen(aspect, tilt):
    """An endless field: each bubble returns on the far side where no one sees it, also near the top of a pitched
    view (the view spans more azimuth there)."""
    _v, _w, tan, _p = scene.camera(0.0, tilt, aspect)
    xs, ys, zs = np.meshgrid(np.linspace(-1.25, 1.25, 9), np.linspace(-1.3, 1.3, 9), (0.0, 1.0))
    n = xs.size
    records = np.column_stack([xs.ravel(), ys.ravel(), zs.ravel(), np.full(n, 0.1), np.ones(n), np.zeros(n),
                               np.arange(n), np.full(n, -1.0)]).ravel()
    previous = None
    for turn in np.linspace(0.0, 2.0, 721):
        here = _on_screen(scene.bubble_instances(records, tan, (turn, tilt)), (turn, tilt), aspect)
        if previous is not None:
            seen = ((np.abs(previous[0]) < 1.15) & (np.abs(previous[1]) < 1.15)) | (
                (np.abs(here[0]) < 1.15) & (np.abs(here[1]) < 1.15))
            assert np.hypot(here[0] - previous[0], here[1] - previous[1])[seen].max(initial=0.0) < 0.06
        previous = here


@pytest.mark.parametrize("light_type", ["Sunlit Surface", "Deep Light"])
def test_every_light_type_gives_the_knobs_the_renderer_reads(light_type):
    knobs = scene.scene_knobs({**SETTINGS, "extruded_bubble_light_type": light_type})
    for key in ("sun", "sun_below", "spec_dir", "light", "water", "deep", "sky", "shaft", "absorb", "exposure",
                "surface", "shaft_y", "focus", "aperture"):
        assert key in knobs, key
    for key in ("sun", "sun_below", "spec_dir"):
        assert np.linalg.norm(knobs[key]) == pytest.approx(1.0)
    assert knobs["sun_below"][1] > 0.0                                 # the light comes from above


def test_particles_read_their_range_at_the_emission_follower_growing_density_and_brightness_together():
    low, high = 0.2, 0.8                                           # TEST INPUT: a Particles range
    settings = {**SETTINGS, "extruded_bubble_particles": [low, high]}
    # Caller already resolved the operator's low/high Range into state.emission. Renderer must not
    # perform an additional interpolation (the old test encoded that exact double-range bug).
    quiet, loud = scene.speck_amount(settings, low), scene.speck_amount(settings, high)
    assert quiet[0] < loud[0] and quiet[1] < loud[1]
    assert loud[0] / quiet[0] == pytest.approx((high / low) ** 2)  # density shaping preserved
    assert scene.speck_amount({**settings, "extruded_bubble_particles": [1.0, 1.0]}, 0.5) == pytest.approx((0.25, 1.2))
    assert scene.speck_amount({**settings, "extruded_bubble_particles": [0.0, 0.0]}, 1.0) == pytest.approx((1.0, 2.4))

def test_ray_strength_reads_its_range_at_the_ray_driver_and_is_off_when_disabled():
    low, high = SETTINGS["extruded_bubble_rays"]
    on = {**SETTINGS, "extruded_bubble_rays_enabled": True}
    assert scene.ray_strength(on, 0.0) == pytest.approx(low)
    assert scene.ray_strength(on, 1.0) == pytest.approx(high)
    assert scene.ray_strength(on, 2.0) == pytest.approx(high)
    assert scene.ray_strength({**SETTINGS, "extruded_bubble_rays_enabled": False}, 0.7) == 0.0


def test_ray_flicker_deepens_as_the_rays_rise_and_a_held_passage_reaches_further():
    on = {**SETTINGS, "extruded_bubble_rays_enabled": True, "extruded_bubble_ray_flicker": 0.5}
    quiet, loud = scene.ray_motion(on, 0.0, 0.0), scene.ray_motion(on, 1.0, 1.0)
    assert 0.0 < quiet[0] < loud[0] <= 0.5
    assert quiet[1] < loud[1]
    assert scene.ray_motion({**on, "extruded_bubble_ray_flicker": 0.0}, 1.0, 1.0)[0] == 0.0
    assert scene.ray_motion({**on, "extruded_bubble_rays_enabled": False}, 1.0, 1.0) == (0.0, 1.0)


def test_procedural_counts_read_the_bead_range_at_the_emission_follower_and_the_tier():
    from rendering.quick.visualizer.implementations.extruded_bubble import (
        _BEADS_PER_CHAIN, _procedural_counts,
    )

    low, high = 2, 7                                               # TEST INPUT: a Bead Chains range
    settings = {**SETTINGS, "extruded_bubble_bead_chains": [low, high], "scene3d_detail": "High"}
    quiet, _snow = _procedural_counts(settings, 0.0)
    loud, snow = _procedural_counts(settings, 1.0)
    assert quiet % _BEADS_PER_CHAIN == 0 and quiet < loud
    assert loud / quiet == pytest.approx(high / low)
    assert _procedural_counts({**settings, "extruded_bubble_bead_chains": [0, 0]}, 1.0)[0] == 0
    cheaper = _procedural_counts({**settings, "scene3d_detail": "KAK"}, 1.0)
    assert cheaper[0] < loud and cheaper[1] < snow

# --- the renderer through the production host -------------------------------------------------------------------


def _snapshot(fade=1.0, **parameters):
    from tests.test_qtquick_extruded_spectrum import H, W
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    snapshot = _build_spectrum_preview_snapshot(width=W, height=H, mode="extruded_bubble", settings=SETTINGS)
    state = snapshot.logical.mode_state
    state = dataclasses.replace(state, parameters={**dict(state.parameters), **parameters})
    logical = dataclasses.replace(snapshot.logical, mode_state=state)
    presentation = dataclasses.replace(snapshot.presentation, content_fade=fade)
    return dataclasses.replace(snapshot, logical=logical, presentation=presentation)


@pytest.fixture
def target(qt_app):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tests.test_qtquick_extruded_spectrum import _Target

    capture, host = _Target(), QuickVisualizerRenderHost()
    try:
        yield capture, host
    finally:
        assert capture.capture.context.makeCurrent(capture.capture.surface)
        host.release_resources()
        capture.close()


@pytest.mark.qt
def test_a_prepared_renderer_draws_without_compiling_or_allocating_and_releases_everything(target, monkeypatch):
    from OpenGL import GL as gl

    from rendering.quick.render import gl_resources
    from rendering.quick.scene3d import defocus, probe, resources
    from rendering.quick.visualizer.implementations.extruded_bubble import QuickExtrudedBubbleRenderer

    capture, host = target
    snapshot = _snapshot()
    renderer = QuickExtrudedBubbleRenderer()
    host._implementations["extruded_bubble"] = renderer
    capture.render(host, _snapshot(fade=0.0))                          # establishes the frame; draws nothing
    frame = _frame(snapshot, capture.capture.vao)
    for _ in range(80):
        if renderer.prepare_step(frame):
            break
    else:
        pytest.fail("the renderer never finished preparing")
    names, allocation = dict(renderer._target._names), renderer._target.allocation

    def forbidden(*_args, **_kwargs):
        pytest.fail("a prepared frame compiled or allocated")
    for module in (resources, defocus, probe, gl_resources):
        if hasattr(module, "compile_program"):
            monkeypatch.setattr(module, "compile_program", forbidden)
    for name in ("glCreateProgram", "glCreateShader", "glCreateTextures", "glGenTextures", "glCreateBuffers",
                 "glCreateVertexArrays", "glCreateFramebuffers", "glCreateRenderbuffers", "glTextureStorage2D",
                 "glTexStorage2D", "glTextureStorage2DMultisample", "glNamedBufferStorage"):
        monkeypatch.setattr(gl, name, forbidden)
    turned = _snapshot(extruded_bubble_turn=0.4, extruded_bubble_tilt=0.2)
    pictures = [capture.render(host, frame_) for frame_ in (snapshot, turned, snapshot)]
    assert renderer._target._names == names and renderer._target.allocation == allocation
    assert np.abs(pictures[0] - pictures[0][0, 0]).max() > 0           # it draws
    assert np.array_equal(pictures[0], pictures[2])                    # the same frame draws the same picture
    assert np.abs(pictures[1] - pictures[0]).mean() > 1.0              # turning the view changes it
    monkeypatch.undo()
    host.release_resources()
    assert not renderer.has_resources


@pytest.mark.qt
def test_the_rays_follow_the_simulation_driver_never_the_raw_level(target):
    """The passage level holds at 1 through loud music: the picture reads the simulation's ray driver instead."""
    capture, host = target

    def with_state(**fields):
        snapshot = _snapshot(extruded_bubble_rays_enabled=True, extruded_bubble_rays=[0.0, 1.0])
        state = dataclasses.replace(snapshot.logical.mode_state, **fields)
        return dataclasses.replace(snapshot, logical=dataclasses.replace(snapshot.logical, mode_state=state))
    for _ in range(4):                                                  # prepared and warm
        capture.render(host, with_state(level=0.0, rays=0.2))
    base = capture.render(host, with_state(level=0.0, rays=0.2))
    assert np.array_equal(capture.render(host, with_state(level=1.0, rays=0.2)), base)
    assert np.abs(capture.render(host, with_state(level=0.0, rays=0.9)) - base).mean() > 0.5


def _frame(snapshot, quad_vao):
    """The frame the host hands the renderer for the capture's card (as ``_Target.render`` draws it)."""
    from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
    from tests.test_qtquick_extruded_spectrum import H, W

    return QuickVisualizerRenderFrame(snapshot=snapshot, viewport=(0, 0, W, H), logical_size=(float(W), float(H)),
                                      matrix_values=(2 / W, 0, 0, 0, 0, -2 / H, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1),
                                      quad_vao=quad_vao)


@pytest.mark.qt
@pytest.mark.parametrize("stage", ["bubble", "particle"])
def test_an_instance_of_no_size_draws_no_quad(qt_app, stage):
    """Generated instances left out (or faded to nothing) carry radius 0. The vertex stages' size floors (half a pixel
    so specks resolve) once drew each as a shaded dot; with no size there is no quad at all."""
    from OpenGL import GL as gl

    from rendering.gl_programs.extruded_bubble_program import BUBBLE_VERTEX, PARTICLE_VERTEX
    from rendering.quick.render.gl_resources import compile_program
    from tools.transition_contact_sheet import TransitionCapture

    width, height = 96, 64
    capture = TransitionCapture(width, height)
    try:
        assert capture.context.makeCurrent(capture.surface)
        _v, _w, tan, projection = scene.camera(0.0, 0.0, width / height)
        program = compile_program(BUBBLE_VERTEX if stage == "bubble" else PARTICLE_VERTEX,
                                  "#version 460 core\nout vec4 colour;\nvoid main() { colour = vec4(1.0); }\n",
                                  label="no-size test")
        gl.glUseProgram(program)
        for name, value in (("uFocus", 10.0), ("uAperture", 0.0), ("uCrisp", 0.0), ("uNearLayer", 0.0),
                            ("uPixel", 2.0 * tan[1] / height), ("uSpecks", 1.0)):
            location = gl.glGetUniformLocation(program, name)
            if location >= 0:
                gl.glUniform1f(location, value)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program, "uWorldToView"), 1, False,
                              np.eye(3, dtype=np.float32))
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(program, "uProjection"), 1, False,
                              np.asarray(projection, dtype=np.float32))
        vao = int(np.asarray(gl.glGenVertexArrays(1)).ravel()[0])
        gl.glBindVertexArray(vao)

        def lit(radius):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_BLEND)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glVertexAttrib4f(0, 0.0, 0.0, -5.0, radius)      # straight ahead
            gl.glVertexAttrib4f(1, 1.0, 0.0, 0.5, 0.0)
            gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, 1)
            gl.glFinish()
            pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
            return int(np.count_nonzero(np.frombuffer(bytes(pixels), dtype=np.uint8)))

        assert lit(1e-6) > 0                                    # the smallest size still resolves (the floor)
        assert lit(0.0) == 0
        gl.glBindVertexArray(0)
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
    finally:
        capture.close()


def test_a_deep_light_tints_the_water_it_lights_more_than_a_sunlit_surface_does():
    """Inside the water the light's own colour carries its glow, beams and veils; under a surface the sky's light is
    mostly the water's."""
    orange = {**SETTINGS, "extruded_bubble_light_colour": [255, 130, 50, 255],
              "extruded_bubble_water_colour": [8, 30, 40, 255]}
    light = np.asarray(scene._rgb(orange["extruded_bubble_light_colour"]))

    def distance(light_type, key):
        knobs = scene.scene_knobs({**orange, "extruded_bubble_light_type": light_type})
        tint = np.asarray(knobs[key]) / max(knobs[key])
        return float(np.abs(tint - light / light.max()).sum())
    for key in ("sky", "shaft"):
        assert distance("Deep Light", key) < 0.5 * distance("Sunlit Surface", key)
