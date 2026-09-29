"""Photo reflections: a per-run, renderer-owned, mipmapped copy of a photograph that blurs by
roughness, never touches the lent photographs, and is adopted where it improves the look.

Offscreen GL through the transition capture harness; no window is shown.
"""
from __future__ import annotations

import ctypes

import numpy as np
import pytest
from OpenGL import GL as gl
from PIL import Image

from rendering.gl_programs import scene3d as lib
from rendering.quick.scene3d.environment import PhotoEnvironment, environment_size
from rendering.quick.scene3d.post import FULLSCREEN_VERTEX_SOURCE
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.transitions.state import TransitionRun
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt


def _levels(texture: int) -> tuple[int, int]:
    """(width of level 0, width of level 1): a texture without mipmaps has no level 1."""
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    widths = []
    for level in (0, 1):
        value = ctypes.c_int()
        gl.glGetTexLevelParameteriv(gl.GL_TEXTURE_2D, level, gl.GL_TEXTURE_WIDTH, ctypes.byref(value))
        widths.append(value.value)
    return tuple(widths)


def _pixels(texture: int, width: int, height: int) -> np.ndarray:
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    data = gl.glGetTexImage(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(data), dtype=np.uint8).reshape(height, width, 4).astype(np.int16)


def test_the_copy_is_once_per_run_mipmapped_and_never_touches_the_photographs(qt_app):
    width, height = 320, 180
    capture = TransitionCapture(width, height)
    resources, environment = MeshResources("environment test"), PhotoEnvironment("environment test")
    try:
        run = capture.run("block_spins", direction="left")
        frame = capture.frame(run, 0.5)
        lent = capture.textures[1]
        before = _pixels(lent, width, height), _levels(lent)
        texture = environment.texture(frame, resources)
        # The lent photograph is only sampled: same pixels, still no mip levels.
        assert np.array_equal(_pixels(lent, width, height), before[0]) and _levels(lent) == before[1] == (width, 0)
        # The copy is ours, sized from the photograph, with its own mip levels...
        copy_width, copy_height = environment_size((width, height))
        assert _levels(texture) == (copy_width, copy_width // 2)
        copy = _pixels(texture, copy_width, copy_height)
        photo = np.asarray(capture.images[1], dtype=np.int16)
        assert np.abs(copy[..., :3].mean(axis=(0, 1)) - photo[..., :3].mean(axis=(0, 1))).max() < 3
        # ...made once per run.
        assert environment.texture(capture.frame(run, 0.7), resources) == texture and environment.copies == 1
        again = TransitionRun.start(run_id=run.run_id + 1, request=run.request, start_ns=0)
        environment.texture(capture.frame(again, 0.5), resources)
        assert environment.copies == 2
        environment.release()
        assert not environment.has_resources
    finally:
        environment.release()
        resources.release_resources()
        capture.close()


_PROBE_FRAGMENT = """#version 410 core
out vec4 FragColor;
uniform sampler2D uEnvironment;
""" + lib.SCENE3D_GLSL + """
void main() {
    // Four probes across a sharp black/white edge at u = 0.5: sharp, then very rough.
    int i = int(gl_FragCoord.x);
    float u = (i % 2 == 0) ? 0.47 : 0.53;
    float roughness = i < 2 ? 0.0 : 1.0;
    FragColor = vec4(sceneEnvironment(uEnvironment, vec2(u, 0.5), roughness), 1.0);
}
"""


def test_roughness_blurs_the_reflection(qt_app):
    width, height = 512, 288
    half = np.zeros((height, width, 4), dtype=np.uint8)
    half[..., 3] = 255
    half[:, width // 2:, :3] = 255
    capture = TransitionCapture(width, height, destination=Image.fromarray(half))
    resources, environment = MeshResources("environment test"), PhotoEnvironment("environment test")
    target, fbo = int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1))
    try:
        frame = capture.frame(capture.run("block_spins", direction="left"), 0.5)
        texture = environment.texture(frame, resources)
        gl.glBindTexture(gl.GL_TEXTURE_2D, target)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, 4, 1, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, target, 0)
        gl.glViewport(0, 0, 4, 1)
        program = resources.program("probe", FULLSCREEN_VERTEX_SOURCE, _PROBE_FRAGMENT)
        gl.glUseProgram(program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glUniform1i(resources.uniforms("probe", ("uEnvironment",))["uEnvironment"], 0)
        gl.glBindVertexArray(capture.vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        values = np.frombuffer(bytes(gl.glReadPixels(0, 0, 4, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)), np.uint8)[::4]
        sharp_dark, sharp_light, rough_dark, rough_light = (int(v) for v in values)
        assert sharp_dark < 30 and sharp_light > 225          # roughness 0: the picture as it is
        # Roughness 1: the picture's broad colours, well under half the sharp contrast across the edge.
        assert 40 < rough_dark < 215 and 40 < rough_light < 215
        assert abs(rough_light - rough_dark) < 0.4 * (sharp_light - sharp_dark)
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([target])
        environment.release()
        resources.release_resources()
        capture.close()


def _dark_top_bright_bottom(width: int, height: int) -> Image.Image:
    rows = np.linspace(15, 235, height)[:, None].repeat(width, axis=1)
    return Image.fromarray(np.dstack([rows, rows, rows, np.full_like(rows, 255)]).astype(np.uint8))


@pytest.mark.parametrize("direction", ("diag_tl_br", "diag_tr_bl", "left", "up"))
def test_block_spins_edge_reflections_read_alike_in_both_halves_of_the_spin(qt_app, direction):
    """A reflection used to read the picture beside the edge on screen, so early diagonal
    spins (edges near the top) reflected only a dark top border and looked flat."""
    width, height = 480, 270
    capture = TransitionCapture(width, height, destination=_dark_top_bright_bottom(width, height))
    try:
        def edge_brightness(progress):
            frames = {}
            for mode in ("Off", "Reflection"):
                run = capture.run("block_spins", direction=direction, settings={"blockspin": {"edge_glass": mode}})
                frames[mode] = np.asarray(capture.render(run, progress)[0], dtype=np.int16)[..., :3]
            edge = np.abs(frames["Reflection"] - frames["Off"]).max(axis=2) > 2
            assert edge.sum() > 50
            return frames["Reflection"][edge].mean()

        early, late = edge_brightness(0.42), edge_brightness(0.58)
        assert min(early, late) / max(early, late) > 0.6, (early, late)
    finally:
        capture.close()


def test_exploding_tiles_reflect_only_once_released_and_glass_only_with_sheen(qt_app, monkeypatch):
    capture = TransitionCapture(320, 180)
    try:
        def frames(effect, direction, progresses, section, reflections):
            if not reflections:
                monkeypatch.setattr(PhotoEnvironment, "texture", lambda self, frame, resources, role="destination": 0)
            else:
                monkeypatch.undo()
            run = capture.run(effect, direction=direction, duration_ms=3000, settings={effect: section})
            return [np.asarray(capture.render(run, p)[0], dtype=np.int16) for p in progresses]

        # The wall is exact until its tiles are released; released tiles reflect the new picture.
        with_env = frames("exploding_tiles", "center_out", (0.05, 0.2), {}, True)
        without = frames("exploding_tiles", "center_out", (0.05, 0.2), {}, False)
        assert np.array_equal(with_env[0], without[0])
        assert np.abs(with_env[1] - without[1]).mean() > 0.05
        # Glass reflections are sheen: none at sheen zero.
        with_env = frames("glass_shatter", "left", (0.4,), {"sheen": 0.0}, True)
        without = frames("glass_shatter", "left", (0.4,), {"sheen": 0.0}, False)
        assert np.array_equal(with_env[0], without[0])
        with_env = frames("glass_shatter", "left", (0.4,), {"sheen": 1.0}, True)
        without = frames("glass_shatter", "left", (0.4,), {"sheen": 1.0}, False)
        assert np.abs(with_env[0] - without[0]).mean() > 0.05
        # The copies are per run: the host's park drops them.
        monkeypatch.undo()
        renderer = capture.host._implementations["glass_shatter"]
        assert renderer._environment.has_resources
        capture.host.park()
        assert not renderer._environment.has_resources
    finally:
        capture.close()
