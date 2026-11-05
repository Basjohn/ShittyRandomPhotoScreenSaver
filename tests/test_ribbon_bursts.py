"""Event admission and birth geometry, independent of mutable authored presets."""
from dataclasses import replace
from types import SimpleNamespace
import math
import numpy as np
from core.ribbon_bursts import CAPACITY, MAX_BURST, RibbonAccentControls, RibbonBursts
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
    c=controls();c=replace(c,ranges={**c.ranges,'spark_count':(MAX_BURST,MAX_BURST)})
    for index in range(100):assert field.admit(snapshot(base+index*.161),c,1.)
    records=np.frombuffer(field.payload,np.float32).reshape(CAPACITY,16)
    age=base+99*.161-field.origin-records[:,3]
    active=(records[:,7]>0)&(age>=0)&(age<records[:,7])
    # Lifetimes vary per birth below the authored bound; every cohort younger than the shortest life survives intact.
    assert records[records[:,7]>0,7].min()>=.7*8. and records[:,7].max()<=8.
    young=int(.7*8./.161)
    assert active.sum()>=young*MAX_BURST and field.serial==100
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


def waved(now=0.,drive=.4,colours=None,ribbons=1):
    """A travelling sine body: crests and troughs across the whole emitter span."""
    ring=RibbonRing(ribbons,colours=colours)
    for index in range(40):
        x=index-20.
        ring.append(index/6,[(x,2.+1.5*math.sin(x*.6)+3.*owner,0.) for owner in range(ribbons)],[.3]*ribbons,twists=.4)
    return SimpleNamespace(time=now,ready=True,packet=ring.packet(),head_x=0.,travel=0.,
                           drives=(('sparkle',drive),),realized=(('sparkle',1.),))


def admitted(drive,events=40,strength=.5):
    field=RibbonBursts()
    for index in range(events):field.admit(waved(index*.25,drive),controls_with(spark_count=(0.,64.),
        spark_lifetime=(1.5,8.)),strength)
    now=(events-1)*.25
    age=now-field.origin-field.records[:,3]
    alive=(field.records[:,7]>0)&(age>=0)&(age<field.records[:,7])
    return field,alive


def controls_with(**ranges):
    base=controls();return replace(base,ranges={**base.ranges,**ranges})


def test_quiet_passages_hold_few_sparks_and_hot_passages_a_dense_population():
    quiet=admitted(.1)[1].sum();warm=admitted(.5)[1].sum();hot=admitted(1.)[1].sum()
    assert 0<quiet<warm<hot and hot>=8*quiet


def test_births_spread_across_the_whole_span_and_gather_around_crests():
    field,alive=admitted(.8)
    born=field.records[alive]
    occupied=np.histogram(born[:,0],bins=8,range=(-12.,12.))[0]
    assert (occupied>0).all() and occupied.max()<.35*len(born)
    # Crest preference: most births leave the upper half of their ribbon's sine, but troughs are never excluded.
    phase=np.sin(born[:,0]*.6)
    assert (phase>0).mean()>.65 and (phase<-.5).any()


def test_each_birth_takes_the_colour_of_the_ribbon_that_emitted_it():
    colours=((1.,.5,.1,1.),(.1,.9,.8,1.))
    field=RibbonBursts()
    assert field.admit(waved(colours=colours,ribbons=2),controls_with(spark_count=(64.,64.)),.5)
    born=field.records[field.records[:,7]>0]
    owner=(born[:,1]-(2.+1.5*np.sin(born[:,0]*.6))>1.5).astype(int)
    np.testing.assert_allclose(born[:,8:11],np.asarray(colours)[owner,:3],atol=1e-5)
    assert len(set(owner))==2


def test_births_leave_the_rim_outward_with_varied_speed_and_finite_life():
    c=controls_with(spark_drift=(1.,2.),spark_rise=(0.,1.))
    field=RibbonBursts();assert field.admit(waved(drive=.5),c,.5)
    born=field.records[field.records[:,7]>0]
    speed=np.linalg.norm(born[:,4:7],axis=1)
    assert speed.max()<=1.5+1e-6 and speed.min()>=.35*1.5-1e-6 and speed.std()>.05
    assert np.all(born[:,7]<=8.) and np.all(born[:,7]>0.)


def test_every_spark_range_reaches_its_birth_consumer_through_both_handles():
    # Each authored quiet -> peak pair; moving either handle alone must change the admitted births at a mid drive.
    pairs={'spark_count':(16.,48.),'spark_lifetime':(2.,6.),'spark_drift':(.5,1.5),'spark_rise':(.2,.8),
           'spark_size':(1.,3.),'spark_light':(10.,40.),'spark_white':(.1,.5),'spark_glow':(.5,1.5),'spark_span':(16.,30.)}
    measures={'spark_count':len,'spark_lifetime':lambda r:r[:,7].mean(),
              'spark_drift':lambda r:np.linalg.norm(r[:,4:7],axis=1).mean(),
              'spark_rise':lambda r:(r[:,5]/np.linalg.norm(r[:,4:7],axis=1)).mean(),'spark_size':lambda r:r[:,11].mean(),
              'spark_light':lambda r:r[:,12].mean(),'spark_white':lambda r:r[:,13].mean(),'spark_glow':lambda r:r[:,15].mean(),
              'spark_span':lambda r:np.abs(r[:,0]).max()}
    def measure(key,pair):
        field=RibbonBursts();assert field.admit(waved(drive=.5),controls_with(**{key:pair}),.5)
        return measures[key](field.records[field.records[:,7]>0])
    for key,(low,high) in pairs.items():
        reference=measure(key,(low,high))
        assert measure(key,(.5*(low+high),high))>reference,key
        assert measure(key,(low,1.2*high))>reference,key


def test_sparks_off_builds_no_admission_owner_and_publishes_nothing():
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_mode_settings import require_mode_settings
    from core.waveform_ribbon_dynamics import WaveformDynamics
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    values={control.key:require_canonical_default('widgets.spotify_visualizer.'+control.key)
            for control in require_mode_settings('waveform_ribbon').controls}
    values['waveform_ribbon_sparks_enabled']=False
    config=CompiledWaveformSettings(values);model=WaveformDynamics(config.controls)
    assert config.controls.accents is None
    for index in range(240):
        snapshot=model.advance(1/60,bands=(.8,.8,.8),intensity=.8,presence=1.,hit=float(index%15==0),accent=1.)
    assert model._bursts is None and snapshot.particles==b'' and snapshot.particle_serial==0
    assert config.scene(snapshot).sparks is None


def test_authored_glow_draws_a_halo_outside_the_particle_core(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.scene3d.ribbon_bursts import RibbonBurstRenderer
    from rendering.gl_programs.mist import FOG_OFF
    renderer=RibbonBurstRenderer();target=OffscreenRenderTarget(160,120)
    record=np.zeros((CAPACITY,16),np.float32)
    record[0]=(0.,.03,0.,0.,0.,0.,0.,2.,1.,1.,1.,4.,12.,0.,0.,0.)
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
