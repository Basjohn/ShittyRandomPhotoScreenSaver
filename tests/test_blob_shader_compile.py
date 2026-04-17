from __future__ import annotations

import pytest
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat


@pytest.mark.qt
def test_blob_fragment_shader_compiles(qt_app):
    """Compile blob.frag inside a headless GL context to catch fallback-causing GLSL errors."""

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

    source = load_fragment_shader("blob")
    assert source, "blob shader source missing"

    shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    try:
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        log = gl.glGetShaderInfoLog(shader)
        if isinstance(log, bytes):
            log = log.decode("utf-8", errors="ignore")
        assert status == gl.GL_TRUE, f"blob.frag failed to compile: {log.strip()}"
    finally:
        gl.glDeleteShader(shader)
        context.doneCurrent()
        if hasattr(surface, "destroy"):
            surface.destroy()


@pytest.mark.qt
def test_blob_shader_program_links_with_shared_vertex_shader(qt_app):
    """Link the real Blob GL program shape used by the overlay to catch fallback-causing link errors."""

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
        pytest.skip("Failed to create an offscreen surface for shader link test")

    if not context.makeCurrent(surface):
        pytest.skip("Unable to make OpenGL context current")

    try:
        from OpenGL import GL as gl
    except Exception as exc:  # pragma: no cover - infrastructure guard
        context.doneCurrent()
        surface.destroy()
        pytest.skip(f"PyOpenGL unavailable: {exc}")

    from widgets.spotify_visualizer.shaders import SHARED_VERTEX_SHADER, load_fragment_shader

    vertex_source = SHARED_VERTEX_SHADER
    fragment_source = load_fragment_shader("blob")
    assert fragment_source, "blob shader source missing"

    vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
    fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    prog = gl.glCreateProgram()
    try:
        gl.glShaderSource(vs, vertex_source)
        gl.glCompileShader(vs)
        vs_status = gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS)
        vs_log = gl.glGetShaderInfoLog(vs)
        if isinstance(vs_log, bytes):
            vs_log = vs_log.decode("utf-8", errors="ignore")
        assert vs_status == gl.GL_TRUE, f"shared vertex shader failed to compile: {vs_log.strip()}"

        gl.glShaderSource(fs, fragment_source)
        gl.glCompileShader(fs)
        fs_status = gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS)
        fs_log = gl.glGetShaderInfoLog(fs)
        if isinstance(fs_log, bytes):
            fs_log = fs_log.decode("utf-8", errors="ignore")
        assert fs_status == gl.GL_TRUE, f"blob.frag failed to compile: {fs_log.strip()}"

        gl.glAttachShader(prog, vs)
        gl.glAttachShader(prog, fs)
        gl.glLinkProgram(prog)
        link_status = gl.glGetProgramiv(prog, gl.GL_LINK_STATUS)
        link_log = gl.glGetProgramInfoLog(prog)
        if isinstance(link_log, bytes):
            link_log = link_log.decode("utf-8", errors="ignore")
        assert link_status == gl.GL_TRUE, f"Blob shader program failed to link: {link_log.strip()}"
    finally:
        gl.glDeleteProgram(prog)
        gl.glDeleteShader(vs)
        gl.glDeleteShader(fs)
        context.doneCurrent()
        if hasattr(surface, "destroy"):
            surface.destroy()
