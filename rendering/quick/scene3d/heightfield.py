"""One lazy immutable-storage height texture, updated only on authoring changes.

The consumer supplies a validated canonical field's packed float32 data. There
is no simulation, clock, mesh cache or mode dependency at this shared owner.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes

from OpenGL import GL as gl

from rendering.quick import gl_query


class HeightfieldTexture:
    def __init__(self, label: str, components: int = 1) -> None:
        if isinstance(components, bool) or not isinstance(components, int) or components not in (1, 2):
            raise ValueError("heightfield texture components must be 1 or 2")
        self.label = label
        self._components = components
        self._texture = 0
        self._size = 0
        self._data: bytes | None = None
        self.uploads = 0

    @property
    def has_resources(self) -> bool:
        return bool(self._texture)

    @property
    def texture_id(self) -> int:
        return self._texture

    @property
    def components(self) -> int:
        return self._components

    def ensure(self, size: int, data: bytes) -> int:
        if isinstance(size, bool) or not isinstance(size, int) or not 2 <= size <= 65:
            raise ValueError(f"{self.label}: heightfield size must be within 2..65")
        if not isinstance(data, bytes) or len(data) != size * size * self._components * 4:
            raise ValueError(f"{self.label}: heightfield data must contain complete float32 texels for {self._components} components")
        if self._texture and size == self._size and data is self._data:
            return self._texture
        if self._texture and size == self._size and data == self._data:
            self._data = data
            return self._texture
        if self._texture and size != self._size:
            self.release()
        if not self._texture:
            name = ctypes.c_uint(0)
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            self._texture = int(name.value)
            if not self._texture:
                raise RuntimeError(f"{self.label}: heightfield texture allocation failed")
            # Retain the handle on failure: release() is still its deletion owner.
            internal_format = gl.GL_R32F if self._components == 1 else gl.GL_RG32F
            gl.glTextureStorage2D(self._texture, 1, internal_format, size, size)
            gl.glTextureParameteri(self._texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTextureParameteri(self._texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTextureParameteri(self._texture, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTextureParameteri(self._texture, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            self._size = size
        prior = {name: gl_query.get_int(name) for name in (
            gl.GL_PIXEL_UNPACK_BUFFER_BINDING, gl.GL_UNPACK_ALIGNMENT,
            gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS,
        )}
        try:
            gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 4)
            for name in (gl.GL_UNPACK_ROW_LENGTH, gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS):
                gl.glPixelStorei(name, 0)
            external_format = gl.GL_RED if self._components == 1 else gl.GL_RG
            gl.glTextureSubImage2D(self._texture, 0, 0, 0, size, size, external_format, gl.GL_FLOAT, data)
        finally:
            gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, prior[gl.GL_PIXEL_UNPACK_BUFFER_BINDING])
            for name in (gl.GL_UNPACK_ALIGNMENT, gl.GL_UNPACK_ROW_LENGTH,
                         gl.GL_UNPACK_SKIP_ROWS, gl.GL_UNPACK_SKIP_PIXELS):
                gl.glPixelStorei(name, prior[name])
        self._data = data
        self.uploads += 1
        return self._texture

    @contextmanager
    def bound(self, unit: int):
        if not self._texture or self._data is None:
            raise RuntimeError(f"{self.label}: cannot sample an unprepared heightfield")
        active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0 + int(unit))
        prior_texture = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        prior_sampler = gl_query.get_indexed_int(gl.GL_SAMPLER_BINDING, int(unit))
        try:
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture)
            gl.glBindSampler(int(unit), 0)
            yield self._texture
        finally:
            gl.glBindSampler(int(unit), prior_sampler)
            gl.glBindTexture(gl.GL_TEXTURE_2D, prior_texture)
            gl.glActiveTexture(active)

    def release(self) -> None:
        if self._texture:
            gl.glDeleteTextures([self._texture])
            self._texture = 0
        self._size = 0
        self._data = None


__all__ = ["HeightfieldTexture"]
