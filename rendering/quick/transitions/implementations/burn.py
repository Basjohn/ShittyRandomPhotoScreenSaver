"""Lazy Quick renderer for the full authored Burn transition shader."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.burn_program import burn_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


@dataclass(frozen=True, slots=True)
class _BurnParameters:
    direction: int
    jaggedness: float
    glow_intensity: float
    glow_color: tuple[float, float, float, float]
    ember_color: tuple[float, float, float, float]
    char_width: float
    smoke_enabled: bool
    smoke_density: float
    ash_enabled: bool
    ash_density: float
    seed: float


def _number(parameters: Mapping[str, object], name: str) -> float:
    raw = parameters.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"Burn requires resolved numeric parameter {name!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Burn {name} must be finite")
    return value


def _boolean(parameters: Mapping[str, object], name: str) -> bool:
    raw = parameters.get(name)
    if not isinstance(raw, bool):
        raise ValueError(f"Burn requires resolved boolean parameter {name!r}")
    return raw


def _burn_color(
    parameters: Mapping[str, object],
    name: str,
) -> tuple[float, float, float, float]:
    raw = parameters.get(name)
    if not isinstance(raw, tuple) or len(raw) != 4:
        raise ValueError(
            f"Burn requires resolved normalized RGBA tuple parameter {name!r}"
        )
    channels: list[float] = []
    for channel in raw:
        if isinstance(channel, bool) or not isinstance(channel, (int, float)):
            raise ValueError(f"Burn {name} channels must be numeric")
        value = float(channel)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"Burn {name} channels must be finite and between 0 and 1")
        channels.append(value)
    return tuple(channels)  # type: ignore[return-value]


def _burn_parameters(parameters: Mapping[str, object]) -> _BurnParameters:
    direction_raw = parameters.get("direction")
    if isinstance(direction_raw, bool) or not isinstance(direction_raw, int):
        raise ValueError("Burn requires resolved integer parameter 'direction'")
    if not 0 <= direction_raw <= 5:
        raise ValueError("Burn direction must be between 0 and 5")

    jaggedness = _number(parameters, "jaggedness")
    glow_intensity = _number(parameters, "glow_intensity")
    char_width = _number(parameters, "char_width")
    smoke_density = _number(parameters, "smoke_density")
    ash_density = _number(parameters, "ash_density")
    seed = _number(parameters, "seed")

    if not 0.0 <= jaggedness <= 1.0:
        raise ValueError("Burn jaggedness must be between 0 and 1")
    if not 0.0 <= glow_intensity <= 1.0:
        raise ValueError("Burn glow_intensity must be between 0 and 1")
    if not 0.1 <= char_width <= 1.0:
        raise ValueError("Burn char_width must be between 0.1 and 1")
    if not 0.0 <= smoke_density <= 1.0:
        raise ValueError("Burn smoke_density must be between 0 and 1")
    if not 0.0 <= ash_density <= 1.0:
        raise ValueError("Burn ash_density must be between 0 and 1")

    return _BurnParameters(
        direction=direction_raw,
        jaggedness=jaggedness,
        glow_intensity=glow_intensity,
        glow_color=_burn_color(parameters, "glow_color"),
        ember_color=_burn_color(parameters, "ember_color"),
        char_width=char_width,
        smoke_enabled=_boolean(parameters, "smoke_enabled"),
        smoke_density=smoke_density,
        ash_enabled=_boolean(parameters, "ash_enabled"),
        ash_density=ash_density,
        seed=seed,
    )


def _burn_effect_time_seconds(frame: QuickTransitionRenderFrame) -> float:
    return (
        float(frame.sample.linear_progress)
        * float(frame.run.request.duration_ms)
        / 1000.0
    )


class QuickBurnRenderer:
    transition_id = "burn"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        params = _burn_parameters(frame.run.request.parameter_dict())
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], float(frame.sample.eased_progress))
        gl.glUniform1i(uniforms["u_direction"], params.direction)
        gl.glUniform1f(uniforms["u_jaggedness"], params.jaggedness)
        gl.glUniform1f(uniforms["u_glow_intensity"], params.glow_intensity)
        gl.glUniform4f(uniforms["u_glow_color"], *params.glow_color)
        gl.glUniform4f(uniforms["u_ember_color"], *params.ember_color)
        gl.glUniform1f(uniforms["u_char_width"], params.char_width)
        gl.glUniform1i(uniforms["u_smoke_enabled"], 1 if params.smoke_enabled else 0)
        gl.glUniform1f(uniforms["u_smoke_density"], params.smoke_density)
        gl.glUniform1i(uniforms["u_ash_enabled"], 1 if params.ash_enabled else 0)
        gl.glUniform1f(uniforms["u_ash_density"], params.ash_density)
        gl.glUniform1f(uniforms["u_time"], _burn_effect_time_seconds(frame))
        gl.glUniform1f(uniforms["u_seed"], params.seed)

        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        program = compile_program(
            QUICK_TRANSITION_VERTEX_SOURCE,
            burn_program.fragment_source,
            label="Quick Burn",
        )
        self._program = program
        try:
            required = (
                "uMatrix", "uItemSize", "u_progress", "uOldTex", "uNewTex",
                "u_direction", "u_jaggedness", "u_glow_intensity",
                "u_glow_color", "u_ember_color", "u_char_width", "u_smoke_enabled",
                "u_smoke_density", "u_ash_enabled", "u_ash_density",
                "u_time", "u_seed",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Burn uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickBurnRenderer:
    return QuickBurnRenderer()
