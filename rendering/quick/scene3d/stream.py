"""One persistently mapped, fenced stream ring for small per-frame buffer payloads.

A consumer writes a frame's changing bytes (a uniform block, a std430 record array) into
coherent mapped memory and binds that range: one ``memmove`` and one multi-bind instead
of re-specifying a buffer per upload. Multi-bind (``glBindBuffersRange``) never touches the
generic buffer binding, so only the indexed point is saved and restored.

The storage is fixed: ``slots`` slots of ``slot_bytes``. Writes advance through the current
slot. A slot is retired with one fence once nothing still binds it, and it is written again
only after that fence signals (a blocking bounded wait, never a poll). It holds several
frames, so a fence is placed every few dozen frames, not per frame.

"Nothing still binds it" is enforced, not trusted: every write happens inside ``bound``,
which restores the previous binding on exit, so once the outermost ``bound`` has exited no
later command can read the ring. Slots rotate only there. One outermost ``bound`` may write
at most ``hold_bytes``; more is a loud error, never a silent overwrite.

Nothing is allocated until a consumer first writes (or warms); ``release`` returns the ring
to zero and a later write rebuilds it.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from typing import Iterator

from OpenGL import GL as gl
from OpenGL.raw.GL.VERSION import GL_4_4 as _gl44

from rendering.quick import gl_query

_MAP_FLAGS = gl.GL_MAP_WRITE_BIT | gl.GL_MAP_PERSISTENT_BIT | gl.GL_MAP_COHERENT_BIT
# A slot is reused three rotations (dozens of frames) after its fence: waiting at all means
# the GPU is that far behind, and a second is already a hang, not a slow frame.
_FENCE_TIMEOUT_NS = 1_000_000_000

_BINDINGS = {
    int(gl.GL_UNIFORM_BUFFER): (gl.GL_UNIFORM_BUFFER_BINDING, gl.GL_UNIFORM_BUFFER_START,
                                gl.GL_UNIFORM_BUFFER_SIZE, gl.GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT),
    int(gl.GL_SHADER_STORAGE_BUFFER): (gl.GL_SHADER_STORAGE_BUFFER_BINDING, gl.GL_SHADER_STORAGE_BUFFER_START,
                                       gl.GL_SHADER_STORAGE_BUFFER_SIZE,
                                       gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT),
}


class StreamRing:
    def __init__(self, label: str, *, slots: int = 4, slot_bytes: int = 16384, hold_bytes: int = 4096) -> None:
        if slots < 2 or hold_bytes <= 0 or hold_bytes > slot_bytes:
            raise ValueError(f"{label}: invalid stream ring shape")
        self.label = label
        self.slots, self.slot_bytes, self.hold_bytes = slots, slot_bytes, hold_bytes
        self._buffer = 0
        self._address = 0
        self._alignment: dict[int, int] = {}
        self._fences: list[object | None] = [None] * slots
        self._slot = 0
        self._cursor = 0
        self._hold_end = 0
        self._depth = 0
        # Reused multi-bind argument arrays: the hot bind is one raw call, no array building.
        self._names = (ctypes.c_uint * 1)()
        self._offsets = (ctypes.c_ssize_t * 1)()
        self._sizes = (ctypes.c_ulonglong * 1)()

    @property
    def has_resources(self) -> bool:
        return bool(self._buffer) or any(fence is not None for fence in self._fences)

    @property
    def capacity(self) -> int:
        return self.slots * self.slot_bytes

    def warm(self) -> bool:
        """One warm-up step: True when the ring already exists, else allocate it."""
        if self._buffer:
            return True
        self._allocate()
        return False

    @contextmanager
    def bound(self, target: int, binding: int, data: bytes) -> Iterator[None]:
        """Write ``data`` and bind it to ``binding`` of ``target`` for the scope; restore after."""
        names = _BINDINGS[int(target)]
        previous = (
            gl_query.get_indexed_int(names[0], binding),
            gl_query.get_indexed_int64(names[1], binding),
            gl_query.get_indexed_int64(names[2], binding),
        )
        if self._depth == 0:
            self._begin_hold()
        self._depth += 1
        try:
            self.rebind(target, binding, data)
            yield
        finally:
            self._depth -= 1
            self._restore(target, binding, *previous)

    def rebind(self, target: int, binding: int, data: bytes) -> None:
        """Write a new copy of ``data`` and bind it in place of the current range (inside ``bound``)."""
        if self._depth <= 0:
            raise RuntimeError(f"{self.label}: stream writes happen inside bound()")
        size = len(data)
        alignment = self._alignment[int(target)]
        offset = -(-self._cursor // alignment) * alignment
        if size <= 0 or offset + size > self._hold_end:
            raise RuntimeError(f"{self.label}: {size} bytes exceed the stream ring's per-frame capacity")
        ctypes.memmove(self._address + offset, data, size)
        self._cursor = offset + size
        self._names[0], self._offsets[0], self._sizes[0] = self._buffer, offset, size
        # Raw entry point: ring-owned name, aligned in-range offset, valid target (no error to check).
        _gl44.glBindBuffersRange(target, binding, 1, self._names, self._offsets, self._sizes)

    def release(self) -> None:
        """Delete fences and the buffer. A failed deletion keeps its handle for a later retry."""
        for index, fence in enumerate(self._fences):
            if fence is not None:
                gl.glDeleteSync(fence)
                self._fences[index] = None
        if self._buffer:
            gl.glDeleteBuffers(1, [self._buffer])  # deletion unmaps
            self._buffer = 0
        self._address = 0
        self._slot = self._cursor = self._hold_end = 0

    def _begin_hold(self) -> None:
        if not self._buffer:
            self._allocate()
        slot_end = (self._slot + 1) * self.slot_bytes
        if self._cursor + self.hold_bytes > slot_end:
            # Every command reading this slot has been submitted: the fence covers them all.
            self._fences[self._slot] = gl.glFenceSync(gl.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
            self._slot = (self._slot + 1) % self.slots
            self._wait(self._slot)
            self._cursor = self._slot * self.slot_bytes
        self._hold_end = self._cursor + self.hold_bytes

    def _wait(self, slot: int) -> None:
        fence = self._fences[slot]
        if fence is None:
            return
        status = gl.glClientWaitSync(fence, gl.GL_SYNC_FLUSH_COMMANDS_BIT, _FENCE_TIMEOUT_NS)
        if status not in (gl.GL_ALREADY_SIGNALED, gl.GL_CONDITION_SATISFIED):
            raise RuntimeError(f"{self.label}: stream slot {slot} is still in use by the GPU")
        gl.glDeleteSync(fence)
        self._fences[slot] = None

    def _allocate(self) -> None:
        name = (ctypes.c_uint * 1)()
        gl.glCreateBuffers(1, name)
        self._buffer = int(name[0])
        if not self._buffer:
            raise RuntimeError(f"{self.label} stream ring allocation failed")
        try:
            gl.glNamedBufferStorage(self._buffer, self.capacity, None, _MAP_FLAGS)
            address = gl.glMapNamedBufferRange(self._buffer, 0, self.capacity, _MAP_FLAGS)
            if not address:
                raise RuntimeError(f"{self.label} stream ring mapping failed")
            self._address = int(address)
            self._alignment = {target: gl_query.get_int(names[3]) for target, names in _BINDINGS.items()}
        except Exception:
            self.release()
            raise
        self._slot = self._cursor = self._hold_end = 0

    def _restore(self, target: int, binding: int, buffer: int, start: int, size: int) -> None:
        self._names[0] = buffer
        if buffer and size:
            self._offsets[0], self._sizes[0] = start, size
            _gl44.glBindBuffersRange(target, binding, 1, self._names, self._offsets, self._sizes)
        else:
            # A whole-buffer binding (or none) reports size 0.
            _gl44.glBindBuffersBase(target, binding, 1, self._names)
