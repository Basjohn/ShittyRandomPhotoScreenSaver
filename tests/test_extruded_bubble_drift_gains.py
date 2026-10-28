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
