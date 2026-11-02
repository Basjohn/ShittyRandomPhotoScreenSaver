"""Event admission and birth geometry, independent of mutable authored presets."""
from dataclasses import replace
from types import SimpleNamespace
import math
import numpy as np
from core.ribbon_bursts import CAPACITY, RibbonAccentControls, RibbonBursts
from core.ribbon_ring import RibbonRing


def controls():
    return RibbonAccentControls({key:(value,value) for key,value in dict(spark_count=36.,spark_lifetime=8.,
        spark_drift=1.,spark_rise=.4,spark_size=5.,spark_light=12.,spark_white=.2,spark_glow=1.,spark_span=24.).items()})


def snapshot(now=0.):
    ring=RibbonRing(1)
    for index in range(10):ring.append(index/6,[(index-5,2.,0.)],[.5],twists=.7)
    return SimpleNamespace(time=now,ready=True,packet=ring.packet(),head_x=0.,travel=0.,
                           drives=(('sparkle',.4),),realized=(('sparkle',1.),))


def test_sparks_are_born_on_the_actual_rolled_rim_and_silence_cannot_respawn_them():
    field=RibbonBursts();s=snapshot()
    assert field.admit(s,controls(),1.)
    records=np.frombuffer(field.payload,np.float32).reshape(CAPACITY,16)
    born=records[records[:,7]>0]
    assert len(born)==36
    # Independent straight-sheet cross-section; the rim has zero camber and uses the shader's floor map.
    side=np.sign(born[:,2]);raw_y=2.+side*.5*math.cos(.7)
    np.testing.assert_allclose(born[:,2],side*.5*math.sin(.7),atol=1e-6)
    np.testing.assert_allclose(born[:,1],.03+.15*np.logaddexp(0.,(raw_y-.03)/.15),atol=1e-6)
    payload=field.payload
    assert not field.admit(snapshot(.01),controls(),1.)
    assert not field.admit(snapshot(1.),controls(),0.)
    assert field.serial==1 and field.payload is payload
    assert field.visible_payload(8.)==b''


def test_capacity_admission_and_epoch_rebase_preserve_living_births_without_truncation():
    field=RibbonBursts();base=1_000_000_000.
    for index in range(100):assert field.admit(snapshot(base+index*.161),controls(),1.)
    records=np.frombuffer(field.payload,np.float32).reshape(CAPACITY,16)
    age=base+99*.161-field.origin-records[:,3]
    active=(records[:,7]>0)&(age>=0)&(age<records[:,7])
    assert active.sum()==50*36 and field.serial==100
    assert age[active].max()<8. and np.isfinite(records).all()


def test_both_count_handles_reach_event_owned_population():
    baseline=controls()
    def population(pair):
        field=RibbonBursts();ranges={**baseline.ranges,'spark_count':pair}
        assert field.admit(snapshot(),replace(baseline,ranges=ranges),.75)
        return np.count_nonzero(field.records[:,7])
    reference=population((8.,24.))
    assert population((16.,24.))>reference
    assert population((8.,36.))>reference


def test_fixed_world_births_cover_the_authored_span_including_continued_rims():
    field=RibbonBursts()
    assert field.admit(snapshot(),controls(),1.)
    born=field.records[field.records[:,7]>0]
    assert born[:,0].min() < -10. and born[:,0].max() > 10.
    assert np.all(np.abs(born[:,0])<=12.)
    assert np.all(born[:,15]==1.)


def test_admitted_accent_uses_count_and_light_ranges_once():
    baseline=controls();ranges={**baseline.ranges,'spark_count':(8.,24.),'spark_light':(8.,24.)}
    for strength in (.1,.9):
        field=RibbonBursts()
        assert field.admit(snapshot(),replace(baseline,ranges=ranges),strength)
        born=field.records[field.records[:,7]>0]
        assert len(born)==15  # ceil(8+(24-8)*.4), independent of event confidence
        np.testing.assert_allclose(born[:,12],14.4,rtol=1e-6)
    field=RibbonBursts();off=snapshot();off.realized=(('sparkle',0.),)
    assert not field.admit(off,baseline,1.)


def test_particle_admission_range_controls_cohort_frequency_continuously():
    populations=[]
    for admission in (0.,.05,.3,.7,1.):
        field=RibbonBursts()
        for index in range(200):
            s=snapshot(index*.161);s.realized=(('sparkle',admission),)
            field.admit(s,controls(),.8)
        populations.append(field.serial)
        assert abs(field.serial-200*admission)<=1
    assert all(a<b for a,b in zip(populations,populations[1:]))


def test_authored_glow_draws_a_halo_outside_the_particle_core(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon_bursts import RibbonBurstRenderer
    from rendering.gl_programs.mist import FOG_OFF
    renderer=RibbonBurstRenderer();target=OffscreenRenderTarget(160,120)
    record=np.zeros((CAPACITY,16),np.float32)
    record[0]=(0.,.03,0.,0.,0.,0.,0.,2.,1.,1.,1.,4.,1.,0.,0.,0.)
    images=[]
    try:
        with target.current():
            for glow in (0.,1.):
                record[0,15]=glow;target.bind(clear=(0.,0.,0.,0.))
                gl.glDisable(gl.GL_DEPTH_TEST)
                renderer.draw(record.tobytes(),mvp=tuple(np.identity(4).flatten(order='F')),now=.2,
                    viewport=(160,120),mist=FOG_OFF,grade={})
                images.append(target.read_rgba()[:,:,:3].astype(float))
            core,halo=images
            assert np.count_nonzero(halo.max(axis=2)>2) > 4*np.count_nonzero(core.max(axis=2)>2)
            assert halo[58:62,78:82].max() >= core[58:62,78:82].max()
    finally:
        with target.current():renderer.release()
        target.close()
