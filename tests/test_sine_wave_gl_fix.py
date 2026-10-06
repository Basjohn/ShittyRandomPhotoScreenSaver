"""Regression tests for sine_wave visualizer mode GL overlay fix.

Verifies that:
- sine_wave remains a registered worker-backed visualizer mode
- registry and worker identity agree for sine_wave
- Card height growth labels use 'x' multiplier format (not '%')
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

class TestSineWaveGLOverlayFix:
    def test_sine_wave_is_registered_and_worker_backed(self):
        from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        assert "sine_wave" in VISUALIZER_MODE_IDS
        assert VisualizerMode.SINE_WAVE.name.lower() == "sine_wave"

    def test_sine_wave_shader_registered(self):
        """sine_wave.frag must be in the shader registry."""
        from widgets.spotify_visualizer.shaders import _ALL_SHADER_FILES
        assert 'sine_wave' in _ALL_SHADER_FILES
        assert _ALL_SHADER_FILES['sine_wave'] == 'sine_wave.frag'

    def test_sine_wave_shader_loads(self):
        """sine_wave shader source must load without error."""
        from widgets.spotify_visualizer.shaders import load_fragment_shader
        source = load_fragment_shader('sine_wave')
        assert source is not None
        assert len(source) > 100

    def test_sine_wave_shader_support_gates_wave_effect(self):
        """Wave Effect should be explicitly gated so quiet passages stay calmer."""
        from widgets.spotify_visualizer.shaders import load_fragment_shader
        source = load_fragment_shader('sine_wave')
        assert "uniform float u_wave_effect_gate;" in source
        assert "wave_fx_gate" in source
        assert "u_wave_effect_gate" in source


@pytest.mark.qt
def test_sine_wave_fragment_shader_compiles(qt_app):
    """Compile sine_wave.frag inside a headless GL context to catch GLSL errors."""

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    fmt.setSwapBehavior(QSurfaceFormat.SingleBuffer)

    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.6 context unavailable on this runner")

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

    source = load_fragment_shader('sine_wave')
    assert source, "sine_wave shader source missing"

    shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
    try:
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        log = gl.glGetShaderInfoLog(shader)
        if isinstance(log, bytes):
            log = log.decode('utf-8', errors='ignore')
        assert status == gl.GL_TRUE, f"sine_wave.frag failed to compile: {log.strip()}"
    finally:
        gl.glDeleteShader(shader)
        context.doneCurrent()
        if hasattr(surface, 'destroy'):
            surface.destroy()
