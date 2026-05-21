from __future__ import annotations

import time
from typing import Callable

import pytest
from types import SimpleNamespace

from utils.lockfree import TripleBuffer
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key
from core.settings.visualizer_presets import get_custom_preset_index
from widgets.spotify_visualizer import bar_computation
from widgets.spotify_visualizer import config_applier
from widgets.spotify_visualizer import mode_transition
from widgets.spotify_visualizer import tick_helpers
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


def test_compute_snapshot_is_bounded_and_ignores_unrelated_private_state(np_module):
    class _ExplodingCopy:
        def __copy__(self):
            raise AssertionError("unrelated private state should not be copied")

        def __deepcopy__(self, memo):
            raise AssertionError("unrelated private state should not be copied")

    worker = _make_audio_worker(np_module)
    worker._unrelated_private_runtime_owner = _ExplodingCopy()  # type: ignore[attr-defined]

    snapshot = worker.make_compute_snapshot()

    assert snapshot._manual_floor == pytest.approx(worker._manual_floor)  # type: ignore[attr-defined]
    assert snapshot._np is np_module
    assert not hasattr(snapshot, "_unrelated_private_runtime_owner")


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


def test_audio_worker_block_size_change_restarts_running_capture(np_module):
    worker = _make_audio_worker(np_module)
    backend = SimpleNamespace(_config=SimpleNamespace(block_size=256), restarts=0)

    def _restart():
        backend.restarts += 1
        return True

    backend.restart = _restart
    worker._backend = backend  # type: ignore[attr-defined]
    worker._running = True  # type: ignore[attr-defined]
    worker._preferred_block_size = 256  # type: ignore[attr-defined]

    worker.set_audio_block_size(128)

    assert worker._preferred_block_size == 128  # type: ignore[attr-defined]
    assert backend._config.block_size == 128
    assert backend.restarts == 1


def test_audio_worker_block_size_noop_does_not_restart_capture(np_module):
    worker = _make_audio_worker(np_module)
    backend = SimpleNamespace(_config=SimpleNamespace(block_size=256), restarts=0)

    def _restart():
        backend.restarts += 1
        return True

    backend.restart = _restart
    worker._backend = backend  # type: ignore[attr-defined]
    worker._running = True  # type: ignore[attr-defined]
    worker._preferred_block_size = 256  # type: ignore[attr-defined]

    worker.set_audio_block_size(256)

    assert worker._preferred_block_size == 256  # type: ignore[attr-defined]
    assert backend._config.block_size == 256
    assert backend.restarts == 0


def test_update_timer_interval_does_not_thrash_same_target_when_actual_is_jittered():
    class _Timer:
        def __init__(self):
            self.calls: list[int] = []

        def setInterval(self, interval: int):
            self.calls.append(interval)

    timer = _Timer()
    widget = SimpleNamespace(
        _bars_timer=timer,
        _target_timer_interval_ms=11,
        _current_timer_interval_ms=13,
    )

    tick_helpers.update_timer_interval(widget, 90.0)

    assert timer.calls == []
    assert widget._target_timer_interval_ms == 11
    assert widget._current_timer_interval_ms == 13


def test_latency_logging_skips_disabled_widget(monkeypatch):
    engine = SimpleNamespace(_last_audio_ts=1.0, _last_smooth_ts=1.0)
    widget = SimpleNamespace(
        _enabled=False,
        _latency_last_log_ts=0.0,
        _latency_log_interval=10.0,
        _latency_error_ms=150.0,
        _latency_warn_ms=80.0,
        _latency_last_signature=None,
        _mode_transition_phase=0,
        _vis_mode_str="spectrum",
        _mode_transition_pending=None,
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tick_pipeline.logger,
        "error",
        lambda msg: calls.append(("error", msg)),
    )
    monkeypatch.setattr(
        tick_pipeline.logger,
        "warning",
        lambda msg: calls.append(("warning", msg)),
    )

    tick_pipeline.log_audio_latency_metrics(widget, engine, now_ts=5.0, force_reason=None)

    assert calls == []


def test_latency_logging_suppresses_pre_ready_startup_warning(monkeypatch):
    engine = SimpleNamespace(
        _last_audio_ts=5.0,
        _last_smooth_ts=-1.0,
        get_generation_id=lambda: 8,
        get_latest_generation_with_frame=lambda: 7,
    )
    widget = SimpleNamespace(
        _enabled=True,
        _latency_audio_ready=False,
        _latency_activation_started_ts=10.0,
        _latency_last_log_ts=0.0,
        _latency_log_interval=10.0,
        _latency_error_ms=150.0,
        _latency_warn_ms=80.0,
        _latency_last_signature=None,
        _mode_transition_phase=0,
        _vis_mode_str="bubble",
        _mode_transition_pending=None,
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    monkeypatch.setattr(tick_pipeline.logger, "error", lambda msg: calls.append(("error", msg)))
    monkeypatch.setattr(tick_pipeline.logger, "warning", lambda msg: calls.append(("warning", msg)))

    tick_pipeline.log_audio_latency_metrics(widget, engine, now_ts=15.0, force_reason=None)

    assert calls == []
    assert widget._latency_audio_ready is False


def test_latency_logging_warns_once_current_activation_is_ready(monkeypatch):
    engine = SimpleNamespace(
        _last_audio_ts=0.0,
        _last_smooth_ts=14.9,
        get_generation_id=lambda: 8,
        get_latest_generation_with_frame=lambda: 8,
    )
    widget = SimpleNamespace(
        _enabled=True,
        _latency_audio_ready=False,
        _latency_activation_started_ts=10.0,
        _latency_last_log_ts=0.0,
        _latency_log_interval=10.0,
        _latency_error_ms=150.0,
        _latency_warn_ms=80.0,
        _latency_last_signature=None,
        _mode_transition_phase=0,
        _vis_mode_str="bubble",
        _mode_transition_pending=None,
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    monkeypatch.setattr(tick_pipeline.logger, "error", lambda msg: calls.append(("error", msg)))
    monkeypatch.setattr(tick_pipeline.logger, "warning", lambda msg: calls.append(("warning", msg)))

    tick_pipeline.log_audio_latency_metrics(widget, engine, now_ts=15.0, force_reason=None)

    assert widget._latency_audio_ready is True
    assert calls == [("warning", "[SPOTIFY_VIS][LATENCY] lag_ms=100.0 mode=bubble transition_phase=0 pending=<none>")]


def test_latency_logging_force_probe_remains_active_before_ready(monkeypatch):
    engine = SimpleNamespace(
        _last_audio_ts=5.0,
        _last_smooth_ts=-1.0,
        get_generation_id=lambda: 8,
        get_latest_generation_with_frame=lambda: 7,
    )
    widget = SimpleNamespace(
        _enabled=True,
        _latency_audio_ready=False,
        _latency_activation_started_ts=10.0,
        _latency_last_log_ts=0.0,
        _latency_log_interval=10.0,
        _latency_error_ms=150.0,
        _latency_warn_ms=80.0,
        _latency_last_signature=None,
        _mode_transition_phase=0,
        _vis_mode_str="bubble",
        _mode_transition_pending=None,
    )
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(tick_pipeline, "is_viz_logging_enabled", lambda: True)
    monkeypatch.setattr(tick_pipeline.logger, "error", lambda msg: calls.append(("error", msg)))
    monkeypatch.setattr(tick_pipeline.logger, "warning", lambda msg: calls.append(("warning", msg)))

    tick_pipeline.log_audio_latency_metrics(widget, engine, now_ts=15.0, force_reason="transition_start")

    assert widget._latency_audio_ready is False
    assert calls == [("error", "[!!!!][SPOTIFY_VIS][LATENCY] lag_ms=10000.0 mode=bubble transition_phase=0 pending=<none> trigger=transition_start")]


def test_bars_snapshot_gate_skips_emit_when_logger_info_disabled(monkeypatch):
    worker = SimpleNamespace(
        _bars_log_last_ts=0.0,
        _bars_log_interval=5.0,
    )
    monkeypatch.setattr(bar_computation, "is_viz_diagnostics_enabled", lambda: True)
    monkeypatch.setattr(bar_computation.logger, "isEnabledFor", lambda level: False)

    assert bar_computation._should_emit_bars_snapshot(worker, now=10.0) is False


def test_stop_legacy_clears_latency_probe_state():
    timer_stopped: list[bool] = []

    class _Timer:
        def stop(self):
            timer_stopped.append(True)

    engine = SimpleNamespace(release=lambda: None)
    widget = SimpleNamespace(
        _enabled=True,
        _latency_pending_probe=["mode_switch"],
        _latency_last_signature=("error", 123.4, "spectrum", 0, None, None),
        _latency_last_log_ts=99.0,
        _startup_secondary_stage_pending=False,
        _startup_hot_start_started=False,
        _startup_wake_deferred=False,
        _startup_require_playing_before_reveal=False,
        _startup_reveal_pending=False,
        _startup_reveal_token=3,
        _startup_reveal_ready_token=3,
        _bar_count=35,
        _engine=engine,
        _bars_timer=_Timer(),
        _using_animation_ticks=True,
        detach_from_animation_manager=lambda: None,
        _log_perf_snapshot=lambda reset=False: None,
        hide=lambda: None,
        _reset_latency_diagnostics=lambda: (
            widget._latency_pending_probe.clear(),
            setattr(widget, "_latency_last_signature", None),
            setattr(widget, "_latency_last_log_ts", 0.0),
        ),
    )

    from widgets.spotify_visualizer import startup_staging

    startup_staging.stop_legacy(widget)

    assert widget._enabled is False
    assert widget._latency_pending_probe == []
    assert widget._latency_last_signature is None
    assert widget._latency_last_log_ts == 0.0
    assert timer_stopped == [True]


def test_shared_beat_engine_registry_reconfigures_single_engine_across_bar_counts():
    registry = BeatEngineRegistry()
    engine = registry.get_engine(36)
    same_engine = registry.get_engine(40)

    assert same_engine is engine
    assert engine._bar_count == 40


class _FakeEngine:
    def __init__(self, bar_count: int = 16) -> None:
        self._audio_buffer = object()
        self._audio_worker = SimpleNamespace(_kick_lane_gain=1.0)
        self._bars_result_buffer = object()
        self.last_floor_config = (True, 0.12)
        self.last_sensitivity_config = (True, 1.0)
        self.last_energy_boost = None
        self.last_input_gain = None
        self.last_agc_strength = None
        self.process_supervisor = None
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

    def set_process_supervisor(self, supervisor) -> None:
        self.process_supervisor = supervisor

    def set_energy_boost(self, boost: float) -> None:
        self.last_energy_boost = float(boost)

    def set_input_gain(self, gain: float) -> None:
        self.last_input_gain = float(gain)

    def set_agc_strength(self, value: float) -> None:
        self.last_agc_strength = float(value)

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


def _patch_shared_engine(monkeypatch, provider: Callable[..., object]) -> None:
    """Patch both widget-local and extracted beat-engine resolution seams."""

    monkeypatch.setattr(vis_mod, "get_shared_spotify_beat_engine", provider)
    import widgets.spotify_visualizer.beat_engine as beat_engine_mod
    import widgets.spotify_visualizer.runtime_config as runtime_config_mod

    monkeypatch.setattr(beat_engine_mod, "get_shared_spotify_beat_engine", provider)
    monkeypatch.setattr(runtime_config_mod, "get_shared_spotify_beat_engine", provider)


@pytest.mark.qt
def test_resize_bar_buffers_reuses_existing_engine_and_reconfigures_bar_count(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    engine_36 = _FakeEngine(bar_count=36)
    engine_40 = _FakeEngine(bar_count=40)

    def _fake_get_engine(count: int):
        return engine_36 if int(count) == 36 else engine_40

    _patch_shared_engine(monkeypatch, _fake_get_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=36)
    vis._enabled = True
    engine_36.acquired = 1

    vis._resize_bar_buffers(40)

    assert vis._engine is engine_36
    assert engine_36.reconfigure_calls == [40]
    assert engine_40.acquired == 0


@pytest.mark.qt
def test_resize_bar_buffers_applies_authoritative_technical_config_when_ready(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    engine = _FakeEngine(bar_count=8)
    engine._audio_worker = SimpleNamespace()
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=8, initial_mode="bubble")
    vis._enabled = True
    vis._settings_model = object()
    vis._technical_config_cache = {
        "bubble": {
            "bar_count": 24,
            "dynamic_floor": False,
            "manual_floor": 0.41,
            "adaptive_sensitivity": False,
            "sensitivity": 0.72,
            "audio_block_size": 256,
            "dynamic_range_enabled": False,
            "agc_strength": 0.5,
            "input_gain": 1.0,
            "kick_lane_gain": 1.0,
            "transient_pulse_gain": 1.0,
            "transient_clamp": 1.5,
            "bubble_transient_mix_bass": 0.75,
            "bubble_transient_mix_vocal": 0.25,
        }
    }
    vis._spotify_playing = True
    vis._engine = engine

    vis._resize_bar_buffers(24)

    assert vis._engine is engine
    assert engine.reconfigure_calls == [24]
    assert vis._last_floor_config == (False, pytest.approx(0.41))
    assert vis._last_sensitivity_config == (False, pytest.approx(0.72))
    assert vis._last_audio_block_size == 256
    assert engine.started == 1


@pytest.mark.qt
def test_runtime_config_setters_remain_noop_safe_when_engine_resolution_fails(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    import widgets.spotify_visualizer.runtime_config as runtime_config_mod

    monkeypatch.setattr(
        runtime_config_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: (_ for _ in ()).throw(RuntimeError("no engine")),
    )

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=24)
    vis._engine = None
    ensure_calls: list[bool] = []
    vis._enabled = True
    monkeypatch.setattr(vis, "_ensure_tick_source", lambda: ensure_calls.append(True))

    vis.set_process_supervisor(object())
    vis.apply_floor_config(False, 0.55)
    vis.apply_sensitivity_config(False, 1.25)
    vis._apply_energy_boost(1.4)
    vis._apply_input_gain(1.15)
    vis._apply_audio_block_size(512)

    assert ensure_calls == [True]
    assert vis._last_floor_config == (False, pytest.approx(0.55))
    assert vis._last_sensitivity_config == (False, pytest.approx(1.25))
    assert vis._last_energy_boost == pytest.approx(1.4)
    assert vis._last_input_gain == pytest.approx(1.15)
    assert vis._last_audio_block_size == 512


@pytest.mark.qt
def test_runtime_config_bridge_forwards_engine_and_worker_updates(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    engine = _FakeEngine(bar_count=24)
    block_sizes: list[int] = []
    engine._audio_worker = SimpleNamespace(
        _kick_lane_gain=1.0,
        set_audio_block_size=lambda value: block_sizes.append(int(value)),
    )
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=24)
    thread_manager = object()
    supervisor = object()

    vis.set_thread_manager(thread_manager)
    vis.set_process_supervisor(supervisor)
    vis.apply_floor_config(False, 0.44)
    vis.apply_sensitivity_config(False, 1.7)
    vis._apply_energy_boost(1.33)
    vis._apply_input_gain(1.25)
    vis._apply_agc_strength(0.4)
    vis._apply_audio_block_size(256)

    assert vis._engine is engine
    assert engine.thread_manager is thread_manager
    assert engine.process_supervisor is supervisor
    assert engine.last_floor_config == (False, 0.44)
    assert engine.last_sensitivity_config == (False, 1.7)
    assert engine.last_energy_boost == pytest.approx(1.33)
    assert engine.last_input_gain == pytest.approx(1.25)
    assert engine.last_agc_strength == pytest.approx(0.4)
    assert block_sizes == [256]


@pytest.mark.qt
def test_set_thread_manager_defers_authoritative_replay_until_settings_model_ready(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    engine = _FakeEngine(bar_count=24)
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=24, initial_mode="bubble")
    replay_calls: list[object] = []
    monkeypatch.setattr(vis, "_replay_engine_config", lambda replay_engine: replay_calls.append(replay_engine))

    first_thread_manager = object()
    vis.set_thread_manager(first_thread_manager)

    assert engine.thread_manager is first_thread_manager
    assert replay_calls == []

    vis._settings_model = object()
    vis._technical_config_cache = {"bubble": {}}

    second_thread_manager = object()
    vis.set_thread_manager(second_thread_manager)

    assert engine.thread_manager is second_thread_manager
    assert replay_calls == [engine]


@pytest.mark.qt
def test_set_thread_manager_applies_authoritative_technical_config_when_ready(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    engine = _FakeEngine(bar_count=8)
    engine._audio_worker = SimpleNamespace()
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=8, initial_mode="bubble")
    vis._settings_model = object()
    vis._technical_config_cache = {
        "bubble": {
            "bar_count": 24,
            "dynamic_floor": False,
            "manual_floor": 0.29,
            "adaptive_sensitivity": False,
            "sensitivity": 0.63,
            "audio_block_size": 256,
            "dynamic_range_enabled": False,
            "agc_strength": 0.5,
            "input_gain": 1.0,
            "kick_lane_gain": 1.0,
            "transient_pulse_gain": 1.0,
            "transient_clamp": 1.5,
            "bubble_transient_mix_bass": 0.75,
            "bubble_transient_mix_vocal": 0.25,
        }
    }

    vis.set_thread_manager(object())

    assert vis._bar_count == 24
    assert vis._last_floor_config[0] is False
    assert vis._last_floor_config[1] == pytest.approx(0.29)
    assert vis._last_sensitivity_config[0] is False
    assert vis._last_sensitivity_config[1] == pytest.approx(0.63)
    assert vis._last_audio_block_size == 256


@pytest.mark.qt
def test_set_settings_model_replays_engine_when_authoritative_engine_exists(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    engine = _FakeEngine(bar_count=8)
    engine._audio_worker = SimpleNamespace()
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8, initial_mode="oscilloscope")
    widget._engine = engine
    replay_calls: list[object] = []
    monkeypatch.setattr(widget, "_replay_engine_config", lambda replay_engine: replay_calls.append(replay_engine))

    model = SpotifyVisualizerSettings(
        mode="oscilloscope",
        bar_count=8,
        oscilloscope_bar_count=24,
        oscilloscope_dynamic_floor=False,
        oscilloscope_manual_floor=0.21,
    )

    widget.set_settings_model(model)

    assert replay_calls == [engine]


@pytest.mark.qt
def test_spectrum_gpu_push_extras_dict_is_reused(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)

    engine = _FakeEngine(bar_count=24)
    _patch_shared_engine(monkeypatch, lambda *_: engine)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=24)
    widget._engine = engine
    widget._heartbeat_intensity = 0.25

    first = config_applier.build_gpu_push_extra_kwargs(widget, "spectrum", engine)
    first_id = id(first)
    assert first["heartbeat_intensity"] == pytest.approx(0.25)

    widget._heartbeat_intensity = 0.75
    second = config_applier.build_gpu_push_extra_kwargs(widget, "spectrum", engine)

    assert id(second) == first_id
    assert second["heartbeat_intensity"] == pytest.approx(0.75)


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


class _DeferredComputeThreadManager:
    def __init__(self) -> None:
        self.tasks: list[tuple[Callable[[], object], Callable[[object], None] | None]] = []

    def submit_compute_task(self, fn, callback=None) -> None:
        self.tasks.append((fn, callback))

    def run_next(self) -> object:
        fn, callback = self.tasks.pop(0)
        result = SimpleNamespace(success=True, result=fn())
        if callback is not None:
            callback(result)
        return result


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
    aw._pre_agc_control_norm = 9.0
    aw._pre_agc_control_bass = 0.91
    aw._pre_agc_control_mid = 0.82
    aw._pre_agc_control_treble = 0.73


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
    assert aw._pre_agc_control_norm == pytest.approx(1.0)
    assert aw._pre_agc_control_bass == pytest.approx(0.0)
    assert aw._pre_agc_control_mid == pytest.approx(0.0)
    assert aw._pre_agc_control_treble == pytest.approx(0.0)


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

    assert parent._spotify_bars_overlay is None
    assert widget._vis_mode is VisualizerMode.OSCILLOSCOPE
    assert widget._waiting_for_fresh_engine_frame is True


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


@pytest.mark.qt
def test_bubble_dispatch_reads_pre_agc_snapshot_once_per_tick(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    pre_agc_calls = {"count": 0}

    def _pre_agc_snapshot():
        pre_agc_calls["count"] += 1
        return SimpleNamespace(bass=0.61, mid=0.41, high=0.21, overall=0.51)

    fake_engine.get_pre_agc_energy_bands = _pre_agc_snapshot
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

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())

    assert pre_agc_calls["count"] == 1


@pytest.mark.qt
def test_bubble_dispatch_reuses_cached_payload_dicts_between_ticks(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine.get_pre_agc_energy_bands = lambda: SimpleNamespace(bass=0.21, mid=0.31, high=0.41, overall=0.51)
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

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())
    first_call = widget._thread_manager.calls[-1]
    first_energy = first_call["args"][1]
    first_settings = first_call["args"][2]
    first_pulse = first_call["args"][3]

    widget._bubble_compute_pending = False
    widget._bubble_stream_constant_speed = 0.83
    widget._bubble_big_bass_pulse = 0.92
    widget._bubble_last_tick_ts = time.time() - 0.016

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())
    second_call = widget._thread_manager.calls[-1]

    assert second_call["args"][1] is first_energy
    assert second_call["args"][2] is first_settings
    assert second_call["args"][3] is first_pulse
    assert second_call["args"][2]["bubble_stream_constant_speed"] == pytest.approx(0.83)
    assert second_call["args"][3]["big_bass_pulse"] == pytest.approx(0.92)


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
    widget._engine = fake_engine
    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    assert widget._waiting_for_fresh_engine_frame is True
    assert widget._pending_engine_generation == widget._mode_teardown_target_generation
    assert fake_engine.get_latest_generation_with_frame() < widget._pending_engine_generation

    parent.reset_pushes()
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is True
    assert parent.frames == []

    fake_engine.publish_frame([0.75] * widget._bar_count)
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is False
    assert parent.frames


@pytest.mark.qt
def test_fresh_engine_frame_gate_blocks_gpu_push_after_mode_reset(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()
    widget._engine = fake_engine

    widget._prepare_engine_for_mode_reset()

    assert widget._waiting_for_fresh_engine_frame is True
    assert widget._pending_engine_generation == widget._mode_teardown_target_generation
    assert fake_engine.get_latest_generation_with_frame() < widget._pending_engine_generation

    parent.reset_pushes()
    widget._on_tick()

    assert parent.frames == []
    assert widget._waiting_for_fresh_engine_frame is True

    fake_engine.publish_frame([0.66] * widget._bar_count)
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is False
    assert parent.frames, "GPU push should stay blocked until a fresh post-reset engine frame publishes"


@pytest.mark.qt
def test_osc_mode_switch_waits_for_fresh_waveform_generation(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed_bars = [0.4] * 8  # type: ignore[attr-defined]
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()
    widget._engine = fake_engine
    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    parent.reset_pushes()
    assert widget._pending_engine_generation == widget._mode_teardown_target_generation
    fake_engine._latest_generation_with_frame = widget._pending_engine_generation
    fake_engine._latest_generation_with_waveform = widget._pending_engine_generation - 1
    widget._on_tick()

    assert widget._waiting_for_fresh_engine_frame is True
    assert parent.frames == []

    fake_engine._latest_generation_with_waveform = widget._pending_engine_generation
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
    assert parent._spotify_bars_overlay is None

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
    assert parent._spotify_bars_overlay is None


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
def test_visualizer_preferred_height_defers_direct_resize_when_custom_rect_active(qt_app, qtbot):
    from PySide6.QtCore import QRect

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": {"position": "Custom"}}
            return default

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._custom_layout_local_rect = QRect(10, 20, 300, 160)
    widget._vis_mode = VisualizerMode.BLOB
    widget.setGeometry(0, 0, 300, 160)

    widget._apply_preferred_height()

    assert widget.height() == 160


@pytest.mark.qt
def test_visualizer_request_reposition_uses_anchor_media_in_custom_without_local_media(qt_app, qtbot):
    from PySide6.QtCore import QRect

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.resize(1280, 720)

    calls: list[tuple[object | None, int, int]] = []

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": {"position": "Custom"}}
            return default

    class _WidgetManager:
        def __init__(self):
            self._widgets = {}
            self._settings_manager = _Settings()

        def position_spotify_visualizer(self, vis, media, pw, ph):
            calls.append((media, pw, ph))

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = _WidgetManager()
    widget._custom_layout_local_rect = QRect(10, 20, 300, 160)
    anchor_media = SimpleNamespace()
    widget._anchor_media = anchor_media

    widget._request_reposition()

    assert calls == [(anchor_media, 1280, 720)]


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
def test_runtime_switch_paths_apply_target_technical_floor_for_all_modes(qt_app, qtbot, np_module):
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    ordered_modes = [
        getattr(VisualizerMode, desc.mode_id.upper())
        for desc in iter_visualizer_mode_descriptors()
        if getattr(VisualizerMode, desc.mode_id.upper(), None) is not None
    ]
    spotify_cfg = {"mode": "spectrum"}
    expected_floor: dict[str, float] = {}
    expected_sensitivity: dict[str, float] = {}
    for idx, mode in enumerate(ordered_modes):
        mode_id = mode.name.lower()
        spotify_cfg[get_preset_key(mode_id)] = get_custom_preset_index(mode_id)
        spotify_cfg[f"{mode_id}_bar_count"] = 18 + idx
        spotify_cfg[f"{mode_id}_dynamic_floor"] = False
        spotify_cfg[f"{mode_id}_manual_floor"] = 0.14 + idx * 0.07
        spotify_cfg[f"{mode_id}_adaptive_sensitivity"] = False
        spotify_cfg[f"{mode_id}_sensitivity"] = 0.55 + idx * 0.11
        expected_floor[mode_id] = spotify_cfg[f"{mode_id}_manual_floor"]
        expected_sensitivity[mode_id] = spotify_cfg[f"{mode_id}_sensitivity"]

    class _Settings:
        def get(self, key, default=None):
            if key == "widgets":
                return {"spotify_visualizer": dict(spotify_cfg)}
            return default

    engine = _SpotifyBeatEngine(18)
    engine._audio_worker._np = np_module
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=18)
    qtbot.addWidget(widget)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = False

    for idx, target in enumerate(ordered_modes):
        previous = ordered_modes[idx - 1]
        widget._vis_mode = previous
        widget._mode_transition_phase = 0
        widget._mode_transition_pending = None
        widget._last_floor_config = (False, 0.99)
        widget._last_sensitivity_config = (False, 2.25)
        engine._audio_worker.set_floor_config(False, 0.99)
        engine._audio_worker.set_sensitivity_config(False, 2.25)

        assert mode_transition.switch_to_mode(widget, target.name.lower()) is True
        now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
        mode_transition.mode_transition_fade_factor(widget, now)

        target_key = target.name.lower()
        assert widget._vis_mode is target
        assert engine._audio_worker._manual_floor == pytest.approx(expected_floor[target_key])
        assert engine._audio_worker._raw_bass_avg == pytest.approx(expected_floor[target_key])
        assert engine._audio_worker._last_floor_config == (
            False,
            pytest.approx(expected_floor[target_key]),
        )
        assert engine._audio_worker._last_sensitivity_config == (
            False,
            pytest.approx(expected_sensitivity[target_key]),
        )

    original_engine_id = id(widget._engine)
    for idx, target in enumerate(ordered_modes):
        previous = ordered_modes[idx - 1]
        widget._vis_mode = previous
        widget._mode_transition_phase = 0
        widget._mode_transition_pending = None
        engine._audio_worker.set_floor_config(False, 0.99)

        assert mode_transition.cycle_mode(widget) is True
        now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
        mode_transition.mode_transition_fade_factor(widget, now)

        assert widget._vis_mode is target
        assert id(widget._engine) == original_engine_id
        assert engine._audio_worker._manual_floor == pytest.approx(expected_floor[target.name.lower()])


@pytest.mark.qt
def test_widget_cycle_does_not_activate_target_before_overlay_teardown(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM

    fade_out_started: list[str] = []

    def _defer_fade_out(target, duration_ms=1200, on_complete=None):
        fade_out_started.append("started")

    monkeypatch.setattr(
        "widgets.spotify_visualizer.mode_transition.start_widget_fade_out",
        _defer_fade_out,
    )

    assert widget._cycle_mode() is True
    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert fade_out_started == ["started"]
    assert widget._vis_mode is VisualizerMode.SPECTRUM
    assert widget._mode_transition_pending is VisualizerMode.OSCILLOSCOPE
    assert parent._spotify_bars_overlay is not None

    mode_transition.on_mode_fade_out_complete(widget)

    assert widget._vis_mode is VisualizerMode.OSCILLOSCOPE
    assert widget._mode_transition_pending is None
    assert parent._spotify_bars_overlay is None
    assert widget._mode_teardown_block_until_ready is True


@pytest.mark.qt
def test_runtime_mode_activation_clears_widget_owned_visual_state(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    widget._devcurve_runtime_state = object()
    widget._devcurve_last_tick_ts = 123.0
    widget._devcurve_active_amplitude = 0.91
    widget._devcurve_curve_bass = [0.9, 0.8]
    widget._devcurve_specular_slot0 = [0.5, 0.4, 0.3, 0.2]
    widget._blob_shaper_runtime_profile = [0.8] * 8
    widget._blob_live_bass_energy = 0.77
    widget._sine_peak_bass = 0.66
    widget._heartbeat_intensity = 0.55

    mode_transition.reset_mode_owned_runtime_state(widget, reason="test")

    assert widget._devcurve_runtime_state is None
    assert widget._devcurve_last_tick_ts == pytest.approx(0.0)
    assert widget._devcurve_active_amplitude == pytest.approx(0.0)
    assert widget._devcurve_curve_bass == []
    assert widget._devcurve_specular_slot0 == [0.0, 0.0, 0.0, 0.0]
    assert widget._blob_shaper_runtime_profile is None
    assert widget._blob_live_bass_energy == pytest.approx(0.0)
    assert widget._sine_peak_bass == pytest.approx(0.0)
    assert widget._heartbeat_intensity == pytest.approx(0.0)


@pytest.mark.qt
def test_gpu_payload_carries_activation_generation_snapshot(qt_app, qtbot, np_module):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    engine = _SpotifyBeatEngine(10)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM

    samples = _synthetic_audio(np_module, hz=220.0, amp=0.30)
    engine._audio_buffer.publish(_AudioFrame(samples=samples, activation_id=engine.get_activation_id()))
    engine.tick()
    widget._display_bars = engine.get_smoothed_bars()

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is True
    frame = parent.frames[-1]
    assert frame["activation_id"] == engine.get_activation_id()
    assert frame["engine_generation"] == engine.get_generation_id()
    assert frame["latest_frame_generation"] == engine.get_latest_generation_with_frame()
    assert frame["latest_waveform_generation"] == engine.get_latest_generation_with_waveform()


@pytest.mark.qt
def test_first_frame_guard_warning_emits_on_overlay_generation_mismatch(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.25] * 6
    widget._display_bars_source_generation = 12
    widget._display_bars_source_activation = 12

    warnings: list[str] = []

    def _capture_warning(msg, *args, **kwargs):
        try:
            warnings.append(msg % args if args else str(msg))
        except Exception:
            warnings.append(str(msg))

    monkeypatch.setattr(tick_pipeline.logger, "warning", _capture_warning)

    tick_pipeline._warn_on_first_frame_guard_mismatch(widget, parent)

    assert any("[SPOTIFY_VIS][FIRST_FRAME_GUARD]" in message for message in warnings)
    assert any("overlay_generation_mismatch" in message for message in warnings)


@pytest.mark.qt
def test_first_frame_guard_does_not_warn_for_normal_waiting_frame_only(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.25] * 6
    widget._display_bars_source_generation = 12
    widget._display_bars_source_activation = 12
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = True

    overlay = type("Overlay", (), {"_activation_id": 12, "_engine_generation": 12})()
    parent._spotify_bars_overlay = overlay

    warnings: list[str] = []

    def _capture_warning(msg, *args, **kwargs):
        try:
            warnings.append(msg % args if args else str(msg))
        except Exception:
            warnings.append(str(msg))

    monkeypatch.setattr(tick_pipeline.logger, "warning", _capture_warning)

    tick_pipeline._warn_on_first_frame_guard_mismatch(widget, parent)

    assert warnings == []


@pytest.mark.qt
def test_first_frame_guard_does_not_warn_for_zero_data_staged_push(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.0] * 6
    widget._display_bars_source_generation = -1
    widget._display_bars_source_activation = 12
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = True

    overlay = type("Overlay", (), {"_activation_id": 99, "_engine_generation": None})()
    parent._spotify_bars_overlay = overlay

    warnings: list[str] = []

    def _capture_warning(msg, *args, **kwargs):
        try:
            warnings.append(msg % args if args else str(msg))
        except Exception:
            warnings.append(str(msg))

    monkeypatch.setattr(tick_pipeline.logger, "warning", _capture_warning)

    tick_pipeline._warn_on_first_frame_guard_mismatch(widget, parent)

    assert warnings == []


@pytest.mark.qt
def test_before_first_overlay_push_logs_once_per_source_signature(qt_app, qtbot):
    class _NotReadyParent(_FakeDisplayParent):
        def push_spotify_visualizer_frame(self, *_, **kwargs):
            self.frames.append(kwargs)
            return False

    parent = _NotReadyParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SINE_WAVE
    widget._display_bars = [0.25] * 6
    widget._display_bars_source_generation = 12
    widget._display_bars_source_activation = 34
    widget._pending_engine_generation = 12
    widget._pending_engine_activation_id = 34

    reasons: list[str] = []

    def _capture_render_state(*, reason: str):
        reasons.append(reason)

    widget._log_active_render_state_snapshot = _capture_render_state  # type: ignore[method-assign]

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is False
    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is False

    assert reasons == ["before_first_overlay_push"]
    assert widget._first_overlay_push_probe_key is not None

    widget._display_bars_source_generation = 13
    widget._pending_engine_generation = 13

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is False
    assert reasons == ["before_first_overlay_push", "before_first_overlay_push"]


@pytest.mark.qt
def test_animation_manager_listener_is_transition_scoped_and_resumes_timer_after_transition(qt_app, qtbot, monkeypatch):
    class _FakeAnimationManager:
        def __init__(self):
            self.listener = None
            self.removed = None

        def add_tick_listener(self, callback):
            self.listener = callback
            return 77

        def remove_tick_listener(self, callback_id: int) -> None:
            self.removed = callback_id

    class _TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = False

        def get_transition_snapshot(self):
            return {"running": self.running}

    parent = _TransitionParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    widget._enabled = True
    widget._bars_timer = None

    class _Timer:
        def __init__(self):
            self.active = True
            self.start_calls = 0
            self.stop_calls = 0

        def isActive(self):
            return self.active

        def start(self):
            self.active = True
            self.start_calls += 1

        def stop(self):
            self.active = False
            self.stop_calls += 1

    timer = _Timer()
    widget._bars_timer = timer

    ticks: list[str] = []
    monkeypatch.setattr(widget, "_on_tick", lambda: ticks.append("tick"))

    manager = _FakeAnimationManager()
    widget.attach_to_animation_manager(manager)

    assert widget._using_animation_ticks is False
    assert manager.listener is None

    tick_helpers.pause_timer_during_transition(widget, True)
    assert widget._using_animation_ticks is True
    assert manager.listener is not None
    assert timer.stop_calls == 1
    assert timer.isActive() is False

    parent.running = True
    manager.listener(0.016)
    assert ticks == ["tick"]

    parent.running = False
    manager.listener(0.016)

    assert widget._using_animation_ticks is False
    assert manager.removed == 77
    assert timer.start_calls == 1
    assert timer.isActive() is True

    widget.detach_from_animation_manager()


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
def test_stale_compute_job_cannot_commit_dsp_state_after_activation(qt_app, qtbot, np_module):
    engine = _SpotifyBeatEngine(24)
    engine._audio_worker._np = np_module
    thread_manager = _DeferredComputeThreadManager()
    engine.set_thread_manager(thread_manager)
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    old_activation = engine.get_activation_id()
    hot_samples = _synthetic_audio(np_module, hz=92.0, amp=0.95)
    engine._audio_buffer.publish(_AudioFrame(samples=hot_samples, activation_id=old_activation))
    engine.tick()

    assert len(thread_manager.tasks) == 1
    assert engine._compute_task_active is True

    engine.reset_smoothing_state()
    engine.reset_floor_state()
    reset_activation = engine.get_activation_id()
    reset_floor = engine._audio_worker._applied_noise_floor
    reset_env_short = engine._audio_worker._env_short
    reset_transient_bass = engine._audio_worker._transient_bass

    thread_manager.run_next()

    assert engine.get_activation_id() == reset_activation
    assert engine._audio_worker._activation_id == reset_activation
    assert engine._audio_worker._applied_noise_floor == pytest.approx(reset_floor)
    assert engine._audio_worker._env_short == pytest.approx(reset_env_short)
    assert engine._audio_worker._transient_bass == pytest.approx(reset_transient_bass)
    assert engine.get_latest_generation_with_frame() < engine.get_generation_id()
    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)


@pytest.mark.qt
def test_stale_audio_frame_with_old_activation_is_ignored(qt_app, qtbot, np_module):
    engine = _SpotifyBeatEngine(18)
    engine._audio_worker._np = np_module
    thread_manager = _DeferredComputeThreadManager()
    engine.set_thread_manager(thread_manager)
    engine.set_playback_state(True)

    old_activation = engine.get_activation_id()
    engine.reset_smoothing_state()

    hot_samples = _synthetic_audio(np_module, hz=110.0, amp=0.90)
    engine._audio_buffer.publish(_AudioFrame(samples=hot_samples, activation_id=old_activation))
    engine.tick()

    assert thread_manager.tasks == []
    assert engine.get_latest_generation_with_frame() < engine.get_generation_id()
    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)


@pytest.mark.qt
def test_beat_engine_force_stop_cancels_compute_and_discards_runtime_buffers(qt_app, qtbot, np_module):
    engine = _SpotifyBeatEngine(18)
    engine._audio_worker._np = np_module
    thread_manager = _DeferredComputeThreadManager()
    engine.set_thread_manager(thread_manager)
    engine.set_playback_state(True)

    old_audio_buffer = engine._audio_buffer
    old_result_buffer = engine._bars_result_buffer
    engine._audio_buffer.publish(
        _AudioFrame(
            samples=_synthetic_audio(np_module, hz=110.0, amp=0.85),
            activation_id=engine.get_activation_id(),
        )
    )
    engine.tick()

    assert engine._compute_task_active is True
    assert thread_manager.tasks

    engine.force_stop()

    assert engine._compute_task_active is False
    assert engine._audio_buffer is not old_audio_buffer
    assert engine._bars_result_buffer is not old_result_buffer
    assert max(engine.get_smoothed_bars()) == pytest.approx(0.0)


@pytest.mark.qt
def test_reset_smoothing_state_clears_audio_worker_processing_caches_even_without_bar_count_change(qt_app, qtbot):
    engine = _SpotifyBeatEngine(35)
    worker = engine._audio_worker

    worker._band_cache_key = (2048, 35)
    worker._band_log_idx = [1, 2, 3]
    worker._band_bins = [4, 5, 6]
    worker._weight_bands = [0.1, 0.2]
    worker._weight_factors = [0.3, 0.4]
    worker._smooth_kernel = [0.25, 0.5, 0.25]
    worker._work_bars = [0.9] * 35
    worker._zero_bars = [0.0] * 35
    worker._band_edges = [0, 10, 20]
    worker._freq_values = [0.7] * 35

    engine.reset_smoothing_state()

    assert worker._band_cache_key is None
    assert worker._band_log_idx is None
    assert worker._band_bins is None
    assert worker._weight_bands is None
    assert worker._weight_factors is None
    assert worker._smooth_kernel is None
    assert worker._work_bars is None
    assert worker._zero_bars is None
    assert worker._band_edges is None
    assert worker._freq_values is None


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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)

    widget._engine = fake_engine
    widget._spotify_playing = True
    widget.start()
    qt_app.processEvents()
    widget._engine = fake_engine

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
        widget._engine = fake_engine

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

    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    # After commit ff691e3, _replay_engine_config reads from authoritative config cache,
    # not from widget cached state. Update the technical config cache to have expected values.
    widget._technical_config_cache = {
        widget._vis_mode.name.lower(): {
            "dynamic_floor": False,
            "manual_floor": 0.3,
            "adaptive_sensitivity": False,
            "sensitivity": 2.4,
            "audio_block_size": 0,
            "dynamic_range_enabled": False,
            "agc_strength": 0.5,
            "input_gain": 1.0,
        }
    }

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
    widget._engine = fake_engine

    widget.set_visualization_mode(VisualizerMode.BLOB)
    widget._engine = fake_engine
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
def test_mode_cycle_cold_clears_overlay_before_target_activation(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    cleared = {"count": 0}

    def _patched_clear_overlay() -> None:
        cleared["count"] += 1

    monkeypatch.setattr(widget, "_clear_gl_overlay", _patched_clear_overlay)

    assert mode_transition.cycle_mode(widget) is True

    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert cleared["count"] == 1


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

    monkeypatch.setattr(vis_mod, "is_perf_metrics_enabled", lambda: True, raising=False)
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
    assert widget._pending_engine_activation_id == -1
    assert widget._last_engine_activation_seen == -1
    assert widget._pending_engine_activation_id == -1
    assert widget._last_engine_activation_seen == -1


@pytest.mark.qt
def test_tick_pipeline_backfills_missing_fresh_generation_state(qt_app, qtbot):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    delattr(widget, "_waiting_for_fresh_frame")
    delattr(widget, "_waiting_for_fresh_engine_frame")
    delattr(widget, "_pending_engine_generation")
    delattr(widget, "_last_engine_generation_seen")
    delattr(widget, "_pending_engine_activation_id")
    delattr(widget, "_last_engine_activation_seen")

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
def test_set_visualization_mode_requests_single_overlay_clear(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    qtbot.addWidget(widget)

    clear_calls = {"count": 0}

    def _patched_clear_gl_overlay(*args, **kwargs):
        clear_calls["count"] += 1

    monkeypatch.setattr(widget, "_clear_gl_overlay", _patched_clear_gl_overlay)
    monkeypatch.setattr(widget, "_prepare_engine_for_mode_reset", lambda: None)

    widget.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    assert clear_calls["count"] == 1


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
def test_clear_gl_overlay_preserves_overlay_instance_and_clears_runtime_state(qt_app, qtbot):
    class _PixelShiftStub:
        def __init__(self) -> None:
            self.unregistered: list[QWidget] = []

        def unregister_widget(self, widget: QWidget) -> None:
            self.unregistered.append(widget)

    class _OverlayStub(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.hide_calls = 0
            self.clear_calls = 0
            self.cleanup_calls = 0
            self.delete_calls = 0
            self.reset_requests: list[str] = []

        def hide(self) -> None:  # type: ignore[override]
            self.hide_calls += 1

        def clear_overlay_buffer(self) -> None:
            self.clear_calls += 1

        def cleanup_gl(self) -> None:
            self.cleanup_calls += 1

        def request_mode_reset(self, mode: str) -> None:
            self.reset_requests.append(mode)

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
    widget._vis_mode = VisualizerMode.SPECTRUM

    widget._clear_gl_overlay()

    stub: _OverlayStub = parent._spotify_bars_overlay  # type: ignore[assignment]
    assert stub.hide_calls == 1
    assert stub.clear_calls == 1
    assert stub.cleanup_calls == 0
    assert stub.delete_calls == 0
    assert stub.reset_requests == ["spectrum"]
    assert parent._pixel_shift_manager.unregistered == []


@pytest.mark.qt
def test_destroy_parent_overlay_still_destroys_overlay(qt_app, qtbot):
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

        def clear_overlay_buffer(self) -> None:
            pass

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

    widget._destroy_parent_overlay(reason="test_cleanup")

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._spotify_secondary_stage_registered = True
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    prewarm_calls: list[str] = []
    import widgets.spotify_visualizer.startup_staging as startup_staging_mod

    monkeypatch.setattr(startup_staging_mod, "prewarm_parent_overlay", lambda widget: prewarm_calls.append("prewarm"))

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

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
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: None)

    vis.start()
    qt_app.processEvents()

    assert anchor.refresh_requests == 1
    assert fake_engine.playback_states[-1] is False

    vis.stop()


def test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config():
    """Verify _replay_engine_config is not called during mode reset."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    class FakeEngine:
        def cancel_pending_compute_tasks(self):
            pass

        def reset_smoothing_state(self):
            pass

        def reset_floor_state(self):
            pass

        def set_smoothing(self, value):
            pass

        def set_playback_state(self, value):
            pass

        def get_generation_id(self):
            return 1

    class FakeWidget:
        _engine = FakeEngine()
        _bar_count = 32
        _vis_mode = VisualizerMode.SPECTRUM
        _smoothing = 0.18
        _spotify_playing = False
        replay_called = False
        technical_called = False
        _mode_teardown_target_generation = -1

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            pass

        def _replay_engine_config(self, engine):
            self.replay_called = True

        def _apply_technical_config_for_mode(self, mode, reason):
            self.technical_called = True

        def _track_engine_generation(self, engine):
            pass

    widget = FakeWidget()

    prepare_engine_for_mode_reset(widget)

    assert widget.technical_called is True
    assert widget.replay_called is False


def test_prepare_engine_for_mode_reset_applies_target_technical_config_only():
    """Verify mode reset applies only target technical config after reset."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    calls = []

    class FakeEngine:
        def __init__(self):
            self.floor = None
            self.sensitivity = None
            self.input_gain = None
            self.block_size = None
            self.generation = 1

        def cancel_pending_compute_tasks(self):
            calls.append(("cancel",))

        def reset_smoothing_state(self):
            calls.append(("reset_smoothing",))

        def reset_floor_state(self):
            calls.append(("reset_floor",))

        def set_smoothing(self, value):
            calls.append(("smoothing", value))

        def set_floor_config(self, dynamic, manual):
            self.floor = (dynamic, manual)
            calls.append(("floor", dynamic, manual))

        def set_sensitivity_config(self, adaptive, sensitivity):
            self.sensitivity = (adaptive, sensitivity)
            calls.append(("sensitivity", adaptive, sensitivity))

        def set_input_gain(self, value):
            self.input_gain = value
            calls.append(("input_gain", value))

        def set_audio_block_size(self, value):
            self.block_size = value
            calls.append(("block_size", value))

        def set_playback_state(self, value):
            calls.append(("playback", value))

        def get_generation_id(self):
            return self.generation

    engine = FakeEngine()

    class FakeWidget:
        _engine = engine
        _bar_count = 32
        _vis_mode = VisualizerMode.BUBBLE
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1

        def _get_mode_technical_config(self, mode):
            assert mode == VisualizerMode.BUBBLE
            return {
                "dynamic_floor": False,
                "manual_floor": 0.66,
                "adaptive_sensitivity": False,
                "sensitivity": 0.77,
                "audio_block_size": 1024,
                "dynamic_range_enabled": False,
                "agc_strength": 0.25,
                "input_gain": 1.55,
            }

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            calls.append(("full_runtime", mode, reason))

        def _apply_technical_config_for_mode(self, mode, reason):
            cfg = self._get_mode_technical_config(mode)
            engine.set_floor_config(cfg["dynamic_floor"], cfg["manual_floor"])
            engine.set_sensitivity_config(cfg["adaptive_sensitivity"], cfg["sensitivity"])
            engine.set_input_gain(cfg["input_gain"])
            engine.set_audio_block_size(cfg["audio_block_size"])
            calls.append(("technical", mode, reason))

        def _track_engine_generation(self, engine):
            calls.append(("track_generation", engine.get_generation_id()))

    widget = FakeWidget()

    prepare_engine_for_mode_reset(widget)

    assert engine.floor == (False, 0.66)
    assert engine.sensitivity == (False, 0.77)
    assert engine.input_gain == 1.55
    assert engine.block_size == 1024
    assert ("technical", VisualizerMode.BUBBLE, "mode_prepare_reset") in calls


def test_mode_reset_with_distinct_mode_configs_prevents_bleed():
    """Verify mode switching with distinct configs prevents state bleed."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    class FakeEngine:
        def __init__(self):
            self.floor = None
            self.sensitivity = None
            self.input_gain = None
            self.block_size = None
            self.generation = 1

        def cancel_pending_compute_tasks(self):
            pass

        def reset_smoothing_state(self):
            pass

        def reset_floor_state(self):
            pass

        def set_smoothing(self, value):
            pass

        def set_floor_config(self, dynamic, manual):
            self.floor = (dynamic, manual)

        def set_sensitivity_config(self, adaptive, sensitivity):
            self.sensitivity = (adaptive, sensitivity)

        def set_input_gain(self, value):
            self.input_gain = value

        def set_audio_block_size(self, value):
            self.block_size = value

        def set_playback_state(self, value):
            pass

        def get_generation_id(self):
            return self.generation

    engine = FakeEngine()

    class FakeWidget:
        _engine = engine
        _bar_count = 32
        _vis_mode = VisualizerMode.SPECTRUM
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1
        _settings_model = None
        _technical_config_cache = {}

        def _get_mode_technical_config(self, mode):
            mode_key = mode.name.lower()
            return self._technical_config_cache.get(mode_key)

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            pass

        def _apply_technical_config_for_mode(self, mode, reason):
            cfg = self._get_mode_technical_config(mode)
            if cfg is None:
                return
            engine.set_floor_config(cfg["dynamic_floor"], cfg["manual_floor"])
            engine.set_sensitivity_config(cfg["adaptive_sensitivity"], cfg["sensitivity"])
            engine.set_input_gain(cfg["input_gain"])
            engine.set_audio_block_size(cfg["audio_block_size"])

        def _track_engine_generation(self, engine):
            pass

        def _build_technical_cache(self, model):
            cache = {}
            for mode_key in ["spectrum", "bubble", "blob", "devcurve"]:
                cache[mode_key] = {
                    "dynamic_floor": mode_key == "bubble",
                    "manual_floor": 0.12 if mode_key == "spectrum" else 0.66 if mode_key == "bubble" else 0.44,
                    "adaptive_sensitivity": mode_key != "devcurve",
                    "sensitivity": 1.0 if mode_key == "spectrum" else 0.77 if mode_key == "bubble" else 0.88,
                    "audio_block_size": 128 if mode_key == "spectrum" else 256 if mode_key == "bubble" else 512,
                    "input_gain": 1.1,
                }
            return cache

    widget = FakeWidget()
    widget._settings_model = type("Model", (), {})()

    # Test SPECTRUM -> BUBBLE
    widget._vis_mode = VisualizerMode.BUBBLE
    prepare_engine_for_mode_reset(widget)
    assert engine.floor == (True, 0.66)
    assert engine.sensitivity == (True, 0.77)
    assert engine.input_gain == 1.1
    assert engine.block_size == 256

    # Test BUBBLE -> BLOB
    widget._vis_mode = VisualizerMode.BLOB
    prepare_engine_for_mode_reset(widget)
    assert engine.floor == (False, 0.44)
    assert engine.sensitivity == (True, 0.88)
    assert engine.input_gain == 1.1
    assert engine.block_size == 512


def test_prepare_engine_for_mode_reset_rebuilds_technical_config_cache():
    """Verify that mode reset rebuilds the technical config cache from settings model."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    class FakeEngine:
        def __init__(self):
            self.floor = None
            self.sensitivity = None
            self.input_gain = None
            self.block_size = None
            self.generation = 1

        def cancel_pending_compute_tasks(self):
            pass

        def reset_smoothing_state(self):
            pass

        def reset_floor_state(self):
            pass

        def set_smoothing(self, value):
            pass

        def set_floor_config(self, dynamic, manual):
            self.floor = (dynamic, manual)

        def set_sensitivity_config(self, adaptive, sensitivity):
            self.sensitivity = (adaptive, sensitivity)

        def set_input_gain(self, value):
            self.input_gain = value

        def set_audio_block_size(self, value):
            self.block_size = value

        def set_playback_state(self, value):
            pass

        def get_generation_id(self):
            return self.generation

    engine = FakeEngine()

    class FakeWidget:
        _engine = engine
        _bar_count = 32
        _vis_mode = VisualizerMode.SPECTRUM
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1
        _settings_model = None
        _technical_config_cache = {}

        def _get_mode_technical_config(self, mode):
            mode_key = mode.name.lower()
            return self._technical_config_cache.get(mode_key)

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            pass

        def _apply_technical_config_for_mode(self, mode, reason):
            cfg = self._get_mode_technical_config(mode)
            if cfg is None:
                return
            engine.set_floor_config(cfg["dynamic_floor"], cfg["manual_floor"])
            engine.set_sensitivity_config(cfg["adaptive_sensitivity"], cfg["sensitivity"])
            engine.set_input_gain(cfg["input_gain"])
            engine.set_audio_block_size(cfg["audio_block_size"])

        def _track_engine_generation(self, engine):
            pass

        def _build_technical_cache(self, model):
            cache = {}
            for mode_key in ["spectrum", "bubble", "blob", "devcurve"]:
                cache[mode_key] = {
                    "dynamic_floor": False,
                    "manual_floor": 0.99,
                    "adaptive_sensitivity": False,
                    "sensitivity": 0.99,
                    "audio_block_size": 1024,
                    "input_gain": 2.0,
                }
            return cache

    widget = FakeWidget()
    widget._settings_model = type("Model", (), {})()

    # Start with empty cache
    assert widget._technical_config_cache == {}

    # Mode reset should rebuild cache
    prepare_engine_for_mode_reset(widget)

    # Verify cache was rebuilt
    assert len(widget._technical_config_cache) == 4
    assert "spectrum" in widget._technical_config_cache
    assert "bubble" in widget._technical_config_cache
    assert "blob" in widget._technical_config_cache
    assert "devcurve" in widget._technical_config_cache

    # Verify config was applied from rebuilt cache
    assert engine.floor == (False, 0.99)
    assert engine.sensitivity == (False, 0.99)
    assert engine.input_gain == 2.0
    assert engine.block_size == 1024


def test_prepare_engine_for_mode_reset_handles_missing_settings_model():
    """Verify mode reset handles missing settings model gracefully."""
    from widgets.spotify_visualizer.mode_transition import prepare_engine_for_mode_reset
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    class FakeEngine:
        def __init__(self):
            self.floor = None
            self.sensitivity = None
            self.generation = 1

        def cancel_pending_compute_tasks(self):
            pass

        def reset_smoothing_state(self):
            pass

        def reset_floor_state(self):
            pass

        def set_smoothing(self, value):
            pass

        def set_floor_config(self, dynamic, manual):
            self.floor = (dynamic, manual)

        def set_sensitivity_config(self, adaptive, sensitivity):
            self.sensitivity = (adaptive, sensitivity)

        def set_playback_state(self, value):
            pass

        def get_generation_id(self):
            return self.generation

    engine = FakeEngine()

    class FakeWidget:
        _engine = engine
        _bar_count = 32
        _vis_mode = VisualizerMode.SPECTRUM
        _smoothing = 0.18
        _spotify_playing = False
        _mode_teardown_target_generation = -1
        _settings_model = None
        _technical_config_cache = {}

        def _get_mode_technical_config(self, mode):
            mode_key = mode.name.lower()
            return self._technical_config_cache.get(mode_key)

        def _apply_full_runtime_config_for_mode(self, mode, reason):
            pass

        def _apply_technical_config_for_mode(self, mode, reason):
            cfg = self._get_mode_technical_config(mode)
            if cfg is None:
                return
            engine.set_floor_config(cfg["dynamic_floor"], cfg["manual_floor"])
            engine.set_sensitivity_config(cfg["adaptive_sensitivity"], cfg["sensitivity"])

        def _track_engine_generation(self, engine):
            pass

    widget = FakeWidget()

    # No settings model - should not crash
    prepare_engine_for_mode_reset(widget)

    # Cache remains empty, no config applied
    assert widget._technical_config_cache == {}
    assert engine.floor is None
    assert engine.sensitivity is None
