"""Lazy renderer for the finite directional Melt / Drip transition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from OpenGL import GL as gl

from rendering.gl_programs.melt_drip_program import MELT_DRIP_FRAGMENT_SOURCE
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


_DIRECTION_VECTORS = {"down": (0.0, 1.0), "up": (0.0, -1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}


@dataclass(frozen=True, slots=True)
class MeltDripParameters:
    seed: int
    detail: float
    direction: tuple[float, float]


def melt_drip_parameters(parameters: Mapping[str, object], direction: object) -> MeltDripParameters:
    seed = parameters.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 1 <= seed <= 65535:
        raise ValueError("Melt / Drip seed must be an integer between 1 and 65535")
    detail = parameters.get("detail")
    if isinstance(detail, bool) or not isinstance(detail, (int, float)):
        raise ValueError("Melt / Drip detail must be numeric")
    detail = float(detail)
    if not math.isfinite(detail) or not 0.5 <= detail <= 2.0:
        raise ValueError("Melt / Drip detail must be finite and between 0.5 and 2")
    resolved = _DIRECTION_VECTORS.get(str(direction).strip().lower())
    if resolved is None:
        raise ValueError("Melt / Drip requires resolved direction down, up, left, or right")
    return MeltDripParameters(seed, detail, resolved)


class QuickMeltDripRenderer:
    transition_id = "melt_drip"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        params = melt_drip_parameters(frame.run.request.parameter_dict(), frame.run.request.direction)
        uniforms = self._uniforms
        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], float(frame.sample.eased_progress))
        gl.glUniform1f(uniforms["u_seed"], float(params.seed))
        gl.glUniform1f(uniforms["u_detail"], params.detail)
        gl.glUniform2f(uniforms["u_direction"], *params.direction)
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
        self._program = compile_program(QUICK_TRANSITION_VERTEX_SOURCE, MELT_DRIP_FRAGMENT_SOURCE, label="Quick Melt Drip")
        try:
            names = ("uMatrix", "uItemSize", "u_progress", "u_seed", "u_detail", "u_direction", "uOldTex", "uNewTex")
            self._uniforms = {name: int(gl.glGetUniformLocation(self._program, name)) for name in names}
            missing = [name for name in names if self._uniforms[name] < 0]
            if missing:
                raise RuntimeError("Quick Melt Drip uniforms are incomplete: " + ", ".join(missing))
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickMeltDripRenderer:
    return QuickMeltDripRenderer()
