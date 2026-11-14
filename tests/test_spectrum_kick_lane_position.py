"""The kick express lane lands where the Bass lane is authored (1B.10 side defect).

In a mirrored layout the kick boost used to land on the first bars and their mirror, the edge bars, wherever the Bass
lane sat (and, for an even bar count, one bar short on the right). It follows the Bass lane's position on the lane
axis now. Driven through the engine's real ``fft_to_bars`` with the transient lane pinned high or off: the bars the
kick lifts are the ones whose output grows.
"""
from __future__ import annotations

import numpy as np
import pytest

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker, _AudioFrame
from widgets.spotify_visualizer.bar_computation import (
    SpectrumShapeConfig,
    kick_lane_bars,
    lane_sample_positions,
)

MIRRORED_LANES = ("Mid", "Vocal", "Low-Mid", "Bass")
LINEAR_LANES = ("Bass", "Low-Mid", "Vocal", "Hi-Mid", "Treble")


def _worker(bars: int, mirrored: bool, notches: list, transient: float) -> SpotifyVisualizerAudioWorker:
    worker = SpotifyVisualizerAudioWorker(bar_count=bars, buffer=TripleBuffer[_AudioFrame]())
    worker._np = np
    worker.set_spectrum_shaping_enabled(True)
    worker._spectrum_shape_nodes = [[0.0, 0.6], [1.0, 0.6]]
    worker._spectrum_mirrored = mirrored
    worker._spectrum_notch_positions = notches
    flat = {label: 0.6 for label in (*MIRRORED_LANES, *LINEAR_LANES)}
    worker._spectrum_shape_config = SpectrumShapeConfig(
        lane_strengths_mirrored=flat, lane_strengths_linear=flat, wave_amplitude=0.5, profile_floor=0.05)
    worker.set_sensitivity_config(recommended=False, sensitivity=1.0)
    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.05)
    worker.set_input_gain(1.0)
    worker.set_agc_strength(0.0)
    worker.set_energy_boost(1.0)
    worker.set_transient_lane_config(kick_lane_gain=1.0, spectrum_lane_transient_mix=1.0, transient_clamp=1.5)
    worker._applied_noise_floor = 0.05
    worker._raw_bass_avg = 0.05
    worker._transient_bus = None          # the transient lane is pinned below, not measured
    worker._transient_bass = transient
    return worker


def _lifted(bars: int, mirrored: bool, notches: list) -> np.ndarray:
    """Per bar: the output with the kick lane on over the output with it off (same input, fresh workers)."""
    fft = np.zeros(2048, dtype="float32")
    fft[2:640] = 1.2
    plain = np.asarray(_worker(bars, mirrored, notches, 0.0)._fft_to_bars(fft))
    kicked = np.asarray(_worker(bars, mirrored, notches, 0.8)._fft_to_bars(fft))
    assert plain.max() > 0.0
    assert plain.max() < 0.95                # nothing pinned: a boost shows as growth
    return kicked / np.maximum(plain, 1e-6)


@pytest.mark.parametrize("bars", (15, 16))
def test_mirrored_kick_follows_a_centre_bass_lane(bars: int) -> None:
    notches = [[0.0, "Bass"], [0.3, "Vocal"], [0.65, "Low-Mid"], [1.0, "Mid"]]
    ratio = _lifted(bars, True, notches)
    centre = ratio[bars // 2 - 1: bars // 2 + 1]
    edges = np.array([ratio[0], ratio[-1]])
    assert centre.min() > 1.05, ratio
    assert edges.max() < 1.01, ratio
    np.testing.assert_allclose(ratio, ratio[::-1], rtol=1e-5)    # the boost is symmetric


@pytest.mark.parametrize("bars", (15, 16))
def test_mirrored_kick_follows_an_edge_bass_lane(bars: int) -> None:
    notches = [[0.0, "Mid"], [0.3, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]]
    ratio = _lifted(bars, True, notches)
    assert min(ratio[0], ratio[-1]) > 1.05, ratio
    assert ratio[bars // 2] < 1.01, ratio
    np.testing.assert_allclose(ratio, ratio[::-1], rtol=1e-5)


def test_linear_kick_still_lifts_the_first_bars() -> None:
    notches = [[0.0, "Bass"], [0.25, "Low-Mid"], [0.5, "Vocal"], [0.75, "Hi-Mid"], [1.0, "Treble"]]
    ratio = _lifted(16, False, notches)
    assert ratio[0] > 1.05 and ratio[-1] < 1.01, ratio


def test_kick_lane_bars_take_the_count_nearest_the_bass_lane() -> None:
    positions = lane_sample_positions(np, 11, True)
    middle = kick_lane_bars(np, positions, [[0.5, "Bass"], [1.0, "Mid"]], 2, True)
    assert len(middle) == 4
    assert all(abs(float(positions[i]) - 0.5) <= 0.21 for i in middle)
    assert kick_lane_bars(np, positions, [[0.0, "Mid"], [1.0, "Vocal"]], 2, True) == []
