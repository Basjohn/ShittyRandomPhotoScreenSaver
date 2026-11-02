"""Held root cohorts: live thresholds cannot re-admit or erase a living strand."""
from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pytest
from core.ribbon_ring import RibbonRing
from core.ribbon_strand_cohorts import RibbonStrandControls,RibbonStrandCohorts


def packet():
    ring=RibbonRing(1)
    for index in range(256):ring.append(index/6,[(index/6-20.,2.,0.)],[.4])
    return ring.packet()


def controls(**overrides):
    ranges=dict(strand_count=(4.,4.),strand_chance=(.6,.6),strand_span=(32.,32.),
                strand_length=(4.,4.),strand_reach=(1.,1.),strand_width=(2.,2.),strand_light=(4.,4.),
                strand_beads=(5.,5.),strand_peel=(.3,.3),strand_halo=(.2,.2),strand_glow=(1.,1.))
    return RibbonStrandControls({**ranges,**overrides})


def snapshot(p,now,*,sparkle=.6):
    return SimpleNamespace(packet=p,time=now,head_x=0.,travel=0.,drives=(('sparkle',.5),),realized=(('sparkle',sparkle),))


def test_living_admission_survives_reactive_threshold_changes_and_has_no_timer_expiry():
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
    assert cohorts.update(snapshot(p,1000.),controls(),0.,history=p,knot_hz=6.)==payload


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
    cohorts.update(snapshot(p,1.),controls(),1.,history=p,knot_hz=6.)
    before=cohorts.records.copy();live=before[:,:,0,0]>0
    cohorts.update(snapshot(p,2.),controls(strand_length=(12.,12.),strand_light=(0.,0.)),.5,history=p,knot_hz=6.)
    after=cohorts.records
    np.testing.assert_array_equal(after[:,:,0,:2][live],before[:,:,0,:2][live])
    np.testing.assert_array_equal(after[:,:,1:][live],before[:,:,1:][live])
    assert np.all(after[:,:,0,2][live]==2.)
    assert np.all(after[:,:,0,3][live]==0.)
    cohorts.update(snapshot(p,2.15),controls(),.5,history=p,knot_hz=6.)
    assert np.all(cohorts.records[:,:,0,3][live]>.8)


def test_rejected_lifetime_setting_is_removed_at_settings_admission():
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping
    values=normalize_visualizer_section_mapping({'waveform_ribbon_strand_lifetime':[2.,8.]},apply_preset_overlay=False)
    assert 'waveform_ribbon_strand_lifetime' not in values


@pytest.mark.qt
def test_actual_strand_shader_holds_visibility_and_smoothly_grows_without_timer_death(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive,RibbonStrays,RibbonMaterial
    from core.settings.framed_camera import orthographic_matrix
    target=OffscreenRenderTarget(240,160);primitive=RibbonPrimitive();p=packet()
    births=np.zeros((1,256,3,4),np.float32);births[:,:,0,0]=1.;births[:,:,0,2]=2.
    births[:,:,1]=[4.,1.,2.,4.];births[:,:,2]=[5.,.3,.2,1.]
    view=tuple(np.identity(4).flatten(order='F'));mvp=orthographic_matrix((6.,4.),.1,100.)
    # Put the test sheet in front of the eye without changing its stable knot IDs.
    mvp=np.asarray(mvp).reshape(4,4,order='F');mvp=mvp@np.array(((1,0,0,0),(0,1,0,-2),(0,0,1,-5),(0,0,0,1)))
    images=[]
    try:
        with target.current():
            for now,chance in ((1.,0.),(1.,1.),(.001,1.),(10.,1.)):
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
            assert primitive.strand_stream.has_resources
            primitive.release_strands()
            assert primitive.strand_stream is None and primitive.strand_resources is None
    finally:
        with target.current():primitive.release()
        target.close()


@pytest.mark.qt
def test_repeat_pulse_temporarily_extends_actual_strands_and_adds_glow(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon import RibbonPrimitive,RibbonStrays,RibbonMaterial
    from core.settings.framed_camera import orthographic_matrix
    p=packet();target=OffscreenRenderTarget(360,200);primitive=RibbonPrimitive()
    births=np.zeros((1,256,3,4),np.float32)
    births[0,100,0]=[1.,0.,1.,0.]
    births[0,100,1]=[8.,1.,2.,4.];births[0,100,2]=[5.,.3,.2,1.]
    projection=np.asarray(orthographic_matrix((6.,10/3),.1,100.)).reshape(4,4,order='F')
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
