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

import rendering.quick.scene3d.environment as environment_module
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


def _immutable_levels(texture: int) -> int:
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    return int(gl.glGetTexParameteriv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_IMMUTABLE_LEVELS))


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
        assert _immutable_levels(texture) == max(copy_width, copy_height).bit_length()
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


def test_named_environment_construction_uses_immutable_storage_and_only_binds_the_lent_photo(
    qt_app, monkeypatch,
):
    """Named setup removes three owned-texture bind/select calls from the first copy.

    The raster draw still binds its framebuffer and the borrowed photo to unit
    zero; those are deliberate draw-time state operations and are not counted
    as construction savings.
    """

    capture = TransitionCapture(320, 180)
    resources = MeshResources("environment DSA calls")
    environment = PhotoEnvironment("environment DSA calls")
    calls: dict[str, int] = {}
    names = (
        "glCreateTextures",
        "glTextureParameteri",
        "glTextureStorage2D",
        "glCreateFramebuffers",
        "glNamedFramebufferTexture",
        "glCheckNamedFramebufferStatus",
        "glGenerateTextureMipmap",
        "glActiveTexture",
        "glBindTexture",
        "glBindFramebuffer",
    )
    try:
        for name in names:
            original = getattr(environment_module.gl, name)

            def record(*args, _name=name, _original=original, **kwargs):
                calls[_name] = calls.get(_name, 0) + 1
                return _original(*args, **kwargs)

            monkeypatch.setattr(environment_module.gl, name, record)

        texture = environment.texture(
            capture.frame(capture.run("glass_shatter", direction="left"), 0.5),
            resources,
        )

        assert texture > 0
        assert calls["glCreateTextures"] == 1
        assert calls["glTextureParameteri"] == 4
        assert calls["glTextureStorage2D"] == 1
        assert calls["glCreateFramebuffers"] == 1
        assert calls["glNamedFramebufferTexture"] == 1
        assert calls["glCheckNamedFramebufferStatus"] == 1
        # N5.2c (ABI 36): the copy's levels are the shared box kernel's, never the driver's.
        assert calls.get("glGenerateTextureMipmap", 0) == 0
        # One active/bind pair samples the lent photo. Legacy construction also
        # selected/bound the owned texture for allocation and mipmaps, so this
        # complete first-copy path removes three calls (2 + 1).
        assert calls["glActiveTexture"] == 1
        assert calls["glBindTexture"] == 1
        assert calls["glBindFramebuffer"] >= 1
    finally:
        environment.release()
        resources.release_resources()
        capture.close()


def test_partial_environment_allocation_and_copy_failures_keep_or_retry_ownership(qt_app, monkeypatch):
    """No texture can become a valid cached environment until its copy succeeds."""

    capture = TransitionCapture(160, 90)
    resources = MeshResources("environment ownership")
    environment = PhotoEnvironment("environment ownership")
    try:
        with monkeypatch.context() as failed_allocation:
            def fail_storage(*_args, **_kwargs):
                raise RuntimeError("injected storage failure")

            failed_allocation.setattr(environment_module.gl, "glTextureStorage2D", fail_storage)
            with pytest.raises(RuntimeError, match="injected storage failure"):
                environment._allocate((64, 32))
        assert not environment.has_resources

        frame = capture.frame(capture.run("glass_shatter", direction="left"), 0.5)
        with monkeypatch.context() as failed_copy:
            def fail_attachment(*_args, **_kwargs):
                raise RuntimeError("injected attachment failure")

            failed_copy.setattr(
                environment_module.gl,
                "glNamedFramebufferTexture",
                fail_attachment,
            )
            with pytest.raises(RuntimeError, match="injected attachment failure"):
                environment.texture(frame, resources)
        assert environment._textures == {}
        # The FBO name was created before the named attachment failed, so its
        # owner retains it until explicit cleanup rather than losing the name.
        assert environment._fbo > 0 and environment.has_resources
        environment.release()
        assert not environment.has_resources

        texture = environment.texture(frame, resources)
        assert texture > 0 and environment.copies == 1
        rerun = TransitionRun.start(
            run_id=frame.run.run_id + 1,
            request=frame.run.request,
            start_ns=0,
        )
        with monkeypatch.context() as failed_reuse:
            failed_reuse.setattr(
                environment_module.gl,
                "glNamedFramebufferTexture",
                fail_attachment,
            )
            with pytest.raises(RuntimeError, match="injected attachment failure"):
                environment.texture(capture.frame(rerun, 0.5), resources)
        # Same-size reuse is invalidated too: a failed raster copy can have
        # partially replaced its pixels, so no old run key may retain it.
        assert environment._textures == {}
        environment.release()
        assert not environment.has_resources
    finally:
        environment.release()
        resources.release_resources()
        capture.close()


def test_environment_copy_restores_inherited_framebuffer_viewport_and_scissor(qt_app):
    """Named attachment construction must not weaken the existing raster-state fence."""

    capture = TransitionCapture(160, 90)
    resources = MeshResources("environment state restore")
    environment = PhotoEnvironment("environment state restore")
    read_fbo = int(gl.glGenFramebuffers(1))
    try:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, capture.fbo)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read_fbo)
        gl.glViewport(7, 9, 111, 61)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glScissor(11, 13, 77, 41)
        expected = (
            int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)),
            int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING)),
            tuple(int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)),
            tuple(int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)),
        )

        frame = capture.frame(capture.run("glass_shatter", direction="left"), 0.5)
        assert environment.texture(frame, resources) > 0

        actual = (
            int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)),
            int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING)),
            tuple(int(value) for value in gl.glGetIntegerv(gl.GL_VIEWPORT)),
            tuple(int(value) for value in gl.glGetIntegerv(gl.GL_SCISSOR_BOX)),
        )
        assert actual == expected and gl.glIsEnabled(gl.GL_SCISSOR_TEST)
    finally:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glDeleteFramebuffers(1, [read_fbo])
        environment.release()
        resources.release_resources()
        capture.close()


def test_environment_release_retries_a_failed_texture_deletion(qt_app, monkeypatch):
    """Park cleanup retains a live name when a driver deletion attempt fails."""

    capture = TransitionCapture(160, 90)
    resources = MeshResources("environment release retry")
    environment = PhotoEnvironment("environment release retry")
    try:
        frame = capture.frame(capture.run("glass_shatter", direction="left"), 0.5)
        environment.texture(frame, resources)
        original_delete = environment_module.gl.glDeleteTextures

        def fail_delete(*_args, **_kwargs):
            raise RuntimeError("injected delete failure")

        monkeypatch.setattr(environment_module.gl, "glDeleteTextures", fail_delete)
        with pytest.raises(RuntimeError, match="injected delete failure"):
            environment.release()
        assert environment.has_resources

        monkeypatch.setattr(environment_module.gl, "glDeleteTextures", original_delete)
        environment.release()
        assert not environment.has_resources
    finally:
        environment.release()
        resources.release_resources()
        capture.close()


def _level(texture: int, level: int, size: tuple[int, int]) -> np.ndarray:
    width, height = max(1, size[0] >> level), max(1, size[1] >> level)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    data = gl.glGetTexImage(gl.GL_TEXTURE_2D, level, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    return np.frombuffer(bytes(data), dtype=np.uint8).reshape(height, width, 4).astype(np.float64)


def _area_average(level: np.ndarray) -> np.ndarray:
    """The next level as the box kernel defines it (mip_chain.py): each texel the exact area average of the texels it
    covers (an even side two of 1/2, an odd side 2d + 1 three of (d - i), d and i + 1 over 2d + 1), rounded once."""

    def along(a: np.ndarray, axis: int) -> np.ndarray:
        a = np.moveaxis(a, axis, 0)
        s = a.shape[0]
        if s == 1:
            out = a
        elif s % 2 == 0:
            out = 0.5 * a[0::2] + 0.5 * a[1::2]
        else:
            d = s // 2
            i = np.arange(d).reshape((-1,) + (1,) * (a.ndim - 1))
            out = ((d - i) * a[0:2 * d:2] + d * a[1:2 * d:2] + (i + 1) * a[2:2 * d + 1:2]) / s
        return np.moveaxis(out, 0, axis)

    return np.floor(along(along(level, 0), 1) + 0.5)


def _chain_error() -> tuple[int, int]:
    """(the largest difference in 8-bit levels, the texels that differ) between each level of a copy of an odd-sized
    environment and the area average of the level above it."""
    width, height = 300, 200                         # the copy 512 x 341: an odd side from level 0
    noise = np.random.default_rng(52).integers(0, 256, (height, width, 4), dtype=np.uint8)
    noise[..., 3] = 255
    capture = TransitionCapture(width, height, destination=Image.fromarray(noise, "RGBA"))
    resources, environment = MeshResources("environment chain"), PhotoEnvironment("environment chain")
    try:
        texture = environment.texture(capture.frame(capture.run("glass_shatter", direction="left"), 0.5), resources)
        size = environment_size((width, height))
        assert size[1] % 2 == 1
        worst = differing = 0
        for level in range(1, max(size).bit_length()):
            made = _level(texture, level, size)
            expected = _area_average(_level(texture, level - 1, size))
            worst = max(worst, int(np.abs(made - expected).max()))
            differing += int((made != expected).any(axis=2).sum())
        return worst, differing
    finally:
        environment.release()
        resources.release_resources()
        capture.close()


def test_the_copys_chain_is_the_shared_box_kernels(qt_app, monkeypatch):
    """N5.2c (ABI 36): the copy's levels are the shared box kernel's (the native core's environment step runs the same
    text), each the area average of the level above: a texel apart only where the kernel's float sum of an odd side's
    thirds rounds a half the other way (measured 1 of the chain's ~58,000 texels)."""
    worst, differing = _chain_error()
    assert worst <= 1 and differing <= 8
    # Negative control: the former chain, the driver's glGenerateTextureMipmap (its odd levels anchored at row 0 on this
    # machine's OpenGL; measured 12,532 texels apart), is caught.
    monkeypatch.setattr(environment_module, "dispatch_mip_chain",
                        lambda _program, texture, _size, _levels, _fmt: gl.glGenerateTextureMipmap(texture))
    assert _chain_error()[1] > 8


_PROBE_FRAGMENT = """#version 460 core
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
