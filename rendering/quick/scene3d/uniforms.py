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
from typing import Callable, Iterator, Mapping

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_PASS_BLOCK_BINDING, Scene3DBlockLayout
from rendering.quick.scene3d.stream import StreamRing

# Well clear of the points Qt Quick's own shaders use; restored after every use anyway.
SCENE3D_UNIFORM_BINDING = 15
# A pass block's binding (``SCENE3D_PASS_BLOCK_BINDING``): its program's sources state it, the pass binds it.
PASS_BLOCK_BINDING = SCENE3D_PASS_BLOCK_BINDING
# One bound scope (a pass's draws, each with its own copy at the uniform offset alignment, at most 256) holds at most
# this many bytes; a slot holds four scopes' worth, so a fence falls every few dozen passes.
_PASS_HOLD = 4096


def declares_pass_block(source: str) -> bool:
    """Whether a shader source declares a pass block (``Scene3DBlockLayout.glsl(PASS_BLOCK_BINDING)``)."""
    return f"binding = {PASS_BLOCK_BINDING}) uniform" in source


class PassBlocks:
    """A program owner's pass blocks (N1.6). A program whose loose uniforms became one std140 block (Vulkan GLSL has
    no loose uniforms) declares it with ``layout.glsl(PASS_BLOCK_BINDING)``; the pass that drew with ``glUniform*``
    calls packs the same values, from the same place in the frame, and draws inside ``bound(layout.pack(values))``:
    one write into a small fenced stream ring (``stream.py``) and one bind, instead of a call per uniform. ``rebind``
    gives a later draw of the scope other values (each draw already submitted keeps its own copy). The point is left
    unbound afterwards: nothing is read back and nothing inherits it. Nothing is allocated until ``warm`` or the first
    ``bound``; ``release`` returns it to zero."""

    def __init__(self, label: str) -> None:
        self._ring = StreamRing(f"{label} pass blocks", slots=4, slot_bytes=4 * _PASS_HOLD, hold_bytes=_PASS_HOLD)

    @property
    def has_resources(self) -> bool:
        return self._ring.has_resources

    def warm(self) -> bool:
        """One warm-up step: True when the ring already exists, else allocate it."""
        return self._ring.warm()

    @contextmanager
    def bound(self, data: bytes) -> Iterator[Callable[[bytes], None]]:
        ring = self._ring
        with ring.bound(gl.GL_UNIFORM_BUFFER, PASS_BLOCK_BINDING, data, restore=False):
            yield lambda values: ring.rebind(gl.GL_UNIFORM_BUFFER, PASS_BLOCK_BINDING, values)

    def release(self) -> None:
        self._ring.release()


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
    def bound(self, values: Mapping[str, object] | bytes) -> Iterator[None]:
        """Bind resolved values or a packed immutable frame reused across passes."""
        data = values if isinstance(values, bytes) else self.layout.pack(values)
        if len(data) != self.layout.size:
            raise ValueError(f"{self.label} requires {self.layout.size} packed bytes")
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
        self.update_packed(self.layout.patch(self._packed, values))

    def update_packed(self, data: bytes) -> None:
        """Rebind a resolved immutable frame inside the current scope."""
        if self._packed is None:
            raise RuntimeError(f"{self.label} is not bound")
        if len(data) != self.layout.size:
            raise ValueError(f"{self.label} requires {self.layout.size} packed bytes")
        self._packed = data
        self._stream.rebind(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, self._packed)

    def release(self) -> None:
        """Forget attached programs (their names may be reused); release an owned ring."""
        self._attached.clear()
        if self._owns_stream:
            self._stream.release()
