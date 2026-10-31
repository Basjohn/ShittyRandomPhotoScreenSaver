"""Lazy WR-02 strip primitive; caller owns target/depth/blend and context scope.

``shading='diagnostic'`` draws the WR-02a diagnostics. ``'body'`` and ``'light'`` are the filament material's two
passes (``rendering/gl_programs/ribbon.py``): the caller draws ``body`` inside ``SceneTarget.transparent_writes`` and
``light`` afterwards inside ``emission_writes`` with additive blending on colour. Both need the world view matrix,
which is rebased with the packet origin exactly as the MVP is, so no shader mixes local and absolute space.
"""
from dataclasses import astuple, dataclass
import math
import weakref

import numpy as np
from OpenGL import GL as gl

from core.ribbon_packet import MAX_PACKET_BYTES, MAX_RIBBONS, RIBBON_BYTES, RibbonPacket
from core.ribbon_frames import MAX_STRIP_STATIONS
from rendering.gl_programs.ribbon import (RIBBON_BODY_FRAGMENT, RIBBON_FRAGMENT, RIBBON_LIGHT_FRAGMENT,
                                          RIBBON_VERTEX)
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.stream import StreamRing

_FRAGMENTS = {'diagnostic': RIBBON_FRAGMENT, 'body': RIBBON_BODY_FRAGMENT, 'light': RIBBON_LIGHT_FRAGMENT}
_MATERIAL_UNIFORMS = ('uViewZ', 'uEye', 'uForward', 'uOrthographic', 'uStrands', 'uRim', 'uBody')


@dataclass(frozen=True)
class RibbonMaterial:
    """Filament look, in units of the ribbon itself; no music, palette or scene authority."""
    strands: float = 24.            # filament lines across the width
    strand_half_width: float = .12  # of one strand spacing
    strand_light: float = 1.
    strand_warp: float = .06        # across-width spread/gather amplitude
    warp_frequency: float = .25     # warp cycles per strand-phase unit along the path
    rim_half_width: float = .02     # of the width
    rim_light: float = 1.4
    fold_light: float = 1.5         # extra light where the sheet turns edge-on
    fold_power: float = 3.
    body_alpha: float = .035
    body_tint: float = .35
    fold_alpha: float = 1.          # extra body opacity where edge-on

    def __post_init__(self):
        values = astuple(self)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('Ribbon material values must be finite and non-negative')
        if not 1 <= self.strands <= 256 or not 0 < self.strand_half_width <= .5 or not 0 < self.rim_half_width <= .5:
            raise ValueError('Ribbon strands need 1..256 lines and positive half-widths up to half a spacing')
        if self.body_alpha > .95 or self.fold_power <= 0:
            raise ValueError('Ribbon body alpha must stay below 0.95 and fold power positive')

    def uniforms(self):
        return dict(uStrands=(self.strands, self.strand_half_width, self.strand_light, self.strand_warp),
                    uRim=(self.rim_half_width, self.rim_light, self.fold_light, self.fold_power),
                    uBody=(self.body_alpha, self.body_tint, self.fold_alpha, self.warp_frequency))


class RibbonPrimitive:
    def __init__(self):
        self.resources = MeshResources('ribbon primitive')
        self.stream = None
        self._context_ref = None

    @property
    def has_resources(self):
        return self.resources.has_resources or (self.stream is not None and self.stream.has_resources)

    @property
    def stream_bytes(self):
        return self.stream.capacity if self.stream is not None and self.stream.has_resources else 0

    def draw(self, packet: RibbonPacket, mvp, *, diagnostic=0, timing_query=None, shading='diagnostic',
             view=None, orthographic=True, material: RibbonMaterial | None = None):
        if not 0 <= packet.instances <= MAX_RIBBONS or len(packet.payload) != packet.instances*RIBBON_BYTES:
            raise ValueError('Invalid ribbon packet shape')
        if shading not in _FRAGMENTS:
            raise ValueError(f'Unknown ribbon shading: {shading}')
        if packet.instances == 0:
            if packet.vertices != 0:
                raise ValueError('Empty packet cannot draw vertices')
            return
        if packet.vertices % 6 or not 0 < packet.vertices <= (MAX_STRIP_STATIONS-1)*6:
            raise ValueError('Ribbon draw exceeds vertex capacity')
        if len(mvp) != 16 or not all(math.isfinite(v) for v in mvp) or diagnostic not in (0, 1, 2):
            raise ValueError('Finite MVP and admitted diagnostic required')
        origin = np.asarray(packet.world_origin, dtype=float)
        if origin.shape != (3,) or not np.isfinite(origin).all():
            raise ValueError('Finite packet world origin required')
        translate = np.array((*origin, 1.))
        matrix = np.asarray(mvp, dtype=float).reshape(4, 4, order='F').copy()
        matrix[:, 3] = matrix @ translate
        matrix = matrix.astype(np.float32)
        if not np.isfinite(matrix).all():
            raise ValueError('Rebased MVP exceeds float32 range')
        shaded = None
        if shading != 'diagnostic':
            shaded = self._material_uniforms(view, translate, bool(orthographic), material or RibbonMaterial())
        self._check_context(admit=True)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        try:
            program = self.resources.program(shading, RIBBON_VERTEX, _FRAGMENTS[shading])
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            names = ('uMvp', 'uDiagnostic') if shaded is None else ('uMvp', *_MATERIAL_UNIFORMS)
            # Each pass reads only part of the material, so its unused uniforms are compiled out (location -1).
            uniforms = self.resources.uniforms(shading, names, required=shaded is None)
            if self.stream is None:
                alignment = gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
                hold = MAX_PACKET_BYTES+alignment
                self.stream = StreamRing('ribbon knots', slots=3, slot_bytes=hold, hold_bytes=hold)
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, matrix.flatten(order='F'))
            if shaded is None:
                gl.glUniform1i(uniforms['uDiagnostic'], diagnostic)
            else:
                for name, value in shaded.items():
                    if name == 'uOrthographic':
                        gl.glUniform1i(uniforms[name], value)
                    elif len(value) == 3:
                        gl.glUniform3f(uniforms[name], *value)
                    else:
                        gl.glUniform4f(uniforms[name], *value)
            with self.stream.bound(gl.GL_SHADER_STORAGE_BUFFER, 0, packet.payload):
                if timing_query is not None:
                    gl.glBeginQuery(gl.GL_TIME_ELAPSED, timing_query)
                try:
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, packet.vertices, packet.instances)
                finally:
                    if timing_query is not None:
                        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        finally:
            gl.glBindVertexArray(vao_before)
            gl.glUseProgram(program_before)

    @staticmethod
    def _material_uniforms(view, translate, orthographic, material):
        if view is None or len(view) != 16 or not all(math.isfinite(v) for v in view):
            raise ValueError('Material shading needs the finite world view matrix')
        rebased = np.asarray(view, dtype=float).reshape(4, 4, order='F').copy()
        rebased[:, 3] = rebased @ translate
        forward = -rebased[2, :3]
        length = float(np.linalg.norm(forward))
        if not length > 0:
            raise ValueError('View matrix has no forward axis')
        eye = np.linalg.inv(rebased) @ np.array((0., 0., 0., 1.))
        values = dict(uViewZ=tuple(rebased[2]), uEye=tuple(eye[:3]/eye[3]), uForward=tuple(forward/length),
                      uOrthographic=int(orthographic), **material.uniforms())
        if not all(np.isfinite(v).all() for k, v in values.items() if k != 'uOrthographic'):
            raise ValueError('Rebased view exceeds finite range')
        return values

    def _check_context(self, *, admit=False):
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError('Ribbon GL work requires its owning current context')
        if self._context_ref is None and admit:
            self._context_ref = weakref.ref(current)
        if self._context_ref is None or self._context_ref() != current:
            raise RuntimeError('Ribbon primitive used in a foreign context')

    def release(self):
        if self.has_resources:
            self._check_context()
        if self.stream is not None:
            self.stream.release()
        self.resources.release_resources()
        self.stream = None
        self._context_ref = None
