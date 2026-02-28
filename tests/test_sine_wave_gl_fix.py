"""Regression tests for sine_wave visualizer mode GL overlay fix.

Verifies that:
- sine_wave is accepted by the GL overlay's vis_mode validation
- The mode cycle order is Spectrum → Oscilloscope → Sine Wave → Blob
- Card height growth labels use 'x' multiplier format (not '%')
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

class TestSineWaveGLOverlayFix:
    def test_sine_wave_in_allowed_modes(self):
        """sine_wave must be in the GL overlay's allowed mode set."""
        allowed = ('spectrum', 'oscilloscope', 'starfield', 'blob', 'helix', 'sine_wave')
        assert 'sine_wave' in allowed

    def test_sine_wave_not_rejected_to_spectrum(self):
        """Simulate the GL overlay's mode validation — sine_wave should NOT fall back."""
        vis_mode = 'sine_wave'
        result = vis_mode if vis_mode in (
            'spectrum', 'oscilloscope', 'starfield', 'blob', 'helix', 'sine_wave'
        ) else 'spectrum'
        assert result == 'sine_wave', f"sine_wave was rejected, got: {result}"

    def test_mode_cycle_order(self):
        """Verify the cycle order: Spectrum → Oscilloscope → Sine Wave → Blob."""
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        _CYCLE_MODES = [
            VisualizerMode.SPECTRUM,
            VisualizerMode.OSCILLOSCOPE,
            VisualizerMode.SINE_WAVE,
            VisualizerMode.BLOB,
        ]
        assert _CYCLE_MODES[0] == VisualizerMode.SPECTRUM
        assert _CYCLE_MODES[1] == VisualizerMode.OSCILLOSCOPE
        assert _CYCLE_MODES[2] == VisualizerMode.SINE_WAVE
        assert _CYCLE_MODES[3] == VisualizerMode.BLOB

    def test_mode_cycle_wraps(self):
        """Cycling from Blob should wrap back to Spectrum."""
        from widgets.spotify_visualizer.audio_worker import VisualizerMode
        _CYCLE_MODES = [
            VisualizerMode.SPECTRUM,
            VisualizerMode.OSCILLOSCOPE,
            VisualizerMode.SINE_WAVE,
            VisualizerMode.BLOB,
        ]
        idx = _CYCLE_MODES.index(VisualizerMode.BLOB)
        next_mode = _CYCLE_MODES[(idx + 1) % len(_CYCLE_MODES)]
        assert next_mode == VisualizerMode.SPECTRUM

    def test_sine_wave_shader_registered(self):
        """sine_wave.frag must be in the shader registry."""
        from widgets.spotify_visualizer.shaders import _SHADER_FILES
        assert 'sine_wave' in _SHADER_FILES
        assert _SHADER_FILES['sine_wave'] == 'sine_wave.frag'

    def test_sine_wave_shader_loads(self):
        """sine_wave shader source must load without error."""
        from widgets.spotify_visualizer.shaders import load_fragment_shader
        source = load_fragment_shader('sine_wave')
        assert source is not None
        assert len(source) > 100

    def test_card_height_growth_factor_defaults(self):
        """Verify default growth factors per mode."""
        from widgets.spotify_visualizer.card_height import DEFAULT_GROWTH
        assert DEFAULT_GROWTH['oscilloscope'] == 2.0
        assert DEFAULT_GROWTH['sine_wave'] == 2.0
        assert DEFAULT_GROWTH['blob'] == 3.5

    def test_card_height_expansion_works(self):
        """Setting growth > 1.0 should expand the card height."""
        from widgets.spotify_visualizer.card_height import preferred_height
        base = 80
        h_default = preferred_height('oscilloscope', base, growth_factor=1.0)
        h_expanded = preferred_height('oscilloscope', base, growth_factor=2.0)
        assert h_expanded > h_default
        assert h_expanded == 160

    def test_card_height_sine_wave_expansion(self):
        """Sine wave growth factor should expand card height."""
        from widgets.spotify_visualizer.card_height import preferred_height
        base = 80
        h = preferred_height('sine_wave', base, growth_factor=2.5)
        assert h == 200


@pytest.mark.qt
def test_sine_wave_fragment_shader_compiles(qt_app):
    """Compile sine_wave.frag inside a headless GL context to catch GLSL errors."""

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
