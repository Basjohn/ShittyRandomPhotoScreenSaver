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

import ctypes

from OpenGL import GL as gl

from rendering.gl_programs.conventions import SRPSS_VERTEX_INDEX_GLSL
from rendering.gl_programs.scene3d import Scene3DBlockLayout

from .passes import blend_scope
from .uniforms import PASS_BLOCK_BINDING, PassBlocks

BLOOM_LEVELS = 4

# A fragment drawn with it reads ``layout(location = 0) in vec2 vUv``.
FULLSCREEN_VERTEX_SOURCE = "#version 460 core\n" + SRPSS_VERTEX_INDEX_GLSL + """
layout(location = 0) out vec2 vUv;
void main() {
    vec2 corner = vec2((srpssVertexIndex << 1) & 2, srpssVertexIndex & 2);
    vUv = corner;
    gl_Position = vec4(corner * 2.0 - 1.0, 0.0, 1.0);
}
"""

# The bloom passes' values (binding plan: uSource 0, the block PASS_BLOCK_BINDING).
BLOOM_BLOCK = Scene3DBlockLayout.of("SceneBloomPass", (
    ("uTexel", "vec2"),   # one source texel in uv
    ("uFirst", "int"),    # 1: keep only the emitted light (colour scaled to alpha's brightness); the upsample ignores it
))

_DOWNSAMPLE_FRAGMENT = """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;
layout(binding = 0) uniform sampler2D uSource;
""" + BLOOM_BLOCK.glsl(PASS_BLOCK_BINDING) + """
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

_UPSAMPLE_FRAGMENT = """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;
layout(binding = 0) uniform sampler2D uSource;
""" + BLOOM_BLOCK.glsl(PASS_BLOCK_BINDING) + """
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
        # The passes' blocks: one copy per draw of the chain (2 * BLOOM_LEVELS - 1) in one scope.
        self._blocks = PassBlocks(f"{label} bloom", copies=2 * BLOOM_LEVELS)

    @property
    def has_resources(self) -> bool:
        return bool(self._levels) or self._blocks.has_resources

    def apply(self, source_texture: int, allocation: tuple[int, int], resources, vao: int) -> int:
        """Blur the emissive light of ``source_texture``; returns the half-size glow texture.

        The source covers the whole allocation (outside the drawn rect it is
        cleared black); so does the glow texture, at half resolution.
        """
        self.warm(allocation)
        down = resources.program("bloom_down", FULLSCREEN_VERTEX_SOURCE, _DOWNSAMPLE_FRAGMENT)
        up = resources.program("bloom_up", FULLSCREEN_VERTEX_SOURCE, _UPSAMPLE_FRAGMENT)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glBindVertexArray(vao)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glUseProgram(down)
        source, source_size = source_texture, allocation
        pack = BLOOM_BLOCK.pack
        # One pass-block scope for the chain: each draw reads its own copy of the values it used to set.
        with self._blocks.bound(pack({"uTexel": (1.0 / allocation[0], 1.0 / allocation[1]),
                                               "uFirst": 1})) as rebind:
            for index, (texture, fbo, width, height) in enumerate(self._levels):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
                gl.glViewport(0, 0, width, height)
                gl.glBindTexture(gl.GL_TEXTURE_2D, source)
                if index:
                    rebind(pack({"uTexel": (1.0 / source_size[0], 1.0 / source_size[1]), "uFirst": 0}))
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
                source, source_size = texture, (width, height)
            gl.glUseProgram(up)
            with blend_scope(gl.GL_FUNC_ADD):
                for index in range(len(self._levels) - 1, 0, -1):
                    small = self._levels[index]
                    large = self._levels[index - 1]
                    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, large[1])
                    gl.glViewport(0, 0, large[2], large[3])
                    gl.glBindTexture(gl.GL_TEXTURE_2D, small[0])
                    rebind(pack({"uTexel": (1.0 / small[2], 1.0 / small[3]), "uFirst": 0}))
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        return self._levels[0][0]

    def warm(self, allocation: tuple[int, int]) -> bool:
        """Allocate for ``allocation`` if not yet (ahead of a run, or at first use), one unit per call: the levels, then
        the passes' blocks; True once both are."""
        if self._key == allocation:
            return self._blocks.warm()
        self.release()
        self._allocate(*allocation)
        self._key = allocation
        return False

    def _allocate(self, width: int, height: int) -> None:
        for _level in range(BLOOM_LEVELS):
            width, height = max(1, width // 2), max(1, height // 2)
            texture_name, framebuffer_name = (ctypes.c_uint * 1)(), (ctypes.c_uint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, texture_name)
            texture = int(texture_name[0])
            if not texture:
                raise RuntimeError(f"{self.label} bloom texture allocation failed")
            self._levels.append((texture, 0, width, height))
            for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTextureParameteri(texture, parameter, gl.GL_LINEAR)
            for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
            gl.glTextureStorage2D(texture, 1, gl.GL_RGBA16F, width, height)
            gl.glCreateFramebuffers(1, framebuffer_name)
            fbo = int(framebuffer_name[0])
            if not fbo:
                raise RuntimeError(f"{self.label} bloom framebuffer allocation failed")
            self._levels[-1] = (texture, fbo, width, height)
            gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, texture, 0)
            if gl.glCheckNamedFramebufferStatus(fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"{self.label} bloom level incomplete at {width}x{height}")

    def release(self) -> None:
        errors: list[str] = []
        try:
            self._blocks.release()
        except Exception as exc:
            errors.append(str(exc))
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

# (key, vertex, fragment) of the programs ``BloomChain.apply`` draws with (for a gradual warm-up).
BLOOM_PROGRAMS = (
    ("bloom_down", FULLSCREEN_VERTEX_SOURCE, _DOWNSAMPLE_FRAGMENT),
    ("bloom_up", FULLSCREEN_VERTEX_SOURCE, _UPSAMPLE_FRAGMENT),
)
