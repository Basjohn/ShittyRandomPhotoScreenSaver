"""Held root cohorts: live thresholds cannot re-admit or erase a living strand."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from core.ribbon_ring import RibbonRing
from core.ribbon_strand_cohorts import RibbonStrandControls,RibbonStrandCohorts,COHORT_ROWS,remaining_strand
from core.ribbon_strand_cohorts import ROOTS_PER_ACCENT


def packet():
    ring=RibbonRing(1)
    for index in range(256):ring.append(index/6,[(index/6-20.,2.,0.)],[.4])
    return ring.packet()


def controls(**overrides):
    ranges=dict(strand_count=(4.,4.),strand_chance=(.6,.6),strand_span=(32.,32.),
                strand_length=(4.,4.),strand_reach=(1.,1.),strand_width=(2.,2.),strand_light=(4.,4.),
                strand_beads=(5.,5.),strand_peel=(.3,.3),strand_halo=(.2,.2),strand_glow=(1.,1.),strand_eol=(30.,30.),strand_fade=(.85,.85))
    return RibbonStrandControls({**ranges,**overrides})


def snapshot(p,now,*,sparkle=.6):
    return SimpleNamespace(packet=p,time=now,head_x=0.,travel=0.,drives=(('sparkle',.5),),realized=(('sparkle',sparkle),))


def test_held_look_survives_threshold_changes_and_metadata_remains_for_smooth_reactivation():
    p=packet();cohorts=RibbonStrandCohorts(1)
    payload=cohorts.update(snapshot(p,1.),controls(),.5,history=p,knot_hz=6.)
    assert payload
    live=cohorts.records[:,:,0,0]>0
    assert live.any()
    born=cohorts.records.copy()
    for now in np.linspace(1.01,3.9,90):
        held=cohorts.update(snapshot(p,now,sparkle=.001),controls(strand_count=(0.,0.),strand_chance=(0.,0.)),
                            .5,history=p,knot_hz=6.)
        assert held==payload
        np.testing.assert_array_equal(cohorts.records[live],born[live])
    assert cohorts.update(snapshot(p,1000.),controls(),0.,history=p,knot_hz=6.)==b''
    np.testing.assert_array_equal(cohorts.records[live],born[live])


def test_root_identity_survives_coordinate_rebase_but_recycled_slots_cannot_reuse_a_cohort():
    from core.ribbon_packet import RibbonPacket,KNOT_ROWS
    p=packet();cohorts=RibbonStrandCohorts(1)
    original=cohorts.update(snapshot(p,1.),controls(),1.,history=p,knot_hz=6.)
    data=np.frombuffer(p.payload,np.float32).copy().reshape(1,-1,4)
    data[:,5::KNOT_ROWS,0]-=16.
    rebased=replace(p,payload=data.tobytes(),coordinate_origin=p.coordinate_origin+16.)
    assert cohorts.update(snapshot(rebased,1.1),controls(),0.,history=rebased,knot_hz=6.)==original
    active=np.flatnonzero(cohorts.records[0,:,0,0]>0)[0]
    data[0,5+active*KNOT_ROWS,0]+=1.
    recycled=replace(rebased,payload=data.tobytes())
    cohorts.update(snapshot(recycled,1.2),controls(),0.,history=recycled,knot_hz=6.)
    assert cohorts.records[0,active,0,0]==0.


def test_repeat_event_updates_pulse_without_rebirth_or_look_replacement():
    p=packet();cohorts=RibbonStrandCohorts(1)
    cohorts.update(snapshot(p,1.),controls(strand_span=(.01,.01)),1.,history=p,knot_hz=6.)
    before=cohorts.records.copy();live=before[:,:,0,0]>0
    cohorts.update(snapshot(p,2.),controls(strand_length=(12.,12.),strand_light=(0.,0.),strand_span=(.01,.01)),.5,history=p,knot_hz=6.)
    after=cohorts.records
    np.testing.assert_array_equal(after[:,:,0,:2][live],before[:,:,0,:2][live])
    np.testing.assert_array_equal(after[:,:,1:3][live],before[:,:,1:3][live])
    assert np.all(after[:,:,0,2][live]==2.)
    assert np.all(after[:,:,0,3][live]==0.)
    cohorts.update(snapshot(p,2.15),controls(strand_span=(.01,.01)),.5,history=p,knot_hz=6.)
    assert np.all(cohorts.records[:,:,0,3][live]>.8)


def test_rejected_lifetime_setting_is_removed_at_settings_admission():
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    values=normalize_visualizer_section_mapping({'waveform_ribbon_strand_lifetime':[2.,8.]},apply_preset_overlay=False)
    assert 'waveform_ribbon_strand_lifetime' not in values


def test_each_real_accent_only_activates_a_few_roots_and_total_life_is_three_to_five_seconds():
    p=packet();cohorts=RibbonStrandCohorts(1)
    c=controls(strand_eol=(3.,5.),strand_fade=(.85,.9))
    cohorts.update(snapshot(p,1.),c,1.,history=p,knot_hz=6.)
    life=cohorts.records[:,:,3][cohorts.records[:,:,0,0]>0.]
    assert 0<len(life)<=ROOTS_PER_ACCENT
    assert np.all(life[:,0]==4.) and np.all(life[:,1]<life[:,0])
    assert (remaining_strand(life[:,0],life[:,0],life[:,1],life[:,2])==0.).all()


def test_root_selection_cannot_renew_a_strand_past_its_retained_history_lease():
    p=packet();cohorts=RibbonStrandCohorts(1)
    c=controls(strand_eol=(5.,5.),strand_fade=(.9,.9),strand_span=(.01,.01))
    # The only root in this emitter is q=20. It has 3.5 seconds left at now=59; a 5-second strand is inadmissible.
    assert cohorts.update(snapshot(p,59.),c,1.,history=p,knot_hz=6.)==b''


def test_expired_cohorts_submit_no_payload_and_can_reactivate_without_rebirth():
    p=packet();cohorts=RibbonStrandCohorts(1)
    c=controls(strand_eol=(3.,3.),strand_fade=(.9,.9),strand_span=(.01,.01))
    born=cohorts.update(snapshot(p,1.),c,1.,history=p,knot_hz=6.)
    held=cohorts.records[:,:,1:3].copy()
    assert born and cohorts.update(snapshot(p,3.999),c,0.,history=p,knot_hz=6.)==born
    assert cohorts.update(snapshot(p,4.),c,0.,history=p,knot_hz=6.)==b''
    assert cohorts.update(snapshot(p,5.),c,1.,history=p,knot_hz=6.)
    np.testing.assert_array_equal(cohorts.records[:,:,1:3],held)
    active=cohorts.records[:,:,0,0]>0.
    life=cohorts.records[:,:,3][active]
    assert (life[:,2]==0.).all()  # invisible at the retrigger, then recovers smoothly
    assert (remaining_strand(.3,life[:,0],life[:,1],life[:,2])>0.).all()


def test_partial_and_finished_fades_reactivate_continuously_with_held_look():
    p=packet();cohorts=RibbonStrandCohorts(1);c=controls(strand_eol=(2.,2.),strand_fade=(.85,.85),strand_span=(.01,.01))
    cohorts.update(snapshot(p,1.),c,1.,history=p,knot_hz=6.)
    live=cohorts.records[:,:,0,0]>0.;held=cohorts.records[:,:,1:3].copy()
    for now in (2.2,30.):
        before=cohorts.records[:,:,3][live].copy()
        front=remaining_strand(now-cohorts.origin-before[:,3],before[:,0],before[:,1],before[:,2])
        cohorts.update(snapshot(p,now),c,1.,history=p,knot_hz=6.)
        after=cohorts.records[:,:,3][live]
        np.testing.assert_allclose(remaining_strand(now-cohorts.origin-after[:,3],after[:,0],after[:,1],after[:,2]),front,atol=1e-6)
        assert (remaining_strand(now+.5-cohorts.origin-after[:,3],after[:,0],after[:,1],after[:,2])>=front).all()
        np.testing.assert_array_equal(cohorts.records[:,:,1:3],held)


@pytest.mark.qt
def test_actual_strand_shader_holds_birth_look_before_its_authored_gentle_eol(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive,RibbonStrays,RibbonMaterial
    from tests.test_ribbon_gpu import parallel_mvp
    target=OffscreenRenderTarget(240,160);primitive=RibbonPrimitive();p=packet()
    births=np.zeros((1,256,COHORT_ROWS,4),np.float32);births[:,:,0,0]=1.;births[:,:,0,2]=2.
    births[:,:,1]=[4.,1.,2.,4.];births[:,:,2]=[5.,.3,.2,1.];births[:,:,3]=[30.,12.,1.,0.]
    view=tuple(np.identity(4).flatten(order='F'));mvp=parallel_mvp((6.,4.),.1,100.)
    # Put the test sheet in front of the eye without changing its stable knot IDs.
    mvp=np.asarray(mvp).reshape(4,4,order='F');mvp=mvp@np.array(((1,0,0,0),(0,1,0,-2),(0,0,1,-5),(0,0,0,1)))
    images=[]
    try:
        with target.current():
            for now,chance in ((1.,0.),(1.,1.),(.001,1.),(10.,1.),(1000.,1.)):
                target.bind(clear=(0.,0.,0.,0.));gl.glDisable(gl.GL_DEPTH_TEST)
                primitive.draw(p,tuple(mvp.flatten(order='F')),shading='strays',view=view,now=now,
                    sweep_axis=(1.,0.,0.),material=RibbonMaterial(cross_curve=.3),
                    strays=RibbonStrays(per_knot=8,length=32. if chance else 4.,reach=4. if chance else 1.,
                        chance=chance,width=.1 if chance else 2.,light=0. if chance else 4.,peel_time=4. if chance else .3),
                    strand_births=births.tobytes(),strand_origin=0.)
                images.append(target.read_rgba()[:,:,:3])
            assert images[0].max()>50
            np.testing.assert_array_equal(images[0],images[1])
            assert images[2].sum()<images[0].sum()*.1
            assert images[3].sum()>=images[0].sum()*.9
            assert images[4].max()==0
            assert primitive.strand_stream.has_resources
            primitive.release_strands()
            assert primitive.strand_stream is None and primitive.strand_resources is None
    finally:
        with target.current():primitive.release()
        target.close()


@pytest.mark.qt
def test_production_tip_fade_is_broad_slow_and_reaches_roots_last(qt_app):
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.gl_programs.fog_volume import FOG_FULLSCREEN_VERTEX
    from rendering.gl_programs.ribbon import STRAND_LIFE_GLSL
    from OpenGL import GL as gl
    target=OffscreenRenderTarget(100,8);resources=MeshResources('tip fade proof')
    try:
        shader='#version 460 core\nin vec2 vNdc;out vec4 FragColor;uniform float uAge;\n'+STRAND_LIFE_GLSL+'''
void main(){float front=strandRemaining(uAge,vec4(5,4.4,1,0));
float fade=strandLifeCoverage(front,vNdc.x*0.5+0.5);FragColor=vec4(fade);}
'''
        program=resources.program('fade',FOG_FULLSCREEN_VERTEX,shader);vao,_=resources.mesh('quad',bytes(36),(3,))
        images=[]
        for age in (.2,.6+4.4/3,.6+4.4/3+1/60,.6+8.8/3,5.):
            target.bind();gl.glDisable(gl.GL_DEPTH_TEST);gl.glDisable(gl.GL_BLEND)
            gl.glUseProgram(program);gl.glBindVertexArray(vao)
            gl.glUniform1f(gl.glGetUniformLocation(program,'uAge'),age);gl.glDrawArrays(gl.GL_TRIANGLES,0,3)
            images.append(target.read_rgba()[4,:,0].astype(float))
        assert images[0].min()==255 and images[1][10]>images[1][90]+40 and 40<images[1][90]<160
        assert np.abs(images[2]-images[1]).max()<=4.
        assert 10<images[3][10]<200 and images[3][90]<15 and images[4].max()==0
    finally:resources.release_resources();target.close()


@pytest.mark.qt
def test_repeat_pulse_temporarily_extends_actual_strands_and_adds_glow(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive,RibbonStrays,RibbonMaterial
    from tests.test_ribbon_gpu import parallel_mvp
    p=packet();target=OffscreenRenderTarget(360,200);primitive=RibbonPrimitive()
    births=np.zeros((1,256,COHORT_ROWS,4),np.float32)
    births[0,100,0]=[1.,0.,1.,0.]
    births[0,100,1]=[8.,1.,2.,4.];births[0,100,2]=[5.,.3,.2,1.];births[0,100,3]=[30.,12.,1.,0.]
    projection=np.asarray(parallel_mvp((6.,10/3),.1,100.)).reshape(4,4,order='F')
    matrix=projection@np.array(((1,0,0,0),(0,1,0,-2),(0,0,1,-5),(0,0,0,1)))
    view=tuple(np.identity(4).flatten(order='F'))
    images=[]
    try:
        with target.current():
            previous=1.3*(1.-np.exp(-.15/.025))*np.exp(-.15/.35)
            for now,growth,glow,pulse_time,seed in ((1.07,0.,0.,1.,0.),(1.07,.2,0.,1.,0.),
                    (1.07,.2,2.,1.,0.),(3.,.2,2.,1.,0.),(3.,0.,0.,1.,0.),
                    (1.15,.2,2.,1.,0.),(1.15,.2,2.,1.15,previous)):
                births[0,100,0,2:]=[pulse_time,seed]
                target.bind(clear=(0.,0.,0.,0.));gl.glDisable(gl.GL_DEPTH_TEST)
                primitive.draw(p,tuple(matrix.flatten(order='F')),shading='strays',view=view,now=now,
                    sweep_axis=(1.,0.,0.),material=RibbonMaterial(cross_curve=.3),
                    strays=RibbonStrays(per_knot=8,length=8.,reach=1.,width=2.,light=4.,peel_time=.3,
                        pulse_growth=growth,pulse_glow=glow),strand_births=births.tobytes(),strand_origin=0.)
                images.append(target.read_rgba()[:,:,:3].astype(float))
            def right(image):return np.nonzero(image.max(axis=2)>2)[1].max()
            assert right(images[1])>=right(images[0])+2
            assert images[2].sum()>images[1].sum()*1.1
            assert np.abs(images[3]-images[4]).sum()<.1*np.abs(images[2]-images[0]).sum()
            assert np.max(np.abs(images[5]-images[6]))<=1  # Retrigger keeps the in-flight envelope.
    finally:
        with target.current():primitive.release()
        target.close()
