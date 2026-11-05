"""Real-GL parity checks for line-visualizer glow footprint coordinates."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from struct import pack

import pytest

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tests._visualizer_presentation import resolve_presentation as resolve_visualizer_presentation
from widgets.spotify_visualizer.render_state import (
    OscilloscopeFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


_BACKGROUND = (6, 11, 19)
_CANONICAL_SIZE = (420.0, 280.0)


def _osc_frame(*, with_glow: bool) -> OscilloscopeFrame:
    points = []
    for index in range(128):
        x = -1.0 + 2.0 * index / 127.0
        points.extend((x, 0.72 * math.sin(index * math.tau * 3.0 / 127.0)))
    packed = pack("<" + "f" * len(points), *points)
    return OscilloscopeFrame(
        points=packed,
        trace_alphas=(1.0,),
        flare=0.2,
        drive=0.8,
        tone=0.65,
        parameters=freeze_render_fields({
            "osc_display": "Trace",
            "osc_beam_color": (120, 255, 170, 255),
            "osc_beam_glow_color": (40, 255, 120, 255),
            "osc_beam_width": 1.6,
            "osc_glow": 0.65 if with_glow else 0.0,
            "osc_afterglow": 0.45,
            "osc_analog": 0.55,
            "osc_spectral": 0.0,
            "osc_flare": 0.6,
            "osc_pulse": 0.6,
            "osc_graticule": "Off",
            "osc_graticule_color": (120, 255, 170, 46),
        }),
    )


def _logical(mode_id: str) -> VisualizerLogicalFrame:
    """Curated frozen payload, isolated from the neighbouring coverage test."""

    waveform = tuple(math.sin(index * math.tau * 3.0 / 64.0) for index in range(64))
    common = VisualizerCommonState(
        bars=(),
        bar_count=0,
        waveform=() if mode_id == "oscilloscope" else waveform,
        waveform_count=0 if mode_id == "oscilloscope" else len(waveform),
        energy=VisualizerEnergyState(bass=0.8, mid=0.6, high=0.4, overall=0.8),
    )
    if mode_id == "oscilloscope":
        state = _osc_frame(with_glow=True)
    else:  # pragma: no cover - parametrization only admits the line mode.
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


def _snapshot(
    mode_id: str,
    *,
    content_size: tuple[float, float],
    dpr: float,
    viewport_extent: tuple[float, float],
    uniform_visual_scale: float,
):
    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(mode_id),
        display_size=content_size,
        viewport_extent=viewport_extent,
        uniform_visual_scale=uniform_visual_scale,
        shadow_enabled=False,
    )
    presentation = replace(
        presentation,
        outer_rect=(0.0, 0.0, *content_size),
        content_rect=(0.0, 0.0, *content_size),
        dpr=dpr,
    )
    return compose_visualizer_render_snapshot(
        _logical(mode_id), presentation, logical_revision=1
    )


def _halo_pixel_count(
    host: QuickVisualizerRenderHost,
    *,
    snapshot,
    mode_id: str,
    with_glow: bool,
) -> int:
    from OpenGL import GL as gl

    width = round(snapshot.presentation.content_rect[2] * snapshot.presentation.dpr)
    height = round(snapshot.presentation.content_rect[3] * snapshot.presentation.dpr)
    color = gl.glGenTextures(1)
    fbo = gl.glGenFramebuffers(1)
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, color)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D,
            0,
            gl.GL_RGBA8,
            width,
            height,
            0,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            None,
        )
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER,
            gl.GL_COLOR_ATTACHMENT0,
            gl.GL_TEXTURE_2D,
            color,
            0,
        )
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE

        def render(enabled: bool) -> bytes:
            logical = snapshot.logical
            parameters = dict(logical.mode_state.parameters)
            parameters["osc_glow"] = 0.65 if enabled else 0.0
            rendered_snapshot = replace(
                snapshot,
                logical=replace(
                    logical,
                    mode_state=replace(
                        logical.mode_state,
                        parameters=freeze_render_fields(parameters),
                    ),
                ),
            )
            gl.glViewport(0, 0, width, height)
            gl.glClearColor(*[component / 255.0 for component in _BACKGROUND], 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            matrix = (
                2.0 / snapshot.presentation.content_rect[2], 0, 0, 0,
                0, 2.0 / snapshot.presentation.content_rect[3], 0, 0,
                0, 0, 1, 0, -1, -1, 0, 1,
            )
            assert host.render(
                snapshot=rendered_snapshot,
                viewport=(0, 0, width, height),
                logical_size=snapshot.presentation.content_rect[2:4],
                matrix_values=matrix,
            ) == snapshot.logical.mode_id
            return bytes(gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE))

        core = render(False)
        glow = render(with_glow)
        return sum(
            max(abs(glow[offset + channel] - core[offset + channel]) for channel in range(3)) >= 2
            and max(abs(core[offset + channel] - _BACKGROUND[channel]) for channel in range(3)) < 4
            for offset in range(0, len(core), 4)
        )
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([color])


@pytest.mark.qt
@pytest.mark.parametrize(
    ("mode_id", "expected_glow_color"),
    (("oscilloscope", (40, 255, 120, 255)),),
)
def test_real_gl_line_glow_uses_visible_logical_footprint(
    qt_app,
    mode_id: str,
    expected_glow_color: tuple[int, int, int, int],
) -> None:
    """DPR, 2x content, and huge authored worlds retain the intended halo math."""
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 6)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.6 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("offscreen OpenGL context unavailable")

    host = QuickVisualizerRenderHost()
    try:
        canonical = _snapshot(
            mode_id,
            content_size=_CANONICAL_SIZE,
            dpr=1.0,
            viewport_extent=_CANONICAL_SIZE,
            uniform_visual_scale=1.0,
        )
        dpr_150 = _snapshot(
            mode_id,
            content_size=_CANONICAL_SIZE,
            dpr=1.5,
            viewport_extent=_CANONICAL_SIZE,
            uniform_visual_scale=1.0,
        )
        doubled = _snapshot(
            mode_id,
            content_size=(840.0, 560.0),
            dpr=1.0,
            viewport_extent=_CANONICAL_SIZE,
            uniform_visual_scale=2.0,
        )
        huge_authored_world = _snapshot(
            mode_id,
            content_size=_CANONICAL_SIZE,
            dpr=1.0,
            viewport_extent=(420.0 / 0.17, 280.0 / 0.17),
            uniform_visual_scale=0.17,
        )
        assert canonical.logical.mode_state.parameters["osc_beam_glow_color"] == expected_glow_color

        canonical_pixels = _halo_pixel_count(host, snapshot=canonical, mode_id=mode_id, with_glow=True)
        dpr_150_pixels = _halo_pixel_count(host, snapshot=dpr_150, mode_id=mode_id, with_glow=True)
        doubled_pixels = _halo_pixel_count(host, snapshot=doubled, mode_id=mode_id, with_glow=True)
        huge_world_pixels = _halo_pixel_count(host, snapshot=huge_authored_world, mode_id=mode_id, with_glow=True)

        assert canonical_pixels > 2_000
        # Oscilloscope uses SceneTarget bloom. Check that glow reaches beyond
        # the beam at every geometry, without imposing the retired analytic
        # Gaussian shader's area ratios on the bloom pyramid.
        assert min(dpr_150_pixels, doubled_pixels, huge_world_pixels) > 2_000
        assert doubled_pixels > canonical_pixels
    finally:
        host.release_resources()
        context.doneCurrent()
        surface.destroy()
