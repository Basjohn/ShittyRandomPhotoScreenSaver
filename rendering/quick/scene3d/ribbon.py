"""Lazy WR-02a strip primitive; caller owns target/depth/blend and context scope."""
import math
import weakref
import numpy as np

from OpenGL import GL as gl

from core.ribbon_packet import MAX_PACKET_BYTES, MAX_RIBBONS, RIBBON_BYTES, RibbonPacket
from core.ribbon_frames import MAX_STRIP_STATIONS
from rendering.gl_programs.ribbon import RIBBON_VERTEX, RIBBON_FRAGMENT
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.stream import StreamRing


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

    def draw(self, packet: RibbonPacket, mvp, *, diagnostic=0, timing_query=None):
        if not 0 <= packet.instances <= MAX_RIBBONS or len(packet.payload) != packet.instances*RIBBON_BYTES:
            raise ValueError('Invalid ribbon packet shape')
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
        matrix = np.asarray(mvp, dtype=float).reshape(4, 4, order='F').copy()
        matrix[:, 3] = matrix @ np.array((*origin, 1.))
        matrix = matrix.astype(np.float32)
        if not np.isfinite(matrix).all():
            raise ValueError('Rebased MVP exceeds float32 range')
        self._check_context(admit=True)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        try:
            program = self.resources.program('strip', RIBBON_VERTEX, RIBBON_FRAGMENT)
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            uniforms = self.resources.uniforms('strip', ('uMvp', 'uDiagnostic'))
            if self.stream is None:
                alignment = gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
                hold = MAX_PACKET_BYTES+alignment
                self.stream = StreamRing('ribbon knots', slots=3, slot_bytes=hold, hold_bytes=hold)
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, matrix.flatten(order='F'))
            gl.glUniform1i(uniforms['uDiagnostic'], diagnostic)
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
