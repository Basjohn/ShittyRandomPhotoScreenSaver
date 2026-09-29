"""The multisampled scene target: smooth 3D edges for any pixel rect of Quick's target.

``begin`` redirects drawing into a colour+depth multisampled framebuffer that
covers ``rect`` (by default the item's pixel bounds) and offsets the viewport,
so the frame's own matrix draws exactly as it would directly. ``end`` resolves
and composites it back through the item quad; Quick's scissor, stencil (the
Visualizer card clip) and item bounds then apply as for a direct draw.

The colour attachment is a texture the composite reads directly, averaging the
samples itself: there is no resolve blit. (A ``glBlitFramebuffer`` resolve of
drawn content measured ~0.5 ms at 2560x1440 on an RTX 4090, 1 or 4 samples
alike; the shader average costs a few hundredths of that.) Bloom needs one
resolved image, so with bloom a resolve pass writes it first.

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
from .post import FULLSCREEN_VERTEX_SOURCE, BloomChain

SCENE_TARGET_BUCKET = 64

# The average of a multisampled texel's samples (what a resolve blit computes).
_RESOLVE_GLSL = """
uniform sampler2DMS uSceneSamples;
uniform int uSamples;
vec4 sceneResolved(ivec2 texel) {
    vec4 sum = vec4(0.0);
    for (int i = 0; i < uSamples; ++i) sum += texelFetch(uSceneSamples, texel, i);
    return sum / float(uSamples);
}
"""

_COMPOSITE_HEADER = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform ivec2 uOrigin;
uniform ivec2 uExtent;
"""

# From a single-sample (or resolved) scene, with the glow added.
_COMPOSITE_FRAGMENT = _COMPOSITE_HEADER + """
uniform sampler2D uScene;
uniform sampler2D uBloom;
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

# Straight from the multisampled scene: resolve and composite in one pass.
_COMPOSITE_SAMPLES_FRAGMENT = _COMPOSITE_HEADER + _RESOLVE_GLSL + """
void main() {
    ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin;
    if (any(lessThan(texel, ivec2(0))) || any(greaterThanEqual(texel, uExtent))) discard;
    FragColor = vec4(sceneResolved(texel).rgb, 1.0);
}
"""

# The whole allocation, resolved for the bloom (outside the rect it is cleared black).
_RESOLVE_FRAGMENT = "#version 410 core\nout vec4 FragColor;\n" + _RESOLVE_GLSL + """
void main() {
    FragColor = sceneResolved(ivec2(gl_FragCoord.xy));
}
"""


def _bucket(size: int) -> int:
    return max(SCENE_TARGET_BUCKET, -(-int(size) // SCENE_TARGET_BUCKET) * SCENE_TARGET_BUCKET)


def _plain_texture(width: int, height: int) -> int:
    texture = int(gl.glGenTextures(1))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
        gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_NEAREST)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None)
    return texture


class SceneTarget:
    def __init__(self, label: str) -> None:
        self.label = label
        self._key: tuple[int, int, int] | None = None  # allocated width, height, requested samples
        self._samples = 0                                # samples allocated (1 = a plain texture)
        # colour: the scene texture (multisampled when _samples > 1); resolve_*: bloom's resolved copy.
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
        return None if self._key is None else (self._key[0], self._key[1], self._samples)

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
        samples = max(1, int(samples))
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
        multisampled = self._samples > 1
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        scene, glow = self._names["colour"], 0
        if bloom > 0.0:
            if multisampled:
                scene = self._resolve(frame, resources)
            glow = self._bloom.apply(scene, (allocated_width, allocated_height), resources, frame.quad_vao)
        self._restore_inherited(frame)
        if multisampled and not glow:
            program = resources.program("scene_composite_samples", ITEM_QUAD_VERTEX_SOURCE,
                                        _COMPOSITE_SAMPLES_FRAGMENT)
            uniforms = resources.uniforms("scene_composite_samples", ("uMatrix", "uItemSize", "uOrigin", "uExtent",
                                                                       "uSceneSamples", "uSamples"))
            gl.glUseProgram(program)
            gl.glUniform1i(uniforms["uSamples"], self._samples)
            gl.glUniform1i(uniforms["uSceneSamples"], 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, scene)
        else:
            program = resources.program("scene_composite", ITEM_QUAD_VERTEX_SOURCE, _COMPOSITE_FRAGMENT)
            uniforms = resources.uniforms("scene_composite", ("uMatrix", "uItemSize", "uScene", "uBloom", "uOrigin",
                                                               "uExtent", "uBloomScale", "uBloomStrength"))
            gl.glUseProgram(program)
            gl.glUniform2f(uniforms["uBloomScale"], 1.0 / allocated_width, 1.0 / allocated_height)
            gl.glUniform1f(uniforms["uBloomStrength"], float(bloom) if glow else 0.0)
            gl.glActiveTexture(gl.GL_TEXTURE1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, glow or scene)
            gl.glUniform1i(uniforms["uBloom"], 1)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, scene)
            gl.glUniform1i(uniforms["uScene"], 0)
        gl.glUniformMatrix4fv(uniforms["uMatrix"], 1, gl.GL_FALSE, frame.matrix_values)
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform2i(uniforms["uOrigin"], x, y)
        gl.glUniform2i(uniforms["uExtent"], width, height)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        if multisampled and not glow:
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)

    def _resolve(self, frame: SceneFrame, resources) -> int:
        """Average the samples of the whole allocation into a plain texture (for the bloom)."""
        width, height = self._key[0], self._key[1]
        if not self._names["resolve_texture"]:
            self._names["resolve_texture"] = _plain_texture(width, height)
            self._names["resolve_fbo"] = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["resolve_fbo"])
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D,
                                      self._names["resolve_texture"], 0)
            if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"{self.label} scene resolve incomplete at {width}x{height}")
        program = resources.program("scene_resolve", FULLSCREEN_VERTEX_SOURCE, _RESOLVE_FRAGMENT)
        uniforms = resources.uniforms("scene_resolve", ("uSceneSamples", "uSamples"))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["resolve_fbo"])
        gl.glViewport(0, 0, width, height)
        gl.glUseProgram(program)
        gl.glUniform1i(uniforms["uSamples"], self._samples)
        gl.glUniform1i(uniforms["uSceneSamples"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["colour"])
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)
        return self._names["resolve_texture"]

    def _restore_inherited(self, frame: SceneFrame) -> None:
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._inherited[0])
        gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, self._inherited[1])
        gl.glViewport(*frame.viewport)
        if self._scissor:
            gl.glEnable(gl.GL_SCISSOR_TEST)
        else:
            gl.glDisable(gl.GL_SCISSOR_TEST)

    def _allocate(self, width: int, height: int, requested: int) -> None:
        samples = min(requested, gl_query.get_int(gl.GL_MAX_SAMPLES),
                      gl_query.get_int(gl.GL_MAX_COLOR_TEXTURE_SAMPLES))
        renderbuffer = gl_query.get_int(gl.GL_RENDERBUFFER_BINDING)
        try:
            self._names["fbo"] = int(gl.glGenFramebuffers(1))
            if samples > 1:
                self._names["colour"] = int(gl.glGenTextures(1))
                gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, self._names["colour"])
                gl.glTexImage2DMultisample(gl.GL_TEXTURE_2D_MULTISAMPLE, samples, gl.GL_RGBA8, width, height, True)
                gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)
                colour_target = gl.GL_TEXTURE_2D_MULTISAMPLE
            else:
                self._names["colour"] = _plain_texture(width, height)
                colour_target = gl.GL_TEXTURE_2D
            self._names["depth"] = int(gl.glGenRenderbuffers(1))
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self._names["depth"])
            gl.glRenderbufferStorageMultisample(gl.GL_RENDERBUFFER, samples if samples > 1 else 0,
                                                gl.GL_DEPTH_COMPONENT24, width, height)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self._names["fbo"])
            gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, colour_target,
                                      self._names["colour"], 0)
            gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_DEPTH_ATTACHMENT, gl.GL_RENDERBUFFER,
                                         self._names["depth"])
            if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"{self.label} scene target incomplete at {width}x{height}x{samples}")
            self._key = (width, height, requested)
            self._samples = max(1, samples)
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
            ("colour", lambda name: gl.glDeleteTextures([name])),
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
        self._samples = 0
        if errors:
            raise RuntimeError(f"{self.label} scene target cleanup incomplete: {' | '.join(errors)}")
