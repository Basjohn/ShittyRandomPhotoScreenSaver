"""Lazy Quick renderer for the canonical authored Crumble shader."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.crumble_program import crumble_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


def _number(parameters: Mapping[str, object], name: str) -> float:
    raw = parameters.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"Crumble requires resolved numeric parameter {name!r}")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"Crumble {name} must be finite")
    return value


def _crumble_parameters(parameters: Mapping[str, object]) -> tuple[float, int, float, bool, float]:
    seed = _number(parameters, "seed")

    piece_raw = parameters.get("piece_count")
    if isinstance(piece_raw, bool) or not isinstance(piece_raw, int):
        raise ValueError("Crumble requires resolved integer parameter 'piece_count'")
    if piece_raw < 4:
        raise ValueError("Crumble piece_count must be at least 4")

    complexity = _number(parameters, "crack_complexity")
    if not 0.5 <= complexity <= 2.0:
        raise ValueError("Crumble crack_complexity must be between 0.5 and 2.0")

    mosaic = parameters.get("mosaic_mode")
    if not isinstance(mosaic, bool):
        raise ValueError("Crumble requires resolved boolean parameter 'mosaic_mode'")

    weight_mode = _number(parameters, "weight_mode")
    if weight_mode not in {0.0, 1.0, 2.0, 3.0, 4.0}:
        raise ValueError("Crumble weight_mode must be one of 0, 1, 2, 3, 4")

    return seed, piece_raw, complexity, mosaic, weight_mode


class QuickCrumbleRenderer:
    transition_id = "crumble"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        seed, pieces, complexity, mosaic, weight_mode = _crumble_parameters(
            frame.run.request.parameter_dict()
        )
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"], float(frame.sample.eased_progress)
        )
        resolution = uniforms.get("u_resolution", -1)
        if resolution >= 0:
            gl.glUniform2f(
                resolution,
                float(frame.viewport[2]),
                float(frame.viewport[3]),
            )
        gl.glUniform1f(uniforms["u_seed"], seed)
        gl.glUniform1f(uniforms["u_piece_count"], float(pieces))
        gl.glUniform1f(uniforms["u_crack_complexity"], complexity)
        mosaic_location = uniforms.get("u_mosaic_mode", -1)
        if mosaic_location >= 0:
            gl.glUniform1f(mosaic_location, 1.0 if mosaic else 0.0)
        gl.glUniform1f(uniforms["u_weight_mode"], weight_mode)
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
            crumble_program.fragment_source,
            label="Quick Crumble",
        )
        self._program = program
        try:
            required = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_seed",
                "u_piece_count",
                "u_crack_complexity",
                "u_weight_mode",
                "uOldTex",
                "uNewTex",
            )
            optional = ("u_resolution", "u_mosaic_mode")
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in (*required, *optional)
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Crumble uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickCrumbleRenderer:
    return QuickCrumbleRenderer()
