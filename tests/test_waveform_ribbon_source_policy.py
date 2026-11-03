"""Production PCM, bus policy transitions and replay freshness; no prerecorded feature substitutes."""
from dataclasses import replace
import numpy as np
import pytest

from tools.visualizer_replay.driver import deterministic_clock
from tools.visualizer_replay.engine import ReplayBeatEngine
from tools.visualizer_replay.pcm_reanalysis import PcmReanalysis
from widgets.spotify_visualizer.bar_computation import compute_bars_from_samples
from widgets.spotify_visualizer.feature_frame import CaptureHistory
from tests.test_visualizer_replay_capture_history import _frame


def configured(*, dynamic=False, raw=True):
    engine = ReplayBeatEngine(32)
    engine.set_sensitivity_config(True, 1.)
    engine.set_floor_config(dynamic, .1)
    engine.set_input_gain(1.)
    engine.set_energy_boost(.85)
    engine.set_agc_strength(.5)
    engine.set_transient_lane_config(1., .65, 1.)
    engine.set_spectrum_shaping_enabled(False)
    engine.set_notch_positions([[0., "Bass"], [.25, "Mid"], [.75, "High"], [1., "End"]])
    engine.set_raw_musical_signals(raw)
    engine._audio_worker._np = np
    return engine


@pytest.mark.parametrize('block', [128, 256, 512])
def test_actual_pcm_body_and_entire_musical_bus_are_floor_independent(qt_app, block):
    results = []
    for dynamic in (False, True):
        engine = configured(dynamic=dynamic)
        try:
            worker = engine._audio_worker
            rows = []; events = []; serial = 0
            with deterministic_clock() as clock:
                for index in range(180):
                    clock[0] = 100. + index / 90
                    t = (np.arange(block) + index * block) / 44100.
                    envelope = .02 + .35 * (index % 19) / 18
                    pcm = envelope * (np.sin(t*2*np.pi*83) + .3*np.sin(t*2*np.pi*1750))
                    assert compute_bars_from_samples(worker, pcm.astype('float32')) is not None
                    bus = worker._transient_bus
                    rows.append((worker._last_raw_bass, worker._last_raw_mid, worker._last_raw_treble,
                                 *bus.musical_level, bus.musical_intensity))
                    for event in bus.recent_onsets:
                        if event.serial > serial:
                            events.append((event.timestamp,event.kind,event.magnitude,event.loudness,event.presence))
                            serial = event.serial
            assert np.ptp(np.asarray(rows)[:, 0]) > .1
            assert events
            results.append((rows, events))
        finally:
            engine.force_stop()
    assert results[0] == results[1]


def test_policy_changes_clear_musical_domain_but_same_policy_preserves_it(qt_app):
    engine = configured(raw=False)
    try:
        worker = engine._audio_worker
        with deterministic_clock() as clock:
            for policy in (True, False):
                old = worker._transient_bus
                clock[0] = 100.
                old.update(1., .4, .2, loudness=20.)
                epoch = engine._analysis_compute_state_epoch
                engine.set_raw_musical_signals(not policy)
                assert worker._transient_bus is old
                assert engine._analysis_compute_state_epoch == epoch
                engine.set_raw_musical_signals(policy)
                assert worker._transient_bus is not old
                assert worker._transient_bus.musical_level == (0., 0.)
                assert worker._transient_bus.musical_intensity == 0.
                assert not worker._transient_bus.recent_onsets
                assert engine._analysis_compute_state_epoch > epoch
                # Raw Waveform's quieter fixed-scale input must not reuse the default curve's hard zero.
                value=worker._transient_bus._intensity.update(4.,1/90)
                assert (value>0.) is policy
                assert worker.make_compute_snapshot()._raw_musical_signals == policy
    finally:
        engine.force_stop()


def test_live_digital_silence_clears_waveform_raw_support(qt_app):
    engine = configured()
    try:
        worker = engine._audio_worker
        with deterministic_clock() as clock:
            clock[0] = 100.
            assert compute_bars_from_samples(worker, (.2*np.sin(np.arange(256)*2*np.pi*3/256)).astype('float32')) is not None
            assert worker._last_raw_bass > 0.
            clock[0] += 1/90
            assert compute_bars_from_samples(worker, np.zeros(256, dtype='float32')) is not None
            assert (worker._last_raw_bass,worker._last_raw_mid,worker._last_raw_treble) == (0.,0.,0.)
            assert worker._transient_bus.musical_level == (0.,0.)
            assert worker._transient_bus.musical_intensity == 0.
    finally:
        engine.force_stop()


def test_reanalysis_is_fenced_by_current_frame_engine_and_configuration(qt_app):
    first, second = configured(), configured()
    reanalysis = PcmReanalysis()
    frame = _frame(CaptureHistory.from_samples((.2*np.sin(np.arange(256)*2*np.pi*3/256)).astype('float32'),capture_serial=1))
    try:
        with deterministic_clock():
            first.accept_feature_frame(frame);reanalysis.accept(first,frame)
            first.get_musical_level()
            first.set_input_gain(.5)
            with pytest.raises(RuntimeError,match='current PCM'):
                first.get_musical_level()
            reanalysis.accept(first,frame)
            first.get_musical_level()
            next_frame=replace(frame,timestamp_us=2_000_000,capture_history=replace(frame.capture_history,capture_serial=2))
            first.accept_feature_frame(next_frame)
            with pytest.raises(RuntimeError,match='current PCM'):
                first.get_musical_level()
            with pytest.raises(ValueError,match='exact source'):
                reanalysis.accept(first,frame)
            second.accept_feature_frame(frame);reanalysis.accept(second,frame)
            assert second._audio_worker._last_raw_bass > 0.
            second.get_musical_level()
    finally:
        first.force_stop();second.force_stop()
