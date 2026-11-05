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


def _atmosphere_light(qt_app,locals_,ambient,ceiling,share):
    """The medium's own local-light response, evaluated on GPU for each linear source radiance."""
    from rendering.gl_programs.waveform_atmosphere import ATMOSPHERE_LIGHT_GLSL
    target=OffscreenRenderTarget(16,16);field=WaveformField();buffer=0
    locals_=np.asarray(locals_,np.float32);count=len(locals_)
    try:
        shader='#version 460 core\n'+ATMOSPHERE_LIGHT_GLSL+'''
layout(local_size_x=1) in;
layout(std430,binding=2) buffer Io {vec4 io[];};
uniform vec3 uAmbient;
void main(){uint i=gl_GlobalInvocationID.x;io[i]=vec4(atmosphereLight(io[i].rgb,uAmbient),0);}
'''
        program=field.resources.compute_program('atmosphere light',shader)
        data=np.zeros((count,4),np.float32);data[:,:3]=locals_
        buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0]);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,data.nbytes,data,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,buffer)
        gl.glUseProgram(program);location=lambda name:gl.glGetUniformLocation(program,name)
        gl.glUniform2f(location('uAtmosphereLight'),ceiling,share);gl.glUniform3f(location('uAmbient'),*ambient)
        gl.glDispatchCompute(count,1,1);gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        out=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,data.nbytes),np.float32).reshape(count,4)
        return out[:,:3].astype(float)
    finally:
        gl.glUseProgram(0);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
        field.release();target.close()


LUMA=np.array((.2126,.7152,.0722))


def test_strong_local_light_compresses_below_a_bounded_wash(qt_app):
    """However bright the ribbons (or Local Light), the medium's lit radiance never passes its ceiling."""
    ceiling=.2;strengths=np.geomspace(1e-3,1e4,40)
    hues=((1.,.1,.9),(0.,.8,1.),(1.,.55,.1),(1.,1.,1.))
    for hue in hues:
        locals_=np.outer(strengths,hue)
        lit=_atmosphere_light(qt_app,locals_,(.035,.05,.085),ceiling,.5)@LUMA
        assert np.all(np.diff(lit)>=-1e-6), 'brighter light never darkens the haze'
        assert lit.max()<=ceiling*1.0001
        assert lit[-1]>ceiling*.99, 'strong light saturates at the ceiling rather than vanishing'
        assert abs(lit[0]-1e-3*max(hue))<1e-4, 'faint light passes through unchanged'
    assert np.allclose(_atmosphere_light(qt_app,[(0.,0.,0.)],(.035,.05,.085),ceiling,.5),0.)


def test_tint_keeps_a_capped_share_of_the_local_source_hue(qt_app):
    """The haze leans toward each ribbon's own hue by exactly the share, over the medium's own hue."""
    ambient=np.array((.035,.05,.085));own=ambient/ambient.max()
    warm,cool=np.array((1.,.55,.1)),np.array((0.,.8,1.))
    for share in (0.,.3,1.):
        lit=_atmosphere_light(qt_app,[warm*50.,cool*50.],ambient,.2,share)
        for colour,source in zip(lit,(warm,cool)):
            expected=own+share*(source/source.max()-own)
            np.testing.assert_allclose(colour/colour.max(),expected/expected.max(),atol=2e-3)
        warmth=(lit[:,0]-lit[:,2])/lit.sum(1)
        if share==0.:assert abs(warmth[0]-warmth[1])<1e-4, 'no share: the medium keeps its own colour'
        else:assert warmth[0]>warmth[1], 'haze near the warm ribbon is warmer than near the cool one'
    # A partial share never reaches the saturated source colour.
    partial=_atmosphere_light(qt_app,[warm*50.],ambient,.2,.3)[0]
    full=_atmosphere_light(qt_app,[warm*50.],ambient,.2,1.)[0]
    assert (partial[0]-partial[2])/partial.sum()<(full[0]-full[2])/full.sum()
