"""Lazy Quick renderer for the canonical Warp Dissolve shader."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.warp_program import warp_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


class QuickWarpRenderer:
    transition_id = "warp_dissolve"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"],
            float(frame.sample.eased_progress),
        )
        gl.glUniform2f(
            uniforms["u_resolution"],
            float(frame.viewport[2]),
            float(frame.viewport[3]),
        )
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
            warp_program.fragment_source,
            label="Quick Warp Dissolve",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_resolution",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            missing = [
                name for name, location in uniforms.items() if location < 0
            ]
            if missing:
                raise RuntimeError(
                    "Quick Warp Dissolve uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickWarpRenderer:
    return QuickWarpRenderer()
