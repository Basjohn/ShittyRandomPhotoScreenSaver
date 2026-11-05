"""The Waveform scene owns the GL state of its frame: a steady frame reads (almost) nothing back.

Every GL state read on the render thread is a round trip to the driver thread; on a loaded machine each one waits for a
time slice and leaves the GPU idle. A frame of the scene used to make ~170 of them (uniform locations by name, the
OIT/stream/image-unit/ribbon save-and-restore fences). These tests keep the owned path query-free and the opt-in
``restore=False`` contracts of the shared primitives exact.
"""
from __future__ import annotations

import pytest

from tests.test_waveform_ribbon_mode import frame_for

# What a steady frame may still read: the scene target's fence of the caller's framebuffer/scissor/blend at begin and
# the planar reflection's fence of the caller's target (both hand the caller's state back), and the scissor check.
STEADY_QUERY_BUDGET = 24


def _count_queries(monkeypatch):
    from OpenGL import GL
    from rendering.quick import gl_query
    counts: dict[str, int] = {}

    def counting(owner, name):
        original = getattr(owner, name)

        def run(*a, **k):
            counts[name] = counts.get(name, 0) + 1
            return original(*a, **k)
        monkeypatch.setattr(owner, name, run)

    for name in ("glGetUniformLocation", "glGetIntegerv", "glGetBooleanv", "glGetFloatv", "glIsEnabled",
                 "glIsEnabledi", "glGetIntegeri_v", "glGetBooleani_v"):
        counting(GL, name)
    for name in ("get_int", "get_ints", "get_bool", "get_bools", "get_float", "get_floats", "is_enabled",
                 "get_indexed_int", "get_indexed_bools", "get_indexed_int64"):
        counting(gl_query, name)
    return counts


@pytest.mark.qt
def test_steady_scene_frame_looks_up_no_uniform_and_reads_little_state(qt_app, monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from tools.labs.render_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target = OffscreenRenderTarget(320, 240)
    renderer = QuickWaveformRibbonRenderer()
    try:
        frame = frame_for(target)
        state = frame.snapshot.logical.mode_state
        assert state.scene.fog is not None, 'the counted frame must include the mist volume passes'
        for _ in range(2):                         # first frames compile programs and look locations up
            target.bind(); renderer.render(frame)
        counts = _count_queries(monkeypatch)
        target.bind(); renderer.render(frame)
        assert counts.get("glGetUniformLocation", 0) == 0, counts
        assert sum(counts.values()) <= STEADY_QUERY_BUDGET, counts
    finally:
        monkeypatch.undo()
        renderer.release_resources(); target.close()


@pytest.mark.qt
def test_owned_storage_and_image_bindings_are_left_unbound_without_reads(qt_app, monkeypatch):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick import gl_query
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.compute import bound_image
    from rendering.quick.scene3d.stream import StreamRing
    target = OffscreenRenderTarget(8, 8)
    ring = StreamRing('owned test ring', slots=3, slot_bytes=4096, hold_bytes=4096)
    texture = 0
    try:
        with target.current():
            name = (gl.GLuint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name); texture = int(name[0])
            gl.glTextureStorage2D(texture, 1, gl.GL_RGBA16F, 4, 4)
            ring.warm()
            counts = _count_queries(monkeypatch)
            with ring.bound(gl.GL_SHADER_STORAGE_BUFFER, 1, bytes(64), restore=False):
                with bound_image(2, texture, gl.GL_WRITE_ONLY, gl.GL_RGBA16F, restore=False):
                    pass
            reads = sum(counts.values())
            monkeypatch.undo()
            assert reads == 0, counts
            assert gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, 1) == 0
            assert gl_query.get_indexed_int(gl.GL_IMAGE_BINDING_NAME, 2) == 0
    finally:
        with target.current():
            ring.release()
            if texture:
                gl.glDeleteTextures(1, [texture])
        target.close()


@pytest.mark.qt
def test_owned_transparent_writes_leave_the_documented_state(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick import gl_query
    from tools.labs.render_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target = OffscreenRenderTarget(64, 48)
    renderer = QuickWaveformRibbonRenderer()
    try:
        frame = frame_for(target)
        target.bind()
        scene = renderer._scene
        scene.admit_preparation()
        with scene.scene.scope(frame, 4, scene.resources, overlay=1., bloom=.2, oit=True, hdr=1.):
            with scene.scene.transparent_writes(frame, scene.resources, restore=False):
                pass
            assert not gl.glIsEnabledi(gl.GL_BLEND, 0) and not gl.glIsEnabledi(gl.GL_BLEND, 1)
            assert gl_query.is_enabled(gl.GL_DEPTH_TEST) and not gl_query.get_bool(gl.GL_DEPTH_WRITEMASK)
            assert gl_query.get_indexed_bools(gl.GL_COLOR_WRITEMASK, 0) == [True] * 4
            assert gl_query.get_indexed_bools(gl.GL_COLOR_WRITEMASK, 1) == [False] * 4   # emission: own scope only
    finally:
        renderer.release_resources(); target.close()
