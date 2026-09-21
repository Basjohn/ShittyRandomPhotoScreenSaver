"""Lazy renderer for the finite connected Ink Bloom transition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.ink_bloom_program import INK_BLOOM_FRAGMENT_SOURCE
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


@dataclass(frozen=True, slots=True)
class InkBloomParameters:
    seed: int
    detail: float


def ink_bloom_parameters(parameters: Mapping[str, object]) -> InkBloomParameters:
    """Validate the resolved, immutable authored values once per draw."""

    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Ink Bloom seed must be an integer between 1 and 65535")
    detail = parameters.get("detail")
    if isinstance(detail, bool) or not isinstance(detail, (int, float)):
        raise ValueError("Ink Bloom detail must be numeric")
    detail = float(detail)
    if not math.isfinite(detail) or not 0.5 <= detail <= 2.0:
        raise ValueError("Ink Bloom detail must be finite and between 0.5 and 2")
    return InkBloomParameters(seed, detail)


class QuickInkBloomRenderer:
    transition_id = "ink_bloom"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        params = ink_bloom_parameters(frame.run.request.parameter_dict())
        uniforms = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], float(frame.sample.eased_progress))
        gl.glUniform1f(uniforms["u_seed"], float(params.seed))
        gl.glUniform1f(uniforms["u_detail"], params.detail)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if self._program:
            gl.glDeleteProgram(self._program)
            self._program = 0
            self._uniforms.clear()

    def _initialize(self) -> None:
        self._program = compile_program(QUICK_TRANSITION_VERTEX_SOURCE, INK_BLOOM_FRAGMENT_SOURCE, label="Quick Ink Bloom")
        try:
            names = ("uMatrix", "uItemSize", "u_progress", "u_seed", "u_detail", "uOldTex", "uNewTex")
            self._uniforms = {name: int(gl.glGetUniformLocation(self._program, name)) for name in names}
            missing = [name for name in names if self._uniforms[name] < 0]
            if missing:
                raise RuntimeError("Quick Ink Bloom uniforms are incomplete: " + ", ".join(missing))
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickInkBloomRenderer:
    return QuickInkBloomRenderer()
