"""The shared planar shadow pass: soft shadows of rigid pieces on the photograph.

An effect's shadow program draws one instance per piece over the item quad's four
corners: its vertex shader builds the piece (``ScenePiece``) and places the quad with
``scenePieceShadow``; its fragment shader draws its own lit photograph darkened by
``sceneSoftRect(local, feather)`` times its strength. Drawn with MIN blending, so
overlapping shadows never darken twice and the photograph is never brightened.
"""
from __future__ import annotations

from OpenGL import GL as gl

from .passes import blend_scope


def draw_planar_shadows(frame, count: int) -> None:
    """Draw ``count`` pieces' shadows with the program already in use."""
    gl.glBindVertexArray(frame.quad_vao)
    with blend_scope(gl.GL_MIN):
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count)
