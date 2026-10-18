"""Defocus layer: depth of field for things near the lens, as a lens makes it.

Objects close to the camera and far out of focus (a bubble drifting past the lens, specks just in front of it) are
drawn sharp into their own layer, each pixel with its circle of confusion; ``composite`` then spreads every pixel
over its own disc and lays the result over the scene. A bright point becomes a disc of even light (bokeh), an edge
softens by exactly its circle, and the light a pixel carries is kept, only spread.

* ``DefocusLayer(label)``; ``begin(width, height)`` binds the layer (RGBA16F premultiplied colour at location 0, the
  circle of confusion in pixels, RG16F, at location 1, both cleared to 0) with premultiplied-over blending on
  colour and max blending on the circle, so nearer layered objects win; the caller draws its near objects with
  ``SCENE_DEFOCUS_GLSL`` ``sceneDefocusWrite(premultipliedColour, alpha, cocPixels)``. ``end()`` hands back the
  caller's framebuffer, viewport, blend and draw buffers.
* ``composite(max_radius)`` draws over the bound framebuffer (premultiplied over): for each pixel, 64 taps on a
  golden-angle disc out to ``max_radius`` pixels, each tap read from the layer's mip level whose texels are about
  the taps' spacing (so every source pixel is caught by the taps round it, never missed between them), counted where
  its circle reaches this pixel and weighted by the share of its light that lands here (1 / its circle's area), so
  energy is conserved and a bright point becomes an even disc; pixels with no circle pass through sharp. The circle
  is stored alpha-weighted so mip levels average it only over what was drawn.
* Highlights: a fixed tap pattern catches a small bright source unevenly (striped, blocky blobs where a lens draws
  a round disc). Light above ``highlight`` (luminance, averaged over a texel of the read level) and above the
  mean round it (two levels coarser) is taken out of the
  gather and drawn instead as one instanced disc per such texel, of that texel's circle, its edge antialiased and a
  little brighter (as lens bokeh is), holding exactly the light removed. Below the threshold nothing changes.

Nothing is allocated per frame after the first ``begin`` at a size; ``release`` drops the textures, framebuffer and
program.
"""
from __future__ import annotations

import ctypes
import math

from OpenGL import GL as gl

from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program

DEFOCUS_TAPS = 64

SCENE_DEFOCUS_GLSL = """
layout(location=0) out vec4 DefocusColour;
layout(location=1) out vec4 DefocusCircle;
void sceneDefocusWrite(vec3 premultiplied, float alpha, float cocPixels) {
    DefocusColour = vec4(premultiplied, alpha);
    DefocusCircle = vec4(cocPixels * alpha, alpha, 0.0, 1.0);
}
"""

_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""
_GATHER = """#version 460 core
out vec4 FragColor;
uniform sampler2D uColour;
uniform sampler2D uCircle;
uniform float uMaxRadius;
const int TAPS = %d;
float circleAt(vec2 uv, float level) {
    vec2 c = textureLod(uCircle, uv, level).rg;
    return c.y > 1e-4 ? c.x / c.y : 0.0;
}
void main() {
    vec2 size = vec2(textureSize(uColour, 0));
    ivec2 here = ivec2(gl_FragCoord.xy);
    vec4 own = texelFetch(uColour, here, 0);
    vec2 ownCircle = texelFetch(uCircle, here, 0).rg;
    float ownRadius = ownCircle.y > 1e-4 ? ownCircle.x / ownCircle.y : 0.0;
    if (uMaxRadius < 0.5) { FragColor = own; return; }
    vec4 sum = vec4(0.0);
    // Each tap stands for an equal share of the disc of radius uMaxRadius, read at the level whose texels are about
    // that share's width; a source pixel's light spreads evenly over its own circle.
    float tapArea = 3.14159265 * uMaxRadius * uMaxRadius / float(TAPS);
    float level = max(floor(log2(max(sqrt(tapArea), 1.0))), 0.0);
    for (int i = 0; i < TAPS; ++i) {
        float r = sqrt((float(i) + 0.5) / float(TAPS)) * uMaxRadius;
        float a = float(i) * 2.39996323;
        vec2 uv = (gl_FragCoord.xy + vec2(cos(a), sin(a)) * r) / size;
        if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) continue;
        float circle = circleAt(uv, level);
        if (circle < 0.5) continue;
        float reach = clamp(circle - r + 0.5, 0.0, 1.0);          // the circle's edge, antialiased
        sum += textureLod(uColour, uv, level) * reach * tapArea / (3.14159265 * circle * circle);
    }
    // Sharp pixels (no circle) stay where they are.
    if (ownRadius < 0.5) sum += own;
    FragColor = sum;
}
""" % DEFOCUS_TAPS
# Each tap gathers only the light below the highlight threshold; the excess goes to the sprites.
_GATHER = _GATHER.replace("uniform float uMaxRadius;", "uniform float uMaxRadius;\nuniform sampler2D uBelow;"
                          ).replace("sum += textureLod(uColour, uv, level) * reach", "sum += textureLod(uBelow, uv, 0.0) * reach")
_CLIP = """#version 460 core
out vec4 FragColor;
uniform sampler2D uColour;
uniform int uLevel;
uniform float uHighlight;
// A highlight is light above its surroundings (the mean two levels coarser) and above the floor.
float sceneHighlightAt(sampler2D colour, ivec2 texel, int level, float floorLevel) {
    vec2 uv = (vec2(texel) + 0.5) / vec2(textureSize(colour, level));
    float local = dot(textureLod(colour, uv, float(level + 2)).rgb, vec3(0.2126, 0.7152, 0.0722));
    return max(floorLevel, local);
}
void main() {
    vec4 c = texelFetch(uColour, ivec2(gl_FragCoord.xy), uLevel);
    float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    float limit = sceneHighlightAt(uColour, ivec2(gl_FragCoord.xy), uLevel, uHighlight);
    FragColor = l > limit ? vec4(c.rgb * (limit / l), c.a) : c;
}
"""
_SPRITE_VERTEX = """#version 460 core
uniform sampler2D uColour;
uniform sampler2D uCircle;
uniform int uLevel;
uniform float uHighlight;
uniform vec2 uSize;
out vec2 vOffset;
flat out float vCircle;
flat out vec3 vLight;
// A highlight is light above its surroundings (the mean two levels coarser) and above the floor.
float sceneHighlightAt(sampler2D colour, ivec2 texel, int level, float floorLevel) {
    vec2 uv = (vec2(texel) + 0.5) / vec2(textureSize(colour, level));
    float local = dot(textureLod(colour, uv, float(level + 2)).rgb, vec3(0.2126, 0.7152, 0.0722));
    return max(floorLevel, local);
}
void main() {
    ivec2 grid = textureSize(uColour, uLevel);
    ivec2 texel = ivec2(gl_InstanceID % grid.x, gl_InstanceID / grid.x);
    vec4 c = texelFetch(uColour, texel, uLevel);
    vec2 circleData = texelFetch(uCircle, texel, uLevel).rg;
    float circle = circleData.y > 1e-4 ? circleData.x / circleData.y : 0.0;
    float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1)) * 2.0 - 1.0;
    float limit = sceneHighlightAt(uColour, texel, uLevel, uHighlight);
    if (l <= limit || circle < 1.5) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    float texelPx = float(1 << uLevel);
    // The texel's excess light, in pixel units, spread over its circle's area.
    vLight = c.rgb * (1.0 - limit / l) * texelPx * texelPx / (3.14159265 * circle * circle);
    vCircle = circle;
    vOffset = corner * (circle + 1.0);
    vec2 centre = (vec2(texel) + 0.5) * texelPx;
    gl_Position = vec4((centre + vOffset) / uSize * 2.0 - 1.0, 0.0, 1.0);
}
"""
_SPRITE_FRAGMENT = """#version 460 core
out vec4 FragColor;
in vec2 vOffset;
flat in float vCircle;
flat in vec3 vLight;
void main() {
    float d = length(vOffset);
    float inside = clamp(vCircle - d + 0.5, 0.0, 1.0);
    if (inside <= 0.0) discard;
    // A lens disc: even, its edge a little brighter (the mean of this profile over the disc is ~1).
    float rim = 0.88 + 0.3 * smoothstep(0.55, 1.0, d / vCircle);
    FragColor = vec4(vLight * inside * rim, 0.0);
}
"""


class DefocusLayer:
    """A near layer drawn sharp with each pixel's circle of confusion, then spread over those circles."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._size = (0, 0)
        self._colour = 0
        self._circle = 0
        self._fbo = 0
        self._program = 0
        self._sprites = 0
        self._clip = 0
        self._below = 0
        self._below_fbo = 0
        self._below_size = (0, 0)
        self._vao = 0
        self._saved = None

    def has_resources(self) -> bool:
        return bool(self._colour or self._circle or self._fbo or self._program or self._sprites or self._clip
                    or self._below or self._below_fbo or self._vao)

    def _texture(self, internal, width, height) -> int:
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        texture = int(name[0])
        levels = max(width, height).bit_length()
        gl.glTextureStorage2D(texture, levels, internal, width, height)
        gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_NEAREST)
        gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
        return texture

    def _allocate(self, width: int, height: int) -> None:
        self._drop_targets()
        self._colour = self._texture(gl.GL_RGBA16F, width, height)
        self._circle = self._texture(gl.GL_RG16F, width, height)
        name = (ctypes.c_uint * 1)()
        gl.glCreateFramebuffers(1, name)
        self._fbo = int(name[0])
        gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._colour, 0)
        gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT1, self._circle, 0)
        gl.glNamedFramebufferDrawBuffers(self._fbo, 2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
        if gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"{self.label}: defocus layer incomplete at {width}x{height}")
        self._size = (width, height)
        if not self._program:
            self._program = compile_program(_VERTEX, _GATHER, label=f"{self.label} defocus")
            self._sprites = compile_program(_SPRITE_VERTEX, _SPRITE_FRAGMENT, label=f"{self.label} bokeh")
            self._clip = compile_program(_VERTEX, _CLIP, label=f"{self.label} defocus clip")
            gl.glCreateVertexArrays(1, name)
            self._vao = int(name[0])

    def warm(self, width: int, height: int, max_radius: float) -> bool:
        """One warm-up step: True when the layer is allocated at this size (programs compiled) with the read level
        ``composite(max_radius)`` clips into, else allocate the next of them now (on a hidden frame) instead of at
        the first ``begin`` / ``composite``."""
        if self._size != (int(width), int(height)) or not self._fbo:
            self._allocate(int(width), int(height))
            return False
        size = self._read_size(max_radius)[1:]
        if self._below_size != size or not self._below:
            self._ensure_below(*size)
            return False
        return True

    def _read_size(self, max_radius: float) -> tuple[int, int, int]:
        """The gather's read level for ``max_radius`` (as in the shader) and its size."""
        tap_area = math.pi * max_radius * max_radius / DEFOCUS_TAPS
        level = max(int(math.floor(math.log2(max(math.sqrt(tap_area), 1.0)))), 0)
        return level, max(self._size[0] >> level, 1), max(self._size[1] >> level, 1)

    def begin(self, width: int, height: int) -> None:
        if self._size != (int(width), int(height)) or not self._fbo:
            self._allocate(int(width), int(height))
        self._saved = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                       [(bool(gl.glIsEnabledi(gl.GL_BLEND, i)),
                         gl_query.get_indexed_int(gl.GL_BLEND_SRC_RGB, i), gl_query.get_indexed_int(gl.GL_BLEND_DST_RGB, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_SRC_ALPHA, i), gl_query.get_indexed_int(gl.GL_BLEND_DST_ALPHA, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_EQUATION_RGB, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_EQUATION_ALPHA, i)) for i in range(2)],
                       bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK)), gl_query.is_enabled(gl.GL_DEPTH_TEST),
                       # Colour masks are per draw buffer index, not per framebuffer: a caller's masked index (a
                       # scene target's emission outside emission_writes()) would drop the circles here.
                       [[bool(v) for v in gl.glGetBooleani_v(gl.GL_COLOR_WRITEMASK, i)] for i in range(2)])
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
        for i in range(2):
            gl.glColorMaski(i, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE, gl.GL_TRUE)
        gl.glViewport(0, 0, *self._size)
        gl.glClearBufferfv(gl.GL_COLOR, 0, (0.0, 0.0, 0.0, 0.0))
        gl.glClearBufferfv(gl.GL_COLOR, 1, (0.0, 0.0, 0.0, 0.0))
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_FALSE)
        gl.glEnablei(gl.GL_BLEND, 0)
        gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
        gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnablei(gl.GL_BLEND, 1)
        gl.glBlendEquationSeparatei(1, gl.GL_MAX, gl.GL_MAX)
        gl.glBlendFuncSeparatei(1, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)

    def end(self) -> None:
        framebuffer, viewport, blends, depth_mask, depth_test, masks = self._saved
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
        for i, mask in enumerate(masks):
            gl.glColorMaski(i, *mask)
        gl.glViewport(*viewport)
        for i, (enabled, src_rgb, dst_rgb, src_a, dst_a, eq_rgb, eq_a) in enumerate(blends):
            gl.glBlendFuncSeparatei(i, src_rgb, dst_rgb, src_a, dst_a)
            gl.glBlendEquationSeparatei(i, eq_rgb, eq_a)
            (gl.glEnablei if enabled else gl.glDisablei)(gl.GL_BLEND, i)
        gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
        (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
        self._saved = None

    def composite(self, max_radius: float, highlight: float = 0.25) -> None:
        """Spread the layer over its circles and lay it over the bound framebuffer (premultiplied over); light above
        ``highlight`` (texel-averaged luminance) and its surroundings becomes round discs."""
        program = self._program
        prior_program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        prior_vao = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        prior_active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        blend = (bool(gl.glIsEnabledi(gl.GL_BLEND, 0)), gl_query.get_indexed_int(gl.GL_BLEND_SRC_RGB, 0),
                 gl_query.get_indexed_int(gl.GL_BLEND_DST_RGB, 0), gl_query.get_indexed_int(gl.GL_BLEND_SRC_ALPHA, 0),
                 gl_query.get_indexed_int(gl.GL_BLEND_DST_ALPHA, 0))
        depth_test = gl_query.is_enabled(gl.GL_DEPTH_TEST)
        units = []
        for unit in range(3):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            units.append(gl_query.get_int(gl.GL_TEXTURE_BINDING_2D))
        framebuffer = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        # The gather's read level (as in the shader), so the sprites and the gather split the same texels.
        level, width, height = self._read_size(max_radius)
        try:
            gl.glGenerateTextureMipmap(self._colour)
            gl.glGenerateTextureMipmap(self._circle)
            gl.glDisable(gl.GL_DEPTH_TEST)
            for unit, texture in ((0, self._colour), (1, self._circle)):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glBindVertexArray(self._vao)
            # The read level with each texel clipped at the threshold (what the gather spreads).
            self._ensure_below(width, height)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._below_fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisablei(gl.GL_BLEND, 0)
            gl.glUseProgram(self._clip)
            gl.glUniform1i(gl.glGetUniformLocation(self._clip, "uColour"), 0)
            gl.glUniform1i(gl.glGetUniformLocation(self._clip, "uLevel"), level)
            gl.glUniform1f(gl.glGetUniformLocation(self._clip, "uHighlight"), float(highlight))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glViewport(*viewport)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glActiveTexture(gl.GL_TEXTURE2)
            gl.glBindTexture(gl.GL_TEXTURE_2D, self._below)
            gl.glUseProgram(program)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uColour"), 0)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uCircle"), 1)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uBelow"), 2)
            gl.glUniform1f(gl.glGetUniformLocation(program, "uMaxRadius"), float(max_radius))
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
            if max_radius >= 0.5:
                gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
                gl.glUseProgram(self._sprites)
                gl.glUniform1i(gl.glGetUniformLocation(self._sprites, "uColour"), 0)
                gl.glUniform1i(gl.glGetUniformLocation(self._sprites, "uCircle"), 1)
                gl.glUniform1i(gl.glGetUniformLocation(self._sprites, "uLevel"), level)
                gl.glUniform1f(gl.glGetUniformLocation(self._sprites, "uHighlight"), float(highlight))
                gl.glUniform2f(gl.glGetUniformLocation(self._sprites, "uSize"), float(self._size[0]), float(self._size[1]))
                gl.glDrawArraysInstanced(gl.GL_TRIANGLE_STRIP, 0, 4, width * height)
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glViewport(*viewport)
            for unit in (2, 1, 0):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, units[unit])
            gl.glActiveTexture(prior_active)
            gl.glUseProgram(prior_program)
            gl.glBindVertexArray(prior_vao)
            enabled, src_rgb, dst_rgb, src_a, dst_a = blend
            gl.glBlendFuncSeparatei(0, src_rgb, dst_rgb, src_a, dst_a)
            (gl.glEnablei if enabled else gl.glDisablei)(gl.GL_BLEND, 0)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)

    def _ensure_below(self, width: int, height: int) -> None:
        if self._below_size == (width, height) and self._below:
            return
        self._drop_below()
        name = (ctypes.c_uint * 1)()
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        self._below = int(name[0])
        gl.glTextureStorage2D(self._below, 1, gl.GL_RGBA16F, width, height)
        for parameter in (gl.GL_TEXTURE_MIN_FILTER, gl.GL_TEXTURE_MAG_FILTER):
            gl.glTextureParameteri(self._below, parameter, gl.GL_LINEAR)
        for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T):
            gl.glTextureParameteri(self._below, wrap, gl.GL_CLAMP_TO_EDGE)
        gl.glCreateFramebuffers(1, name)
        self._below_fbo = int(name[0])
        gl.glNamedFramebufferTexture(self._below_fbo, gl.GL_COLOR_ATTACHMENT0, self._below, 0)
        self._below_size = (width, height)

    def _drop_below(self) -> None:
        if self._below_fbo:
            gl.glDeleteFramebuffers(1, [self._below_fbo])
        if self._below:
            gl.glDeleteTextures(1, [self._below])
        self._below = self._below_fbo = 0
        self._below_size = (0, 0)

    def _drop_targets(self) -> None:
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        for texture in (self._colour, self._circle):
            if texture:
                gl.glDeleteTextures(1, [texture])
        self._colour = self._circle = self._fbo = 0
        self._size = (0, 0)
        self._drop_below()

    def release(self) -> None:
        self._drop_targets()
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        for program in (self._program, self._sprites, self._clip):
            if program:
                gl.glDeleteProgram(program)
        self._program = self._sprites = self._clip = self._vao = 0


__all__ = ["DEFOCUS_TAPS", "DefocusLayer", "SCENE_DEFOCUS_GLSL"]
