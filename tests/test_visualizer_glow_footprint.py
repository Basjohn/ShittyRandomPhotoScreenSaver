"""Real-GL parity checks for line-visualizer glow footprint coordinates."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtGui import QColor

from core.settings.visualizer_mode_registry import get_visualizer_presentation_policy
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation
from widgets.spotify_visualizer.render_state import (
    OscilloscopeFrame,
    SineFrame,
    VisualizerCommonState,
    VisualizerEnergyState,
    VisualizerLogicalFrame,
    compose_visualizer_render_snapshot,
    freeze_render_fields,
)


_BACKGROUND = (6, 11, 19)
_CANONICAL_SIZE = (420.0, 280.0)


def _logical(mode_id: str) -> VisualizerLogicalFrame:
    """Curated frozen payload, isolated from the neighbouring coverage test."""

    waveform = tuple(math.sin(index * math.tau * 3.0 / 64.0) for index in range(64))
    common = VisualizerCommonState(
        bars=(),
        bar_count=0,
        waveform=waveform,
        waveform_count=len(waveform),
        energy=VisualizerEnergyState(bass=0.8, mid=0.6, high=0.4, overall=0.8),
    )
    preset_root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    if mode_id == "sine_wave":
        preset = json.loads((preset_root / "sine_wave" / "preset_1_Wobble_Groove.json").read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]
        state = SineFrame(
            animation_time=0.37,
            parameters=freeze_render_fields({
                "sine_density": preset["sine_density"],
                "sine_card_adaptation": preset["sine_card_adaptation"],
                "line_speed": preset["sine_speed"],
                "sine_wave_travel": preset["sine_wave_travel"],
                "sine_wave_effect": preset["sine_wave_effect"],
                "sine_micro_wobble": preset["sine_micro_wobble"],
                "line_count": preset["sine_line_count"],
                "line_color": QColor(*preset["sine_line_color"]),
                "glow_enabled": True,
                "glow_intensity": preset["sine_glow_intensity"],
                "glow_reactivity": preset["sine_glow_reactivity"],
                "glow_color": QColor(*preset["sine_glow_color"]),
                "resolved_sensitivity": preset["sine_sensitivity"],
                **{f"line{index}_color": QColor(*preset[f"sine_line{index}_color"]) for index in range(2, 7)},
                **{f"sine_travel_line{index}": preset[f"sine_travel_line{index}"] for index in range(2, 7)},
                **{f"sine_line{index}_shift": preset[f"sine_line{index}_shift"] for index in range(1, 7)},
            }),
        )
    elif mode_id == "oscilloscope":
        preset = json.loads((preset_root / "oscilloscope" / "preset_1_night_drive.json").read_text(encoding="utf-8"))["snapshot"]["widgets"]["spotify_visualizer"]
        state = OscilloscopeFrame(
            animation_time=0.37,
            parameters=freeze_render_fields({
                "line_smoothing": preset["osc_smoothing"],
                "resolved_sensitivity": preset["osc_line_amplitude"],
                "line_color": QColor(*preset["osc_line_color"]),
                "line_count": preset["osc_line_count"],
                "glow_enabled": True,
                "glow_intensity": preset["osc_glow_intensity"],
                "glow_reactivity": preset["osc_glow_reactivity"],
                "glow_color": QColor(*preset["osc_glow_color"]),
                "reactive_glow": preset["osc_reactive_glow"],
                "osc_line_offset_bias": preset["osc_line_offset_bias"],
                "osc_vertical_shift": preset["osc_vertical_shift"],
                **{f"line{index}_color": QColor(*preset[f"osc_line{index}_color"]) for index in range(2, 7)},
                **{f"line{index}_glow_color": QColor(*preset[f"osc_line{index}_glow_color"]) for index in range(2, 7)},
            }),
        )
    else:  # pragma: no cover - parametrization only admits the two line modes.
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
            parameters["glow_enabled"] = enabled
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
    (("sine_wave", (206, 92, 255, 255)), ("oscilloscope", (130, 160, 255, 255))),
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
        assert canonical.logical.mode_state.parameters["glow_color"] == expected_glow_color

        canonical_pixels = _halo_pixel_count(host, snapshot=canonical, with_glow=True)
        dpr_150_pixels = _halo_pixel_count(host, snapshot=dpr_150, with_glow=True)
        doubled_pixels = _halo_pixel_count(host, snapshot=doubled, with_glow=True)
        huge_world_pixels = _halo_pixel_count(host, snapshot=huge_authored_world, with_glow=True)

        # Pixel count is a halo area. Dividing by DPR² restores logical area;
        # doubled visible dimensions produce four times that area. The same
        # visible content must not inherit its 0.17 authored-world scale.
        assert canonical_pixels > 2_000
        assert dpr_150_pixels / (1.5 * 1.5) == pytest.approx(canonical_pixels, rel=0.18)
        assert doubled_pixels == pytest.approx(canonical_pixels * 4.0, rel=0.25)
        # Sine's authored-scale margins and amplitude alter its curve length
        # slightly, while the halo radius itself remains content-derived. A
        # 30% area bound catches reintroducing the old 0.17 sigma collapse.
        assert huge_world_pixels == pytest.approx(canonical_pixels, rel=0.30)
    finally:
        host.release_resources()
        context.doneCurrent()
        surface.destroy()
