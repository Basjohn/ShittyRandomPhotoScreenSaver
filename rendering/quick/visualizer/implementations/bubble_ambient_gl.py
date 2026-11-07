"""Bubble's opt-in *under-bubble* decorative layer, composited in the Bubble shader.

One transparent, content-local RGBA target holds at most 192 GPU point sprites.
The existing fullscreen Bubble shader samples it *after the gradient and before*
its original wake, ghost and hero loops. Nothing touches the bubble simulator,
its RNG, 110-body shader loop, scene clipping or persistent render clock.

Particle glow is real emitted light: while any particle glows, a second,
same-sized R11F_G11F_B10F float attachment accumulates its *linear-light* radiance
additively (a bright energy-conserving core plus a smooth, monotonic halo in
the particle's own hue). The Bubble shader adds that light over the gradient in
linear space and lets it fill the remaining headroom without clipping
(``bubble.frag``). The 8-bit coverage attachment, and with it the accepted
microbubble look, is unchanged.

No target or GL resources exist when the optional feature has never been used,
and the light attachment exists only while some particle glows. The target
respects the content aspect and bounded physical resolution. The main Bubble
shader performs the final content/stencil clip, including rotation.
"""
from __future__ import annotations

import ctypes

import numpy as np
from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from rendering.quick import gl_query
from widgets.spotify_visualizer.bubble_ambient import (
    MAX_MICROBUBBLES, MAX_PARTICLES, RECORD_STRIDE,
)
from widgets.spotify_visualizer.bubble_ambient_geometry import (
    ambient_target_size, ambient_occluder_vertices, MAX_AMBIENT_TEXTURE_EDGE,
)


_POINT_VERTEX = """#version 460 core
layout(location=0) in vec4 aPoint;  // normalized x/y, logical diameter px, opacity
layout(location=1) in vec2 aOther;  // glow, class 0 microbubble / 1 particle
uniform float uTexelScale;
uniform float uSpriteScale;
uniform float uGlowSpread;
out float vOpacity;
out float vGlow;
out float vClass;
out float vCoreRatio;
out float vSpriteRadius;  // texels
out float vCoreRadius;    // texels, the authored physical core
out float vHaloRadius;    // texels, where the light reaches zero
void main() {
    // The FBO is in the unrotated *content* coordinate system. Sampling from
    // Bubble's logical UV maps the decoration through the same physical camera,
    // including quarter turns and extreme CUSTOM viewport shape changes.
    gl_Position = vec4(aPoint.x * 2.0 - 1.0, 1.0 - aPoint.y * 2.0, 0.0, 1.0);
    float coreDiameterPx = aPoint.z * uTexelScale * uSpriteScale;
    float size = coreDiameterPx;
    vHaloRadius = 0.0;
    if (aOther.y > 0.5) {
        // The core's drawn extent: at least 2.2 texels across (spread below
        // that), plus its filter edge (>= 1 texel each side) and a texel margin.
        float coreExtent = 2.0 * max(0.3875 * coreDiameterPx, 1.1) + 2.0 * max(1.0, 0.1375 * coreDiameterPx) + 2.0;
        // Light-only footprint, explicitly tunable. It follows the light (the
        // glow strength and Glow Spread) and never the musical core size, and
        // a sub-texel core keeps a legible halo (sized from its 2-texel floor).
        float haloDiameter = aOther.x > 0.001
            ? max(coreDiameterPx, 2.0) * mix(8.0, 12.0, clamp(aOther.x / 6.0, 0.0, 1.0))
                * clamp(uGlowSpread, 0.6, 2.0)
            : 0.0;
        size = max(coreExtent, haloDiameter);
        vHaloRadius = 0.5 * min(haloDiameter, 128.0);
    }
    gl_PointSize = clamp(size, 1.0, 128.0);
    vSpriteRadius = 0.5 * gl_PointSize;
    vCoreRadius = 0.5 * coreDiameterPx;
    vCoreRatio = min(1.0, coreDiameterPx / gl_PointSize);
    vOpacity = aPoint.w;
    vGlow = aOther.x;
    vClass = aOther.y;
}
"""

_POINT_FRAGMENT = """#version 460 core
in float vOpacity;
in float vGlow;
in float vClass;
in float vCoreRatio;
in float vSpriteRadius;
in float vCoreRadius;
in float vHaloRadius;
uniform vec4 uMicroColor;
uniform vec4 uParticleColor;
layout(location=0) out vec4 fragColor;   // premultiplied sRGB coverage (8-bit)
layout(location=1) out vec4 fragLight;   // linear-light radiance (R11G11B10 float), additive

vec3 srgbToLinear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void main() {
    vec2 p = 2.0 * (gl_PointCoord - vec2(0.5));
    float d = length(p);
    if (d > 1.0) discard;
    float alpha;
    vec3 rgb;
    vec3 light = vec3(0.0);
    if (vClass < 0.5) {
        float ring = smoothstep(0.43,0.68,d) * (1.0-smoothstep(0.68,0.96,d));
        float glass = (1.0-smoothstep(0.10,0.90,d))*0.10;
        float glint = (1.0-smoothstep(0.0,0.30,length(p-vec2(-0.38,0.32))))*0.60;
        alpha = clamp(ring + glass + glint,0.0,1.0) * uMicroColor.a;
        rgb = mix(uMicroColor.rgb,vec3(1.0),glint*0.28);
    } else {
        // Distances in texels from the true (sub-pixel) centre: gl_PointCoord is
        // exact, so the profile is shift-invariant as the particle drifts.
        float r = d * vSpriteRadius;
        // Fixed physical core, never breathing. It keeps the accepted edge
        // (half coverage at 0.775 of the authored radius, softening with size),
        // but a core too small to sample is spread to a 1.1-texel radius with
        // its area share of the light and an edge of at least one texel, so
        // its total light no longer depends on where it falls between pixel
        // centres (sub-pixel cores used to twinkle and vanish). Coverage blends
        // in sRGB, so its share takes the display-gamma inverse: on dark water
        // the spread core keeps the same total light.
        float edgeRadius = 0.775 * vCoreRadius;
        float coreRadius = max(edgeRadius, 1.1);
        float coreEnergy = min(1.0, (edgeRadius * edgeRadius) / (coreRadius * coreRadius));
        float edge = max(1.0, 0.275 * vCoreRadius);
        float coreShape = 1.0 - smoothstep(coreRadius - edge, coreRadius + edge, r);
        alpha = pow(coreEnergy, 1.0 / 2.2) * coreShape * uParticleColor.a;
        rgb = uParticleColor.rgb;
        float response = clamp(max(0.0, vGlow) / 3.0, 0.0, 1.0);
        if (response > 0.0 && vHaloRadius > 0.0) {
            // Emitted light in LINEAR light: a hot core (the core itself shining,
            // so it can exceed its own surface colour) and one smooth halo that
            // falls monotonically from the core (no dark moat), with a tight bloom
            // and a soft inverse-square-like tail, in the particle's own hue with
            // its chroma deepened (neutral colours stay neutral).
            vec3 lin = srgbToLinear(uParticleColor.rgb);
            float luma = dot(lin, vec3(0.2126, 0.7152, 0.0722));
            vec3 hue = max(mix(vec3(luma), lin, 1.6), vec3(0.0));
            float x = r / vHaloRadius;
            float bloom = exp(-x * x * 30.0);
            float tail = 1.0 / (1.0 + 25.0 * x * x);
            float fade = 1.0 - smoothstep(0.5, 1.0, x);
            float halo = (0.5 * bloom + 0.5 * tail) * fade;
            light = (lin * coreEnergy * coreShape * 1.6 + hue * halo) * response * uParticleColor.a;
        }
    }
    alpha = clamp(alpha*vOpacity,0.0,1.0);
    light *= vOpacity;
    if (alpha < 0.002 && max(max(light.r, light.g), light.b) <= 0.0) discard;
    // Coverage keeps the accepted premultiplied over-blend; light is additive
    // radiance that may exceed 1 where halos overlap (the Bubble shader maps it).
    fragColor = vec4(rgb * alpha, alpha);
    fragLight = vec4(light, 0.0);
}
"""

_OCCLUDER_VERTEX = """#version 460 core
layout(location=0) in vec2 aPosition;
layout(location=1) in vec2 aUnitCircle;
layout(location=2) in float aOcclusionAlpha;
out vec2 vUnitCircle;
out float vOcclusionAlpha;
void main() {
    gl_Position = vec4(aPosition.x*2.0-1.0, 1.0-aPosition.y*2.0, 0.0, 1.0);
    vUnitCircle = aUnitCircle;
    vOcclusionAlpha = aOcclusionAlpha;
}
"""

_OCCLUDER_FRAGMENT = """#version 460 core
in vec2 vUnitCircle;
in float vOcclusionAlpha;
layout(location=0) out vec4 fragColor;
layout(location=1) out vec4 fragLight;
void main() {
    float distanceFromCentre = length(vUnitCircle);
    float aa = max(fwidth(distanceFromCentre), 0.0001);
    float coverage = (1.0-smoothstep(1.0-aa, 1.0+aa, distanceFromCentre))
        * clamp(vOcclusionAlpha, 0.0, 1.0);
    if (coverage <= 0.0) discard;
    // With GL_ZERO / GL_ONE_MINUS_SRC_ALPHA this removes ONLY the ambience
    // (its coverage and its light) under actual hero surfaces; the gradient
    // and Bubble remain intact.
    fragColor = vec4(0.0, 0.0, 0.0, coverage);
    fragLight = vec4(0.0, 0.0, 0.0, coverage);
}
"""


# The state fence reads through ``rendering.quick.gl_query`` (the GL entry points directly, as the shared
# Quick fence does): PyOpenGL's wrappers allocate a numpy array per query, and this pass makes twenty of
# them every frame. Same driver functions, same names, same order.


def _points_glow(points: tuple[float, ...]) -> bool:
    """True when any particle record emits light (glow is the record's fifth field)."""
    return max(points[4::RECORD_STRIDE], default=0.0) > 0.0


class QuickBubbleAmbientPoints:
    """Render tiny decoration to an owned premultiplied transparent texture.

    Returned textures are borrowed for the current draw only; this object owns
    their lifetime and must be retired by the Bubble renderer's GL context.
    """

    def __init__(self) -> None:
        self._program = self._vao = self._vbo = 0
        self._occluder_program = self._occluder_vao = self._occluder_vbo = 0
        self._fbo = self._texture = self._light_texture = 0
        self._target_size = (0, 0)
        self._uniforms: dict[str, int] = {}
        self._data = np.zeros((MAX_MICROBUBBLES+MAX_PARTICLES, RECORD_STRIDE), dtype=np.float32)
        self._occluder_data = np.zeros((110 * 6, 5), dtype=np.float32)

    def _initialize(self) -> None:
        if self._program:
            return
        program = vao = vbo = mask_program = mask_vao = mask_vbo = 0
        try:
            program = compile_program(_POINT_VERTEX, _POINT_FRAGMENT, label='Bubble ambience underlay')
            vao = int(gl.glGenVertexArrays(1))
            vbo = int(gl.glGenBuffers(1))
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, self._data.nbytes, None, gl.GL_STREAM_DRAW)
            stride = RECORD_STRIDE * 4
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 4, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(16))
            names = ('uTexelScale','uSpriteScale','uGlowSpread','uMicroColor','uParticleColor')
            uniforms = {name:int(gl.glGetUniformLocation(program,name)) for name in names}
            if any(value < 0 for value in uniforms.values()):
                raise RuntimeError('Bubble ambient GL uniforms incomplete')
            # Explicit big-bubble mask. A few triangle quads are fast even when
            # the displayed circle exceeds GL_POINT_SIZE or at extreme viewports.
            mask_program = compile_program(_OCCLUDER_VERTEX, _OCCLUDER_FRAGMENT,
                                           label='Bubble ambience hero-bubble mask')
            mask_vao = int(gl.glGenVertexArrays(1))
            mask_vbo = int(gl.glGenBuffers(1))
            gl.glBindVertexArray(mask_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER,mask_vbo)
            gl.glBufferData(gl.GL_ARRAY_BUFFER,self._occluder_data.nbytes,None,gl.GL_STREAM_DRAW)
            mask_stride = 5 * 4
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0,2,gl.GL_FLOAT,gl.GL_FALSE,mask_stride,ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1,2,gl.GL_FLOAT,gl.GL_FALSE,mask_stride,ctypes.c_void_p(8))
            gl.glEnableVertexAttribArray(2)
            gl.glVertexAttribPointer(2,1,gl.GL_FLOAT,gl.GL_FALSE,mask_stride,ctypes.c_void_p(16))
            self._program,self._vao,self._vbo,self._uniforms=program,vao,vbo,uniforms
            self._occluder_program,self._occluder_vao,self._occluder_vbo=mask_program,mask_vao,mask_vbo
        except Exception:
            if mask_vbo: gl.glDeleteBuffers(1,[mask_vbo])
            if mask_vao: gl.glDeleteVertexArrays(1,[mask_vao])
            if mask_program: gl.glDeleteProgram(mask_program)
            if vbo: gl.glDeleteBuffers(1,[vbo])
            if vao: gl.glDeleteVertexArrays(1,[vao])
            if program: gl.glDeleteProgram(program)
            raise

    @staticmethod
    def _new_texture(width: int, height: int, internal: int, kind: int) -> int:
        texture = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        for axis in (gl.GL_TEXTURE_WRAP_S,gl.GL_TEXTURE_WRAP_T):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, axis, gl.GL_CLAMP_TO_EDGE)
        for filt in (gl.GL_TEXTURE_MIN_FILTER,gl.GL_TEXTURE_MAG_FILTER):
            gl.glTexParameteri(gl.GL_TEXTURE_2D, filt, gl.GL_LINEAR)
        gl.glTexImage2D(gl.GL_TEXTURE_2D,0,internal,width,height,0,gl.GL_RGBA,kind,None)
        return texture

    def _ensure_target(self, width: int, height: int, light: bool) -> None:
        if self._target_size == (width,height) and self._fbo and self._texture:
            if light == bool(self._light_texture):
                return
            # Glow toggled on an unchanged target: attach or retire only the light.
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
            if light:
                self._light_texture = self._new_texture(width, height, gl.GL_R11F_G11F_B10F, gl.GL_FLOAT)
                gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT1, gl.GL_TEXTURE_2D,
                                          self._light_texture, 0)
                gl.glDrawBuffers(2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
            else:
                gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT1, gl.GL_TEXTURE_2D, 0, 0)
                gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
                gl.glDeleteTextures([self._light_texture])
                self._light_texture = 0
            if gl.glCheckFramebufferStatus(gl.GL_DRAW_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError('Bubble ambient framebuffer incomplete')
            return
        fbo = texture = light_texture = 0
        # The caller saved/restores framebuffer and texture bindings.
        try:
            texture = self._new_texture(width, height, gl.GL_RGBA8, gl.GL_UNSIGNED_BYTE)
            if light:
                light_texture = self._new_texture(width, height, gl.GL_R11F_G11F_B10F, gl.GL_FLOAT)
            fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER,fbo)
            gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
            if light_texture:
                gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT1, gl.GL_TEXTURE_2D,
                                          light_texture, 0)
                gl.glDrawBuffers(2, [gl.GL_COLOR_ATTACHMENT0, gl.GL_COLOR_ATTACHMENT1])
            else:
                gl.glDrawBuffers(1, [gl.GL_COLOR_ATTACHMENT0])
            if gl.glCheckFramebufferStatus(gl.GL_DRAW_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError('Bubble ambient framebuffer incomplete')
        except Exception:
            if fbo: gl.glDeleteFramebuffers(1,[fbo])
            if texture: gl.glDeleteTextures([texture])
            if light_texture: gl.glDeleteTextures([light_texture])
            raise
        if self._fbo: gl.glDeleteFramebuffers(1,[self._fbo])
        if self._texture: gl.glDeleteTextures([self._texture])
        if self._light_texture: gl.glDeleteTextures([self._light_texture])
        self._fbo,self._texture,self._light_texture,self._target_size = fbo,texture,light_texture,(width,height)

    def render_texture(self, content_rect, dpr: float, points: tuple[float,...], *,
                       sprite_scale: float, glow_spread: float = 1.0,
                       micro_color: tuple[float,...], particle_color: tuple[float,...],
                       occluders: tuple[float,...] = (),
                       response_radius_scale: float = 1.0) -> tuple[int, int]:
        """Draw the decoration; return ``(coverage texture, light texture or 0)``."""
        if not points:
            return 0, 0
        if len(points)%RECORD_STRIDE or len(points)>self._data.size:
            raise ValueError('Unbounded Bubble ambient point input')
        if len(occluders) % 4 or len(occluders) > 110 * 4:
            raise ValueError('Unbounded Bubble ambient occluders')
        width,height,texel_scale = ambient_target_size(content_rect,dpr)
        light = _points_glow(points)
        # Preserve inherited Quick state; Qt may have an active rounded-stencil
        # clip on the display FBO. It must not apply to our texture-local FBO.
        draw_fb = gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        read_fb = gl_query.get_int(gl.GL_READ_FRAMEBUFFER_BINDING)
        viewport = gl_query.get_ints(gl.GL_VIEWPORT, 4)
        program = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        buffer = gl_query.get_int(gl.GL_ARRAY_BUFFER_BINDING)
        texture_unit = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        texture_before = gl_query.get_int(gl.GL_TEXTURE_BINDING_2D)
        blend = gl_query.is_enabled(gl.GL_BLEND)
        depth = gl_query.is_enabled(gl.GL_DEPTH_TEST)
        stencil = gl_query.is_enabled(gl.GL_STENCIL_TEST)
        scissor = gl_query.is_enabled(gl.GL_SCISSOR_TEST)
        point_size = gl_query.is_enabled(gl.GL_PROGRAM_POINT_SIZE)
        blend_factors = tuple(gl_query.get_int(p) for p in (gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB,
                         gl.GL_BLEND_SRC_ALPHA,gl.GL_BLEND_DST_ALPHA))
        blend_eq = tuple(gl_query.get_int(p) for p in (gl.GL_BLEND_EQUATION_RGB,gl.GL_BLEND_EQUATION_ALPHA))
        clear_color = gl_query.get_floats(gl.GL_COLOR_CLEAR_VALUE, 4)
        color_mask = gl_query.get_bools(gl.GL_COLOR_WRITEMASK, 4)
        try:
            self._initialize()
            self._ensure_target(width,height,light)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER,self._fbo)
            gl.glViewport(0,0,width,height)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glColorMask(gl.GL_TRUE,gl.GL_TRUE,gl.GL_TRUE,gl.GL_TRUE)
            gl.glClearColor(0.,0.,0.,0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glEnable(gl.GL_BLEND)
            # Coverage: premultiplied over (do not multiply RGB by alpha again).
            # Light: purely additive linear radiance in its own attachment.
            gl.glBlendEquationSeparate(gl.GL_FUNC_ADD,gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparate(gl.GL_ONE,gl.GL_ONE_MINUS_SRC_ALPHA,
                                   gl.GL_ONE,gl.GL_ONE_MINUS_SRC_ALPHA)
            if light:
                gl.glBlendFuncSeparatei(1, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
            data = self._data.reshape(-1)
            data[:len(points)] = points
            gl.glUseProgram(self._program)
            gl.glUniform1f(self._uniforms['uTexelScale'],texel_scale)
            gl.glUniform1f(self._uniforms['uSpriteScale'],sprite_scale)
            gl.glUniform1f(self._uniforms['uGlowSpread'],glow_spread)
            gl.glUniform4f(self._uniforms['uMicroColor'],*micro_color)
            gl.glUniform4f(self._uniforms['uParticleColor'],*particle_color)
            gl.glBindVertexArray(self._vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER,self._vbo)
            gl.glBufferSubData(gl.GL_ARRAY_BUFFER,0,data[:len(points)].nbytes,data[:len(points)])
            gl.glDrawArrays(gl.GL_POINTS,0,len(points)//RECORD_STRIDE)
            if occluders:
                vertices = ambient_occluder_vertices(occluders, width, height,
                                                     response_radius_scale)
                count = len(vertices)
                if count > len(self._occluder_data):
                    raise ValueError('Bubble ambience occlusion vertices exceed bounded capacity')
                self._occluder_data[:count] = vertices
                gl.glUseProgram(self._occluder_program)
                gl.glBindVertexArray(self._occluder_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER,self._occluder_vbo)
                gl.glBufferSubData(gl.GL_ARRAY_BUFFER,0,count*5*4,self._occluder_data[:count])
                # Erase premultiplied RGB, alpha and light under rendered hero circles.
                # No additional full-screen shader scans and no hero shape change.
                gl.glBlendFuncSeparate(gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA,
                                       gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDrawArrays(gl.GL_TRIANGLES,0,count)
            return self._texture, self._light_texture
        finally:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER,draw_fb)
            gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER,read_fb)
            gl.glViewport(*viewport)
            gl.glBlendEquationSeparate(*blend_eq)
            gl.glBlendFuncSeparate(*blend_factors)
            for enabled,cap in ((blend,gl.GL_BLEND),(depth,gl.GL_DEPTH_TEST),
                                (stencil,gl.GL_STENCIL_TEST),(scissor,gl.GL_SCISSOR_TEST),
                                (point_size,gl.GL_PROGRAM_POINT_SIZE)):
                (gl.glEnable if enabled else gl.glDisable)(cap)
            gl.glColorMask(*color_mask)
            gl.glClearColor(*clear_color)
            gl.glBindVertexArray(vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER,buffer)
            gl.glUseProgram(program)
            gl.glBindTexture(gl.GL_TEXTURE_2D,texture_before)
            gl.glActiveTexture(texture_unit)

    def release_resources(self) -> None:
        if self._fbo: gl.glDeleteFramebuffers(1,[self._fbo])
        if self._texture: gl.glDeleteTextures([self._texture])
        if self._light_texture: gl.glDeleteTextures([self._light_texture])
        if self._occluder_vbo: gl.glDeleteBuffers(1,[self._occluder_vbo])
        if self._occluder_vao: gl.glDeleteVertexArrays(1,[self._occluder_vao])
        if self._occluder_program: gl.glDeleteProgram(self._occluder_program)
        if self._vbo: gl.glDeleteBuffers(1,[self._vbo])
        if self._vao: gl.glDeleteVertexArrays(1,[self._vao])
        if self._program: gl.glDeleteProgram(self._program)
        self._fbo = self._texture = self._light_texture = self._vbo = self._vao = self._program = 0
        self._occluder_vbo = self._occluder_vao = self._occluder_program = 0
        self._target_size = (0,0)
        self._uniforms.clear()


__all__ = ['QuickBubbleAmbientPoints','ambient_target_size','MAX_AMBIENT_TEXTURE_EDGE']
