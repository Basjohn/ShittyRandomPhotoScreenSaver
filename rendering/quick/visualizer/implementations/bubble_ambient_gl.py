"""Bubble's opt-in *under-bubble* decorative layer, composited in the Bubble shader.

One transparent, content-local RGBA target holds at most 192 GPU point sprites.
The existing fullscreen Bubble shader samples it *after the gradient and before*
its original wake, ghost and hero loops. Nothing touches the bubble simulator,
its RNG, 110-body shader loop, scene clipping or persistent render clock.

Particle glow is real emitted light: while any particle glows, a second,
same-sized half-float (RGBA16F) attachment accumulates its *linear-light* radiance
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
from pathlib import Path

import numpy as np
from OpenGL import GL as gl

from rendering.gl_programs.portable import block_declaration, block_layout_from_glsl, pack_block
from rendering.quick.render.gl_resources import compile_program, delete_program
from rendering.quick.scene3d.uniforms import PassBlocks
from rendering.quick import gl_query
from widgets.spotify_visualizer import shaders as shader_package
from widgets.spotify_visualizer.bubble_ambient import (
    MAX_MICROBUBBLES, MAX_PARTICLES, RECORD_STRIDE,
)
from widgets.spotify_visualizer.bubble_ambient_geometry import (
    ambient_target_size, ambient_occluder_vertices, MAX_AMBIENT_TEXTURE_EDGE,
)


def _ambient_programs():
    """The two ambient programs' sources from their shader files beside ``bubble.frag`` (one source for this renderer
    and the native core's bake, ``tools/regen_qrc.py --shaders``), composed as the loader composes them, and the points'
    block layout read from its own declaration."""
    from widgets.spotify_visualizer.shaders import compose_shader_source

    folder = Path(shader_package.__file__).resolve().parent
    sources = {name: compose_shader_source(folder / name) for name in AMBIENT_SHADER_FILES}
    points_block = block_layout_from_glsl(block_declaration(sources["bubble_ambient_points.frag"],
                                                            "BubbleAmbientPoints"))
    return sources, points_block


#: The ambient layer's shader files (``widgets/spotify_visualizer/shaders``): the points and the hero-bubble mask.
AMBIENT_SHADER_FILES = ("bubble_ambient_points.vert", "bubble_ambient_points.frag",
                        "bubble_ambient_mask.vert", "bubble_ambient_mask.frag")
_SOURCES, _POINT_BLOCK = _ambient_programs()
_POINT_VERTEX = _SOURCES["bubble_ambient_points.vert"]
_POINT_FRAGMENT = _SOURCES["bubble_ambient_points.frag"]
_OCCLUDER_VERTEX = _SOURCES["bubble_ambient_mask.vert"]
_OCCLUDER_FRAGMENT = _SOURCES["bubble_ambient_mask.frag"]


# The state fence reads through ``rendering.quick.gl_query`` (the GL entry points directly, as the shared
# Quick fence does): PyOpenGL's wrappers allocate a numpy array per query, and this pass makes twenty of
# them every frame. Same driver functions, same names, same order.


# The light attachment: linear radiance in .rgb of an RGBA16F (N1.7: QRhi has no R11G11B10F; RGB10A2 is unorm and
# has no headroom). Its alpha is written 0 by the particles and erased with the rest by the hero mask; nothing reads
# it.
_LIGHT_FORMAT = gl.GL_RGBA16F


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
        self._blocks = PassBlocks("Bubble ambience", block_bytes=_POINT_BLOCK.size)
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
            if not set(names) <= {name for name, _kind in _POINT_BLOCK.fields}:
                raise RuntimeError('Bubble ambient GL block incomplete')
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
            self._program,self._vao,self._vbo=program,vao,vbo
            self._occluder_program,self._occluder_vao,self._occluder_vbo=mask_program,mask_vao,mask_vbo
            # The points' block ring, allocated with the programs.
            self._blocks.warm()
        except Exception:
            if mask_vbo: gl.glDeleteBuffers(1,[mask_vbo])
            if mask_vao: gl.glDeleteVertexArrays(1,[mask_vao])
            if mask_program: delete_program(mask_program)
            if vbo: gl.glDeleteBuffers(1,[vbo])
            if vao: gl.glDeleteVertexArrays(1,[vao])
            if program: delete_program(program)
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
                self._light_texture = self._new_texture(width, height, _LIGHT_FORMAT, gl.GL_FLOAT)
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
                light_texture = self._new_texture(width, height, _LIGHT_FORMAT, gl.GL_FLOAT)
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
            block = pack_block(_POINT_BLOCK, {'uTexelScale': texel_scale, 'uSpriteScale': sprite_scale,
                                              'uGlowSpread': glow_spread, 'uMicroColor': tuple(micro_color),
                                              'uParticleColor': tuple(particle_color)})
            gl.glBindVertexArray(self._vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER,self._vbo)
            gl.glBufferSubData(gl.GL_ARRAY_BUFFER,0,data[:len(points)].nbytes,data[:len(points)])
            with self._blocks.bound(block):
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
            # The caller's program comes back only while it lives: one deleted while current went with the switch
            # to this pass's program, and naming it again raises GL_INVALID_VALUE.
            gl.glUseProgram(program if program and gl.glIsProgram(program) else 0)
            gl.glBindTexture(gl.GL_TEXTURE_2D,texture_before)
            gl.glActiveTexture(texture_unit)

    def release_resources(self) -> None:
        if self._fbo: gl.glDeleteFramebuffers(1,[self._fbo])
        if self._texture: gl.glDeleteTextures([self._texture])
        if self._light_texture: gl.glDeleteTextures([self._light_texture])
        if self._occluder_vbo: gl.glDeleteBuffers(1,[self._occluder_vbo])
        if self._occluder_vao: gl.glDeleteVertexArrays(1,[self._occluder_vao])
        if self._occluder_program: delete_program(self._occluder_program)
        if self._vbo: gl.glDeleteBuffers(1,[self._vbo])
        if self._vao: gl.glDeleteVertexArrays(1,[self._vao])
        if self._program: delete_program(self._program)
        self._blocks.release()
        self._fbo = self._texture = self._light_texture = self._vbo = self._vao = self._program = 0
        self._occluder_vbo = self._occluder_vao = self._occluder_program = 0
        self._target_size = (0,0)


__all__ = ['QuickBubbleAmbientPoints','ambient_target_size','MAX_AMBIENT_TEXTURE_EDGE']
