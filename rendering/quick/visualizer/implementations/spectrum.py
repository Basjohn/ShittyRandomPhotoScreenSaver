"""Qt Quick Spectrum renderer consuming only one immutable snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import SpectrumFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    SPECTRUM_SHADER_INPUT_SCALE,
    compute_spectrum_height_scale,
)

from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)
from ..implementation_values import parameter, rgba, safe_hue


_MAX_BARS = 64


def prepare_spectrum_shader_levels(
    bars: Sequence[object],
    peaks: Sequence[object],
    *,
    bar_count: int,
) -> tuple[list[float], list[float]]:
    """Return fixed-width shader arrays with the historical final transfer.

    Authored Spectrum bars stay in their canonical logical domain.  The old GL
    renderer applied ``0.55`` only at upload time; retained Quick presentation
    must do the same rather than weakening the BeatEngine or frame runtime.
    """

    count = min(_MAX_BARS, max(0, int(bar_count)))
    resolved_bars = [float(value) for value in bars[:count]]
    if len(resolved_bars) < count:
        resolved_bars.extend([0.0] * (count - len(resolved_bars)))

    resolved_peaks = [float(value) for value in peaks[:count]]
    if len(resolved_peaks) < count:
        resolved_peaks.extend(resolved_bars[len(resolved_peaks):count])

    for index in range(count):
        resolved_bars[index] *= SPECTRUM_SHADER_INPUT_SCALE
        resolved_peaks[index] *= SPECTRUM_SHADER_INPUT_SCALE

    resolved_bars.extend([0.0] * (_MAX_BARS - len(resolved_bars)))
    resolved_peaks.extend([0.0] * (_MAX_BARS - len(resolved_peaks)))
    return resolved_bars, resolved_peaks


@dataclass(frozen=True, slots=True)
class QuickSpectrumLayout:
    content_rect: tuple[float, float, float, float]
    bars_left: float
    bar_width: float
    bar_gap: float
    bar_span: float
    segment_count: int
    height_scale: float


def compute_quick_spectrum_layout(
    *,
    local_content_rect: Sequence[object],
    viewport_extent: Sequence[object],
    visual_scale: float,
    bar_count: int,
) -> QuickSpectrumLayout:
    if len(local_content_rect) != 4 or len(viewport_extent) != 2:
        raise ValueError("Spectrum layout geometry is incomplete")
    content_x, content_y, content_width, content_height = (
        float(value) for value in local_content_rect
    )
    extent_height = float(viewport_extent[1])
    scale = float(visual_scale)
    count = int(bar_count)
    if min(content_width, content_height, extent_height, scale) <= 0.0:
        raise ValueError("Spectrum layout geometry must be positive")
    if count <= 0 or count > _MAX_BARS:
        raise ValueError("Spectrum bar count must be in [1, 64]")

    margin = 8.0 * scale
    left_inset = 1.0 * scale
    right_inset = 3.0 * scale
    gap = 2.0 * scale
    bar_region_width = (
        content_width - (2.0 * margin) - left_inset - right_inset
    )
    total_gap = gap * max(0, count - 1)
    usable_width = bar_region_width - total_gap
    if usable_width <= 0.0:
        raise ValueError("Spectrum viewport is too narrow for its bars")
    bar_width = usable_width / count
    span = (bar_width * count) + total_gap
    inner_height = max(0.0, extent_height - 12.0)
    segments = max(8, min(64, int(inner_height // 5.0)))
    return QuickSpectrumLayout(
        content_rect=(content_x, content_y, content_width, content_height),
        bars_left=content_x + margin + left_inset,
        bar_width=bar_width,
        bar_gap=gap,
        bar_span=span,
        segment_count=segments,
        height_scale=compute_spectrum_height_scale(extent_height),
    )


class QuickSpectrumRenderer:
    mode_id = "spectrum"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickVisualizerRenderFrame) -> None:
        snapshot = frame.snapshot
        logical = snapshot.logical
        mode_state = logical.mode_state
        if not isinstance(mode_state, SpectrumFrame):
            raise TypeError("Spectrum renderer received another mode frame")
        count = min(_MAX_BARS, int(logical.common.bar_count))
        if count <= 0:
            return
        bars, peaks = prepare_spectrum_shader_levels(
            logical.common.bars,
            mode_state.peaks,
            bar_count=count,
        )

        presentation = snapshot.presentation
        outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
        content_x, content_y, content_width, content_height = (
            presentation.content_rect
        )
        local_content_rect = (
            content_x - outer_x,
            content_y - outer_y,
            content_width,
            content_height,
        )
        layout = compute_quick_spectrum_layout(
            local_content_rect=local_content_rect,
            viewport_extent=presentation.viewport_extent,
            visual_scale=presentation.uniform_visual_scale,
            bar_count=count,
        )
        if not self._program:
            self._initialize()

        parameters = mode_state.parameters
        style = logical.common.style
        fill = rgba(
            style.get("fill_color"),
            default=(30, 215, 96, 255),
        )
        border = rgba(
            style.get("border_color"),
            default=(255, 255, 255, 255),
        )
        glow_color = rgba(
            parameter(parameters, "spectrum_glow_color", None),
            default=tuple(round(channel * 255.0) for channel in border),
        )
        rainbow_enabled = bool(
            parameter(parameters, "rainbow_enabled", False)
        )
        rainbow_per_bar = bool(
            parameter(parameters, "rainbow_per_bar", False)
        )
        rainbow_speed = max(
            0.01,
            min(5.0, float(parameter(parameters, "rainbow_speed", 0.5))),
        )
        if rainbow_enabled:
            hue = safe_hue(
                mode_state.animation_time * rainbow_speed * 0.1
            )
        elif rainbow_per_bar:
            hue = safe_hue(mode_state.animation_time * 0.05)
        else:
            hue = 0.0

        uniforms = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2f(uniforms["u_resolution"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_dpr"], presentation.dpr)
        gl.glUniform2f(uniforms["u_viewport_origin_px"], 0.0, 0.0)
        gl.glUniform1i(uniforms["u_quick_item_coords"], 1)
        gl.glUniform4f(uniforms["u_content_rect"], *layout.content_rect)
        gl.glUniform1f(
            uniforms["u_visual_scale"],
            presentation.uniform_visual_scale,
        )
        gl.glUniform1i(uniforms["u_bar_count"], count)
        gl.glUniform1i(uniforms["u_segments"], layout.segment_count)
        gl.glUniform1fv(uniforms["u_bars"], _MAX_BARS, bars)
        gl.glUniform1fv(uniforms["u_peaks"], _MAX_BARS, peaks)
        gl.glUniform4f(uniforms["u_fill_color"], *fill)
        gl.glUniform4f(uniforms["u_border_color"], *border)
        gl.glUniform1f(uniforms["u_fade"], presentation.content_fade)
        gl.glUniform1f(uniforms["u_bar_height_scale"], layout.height_scale)
        gl.glUniform1i(
            uniforms["u_single_piece"],
            1 if bool(style.get("single_piece", False)) else 0,
        )
        gl.glUniform1i(
            uniforms["u_slanted"],
            1 if bool(parameter(parameters, "slanted", False)) else 0,
        )
        gl.glUniform1f(
            uniforms["u_border_radius"],
            max(0.0, float(style.get("border_radius", 0.0)))
            * presentation.uniform_visual_scale,
        )
        ghost_enabled = bool(
            parameter(parameters, "spectrum_ghosting_enabled", True)
        )
        ghost_alpha = float(
            parameter(parameters, "spectrum_ghost_alpha", 0.4)
        )
        gl.glUniform1f(
            uniforms["u_ghost_alpha"],
            max(0.0, min(1.0, ghost_alpha)) if ghost_enabled else 0.0,
        )
        gl.glUniform1i(
            uniforms["u_spectrum_glow_enabled"],
            1
            if bool(parameter(parameters, "spectrum_glow_enabled", False))
            else 0,
        )
        gl.glUniform1f(
            uniforms["u_spectrum_glow_intensity"],
            max(
                0.0,
                min(
                    1.5,
                    float(
                        parameter(
                            parameters,
                            "spectrum_glow_intensity",
                            0.55,
                        )
                    ),
                ),
            ),
        )
        gl.glUniform4f(uniforms["u_spectrum_glow_color"], *glow_color)
        gl.glUniform1f(uniforms["u_rainbow_hue_offset"], hue)
        gl.glUniform1i(
            uniforms["u_rainbow_per_bar"],
            1 if rainbow_per_bar else 0,
        )
        gl.glUniform1i(
            uniforms["u_rainbow_border"],
            1
            if bool(
                parameter(parameters, "spectrum_rainbow_border", False)
            )
            else 0,
        )
        gl.glUniform1f(uniforms["u_bars_left"], layout.bars_left)
        gl.glUniform1f(uniforms["u_bar_width_px"], layout.bar_width)
        gl.glUniform1f(uniforms["u_bar_gap_px"], layout.bar_gap)
        gl.glUniform1f(uniforms["u_bar_span_px"], layout.bar_span)
        playing_location = uniforms.get("u_playing", -1)
        if playing_location >= 0:
            gl.glUniform1i(playing_location, 1 if logical.playing else 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("spectrum")
        if fragment_source is None:
            raise RuntimeError("canonical Spectrum shader is unavailable")
        program = compile_program(
            QUICK_VISUALIZER_VERTEX_SOURCE,
            fragment_source,
            label="Quick Spectrum",
        )
        self._program = program
        try:
            required = (
                "uMatrix",
                "uItemSize",
                "u_resolution",
                "u_dpr",
                "u_viewport_origin_px",
                "u_quick_item_coords",
                "u_content_rect",
                "u_visual_scale",
                "u_bar_count",
                "u_segments",
                "u_bars",
                "u_peaks",
                "u_fill_color",
                "u_border_color",
                "u_fade",
                "u_ghost_alpha",
                "u_bar_height_scale",
                "u_single_piece",
                "u_slanted",
                "u_border_radius",
                "u_spectrum_glow_enabled",
                "u_spectrum_glow_intensity",
                "u_spectrum_glow_color",
                "u_rainbow_hue_offset",
                "u_rainbow_per_bar",
                "u_rainbow_border",
                "u_bars_left",
                "u_bar_width_px",
                "u_bar_gap_px",
                "u_bar_span_px",
            )
            names = (*required, "u_playing")
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in names
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Spectrum uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_visualizer_renderer() -> QuickSpectrumRenderer:
    return QuickSpectrumRenderer()


__all__ = [
    "QuickSpectrumLayout",
    "QuickSpectrumRenderer",
    "compute_quick_spectrum_layout",
    "create_visualizer_renderer",
]
