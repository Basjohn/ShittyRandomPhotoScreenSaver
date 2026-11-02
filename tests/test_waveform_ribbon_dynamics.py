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
                          .045,.65,True,.045,1.2,(.02,1.5),.5)


def primed(c=None):
    model = WaveformDynamics(c or controls())
    for _ in range(64):model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    assert model.ready and model.time==0.
    return model


def data(snapshot):
    return np.frombuffer(snapshot.packet.payload,np.float32).reshape(3,-1,4)


def test_visible_body_changes_before_another_head_knot_and_snapshots_do_not_reintegrate():
    model = primed()
    before = model.snapshot()
    raw = model.ring.packet().payload
    active = model.advance(.1,bands=(.8,.7,.6),intensity=.9,presence=1.,hit=1.)
    assert model.ring.packet().payload==raw
    assert np.max(np.abs(data(active)[:,4::5,1:]-data(before)[:,4::5,1:]))>.03
    assert model.snapshot() is active
    assert model.snapshot().packet.payload==active.packet.payload


def test_axial_roll_keeps_the_axis_and_history_motion_and_rotates_the_width_basis():
    c = controls()
    a = primed(c)
    b = primed(replace(c,rotation_enabled=False))
    for _ in range(90):
        sa = a.advance(1/90,bands=(.6,.5,.3),intensity=.8,presence=1.,hit=1.)
        sb = b.advance(1/90,bands=(.6,.5,.3),intensity=.8,presence=1.,hit=1.)
    aa,bb = data(sa),data(sb)
    np.testing.assert_array_equal(aa[:,4::5,0],bb[:,4::5,0])
    np.testing.assert_allclose(np.sum(aa[:,4::5,1:3]**2,axis=2),np.sum(bb[:,4::5,1:3]**2,axis=2),atol=2e-6)
    np.testing.assert_allclose(aa[:,5::5,1]-bb[:,5::5,1],sa.rotation_angle,atol=1e-6)
    assert sa.travel==sb.travel and abs(sa.rotation_angle)>.5


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
    for key in ('height','width','bend','torsion','twist','stretch','lift','spread','depth'):
        baseline = controls()
        models = [primed(baseline)]
        for endpoint in (0,1):
            ranges = dict(baseline.ranges)
            pair = list(ranges[key]);pair[endpoint]+=.1;ranges[key]=tuple(pair)
            models.append(primed(replace(baseline,ranges=ranges)))
        for _ in range(90):
            for model in models:model.advance(1/90,bands=(.4,.4,.4),intensity=.4,presence=1.)
        reference = data(models[0].snapshot())
        for model in models[1:]:
            assert np.max(np.abs(data(model.snapshot())-reference))>.001,key


def test_runtime_consumes_onsets_once_fences_sources_and_is_terminal_after_retirement():
    runtime = WaveformRibbonFrameRuntime()
    c = controls()
    args = dict(onsets=(),playing=True,identity=(1,2,3),source_identity=(2,3),controls=c,
                body_bands=(.5,.4,.3),intensity=.6,loudness=.8,presence=1.)
    for i in range(65):runtime.advance(now_ts=i/90,**args)
    onset = SimpleNamespace(serial=10,strength=1.,loudness=.8,presence=1.)
    args['onsets'] = (onset,)
    first = runtime.advance(now_ts=65/90,**args)
    again = runtime.advance(now_ts=65/90,**args)
    assert again.packet.payload==first.packet.payload and runtime.onset_serial==10
    args['source_identity']=(9,9)
    silent = runtime.advance(now_ts=66/90,**args)
    assert all(value==0. for _key,value in silent.drives)
    runtime.retire()
    assert runtime.advance(now_ts=67/90,**args) is None


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
    model.ring = RibbonRing(3)
    model._primed = model.ring.capacity
    for index in range(330):
        model.ring.append(index/6,[(index/6,2.,0.)]*3,[.5]*3,[-.4]*3)
        if index in (2,329):
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
