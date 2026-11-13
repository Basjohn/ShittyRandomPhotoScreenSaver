"""Loose-uniform calls over a pass block (N1.6), for harnesses and tests that draw a converted program by name.

A program whose loose uniforms became one std140 pass block (``rendering.gl_programs.portable``) has no uniform
locations for them any more, so a harness that set them with ``glUniform*`` would draw with zeros. ``PassBlockGL(gl)``
stands in for ``OpenGL.GL`` there: ``register(program, layout, initial)`` names the program's block (and what it starts
from), then ``glGetUniformLocation`` gives each block member a location of its own (never negative), the ``glUniform*``
and ``glProgramUniform*`` calls set that member as the loose uniform took the call (matrices column-major, or
transposed when the call says so), and every draw of a registered program first binds its packed block at the pass
block's binding from a buffer of its own. Every other call, and every name a block does not hold, goes to GL.

Harness-only: the product packs its blocks itself (``PassBlocks``)."""
from __future__ import annotations

import ctypes
import re

import numpy as np

from rendering.gl_programs.portable import pack_block
from rendering.gl_programs.scene3d import SCENE3D_PASS_BLOCK_BINDING

_TOKEN = 0x40000000                      # far above any location a driver hands out
_SET = re.compile(r"gl(Program)?Uniform(Matrix)?([1234])(f|i|ui)(v?)$")


class PassBlockGL:
    def __init__(self, gl) -> None:
        self._gl = gl
        self._blocks: dict[int, tuple[object, dict]] = {}
        self._tokens: dict[int, tuple[int, str]] = {}
        self._buffer = 0

    def __getattr__(self, name):
        attribute = getattr(self._gl, name)
        match = _SET.match(name)
        if match is not None:
            program_call, matrix, size, _kind, vector = match.groups()
            return self._setter(attribute, bool(program_call), bool(matrix), int(size), bool(vector))
        if name.startswith("glDraw"):
            def draw(*args, **kwargs):
                self._bind(self._current_program())
                return attribute(*args, **kwargs)
            return draw
        return attribute

    def _current_program(self) -> int:
        """GL's current program (owners outside the harness switch it with their own GL calls)."""
        value = self._gl.glGetIntegerv(self._gl.GL_CURRENT_PROGRAM)
        return int(np.asarray(value).ravel()[0])

    def register(self, program: int, layout, initial: dict | None = None) -> None:
        """``program`` draws with ``layout``'s pass block, its members starting from ``initial`` (else zero)."""
        self._blocks[int(program)] = (layout, dict(initial or {}))

    def values(self, program: int) -> dict:
        return self._blocks[int(program)][1]

    def glGetUniformLocation(self, program, name):
        program = int(program)
        name = name.decode() if isinstance(name, bytes) else str(name)
        held = self._blocks.get(program)
        if held is not None and name in {field for field, _kind in held[0].fields}:
            token = _TOKEN + len(self._tokens)
            for known, key in self._tokens.items():
                if key == (program, name):
                    return known
            self._tokens[token] = (program, name)
            return token
        return self._gl.glGetUniformLocation(program, name)

    def _setter(self, call, program_call: bool, matrix: bool, size: int, vector: bool):
        def set_(*args):
            location, rest = (args[1], args[2:]) if program_call else (args[0], args[1:])
            key = self._tokens.get(int(location)) if isinstance(location, (int, np.integer)) else None
            if key is None:
                return call(*args)
            if matrix:
                _count, transpose, value = rest
                values = np.asarray(_floats(value), dtype=np.float32).reshape(size, size)
                values = values.T if transpose else values           # memory order is column-major for GL
                value = tuple(float(v) for v in values.ravel())
            elif vector:
                _count, value = rest
                value = tuple(_floats(value))
                value = value[0] if len(value) == 1 else value
            else:
                value = rest[0] if len(rest) == 1 else tuple(rest)
            self._blocks[key[0]][1][key[1]] = value
        return set_

    def _bind(self, program: int) -> None:
        held = self._blocks.get(program)
        if held is None:
            return
        layout, values = held
        data = pack_block(layout, values)
        gl = self._gl
        if not self._buffer:
            name = (ctypes.c_uint * 1)()
            gl.glCreateBuffers(1, name)
            self._buffer = int(name[0])
        gl.glNamedBufferData(self._buffer, len(data), data, gl.GL_DYNAMIC_DRAW)
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_PASS_BLOCK_BINDING, self._buffer)

    def release(self) -> None:
        if self._buffer:
            self._gl.glBindBufferBase(self._gl.GL_UNIFORM_BUFFER, SCENE3D_PASS_BLOCK_BINDING, 0)
            self._gl.glDeleteBuffers(1, [self._buffer])
            self._buffer = 0


def _floats(value):
    if isinstance(value, ctypes.Array):
        return list(value)
    return np.asarray(value, dtype=np.float64).ravel().tolist()


__all__ = ["PassBlockGL"]
