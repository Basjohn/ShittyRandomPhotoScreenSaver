"""Motion trails: faint fading outlines of where moving pieces were a moment ago.

An effect draws its pieces a few more times at earlier moments of the run (a fixed real
time apart, ``scene3d_trail_ghosts``) with its ghost variant (``scene3d_ghost_fragment``
of its motion-writing shaders): each ghost a flat silhouette whose value is its fade, the
newest brightest, MAX-blended so the newest ghost wins where they overlap. A ghost knows
where its piece is *now* and draws nothing unless the piece has moved further than the
trail's line reaches, so a still or slow piece never trails or wears a halo, while a
dense field of moving pieces (Directional Pixel Accretion) still does. An edge filter
turns the silhouettes into soft light lines that fade with the ghost's age and lays them
over the photograph *before* the pieces draw, so a piece covers its own trail: only
where it has just been shows. Needs the scene target (``SceneTarget.scope``); the buffer
is sized from its allocation and dropped with the run.
"""
from __future__ import annotations

import ctypes
from typing import Callable, Iterable

from OpenGL import GL as gl

from rendering.quick import gl_query

from .passes import blend_scope
from .post import FULLSCREEN_VERTEX_SOURCE

# Edges between a ghost and what lies around it, as a soft line (``scene3d_trail_line``
# either side): bright white, as strong as the step in ghost value (the newest ghost's
# outline the strongest).
_EDGE_FRAGMENT = """#version 460 core
out vec4 FragColor;
uniform sampler2D uGhosts;
uniform ivec2 uSize;
uniform float uRadius;
uniform float uStrength;
float ghost(ivec2 texel) {
    return texelFetch(uGhosts, clamp(texel, ivec2(0), uSize - 1), 0).r;
}
void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    float here = ghost(pixel);
    float edge = 0.0;
    for (int i = 0; i < 8; ++i) {
        float angle = float(i) * 0.78539816;
        vec2 direction = vec2(cos(angle), sin(angle));
        edge = max(edge, abs(ghost(pixel + ivec2(round(direction * uRadius))) - here));
        edge = max(edge, abs(ghost(pixel + ivec2(round(direction * uRadius * 0.5))) - here) * 0.8);
    }
    FragColor = vec4(vec3(0.94, 0.97, 1.0), edge * uStrength);
}
"""

TRAIL_STRENGTH = 0.6


def trail_line(height: float) -> float:
    """The trail line's reach either side of a ghost's edge, in pixels (~1/540 of the height).
    The ghost variant's own copy is ``max(1.5, uViewport.y / 540.0)``."""
    return max(1.5, float(height) / 540.0)


def trail_program(resources, key: str, vertex: str, ghost_fragment: str,
                  names: tuple[str, ...]) -> tuple[int, dict[str, int]]:
    """An effect's ghost variant and its uniforms (``uGhostFade`` added). Its driver may drop
    uniforms the flat output no longer reads; setting those is a harmless no-op."""
    key = key + "_ghost"
    return (resources.program(key, vertex, ghost_fragment),
            resources.uniforms(key, names + ("uGhostFade",), required=False))


class MotionTrails:
    def __init__(self, label: str) -> None:
        self.label = label
        self._texture = 0
        self._fbo = 0
        self._size: tuple[int, int] | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._texture or self._fbo)

    def draw(self, target, frame, resources, ghosts: Iterable[tuple[float, float]],
             draw_ghosts: Callable[[Iterable[tuple[float, float]]], None]) -> None:
        """Inside ``target.scope``, let an effect draw its ghosts, then lay their outlines over the scene.

        The callback owns one prepared ghost pass: invariant program, geometry, texture and frame uniforms bind
        once, while its loop changes only each ghost's time and fade.  A multi-program effect may group its
        ghosts by program; MAX blending makes that ordering pixel-equivalent.
        """
        self.warm(target)
        width, height = self._size
        scene = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        clear = gl_query.get_floats(gl.GL_COLOR_CLEAR_VALUE, 4)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glClearColor(*clear)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        with blend_scope(gl.GL_MAX):
            draw_ghosts(ghosts)
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, scene)
        gl.glViewport(0, 0, width, height)
        program = resources.program("trail_edges", FULLSCREEN_VERTEX_SOURCE, _EDGE_FRAGMENT)
        uniforms = resources.uniforms("trail_edges", ("uGhosts", "uSize", "uRadius", "uStrength"))
        gl.glUseProgram(program)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texture)
        gl.glUniform1i(uniforms["uGhosts"], 0)
        gl.glUniform2i(uniforms["uSize"], width, height)
        gl.glUniform1f(uniforms["uRadius"], trail_line(height))
        gl.glUniform1f(uniforms["uStrength"], TRAIL_STRENGTH)
        gl.glBindVertexArray(frame.quad_vao)
        with blend_scope(gl.GL_FUNC_ADD, gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA):
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glViewport(*viewport)

    def warm(self, target) -> bool:
        """Allocate for ``target``'s allocation if not yet (ahead of a run, or at first use);
        True if it was."""
        width, height, _samples = target.allocation
        if self._size == (width, height):
            return True
        self.release()
        self._allocate(width, height)
        return False

    def _allocate(self, width: int, height: int) -> None:
        texture_name, framebuffer_name = (ctypes.c_uint * 1)(), (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, texture_name)
        self._texture = int(texture_name[0])
        if not self._texture:
            raise RuntimeError(f"{self.label} motion trails texture allocation failed")
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(self._texture, parameter, gl.GL_NEAREST)
        gl.glTextureStorage2D(self._texture, 1, gl.GL_R8, width, height)
        gl.glCreateFramebuffers(1, framebuffer_name)
        self._fbo = int(framebuffer_name[0])
        if not self._fbo:
            raise RuntimeError(f"{self.label} motion trails framebuffer allocation failed")
        gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._texture, 0)
        if gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"{self.label} motion trails incomplete at {width}x{height}")
        self._size = (width, height)

    def release(self) -> None:
        errors: list[str] = []
        if self._fbo:
            try:
                gl.glDeleteFramebuffers(1, [self._fbo])
                self._fbo = 0
            except Exception as exc:
                errors.append(str(exc))
        if self._texture:
            try:
                gl.glDeleteTextures([self._texture])
                self._texture = 0
            except Exception as exc:
                errors.append(str(exc))
        self._size = None
        if errors:
            raise RuntimeError(f"{self.label} motion trails cleanup incomplete: {' | '.join(errors)}")

# (key, vertex, fragment) of the edge pass (for a gradual warm-up).
TRAIL_EDGES_PROGRAM = ("trail_edges", FULLSCREEN_VERTEX_SOURCE, _EDGE_FRAGMENT)
