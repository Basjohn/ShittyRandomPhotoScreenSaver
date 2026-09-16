from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor






def _make_spectrum_soak_worker(np_module, bar_count: int = 15):
    from utils.lockfree import TripleBuffer
    from widgets.spotify_visualizer.bar_computation import SpectrumShapeConfig
    from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker, _AudioFrame

    worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=TripleBuffer())
    worker._np = np_module  # type: ignore[attr-defined]
    worker._spectrum_shape_nodes = [[0.0, 0.9], [0.5, 0.9], [1.0, 0.9]]
    worker._spectrum_mirrored = False
    worker._spectrum_notch_positions = [
        [0.0, "Bass"],
        [0.25, "Low-Mid"],
        [0.50, "Vocal"],
        [0.75, "Hi-Mid"],
        [1.0, "Treble"],
    ]
    _lane_strengths = {
        "Bass": 0.7,
        "Low-Mid": 0.6,
        "Vocal": 0.55,
        "Hi-Mid": 0.55,
        "Treble": 0.50,
    }
    worker._spectrum_shape_config = SpectrumShapeConfig(
        lane_strengths_linear=dict(_lane_strengths),
        lane_strengths_mirrored=dict(_lane_strengths),
        wave_amplitude=0.9,
        profile_floor=0.05,
    )
    worker._use_recommended = False
    worker._user_sensitivity = 1.0
    worker._use_dynamic_floor = False
    worker._manual_floor = 0.12
    worker._applied_noise_floor = 0.12
    worker._raw_bass_avg = 0.12
    # The current bar_computation pipeline fails closed (zero bars) until the
    # transient express-lane clamp and energy/gain resolution are present.
    worker.set_transient_lane_config(1.0, 0.65, 1.5)
    worker.set_energy_boost(1.0)
    worker.set_agc_strength(0.5)
    worker.set_input_gain(1.0)
    return worker


def _make_lane_fft(np_module, low: float, mid: float, high: float, size: int = 2048):
    fft = np_module.zeros(size, dtype="float32")
    fft[2:24] = low
    fft[48:180] = mid
    fft[260:640] = high
    return fft
























































def test_spectrum_lane_isolation_survives_long_run():
    import numpy as np

    worker = _make_spectrum_soak_worker(np)

    def _tail_lane_mean(sequence, lane_slice: slice) -> float:
        tail = sequence[-8:]
        totals = []
        for bars in tail:
            totals.append(sum(bars[lane_slice]) / max(1, len(bars[lane_slice])))
        return sum(totals) / len(totals)

    phases = {
        "vocal": [_make_lane_fft(np, low=0.0, mid=12.0, high=10.0) for _ in range(28)],
        "bass": [_make_lane_fft(np, low=10.0, mid=0.0, high=2.0) for _ in range(28)],
        "treble": [_make_lane_fft(np, low=1.0, mid=2.0, high=12.0) for _ in range(28)],
    }

    vocal_bars = [worker._fft_to_bars(fft) for fft in phases["vocal"]]
    bass_bars = [worker._fft_to_bars(fft) for fft in phases["bass"]]
    treble_bars = [worker._fft_to_bars(fft) for fft in phases["treble"]]

    vocal_lane = _tail_lane_mean(vocal_bars, slice(5, 10))
    vocal_bass_lane = _tail_lane_mean(vocal_bars, slice(0, 4))
    bass_lane = _tail_lane_mean(bass_bars, slice(0, 4))
    bass_vocal_lane = _tail_lane_mean(bass_bars, slice(5, 10))
    treble_lane = _tail_lane_mean(treble_bars, slice(11, 15))
    treble_bass_lane = _tail_lane_mean(treble_bars, slice(0, 4))
    treble_vocal_lane = _tail_lane_mean(treble_bars, slice(5, 10))

    assert vocal_bass_lane < vocal_lane * 0.55
    assert bass_vocal_lane < bass_lane * 0.70
    assert treble_bass_lane < treble_lane * 0.70
    assert treble_vocal_lane < treble_lane * 0.85
