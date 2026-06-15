from __future__ import annotations

import pytest
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat


@pytest.mark.qt
def test_bubble_fragment_shader_compiles(qt_app):
    """Compile bubble.frag in a real GL context to catch shader regressions."""

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
        pytest.skip("Failed to create an offscreen surface for shader compile test")

    if not context.makeCurrent(surface):
        pytest.skip("Unable to make OpenGL context current")

    try:
        from OpenGL import GL as gl
    except Exception as exc:  # pragma: no cover - infrastructure guard
        context.doneCurrent()
        surface.destroy()
        pytest.skip(f"PyOpenGL unavailable: {exc}")

    from widgets.spotify_visualizer.shaders import load_fragment_shader

    source = load_fragment_shader("bubble")
    assert source, "bubble shader source missing"

    shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    try:
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        log = gl.glGetShaderInfoLog(shader)
        if isinstance(log, bytes):
            log = log.decode("utf-8", errors="ignore")
        assert status == gl.GL_TRUE, f"bubble.frag failed to compile: {log.strip()}"
    finally:
        gl.glDeleteShader(shader)
        context.doneCurrent()
        if hasattr(surface, "destroy"):
            surface.destroy()
