"""Qt Quick Oscilloscope renderer consuming one immutable snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import OscilloscopeFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader

from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)


_MAX_WAVEFORM_SAMPLES = 256


@dataclass(frozen=True, slots=True)
class QuickOscilloscopeLayout:
    content_rect: tuple[float, float, float, float]
    inner_rect: tuple[float, float, float, float]
    line_width: float
    glow_sigma: float
    vertical_spacing_range: tuple[float, float]


def compute_quick_oscilloscope_layout(
    *,
    local_content_rect: Sequence[object],
    visual_scale: float,
) -> QuickOscilloscopeLayout:
    if len(local_content_rect) != 4:
        raise ValueError("Oscilloscope content geometry is incomplete")
    content_x, content_y, content_width, content_height = (
        float(value) for value in local_content_rect
    )
    scale = float(visual_scale)
    if min(content_width, content_height, scale) <= 0.0:
        raise ValueError("Oscilloscope content geometry must be positive")
    margin_x = 5.0 * scale
    margin_y = 1.0 * scale
    inner_width = content_width - (2.0 * margin_x)
    inner_height = content_height - (2.0 * margin_y)
    if min(inner_width, inner_height) <= 0.0:
        raise ValueError("Oscilloscope content is too small for its margins")
    return QuickOscilloscopeLayout(
        content_rect=(content_x, content_y, content_width, content_height),
        inner_rect=(
            content_x + margin_x,
            content_y + margin_y,
            inner_width,
            inner_height,
        ),
        line_width=2.0 * scale,
        glow_sigma=8.0 * scale,
        vertical_spacing_range=(20.0 * scale, 80.0 * scale),
    )


def _padded(values: Sequence[object]) -> list[float]:
    resolved = [float(value) for value in values[:_MAX_WAVEFORM_SAMPLES]]
    resolved.extend([0.0] * (_MAX_WAVEFORM_SAMPLES - len(resolved)))
    return resolved


class QuickOscilloscopeRenderer:
    mode_id = "oscilloscope"

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
        if not isinstance(mode_state, OscilloscopeFrame):
            raise TypeError("Oscilloscope renderer received another mode frame")

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
        layout = compute_quick_oscilloscope_layout(
            local_content_rect=local_content_rect,
            visual_scale=presentation.uniform_visual_scale,
        )
        if not self._program:
            self._initialize()

        waveform_count = min(
            max(0, int(logical.common.waveform_count)),
            len(logical.common.waveform),
            _MAX_WAVEFORM_SAMPLES,
        )
        waveform = _padded(logical.common.waveform)
        previous_waveform = _padded(mode_state.previous_waveform)
        parameters = mode_state.parameters
        rainbow_enabled = bool(parameter(parameters, "rainbow_enabled", False))
        rainbow_speed = max(
            0.01,
            min(5.0, float(parameter(parameters, "rainbow_speed", 0.5))),
        )
        hue = (
            safe_hue(mode_state.animation_time * rainbow_speed * 0.1)
            if rainbow_enabled
            else 0.0
        )
        ghost_enabled = bool(
            parameter(parameters, "osc_ghosting_enabled", False)
        )
        ghost_alpha = max(
            0.0,
            min(
                1.0,
                float(parameter(parameters, "osc_ghost_intensity", 0.4)),
            ),
        )
        if not ghost_enabled or not mode_state.previous_waveform:
            ghost_alpha = 0.0

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
        gl.glUniform1f(uniforms["u_fade"], presentation.content_fade)
        gl.glUniform1i(uniforms["u_waveform_count"], max(waveform_count, 2))
        gl.glUniform1fv(
            uniforms["u_waveform"],
            _MAX_WAVEFORM_SAMPLES,
            waveform,
        )
        gl.glUniform1fv(
            uniforms["u_prev_waveform"],
            _MAX_WAVEFORM_SAMPLES,
            previous_waveform,
        )
        gl.glUniform1f(uniforms["u_osc_ghost_alpha"], ghost_alpha)

        gl.glUniform1i(
            uniforms["u_glow_enabled"],
            1 if bool(parameter(parameters, "glow_enabled", True)) else 0,
        )
        gl.glUniform1f(
            uniforms["u_glow_intensity"],
            max(0.0, float(parameter(parameters, "glow_intensity", 0.5))),
        )
        gl.glUniform1f(
            uniforms["u_glow_size"],
            max(0.1, min(3.0, float(parameter(parameters, "glow_size", 1.0)))),
        )
        gl.glUniform1f(
            uniforms["u_glow_reactivity"],
            max(
                0.0,
                min(2.0, float(parameter(parameters, "glow_reactivity", 1.0))),
            ),
        )
        gl.glUniform4f(
            uniforms["u_glow_color"],
            *rgba(
                parameter(parameters, "glow_color", None),
                default=(0, 200, 255, 230),
            ),
        )
        gl.glUniform1i(
            uniforms["u_reactive_glow"],
            1 if bool(parameter(parameters, "reactive_glow", True)) else 0,
        )
        gl.glUniform1f(
            uniforms["u_sensitivity"],
            max(
                0.5,
                min(
                    10.0,
                    float(parameter(parameters, "resolved_sensitivity", 3.0)),
                ),
            ),
        )
        gl.glUniform1f(
            uniforms["u_smoothing"],
            max(0.0, min(1.0, float(parameter(parameters, "line_smoothing", 0.7)))),
        )
        gl.glUniform4f(
            uniforms["u_line_color"],
            *rgba(
                parameter(parameters, "line_color", None),
                default=(255, 255, 255, 255),
            ),
        )
        gl.glUniform1i(
            uniforms["u_line_count"],
            max(1, min(6, int(parameter(parameters, "line_count", 1)))),
        )
        color_defaults = {
            2: ((255, 120, 50, 230), (255, 120, 50, 180)),
            3: ((50, 255, 120, 230), (50, 255, 120, 180)),
            4: ((255, 0, 150, 230), (255, 0, 150, 180)),
            5: ((0, 255, 200, 230), (0, 255, 200, 180)),
            6: ((200, 100, 255, 230), (200, 100, 255, 180)),
        }
        for line_number, (line_default, glow_default) in color_defaults.items():
            gl.glUniform4f(
                uniforms[f"u_line{line_number}_color"],
                *rgba(
                    parameter(parameters, f"line{line_number}_color", None),
                    default=line_default,
                ),
            )
            gl.glUniform4f(
                uniforms[f"u_line{line_number}_glow_color"],
                *rgba(
                    parameter(
                        parameters,
                        f"line{line_number}_glow_color",
                        None,
                    ),
                    default=glow_default,
                ),
            )
            gl.glUniform1i(
                uniforms[f"u_ghost_line{line_number}_enabled"],
                1
                if bool(
                    parameter(
                        parameters,
                        f"ghost_line{line_number}_enabled",
                        True,
                    )
                )
                else 0,
            )

        gl.glUniform1i(
            uniforms["u_osc_line_dim"],
            1 if bool(parameter(parameters, "line_dim", False)) else 0,
        )
        gl.glUniform1f(
            uniforms["u_osc_line_offset_bias"],
            max(
                0.0,
                min(1.0, float(parameter(parameters, "line_offset_bias", 0.0))),
            ),
        )
        gl.glUniform1i(
            uniforms["u_osc_vertical_shift"],
            max(-50, min(200, int(parameter(parameters, "osc_vertical_shift", 0)))),
        )
        gl.glUniform1f(uniforms["u_rainbow_hue_offset"], hue)

        energy = logical.common.energy
        gl.glUniform1f(uniforms["u_overall_energy"], energy.overall)
        gl.glUniform1f(uniforms["u_bass_energy"], energy.bass)
        gl.glUniform1f(uniforms["u_mid_energy"], energy.mid)
        gl.glUniform1f(uniforms["u_high_energy"], energy.high)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("oscilloscope")
        if fragment_source is None:
            raise RuntimeError("canonical Oscilloscope shader is unavailable")
        program = compile_program(
            QUICK_VISUALIZER_VERTEX_SOURCE,
            fragment_source,
            label="Quick Oscilloscope",
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
                "u_fade",
                "u_waveform_count",
                "u_waveform",
                "u_prev_waveform",
                "u_osc_ghost_alpha",
                "u_glow_enabled",
                "u_glow_intensity",
                "u_glow_size",
                "u_glow_reactivity",
                "u_glow_color",
                "u_reactive_glow",
                "u_sensitivity",
                "u_smoothing",
                "u_line_color",
                "u_line_count",
                "u_line2_color",
                "u_line2_glow_color",
                "u_line3_color",
                "u_line3_glow_color",
                "u_line4_color",
                "u_line4_glow_color",
                "u_line5_color",
                "u_line5_glow_color",
                "u_line6_color",
                "u_line6_glow_color",
                "u_osc_line_dim",
                "u_osc_line_offset_bias",
                "u_osc_vertical_shift",
                "u_rainbow_hue_offset",
                "u_ghost_line2_enabled",
                "u_ghost_line3_enabled",
                "u_ghost_line4_enabled",
                "u_ghost_line5_enabled",
                "u_ghost_line6_enabled",
                "u_overall_energy",
                "u_bass_energy",
                "u_mid_energy",
                "u_high_energy",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Oscilloscope uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_visualizer_renderer() -> QuickOscilloscopeRenderer:
    return QuickOscilloscopeRenderer()


__all__ = [
    "QuickOscilloscopeLayout",
    "QuickOscilloscopeRenderer",
    "compute_quick_oscilloscope_layout",
    "create_visualizer_renderer",
]
