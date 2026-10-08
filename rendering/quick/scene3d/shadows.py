"""Shared Scene3D shadow primitives.

Planar transition shadows use the photograph-darkening MIN-blend path below.
Extruded's retained overlay shadow is a different admitted primitive: all cuboid
faces project onto a transparent floor target and union their premultiplied
silhouette with MAX blending so overlap never compounds opacity.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
from collections.abc import Iterator, Sequence

from OpenGL import GL as gl

from .passes import blend_scope


def directional_shadow_vector(resolved_offset: Sequence[object], length: float) -> tuple[float, float]:
    """Return a world-space shadow vector using the canonical resolved direction only.

    The display owner has already projected ``widgets.shadows.direction`` into a signed card
    offset.  A Scene3D consumer keeps its own geometry magnitude, while this shared seam keeps
    the one global orientation authority: a cardinal direction has a zero perpendicular axis and
    a diagonal retains both signs.  It deliberately does not reuse the card offset's magnitude.
    """
    if len(resolved_offset) != 2:
        raise ValueError("resolved shadow offset needs two coordinates")
    magnitude = float(length)
    if not math.isfinite(magnitude) or magnitude < 0.0:
        raise ValueError("directional shadow length must be finite and non-negative")
    x, y = (float(value) for value in resolved_offset)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("resolved shadow offset must be finite")
    return (
        math.copysign(magnitude, x) if abs(x) > 1e-9 else 0.0,
        math.copysign(magnitude, y) if abs(y) > 1e-9 else 0.0,
    )


@contextmanager
def directional_shadow_pass() -> Iterator[None]:
    """Draw one projected silhouette as a single-alpha union in the scene target.

    Extruded projects all six box faces onto the floor so side faces fill the
    sweep between each base and shifted top footprint. Those triangles overlap.
    MAX blending over the transparent target keeps the premultiplied shadow
    colour/alpha exactly once at every covered sample rather than stacking a
    darker shadow for every overlapping triangle. The consumer's fragment pass
    emits premultiplied shadow colour specifically for this scope.
    """
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glDepthMask(gl.GL_FALSE)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendEquationSeparate(gl.GL_MAX, gl.GL_MAX)
    gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
    try:
        yield
    finally:
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparate(
            gl.GL_SRC_ALPHA,
            gl.GL_ONE_MINUS_SRC_ALPHA,
            gl.GL_ONE,
            gl.GL_ONE_MINUS_SRC_ALPHA,
        )


def draw_planar_shadows(frame, count: int) -> None:
    """Draw ``count`` pieces' shadows with the program already in use."""
    gl.glBindVertexArray(frame.quad_vao)
    with blend_scope(gl.GL_MIN):
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count)
