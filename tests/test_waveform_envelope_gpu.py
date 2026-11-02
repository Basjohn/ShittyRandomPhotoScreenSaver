"""Native packet→GPU-field equivalence and physical clearance; no curated-preset golden."""
from dataclasses import replace
import numpy as np
import pytest
from core.ribbon_ring import RibbonRing
from core.waveform_ribbon_scene import Recipe,FLOOR_CONTACT,VIEW_SLOPE
from rendering.quick.scene3d.waveform import waveform_envelope,crackle_limit,colour_grade


@pytest.mark.qt
@pytest.mark.parametrize('removed',(False,True))
def test_gpu_field_and_edge_limit_match_the_cpu_oracle(qt_app,removed):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    from rendering.quick.scene3d.waveform_envelope import WaveformEnvelope
    from tools.labs.waveform_ribbon_lab import camera,POSES
    target=OffscreenRenderTarget(160,120);primitive=RibbonPrimitive();gpu=WaveformEnvelope()
    try:
        ring=RibbonRing(3,colours=[(.2,.5,.8,1.),(.8,.1,.4,0. if removed else .4),(.1,.8,.2,1.)])
        for index in range(60):
            x=64.+(index-30)*.4
            ring.append(index/6,[(x,2.+np.sin(index*.2+i),np.cos(index*.15+i)) for i in range(3)],
                        [.5,.25,.8],twists=index*.1,emission=[1.,.5,1.5],
                        tint=[(.9,.2,.1,.3),(.2,.9,.3,.6),(.1,.3,.9,.8)])
        packet=ring.packet();recipe=Recipe();fog=recipe.fog
        translation=(-64.,0.,0.);age=(10.,.2,20.,.5);grade=colour_grade(recipe,.4)
        view,projection,_=camera(POSES['mock'],160/120);mvp=projection@view
        with primitive.packet_scope(packet):
            gpu.update(packet,translation=translation,age_fade=age,fog=fog,grade=grade,camber=.7,
                       mvp=mvp,slopes=(0.,VIEW_SLOPE),floor=FLOOR_CONTACT)
        gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT)
        observed=np.empty((6,640,4),np.float32)
        gl.glGetTextureImage(gpu.texture,0,gl.GL_RGBA,gl.GL_FLOAT,observed.nbytes,observed)
        expected=waveform_envelope(packet,translation,age,fog,grade,camber=.7)
        np.testing.assert_allclose(observed,expected,atol=3e-4,rtol=3e-4)
        limit=np.empty(256,np.float32)
        gl.glGetTextureImage(gpu.limit,0,gl.GL_RED,gl.GL_FLOAT,limit.nbytes,limit)
        np.testing.assert_allclose(limit,crackle_limit(expected,fog,mvp,160),atol=3e-5,rtol=3e-5)
    finally:
        gpu.release();primitive.release();target.close()


@pytest.mark.qt
@pytest.mark.parametrize('roll,share',((0.,1.),(.8,.4),(1.6,1.)))
def test_gpu_clearance_contains_real_shader_vertices_through_side_wall_and_count_fade(qt_app,roll,share):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from core.ribbon_style import RibbonMaterial
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    from rendering.quick.scene3d.waveform_envelope import WaveformEnvelope
    from tests.test_ribbon_gpu import capture_vertices
    target=OffscreenRenderTarget(160,120);primitive=RibbonPrimitive();gpu=WaveformEnvelope()
    try:
        ring=RibbonRing(1,colours=[(.1,.5,.9,share)])
        for index in range(80):
            y,z=2.4*np.sin(index*.25),1.8*np.cos(index*.18)
            c,s=np.cos(roll),np.sin(roll)
            ring.append(index/6,[((index-40)*.4,2.+share*(c*y-s*z),share*(s*y+c*z))],[1.2*share],
                        twists=roll+np.sin(index*.2))
        packet=ring.packet();recipe=Recipe();fog=replace(recipe.fog,sides=(5.,10.))
        matrix=tuple(np.identity(4).flatten(order='F'));age=(20.,0.,100.,0.)
        with primitive.packet_scope(packet):
            gpu.update(packet,translation=(0.,0.,0.),age_fade=age,fog=fog,grade=colour_grade(recipe,.4),
                camber=1.,mvp=np.identity(4),slopes=(0.,VIEW_SLOPE),floor=FLOOR_CONTACT)
            vertices=capture_vertices(primitive,packet,matrix,material=RibbonMaterial(cross_curve=1.),
                                      sweep_axis=(1.,0.,0.),floor=FLOOR_CONTACT)
        gl.glMemoryBarrier(gl.GL_TEXTURE_UPDATE_BARRIER_BIT)
        table=np.empty((6,640,4),np.float32)
        gl.glGetTextureImage(gpu.texture,0,gl.GL_RGBA,gl.GL_FLOAT,table.nbytes,table)
        points=vertices[:,0,:3]+np.asarray(packet.world_origin)
        points=points[(np.abs(points[:,0])<13.)&(np.abs(points[:,0])>.01)]
        xs=np.linspace(*fog.envelope_range)
        cy,cz,radius,live=(np.interp(points[:,0],xs,table[3,:,i]) for i in range(4))
        assert np.min(live)>.99
        distance=np.hypot(points[:,1]-cy,points[:,2]-cz)-radius
        assert distance.max()<=1e-4,f'Fog can enter the real surface by {distance.max()} world units'
    finally:
        gpu.release();primitive.release();target.close()
