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

Nothing is allocated per frame after the first ``begin`` at a size; ``release`` drops the textures, framebuffer and
program.
"""
from __future__ import annotations

import ctypes

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


class DefocusLayer:
    """A near layer drawn sharp with each pixel's circle of confusion, then spread over those circles."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._size = (0, 0)
        self._colour = 0
        self._circle = 0
        self._fbo = 0
        self._program = 0
        self._vao = 0
        self._saved = None

    def has_resources(self) -> bool:
        return bool(self._colour or self._circle or self._fbo or self._program or self._vao)

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
            gl.glCreateVertexArrays(1, name)
            self._vao = int(name[0])

    def begin(self, width: int, height: int) -> None:
        if self._size != (int(width), int(height)) or not self._fbo:
            self._allocate(int(width), int(height))
        self._saved = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                       [(bool(gl.glIsEnabledi(gl.GL_BLEND, i)),
                         gl_query.get_indexed_int(gl.GL_BLEND_SRC_RGB, i), gl_query.get_indexed_int(gl.GL_BLEND_DST_RGB, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_SRC_ALPHA, i), gl_query.get_indexed_int(gl.GL_BLEND_DST_ALPHA, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_EQUATION_RGB, i),
                         gl_query.get_indexed_int(gl.GL_BLEND_EQUATION_ALPHA, i)) for i in range(2)],
                       bool(gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK)), gl_query.is_enabled(gl.GL_DEPTH_TEST))
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
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
        framebuffer, viewport, blends, depth_mask, depth_test = self._saved
        gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
        gl.glViewport(*viewport)
        for i, (enabled, src_rgb, dst_rgb, src_a, dst_a, eq_rgb, eq_a) in enumerate(blends):
            gl.glBlendFuncSeparatei(i, src_rgb, dst_rgb, src_a, dst_a)
            gl.glBlendEquationSeparatei(i, eq_rgb, eq_a)
            (gl.glEnablei if enabled else gl.glDisablei)(gl.GL_BLEND, i)
        gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
        (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
        self._saved = None

    def composite(self, max_radius: float) -> None:
        """Spread the layer over its circles and lay it over the bound framebuffer (premultiplied over)."""
        program = self._program
        prior_program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        prior_vao = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        prior_active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        blend = (bool(gl.glIsEnabledi(gl.GL_BLEND, 0)), gl_query.get_indexed_int(gl.GL_BLEND_SRC_RGB, 0),
                 gl_query.get_indexed_int(gl.GL_BLEND_DST_RGB, 0), gl_query.get_indexed_int(gl.GL_BLEND_SRC_ALPHA, 0),
                 gl_query.get_indexed_int(gl.GL_BLEND_DST_ALPHA, 0))
        depth_test = gl_query.is_enabled(gl.GL_DEPTH_TEST)
        units = []
        for unit in range(2):
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            units.append(gl_query.get_int(gl.GL_TEXTURE_BINDING_2D))
        try:
            gl.glGenerateTextureMipmap(self._colour)
            gl.glGenerateTextureMipmap(self._circle)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA, gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glUseProgram(program)
            for unit, texture in ((0, self._colour), (1, self._circle)):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uColour"), 0)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uCircle"), 1)
            gl.glUniform1f(gl.glGetUniformLocation(program, "uMaxRadius"), float(max_radius))
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        finally:
            for unit in (1, 0):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, units[unit])
            gl.glActiveTexture(prior_active)
            gl.glUseProgram(prior_program)
            gl.glBindVertexArray(prior_vao)
            enabled, src_rgb, dst_rgb, src_a, dst_a = blend
            gl.glBlendFuncSeparatei(0, src_rgb, dst_rgb, src_a, dst_a)
            (gl.glEnablei if enabled else gl.glDisablei)(gl.GL_BLEND, 0)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)

    def _drop_targets(self) -> None:
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        for texture in (self._colour, self._circle):
            if texture:
                gl.glDeleteTextures(1, [texture])
        self._colour = self._circle = self._fbo = 0
        self._size = (0, 0)

    def release(self) -> None:
        self._drop_targets()
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        if self._program:
            gl.glDeleteProgram(self._program)
        self._program = self._vao = 0


__all__ = ["DEFOCUS_TAPS", "DefocusLayer", "SCENE_DEFOCUS_GLSL"]
