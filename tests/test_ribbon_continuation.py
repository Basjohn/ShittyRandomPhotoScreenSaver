"""C2 joins, view-independent world field and conservative physical frustum culling."""
from dataclasses import replace
import numpy as np
import pytest
from core.ribbon_continuation import endpoint_jet,continued_values,cloth_values,frustum_axial_span
from core.ribbon_ring import RibbonRing
from core.waveform_ribbon_scene import SPEC,FLOOR_CONTACT,Recipe,VIEW_SLOPE
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera


def packet_and_knots():
    ring=RibbonRing(1,colours=[(.1,.5,.9,1.)])
    for i in range(32):
        ring.append(i/6,[(i*.25,2.+np.sin(i*.25),.5*np.cos(i*.2))], [.5+.1*np.sin(i*.15)],twists=.1*i)
    packet=ring.packet();path=np.frombuffer(packet.payload,np.float32).reshape(-1,4)
    count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
    return packet,path[4:].reshape(-1,5,4)[(start+np.arange(count))%capacity].astype(float)


@pytest.mark.parametrize('before',(True,False))
def test_continuation_matches_actual_cloth_value_slope_and_curvature(before):
    _,knots=packet_and_knots()
    origin,value,first,second,reach=endpoint_jet(knots,before)
    direction=-1 if before else 1;step=1e-4
    values=continued_values(knots,origin+direction*step*np.arange(4),before)
    np.testing.assert_allclose(values[0],value,atol=1e-12)
    np.testing.assert_allclose(direction*(-11*values[0]+18*values[1]-9*values[2]+2*values[3])/(6*step),first,atol=2e-6)
    np.testing.assert_allclose((2*values[0]-5*values[1]+4*values[2]-values[3])/step**2,second,atol=2e-5)
    inside=cloth_values(knots,origin-direction*step*np.arange(4))
    np.testing.assert_allclose(inside[0],value,atol=1e-12)
    np.testing.assert_allclose(-direction*(-11*inside[0]+18*inside[1]-9*inside[2]+2*inside[3])/(6*step),first,atol=2e-6)
    np.testing.assert_allclose((2*inside[0]-5*inside[1]+4*inside[2]-inside[3])/step**2,second,atol=2e-5)
    distant=continued_values(knots,np.linspace(origin,origin+direction*10000,10000),before)
    assert np.isfinite(distant).all() and (distant[:,2]>0).all()


def test_continuation_phase_survives_packet_coordinate_rebase():
    _,knots=packet_and_knots();rebased=knots.copy();rebased[:,0,0]-=128.
    xs=np.linspace(-200.,200.,1000)
    np.testing.assert_allclose(cloth_values(knots,xs),cloth_values(rebased,xs-128.),atol=1e-11)


@pytest.mark.parametrize('aspect',(.2,1.5,12.))
def test_frustum_culling_contains_every_visible_fixed_world_point(aspect):
    transverse=((0.,9.),(-8.,8.))
    points=np.array([(x,y,z,1.) for x in np.linspace(-400,400,81) for y in (0.,4.,9.) for z in (-8.,0.,8.)])
    for turn in (-1.,-.5,0.,.5,1.):
        view,matrix,_,_=physical_view(camera(turn=turn,scene_scale=.25),aspect)
        mvp=matrix@view;low,high=frustum_axial_span(mvp,transverse)
        clip=points@mvp.T
        visible=(clip[:,3]>0)&(np.abs(clip[:,:3])<=clip[:,3,None]+1e-9).all(1)
        assert ((points[visible,0]>=low-1e-8)&(points[visible,0]<=high+1e-8)).all()


@pytest.mark.qt
def test_native_continuation_vertices_and_atmosphere_share_one_world_field(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    from rendering.quick.scene3d.waveform_field import WaveformField
    from rendering.quick.scene3d.waveform import colour_grade
    from rendering.gl_programs.ribbon import RIBBON_CONTINUOUS_VERTEX,RIBBON_FRAGMENT
    from core.ribbon_style import RibbonMaterial
    packet,knots=packet_and_knots();target=OffscreenRenderTarget(80,60);primitive=RibbonPrimitive();gpu=WaveformField()
    # Capture the real extension draw's world positions without replacing surface calculations.
    source=RIBBON_CONTINUOUS_VERTEX.replace('void main() {','void ribbonMain() {',1)+'''
layout(std430,binding=1) buffer Captured { vec4 captured[]; };
void main(){ribbonMain();if(uContinuation.w!=0.0)captured[gl_VertexID]=vec4(vWorld,1);}
'''
    segments=256;vertices=segments*6*8;buffer=0;distance_buffer=0
    try:
        primitive.resources.program('diagnostic_continuous',source,RIBBON_FRAGMENT)
        buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0]);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,vertices*16,None,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,1,buffer)
        gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        matrix=tuple(np.identity(4).flatten(order='F'));age=(10.,0.,100.,0.)
        recipe=Recipe();fog=recipe.fog
        with primitive.packet_scope(packet):
            primitive.draw(packet,matrix,material=RibbonMaterial(cross_curve=1.),sweep_axis=(1.,0.,0.),
                           floor=FLOOR_CONTACT,continuation=(float(packet.world_origin[0]+knots[0,0,0]),200.,segments))
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
            points=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,vertices*16),np.float32).reshape(-1,4)[:,:3]
            points+=np.asarray(packet.world_origin)
            gpu.update(packet,translation=(0.,0.,0.),span=fog.field_span,grade=colour_grade(recipe,.4))
        gl.glDisable(gl.GL_RASTERIZER_DISCARD);gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT)
        table=np.empty((8,1024,4),np.float32);gl.glGetTextureImage(gpu.texture,0,gl.GL_RGBA,gl.GL_FLOAT,table.nbytes,table)
        xs=np.linspace(*fog.field_span)
        expected=cloth_values(knots,xs-packet.world_origin[0])
        expected[:,:2]+=np.asarray(packet.world_origin)[None,1:]
        expected[:,3]+=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)[0,1,0]
        np.testing.assert_allclose(table[0],expected,atol=4e-4,rtol=4e-4)
        assert not table[2:].any()  # absent ribbons neither clear nor illuminate the atmosphere
        with primitive.packet_scope(packet):
            gpu.update(packet,translation=(0.,0.,0.),span=fog.field_span,grade=colour_grade(recipe,.4))
            gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT)
            after=np.empty_like(table);gl.glGetTextureImage(gpu.texture,0,gl.GL_RGBA,gl.GL_FLOAT,after.nbytes,after)
            np.testing.assert_array_equal(after,table)  # API has no camera input to distort the field
        assert np.min(points[:,1])>=FLOOR_CONTACT[0]+FLOOR_CONTACT[1]-1e-5
        assert points[:,0].max()==pytest.approx(200.,abs=1e-5)
        # Last extension draw is the +x side; it joins at the actual finite endpoint without a cap.
        assert points[:,0].min()==pytest.approx(knots[-1,0,0]+packet.world_origin[0],abs=1e-5)
        # Run the actual mist's far-table clearance function over the real raster vertex-stage output.
        from rendering.gl_programs.waveform_atmosphere import WORLD_FIELD_GLSL
        shader='#version 460 core\n'+WORLD_FIELD_GLSL+'''
layout(local_size_x=64) in;
layout(std430,binding=1) readonly buffer Samples { vec4 samples[]; };
layout(std430,binding=2) writeonly buffer Distances { float distances[]; };
uniform float uCount;
void main(){int i=int(gl_GlobalInvocationID.x);if(i<int(uCount))distances[i]=bodyField(samples[i].xyz+uFieldOrigin.xyz).a;}
'''
        program=gpu.resources.compute_program('far physical clearance test',shader);gl.glUseProgram(program)
        gl.glBindTextureUnit(14,gpu.texture)
        gl.glUniform1i(gl.glGetUniformLocation(program,'uBodyField'),14)
        step=(fog.field_span[1]-fog.field_span[0])/(fog.field_span[2]-1)
        gl.glUniform2f(gl.glGetUniformLocation(program,'uBodySpan'),fog.field_span[0]-.5*step,
                       1/(fog.field_span[1]-fog.field_span[0]+step))
        gl.glUniform4f(gl.glGetUniformLocation(program,'uFieldOrigin'),*packet.world_origin,1.)
        gl.glUniform4f(gl.glGetUniformLocation(program,'uBodyShape'),FLOOR_CONTACT[0]+FLOOR_CONTACT[1],FLOOR_CONTACT[2],1.,.3)
        gl.glUniform1f(gl.glGetUniformLocation(program,'uCount'),vertices)
        distance_buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0])
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,distance_buffer)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,vertices*4,None,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,distance_buffer)
        with primitive.packet_scope(packet):gl.glDispatchCompute(-(-vertices//64),1,1)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        distances=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,vertices*4),np.float32)
        assert distances.max()<.04  # interpolation/polyline error stays inside the .3-unit physical clearance
        assert distances[points[:,0]>81.].max()<1e-4  # exact continuation beyond the fixed texture, no side-wall fade
        gl.glUseProgram(0)
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,1,0)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,2,0)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
        if distance_buffer:gl.glDeleteBuffers(1,[distance_buffer])
        gpu.release();primitive.release();target.close()
