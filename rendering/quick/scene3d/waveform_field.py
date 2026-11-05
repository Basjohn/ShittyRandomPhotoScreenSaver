"""One fixed-world cloth field, reduced once per frame on GPU without readback or camera inputs."""
import numpy as np
from OpenGL import GL as gl
from rendering.quick import gl_query
from rendering.quick.scene3d.compute import bound_image,dispatch
from rendering.quick.scene3d.resources import MeshResources,warm_programs
from rendering.quick.scene3d.ribbon import ribbon_grade
from rendering.gl_programs.waveform_atmosphere import FIELD_COMPUTE,FIELD_ROWS,FIELD_RIBBONS


class WaveformField:
    def __init__(self):
        self.resources=MeshResources('waveform world field');self.texture=0;self._samples=0;self._context=None

    @property
    def has_resources(self):return bool(self.texture or self.resources.has_resources)

    def _check(self):
        from PySide6.QtGui import QOpenGLContext
        current=QOpenGLContext.currentContext()
        if current is None:raise RuntimeError('Waveform field requires its current GL context')
        if self._context is None:self._context=current
        if current!=self._context:raise RuntimeError('Waveform field used in a foreign GL context')

    def prepare_step(self):
        self._check()
        return warm_programs(((self.resources,'field',FIELD_COMPUTE),))

    def update(self,packet,*,translation,span,grade,side=1.):
        self._check();first,last,samples=span;samples=int(samples)
        if not 4<=samples<=2048 or packet.instances>FIELD_RIBBONS or not first<last:
            raise ValueError('Waveform world field exceeds its bounded domain')
        if samples!=self._samples:
            if self.texture:gl.glDeleteTextures(1,[self.texture]);self.texture=0
            name=(gl.GLuint*1)();gl.glCreateTextures(gl.GL_TEXTURE_2D,1,name);self.texture=int(name[0])
            gl.glTextureStorage2D(self.texture,1,gl.GL_RGBA32F,samples,FIELD_ROWS)
            for key,value in ((gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR),(gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR),
                    (gl.GL_TEXTURE_WRAP_S,gl.GL_CLAMP_TO_EDGE),(gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(self.texture,key,value)
            self._samples=samples
        before=gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        try:
            program=self.resources.compute_program('field',FIELD_COMPUTE);gl.glUseProgram(program)
            locations=self.resources.uniforms('field',('uFieldSpan','uFieldOrigin','uGrade','uGradeStops','uFieldSide'),required=False)
            gl.glUniform1f(locations['uFieldSide'],float(side))
            gl.glUniform4f(locations['uFieldSpan'],first,last,samples,packet.instances)
            gl.glUniform4f(locations['uFieldOrigin'],*(float(a+b) for a,b in zip(packet.world_origin,translation)),packet.instances)
            values=ribbon_grade(grade[0],grade[1],grade[3])
            gl.glUniform4f(locations['uGrade'],*values['uGrade'])
            gl.glUniform4fv(locations['uGradeStops'],6,np.asarray(values['uGradeStops'],np.float32))
            with bound_image(0,self.texture,gl.GL_WRITE_ONLY,gl.GL_RGBA32F):
                dispatch((-(-samples//64),1,1),gl.GL_TEXTURE_FETCH_BARRIER_BIT)
        finally:gl.glUseProgram(before)

    def release(self):
        if self.has_resources:self._check()
        errors=[]
        if self.texture:
            try:gl.glDeleteTextures(1,[self.texture])
            except Exception as error:errors.append(error)
            else:self.texture=0;self._samples=0
        try:self.resources.release_resources()
        except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Waveform field remains for retry',errors)
        self._context=None
