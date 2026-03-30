"""Shared OpenGL uniform upload helpers for visualizer renderers.

Extracted from per-renderer duplicated helpers (spectrum, oscilloscope,
sine_wave, blob, bubble) to eliminate copy-paste.
"""
from __future__ import annotations


def set1f(gl, u, name, val):
    """Upload a single float uniform if the location is valid."""
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(val))


def set1i(gl, u, name, val):
    """Upload a single int uniform if the location is valid."""
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1i(loc, int(val))


def set1fv(gl, u, name, values, count):
    """Upload a float array uniform if the location is valid."""
    loc = u.get(name, -1)
    if loc >= 0:
        import ctypes
        arr = (ctypes.c_float * count)(*[float(v) for v in values[:count]])
        gl.glUniform1fv(loc, count, arr)


def set4f(gl, u, name, x, y, z, w):
    """Upload a vec4 uniform if the location is valid."""
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform4f(loc, float(x), float(y), float(z), float(w))


def set_color4(gl, u, name, qc):
    """Upload a QColor as a vec4 uniform if the location is valid."""
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform4f(loc, float(qc.redF()), float(qc.greenF()),
                        float(qc.blueF()), float(qc.alphaF()))
