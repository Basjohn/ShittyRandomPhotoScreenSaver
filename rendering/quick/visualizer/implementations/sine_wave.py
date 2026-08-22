"""Qt Quick Sine Wave renderer consuming one immutable snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.render_state import SineFrame
from widgets.spotify_visualizer.shaders import load_fragment_shader

from ..implementation_values import parameter, rgba, safe_hue
from ..render_contract import (
    QUICK_VISUALIZER_VERTEX_SOURCE,
    QuickVisualizerRenderFrame,
)


@dataclass(frozen=True, slots=True)
class QuickSineLayout:
    content_rect: tuple[float, float, float, float]
    inner_rect: tuple[float, float, float, float]
    line_width: float
    glow_sigma: float
    vertical_spacing_range: tuple[float, float]


def compute_quick_sine_layout(
    *,
    local_content_rect: Sequence[object],
    visual_scale: float,
) -> QuickSineLayout:
    if len(local_content_rect) != 4:
        raise ValueError("Sine content geometry is incomplete")
    content_x, content_y, content_width, content_height = (
        float(value) for value in local_content_rect
    )
    scale = float(visual_scale)
    if min(content_width, content_height, scale) <= 0.0:
        raise ValueError("Sine content geometry must be positive")
    margin_x = 5.0 * scale
    margin_y = 2.0 * scale
    inner_width = content_width - 2.0 * margin_x
    inner_height = content_height - 2.0 * margin_y
    if min(inner_width, inner_height) <= 0.0:
        raise ValueError("Sine content is too small for its margins")
    return QuickSineLayout(
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


class QuickSineRenderer:
    mode_id = "sine_wave"

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
        if not isinstance(mode_state, SineFrame):
            raise TypeError("Sine renderer received another mode frame")

        presentation = snapshot.presentation
        outer_x, outer_y, _outer_width, _outer_height = presentation.outer_rect
        content_x, content_y, content_width, content_height = (
            presentation.content_rect
        )
        layout = compute_quick_sine_layout(
            local_content_rect=(
                content_x - outer_x,
                content_y - outer_y,
                content_width,
                content_height,
            ),
            visual_scale=presentation.uniform_visual_scale,
        )
        if not self._program:
            self._initialize()

        parameters = mode_state.parameters
        uniforms = self._uniforms

        def _set1f(name: str, value: object) -> None:
            gl.glUniform1f(uniforms[name], float(value))

        def _set1i(name: str, value: object) -> None:
            gl.glUniform1i(uniforms[name], int(value))

        def _set_color(
            name: str,
            value: object,
            default: tuple[int, int, int, int],
        ) -> None:
            gl.glUniform4f(
                uniforms[name],
                *rgba(value, default=default),
            )

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2f(uniforms["u_resolution"], *frame.logical_size)
        _set1f("u_dpr", presentation.dpr)
        gl.glUniform2f(uniforms["u_viewport_origin_px"], 0.0, 0.0)
        _set1i("u_quick_item_coords", 1)
        gl.glUniform4f(uniforms["u_content_rect"], *layout.content_rect)
        _set1f("u_visual_scale", presentation.uniform_visual_scale)
        _set1f("u_fade", presentation.content_fade)
        _set1f("u_time", mode_state.animation_time)

        energy = logical.common.energy
        _set1f("u_bass_energy", energy.bass)
        _set1f("u_mid_energy", energy.mid)
        _set1f("u_high_energy", energy.high)

        _set1i("u_playing", 1 if logical.playing else 0)
        _set1f("u_sine_speed", parameter(parameters, "line_speed", 1.0))
        _set1i(
            "u_sine_line_dim",
            1 if bool(parameter(parameters, "line_dim", False)) else 0,
        )
        _set1f(
            "u_sine_line_offset_bias",
            _bounded(parameter(parameters, "line_offset_bias", 0.0), 0.0, 1.0),
        )
        _set1f(
            "u_card_adaptation",
            _bounded(parameter(parameters, "sine_card_adaptation", 0.3), 0.05, 1.0),
        )
        travel_names = (
            "sine_wave_travel",
            "sine_travel_line2",
            "sine_travel_line3",
            "sine_travel_line4",
            "sine_travel_line5",
            "sine_travel_line6",
        )
        uniform_travel_names = (
            "u_sine_travel",
            "u_sine_travel_line2",
            "u_sine_travel_line3",
            "u_sine_travel_line4",
            "u_sine_travel_line5",
            "u_sine_travel_line6",
        )
        for setting_name, uniform_name in zip(
            travel_names,
            uniform_travel_names,
        ):
            _set1i(
                uniform_name,
                max(0, min(2, int(parameter(parameters, setting_name, 0)))),
            )
        for index in range(1, 7):
            _set1f(
                f"u_sine_line{index}_shift",
                _bounded(
                    parameter(parameters, f"sine_line{index}_shift", 0.0),
                    -2.0,
                    2.0,
                ),
            )
        _set1f("u_wave_effect", parameter(parameters, "sine_wave_effect", 0.0))
        _set1f("u_micro_wobble", parameter(parameters, "sine_micro_wobble", 0.0))
        _set1f("u_crawl_amount", parameter(parameters, "sine_crawl_amount", 0.0))
        _set1f("u_wave_effect_gate", parameter(parameters, "wave_effect_gate", 0.06))
        _set1i(
            "u_sine_vertical_shift",
            max(
                -50,
                min(200, int(parameter(parameters, "sine_vertical_shift", 0))),
            ),
        )
        _set1f("u_heartbeat", parameter(parameters, "sine_heartbeat", 0.0))
        _set1f("u_heartbeat_intensity", mode_state.heartbeat_intensity)
        _set1f(
            "u_width_reaction",
            parameter(parameters, "resolved_width_reaction", 0.0),
        )
        _set1f("u_sine_density", parameter(parameters, "sine_density", 1.0))
        _set1f(
            "u_sine_displacement",
            parameter(parameters, "sine_displacement", 0.0),
        )

        ghost_enabled = bool(
            parameter(parameters, "sine_ghosting_enabled", True)
        )
        ghost_alpha = _bounded(
            parameter(parameters, "sine_ghost_alpha", 0.45),
            0.0,
            1.0,
        )
        _set1f("u_ghost_alpha", ghost_alpha if ghost_enabled else 0.0)
        _set1f("u_ghost_bass", mode_state.ghost_energy.bass)
        _set1f("u_ghost_mid", mode_state.ghost_energy.mid)
        _set1f("u_ghost_high", mode_state.ghost_energy.high)
        for index in range(2, 7):
            _set1i(
                f"u_ghost_line{index}_enabled",
                1
                if bool(
                    parameter(
                        parameters,
                        f"ghost_line{index}_enabled",
                        True,
                    )
                )
                else 0,
            )

        _set1i(
            "u_glow_enabled",
            1 if bool(parameter(parameters, "glow_enabled", True)) else 0,
        )
        _set1f(
            "u_glow_intensity",
            max(0.0, float(parameter(parameters, "glow_intensity", 0.5))),
        )
        _set1f(
            "u_glow_size",
            _bounded(parameter(parameters, "glow_size", 1.0), 0.1, 3.0),
        )
        _set1f(
            "u_glow_reactivity",
            _bounded(parameter(parameters, "glow_reactivity", 1.0), 0.0, 2.0),
        )
        _set_color(
            "u_glow_color",
            parameter(parameters, "glow_color", None),
            (0, 200, 255, 230),
        )
        _set1i(
            "u_reactive_glow",
            1 if bool(parameter(parameters, "reactive_glow", True)) else 0,
        )
        _set1f(
            "u_sensitivity",
            _bounded(
                parameter(parameters, "resolved_sensitivity", 1.0),
                0.1,
                5.0,
            ),
        )
        _set_color(
            "u_line_color",
            parameter(parameters, "line_color", None),
            (255, 255, 255, 255),
        )
        _set1i(
            "u_line_count",
            max(1, min(6, int(parameter(parameters, "line_count", 1)))),
        )
        color_defaults = {
            2: ((255, 120, 50, 230), (255, 120, 50, 180)),
            3: ((50, 255, 120, 230), (50, 255, 120, 180)),
            4: ((255, 0, 150, 230), (255, 0, 150, 180)),
            5: ((0, 255, 200, 230), (0, 255, 200, 180)),
            6: ((200, 100, 255, 230), (200, 100, 255, 180)),
        }
        for index, (line_default, glow_default) in color_defaults.items():
            _set_color(
                f"u_line{index}_color",
                parameter(parameters, f"line{index}_color", None),
                line_default,
            )
            _set_color(
                f"u_line{index}_glow_color",
                parameter(parameters, f"line{index}_glow_color", None),
                glow_default,
            )

        rainbow_enabled = bool(
            parameter(parameters, "rainbow_enabled", False)
        )
        rainbow_speed = _bounded(
            parameter(parameters, "rainbow_speed", 0.5),
            0.01,
            5.0,
        )
        hue = (
            safe_hue(mode_state.animation_time * rainbow_speed * 0.1)
            if rainbow_enabled
            else 0.0
        )
        _set1f("u_rainbow_hue_offset", hue)

        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        fragment_source = load_fragment_shader("sine_wave")
        if fragment_source is None:
            raise RuntimeError("canonical Sine shader is unavailable")
        program = compile_program(
            QUICK_VISUALIZER_VERTEX_SOURCE,
            fragment_source,
            label="Quick Sine Wave",
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
                "u_time",
                "u_bass_energy",
                "u_mid_energy",
                "u_high_energy",
                "u_line_color",
                "u_glow_enabled",
                "u_glow_intensity",
                "u_glow_size",
                "u_glow_reactivity",
                "u_glow_color",
                "u_reactive_glow",
                "u_sensitivity",
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
                "u_sine_line_dim",
                "u_sine_speed",
                "u_card_adaptation",
                "u_sine_line_offset_bias",
                "u_sine_travel",
                "u_sine_travel_line2",
                "u_sine_travel_line3",
                "u_sine_travel_line4",
                "u_sine_travel_line5",
                "u_sine_travel_line6",
                "u_sine_line1_shift",
                "u_sine_line2_shift",
                "u_sine_line3_shift",
                "u_sine_line4_shift",
                "u_sine_line5_shift",
                "u_sine_line6_shift",
                "u_playing",
                "u_wave_effect",
                "u_wave_effect_gate",
                "u_micro_wobble",
                "u_crawl_amount",
                "u_sine_vertical_shift",
                "u_rainbow_hue_offset",
                "u_heartbeat",
                "u_heartbeat_intensity",
                "u_width_reaction",
                "u_sine_density",
                "u_sine_displacement",
                "u_ghost_alpha",
                "u_ghost_bass",
                "u_ghost_mid",
                "u_ghost_high",
                "u_ghost_line2_enabled",
                "u_ghost_line3_enabled",
                "u_ghost_line4_enabled",
                "u_ghost_line5_enabled",
                "u_ghost_line6_enabled",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Sine uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def _bounded(value: object, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def create_visualizer_renderer() -> QuickSineRenderer:
    return QuickSineRenderer()


__all__ = [
    "QuickSineLayout",
    "QuickSineRenderer",
    "compute_quick_sine_layout",
    "create_visualizer_renderer",
]
