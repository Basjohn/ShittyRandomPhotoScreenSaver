"""Forward-only three-card migration and actual four-card logical/renderer admission."""
from dataclasses import replace
import copy
import numpy as np
import pytest
from core.waveform_ribbon_authoring import admit_ribbons,RIBBON_CAPACITY
from core.waveform_ribbon_dynamics import WaveformDynamics
from tests.test_waveform_ribbon_mode import parameters,frame_for
from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings


def test_three_card_state_migrates_once_preserving_identity_values_and_visible_count():
    values=parameters();original=copy.deepcopy(values['waveform_ribbon_ribbons'][:3])
    values['waveform_ribbon_ribbons']=original;values['waveform_ribbon_count']=3
    migrated=admit_ribbons(original)
    assert migrated[:3]==original and len(migrated)==RIBBON_CAPACITY==4
    assert admit_ribbons(migrated)==migrated
    config=CompiledWaveformSettings(values)
    assert config.controls.count==3 and len(config.controls.cards)==4
    model=WaveformDynamics(config.controls)
    for _ in range(64):snapshot=model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
    paths=np.frombuffer(snapshot.packet.payload,np.float32).reshape(4,-1,4)
    assert (paths[:3,2,3]>0).all() and paths[3,2,3]==0.
    for _ in range(180):snapshot=model.advance(1/90,bands=(.8,.7,.6),intensity=.9,presence=1.,
                                              controls=replace(config.controls,count=4))
    paths=np.frombuffer(snapshot.packet.payload,np.float32).reshape(4,-1,4)
    assert (paths[:,2,3]>.98).all() and snapshot.packet.instances==4
    assert np.ptp(paths[3,4::5,1])>.2


@pytest.mark.qt
def test_fourth_visible_sheet_reaches_native_direct_and_reflected_scene(qt_app):
    from rendering.quick.offscreen_target import OffscreenRenderTarget
    from rendering.quick.visualizer.implementations.waveform_ribbon import QuickWaveformRibbonRenderer
    target=OffscreenRenderTarget(640,360);renderer=QuickWaveformRibbonRenderer()
    try:
        frame=frame_for(target);values=parameters();values['waveform_ribbon_count']=4
        values['waveform_ribbon_ribbons'][3]['quiet']=[[1.,.35,.01],[1.,.6,.03]]
        config=CompiledWaveformSettings(values);model=WaveformDynamics(config.controls)
        for _ in range(64):state=model.advance(1/90,bands=(0.,0.,0.),intensity=0.,presence=0.)
        original=frame.snapshot.logical.mode_state
        paths=np.frombuffer(state.packet.payload,np.float32).reshape(4,-1,4).copy()
        paths[:3,2:4,3]=0.  # Isolate the fourth identity's actual raster contribution.
        paths[:3,7::5,3]=0.;paths[:3,6::5,3]=0.
        visible=replace(state.packet,payload=paths.tobytes())
        frame.snapshot.logical.mode_state=replace(original,packet=visible,scene=config.scene(state))
        target.bind();renderer.render(frame);four=target.read_rgba().astype(float)
        paths[3,2:4,3]=0.
        paths[3,7::5,3]=0.;paths[3,6::5,3]=0.
        hidden=replace(state.packet,payload=paths.tobytes())
        frame.snapshot.logical.mode_state=replace(original,packet=hidden,scene=config.scene(state))
        target.bind();renderer.render(frame);three=target.read_rgba().astype(float)
        # The added orange sheet and its reflected light must alter actual output, not just a count setting.
        assert (np.abs(four[:230,:,:3]-three[:230,:,:3]).max(2)>8.).sum()>100
        assert (np.abs(four[230:,:,:3]-three[230:,:,:3]).max(2)>8.).sum()>100
    finally:renderer.release_resources();target.close()
