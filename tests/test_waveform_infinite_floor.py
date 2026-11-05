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
        assert np.nanmax(np.abs(hits[:,:,1]))==0.
        # Since the grounded long-lens orbit (2e201069: eye radius 64-104, 4.5 high, pitch at most a
        # few degrees, 3 degree lens) the visible ground runs 10^2-10^5 world units out at grazing
        # incidence, where a float32 inverse-MVP ray loses ~1e-3 of its range ALONG the view. The
        # accuracy that matters is that each hit lies on its own pixel's ray: reproject it.
        clip=np.einsum('ij,hwj->hwi',projection@view,np.concatenate((hits[:,:,:3],np.ones((height,width,1))),axis=-1))
        reprojected=clip[:,:,:2]/clip[:,:,3:4]
        pixel_error=np.abs(reprojected[valid]-ndc[valid])*np.array((width,height))/2.
        assert pixel_error.max()<.05,pixel_error.max()
        # The analytic world point agrees with the ray/plane solution where float32 range is not the limit.
        near=distance<=200.
        np.testing.assert_allclose(hits[valid&near,:3],world[valid&near],atol=.03,rtol=3e-4)
        if lens[2]:
            assert observed.all()  # Foreground AND far background, not just the old middle band.
            # Farther ground sits higher in the frame: raster depth never decreases upward, and the
            # horizon-side row reaches the far bound. (With the long-lens orbit the whole visible ground
            # lies beyond the fitted scene slab, so the old "foreground row at the near plane" is gone.)
            assert (np.diff(hits[::-1,:,3],axis=0)>=-1e-6).all()
            assert (hits[0,:,3]>0.9999).all()
        else:
            assert not observed[0].any() and observed[-1].all()
    finally:probe.close()


@pytest.mark.parametrize('kind',('Orthographic','Perspective'))
def test_ground_occlusion_and_perspective_positive_actor_clip(qt_app,kind):
    # Steepest grounded pose. Actors are placed on one real pixel ray (bottom-centre) relative to
    # that ray's own ground hit, not at fixed world points framed by the pre-2e201069 close orbit.
    probe=GroundProbe(144,96);values=camera(camera_projection=kind,tilt=-1.)
    try:
        view,projection,eye,lens,baseline,hits=probe.draw(values)
        basis=(view[0,:3],view[1,:3]);right,up,back=view[:3,:3]
        row,column=88,72
        ndc=((column+.5)/144*2.-1.,1.-(row+.5)/96*2.)
        if lens[2]:
            origin=eye+ndc[0]*lens[0]*right+ndc[1]*lens[1]*up;direction=-back
            # Raster depth is the fitted signed slab about the scene (orthographic_raster_projection).
            near,far=(projection[2,3]+1.)/projection[2,2],(projection[2,3]-1.)/projection[2,2]
        else:
            origin=eye;direction=ndc[0]*lens[0]*right+ndc[1]*lens[1]*up-back
            direction=direction/np.linalg.norm(direction);near,far=.3,200.
        ground=-origin[1]/direction[1]
        along=lambda point:float(np.dot(point-eye,-back))
        assert np.allclose(hits[row,column,:3],origin+ground*direction,atol=1e-2*max(1.,ground))
        if along(origin+1.2*ground*direction)<far:
            # A body beneath the ground on the same ray is hidden by the ground in front of it.
            pixels=probe.actor(origin+1.2*ground*direction,name='underfloor',basis=basis)
            np.testing.assert_array_equal(pixels,baseline)
        else:
            # Ortho: the whole visible ground lies beyond the scene slab, so no under-floor point is
            # both rasterised and in frame: nothing can leak through it.
            assert lens[2] and along(origin+ground*direction)>far
        cosine=float(np.dot(direction,-back))
        above=.5*(near/cosine+min(ground,far/cosine))  # rasterised, and in front of the ground
        assert (origin+above*direction)[1]>0.
        pixels=probe.actor(origin+above*direction,name='abovefloor',basis=basis)
        assert (pixels[:,:,1]>200).any()
        if kind=='Perspective':
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
        from core.settings.framed_camera import orthographic_matrix
        # A finite clip interval inside the ground's real depth range (taken from the analytic hits,
        # since the long-lens orbit of 2e201069 puts the visible ground far beyond a fixed .3-200).
        depth=np.dot(hits[:,:,:3]-eye,-view[2,:3])
        clip_near,clip_far=np.percentile(depth,(25.,75.))
        old=np.asarray(orthographic_matrix(lens[:2],clip_near,clip_far)).reshape(4,4,order='F')@view
        gl.glUniformMatrix4fv(gl.glGetUniformLocation(program,'uMvp'),1,gl.GL_FALSE,np.asarray(old.flatten(order='F'),np.float32))
        gl.glDrawArrays(gl.GL_TRIANGLES,0,count);pixels=probe.target.read_rgba()
        assert not pixels[0,:,0].any() and not pixels[-1,:,0].any()
        assert pixels[30:66,:,0].max()>200  # Same bounded band despite ample world coverage.
    finally:probe.close()


# Perspective only, at the steepest grounded pose. Under the long-lens grounded orbit (2e201069) the
# scene's mirror image lies below every framed Orthographic ray at any authored tilt/scale, and below
# the near-level (tilt .5) Perspective frame, so the floor's reflection is physically out of view there.
@pytest.mark.parametrize('kind',('Perspective',))
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
        # Slightly zoomed out: at the authored framing the mirror image sits at the very edge of this steepest pose,
        # so any small rise of the sheets would push the measured reflection out of frame.
        values={**dict(state.parameters),'waveform_ribbon_camera_projection':kind,'waveform_ribbon_tilt':-1.,'waveform_ribbon_scene_scale':.8}
        # Isolate receiver/cap behavior from the rejected finite old haze: a near-level
        # Ortho reflection meets the world floor far in the foreground, outside that haze's clear ellipse.
        environment=replace(state.scene.environment,mist={**state.scene.environment.mist,'uMistShape':(0.,0.,0.,0.)})
        state=replace(state,parameters=freeze_render_fields(values),scene=replace(state.scene,fog=None,environment=environment))
        def draw(cap,reflection):
            floor=replace(state.scene.floor,specular_max_height=cap,reflection=reflection)
            frame.snapshot.logical.mode_state=replace(state,scene=replace(state.scene,floor=floor))
            target.bind();renderer.render(frame)
            return target.read_rgba()[:,:,:3].astype(float)
        plain=draw(10000,0.);capped_plain=draw(80,0.)
        np.testing.assert_allclose(capped_plain,plain,atol=1.)  # capped specular cannot replace the roughness map
        inline=draw(10000,4.5)-plain
        capped=draw(80,4.5)-capped_plain
        a,b=inline.clip(0).mean(),capped.clip(0).mean()
        assert a>.2 and .8<b/a<1.2,(a,b,b/a)
    finally:renderer.release_resources();target.close()
