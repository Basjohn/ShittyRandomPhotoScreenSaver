"""Oscilloscope rework contracts, from captured PCM to real offscreen beam pixels.

Signals, colours and timings below are test vectors, never curated-preset assertions.
No capture device, visible window, environment flags or wall-clock sleeps are needed.
"""
from __future__ import annotations

from dataclasses import replace
import math
from types import SimpleNamespace

import numpy as np
import pytest

from rendering.gl_programs import oscilloscope_program as scope
from widgets.spotify_visualizer import oscilloscope_frame_runtime as runtime_module
from widgets.spotify_visualizer.oscilloscope_frame_runtime import OscilloscopeFrameRuntime
from widgets.spotify_visualizer.render_state import OscilloscopeFrame


def _resolve(runtime, samples, **changes):
    """Resolve real PCM with reactions/ghosts disabled unless the test asks for them."""
    values = dict(
        history=samples, waveform=samples, waveform_count=len(samples), now_ts=10.0,
        runtime_generation=2, engine_generation=5, activation_id=7,
        source_generation=5, source_activation_id=7, source_timestamp=9.99,
        playing=True, display="Trace", span_ms=20.0, gain=1.0, delay_ms=1.0,
        afterglow=0.0, detail=1.0, sample_rate=scope.SAMPLE_RATE,
    )
    values.update(changes)
    result = runtime.resolve(**values)
    assert result is not None
    return result


def _points(frame):
    assert frame.trace_alphas == (1.0,)
    return np.frombuffer(frame.points, dtype=np.float32).reshape(-1, 2)


def _sine(count, frequency, *, rate=scope.SAMPLE_RATE, offset=0, amplitude=0.4):
    return (amplitude * np.sin(math.tau * frequency * (np.arange(count) + offset) / rate)).astype(np.float32)


def test_trigger_holds_an_advancing_220_hz_trace_still_at_a_rising_crossing():
    runtime = OscilloscopeFrameRuntime()
    traces = []
    previous = None
    window = round(0.020 * scope.SAMPLE_RATE)
    for frame_index in range(12):
        # 137 samples is deliberately unrelated to the 218.18-sample period.
        history = _sine(4096, 220, offset=137 * frame_index)
        signal = scope.condition(history, 1.0)
        start = scope.trigger_start(signal, window, previous)
        smooth = np.convolve(signal, np.ones(scope.SMOOTH_SAMPLES) / scope.SMOOTH_SAMPLES, mode="same")
        assert 0 < start <= len(signal) - window
        assert smooth[start - 1] < 0.0 <= smooth[start]
        previous = scope.trace_template(signal, start, window)
        traces.append(_points(_resolve(runtime, history, now_ts=10.0 + frame_index / 60.0)))
    traces = np.stack(traces)
    assert np.ptp(traces[0, :, 1]) > 0.7  # A flat output cannot satisfy the stability bar.
    assert np.max(np.abs(traces - traces[0])) < 0.025, "triggered traces drift between callbacks"
    assert np.mean(np.abs(traces - traces[0])) < 0.006


def test_long_trace_preserves_every_bins_low_and_high_including_one_sample_spikes():
    count = scope.TRACE_POINTS * 7 + 17
    signal = np.random.default_rng(104).uniform(-0.3, 0.3, count).astype(np.float32)
    signal[731], signal[1229] = 0.95, -0.91
    points = scope.trace_points("Trace", signal, 0, count)
    edges = np.linspace(0, count, scope.TRACE_POINTS // 2 + 1).astype(int)
    expected = np.array([(signal[a:b].min(), signal[a:b].max()) for a, b in zip(edges[:-1], edges[1:])])
    np.testing.assert_array_equal(np.sort(points[:, 1].reshape(-1, 2), axis=1), expected,
                                  err_msg="envelope discarded a bin extremum")
    assert points[:, 1].max() == signal[731]
    assert points[:, 1].min() == signal[1229]
    assert np.all(np.diff(points[:, 0]) > 0.0)


def test_short_trace_interpolates_instead_of_padding_or_repeating_samples():
    signal = np.array([-0.8, 0.5, -0.2, 0.9], dtype=np.float32)
    points = scope.trace_points("Trace", signal, 0, len(signal))
    positions = np.linspace(0.0, len(signal) - 1, scope.TRACE_POINTS)
    np.testing.assert_allclose(points[:, 1], np.interp(positions, np.arange(len(signal)), signal), atol=4e-7)
    np.testing.assert_allclose(points[:, 0], np.linspace(-1.0, 1.0, scope.TRACE_POINTS), atol=2e-7)
    assert len(np.unique(points[:, 1])) > len(signal) * 10


def test_negative_control_untriggered_runtime_fails_the_stability_bar(monkeypatch):
    """Break the runtime in memory, prove the real regression bar fails, restore exactly."""
    original = runtime_module.trigger_start
    with monkeypatch.context() as patch:
        patch.setattr(runtime_module, "trigger_start", lambda signal, window, previous: len(signal) - window)
        with pytest.raises(AssertionError, match="triggered traces drift between callbacks"):
            test_trigger_holds_an_advancing_220_hz_trace_still_at_a_rising_crossing()
    assert runtime_module.trigger_start is original
    test_trigger_holds_an_advancing_220_hz_trace_still_at_a_rising_crossing()


def test_negative_control_subsampling_fails_the_envelope_bar(monkeypatch):
    """Ordinary interpolation loses the long window's extrema; no source files are edited."""
    original = scope._envelope

    def subsample(segment):
        x = np.linspace(0.0, 1.0, scope.TRACE_POINTS, dtype=np.float32)
        y = np.interp(x * (len(segment) - 1), np.arange(len(segment)), segment).astype(np.float32)
        return x, y

    with monkeypatch.context() as patch:
        patch.setattr(scope, "_envelope", subsample)
        with pytest.raises(AssertionError, match="envelope discarded a bin extremum"):
            test_long_trace_preserves_every_bins_low_and_high_including_one_sample_spikes()
    assert scope._envelope is original
    test_long_trace_preserves_every_bins_low_and_high_including_one_sample_spikes()


@pytest.mark.parametrize("display", ["Trace", "Ring", "Phase"])
def test_zero_audio_draws_the_resting_line_circle_or_dot(display):
    points = _points(_resolve(OscilloscopeFrameRuntime(), np.zeros(4096, np.float32), display=display))
    assert points.shape == (scope.TRACE_POINTS, 2)
    if display == "Trace":
        np.testing.assert_array_equal(points[:, 1], 0.0)
        np.testing.assert_allclose(points[:, 0], np.linspace(-1.0, 1.0, scope.TRACE_POINTS), atol=2e-7)
    elif display == "Ring":
        np.testing.assert_allclose(np.linalg.norm(points, axis=1), scope.RING_RADIUS, atol=1e-7)
        np.testing.assert_allclose(points[0], points[-1], atol=2e-7)
        assert np.all(np.ptp(points, axis=0) > 1.9 * scope.RING_RADIUS)
    else:
        np.testing.assert_array_equal(points, 0.0)


@pytest.mark.parametrize("count", [4, 7, 8, 15])
@pytest.mark.parametrize("display", ["Trace", "Ring", "Phase"])
def test_short_nonzero_inputs_resolve_without_errors(count, display):
    samples = np.linspace(-0.5, 0.6, count, dtype=np.float32)
    points = _points(_resolve(OscilloscopeFrameRuntime(), samples, display=display))
    assert points.shape == (scope.TRACE_POINTS, 2)
    assert np.isfinite(points).all()
    assert np.ptp(points[:, 1]) > 0.01


def test_detail_removes_high_frequency_from_the_drawn_trace_but_keeps_the_low_tone():
    assert scope.smoothing_samples(0.0) > scope.smoothing_samples(1.0) == 1
    rate, window = scope.SAMPLE_RATE, round(0.005 * scope.SAMPLE_RATE)
    samples = _sine(4096, 200, amplitude=0.1) + _sine(4096, 6000, amplitude=0.05)

    def amplitudes(detail):
        points = _points(_resolve(OscilloscopeFrameRuntime(), samples, detail=detail, span_ms=5.0))
        seconds = (points[:, 0].astype(float) + 1.0) * 0.5 * (window - 1) / rate
        # Fit both quadratures: the trigger may choose any phase, never changing a tone's amplitude.
        columns = [np.ones(len(seconds))]
        for frequency in (200, 6000):
            columns += [np.sin(math.tau * frequency * seconds), np.cos(math.tau * frequency * seconds)]
        coefficients = np.linalg.lstsq(np.column_stack(columns), points[:, 1], rcond=None)[0]
        return np.hypot(*coefficients[1:3]), np.hypot(*coefficients[3:5])

    detailed_low, detailed_high = amplitudes(1.0)
    smooth_low, smooth_high = amplitudes(0.0)
    assert detailed_low > 0.08 and detailed_high > 0.03
    assert smooth_low > 0.85 * detailed_low
    assert smooth_high < 0.15 * detailed_high


@pytest.mark.parametrize("frequency,delay", [(100, 32), (30, 1)])
def test_phase_widens_low_tones_without_exceeding_the_stretch_cap(frequency, delay):
    signal = _sine(6000, frequency, amplitude=0.2)
    window = 4800
    points = scope.phase_points(signal, window, delay)
    start = len(signal) - window - delay
    edges = np.linspace(0, window, scope.TRACE_POINTS + 1).astype(int)
    # Independent un-widened X/Y reference, using explicit bin slices.
    a = np.array([signal[start + lo:start + hi].mean() for lo, hi in zip(edges[:-1], edges[1:])])
    b = np.array([signal[start + delay + lo:start + delay + hi].mean() for lo, hi in zip(edges[:-1], edges[1:])])
    raw_x = (a - b) * scope.PHASE_SCALE / math.sqrt(2.0)
    raw_y = (a + b) * scope.PHASE_SCALE / math.sqrt(2.0)
    np.testing.assert_allclose(points[:, 1], raw_y, atol=1e-7)
    stretch = np.linalg.norm(points[:, 0]) / np.linalg.norm(raw_x)
    assert 1.0 < stretch <= scope.PHASE_MAX_STRETCH + 1e-4
    if delay == 32:
        assert 0.85 < np.ptp(points[:, 0]) / np.ptp(points[:, 1]) < 1.15
    else:
        assert stretch == pytest.approx(scope.PHASE_MAX_STRETCH, rel=2e-5)


def test_runtime_span_uses_the_callback_sample_rate(monkeypatch):
    windows = []
    original = runtime_module.trace_points

    def record_window(display, signal, start, window):
        windows.append(window)
        return original(display, signal, start, window)

    monkeypatch.setattr(runtime_module, "trace_points", record_window)
    for rate in (44100, 48000):
        samples = _sine(round(0.085 * rate), 220, rate=rate)
        points = _points(_resolve(OscilloscopeFrameRuntime(), samples, sample_rate=rate, span_ms=20.0))
        assert np.ptp(points[:, 1]) > 0.7
    assert windows == [882, 960]
    assert windows[0] / 44100 == pytest.approx(windows[1] / 48000)


def test_same_history_is_rebuilt_when_source_becomes_ready():
    runtime, history = OscilloscopeFrameRuntime(), _sine(4096, 220)
    waiting = _resolve(runtime, history, source_timestamp=None)
    assert waiting.reactive_source_ready is False
    np.testing.assert_array_equal(_points(waiting)[:, 1], 0.0)
    ready = _resolve(runtime, history, source_timestamp=10.01, now_ts=10.02)
    assert ready.reactive_source_ready is True
    assert ready.changed is True
    assert np.ptp(_points(ready)[:, 1]) > 0.7


def _onset(serial, timestamp):
    from widgets.spotify_visualizer.transient_bus import MusicalOnset, MUSICAL_USUAL_LOUDNESS

    return MusicalOnset(serial=serial, timestamp=timestamp, kind="kick", strength=1.0,
                        magnitude=3.0, loudness=1.8 * MUSICAL_USUAL_LOUDNESS, presence=1.6)


def test_onset_older_than_max_age_flares_nothing_and_is_taken_once():
    runtime, samples = OscilloscopeFrameRuntime(), _sine(1024, 220)
    _resolve(runtime, samples)
    onset = _onset(901, 10.01 - scope.FLARE_MAX_AGE - 0.001)
    stale = _resolve(runtime, samples, now_ts=10.01, onsets=(onset,), intensity=1.0)
    assert stale.flare == 0.0
    assert runtime.onset_serial == onset.serial
    # Even a refreshed timestamp cannot reuse an already-taken serial.
    repeated = _resolve(runtime, samples, now_ts=10.02,
                        onsets=(replace(onset, timestamp=10.02),), intensity=1.0)
    assert repeated.flare == 0.0


@pytest.mark.parametrize("primed", [True, False], ids=["running-clock", "first-frame"])
def test_fresh_flare_rises_over_tens_of_ms_then_decays(primed):
    runtime, samples = OscilloscopeFrameRuntime(), _sine(1024, 220)
    if primed:
        _resolve(runtime, samples)
    onset = _onset(902, 10.005)
    strength = scope.flare_strength(onset.magnitude, onset.loudness, onset.presence, 1.0)
    assert strength > 0.5
    taken = _resolve(runtime, samples, now_ts=onset.timestamp, onsets=(onset,), intensity=1.0)
    assert 0.0 <= taken.flare < 0.4 * strength
    growing = [_resolve(runtime, samples, now_ts=onset.timestamp + step * 0.01, intensity=1.0).flare
               for step in range(1, 5)]
    assert taken.flare < growing[0] < growing[1] < growing[2] < growing[3] < strength
    assert growing[-1] > 0.5 * strength
    decayed = _resolve(runtime, samples, now_ts=onset.timestamp + 0.7, intensity=1.0)
    assert 0.0 < decayed.flare < growing[-1] * 0.3


def test_a_serial_cannot_retrigger_a_fresh_flare():
    repeated, once = OscilloscopeFrameRuntime(), OscilloscopeFrameRuntime()
    samples, onset = _sine(1024, 220), _onset(903, 10.01)
    for runtime in (repeated, once):
        _resolve(runtime, samples)
        _resolve(runtime, samples, now_ts=10.01, onsets=(onset,), intensity=1.0)
    for now in (10.04, 10.10, 10.25, 10.5):
        actual = _resolve(repeated, samples, now_ts=now,
                          onsets=(replace(onset, timestamp=now),), intensity=1.0)
        expected = _resolve(once, samples, now_ts=now, intensity=1.0)
        assert actual.flare == pytest.approx(expected.flare, abs=1e-12)
        assert repeated.onset_serial == onset.serial


@pytest.fixture
def capture_worker(qt_app):
    from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker

    worker = SpotifyVisualizerAudioWorker(4)
    worker._np = np
    worker._running = True  # Admit callbacks directly; never start/open a device or owner lane.
    worker._capture_generation = 11
    worker._activation_id = 23
    worker._backend = SimpleNamespace(sample_rate=48000)
    worker.set_waveform_history_demand(True)
    yield worker
    worker._running = False
    worker._backend = None


def _deliver(worker, samples, **kwargs):
    worker._on_audio_samples(worker._capture_generation, samples, **kwargs)
    frame = worker._buffer.consume_latest()
    assert frame is not None, "the real capture callback did not publish"
    assert worker._capture_callback_failures == 0
    return frame


def test_consecutive_capture_callbacks_keep_one_contiguous_immutable_history(capture_worker):
    worker = capture_worker
    first, second = np.linspace(-0.8, -0.2, 517, dtype=np.float32), np.linspace(0.1, 0.7, 631, dtype=np.float32)
    initial = _deliver(worker, first)
    following = _deliver(worker, second)
    np.testing.assert_array_equal(initial.history, first)
    np.testing.assert_array_equal(following.history, np.concatenate((first, second)))
    assert not initial.history.flags.writeable and not following.history.flags.writeable
    assert not np.shares_memory(initial.history, following.history)


@pytest.mark.parametrize("boundary", ["demand-toggle", "capture-generation", "activation"])
def test_history_starts_afresh_at_a_capture_or_demand_boundary(capture_worker, boundary):
    worker = capture_worker
    _deliver(worker, np.full(512, -0.6, np.float32))
    if boundary == "demand-toggle":
        # No intervening callback: the epoch must remember that demand was dropped.
        worker.set_waveform_history_demand(False)
        worker.set_waveform_history_demand(True)
    elif boundary == "capture-generation":
        worker._capture_generation += 1
    else:
        worker._activation_id += 1
    samples = np.full(257, 0.3, np.float32)
    frame = _deliver(worker, samples)
    np.testing.assert_array_equal(frame.history, samples)


@pytest.mark.parametrize("fence", ["entry", "publication"])
def test_generation_rejected_callback_leaves_no_history_or_published_frame(capture_worker, monkeypatch, fence):
    worker = capture_worker
    seed = np.full(64, -0.2, np.float32)
    _deliver(worker, seed)
    prior, prior_key = worker._history, worker._history_key
    rejected = np.full(128, 0.9, np.float32)
    generation = worker._capture_generation
    with monkeypatch.context() as patch:
        if fence == "entry":
            generation -= 1
        else:
            class RetiringNumpy:
                def __getattr__(self, name):
                    return getattr(np, name)

                def asarray(self, *args, **kwargs):
                    result = np.asarray(*args, **kwargs)
                    # Deterministically retire between the two locks, without sleeps/threads.
                    worker._capture_generation += 1
                    return result

            patch.setattr(worker, "_np", RetiringNumpy())
        worker._on_audio_samples(generation, rejected)
    assert worker._buffer.consume_latest() is None
    assert worker._history is prior and worker._history_key == prior_key
    assert worker._capture_callback_failures == 0
    fresh = np.full(32, 0.1, np.float32)
    following = _deliver(worker, fresh)
    expected = np.concatenate((seed, fresh)) if fence == "entry" else fresh
    np.testing.assert_array_equal(following.history, expected)


def test_oversized_callback_preserves_full_history_and_uses_its_source_backend_rate(capture_worker):
    samples = np.linspace(-0.7, 0.8, 3001, dtype=np.float32)
    frame = _deliver(capture_worker, samples, source=SimpleNamespace(sample_rate=44100))
    np.testing.assert_array_equal(frame.history, samples)
    np.testing.assert_array_equal(frame.samples, samples[-2048:])
    assert len(frame.samples) == 2048
    assert frame.history_rate == 44100  # The callback backend differs from the worker's current one.


def test_capture_history_is_bounded_and_disabled_capture_retains_none(capture_worker):
    from widgets.spotify_visualizer.audio_worker import WAVEFORM_HISTORY_SAMPLES

    samples = np.linspace(-0.9, 0.9, WAVEFORM_HISTORY_SAMPLES + 137, dtype=np.float32)
    _deliver(capture_worker, samples[:2000])
    frame = _deliver(capture_worker, samples[2000:])
    np.testing.assert_array_equal(frame.history, samples[-WAVEFORM_HISTORY_SAMPLES:])
    capture_worker.set_waveform_history_demand(False)
    disabled = _deliver(capture_worker, samples[:100])
    assert disabled.history is None and capture_worker._history is None


def test_engine_drops_history_from_frames_consumed_after_demand_ends(qt_app, monkeypatch):
    from widgets.spotify_visualizer.audio_worker import _AudioFrame
    from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

    engine = _SpotifyBeatEngine(4)
    engine._is_spotify_playing = True
    # History consumption precedes analysis admission. Record admission without opening a lane.
    engine._thread_manager = object()
    scheduled = []
    monkeypatch.setattr(engine, "_schedule_compute_bars_task", lambda samples, **kw: scheduled.append(samples))
    history = _sine(4096, 220)
    engine.set_waveform_history_demand(True)
    engine._audio_buffer.publish(_AudioFrame(samples=history[-512:], history=history, history_rate=44100))
    engine.tick()
    assert engine.get_waveform_history() is history
    assert engine.get_waveform_history_rate() == 44100
    # A packet queued while demanded can still reach tick after demand is switched off.
    engine._audio_buffer.publish(_AudioFrame(samples=history[-256:], history=history, history_rate=44100))
    engine.set_waveform_history_demand(False)
    assert engine.get_waveform_history() is None
    engine.tick()
    assert engine.get_waveform_history() is None
    assert len(scheduled) == 2 and engine._audio_buffer.consume_latest() is None
    assert engine._audio_worker._history_demanded is False


def test_snapshot_restore_never_reinstates_retired_keys():
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_presets import restore_visualizer_snapshot
    from core.settings.visualizer_retired_modes import _RETIRED_VISUALIZER_KEYS

    cfg = require_canonical_default("widgets.spotify_visualizer")
    payload = {"mode": "oscilloscope", "osc_gain": 2.25}
    for key in _RETIRED_VISUALIZER_KEYS:
        payload[key] = 123
        payload[f"widgets.spotify_visualizer.{key}"] = 123
    restore_visualizer_snapshot("oscilloscope", cfg, payload)
    assert cfg["osc_gain"] == 2.25  # Restore still applies a live owned key.
    assert not {key.removeprefix("widgets.spotify_visualizer.") for key in cfg} & _RETIRED_VISUALIZER_KEYS


@pytest.mark.parametrize("count,alphas", [(2, ()), (0, (1.0,)), (5, (0.5, 1.0)), (385, (1.0,))],
                         ids=["points-without-alphas", "alphas-without-points", "uneven-traces", "too-many-points"])
def test_frame_rejects_inconsistent_or_oversized_traces(count, alphas):
    with pytest.raises(ValueError):
        OscilloscopeFrame(points=np.zeros((count, 2), np.float32).tobytes(), trace_alphas=alphas)


def test_frame_accepts_two_complete_384_point_traces():
    frame = OscilloscopeFrame(points=np.zeros((2 * 384, 2), np.float32).tobytes(), trace_alphas=(0.4, 1.0))
    assert frame.trace_points == 384


class _ScopeGlTarget:
    """The existing offscreen capture pattern, with an explicit physical item size."""

    def __init__(self, width, height):
        from tools.transition_contact_sheet import TransitionCapture

        self.width, self.height = width, height
        self.capture = TransitionCapture(width, height)

    def render(self, host, snapshot):
        from OpenGL import GL as gl

        width, height = self.width, self.height
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.capture.fbo)
        gl.glViewport(0, 0, width, height)
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        mode = host.render(snapshot=snapshot, viewport=(0, 0, width, height),
                           logical_size=(float(width), float(height)), matrix_values=matrix)
        assert mode == "oscilloscope"
        pixels = gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
        return np.flipud(np.frombuffer(bytes(pixels), np.uint8).reshape(height, width, 4)).astype(np.int16)

    def close(self):
        self.capture.close()


def _scope_gl_snapshot(width, height):
    """Canonical settings with controlled beam inputs, shared by all real GL checks."""
    from core.settings.default_contract import require_canonical_default
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot

    settings = require_canonical_default("widgets.spotify_visualizer")
    settings["mode"] = "oscilloscope"
    snapshot = _build_spectrum_preview_snapshot(width=width, height=height, mode="oscilloscope", settings=settings)
    presentation = replace(snapshot.presentation, content_fade=1.0, dpr=1.0, uniform_visual_scale=1.0,
                           content_rotation_quarters=0)
    parameters = {**dict(snapshot.logical.mode_state.parameters),
                  "osc_display": "Trace", "osc_glow": 0.0, "osc_graticule": "Off",
                  "osc_beam_color": (32, 224, 64, 255), "osc_beam_glow_color": (32, 224, 64, 255),
                  "osc_graticule_color": (24, 24, 24, 48), "osc_beam_width": 4.0,
                  "osc_analog": 0.0, "osc_spectral": 0.0, "osc_flare": 0.0, "osc_pulse": 0.0}
    state = OscilloscopeFrame(points=scope.flat_points("Trace").tobytes(), trace_alphas=(1.0,), parameters=parameters)
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=state), presentation=presentation)


@pytest.mark.qt
def test_real_gl_flat_beam_grid_glow_determinism_and_resource_release(qt_app):
    from OpenGL import GL as gl
    from rendering.quick.visualizer.implementations.oscilloscope import oscilloscope_layout
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    W, H = 684, 418
    snapshot = _scope_gl_snapshot(W, H)
    x, y, width, height = snapshot.presentation.content_rect
    ox, oy, *_ = snapshot.presentation.outer_rect
    field = (x - ox, y - oy, width, height)
    scale, _ = oscilloscope_layout(field, "Trace")
    # Centre the beam on a pixel row, away from the graticule's horizontal lines.
    row = round(field[1] + height / 2 - 0.37 * scale[1])
    unit_y = (field[1] + height / 2 - (row + 0.5)) / scale[1]
    points = np.column_stack((np.linspace(-1, 1, scope.TRACE_POINTS), np.full(scope.TRACE_POINTS, unit_y))).astype(np.float32)
    state = replace(snapshot.logical.mode_state, points=points.tobytes())
    parameters = dict(state.parameters)
    snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=state))

    def variant(**changes):
        return replace(snapshot, logical=replace(snapshot.logical,
                       mode_state=replace(state, parameters={**parameters, **changes})))

    target, host = _ScopeGlTarget(W, H), QuickVisualizerRenderHost()
    try:
        off = target.render(host, snapshot)
        renderer = host._implementations["oscilloscope"]
        assert not renderer._target._names["emission"]
        assert not renderer._target._bloom.has_resources
        centre_x = field[0] + width / 2
        left, right = math.ceil(centre_x - 0.8 * scale[0]), math.floor(centre_x + 0.8 * scale[0])
        beam = off[row, left:right]
        assert len(beam) > W / 2
        assert np.all(beam[:, 1] > 150)
        assert np.all(beam[:, 1] > 2 * beam[:, 0]) and np.all(beam[:, 1] > 2 * beam[:, 2])
        far = np.abs(np.arange(H) - row) > 5
        assert not off[far].any()
        np.testing.assert_array_equal(target.render(host, snapshot), off)

        grid = target.render(host, variant(osc_graticule="Grid"))
        drawn = off[..., 3] > 0
        np.testing.assert_array_equal(grid[drawn], off[drawn])
        assert np.count_nonzero(np.any(grid[~drawn] != off[~drawn], axis=1)) > 500
        np.testing.assert_array_equal(target.render(host, snapshot), off)

        glowing_snapshot = variant(osc_glow=0.8)
        glowing = target.render(host, glowing_snapshot)
        assert renderer._target._names["emission"]
        assert renderer._target._bloom.has_resources
        assert glowing[..., :3].sum() > off[..., :3].sum()
        np.testing.assert_array_equal(target.render(host, glowing_snapshot), glowing)

        names = dict(renderer._target._names)
        bloom_levels = tuple(renderer._target._bloom._levels)
        programs = tuple(renderer._resources._programs.values())
        stream_buffer = renderer._stream._buffer
        quad_vao, quad_vbo = host._quad_vao, host._quad_vbo
        assert names["fbo"] and names["colour"] and programs and stream_buffer
        assert bloom_levels and quad_vao and quad_vbo
        host.release_resources()
        assert not renderer.has_resources
        assert not any(renderer._target._names.values())
        assert not renderer._target._bloom.has_resources
        assert not renderer._stream.has_resources and not renderer._resources.has_resources
        for key, name in names.items():
            if name:
                is_live = gl.glIsFramebuffer if "fbo" in key else gl.glIsRenderbuffer if key == "depth" else gl.glIsTexture
                assert not is_live(name), f"released {key} still exists on the GPU"
        assert not gl.glIsBuffer(stream_buffer)
        assert all(not gl.glIsProgram(program) for program in programs)
        assert all(not gl.glIsTexture(texture) and not gl.glIsFramebuffer(fbo)
                   for texture, fbo, _width, _height in bloom_levels)
        assert not gl.glIsVertexArray(quad_vao) and not gl.glIsBuffer(quad_vbo)
    finally:
        host.release_resources()
        target.close()


_ROTATION_SIZE = (320, 180)
_ROTATION_CONTENT_RECT = (23.0, 17.0, 267.0, 139.0)


def _rotation_snapshot(quarters, *, diagonal=False):
    snapshot = _scope_gl_snapshot(*_ROTATION_SIZE)
    # An asymmetric inset and a nonzero outer origin also catch rotation about the wrong centre.
    x, y, width, height = _ROTATION_CONTENT_RECT
    item_width, item_height = _ROTATION_SIZE
    presentation = replace(snapshot.presentation, outer_rect=(31.0, 47.0, *_ROTATION_SIZE),
                           content_rect=(31.0 + x, 47.0 + y, width, height),
                           current_aspect_ratio=(item_height / item_width if quarters % 2 else item_width / item_height),
                           content_rotation_quarters=quarters)
    unit_x = np.linspace(-1.0, 1.0, scope.TRACE_POINTS, dtype=np.float32)
    # Off-centre but flat: clockwise and counterclockwise must land on different rows/columns.
    unit_y = unit_x if diagonal else np.full_like(unit_x, 0.25)
    points = np.column_stack((unit_x, unit_y))
    state = replace(snapshot.logical.mode_state, points=points.tobytes())
    return replace(snapshot, logical=replace(snapshot.logical, mode_state=state), presentation=presentation)


def _expected_rotated_segment(quarters, *, diagonal=False):
    """Independent quarter-turn oracle; only the unrotated beam layout is shared with production."""
    from rendering.quick.visualizer.implementations.oscilloscope import oscilloscope_layout

    width, height = _ROTATION_SIZE
    x, y, cw, ch = _ROTATION_CONTENT_RECT
    logical_rect = (
        (x, y, cw, ch),
        (y, width - x - cw, ch, cw),
        (width - x - cw, height - y - ch, cw, ch),
        (height - y - ch, x, ch, cw),
    )[quarters]
    lx, ly, lw, lh = logical_rect
    scale, _ = oscilloscope_layout(logical_rect, "Trace")
    endpoints = np.array([[-1.0, -1.0], [1.0, 1.0]] if diagonal else [[-1.0, 0.25], [1.0, 0.25]])
    logical = (lx + lw / 2, ly + lh / 2) + endpoints * (scale[0], -scale[1])
    oriented_w, oriented_h = (height, width) if quarters % 2 else (width, height)
    px, py = logical.T
    if quarters == 1:
        return np.column_stack((oriented_h - py, px))
    if quarters == 2:
        return np.column_stack((oriented_w - px, oriented_h - py))
    if quarters == 3:
        return np.column_stack((py, oriented_w - px))
    return logical


def _beam_pixel_centres(pixels):
    green = pixels[..., 1]
    ys, xs = np.nonzero((green > 32) & (green > 2 * pixels[..., 0]) & (green > 2 * pixels[..., 2]))
    assert len(xs) > 100, "expected a visible beam, not an empty or clipped draw"
    return np.column_stack((xs + 0.5, ys + 0.5))


def _assert_beam_follows_segment(pixels, expected):
    centres = _beam_pixel_centres(pixels)
    start, end = expected
    direction = end - start
    fractions = np.clip((centres - start) @ direction / (direction @ direction), 0.0, 1.0)
    distances = np.linalg.norm(centres - (start + fractions[:, None] * direction), axis=1)
    assert distances.max() < 3.0, "beam left the expected physical segment"
    # Both ends and the whole interior must exist: viewport clipping cannot bless a partial line.
    probes = start + np.linspace(0.0, 1.0, 25)[:, None] * direction
    nearest = np.linalg.norm(probes[:, None, :] - centres[None, :, :], axis=2).min(axis=1)
    assert nearest.max() < 1.1, "beam does not cover the expected physical segment"
    ys, xs = np.nonzero(pixels[..., 3])
    x, y, width, height = _ROTATION_CONTENT_RECT
    assert xs.min() >= x and xs.max() < x + width
    assert ys.min() >= y and ys.max() < y + height
    assert not pixels[[0, -1]].any() and not pixels[:, [0, -1]].any()


def _assert_rotated_flat_beam(pixels, quarters):
    spread = np.ptp(_beam_pixel_centres(pixels), axis=0)
    width, height = _ROTATION_SIZE
    if quarters % 2:
        assert spread[1] > 0.6 * height and spread[0] < 6.0, "quarter-turned flat trace must be vertical"
    else:
        assert spread[0] > 0.6 * width and spread[1] < 6.0, "even-quarter flat trace must be horizontal"
    _assert_beam_follows_segment(pixels, _expected_rotated_segment(quarters))


@pytest.mark.qt
@pytest.mark.parametrize("quarters", [0, 1, 2, 3])
def test_real_gl_quarter_turns_keep_flat_and_rising_traces_in_the_item(qt_app, quarters):
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    target, host = _ScopeGlTarget(*_ROTATION_SIZE), QuickVisualizerRenderHost()
    try:
        flat = target.render(host, _rotation_snapshot(quarters))
        _assert_rotated_flat_beam(flat, quarters)
        diagonal = target.render(host, _rotation_snapshot(quarters, diagonal=True))
        expected = _expected_rotated_segment(quarters, diagonal=True)
        _assert_beam_follows_segment(diagonal, expected)
        centres = _beam_pixel_centres(diagonal)
        assert np.all(np.ptp(centres, axis=0) > np.array(_ROTATION_SIZE) * 0.6)
        slope_sign = np.sign(np.cov(centres.T)[0, 1])
        assert slope_sign == np.sign(np.prod(expected[1] - expected[0]))
    finally:
        host.release_resources()
        target.close()


@pytest.mark.qt
def test_negative_control_missing_physical_mapping_fails_the_vertical_beam_bar(qt_app, monkeypatch):
    from rendering.quick.visualizer.implementations import oscilloscope as renderer_module
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost

    original = renderer_module.OSC_BEAM_VERTEX_SOURCE
    assert original.count("physicalPoint(vLocal)") == 1
    snapshot = _rotation_snapshot(1)
    target, host = _ScopeGlTarget(*_ROTATION_SIZE), QuickVisualizerRenderHost()
    try:
        with monkeypatch.context() as patch:
            # Identity mapping for every valid quarter turn. The invalid-token branch keeps the
            # required uniforms active, so the mutant reaches pixels instead of uniform admission.
            identity = "(vLocal + (uQuarters < 0 ? uOriented : vec2(0.0)))"
            patch.setattr(renderer_module, "OSC_BEAM_VERTEX_SOURCE", original.replace("physicalPoint(vLocal)", identity))
            broken = target.render(host, snapshot)  # Compile and draw the actual broken shader.
            with pytest.raises(AssertionError, match="quarter-turned flat trace must be vertical"):
                _assert_rotated_flat_beam(broken, 1)
            host.release_resources()  # Discard the mutant GL program before rebuilding.
        assert renderer_module.OSC_BEAM_VERTEX_SOURCE is original
        restored = target.render(host, snapshot)
        _assert_rotated_flat_beam(restored, 1)
    finally:
        host.release_resources()
        target.close()
