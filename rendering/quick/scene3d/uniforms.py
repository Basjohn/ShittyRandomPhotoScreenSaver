"""Shared per-frame uniform blocks with scoped binding and named partial updates.

A renderer declares its per-frame values once as a ``Scene3DBlockLayout`` (pure,
in ``rendering.gl_programs.scene3d``), puts ``layout.glsl()`` in each program and
draws its passes inside ``block.bound(values)``. That replaces a dozen
``glUniform*`` calls per pass with one packed write and one bind: the render-thread
Python cost Visualizer modes need to afford 3D.

The bytes travel through a ``StreamRing`` (persistently mapped, fenced; see
``stream.py``). A renderer with several blocks hands them one shared ring and
releases it itself; a block given none owns a private one. Time-varying ghost passes
update selected members with ``update_fields``: a patched copy of the block is written
and rebound, so draws already submitted keep reading the values they were given.

The block sits on binding point ``SCENE3D_UNIFORM_BINDING``; ``bound`` restores that
point's previous buffer range and never touches the generic uniform-buffer binding,
so no host fence has to know about it.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Mapping

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import Scene3DBlockLayout
from rendering.quick.scene3d.stream import StreamRing

# Well clear of the points Qt Quick's own shaders use; restored after every use anyway.
SCENE3D_UNIFORM_BINDING = 15


class UniformBlock:
    def __init__(self, layout: Scene3DBlockLayout, label: str, stream: StreamRing | None = None) -> None:
        self.layout = layout
        self.label = label
        self._owns_stream = stream is None
        self._stream = stream if stream is not None else StreamRing(label)
        self._attached: set[int] = set()
        self._packed: bytes | None = None

    @property
    def has_resources(self) -> bool:
        return self._stream.has_resources

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
        with self._stream.bound(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, data):
            outer, self._packed = self._packed, data
            try:
                yield
            finally:
                self._packed = outer

    def update_fields(self, values: Mapping[str, object]) -> None:
        """Rebind the block with selected fields changed (inside ``bound``)."""
        if self._packed is None:
            raise RuntimeError(f"{self.label} is not bound")
        data = bytearray(self._packed)
        for offset, part in self.layout.pack_fields(values):
            data[offset:offset + len(part)] = part
        self._packed = bytes(data)
        self._stream.rebind(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, self._packed)

    def release(self) -> None:
        """Forget attached programs (their names may be reused); release an owned ring."""
        self._attached.clear()
        if self._owns_stream:
            self._stream.release()
