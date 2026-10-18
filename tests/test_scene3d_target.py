"""The shared scene target works for any item rect (a full-screen transition or a
Visualizer card): it reproduces a direct draw, reuses its allocation while the
rect fits, and always hands Quick back its framebuffer, viewport and scissor.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.scene3d.frame import item_pixel_rect
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.target import SceneTarget
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

WIDTH, HEIGHT = 256, 144


def _card_frame(capture, left: float, top: float, width: float, height: float):
    """An item placed at (left, top) in the window, as a Visualizer card is."""
    matrix = (2 / WIDTH, 0, 0, 0, 0, -2 / HEIGHT, 0, 0, 0, 0, 1, 0,
              2 * left / WIDTH - 1, 1 - 2 * top / HEIGHT, 0, 1)
    return SimpleNamespace(viewport=(0, 0, WIDTH, HEIGHT), logical_size=(width, height),
                           matrix_values=matrix, quad_vao=capture.vao)


def _read(capture) -> np.ndarray:
    pixels = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(pixels), dtype=np.uint8).reshape(HEIGHT, WIDTH, 4).astype(np.int16)


def _clear(capture) -> None:
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
    gl.glViewport(0, 0, WIDTH, HEIGHT)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(1.0, 0.0, 1.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT)


@pytest.fixture
def capture(qt_app):
    result = TransitionCapture(WIDTH, HEIGHT)
    yield result
    result.close()


def test_item_pixel_rect_follows_the_item_matrix(capture):
    full = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
    assert item_pixel_rect(full) == (0, 0, WIDTH, HEIGHT)
    card = _card_frame(capture, 40, 20, 120, 80)
    # GL rows count up from the bottom: the card spans rows 44..124.
    assert item_pixel_rect(card) == (40, HEIGHT - 20 - 80, 120, 80)
    spill = _card_frame(capture, 200, -10, 120, 80)
    assert item_pixel_rect(spill) == (200, HEIGHT - 70, WIDTH - 200, 70)


@pytest.mark.parametrize("samples", (1, 4))
def test_a_card_drawn_through_the_target_matches_a_direct_draw(capture, samples):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        texture = capture.textures[0]
        _clear(capture)
        resources.draw_image(card, texture)
        direct = _read(capture)

        _clear(capture)
        with target.scope(card, samples, resources):
            resources.draw_image(card, texture)
        through = _read(capture)
        assert np.array_equal(direct, through)
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == (0, 0, WIDTH, HEIGHT)
    finally:
        target.release()
        resources.release_resources()


def test_the_composite_respects_an_inherited_scissor(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        _clear(capture)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(10, 10, 100, 60)
        with target.scope(card, 4, resources):
            resources.draw_image(card, capture.textures[0])
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)) == (10, 10, 100, 60)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        pixels = _read(capture)
        magenta = np.array([255, 0, 255, 255])
        assert (pixels[5, 5] == magenta).all() and (pixels[100, 200] == magenta).all()
        assert not (pixels[40, 50] == magenta).all()
    finally:
        target.release()
        resources.release_resources()


def test_the_allocation_is_reused_while_the_rect_fits(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        _clear(capture)
        with target.scope(_card_frame(capture, 0, 0, 100, 60), 4, resources):
            pass
        first, fbo = target.allocation, target._names["fbo"]
        assert first == (128, 64, 4)
        with target.scope(_card_frame(capture, 0, 0, 120, 64), 4, resources):
            pass
        assert target.allocation == first and target._names["fbo"] == fbo  # a resize drag inside the bucket
        with target.scope(_card_frame(capture, 0, 0, 130, 60), 4, resources):
            pass
        assert target.allocation == (192, 64, 4)
        target.release()
        assert not target.has_resources and target.allocation is None
    finally:
        target.release()
        resources.release_resources()


def test_a_failing_scene_hands_quick_back_its_state(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        _clear(capture)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(0, 0, WIDTH, HEIGHT)
        with pytest.raises(RuntimeError, match="mid-scene"):
            with target.scope(_card_frame(capture, 40, 20, 120, 80), 4, resources):
                assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) != capture.fbo
                raise RuntimeError("mid-scene failure")
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        assert int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING)) == capture.fbo
        assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == (0, 0, WIDTH, HEIGHT)
        assert bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        target.release()
        resources.release_resources()


@pytest.mark.parametrize("samples,bloom", ((1, 0.0), (4, 0.0), (1, 1.0), (4, 1.0)))
def test_the_target_resolves_in_shaders_never_through_a_blit(capture, monkeypatch, samples, bloom):
    """A blit resolve of drawn content cost ~0.5 ms at 1440p (see the 3D foundation lessons)."""
    import rendering.quick.scene3d.target as target_module

    def blit(*_args):
        raise AssertionError("scene target resolved through glBlitFramebuffer")

    monkeypatch.setattr(target_module.gl, "glBlitFramebuffer", blit)
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        _clear(capture)
        resources.draw_image(card, capture.textures[0])
        direct = _read(capture)
        _clear(capture)
        with target.scope(card, samples, resources, bloom=bloom):
            resources.draw_image(card, capture.textures[0])
            # A photograph emits nothing: in a bloom target its alpha (emitted brightness) is 0.
            gl.glColorMask(gl.GL_FALSE, gl.GL_FALSE, gl.GL_FALSE, gl.GL_TRUE)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glColorMask(gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        # So even with bloom the card is the direct draw.
        assert np.abs(_read(capture) - direct).max() <= 1
    finally:
        target.release()
        resources.release_resources()


@pytest.mark.parametrize("samples", (1, 4))
def test_motion_blur_leaves_a_still_scene_exact(capture, samples):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        _clear(capture)
        resources.draw_image(card, capture.textures[0])
        direct = _read(capture)
        _clear(capture)
        with target.scope(card, samples, resources, motion_blur=True):
            resources.draw_image(card, capture.textures[0])   # nothing writes motion
        assert np.array_equal(_read(capture), direct)
        target.release()
        assert not target.has_resources
    finally:
        target.release()
        resources.release_resources()


_MOVING_FRAGMENT = """#version 460 core
layout(location = 0) out vec4 FragColor;
layout(location = 1) out vec4 Motion;
uniform vec2 uMotion;
void main() {
    FragColor = vec4(1.0);
    Motion = vec4(uMotion, 0.0, 1.0);
}
"""


@pytest.mark.parametrize("samples", (1, 4))
def test_motion_blur_smears_a_moving_surface_along_its_motion_only(capture, samples):
    from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
    from rendering.quick.scene3d.motion import motion_blur_tile
    from rendering.quick.scene3d.resources import bind_frame

    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        full = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        square = _card_frame(capture, 120, 64, 16, 16)   # rows 64..79, columns 120..135 (top-down)
        motion = 1.5 * motion_blur_tile(HEIGHT)          # within the longest blur (two tiles)

        def draw(velocity, writes=True):
            _clear(capture)
            with target.scope(full, samples, resources, rect=(0, 0, WIDTH, HEIGHT), motion_blur=True):
                gl.glClearColor(0.0, 0.0, 0.0, 1.0)
                program = resources.program("moving", ITEM_QUAD_VERTEX_SOURCE, _MOVING_FRAGMENT)
                bind_frame(program, resources.uniforms("moving", ("uMatrix", "uItemSize", "uMotion")), square)
                gl.glUniform2f(resources.uniforms("moving", ("uMatrix", "uItemSize", "uMotion"))["uMotion"],
                               *velocity)
                gl.glBindVertexArray(capture.vao)
                if writes:
                    with target.velocity_writes():
                        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                else:
                    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            return _read(capture)[::-1]   # top-down rows

        still = draw((0.0, 0.0))
        lit = np.nonzero(still[..., 0] > 0)
        assert (lit[0].min(), lit[0].max(), lit[1].min(), lit[1].max()) == (64, 79, 120, 135)
        # Motion the pass may not write (outside velocity_writes) changes nothing.
        assert np.array_equal(draw((motion, 0.0), writes=False), still)

        moving = draw((motion, 0.0))
        middle = moving[72, :, 0]
        spread = np.nonzero(middle > 0)[0]
        # It smears sideways, about half the motion each way (the shutter centres on now)...
        assert spread.min() <= 120 - motion / 2 + 3 and spread.max() >= 135 + motion / 2 - 3
        assert 0 < middle[118] < 255 and 0 < middle[137] < 255   # translucent streak ends
        # ...but never up or down.
        assert not moving[:62, :, :3].any() and not moving[82:, :, :3].any()
        # Vertical motion smears vertically only.
        rising = draw((0.0, motion))
        assert not rising[:, :118, :3].any() and not rising[:, 138:, :3].any()
        assert rising[62, 128, 0] > 0 and rising[81, 128, 0] > 0
    finally:
        target.release()
        resources.release_resources()


def _straight_alpha() -> None:
    """The Visualizer host's blend state, which an overlay composites into."""
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
    gl.glBlendFuncSeparate(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)


@pytest.mark.parametrize("samples", (1, 4))
def test_an_overlay_lays_the_scene_over_what_is_drawn(capture, samples):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        inner = _card_frame(capture, 70, 40, 50, 30)       # the scene covers only part of the card
        texture = capture.textures[0]
        _clear(capture)
        _straight_alpha()
        resources.draw_image(inner, texture)
        direct = _read(capture)

        _clear(capture)
        _straight_alpha()
        with target.scope(card, samples, resources, overlay=1.0):
            resources.draw_image(inner, texture)
        through = _read(capture)
        assert np.array_equal(direct, through)              # untouched card pixels stay as they were

        _clear(capture)
        _straight_alpha()
        with target.scope(card, samples, resources, overlay=0.5):
            resources.draw_image(inner, texture)
        half = _read(capture)
        magenta = np.array([255, 0, 255, 255])
        drawn = (direct != magenta).any(axis=2)
        expected = 0.5 * direct[..., :3] + 0.5 * magenta[:3]
        assert np.abs(half[..., :3][drawn] - expected[drawn]).max() <= 1
        assert np.array_equal(half[~drawn], direct[~drawn])
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        programs = {key for key, *_ in __import__("rendering.quick.scene3d.target", fromlist=["x"])
                    .scene_target_programs(samples, False, False, overlay=True)}
        assert programs <= set(resources._programs)        # the warm-up list covers what it draws
    finally:
        gl.glDisable(gl.GL_BLEND)
        target.release()
        resources.release_resources()


def test_an_overlays_smoothed_edges_blend_without_a_dark_fringe(capture):
    from rendering.quick.render.gl_resources import compile_program

    program = compile_program("#version 460 core\nvoid main() {\n"
                              "    vec2 p[3] = vec2[](vec2(-0.6, -0.8), vec2(0.7, -0.5), vec2(-0.2, 0.9));\n"
                              "    gl_Position = vec4(p[gl_VertexID], 0.0, 1.0);\n}\n",
                              "#version 460 core\nout vec4 FragColor;\nvoid main() { FragColor = vec4(1.0); }\n",
                              label="overlay edge test")
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        _clear(capture)
        _straight_alpha()
        with target.scope(card, 4, resources, overlay=1.0):
            gl.glUseProgram(program)
            gl.glBindVertexArray(capture.vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        pixels = _read(capture)
        green = pixels[..., 1]
        assert ((green > 10) & (green < 245)).sum() > 50     # smoothed edge pixels exist
        # White over magenta: red and blue stay full everywhere; a dark fringe would drop them.
        assert pixels[..., 0].min() >= 253 and pixels[..., 2].min() >= 253
    finally:
        gl.glDisable(gl.GL_BLEND)
        gl.glDeleteProgram(program)
        target.release()
        resources.release_resources()


def test_an_overlay_refuses_motion_blur(capture):
    from rendering.quick.scene3d.target import scene_target_programs

    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        with pytest.raises(ValueError, match="overlay"):
            with target.scope(card, 4, resources, overlay=1.0, motion_blur=True):
                pass
        with pytest.raises(ValueError, match="overlay"):
            scene_target_programs(4, False, True, overlay=True)
    finally:
        target.release()
        resources.release_resources()


def _emitting_program(emit: bool):
    """A quad over the middle of the card: dim grey, emitting warm light into location 1."""
    from rendering.quick.render.gl_resources import compile_program
    from rendering.quick.scene3d.target import SCENE_EMISSION_GLSL

    vertex = ("#version 460 core\nvoid main() {\n"
              "    vec2 p[4] = vec2[](vec2(-0.2, -0.2), vec2(0.2, -0.2), vec2(-0.2, 0.2), vec2(0.2, 0.2));\n"
              "    gl_Position = vec4(p[gl_VertexID], 0.0, 1.0);\n}\n")
    fragment = ("#version 460 core\nlayout(location = 0) out vec4 FragColor;\n"
                "layout(location = 1) out vec4 Emission;\n" + SCENE_EMISSION_GLSL
                + "void main() { FragColor = vec4(0.2, 0.2, 0.2, 1.0);"
                + (" Emission = sceneEmission(vec3(2.0, 1.2, 0.3)); }\n" if emit else " Emission = vec4(0.0); }\n"))
    return compile_program(vertex, fragment, label="overlay bloom test")


def _blend_state():
    names = (gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB, gl.GL_BLEND_SRC_ALPHA, gl.GL_BLEND_DST_ALPHA,
             gl.GL_BLEND_EQUATION_RGB, gl.GL_BLEND_EQUATION_ALPHA)
    return bool(gl.glIsEnabled(gl.GL_BLEND)), tuple(int(gl.glGetIntegerv(name)) for name in names)


@pytest.mark.parametrize("samples", (1, 4))
def test_an_overlays_bloom_glows_only_from_emitted_light_and_never_darkens(capture, samples):
    """With bloom an overlay's emitted light (written in emission_writes()) glows over what is
    drawn: additively, so nothing gets darker; without emission writes the bloom changes
    nothing; the caller's blend state comes back; the warm-up list covers what it draws."""
    from rendering.quick.scene3d.target import scene_target_programs

    resources, target = MeshResources("target test"), SceneTarget("target test")
    emitting, plain = _emitting_program(True), _emitting_program(False)

    def draw(program, *, bloom, emit_scope):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, WIDTH, HEIGHT)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.25, 0.25, 0.3, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        _straight_alpha()
        before = _blend_state()
        with target.scope(card, samples, resources, overlay=1.0, bloom=bloom):
            gl.glUseProgram(program)
            gl.glBindVertexArray(capture.vao)
            if emit_scope:
                with target.emission_writes():
                    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            else:
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        assert _blend_state() == before                             # the caller's blend is back
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == capture.fbo
        return _read(capture)

    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        without = draw(emitting, bloom=0.0, emit_scope=True)        # no bloom: no emission attachment
        unlit = draw(plain, bloom=1.0, emit_scope=True)             # emits nothing
        unwritten = draw(emitting, bloom=1.0, emit_scope=False)     # emission writes not opened
        assert np.abs(unlit - without).max() <= 1
        assert np.abs(unwritten - without).max() <= 1
        glowing = draw(emitting, bloom=1.0, emit_scope=True)
        brighter = glowing[..., :3].sum(axis=2) - without[..., :3].sum(axis=2)
        assert brighter.min() >= -2                                 # additive: never darker
        ring = (slice(HEIGHT // 2 - 26, HEIGHT // 2 - 16), slice(WIDTH // 2 - 10, WIDTH // 2 + 10))
        assert brighter[ring].mean() > 20                           # the glow spills past the quad
        assert brighter[:6, :6].max() <= 2                          # far away: untouched
        # Nothing carries over: a frame without emission after a glowing one shows no glow.
        assert np.abs(draw(plain, bloom=1.0, emit_scope=True) - unlit).max() <= 1
        programs = {key for key, *_ in scene_target_programs(samples, True, False, overlay=True)}
        assert programs <= set(resources._programs)
    finally:
        gl.glDisable(gl.GL_BLEND)
        gl.glDeleteProgram(emitting)
        gl.glDeleteProgram(plain)
        target.release()
        resources.release_resources()
    assert not target.has_resources


def test_light_shafts_are_one_transform_of_the_overlay_composite_and_warm_with_the_target():
    from rendering.quick.scene3d import target as module
    from rendering.quick.scene3d.shafts import SHAFT_PROGRAMS, SHAFT_SAMPLES_PROGRAMS
    for plain, shafted in ((module._COMPOSITE_OVERLAY_BLOOM_FRAGMENT, module._COMPOSITE_OVERLAY_SHAFTS_FRAGMENT),
                           (module._COMPOSITE_OVERLAY_BLOOM_SAMPLES_FRAGMENT,
                            module._COMPOSITE_OVERLAY_SHAFTS_SAMPLES_FRAGMENT)):
        assert shafted == module._with_shafts(plain) and shafted != plain
        assert shafted.count("uShafts") == 2 and "* scene.a" in shafted   # rays only where the scene drew
    for samples, extra in ((1, SHAFT_PROGRAMS), (4, SHAFT_SAMPLES_PROGRAMS)):
        for bloom in (False, True):
            without = module.scene_target_programs(samples, bloom, False, overlay=True)
            with_shafts = module.scene_target_programs(samples, bloom, False, overlay=True, shafts=True)
            assert with_shafts[:len(without)] == without        # frames without a light are covered too
            assert all(program in with_shafts for program in extra)
            assert any(key.startswith("scene_overlay_shafts") for key, *_ in with_shafts)


_RECT_VERTEX = """#version 460 core
uniform vec4 uRect;   // clip-space x0, y0, x1, y1
uniform float uDepth; // clip-space z
void main() {
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1));
    gl_Position = vec4(mix(uRect.xy, uRect.zw, corner), uDepth, 1.0);
}
"""
_FLAT_FRAGMENT = """#version 460 core
out vec4 FragColor;
uniform vec4 uColour;
void main() { FragColor = uColour; }
"""
# Reads the captured background at its own pixel: blue -> red, depth -> green.
_READ_BACK_FRAGMENT = """#version 460 core
out vec4 FragColor;
uniform sampler2D uBackground;
uniform sampler2D uBackgroundDepth;
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy);
    FragColor = vec4(texelFetch(uBackground, texel, 0).b, texelFetch(uBackgroundDepth, texel, 0).r, 0.0, 1.0);
}
"""


def _rect(program, rect, depth, colour=None):
    gl.glUseProgram(program)
    gl.glUniform4f(gl.glGetUniformLocation(program, "uRect"), *rect)
    gl.glUniform1f(gl.glGetUniformLocation(program, "uDepth"), depth)
    if colour is not None:
        gl.glUniform4f(gl.glGetUniformLocation(program, "uColour"), *colour)
    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)


@pytest.mark.parametrize("samples", (1, 4))
def test_a_depth_texture_target_draws_the_same_and_its_background_holds_colour_and_nearest_depth(capture, samples):
    from rendering.quick.render.gl_resources import compile_program
    resources, target = MeshResources("target test"), SceneTarget("target test")
    flat = compile_program(_RECT_VERTEX, _FLAT_FRAGMENT, label="flat")
    read_back = compile_program(_RECT_VERTEX, _READ_BACK_FRAGMENT, label="read back")
    try:
        card = _card_frame(capture, 40, 20, 120, 80)
        _clear(capture)
        with target.scope(card, samples, resources):
            resources.draw_image(card, capture.textures[0])
        plain = _read(capture)
        _clear(capture)
        with target.scope(card, samples, resources, depth_texture=True):
            resources.draw_image(card, capture.textures[0])
        assert np.array_equal(plain, _read(capture))      # the depth texture changes nothing it draws
        assert target._names["depth_texture"] and not target._names["depth"]

        _clear(capture)
        with target.scope(card, samples, resources, depth_texture=True):
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glBindVertexArray(capture.vao)
            _rect(flat, (-1.0, -1.0, 0.0, 1.0), -0.6, (1.0, 0.0, 0.0, 1.0))   # left: red, nearer
            _rect(flat, (-1.0, -1.0, 1.0, 1.0), 0.2, (0.0, 0.0, 1.0, 1.0))    # everywhere else: blue
            fbo, viewport = (int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)),
                             tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)))
            colour, depth = target.background(card, resources)
            # Drawing carries on exactly where it was.
            assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == fbo
            assert tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT)) == viewport
            assert bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glUseProgram(read_back)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, depth)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUniform1i(gl.glGetUniformLocation(read_back, "uBackground"), 0)
            gl.glUniform1i(gl.glGetUniformLocation(read_back, "uBackgroundDepth"), 1)
            _rect(read_back, (-1.0, -1.0, 1.0, 1.0), 0.0)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        pixels = _read(capture)
        rows = HEIGHT - 20 - 80
        left, right = pixels[rows + 40, 40 + 20], pixels[rows + 40, 40 + 100]
        # The window viewport spans the whole capture: x < 0 in clip space is the window's left half (x < 128).
        assert abs(int(left[0]) - 0) <= 1 and abs(int(left[1]) - round(0.2 * 255)) <= 1     # red, depth 0.2
        assert abs(int(right[0]) - 255) <= 1 and abs(int(right[1]) - round(0.6 * 255)) <= 1  # blue, depth 0.6
    finally:
        gl.glDeleteProgram(flat)
        gl.glDeleteProgram(read_back)
        target.release()
        resources.release_resources()
    assert not target.has_resources


def test_targets_that_ask_for_neither_allocate_no_depth_texture_or_background(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    try:
        _clear(capture)
        with target.scope(_card_frame(capture, 40, 20, 120, 80), 4, resources):
            resources.draw_image(_card_frame(capture, 40, 20, 120, 80), capture.textures[0])
        assert target._names["depth"] and not target._names["depth_texture"]
        assert not any(target._names[key] for key in ("background_fbo", "background_colour", "background_depth"))
        # Warming ahead for a background allocates it as one unit, then reports ready.
        size = (120, 80)
        assert not target.warm(size, 4, background=True)
        assert target.warm(size, 4, background=True) and target._names["background_fbo"]
    finally:
        target.release()
        resources.release_resources()


_TRANSPARENT_FRAGMENT = """#version 460 core
uniform vec4 uColour;     // straight colour and alpha
uniform float uViewDepth; // scene units from the eye
""" + __import__("rendering.quick.scene3d.target", fromlist=["SCENE_OIT_GLSL"]).SCENE_OIT_GLSL + """
void main() { sceneTransparent(uColour.rgb * uColour.a, uColour.a, uViewDepth); }
"""


def _transparent(program, rect, depth, colour, view_depth):
    gl.glUseProgram(program)
    gl.glUniform1f(gl.glGetUniformLocation(program, "uViewDepth"), view_depth)
    _rect(program, rect, depth, colour)


@pytest.mark.parametrize("samples", (1, 4))
def test_transparent_layers_give_the_same_picture_in_either_order_and_respect_opaque_depth(capture, samples):
    from rendering.quick.render.gl_resources import compile_program
    resources, target = MeshResources("target test"), SceneTarget("target test")
    flat = compile_program(_RECT_VERTEX, _FLAT_FRAGMENT, label="flat")
    glass = compile_program(_RECT_VERTEX, _TRANSPARENT_FRAGMENT, label="glass")
    red, blue = ((-0.8, -0.8, 0.4, 0.8), -0.2, (1.0, 0.0, 0.0, 0.5), 2.0), ((-0.4, -0.6, 0.8, 0.6), 0.0, (0.0, 0.0, 1.0, 0.5), 3.0)
    behind = ((0.5, -1.0, 1.0, 1.0), 0.8, (1.0, 1.0, 0.0, 0.8), 9.0)
    card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)

    def draw(order):
        _clear(capture)
        with target.scope(card, samples, resources, oit=True):
            gl.glEnable(gl.GL_DEPTH_TEST)
            gl.glDepthFunc(gl.GL_LESS)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glBindVertexArray(capture.vao)
            _rect(flat, (-1.0, -1.0, 1.0, 1.0), 0.95, (0.1, 0.1, 0.1, 1.0))   # a far backdrop
            _rect(flat, (0.5, -1.0, 1.0, 1.0), 0.5, (0.0, 1.0, 0.0, 1.0))     # an opaque wall at the right
            gl.glBlendFunci(0, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            with target.transparent_writes(card, resources):
                for layer in order:
                    _transparent(glass, *layer)
            # Blend and depth state come back as they were.
            assert int(np.asarray(gl.glGetIntegeri_v(gl.GL_BLEND_SRC_RGB, 0)).ravel()[0]) == gl.GL_SRC_ALPHA
            assert bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK)) and bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        return _read(capture)

    try:
        forward, backward = draw((red, blue, behind)), draw((behind, blue, red))
        assert np.abs(forward - backward).max() <= 1

        def naive(order):   # negative control: ordinary alpha blending depends on the order
            _clear(capture)
            with target.scope(card, samples, resources):
                gl.glDisable(gl.GL_DEPTH_TEST)
                gl.glEnable(gl.GL_BLEND)
                gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glBindVertexArray(capture.vao)
                for rect, depth, colour, _view in order:
                    _rect(flat, rect, depth, colour)
                gl.glDisable(gl.GL_BLEND)
            return _read(capture)
        assert np.abs(naive((red, blue)) - naive((blue, red))).max() > 40
        row = HEIGHT // 2
        column = lambda clip_x: int((clip_x + 1.0) * 0.5 * WIDTH)
        both, red_only, wall = forward[row, column(0.0)], forward[row, column(-0.6)], forward[row, column(0.9)]
        assert red_only[0] > 120 and red_only[2] < 30            # one layer: red over the dark backdrop
        assert both[0] > both[2] > 40                              # both: the nearer red outweighs the blue
        assert abs(int(wall[1]) - 255) <= 2 and wall[0] < 5       # the wall hides the yellow layer behind it
    finally:
        gl.glDeleteProgram(flat)
        gl.glDeleteProgram(glass)
        target.release()
        resources.release_resources()


def test_transparency_allocates_nothing_unless_asked_and_needs_its_scope(capture):
    resources, target = MeshResources("target test"), SceneTarget("target test")
    card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
    try:
        _clear(capture)
        with target.scope(card, 4, resources):
            with pytest.raises(RuntimeError, match="oit=True"):
                with target.transparent_writes(card, resources):
                    pass
        assert not any(target._names[key] for key in ("oit_fbo", "oit_accum", "oit_reveal"))
        with target.scope(card, 4, resources, oit=True):
            pass
        assert all(target._names[key] for key in ("oit_fbo", "oit_accum", "oit_reveal"))
        target.release()
        assert not target.has_resources
    finally:
        target.release()
        resources.release_resources()


@pytest.mark.parametrize("samples", (1, 4))
def test_an_hdr_target_keeps_light_brighter_than_white_and_tone_maps_it_once(capture, samples):
    from rendering.quick.render.gl_resources import compile_program
    resources, target = MeshResources("target test"), SceneTarget("target test")
    flat = compile_program(_RECT_VERTEX, _FLAT_FRAGMENT, label="flat")
    try:
        card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
        with pytest.raises(ValueError):
            with target.scope(card, samples, resources, hdr=1.0):
                pass
        captured = {}

        def draw(values):
            _clear(capture)
            with target.scope(card, samples, resources, overlay=1.0, bloom=0.5, hdr=1.0):
                gl.glBindVertexArray(capture.vao)
                for x0, value in zip((-1.0, -0.5, 0.0, 0.5), values):
                    _rect(flat, (x0, -1.0, x0 + 0.5, 1.0), 0.0, (value, value, value, 1.0))
                colour, _depth = target.background(card, resources)
                buffer = np.zeros((target.allocation[1], target.allocation[0], 4), dtype=np.float32)
                gl.glGetTextureImage(colour, 0, gl.GL_RGBA, gl.GL_FLOAT, buffer.nbytes, buffer)
                captured["background"] = buffer
            return _read(capture)

        pixels = draw((0.25, 1.0, 3.0, 12.0))
        row = HEIGHT // 2
        # Light past white is kept for every pass that reads the scene.
        assert captured["background"][row, 3 * WIDTH // 4 - 8, 0] == pytest.approx(3.0, abs=0.01)
        levels = [int(pixels[row, x, 0]) for x in (WIDTH // 8, 3 * WIDTH // 8, 5 * WIDTH // 8, 7 * WIDTH // 8)]
        # One smooth curve: brighter in stays brighter out, nothing clips below the brightest.
        assert levels[0] < levels[1] < levels[2] < levels[3] <= 255
        assert levels[2] < 250
    finally:
        gl.glDeleteProgram(flat)
        target.release()
        resources.release_resources()


def test_every_optional_attachment_follows_a_resize_and_is_gone_after_release(capture):
    """Depth texture, background capture, OIT and HDR (with bloom) reallocate when the rect outgrows its bucket and
    leave no GL object behind on release (park / context teardown)."""
    resources, target = MeshResources("target test"), SceneTarget("target test")

    def names():
        return {key: name for key, name in target._names.items() if name}

    def alive(key, name):
        return bool(gl.glIsFramebuffer(name) if key.endswith("fbo") else
                    gl.glIsTexture(name) or gl.glIsRenderbuffer(name))

    try:
        _clear(capture)
        kwargs = dict(overlay=1.0, bloom=0.5, depth_texture=True, oit=True, hdr=1.0)
        with target.scope(_card_frame(capture, 0, 0, 100, 60), 4, resources, **kwargs):
            target.background(_card_frame(capture, 0, 0, 100, 60), resources)
        small = names()
        for key in ("depth_texture", "background_colour", "background_depth", "oit_fbo", "oit_accum", "oit_reveal"):
            assert key in small, key
        assert all(alive(key, name) for key, name in small.items())
        with target.scope(_card_frame(capture, 0, 0, 130, 60), 4, resources, **kwargs):
            target.background(_card_frame(capture, 0, 0, 130, 60), resources)
        assert target.allocation == (192, 64, 4)
        large = names()
        assert set(large) == set(small)
        out = np.zeros(1, dtype=np.int32)
        gl.glGetTextureLevelParameteriv(large["depth_texture"], 0, gl.GL_TEXTURE_WIDTH, out)
        width = int(out[0])
        assert width == 192                        # the depth texture followed the new bucket
        target.release()
        assert not target.has_resources
        assert not any(alive(key, name) for key, name in {**small, **large}.items())
    finally:
        target.release()
        resources.release_resources()


@pytest.mark.parametrize("samples", (1, 4))
def test_bright_transparent_layers_at_the_near_plane_stay_finite_and_order_independent(capture, samples):
    """Layers right at the eye (near giants crossing the near plane) carry the largest weight; bright (HDR) light
    stacked there must not overflow the half-float accumulation into infinity / NaN (a black hole)."""
    from rendering.quick.render.gl_resources import compile_program
    resources, target = MeshResources("target test"), SceneTarget("target test")
    flat = compile_program(_RECT_VERTEX, _FLAT_FRAGMENT, label="flat")
    glass = compile_program(_RECT_VERTEX, _TRANSPARENT_FRAGMENT, label="glass")
    card = _card_frame(capture, 0, 0, WIDTH, HEIGHT)
    layers = [((-0.9 + 0.05 * i, -0.9, 0.9, 0.9), 0.0, (6.0, 5.0, 4.0, 0.9), 0.001 * (i + 1)) for i in range(8)]

    def draw(order):
        _clear(capture)
        with target.scope(card, samples, resources, overlay=1.0, bloom=0.5, oit=True, hdr=1.0):
            gl.glBindVertexArray(capture.vao)
            _rect(flat, (-1.0, -1.0, 1.0, 1.0), 0.95, (0.1, 0.1, 0.1, 1.0))
            with target.transparent_writes(card, resources):
                for layer in order:
                    _transparent(glass, *layer)
            colour, _depth = target.background(card, resources)
            buffer = np.zeros((target.allocation[1], target.allocation[0], 4), dtype=np.float32)
            gl.glGetTextureImage(colour, 0, gl.GL_RGBA, gl.GL_FLOAT, buffer.nbytes, buffer)
        return _read(capture), buffer

    try:
        forward, scene = draw(layers)
        backward, _ = draw(layers[::-1])
        overlap = scene[HEIGHT // 2, WIDTH // 2]
        assert np.all(np.isfinite(scene)), "transparency accumulation overflowed"
        assert overlap[0] > 1.0                                   # bright light kept past white
        assert int(forward[HEIGHT // 2, WIDTH // 2, 0]) > 200      # shown bright, not a black hole
        assert np.abs(forward - backward).max() <= 2
    finally:
        gl.glDeleteProgram(flat)
        gl.glDeleteProgram(glass)
        target.release()
        resources.release_resources()
