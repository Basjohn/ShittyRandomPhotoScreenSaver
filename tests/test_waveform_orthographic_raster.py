"""Fitted Ortho depth is camera metadata; eye, projection XY and world field stay fixed."""
from dataclasses import replace
import itertools
import numpy as np
import pytest
from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import RasterSupport,scene_raster_support
from core.ribbon_continuation import frustum_axial_span
from core.waveform_ribbon_scene import Recipe,FLOOR_CONTACT,SPEC
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera
from tests.test_ribbon_continuation_culling import full_packet


@pytest.mark.parametrize('aspect',(.2,1.5,4.,16.))
def test_fit_covers_xy_support_in_main_and_mirror_without_changing_eye_basis_or_projection_xy(aspect):
    from rendering.gl_programs.reflection import mirror_view
    support=RasterSupport(((0.,15.),(-10.,10.)),(.2,.3))
    for turn,tilt,scale,aperture in itertools.product((-1.,0.,1.),(-.5,.5),(.25,4.),(.25,1.,3.)):
        values=camera(turn=turn,tilt=tilt,scene_scale=scale)
        view,projection,eye,lens=physical_view(values,aspect,aperture,geometry_bounds=support)
        axes,resolved,_=fc.resolve_camera_frame(SPEC,values)
        np.testing.assert_array_equal(eye,resolved)
        np.testing.assert_allclose(view[:3,:3].flatten(),axes,atol=0.)
        positive=np.asarray(fc.orthographic_matrix(lens[:2],.3,200.)).reshape(4,4,order='F')
        np.testing.assert_array_equal(projection[:2],positive[:2])
        near,far=fc.orthographic_depth_interval(projection)
        assert far>near
        padded=tuple(h*(1.+p) for h,p in zip(lens[:2],support.padding_ndc))
        xy=np.asarray(fc.orthographic_matrix(padded,0.,1.)).reshape(4,4,order='F')
        mirrored=mirror_view(view,0.)
        spans=[frustum_axial_span(xy@v,support.transverse,depth_clip=False) for v in (view,mirrored)]
        span=(min(s[0] for s in spans),max(s[1] for s in spans))
        corners=np.array([(*point,1.) for point in itertools.product(span,*support.transverse)])
        for v in (view,mirrored):
            clip=corners@(projection@v).T
            assert (np.abs(clip[:,2]/clip[:,3])<1.).all()


def test_wide_fitted_slab_admits_real_field_behind_reference_while_perspective_is_unchanged():
    values=camera(turn=1.,tilt=.5)
    view,projection,eye,lens=physical_view(values,4.)
    point=np.array((22.,2.,0.,1.))
    assert (view@point)[2]>0.  # Behind the finite reference plane, still inside the parallel XY aperture.
    positive=np.asarray(fc.orthographic_matrix(lens[:2],.3,200.)).reshape(4,4,order='F')
    assert (positive@view@point)[2]<-1.
    clip=projection@view@point
    assert (np.abs(clip[:3])<1.).all()
    values[SPEC.key('camera_projection')]='Perspective'
    view,projection,eye,lens=physical_view(values,4.,geometry_bounds=RasterSupport(((0.,100.),(-100.,100.))))
    expected=np.asarray(fc.perspective_matrix(lens[:2],.3,200.)).reshape(4,4,order='F')
    np.testing.assert_array_equal(projection,expected)


def test_support_keeps_living_particle_excursions_held_strands_and_reflected_pixel_halos():
    from core.ribbon_bursts import CAPACITY
    from core.ribbon_style import RibbonStrays
    packet=full_packet();recipe=replace(Recipe(),strays=RibbonStrays(reach=.01,width=.1))
    bursts=np.zeros((CAPACITY,16),np.float32)
    bursts[0,:]=(0.,30.,-20.,2.,3.,6.,-4.,8.,1.,1.,1.,12.,2.,0.,0.,3.)
    strands=np.zeros((packet.instances*256,3,4),np.float32)
    strands[0,0,0]=1.;strands[0,1]=(16.,4.,16.,10.)
    support=scene_raster_support(packet,recipe,0.,now=100.,viewport=(240,60),burst_payload=bursts.tobytes(),
                                 burst_origin=96.,strand_payload=strands.tobytes())
    assert support.transverse[0][1]>=39.6
    assert support.transverse[1][0]<=-26.4
    assert support.transverse[1][1]>=11.
    assert support.padding_ndc[1]>=2.*78./30.
    expired=scene_raster_support(packet,recipe,0.,now=110.,viewport=(240,60),burst_payload=bursts.tobytes(),
                                 burst_origin=96.,strand_payload=strands.tobytes())
    assert expired.transverse[0][1]<support.transverse[0][1]


@pytest.mark.qt
def test_native_wide_field_has_no_in_aperture_depth_cuts_and_retains_exact_world_vertices(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    from rendering.gl_programs.ribbon import RIBBON_CONTINUOUS_VERTEX,RIBBON_FRAGMENT
    from core.ribbon_style import RibbonMaterial
    from rendering.gl_programs.reflection import mirror_view
    packet=full_packet();recipe=replace(Recipe(),material=RibbonMaterial(cross_curve=.7),sparks=None,strays=None)
    target=OffscreenRenderTarget(240,60);primitive=RibbonPrimitive();buffer=0
    source=RIBBON_CONTINUOUS_VERTEX.replace('void main() {','void ribbonMain() {',1)+'''
layout(std430,binding=5) buffer Statistics { uint stats[4]; };
void main(){ribbonMain();vec4 c=gl_Position;
if(c.w>0.0 && all(lessThanEqual(abs(c.xy),vec2(c.w)))){
atomicAdd(stats[0],1u);if(c.z< -c.w)atomicAdd(stats[1],1u);if(c.z>c.w)atomicAdd(stats[2],1u);}}
'''
    try:
        primitive.resources.program('diagnostic_continuous',source,RIBBON_FRAGMENT)
        buffer=int(np.asarray(gl.glGenBuffers(1)).reshape(-1)[0]);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,buffer)
        support=scene_raster_support(packet,recipe,0.,now=1.,viewport=(240,60),burst_payload=b'',strand_payload=b'')
        view,projection,eye,lens=physical_view(camera(turn=1.,tilt=.5),4.,geometry_bounds=support)
        mirror=mirror_view(view,0.)
        spans=[frustum_axial_span(projection@v,support.transverse) for v in (view,mirror)]
        span=(min(s[0] for s in spans),max(s[1] for s in spans),2048)
        positive=np.asarray(fc.orthographic_matrix(lens[:2],.3,200.)).reshape(4,4,order='F')
        def draw(matrix,v):
            zero=np.zeros(4,np.uint32);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
            gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER,zero.nbytes,zero,gl.GL_STREAM_READ)
            target.bind();primitive.draw(packet,tuple((matrix@v).flatten(order='F')),sweep_axis=(1.,0.,0.),
                floor=FLOOR_CONTACT,material=recipe.material,continuation=span)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,buffer)
            stats=np.frombuffer(gl.glGetBufferSubData(gl.GL_SHADER_STORAGE_BUFFER,0,zero.nbytes),np.uint32).copy()
            return stats,target.read_rgba()
        for v in (view,mirror):
            fitted,pixels=draw(projection,v);old,clipped=draw(positive,v)
            assert fitted[0]>1000 and fitted[1]==0 and fitted[2]==0
            assert old[1]>1000  # Negative control: same world geometry and XY, only the old Z slab differs.
            assert np.count_nonzero(pixels[:,-12:,:3])>np.count_nonzero(clipped[:,-12:,:3])
    finally:
        gl.glUseProgram(0);gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER,5,0);gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER,0)
        if buffer:gl.glDeleteBuffers(1,[buffer])
        primitive.release();target.close()
