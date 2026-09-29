"""The shared particle pass: instanced camera-facing streaks or soft sprites, added as light.

An effect's particle program draws one instance per particle over the item quad's
four corners (``aPosition`` in [0, 1]^2 is the ``corner`` of ``sceneParticleStreak``).
Its emitter (birth, heading, speed, life, colour) stays in its own shaders; the flight
and the streak come from the library, so every effect's particles move alike. The
pass leaves depth untouched and adds colour, and alpha too (emitted light for the
bloom), so particles never occlude and bloom exactly where they glow.
"""
from __future__ import annotations

from OpenGL import GL as gl

from .passes import blend_scope


def particle_budget(count: int, detail) -> int:
    """How many of an effect's ``count`` particles its 3D Detail tier draws."""
    return round(count * detail.particles)


def draw_particles(frame, count: int) -> None:
    """Draw ``count`` particles with the program already in use."""
    gl.glDepthMask(gl.GL_FALSE)
    gl.glBindVertexArray(frame.quad_vao)
    with blend_scope(gl.GL_FUNC_ADD, accumulate_alpha=True):
        gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, count)
