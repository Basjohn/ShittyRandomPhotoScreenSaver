"""Bloom for the multisampled scene target (3D Detail High).

Only **emissive** light glows: an effect writes how much of each pixel is
emitted light (sparks, embers, hot cracks, glints) into the scene target's
alpha while it renders into a bloom-enabled target, and writes 0 for the
photographs. So a bright sky never blooms and the effect's endpoints stay exact.

The target's alpha is the brightness of the light each pixel emits (opaque passes
write theirs, additive passes add theirs). The chain works on the resolved target:
a bright pass that scales each pixel's colour down to that brightness while
halving the size, three more halvings, then three tent-filtered upsamples
added back with additive blending. Levels are RGBA16F (smooth dim glows), sized
from the target's allocation bucket and dropped with it. About 1/3 of a
full-screen pass in total; no allocation per frame.
"""
from __future__ import annotations

from OpenGL import GL as gl

from rendering.quick import gl_query

from .passes import blend_scope

BLOOM_LEVELS = 4

_FULLSCREEN_VERTEX = """#version 410 core
out vec2 vUv;
void main() {
    vec2 corner = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    vUv = corner;
    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
"""

_DOWNSAMPLE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uSource;
uniform vec2 uTexel;       // one source texel in uv
uniform int uFirst;        // 1: keep only the emitted light (colour scaled to alpha's brightness)
vec3 tap(vec2 offset) {
    vec4 value = texture(uSource, vUv + offset * uTexel);
    if (uFirst != 1) return value.rgb;
    float brightness = dot(value.rgb, vec3(0.2126, 0.7152, 0.0722));
    return value.rgb * clamp(value.a / max(brightness, 1e-3), 0.0, 1.0);
}
void main() {
    // A 13-tap filter: a smooth downsample that neither flickers nor boxes.
    vec3 centre = tap(vec2(0.0)) * 0.125;
    vec3 inner = (tap(vec2(-1.0, -1.0)) + tap(vec2(1.0, -1.0)) + tap(vec2(-1.0, 1.0)) + tap(vec2(1.0, 1.0))) * 0.125;
    vec3 outer = (tap(vec2(-2.0, -2.0)) + tap(vec2(2.0, -2.0)) + tap(vec2(-2.0, 2.0)) + tap(vec2(2.0, 2.0))) * 0.03125;
    vec3 sides = (tap(vec2(-2.0, 0.0)) + tap(vec2(2.0, 0.0)) + tap(vec2(0.0, -2.0)) + tap(vec2(0.0, 2.0))) * 0.0625;
    FragColor = vec4(centre + inner + outer + sides, 1.0);
}
"""

_UPSAMPLE_FRAGMENT = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uSource;
uniform vec2 uTexel;
void main() {
    // A 3x3 tent, added onto the next larger level by the blend state.
    vec3 sum = texture(uSource, vUv).rgb * 4.0;
    sum += (texture(uSource, vUv + vec2(uTexel.x, 0.0)).rgb + texture(uSource, vUv - vec2(uTexel.x, 0.0)).rgb
          + texture(uSource, vUv + vec2(0.0, uTexel.y)).rgb + texture(uSource, vUv - vec2(0.0, uTexel.y)).rgb) * 2.0;
    sum += texture(uSource, vUv + uTexel).rgb + texture(uSource, vUv - uTexel).rgb
         + texture(uSource, vUv + vec2(uTexel.x, -uTexel.y)).rgb + texture(uSource, vUv + vec2(-uTexel.x, uTexel.y)).rgb;
    FragColor = vec4(sum / 16.0, 1.0);
}
"""


class BloomChain:
    def __init__(self, label: str) -> None:
        self.label = label
        self._levels: list[tuple[int, int, int, int]] = []   # (texture, fbo, width, height)
        self._key: tuple[int, int] | None = None

    @property
    def has_resources(self) -> bool:
        return bool(self._levels)

    def apply(self, source_texture: int, allocation: tuple[int, int], resources, vao: int) -> int:
        """Blur the emissive light of ``source_texture``; returns the half-size glow texture.

        The source covers the whole allocation (outside the drawn rect it is
        cleared black); so does the glow texture, at half resolution.
        """
        if self._key != allocation:
            self.release()
            self._allocate(*allocation)
            self._key = allocation
        down = resources.program("bloom_down", _FULLSCREEN_VERTEX, _DOWNSAMPLE_FRAGMENT)
        down_uniforms = resources.uniforms("bloom_down", ("uSource", "uTexel", "uFirst"))
        up = resources.program("bloom_up", _FULLSCREEN_VERTEX, _UPSAMPLE_FRAGMENT)
        up_uniforms = resources.uniforms("bloom_up", ("uSource", "uTexel"))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(vao)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glUseProgram(down)
        gl.glUniform1i(down_uniforms["uSource"], 0)
        source, source_size = source_texture, allocation
        for index, (texture, fbo, width, height) in enumerate(self._levels):
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glViewport(0, 0, width, height)
            gl.glBindTexture(gl.GL_TEXTURE_2D, source)
            gl.glUniform2f(down_uniforms["uTexel"], 1.0 / source_size[0], 1.0 / source_size[1])
            gl.glUniform1i(down_uniforms["uFirst"], 1 if index == 0 else 0)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            source, source_size = texture, (width, height)
        gl.glUseProgram(up)
        gl.glUniform1i(up_uniforms["uSource"], 0)
        with blend_scope(gl.GL_FUNC_ADD):
            for index in range(len(self._levels) - 1, 0, -1):
                small = self._levels[index]
                large = self._levels[index - 1]
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, large[1])
                gl.glViewport(0, 0, large[2], large[3])
                gl.glBindTexture(gl.GL_TEXTURE_2D, small[0])
                gl.glUniform2f(up_uniforms["uTexel"], 1.0 / small[2], 1.0 / small[3])
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        return self._levels[0][0]

    def _allocate(self, width: int, height: int) -> None:
        previous = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        try:
            for _level in range(BLOOM_LEVELS):
                width, height = max(1, width // 2), max(1, height // 2)
                texture = int(gl.glGenTextures(1))
                self._levels.append((texture, 0, width, height))
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, parameter, gl.GL_LINEAR)
                for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, wrap, gl.GL_CLAMP_TO_EDGE)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA16F, width, height, 0, gl.GL_RGBA, gl.GL_HALF_FLOAT, None)
                fbo = int(gl.glGenFramebuffers(1))
                self._levels[-1] = (texture, fbo, width, height)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
                if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"{self.label} bloom level incomplete at {width}x{height}")
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, previous)

    def release(self) -> None:
        errors: list[str] = []
        kept: list[tuple[int, int, int, int]] = []
        for texture, fbo, width, height in self._levels:
            try:
                if fbo:
                    gl.glDeleteFramebuffers(1, [fbo])
                    fbo = 0
                if texture:
                    gl.glDeleteTextures([texture])
                    texture = 0
            except Exception as exc:
                errors.append(str(exc))
            if texture or fbo:
                kept.append((texture, fbo, width, height))
        self._levels = kept
        self._key = None
        if errors:
            raise RuntimeError(f"{self.label} bloom cleanup incomplete: {' | '.join(errors)}")
