"""Quick Slide renderer using the canonical production fragment shader."""

from __future__ import annotations

from OpenGL import GL as gl

from rendering.gl_programs.slide_program import slide_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_VECTORS = {
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "up": (0.0, -1.0),
    "down": (0.0, 1.0),
    "diag_tl_br": (-1.0, -1.0),
    "diag_tr_bl": (1.0, -1.0),
}


def _slide_rects(
    direction: object,
    progress: float,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    """Return old/new normalized rects for one canonical Slide direction."""

    value = "left" if direction is None else str(direction).strip().lower()
    vector = _DIRECTION_VECTORS.get(value)
    if vector is None:
        raise ValueError(f"unknown canonical Slide direction: {direction!r}")
    amount = max(0.0, min(1.0, float(progress)))
    dx, dy = vector
    old_rect = (dx * amount, dy * amount, 1.0, 1.0)
    new_rect = (dx * (amount - 1.0), dy * (amount - 1.0), 1.0, 1.0)
    return old_rect, new_rect


class QuickSlideRenderer:
    transition_id = "slide"

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
        progress = float(frame.sample.eased_progress)
        old_rect, new_rect = _slide_rects(
            frame.run.request.direction,
            progress,
        )

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        progress_location = uniforms["u_progress"]
        if progress_location >= 0:
            gl.glUniform1f(progress_location, progress)
        gl.glUniform4f(uniforms["u_oldRect"], *old_rect)
        gl.glUniform4f(uniforms["u_newRect"], *new_rect)
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
            slide_program.fragment_source,
            label="Quick Slide",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "uOldTex",
                "uNewTex",
                "u_oldRect",
                "u_newRect",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            required = (
                "uMatrix",
                "uItemSize",
                "uOldTex",
                "uNewTex",
                "u_oldRect",
                "u_newRect",
            )
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Slide uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickSlideRenderer:
    return QuickSlideRenderer()
