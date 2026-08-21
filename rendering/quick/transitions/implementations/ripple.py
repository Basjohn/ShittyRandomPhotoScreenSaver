"""Lazy Quick renderer for the canonical authored Ripple/Raindrops shader."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.raindrops_program import raindrops_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


def _ripple_count(parameters: Mapping[str, object]) -> int:
    raw = parameters.get("ripple_count")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("Ripple requires resolved integer parameter 'ripple_count'")
    if not 1 <= raw <= 8:
        raise ValueError("Ripple ripple_count must be between 1 and 8")
    return raw


def _ripple_seed(parameters: Mapping[str, object]) -> float:
    raw = parameters.get("ripple_seed")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Ripple requires resolved numeric parameter 'ripple_seed'")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Ripple ripple_seed must be finite")
    return value


class QuickRippleRenderer:
    transition_id = "ripple"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        parameters = frame.run.request.parameter_dict()
        count = _ripple_count(parameters)
        seed = _ripple_seed(parameters)
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"], float(frame.sample.eased_progress)
        )
        gl.glUniform2f(
            uniforms["u_resolution"],
            float(frame.viewport[2]),
            float(frame.viewport[3]),
        )
        gl.glUniform1i(uniforms["u_ripple_count"], count)
        gl.glUniform1f(uniforms["u_ripple_seed"], seed)
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
            raindrops_program.fragment_source,
            label="Quick Ripple",
        )
        self._program = program
        try:
            required = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_resolution",
                "u_ripple_count",
                "u_ripple_seed",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in required
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Ripple uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickRippleRenderer:
    return QuickRippleRenderer()
