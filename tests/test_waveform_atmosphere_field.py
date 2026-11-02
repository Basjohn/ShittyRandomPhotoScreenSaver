"""Actual shader field agrees with all four retained sheets, including off-table interior history."""
import numpy as np
import pytest
from OpenGL import GL as gl
from core.ribbon_ring import RibbonRing
from core.ribbon_continuation import cloth_values
from rendering.gl_programs.waveform_atmosphere import WORLD_FIELD_GLSL
from rendering.quick.scene3d.waveform_field import WaveformField
from rendering.quick.scene3d.ribbon import RibbonPrimitive
from rendering.quick.offscreen_target import OffscreenRenderTarget

pytestmark=pytest.mark.qt


def test_four_sheet_shape_light_and_clearance_match_retained_history_outside_table(qt_app):
    target=OffscreenRenderTarget(16,16);field=WaveformField();primitive=RibbonPrimitive();buffer=0
    ring=RibbonRing(4,colours=[(.1+.1*i,.5,.9,1.) for i in range(4)])
    for index in range(256):
        x=-95.6+.4*index
        ring.append(index/6,[(x,1.8+.6*np.sin(x*.4+i),i*.35) for i in range(4)],
                    [.4]*4,twists=[.07*index+.4*i for i in range(4)],emission=.5+index/256)
    packet=ring.packet();xs=np.array((-120.,-90.,-80.1,-79.9,0.,6.,45.,150.),np.float32)
    try:
        shader='#version 460 core\n'+WORLD_FIELD_GLSL+'''
layout(local_size_x=8) in;
layout(std430,binding=2) writeonly buffer Results {vec4 results[];};
uniform float uXs[8];
void main(){int col=int(gl_GlobalInvocationID.x);float x=uXs[col];
for(int owner=0;owner<4;owner++){
vec4 shape,light;sourceField(x,owner,shape,light);
int at=(col*4+owner)*3;results[at]=shape;results[at+1]=light;
vec2 surface=fieldSection(shape,0.5);results[at+2]=vec4(bodyField(vec3(x,surface)).a,0,0,0);}}
'''
        program=field.resources.compute_program('field samples',shader)
        buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0]);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        output=np.empty((8,4,3,4),np.float32);gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,output.nbytes,None,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,buffer)
        with primitive.packet_scope(packet):
            field.update(packet,translation=(0.,0.,0.),span=(-80.,80.,1024),grade=(((0.,(.1,.5,.9)),),(0.,1.),0.,0.))
            gl.glUseProgram(program);location=lambda name:gl.glGetUniformLocation(program,name)
            gl.glBindTextureUnit(14,field.texture);gl.glUniform1i(location('uBodyField'),14)
            step=160/1023;gl.glUniform2f(location('uBodySpan'),-80.-step*.5,1./(160.+step))
            gl.glUniform4f(location('uFieldOrigin'),*packet.world_origin,4.)
            gl.glUniform4f(location('uBodyShape'),.03,.15,1.,.3)
            gl.glUniform4f(location('uGrade'),0.,1.,0.,1.)
            gl.glUniform1fv(location('uXs'),8,xs)
            gl.glDispatchCompute(1,1,1);gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        output[:]=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,output.nbytes),np.float32).reshape(output.shape)
        paths=np.frombuffer(packet.payload,np.float32).reshape(4,-1,4)
        for owner,path in enumerate(paths):
            n,start,cap=int(path[0,0]),int(path[1,1]),int(path[1,2])
            knots=path[4:].reshape(-1,5,4)[(start+np.arange(n))%cap].astype(float)
            expected=cloth_values(knots,xs-packet.world_origin[0]);expected[:,:2]+=packet.world_origin[1:]
            expected[:,3]+=path[1,0]
            np.testing.assert_allclose(output[:,owner,0],expected,atol=.002,rtol=1e-4)
            emission=np.interp(xs,knots[:,0,0]+packet.world_origin[0],knots[:,3,3])
            np.testing.assert_allclose(output[:,owner,1,:3],emission[:,None]*path[2,:3],atol=.002)
        assert output[:,:,2,0].max()<.04
        # The regression's -90 sample is inside history, outside the texture, and cannot use endpoint continuation.
        assert -95.6<float(xs[1])<-80.
    finally:
        gl.glUseProgram(0);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
        field.release();primitive.release();target.close()
