"""Blend scopes for 3D scene passes (MIN-blended shadows, additive light)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from OpenGL import GL as gl


@contextmanager
def blend_scope(equation: int, source: int = gl.GL_ONE, destination: int = gl.GL_ONE) -> Iterator[None]:
    """Blend one pass; alpha is left untouched. The consumer's fence restores the rest."""
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendEquationSeparate(equation, gl.GL_FUNC_ADD)
    gl.glBlendFuncSeparate(source, destination, gl.GL_ZERO, gl.GL_ONE)
    try:
        yield
    finally:
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE, gl.GL_ZERO)
        gl.glDisable(gl.GL_BLEND)
