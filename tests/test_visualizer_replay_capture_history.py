"""Native capture history round-trips and reaches the production waveform replay seam."""
from dataclasses import replace
from pathlib import Path
import struct

import numpy as np
import pytest

from tools.visualizer_replay.engine import ReplayBeatEngine
from widgets.spotify_visualizer.feature_frame import (
    BandEnergy, CaptureHistory, EnergyLanes, FeatureClip, FeatureFrame, RealScaleLanes,
    RecordedOnset, TransientEnergy, canonical_json,
)


def _frame(history=None):
    band = BandEnergy(0.2, 0.3, 0.1, 0.2)
    return FeatureFrame(
        timestamp_us=1_000_000,
        energy=EnergyLanes(band, band, band, TransientEnergy(0, 0, 0, 0, False, "", 0)),
        raw_bars=(0.2,) * 32, waveform=(0.0,) * 64,
        playing=True, visible=True, mode="oscilloscope", schema_version=2,
        real=RealScaleLanes((0.2, 0.3, 0.1, 0.2), (9.0, 1.2), (2.0,) * 32,
                            onsets=(RecordedOnset("kick", 0.8, 4.0, 9.0, 1.2),)),
        capture_history=history,
    )


def test_native_float32_bytes_survive_clip_serialisation_without_clipping():
    # Include native values beyond the old normalized preview clamp and fine sample detail.
    samples = np.linspace(-1.25, 1.5, 4096, dtype=np.float32)
    history = CaptureHistory.from_samples(samples, capture_serial=4)
    frame = _frame(history)
    encoded = FeatureClip("native_music", (frame,)).to_jsonl_bytes()
    restored = FeatureClip.from_jsonl_bytes("native_music", encoded).frames[0]
    assert restored == frame
    assert history.pcm_f32le == samples.astype("<f4").tobytes()
    assert restored.capture_history.pcm_f32le == history.pcm_f32le
    assert history.sample_count == 4096
    assert len(encoded) < 26000


def test_absent_history_preserves_old_schema_bytes():
    source = Path(__file__).parent / "fixtures/visualizer_replay/v1/silence.jsonl"
    original_line = source.read_bytes().splitlines()[0]
    frame = FeatureClip.from_jsonl_bytes("silence", original_line).frames[0]
    assert "capture_history" not in frame.to_dict()
    assert canonical_json(frame.to_dict()) == original_line
    old_v2 = _frame()
    assert "capture_history" not in old_v2.to_dict()
    assert FeatureFrame.from_dict(old_v2.to_dict()) == old_v2


@pytest.mark.parametrize("samples", [(), (0.0,) * 4097, (float("nan"),), (float("inf"),), (True,)])
def test_invalid_native_samples_fail_loudly(samples):
    with pytest.raises((TypeError, ValueError)):
        CaptureHistory.from_samples(samples, capture_serial=0)


def test_invalid_history_encoding_rate_serial_and_schema_fail_loudly():
    history = CaptureHistory.from_samples((0.25,), capture_serial=0)
    for changes in ({"encoding": "unknown"}, {"samples": "@@@"}, {"sample_rate": 0}, {"capture_serial": -1}):
        with pytest.raises(ValueError):
            CaptureHistory.from_dict({**history.to_dict(), **changes})
    with pytest.raises(ValueError):
        CaptureHistory(struct.pack("<f", float("nan")), capture_serial=0)
    with pytest.raises(ValueError):
        replace(_frame(history), real=None, schema_version=1)


def test_replay_publishes_exact_read_only_history_native_tail_and_events(qt_app):
    samples = np.linspace(-1.1, 1.2, 4096, dtype=np.float32)
    history = CaptureHistory.from_samples(samples, capture_serial=1)
    engine = ReplayBeatEngine(32)
    engine.set_waveform_history_demand(True)
    try:
        assert engine.accept_feature_frame(_frame(history))
        replayed = engine.get_waveform_history()
        assert np.array_equal(replayed, samples)
        assert not replayed.flags.writeable
        assert engine.get_waveform() == samples[-256:].tolist()
        assert engine.get_waveform_count() == 256
        onset, = engine.get_onset_events()
        assert (onset.kind, onset.magnitude, onset.loudness, onset.presence) == ("kick", 4.0, 9.0, 1.2)
        assert engine.get_onset_events(onset.serial) == ()
        assert engine.get_musical_level() == (9.0, 1.2)
        assert engine.get_pre_agc_analysis_spectrum() == (2.0,) * 32
    finally:
        engine.force_stop()


def test_held_capture_keeps_identity_new_serial_refreshes_even_equal_samples(qt_app):
    history = CaptureHistory.from_samples(np.zeros(4096, dtype=np.float32), capture_serial=1)
    engine = ReplayBeatEngine(32)
    engine.set_waveform_history_demand(True)
    try:
        assert engine.accept_feature_frame(_frame(history))
        first = engine.get_waveform_history()
        held = FeatureFrame.from_dict(replace(_frame(history), timestamp_us=1_011_111).to_dict())
        assert engine.accept_feature_frame(held)
        assert engine.get_waveform_history() is first
        assert engine.accept_feature_frame(replace(held, timestamp_us=1_022_222,
                                                   capture_history=replace(history, capture_serial=2)))
        assert engine.get_waveform_history() is not first
        assert np.array_equal(engine.get_waveform_history(), first)
        with pytest.raises(ValueError, match="serial"):
            engine.accept_feature_frame(replace(held, timestamp_us=1_033_333))
        with pytest.raises(ValueError, match="serial"):
            engine.accept_feature_frame(replace(held, capture_history=CaptureHistory.from_samples(
                (0.25,), capture_serial=2)))
    finally:
        engine.force_stop()


def test_short_native_startup_does_not_manufacture_valid_waveform_samples(qt_app):
    history = CaptureHistory.from_samples((0.5,) * 16, capture_serial=0)
    engine = ReplayBeatEngine(32)
    try:
        assert engine.accept_feature_frame(_frame(history))
        assert engine.get_waveform_count() == 16
        assert engine.get_waveform()[:16] == [0.5] * 16
        assert engine.get_waveform()[16:] == [0.0] * 240
    finally:
        engine.force_stop()


def test_old_clip_missing_history_warns_once_without_inventing_history(qt_app, monkeypatch):
    from tools.visualizer_replay import engine as module

    warnings = []
    monkeypatch.setattr(module.logger, "warning", lambda message: warnings.append(message))
    engine = ReplayBeatEngine(32)
    engine.set_waveform_history_demand(True)
    try:
        assert engine.accept_feature_frame(_frame())
        assert engine.get_waveform_history() is None
        assert engine.get_waveform_history() is None
        assert len(warnings) == 1 and "cannot validate full Oscilloscope fidelity" in warnings[0]
        # A device's own rate replays as recorded: the Oscilloscope converts its spans at it.
        assert engine.accept_feature_frame(_frame(CaptureHistory.from_samples((0.1,), capture_serial=0,
                                                                              sample_rate=44100)))
        assert engine.get_waveform_history_rate() == 44100
    finally:
        engine.force_stop()


def _music_clip(seconds=3.0):
    """A pulsing two-tone passage whose recorded bars are the recorder's own: all zero (R160 gives
    every non-Spectrum-family analysis zero bars, and the recorder is configured as Sphere)."""
    rate, step = 48000, 528                     # ~91 frames per second, as the recorder writes
    count = int(seconds * rate / step)
    time = np.arange(count * step + 4096, dtype=np.float64) / rate
    pulse = 0.25 + 0.75 * (0.5 + 0.5 * np.sin(time * np.pi * 4.0)) ** 4
    audio = (pulse * (0.6 * np.sin(time * 2 * np.pi * 70.0) + 0.3 * np.sin(time * 2 * np.pi * 900.0))
             ).astype(np.float32)
    frames = []
    for index in range(count):
        end = 4096 + index * step
        history = CaptureHistory.from_samples(audio[end - 4096:end], capture_serial=index + 1,
                                              sample_rate=rate)
        frames.append(replace(_frame(history), timestamp_us=1_000_000 + round(index * step * 1e6 / rate),
                              raw_bars=(0.0,) * 32, mode="sphere", real=replace(_frame().real, onsets=())))
    return FeatureClip("shaped_bars", tuple(frames))


def test_full_history_clip_replays_spectrum_bars_from_its_audio_not_the_recorders(qt_app, monkeypatch):
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.visualizer_replay.driver import replay_clip

    def bars(clip, mode):
        result = replay_clip(clip, mode, settings=frozen_visualizer_settings(mode))
        return np.array([frame["display_bars"] for frame in result["frames"]][30:])

    clip = _music_clip()
    shaped = bars(clip, "spectrum")
    # The mode's own DSP draws the music: bars rise and follow the pulse.
    assert shaped.max() > 0.2
    assert np.abs(np.diff(shaped, axis=0)).mean() > 1e-3
    # Negative control: replaying the recorded bars (the old seam) leaves Spectrum flat.
    monkeypatch.setattr(ReplayBeatEngine, "_replay_shaped_bars", lambda self, rate: None)
    assert bars(clip, "spectrum").max() == 0.0

