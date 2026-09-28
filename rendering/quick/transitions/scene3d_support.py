"""3D Detail tiers, blend scopes and the optional multisampled scene target.

A 3D transition resolves its tier once, into the immutable request, from the
canonical ``transitions.detail_3d`` setting; renderers read it from there and
never touch Settings. The tier trades fidelity for cost in one place:

* **High** -- the scene renders into a 4x multisampled target (smooth tile and
  shard silhouettes), with soft shadows and the full particle budget;
* **Balanced** -- straight into Quick's target, soft shadows, 60% particles;
* **Performance** -- straight into Quick's target, no shadow pass, 30% particles.

The tier table itself is pure data in ``rendering.gl_programs.scene3d``.

The scene target is context-local and allocated on first use; the transition
host's ``park`` (after every run) drops it, so its memory is held only while a
3D run is on screen. Programs stay warm in the owning ``MeshResources``.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from OpenGL import GL as gl

from rendering.gl_programs.scene3d import (  # noqa: F401  (re-exported for renderers)
    SCENE3D_DETAIL_NAMES,
    SCENE3D_DETAIL_TIERS,
    Scene3DDetail,
    scene3d_detail,
)

from .render_contract import QUICK_TRANSITION_VERTEX_SOURCE, QuickTransitionRenderFrame


@contextmanager
def blend_scope(equation: int, source: int = gl.GL_ONE, destination: int = gl.GL_ONE) -> Iterator[None]:
    """Blend one pass; alpha is left untouched. The host fence restores the rest."""
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendEquationSeparate(equation, gl.GL_FUNC_ADD)
    gl.glBlendFuncSeparate(source, destination, gl.GL_ZERO, gl.GL_ONE)
    try:
        yield
    finally:
        gl.glBlendEquationSeparate(gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparate(gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE, gl.GL_ZERO)
        gl.glDisable(gl.GL_BLEND)


_COMPOSITE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uScene;
void main() { FragColor = texelFetch(uScene, ivec2(gl_FragCoord.xy), 0); }
"""


def _binding(name: int) -> int:
    value = gl.glGetIntegerv(name)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


class SceneTarget:
    """Multisampled colour+depth target the size of Quick's render target.

    ``begin`` redirects drawing into it; ``end`` resolves it and composites the
    result through the item quad, so Quick's scissor and item bounds apply
    exactly as for a direct draw. Failed deletions keep their handles for retry.
    """

    def __init__(self, label: str) -> None:
        self.label = label
        self._key: tuple[int, int, int] | None = None
        self._names = {"fbo": 0, "colour": 0, "depth": 0, "resolve_fbo": 0, "resolve_texture": 0}
        self._inherited = (0, 0)

    @property
    def has_resources(self) -> bool:
        return any(self._names.values())

    def begin(self, frame: QuickTransitionRenderFrame, samples: int) -> None:
        width, height = int(frame.viewport[2]), int(frame.viewport[3])
        samples = max(1, min(int(samples), _binding(gl.GL_MAX_SAMPLES)))
        self._inherited = (_binding(gl.GL_DRAW_FRAMEBUFFER_BINDING), _binding(gl.GL_READ_FRAMEBUFFER_BINDING))
        if self._key != (width, height, samples):
            self.release()
            self._allocate(width, height, samples)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
        clear = tuple(float(value) for value in gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE))
        scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        gl.glDisable(gl.GL_SCISSOR_TEST)
        try:
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glClearDepth(1.0)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        finally:
            gl.glClearColor(*clear)
            if scissor:
                gl.glEnable(gl.GL_SCISSOR_TEST)

    def end(self, frame: QuickTransitionRenderFrame, resources) -> None:
        width, height = self._key[0], self._key[1]
        draw, read = self._inherited
        scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        gl.glDisable(gl.GL_SCISSOR_TEST)
        try:
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._names["fbo"])
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._names["resolve_fbo"])
            gl.glBlitFramebuffer(0, 0, width, height, 0, 0, width, height, gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        finally:
            if scissor:
                gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, draw)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, read)
        program = resources.program("scene_composite", QUICK_TRANSITION_VERTEX_SOURCE, _COMPOSITE_FRAGMENT)
        uniforms = resources.uniforms("scene_composite", ("uMatrix", "uItemSize", "uScene"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glUseProgram(program)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._names["resolve_texture"])
        gl.glUniform1i(uniforms["uScene"], 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _allocate(self, width: int, height: int, samples: int) -> None:
        renderbuffer = _binding(gl.GL_RENDERBUFFER_BINDING)
        try:
            self._names["fbo"] = int(gl.glGenFramebuffers(1))
            self._names["colour"] = int(gl.glGenRenderbuffers(1))
            self._names["depth"] = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._names["colour"])
            gl.glRenderbufferStorageMultisample(gl.GL_RENDERBUFFER, samples, gl.GL_RGBA8, width, height)
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._names["depth"])
            gl.glRenderbufferStorageMultisample(gl.GL_RENDERBUFFER, samples, gl.GL_DEPTH_COMPONENT24, width, height)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER,
                                         self._names["colour"])
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER,
                                         self._names["depth"])
            complete = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            self._names["resolve_texture"] = int(gl.glGenTextures(1))
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._names["resolve_texture"])
            for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
            self._names["resolve_fbo"] = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["resolve_fbo"])
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D,
                                      self._names["resolve_texture"], 0)
            complete = complete and gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
            if not complete:
                raise RuntimeError(f"{self.label} scene target incomplete at {width}x{height}x{samples}")
            self._key = (width, height, samples)
        finally:
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, renderbuffer)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._inherited[0])
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._inherited[1])

    def release(self) -> None:
        errors: list[str] = []
        for key, delete in (
            ("fbo", lambda name: gl.glDeleteFramebuffers(1, [name])),
            ("resolve_fbo", lambda name: gl.glDeleteFramebuffers(1, [name])),
            ("colour", lambda name: gl.glDeleteRenderbuffers(1, [name])),
            ("depth", lambda name: gl.glDeleteRenderbuffers(1, [name])),
            ("resolve_texture", lambda name: gl.glDeleteTextures([name])),
        ):
            name = self._names[key]
            if not name:
                continue
            try:
                delete(name)
            except Exception as exc:
                errors.append(f"{key}: {exc}")
            else:
                self._names[key] = 0
        self._key = None
        if errors:
            raise RuntimeError(f"{self.label} scene target cleanup incomplete: {' | '.join(errors)}")
