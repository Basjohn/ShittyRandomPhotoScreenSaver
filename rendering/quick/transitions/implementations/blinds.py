"""Lazy Quick renderer for the canonical authored Blinds shader."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.blinds_program import blinds_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_BLINDS_DIRECTION_MODES = {
    "horizontal": 0,
    "vertical": 1,
    "diagonal": 2,
}
_AUTHORED_SLAT_COLS = 7
_MIN_FEATHER = 0.001
_MAX_FEATHER = 0.5


def _blinds_direction_mode(direction: object) -> int:
    """Map one fully resolved authored direction to the shader mode."""

    value = str(direction).strip().lower()
    mode = _BLINDS_DIRECTION_MODES.get(value)
    if mode is None:
        raise ValueError(f"unknown resolved Blinds direction: {direction!r}")
    return mode


def _blinds_feather(parameters: Mapping[str, object]) -> float:
    """Read the resolved shader feather without a renderer-side UI fallback."""

    raw = parameters.get("feather")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("Blinds requires resolved numeric parameter 'feather'")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError("Blinds feather must be finite")
    if not _MIN_FEATHER <= value <= _MAX_FEATHER:
        raise ValueError(
            f"Blinds feather must be between {_MIN_FEATHER} and {_MAX_FEATHER}"
        )
    return value


def _blinds_grid(logical_size: tuple[float, float]) -> tuple[int, int]:
    """Preserve the compositor Blinds grid derived from display aspect ratio."""

    if len(logical_size) != 2:
        raise ValueError("Blinds logical size must contain width and height")
    width, height = (float(value) for value in logical_size)
    if not math.isfinite(width) or not math.isfinite(height):
        raise ValueError("Blinds logical size must be finite")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Blinds logical size must be positive")

    # GLCompositorBlindsTransition historically used its default slat_cols=7,
    # doubled it, then derived row count from the target aspect ratio.  Its
    # slat_rows constructor value never participated in the effective grid.
    cols = max(2, _AUTHORED_SLAT_COLS * 2)
    aspect = height / max(1.0, width)
    rows = max(2, int(round(cols * aspect)))
    return cols, rows


class QuickBlindsRenderer:
    transition_id = "blinds"

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
        parameters = frame.run.request.parameter_dict()
        feather = _blinds_feather(parameters)
        direction = _blinds_direction_mode(frame.run.request.direction)
        cols, rows = _blinds_grid(frame.logical_size)

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
        gl.glUniform2f(uniforms["u_grid"], float(cols), float(rows))
        gl.glUniform1f(uniforms["u_feather"], feather)
        gl.glUniform1i(uniforms["u_direction"], direction)
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
            blinds_program.fragment_source,
            label="Quick Blinds",
        )
        self._program = program
        try:
            # u_resolution exists in the legacy shader source but is not read
            # by that shader and may be optimized out.  Do not turn an unused
            # compatibility uniform into a new runtime requirement.
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_grid",
                "u_feather",
                "u_direction",
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
                    "Quick Blinds uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickBlindsRenderer:
    return QuickBlindsRenderer()
