"""Real-GL coverage checks for tiny-scale Qt Quick line visualizers."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.render_state import (
    DevCurveFrame,
    OscilloscopeFrame,
    SineFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


_LOGICAL_SIZE = (1368.0, 268.0)
_DPR = 1.5
_PHYSICAL_SIZE = tuple(round(value * _DPR) for value in _LOGICAL_SIZE)


def _presentation(mode_id: str, *, fractional_x: float):
    """The rejected 8240x1579 source extent at its observed 0.17x scale."""
    base = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode_id),
        display_size=_LOGICAL_SIZE,
        viewport_extent=(8240.0, 1579.0),
        uniform_visual_scale=0.17,
        shadow_enabled=False,
    )
    return replace(
        base,
        outer_rect=(0.0, 0.0, *_LOGICAL_SIZE),
        content_rect=(fractional_x, 0.0, _LOGICAL_SIZE[0] - fractional_x, _LOGICAL_SIZE[1]),
        dpr=_DPR,
        uniform_visual_scale=0.17,
    )


def _logical(mode_id: str) -> VisualizerLogicalFrame:
    waveform = tuple(math.sin(index * math.tau * 3.0 / 64.0) for index in range(64))
    common = VisualizerCommonState(
        bars=(),
        bar_count=0,
        waveform=waveform,
        waveform_count=len(waveform),
        energy=VisualizerEnergyState(bass=0.8, mid=0.6, high=0.4, overall=0.8),
    )
    if mode_id == "sine_wave":
        state = SineFrame(
            animation_time=0.37,
            parameters=freeze_render_fields({
                "sine_density": 3.0,
                "sine_card_adaptation": 0.8,
                "sine_line_color": (240, 250, 255, 255),
                "sine_glow_enabled": False,
            }),
        )
    elif mode_id == "oscilloscope":
        state = OscilloscopeFrame(
            animation_time=0.37,
            parameters=freeze_render_fields({
                "osc_smoothing": 0.0,
                "osc_line_amplitude": 3.0,
                "osc_line_color": (240, 250, 255, 255),
                "osc_glow_enabled": False,
            }),
        )
    elif mode_id == "devcurve":
        curve = tuple(0.50 + 0.32 * math.sin(index * math.tau * 3.0 / 95.0) for index in range(96))
        state = DevCurveFrame(
            curves=tuple((name, curve) for name in ("bass", "vocals", "mids", "transients")),
            draw_order=("bass", "vocals", "mids", "transients"),
            parameters=freeze_render_fields({
                "devcurve_sample_count": 96,
                **{
                    f"devcurve_layer_{name}_{field}": value
                    for name in ("bass", "vocals", "mids", "transients")
                    for field, value in (
                        ("enabled", name == "bass"),
                        ("color", (80, 180, 255, 0)),
                        ("outline_color", (240, 250, 255, 255)),
                        ("outline_width", 0.006),
                        ("alpha", 0.0),
                    )
                },
            }),
        )
    else:  # pragma: no cover - keeps the parametrization honest.
        raise AssertionError(mode_id)
    return VisualizerLogicalFrame(
        runtime_generation=1,
        engine_generation=1,
        activation_id=1,
        source_generation=1,
        source_activation_id=1,
        mode_id=mode_id,
        playing=True,
        logical_timestamp=0.37,
        source_timestamp=0.37,
        changed=True,
        present_frame=True,
        mode_reveal_ready=True,
        common=common,
        mode_state=state,
    )


def _snapshot(mode_id: str, *, fractional_x: float):
    return compose_visualizer_render_snapshot(
        _logical(mode_id), _presentation(mode_id, fractional_x=fractional_x), logical_revision=1
    )


@pytest.mark.qt
@pytest.mark.parametrize("mode_id", ("sine_wave", "oscilloscope", "devcurve"))
def test_real_gl_tiny_scale_steep_lines_keep_fractional_translation_coverage(qt_app, mode_id: str):
    """Coverage stays present and smooth at DPR 1.5 without retuning geometry."""
    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.1 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("offscreen OpenGL context unavailable")

    width, height = _PHYSICAL_SIZE
    fbo = color = 0
    host = QuickVisualizerRenderHost()
    try:
        color = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
        fbo = gl.glGenFramebuffers(1)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, color, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        matrix = (2 / _LOGICAL_SIZE[0], 0, 0, 0, 0, 2 / _LOGICAL_SIZE[1], 0, 0, 0, 0, 1, 0, -1, -1, 0, 1)

        def render(fractional_x: float) -> bytes:
            gl.glViewport(0, 0, width, height)
            gl.glClearColor(0, 0, 0, 0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            assert host.render(
                snapshot=_snapshot(mode_id, fractional_x=fractional_x),
                viewport=(0, 0, width, height),
                logical_size=_LOGICAL_SIZE,
                matrix_values=matrix,
            ) == mode_id
            return bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))

        aligned = render(0.0)
        translated = render(0.37)
        aligned_alpha = aligned[3::4]
        translated_alpha = translated[3::4]
        aligned_energy = sum(aligned_alpha)
        translated_energy = sum(translated_alpha)
        assert aligned_energy > 18_000
        assert translated_energy > 18_000
        assert translated_energy / aligned_energy == pytest.approx(1.0, rel=0.22)
        # A device-pixel coverage ramp must retain fractional alpha, rather
        # than collapsing the tiny authored stroke to binary sample hits.
        assert any(8 < alpha < 247 for alpha in translated_alpha)
    finally:
        host.release_resources()
        if fbo:
            gl.glDeleteFramebuffers(1, [fbo])
        if color:
            gl.glDeleteTextures([color])
        context.doneCurrent()
        surface.destroy()


def test_line_shaders_keep_style_scale_separate_from_derivative_coverage() -> None:
    root = __import__("pathlib").Path(__file__).resolve().parent.parent
    sine = (root / "widgets/spotify_visualizer/shaders/sine_wave.frag").read_text(encoding="utf-8")
    osc = (root / "widgets/spotify_visualizer/shaders/oscilloscope.frag").read_text(encoding="utf-8")
    devcurve = (root / "widgets/spotify_visualizer/shaders/devcurve.frag").read_text(encoding="utf-8")

    for source in (sine, osc):
        assert "float line_footprint_px = max(fwidth(dist_px), 1e-4);" in source
        assert "line_width + line_footprint_px" in source
        assert "authored_visual_scale()" in source
    assert "float edgeAA = max(aa, fwidth(y - yCurve));" in devcurve
    assert "float fgAA = max(aa, fwidth(uv.y - yFg));" in devcurve
