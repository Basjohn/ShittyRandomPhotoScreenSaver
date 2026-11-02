"""Lab fixture/head-state contracts; independent test-owned ranges, no authored recipe pins or GL."""
from types import SimpleNamespace

import numpy as np
import pytest

from tools.labs.waveform_ribbon_reactivity import CANDIDATES, HeadHistory, PRE_ROLL, signal
from tools.labs.waveform_ribbon_reactivity import Signal


def recipe():
    return SimpleNamespace(
        flow=SimpleNamespace(knot_hz=6., shape_tau=.45, head_hz=.33, phase=4.2, phase_swell=.35,
                             amplitude_swell=.3, depth_sway=1., speed=1.6,head_x=6.4),
        shaping=SimpleNamespace(characters=((1.,1.,1.,0.,1.),(.85,1.1,.96,1.1,1.5),(.72,.75,1.07,.55,.65)),
            ranges=dict(width=(.4,.78), amplitude=(.5,1.2), twist=(.85,1.85), spread=(.32,1.25),
                        lift=(-.35,.2), deformation=(.15,.3), width_swell=(.08,.28))),
        ribbon_colours={'low':(((0.,.5,1.),(0.,.2,1.)),)*3})


@pytest.mark.parametrize('candidate', CANDIDATES)
def test_render_delivery_partitions_do_not_change_logical_knots(candidate):
    expected = HeadHistory(candidate, recipe())
    expected.advance(PRE_ROLL+10)
    payload = expected.ring.packet().payload
    for hz in (30,60,144):
        model = HeadHistory(candidate, recipe())
        model.advance(PRE_ROLL)
        for index in range(1,10*hz+1):
            model.advance(PRE_ROLL+index/hz)
        assert model.ring.packet().payload == payload
    model = HeadHistory(candidate, recipe())
    for t in (PRE_ROLL,.0+PRE_ROLL,PRE_ROLL+.013,PRE_ROLL+.9,PRE_ROLL+2.11,PRE_ROLL+2.12,
              PRE_ROLL+6.731,PRE_ROLL+8.4,PRE_ROLL+10):
        model.advance(t)
    assert model.ring.packet().payload == payload


@pytest.mark.parametrize('candidate', CANDIDATES)
def test_events_consume_once_and_silence_cannot_reemit(candidate):
    model = HeadHistory(candidate, recipe(), trace=True)
    model.advance(PRE_ROLL+10)
    assert len(model.event_log) == len({(event['epoch'],event['sequence']) for event in model.event_log}) == 6
    before = model.ring.packet().payload
    count = len(model.cost_ns)
    model.advance(PRE_ROLL+10)
    assert model.ring.packet().payload == before and len(model.cost_ns) == count
    model.advance(PRE_ROLL+18)
    assert len(model.event_log) == 6 and not model.packets
    assert max(abs(value) for value in model.spring) < .001
    assert all(signal(t) == signal(-1) for t in (0.,.9,8.,10.,30.))


@pytest.mark.parametrize('candidate', CANDIDATES)
def test_head_target_band_differentials_are_not_a_loudness_only_response(candidate):
    baseline = HeadHistory(candidate, recipe(), fixture='band_baseline', trace=True)
    baseline.advance(PRE_ROLL+6)
    for band,target in (('bass','width'),('mids','twist'),('highs','deformation')):
        model = HeadHistory(candidate, recipe(), fixture=band, trace=True)
        model.advance(PRE_ROLL+6)
        delta = np.array([row['targets'][target] for row in model.trace])-np.array(
            [row['targets'][target] for row in baseline.trace])
        assert delta.max() > .01
        assert not model.event_log
        # Preserve broad bounds rather than freezing any recipe or response coefficients.
        for row in model.trace:
            for key,value in row['targets'].items():
                lo,hi=recipe().shaping.ranges[key]
                assert min(lo,hi)-1e-9 <= value <= max(lo,hi)+1e-9
    loudness_only = HeadHistory(candidate, recipe(), fixture='loudness', trace=True)
    loudness_only.advance(PRE_ROLL+6)
    assert np.ptp([row['targets']['width'] for row in loudness_only.trace]) < 1e-8


def test_four_distinct_bounded_histories_and_backwards_time_rejected():
    payloads = set()
    for candidate in CANDIDATES:
        model=HeadHistory(candidate,recipe(),trace=True)
        model.advance(PRE_ROLL+12)
        payloads.add(model.ring.packet().payload)
        for row in model.records:
            assert np.isfinite(row['positions']).all() and np.isfinite(row['twists']).all()
            assert 0 < min(row['widths']) <= max(row['widths']) < 1.5
        with pytest.raises(ValueError,match='backwards'):
            model.advance(PRE_ROLL)
    assert len(payloads)==4


def test_current_body_envelope_changes_existing_body_before_another_head_knot_is_admitted():
    class Input:
        events=()
        def sample(self,t):
            return Signal(bass=.8,loudness=1.) if t>0 else Signal()
    model=HeadHistory('A',recipe(),input_source=Input(),body_envelope=True)
    model.advance(PRE_ROLL)
    stored=model.ring.packet().payload
    quiet=model.snapshot().packet()
    model.advance(PRE_ROLL+.1)  # 100ms of logical state, less than the 166.7ms knot interval
    assert model.ring.packet().payload==stored
    active=model.snapshot().packet()
    assert active.payload!=quiet.payload
    assert model.body_level>.4
    a=np.frombuffer(active.payload,np.float32).reshape(3,-1,4)[:,4::5,1]+active.world_origin[1]
    b=np.frombuffer(quiet.payload,np.float32).reshape(3,-1,4)[:,4::5,1]+quiet.world_origin[1]
    assert np.mean(np.abs(a-b))>.05


def test_low_high_projection_changes_all_history_without_rewriting_it():
    model=HeadHistory('B',recipe(),body_envelope=True)
    model.advance(PRE_ROLL+10)
    original=model.ring.packet().payload
    low,high=(model.snapshot(body_level=value).packet() for value in (0.,1.))
    before=np.frombuffer(original,np.float32).reshape(3,-1,4)
    lo=np.frombuffer(low.payload,np.float32).reshape(3,-1,4)
    hi=np.frombuffer(high.payload,np.float32).reshape(3,-1,4)
    assert np.min(hi[:,4::5,3]/lo[:,4::5,3])>1.5
    low_y=lo[:,4::5,1]+low.world_origin[1]
    high_y=hi[:,4::5,1]+high.world_origin[1]
    assert np.percentile(np.abs(high_y-low_y),25)>.01
    assert np.isfinite(hi).all() and np.isfinite(lo).all()
    assert model.ring.packet().payload==original


def test_actual_motion_profiles_are_not_scaled_copies_of_one_oscillator():
    class Music:
        events=((0.,'bass',.9),(1.,'onset',.8),(2.,'bass',1.))
        def sample(self,t):
            return Signal(bass=.6,mids=.5,highs=.3,loudness=.8,rms=.5+.2*np.sin(5*t)) if t>=0 else Signal()
    profiles={}
    for candidate in CANDIDATES:
        model=HeadHistory(candidate,recipe(),input_source=Music(),body_envelope=True)
        model.advance(PRE_ROLL+3)
        packet=model.snapshot().packet()
        data=np.frombuffer(packet.payload,np.float32).reshape(3,-1,4)
        x=data[0,4::5,0]+packet.world_origin[0]+6.4-1.6*(PRE_ROLL+3)
        profiles[candidate]=data[0,4::5,1][np.abs(x)<5.5]+packet.world_origin[1]
    for i,left in enumerate(CANDIDATES):
        for right in CANDIDATES[i+1:]:
            assert abs(np.corrcoef(profiles[left],profiles[right])[0,1])<.995


def test_traveling_packet_geometry_moves_with_flow_instead_of_pulsing_whole_body():
    class Music:
        events=((0.,'bass',1.),)
        def sample(self,t):return Signal(bass=.4,loudness=.6)
    class Control(Music):events=()
    centres=[]
    for t in (.5,1.5):
        event=HeadHistory('B',recipe(),input_source=Music(),body_envelope=True)
        idle=HeadHistory('B',recipe(),input_source=Control(),body_envelope=True)
        event.advance(PRE_ROLL+t);idle.advance(PRE_ROLL+t)
        a,b=event.snapshot().packet(),idle.snapshot().packet()
        aa=np.frombuffer(a.payload,np.float32).reshape(3,-1,4)
        bb=np.frombuffer(b.payload,np.float32).reshape(3,-1,4)
        x=aa[0,4::5,0]+a.world_origin[0]+6.4-1.6*(PRE_ROLL+t)
        weight=np.abs(aa[0,4::5,1]-bb[0,4::5,1])
        centres.append(float((x*weight).sum()/weight.sum()))
    assert centres[0]-centres[1]==pytest.approx(1.6,abs=.4)


def test_pcm_envelope_detail_is_written_into_d_history_not_a_shared_body_pulse():
    class Audio:
        events=()
        def sample(self,t):return Signal(loudness=.6,rms=.9 if 0<t<1 else .2)
    class Control(Audio):
        def sample(self,t):return Signal(loudness=.6,rms=.2)
    actual=HeadHistory('D',recipe(),input_source=Audio(),body_envelope=True)
    idle=HeadHistory('D',recipe(),input_source=Control(),body_envelope=True)
    actual.advance(PRE_ROLL+2);idle.advance(PRE_ROLL+2)
    a,b=actual.snapshot().packet(),idle.snapshot().packet()
    aa=np.frombuffer(a.payload,np.float32).reshape(3,-1,4)
    bb=np.frombuffer(b.payload,np.float32).reshape(3,-1,4)
    assert np.max(np.abs(aa[:,4::5,1]-bb[:,4::5,1]))>.02
    assert actual.body_level==idle.body_level


def test_travel_packet_fades_before_it_is_retired_inside_the_view():
    class Event:
        events=((0.,'bass',1.),)
        def sample(self,t):return Signal(bass=.4,loudness=.6)
    class Control(Event):events=()
    residuals=[]
    for t in (5.9,5.999,6.01):
        active=HeadHistory('B',recipe(),input_source=Event(),body_envelope=True)
        idle=HeadHistory('B',recipe(),input_source=Control(),body_envelope=True)
        active.advance(PRE_ROLL+t);idle.advance(PRE_ROLL+t)
        a=np.frombuffer(active.snapshot().packet().payload,np.float32).reshape(3,-1,4)[:,4::5,1]
        b=np.frombuffer(idle.snapshot().packet().payload,np.float32).reshape(3,-1,4)[:,4::5,1]
        residuals.append(float(np.max(np.abs(a-b))))
    assert residuals[0]<.005 and residuals[1]<.0001 and residuals[2]<1e-6
