"""Acceptance bars for deterministic shared visualizer beat analysis."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.beat_engine import (
    _SpotifyBeatEngine,
    _smooth_analysis_bars,
)
from widgets.spotify_visualizer.energy_bands import EnergyBands, extract_energy_bands


class _ImmediateComputeThreadManager:
    def __init__(self) -> None:
        self.categories: list[str] = []

    def submit_compute_task(self, fn, callback=None, category="uncategorized") -> None:
        self.categories.append(category)
        result = SimpleNamespace(success=True, result=fn())
        if callback is not None:
            callback(result)


def _pre_extraction_formula(
    raw_bars,
    previous_bars,
    prior_timestamp,
    current_timestamp,
    *,
    bar_count,
    smoothing_tau,
    segment_hysteresis,
    min_change_threshold,
):
    """Frozen copy of the formula that lived inside the compute job."""
    dt = (
        max(0.0, current_timestamp - prior_timestamp)
        if prior_timestamp >= 0.0
        else 0.0
    )
    if dt > 2.0 or dt <= 0.0:
        return list(raw_bars), True, extract_energy_bands(raw_bars)

    tau_rise = smoothing_tau * 0.35
    tau_decay = smoothing_tau * 1.5
    alpha_rise = max(0.0, min(1.0, 1.0 - math.exp(-dt / tau_rise)))
    alpha_decay = max(0.0, min(1.0, 1.0 - math.exp(-dt / tau_decay)))

    smoothed = []
    for i in range(bar_count):
        cur = previous_bars[i] if i < len(previous_bars) else 0.0
        tgt = raw_bars[i] if i < len(raw_bars) else 0.0
        if abs(tgt - cur) < min_change_threshold:
            smoothed.append(cur)
            continue
        if tgt > cur:
            tgt_adjusted = tgt + segment_hysteresis
        elif tgt < cur:
            tgt_adjusted = tgt - segment_hysteresis
        else:
            tgt_adjusted = tgt
        tgt_adjusted = max(0.0, min(1.0, tgt_adjusted))
        alpha = alpha_rise if tgt_adjusted >= cur else alpha_decay
        nxt = cur + (tgt_adjusted - cur) * alpha
        if abs(nxt) < 1e-3:
            nxt = 0.0
        smoothed.append(nxt)
    return smoothed, False, extract_energy_bands(smoothed)


def _analysis_state(engine: _SpotifyBeatEngine) -> dict:
    return {
        "latest": None if engine._latest_bars is None else list(engine._latest_bars),
        "smoothed": list(engine._smoothed_bars),
        "smooth_ts": engine._last_smooth_ts,
        "energy": engine._energy_bands,
        "waveform": list(engine._waveform),
        "waveform_count": engine._waveform_count,
        "frame_generation": engine._latest_generation_with_frame,
        "waveform_generation": engine._latest_generation_with_waveform,
        "audio_ts": engine._last_audio_ts,
    }


def test_smoothing_helper_matches_frozen_pre_extraction_series():
    frames = [
        (5.0, [0.2, 0.5, 1.0, 0.004]),
        (5.05, [0.6, 0.503, 0.4, 0.02]),
        (5.10, [0.1, 0.9, 0.0, 0.021]),
        (7.11, [0.7, 0.2, 0.3, 0.001]),
    ]
    frozen = [
        [0.2, 0.5, 1.0, 0.004],
        [0.5041395854232892, 0.5, 0.8299187863442741, 0.01616558341693157],
        [0.3895786667980976, 0.8041395854232892, 0.594662795649072, 0.01616558341693157],
        [0.7, 0.2, 0.3, 0.001],
    ]
    previous = [0.0] * 4
    prior_timestamp = -1.0

    for index, (timestamp, raw_bars) in enumerate(frames):
        kwargs = dict(
            bar_count=4,
            smoothing_tau=0.1,
            segment_hysteresis=0.0,
            min_change_threshold=0.008,
        )
        actual = _smooth_analysis_bars(
            raw_bars, previous, prior_timestamp, timestamp, **kwargs
        )
        reference = _pre_extraction_formula(
            raw_bars, previous, prior_timestamp, timestamp, **kwargs
        )
        assert actual[0] == pytest.approx(reference[0])
        assert actual[0] == pytest.approx(frozen[index])
        assert actual[1:] == reference[1:]
        previous = actual[0]
        prior_timestamp = timestamp


def test_live_compute_callback_and_replay_acceptance_publish_same_analysis(monkeypatch):
    from widgets.spotify_visualizer import bar_computation, beat_engine

    raw_bars = [0.8, 0.1, 0.55, 0.004]
    previous = [0.2, 0.5, 0.4, 0.0]
    live = _SpotifyBeatEngine(4)
    replay = _SpotifyBeatEngine(4)
    for engine in (live, replay):
        engine._smoothed_bars = list(previous)
        engine._last_smooth_ts = 9.95
        engine._play_ramp_start_ts = 0.0

    manager = _ImmediateComputeThreadManager()
    live.set_thread_manager(manager)
    monkeypatch.setattr(
        bar_computation,
        "compute_bars_from_samples",
        lambda _state, _samples: list(raw_bars),
    )
    clock = iter((10.0, 10.01, 10.02))
    monkeypatch.setattr(beat_engine, "time", SimpleNamespace(time=lambda: next(clock)))

    live._schedule_compute_bars_task(object())
    assert manager.categories == ["visualizer.audio_analysis"]
    assert replay.accept_analysis_frame(
        raw_bars,
        10.0,
        activation_id=replay.get_activation_id(),
    )

    assert live._latest_bars == replay._latest_bars
    assert live._smoothed_bars == pytest.approx(replay._smoothed_bars)
    assert live._last_smooth_ts == replay._last_smooth_ts == 10.0
    assert live._energy_bands == replay._energy_bands
    assert live._latest_generation_with_frame == replay._latest_generation_with_frame
    assert live._bars_result_buffer.consume_latest() == raw_bars
    assert replay._bars_result_buffer.consume_latest() == raw_bars


def test_acceptance_preserves_reset_and_gap_energy_behavior():
    engine = _SpotifyBeatEngine(4)
    activation = engine.get_activation_id()
    first = [0.2, 0.4, 0.6, 0.8]
    second = [0.9, 0.1, 0.3, 0.7]
    gap = [0.05, 0.15, 0.25, 0.35]

    assert engine.accept_analysis_frame(first, 20.0, activation_id=activation)
    assert engine._smoothed_bars == first
    assert engine._energy_bands == extract_energy_bands(first)

    assert engine.accept_analysis_frame(second, 20.05, activation_id=activation)
    assert engine._smoothed_bars != second
    assert engine._energy_bands == extract_energy_bands(engine._smoothed_bars)

    assert engine.accept_analysis_frame(gap, 22.051, activation_id=activation)
    assert engine._smoothed_bars == gap
    assert engine._energy_bands == extract_energy_bands(gap)

    backwards = [0.3, 0.2, 0.1, 0.0]
    assert engine.accept_analysis_frame(backwards, 22.0, activation_id=activation)
    assert engine._smoothed_bars == backwards


def test_acceptance_commits_waveform_worker_energy_and_current_activation(monkeypatch):
    engine = _SpotifyBeatEngine(3)
    activation = engine.get_activation_id()
    worker_state = object()
    committed = []
    monkeypatch.setattr(
        engine._audio_worker,
        "commit_compute_snapshot",
        lambda state: committed.append(state),
    )
    override = EnergyBands(bass=0.9, mid=0.8, high=0.7, overall=0.6)

    before = _analysis_state(engine)
    assert not engine.accept_analysis_frame(
        [0.1, 0.2, 0.3],
        30.0,
        activation_id=activation + 1,
        waveform=[0.5, -0.5],
        worker_state=worker_state,
        energy_override=override,
    )
    assert _analysis_state(engine) == before
    assert committed == []

    assert engine.accept_analysis_frame(
        [0.1, 0.2, 0.3],
        30.0,
        activation_id=activation,
        waveform=[0.5, -0.5, 0.25],
        waveform_count=2,
        worker_state=worker_state,
        energy_override=override,
    )
    assert committed == [worker_state]
    assert engine.get_waveform()[:4] == [0.5, -0.5, 0.25, 0.0]
    assert len(engine.get_waveform()) == 256
    assert engine.get_waveform_count() == 2
    assert engine._energy_bands == override
    assert engine.get_latest_generation_with_frame() == engine.get_generation_id()
    assert engine.get_latest_generation_with_waveform() == engine.get_generation_id()
    assert engine._last_audio_ts == 30.0

    engine.reset_smoothing_state()
    assert not engine.accept_analysis_frame(
        [0.4, 0.5, 0.6], 31.0, activation_id=activation
    )


@pytest.mark.parametrize(
    "raw_bars,timestamp,kwargs",
    [
        ((0.1, 0.2), 1.0, {}),
        ([0.1], 1.0, {}),
        ([0.1, float("nan")], 1.0, {}),
        ([-0.1, 0.2], 1.0, {}),
        ([0.1, 1.2], 1.0, {}),
        ([0.1, 0.2], float("inf"), {}),
        ([0.1, 0.2], -1.0, {}),
        ([0.1, 0.2], 1.0, {"waveform": "bad"}),
        ([0.1, 0.2], 1.0, {"waveform_count": 1}),
        ([0.1, 0.2], 1.0, {"waveform": [0.2], "waveform_count": 2}),
        ([0.1, 0.2], 1.0, {"energy_override": object()}),
    ],
)
def test_invalid_acceptance_input_is_rejected_without_mutation(raw_bars, timestamp, kwargs):
    engine = _SpotifyBeatEngine(2)
    before = _analysis_state(engine)

    assert not engine.accept_analysis_frame(
        raw_bars,
        timestamp,
        activation_id=engine.get_activation_id(),
        **kwargs,
    )
    assert _analysis_state(engine) == before
    assert engine._bars_result_buffer.consume_latest() is None


def test_boolean_activation_id_is_rejected_without_mutation():
    engine = _SpotifyBeatEngine(2)
    before = _analysis_state(engine)

    assert not engine.accept_analysis_frame([0.1, 0.2], 1.0, activation_id=False)
    assert _analysis_state(engine) == before


def test_replay_acceptance_is_deterministic_for_identical_timestamped_frames():
    frames = [
        (40.0, [0.1, 0.6, 0.3], [0.2, -0.2]),
        (40.016, [0.8, 0.61, 0.1], [0.4, -0.4, 0.1]),
        (40.250, [0.2, 0.2, 0.9], None),
    ]
    engines = [_SpotifyBeatEngine(3), _SpotifyBeatEngine(3)]

    for engine in engines:
        activation = engine.get_activation_id()
        for timestamp, bars, waveform in frames:
            assert engine.accept_analysis_frame(
                bars,
                timestamp,
                activation_id=activation,
                waveform=waveform,
            )

    assert _analysis_state(engines[0]) == _analysis_state(engines[1])