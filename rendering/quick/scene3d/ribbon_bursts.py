"""Lazy event-spark draw over the shared particle pass and immutable logical birth records."""
from __future__ import annotations
import weakref
import numpy as np
from OpenGL import GL as gl
from core.ribbon_bursts import CAPACITY, STRIDE
from rendering.gl_programs.ribbon_bursts import VERTEX, FRAGMENT
from rendering.gl_programs.mist import FOG_OFF
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.stream import StreamRing
from rendering.quick.scene3d.particles import draw_particles
from rendering.quick.scene3d.ribbon import GRADE_OFF


class RibbonBurstRenderer:
    def __init__(self):
        self.resources=MeshResources('ribbon event sparks')
        self.stream=None
        self._context_ref=None

    @property
    def has_resources(self):return self.resources.has_resources or (self.stream is not None and self.stream.has_resources)

    def _context(self, *, admit=False):
        from PySide6.QtGui import QOpenGLContext
        current=QOpenGLContext.currentContext()
        if current is None:raise RuntimeError('Ribbon event sparks require their current GL context')
        if self._context_ref is None and admit:self._context_ref=weakref.ref(current)
        if self._context_ref is None or self._context_ref()!=current:
            raise RuntimeError('Ribbon event sparks used in a foreign context')

    def prepare_step(self):
        self._context(admit=True)
        if not warm_programs(((self.resources,'bursts',VERTEX,FRAGMENT),)):return False
        if not self.resources.has_mesh('quad'):
            self.resources.mesh('quad',(0.,0.,1.,0.,0.,1.,1.,1.),(2,));return False
        return self._stream().warm()

    def _stream(self):
        if self.stream is None:
            alignment=gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
            size=CAPACITY*STRIDE*4+alignment
            # Two binds a frame (direct and reflected), four per slot: a fence every second frame, and a reused slot
            # was last read four frames ago, so no fence wait ties this frame's submission to the previous frame's.
            self.stream=StreamRing('ribbon event sparks',slots=3,slot_bytes=4*size,hold_bytes=size)
        return self.stream

    def draw(self,payload,*,mvp,now,viewport,mist,grade,restore=True):
        """``restore=False``: the caller owns the program and storage binding for its frame (nothing read back)."""
        if not payload:return
        if len(payload)!=CAPACITY*STRIDE*4:raise ValueError('Invalid ribbon burst packet size')
        self._context(admit=True)
        # A revealed mode may enable Sparks after activation preparation has completed. The same lazy owners
        # admit that explicit user transition; initial activation still warms these units separately while hidden.
        program=self.resources.program('bursts',VERTEX,FRAGMENT)
        names=('uMvp','uNow','uViewport','uMist','uMistShape','uFogVolume','uFogView','uFogLens','uFogRange','uGradeStops','uGrade')
        u=self.resources.uniforms('bursts',names,required=False)
        gl.glUseProgram(program)
        gl.glUniformMatrix4fv(u['uMvp'],1,gl.GL_FALSE,np.asarray(mvp,np.float32))
        gl.glUniform1f(u['uNow'],now);gl.glUniform2f(u['uViewport'],*viewport)
        values={'uMist':(0.,0.,1.,1.),'uMistShape':(0.,0.,0.,0.),**FOG_OFF,**mist,**GRADE_OFF,**grade}
        for key,value in values.items():
            if key not in u:continue
            if key=='uFogVolume':gl.glUniform1i(u[key],value)
            elif len(value)==16:gl.glUniformMatrix4fv(u[key],1,gl.GL_FALSE,np.asarray(value,np.float32))
            elif key=='uGradeStops':gl.glUniform4fv(u[key],len(value)//4,np.asarray(value,np.float32))
            else:gl.glUniform4f(u[key],*value)
        vao,_=self.resources.mesh('quad',(0.,0.,1.,0.,0.,1.,1.,1.),(2,))
        from types import SimpleNamespace
        stream=self._stream();stream.warm()
        with stream.bound(gl.GL_SHADER_STORAGE_BUFFER,1,payload,restore=restore):
            draw_particles(SimpleNamespace(quad_vao=vao),CAPACITY)

    def release(self):
        if self.has_resources:self._context()
        errors=[]
        for release in ((self.stream.release,) if self.stream is not None else ())+(self.resources.release_resources,):
            try:release()
            except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Ribbon event sparks remain for retry',errors)
        self.stream=None;self._context_ref=None
