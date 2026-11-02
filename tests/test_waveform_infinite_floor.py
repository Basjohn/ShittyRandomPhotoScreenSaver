"""Actual opaque world-plane coverage, coordinates, occlusion and actor-clip negative controls."""
from dataclasses import replace
import numpy as np
import pytest
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera

pytestmark=pytest.mark.qt


class GroundProbe:
    def __init__(self,width,height):
        from rendering.gl_error_policy import disable_per_call_gl_error_checking
        disable_per_call_gl_error_checking()
        from OpenGL import GL as gl
        from rendering.quick.offscreen_target import OffscreenRenderTarget
        from rendering.quick.scene3d.resources import MeshResources
        from rendering.quick.scene3d.waveform import floor_vertices
        from rendering.gl_programs.waveform_ribbon import FLOOR_VERTEX,FLOOR_WORLD_GLSL
        self.gl=gl;self.target=OffscreenRenderTarget(width,height);self.resources=MeshResources('infinite ground probe')
        fragment='#version 460 core\n'+FLOOR_WORLD_GLSL+'''
layout(std430,binding=5) writeonly buffer WorldHits { vec4 hits[]; };
uniform float uTestWidth;
out vec4 FragColor;
void main(){vec3 world;float depth;if(!floorWorldHit(world,depth))discard;
gl_FragDepth=depth;FragColor=vec4(1,0,0,1);
hits[int(gl_FragCoord.y)*int(uTestWidth)+int(gl_FragCoord.x)]=vec4(world,depth);}
'''
        self.program=self.resources.program('ground',FLOOR_VERTEX,fragment)
        self.vao,self.count=self.resources.mesh('coverage',floor_vertices(),(3,))
        self.buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0])

    def draw(self,values):
        gl=self.gl;target=self.target
        view,projection,eye,lens=physical_view(values,target.width/target.height)
        self.mvp=projection@view
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,self.buffer)
        data=np.full((target.height,target.width,4),np.nan,np.float32)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,data.nbytes,data,gl.GL_STREAM_READ)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,self.buffer)
        target.bind();gl.glEnable(gl.GL_DEPTH_TEST);gl.glDepthFunc(gl.GL_LESS);gl.glDepthMask(gl.GL_TRUE)
        gl.glUseProgram(self.program);gl.glBindVertexArray(self.vao)
        for name,matrix in (('uMvp',self.mvp),('uFloorInverseMvp',np.linalg.inv(self.mvp))):
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(self.program,name),1,gl.GL_FALSE,np.asarray(matrix.flatten(order='F'),np.float32))
        gl.glUniform3f(gl.glGetUniformLocation(self.program,'uEye'),*eye)
        gl.glUniform1i(gl.glGetUniformLocation(self.program,'uOrthographic'),int(lens[2]))
        gl.glUniform1f(gl.glGetUniformLocation(self.program,'uTestWidth'),target.width)
        gl.glDrawArrays(gl.GL_TRIANGLES,0,self.count)
        gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,self.buffer)
        hits=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,data.nbytes),np.float32).reshape(data.shape)[::-1].copy()
        return view,projection,eye,lens,target.read_rgba(),hits

    def actor(self,centre,name='actor',basis=None):
        gl=self.gl
        vertex='#version 460 core\nlayout(location=0)in vec3 position;uniform mat4 uMvp;void main(){gl_Position=uMvp*vec4(position,1);}'
        fragment='#version 460 core\nout vec4 FragColor;void main(){FragColor=vec4(0,1,1,1);}'
        program=self.resources.program('actor',vertex,fragment)
        right,up=(np.array((1.,0.,0.)),np.array((0.,1.,0.))) if basis is None else basis
        corners=((-1.,-1.),(1.,-1.),(1.,1.),(-1.,-1.),(1.,1.),(-1.,1.))
        points=np.array([centre+.3*x*right+.3*y*up for x,y in corners],np.float32)
        vao,count=self.resources.mesh(name,points.tobytes(),(3,))
        gl.glUseProgram(program);gl.glBindVertexArray(vao)
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(program,'uMvp'),1,gl.GL_FALSE,np.asarray(self.mvp.flatten(order='F'),np.float32))
        gl.glDrawArrays(gl.GL_TRIANGLES,0,count)
        return self.target.read_rgba()

    def close(self):
        gl=self.gl;gl.glUseProgram(0);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,0)
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,0);gl.glDeleteBuffers(1,[self.buffer])
        self.resources.release_resources();self.target.close()


@pytest.mark.parametrize('kind,width,height,turn,scale',(
    ('Orthographic',96,64,0.,1.),('Orthographic',160,48,1.,.25),
    ('Perspective',96,64,0.,1.),('Perspective',48,160,-1.,4.),
))
def test_actual_plane_covers_complete_ground_and_reports_true_world_xz(qt_app,kind,width,height,turn,scale):
    probe=GroundProbe(width,height)
    try:
        view,projection,eye,lens,pixels,hits=probe.draw(camera(camera_projection=kind,tilt=.5,turn=turn,scene_scale=scale))
        yy,xx=np.mgrid[:height,:width]
        ndc=np.stack(((xx+.5)/width*2.-1.,1.-(yy+.5)/height*2.),axis=-1)
        right,up,back=view[:3,:3]
        if lens[2]:
            origin=eye+ndc[:,:,0,None]*lens[0]*right+ndc[:,:,1,None]*lens[1]*up
            direction=np.broadcast_to(-back,origin.shape)
        else:
            origin=np.broadcast_to(eye,(height,width,3))
            direction=ndc[:,:,0,None]*lens[0]*right+ndc[:,:,1,None]*lens[1]*up-back
        valid=direction[:,:,1]<0.
        distance=np.zeros((height,width));distance[valid]=-origin[valid,1]/direction[valid,1]
        world=origin+distance[:,:,None]*direction
        observed=pixels[:,:,0]>200
        np.testing.assert_array_equal(observed,valid)
        np.testing.assert_allclose(hits[valid,:3],world[valid],atol=.03,rtol=3e-4)
        assert np.nanmax(np.abs(hits[:,:,1]))==0.
        if lens[2]:
            assert observed.all()  # Foreground AND far background, not just the old middle band.
            assert (hits[-1,:,3]==0.).all()
            assert (hits[0,:,3]>0.9999).all()
        else:
            assert not observed[0].any() and observed[-1].all()
    finally:probe.close()


@pytest.mark.parametrize('kind',('Orthographic','Perspective'))
def test_ground_depth_occludes_underfloor_but_preserves_abovefloor_and_actor_positive_clip(qt_app,kind):
    probe=GroundProbe(144,96);values=camera(camera_projection=kind,tilt=.5)
    try:
        view,projection,eye,lens,baseline,hits=probe.draw(values)
        pixels=probe.actor(np.array((0.,-1.,0.)),name='underfloor')
        np.testing.assert_array_equal(pixels,baseline)
        pixels=probe.actor(np.array((0.,1.,0.)),name='abovefloor')
        assert (pixels[:,:,1]>200).any()
        view,projection,eye,lens,baseline,hits=probe.draw(values)
        behind=eye+view[2,:3]*3.
        pixels=probe.actor(behind,name='behindeye',basis=(view[0,:3],view[1,:3]))
        np.testing.assert_array_equal(pixels,baseline)
    finally:probe.close()


def test_negative_control_larger_plane_and_disabled_depth_test_cannot_remove_actor_clip_cuts(qt_app):
    probe=GroundProbe(144,96)
    try:
        view,projection,eye,lens,complete,hits=probe.draw(camera(tilt=.5))
        assert (complete[:,:,0]>200).all()
        gl=probe.gl;probe.target.bind();gl.glDisable(gl.GL_DEPTH_TEST)
        vertex='#version 460 core\nlayout(location=0)in vec3 position;uniform mat4 uMvp;void main(){gl_Position=uMvp*vec4(position,1);}'
        fragment='#version 460 core\nout vec4 FragColor;void main(){FragColor=vec4(1,0,0,1);}'
        program=probe.resources.program('clipped negative control',vertex,fragment)
        corners=((-10000.,0.,-10000.),(10000.,0.,-10000.),(10000.,0.,10000.),(-10000.,0.,-10000.),(10000.,0.,10000.),(-10000.,0.,10000.))
        vao,count=probe.resources.mesh('huge finite plane',np.asarray(corners,np.float32).tobytes(),(3,))
        gl.glUseProgram(program);gl.glBindVertexArray(vao)
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(program,'uMvp'),1,gl.GL_FALSE,np.asarray(probe.mvp.flatten(order='F'),np.float32))
        gl.glDrawArrays(gl.GL_TRIANGLES,0,count);pixels=probe.target.read_rgba()
        assert not pixels[0,:,0].any() and not pixels[-1,:,0].any()
        assert pixels[60:72,:,0].max()>200  # Same bounded band despite ample world coverage.
    finally:probe.close()


@pytest.mark.parametrize('kind',('Orthographic','Perspective'))
def test_production_floor_material_and_specular_cap_share_coverage_and_reflection(qt_app,kind):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    from tests.test_waveform_ribbon_mode import frame_for
    from widgets.spotify_visualizer.render_state import freeze_render_fields
    target=OffscreenRenderTarget(240,160);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);state=frame.snapshot.logical.mode_state
        values={**dict(state.parameters),'waveform_ribbon_camera_projection':kind,'waveform_ribbon_tilt':.5}
        # Isolate receiver/cap behavior from the rejected finite old haze: a near-level
        # Ortho reflection meets the world floor far in the foreground, outside that haze's clear ellipse.
        environment=replace(state.scene.environment,mist={**state.scene.environment.mist,'uMistShape':(0.,0.,0.,0.)})
        state=replace(state,parameters=freeze_render_fields(values),scene=replace(state.scene,fog=None,environment=environment))
        def draw(cap,reflection):
            floor=replace(state.scene.floor,specular_max_height=cap,reflection=reflection)
            frame.snapshot.logical.mode_state=replace(state,scene=replace(state.scene,floor=floor))
            target.bind();renderer.render(frame)
            return target.read_rgba()[:,:,:3].astype(float)
        inline=draw(10000,4.5)-draw(10000,0.)
        capped=draw(80,4.5)-draw(80,0.)
        a,b=inline.clip(0).mean(),capped.clip(0).mean()
        assert a>.2 and .8<b/a<1.2,(a,b,b/a)
    finally:renderer.release_resources();target.close()
