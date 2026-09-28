"""Cheap GL state queries for per-frame fences.

PyOpenGL's checked getters build an output array per call (~13 us each on the
render thread); the raw entry points writing into a small ctypes buffer cost
~2.7 us. A transition frame captures ~20 states, so this is most of the fence's
Python cost. Buffers are allocated per call: each display has its own render
thread. Only valid enums are queried, so the skipped error check loses nothing.
"""
from __future__ import annotations

import ctypes

from OpenGL.raw.GL.VERSION import GL_1_0 as _gl10
from OpenGL.raw.GL.VERSION import GL_3_0 as _gl30
from OpenGL.raw.GL.VERSION import GL_3_2 as _gl32


def get_int(name: int) -> int:
    value = ctypes.c_int()
    _gl10.glGetIntegerv(name, ctypes.byref(value))
    return value.value


def get_ints(name: int, count: int) -> tuple[int, ...]:
    values = (ctypes.c_int * count)()
    _gl10.glGetIntegerv(name, values)
    return tuple(values)


def get_bool(name: int) -> bool:
    value = (ctypes.c_ubyte * 4)()
    _gl10.glGetBooleanv(name, value)
    return bool(value[0])


def get_bools(name: int, count: int) -> tuple[bool, ...]:
    values = (ctypes.c_ubyte * count)()
    _gl10.glGetBooleanv(name, values)
    return tuple(bool(value) for value in values)


def get_float(name: int) -> float:
    value = ctypes.c_float()
    _gl10.glGetFloatv(name, ctypes.byref(value))
    return value.value


def get_floats(name: int, count: int) -> tuple[float, ...]:
    values = (ctypes.c_float * count)()
    _gl10.glGetFloatv(name, values)
    return tuple(values)


def is_enabled(capability: int) -> bool:
    return bool(_gl10.glIsEnabled(capability))


def get_indexed_int(name: int, index: int) -> int:
    value = ctypes.c_int()
    _gl30.glGetIntegeri_v(name, index, ctypes.byref(value))
    return value.value


def get_indexed_int64(name: int, index: int) -> int:
    value = ctypes.c_int64()
    _gl32.glGetInteger64i_v(name, index, ctypes.byref(value))
    return value.value
