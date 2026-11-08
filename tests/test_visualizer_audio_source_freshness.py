"""R-171: every new capture publication reaches the next logical tick; a hot swap is a clean start.

The live failure: 128-sample WASAPI callbacks arrive 3-4 per 10 ms burst. The capture TripleBuffer
judged freshness by slot index, so exactly three publishes between two ticks wrapped back to the
last-read slot and the tick saw "no new audio" (~23% of Spectrum ticks; the bars held, then jumped).
"""
from __future__ import annotations

from dataclasses import asdict, replace

import numpy as np
import pytest

from utils.lockfree import TripleBuffer


@pytest.mark.parametrize("publishes", range(1, 8))
def test_triple_buffer_reports_every_new_publication_whatever_the_count(publishes):
    buffer = TripleBuffer()
    for round_index in range(4):
        values = [(round_index, index) for index in range(publishes)]
        for value in values:
            buffer.publish(value)
        assert buffer.has_pending()
        assert buffer.consume_latest() == values[-1]
        assert not buffer.has_pending()
        assert buffer.consume_latest() is None


def _burst_schedule(seconds=2.0, block=128, rate=48000, period_s=0.010, tick_hz=90.0):
    """WASAPI-shaped delivery as measured on the operator's device: each 10 ms period's frames
    arrive back to back in callbacks of ``block`` (3 or 4 per burst at 128), against 90 Hz ticks."""
    publishes, carried, t = [], 0, 0.0
    while t < seconds:
        carried += int(round(period_s * rate))
        burst = carried // block
        carried -= burst * block
        publishes.extend(t + 1e-5 * index for index in range(burst))
        t += period_s
    ticks = np.arange(1.0 / tick_hz, seconds, 1.0 / tick_hz)
    return publishes, ticks


def test_engine_tick_consumes_the_newest_small_block_after_every_burst(qt_app):
    from widgets.spotify_visualizer.audio_worker import _AudioFrame
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    publishes, ticks = _burst_schedule()
    engine = _SpotifyBeatEngine(32)
    try:
        engine.set_playback_state(True)
        cursor, fresh_ticks, analysed = 0, 0, 0
        samples = np.zeros(128, dtype=np.float32)
        for tick in ticks:
            newest = None
            while cursor < len(publishes) and publishes[cursor] < tick:
                newest = 1000.0 + publishes[cursor]
                engine._audio_worker._buffer.publish(_AudioFrame(
                    samples=samples, activation_id=engine.get_activation_id(), capture_ts=newest))
                cursor += 1
            engine.tick()
            if newest is not None:
                fresh_ticks += 1
                analysed += engine._last_audio_ts == newest
        assert fresh_ticks > 150
        # Every tick that had new capture audio analyses the newest block (the slot-index
        # buffer missed every tick whose window held exactly three callbacks).
        assert analysed == fresh_ticks
    finally:
        engine.deleteLater()


def _music_clip(seconds):
    from widgets.spotify_visualizer.feature_frame import (
        BandEnergy, CaptureHistory, EnergyLanes, FeatureClip, FeatureFrame, RealScaleLanes,
        TransientEnergy,
    )

    rate, step = 48000, 533                      # ~90 frames per second
    count = int(seconds * rate / step)
    time = np.arange(count * step + 4096, dtype=np.float64) / rate
    rng = np.random.default_rng(171)
    pulse = 0.25 + 0.75 * (0.5 + 0.5 * np.sin(time * np.pi * 4.0)) ** 4
    audio = (pulse * (0.5 * np.sin(time * 2 * np.pi * 70.0) + 0.25 * np.sin(time * 2 * np.pi * 900.0)
                      + 0.15 * np.sin(time * 2 * np.pi * 4200.0))
             + 0.03 * rng.standard_normal(time.size)).astype(np.float32)
    band = BandEnergy(0.2, 0.3, 0.1, 0.2)
    base = FeatureFrame(
        timestamp_us=1_000_000,
        energy=EnergyLanes(band, band, band, TransientEnergy(0, 0, 0, 0, False, "", 0)),
        raw_bars=(0.0,) * 32, waveform=(0.0,) * 64, playing=True, visible=True, mode="spectrum",
        schema_version=2, real=RealScaleLanes((0.2, 0.3, 0.1, 0.2), (9.0, 1.2), (2.0,) * 32, onsets=()),
    )
    frames = []
    for index in range(count):
        end = 4096 + index * step
        history = CaptureHistory.from_samples(audio[end - 4096:end], capture_serial=index + 1, sample_rate=rate)
        frames.append(replace(base, timestamp_us=1_000_000 + round(index * step * 1e6 / rate),
                              capture_history=history))
    return FeatureClip("hot_swap_music", tuple(frames))


def _model(mode):
    from core.settings.models import SpotifyVisualizerSettings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    return SpotifyVisualizerSettings.from_mapping(
        frozen_visualizer_settings(mode), apply_preset_overlay=False, resolve_preset_indices=False)


def _production_hot_swap(controller, engine, target):
    """The production owner's activation commit (``logical_edges``, the one the owner itself runs), minus its Qt
    presentation, then render admission for the committed identity."""
    from widgets.spotify_visualizer.logical_edges import commit_logical_activation
    from widgets.spotify_visualizer.technical_config import build_technical_cache

    model = _model(target)
    generation, activation_id = commit_logical_activation(
        controller, kind="mode", target=target, settings_model=model, resolved_activation=None,
        technical_cache=build_technical_cache(None, model), logical_kwargs=asdict(model),
        presentation_kwargs=asdict(model))
    controller.begin_render_activation(engine_generation=generation, activation_id=activation_id)


def _spectrum_series(clip, *, warm_mode, warm_frames):
    from tools.visualizer_replay.pcm_reanalysis import reanalyzed_bubble_bands
    from widgets.spotify_visualizer.feature_replay import (
        ReplayBeatEngine, configure_offline_controller, deterministic_clock,
    )
    from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
    from widgets.spotify_visualizer.tick_pipeline import logical_tick
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    bars = []
    with reanalyzed_bubble_bands(), deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(
            runtime_generation=0, initial_mode=warm_mode or "spectrum", engine_factory=lambda _count: engine)
        controller.engine = engine
        try:
            frames = clip.frames
            if warm_mode:
                configure_offline_controller(controller, warm_mode, settings=frozen_visualizer_settings(warm_mode))
                for feature in frames[:warm_frames]:
                    clock[0] = feature.timestamp_us / 1e6
                    engine.set_playback_state(True)
                    assert engine.accept_feature_frame(feature)
                    logical_tick(controller.logical_tick_state)
                _production_hot_swap(controller, engine, "spectrum")
            else:
                configure_offline_controller(controller, "spectrum", settings=frozen_visualizer_settings("spectrum"))
            for feature in frames[warm_frames:]:
                clock[0] = feature.timestamp_us / 1e6
                engine.set_playback_state(True)
                assert engine.accept_feature_frame(feature)
                logical = logical_tick(controller.logical_tick_state)
                bars.append(tuple(logical.common.bars) if logical is not None else ())
        finally:
            controller.close_render_admission()
            engine.deleteLater()
    return bars


def test_spectrum_after_a_long_waveform_hot_swap_moves_exactly_like_a_fresh_start(qt_app):
    warm = 900                                    # ~10 s of Waveform Ribbon before the swap
    clip = _music_clip(seconds=14.0)
    fresh = _spectrum_series(clip, warm_mode=None, warm_frames=warm)
    swapped = _spectrum_series(clip, warm_mode="waveform_ribbon", warm_frames=warm)
    assert len(fresh) == len(swapped) > 300
    # The first ~1 s legitimately differs: the cold start is a play edge with its resume ramp, the
    # warm swap is not. Worker/engine DSP state is identical at both boundaries; motion after the
    # edge must be too.
    settle = 150
    fresh_bars = np.asarray(fresh[settle:], dtype=float)
    swap_bars = np.asarray(swapped[settle:], dtype=float)
    assert fresh_bars.shape == swap_bars.shape and fresh_bars.max() > 0.2
    # The swap inherits nothing from Waveform: same bars, same per-tick motion.
    assert np.max(np.abs(fresh_bars - swap_bars)) < 1e-6
    np.testing.assert_allclose(np.abs(np.diff(swap_bars, axis=0)).mean(),
                               np.abs(np.diff(fresh_bars, axis=0)).mean(), rtol=1e-6)
