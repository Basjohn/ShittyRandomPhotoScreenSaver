"""Grounded navigation crosses admission, capture-clock motion, raster and Settings seams."""
import itertools
import math
from types import SimpleNamespace
import numpy as np
import pytest
from core.settings import framed_camera as fc
from core.waveform_ribbon_scene import SPEC
from rendering.quick.visualizer.implementations.waveform_ribbon import physical_view
from tests.test_waveform_ribbon_camera import camera
from widgets.spotify_visualizer.config_applier import apply_presentation_vis_mode_kwargs
from widgets.spotify_visualizer.view_orbit import (
    apply_view_orbit_motion,set_framed_flight_rates,settle_framed_flight,stop_view_orbit_motion,
)


def focused(values):
    axes,eye,offset=fc.resolve_camera_frame(SPEC,values)
    radius=math.hypot(eye[0]-SPEC.pivot[0],eye[2]-SPEC.pivot[2])
    assert eye[1]==pytest.approx(SPEC.grounded_orbit.eye_height,abs=1e-12)
    assert SPEC.grounded_orbit.radius_range[0]-1e-10<=radius<=SPEC.grounded_orbit.radius_range[1]+1e-10
    assert abs(math.atan2(eye[0]-SPEC.pivot[0],eye[2]-SPEC.pivot[2]))<=SPEC.yaw_span+1e-10
    assert eye[2]>=SPEC.grounded_orbit.radius_range[0]*math.cos(SPEC.yaw_span)-1e-10
    tilt=max(SPEC.tilt_range[0],min(SPEC.tilt_range[1],values[SPEC.key('tilt')]))
    target=(*SPEC.pivot,1.)
    target=np.asarray(target);target[1]=fc.grounded_focus_height(SPEC,tilt,eye)
    view,projection,rendered,lens=physical_view(values,1.5)
    np.testing.assert_allclose(rendered,eye,atol=1e-12)
    clip=projection@view@target
    np.testing.assert_allclose(clip[:2]/clip[3],0.,atol=1e-12)
    assert clip[3]>0 and -1.<clip[2]/clip[3]<1.
    return np.asarray(eye),radius,lens


def test_all_pose_authoring_paths_keep_height_focus_and_front_annulus():
    for turn,tilt,scale,pan,position in itertools.product(
            (-1.,0.,1.),(-.5,.5),(.25,1.,4.),(-.5,.5),((-1.,-1.,-1.),(1.,1.,1.))):
        values=camera(turn=turn,tilt=tilt,scene_scale=scale,
                      scene_pan_x=pan,scene_pan_y=-pan,camera_position=position)
        eye,radius,lens=focused(values)
        offset=fc.admit_camera_parameters(SPEC,values)
        focused({**values,SPEC.key('camera_position'):offset})


def test_forward_approaches_visibly_and_reverse_has_no_boundary_debt():
    values=camera();host=SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host,values)
    before,radius,lens=focused(values)
    set_framed_flight_rates(host,'waveform_ribbon',0.,0.,0.,1.,0.)
    approached={**values,**apply_view_orbit_motion(host,'waveform_ribbon',values,.5)}
    after,new_radius,new_lens=focused(approached)
    assert new_radius==pytest.approx(radius-8.)
    # A fixed world landmark grows through the admitted physical dolly.
    def projected_x(pose):
        view,projection,_,_=physical_view(pose,1.5)
        clip=projection@view@np.array((1.,2.,0.,1.))
        return abs(clip[0]/clip[3])
    assert projected_x(approached)>projected_x(values)*1.1
    assert approached[SPEC.key('camera_fov')]==values[SPEC.key('camera_fov')]
    at_boundary={**values,**apply_view_orbit_motion(host,'waveform_ribbon',values,10000.)}
    assert focused(at_boundary)[1]==pytest.approx(64.)
    set_framed_flight_rates(host,'waveform_ribbon',0.,0.,0.,-1.,10000.)
    reversed_={**values,**apply_view_orbit_motion(host,'waveform_ribbon',values,10000.1)}
    assert focused(reversed_)[1]==pytest.approx(65.6)


@pytest.mark.parametrize('yaw,pitch,strafe,travel',((0.,0.,1.,0.),(1.,1.,0.,1.),(-1.,-1.,0.,-1.)))
def test_held_orbit_pitch_and_approach_stay_grounded_and_persist_the_same_admitted_pose(yaw,pitch,strafe,travel):
    values=camera();host=SimpleNamespace()
    apply_presentation_vis_mode_kwargs(host,values)
    set_framed_flight_rates(host,'waveform_ribbon',yaw,pitch,strafe,travel,0.)
    for now in (.01,.1,1.,3.,10000.):
        pose={**values,**apply_view_orbit_motion(host,'waveform_ribbon',values,now)}
        focused(pose)
        assert -1.<=pose[SPEC.key('turn')]<=1.
    frozen=pose
    offset=settle_framed_flight(host,10000.)
    stop_view_orbit_motion(host,10000.)
    persisted={key:getattr(host,'_'+key) for key in values}
    # Existing Camera Position settings persist six decimals (120-unit X/Z normalization).
    np.testing.assert_allclose(focused(persisted)[0],focused(frozen)[0],atol=8e-5)
    assert tuple(offset)==pytest.approx(persisted[SPEC.key('camera_position')])
    if strafe:assert abs(persisted[SPEC.key('turn')])==pytest.approx(1.)


def test_near_level_tilt_is_half_a_degree_down_at_every_admitted_radius_with_shared_inverse():
    assert SPEC.grounded_orbit.eye_height==4.5
    assert SPEC.grounded_orbit.radius_range==(64.,104.)
    for turn,scale,tilt in itertools.product((-1.,0.,1.),(.25,1.,4.),(-.5,0.,.5)):
        values=camera(turn=turn,scene_scale=scale,tilt=tilt)
        axes,eye,_=fc.resolve_camera_frame(SPEC,values)
        radius=math.hypot(eye[0]-SPEC.pivot[0],eye[2]-SPEC.pivot[2])
        bottom,top=1.5,4.5-radius*math.tan(math.radians(.5))
        focus=bottom+(top-bottom)*(tilt+.5)
        assert fc.grounded_focus_height(SPEC,tilt,eye)==pytest.approx(focus,abs=1e-12)
        assert fc.grounded_tilt_from_focus_height(SPEC,focus,eye)==pytest.approx(tilt,abs=1e-12)
        if tilt==.5:assert math.degrees(math.asin(axes[7]))==pytest.approx(.5,abs=1e-12)
        assert eye[1]==4.5 and 1.5<=focus<4.5


@pytest.mark.qt
def test_near_level_native_ground_coverage_and_approach_grows_real_geometry(qt_app):
    """Use production floor vertices/camera with a solid test material, independent of fog/material tuning."""
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from core.ribbon_geometry import PathSample
    from core.ribbon_packet import pack_ribbons
    from rendering.gl_programs.waveform_ribbon import FLOOR_WORLD_GLSL
    from tests.test_waveform_infinite_floor import probe_floor_vertex
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.waveform import floor_vertices
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.scene3d.ribbon import RibbonPrimitive
    target=OffscreenRenderTarget(240,160);floor=MeshResources('near-level floor test');body=RibbonPrimitive()
    fragment='#version 460 core\n'+FLOOR_WORLD_GLSL+'''
out vec4 FragColor;void main(){vec3 world;float depth;if(!floorWorldHit(world,depth))discard;
gl_FragDepth=depth;FragColor=vec4(1,0,0,1);}
'''
    packet=pack_ribbons([([PathSample(0.,(-2.,2.,0.),.4),PathSample(1.,(2.,2.,0.),.4)],[(1.,0.,0.)]*2,None)])
    try:
        program=floor.program('floor',probe_floor_vertex(),fragment)
        vao,count=floor.mesh('floor',floor_vertices(),(3,))
        def draw_floor(values):
            view,projection,eye,lens=physical_view(values,1.5)
            target.bind();gl.glEnable(gl.GL_DEPTH_TEST);gl.glDepthFunc(gl.GL_LESS);gl.glDepthMask(gl.GL_TRUE)
            gl.glUseProgram(program);gl.glBindVertexArray(vao)
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(program,'uMvp'),1,gl.GL_FALSE,
                                  np.asarray((projection@view).flatten(order='F'),np.float32))
            gl.glUniformMatrix4fv(gl.glGetUniformLocation(program,'uFloorInverseMvp'),1,gl.GL_FALSE,
                                  np.asarray(np.linalg.inv(projection@view).flatten(order='F'),np.float32))
            gl.glUniform3f(gl.glGetUniformLocation(program,'uEye'),*eye)
            gl.glDrawArrays(gl.GL_TRIANGLES,0,count)
            return view,projection
        for turn,scale in itertools.product((-1.,0.,1.),(.25,1.,4.)):
            values=camera(tilt=.5,turn=turn,scene_scale=scale)
            v,p=draw_floor(values);pixels=target.read_rgba();yy,xx=np.where(pixels[:,:,0]>200)
            assert len(xx)>240*160*.03
            horizon=160*.5*(1.-v[2,1]/(v[1,1]*(1./p[1,1])))
            assert yy.min()==math.ceil(horizon-.5) and yy.max()==159
        values=camera(tilt=.5);host=SimpleNamespace()
        apply_presentation_vis_mode_kwargs(host,values)
        set_framed_flight_rates(host,'waveform_ribbon',0.,0.,0.,1.,0.)
        approached={**values,**apply_view_orbit_motion(host,'waveform_ribbon',values,.5)}
        widths=[]
        for pose in (values,approached):
            view,projection=draw_floor(pose)
            body.draw(packet,tuple((projection@view).flatten(order='F')))
            pixels=target.read_rgba();yy,xx=np.where((pixels[:,:,1]>100)&(pixels[:,:,2]>100))
            assert len(xx)>0
            widths.append(xx.max()-xx.min()+1)
        assert widths[1]>widths[0]*1.1
    finally:
        gl.glUseProgram(0);body.release();floor.release_resources();target.close()
