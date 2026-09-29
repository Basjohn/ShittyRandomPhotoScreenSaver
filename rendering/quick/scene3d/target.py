"""The multisampled scene target: smooth 3D edges for any pixel rect of Quick's target.

``begin`` redirects drawing into a colour+depth multisampled framebuffer that
covers ``rect`` (by default the item's pixel bounds) and offsets the viewport,
so the frame's own matrix draws exactly as it would directly. ``end`` resolves
and composites it back through the item quad; Quick's scissor, stencil (the
Visualizer card clip) and item bounds then apply as for a direct draw.

``scope`` restores Quick's framebuffers, viewport and scissor even when the
scene raises, so a consumer needs no fence change of its own (the Visualizer
fence stays as it is: modes that do not use a target pay nothing).

Allocation rounds up to 64 px and is reused while the rect fits, so a CUSTOM
resize drag does not reallocate per frame. The owner releases the target: a
transition at the host's ``park()`` after each run, a Visualizer mode when it
retires. Failed deletions keep their handles for retry.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from OpenGL import GL as gl

from rendering.quick import gl_query

from .frame import ITEM_QUAD_VERTEX_SOURCE, SceneFrame, item_pixel_rect
from .post import BloomChain

SCENE_TARGET_BUCKET = 64

_COMPOSITE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uScene;
uniform sampler2D uBloom;
uniform ivec2 uOrigin;
uniform ivec2 uExtent;
uniform vec2 uBloomScale;      // 1 / allocation size: the glow covers the allocation at half size
uniform float uBloomStrength;  // 0 without bloom
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    vec3 colour = texelFetch(uScene, texel, 0).rgb;
    if (uBloomStrength > 0.0) colour += texture(uBloom, (vec2(texel) + 0.5) * uBloomScale).rgb * uBloomStrength;
    // The target's alpha may carry emissive light for the bloom; Quick gets opaque pixels.
    FragColor = vec4(colour, 1.0);
}
"""


def _bucket(size: int) -> int:
    return max(SCENE_TARGET_BUCKET, -(-int(size) // SCENE_TARGET_BUCKET) * SCENE_TARGET_BUCKET)


class SceneTarget:
    def __init__(self, label: str) -> None:
        self.label = label
        self._key: tuple[int, int, int] | None = None  # allocated width, height, samples
        self._names = {"fbo": 0, "colour": 0, "depth": 0, "resolve_fbo": 0, "resolve_texture": 0}
        self._inherited = (0, 0)
        self._scissor = False
        self._rect = (0, 0, 0, 0)
        self._bloom = BloomChain(label)

    @property
    def has_resources(self) -> bool:
        return any(self._names.values()) or self._bloom.has_resources

    @property
    def allocation(self) -> tuple[int, int, int] | None:
        """(width, height, samples) currently allocated, if any."""
        return self._key

    @contextmanager
    def scope(self, frame: SceneFrame, samples: int, resources,
              rect: tuple[int, int, int, int] | None = None, bloom: float = 0.0) -> Iterator[None]:
        """Draw the enclosed passes through the target; Quick's bindings come back either way.

        With ``bloom`` > 0 the emissive light the passes wrote into alpha glows
        (see ``post.BloomChain``); the passes must then write alpha deliberately.
        """
        self.begin(frame, samples, rect)
        try:
            yield
        except BaseException:
            self._restore_inherited(frame)
            raise
        self.end(frame, resources, bloom)

    def begin(self, frame: SceneFrame, samples: int, rect: tuple[int, int, int, int] | None = None) -> None:
        x, y, width, height = tuple(int(v) for v in (rect if rect is not None else item_pixel_rect(frame)))
        if width <= 0 or height <= 0:
            raise ValueError(f"{self.label} scene target needs a positive rect, got {(x, y, width, height)}")
        samples = max(1, min(int(samples), gl_query.get_int(gl.GL_MAX_SAMPLES)))
        self._inherited = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING),
                           gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING))
        self._scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        key = self._key
        if key is None or key[2] != samples or width > key[0] or height > key[1]:
            self.release()
            self._allocate(_bucket(width), _bucket(height), samples)
        self._rect = (x, y, width, height)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
        gl.glDisable(gl.GL_SCISSOR_TEST)
        clear = gl_query.get_floats(gl.GL_COLOR_CLEAR_VALUE, 4)
        try:
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
            gl.glClearDepth(1.0)
            gl.glDepthMask(gl.GL_TRUE)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        finally:
            gl.glClearColor(*clear)
        vx, vy, vw, vh = frame.viewport
        gl.glViewport(vx - x, vy - y, vw, vh)

    def end(self, frame: SceneFrame, resources, bloom: float = 0.0) -> None:
        x, y, width, height = self._rect
        allocated_width, allocated_height = self._key[0], self._key[1]
        # With bloom, resolve the whole allocation: outside the rect it is cleared black.
        blit_width, blit_height = (allocated_width, allocated_height) if bloom > 0.0 else (width, height)
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._names["fbo"])
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._names["resolve_fbo"])
        gl.glBlitFramebuffer(0, 0, blit_width, blit_height, 0, 0, blit_width, blit_height,
                             gl.GL_COLOR_BUFFER_BIT, gl.GL_NEAREST)
        glow = 0
        if bloom > 0.0:
            glow = self._bloom.apply(self._names["resolve_texture"], (allocated_width, allocated_height),
                                     resources, frame.quad_vao)
        self._restore_inherited(frame)
        program = resources.program("scene_composite", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_FRAGMENT)
        uniforms = resources.uniforms("scene_composite", ("uMatrix", "uItemSize", "uScene", "uBloom", "uOrigin",
                                                           "uExtent", "uBloomScale", "uBloomStrength"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glUseProgram(program)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2i(uniforms["uOrigin"], x, y)
        gl.glUniform2i(uniforms["uExtent"], width, height)
        gl.glUniform2f(uniforms["uBloomScale"], 1.0 / allocated_width, 1.0 / allocated_height)
        gl.glUniform1f(uniforms["uBloomStrength"], float(bloom) if glow else 0.0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, glow or self._names["resolve_texture"])
        gl.glUniform1i(uniforms["uBloom"], 1)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._names["resolve_texture"])
        gl.glUniform1i(uniforms["uScene"], 0)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def _restore_inherited(self, frame: SceneFrame) -> None:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._inherited[0])
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._inherited[1])
        gl.glViewport(*frame.viewport)
        if self._scissor:
            gl.glEnable(gl.GL_SCISSOR_TEST)
        else:
            gl.glDisable(gl.GL_SCISSOR_TEST)

    def _allocate(self, width: int, height: int, samples: int) -> None:
        renderbuffer = gl_query.get_int(gl.GL_RENDERBUFFER_BINDING)
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
        try:
            self._bloom.release()
        except Exception as exc:
            errors.append(str(exc))
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
