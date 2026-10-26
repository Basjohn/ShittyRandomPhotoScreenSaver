"""Real GL lifecycle checks for the shared diagnostic/lab target."""
import pytest
from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext

from tools.labs.render_target import OffscreenRenderTarget

pytestmark = pytest.mark.qt


def test_lab_target_reads_resizes_and_retires_its_own_resources(qt_app):
    target = OffscreenRenderTarget(32, 24)
    try:
        target.bind(clear=(1., 0., 0., 1.))
        assert tuple(target.read_rgba()[12, 16]) == (255, 0, 0, 255)
        assert gl.glIsVertexArray(target.vao)
        old_texture = target.color_texture
        target.resize(48, 16)
        assert not gl.glIsTexture(old_texture)
        target.bind(clear=(0., 0., 1., 1.))
        pixels = target.read_rgba()
        assert pixels.shape == (16, 48, 4)
        assert tuple(pixels[8, 24]) == (0, 0, 255, 255)
    finally:
        target.close()
    target.close()
    assert target.closed
    with pytest.raises(RuntimeError, match="closed"):
        target.bind()


def test_retiring_one_target_restores_the_other_current_context(qt_app):
    first = OffscreenRenderTarget(16, 16)
    second = OffscreenRenderTarget(20, 20)
    try:
        second.bind(clear=(0., 1., 0., 1.))
        first.close()
        assert QOpenGLContext.currentContext() == second.context
        assert tuple(second.read_rgba()[10, 10]) == (0, 255, 0, 255)
    finally:
        first.close()
        second.close()


def test_failed_resize_keeps_the_last_admitted_target(qt_app, monkeypatch):
    target = OffscreenRenderTarget(24, 16)
    try:
        old = target.fbo, target.depth, target.color_texture
        with monkeypatch.context() as patch:
            patch.setattr(gl, "glCheckFramebufferStatus", lambda *_: gl.GL_FRAMEBUFFER_UNSUPPORTED)
            with pytest.raises(RuntimeError, match="incomplete"):
                target.resize(48, 32)
        assert (target.fbo, target.depth, target.color_texture) == old
        assert (target.width, target.height) == (24, 16)
        target.bind(clear=(1., 1., 0., 1.))
        assert tuple(target.read_rgba()[8, 12]) == (255, 255, 0, 255)
    finally:
        target.close()


def test_partial_capture_admission_restores_the_callers_context(qt_app):
    from tools.transition_contact_sheet import TransitionCapture

    previous = OffscreenRenderTarget(16, 16)
    try:
        with pytest.raises(AttributeError, match="convert"):
            TransitionCapture(16, 16, source=object())
        assert QOpenGLContext.currentContext() == previous.context
    finally:
        previous.close()


def test_invalid_target_size_is_rejected_before_allocation():
    with pytest.raises(ValueError, match="positive integers"):
        OffscreenRenderTarget(0, 20)


def test_failed_retirement_restores_context_and_can_be_retried(qt_app, monkeypatch):
    first = OffscreenRenderTarget(16, 16)
    first.vao
    second = OffscreenRenderTarget(16, 16)
    try:
        with monkeypatch.context() as patch:
            def fail_release():
                raise RuntimeError("injected retirement failure")
            patch.setattr(first._mesh, "release_resources", fail_release)
            with pytest.raises(RuntimeError, match="injected retirement"):
                first.close()
        assert not first.closed
        assert QOpenGLContext.currentContext() == second.context
        first.close()
        assert QOpenGLContext.currentContext() == second.context
    finally:
        first.close()
        second.close()


def test_transition_render_and_failed_benchmark_keep_contexts_and_queries_owned(qt_app, monkeypatch):
    from PIL import Image
    from tools.transition_contact_sheet import TransitionCapture

    first = TransitionCapture(24, 16, source=Image.new("RGBA", (24,16), "red"))
    second = OffscreenRenderTarget(24, 16)
    query_ids = []
    try:
        run = first.production_run("slide")
        image, _ = first.render(run, 0.)
        assert image.getpixel((12,8)) == (255, 0, 0, 255)
        assert QOpenGLContext.currentContext() == second.context
        original_gen = gl.glGenQueries
        def gen_queries(*args):
            result = original_gen(*args)
            query_ids.extend(int(value) for value in result)
            return result
        def fail_draw(*_args):
            raise RuntimeError("injected draw failure")
        with monkeypatch.context() as patch:
            patch.setattr(gl, "glGenQueries", gen_queries)
            patch.setattr(first.host, "render", fail_draw)
            with pytest.raises(RuntimeError, match="injected draw"):
                first.benchmark(run)
        assert QOpenGLContext.currentContext() == second.context
        with first._target.current():
            assert int(gl.glGetQueryiv(gl.GL_TIME_ELAPSED, gl.GL_CURRENT_QUERY)) == 0
            assert query_ids and not any(gl.glIsQuery(query) for query in query_ids)
    finally:
        first.close()
        second.close()
