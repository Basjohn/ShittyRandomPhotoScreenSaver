"""Signed quiet/loud gain admission and same-identity physical drift transfer."""
from copy import deepcopy
from dataclasses import replace
import pytest

from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleSimulation, ExtrudedBubbleControls, MusicInput,
)


@pytest.mark.parametrize('large', (True,False))
def test_signed_gains_scale_existing_and_forming_drift_without_scaling_stream(large):
    controls=ExtrudedBubbleControls(large_count=(3,3),mid_count=(3,3),sway=0.,collision_scope='off',
        drift_direction='right',drift_large=(0.,0.),drift_small=(0.,0.))
    seed=ExtrudedBubbleSimulation(281)
    music=MusicInput(1/60,True,.5,(),(.5,.3,.2))
    seed.advance(music,controls)
    for bubble in seed._bubbles[::2]: bubble.alpha=0.
    positions={}
    for gain in (-1.,0.,1.,2.):
        sim=deepcopy(seed)
        c=replace(controls,**{'drift_large' if large else 'drift_small':(gain,gain)})
        sim.advance(music,c)
        positions[gain]={b.ident:(b.x,b.y,b.z) for b in sim._bubbles if b.large is large}
    for ident,zero in positions[0.].items():
        delta=tuple(a-b for a,b in zip(positions[1.][ident],zero))
        assert abs(delta[0])+abs(delta[2])>0
        assert delta[1]==pytest.approx(0.)
        for gain in (-1.,2.):
            assert tuple(a-b for a,b in zip(positions[gain][ident],zero))==pytest.approx(
                tuple(gain*d for d in delta))


def test_gain_endpoints_admit_signed_domain_and_default_to_existing_calibration():
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_mode_settings import spec_control
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.extruded_bubble_frame_runtime import controls_from_parameters
    model=SpotifyVisualizerSettings.from_mapping({},apply_preset_overlay=False)
    for suffix in ('large','small','fused'):
        key='extruded_bubble_drift_'+suffix
        assert getattr(model,key)==[1.,1.]
        assert spec_control(key).admit([-9,9],[1,1])==[-1.,2.]
    controls=controls_from_parameters(frozen_visualizer_settings('extruded_bubble'))
    assert controls.drift_large==controls.drift_small==controls.drift_fused==(1.,1.)


def test_signed_gain_at_fused_centre_is_applied_once():
    controls=ExtrudedBubbleControls(large_count=(2,2),mid_count=(0,0),sway=0.,collision_scope='off',
        drift_direction='right',drift_fused=(0.,0.))
    seed=ExtrudedBubbleSimulation(286);music=MusicInput(1/60,True,.5,(),(.5,.3,.2))
    seed.advance(music,controls)
    a,b=seed._bubbles[:2];b.x,b.y,b.z=a.x+a.radius+b.radius,a.y,a.z
    assert seed._fuse(a,b)
    positions={}
    for gain in (-1.,0.,1.,2.):
        sim=deepcopy(seed);sim.advance(music,replace(controls,drift_fused=(gain,gain)))
        c=next(iter(sim._clusters.values()));positions[gain]=(c.x,c.y,c.z)
    delta=tuple(a-b for a,b in zip(positions[1.],positions[0.]))
    assert abs(delta[0])+abs(delta[2])>0
    for gain in (-1.,2.):
        assert tuple(a-b for a,b in zip(positions[gain],positions[0.]))==pytest.approx(tuple(gain*d for d in delta))


def test_musical_gain_rises_and_releases_on_existing_identity_without_pinning():
    controls=ExtrudedBubbleControls(large_count=(1,1),mid_count=(0,0),sway=0.,stream_speed=(0.,0.),
        collision_scope='off',drift_direction='right',drift=(.2,.2),drift_large=(0.,2.))
    sim=ExtrudedBubbleSimulation(287)
    ratios=[]
    for intensity,body in ((.02,.02),(1.,.7),(.02,.02)):
        for _ in range(600):
            sim.advance(MusicInput(1/60,True,intensity,(),(body,body,body)),controls)
        for b in sim._bubbles: b.x=b.y=b.z=0.  # fixture keeps the same ID inside its tank
        baseline=deepcopy(sim);probe=deepcopy(sim)
        music=MusicInput(1/60,True,intensity,(),(body,body,body))
        baseline.advance(music,replace(controls,drift_large=(1.,1.)))
        probe.advance(music,controls)
        ratios.append(probe._bubbles[0].x/baseline._bubbles[0].x)
    assert ratios[0]<.15
    assert ratios[1]>1.8
    assert ratios[2]<.15


def test_master_drift_has_honest_playing_endpoints_and_releases_after_held_loud_input():
    controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0),drift=(.2,.8))
    sim=ExtrudedBubbleSimulation(288)
    observed=[]
    for intensity in (0.,1.,0.):
        for _ in range(900):
            state=sim.advance(MusicInput(1/60,True,intensity,(),(.5,.3,.2)),controls)
        observed.append(state.drift)
    assert observed==pytest.approx((.2,.8,.2),abs=.001)


def test_free_drift_never_changes_bubble_wake_history_or_inertia_and_zero_is_dormant():
    controls=ExtrudedBubbleControls(large_count=(3,3),mid_count=(5,5),wake_trails=1.,
        stream_path=(0.,-1.,0.,0.,1.,0.),emission_geometry='SCENE',collision_scope='off')
    a,b=ExtrudedBubbleSimulation(289),ExtrudedBubbleSimulation(289)
    for _ in range(60):
        music=MusicInput(1/60,True,.6,(),(.6,.4,.2))
        original=a.advance(music,controls)
        extra=b.advance(music,replace(controls,drift_chains=(1.,1.),drift_snow=(1.,1.),drift_specks=(1.,1.)))
        assert original.bubbles==extra.bubbles
        assert original.wakes==extra.wakes
        assert not original.drift_families and not original.drift_steps
    assert original.wakes
    assert {family.family for family in extra.drift_families} == {'chains', 'snow', 'specks'}
    assert extra.drift_steps


def test_resolved_emission_lifts_and_settings_release_tails_always_have_complete_offset_records():
    import math
    import numpy as np
    from core.constants.extruded_bubble_world import SPECKS_FULL, SNOW_FULL
    from rendering.gl_programs.extruded_bubble_scene import speck_amount
    from rendering.gl_programs.scene3d import SCENE3D_DETAIL_TIERS
    controls=ExtrudedBubbleControls(large_count=(0,0),mid_count=(0,0),emission=(0.,.35),
        stream_path=(0.,-1.,0.,0.,1.,0.),drift_snow=(1.,1.),drift_specks=(1.,1.))
    from widgets.spotify_visualizer.extruded_bubble_drift_log import MaterialDriftReference, STEP_INDEX, unpack_steps
    sim=ExtrudedBubbleSimulation(290)
    reference=MaterialDriftReference()
    def offsets(state):
        payload=reference.apply(state.drift_families,state.drift_steps)
        return payload.get('snow',b''),payload.get('specks',b'')
    def covered(state):
        # The published counts cover what every tier draws, and the integrated records exist for each of them.
        last=unpack_steps(state.drift_steps)[-1]
        snow_offsets,speck_offsets=offsets(state)
        for tier in SCENE3D_DETAIL_TIERS.values():
            snow=math.ceil(SNOW_FULL*max(0.,min(1.,state.emission))*tier.particles)
            specks=round(SPECKS_FULL*speck_amount(state.emission)[0]*tier.particles)
            assert last[STEP_INDEX['count_snow']]>=snow and len(snow_offsets)//16>=snow
            assert last[STEP_INDEX['count_specks']]>=specks and len(speck_offsets)//16>=specks
    for i in range(120):
        body=.9 if i%8<4 else .4
        state=sim.advance(MusicInput(1/60,True,1.,(('kick',1.),), (body,body,.7)),controls)
        covered(state)
    assert state.emission>.35  # reproduce authored endpoint overshoot before bounding offsets
    old=np.frombuffer(offsets(state)[1],dtype='f4').reshape(-1,4)[:,:3].copy()
    reduced=replace(controls,emission=(0.,0.))
    state=sim.advance(MusicInput(1/60,True,1.,(),(.5,.5,.5)),reduced)
    families={family.family for family in state.drift_families}
    assert state.emission>0. and {'snow','specks'}<=families
    covered(state)
    packed=np.frombuffer(offsets(state)[1],dtype='f4').reshape(-1,4)
    overlap=min(len(old),len(packed));retained=packed[:overlap,3]>=0.
    assert np.max(np.linalg.norm(packed[:overlap,:3][retained]-old[:overlap][retained],axis=-1))<.15
    for _ in range(120):
        state=sim.advance(MusicInput(1/60,False,0.,(),(0.,)*3),reduced)
        if any(family.family=='specks' for family in state.drift_families):
            covered(state)
