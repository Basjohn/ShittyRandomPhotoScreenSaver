"""Lazy Quick renderer for the canonical authored Diffuse shader."""

from __future__ import annotations

from collections.abc import Mapping
import math

from OpenGL import GL as gl

from rendering.gl_programs.diffuse_program import diffuse_program
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_MIN_BLOCK_SIZE = 1
_SHAPE_MODES = frozenset(range(6))


def _diffuse_block_size(parameters: Mapping[str, object]) -> int:
    raw = parameters.get("block_size")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("Diffuse requires resolved integer parameter 'block_size'")
    if raw < _MIN_BLOCK_SIZE:
        raise ValueError("Diffuse block_size must be positive")
    return raw


def _diffuse_shape_mode(parameters: Mapping[str, object]) -> int:
    raw = parameters.get("shape_mode")
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError("Diffuse requires resolved integer parameter 'shape_mode'")
    if raw not in _SHAPE_MODES:
        raise ValueError("Diffuse shape_mode must be between 0 and 5")
    return raw


def _diffuse_grid(
    logical_size: tuple[float, float],
    block_size: int,
) -> tuple[int, int]:
    if len(logical_size) != 2:
        raise ValueError("Diffuse logical size must contain width and height")
    width, height = (float(value) for value in logical_size)
    if not math.isfinite(width) or not math.isfinite(height):
        raise ValueError("Diffuse logical size must be finite")
    if width <= 0.0 or height <= 0.0:
        raise ValueError("Diffuse logical size must be positive")
    size = int(block_size)
    if size < _MIN_BLOCK_SIZE:
        raise ValueError("Diffuse block_size must be positive")
    return (
        max(1, math.ceil(width / size)),
        max(1, math.ceil(height / size)),
    )


class QuickDiffuseRenderer:
    transition_id = "diffuse"

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
        block_size = _diffuse_block_size(parameters)
        shape_mode = _diffuse_shape_mode(parameters)
        cols, rows = _diffuse_grid(frame.logical_size, block_size)
        uniforms = self._uniforms

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"], float(frame.sample.eased_progress)
        )
        gl.glUniform2f(uniforms["u_grid"], float(cols), float(rows))
        gl.glUniform1i(uniforms["u_shapeMode"], shape_mode)
        resolution = uniforms.get("u_resolution", -1)
        if resolution >= 0:
            gl.glUniform2f(
                resolution,
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
            diffuse_program.fragment_source,
            label="Quick Diffuse",
        )
        self._program = program
        try:
            required = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_grid",
                "u_shapeMode",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in (*required, "u_resolution")
            }
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Diffuse uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickDiffuseRenderer:
    return QuickDiffuseRenderer()
