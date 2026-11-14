"""Light shafts for a scene target: rays you can see, streaming from a light past whatever stands in front.

A mode that wants shafts opens its target with ``shafts=True`` and draws its light's **source** (the light and a
soft glow round it, its intensity 0..1) into the target's shaft-source attachment inside
``SceneTarget.shaft_writes()``, depth-tested so terrain, water or anything else nearer leaves it out. It then
hands the target a ``ShaftLight`` (where the light is on screen, how far the rays reach, their colour).

``LightShafts.apply`` turns the source into rays on the resolved target: a half-size downsample that resolves the
samples, then two radial gathers toward the light. The first averages 16 taps over ``reach`` of each pixel's way to
the light; the second averages 16 taps of that over a sixteenth of the reach, filling the gaps between the first's
taps, so the rays are smooth (256 effective taps) without jitter. A pixel near the light gathers mostly source and
is bright; further out only the share of its way that crosses the source lights it, so rays thin with distance and
end where ``reach`` stops short of the source. The composite adds them in the shafts' colour (see
``target._with_shafts``). Levels are half-size R16F from the target's allocation bucket, dropped with it; nothing
is allocated per frame, and a target without shafts draws exactly as before.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from OpenGL import GL as gl

from rendering.gl_programs.conventions import SRPSS_CONVENTIONS_FRAGMENT_GLSL
from rendering.gl_programs.portable import portable_program

from .post import FULLSCREEN_VERTEX_SOURCE
from .uniforms import PassBlocks

SHAFT_TAPS = 16


@dataclass(frozen=True, slots=True)
class ShaftLight:
    """One frame's light for the shafts. ``item_point``: the light in the item's logical coordinates (it may lie
    outside the item). ``reach``: 0..1, the share of each pixel's way to the light the rays gather over (1: rays
    reach every pixel). ``colour``: linear RGB already scaled by the shafts' strength."""

    item_point: tuple[float, float]
    reach: float
    colour: tuple[float, float, float]


_DOWNSAMPLE_FRAGMENT = """#version 460 core
layout(location = 0) in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uSource;
void main() {
    // Half size, bilinear between the four texels a level texel covers.
    FragColor = vec4(texture(uSource, vUv).r, 0.0, 0.0, 1.0);
}
"""

_DOWNSAMPLE_SAMPLES_FRAGMENT = """#version 460 core
out vec4 FragColor;
uniform sampler2DMS uSource;
uniform int uSamples;
""" + SRPSS_CONVENTIONS_FRAGMENT_GLSL + """
void main() {
    // The four full-size texels under this half-size texel, every sample of each.
    ivec2 base = fragTexel(textureSize(uSource) / 2) * 2;
    float sum = 0.0;
    for (int y = 0; y < 2; ++y)
        for (int x = 0; x < 2; ++x)
            for (int i = 0; i < uSamples; ++i) sum += texelFetch(uSource, base + ivec2(x, y), i).r;
    FragColor = vec4(sum / float(4 * uSamples), 0.0, 0.0, 1.0);
}
"""

_GATHER_FRAGMENT = """#version 460 core
layout(location = 0) in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uSource;
uniform vec2 uLight;   // the light, in uv (may lie outside 0..1)
uniform float uReach;  // the share of the way to the light this pass gathers over
void main() {
    vec2 way = (uLight - vUv) * uReach;
    float sum = 0.0;
    for (int i = 0; i < %d; ++i) sum += texture(uSource, vUv + way * (float(i) + 0.5) / %d.0).r;
    FragColor = vec4(sum / %d.0, 0.0, 0.0, 1.0);
}
""" % (SHAFT_TAPS, SHAFT_TAPS, SHAFT_TAPS)

# N1.6 (``portable_program``): each pass's values in one std140 pass block, its source at unit 0 (the unit it read as
# a loose uniform); the gather's two draws each bind their own copy.
_, (_DOWNSAMPLE_FRAGMENT,), _ = portable_program(None, (_DOWNSAMPLE_FRAGMENT,), block="ShaftDownsample",
                                                                 samplers={"uSource": 0})
_, (_DOWNSAMPLE_SAMPLES_FRAGMENT,), _DOWNSAMPLE_SAMPLES_BLOCK = portable_program(
    None, (_DOWNSAMPLE_SAMPLES_FRAGMENT,), block="ShaftDownsampleSamples", samplers={"uSource": 0})
_, (_GATHER_FRAGMENT,), _GATHER_BLOCK = portable_program(None, (_GATHER_FRAGMENT,), block="ShaftGather",
                                                         samplers={"uSource": 0})

SHAFT_PROGRAMS = (
    ("shaft_down", FULLSCREEN_VERTEX_SOURCE, _DOWNSAMPLE_FRAGMENT),
    ("shaft_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT),
)
SHAFT_SAMPLES_PROGRAMS = (
    ("shaft_down_samples", FULLSCREEN_VERTEX_SOURCE, _DOWNSAMPLE_SAMPLES_FRAGMENT),
    ("shaft_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT),
)


class LightShafts:
    def __init__(self, label: str) -> None:
        self.label = label
        self._levels: list[tuple[int, int]] = []   # (texture, fbo) x 2, both half the allocation
        self._size: tuple[int, int] | None = None
        self._key: tuple[int, int] | None = None
        # The passes' blocks (N1.6): one copy per draw of a pass (the downsample, the gather's two) in one scope.
        self._blocks = PassBlocks(f"{label} shafts", copies=2)

    @property
    def has_resources(self) -> bool:
        return bool(self._levels) or self._blocks.has_resources

    def apply(self, source: int, samples: int, allocation: tuple[int, int], light_uv: tuple[float, float],
              reach: float, resources, vao: int) -> int:
        """Rays from ``source`` (the shaft-source attachment; multisampled when ``samples`` > 1) toward
        ``light_uv`` (in the allocation's uv); returns the half-size shaft texture."""
        self.warm(allocation)
        width, height = self._size
        multisampled = samples > 1
        key, vertex, fragment = (SHAFT_SAMPLES_PROGRAMS if multisampled else SHAFT_PROGRAMS)[0]
        down = resources.program(key, vertex, fragment)
        gather = resources.program("shaft_gather", FULLSCREEN_VERTEX_SOURCE, _GATHER_FRAGMENT)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glDisable(gl.GL_BLEND)
        gl.glBindVertexArray(vao)
        gl.glViewport(0, 0, width, height)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        first, second = self._levels
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, first[1])
        gl.glUseProgram(down)
        if multisampled:
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, source)
            with self._blocks.bound(_DOWNSAMPLE_SAMPLES_BLOCK.pack({"uSamples": samples})):
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindTexture(gl.GL_TEXTURE_2D_MULTISAMPLE, 0)
        else:
            gl.glBindTexture(gl.GL_TEXTURE_2D, source)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)          # no values: the downsample reads its source alone
        gl.glUseProgram(gather)
        reach = max(0.0, min(1.0, float(reach)))
        light = tuple(float(v) for v in light_uv)
        with self._blocks.bound(_GATHER_BLOCK.pack({"uLight": light, "uReach": reach})) as rebind:
            for target, read, span in ((second, first, reach), (first, second, reach / SHAFT_TAPS)):
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target[1])
                gl.glBindTexture(gl.GL_TEXTURE_2D, read[0])
                if read is second:
                    rebind(_GATHER_BLOCK.pack({"uLight": light, "uReach": span}))
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        return first[0]

    def warm(self, allocation: tuple[int, int]) -> bool:
        """Allocate for ``allocation`` if not yet (one unit per call: the levels, then the passes' blocks); True once
        both are."""
        if self._key == allocation:
            return self._blocks.warm()
        self.release()
        width, height = max(1, allocation[0] // 2), max(1, allocation[1] // 2)
        for _level in range(2):
            texture_name, framebuffer_name = (ctypes.c_uint * 1)(), (ctypes.c_uint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, texture_name)
            texture = int(texture_name[0])
            if not texture:
                raise RuntimeError(f"{self.label} shaft texture allocation failed")
            self._levels.append((texture, 0))
            for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
                gl.glTextureParameteri(texture, parameter, gl.GL_LINEAR)
            for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
                gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
            gl.glTextureStorage2D(texture, 1, gl.GL_R16F, width, height)
            gl.glCreateFramebuffers(1, framebuffer_name)
            fbo = int(framebuffer_name[0])
            if not fbo:
                raise RuntimeError(f"{self.label} shaft framebuffer allocation failed")
            self._levels[-1] = (texture, fbo)
            gl.glNamedFramebufferTexture(fbo, gl.GL_COLOR_ATTACHMENT0, texture, 0)
            if gl.glCheckNamedFramebufferStatus(fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"{self.label} shaft level incomplete at {width}x{height}")
        self._size = (width, height)
        self._key = allocation
        return False

    def release(self) -> None:
        errors: list[str] = []
        try:
            self._blocks.release()
        except Exception as exc:
            errors.append(str(exc))
        kept: list[tuple[int, int]] = []
        for texture, fbo in self._levels:
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
                kept.append((texture, fbo))
        self._levels = kept
        self._key = None
        self._size = None
        if errors:
            raise RuntimeError(f"{self.label} shaft cleanup incomplete: {' | '.join(errors)}")


__all__ = ["SHAFT_PROGRAMS", "SHAFT_SAMPLES_PROGRAMS", "SHAFT_TAPS", "LightShafts", "ShaftLight"]
