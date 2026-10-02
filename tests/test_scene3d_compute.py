"""S15: the compute seam and its first consumer, motion blur's tile max.

Real offscreen GL, no window. The compute tile max must equal a column-then-row
first-longest reference exactly (ties and partial edge tiles included), its dispatch must
own the barrier its reader needs, image unit state must come back, a run without motion
blur must compile and dispatch no compute, and failures must leave nothing behind.
"""
from __future__ import annotations

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.quick.render import gl_resources
from rendering.quick.scene3d import compute as compute_module
from rendering.quick.scene3d.compute import bound_image, dispatch
from rendering.quick.scene3d.motion import MOTION_BLUR_MAX_TILE, MotionBlur, motion_blur_tile
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick import gl_query
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(64, 64)
    yield capture
    capture.close()


def _texture(width: int, height: int, internal: int, data=None, layout=(gl.GL_RG, gl.GL_FLOAT)) -> int:
    name = (gl.GLuint * 1)()
    gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
    texture = int(name[0])
    for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
        gl.glTextureParameteri(texture, parameter, gl.GL_NEAREST)
    gl.glTextureStorage2D(texture, 1, internal, width, height)
    if data is not None:
        gl.glTextureSubImage2D(texture, 0, 0, 0, width, height, *layout, np.ascontiguousarray(data))
    return texture


def _read_rg(texture: int, width: int, height: int) -> np.ndarray:
    out = np.zeros((height, width, 2), np.float32)
    gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT)   # this test-only readback follows image stores
    gl.glGetTextureImage(texture, 0, gl.GL_RG, gl.GL_FLOAT, out.nbytes, out)
    return out


def _reference_tile_max(velocity: np.ndarray, tile: int) -> np.ndarray:
    """The previous separable fragment passes: first longest across each tile row's columns,
    then first longest down those rows (strictly longer wins, starting from no motion)."""
    height, width, _ = velocity.shape
    rows_out, columns_out = -(-height // tile), -(-width // tile)
    out = np.zeros((rows_out, columns_out, 2), np.float32)
    squared = (velocity.astype(np.float64) ** 2).sum(axis=2)
    for ty in range(rows_out):
        for tx in range(columns_out):
            best, best_squared = np.zeros(2), 0.0
            for y in range(ty * tile, min((ty + 1) * tile, height)):
                row_best, row_squared = np.zeros(2), 0.0
                for x in range(tx * tile, min((tx + 1) * tile, width)):
                    if squared[y, x] > row_squared:
                        row_squared, row_best = squared[y, x], velocity[y, x]
                if row_squared > best_squared:
                    best_squared, best = row_squared, row_best
            out[ty, tx] = best
    return out


def _fields(width: int, height: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(1234)
    # Quarter steps: exactly representable in RG16F, and exact squares, so the reference is exact.
    random = rng.integers(-64, 65, size=(height, width, 2)).astype(np.float32) / 4.0
    # Many equal magnitudes pointing different ways: only the scan order decides.
    ties = np.zeros((height, width, 2), np.float32)
    choices = np.array([(3.0, 4.0), (4.0, 3.0), (-5.0, 0.0), (0.0, -5.0), (-3.0, -4.0)], np.float32)
    mask = rng.random((height, width)) < 0.3
    ties[mask] = choices[rng.integers(0, len(choices), size=int(mask.sum()))]
    single = np.zeros((height, width, 2), np.float32)
    single[height - 1, width - 1] = (-2.5, 1.25)   # the last texel of a partial corner tile
    return {"random": random, "ties": ties, "single": single, "still": np.zeros((height, width, 2), np.float32)}


@pytest.mark.parametrize("size", ((97, 61), (300, 770)), ids=("K8-partial", "K19-partial"))
def test_the_compute_tile_max_equals_the_column_then_row_reference_exactly(capture, size):
    width, height = size
    tile = motion_blur_tile(height)
    assert width % tile and height % tile, "both axes end in a partial tile"
    resources = MeshResources("tile max test")
    blur = MotionBlur("tile max test")
    scene = _texture(width, height, gl.GL_RGBA8)
    try:
        for name, field in _fields(width, height).items():
            velocity = _texture(width, height, gl.GL_RG16F, field)
            try:
                blur.apply(scene, velocity, (width, height), resources, capture.vao)
                tiles, _fbo, tile_w, tile_h = blur._passes[0]
                got = _read_rg(tiles, tile_w, tile_h)
                assert np.array_equal(got, _reference_tile_max(field, tile)), name
            finally:
                gl.glDeleteTextures([velocity])
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glDeleteTextures([scene])
        blur.release()
        resources.release_resources()


def test_the_dispatch_owns_the_texture_fetch_barrier_before_the_gather_reads(capture, monkeypatch):
    """The tile image is sampled by the gather: the barrier must be issued after the dispatch
    and before that draw, naming texture fetches (a missing or wrong bit fails here)."""
    events = []
    for name in ("glDispatchCompute", "glMemoryBarrier", "glDrawArrays"):
        original = getattr(gl, name)

        def recording(*args, _name=name, _original=original):
            events.append((_name, args))
            return _original(*args)

        monkeypatch.setattr(gl, name, recording)
    resources = MeshResources("barrier test")
    blur = MotionBlur("barrier test")
    scene, velocity = _texture(64, 64, gl.GL_RGBA8), _texture(64, 64, gl.GL_RG16F, _fields(64, 64)["random"])
    try:
        blur.apply(scene, velocity, (64, 64), resources, capture.vao)
        names = [name for name, _args in events]
        assert names == ["glDispatchCompute", "glMemoryBarrier", "glDrawArrays"]
        assert events[1][1][0] & gl.GL_TEXTURE_FETCH_BARRIER_BIT
    finally:
        monkeypatch.undo()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glDeleteTextures([scene, velocity])
        blur.release()
        resources.release_resources()


def test_a_dispatch_names_its_groups_and_barrier(monkeypatch):
    monkeypatch.setattr(compute_module.gl, "glDispatchCompute", lambda *_args: pytest.fail("dispatched"))
    with pytest.raises(ValueError, match="empty"):
        dispatch((0, 1, 1), gl.GL_TEXTURE_FETCH_BARRIER_BIT)
    with pytest.raises(ValueError, match="barrier"):
        dispatch((1, 1, 1), 0)


@pytest.mark.parametrize("inherited", (True, False), ids=("bound", "unbound"))
def test_image_units_are_handed_back_even_after_a_failure(capture, inherited):
    sentinel = _texture(8, 8, gl.GL_RGBA8)
    target = _texture(4, 4, gl.GL_RG16F)
    try:
        if inherited:
            gl.glBindImageTexture(0, sentinel, 0, gl.GL_FALSE, 0, gl.GL_READ_ONLY, gl.GL_RGBA8)
        with pytest.raises(RuntimeError, match="inside"):
            with bound_image(0, target, gl.GL_WRITE_ONLY, gl.GL_RG16F):
                assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, 0) == target
                raise RuntimeError("inside")
        assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, 0) == (sentinel if inherited else 0)
        if inherited:
            assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_ACCESS, 0) == gl.GL_READ_ONLY
            assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_FORMAT, 0) == gl.GL_RGBA8
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glBindImageTexture(0, 0, 0, gl.GL_FALSE, 0, gl.GL_READ_ONLY, gl.GL_R8)
        gl.glDeleteTextures([sentinel, target])


def test_a_motion_blurred_run_hands_back_image_unit_zero(qt_app):
    capture = TransitionCapture(256, 144)
    sentinel = _texture(8, 8, gl.GL_RGBA8)
    try:
        gl.glBindImageTexture(0, sentinel, 0, gl.GL_FALSE, 0, gl.GL_READ_WRITE, gl.GL_RGBA8)
        run = capture.run("exploding_tiles", parameters={"motion_blur": True}, duration_ms=3000)
        capture.render(run, 0.4)
        assert capture.host._implementations["exploding_tiles"]._target._motion.has_resources
        assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, 0) == sentinel
        assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_ACCESS, 0) == gl.GL_READ_WRITE
    finally:
        gl.glBindImageTexture(0, 0, 0, gl.GL_FALSE, 0, gl.GL_READ_ONLY, gl.GL_R8)
        gl.glDeleteTextures([sentinel])
        capture.close()


_CASES = (("exploding_tiles", None), ("glass_shatter", "left"), ("crumble", None), ("pixel_accretion", "left"),
          ("block_spins", "left"))


@pytest.mark.parametrize("effect,direction", _CASES)
def test_without_motion_blur_nothing_compiles_or_dispatches_compute(qt_app, monkeypatch, effect, direction):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("dormant compute touched GL")

    monkeypatch.setattr(gl, "glDispatchCompute", forbidden)
    monkeypatch.setattr(gl, "glBindImageTexture", forbidden)
    monkeypatch.setattr(gl_resources, "compile_compute_program", forbidden)
    import rendering.quick.scene3d.resources as scene_resources
    monkeypatch.setattr(scene_resources, "compile_compute_program", forbidden)
    capture = TransitionCapture(256, 144)
    try:
        run = capture.run(effect, direction=direction, parameters={"motion_trails": True}, duration_ms=3000)
        assert not run.request.parameter_dict().get("motion_blur")
        while not capture.host.warm_step(run.request.transition_id, run.request.parameter_dict(), (256, 144)):
            pass
        for progress in (0.0, 0.2, 0.5, 0.8, 1.0):
            capture.render(run, progress)
        renderer = capture.host._implementations[run.request.transition_id]
        assert not renderer._target._motion.has_resources
        resources = getattr(renderer, "_resources", None) or renderer._target_resources
        assert not resources.has_program("motion_tile_max")
    finally:
        capture.close()


def test_tile_capacity_is_fixed_and_loud():
    assert motion_blur_tile(MOTION_BLUR_MAX_TILE * 40) == MOTION_BLUR_MAX_TILE
    with pytest.raises(ValueError, match="capacity"):
        motion_blur_tile((MOTION_BLUR_MAX_TILE + 1) * 40)


def test_release_returns_to_zero_and_rebuilds(capture):
    resources = MeshResources("rebuild test")
    blur = MotionBlur("rebuild test")
    field = _fields(97, 61)["random"]
    scene, velocity = _texture(97, 61, gl.GL_RGBA8), _texture(97, 61, gl.GL_RG16F, field)
    try:
        blur.apply(scene, velocity, (97, 61), resources, capture.vao)
        first = blur._passes[0][0]
        program = resources.compute_program("motion_tile_max", "unused: already compiled")
        blur.release()
        resources.release_resources()
        assert not blur.has_resources and not resources.has_resources
        assert not gl.glIsTexture(first) and not gl.glIsProgram(program)
        blur.apply(scene, velocity, (97, 61), resources, capture.vao)
        tiles, _fbo, tile_w, tile_h = blur._passes[0]
        assert np.array_equal(_read_rg(tiles, tile_w, tile_h), _reference_tile_max(field, motion_blur_tile(61)))
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glDeleteTextures([scene, velocity])
        blur.release()
        resources.release_resources()


def test_a_compute_program_that_fails_to_compile_or_link_leaves_nothing(capture, monkeypatch):
    shaders, programs = [], []
    real_shader, real_program = gl.glCreateShader, gl.glCreateProgram
    monkeypatch.setattr(gl, "glCreateShader", lambda kind: shaders.append(real_shader(kind)) or shaders[-1])
    monkeypatch.setattr(gl, "glCreateProgram", lambda: programs.append(real_program()) or programs[-1])
    resources = MeshResources("compile failure test")
    with pytest.raises(RuntimeError, match="compute shader compile failed"):
        resources.compute_program("broken", "#version 460 core\nlayout(local_size_x = 1) in;\nvoid main() { nope; }\n")
    # Compiles, but uses more shared memory than any driver allows: the link fails after a program exists.
    with pytest.raises(RuntimeError, match="link failed|compile failed"):
        resources.compute_program("too_big", "#version 460 core\nlayout(local_size_x = 1) in;\n"
                                             "shared vec4 huge[1048576];\nvoid main() { huge[0] = vec4(1.0); }\n")
    assert not resources.has_resources
    monkeypatch.undo()
    assert shaders and not any(gl.glIsShader(shader) for shader in shaders)
    assert not any(gl.glIsProgram(program) for program in programs)
