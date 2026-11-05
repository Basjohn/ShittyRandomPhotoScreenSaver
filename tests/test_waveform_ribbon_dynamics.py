"""Independent configurations test selected body motion and immutable logical publication, never preset bytes."""
from dataclasses import replace
import math
from types import SimpleNamespace
import numpy as np
import pytest
from core.waveform_ribbon_authoring import TARGETS, admit_routing, admit_ribbons, admit_palette, route
from core.waveform_ribbon_dynamics import HybridControls, WaveformDynamics
from core.waveform_ribbon_scene import Recipe
from core.ribbon_ring import RibbonRing
from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime


@pytest.fixture(autouse=True)
def _swell_mechanics_on_test_paths(monkeypatch):
    """These tests examine swell mechanics on short test paths near the centre: launch the swell inside them and keep
    the fixed end taper short (production births swells beyond the ~±30 view and tapers the slide over 20 units)."""
    import core.waveform_ribbon_dynamics as dyn
    monkeypatch.setattr(dyn, 'PULSE_ORIGIN', 3.5)
    monkeypatch.setattr(dyn, 'SURGE_TAPER', 2.)


def controls():
    routing = {key:[[0.,1.] for _ in range(6)] for key in TARGETS}
    for key,source in (('height',3),('width',0),('bend',0),('torsion',1),('twist',1),('stretch',0),
                       ('lift',0),('spread',1),('depth',2),('rotation',4),('light',3),('sparkle',2),
                       ('colour',3),('highlights',2)):
        routing[key][source][0] = 1.
    ranges = {key:(.2,1.2) for key in TARGETS}
    ranges.update(height=(.4,1.),width=(.3,.8),lift=(-.2,.2),spread=(.5,1.3),rotation=(0.,120.))
    cards = tuple(dict(band='All',height=1.-i*.1,width=1.,rate=1.+i*.05,phase=i*.9,light=1.,
                       quiet=((.05,.2,.8),(.1,.4,1.)),peak=((1.,.1,.4),(.8,.05,.2))) for i in range(3))
    scene = Recipe(flow=replace(Recipe().flow,head_x=6.4,fade_in=.1,fade_out=.5))
    return HybridControls(scene,ranges,admit_routing(routing),tuple(admit_ribbons(cards)),3,.65,.65,1.,
                          .045,.65,True,.045,1.2,(.02,1.5),.5,idle_motion=0.)


def primed(c=None):
    model = WaveformDynamics(c or controls())
    for _ in range(64):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    assert model.ready and model.time==0.
    return model


def data(snapshot):
    return np.frombuffer(snapshot.packet.payload,np.float32).reshape(4,-1,4)


def test_visible_body_changes_before_another_head_knot_and_snapshots_do_not_reintegrate():
    model = primed()
    before = model.snapshot()
    raw = model.ring.packet().payload
    active = model.advance(.1,bands=(.8,.7,.6),intensity=.9,presence=1.,hit=1.)
    assert model.ring.packet().payload==raw
    assert np.max(np.abs(data(active)[:,4::5,1:]-data(before)[:,4::5,1:]))>.03
    assert model.snapshot() is active
    assert model.snapshot().packet.payload==active.packet.payload


def test_short_audio_pulses_do_not_write_small_amplitude_dents_into_travelling_history():
    c=controls()
    # A fixed crest exposes only the recorded amplitude envelope, independently of the immediate body projection.
    c=replace(c,cards=tuple({**card,'rate':0.,'phase':math.pi/1.4} for card in c.cards),
              scene=replace(c.scene,flow=replace(c.scene.flow,phase_swell=0.,amplitude_swell=0.)))
    smooth=primed(c)
    negative=primed(replace(c,scene=replace(c.scene,flow=replace(c.scene.flow,shape_tau=.0001))))
    for tick in range(60):
        level=float(tick%4<2)
        for model in (smooth,negative):model.advance(.1,bands=(level,)*3,intensity=level,presence=1.,hit=level)
    def recorded_steps(model):
        p=model.ring.packet();path=np.frombuffer(p.payload,np.float32).reshape(4,-1,4)[0]
        start,count,capacity=int(path[1,1]),int(path[0,0]),int(path[1,2])
        y=path[4::5,1][(start+np.arange(count))%capacity][-30:]
        return np.abs(np.diff(y)).max()
    assert recorded_steps(smooth)<.1
    # Unsmoothed admission writes the pulse train as dents several times the smoothed step.
    assert recorded_steps(negative)>max(.3,4*recorded_steps(smooth))


def test_axial_roll_keeps_the_axis_and_history_motion_and_rotates_the_width_basis(monkeypatch):
    # The roll alone: the along-curve surge legitimately moves x with the (rolled) slope; it has its own test.
    monkeypatch.setattr('core.waveform_ribbon_dynamics.PULSE_SURGE',0.)
    c = controls()
    a = primed(c)
    b = primed(replace(c,rotation_enabled=False))
    for _ in range(90):
        sa = a.advance(1/90,bands=(.6,.5,.3),intensity=.8,presence=1.,hit=1.)
        sb = b.advance(1/90,bands=(.6,.5,.3),intensity=.8,presence=1.,hit=1.)
    aa,bb = data(sa),data(sb)
    np.testing.assert_array_equal(aa[:,4::5,0],bb[:,4::5,0])
    np.testing.assert_allclose(aa[:,5::5,1]-bb[:,5::5,1],sa.rotation_angle,atol=1e-6)
    assert sa.travel==sb.travel and abs(sa.rotation_angle)>.5


def test_axial_roll_never_rotates_the_musical_vertical_excursion_out_of_view():
    # The roll turns the carrier like a skewer; the louder passage must not hide its own height in depth.
    # Under the former projection order a quarter turn collapsed the visible excursion to the unscaled depth wave.
    c = replace(controls(),rotation_enabled=False)
    model = primed(c)
    for _ in range(180):model.advance(1/90,bands=(.9,.8,.6),intensity=.95,presence=1.,hit=0.)
    def vertical_extent(angle):
        model.angle=angle;model._snapshot=None
        y=data(model.snapshot())[:3,4::5,1]
        count=int(data(model.snapshot())[0,0,0])
        return float(np.mean([np.ptp(row[:count]) for row in y]))
    level=vertical_extent(0.)
    for angle in (math.pi/4,math.pi/2,math.pi):
        assert vertical_extent(angle)>.8*level


def test_vertical_lift_keeps_the_skewer_axis_at_the_same_world_height_at_every_roll_angle():
    c=controls();model=primed(c)
    for angle in (0.,math.pi/2,math.pi,3*math.pi/2):
        model.angle=angle;model.controls=replace(c,ranges={**c.ranges,'lift':(0.,0.)});model._snapshot=None
        low=data(model.snapshot()).copy()
        model.controls=replace(c,ranges={**c.ranges,'lift':(1.,1.)});model._snapshot=None
        high=data(model.snapshot())
        np.testing.assert_allclose(high[:3,4::5,1]-low[:3,4::5,1],1.,atol=1e-6)
        np.testing.assert_array_equal(high[:,4::5,2],low[:,4::5,2])


def test_stretch_no_longer_scales_the_axis_so_kicks_cannot_burst_sideways():
    # Operator, 5 Nov: horizontal bursts are rejected; only the steady flow (and the along-curve surge) moves x.
    model=primed()
    for _ in range(60):model.advance(1/90,bands=(.8,.5,.3),intensity=.8,presence=1.,hit=1.)
    c=model.controls;model.controls=replace(c,ranges={**c.ranges,'stretch':(0.,0.)});model._snapshot=None
    straight=data(model.snapshot()).copy()
    model.controls=replace(c,ranges={**c.ranges,'stretch':(1.,1.)});model._snapshot=None
    np.testing.assert_array_equal(data(model.snapshot()),straight)


def test_ribbon_card_band_selects_its_own_elastic_body_response():
    c=controls();cards=list(c.cards)
    cards[0]={**cards[0],'band':'Bass'}
    a=primed(replace(c,cards=tuple(cards)))
    cards[0]={**cards[0],'band':'Highs'}
    b=primed(replace(c,cards=tuple(cards)))
    for _ in range(90):
        sa=a.advance(1/90,bands=(.8,0.,0.),intensity=.8,presence=1.)
        sb=b.advance(1/90,bands=(.8,0.,0.),intensity=.8,presence=1.)
    assert np.max(np.abs(data(sa)[0,4::5,1:3]-data(sb)[0,4::5,1:3]))>.05


def test_rotation_attacks_quickly_decays_slowly_and_angle_never_jumps_on_speed_change():
    model = primed()
    for _ in range(12):model.advance(1/90,bands=(1.,1.,1.),intensity=1.,presence=1.,hit=1.)
    fast = model.angular_speed
    before = model.angle
    model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    assert fast>50. and model.angular_speed>fast*.95
    assert abs(math.remainder(model.angle-before,2*math.pi))<=math.radians(120.)/90
    for _ in range(900):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    assert model.angular_speed<.1


def test_independent_low_and_peak_geometry_handles_reach_the_projected_body():
    # 'stretch' is retired from geometry: no time-varying axial scaling (sideways bursts, 5 Nov).
    for key in ('height','width','bend','torsion','twist','lift','spread','depth'):
        baseline = controls()
        models = [primed(baseline)]
        for endpoint in (0,1):
            ranges = dict(baseline.ranges)
            pair = list(ranges[key]);pair[endpoint]+=.1;ranges[key]=tuple(pair)
            models.append(primed(replace(baseline,ranges=ranges)))
        # One beat launches a travelling swell, so Pulse Strength (bend) has a body to act on.
        for tick in range(90):
            for model in models:model.advance(1/90,bands=(.4,.4,.4),intensity=.4,presence=1.,hit=float(tick==20 and key=='bend'))
        reference = data(models[0].snapshot())
        for model in models[1:]:
            assert np.max(np.abs(data(model.snapshot())-reference))>.001,key


def test_runtime_consumes_onsets_once_fences_sources_and_is_terminal_after_retirement():
    runtime = WaveformRibbonFrameRuntime()
    c = controls()
    args = dict(onsets=(),playing=True,identity=(1,2,3),source_identity=(2,3),controls=c,
                body_bands=(.5,.4,.3),intensity=.6,loudness=.8,presence=1.)
    for i in range(65):runtime.advance(now_ts=i/90,**args)
    onset = SimpleNamespace(serial=10,strength=1.,magnitude=2.,kind='kick',loudness=.8,presence=1.)
    args['onsets'] = (onset,)
    first = runtime.advance(now_ts=65/90,**args)
    first_stage = runtime._model._drive_stage['height']
    again = runtime.advance(now_ts=65/90,**args)
    assert again.packet.payload==first.packet.payload and runtime.onset_serial==10
    args['source_identity']=(9,9)
    silent = runtime.advance(now_ts=66/90,**args)
    assert silent.ready and silent.time>first.time
    # Silence adds no energy: the geometry drives are velocity-continuous (two stages), so height may carry on a
    # hair for a tick, but the stage that takes the input does not rise.
    assert runtime._model._drive_stage['height']<=first_stage+1e-12
    runtime.retire()
    assert runtime.advance(now_ts=67/90,**args) is None


def test_first_idle_to_play_and_engine_epoch_preserve_the_ready_world():
    runtime=WaveformRibbonFrameRuntime()
    args=dict(onsets=(),playing=False,identity=(1,2,3),source_identity=(-1,-1),controls=controls(),
              body_bands=(0.,0.,0.),intensity=0.,loudness=0.,presence=0.)
    for i in range(100):idle=runtime.advance(now_ts=i/90,**args)
    model=runtime._model
    args.update(playing=True,source_identity=(2,3),body_bands=(.8,.6,.4),intensity=.6,loudness=8.,presence=1.)
    playing=runtime.advance(now_ts=100/90,**args)
    assert runtime._model is model and playing.ready and playing.time>idle.time
    assert playing.travel>idle.travel and playing.packet.instances==4
    args.update(identity=(1,4,5),source_identity=(-1,-1))
    waiting=runtime.advance(now_ts=101/90,**args)
    assert runtime._model is model and waiting.ready and waiting.time>playing.time


def test_subtle_idle_has_motion_without_events_and_a_fresh_kick_reaches_visible_emission():
    still=primed(controls());idle=primed(replace(controls(),idle_motion=.6))
    for _ in range(90):
        a=still.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
        b=idle.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    delta=np.max(np.abs(data(a)[:,4::5,1:3]-data(b)[:,4::5,1:3]))
    assert .001<delta<.1 and idle._hit==0.
    plain=primed();punched=primed()
    for index in range(18):
        a=plain.advance(1/90,bands=(.4,.4,.4),intensity=.2,presence=1.)
        b=punched.advance(1/90,bands=(.4,.4,.4),intensity=.2,presence=1.,hit=.8 if index==5 else 0.)
    # No new head has reached the visible centre: the already-visible body's emission and deformation change.
    assert np.max(data(b)[:,7::5,3]-data(a)[:,7::5,3])>.2
    assert np.max(np.abs(data(b)[:,4::5,1:3]-data(a)[:,4::5,1:3]))>.01


def test_typed_events_have_distinct_impulses_and_unclipped_magnitude_preserves_headroom():
    def event(kind,magnitude,level=8.5):
        runtime=WaveformRibbonFrameRuntime()
        args=dict(onsets=(),playing=True,identity=(1,2,3),source_identity=(2,3),controls=controls(),
                  body_bands=(.5,.5,.5),intensity=.65,loudness=level,presence=1.)
        for index in range(80):runtime.advance(now_ts=index/90,**args)
        before=np.asarray(runtime._model.velocity).copy()
        args['onsets']=(SimpleNamespace(serial=1,kind=kind,strength=1.,magnitude=magnitude,loudness=level,presence=1.),)
        state=runtime.advance(now_ts=80/90,**args)
        return np.asarray(runtime._model.velocity)-before,runtime._model._hit,state
    kick,_,_=event('kick',2.);snare,_,_=event('snare',2.);vocal,_,_=event('vocal_swell',2.)
    assert kick[0,0]>snare[0,0] and snare[0,1]>kick[0,1] and vocal[0,2]>kick[0,2]
    hits=[event('kick',magnitude)[1] for magnitude in (.2,1.,3.)]
    assert 0.<hits[0]<hits[1]<hits[2]<1.
    _,silent,state=event('kick',3.,level=0.)
    assert silent==0. and not state.particles


def test_fast_band_articulation_does_not_hold_quiet_passages_at_the_peak_handle():
    # Quiet, ordinary and hot passages on the fixed real-music scale: articulation stays ordered, a quiet
    # passage sits well below the peak handle and a hot one keeps headroom instead of pinning.
    values=[]
    for bands,intensity in (((.3,.2,.1),.05),((.55,.45,.35),.6),((.85,.8,.7),.95)):
        model=primed()
        for _ in range(270):snapshot=model.advance(1/90,bands=bands,intensity=intensity,presence=1.)
        values.append(dict(snapshot.drives)['bend'])
    assert 0.<values[0]<.15 and values[0]<values[1]<values[2]<.97
    assert values[2]>4*values[0]


def test_a_steady_beat_keeps_its_force_and_a_bigger_hit_still_lands_bigger():
    # Operator, 5 Nov: kicks felt muted in the middle of a song, never at its start. The body's force of a routine
    # kick 40 s into a steady beat must stay that of the same kick near the start; accents (sparks/strands) may still
    # ask whether an onset stands out from the routine. Before the fix the 40th identical kick earned < 1%.
    runtime=WaveformRibbonFrameRuntime()
    args=dict(onsets=(),playing=True,identity=(1,2,3),source_identity=(2,3),controls=controls(),
              body_bands=(.5,.5,.5),intensity=.65,loudness=8.5,presence=1.)
    for index in range(80):runtime.advance(now_ts=index/90,**args)
    def onset(serial,magnitude):
        args['onsets']=(SimpleNamespace(serial=serial,kind='kick',strength=1.,magnitude=magnitude,loudness=8.5,presence=1.),)
        runtime.advance(now_ts=1.+serial*.5,**args)
        return runtime._model._hit
    near_start=[onset(serial,.4) for serial in range(1,6)][-1]
    for serial in range(6,100):routine=onset(serial,.4)
    assert routine >= .85*near_start > 0.
    assert onset(100,1.5) > routine


def test_supported_quiet_accent_is_admitted_independently_of_its_small_deformation_force():
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
    # Test-owned complete settings (never a curated preset, which the operator retunes) with sparks and
    # strands on, so a quiet accent has both emitters to reach.
    settings={**frozen_visualizer_settings('waveform_ribbon'),
              'waveform_ribbon_sparks_enabled':True,'waveform_ribbon_strands_enabled':True}
    c=CompiledWaveformSettings(settings).controls
    runtime=WaveformRibbonFrameRuntime()
    args=dict(onsets=(),playing=True,identity=(1,2,3),source_identity=(2,3),controls=c,
              body_bands=(.15,.1,.05),intensity=.1,loudness=1.,presence=1.)
    for index in range(90):runtime.advance(now_ts=index/90,**args)
    args['onsets']=(SimpleNamespace(serial=1,kind='kick',strength=1.,magnitude=1.,loudness=1.,presence=1.),)
    state=runtime.advance(now_ts=1.,**args)
    assert 0.<runtime._model._hit<.08  # former admission rejected this real quiet accent
    assert state.particle_serial==1 and state.particles and state.strands
    # Same supported history cannot emit again when the current source is silent or stale.
    args.update(loudness=0.,intensity=0.,source_identity=(-1,-1))
    args['onsets']=(SimpleNamespace(serial=2,kind='kick',strength=1.,magnitude=3.,loudness=0.,presence=1.),)
    assert runtime.advance(now_ts=1.1,**args).particle_serial==1


@pytest.mark.parametrize('frequency',(.3,1.3,3.))
@pytest.mark.parametrize('damping',(.2,.8))
def test_authored_impulse_excursion_survives_spring_timing_changes(frequency,damping):
    c=controls()
    c=replace(c,frequency=frequency,damping=damping,impulse=.75,
              routing=admit_routing({key:[[0.,1.] for _ in range(6)] for key in TARGETS}))
    model=primed(c);peaks=[]
    for index in range(math.ceil(.5/frequency*360)):
        model.advance(1/360,bands=(1.,1.,1.),intensity=.65,presence=1.,
                      hit_components=(.4,0.,0.) if index==0 else (0.,0.,0.))
        peaks.append(model.spring[0][0])
    # A .4 admitted impulse at authored strength .75 requests .3 normalized
    # spring excursion. Timing changes must not erase it at high frequency.
    assert max(peaks)==pytest.approx(.3,rel=.01)


def test_authoring_contracts_reject_ambiguous_or_nonfinite_data():
    with pytest.raises(ValueError):admit_palette({'low':[[.5,[0.,0.,0.]], [.5,[1.,1.,1.]]],'high':[[0.,[0.,0.,0.]]]})
    c = controls()
    bad = dict(c.routing);bad.pop('bend')
    with pytest.raises(ValueError):admit_routing(bad)
    bad = [dict(card) for card in c.cards];bad[0]['rate']=float('nan')
    with pytest.raises(ValueError):admit_ribbons(bad)


def test_noninteger_twist_gain_uses_signed_origin_before_and_after_rebasing():
    c = controls()
    ranges = dict(c.ranges);ranges['twist']=(.5,.5)
    model = WaveformDynamics(replace(c,ranges=ranges,rotation_enabled=False,twist_speed=(0.,0.)))
    model.ring = RibbonRing(4)
    model._primed = model.ring.capacity
    for index in range(330):
        model.ring.append(index/6,[(index/6,2.,0.)]*4,[.5]*4,[-.4]*4)
        if index in (3,329):  # the cloth reducer admits four controls before a complete interval
            model._snapshot = None
            snapshot = data(model.snapshot())
            flags = snapshot[:,5::5,2]>.5
            np.testing.assert_allclose(snapshot[:,5::5,1][flags],-.2,atol=1e-6)


def test_live_flow_speed_change_integrates_travel_without_moving_existing_history():
    model = primed()
    for _ in range(20):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    before = model.snapshot()
    c = replace(model.controls,scene=replace(model.controls.scene,
                flow=replace(model.controls.scene.flow,speed=model.controls.scene.flow.speed*2)))
    after = model.advance(0.,bands=(0.,0.,0.),intensity=0.,presence=0.,controls=c)
    assert after.travel==before.travel
    np.testing.assert_array_equal(data(after)[:,4::5,0],data(before)[:,4::5,0])


@pytest.mark.parametrize('column,value',((2,0.),(3,1.)))
def test_interior_history_break_is_rejected_before_gpu_publication(column,value):
    from core.ribbon_packet import RibbonPacket
    model=primed();raw=model.ring.packet();array=np.frombuffer(raw.payload,np.float32).reshape(4,-1,4).copy()
    array[0,5+5*120,column]=value
    model.ring.packet=lambda:RibbonPacket(array.tobytes(),raw.instances,raw.vertices,raw.world_origin,raw.coordinate_origin)
    model._snapshot=None
    with pytest.raises(ValueError,match='valid monotone'):model.snapshot()


def test_extreme_admitted_carrier_stays_one_valid_run_during_edits():
    c=controls();cards=tuple({**card,'height':2.,'rate':2.,'width':2.} for card in c.cards)
    scene=replace(c.scene,flow=replace(c.scene.flow,speed=.8,head_hz=.6,phase_swell=1.,amplitude_swell=1.))
    model=primed(replace(c,scene=scene,cards=cards))
    for index in range(180):
        edited=tuple({**card,'phase':card['phase']+(math.pi if index%2 else 0.)} for card in cards)
        snapshot=model.advance(.1,bands=(1.,1.,1.),intensity=1.,presence=1.,hit=1.,controls=replace(model.controls,cards=edited))
        assert snapshot.ready


def test_gain_above_one_and_independent_matrix_cells_have_real_effects():
    row = [[0.,1.] for _ in range(6)];row[0][0]=1.
    assert route(row,(.3,0.,0.,0.,0.,0.))==pytest.approx(.3)
    row[0][0]=2.
    assert route(row,(.3,0.,0.,0.,0.,0.))==pytest.approx(.6)
    row[1][0]=.5
    assert route(row,(.3,.2,0.,0.,0.,0.))==pytest.approx(.7)


def test_live_quiet_colour_edits_reach_headers_without_rewriting_history():
    model = primed()
    stored = model.ring.packet().payload
    cards = [dict(card) for card in model.controls.cards]
    cards[0]['quiet']=((.8,.1,.2),(.2,.9,.1))
    snapshot = model.advance(0.,bands=(0.,0.,0.),intensity=0.,presence=0.,
                             controls=replace(model.controls,cards=tuple(cards)))
    np.testing.assert_allclose(data(snapshot)[0,2:4,:3],cards[0]['quiet'])
    assert model.ring.packet().payload==stored


def test_count_transition_changes_actual_geometry_and_returns_to_exact_hidden_state():
    model = primed()
    before = data(model.snapshot()).copy()
    c = replace(model.controls,count=1)
    model.advance(.1,bands=(0.,0.,0.),intensity=0.,presence=0.,controls=c)
    partial = data(model.snapshot())
    assert 0.<partial[2,2,3]<1.
    np.testing.assert_allclose(partial[2,4::5,1:3],before[2,4::5,1:3]*partial[2,2,3],atol=1e-6)
    for _ in range(50):model.advance(.1,bands=(0.,0.,0.),intensity=0.,presence=0.)
    assert data(model.snapshot())[2,2,3]==0.


def test_flow_rule_share_is_the_largest_share_meeting_both_bounds():
    """The owner's flow-rule share (closed form) is the largest share in [0, 1] whose gain keeps |g'|/g and |g''|/g
    within their bounds: it matches a fine bisection of the bound itself, and a share just above it breaks a bound."""
    import core.waveform_ribbon_dynamics as dyn
    model = primed()
    k = 2.*math.pi/dyn.carrier_wavelength(model.controls)
    def excess(share,swell):
        g = 1.+share*swell
        first = np.gradient(g,dyn.PULSE_DX)
        second = np.gradient(first,dyn.PULSE_DX)
        return max(np.abs(first/g).max()/(dyn.GEOM_SLOPE*k),np.abs(second/g).max()/(dyn.GEOM_CURVE*k*k))
    rng = np.random.default_rng(7)
    bound_cases = 0
    for case in range(40):
        centre,width,height = rng.uniform(-30.,30.),rng.uniform(.4,2.5),rng.uniform(.3,1.2)
        model._geom = dyn.soft(height*np.exp(-((dyn.PULSE_GRID-centre)/width)**2))
        model._geom_share = (1.,None)                   # no rate limit: the instantaneous bound alone
        strength = rng.uniform(.4,1.)
        swell = .7*strength*model._geom
        peak = int(np.argmax(swell))
        share = float((model.geometric_gain(strength)[peak]-1.)/swell[peak])
        low,high = 0.,1.
        if excess(1.,swell)>1.:
            bound_cases += 1
            for _ in range(40):
                mid = .5*(low+high)
                low,high = (mid,high) if excess(mid,swell)<=1. else (low,mid)
            assert share == pytest.approx(low,abs=1e-9)
            assert excess(min(1.,share*1.001),swell) > 1.
        else:
            assert share == pytest.approx(1.)
        assert excess(share,swell) <= 1.+1e-9
    assert bound_cases >= 10
