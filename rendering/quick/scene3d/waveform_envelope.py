"""One bounded GPU envelope/edge-limit owner over the scene's held ribbon packet. No readback or CPU field upload."""
from __future__ import annotations
import math
import numpy as np
from OpenGL import GL as gl
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources,warm_programs
from rendering.quick.scene3d.compute import bound_image,dispatch
from rendering.gl_programs import waveform_envelope as source
from rendering.quick.scene3d.ribbon import ribbon_grade

PROGRAMS=(('raw',source.RAW),('blur',source.BLUR),('even',source.EVEN),('limit',source.LIMIT),('fill',source.FILL_LIMIT))


class WaveformEnvelope:
    def __init__(self):
        self.resources=MeshResources('waveform envelope')
        self.textures={};self._count=0;self._context=None

    @property
    def has_resources(self):return bool(self.textures or self.resources.has_resources)

    @property
    def texture(self):return self.textures['table']

    @property
    def limit(self):return self.textures['limit']

    def _check(self,*,admit=False):
        from PySide6.QtGui import QOpenGLContext
        current=QOpenGLContext.currentContext()
        if current is None:raise RuntimeError('Waveform envelope needs its current GL context')
        if self._context is None and admit:self._context=current
        if self._context!=current:raise RuntimeError('Waveform envelope used in a foreign context')

    def prepare_step(self):
        self._check(admit=True)
        return warm_programs(tuple((self.resources,key,shader) for key,shader in PROGRAMS))

    def _allocate(self,count):
        if self._count==count and len(self.textures)==5:return
        self._drop_textures()
        for key in ('raw','blur','table','limit_raw','limit'):
            name=(gl.GLuint*1)();gl.glCreateTextures(gl.GL_TEXTURE_2D,1,name)
            texture=self.textures[key]=int(name[0]);limit=key.startswith('limit')
            gl.glTextureStorage2D(texture,1,gl.GL_R32F if limit else gl.GL_RGBA32F,256 if limit else count,1 if limit else 6)
            for param,value in ((gl.GL_TEXTURE_MIN_FILTER,gl.GL_LINEAR),(gl.GL_TEXTURE_MAG_FILTER,gl.GL_LINEAR),
                                (gl.GL_TEXTURE_WRAP_S,gl.GL_CLAMP_TO_EDGE),(gl.GL_TEXTURE_WRAP_T,gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(texture,param,value)
        self._count=count

    def _run(self,key,output,inputs,uniforms,groups,*,limit=False):
        shader=dict(PROGRAMS)[key];program=self.resources.compute_program(key,shader);gl.glUseProgram(program)
        names=tuple(uniforms)+(('uInput',) if inputs is not None else ())
        locations=self.resources.uniforms(key,names,required=False)
        for name,value in uniforms.items():
            location=locations[name]
            if name=='uMvp':gl.glUniformMatrix4fv(location,1,gl.GL_FALSE,np.asarray(value,np.float32))
            elif name=='uGradeStops':gl.glUniform4fv(location,6,np.asarray(value,np.float32))
            elif isinstance(value,(int,float)):gl.glUniform1f(location,value)
            elif len(value)==2:gl.glUniform2f(location,*value)
            else:gl.glUniform4f(location,*value)
        if inputs is not None:
            gl.glBindTextureUnit(14,self.textures[inputs]);gl.glUniform1i(locations['uInput'],14)
        with bound_image(0,self.textures[output],gl.GL_WRITE_ONLY,gl.GL_R32F if limit else gl.GL_RGBA32F):
            dispatch((groups,1,1),gl.GL_TEXTURE_FETCH_BARRIER_BIT)

    def update(self,packet,*,translation,age_fade,fog,grade,camber,mvp,slopes,floor,continuation=False):
        self._check(admit=True)
        x0,x1,count=fog.envelope_range;count=int(count)
        if not 4<=count<=2048 or packet.instances>3 or slopes[0]!=0.:
            raise ValueError('Waveform GPU envelope exceeds its admitted domain')
        self._allocate(count)
        step=(x1-x0)/(count-1);groups=-(-count//64)
        before=gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        texture=gl_query.get_indexed_int(gl.GL_TEXTURE_BINDING_2D,14)
        try:
            origin=tuple(float(a+b) for a,b in zip(packet.world_origin,translation))
            now,fade_in,lifetime,fade_out=age_fade
            nodes,range_,_,share=grade
            self._run('raw','raw',None,dict(uSpan=(x0,x1,float(count),float(packet.instances)),uOrigin=(*origin,0.),
                uAge=(now-packet.coordinate_origin,fade_in,lifetime,fade_out),
                uShape=(fog.envelope_width,camber,floor[0]+floor[1],floor[2]),uSlope=slopes,uContinue=float(continuation),
                **ribbon_grade(nodes,range_,share)),groups)
            self._run('blur','blur','raw',dict(uSigma=(fog.envelope_smoothing/step,4*fog.envelope_smoothing/step)),groups)
            self._run('even','table','blur',dict(uWorld=(x0,x1,fog.edge_evening/step,fog.sides[0]),uSideEnd=fog.sides[1]),groups)
            self._run('limit','limit_raw','table',dict(uMvp=tuple(np.asarray(mvp).flatten(order='F')),
                uWorld=(x0,x1,*slopes),uDepth=fog.sheets_z),4,limit=True)
            self._run('fill','limit','limit_raw',{},4,limit=True)
        finally:
            gl.glBindTextureUnit(14,texture);gl.glUseProgram(before)

    def _drop_textures(self):
        errors=[]
        for key,name in tuple(self.textures.items()):
            try:gl.glDeleteTextures(1,[name])
            except Exception as error:errors.append(error)
            else:del self.textures[key]
        if errors:raise ExceptionGroup('Waveform envelope textures remain for retry',errors)
        self._count=0

    def release(self):
        if self.has_resources:self._check()
        errors=[]
        for release in (self._drop_textures,self.resources.release_resources):
            try:release()
            except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Waveform envelope remains for retry',errors)
        self._context=None
