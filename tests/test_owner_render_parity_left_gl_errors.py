"""N5.6: the scene mirror's read takes the GL errors a drawn frame left pending before its own calls and counts them
(``SceneMirror._read``, ``left_gl_errors``), so a frame's ignored error (Qt's sampler state on a multisample texture)
is reported, never raised by the read's first call."""
from __future__ import annotations

import pytest


class _GL:
    """PyOpenGL's error check in miniature: a call raises while an error is pending."""
    GL_NO_ERROR = 0
    GL_READ_FRAMEBUFFER_BINDING = 0x8CAA
    GL_READ_FRAMEBUFFER = 0x8CA8
    GL_COLOR_ATTACHMENT0 = 0x8CE0
    GL_TEXTURE_2D = 0x0DE1
    GL_FRAMEBUFFER_COMPLETE = 0x8CD5
    GL_PACK_ALIGNMENT = 0x0D05
    GL_RGBA = 0x1908
    GL_UNSIGNED_BYTE = 0x1401

    def __init__(self, pending):
        self.pending = list(pending)

    def glGetError(self):
        return self.pending.pop(0) if self.pending else 0

    def _checked(self):
        if self.pending:
            raise RuntimeError(f"GLError {self.pending[0]:#x}")

    def glGetIntegerv(self, _name):
        self._checked()
        return 0

    def glGenFramebuffers(self, _n):
        return 1

    def glBindFramebuffer(self, *_):
        self._checked()

    def glFramebufferTexture2D(self, *_):
        pass

    def glCheckFramebufferStatus(self, _target):
        return self.GL_FRAMEBUFFER_COMPLETE

    def glPixelStorei(self, *_):
        pass

    def glReadPixels(self, _x, _y, width, height, *_):
        return bytes(width * height * 4)


class _Host:
    def __init__(self, gl):
        self._gl = gl
        self.texture = 1
        self.pixels = (4, 4)

    def _current(self):
        pass


def _mirror(pending):
    from tools.visualizer_replay.owner_render_parity import SceneMirror

    mirror = SceneMirror.__new__(SceneMirror)
    mirror.host = _Host(_GL(pending))
    mirror._fbo = 0
    mirror.left_gl_errors = {}
    return mirror


def test_the_read_counts_the_errors_a_frame_left_and_reads_the_frame():
    mirror = _mirror([0x500, 0x500])
    pixels = mirror._read((0, 0, 2, 2))
    assert pixels.shape == (2, 2, 4)
    assert mirror.left_gl_errors == {0x500: 2}
    assert mirror.host._gl.pending == []
    # Control: the same pending error raises at the read's first call when nothing takes it first.
    with pytest.raises(RuntimeError, match="0x500"):
        _GL([0x500]).glGetIntegerv(_GL.GL_READ_FRAMEBUFFER_BINDING)


def test_a_clean_frame_leaves_nothing_counted():
    mirror = _mirror([])
    mirror._read((0, 0, 2, 2))
    assert mirror.left_gl_errors == {}
