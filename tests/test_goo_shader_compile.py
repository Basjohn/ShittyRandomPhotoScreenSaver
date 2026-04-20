from __future__ import annotations

import pytest
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat


@pytest.mark.qt
def test_goo_fragment_shader_compiles(qt_app):
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(3, 3)
    fmt.setSwapBehavior(QSurfaceFormat.SingleBuffer)

    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 3.3 context unavailable on this runner")

    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        pytest.skip("Failed to create offscreen surface for goo shader compile test")
    if not context.makeCurrent(surface):
        pytest.skip("Unable to make OpenGL context current")

    try:
        from OpenGL import GL as gl
    except Exception as exc:  # pragma: no cover - infrastructure guard
        context.doneCurrent()
        surface.destroy()
        pytest.skip(f"PyOpenGL unavailable: {exc}")

    from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader

    source = load_fragment_shader("goo")
    assert source, "goo shader source missing"

    vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
    fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    prog = gl.glCreateProgram()
    try:
        gl.glShaderSource(vs, SHARED_VERTEX_SHADER)
        gl.glCompileShader(vs)
        assert gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS) == gl.GL_TRUE

        gl.glShaderSource(fs, source)
        gl.glCompileShader(fs)
        fs_status = gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS)
        fs_log = gl.glGetShaderInfoLog(fs)
        if isinstance(fs_log, bytes):
            fs_log = fs_log.decode("utf-8", errors="ignore")
        assert fs_status == gl.GL_TRUE, f"goo.frag failed to compile: {fs_log.strip()}"

        gl.glAttachShader(prog, vs)
        gl.glAttachShader(prog, fs)
        gl.glLinkProgram(prog)
        assert gl.glGetProgramiv(prog, gl.GL_LINK_STATUS) == gl.GL_TRUE
    finally:
        gl.glDeleteProgram(prog)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        context.doneCurrent()
        if hasattr(surface, "destroy"):
            surface.destroy()


def test_goo_shader_avoids_block_noise_pattern():
    from widgets.spotify_visualizer.shaders import load_fragment_shader

    source = load_fragment_shader("goo")
    assert source, "goo shader source missing"
    lower = source.lower()
    assert "fract(sin(dot" not in lower
    assert "floor(sp" not in lower
    assert "u_goo_sources" in source

