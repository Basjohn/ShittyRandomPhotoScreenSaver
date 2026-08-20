"""Lazy Quick renderer for the authored single-slab 3D BlockSpin effect."""

from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from rendering.gl_programs.blockspin_program import (
    BLOCK_SPIN_BOX_VERTEX_COUNT,
    BLOCK_SPIN_BOX_VERTICES,
    BLOCK_SPIN_FRAGMENT_SOURCE,
    BLOCK_SPIN_QUICK_VERTEX_SOURCE,
    BLOCK_SPIN_VERTEX_STRIDE_FLOATS,
    block_spin_progress,
)
from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_STATES = {
    "left": (0, 1.0),
    "right": (0, -1.0),
    "up": (1, 1.0),
    "down": (1, -1.0),
    "diag_tl_br": (2, 1.0),
    "diag_tr_bl": (3, -1.0),
}


_VOID_FRAGMENT_SOURCE = """#version 410 core
out vec4 FragColor;

void main() {
    FragColor = vec4(0.0, 0.0, 0.0, 1.0);
}
"""


def _block_spin_direction_state(direction: object) -> tuple[int, float]:
    value = str(direction).strip().lower()
    state = _DIRECTION_STATES.get(value)
    if state is None:
        raise ValueError(f"unknown resolved 3D Block Spins direction: {direction!r}")
    return state


class QuickBlockSpinsRenderer:
    transition_id = "block_spins"

    def __init__(self) -> None:
        self._void_program = 0
        self._slab_program = 0
        self._box_vao = 0
        self._box_vbo = 0
        self._void_uniforms: dict[str, int] = {}
        self._slab_uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(
            self._void_program
            or self._slab_program
            or self._box_vao
            or self._box_vbo
        )

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._slab_program:
            self._initialize()
        axis_mode, spin_direction = _block_spin_direction_state(
            frame.run.request.direction
        )
        spin = block_spin_progress(frame.sample.eased_progress)

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glUseProgram(self._void_program)
        gl.glUniformMatrix4fv(
            self._void_uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(
            self._void_uniforms["uItemSize"],
            *frame.logical_size,
        )
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

        gl.glDepthMask(gl.GL_TRUE)
        gl.glClearDepth(1.0)
        gl.glClear(gl.GL_DEPTH_BUFFER_BIT)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LESS)

        uniforms = self._slab_uniforms
        gl.glUseProgram(self._slab_program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["uAngle"],
            math.pi * spin * spin_direction,
        )
        gl.glUniform1f(uniforms["uSpecDirection"], spin_direction)
        gl.glUniform1i(uniforms["uAxisMode"], axis_mode)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTexture"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTexture"], 1)
        gl.glBindVertexArray(self._box_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, BLOCK_SPIN_BOX_VERTEX_COUNT)

    def release_resources(self) -> None:
        errors: list[str] = []
        for attribute, delete in (
            ("_box_vbo", lambda value: gl.glDeleteBuffers(1, [value])),
            ("_box_vao", lambda value: gl.glDeleteVertexArrays(1, [value])),
            ("_slab_program", gl.glDeleteProgram),
            ("_void_program", gl.glDeleteProgram),
        ):
            value = int(getattr(self, attribute))
            if not value:
                continue
            try:
                delete(value)
            except Exception as exc:
                errors.append(f"{attribute}:{type(exc).__name__}:{exc}")
            else:
                setattr(self, attribute, 0)
        if not self._slab_program:
            self._slab_uniforms.clear()
        if not self._void_program:
            self._void_uniforms.clear()
        if errors:
            raise RuntimeError(
                "Quick 3D Block Spins cleanup incomplete: " + " | ".join(errors)
            )

    def _initialize(self) -> None:
        try:
            self._void_program = compile_program(
                QUICK_TRANSITION_VERTEX_SOURCE,
                _VOID_FRAGMENT_SOURCE,
                label="Quick 3D Block Spins void",
            )
            self._slab_program = compile_program(
                BLOCK_SPIN_QUICK_VERTEX_SOURCE,
                BLOCK_SPIN_FRAGMENT_SOURCE,
                label="Quick 3D Block Spins slab",
            )
            self._void_uniforms = self._uniform_locations(
                self._void_program,
                ("uMatrix", "uItemSize"),
            )
            self._slab_uniforms = self._uniform_locations(
                self._slab_program,
                (
                    "uMatrix",
                    "uItemSize",
                    "uAngle",
                    "uSpecDirection",
                    "uAxisMode",
                    "uOldTexture",
                    "uNewTexture",
                ),
            )

            vertex_data = (ctypes.c_float * len(BLOCK_SPIN_BOX_VERTICES))(
                *BLOCK_SPIN_BOX_VERTICES
            )
            self._box_vao = int(gl.glGenVertexArrays(1))
            self._box_vbo = int(gl.glGenBuffers(1))
            if not self._box_vao or not self._box_vbo:
                raise RuntimeError("Quick 3D Block Spins box allocation failed")
            gl.glBindVertexArray(self._box_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._box_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(vertex_data),
                vertex_data,
                gl.GL_STATIC_DRAW,
            )
            stride = BLOCK_SPIN_VERTEX_STRIDE_FLOATS * ctypes.sizeof(
                ctypes.c_float
            )
            for location, size, offset in (
                (0, 3, 0),
                (1, 3, 3 * ctypes.sizeof(ctypes.c_float)),
                (2, 2, 6 * ctypes.sizeof(ctypes.c_float)),
            ):
                gl.glEnableVertexAttribArray(location)
                gl.glVertexAttribPointer(
                    location,
                    size,
                    gl.GL_FLOAT,
                    gl.GL_FALSE,
                    stride,
                    ctypes.c_void_p(offset),
                )
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)
        except Exception:
            self.release_resources()
            raise

    @staticmethod
    def _uniform_locations(
        program: int,
        names: tuple[str, ...],
    ) -> dict[str, int]:
        uniforms = {
            name: int(gl.glGetUniformLocation(program, name)) for name in names
        }
        missing = [name for name, location in uniforms.items() if location < 0]
        if missing:
            raise RuntimeError(
                "Quick 3D Block Spins uniforms are incomplete: "
                + ", ".join(missing)
            )
        return uniforms


def create_transition_renderer() -> QuickBlockSpinsRenderer:
    return QuickBlockSpinsRenderer()
