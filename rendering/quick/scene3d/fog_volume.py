"""S3D-7 bounded fog volume: one camera's froxel grid of in-scatter and transmittance (see gl_programs/fog_volume.py).

``update(inject_program, view=..., lens=..., depth_range=..., grid=...)`` evaluates the consumer's medium program (from
``fog_inject_source``) at every cell and integrates the result; ``uniforms`` and ``bound()`` then let any pass that
includes ``MIST_GLSL`` read it (``mistTransmittance`` / ``mistOver``). The caller sets its medium's own uniforms on
the inject program through ``medium``; the owner sets the camera mapping and dispatches with its own barriers.

Two RGBA16F 3D textures, allocated at the first update of a grid size and reused while it holds; ``warm`` allocates
on a hidden frame instead. Nothing is allocated per frame. ``release`` deletes everything under the owning context.
A mirrored reflection camera uses its own instance (its view is ``mirror_view`` of the scene's).
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
import math
import weakref

import numpy as np
from OpenGL import GL as gl

from rendering.gl_programs.fog_volume import (FOG_COMPOSITE_FRAGMENT, FOG_FULLSCREEN_VERTEX, FOG_INTEGRATE_COMPUTE,
                                              fog_detail_noise, fog_march_source)
from rendering.gl_programs.mist import FOG_TEXTURE_UNIT
from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_compute_program
from .compute import bound_image, dispatch

MAX_FOG_CELLS = 256*256*128


class FogVolume:
    def __init__(self, label: str) -> None:
        self.label = label
        self._grid = (0, 0, 0)
        self._inject = 0
        self._integrated = 0
        self._steady = 0
        self._integrate_program = 0
        self._uniforms = None
        self._context_ref = None

    @property
    def has_resources(self) -> bool:
        return bool(self._inject or self._integrated or self._steady or self._integrate_program)

    @property
    def grid(self) -> tuple[int, int, int]:
        return self._grid

    @property
    def texture(self) -> int:
        return self._integrated

    @property
    def medium_texture(self) -> int:
        """The coarse medium (radiance rgb, extinction a) of the last update: a detail march's input."""
        return self._inject

    @property
    def steady_texture(self) -> int:
        """The coarse extinction share a detail march must not erode (R16F), from the last update."""
        return self._steady

    @property
    def uniforms(self) -> dict:
        """MIST_GLSL sampling uniforms for the last update (the volume must be ``bound()`` while drawing)."""
        if self._uniforms is None:
            raise RuntimeError(f"{self.label}: fog volume sampled before its first update")
        return dict(self._uniforms)

    def _check_context(self, *, admit: bool = False) -> None:
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError(f"{self.label}: fog volume GL work needs its owning current context")
        if self._context_ref is None and admit:
            self._context_ref = weakref.ref(current)
        if self._context_ref is None or self._context_ref() != current:
            raise RuntimeError(f"{self.label}: fog volume used in a foreign context")

    @staticmethod
    def _admit_grid(grid) -> tuple[int, int, int]:
        grid = tuple(int(v) for v in grid)
        if len(grid) != 3 or min(grid) < 1 or math.prod(grid) > MAX_FOG_CELLS:
            raise ValueError(f'Fog grid must be three positive sizes within {MAX_FOG_CELLS} cells')
        return grid

    def _allocate(self, grid) -> None:
        self._drop_textures()
        names = (ctypes.c_uint*3)()
        gl.glCreateTextures(gl.GL_TEXTURE_3D, 3, names)
        self._inject, self._integrated, self._steady = (int(n) for n in names)
        for texture in (self._inject, self._integrated, self._steady):
            gl.glTextureStorage3D(texture, 1, gl.GL_R16F if texture == self._steady else gl.GL_RGBA16F, *grid)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTextureParameteri(texture, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            for wrap in (gl.GL_TEXTURE_WRAP_S, gl.GL_TEXTURE_WRAP_T, gl.GL_TEXTURE_WRAP_R):
                gl.glTextureParameteri(texture, wrap, gl.GL_CLAMP_TO_EDGE)
        self._grid = grid

    def warm(self, grid) -> bool:
        """One warm-up step: True when already allocated at this grid, else allocate now (on a hidden frame)."""
        self._check_context(admit=True)
        grid = self._admit_grid(grid)
        if self._grid == grid and self._integrated:
            return True
        self._allocate(grid)
        return False

    def prepare_program(self) -> bool:
        """Compile one hidden-frame unit with legal ownership even if reveal is cancelled before update."""
        self._check_context(admit=True)
        if self._integrate_program:
            return True
        self._integrate_program=compile_compute_program(FOG_INTEGRATE_COMPUTE,label=f'{self.label} integrate')
        return False

    def update(self, inject_program: int, *, view, lens, depth_range, grid, medium=None, focus_depth=0.) -> None:
        """Evaluate and integrate the medium for one camera. ``view``: world->view (4x4, numpy row-major);
        ``lens``: (half-extent or tangent x, y, orthographic); ``depth_range``: (near, far) view depth."""
        self._check_context(admit=True)
        grid = self._admit_grid(grid)
        view = np.asarray(view, float)
        near, far = (float(v) for v in depth_range)
        if (view.shape != (4, 4) or not np.isfinite(view).all() or not near < far
                or not all(math.isfinite(v) for v in (near,far)) or (near<=0 and not bool(lens[2]))):
            raise ValueError('Fog update needs a finite ordered range; signed depths require Orthographic')
        ext_x, ext_y, orthographic = float(lens[0]), float(lens[1]), bool(lens[2])
        if not (ext_x > 0 and ext_y > 0 and math.isfinite(ext_x) and math.isfinite(ext_y)):
            raise ValueError('Fog lens extents must be finite and positive')
        if self._grid != grid or not self._integrated:
            self._allocate(grid)
        if not self._integrate_program:
            self._integrate_program = compile_compute_program(FOG_INTEGRATE_COMPUTE, label=f'{self.label} integrate')
        focus=float(focus_depth)
        if not math.isfinite(focus) or (focus!=0. and not near<focus<far):
            raise ValueError('Fog focus must lie inside the admitted depth interval')
        lens4 = (ext_x, ext_y, 1. if orthographic else 0., 4. if near<=0 or focus else 0.)
        range4 = (near, far, float(grid[2]), 1.+focus)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        try:
            gl.glUseProgram(inject_program)
            location = gl.glGetUniformLocation
            gl.glUniformMatrix4fv(location(inject_program, 'uFogInvView'), 1, gl.GL_TRUE,
                                  np.linalg.inv(view).astype(np.float32))
            gl.glUniform4f(location(inject_program, 'uFogLens'), *lens4)
            gl.glUniform4f(location(inject_program, 'uFogRange'), *range4)
            if medium is not None:
                medium(inject_program)
            with bound_image(0, self._inject, gl.GL_WRITE_ONLY, gl.GL_RGBA16F, layered=True), \
                    bound_image(1, self._steady, gl.GL_WRITE_ONLY, gl.GL_R16F, layered=True):
                dispatch(tuple(-(-n//4) for n in grid),
                         gl.GL_SHADER_IMAGE_ACCESS_BARRIER_BIT | gl.GL_TEXTURE_FETCH_BARRIER_BIT)
            gl.glUseProgram(self._integrate_program)
            gl.glUniform4f(location(self._integrate_program, 'uFogLens'), *lens4)
            gl.glUniform4f(location(self._integrate_program, 'uFogRange'), *range4)
            with bound_image(0, self._inject, gl.GL_READ_ONLY, gl.GL_RGBA16F, layered=True), \
                    bound_image(1, self._integrated, gl.GL_WRITE_ONLY, gl.GL_RGBA16F, layered=True):
                dispatch((-(-grid[0]//8), -(-grid[1]//8), 1), gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        finally:
            gl.glUseProgram(program_before)
        self._uniforms = dict(uFogVolume=FOG_TEXTURE_UNIT, uFogView=tuple(view.flatten(order='F')),
                              uFogLens=lens4, uFogRange=range4)

    @contextmanager
    def bound(self):
        """Bind the integrated volume on ``FOG_TEXTURE_UNIT`` for the scope, then restore the unit."""
        self._check_context()
        if not self._integrated or self._uniforms is None:
            raise RuntimeError(f"{self.label}: fog volume bound before its first update")
        active = gl_query.get_int(gl.GL_ACTIVE_TEXTURE)
        gl.glActiveTexture(gl.GL_TEXTURE0 + FOG_TEXTURE_UNIT)
        previous = gl_query.get_int(gl.GL_TEXTURE_BINDING_3D)
        gl.glActiveTexture(active)
        gl.glBindTextureUnit(FOG_TEXTURE_UNIT, self._integrated)
        try:
            yield self.uniforms
        finally:
            gl.glBindTextureUnit(FOG_TEXTURE_UNIT, previous)

    def _drop_textures(self) -> None:
        live = [t for t in (self._inject, self._integrated, self._steady) if t]
        if live:
            gl.glDeleteTextures(len(live), live)
        self._inject = self._integrated = self._steady = 0
        self._grid = (0, 0, 0)

    def release(self) -> None:
        if self.has_resources:
            self._check_context()
        self._drop_textures()
        if self._integrate_program:
            gl.glDeleteProgram(self._integrate_program)
        self._integrate_program = 0
        self._uniforms = None
        self._context_ref = None


class FogMarch:
    """Reduced-resolution detail march over a ``FogVolume``'s coarse medium (``FOG_MARCH_FRAGMENT``), then a composite
    of in-scatter and transmittance over whatever the caller drew (blend dst x a + rgb).

    Owns one RGBA16F target at the requested size and the baked tiling detail noise; both allocate at first use and
    are reused. ``march`` restores the caller's framebuffer, viewport, program and blend state.
    """

    DETAIL_UNIT, MEDIUM_UNIT, MARCH_UNIT, STEADY_UNIT, LIMIT_UNIT = 9, 10, 11, 12, 15

    def __init__(self, label: str, coverage_glsl: str | None = None) -> None:
        self.label = label
        self._source = fog_march_source(coverage_glsl)
        self._size = (0, 0)
        self._colour = self._fbo = self._detail = self._vao = 0
        self._limit, self._limit_size = 0, 0
        self._programs = {}
        self._context_ref = None

    @property
    def has_resources(self) -> bool:
        return bool(self._colour or self._fbo or self._detail or self._vao or self._programs)

    @property
    def texture(self) -> int:
        return self._colour

    def _check_context(self) -> None:
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError(f"{self.label}: fog march GL work needs its owning current context")
        if self._context_ref is None:
            self._context_ref = weakref.ref(current)
        if self._context_ref() != current:
            raise RuntimeError(f"{self.label}: fog march used in a foreign context")

    def _program(self, key, fragment):
        if key not in self._programs:
            from rendering.quick.render.gl_resources import compile_program
            self._programs[key] = compile_program(FOG_FULLSCREEN_VERTEX, fragment, label=f'{self.label} {key}')
        return self._programs[key]

    def prepare_programs(self) -> bool:
        """At most one compile per caller-owned hidden preparation step."""
        self._check_context()
        for key,source in (('march',self._source),('composite',FOG_COMPOSITE_FRAGMENT)):
            if key not in self._programs:
                self._program(key,source)
                return False
        return True

    def _allocate(self, width, height) -> None:
        name = (ctypes.c_uint*1)()
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        if self._colour:
            gl.glDeleteTextures(1, [self._colour])
        gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
        self._colour = int(name[0])
        gl.glTextureStorage2D(self._colour, 1, gl.GL_RGBA16F, width, height)
        for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                 (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
            gl.glTextureParameteri(self._colour, parameter, value)
        gl.glCreateFramebuffers(1, name)
        self._fbo = int(name[0])
        gl.glNamedFramebufferTexture(self._fbo, gl.GL_COLOR_ATTACHMENT0, self._colour, 0)
        if gl.glCheckNamedFramebufferStatus(self._fbo, gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"{self.label}: fog march target incomplete at {width}x{height}")
        self._size = (width, height)
        if not self._detail:
            noise = np.ascontiguousarray(fog_detail_noise())
            gl.glCreateTextures(gl.GL_TEXTURE_3D, 1, name)
            self._detail = int(name[0])
            gl.glTextureStorage3D(self._detail, 1, gl.GL_R16F, *noise.shape[::-1])
            gl.glTextureSubImage3D(self._detail, 0, 0, 0, 0, *noise.shape[::-1], gl.GL_RED, gl.GL_FLOAT, noise)
            for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                     (gl.GL_TEXTURE_WRAP_S, gl.GL_REPEAT), (gl.GL_TEXTURE_WRAP_T, gl.GL_REPEAT),
                                     (gl.GL_TEXTURE_WRAP_R, gl.GL_REPEAT)):
                gl.glTextureParameteri(self._detail, parameter, value)
        if not self._vao:
            gl.glCreateVertexArrays(1, name)
            self._vao = int(name[0])

    def march(self, volume: FogVolume, *, size, steps=96, max_extinction=1., erosion=.6, detail_frequency=1.,
              shadow=(.5, 1.), ground=None, step=(.2, 1.), medium=None, shadow_floor=0., edge_glow=0., base=(0., 0., 0.)) -> None:
        """Integrate the eroded medium per pixel of ``size`` along ``volume``'s camera rays (its last update).
        ``medium(program)`` sets a consumer coverage's own uniforms."""
        self._check_context()
        width, height = max(1, int(size[0])), max(1, int(size[1]))
        if (width, height) != self._size or not self._fbo:
            self._allocate(width, height)
        fog = volume.uniforms
        program = self._program('march', self._source)
        saved = (gl_query.get_int(gl.GL_DRAW_FRAMEBUFFER_BINDING), gl_query.get_ints(gl.GL_VIEWPORT, 4),
                 gl_query.get_int(gl.GL_CURRENT_PROGRAM), gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING),
                 gl_query.is_enabled(gl.GL_DEPTH_TEST), gl.glIsEnabledi(gl.GL_BLEND, 0))
        try:
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, self._fbo)
            gl.glViewport(0, 0, width, height)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisablei(gl.GL_BLEND, 0)
            gl.glUseProgram(program)
            location = lambda name: gl.glGetUniformLocation(program, name)
            gl.glBindTextureUnit(self.MEDIUM_UNIT, volume.medium_texture)
            gl.glBindTextureUnit(self.DETAIL_UNIT, self._detail)
            gl.glUniform1i(location('uFogMedium'), self.MEDIUM_UNIT)
            gl.glUniform1i(location('uFogDetail'), self.DETAIL_UNIT)
            gl.glBindTextureUnit(self.STEADY_UNIT, volume.steady_texture)
            gl.glUniform1i(location('uFogSteady'), self.STEADY_UNIT)
            view = np.asarray(fog['uFogView'], np.float32).reshape(4, 4, order='F')
            gl.glUniformMatrix4fv(location('uFogView'), 1, gl.GL_FALSE, np.asarray(fog['uFogView'], np.float32))
            gl.glUniformMatrix4fv(location('uFogInvView'), 1, gl.GL_TRUE, np.linalg.inv(view).astype(np.float32))
            gl.glUniform4f(location('uFogLens'), *fog['uFogLens'])
            gl.glUniform4f(location('uFogRange'), *fog['uFogRange'])
            gl.glUniform4f(location('uMarch'), float(steps), max_extinction, erosion, detail_frequency)
            gl.glUniform3f(location('uMarchStep'), *step, shadow_floor)
            gl.glUniform4f(location('uMarchEdge'), edge_glow, *base)
            gl.glUniform4f(location('uMarchShade'), *shadow, 0. if ground is None else float(ground),
                           0. if ground is None else 1.)
            if medium is not None:
                medium(program)
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        finally:
            framebuffer, viewport, program_before, vao_before, depth_test, blend = saved
            gl.glBindFramebuffer(gl.GL_DRAW_FRAMEBUFFER, framebuffer)
            gl.glViewport(*viewport)
            gl.glUseProgram(program_before)
            gl.glBindVertexArray(vao_before)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
            (gl.glEnablei if blend else gl.glDisablei)(gl.GL_BLEND, 0)

    def composite(self, *, glow: float = 0., additive: bool = False, scale: float = 1., crackle=(0., 0., 1., 1.),
                  crackle_glow: float = 0., crackle_limit=None, crackle_limit_texture: int | None = None,
                  fringe_smoothing: float = 0.) -> None:
        """Draw the last march over the bound framebuffer: dst x transmittance + in-scatter (``additive``: + in-scatter
        only, for a target that holds light alone, such as a reflection)."""
        self._check_context()
        if not self._colour:
            raise RuntimeError(f"{self.label}: fog composite before a march")
        if not math.isfinite(fringe_smoothing) or not 0. <= fringe_smoothing <= 4.:
            raise ValueError('Fog fringe smoothing must be finite in 0..4 march texels')
        if crackle_limit is not None and crackle_limit_texture is not None:
            raise ValueError('Fog edge limit has exactly one owner')
        program = self._program('composite', FOG_COMPOSITE_FRAGMENT)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        depth_test = gl_query.is_enabled(gl.GL_DEPTH_TEST)
        blend = gl.glIsEnabledi(gl.GL_BLEND, 0)
        blend_emission = gl.glIsEnabledi(gl.GL_BLEND, 1)
        depth_mask = gl_query.get_bool(gl.GL_DEPTH_WRITEMASK)
        try:
            gl.glUseProgram(program)
            gl.glBindTextureUnit(self.MARCH_UNIT, self._colour)
            gl.glUniform1i(gl.glGetUniformLocation(program, 'uFogMarch'), self.MARCH_UNIT)
            gl.glUniform1f(gl.glGetUniformLocation(program, 'uFogGlow'), glow)
            gl.glUniform1f(gl.glGetUniformLocation(program, 'uFogScale'), scale)
            gl.glUniform1f(gl.glGetUniformLocation(program, 'uFogFringeSmoothing'), fringe_smoothing)
            gl.glUniform4f(gl.glGetUniformLocation(program, 'uFogCrackle'), *crackle)
            gl.glUniform2f(gl.glGetUniformLocation(program, 'uFogCrackleSeed'), crackle_glow, 0.)
            # Optional per-column limit (float32 array over screen x, values in screen v): the consumer's own geometry.
            limited=crackle_limit is not None or crackle_limit_texture is not None
            gl.glUniform1i(gl.glGetUniformLocation(program, 'uFogCrackleLimited'), int(limited))
            if limited:
                if crackle_limit is not None:self._upload_limit(np.ascontiguousarray(crackle_limit, np.float32))
                gl.glBindTextureUnit(self.LIMIT_UNIT,self._limit if crackle_limit_texture is None else crackle_limit_texture)
                gl.glUniform1i(gl.glGetUniformLocation(program, 'uFogCrackleLimit'), self.LIMIT_UNIT)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDepthMask(gl.GL_FALSE)
            gl.glEnablei(gl.GL_BLEND, 0)
            gl.glBlendEquationSeparatei(0, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            if additive:
                gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_ONE, gl.GL_ZERO, gl.GL_ONE)
            else:
                gl.glBlendFuncSeparatei(0, gl.GL_ONE, gl.GL_SRC_ALPHA, gl.GL_ZERO, gl.GL_ONE)
            gl.glEnablei(gl.GL_BLEND, 1)
            gl.glBlendEquationSeparatei(1, gl.GL_FUNC_ADD, gl.GL_FUNC_ADD)
            gl.glBlendFuncSeparatei(1, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE, gl.GL_ONE)
            gl.glBindVertexArray(self._vao)
            gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        finally:
            gl.glUseProgram(program_before)
            gl.glBindVertexArray(vao_before)
            gl.glDepthMask(gl.GL_TRUE if depth_mask else gl.GL_FALSE)
            (gl.glEnable if depth_test else gl.glDisable)(gl.GL_DEPTH_TEST)
            (gl.glEnablei if blend else gl.glDisablei)(gl.GL_BLEND, 0)
            (gl.glEnablei if blend_emission else gl.glDisablei)(gl.GL_BLEND, 1)

    def _upload_limit(self, limit) -> None:
        if not self._limit or self._limit_size != limit.size:
            if self._limit:
                gl.glDeleteTextures(1, [self._limit])
            name = (ctypes.c_uint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            self._limit, self._limit_size = int(name[0]), limit.size
            gl.glTextureStorage2D(self._limit, 1, gl.GL_R32F, limit.size, 1)
            for parameter, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                                     (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(self._limit, parameter, value)
        gl.glTextureSubImage2D(self._limit, 0, 0, 0, limit.size, 1, gl.GL_RED, gl.GL_FLOAT, limit)

    def release(self) -> None:
        if self.has_resources:
            self._check_context()
        if self._limit:
            gl.glDeleteTextures(1, [self._limit])
        self._limit, self._limit_size = 0, 0
        if self._fbo:
            gl.glDeleteFramebuffers(1, [self._fbo])
        live = [t for t in (self._colour, self._detail) if t]
        if live:
            gl.glDeleteTextures(len(live), live)
        if self._vao:
            gl.glDeleteVertexArrays(1, [self._vao])
        for program in self._programs.values():
            gl.glDeleteProgram(program)
        self._programs = {}
        self._colour = self._fbo = self._detail = self._vao = 0
        self._size = (0, 0)
        self._context_ref = None


__all__ = ["FogMarch", "FogVolume", "MAX_FOG_CELLS"]
