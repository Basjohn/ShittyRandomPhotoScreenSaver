"""Verified-commit terrain contrast without full-spectrum publication or live capture."""
from dataclasses import asdict
import threading

import pytest

from core.settings.models import SpotifyVisualizerSettings
from widgets.spotify_visualizer.neon_terrain_contrast import NeonTerrainContrast
from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime
from widgets.spotify_visualizer.source_config_applier import apply_engine_vis_mode_kwargs, resolve_mode_source_config


def _read(contrast):
    values = [1.0] * 8
    contrast.apply_to(values)
    return values


def test_contrast_keeps_authored_zeros_headroom_mirror_and_existing_storage():
    contrast = NeonTerrainContrast()
    storage = contrast._values
    bars = [0.0, .2, .5, 1.0, 1.0, .5, .2, 0.0]
    raw = [0.0, .1, .2, .4, .8, 1.2, 2.0, 8.0]
    contrast.publish(raw, bars, mirrored=False)
    linear = _read(contrast)
    assert contrast._values is storage
    assert linear[0] == linear[-1] == 0.0
    assert all(.3 <= value < 1.0 for value in linear[1:-1])
    assert linear[1:7] == sorted(linear[1:7])
    contrast.publish(raw, bars, mirrored=True)
    mirrored = _read(contrast)
    assert contrast._values is storage and mirrored == pytest.approx(mirrored[::-1])
    assert mirrored[1] > mirrored[3]
    targets = [0., .2, .3, .4, .4, .3, .2, 0.]
    previous = targets.copy()
    contrast.apply_to(targets)
    assert targets[0] == targets[-1] == 0.0
    assert all(0 <= a <= b for a,b in zip(targets,previous))
    # Neither input is rewritten or retained as mutable backing storage.
    assert raw == [0.0, .1, .2, .4, .8, 1.2, 2.0, 8.0]
    raw[:] = [0.] * 8
    assert _read(contrast) == mirrored
    # Rejected input cannot partially publish earlier regions of that frame.
    with pytest.raises(ValueError,match='finite'):
        contrast.publish([1.,1.,1.,1.,float('nan'),1.,1.,1.],bars,mirrored=False)
    assert _read(contrast) == mirrored


def test_slot_snapshot_cannot_mix_analysis_and_logical_threads():
    contrast = NeonTerrainContrast()
    entered = threading.Event()
    release = threading.Event()
    read_done = threading.Event()
    values = []
    class SlowBars:
        def __len__(self): return 8
        def __getitem__(self, index):
            if index == 3:
                entered.set()
                assert release.wait(2.)
            return 1.
    producer = threading.Thread(target=lambda: contrast.publish([1.]*8, SlowBars(), mirrored=False))
    def read():
        values.extend(_read(contrast)); read_done.set()
    producer.start()
    try:
        assert entered.wait(2.)
        consumer = threading.Thread(target=read); consumer.start()
        assert not read_done.wait(.03)
        release.set(); producer.join(2.); consumer.join(2.)
        assert read_done.is_set()
        assert values == pytest.approx([.3+.7/1.45]*8)
    finally:
        release.set(); producer.join(2.)


def test_mode_policy_is_dormant_for_other_modes_and_disabled_growth():
    model = asdict(SpotifyVisualizerSettings())
    for mode in ('spectrum','extruded_spectrum','sphere','bubble','devcurve','oscilloscope'):
        assert resolve_mode_source_config(mode,model)['_source_neon_terrain_contrast_enabled'] is False
    assert resolve_mode_source_config('shockwave_grid',model)['_source_neon_terrain_contrast_enabled'] is True
    model['shockwave_grid_terrain_reactivity']=0.
    assert resolve_mode_source_config('shockwave_grid',model)['_source_neon_terrain_contrast_enabled'] is False


@pytest.mark.qt
def test_verified_audio_commit_conditions_live_terrain_and_rejects_stale_source(qt_app, monkeypatch):
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
    engine = _SpotifyBeatEngine(8)
    source = resolve_mode_source_config('shockwave_grid',asdict(SpotifyVisualizerSettings()))
    apply_engine_vis_mode_kwargs(engine,source)
    contrast = engine.get_neon_terrain_contrast()
    assert contrast is not None
    state = engine._audio_worker.make_compute_snapshot()
    state._freq_values=[.1,.2,.3,.5,.9,1.4,2.1,3.]
    state._spectrum_mirrored=False
    bars=[0.,.8,.8,.8,.8,.8,.8,0.]
    assert engine.accept_analysis_frame(bars,1.,activation_id=engine.get_activation_id(),worker_state=state)
    published=_read(contrast)
    assert published[0] == published[-1] == 0.0 and published[1] < published[6]
    # The mode never enables the existing demand-driven full raw tuple copy.
    assert engine._pre_agc_analysis_spectrum_requested is False
    assert engine._pre_agc_analysis_spectrum == ()
    state._freq_values[:]=[100.]*8
    assert _read(contrast)==published
    assert not engine.accept_analysis_frame(bars,2.,activation_id=engine.get_activation_id()+1,worker_state=state)
    assert _read(contrast)==published
    runtime=ShockwaveGridFrameRuntime()
    def grow(now, **kwargs):
        return runtime.advance_terrain_growth(bars,now_ts=now,playing=kwargs.get('playing',True),
            identity=(1,1,1),source_identity=(1,1),attack=.35,release=1.2,
            musical_gain=kwargs.get('gain',1.),contrast=contrast)
    grow(1.); grown=grow(4.).values
    assert grown[0]==grown[-1]==0. and grown[1]<grown[6]
    assert max(grow(5.2,gain=0.).values)<max(grown)
    # Mode switch retires this container; future shared commits do no contrast work.
    apply_engine_vis_mode_kwargs(engine,resolve_mode_source_config('spectrum',asdict(SpotifyVisualizerSettings())))
    assert engine.get_neon_terrain_contrast() is None
    monkeypatch.setattr(engine,'_publish_neon_terrain_contrast',lambda *a: pytest.fail('dormant contrast work'))
    assert engine.accept_analysis_frame(bars,6.,activation_id=engine.get_activation_id())
    engine.deleteLater()


@pytest.mark.qt
def test_real_scale_replay_uses_the_same_contrast_and_preserves_authored_zero_mask(qt_app):
    from dataclasses import replace
    from tests.test_visualizer_replay_real_scale import _frame
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    from tools.visualizer_replay.driver import replay_clip
    frames=tuple(replace(_frame(i,loudness=9.,presence=1.),raw_bars=(0.,)*8+(.9,)*16+(0.,)*8,
                         real=replace(_frame(i,loudness=9.,presence=1.).real,
                                      analysis_spectrum=tuple(.05+.08*i for i in range(32)))) for i in range(150))
    settings=asdict(SpotifyVisualizerSettings())
    settings['shockwave_grid_mirrored']=False
    result=replay_clip(FeatureClip('terrain_contrast',frames),'shockwave_grid',settings=settings)
    growth=result['logical_series'][-1].mode_state.terrain_growth
    # The canonical odd bar count interpolates the two mask boundaries; the
    # wholly silent outer regions remain exact zero through the live seam.
    assert growth[0]==growth[7]==0.
    assert 0 < growth[2] < growth[4] < 1.
