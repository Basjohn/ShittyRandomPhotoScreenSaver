"""Shared per-frame uniform blocks with scoped binding and named partial updates.

A renderer declares its per-frame values once as a ``Scene3DBlockLayout`` (pure,
in ``rendering.gl_programs.scene3d``), puts ``layout.glsl()`` in each program and
draws its passes inside ``block.bound(values)``. That replaces a dozen
``glUniform*`` calls per pass with one upload and one bind: the render-thread
Python cost Visualizer modes need to afford 3D.

Time-varying ghost passes may update only selected members of their own block.
Those DSA writes name the owned buffer explicitly and leave generic bindings alone.

Full block uploads re-specify the buffer (orphaning) to avoid reusing the previous
frame's storage; selected-field updates retain that storage. The block sits on binding point
``SCENE3D_UNIFORM_BINDING``; ``bound`` restores that point's previous buffer range
and the generic uniform-buffer binding, so no host fence has to know about it.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Mapping

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.quick import gl_query

# Well clear of the points Qt Quick's own shaders use; restored after every use anyway.
SCENE3D_UNIFORM_BINDING = 15


class UniformBlock:
    def __init__(self, layout: Scene3DBlockLayout, label: str) -> None:
        self.layout = layout
        self.label = label
        self._buffer = 0
        self._attached: set[int] = set()

    @property
    def has_resources(self) -> bool:
        return bool(self._buffer)

    def attach(self, program: int) -> None:
        """Point ``program``'s block at the shared binding (once per program)."""
        if program in self._attached:
            return
        index = int(gl.glGetUniformBlockIndex(program, self.layout.name))
        if index == int(gl.GL_INVALID_INDEX):
            raise RuntimeError(f"{self.label}: program {program} does not use block {self.layout.name}")
        gl.glUniformBlockBinding(program, index, SCENE3D_UNIFORM_BINDING)
        self._attached.add(program)

    @contextmanager
    def bound(self, values: Mapping[str, object]) -> Iterator[None]:
        data = self.layout.pack(values)
        generic = gl_query.get_int(gl.GL_UNIFORM_BUFFER_BINDING)
        previous = (
            gl_query.get_indexed_int(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_UNIFORM_BINDING),
            gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_START, SCENE3D_UNIFORM_BINDING),
            gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_SIZE, SCENE3D_UNIFORM_BINDING),
        )
        try:
            if not self._buffer:
                self._buffer = int(gl.glGenBuffers(1))
                if not self._buffer:
                    raise RuntimeError(f"{self.label} uniform buffer allocation failed")
            gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, self._buffer)
            gl.glBufferData(gl.GL_UNIFORM_BUFFER, len(data), data, gl.GL_STREAM_DRAW)
            gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, self._buffer)
            yield
        finally:
            buffer, start, size = previous
            if buffer and size:
                gl.glBindBufferRange(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, buffer, start, size)
            else:
                gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, buffer)
            gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, generic)

    def update_fields(self, values: Mapping[str, object]) -> None:
        """Update selected fields without relying on the generic uniform-buffer binding."""
        if not self._buffer:
            raise RuntimeError(f"{self.label} has no allocated uniform buffer")
        for offset, data in self.layout.pack_fields(values):
            gl.glNamedBufferSubData(self._buffer, offset, len(data), data)

    def release(self) -> None:
        """Delete the buffer; programs must be re-attached (their names may be reused)."""
        self._attached.clear()
        if self._buffer:
            gl.glDeleteBuffers(1, [self._buffer])
            self._buffer = 0
