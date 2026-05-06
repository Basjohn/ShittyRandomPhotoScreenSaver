from __future__ import annotations

import time
from typing import Callable

import pytest
from types import SimpleNamespace

from utils.lockfree import TripleBuffer
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key
from core.settings.visualizer_presets import get_custom_preset_index
from widgets.spotify_visualizer import mode_transition
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    SpotifyVisualizerWidget,
    _AudioFrame,
)
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.beat_engine import BeatEngineRegistry, _SpotifyBeatEngine
import widgets.spotify_visualizer_widget as vis_mod
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QGraphicsDropShadowEffect


def _require_numpy() -> "Callable[[], object]":
    def _loader():
        try:
            import numpy as np  # type: ignore[import]
        except Exception:
            pytest.skip("numpy not available for Spotify visualizer tests")
        return np

    return _loader


@pytest.fixture()
def np_module():
    return _require_numpy()()


def _make_audio_worker(np_module, bar_count: int = 15) -> SpotifyVisualizerAudioWorker:
    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=bar_count, buffer=buf)
    worker._np = np_module  # type: ignore[attr-defined]
    return worker


def _synth_fft(np_module, magnitude: float, size: int = 2048) -> "object":
    fft = np_module.zeros(size, dtype="float32")
    fft[1:32] = magnitude
    return fft


def test_spotify_visualizer_compute_bars_reasonable_runtime(np_module):
    """compute_bars_from_samples should remain reasonably fast.

    This is a coarse regression guard: if heavy per-sample work accidentally
    migrates into Python, or if bar mapping becomes pathologically slow, this
    test will fail. It does not target an exact FPS, only a sane upper bound
    for a batch of computations.
    """

    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=16, buffer=buf)

    # Seed the worker with a numpy module so compute_bars_from_samples works
    # without needing to start a real audio stream.
    worker._np = np_module  # type: ignore[attr-defined]

    samples = np_module.random.rand(4096).astype("float32")

    iterations = 200
    start = time.perf_counter()
    for _ in range(iterations):
        bars = worker.compute_bars_from_samples(samples)
        # Either we got a valid bar vector or None (in which case the worker
        # treated the input as unusable); both are acceptable for this guard.
        if bars is not None:
            assert len(bars) == worker._bar_count  # type: ignore[attr-defined]
    elapsed = time.perf_counter() - start

    # Generous bound: this should comfortably run on modest CI hardware but
    # will fail if compute_bars_from_samples regresses into multi-second work.
    assert elapsed < 0.5, f"compute_bars_from_samples too slow: {elapsed:.3f}s"


@pytest.mark.qt
def test_visualizer_mode_transition_fade_forwards_duration_override(qt_app, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    widget._shadow_config = {"enabled": False}
    widget._show_background = True

    calls: list[int | None] = []

    def _fake_start_fade_in(target, config, *, duration_ms=None, has_background_frame):
        calls.append(duration_ms)

    monkeypatch.setattr(
        "widgets.shadow_utils.ShadowFadeProfile.start_fade_in",
        _fake_start_fade_in,
    )

    mode_transition.start_widget_fade_in(widget, duration_ms=2222)

    assert calls == [2222]
    widget.deleteLater()


def test_spotify_visualizer_set_floor_config_clamps_and_snaps(np_module):
    worker = _make_audio_worker(np_module)
    worker._raw_bass_avg = 3.5  # type: ignore[attr-defined]

    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.01)
    assert worker._use_dynamic_floor is False  # type: ignore[attr-defined]
    assert worker._manual_floor == pytest.approx(worker._min_floor)  # type: ignore[attr-defined]
    assert worker._raw_bass_avg == pytest.approx(worker._manual_floor)  # type: ignore[attr-defined]

    worker.set_floor_config(dynamic_enabled=True, manual_floor=99.0)
    assert worker._use_dynamic_floor is True  # type: ignore[attr-defined]
    assert worker._manual_floor == pytest.approx(worker._max_floor)  # type: ignore[attr-defined]
    # Re-enabling dynamic should reseed the running average to the baseline.
    assert worker._raw_bass_avg == pytest.approx(worker._manual_floor)  # type: ignore[attr-defined]


def test_dynamic_floor_updates_running_average(np_module):
    worker = _make_audio_worker(np_module)
    worker._raw_bass_avg = 3.0  # type: ignore[attr-defined]
    fft = _synth_fft(np_module, magnitude=0.01)

    worker._fft_to_bars(fft)
    assert worker._raw_bass_avg < 3.0  # type: ignore[attr-defined]


def test_floor_config_api_exists(np_module):
    """Verify floor config API exists and accepts parameters."""
    worker = _make_audio_worker(np_module)
    
    # API should exist and not raise
    worker.set_floor_config(dynamic_enabled=True, manual_floor=0.12)
    assert worker._use_dynamic_floor is True
    
    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.5)
    assert worker._use_dynamic_floor is False


def test_sensitivity_config_api_exists(np_module):
    """Verify sensitivity config API exists and accepts parameters."""
    worker = _make_audio_worker(np_module)
    
    # API should exist and not raise
    worker.set_sensitivity_config(recommended=True, sensitivity=1.0)
    worker.set_sensitivity_config(recommended=False, sensitivity=2.5)


def test_shared_beat_engine_registry_reconfigures_single_engine_across_bar_counts():
    registry = BeatEngineRegistry()
    engine = registry.get_engine(36)
    same_engine = registry.get_engine(40)

    assert same_engine is engine
    assert engine._bar_count == 40


class _FakeEngine:
    def __init__(self, bar_count: int = 16) -> None:
        self._audio_buffer = object()
        self._audio_worker = object()
        self._bars_result_buffer = object()
        self.last_floor_config = (True, 0.12)
        self.last_sensitivity_config = (True, 1.0)
        self.thread_manager = None
        self.acquired = 0
        self.started = 0
        self.reset_calls = 0
        self.cancel_calls = 0
        self.floor_reset_calls = 0
        self.last_smoothing = None
        self._bar_count = bar_count
        self._smoothed_bars = [0.0] * bar_count
        self._generation_id = 1
        self._latest_generation_with_frame = self._generation_id
        self.playback_states: list[bool] = []
        self.wake_calls = 0
        self.reconfigure_calls: list[int] = []

    def set_floor_config(self, dyn: bool, floor: float) -> None:
        self.last_floor_config = (dyn, floor)

    def set_sensitivity_config(self, recommended: bool, sensitivity: float) -> None:
        self.last_sensitivity_config = (recommended, sensitivity)

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def acquire(self) -> None:
        self.acquired += 1

    def release(self) -> None:
        self.acquired = max(0, self.acquired - 1)

    def wake(self) -> None:
        self.wake_calls += 1

    def ensure_started(self) -> None:
        self.started += 1

    def reset_smoothing_state(self) -> None:
        self.reset_calls += 1
        self._generation_id += 1
        self._latest_generation_with_frame = self._generation_id - 1
        self._latest_generation_with_waveform = self._generation_id - 1
        self._smoothed_bars = [0.0] * self._bar_count

    def cancel_pending_compute_tasks(self) -> None:
        self.cancel_calls += 1

    def reset_floor_state(self) -> None:
        self.floor_reset_calls += 1

    def set_smoothing(self, smoothing: float) -> None:
        self.last_smoothing = smoothing

    def set_playback_state(self, is_playing: bool) -> None:
        self.playback_states.append(bool(is_playing))

    def get_generation_id(self) -> int:
        return self._generation_id

    def get_latest_generation_with_frame(self) -> int:
        return self._latest_generation_with_frame

    def get_latest_generation_with_waveform(self) -> int:
        return getattr(self, "_latest_generation_with_waveform", self._latest_generation_with_frame)

    def get_smoothed_bars(self) -> list[float]:
        return list(self._smoothed_bars)

    def get_waveform(self) -> list[float]:
        return []

    def get_energy_bands(self):
        return SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)

    def get_pre_agc_energy_bands(self):
        return self.get_energy_bands()

    def get_transient_energy_bands(self):
        return SimpleNamespace(
            bass_transient=0.0,
            mid_transient=0.0,
            high_transient=0.0,
            overall_transient=0.0,
        )

    def tick(self):
        return list(self._smoothed_bars)

    def publish_frame(self, bars: list[float]) -> None:
        self._smoothed_bars = list(bars)
        self._latest_generation_with_frame = self._generation_id
        self._latest_generation_with_waveform = self._generation_id

    def publish_waveform_only(self) -> None:
        self._latest_generation_with_waveform = self._generation_id

    def reconfigure_bar_count(self, bar_count: int) -> None:
        self.reconfigure_calls.append(int(bar_count))
        self._bar_count = max(1, int(bar_count))
        self._audio_buffer = object()
        self._audio_worker = SimpleNamespace(_kick_lane_gain=1.0)
        self._bars_result_buffer = object()
        self._smoothed_bars = [0.0] * self._bar_count
        self._generation_id += 1
        self._latest_generation_with_frame = self._generation_id - 1
        self._latest_generation_with_waveform = self._generation_id - 1


@pytest.mark.qt
def test_resize_bar_buffers_reuses_existing_engine_and_reconfigures_bar_count(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    engine_36 = _FakeEngine(bar_count=36)
    engine_40 = _FakeEngine(bar_count=40)

    def _fake_get_engine(count: int):
        return engine_36 if int(count) == 36 else engine_40

    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", _fake_get_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=36)
    vis._enabled = True
    engine_36.acquired = 1

    vis._resize_bar_buffers(40)

    assert vis._engine is engine_36
    assert engine_36.reconfigure_calls == [40]
    assert engine_40.acquired == 0


class _OverlayStub:
    def __init__(self) -> None:
        self.reset_requests: list[str] = []

    def request_mode_reset(self, mode: str) -> None:  # pragma: no cover - trivial
        self.reset_requests.append(mode)


class _FakeDisplayParent(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._spotify_bars_overlay = _OverlayStub()
        self.frames: list[dict[str, object]] = []

    def push_spotify_visualizer_frame(self, *_, **kwargs):
        self.frames.append(kwargs)
        return True

    def reset_pushes(self) -> None:
        self.frames.clear()


class _BubbleDispatchThreadManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_compute_task(self, worker, *args, **kwargs) -> None:
        self.calls.append(
            {
                "worker": worker,
                "args": args,
                "kwargs": kwargs,
            }
        )


class _ImmediateComputeThreadManager:
    def submit_compute_task(self, fn, callback=None) -> None:
        result = SimpleNamespace(success=True, result=fn())
        if callback is not None:
            callback(result)


def _synthetic_audio(np_module, *, hz: float, amp: float, n: int = 4096):
    t = np_module.arange(n, dtype="float32") / 48000.0
    signal = (
        np_module.sin(2.0 * np_module.pi * hz * t) * amp
        + np_module.sin(2.0 * np_module.pi * hz * 2.7 * t) * (amp * 0.28)
    )
    return signal.astype("float32")


def _poison_audio_worker_state(engine: _SpotifyBeatEngine) -> None:
    aw = engine._audio_worker
    aw._env_short = 9.0
    aw._env_long = 8.0
    aw._env_bass_short = 7.0
    aw._env_bass_long = 6.0
    aw._env_mix_short = 5.0
    aw._env_mix_long = 4.0
    aw._agc_bass_split = 31
    aw._agc_mid_split = 33
    aw._last_raw_bass = 0.91
    aw._last_raw_mid = 0.82
    aw._last_raw_treble = 0.73
    aw._prev_raw_bass = 0.64
    aw._running_peak = 3.0
    aw._raw_bass_avg = 2.5
    aw._applied_noise_floor = 2.0
    aw._last_noise_floor = 1.8
    aw._last_bass_drop_ratio = 0.7
    aw._bass_drop_accum = 0.6
    aw._bar_gate_prev1 = [0.9]
    aw._bar_gate_prev2 = [0.8]
    aw._bar_gate_output = [0.7]
    aw._bar_history = [[0.6]]
    aw._bar_hold_timers = [12]
    aw._last_fft_ts = 123.0
    aw._transient_bass = 0.9
    aw._transient_mid = 0.8
    aw._transient_high = 0.7
    aw._onset_detected = True
    aw._onset_type = "poison"
    aw._onset_strength = 0.6
    aw._pre_agc_bass = 0.88
    aw._pre_agc_mid = 0.77
    aw._pre_agc_treble = 0.66
    aw._bubble_control_norm = 9.0
    aw._bubble_pre_agc_bass = 0.91
    aw._bubble_pre_agc_mid = 0.82
    aw._bubble_pre_agc_treble = 0.73


def _assert_audio_worker_state_reset(engine: _SpotifyBeatEngine) -> None:
    aw = engine._audio_worker
    floor = aw._manual_floor
    assert aw._env_short == pytest.approx(0.5)
    assert aw._env_long == pytest.approx(0.5)
    assert aw._env_bass_short == pytest.approx(0.5)
    assert aw._env_bass_long == pytest.approx(0.5)
    assert aw._env_mix_short == pytest.approx(0.5)
    assert aw._env_mix_long == pytest.approx(0.5)
    assert aw._agc_bass_split == 4
    assert aw._agc_mid_split == 10
    assert aw._last_raw_bass == pytest.approx(0.0)
    assert aw._last_raw_mid == pytest.approx(0.0)
    assert aw._last_raw_treble == pytest.approx(0.0)
    assert aw._prev_raw_bass == pytest.approx(0.0)
    assert aw._running_peak == pytest.approx(0.5)
    assert aw._raw_bass_avg == pytest.approx(floor)
    assert aw._applied_noise_floor == pytest.approx(floor)
    assert aw._last_noise_floor == pytest.approx(floor)
    assert aw._last_bass_drop_ratio == pytest.approx(0.0)
    assert aw._bass_drop_accum == pytest.approx(0.0)
    assert aw._bar_gate_prev1 is None
    assert aw._bar_gate_prev2 is None
    assert aw._bar_gate_output is None
    assert aw._bar_history is None
    assert aw._bar_hold_timers is None
    assert aw._last_fft_ts == pytest.approx(0.0)
    assert aw._transient_bass == pytest.approx(0.0)
    assert aw._transient_mid == pytest.approx(0.0)
    assert aw._transient_high == pytest.approx(0.0)
    assert aw._onset_detected is False
    assert aw._onset_type == ""
    assert aw._onset_strength == pytest.approx(0.0)
    assert aw._pre_agc_bass == pytest.approx(0.0)
    assert aw._pre_agc_mid == pytest.approx(0.0)
    assert aw._pre_agc_treble == pytest.approx(0.0)
    assert aw._bubble_control_norm == pytest.approx(1.0)
    assert aw._bubble_pre_agc_bass == pytest.approx(0.0)
    assert aw._bubble_pre_agc_mid == pytest.approx(0.0)
    assert aw._bubble_pre_agc_treble == pytest.approx(0.0)


def _poison_engine_runtime_state(engine: _SpotifyBeatEngine, np_module) -> tuple[object, object]:
    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    old_audio_buffer = engine._audio_buffer
    old_result_buffer = engine._bars_result_buffer
    engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
    engine._bars_result_buffer.publish([0.9] * engine._bar_count)
    engine._waveform = [0.77] * 256
    engine._waveform_count = 256
    engine._idle_wave_phase = 123.45
    engine._latest_generation_with_waveform = engine.get_generation_id()
    return old_audio_buffer, old_result_buffer


def _assert_engine_runtime_state_reset(
    engine: _SpotifyBeatEngine,
    old_audio_buffer: object,
    old_result_buffer: object,
) -> None:
    assert engine._audio_buffer is not old_audio_buffer
    assert engine._bars_result_buffer is not old_result_buffer
    assert engine._audio_worker._buffer is engine._audio_buffer
    assert engine._waveform == [0.0] * 256
    assert engine._waveform_count == 0
    assert engine._idle_wave_phase == pytest.approx(0.0)
    assert engine.get_latest_generation_with_waveform() < engine.get_generation_id()


@pytest.mark.qt
def test_mode_switch_requests_overlay_reset_after_target_mode_lands(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    parent._spotify_bars_overlay.reset_requests.clear()
    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    assert parent._spotify_bars_overlay.reset_requests == ["oscilloscope"]


@pytest.mark.qt
def test_bubble_dispatch_uses_pre_agc_energy_even_without_legacy_toggle(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine.get_energy_bands = lambda: SimpleNamespace(bass=0.11, mid=0.22, high=0.33, overall=0.44)
    fake_engine.get_pre_agc_energy_bands = lambda: SimpleNamespace(bass=0.71, mid=0.72, high=0.73, overall=0.74)
    fake_engine.get_transient_energy_bands = lambda: SimpleNamespace(
        bass_transient=0.0,
        mid_transient=0.0,
        high_transient=0.0,
        onset_detected=False,
        onset_type="",
        onset_strength=0.0,
    )
    fake_engine.get_event_scheduler = lambda: None

    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget.set_visualization_mode(VisualizerMode.BUBBLE)
    widget._mode_teardown_block_until_ready = False
    widget._bubble_compute_pending = False
    widget._thread_manager = _BubbleDispatchThreadManager()
    widget._spotify_playing = True
    widget._bubble_last_tick_ts = time.time() - 0.016
    widget._bubble_bounce_big_pct = 87
    widget._bubble_bounce_small_pct = 14
    widget._bubble_bounce_big_speed = 1.25
    widget._bubble_bounce_small_speed = 0.42
    widget._bubble_bounce_same_only = True
    widget._bubble_collision_pop_mode = "one"

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())

    assert widget._thread_manager.calls
    eb_snap = widget._thread_manager.calls[0]["args"][1]
    sim_settings = widget._thread_manager.calls[0]["args"][2]
    assert eb_snap["bass"] == pytest.approx(0.71)
    assert eb_snap["mid"] == pytest.approx(0.72)
    assert eb_snap["high"] == pytest.approx(0.73)
    assert eb_snap["overall"] == pytest.approx(0.74)
    assert sim_settings["bubble_bounce_big_pct"] == 87
    assert sim_settings["bubble_bounce_small_pct"] == 14
    assert sim_settings["bubble_bounce_big_speed"] == pytest.approx(1.25)
    assert sim_settings["bubble_bounce_small_speed"] == pytest.approx(0.42)
    assert sim_settings["bubble_bounce_same_only"] is True
    assert sim_settings["bubble_collision_pop_mode"] == "one"


def test_beat_engine_playback_state_strict_worker_lifecycle():
    class _WorkerStub:
        def __init__(self) -> None:
            self.running = False
            self.start_calls = 0
            self.stop_calls = 0

        def is_running(self) -> bool:
            return self.running

        def start(self) -> None:
            self.start_calls += 1
            self.running = True

        def stop(self) -> None:
            self.stop_calls += 1
            self.running = False

    engine = _SpotifyBeatEngine(bar_count=8)
    worker = _WorkerStub()
    engine._audio_worker = worker  # type: ignore[assignment]
    engine._ref_count = 1

    engine.set_playback_state(True)
    assert worker.start_calls == 1
    assert worker.running is True

    engine.set_playback_state(False)
    assert worker.stop_calls == 1
    assert worker.running is False

    # Without an active widget reference, play-state must not auto-start capture.
    engine._ref_count = 0
    engine.set_playback_state(True)
    assert worker.start_calls == 1


@pytest.mark.qt
def test_bubble_dispatch_keeps_idle_motion_while_paused(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine.get_pre_agc_energy_bands = lambda: SimpleNamespace(bass=0.0, mid=0.0, high=0.0, overall=0.0)
    fake_engine.get_transient_energy_bands = lambda: SimpleNamespace(
        bass_transient=0.0,
        mid_transient=0.0,
        high_transient=0.0,
        onset_detected=False,
        onset_type="",
        onset_strength=0.0,
    )
    fake_engine.get_event_scheduler = lambda: None
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget.set_visualization_mode(VisualizerMode.BUBBLE)
    widget._mode_teardown_block_until_ready = False
    widget._bubble_compute_pending = False
    widget._thread_manager = _BubbleDispatchThreadManager()
    widget._spotify_playing = False
    widget._bubble_last_tick_ts = time.time() - 0.016

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())

    assert widget._thread_manager.calls
    dt = widget._thread_manager.calls[0]["args"][0]
    eb_snap = widget._thread_manager.calls[0]["args"][1]
    assert dt > 0.0
    assert eb_snap["bass"] > 0.0
    assert eb_snap["overall"] > 0.0


@pytest.mark.parametrize(
    "mode",
    [
        VisualizerMode.BUBBLE,
        VisualizerMode.OSCILLOSCOPE,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.SPECTRUM,
    ],
)
@pytest.mark.qt
def test_paused_idle_modes_do_not_block_on_fresh_engine_wait(qt_app, qtbot, monkeypatch, mode):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget.set_visualization_mode(mode)
    widget._spotify_playing = False
    widget._waiting_for_fresh_engine_frame = True
    widget._pending_engine_generation = 42

    tick_pipeline.consume_engine_bars(widget, time.time())

    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._pending_engine_generation == -1


@pytest.mark.qt
def test_on_tick_checks_mode_teardown_before_fresh_wait_return(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._waiting_for_fresh_engine_frame = True
    widget._pending_engine_generation = fake_engine.get_generation_id()
    widget._mode_teardown_state = "waiting_bars"
    widget._mode_teardown_block_until_ready = True
    widget._mode_transition_ready = False
    widget._mode_teardown_target_generation = fake_engine.get_generation_id()
    widget._mode_teardown_wait_started_ts = time.time() - 1.0

    widget._on_tick()

    assert widget._mode_teardown_state in {"ready", "fading_in"}
    assert widget._mode_teardown_block_until_ready is False


@pytest.mark.qt
def test_mode_teardown_ready_uses_timeout_fallback_when_paused(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    widget._spotify_playing = False
    widget._enabled = True
    widget._mode_teardown_state = "waiting_bars"
    widget._mode_teardown_block_until_ready = True
    widget._mode_transition_ready = False
    widget._mode_teardown_target_generation = 999
    widget._mode_teardown_wait_started_ts = time.time() - 1.0

    # Keep the test deterministic; we only care that waiting state clears.
    monkeypatch.setattr(mode_transition, "start_widget_fade_in", lambda *_args, **_kwargs: None)

    mode_transition.check_mode_teardown_ready(widget, engine=_FakeEngine(bar_count=8), now_ts=time.time())

    assert widget._mode_transition_ready is True
    assert widget._mode_teardown_block_until_ready is False
    assert widget._mode_teardown_state in {"ready", "fading_in"}


@pytest.mark.qt
def test_mode_switch_waits_for_fresh_engine_generation(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()
    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    assert widget._waiting_for_fresh_engine_frame is True
    assert widget._pending_engine_generation == fake_engine.get_generation_id()

    parent.reset_pushes()
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is True
    assert parent.frames == []

    fake_engine.publish_frame([0.75] * widget._bar_count)
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is False
    assert parent.frames


@pytest.mark.qt
def test_osc_mode_switch_waits_for_fresh_waveform_generation(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()
    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    parent.reset_pushes()
    fake_engine._latest_generation_with_frame = fake_engine.get_generation_id()
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is True
    assert parent.frames == []

    fake_engine.publish_waveform_only()
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is False
    assert parent.frames


@pytest.mark.qt
def test_runtime_push_carries_spectrum_glow_settings(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget.apply_vis_mode_config(
        mode="spectrum",
        spectrum_glow_enabled=True,
        spectrum_glow_intensity=1.15,
        spectrum_glow_color=[0, 120, 255, 255],
    )
    widget.start()
    qt_app.processEvents()
    fake_engine.publish_frame([0.65] * widget._bar_count)

    parent.reset_pushes()
    widget._on_tick()

    assert parent.frames
    frame = parent.frames[-1]
    assert frame["vis_mode"] == "spectrum"
    assert frame["spectrum_glow_enabled"] is True
    assert frame["spectrum_glow_intensity"] == pytest.approx(1.15)


@pytest.mark.qt
def test_runtime_push_carries_osc_secondary_ghost_toggles(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget.apply_vis_mode_config(
        mode="oscilloscope",
        osc_line_count=3,
        osc_ghosting_enabled=True,
        osc_ghost_intensity=0.62,
        osc_ghost_line2_enabled=True,
        osc_ghost_line3_enabled=False,
    )
    widget.start()
    qt_app.processEvents()
    fake_engine.publish_frame([0.55] * widget._bar_count)
    fake_engine.publish_waveform_only()

    parent.reset_pushes()
    widget._on_tick()

    assert parent.frames
    frame = parent.frames[-1]
    assert frame["vis_mode"] == "oscilloscope"
    assert frame["osc_ghosting_enabled"] is True
    assert frame["osc_ghost_intensity"] == pytest.approx(0.62)
    assert frame["osc_ghost_line2_enabled"] is True
    assert frame["osc_ghost_line3_enabled"] is False


@pytest.mark.qt
def test_set_settings_model_applies_incoming_mode_technical_config(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    model = SpotifyVisualizerSettings(
        mode="oscilloscope",
        bar_count=8,
        oscilloscope_bar_count=24,
        oscilloscope_dynamic_floor=False,
        oscilloscope_manual_floor=0.21,
    )

    widget.set_settings_model(model)

    assert widget._bar_count == 24
    assert widget._last_floor_config[0] is False
    assert widget._last_floor_config[1] == pytest.approx(0.21)


@pytest.mark.qt
def test_apply_vis_mode_config_merges_runtime_technical_overrides(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine

    widget.apply_vis_mode_config(
        mode="blob",
        blob_dynamic_floor=False,
        blob_manual_floor=0.12,
        blob_adaptive_sensitivity=False,
        blob_sensitivity=0.58,
        blob_audio_block_size=128,
    )

    blob_cfg = widget._technical_config_cache["blob"]
    assert blob_cfg["dynamic_floor"] is False
    assert blob_cfg["manual_floor"] == pytest.approx(0.12)
    assert blob_cfg["adaptive_sensitivity"] is False
    assert blob_cfg["sensitivity"] == pytest.approx(0.58)
    assert blob_cfg["audio_block_size"] == 128
    assert widget._last_floor_config[0] is False
    assert widget._last_floor_config[1] == pytest.approx(0.12)
    assert widget._last_sensitivity_config[0] is False
    assert widget._last_sensitivity_config[1] == pytest.approx(0.58)
    assert widget._last_audio_block_size == 128


@pytest.mark.qt
def test_missing_mode_cache_does_not_fall_back_to_foreign_technical_state(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget._technical_config_cache = {
        "blob": {
            "bar_count": 19,
            "dynamic_floor": False,
            "manual_floor": 0.31,
            "adaptive_sensitivity": False,
            "sensitivity": 0.44,
            "audio_block_size": 256,
            "dynamic_range_enabled": True,
            "agc_strength": 0.71,
            "input_gain": 1.55,
            "kick_lane_gain": 1.25,
            "transient_pulse_gain": 1.4,
            "transient_clamp": 1.8,
            "blob_transient_mix_bass": 0.93,
            "blob_transient_mix_vocal": 0.41,
        }
    }
    widget._last_floor_config = (True, 0.12)
    widget._last_sensitivity_config = (True, 1.0)
    widget._last_audio_block_size = 0
    widget._last_input_gain = 1.0

    widget._apply_technical_config_for_mode(VisualizerMode.SPECTRUM, reason="test_missing_mode_cache")

    assert widget._bar_count == 8
    assert widget._last_floor_config == (True, 0.12)
    assert widget._last_sensitivity_config == (True, 1.0)
    assert widget._last_audio_block_size == 0
    assert widget._last_input_gain == pytest.approx(1.0)
    assert fake_engine.last_floor_config == (True, 0.12)
    assert fake_engine.last_sensitivity_config == (True, 1.0)


@pytest.mark.qt
def test_mode_switch_replays_distinct_per_mode_shared_technical_state(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine

    model = SpotifyVisualizerSettings(
        mode="blob",
        bar_count=8,
        blob_bar_count=18,
        blob_dynamic_floor=False,
        blob_manual_floor=0.14,
        blob_adaptive_sensitivity=False,
        blob_sensitivity=0.66,
        blob_audio_block_size=128,
        blob_dynamic_range_enabled=True,
        blob_agc_strength=0.72,
        blob_input_gain=1.35,
        blob_kick_lane_gain=1.55,
        blob_transient_clamp=2.2,
        blob_transient_mix_bass=0.92,
        blob_transient_mix_vocal=0.38,
        sine_wave_bar_count=27,
        sine_wave_dynamic_floor=False,
        sine_wave_manual_floor=0.24,
        sine_wave_adaptive_sensitivity=False,
        sine_wave_sensitivity=0.83,
        sine_wave_audio_block_size=512,
        sine_wave_dynamic_range_enabled=False,
        sine_wave_agc_strength=0.41,
        sine_wave_input_gain=1.12,
        sine_wave_kick_lane_gain=0.77,
        sine_wave_transient_clamp=1.3,
        sine_wave_transient_width_mix=0.21,
    )

    widget.set_settings_model(model)

    assert widget._bar_count == 18
    assert widget._last_floor_config[0] is False
    assert widget._last_floor_config[1] == pytest.approx(0.14)
    assert widget._last_sensitivity_config[0] is False
    assert widget._last_sensitivity_config[1] == pytest.approx(0.66)
    assert widget._last_audio_block_size == 128
    assert widget._last_input_gain == pytest.approx(1.35)
    assert widget._blob_transient_mix_bass == pytest.approx(0.92)
    assert widget._blob_transient_mix_vocal == pytest.approx(0.38)
    assert parent._spotify_bars_overlay._blob_transient_mix_bass == pytest.approx(0.92)
    assert parent._spotify_bars_overlay._blob_transient_mix_vocal == pytest.approx(0.38)

    widget.set_visualization_mode(VisualizerMode.SINE_WAVE)

    assert widget._bar_count == 27
    assert widget._last_floor_config[0] is False
    assert widget._last_floor_config[1] == pytest.approx(0.24)
    assert widget._last_sensitivity_config[0] is False
    assert widget._last_sensitivity_config[1] == pytest.approx(0.83)
    assert widget._last_audio_block_size == 512
    assert widget._last_input_gain == pytest.approx(1.12)
    assert widget._kick_lane_gain == pytest.approx(0.77)
    assert widget._transient_clamp == pytest.approx(1.3)
    assert widget._sine_wave_transient_width_mix == pytest.approx(0.21)
    assert parent._spotify_bars_overlay._sine_wave_transient_width_mix == pytest.approx(0.21)

    widget.set_visualization_mode(VisualizerMode.BLOB)

    assert widget._bar_count == 18
    assert widget._last_floor_config[0] is False
    assert widget._last_floor_config[1] == pytest.approx(0.14)
    assert widget._last_sensitivity_config[0] is False
    assert widget._last_sensitivity_config[1] == pytest.approx(0.66)
    assert widget._last_audio_block_size == 128
    assert widget._last_input_gain == pytest.approx(1.35)
    assert widget._kick_lane_gain == pytest.approx(1.55)
    assert widget._transient_clamp == pytest.approx(2.2)
    assert widget._blob_transient_mix_bass == pytest.approx(0.92)
    assert widget._blob_transient_mix_vocal == pytest.approx(0.38)
    assert parent._spotify_bars_overlay._blob_transient_mix_bass == pytest.approx(0.92)
    assert parent._spotify_bars_overlay._blob_transient_mix_vocal == pytest.approx(0.38)


@pytest.mark.qt
def test_runtime_mode_switch_replays_target_mode_full_config(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    spectrum_preset_key = get_preset_key("spectrum")
    devcurve_preset_key = get_preset_key("devcurve")
    spotify_cfg = {
        "mode": "devcurve",
        spectrum_preset_key: get_custom_preset_index("spectrum"),
        devcurve_preset_key: get_custom_preset_index("devcurve"),
        "spectrum_bar_count": 8,
        "spectrum_dynamic_floor": True,
        "spectrum_manual_floor": 0.12,
        "spectrum_growth": 2.5,
        "devcurve_bar_count": 8,
        "devcurve_dynamic_floor": True,
        "devcurve_manual_floor": 0.61,
        "devcurve_growth": 5.9,
    }

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": dict(spotify_cfg)}
            return default

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._engine = fake_engine
    widget.set_settings_model(SpotifyVisualizerSettings.from_mapping(spotify_cfg))
    widget._vis_mode = VisualizerMode.DEVCURVE
    widget._spectrum_growth = 5.9
    widget._last_floor_config = (True, 0.61)

    widget.set_visualization_mode(VisualizerMode.SPECTRUM)

    assert widget._vis_mode is VisualizerMode.SPECTRUM
    assert widget._last_floor_config == (True, pytest.approx(0.12))
    assert widget._spectrum_growth == pytest.approx(2.5)
    assert fake_engine.last_floor_config == (True, pytest.approx(0.12))


@pytest.mark.qt
def test_runtime_mode_switch_all_modes_replaces_poisoned_technical_state(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    spotify_cfg = {"mode": "spectrum"}
    expected: dict[str, tuple[int, float]] = {}
    growth_attr = {
        "spectrum": "_spectrum_growth",
        "oscilloscope": "_osc_growth",
        "blob": "_blob_growth",
        "sine_wave": "_sine_wave_growth",
        "bubble": "_bubble_growth",
        "devcurve": "_devcurve_growth",
    }
    for idx, mode_id in enumerate(VISUALIZER_MODE_IDS):
        spotify_cfg[get_preset_key(mode_id)] = get_custom_preset_index(mode_id)
        bar_count = 9 + idx
        floor = 0.11 + idx * 0.03
        growth = 1.2 + idx * 0.25
        spotify_cfg[f"{mode_id}_bar_count"] = bar_count
        spotify_cfg[f"{mode_id}_dynamic_floor"] = False
        spotify_cfg[f"{mode_id}_manual_floor"] = floor
        spotify_cfg[f"{mode_id}_adaptive_sensitivity"] = False
        spotify_cfg[f"{mode_id}_sensitivity"] = 0.55 + idx * 0.02
        if mode_id == "oscilloscope":
            spotify_cfg["osc_growth"] = growth
            spotify_cfg["osc_ghosting_enabled"] = bool(idx % 2)
        else:
            spotify_cfg[f"{mode_id}_growth"] = growth
            spotify_cfg[f"{mode_id}_ghosting_enabled"] = bool(idx % 2)
        if mode_id == "spectrum":
            spotify_cfg["spectrum_profile_floor"] = 0.18
        if mode_id == "devcurve":
            spotify_cfg["devcurve_active_layer"] = "vocals"
        expected[mode_id] = (bar_count, floor)

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": dict(spotify_cfg)}
            return default

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._engine = fake_engine
    original_engine = widget._engine

    for mode_id in VISUALIZER_MODE_IDS:
        target = getattr(VisualizerMode, mode_id.upper())
        widget._vis_mode = VisualizerMode.SPECTRUM if target is not VisualizerMode.SPECTRUM else VisualizerMode.BLOB
        widget._last_floor_config = (False, 0.61)
        widget._last_sensitivity_config = (False, 9.0)
        for attr in growth_attr.values():
            setattr(widget, attr, 5.0)
        widget._spectrum_profile_floor = 0.30
        widget._devcurve_active_layer = "bass"
        before_resets = fake_engine.reset_calls

        widget.set_visualization_mode(target)

        bar_count, floor = expected[mode_id]
        assert widget._engine is original_engine
        assert widget._bar_count == bar_count
        assert widget._last_floor_config == (False, pytest.approx(floor))
        assert fake_engine.last_floor_config == (False, pytest.approx(floor))
        assert fake_engine.reset_calls == before_resets + 1
        assert getattr(widget, growth_attr[mode_id]) == pytest.approx(
            1.2 + VISUALIZER_MODE_IDS.index(mode_id) * 0.25
        )
        if mode_id == "spectrum":
            assert widget._spectrum_profile_floor == pytest.approx(0.18)
        if mode_id == "devcurve":
            assert widget._devcurve_active_layer == "vocals"


@pytest.mark.qt
def test_runtime_switch_paths_reset_all_bleed_state_for_all_modes(qt_app, qtbot, np_module):
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    engine = _SpotifyBeatEngine(12)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=12)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True

    ordered_modes = [
        getattr(VisualizerMode, desc.mode_id.upper())
        for desc in iter_visualizer_mode_descriptors()
        if getattr(VisualizerMode, desc.mode_id.upper(), None) is not None
    ]

    for idx, target in enumerate(ordered_modes):
        previous = ordered_modes[idx - 1]
        widget._vis_mode = previous
        widget._mode_transition_phase = 0
        widget._mode_transition_pending = None
        _poison_audio_worker_state(engine)
        old_audio_buffer, old_result_buffer = _poison_engine_runtime_state(engine, np_module)

        assert mode_transition.switch_to_mode(widget, target.name.lower()) is True
        now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
        mode_transition.mode_transition_fade_factor(widget, now)

        assert widget._engine is engine
        assert widget._vis_mode is target
        _assert_audio_worker_state_reset(engine)
        _assert_engine_runtime_state_reset(engine, old_audio_buffer, old_result_buffer)

    for idx, target in enumerate(ordered_modes):
        previous = ordered_modes[idx - 1]
        widget._vis_mode = previous
        widget._mode_transition_phase = 0
        widget._mode_transition_pending = None
        _poison_audio_worker_state(engine)
        old_audio_buffer, old_result_buffer = _poison_engine_runtime_state(engine, np_module)

        assert mode_transition.cycle_mode(widget) is True
        now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
        mode_transition.mode_transition_fade_factor(widget, now)

        assert widget._engine is engine
        assert widget._vis_mode is target
        _assert_audio_worker_state_reset(engine)
        _assert_engine_runtime_state_reset(engine, old_audio_buffer, old_result_buffer)


@pytest.mark.qt
def test_mode_switch_synthetic_audio_matches_fresh_worker_after_reset(qt_app, qtbot, np_module):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    live_engine = _SpotifyBeatEngine(35)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=35)
    qtbot.addWidget(widget)
    widget._engine = live_engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.DEVCURVE

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    target_samples = _synthetic_audio(np_module, hz=440.0, amp=0.08)

    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    assert max(live_engine._latest_bars or [0.0]) > 0.0
    _poison_audio_worker_state(live_engine)

    assert mode_transition.switch_to_mode(widget, "spectrum") is True
    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    live_engine._audio_buffer.publish(_AudioFrame(samples=target_samples))
    live_engine.tick()
    live_bars = live_engine.get_smoothed_bars()

    fresh_engine = _SpotifyBeatEngine(35)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0
    oracle_widget = SpotifyVisualizerWidget(parent=parent, bar_count=35)
    qtbot.addWidget(oracle_widget)
    oracle_widget._engine = fresh_engine
    oracle_widget._vis_mode = VisualizerMode.SPECTRUM
    oracle_widget._replay_engine_config(fresh_engine)
    fresh_engine._audio_buffer.publish(_AudioFrame(samples=target_samples))
    fresh_engine.tick()
    fresh_bars = fresh_engine.get_smoothed_bars()

    assert live_engine is widget._engine
    assert live_bars == pytest.approx(fresh_bars, abs=0.025)
    assert max(live_bars) < 0.98
    assert max(live_bars) - min(live_bars) > 0.05


@pytest.mark.qt
def test_mode_switch_discards_stale_audio_buffer_before_next_frame(qt_app, qtbot, np_module):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    engine = _SpotifyBeatEngine(24)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=24)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.DEVCURVE

    old_audio_buffer, old_result_buffer = _poison_engine_runtime_state(engine, np_module)

    assert mode_transition.switch_to_mode(widget, "spectrum") is True
    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    engine.tick()

    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)
    assert engine.get_latest_generation_with_frame() < engine.get_generation_id()
    _assert_engine_runtime_state_reset(engine, old_audio_buffer, old_result_buffer)


@pytest.mark.qt
def test_preset_activation_discards_audio_buffer_and_idle_state(qt_app, qtbot, np_module):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    engine = _SpotifyBeatEngine(18)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=18)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM

    _poison_audio_worker_state(engine)
    old_audio_buffer, old_result_buffer = _poison_engine_runtime_state(engine, np_module)

    widget.reset_runtime_activation_state(reason="preset_cycle")
    engine.tick()

    _assert_audio_worker_state_reset(engine)
    _assert_engine_runtime_state_reset(engine, old_audio_buffer, old_result_buffer)
    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)
    assert engine.get_latest_generation_with_frame() < engine.get_generation_id()


@pytest.mark.qt
def test_widget_manager_preset_cycle_discards_real_engine_bleed_state(
    qt_app,
    qtbot,
    settings_manager,
    np_module,
):
    from rendering.widget_manager import WidgetManager

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.screen_index = 0

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg["mode"] = "spectrum"
    spotify_cfg["preset_spectrum"] = 0
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    engine = _SpotifyBeatEngine(20)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=20)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM

    wm = WidgetManager(parent, resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._widgets["spotify_visualizer"] = widget
    widget._widget_manager = wm

    _poison_audio_worker_state(engine)
    old_audio_buffer, old_result_buffer = _poison_engine_runtime_state(engine, np_module)

    assert wm.cycle_visualizer_preset("spectrum", 1) is True
    engine.tick()

    _assert_audio_worker_state_reset(engine)
    _assert_engine_runtime_state_reset(engine, old_audio_buffer, old_result_buffer)
    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)
    assert engine.get_latest_generation_with_frame() < engine.get_generation_id()


@pytest.mark.qt
def test_runtime_cycle_all_modes_and_settle_devcurve_matches_settings_refresh(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._audio_worker = SimpleNamespace()
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    spotify_cfg = {"mode": "devcurve"}
    for idx, mode_id in enumerate(VISUALIZER_MODE_IDS):
        spotify_cfg[get_preset_key(mode_id)] = get_custom_preset_index(mode_id)
        spotify_cfg[f"{mode_id}_bar_count"] = 10 + idx
        spotify_cfg[f"{mode_id}_dynamic_floor"] = False
        spotify_cfg[f"{mode_id}_manual_floor"] = 0.10 + idx * 0.04
        spotify_cfg[f"{mode_id}_adaptive_sensitivity"] = False
        spotify_cfg[f"{mode_id}_sensitivity"] = 0.5 + idx * 0.03
    spotify_cfg.update(
        {
            "spectrum_growth": 4.8,
            "spectrum_profile_floor": 0.22,
            "devcurve_growth": 2.25,
            "devcurve_active_layer": "transients",
            "devcurve_ghosting_enabled": True,
        }
    )

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": dict(spotify_cfg)}
            return default

    runtime = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    runtime._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    runtime._engine = fake_engine
    original_engine = runtime._engine

    for mode_id in VISUALIZER_MODE_IDS:
        runtime.set_visualization_mode(getattr(VisualizerMode, mode_id.upper()))
    runtime.set_visualization_mode(VisualizerMode.DEVCURVE)

    refresh = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    refresh._engine = fake_engine
    refresh.set_settings_model(SpotifyVisualizerSettings.from_mapping(spotify_cfg))
    from rendering.spotify_widget_creators import apply_spotify_vis_model_config

    apply_spotify_vis_model_config(refresh, SpotifyVisualizerSettings.from_mapping(spotify_cfg))

    assert runtime._engine is original_engine
    assert runtime._vis_mode is VisualizerMode.DEVCURVE
    assert runtime._bar_count == refresh._bar_count
    assert runtime._last_floor_config == refresh._last_floor_config
    assert runtime._last_sensitivity_config == refresh._last_sensitivity_config
    assert runtime._devcurve_growth == pytest.approx(refresh._devcurve_growth)
    assert runtime._devcurve_active_layer == refresh._devcurve_active_layer
    assert runtime._devcurve_ghosting_enabled is refresh._devcurve_ghosting_enabled


@pytest.mark.qt
def test_repeated_mode_switches_keep_fresh_generation_contract(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()

    modes = [
        VisualizerMode.OSCILLOSCOPE,
        VisualizerMode.SPECTRUM,
        VisualizerMode.BLOB,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.OSCILLOSCOPE,
    ]

    for idx, mode in enumerate(modes):
        parent.reset_pushes()
        widget.set_visualization_mode(mode)

        assert widget._waiting_for_fresh_engine_frame is True
        widget._on_tick()
        assert parent.frames == []

        fake_engine.publish_frame([0.2 + idx * 0.1] * widget._bar_count)
        widget._on_tick()

        assert widget._waiting_for_fresh_engine_frame is False
        assert parent.frames

    assert fake_engine.reset_calls >= len(modes)


@pytest.mark.qt
def test_spotify_visualizer_replays_config_on_start(qt_app, qtbot, monkeypatch):
    """Ensure manual floor/sensitivity get replayed to the shared engine when starting."""

    fake_engine = _FakeEngine()

    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    widget.set_floor_config(dynamic_enabled=False, manual_floor=0.3)
    widget.set_sensitivity_config(recommended=False, sensitivity=2.4)

    # Simulate the engine forgetting the config before start (e.g., after restart).
    fake_engine.last_floor_config = (True, 0.12)
    fake_engine.last_sensitivity_config = (True, 1.0)

    widget.start()
    qt_app.processEvents()

    assert fake_engine.last_floor_config == (False, 0.3)
    assert fake_engine.last_sensitivity_config == (False, 2.4)


@pytest.mark.qt
def test_blob_crossover_waits_for_fresh_engine_frame(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget.set_visualization_mode(VisualizerMode.SPECTRUM)
    widget.start()
    qt_app.processEvents()

    widget.set_visualization_mode(VisualizerMode.BLOB)
    widget._reset_engine_state(reason="test_crossover")
    widget._track_engine_generation(fake_engine)

    parent.reset_pushes()
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is True
    assert parent.frames == []

    fake_engine.publish_frame([0.75] * widget._bar_count)
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is False
    assert parent.frames, "GPU push should resume once a fresh engine generation publishes"


@pytest.mark.qt
def test_mode_cycle_resets_engine_smoothing(qt_app, qtbot, monkeypatch):
    fake_engine = _FakeEngine()

    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    widget._cached_vis_kwargs = {"spectrum_single_piece": True}  # type: ignore[attr-defined]

    assert mode_transition.cycle_mode(widget) is True

    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert fake_engine.reset_calls >= 1


@pytest.mark.qt
def test_mode_cycle_does_not_destroy_overlay_during_crossfade(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    cleared = {"count": 0}

    def _patched_clear_overlay() -> None:
        cleared["count"] += 1

    monkeypatch.setattr(widget, "_clear_gl_overlay", _patched_clear_overlay)

    assert mode_transition.cycle_mode(widget) is True

    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert cleared["count"] == 0


@pytest.mark.qt
def test_spotify_visualizer_widgets_share_audio_engine(qt_app, qtbot):
    widget1 = SpotifyVisualizerWidget(parent=None, bar_count=16)
    widget2 = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qtbot.addWidget(widget1)
    qtbot.addWidget(widget2)

    aw1 = getattr(widget1, "_audio_worker", None)
    aw2 = getattr(widget2, "_audio_worker", None)
    buf1 = getattr(widget1, "_bars_buffer", None)
    buf2 = getattr(widget2, "_bars_buffer", None)

    assert aw1 is not None
    assert aw1 is aw2
    assert buf1 is not None
    assert buf1 is buf2


@pytest.mark.qt
def test_spotify_visualizer_emits_perf_metrics(qt_app, qtbot, monkeypatch, caplog):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qtbot.addWidget(widget)

    monkeypatch.setattr(vis_mod, "is_perf_metrics_enabled", lambda: True)
    # Also patch the extracted tick_helpers module where log_perf_snapshot now lives
    import widgets.spotify_visualizer.tick_helpers as _th_mod
    monkeypatch.setattr(_th_mod, "is_perf_metrics_enabled", lambda: True)

    widget._perf_tick_start_ts = 0.0  # type: ignore[attr-defined]
    widget._perf_tick_last_ts = 1.0  # type: ignore[attr-defined]
    widget._perf_tick_frame_count = 60  # type: ignore[attr-defined]
    widget._perf_tick_min_dt = 1.0 / 120.0  # type: ignore[attr-defined]
    widget._perf_tick_max_dt = 1.0 / 20.0  # type: ignore[attr-defined]

    with caplog.at_level("INFO"):
        widget._log_perf_snapshot(reset=True)  # type: ignore[attr-defined]

    messages = [r.message for r in caplog.records]
    assert any("[PERF] [SPOTIFY_VIS] Tick metrics" in m for m in messages)


def test_compute_bars_returns_list_or_none(np_module):
    """compute_bars_from_samples should return list or None."""
    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=15, buffer=buf)
    worker._np = np_module
    
    samples = np_module.random.rand(2048).astype("float32")
    result = worker.compute_bars_from_samples(samples)
    
    assert result is None or isinstance(result, list)


@pytest.mark.qt
def test_visualizer_widget_initializes_fresh_generation_state(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    assert widget._waiting_for_fresh_frame is False
    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._pending_engine_generation == -1
    assert widget._last_engine_generation_seen == -1


@pytest.mark.qt
def test_tick_pipeline_backfills_missing_fresh_generation_state(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    delattr(widget, "_waiting_for_fresh_frame")
    delattr(widget, "_waiting_for_fresh_engine_frame")
    delattr(widget, "_pending_engine_generation")
    delattr(widget, "_last_engine_generation_seen")

    tick_pipeline._ensure_fresh_generation_state(widget)

    assert widget._waiting_for_fresh_frame is False
    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._pending_engine_generation == -1
    assert widget._last_engine_generation_seen == -1


@pytest.mark.qt
def test_mode_cycle_switches_without_stale_cached_cold_replay(qt_app, qtbot, monkeypatch):
    """Double-click mode cycle should not replay previous-mode kwargs during handoff."""

    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    widget._cached_vis_kwargs = {"sine_travel_line2": 0.42}  # type: ignore[attr-defined]

    original_reset = SpotifyVisualizerWidget._reset_visualizer_state
    replay_flags: dict[str, bool | None] = {"replay": None, "clear_overlay": None}

    def _patched_reset(self, *, clear_overlay: bool = False, replay_cached: bool = False):
        replay_flags["replay"] = replay_cached
        replay_flags["clear_overlay"] = clear_overlay
        return original_reset(self, clear_overlay=clear_overlay, replay_cached=replay_cached)

    monkeypatch.setattr(SpotifyVisualizerWidget, "_reset_visualizer_state", _patched_reset)

    assert mode_transition.cycle_mode(widget) is True
    # Fast-forward fade-out completion (phase 1 → phase 2)
    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert replay_flags["replay"] is None
    assert replay_flags["clear_overlay"] is None


@pytest.mark.qt
def test_mode_transition_reset_preserves_timestamp(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    widget._mode_transition_phase = 1
    widget._mode_transition_ts = 123.456
    widget._cached_vis_kwargs = {"spectrum_single_piece": True}  # type: ignore[attr-defined]

    applied = {"called": False}

    def _fake_apply(target, kwargs):
        applied["called"] = True

    monkeypatch.setattr(
        "widgets.spotify_visualizer.config_applier.apply_vis_mode_kwargs",
        _fake_apply,
    )

    widget._reset_visualizer_state(clear_overlay=False, replay_cached=True)

    assert applied["called"] is True
    assert widget._mode_transition_phase == 1
    assert widget._mode_transition_ts == pytest.approx(123.456)


@pytest.mark.qt
def test_apply_vis_mode_config_same_mode_skips_cold_reset(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    widget._vis_mode = VisualizerMode.SPECTRUM

    reset_calls = {"count": 0}

    def _patched_reset(*args, **kwargs):
        reset_calls["count"] += 1

    monkeypatch.setattr(widget, "_reset_visualizer_state", _patched_reset)

    widget.apply_vis_mode_config("spectrum", spectrum_single_piece=True)

    assert reset_calls["count"] == 0


@pytest.mark.qt
def test_set_visualization_mode_requests_single_overlay_reset(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    reset_requests = {"count": 0}

    def _patched_request_overlay_mode_reset(*args, **kwargs):
        reset_requests["count"] += 1

    monkeypatch.setattr(widget, "_request_overlay_mode_reset", _patched_request_overlay_mode_reset)
    monkeypatch.setattr(widget, "_prepare_engine_for_mode_reset", lambda: None)

    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    assert reset_requests["count"] == 1


@pytest.mark.qt
def test_mode_cycle_without_transitions_behaves_like_cold_start(qt_app, qtbot, monkeypatch):
    """Disabling transitions should still make double-click cycles match a full reset."""

    fake_engine = _FakeEngine()
    fake_engine._smoothed_bars = [0.5] * 8  # type: ignore[attr-defined]

    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    # Seed bars so we can measure parity after cycling
    widget._display_bars = [0.25] * 8  # type: ignore[attr-defined]
    widget._target_bars = [0.5] * 8  # type: ignore[attr-defined]
    widget._last_smooth_ts = 123.0  # type: ignore[attr-defined]

    # Execute cycle directly (simulates double-click when transitions off)
    mode_transition.cycle_mode(widget)

    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    fade = mode_transition.mode_transition_fade_factor(widget, now)

    # Cold reset should run while transition remains mid-fade (phase 3 waiting).
    assert widget._mode_transition_phase == 3
    assert fade == pytest.approx(0.0)
    assert widget._mode_transition_ts == pytest.approx(now)
    assert len(widget._display_bars) == widget._bar_count
    assert len(widget._target_bars) == widget._bar_count
    assert all(v == 0.0 for v in widget._display_bars)
    assert all(v == 0.0 for v in widget._target_bars)
    assert widget._last_smooth_ts == pytest.approx(0.0)


@pytest.mark.qt
def test_mode_cycle_preserves_transition_resume_ts(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    # Initiate a mode cycle
    assert mode_transition.cycle_mode(widget) is True

    prev_ts = widget._mode_transition_ts
    assert prev_ts > 0.0

    # Fast-forward fade-out completion
    now = prev_ts + widget._mode_transition_duration + 0.05
    fade = mode_transition.mode_transition_fade_factor(widget, now)

    assert fade == pytest.approx(0.0)
    assert widget._mode_transition_phase == 3
    assert widget._mode_transition_ts == pytest.approx(now)
    assert widget._mode_transition_resume_ts == pytest.approx(now)


@pytest.mark.qt
def test_cold_reset_ignores_transition_resume(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=6)
    qtbot.addWidget(widget)

    widget._mode_transition_phase = 0
    widget._mode_transition_ts = 0.0
    widget._mode_transition_resume_ts = 42.0

    widget._reset_visualizer_state(clear_overlay=False, replay_cached=False)

    assert widget._mode_transition_ts == 0.0
    assert widget._mode_transition_resume_ts == 0.0


@pytest.mark.qt
def test_clear_gl_overlay_destroys_overlay(qt_app, qtbot):
    class _PixelShiftStub:
        def __init__(self) -> None:
            self.unregistered: list[QWidget] = []

        def unregister_widget(self, widget: QWidget) -> None:
            self.unregistered.append(widget)

    class _OverlayStub(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.hide_calls = 0
            self.cleanup_calls = 0
            self.delete_calls = 0

        def hide(self) -> None:  # type: ignore[override]
            self.hide_calls += 1

        def cleanup_gl(self) -> None:
            self.cleanup_calls += 1

        def deleteLater(self) -> None:  # type: ignore[override]
            self.delete_calls += 1

    class _OverlayParent(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self._spotify_bars_overlay = _OverlayStub()
            self._pixel_shift_manager = _PixelShiftStub()

    parent = _OverlayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    widget.setGraphicsEffect(QGraphicsDropShadowEffect(widget))

    widget._clear_gl_overlay()

    assert parent._spotify_bars_overlay is None
    stub: _OverlayStub = parent._pixel_shift_manager.unregistered[0]  # type: ignore[index]
    assert stub.hide_calls == 1
    assert stub.cleanup_calls == 1
    assert stub.delete_calls == 1


@pytest.mark.qt
def test_shadow_cache_invalidation_clears_transient_effect_once_per_cycle(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    widget._pending_shadow_cache_invalidation = True  # type: ignore[attr-defined]
    widget.setGraphicsEffect(QGraphicsDropShadowEffect(widget))

    widget._invalidate_shadow_cache_if_needed()

    assert widget.graphicsEffect() is None
    assert widget._pending_shadow_cache_invalidation is False  # type: ignore[attr-defined]


@pytest.mark.qt
def test_spotify_visualizer_setting_uses_painted_frame_shadow(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)
    widget.resize(320, 160)
    widget.set_bar_style(
        bg_color=QColor(16, 16, 16, 255),
        bg_opacity=0.7,
        border_color=QColor(255, 255, 255, 230),
        border_width=3,
        show_background=True,
    )
    widget.set_shadow_config({"enabled": True})

    assert widget.uses_painted_frame_shadow() is True
    assert widget.graphicsEffect() is None
    pixmap = widget._ensure_painted_frame_shadow_pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()

    widget.set_shadow_config({"enabled": False})
    assert widget.uses_painted_frame_shadow() is False


@pytest.mark.qt
def test_spotify_visualizer_secondary_stage_defers_hot_start_until_triggered(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()
    anchor.show()
    anchor.show()

    class _FakeTimer:
        def stop(self) -> None:
            return None

    class _FakeThreadManager:
        def __init__(self) -> None:
            self.calls: list[int] = []

        def schedule_recurring(self, interval_ms: int, callback):
            self.calls.append(interval_ms)
            return _FakeTimer()

    fake_engine = _FakeEngine(bar_count=14)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=14)
    vis.set_thread_manager(_FakeThreadManager())
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is True
    assert fake_engine.acquired == 0
    assert vis._bars_timer is None
    assert fade_calls == []

    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is False
    assert vis._startup_hot_start_started is True
    assert vis._startup_reveal_pending is True
    assert fake_engine.acquired == 1
    assert fake_engine.playback_states[-1] is False
    assert vis._bars_timer is not None
    assert fade_calls == []

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_self_registers_secondary_stage_when_parent_supports_it(qt_app, qtbot, monkeypatch):
    class _Parent(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.secondary_starters: list[Callable[[], None]] = []

        def register_spotify_secondary_fade(self, starter) -> None:
            self.secondary_starters.append(starter)

    parent = _Parent()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=12)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=12)
    vis.set_anchor_media_widget(anchor)
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    assert vis._spotify_secondary_stage_registered is True
    assert vis._startup_secondary_stage_pending is True
    assert fake_engine.acquired == 0
    assert len(parent.secondary_starters) == 1

    parent.secondary_starters[0]()
    qt_app.processEvents()

    assert fake_engine.acquired == 1
    assert vis._startup_secondary_stage_pending is False

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_first_fresh_frame_finishes_staged_reveal(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    vis._spotify_playing = True

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_reveal_pending is True
    assert vis._waiting_for_fresh_frame is True

    vis._startup_reveal_not_before_ts = 0.0
    vis._on_first_frame_after_cold_start()

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_anchor_visibility_can_release_secondary_stage(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    assert fake_engine.acquired == 0
    assert vis._startup_secondary_stage_pending is True

    anchor.show()
    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0
    vis.sync_visibility_with_anchor()
    qt_app.processEvents()

    assert fake_engine.acquired == 1
    assert vis._startup_secondary_stage_pending is False
    assert vis._startup_reveal_pending is True

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_anchor_sync_respects_parent_secondary_stage_deadline(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    parent._overlay_fade_expected = {"clock", "weather"}
    parent._overlay_fade_started = False

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0
    vis.sync_visibility_with_anchor()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is True
    assert fake_engine.acquired == 0

    parent._overlay_fade_started = True
    parent._spotify_secondary_not_before_ts = time.monotonic() + 60.0
    vis.sync_visibility_with_anchor()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is True
    assert fake_engine.acquired == 0

    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0
    vis.sync_visibility_with_anchor()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is False
    assert fake_engine.acquired == 1

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_secondary_stage_prewarms_overlay_before_reveal(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    prewarm_calls: list[str] = []
    monkeypatch.setattr(vis, "_prewarm_parent_overlay", lambda: prewarm_calls.append("prewarm"))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert prewarm_calls == ["prewarm"]
    assert vis._startup_reveal_pending is True

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_fresh_frame_waits_for_minimum_reveal_delay(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    vis._spotify_playing = True

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    vis._startup_reveal_not_before_ts = time.monotonic() + 60.0
    vis._on_first_frame_after_cold_start()

    assert vis._startup_reveal_pending is True
    assert fade_calls == []

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_fresh_frame_schedules_ready_driven_reveal_after_min_delay(
    qt_app,
    qtbot,
    monkeypatch,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    vis._spotify_playing = True

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    vis._startup_reveal_not_before_ts = time.monotonic() + 0.05
    vis._on_first_frame_after_cold_start()

    assert vis._startup_reveal_pending is True
    assert vis._startup_reveal_ready_token == vis._startup_reveal_token
    assert fade_calls == []

    qtbot.wait(120)
    qt_app.processEvents()

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_startup_flags_delegate_to_shared_startup_contract(qt_app):
    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)

    vis._startup_secondary_stage_pending = True
    vis._startup_reveal_token = 7
    vis._startup_reveal_not_before_ts = 12.5

    assert vis._startup_phase.secondary_stage_pending is True
    assert vis._startup_phase.reveal_token == 7
    assert vis._startup_phase.reveal_not_before_ts == pytest.approx(12.5)

    vis._startup_phase.wake_deferred = True

    assert vis._startup_wake_deferred is True
    vis.deleteLater()


@pytest.mark.qt
def test_spotify_visualizer_fallback_reveal_waits_for_playing_state_when_startup_begins_paused(
    qt_app,
    qtbot,
    monkeypatch,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True

    fade_calls: list[int] = []
    def _record_fade(duration_ms=1500):
        fade_calls.append(duration_ms)
        vis.show()
    monkeypatch.setattr(vis, "_start_widget_fade_in", _record_fade)

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_require_playing_before_reveal is True
    vis._startup_reveal_not_before_ts = 0.0
    vis._finish_staged_startup_reveal(reason="fallback_timer", allow_waiting_fallback=True)

    assert vis._startup_reveal_pending is True
    assert fade_calls == []

    vis._waiting_for_fresh_frame = False
    vis.handle_media_update({"state": "playing"})

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_play_transition_still_waits_for_fresh_frame_when_startup_begins_paused(
    qt_app,
    qtbot,
    monkeypatch,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_require_playing_before_reveal is True
    vis._startup_reveal_not_before_ts = 0.0
    vis.handle_media_update({"state": "playing"})

    assert vis._startup_require_playing_before_reveal is False
    assert vis._startup_reveal_pending is True
    assert fade_calls == []

    vis._on_first_frame_after_cold_start()

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

    vis.stop()

@pytest.mark.qt
def test_spotify_visualizer_media_update_sets_playing_state(qt_app):
    """Visualizer should track playing state from media updates."""
    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)
    
    vis._spotify_playing = True
    vis.handle_media_update({"state": "paused"})
    assert vis._spotify_playing is False
    
    vis.handle_media_update({"state": "playing"})
    assert vis._spotify_playing is True
    
    vis.deleteLater()


@pytest.mark.qt
def test_spotify_visualizer_media_update_provider_neutral_musicbee_payload(qt_app):
    """Playback gating must follow the active provider payload, not provider name."""
    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)

    vis._spotify_playing = False
    vis.handle_media_update({"state": "playing", "app_name": "MusicBee"})
    assert vis._spotify_playing is True

    vis.handle_media_update({"state": "paused", "app_name": "MusicBee"})
    assert vis._spotify_playing is False

    vis.deleteLater()


@pytest.mark.qt
def test_spotify_visualizer_paused_update_keeps_visible_anchor_path(qt_app, qtbot, monkeypatch):
    """Paused retained-media updates must stop reactivity without hiding the widget."""
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)
    anchor.show()

    engine_states = []
    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis._engine = SimpleNamespace(set_playback_state=lambda playing: engine_states.append(bool(playing)))
    vis.set_anchor_media_widget(anchor)
    vis._enabled = True
    vis.show()

    hide_calls = []
    fade_calls = []
    monkeypatch.setattr(vis, "hide", lambda: hide_calls.append(True))
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.handle_media_update({"state": "paused"})

    assert vis._spotify_playing is False
    assert engine_states == [False]
    assert hide_calls == []
    assert fade_calls == []

    vis.deleteLater()


@pytest.mark.qt
def test_spotify_visualizer_defers_wake_until_staged_hot_start(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    anchor = QWidget(parent)

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    vis.handle_media_update({"state": "playing", "artwork_url": "art://wake"})

    assert vis._startup_secondary_stage_pending is True
    assert vis._startup_wake_deferred is True
    assert fake_engine.wake_calls == 0

    anchor.show()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_secondary_stage_pending is False
    assert vis._startup_wake_deferred is False
    assert fake_engine.wake_calls == 0
    assert fake_engine.playback_states[-1] is True

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_start_seeds_playback_from_anchor_cache(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    class _Anchor(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.refresh_requests = 0
            self._last_info = SimpleNamespace(
                title="Track",
                artist="Artist",
                album="Album",
                state=SimpleNamespace(value="playing"),
                artwork_url="art://seed",
            )

        def refresh_playback_state(self) -> None:
            self.refresh_requests += 1

    anchor = _Anchor(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    assert vis._spotify_playing is True
    assert fake_engine.playback_states[-1] is True
    assert anchor.refresh_requests == 0

    vis.stop()


@pytest.mark.qt
def test_spotify_visualizer_start_requests_media_refresh_when_anchor_cache_missing(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    class _Anchor(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.refresh_requests = 0
            self._last_info = None

        def refresh_playback_state(self) -> None:
            self.refresh_requests += 1

    anchor = _Anchor(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    assert anchor.refresh_requests == 1
    assert fake_engine.playback_states[-1] is False

    vis.stop()
