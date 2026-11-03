"""Bubble's opt-in *under-bubble* decorative layer, composited in the Bubble shader.

One transparent, content-local RGBA target holds at most 192 GPU point sprites.
The existing fullscreen Bubble shader samples it *after the gradient and before*
its original wake, ghost and hero loops. Nothing touches the bubble simulator,
its RNG, 110-body shader loop, scene clipping or persistent render clock.

No target or GL resources exist when the optional feature has never been used.
The target respects the content aspect and bounded physical resolution. The
main Bubble shader performs the final content/stencil clip, including rotation.
"""
from __future__ import annotations

import ctypes

import numpy as np
from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from widgets.spotify_visualizer.bubble_ambient import (
    MAX_MICROBUBBLES, MAX_PARTICLES, RECORD_STRIDE,
)
from widgets.spotify_visualizer.bubble_ambient_geometry import (
    ambient_target_size, ambient_occluder_quads, MAX_AMBIENT_TEXTURE_EDGE,
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
void main() {
    // The FBO is in the unrotated *content* coordinate system. Sampling from
    // Bubble's logical UV maps the decoration through the same physical camera,
    // including quarter turns and extreme CUSTOM viewport shape changes.
    gl_Position = vec4(aPoint.x * 2.0 - 1.0, 1.0 - aPoint.y * 2.0, 0.0, 1.0);
    float coreDiameterPx = aPoint.z * uTexelScale * uSpriteScale;
    float spriteMultiplier = 1.0;
    if (aOther.y > 0.5) {
        // Explicitly tunable light-only footprint. Neither this value nor
        // musical amplitude can change the physical core diameter.
        spriteMultiplier = aOther.x > 0.001
            ? mix(8.0, 12.0, clamp(aOther.x / 6.0, 0.0, 1.0))
                * clamp(uGlowSpread, 0.6, 2.0)
            : 2.2;
    }
    gl_PointSize = clamp(coreDiameterPx * spriteMultiplier, 1.0, 128.0);
    // Needed when viewport growth or GL_POINT_SIZE's cap constrains the halo.
    // Compensating in the fragment retains the SAME physical core diameter.
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
uniform vec4 uMicroColor;
uniform vec4 uParticleColor;
out vec4 fragColor;
void main() {
    vec2 p = 2.0 * (gl_PointCoord - vec2(0.5));
    float d = length(p);
    if (d > 1.0) discard;
    float alpha;
    vec3 rgb;
    vec3 emission = vec3(0.0);
    if (vClass < 0.5) {
        float ring = smoothstep(0.43,0.68,d) * (1.0-smoothstep(0.68,0.96,d));
        float glass = (1.0-smoothstep(0.10,0.90,d))*0.10;
        float glint = (1.0-smoothstep(0.0,0.30,length(p-vec2(-0.38,0.32))))*0.60;
        alpha = clamp(ring + glass + glint,0.0,1.0) * uMicroColor.a;
        rgb = mix(uMicroColor.rgb,vec3(1.0),glint*0.28);
    } else {
        // Only the fixed-size core owns alpha. Core thresholds are fractions
        // of the actual point sprite width, so expanding or capping the HALO
        // cannot expand the solid body; the Slice 9 physical core is unchanged.
        float core = 1.0 - smoothstep(0.50 * vCoreRatio, 1.05 * vCoreRatio, d);
        alpha = core * uParticleColor.a;
        rgb = uParticleColor.rgb;
        // Fixed core + *hollow-centre* emitted light, not a shaded sphere.
        // The visible radiance emerges outside the core; a fast broad falloff
        // produces an airy aureole. Full settings never fill the sprite with
        // near-opaque grey. RGB contribution is independent of core alpha.
        // Contrast is shaped by the fast admitted small-bubble envelope in
        // the ambient solver, not by artificially long shader persistence.
        float response = clamp(max(0.0, vGlow) / 3.0, 0.0, 1.0);
        float rise = smoothstep(0.95 * vCoreRatio, 3.0 * vCoreRatio, d);
        float nearGlow = exp(-pow(d / 0.26, 1.65));
        float farGlow = exp(-pow(d / 0.72, 2.0));
        float falloff = rise * (0.27 * nearGlow + 0.23 * farGlow)
            * (1.0 - smoothstep(0.78, 1.0, d));
        emission = uParticleColor.rgb * response * falloff * uParticleColor.a;
    }
    alpha = clamp(alpha*vOpacity,0.0,1.0);
    emission *= vOpacity;
    if (alpha < 0.002 && max(max(emission.r, emission.g), emission.b) < 0.002) discard;
    // The owned RGBA target stores premultiplied coverage plus light. RGB may
    // legitimately exceed alpha: illumination is not surface opacity. Final
    // Bubble shading samples this as premultiplied radiance over the gradient.
    fragColor = vec4(rgb * alpha + emission, alpha);
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
out vec4 fragColor;
void main() {
    float distanceFromCentre = length(vUnitCircle);
    float aa = max(fwidth(distanceFromCentre), 0.0001);
    float coverage = (1.0-smoothstep(1.0-aa, 1.0+aa, distanceFromCentre))
        * clamp(vOcclusionAlpha, 0.0, 1.0);
    if (coverage <= 0.0) discard;
    // With GL_ZERO / GL_ONE_MINUS_SRC_ALPHA this removes ONLY the ambience
    // under actual big-bubble surfaces; the gradient and Bubble remain intact.
    fragColor = vec4(0.0, 0.0, 0.0, coverage);
}
"""


def _glint(name: int) -> int:
    result = gl.glGetIntegerv(name)
    try:
        return int(result)
    except TypeError:
        return int(result[0])


class QuickBubbleAmbientPoints:
    """Render tiny decoration to an owned premultiplied transparent texture.

    Returned texture is borrowed for the current draw only; this object owns
    its lifetime and must be retired by the Bubble renderer's GL context.
    """

    def __init__(self) -> None:
        self._program = self._vao = self._vbo = 0
        self._occluder_program = self._occluder_vao = self._occluder_vbo = 0
        self._fbo = self._texture = 0
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

    def _ensure_target(self, width: int, height: int) -> None:
        if self._target_size == (width,height) and self._fbo and self._texture:
            return
        fbo = texture = 0
        # The caller saved/restores framebuffer and texture bindings.
        try:
            texture = int(gl.glGenTextures(1))
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            for axis in (gl.GL_TEXTURE_WRAP_S,gl.GL_TEXTURE_WRAP_T):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, axis, gl.GL_CLAMP_TO_EDGE)
            for filt in (gl.GL_TEXTURE_MIN_FILTER,gl.GL_TEXTURE_MAG_FILTER):
                gl.glTexParameteri(gl.GL_TEXTURE_2D, filt, gl.GL_LINEAR)
            gl.glTexImage2D(gl.GL_TEXTURE_2D,0,gl.GL_RGBA8,width,height,0,gl.GL_RGBA,gl.GL_UNSIGNED_BYTE,None)
            fbo = int(gl.glGenFramebuffers(1))
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER,fbo)
            gl.glFramebufferTexture2D(gl.GL_DRAW_FRAMEBUFFER,gl.GL_COLOR_ATTACHMENT0,gl.GL_TEXTURE_2D,texture,0)
            if gl.glCheckFramebufferStatus(gl.GL_DRAW_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError('Bubble ambient framebuffer incomplete')
        except Exception:
            if fbo: gl.glDeleteFramebuffers(1,[fbo])
            if texture: gl.glDeleteTextures([texture])
            raise
        if self._fbo: gl.glDeleteFramebuffers(1,[self._fbo])
        if self._texture: gl.glDeleteTextures([self._texture])
        self._fbo,self._texture,self._target_size = fbo,texture,(width,height)

    def render_texture(self, content_rect, dpr: float, points: tuple[float,...], *,
                       sprite_scale: float, glow_spread: float = 1.0,
                       micro_color: tuple[float,...], particle_color: tuple[float,...],
                       occluders: tuple[float,...] = (),
                       response_radius_scale: float = 1.0) -> int:
        if not points:
            return 0
        if len(points)%RECORD_STRIDE or len(points)>self._data.size:
            raise ValueError('Unbounded Bubble ambient point input')
        if len(occluders) % 4 or len(occluders) > 110 * 4:
            raise ValueError('Unbounded Bubble ambient occluders')
        width,height,texel_scale = ambient_target_size(content_rect,dpr)
        # Preserve inherited Quick state; Qt may have an active rounded-stencil
        # clip on the display FBO. It must not apply to our texture-local FBO.
        draw_fb = _glint(gl.GL_DRAW_FRAMEBUFFER_BINDING)
        read_fb = _glint(gl.GL_READ_FRAMEBUFFER_BINDING)
        viewport = tuple(int(v) for v in gl.glGetIntegerv(gl.GL_VIEWPORT))
        program = _glint(gl.GL_CURRENT_PROGRAM)
        vao = _glint(gl.GL_VERTEX_ARRAY_BINDING)
        buffer = _glint(gl.GL_ARRAY_BUFFER_BINDING)
        texture_unit = _glint(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        texture_before = _glint(gl.GL_TEXTURE_BINDING_2D)
        blend = bool(gl.glIsEnabled(gl.GL_BLEND))
        depth = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST))
        stencil = bool(gl.glIsEnabled(gl.GL_STENCIL_TEST))
        scissor = bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
        point_size = bool(gl.glIsEnabled(gl.GL_PROGRAM_POINT_SIZE))
        blend_factors = tuple(_glint(p) for p in (gl.GL_BLEND_SRC_RGB, gl.GL_BLEND_DST_RGB,
                         gl.GL_BLEND_SRC_ALPHA,gl.GL_BLEND_DST_ALPHA))
        blend_eq = tuple(_glint(p) for p in (gl.GL_BLEND_EQUATION_RGB,gl.GL_BLEND_EQUATION_ALPHA))
        clear_color = tuple(float(v) for v in gl.glGetFloatv(gl.GL_COLOR_CLEAR_VALUE))
        color_mask = tuple(bool(v) for v in gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK))
        try:
            self._initialize()
            self._ensure_target(width,height)
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER,self._fbo)
            gl.glViewport(0,0,width,height)
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glColorMask(gl.GL_TRUE,gl.GL_TRUE,gl.GL_TRUE,gl.GL_TRUE)
            gl.glClearColor(0.,0.,0.,0.)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            gl.glEnable(gl.GL_BLEND)
            # The point shader emits premultiplied coverage PLUS emissive light.
            # Do not multiply RGB by alpha again, or the halo is washed out.
            gl.glBlendEquationSeparate(gl.GL_FUNC_ADD,gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparate(gl.GL_ONE,gl.GL_ONE_MINUS_SRC_ALPHA,
                                   gl.GL_ONE,gl.GL_ONE_MINUS_SRC_ALPHA)
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
                vertices = ambient_occluder_quads(occluders, width, height,
                                                  response_radius_scale)
                count = len(vertices) // 5
                if count > len(self._occluder_data):
                    raise ValueError('Bubble ambience occlusion vertices exceed bounded capacity')
                mask_data = self._occluder_data.reshape(-1)
                mask_data[:len(vertices)] = vertices
                gl.glUseProgram(self._occluder_program)
                gl.glBindVertexArray(self._occluder_vao)
                gl.glBindBuffer(gl.GL_ARRAY_BUFFER,self._occluder_vbo)
                gl.glBufferSubData(gl.GL_ARRAY_BUFFER,0,count*5*4,self._occluder_data[:count])
                # Erase premultiplied RGB and alpha under rendered hero circles. No
                # additional full-screen shader scans and no hero shape change.
                gl.glBlendFuncSeparate(gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA,
                                       gl.GL_ZERO,gl.GL_ONE_MINUS_SRC_ALPHA)
                gl.glDrawArrays(gl.GL_TRIANGLES,0,count)
            return self._texture
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
        if self._occluder_vbo: gl.glDeleteBuffers(1,[self._occluder_vbo])
        if self._occluder_vao: gl.glDeleteVertexArrays(1,[self._occluder_vao])
        if self._occluder_program: gl.glDeleteProgram(self._occluder_program)
        if self._vbo: gl.glDeleteBuffers(1,[self._vbo])
        if self._vao: gl.glDeleteVertexArrays(1,[self._vao])
        if self._program: gl.glDeleteProgram(self._program)
        self._fbo = self._texture = self._vbo = self._vao = self._program = 0
        self._occluder_vbo = self._occluder_vao = self._occluder_program = 0
        self._target_size = (0,0)
        self._uniforms.clear()


__all__ = ['QuickBubbleAmbientPoints','ambient_target_size','MAX_AMBIENT_TEXTURE_EDGE']
