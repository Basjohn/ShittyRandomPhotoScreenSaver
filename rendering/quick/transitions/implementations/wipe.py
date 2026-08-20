"""Quick Wipe renderer using the canonical production fragment shader."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.wipe_program import wipe_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_MODES = {
    "left_to_right": 0,
    "right_to_left": 1,
    "top_to_bottom": 2,
    "bottom_to_top": 3,
    "diag_tl_br": 4,
    "diag_tr_bl": 5,
}


def _wipe_mode(direction: object) -> int:
    """Map one resolved canonical Wipe direction to its shader mode."""

    value = "left_to_right" if direction is None else str(direction).strip().lower()
    mode = _DIRECTION_MODES.get(value)
    if mode is None:
        raise ValueError(f"unknown canonical Wipe direction: {direction!r}")
    return mode


class QuickWipeRenderer:
    transition_id = "wipe"

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
        gl.glUniform1i(
            uniforms["u_mode"],
            _wipe_mode(frame.run.request.direction),
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
            wipe_program.fragment_source,
            label="Quick Wipe",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_mode",
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
                    "Quick Wipe uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickWipeRenderer:
    return QuickWipeRenderer()
