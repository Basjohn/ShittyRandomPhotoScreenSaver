from __future__ import annotations

import random
import time
import wave
from pathlib import Path
from typing import Callable

import pytest
from types import SimpleNamespace

from utils.lockfree import TripleBuffer
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key
from core.settings.visualizer_presets import get_custom_preset_index, get_preset_settings
from widgets.spotify_visualizer import bar_computation
from widgets.spotify_visualizer import config_applier
from widgets.spotify_visualizer import mode_transition
from widgets.spotify_visualizer import tick_helpers
from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer import overlay_state
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    apply_overlay_spectrum_solid_hysteresis,
    compute_spectrum_height_scale,
    segment_index_to_spectrum_bar,
    spectrum_bar_to_segment_float,
    spectrum_bar_to_segment_index,
)
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    SpotifyVisualizerWidget,
    _AudioFrame,
)
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.beat_engine import BeatEngineRegistry, _SpotifyBeatEngine
import widgets.spotify_visualizer_widget as vis_mod
from PySide6.QtGui import QColor
from PySide6.QtCore import QRect
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


def test_persist_vis_mode_updates_only_visualizer_mode_key():
    class _FakeSettingsManager:
        def __init__(self, current_mode: str | None):
            self.current_mode = current_mode
            self.set_calls: list[tuple[str, str]] = []

        def get(self, key, default=None):
            if key == "widgets.spotify_visualizer.mode":
                return self.current_mode
            return default

        def set(self, key, value):
            self.set_calls.append((key, value))
            if key == "widgets.spotify_visualizer.mode":
                self.current_mode = value

    settings = _FakeSettingsManager(current_mode="spectrum")
    widget = SimpleNamespace(
        _vis_mode_str="bubble",
        _widget_manager=SimpleNamespace(_settings_manager=settings),
    )

    mode_transition.persist_vis_mode(widget)

    assert settings.set_calls == [("widgets.spotify_visualizer.mode", "bubble")]


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


def test_spotify_visualizer_set_floor_config_preserves_authored_low_floor_and_clamps_high(np_module):
    worker = _make_audio_worker(np_module)
    worker._raw_bass_avg = 3.5  # type: ignore[attr-defined]

    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.05)
    assert worker._use_dynamic_floor is False  # type: ignore[attr-defined]
    assert worker._manual_floor == pytest.approx(0.05)  # type: ignore[attr-defined]
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
    backend = SimpleNamespace(_config=SimpleNamespace(block_size=256), _negotiated_block_size=256, restarts=0)

    def _restart():
        backend.restarts += 1
        backend._negotiated_block_size = 128
        return True

    backend.restart = _restart
    worker._backend = backend  # type: ignore[attr-defined]
    worker._running = True  # type: ignore[attr-defined]
    worker._preferred_block_size = 256  # type: ignore[attr-defined]
    worker._effective_block_size = 256  # type: ignore[attr-defined]

    worker.set_audio_block_size(128)

    assert worker._preferred_block_size == 128  # type: ignore[attr-defined]
    assert worker._effective_block_size == 128  # type: ignore[attr-defined]
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


def test_live_activation_logs_parity_warning_on_worker_config_mismatch(monkeypatch):
    from widgets.spotify_visualizer import activation_runtime

    warning_calls: list[str] = []
    monkeypatch.setattr(
        activation_runtime.logger,
        "warning",
        lambda msg, *args: warning_calls.append(msg % args if args else msg),
    )
    monkeypatch.setattr(
        activation_runtime.logger,
        "info",
        lambda *args, **kwargs: None,
    )

    overlay = SimpleNamespace(
        _fill_color=None,
        _border_color=None,
        _peak_decay_per_sec=0.35,
        _activation_id=4,
        _engine_generation=4,
    )
    worker = SimpleNamespace(
        _manual_floor=0.12,
        _use_dynamic_floor=True,
        _user_sensitivity=0.42,
        _use_recommended=True,
        _preferred_block_size=0,
        _effective_block_size=128,
        _input_gain=0.30,
        _agc_strength=0.35,
    )
    engine = SimpleNamespace(
        _audio_worker=worker,
        get_generation_id=lambda: 4,
        get_activation_id=lambda: 4,
    )
    widget = SimpleNamespace(
        _technical_config_cache={"bubble": {"manual_floor": 0.07, "dynamic_floor": True, "adaptive_sensitivity": True, "sensitivity": 0.42, "audio_block_size": 0}},
        _engine=engine,
        parent=lambda: SimpleNamespace(_spotify_bars_overlay=overlay),
        _bar_fill_color=QColor(255, 255, 255, 230),
        _bar_border_color=QColor(255, 255, 255, 255),
        _ghosting_enabled=False,
        _ghost_alpha=0.08,
        _ghost_decay_rate=0.35,
    )
    payload = SimpleNamespace(
        preset_index=7,
        is_custom=False,
        preset_name="Preset 8 (Abyss)",
        preset_path="preset_8_abyss.json",
    )

    activation_runtime.log_live_activation_state(
        widget,
        VisualizerMode.BUBBLE,
        payload,
        reason="preset_cycle",
    )

    assert any("[SPOTIFY_VIS][PARITY]" in msg and "manual_floor" in msg for msg in warning_calls)


def test_apply_resolved_activation_payload_skips_pending_layout_when_custom_route_is_selected_but_rect_is_pending(monkeypatch):
    from widgets.spotify_visualizer import activation_runtime

    layout_calls: list[str] = []
    monkeypatch.setattr(
        activation_runtime,
        "_store_authoritative_settings_model",
        lambda widget, model: model,
    )
    monkeypatch.setattr(
        activation_runtime,
        "apply_authoritative_runtime_handoff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        activation_runtime,
        "log_live_activation_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "rendering.spotify_widget_creators.apply_spotify_vis_model_config",
        lambda *args, **kwargs: None,
    )

    widget = SimpleNamespace(
        _map_mode_key_to_enum=lambda mode: VisualizerMode.BUBBLE,
        _vis_mode=VisualizerMode.BUBBLE,
        _sync_active_mode_legacy_ghost_bridge=lambda mode: None,
        _last_gpu_geom=QRect(1, 2, 3, 4),
        _last_gpu_fade_sent=0.5,
        _has_pushed_first_frame=True,
        _mode_transition_apply_height_on_resume=False,
        _mode_transition_phase=0,
        _is_custom_layout_route_selected=lambda: True,
        _is_custom_layout_active=lambda: False,
        _apply_pending_mode_transition_layout=lambda: layout_calls.append("layout"),
    )
    payload = SimpleNamespace(mode="bubble", preset_index=5, is_custom=True, preset_name="Custom", preset_path=None)
    model = SimpleNamespace(mode="bubble")

    activation_runtime.apply_resolved_activation_payload(
        widget,
        model,
        payload,
        reason="startup_create",
        force_runtime_reset=False,
    )

    assert layout_calls == []
    assert widget._mode_transition_apply_height_on_resume is False


def test_apply_resolved_activation_payload_keeps_pending_layout_for_non_custom_route(monkeypatch):
    from widgets.spotify_visualizer import activation_runtime

    layout_calls: list[str] = []
    monkeypatch.setattr(
        activation_runtime,
        "_store_authoritative_settings_model",
        lambda widget, model: model,
    )
    monkeypatch.setattr(
        activation_runtime,
        "apply_authoritative_runtime_handoff",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        activation_runtime,
        "log_live_activation_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "rendering.spotify_widget_creators.apply_spotify_vis_model_config",
        lambda *args, **kwargs: None,
    )

    widget = SimpleNamespace(
        _map_mode_key_to_enum=lambda mode: VisualizerMode.BUBBLE,
        _vis_mode=VisualizerMode.BUBBLE,
        _sync_active_mode_legacy_ghost_bridge=lambda mode: None,
        _last_gpu_geom=QRect(1, 2, 3, 4),
        _last_gpu_fade_sent=0.5,
        _has_pushed_first_frame=True,
        _mode_transition_apply_height_on_resume=False,
        _mode_transition_phase=0,
        _is_custom_layout_route_selected=lambda: False,
        _is_custom_layout_active=lambda: False,
        _apply_pending_mode_transition_layout=lambda: layout_calls.append("layout"),
    )
    payload = SimpleNamespace(mode="bubble", preset_index=5, is_custom=False, preset_name="Preset 6", preset_path="preset_6.json")
    model = SimpleNamespace(mode="bubble")

    activation_runtime.apply_resolved_activation_payload(
        widget,
        model,
        payload,
        reason="startup_create",
        force_runtime_reset=False,
    )

    assert layout_calls == ["layout"]
    assert widget._mode_transition_apply_height_on_resume is True


def test_update_timer_interval_corrects_stale_live_interval_even_when_target_matches():
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

    assert timer.calls == [11]
    assert widget._target_timer_interval_ms == 11
    assert widget._current_timer_interval_ms == 11


def test_update_timer_interval_sets_exact_stable_interval_for_target():
    class _Timer:
        def __init__(self):
            self.calls: list[int] = []

        def setInterval(self, interval: int):
            self.calls.append(interval)

    timer = _Timer()
    widget = SimpleNamespace(
        _bars_timer=timer,
        _target_timer_interval_ms=16,
        _current_timer_interval_ms=16,
    )

    tick_helpers.update_timer_interval(widget, 90.0)

    assert timer.calls == [11]
    assert widget._target_timer_interval_ms == 11
    assert widget._current_timer_interval_ms == 11


def test_on_tick_does_not_double_throttle_when_timer_already_paces(monkeypatch):
    consume_calls: list[float] = []

    widget = SimpleNamespace(
        _enabled=True,
        _bars_timer=None,
        _waiting_for_fresh_engine_frame=False,
        _waiting_for_fresh_frame=False,
        _last_transition_running=False,
        _last_update_ts=-1.0,
        _dt_spike_threshold_ms=42.0,
        _mode_teardown_block_until_ready=False,
        _mode_transition_ready=True,
        _has_pushed_first_frame=True,
        _engine=None,
        _bar_count=8,
        parent=lambda: None,
        _get_transition_context=lambda parent: {"running": False, "name": None, "elapsed": None, "idle_age": None},
        _pause_timer_during_transition=lambda active: None,
        _resolve_max_fps=lambda ctx: 90.0,
        _update_timer_interval=lambda fps: None,
        _log_tick_spike=lambda dt, ctx: None,
        _check_mode_teardown_ready=lambda engine, now_ts: None,
        _request_latency_probe=lambda reason: None,
    )

    monkeypatch.setattr(tick_pipeline.Shiboken, "isValid", lambda obj: True)
    monkeypatch.setattr(tick_pipeline, "record_tick_perf", lambda widget, now_ts: None)
    monkeypatch.setattr(
        tick_pipeline,
        "consume_engine_bars",
        lambda widget, now_ts: consume_calls.append(now_ts) or (False, False),
    )
    monkeypatch.setattr(tick_pipeline, "process_heartbeat", lambda widget, now_ts: None)
    monkeypatch.setattr(tick_pipeline, "dispatch_bubble_simulation", lambda widget, now_ts: None)
    monkeypatch.setattr(tick_pipeline, "dispatch_devcurve_field", lambda widget, now_ts: None)
    monkeypatch.setattr(
        tick_pipeline,
        "push_gpu_frame",
        lambda widget, parent, now_ts, changed, first_frame: False,
    )

    times = iter([100.0, 100.0, 100.001, 100.005, 100.005, 100.006])
    monkeypatch.setattr(tick_pipeline.time, "time", lambda: next(times))

    tick_pipeline.on_tick(widget)
    tick_pipeline.on_tick(widget)

    assert len(consume_calls) == 2


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
        self._activation_id = 1
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
        self._activation_id += 1
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

    def get_activation_id(self) -> int:
        return self._activation_id

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
        self._activation_id += 1
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


class _PrimingOverlay:
    def __init__(
        self,
        *,
        mode: str = "spectrum",
        activation_id: int = 1,
        engine_generation: int = 1,
        pending_mode_resets: set[str] | None = None,
    ) -> None:
        self._vis_mode = mode
        self._activation_id = activation_id
        self._engine_generation = engine_generation
        self._pending_mode_resets = set(pending_mode_resets or {"bubble"})


class _PrimingDisplayParent(QWidget):
    def __init__(
        self,
        *,
        overlay_mode: str = "spectrum",
        activation_id: int = 1,
        engine_generation: int = 1,
        pending_mode_resets: set[str] | None = None,
    ) -> None:
        super().__init__()
        self._spotify_bars_overlay = _PrimingOverlay(
            mode=overlay_mode,
            activation_id=activation_id,
            engine_generation=engine_generation,
            pending_mode_resets=pending_mode_resets,
        )
        self.frames: list[dict[str, object]] = []

    def push_spotify_visualizer_frame(self, *_, **kwargs):
        self.frames.append(kwargs)
        overlay = self._spotify_bars_overlay
        overlay._vis_mode = str(kwargs.get("vis_mode", overlay._vis_mode))
        overlay._activation_id = kwargs.get("activation_id")
        overlay._engine_generation = kwargs.get("engine_generation")
        overlay._pending_mode_resets.discard(overlay._vis_mode)
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


class _BubbleDispatchProfileEngine(_FakeEngine):
    def __init__(
        self,
        frames: list[dict[str, object]],
        bar_count: int = 48,
        *,
        floor_snapshot: dict[str, float | bool] | None = None,
    ) -> None:
        super().__init__(bar_count=bar_count)
        self._frames = list(frames)
        self._frame = self._frames[0] if self._frames else {}
        self._floor_snapshot = dict(
            floor_snapshot
            or {
                "dynamic_enabled": False,
                "manual_floor": 0.20,
                "gate_floor": 0.20,
                "support_pressure": 0.0,
                "expansion": 0.0,
            }
        )

    def set_frame(self, idx: int) -> None:
        self._frame = self._frames[idx % len(self._frames)]

    def get_pre_agc_energy_bands(self):
        broad = dict(self._frame.get("broad", {}))
        return SimpleNamespace(
            bass=float(broad.get("bass", 0.0)),
            mid=float(broad.get("mid", 0.0)),
            high=float(broad.get("high", 0.0)),
            overall=float(broad.get("overall", 0.0)),
        )

    def get_bubble_energy_bands(self):
        pulse = dict(self._frame.get("pulse", self._frame.get("broad", {})))
        overall = pulse.get("overall", self._frame.get("broad", {}).get("overall", 0.0))
        return SimpleNamespace(
            bass=float(pulse.get("bass", 0.0)),
            mid=float(pulse.get("mid", 0.0)),
            high=float(pulse.get("high", 0.0)),
            overall=float(overall),
        )

    def get_transient_energy_bands(self):
        transient = dict(self._frame.get("transient", {}))
        return SimpleNamespace(
            bass_transient=float(transient.get("bass_transient", 0.0)),
            mid_transient=float(transient.get("mid_transient", 0.0)),
            high_transient=float(transient.get("high_transient", 0.0)),
            overall_transient=float(transient.get("overall_transient", 0.0)),
            onset_detected=bool(transient.get("onset_detected", False)),
            onset_type=str(transient.get("onset_type", "")),
            onset_strength=float(transient.get("onset_strength", 0.0)),
        )

    def get_event_scheduler(self):
        return None

    def get_floor_snapshot(self) -> dict[str, float | bool]:
        return dict(self._floor_snapshot)


def _capture_bubble_runtime_snapshot(
    widget: SpotifyVisualizerWidget,
    now_ts: float,
) -> tuple[dict[str, float], list[float], list[float]]:
    """Run Bubble's real dispatch seam and return the compute inputs/output radii.

    This intentionally goes through ``dispatch_bubble_simulation`` first so the
    test exercises the same transient-mix and pulse-path contract as runtime
    instead of sampling only the beat-engine helper outputs in isolation.
    """
    manager = _BubbleDispatchThreadManager()
    widget._thread_manager = manager
    widget._bubble_compute_pending = False
    widget._mode_teardown_block_until_ready = False
    widget._bubble_last_tick_ts = now_ts - 0.016

    tick_pipeline.dispatch_bubble_simulation(widget, now_ts)

    assert manager.calls, "Bubble dispatch produced no compute task"
    args = manager.calls[-1]["args"]
    pos_data, _extra_data, _trail_data, _count, perf_diag = manager.calls[-1]["worker"](*args)
    radii = [float(pos_data[i]) for i in range(2, len(pos_data), 4)]
    assert isinstance(perf_diag, dict)
    assert perf_diag["worker_total_ms"] >= 0.0
    assert perf_diag["collision_pairs"] >= 0.0
    sim = getattr(widget, "_bubble_simulation", None)
    big_expansion_ratios: list[float] = []
    if sim is not None:
        for idx, bubble in enumerate(getattr(sim, "_bubbles", []) or []):
            if getattr(bubble, "is_big", False) and not getattr(bubble, "exiting", False):
                base_radius = max(1e-6, float(getattr(bubble, "radius", 0.0) or 0.0))
                render_radius = float(pos_data[idx * 4 + 2])
                big_expansion_ratios.append(render_radius / base_radius)
    return dict(args[1]), radii, big_expansion_ratios


def _capture_bubble_lane_metrics(
    widget: SpotifyVisualizerWidget,
    now_ts: float,
) -> dict[str, float]:
    eb_snap, radii, big_expansion = _capture_bubble_runtime_snapshot(widget, now_ts)
    sim = getattr(widget, "_bubble_simulation", None)
    if sim is None:
        return {
            "bass": float(eb_snap.get("bass", 0.0)),
            "big_count": 0.0,
            "big_active_ratio": 0.0,
            "max_big_delta": 0.0,
            "avg_big_delta": 0.0,
            "max_small_delta": 0.0,
            "max_big_pulse": 0.0,
            "max_big_gated": 0.0,
            "top_big_expansion": 0.0,
            "sustained_loud_energy": 0.0,
            "speed_energy": 0.0,
        }

    big_count = 0
    active_big = 0
    big_deltas: list[float] = []
    small_deltas: list[float] = []
    for idx, bubble in enumerate(getattr(sim, "_bubbles", []) or []):
        if getattr(bubble, "exiting", False):
            continue
        if idx >= len(radii):
            continue
        render_radius = float(radii[idx])
        delta = max(0.0, render_radius - float(getattr(bubble, "radius", 0.0) or 0.0))
        if getattr(bubble, "is_big", False):
            big_count += 1
            if float(getattr(bubble, "pulse_energy", 0.0) or 0.0) > 0.04:
                active_big += 1
            big_deltas.append(delta)
        else:
            small_deltas.append(delta)
    diag = sim.get_big_lane_diagnostics()
    top_expansion_count = min(4, len(big_expansion))
    top_big_expansion = (
        sum(sorted(big_expansion)[-top_expansion_count:]) / top_expansion_count
        if top_expansion_count > 0
        else 0.0
    )
    return {
        "bass": float(eb_snap.get("bass", 0.0)),
        "big_count": float(big_count),
        "big_active_ratio": (active_big / big_count) if big_count else 0.0,
        "big_max_render": max((float(radii[idx]) for idx, bubble in enumerate(getattr(sim, "_bubbles", []) or []) if idx < len(radii) and getattr(bubble, "is_big", False) and not getattr(bubble, "exiting", False)), default=0.0),
        "big_avg_render": (
            sum(float(radii[idx]) for idx, bubble in enumerate(getattr(sim, "_bubbles", []) or []) if idx < len(radii) and getattr(bubble, "is_big", False) and not getattr(bubble, "exiting", False)) / big_count
            if big_count
            else 0.0
        ),
        "max_big_delta": max(big_deltas, default=0.0),
        "avg_big_delta": (sum(big_deltas) / len(big_deltas)) if big_deltas else 0.0,
        "max_small_delta": max(small_deltas, default=0.0),
        "max_big_pulse": float(diag.get("max_big_pulse_after", 0.0)),
        "max_big_gated": float(diag.get("max_big_gated_energy", 0.0)),
        "top_big_expansion": float(top_big_expansion),
        "big_clamp_hits": float(getattr(sim, "get_big_render_diagnostics", lambda: {})().get("big_clamp_hits", 0.0)),
        "sustained_loud_energy": float(diag.get("sustained_loud_energy", 0.0)),
        "speed_energy": float(diag.get("speed_energy", 0.0)),
    }


def _capture_bubble_dispatch_profile_metrics(
    widget: SpotifyVisualizerWidget,
    engine: _BubbleDispatchProfileEngine,
    frames: list[dict[str, object]],
    *,
    start_ts: float = 0.0,
    dt: float = 0.016,
) -> list[dict[str, float]]:
    series: list[dict[str, float]] = []
    for idx, _frame in enumerate(frames):
        engine.set_frame(idx)
        series.append(_capture_bubble_lane_metrics(widget, start_ts + idx * dt))
    return series


_AUDIO_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "audio"


def _load_audio_fixture_blocks(
    np_module,
    fixture_name: str,
    *,
    block_size: int = 2048,
):
    fixture_path = _AUDIO_FIXTURE_DIR / f"{fixture_name}.wav"
    assert fixture_path.exists(), f"missing Bubble audio fixture: {fixture_path}"

    with wave.open(str(fixture_path), "rb") as handle:
        assert handle.getnchannels() == 1, f"{fixture_name} must stay mono"
        assert handle.getsampwidth() == 2, f"{fixture_name} must stay 16-bit PCM"
        raw_bytes = handle.readframes(handle.getnframes())

    samples = np_module.frombuffer(raw_bytes, dtype="<i2").astype("float32") / 32768.0
    blocks: list[object] = []
    for start in range(0, int(samples.shape[0]), block_size):
        block = samples[start:start + block_size]
        if int(block.shape[0]) < block_size:
            block = np_module.pad(block, (0, block_size - int(block.shape[0])))
        blocks.append(block.astype("float32"))
    assert blocks, f"{fixture_name} produced no audio blocks"
    return blocks


def _capture_bubble_audio_fixture_metrics(
    widget: SpotifyVisualizerWidget,
    engine: _SpotifyBeatEngine,
    blocks: list[object],
    *,
    sample_rate: int = 44100,
) -> list[dict[str, float]]:
    dt = len(blocks[0]) / float(sample_rate) if blocks else 0.016
    series: list[dict[str, float]] = []
    for idx, samples in enumerate(blocks):
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * dt)
        floor_snapshot = engine.get_floor_snapshot()
        metrics["raw_bass"] = float(getattr(engine._audio_worker, "_last_raw_bass", 0.0) or 0.0)
        metrics["bubble_feed_bass"] = float(engine.get_bubble_energy_bands().bass)
        metrics["bubble_feed_mid"] = float(engine.get_bubble_energy_bands().mid)
        metrics["bubble_feed_high"] = float(engine.get_bubble_energy_bands().high)
        metrics["support_pressure"] = float(floor_snapshot.get("support_pressure", 0.0) or 0.0)
        metrics["gate_floor"] = float(floor_snapshot.get("gate_floor", 0.0) or 0.0)
        series.append(metrics)
    return series


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


def _synthetic_phrase(np_module, *, n: int = 4096):
    t = np_module.arange(n, dtype="float32") / 48000.0
    signal = (
        np_module.sin(2.0 * np_module.pi * 96.0 * t) * 0.18
        + np_module.sin(2.0 * np_module.pi * 220.0 * t) * 0.11
        + np_module.sin(2.0 * np_module.pi * 440.0 * t) * 0.08
        + np_module.sin(2.0 * np_module.pi * 1188.0 * t) * 0.03
    )
    return signal.astype("float32")


def _deep_sea_phrase_sequence(np_module, *, n: int = 4096):
    base = _synthetic_phrase(np_module, n=n)
    bass_hot = _synthetic_audio(np_module, hz=96.0, amp=0.72, n=n)
    bass_cool = _synthetic_audio(np_module, hz=96.0, amp=0.28, n=n)
    vocal_lift = _synthetic_audio(np_module, hz=220.0, amp=0.34, n=n)

    return [
        (base * 0.92 + bass_hot * 0.34 + vocal_lift * 0.16).astype("float32"),
        (base * 0.60 + bass_cool * 0.12 + vocal_lift * 0.05).astype("float32"),
        (base * 1.00 + bass_hot * 0.30 + vocal_lift * 0.10).astype("float32"),
        (base * 0.56 + bass_cool * 0.08 + vocal_lift * 0.03).astype("float32"),
    ]


def _deep_sea_bass_heavy_sequence(np_module, *, n: int = 4096):
    base = _synthetic_audio(np_module, hz=58.0, amp=0.78, n=n)
    sub = _synthetic_audio(np_module, hz=31.0, amp=0.68, n=n)
    kick = _synthetic_audio(np_module, hz=96.0, amp=0.32, n=n)
    mids = _synthetic_audio(np_module, hz=330.0, amp=0.06, n=n)
    air = _synthetic_audio(np_module, hz=1400.0, amp=0.02, n=n)
    return [
        (base * 1.00 + sub * 0.75 + kick * 0.18 + mids + air).astype("float32"),
        (base * 0.96 + sub * 0.72 + kick * 0.16 + mids * 0.95 + air).astype("float32"),
        (base * 1.08 + sub * 0.78 + kick * 0.22 + mids * 1.05 + air).astype("float32"),
        (base * 1.02 + sub * 0.74 + kick * 0.18 + mids * 0.92 + air).astype("float32"),
        (base * 0.94 + sub * 0.70 + kick * 0.14 + mids * 0.90 + air).astype("float32"),
        (base * 1.10 + sub * 0.80 + kick * 0.24 + mids * 1.08 + air).astype("float32"),
    ]


def _deep_sea_sustained_loud_runtime_sequence(np_module, *, n: int = 4096):
    """Model the real failing song shape: soft opening, then long hot bass hold.

    The hot section is intentionally hostile to the old Bubble bars:
    loud/sub-heavy, low mid/high help, and only occasional kick accents.
    """
    soft_body = _synthetic_audio(np_module, hz=84.0, amp=0.24, n=n)
    soft_vocal = _synthetic_audio(np_module, hz=248.0, amp=0.18, n=n)
    soft_air = _synthetic_audio(np_module, hz=1400.0, amp=0.03, n=n)

    loud_base = _synthetic_audio(np_module, hz=52.0, amp=1.00, n=n)
    loud_sub = _synthetic_audio(np_module, hz=29.0, amp=0.88, n=n)
    loud_body = _synthetic_audio(np_module, hz=94.0, amp=0.16, n=n)
    loud_mid = _synthetic_audio(np_module, hz=286.0, amp=0.035, n=n)
    loud_air = _synthetic_audio(np_module, hz=1180.0, amp=0.012, n=n)
    loud_kick = _synthetic_audio(np_module, hz=96.0, amp=0.30, n=n)

    return [
        (soft_body * 0.92 + soft_vocal * 0.70 + soft_air).astype("float32"),
        (soft_body * 0.74 + soft_vocal * 0.54 + soft_air * 0.92).astype("float32"),
        (loud_base * 0.98 + loud_sub * 0.76 + loud_body * 0.08 + loud_mid + loud_air).astype("float32"),
        (loud_base * 1.02 + loud_sub * 0.80 + loud_body * 0.10 + loud_mid * 0.92 + loud_air).astype("float32"),
        (loud_base * 1.08 + loud_sub * 0.84 + loud_body * 0.14 + loud_mid + loud_air).astype("float32"),
        (loud_base * 1.04 + loud_sub * 0.82 + loud_body * 0.09 + loud_mid * 0.88 + loud_air).astype("float32"),
        (loud_base * 1.10 + loud_sub * 0.86 + loud_body * 0.12 + loud_mid + loud_air * 0.96).astype("float32"),
        (loud_base * 1.00 + loud_sub * 0.78 + loud_body * 0.22 + loud_kick * 0.16 + loud_mid + loud_air).astype("float32"),
        (loud_base * 1.06 + loud_sub * 0.84 + loud_body * 0.11 + loud_mid * 0.94 + loud_air).astype("float32"),
        (loud_base * 1.12 + loud_sub * 0.88 + loud_body * 0.14 + loud_mid + loud_air).astype("float32"),
        (loud_base * 1.01 + loud_sub * 0.80 + loud_body * 0.10 + loud_mid * 0.90 + loud_air).astype("float32"),
        (loud_base * 1.07 + loud_sub * 0.86 + loud_body * 0.24 + loud_kick * 0.18 + loud_mid + loud_air).astype("float32"),
    ]


def _deep_sea_runtime_log_replay_profile() -> list[dict[str, object]]:
    """Replay the loud-passsage shape seen in the latest runtime logs.

    The important characteristics are:
    - soft opening has decent mid/high activity and visible small-lane motion
    - later hot section is bass-heavy and loud overall
    - onset/transient help is sparse across most of the hot window
    - a later vocal swell / snare pair must still visibly lift Bubble activity
    - hero lane should not pin flat while the small lane dies
    """

    return [
        {
            "pulse": {"bass": 0.28, "mid": 0.24, "high": 0.08, "overall": 0.36},
            "broad": {"bass": 0.18, "mid": 0.28, "high": 0.08, "overall": 0.35},
            "transient": {"bass_transient": 0.05, "mid_transient": 0.07, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 0.34, "mid": 0.27, "high": 0.07, "overall": 0.42},
            "broad": {"bass": 0.20, "mid": 0.30, "high": 0.07, "overall": 0.40},
            "transient": {"bass_transient": 0.04, "mid_transient": 0.06, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 1.10, "mid": 0.14, "high": 0.03, "overall": 0.60},
            "broad": {"bass": 0.28, "mid": 0.12, "high": 0.03, "overall": 0.45},
            "transient": {"bass_transient": 0.28, "mid_transient": 0.03, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.52, "mid": 0.16, "high": 0.03, "overall": 0.64},
            "broad": {"bass": 0.30, "mid": 0.11, "high": 0.03, "overall": 0.46},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.54, "mid": 0.18, "high": 0.04, "overall": 0.66},
            "broad": {"bass": 0.31, "mid": 0.12, "high": 0.03, "overall": 0.47},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.10, "mid": 0.16, "high": 0.03, "overall": 0.60},
            "broad": {"bass": 0.27, "mid": 0.11, "high": 0.03, "overall": 0.43},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 0.99, "mid": 0.38, "high": 0.06, "overall": 0.63},
            "broad": {"bass": 0.25, "mid": 0.19, "high": 0.04, "overall": 0.44},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 0.80, "mid": 0.22, "high": 0.04, "overall": 0.56},
            "broad": {"bass": 0.22, "mid": 0.12, "high": 0.03, "overall": 0.39},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.42, "mid": 0.86, "high": 0.07, "overall": 0.74},
            "broad": {"bass": 0.29, "mid": 0.44, "high": 0.08, "overall": 0.56},
            "transient": {
                "bass_transient": 1.08,
                "mid_transient": 0.82,
                "high_transient": 0.07,
                "onset_detected": True,
                "onset_type": "vocal_swell",
                "onset_strength": 0.14,
            },
        },
        {
            "pulse": {"bass": 0.90, "mid": 0.26, "high": 0.05, "overall": 0.59},
            "broad": {"bass": 0.22, "mid": 0.14, "high": 0.03, "overall": 0.41},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 2.47, "mid": 1.14, "high": 0.22, "overall": 0.84},
            "broad": {"bass": 0.34, "mid": 0.28, "high": 0.08, "overall": 0.58},
            "transient": {
                "bass_transient": 1.67,
                "mid_transient": 0.99,
                "high_transient": 0.21,
                "onset_detected": True,
                "onset_type": "snare",
                "onset_strength": 0.28,
            },
        },
        {
            "pulse": {"bass": 1.35, "mid": 0.20, "high": 0.04, "overall": 0.62},
            "broad": {"bass": 0.24, "mid": 0.11, "high": 0.02, "overall": 0.40},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
    ]


def _organs_phrase_sequence(np_module, *, n: int = 4096):
    t = np_module.linspace(0.0, 1.0, n, endpoint=False, dtype="float32")
    low = np_module.sin(2.0 * np_module.pi * 73.42 * t) * 0.34
    fifth = np_module.sin(2.0 * np_module.pi * 110.0 * t) * 0.26
    body = np_module.sin(2.0 * np_module.pi * 220.0 * t) * 0.18
    air = np_module.sin(2.0 * np_module.pi * 880.0 * t) * 0.05
    base = (low + fifth + body + air).astype("float32")

    return [
        (base * 1.00).astype("float32"),
        (base * 0.48 + low * 0.10).astype("float32"),
        (base * 0.84 + fifth * 0.08 + body * 0.06).astype("float32"),
        (base * 0.42 + air * 0.04).astype("float32"),
    ]


def _manual_floor_late_loud_runtime_log_replay_profile() -> list[dict[str, object]]:
    """Replay the manual-floor late-loud failure family from `22:30:11 .. 22:30:56`.

    This window matters because the remaining weak Bubble shape happened while
    the floor context stayed manual (`gate=manual=0.200`, `support=0.000`).
    Loud bass repeatedly crossed 1.0, but the visible Bubble lanes still
    behaved more like a cautious soft passage than a hot sustained hold.
    """

    return [
        {
            "pulse": {"bass": 0.24, "mid": 0.20, "high": 0.06, "overall": 0.32},
            "broad": {"bass": 0.15, "mid": 0.23, "high": 0.06, "overall": 0.29},
            "transient": {"bass_transient": 0.05, "mid_transient": 0.06, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 0.29, "mid": 0.24, "high": 0.06, "overall": 0.37},
            "broad": {"bass": 0.17, "mid": 0.26, "high": 0.06, "overall": 0.33},
            "transient": {"bass_transient": 0.04, "mid_transient": 0.06, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 1.89, "mid": 0.11, "high": 0.03, "overall": 0.63},
            "broad": {"bass": 0.30, "mid": 0.10, "high": 0.03, "overall": 0.45},
            "transient": {"bass_transient": 0.16, "mid_transient": 0.02, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.18, "mid": 0.14, "high": 0.03, "overall": 0.57},
            "broad": {"bass": 0.27, "mid": 0.11, "high": 0.03, "overall": 0.42},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.42, "mid": 0.13, "high": 0.03, "overall": 0.60},
            "broad": {"bass": 0.29, "mid": 0.10, "high": 0.03, "overall": 0.44},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.24, "mid": 0.17, "high": 0.04, "overall": 0.60},
            "broad": {"bass": 0.28, "mid": 0.12, "high": 0.03, "overall": 0.43},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.05, "mid": 0.38, "high": 0.06, "overall": 0.64},
            "broad": {"bass": 0.24, "mid": 0.22, "high": 0.05, "overall": 0.47},
            "transient": {
                "bass_transient": 0.18,
                "mid_transient": 0.16,
                "high_transient": 0.03,
                "onset_detected": True,
                "onset_type": "vocal_swell",
                "onset_strength": 0.10,
            },
        },
        {
            "pulse": {"bass": 1.01, "mid": 0.16, "high": 0.03, "overall": 0.56},
            "broad": {"bass": 0.22, "mid": 0.11, "high": 0.03, "overall": 0.39},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.06, "mid": 0.17, "high": 0.04, "overall": 0.58},
            "broad": {"bass": 0.23, "mid": 0.12, "high": 0.03, "overall": 0.40},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.34, "mid": 0.70, "high": 0.07, "overall": 0.72},
            "broad": {"bass": 0.28, "mid": 0.32, "high": 0.06, "overall": 0.53},
            "transient": {
                "bass_transient": 0.56,
                "mid_transient": 0.44,
                "high_transient": 0.05,
                "onset_detected": True,
                "onset_type": "snare",
                "onset_strength": 0.16,
            },
        },
    ]


def _manual_floor_bass_dominant_tail_runtime_log_replay_profile() -> list[dict[str, object]]:
    """Replay the later bass-dominant weak-tail family from `04:28:02 .. 04:28:15`.

    This window matters because Bubble stayed in the improved loud-path regime
    overall, but the tail end still softened more than it should while the
    floor stayed manual, support pressure stayed at zero, and the section was
    not actually quiet. The common shape is:
    - bass authority remains materially hot
    - mid/high presence is thinner or intermittent
    - onset help is absent or too weak to carry the section by itself
    """

    return [
        {
            "pulse": {"bass": 1.79, "mid": 0.16, "high": 0.03, "overall": 0.66},
            "broad": {"bass": 0.51, "mid": 0.14, "high": 0.02, "overall": 0.45},
            "transient": {"bass_transient": 0.30, "mid_transient": 0.05, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 1.54, "mid": 0.43, "high": 0.06, "overall": 0.62},
            "broad": {"bass": 0.44, "mid": 0.22, "high": 0.04, "overall": 0.47},
            "transient": {"bass_transient": 0.19, "mid_transient": 0.33, "high_transient": 0.06},
        },
        {
            "pulse": {"bass": 1.45, "mid": 0.14, "high": 0.03, "overall": 0.58},
            "broad": {"bass": 0.46, "mid": 0.10, "high": 0.02, "overall": 0.40},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 0.94, "mid": 0.12, "high": 0.03, "overall": 0.49},
            "broad": {"bass": 0.31, "mid": 0.08, "high": 0.02, "overall": 0.34},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.47, "mid": 0.26, "high": 0.02, "overall": 0.57},
            "broad": {"bass": 0.41, "mid": 0.13, "high": 0.01, "overall": 0.39},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 1.43, "mid": 0.48, "high": 0.06, "overall": 0.61},
            "broad": {"bass": 0.43, "mid": 0.22, "high": 0.04, "overall": 0.45},
            "transient": {
                "bass_transient": 1.24,
                "mid_transient": 0.39,
                "high_transient": 0.06,
                "onset_detected": True,
                "onset_type": "kick",
                "onset_strength": 0.02,
            },
        },
    ]


def _latest_live_manual_floor_runtime_log_replay_profile() -> list[dict[str, object]]:
    """Replay the newer 2026-06-15 Bubble live family from `21:10:54 .. 21:13:19`.

    This newer run matters because it is closer to the current restored Bubble
    baseline than the older failure windows. The shape we need to preserve is:
    - a soft opener that still has honest small-lane life
    - repeated hot manual-floor windows with `support=0.000`
    - mixed hot sections where some windows are broad/mid-rich and some are
      much thinner, without letting the small lane collapse back toward death
    """

    return [
        {
            "pulse": {"bass": 0.34, "mid": 0.28, "high": 0.08, "overall": 0.42},
            "broad": {"bass": 0.18, "mid": 0.26, "high": 0.07, "overall": 0.36},
            "transient": {"bass_transient": 0.05, "mid_transient": 0.06, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 0.42, "mid": 0.32, "high": 0.09, "overall": 0.49},
            "broad": {"bass": 0.21, "mid": 0.29, "high": 0.08, "overall": 0.40},
            "transient": {"bass_transient": 0.04, "mid_transient": 0.06, "high_transient": 0.01},
        },
        {
            "pulse": {"bass": 1.43, "mid": 0.66, "high": 0.27, "overall": 0.76},
            "broad": {"bass": 0.34, "mid": 0.31, "high": 0.09, "overall": 0.58},
            "transient": {
                "bass_transient": 1.02,
                "mid_transient": 0.42,
                "high_transient": 0.10,
                "onset_detected": True,
                "onset_type": "kick",
                "onset_strength": 0.26,
            },
        },
        {
            "pulse": {"bass": 1.00, "mid": 0.49, "high": 0.10, "overall": 0.63},
            "broad": {"bass": 0.28, "mid": 0.23, "high": 0.05, "overall": 0.46},
            "transient": {"bass_transient": 0.18, "mid_transient": 0.11, "high_transient": 0.02},
        },
        {
            "pulse": {"bass": 1.12, "mid": 0.30, "high": 0.13, "overall": 0.60},
            "broad": {"bass": 0.30, "mid": 0.16, "high": 0.05, "overall": 0.43},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.44, "mid": 0.72, "high": 0.18, "overall": 0.75},
            "broad": {"bass": 0.35, "mid": 0.35, "high": 0.07, "overall": 0.58},
            "transient": {
                "bass_transient": 0.72,
                "mid_transient": 0.38,
                "high_transient": 0.07,
                "onset_detected": True,
                "onset_type": "snare",
                "onset_strength": 0.16,
            },
        },
        {
            "pulse": {"bass": 0.80, "mid": 0.33, "high": 0.07, "overall": 0.54},
            "broad": {"bass": 0.24, "mid": 0.17, "high": 0.04, "overall": 0.38},
            "transient": {"bass_transient": 0.00, "mid_transient": 0.00, "high_transient": 0.00},
        },
        {
            "pulse": {"bass": 1.26, "mid": 0.72, "high": 0.26, "overall": 0.73},
            "broad": {"bass": 0.30, "mid": 0.34, "high": 0.10, "overall": 0.55},
            "transient": {
                "bass_transient": 0.35,
                "mid_transient": 0.22,
                "high_transient": 0.05,
                "onset_detected": True,
                "onset_type": "vocal_swell",
                "onset_strength": 0.12,
            },
        },
        {
            "pulse": {"bass": 1.21, "mid": 0.63, "high": 0.13, "overall": 0.68},
            "broad": {"bass": 0.29, "mid": 0.29, "high": 0.05, "overall": 0.50},
            "transient": {"bass_transient": 0.16, "mid_transient": 0.08, "high_transient": 0.02},
        },
        {
            "pulse": {"bass": 1.64, "mid": 0.51, "high": 0.12, "overall": 0.69},
            "broad": {"bass": 0.36, "mid": 0.23, "high": 0.04, "overall": 0.49},
            "transient": {
                "bass_transient": 0.22,
                "mid_transient": 0.07,
                "high_transient": 0.01,
                "onset_detected": True,
                "onset_type": "kick",
                "onset_strength": 0.08,
            },
        },
    ]


def _organs_runtime_floor_sequence(np_module, *, n: int = 4096):
    base = _organs_phrase_sequence(np_module, n=n)
    sub = _synthetic_audio(np_module, hz=48.0, amp=0.30, n=n)
    kick = _synthetic_audio(np_module, hz=96.0, amp=0.18, n=n)
    body = _synthetic_audio(np_module, hz=220.0, amp=0.14, n=n)
    air = _synthetic_audio(np_module, hz=880.0, amp=0.05, n=n)

    return [
        (base[0] * 0.96 + sub * 0.32 + kick * 0.08 + body * 0.06).astype("float32"),
        (base[2] * 0.86 + sub * 0.26 + kick * 0.05 + body * 0.05).astype("float32"),
        (base[0] * 1.08 + sub * 0.40 + kick * 0.11 + body * 0.07 + air * 0.02).astype("float32"),
        (base[2] * 1.02 + sub * 0.37 + kick * 0.09 + body * 0.08).astype("float32"),
        (base[0] * 1.12 + sub * 0.43 + kick * 0.12 + body * 0.08 + air * 0.03).astype("float32"),
        (base[2] * 1.06 + sub * 0.39 + kick * 0.08 + body * 0.08).astype("float32"),
    ]


def _apply_authored_bubble_preset(widget: SpotifyVisualizerWidget, preset_index: int) -> dict[str, object]:
    settings = dict(get_preset_settings("bubble", preset_index) or {})
    assert settings, f"expected authored Bubble preset {preset_index} settings"

    config_applier.apply_vis_mode_kwargs(widget, settings)
    widget._technical_config_cache["bubble"] = {
        "manual_floor": float(settings.get("bubble_manual_floor", 0.12)),
        "dynamic_floor": bool(settings.get("bubble_dynamic_floor", True)),
        "adaptive_sensitivity": bool(settings.get("bubble_adaptive_sensitivity", True)),
        "sensitivity": float(settings.get("bubble_sensitivity", 1.0)),
        "audio_block_size": int(settings.get("bubble_audio_block_size", 0)),
        "input_gain": float(settings.get("bubble_input_gain", 1.0)),
        "agc_strength": float(settings.get("bubble_agc_strength", 0.35)),
    }
    widget._apply_technical_config_for_mode(
        VisualizerMode.BUBBLE,
        reason=f"bubble_preset_{preset_index}_authored",
    )
    return settings


def _apply_authored_bubble_deep_sea(widget: SpotifyVisualizerWidget) -> dict[str, object]:
    return _apply_authored_bubble_preset(widget, 0)


def _apply_authored_bubble_deep_sea_manual_floor(
    widget: SpotifyVisualizerWidget,
    *,
    manual_floor: float = 0.05,
) -> dict[str, object]:
    settings = _apply_authored_bubble_deep_sea(widget)
    widget._technical_config_cache["bubble"].update(
        {
            "manual_floor": float(manual_floor),
            "dynamic_floor": False,
            "audio_block_size": 128,
        }
    )
    widget._apply_technical_config_for_mode(
        VisualizerMode.BUBBLE,
        reason="deep_sea_manual_floor_authored",
    )
    return settings


def _apply_bubble_deep_sea_dynamic_floor_oracle(widget: SpotifyVisualizerWidget) -> dict[str, object]:
    settings = _apply_authored_bubble_deep_sea(widget)
    widget._technical_config_cache["bubble"].update(
        {
            "manual_floor": 0.05,
            "dynamic_floor": True,
            "audio_block_size": 128,
        }
    )
    widget._apply_technical_config_for_mode(
        VisualizerMode.BUBBLE,
        reason="deep_sea_dynamic_floor_oracle",
    )
    return settings


def _apply_authored_bubble_deep_sea_experimental(widget: SpotifyVisualizerWidget) -> dict[str, object]:
    settings = get_preset_settings("bubble", 8)
    if not settings:
        pytest.skip("authored Bubble preset 8 not available")
    return _apply_authored_bubble_preset(widget, 8)


def test_authored_bubble_preset_1_vs_9_keep_current_signal_path_deltas():
    preset_1 = dict(get_preset_settings("bubble", 0) or {})
    preset_9 = dict(get_preset_settings("bubble", 8) or {})
    if not preset_9:
        pytest.skip("authored Bubble preset 8 not available")

    assert preset_1 and preset_9
    assert float(preset_9.get("bubble_input_gain", 0.0)) < float(preset_1.get("bubble_input_gain", 0.0))
    assert bool(preset_9.get("bubble_adaptive_sensitivity", True)) is False
    assert float(preset_9.get("bubble_sensitivity", 0.0)) > float(preset_1.get("bubble_sensitivity", 0.0))
    assert float(preset_9.get("bubble_big_size_max", 0.0)) > float(preset_1.get("bubble_big_size_max", 0.0))
    assert float(preset_9.get("bubble_big_size_clamp", 0.0)) > float(preset_1.get("bubble_big_size_clamp", 0.0))


def _apply_authored_spectrum_organs(widget: SpotifyVisualizerWidget) -> dict[str, object]:
    settings = dict(get_preset_settings("spectrum", 0) or {})
    assert settings, "expected authored Spectrum preset 0 settings"

    config_applier.apply_vis_mode_kwargs(widget, settings)
    widget._technical_config_cache["spectrum"] = {
        "manual_floor": float(settings.get("spectrum_manual_floor", 0.12)),
        "dynamic_floor": bool(settings.get("spectrum_dynamic_floor", True)),
        "adaptive_sensitivity": bool(settings.get("spectrum_adaptive_sensitivity", True)),
        "sensitivity": float(settings.get("spectrum_sensitivity", 1.0)),
        "audio_block_size": int(settings.get("spectrum_audio_block_size", 0)),
        "input_gain": float(settings.get("spectrum_input_gain", 1.0)),
        "agc_strength": float(settings.get("spectrum_agc_strength", 0.35)),
    }
    widget._apply_technical_config_for_mode(VisualizerMode.SPECTRUM, reason="organs_authored")
    return settings


def _make_spectrum_solid_hysteresis_state():
    return SimpleNamespace(
        _spectrum_solid_display_segments=[],
        _spectrum_solid_display_segment_values=[],
        _spectrum_solid_last_update_ts=[],
        _spectrum_solid_hysteresis_segments=0,
        _spectrum_solid_hysteresis_bar_count=0,
    )


def _capture_first_visible_frame(
    widget: SpotifyVisualizerWidget,
    parent: _PrimingDisplayParent,
    engine: _SpotifyBeatEngine,
    samples,
) -> dict[str, object]:
    parent.reset_pushes()
    widget._has_pushed_first_frame = False
    engine._audio_buffer.publish(
        _AudioFrame(
            samples=samples,
            activation_id=engine.get_activation_id(),
        )
    )
    changed, _any_nonzero = tick_pipeline.consume_engine_bars(widget, time.time())
    assert widget._waiting_for_fresh_engine_frame is False

    assert tick_pipeline.push_gpu_frame(
        widget,
        parent,
        time.time(),
        changed=changed,
        first_frame=True,
    ) is True
    assert widget._has_pushed_first_frame is False

    assert tick_pipeline.push_gpu_frame(
        widget,
        parent,
        time.time(),
        changed=False,
        first_frame=True,
    ) is True
    assert widget._has_pushed_first_frame is True
    assert widget._waiting_for_fresh_frame is False
    return parent.frames[-1]


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
    aw._gate_floor = 1.9
    aw._support_pressure = 0.82
    aw._support_signal_avg = 2.1
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
    aw._pre_agc_live_bass = 1.91
    aw._pre_agc_live_mid = 1.62
    aw._pre_agc_live_treble = 1.43


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
    assert aw._gate_floor == pytest.approx(floor)
    assert aw._support_pressure == pytest.approx(0.0)
    assert aw._support_signal_avg == pytest.approx(floor)
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
    assert aw._pre_agc_live_bass == pytest.approx(0.0)
    assert aw._pre_agc_live_mid == pytest.approx(0.0)
    assert aw._pre_agc_live_treble == pytest.approx(0.0)


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

    assert parent._spotify_bars_overlay is not None
    assert parent._spotify_bars_overlay.reset_requests == ["oscilloscope"]
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


@pytest.mark.qt
def test_bubble_dispatch_skips_while_pending_result_waits_for_ui_tick(qt_app, qtbot, monkeypatch):
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
    widget._store_pending_bubble_result([1.0], [2.0], [3.0], 1)
    widget._bubble_pending_result_skip_count = 0
    widget._thread_manager = _BubbleDispatchThreadManager()
    widget._spotify_playing = True
    widget._bubble_last_tick_ts = time.time() - 0.016

    tick_pipeline.dispatch_bubble_simulation(widget, time.time())

    assert widget._thread_manager.calls == []
    assert widget._bubble_pending_result_skip_count == 1


@pytest.mark.qt
def test_bubble_dispatch_does_not_queue_duplicate_compute_while_previous_compute_is_in_flight(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine.get_pre_agc_energy_bands = lambda: SimpleNamespace(bass=0.52, mid=0.31, high=0.08, overall=0.44)
    fake_engine.get_transient_energy_bands = lambda: SimpleNamespace(
        bass_transient=0.11,
        mid_transient=0.04,
        high_transient=0.01,
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
    first_call_count = len(widget._thread_manager.calls)

    # No callback has run, so the prior compute is still considered in-flight.
    widget._bubble_last_tick_ts = time.time() - 0.016
    tick_pipeline.dispatch_bubble_simulation(widget, time.time())

    assert first_call_count == 1
    assert len(widget._thread_manager.calls) == 1
    assert widget._bubble_compute_pending is True


@pytest.mark.qt
def test_bubble_compute_done_stages_pending_result_until_ui_tick_consumes_it(qt_app, qtbot):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._bubble_compute_pending = True

    result = SimpleNamespace(
        success=True,
        result=([1.0, 2.0], [3.0], [4.0], 5, {"worker_total_ms": 1.25, "collision_pairs": 12.0}),
    )

    widget._bubble_compute_done(result)

    assert widget._bubble_compute_pending is False
    assert widget._has_pending_bubble_result() is True
    assert widget._bubble_pos_data == []

    assert widget._consume_pending_bubble_result() is True
    assert widget._has_pending_bubble_result() is False
    assert widget._bubble_pos_data == [1.0, 2.0]
    assert widget._bubble_extra_data == [3.0]
    assert widget._bubble_trail_data == [4.0]
    assert widget._bubble_count == 5
    assert widget._bubble_last_perf_diag["worker_total_ms"] == pytest.approx(1.25)
    assert widget._bubble_last_perf_diag["collision_pairs"] == pytest.approx(12.0)


def test_beat_engine_playback_state_keeps_worker_warm_for_short_pause():
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
    engine._capture_keepalive_grace = 6.0

    engine.set_playback_state(True)
    assert worker.start_calls == 1
    assert worker.running is True

    engine.set_playback_state(False)
    assert worker.stop_calls == 0
    assert worker.running is True
    assert engine._capture_keepalive_deadline > 0.0

    engine._expire_capture_keepalive_if_needed(engine._capture_keepalive_deadline - 0.01)
    assert worker.stop_calls == 0
    assert worker.running is True

    engine._expire_capture_keepalive_if_needed(engine._capture_keepalive_deadline + 0.01)
    assert worker.stop_calls == 1
    assert worker.running is False

    # Without an active widget reference, play-state must not auto-start capture.
    engine._ref_count = 0
    engine.set_playback_state(True)
    assert worker.start_calls == 1


def test_beat_engine_warm_resume_skips_cold_reactivity_ramp():
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
    engine._capture_keepalive_grace = 6.0

    engine.set_playback_state(True)
    cold_ramp_started = engine._play_ramp_start_ts
    assert cold_ramp_started > 0.0

    engine._play_ramp_start_ts = 0.0
    engine.set_playback_state(False)
    deadline = engine._capture_keepalive_deadline
    assert deadline > 0.0
    assert worker.running is True

    engine.set_playback_state(True)
    assert engine._capture_keepalive_deadline == 0.0
    assert engine._play_ramp_start_ts == 0.0


def test_beat_engine_paused_idle_seed_is_visible_without_audio_frame():
    engine = _SpotifyBeatEngine(bar_count=16)
    engine.set_playback_state(False)
    engine._audio_buffer.consume_latest = lambda: None  # type: ignore[assignment]

    result = engine.tick()

    assert isinstance(result, list)
    assert len(result) == 16
    assert len([bar for bar in result if bar > 0.0]) > 6
    assert max(result) < 0.05
    assert max(engine.get_smoothed_bars()) == pytest.approx(max(result))
    assert engine.get_energy_bands().overall > 0.0


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


@pytest.mark.qt
def test_bubble_dispatch_uses_bubble_specific_engine_feed(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine.get_bubble_energy_bands = lambda: SimpleNamespace(
        bass=0.62,
        mid=0.41,
        high=0.18,
        overall=0.44,
    )
    fake_engine.get_pre_agc_energy_bands = lambda: SimpleNamespace(
        bass=0.09,
        mid=0.08,
        high=0.04,
        overall=0.07,
    )
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

    assert widget._thread_manager.calls
    eb_snap = widget._thread_manager.calls[0]["args"][1]
    assert eb_snap["bass"] == pytest.approx(0.62)
    assert eb_snap["mid"] == pytest.approx(0.41)
    assert eb_snap["overall"] == pytest.approx(min(1.0, 0.62 * 0.46 + 0.41 * 0.34 + 0.18 * 0.20))


@pytest.mark.parametrize(
    "mode",
    [
        VisualizerMode.BUBBLE,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.DEVCURVE,
    ],
)
@pytest.mark.qt
def test_paused_idle_reveal_modes_do_not_block_on_fresh_engine_wait(qt_app, qtbot, monkeypatch, mode):
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


@pytest.mark.parametrize(
    "mode",
    [
        VisualizerMode.BUBBLE,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.DEVCURVE,
    ],
)
@pytest.mark.qt
def test_provisional_nonplaying_startup_seed_allows_idle_reveal_modes_to_clear_engine_wait(
    qt_app,
    qtbot,
    monkeypatch,
    mode,
):
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
    widget._startup_idle_reveal_requires_authoritative_media = False
    widget._startup_has_authoritative_media_update = False

    tick_pipeline.consume_engine_bars(widget, time.time())

    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._pending_engine_generation == -1


@pytest.mark.qt
def test_paused_bubble_idle_seed_can_complete_startup_reveal_without_playback(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    fake_engine = _FakeEngine(bar_count=8)
    fake_engine._smoothed = [0.012] * 8
    fake_engine.get_generation_id = lambda: 9
    fake_engine.get_activation_id = lambda: 4
    fake_engine.get_latest_generation_with_frame = lambda: 9
    monkeypatch.setattr(
        vis_mod,
        "get_shared_spotify_beat_engine",
        lambda *_: fake_engine,
    )

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._engine = fake_engine
    widget.set_visualization_mode(VisualizerMode.BUBBLE)
    widget._enabled = True
    widget._spotify_playing = False
    widget._startup_reveal_pending = True
    widget._startup_reveal_not_before_ts = 0.0
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    widget._pending_engine_generation = 42
    widget._startup_idle_reveal_requires_authoritative_media = False
    widget._startup_has_authoritative_media_update = False

    fade_calls: list[int] = []
    monkeypatch.setattr(widget, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    tick_pipeline.consume_engine_bars(widget, time.time())

    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._waiting_for_fresh_frame is False
    assert widget._startup_reveal_pending is False
    assert fade_calls == [1500]


@pytest.mark.parametrize(
    "mode",
    [
        VisualizerMode.OSCILLOSCOPE,
        VisualizerMode.SPECTRUM,
    ],
)
@pytest.mark.qt
def test_paused_reactive_modes_keep_waiting_for_fresh_engine_frame(qt_app, qtbot, monkeypatch, mode):
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

    assert widget._waiting_for_fresh_engine_frame is True
    assert widget._pending_engine_generation == 42

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
def test_fresh_zero_engine_frame_still_stamps_current_source_generation(qt_app, qtbot, monkeypatch):
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

    fake_engine.publish_frame([0.0] * widget._bar_count)
    changed, any_nonzero = tick_pipeline.consume_engine_bars(widget, time.time())

    assert changed is False
    assert any_nonzero is False
    assert widget._waiting_for_fresh_engine_frame is False
    assert widget._display_bars_source_generation == fake_engine.get_generation_id()
    assert widget._display_bars_source_activation == fake_engine.get_activation_id()


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
    assert parent._spotify_bars_overlay is not None

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
    assert parent._spotify_bars_overlay is not None


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
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Custom"}}

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._custom_layout_local_rect = QRect(10, 20, 300, 160)
    widget._vis_mode = VisualizerMode.BLOB
    widget.setGeometry(0, 0, 300, 160)

    widget._apply_preferred_height()

    assert widget.height() == 160


@pytest.mark.qt
def test_visualizer_preferred_height_defers_when_custom_route_is_selected_but_rect_is_pending(qt_app, qtbot):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    class _Settings:
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Custom"}}

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._vis_mode = VisualizerMode.BLOB
    widget.setGeometry(0, 0, 300, 160)

    widget._apply_preferred_height()

    assert widget.geometry() == QRect(0, 0, 300, 160)


@pytest.mark.qt
def test_visualizer_custom_rect_stays_authoritative_even_if_settings_snapshot_is_stale(qt_app, qtbot):
    from PySide6.QtCore import QRect

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    class _Settings:
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Bottom Left"}}

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    widget._widget_manager = SimpleNamespace(_settings_manager=_Settings())
    widget._custom_layout_local_rect = QRect(10, 20, 300, 160)
    widget._vis_mode = VisualizerMode.BUBBLE
    widget.setGeometry(10, 20, 300, 160)

    widget.setMinimumHeight(400)
    widget._apply_preferred_height()

    assert widget.minimumHeight() == 160
    assert widget.maximumHeight() == 160
    assert widget.geometry() == QRect(10, 20, 300, 160)


@pytest.mark.qt
def test_visualizer_custom_rect_geometry_reapply_restores_committed_rect_after_runtime_drift(qt_app, qtbot):
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget
    from rendering.widget_manager import WidgetManager

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.resize(1280, 720)

    class _Settings:
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Custom"}}

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    widget._custom_layout_local_rect = QRect(10, 20, 300, 160)
    widget._widget_manager = WidgetManager(parent)
    widget._widget_manager._settings_manager = _Settings()

    QWidget.setGeometry(widget, QRect(10, 20, 300, 360))
    assert widget.geometry() == QRect(10, 20, 300, 360)

    widget._request_reposition()

    assert widget.minimumHeight() == 160
    assert widget.maximumHeight() == 160
    assert widget.geometry() == QRect(10, 20, 300, 160)


@pytest.mark.qt
def test_visualizer_custom_rect_survives_repeated_deferred_layout_after_square_runtime_drift(qt_app, qtbot):
    from PySide6.QtCore import QRect
    from PySide6.QtWidgets import QWidget
    from rendering.widget_manager import WidgetManager

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.resize(1280, 720)
    parent._spotify_bars_overlay = QWidget(parent)
    parent._spotify_bars_overlay.setGeometry(QRect(36, 200, 357, 357))

    class _Settings:
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Custom"}}

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    parent.spotify_visualizer_widget = widget
    widget._custom_layout_local_rect = QRect(36, 200, 402, 357)
    widget._widget_manager = WidgetManager(parent)
    widget._widget_manager._settings_manager = _Settings()
    widget._vis_mode = VisualizerMode.BLOB

    for _ in range(3):
        QWidget.setGeometry(widget, QRect(36, 200, 357, 357))
        parent._spotify_bars_overlay.setGeometry(QRect(36, 200, 357, 357))
        widget._mode_transition_apply_height_on_resume = True
        widget._apply_pending_mode_transition_layout()

        assert widget.minimumWidth() == 402
        assert widget.maximumWidth() == 402
        assert widget.minimumHeight() == 357
        assert widget.maximumHeight() == 357
        assert widget.geometry() == QRect(36, 200, 402, 357)
        assert parent._spotify_bars_overlay.geometry() == QRect(36, 200, 402, 357)


@pytest.mark.qt
def test_push_gpu_frame_uses_authoritative_custom_rect_for_geometry_change_detection(qt_app, qtbot):
    from PySide6.QtCore import QRect

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.resize(1280, 720)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.2] * 8
    widget._bar_count = 8
    widget._custom_layout_local_rect = QRect(24, 180, 402, 357)
    widget._last_gpu_geom = QRect(24, 180, 357, 357)
    widget._last_gpu_fade_sent = 1.0
    widget._get_gpu_fade_factor = lambda now_ts: 1.0
    widget._mode_transition_fade_factor = lambda now_ts: 1.0
    widget.setGeometry(24, 180, 357, 357)

    assert tick_pipeline.push_gpu_frame(
        widget,
        parent,
        time.time(),
        changed=False,
        first_frame=False,
    ) is True
    assert len(parent.frames) == 1
    assert widget._last_gpu_geom == QRect(24, 180, 402, 357)


@pytest.mark.qt
def test_visualizer_request_reposition_uses_anchor_media_in_custom_without_local_media(qt_app, qtbot):
    from PySide6.QtCore import QRect

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.resize(1280, 720)

    calls: list[tuple[object | None, int, int]] = []

    class _Settings:
        def get_widgets_map(self):
            return {"spotify_visualizer": {"position": "Custom"}}

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
    authored_floors = {
        "spectrum": 0.11,
        "oscilloscope": 0.21,
        "blob": 0.05,
        "sine_wave": 0.24,
        "bubble": 0.07,
        "devcurve": 0.49,
    }
    for idx, mode in enumerate(ordered_modes):
        mode_id = mode.name.lower()
        spotify_cfg[get_preset_key(mode_id)] = get_custom_preset_index(mode_id)
        spotify_cfg[f"{mode_id}_bar_count"] = 18 + idx
        spotify_cfg[f"{mode_id}_dynamic_floor"] = False
        spotify_cfg[f"{mode_id}_manual_floor"] = authored_floors.get(mode_id, 0.14 + idx * 0.07)
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
    widget._vis_mode = VisualizerMode.BUBBLE
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
def test_first_frame_guard_warns_for_zero_data_reactive_push(qt_app, qtbot, monkeypatch):
    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.0] * 6
    widget._display_bars_source_generation = -1
    widget._display_bars_source_activation = -1
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

    assert any("display_missing_source_generation" in message for message in warnings)
    assert any("display_missing_source_activation" in message for message in warnings)


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
def test_first_frame_uses_hidden_primer_until_overlay_matches_current_activation(qt_app, qtbot):
    parent = _PrimingDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    widget._display_bars = [0.35] * 6
    widget._display_bars_source_generation = 12
    widget._display_bars_source_activation = 34
    widget._pending_engine_generation = 12
    widget._pending_engine_activation_id = 34
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = True

    reasons: list[str] = []

    def _capture_render_state(*, reason: str):
        reasons.append(reason)

    widget._log_active_render_state_snapshot = _capture_render_state  # type: ignore[method-assign]

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is True
    assert parent.frames[0]["fade"] == pytest.approx(0.0)
    assert widget._has_pushed_first_frame is False
    assert widget._waiting_for_fresh_frame is True
    assert reasons == ["before_first_overlay_push"]

    parent._spotify_bars_overlay._vis_mode = "bubble"
    parent._spotify_bars_overlay._activation_id = 34
    parent._spotify_bars_overlay._engine_generation = 12
    parent._spotify_bars_overlay._pending_mode_resets.clear()

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is True
    assert widget._has_pushed_first_frame is True
    assert widget._waiting_for_fresh_frame is False
    assert reasons == ["before_first_overlay_push", "after_first_overlay_push"]


@pytest.mark.qt
def test_reactive_first_frame_uses_hidden_primer_when_source_generation_missing(qt_app, qtbot):
    parent = _PrimingDisplayParent()
    qtbot.addWidget(parent)

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=6)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget._display_bars = [0.0] * 6
    widget._display_bars_source_generation = -1
    widget._display_bars_source_activation = -1
    widget._pending_engine_generation = 12
    widget._pending_engine_activation_id = 34
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = True

    reasons: list[str] = []

    def _capture_render_state(*, reason: str):
        reasons.append(reason)

    widget._log_active_render_state_snapshot = _capture_render_state  # type: ignore[method-assign]

    assert tick_pipeline.push_gpu_frame(widget, parent, time.time(), changed=True, first_frame=True) is True
    assert parent.frames[0]["fade"] == pytest.approx(0.0)
    assert widget._has_pushed_first_frame is False
    assert widget._waiting_for_fresh_frame is True
    assert reasons == ["before_first_overlay_push"]


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
def test_mode_switch_low_floor_bubble_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    settings_manager,
    np_module,
    monkeypatch,
):
    from core.settings import visualizer_presets as vp

    def _fake_get_preset_settings(mode_key, index):
        if mode_key == "bubble":
            if index == 0:
                return {
                    "bubble_manual_floor": 0.12,
                    "bubble_audio_block_size": 256,
                    "bubble_sensitivity": 0.40,
                }
            if index == 1:
                return {
                    "bubble_manual_floor": 0.07,
                    "bubble_audio_block_size": 0,
                    "bubble_sensitivity": 0.42,
                }
        return {}

    monkeypatch.setattr(vp, "get_preset_settings", _fake_get_preset_settings)

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update(
        {
            "mode": "devcurve",
            "preset_devcurve": 0,
            "preset_bubble": 1,
        }
    )
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    live_engine = _SpotifyBeatEngine(35)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=35)
    qtbot.addWidget(widget)
    widget._widget_manager = SimpleNamespace(_settings_manager=settings_manager)
    widget._engine = live_engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.DEVCURVE

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    target_samples = _synthetic_audio(np_module, hz=440.0, amp=0.08)

    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    _poison_audio_worker_state(live_engine)

    assert mode_transition.switch_to_mode(widget, "bubble") is True
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
    oracle_widget._widget_manager = SimpleNamespace(_settings_manager=settings_manager)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.BUBBLE
    oracle_widget._apply_full_runtime_config_for_mode(VisualizerMode.BUBBLE, reason="oracle")

    fresh_engine._audio_buffer.publish(_AudioFrame(samples=target_samples))
    fresh_engine.tick()
    fresh_bars = fresh_engine.get_smoothed_bars()

    assert live_engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert fresh_engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert live_engine._audio_worker._preferred_block_size == 0
    assert fresh_engine._audio_worker._preferred_block_size == 0
    assert live_bars == pytest.approx(fresh_bars, abs=0.025)


@pytest.mark.qt
def test_mode_switch_first_visible_spectrum_frame_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    np_module,
):
    live_parent = _PrimingDisplayParent(
        overlay_mode="devcurve",
        pending_mode_resets={"spectrum"},
    )
    qtbot.addWidget(live_parent)

    live_engine = _SpotifyBeatEngine(35)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    live_widget = SpotifyVisualizerWidget(parent=live_parent, bar_count=35)
    qtbot.addWidget(live_widget)
    live_widget._engine = live_engine
    live_widget._enabled = True
    live_widget._spotify_playing = True
    live_widget._vis_mode = VisualizerMode.DEVCURVE

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    target_samples = _synthetic_audio(np_module, hz=440.0, amp=0.08)

    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    _poison_audio_worker_state(live_engine)

    assert mode_transition.switch_to_mode(live_widget, "spectrum") is True
    now = live_widget._mode_transition_ts + live_widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(live_widget, now)

    live_frame = _capture_first_visible_frame(
        live_widget,
        live_parent,
        live_engine,
        target_samples,
    )

    fresh_parent = _PrimingDisplayParent(
        overlay_mode="devcurve",
        pending_mode_resets={"spectrum"},
    )
    qtbot.addWidget(fresh_parent)

    fresh_engine = _SpotifyBeatEngine(35)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0

    oracle_widget = SpotifyVisualizerWidget(parent=fresh_parent, bar_count=35)
    qtbot.addWidget(oracle_widget)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.SPECTRUM
    oracle_widget.reset_runtime_activation_state(reason="oracle")
    oracle_widget._apply_full_runtime_config_for_mode(VisualizerMode.SPECTRUM, reason="oracle")

    fresh_frame = _capture_first_visible_frame(
        oracle_widget,
        fresh_parent,
        fresh_engine,
        target_samples,
    )

    assert live_frame["vis_mode"] == "spectrum"
    assert fresh_frame["vis_mode"] == "spectrum"
    assert live_frame["bars"] == pytest.approx(fresh_frame["bars"], abs=0.025)


@pytest.mark.qt
def test_spectrum_organs_first_visible_frame_is_nontrivial_under_authored_phrase(
    qt_app,
    qtbot,
    np_module,
):
    parent = _PrimingDisplayParent(
        overlay_mode="spectrum",
        pending_mode_resets={"spectrum"},
    )
    qtbot.addWidget(parent)

    settings = dict(get_preset_settings("spectrum", 0) or {})
    bar_count = int(settings.get("spectrum_bar_count", 35) or 35)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    widget.reset_runtime_activation_state(reason="organs_first_visible")
    _apply_authored_spectrum_organs(widget)

    frame = _capture_first_visible_frame(
        widget,
        parent,
        engine,
        _organs_phrase_sequence(np_module)[0],
    )

    assert frame["vis_mode"] == "spectrum"
    assert max(frame["bars"]) > 0.08
    assert max(frame["bars"]) - min(frame["bars"]) > 0.05


@pytest.mark.qt
def test_spectrum_organs_dynamic_floor_caps_gate_floor_while_support_pressure_stays_alive(
    qt_app,
    qtbot,
    np_module,
):
    engine = _SpotifyBeatEngine(35)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=35)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    _apply_authored_spectrum_organs(widget)

    manual_floor = float(engine._audio_worker._manual_floor)
    gate_cap = min(0.18, (1.0 - manual_floor) * 0.22)
    gate_ceiling = manual_floor + gate_cap

    gate_series: list[float] = []
    support_series: list[float] = []
    raw_series: list[float] = []

    for idx in range(48):
        samples = _organs_runtime_floor_sequence(np_module)[idx % 6]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        snap = engine.get_floor_snapshot()
        gate_series.append(float(snap["gate_floor"]))
        support_series.append(float(snap["support_pressure"]))
        raw_series.append(float(getattr(engine._audio_worker, "_last_raw_bass", 0.0)))

    hot_gate = gate_series[24:]
    hot_support = support_series[24:]
    hot_raw = raw_series[24:]

    assert max(hot_raw) > 1.20, "Authored Organs hot window did not reach a meaningful bass load."
    assert max(gate_series) <= gate_ceiling + 0.025
    assert max(hot_support) > 0.35, "Support pressure never meaningfully rose on the hot Organs window."
    assert max(hot_gate) - min(hot_gate) < 0.12, "Gate floor is still drifting too widely inside one hot window."
    assert max(hot_gate) < 0.70, "Gate floor is still saturating far above authored intent."


@pytest.mark.qt
def test_spectrum_organs_hot_window_keeps_visible_headroom_under_dynamic_floor(
    qt_app,
    qtbot,
    np_module,
):
    engine = _SpotifyBeatEngine(35)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=35)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.SPECTRUM
    _apply_authored_spectrum_organs(widget)

    cool_peaks: list[float] = []
    cool_ranges: list[float] = []
    hot_peaks: list[float] = []
    hot_ranges: list[float] = []
    hot_raw: list[float] = []

    sequence = _organs_runtime_floor_sequence(np_module)
    for idx in range(60):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        bars = list(engine.get_smoothed_bars())
        peak = max(bars)
        spread = peak - min(bars)
        raw_bass = float(getattr(engine._audio_worker, "_last_raw_bass", 0.0))
        if idx >= 24:
            hot_peaks.append(peak)
            hot_ranges.append(spread)
            hot_raw.append(raw_bass)
        else:
            cool_peaks.append(peak)
            cool_ranges.append(spread)

    assert hot_peaks and cool_peaks
    assert max(hot_raw) > 1.20
    assert min(hot_peaks) > 0.30, (
        f"Hot Organs peak collapsed to {min(hot_peaks):.3f}; dynamic floor is still eating too much headroom."
    )
    assert (sum(hot_peaks) / len(hot_peaks)) > (sum(cool_peaks) / len(cool_peaks)) + 0.02, (
        "Hot Organs window is still not materially stronger than the cooler window."
    )
    assert (sum(hot_ranges) / len(hot_ranges)) > (sum(cool_ranges) / len(cool_ranges)) + 0.02, (
        "Hot Organs spread is still not materially stronger than the cooler window."
    )
    assert min(hot_ranges) > 0.14, (
        f"Hot Organs spread collapsed to {min(hot_ranges):.3f}; Spectrum is still flattening into a narrow band."
    )


def test_spectrum_solid_hysteresis_boundary_chatter_holds_single_segment_wobble():
    overlay = _make_spectrum_solid_hysteresis_state()
    segments = 18
    render_height = 220.0
    height_scale = compute_spectrum_height_scale(render_height)
    segment_values = []
    now_ts = 0.0

    for target in [10, 11, 10, 11, 10, 11]:
        now_ts += 0.016
        value = segment_index_to_spectrum_bar(
            target,
            segments=segments,
            height_scale=height_scale,
        )
        bars_out = apply_overlay_spectrum_solid_hysteresis(
            overlay,
            [value],
            segments=segments,
            render_height=render_height,
            now_ts=now_ts,
        )
        segment_values.append(
            spectrum_bar_to_segment_float(
                bars_out[0],
                segments=segments,
                height_scale=height_scale,
            )
        )

    assert min(segment_values) >= 10.0
    assert max(segment_values) < 10.75
    assert any(10.05 < value < 10.95 for value in segment_values[1:])
    assert len({round(value, 2) for value in segment_values}) > 2


def test_spectrum_solid_hysteresis_accepts_true_two_segment_rise_and_fall():
    overlay = _make_spectrum_solid_hysteresis_state()
    segments = 18
    render_height = 220.0
    height_scale = compute_spectrum_height_scale(render_height)

    start_value = segment_index_to_spectrum_bar(10, segments=segments, height_scale=height_scale)
    bars_out = apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [start_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.016,
    )
    assert spectrum_bar_to_segment_index(bars_out[0], segments=segments, height_scale=height_scale) == 10

    rise_value = segment_index_to_spectrum_bar(12, segments=segments, height_scale=height_scale)
    bars_out = apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [rise_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.032,
    )
    rise_seg_1 = spectrum_bar_to_segment_float(
        bars_out[0],
        segments=segments,
        height_scale=height_scale,
    )
    assert 10.4 < rise_seg_1 < 12.0

    bars_out = apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [rise_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.048,
    )
    rise_seg_2 = spectrum_bar_to_segment_float(
        bars_out[0],
        segments=segments,
        height_scale=height_scale,
    )
    assert rise_seg_2 > 11.5
    assert rise_seg_2 < 12.0

    fall_value = segment_index_to_spectrum_bar(10, segments=segments, height_scale=height_scale)
    bars_out = apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [fall_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.064,
    )
    fall_seg_1 = spectrum_bar_to_segment_float(
        bars_out[0],
        segments=segments,
        height_scale=height_scale,
    )
    assert 10.0 < fall_seg_1 < rise_seg_2

    bars_out = apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [fall_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.080,
    )
    fall_seg_2 = spectrum_bar_to_segment_float(
        bars_out[0],
        segments=segments,
        height_scale=height_scale,
    )
    assert fall_seg_2 < 10.6


def test_spectrum_solid_hysteresis_one_segment_drop_settles_smoothly_without_robotic_pin():
    overlay = _make_spectrum_solid_hysteresis_state()
    segments = 18
    render_height = 220.0
    height_scale = compute_spectrum_height_scale(render_height)

    start_value = segment_index_to_spectrum_bar(12, segments=segments, height_scale=height_scale)
    apply_overlay_spectrum_solid_hysteresis(
        overlay,
        [start_value],
        segments=segments,
        render_height=render_height,
        now_ts=0.01,
    )

    settled_outputs = []
    drop_value = segment_index_to_spectrum_bar(11, segments=segments, height_scale=height_scale)
    for now_ts in [0.02, 0.04, 0.06, 0.08]:
        bars_out = apply_overlay_spectrum_solid_hysteresis(
            overlay,
            [drop_value],
            segments=segments,
            render_height=render_height,
            now_ts=now_ts,
        )
        settled_outputs.append(
            spectrum_bar_to_segment_float(
                bars_out[0],
                segments=segments,
                height_scale=height_scale,
            )
        )

    assert settled_outputs[0] < 12.0
    assert settled_outputs[0] > 11.5
    assert settled_outputs[-1] < 11.35
    assert settled_outputs[-1] > 11.0
    assert settled_outputs == sorted(settled_outputs, reverse=True)


@pytest.mark.qt
def test_spectrum_solid_hysteresis_resets_on_mode_reset_and_only_applies_to_single_piece(
    qt_app,
    qtbot,
    monkeypatch,
):
    times = iter([1.00, 1.02, 1.04, 1.06, 1.08, 1.10])
    monkeypatch.setattr(time, "monotonic", lambda: next(times))

    overlay = SpotifyBarsGLOverlay(parent=None)
    qtbot.addWidget(overlay)
    rect = QRect(0, 0, 600, 220)
    height_scale = compute_spectrum_height_scale(float(rect.height()))
    fill = QColor(255, 255, 255, 230)
    border = QColor(255, 255, 255, 255)

    def _set_state(value: float, *, single_piece: bool, vis_mode: str = "spectrum", segments: int = 18):
        overlay.set_state(
            rect=rect,
            bars=[value],
            bar_count=1,
            segments=segments,
            fill_color=fill,
            border_color=border,
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode=vis_mode,
            single_piece=single_piece,
        )
        return overlay._bars[0] if overlay._bars else 0.0

    solid_10 = segment_index_to_spectrum_bar(10, segments=18, height_scale=height_scale)
    solid_11 = segment_index_to_spectrum_bar(11, segments=18, height_scale=height_scale)
    segmented_11 = segment_index_to_spectrum_bar(11, segments=18, height_scale=height_scale)

    _set_state(solid_10, single_piece=True)
    held = _set_state(solid_11, single_piece=True)
    assert len(overlay._spectrum_solid_display_segment_values) == 1
    assert 10.0 < overlay._spectrum_solid_display_segment_values[0] < 11.0
    held_seg = spectrum_bar_to_segment_float(held, segments=18, height_scale=height_scale)
    assert 10.0 < held_seg < 11.0

    passthrough = _set_state(segmented_11, single_piece=False)
    assert overlay._spectrum_solid_display_segments == []
    assert overlay._spectrum_solid_display_segment_values == []
    assert spectrum_bar_to_segment_index(passthrough, segments=18, height_scale=height_scale) == 11

    _set_state(solid_10, single_piece=True)
    overlay_state.reset_mode_state(overlay, "spectrum", reason="test_reset")
    after_reset_value = segment_index_to_spectrum_bar(3, segments=18, height_scale=height_scale)
    after_reset = _set_state(after_reset_value, single_piece=True)
    assert overlay._spectrum_solid_display_segments == [3]
    assert spectrum_bar_to_segment_index(after_reset, segments=18, height_scale=height_scale) == 3

    seg24_height_scale = compute_spectrum_height_scale(float(rect.height()))
    seg24_value = segment_index_to_spectrum_bar(6, segments=24, height_scale=seg24_height_scale)
    seg24_out = _set_state(seg24_value, single_piece=True, segments=24)
    assert overlay._spectrum_solid_hysteresis_segments == 24
    assert spectrum_bar_to_segment_float(seg24_out, segments=24, height_scale=seg24_height_scale) == pytest.approx(6.0, abs=0.02)


@pytest.mark.qt
def test_mode_switch_organs_first_visible_frame_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    np_module,
):
    live_parent = _PrimingDisplayParent(
        overlay_mode="devcurve",
        pending_mode_resets={"spectrum"},
    )
    qtbot.addWidget(live_parent)

    live_engine = _SpotifyBeatEngine(35)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    live_widget = SpotifyVisualizerWidget(parent=live_parent, bar_count=35)
    qtbot.addWidget(live_widget)
    live_widget._engine = live_engine
    live_widget._enabled = True
    live_widget._spotify_playing = True
    live_widget._vis_mode = VisualizerMode.DEVCURVE
    _apply_authored_spectrum_organs(live_widget)

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    _poison_audio_worker_state(live_engine)

    assert mode_transition.switch_to_mode(live_widget, "spectrum") is True
    now = live_widget._mode_transition_ts + live_widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(live_widget, now)

    target_samples = _organs_phrase_sequence(np_module)[0]
    live_frame = _capture_first_visible_frame(
        live_widget,
        live_parent,
        live_engine,
        target_samples,
    )

    fresh_parent = _PrimingDisplayParent(
        overlay_mode="devcurve",
        pending_mode_resets={"spectrum"},
    )
    qtbot.addWidget(fresh_parent)

    fresh_engine = _SpotifyBeatEngine(35)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0

    oracle_widget = SpotifyVisualizerWidget(parent=fresh_parent, bar_count=35)
    qtbot.addWidget(oracle_widget)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.SPECTRUM
    oracle_widget.reset_runtime_activation_state(reason="oracle")
    _apply_authored_spectrum_organs(oracle_widget)

    fresh_frame = _capture_first_visible_frame(
        oracle_widget,
        fresh_parent,
        fresh_engine,
        target_samples,
    )

    assert live_frame["vis_mode"] == "spectrum"
    assert fresh_frame["vis_mode"] == "spectrum"
    assert live_frame["bars"] == pytest.approx(fresh_frame["bars"], abs=0.025)


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
def test_widget_manager_preset_cycle_low_floor_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    settings_manager,
    np_module,
    monkeypatch,
):
    from core.settings import visualizer_presets as vp
    from rendering.widget_manager import WidgetManager

    def _fake_get_preset_settings(mode_key, index):
        if mode_key == "bubble":
            if index == 0:
                return {
                    "bubble_manual_floor": 0.12,
                    "bubble_audio_block_size": 256,
                    "bubble_sensitivity": 0.40,
                }
            if index == 1:
                return {
                    "bubble_manual_floor": 0.07,
                    "bubble_audio_block_size": 0,
                    "bubble_sensitivity": 0.42,
                }
        return {}

    monkeypatch.setattr(vp, "get_preset_settings", _fake_get_preset_settings)
    monkeypatch.setattr("rendering.widget_manager.get_preset_count", lambda mode: 2)

    parent = _FakeDisplayParent()
    qtbot.addWidget(parent)
    parent.screen_index = 0

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update(
        {
            "mode": "bubble",
            "preset_bubble": 0,
        }
    )
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    engine = _SpotifyBeatEngine(20)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=20)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE

    wm = WidgetManager(parent, resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._widgets["spotify_visualizer"] = widget
    widget._widget_manager = wm
    widget._apply_full_runtime_config_for_mode(VisualizerMode.BUBBLE, reason="seed")

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    target_samples = _synthetic_audio(np_module, hz=440.0, amp=0.08)

    for _ in range(8):
        engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        engine.tick()
    _poison_audio_worker_state(engine)

    assert wm.cycle_visualizer_preset("bubble", 1) is True

    engine._audio_buffer.publish(_AudioFrame(samples=target_samples))
    engine.tick()
    live_bars = engine.get_smoothed_bars()

    fresh_engine = _SpotifyBeatEngine(20)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0

    oracle_widget = SpotifyVisualizerWidget(parent=parent, bar_count=20)
    qtbot.addWidget(oracle_widget)
    oracle_widget._widget_manager = SimpleNamespace(_settings_manager=settings_manager)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.BUBBLE
    oracle_widget._apply_full_runtime_config_for_mode(VisualizerMode.BUBBLE, reason="oracle")

    fresh_engine._audio_buffer.publish(_AudioFrame(samples=target_samples))
    fresh_engine.tick()
    fresh_bars = fresh_engine.get_smoothed_bars()

    assert int(((settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}).get("preset_bubble", -1)) == 1
    assert engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert fresh_engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert engine._audio_worker._preferred_block_size == 0
    assert fresh_engine._audio_worker._preferred_block_size == 0
    assert live_bars == pytest.approx(fresh_bars, abs=0.025)


@pytest.mark.qt
def test_widget_manager_preset_cycle_low_floor_first_visible_frame_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    settings_manager,
    np_module,
    monkeypatch,
):
    from core.settings import visualizer_presets as vp
    from rendering.widget_manager import WidgetManager

    def _fake_get_preset_settings(mode_key, index):
        if mode_key == "bubble":
            if index == 0:
                return {
                    "bubble_manual_floor": 0.12,
                    "bubble_audio_block_size": 256,
                    "bubble_sensitivity": 0.40,
                }
            if index == 1:
                return {
                    "bubble_manual_floor": 0.07,
                    "bubble_audio_block_size": 0,
                    "bubble_sensitivity": 0.42,
                }
        return {}

    monkeypatch.setattr(vp, "get_preset_settings", _fake_get_preset_settings)
    monkeypatch.setattr("rendering.widget_manager.get_preset_count", lambda mode: 2)

    live_parent = _PrimingDisplayParent(
        overlay_mode="bubble",
        pending_mode_resets={"bubble"},
    )
    qtbot.addWidget(live_parent)
    live_parent.screen_index = 0

    widgets_cfg = settings_manager.get("widgets", {}) or {}
    spotify_cfg = dict(widgets_cfg.get("spotify_visualizer", {}) or {})
    spotify_cfg.update(
        {
            "mode": "bubble",
            "preset_bubble": 0,
        }
    )
    widgets_cfg = dict(widgets_cfg)
    widgets_cfg["spotify_visualizer"] = spotify_cfg
    settings_manager.set("widgets", widgets_cfg)

    live_engine = _SpotifyBeatEngine(20)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    live_widget = SpotifyVisualizerWidget(parent=live_parent, bar_count=20)
    qtbot.addWidget(live_widget)
    live_widget._engine = live_engine
    live_widget._enabled = True
    live_widget._spotify_playing = True
    live_widget._vis_mode = VisualizerMode.BUBBLE

    wm = WidgetManager(live_parent, resource_manager=None)
    wm._attach_settings_manager(settings_manager)
    wm._widgets["spotify_visualizer"] = live_widget
    live_widget._widget_manager = wm
    live_widget._apply_full_runtime_config_for_mode(VisualizerMode.BUBBLE, reason="seed")

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    target_samples = _synthetic_audio(np_module, hz=440.0, amp=0.08)

    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    _poison_audio_worker_state(live_engine)

    assert wm.cycle_visualizer_preset("bubble", 1) is True
    live_frame = _capture_first_visible_frame(
        live_widget,
        live_parent,
        live_engine,
        target_samples,
    )

    fresh_parent = _PrimingDisplayParent(
        overlay_mode="bubble",
        pending_mode_resets={"bubble"},
    )
    qtbot.addWidget(fresh_parent)

    fresh_engine = _SpotifyBeatEngine(20)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0

    oracle_widget = SpotifyVisualizerWidget(parent=fresh_parent, bar_count=20)
    qtbot.addWidget(oracle_widget)
    oracle_widget._widget_manager = SimpleNamespace(_settings_manager=settings_manager)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.BUBBLE
    oracle_widget.reset_runtime_activation_state(reason="oracle")
    oracle_widget._apply_full_runtime_config_for_mode(VisualizerMode.BUBBLE, reason="oracle")

    fresh_frame = _capture_first_visible_frame(
        oracle_widget,
        fresh_parent,
        fresh_engine,
        target_samples,
    )

    assert int(((settings_manager.get("widgets", {}) or {}).get("spotify_visualizer", {}) or {}).get("preset_bubble", -1)) == 1
    assert live_engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert fresh_engine._audio_worker._manual_floor == pytest.approx(0.07)
    assert live_engine._audio_worker._preferred_block_size == 0
    assert fresh_engine._audio_worker._preferred_block_size == 0
    assert live_frame["vis_mode"] == "bubble"
    assert fresh_frame["vis_mode"] == "bubble"
    assert live_frame["bars"] == pytest.approx(fresh_frame["bars"], abs=0.025)


@pytest.mark.qt
def test_bubble_deep_sea_first_visible_frame_is_nontrivial_under_authored_phrase(
    qt_app,
    qtbot,
    np_module,
):
    parent = _PrimingDisplayParent(
        overlay_mode="bubble",
        pending_mode_resets={"bubble"},
    )
    qtbot.addWidget(parent)

    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=parent, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    frame = _capture_first_visible_frame(
        widget,
        parent,
        engine,
        _synthetic_phrase(np_module),
    )

    bars = list(frame["bars"])
    assert frame["vis_mode"] == "bubble"
    assert max(bars) >= 0.08
    assert sum(bars) / len(bars) >= 0.03


@pytest.mark.qt
def test_deep_sea_bubble_feed_preserves_live_variance_under_floor_pressure(
    qt_app,
    qtbot,
    np_module,
):
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_bubble_deep_sea_dynamic_floor_oracle(widget)

    sequence = _deep_sea_phrase_sequence(np_module)
    pressure_series: list[float] = []
    gate_series: list[float] = []
    control_series: list[float] = []
    bubble_series: list[float] = []
    strong_control: list[float] = []
    weak_control: list[float] = []
    strong_bubble: list[float] = []
    weak_bubble: list[float] = []

    for idx in range(80):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        floor_snapshot = engine.get_floor_snapshot()
        pressure = float(floor_snapshot["support_pressure"])
        gate_series.append(float(floor_snapshot["gate_floor"]))
        control = float(engine.get_pre_agc_energy_bands().bass)
        bubble = float(engine.get_bubble_energy_bands().bass)
        pressure_series.append(pressure)
        control_series.append(control)
        bubble_series.append(bubble)
        if idx >= 24:
            if idx % len(sequence) in (0, 2):
                strong_control.append(control)
                strong_bubble.append(bubble)
            else:
                weak_control.append(control)
                weak_bubble.append(bubble)

    assert max(pressure_series) > 0.20
    assert max(gate_series) <= 0.30
    assert strong_control and weak_control and strong_bubble and weak_bubble

    control_delta = (sum(strong_control) / len(strong_control)) - (sum(weak_control) / len(weak_control))
    bubble_delta = (sum(strong_bubble) / len(strong_bubble)) - (sum(weak_bubble) / len(weak_bubble))
    control_range = max(control_series[24:]) - min(control_series[24:])
    bubble_range = max(bubble_series[24:]) - min(bubble_series[24:])

    assert bubble_delta > 0.08, (
        f"Deep Sea live Bubble delta only reached {bubble_delta:.4f}; "
        "the continuous feed is still too flat under floor pressure."
    )
    assert bubble_range > 0.14, (
        f"Deep Sea Bubble range {bubble_range:.4f} stayed too narrow under floor pressure; "
        "the live lane is still collapsing into a plateau."
    )
    assert min(strong_bubble) > max(0.10, (sum(weak_bubble) / len(weak_bubble)) * 0.95), (
        "Deep Sea Bubble still lets the strong window sag toward the weak window while support pressure is elevated."
    )
    assert (sum(strong_bubble) / len(strong_bubble)) > (sum(weak_bubble) / len(weak_bubble)) * 1.25, (
        "Deep Sea Bubble strong phases are not separating enough from weak phases under high floor pressure."
    )


@pytest.mark.qt
def test_deep_sea_bubble_runtime_dispatch_preserves_visible_radius_variance(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1007)
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_phrase_sequence(np_module)
    strong_feature_radii: list[float] = []
    weak_feature_radii: list[float] = []
    strong_max_radii: list[float] = []
    weak_max_radii: list[float] = []
    strong_expansion: list[float] = []
    weak_expansion: list[float] = []
    bass_series: list[float] = []

    for idx in range(80):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        eb_snap, radii, big_expansion = _capture_bubble_runtime_snapshot(widget, float(idx) * 0.016)
        bass_series.append(float(eb_snap["bass"]))
        if idx < 24 or not radii:
            continue
        feature_count = min(4, len(radii))
        feature_radius = sum(sorted(radii)[-feature_count:]) / feature_count
        max_radius = max(radii)
        expansion_count = min(4, len(big_expansion))
        expansion_avg = (
            sum(sorted(big_expansion)[-expansion_count:]) / expansion_count
            if expansion_count > 0
            else 0.0
        )
        if idx % len(sequence) in (0, 2):
            strong_feature_radii.append(feature_radius)
            strong_max_radii.append(max_radius)
            strong_expansion.append(expansion_avg)
        else:
            weak_feature_radii.append(feature_radius)
            weak_max_radii.append(max_radius)
            weak_expansion.append(expansion_avg)

    assert (
        strong_feature_radii
        and weak_feature_radii
        and strong_max_radii
        and weak_max_radii
        and strong_expansion
        and weak_expansion
    )

    feature_radius_range = max(strong_feature_radii + weak_feature_radii) - min(strong_feature_radii + weak_feature_radii)

    assert max(bass_series[24:]) - min(bass_series[24:]) > 0.18, (
        "Deep Sea Bubble dispatch bass lane is still too flat before it even reaches the simulation."
    )
    assert max(strong_max_radii + weak_max_radii) > 0.090, (
        "Deep Sea Bubble runtime dispatch still is not reaching a visibly alive hero lane."
    )


@pytest.mark.qt
def test_deep_sea_manual_floor_runtime_dispatch_keeps_big_bubble_growth_headroom(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1008)
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget)

    sequence = _deep_sea_phrase_sequence(np_module)
    strong_max_radii: list[float] = []
    weak_max_radii: list[float] = []

    for idx in range(80):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        _eb_snap, radii, _big_expansion = _capture_bubble_runtime_snapshot(widget, float(idx) * 0.016)
        if idx < 24 or not radii:
            continue
        feature_count = min(4, len(radii))
        feature_radius = sum(sorted(radii)[-feature_count:]) / feature_count
        if idx % len(sequence) in (0, 2):
            strong_max_radii.append(feature_radius)
        else:
            weak_max_radii.append(feature_radius)

    assert strong_max_radii and weak_max_radii
    radius_range = max(strong_max_radii + weak_max_radii) - min(strong_max_radii + weak_max_radii)
    assert radius_range > 0.003, (
        f"Deep Sea manual-floor Bubble visible radius range only reached {radius_range:.4f}; "
        "big bubbles are still too dormant when dynamic floor is disabled."
    )
    assert max(strong_max_radii + weak_max_radii) > 0.090, (
        "Deep Sea manual-floor Bubble still is not reaching a visibly alive hero lane."
    )


@pytest.mark.qt
def test_deep_sea_big_bubble_lane_participates_in_soft_and_hot_phrases(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1001)
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_phrase_sequence(np_module)
    soft_metrics: list[dict[str, float]] = []
    hot_metrics: list[dict[str, float]] = []

    for idx in range(80):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if idx < 24:
            continue
        if idx % len(sequence) in (0, 2):
            hot_metrics.append(metrics)
        else:
            soft_metrics.append(metrics)

    assert soft_metrics and hot_metrics
    soft_active = sum(m["big_active_ratio"] for m in soft_metrics) / len(soft_metrics)
    hot_active = sum(m["big_active_ratio"] for m in hot_metrics) / len(hot_metrics)
    soft_render = sum(m["big_max_render"] for m in soft_metrics) / len(soft_metrics)
    hot_render = sum(m["big_max_render"] for m in hot_metrics) / len(hot_metrics)
    soft_pulse = max(m["max_big_pulse"] for m in soft_metrics)
    hot_pulse = max(m["max_big_pulse"] for m in hot_metrics)

    assert soft_metrics[0]["big_count"] >= 6.0
    assert soft_active >= 0.50, (
        f"Deep Sea soft phases only activated {soft_active:.2f} of the big-bubble lane."
    )
    assert soft_render > 0.080, (
        f"Deep Sea soft phases only rendered big bubbles to {soft_render:.4f}."
    )
    assert hot_active >= 0.80, (
        f"Deep Sea hot phases only activated {hot_active:.2f} of the big-bubble lane."
    )
    assert (
        hot_pulse > soft_pulse * 1.02
        or hot_render > soft_render * 1.01
    ), (
        "Deep Sea hot phases still are not separating enough from soft phases in the "
        "baseline authored phrase. The harsher runtime-loud tests own the stronger "
        "chorus regression guard."
    )


@pytest.mark.qt
def test_small_bubble_success_cannot_mask_dead_big_bubble_lane(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1002)
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    engine = _SpotifyBeatEngine(bar_count)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=bar_count)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_experimental(widget)

    sequence = _deep_sea_phrase_sequence(np_module)
    metrics_series: list[dict[str, float]] = []

    for idx in range(96):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if idx >= 24:
            metrics_series.append(metrics)

    assert metrics_series
    active_ratio = sum(m["big_active_ratio"] for m in metrics_series) / len(metrics_series)
    avg_big_delta = sum(m["avg_big_delta"] for m in metrics_series) / len(metrics_series)
    max_small_delta = max(m["max_small_delta"] for m in metrics_series)
    max_big_pulse = max(m["max_big_pulse"] for m in metrics_series)

    assert max_small_delta > 0.002, "Need a live small-bubble lane for this regression guard."
    assert active_ratio >= 0.50, (
        f"Deep Sea Experimental only activated {active_ratio:.2f} of the big-bubble lane while small bubbles were alive."
    )
    assert avg_big_delta > max_small_delta * 0.50, (
        "Small-bubble reactivity is still masking an almost dormant big-bubble lane."
    )
    assert max_big_pulse > 0.08, (
        f"Deep Sea Experimental big-bubble pulse only reached {max_big_pulse:.4f}."
    )


@pytest.mark.qt
def test_deep_sea_preset_1_runtime_loud_phrase_keeps_hero_lane_visible_without_preset_9_goalposts(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1003)
    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    metrics_series: list[dict[str, float]] = []
    for idx in range(84):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx >= 24:
            metrics_series.append(_capture_bubble_lane_metrics(widget, float(idx) * 0.016))

    assert metrics_series
    big_max = max(m["big_max_render"] for m in metrics_series)
    big_avg = sum(m["big_avg_render"] for m in metrics_series) / len(metrics_series)
    top_expand = sum(m["top_big_expansion"] for m in metrics_series) / len(metrics_series)
    small_avg = sum(m["max_small_delta"] for m in metrics_series) / len(metrics_series)

    assert big_max >= 0.118, "Preset 1 hero lane still never reaches a convincing loud-section size range."
    assert big_avg >= 0.098, "Preset 1 average hero-lane size is still too weak on the runtime loud phrase."
    assert top_expand >= 2.70, "Preset 1 hero-lane expansion is still too weak on the runtime loud phrase."
    assert small_avg >= 0.020, "Preset 1 small lane still dies too hard on the runtime loud phrase."


@pytest.mark.qt
def test_live_bubble_big_size_edits_raise_runtime_big_lane_authority(
    qt_app,
    qtbot,
    np_module,
):
    def _capture_hot_window(*, edited: bool) -> list[dict[str, float]]:
        random.seed(1004)
        engine = _SpotifyBeatEngine(48)
        engine._audio_worker._np = np_module
        engine.set_thread_manager(_ImmediateComputeThreadManager())
        engine.set_playback_state(True)
        engine._play_ramp_start_ts = 0.0

        widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
        qtbot.addWidget(widget)
        widget._engine = engine
        widget._enabled = True
        widget._spotify_playing = True
        widget._vis_mode = VisualizerMode.BUBBLE
        _apply_authored_bubble_deep_sea(widget)
        if edited:
            widget._bubble_big_size_max = 0.045
            widget._bubble_big_size_clamp = 4.8
            widget._bubble_big_bass_pulse = 0.95

        sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
        hot_window: list[dict[str, float]] = []
        for idx in range(108):
            samples = sequence[idx % len(sequence)]
            engine._audio_buffer.publish(
                _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
            )
            engine.tick()
            metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
            if 76 <= idx < 96:
                hot_window.append(metrics)
        return hot_window

    before = _capture_hot_window(edited=False)
    after = _capture_hot_window(edited=True)

    assert before and after
    before_big = sum(m["big_max_render"] for m in before) / len(before)
    after_big = sum(m["big_max_render"] for m in after) / len(after)
    before_expand = sum(m["top_big_expansion"] for m in before) / len(before)
    after_expand = sum(m["top_big_expansion"] for m in after) / len(after)

    assert after_big > before_big + 0.006, (
        "Live big-bubble size edits still barely change the runtime hero lane."
    )
    assert after_expand > before_expand * 0.98, (
        "Live big-bubble size edits are still collapsing expansion instead of preserving it."
    )


@pytest.mark.qt
def test_deep_sea_sustained_bass_hot_keeps_big_lane_alive_through_long_hold(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1005)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    early: list[dict[str, float]] = []
    late: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if 24 <= idx < 48:
            early.append(metrics)
        elif idx >= 78:
            late.append(metrics)

    assert early and late
    early_big = sum(m["big_max_render"] for m in early) / len(early)
    late_big = sum(m["big_max_render"] for m in late) / len(late)
    early_pulse = sum(m["max_big_pulse"] for m in early) / len(early)
    late_pulse = sum(m["max_big_pulse"] for m in late) / len(late)
    late_gated = sum(m["max_big_gated"] for m in late) / len(late)

    # The loud-hold contract is perceptual, not "the hold must counterfeit the
    # same size as the earlier crest hit". The hold still needs to stay clearly
    # alive, but the kick/crest bar now owns the stronger step-up requirement.
    assert late_big >= max(0.055, early_big * 0.45), (
        "Deep Sea sustained loud holds are still starving the hero lane after the initial hit."
    )
    assert late_pulse >= 0.26, (
        "Deep Sea big-bubble pulse still collapses too hard during sustained loud passages."
    )
    assert late_gated >= 0.14, (
        "Deep Sea sustained loud hold is still decaying to a near-dead gated-energy floor."
    )


@pytest.mark.qt
def test_deep_sea_sustained_bass_hot_engages_early_without_waiting_for_late_pickup(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10055)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    early: list[dict[str, float]] = []
    late: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if 24 <= idx < 48:
            early.append(metrics)
        elif idx >= 78:
            late.append(metrics)

    assert early and late
    early_big = sum(m["big_max_render"] for m in early) / len(early)
    late_big = sum(m["big_max_render"] for m in late) / len(late)
    early_small = sum(m["max_small_delta"] for m in early) / len(early)
    late_small = sum(m["max_small_delta"] for m in late) / len(late)
    early_speed = sum(m["speed_energy"] for m in early) / len(early)
    late_speed = sum(m["speed_energy"] for m in late) / len(late)

    assert early_big >= late_big * 0.90, (
        "Deep Sea hero-lane loud support is still arriving too late instead of engaging with the hot section."
    )
    assert early_small >= late_small * 0.90, (
        "Deep Sea small-bubble loud support is still waiting for a late pickup."
    )
    assert early_speed >= late_speed * 0.92, (
        "Deep Sea sustained-loud movement still ramps too late instead of feeling immediate."
    )


@pytest.mark.qt
def test_deep_sea_sustained_bass_hot_keeps_small_lane_alive(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1006)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    late: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx >= 78:
            late.append(_capture_bubble_lane_metrics(widget, float(idx) * 0.016))

    assert late
    late_small = sum(m["max_small_delta"] for m in late) / len(late)
    late_speed = sum(m["speed_energy"] for m in late) / len(late)
    late_loud = sum(m["sustained_loud_energy"] for m in late) / len(late)
    assert late_small >= 0.024, (
        "Deep Sea sustained loud holds are still flattening the small-bubble lane too far."
    )
    assert late_speed >= 0.42, (
        "Deep Sea sustained loud passages still are not driving enough Bubble movement authority."
    )
    assert late_loud >= 0.34, (
        "Deep Sea sustained loud passages still are not sustaining the raw loudness envelope strongly enough."
    )


@pytest.mark.qt
def test_deep_sea_sustained_loud_runtime_phrase_fails_if_small_lane_dies_while_big_lane_lives(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10065)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    hot_window: list[dict[str, float]] = []

    for idx in range(144):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx >= 48:
            hot_window.append(_capture_bubble_lane_metrics(widget, float(idx) * 0.016))

    assert hot_window
    avg_big_max = sum(m["big_max_render"] for m in hot_window) / len(hot_window)
    avg_big_expand = sum(m["top_big_expansion"] for m in hot_window) / len(hot_window)
    avg_small_delta = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    avg_big_pulse = sum(m["max_big_pulse"] for m in hot_window) / len(hot_window)

    assert avg_big_max >= 0.064, "Hero lane still never reaches a convincing sustained-loud visible range."
    assert avg_big_expand >= 0.010, "Hero lane still grows too little during the runtime-shaped loud phrase."
    assert avg_big_pulse >= 0.30, "Hero lane pulse still looks too weak in the runtime-shaped loud phrase."
    assert avg_small_delta >= 0.022, (
        "Small bubbles still die in the runtime-shaped loud phrase while big bubbles keep moving."
    )


@pytest.mark.qt
def test_deep_sea_runtime_loud_phrase_hot_window_cannot_collapse_relative_to_soft_window(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1003)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    soft_window: list[dict[str, float]] = []
    hot_window: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if 24 <= idx < 26:
            soft_window.append(metrics)
        elif idx >= 76:
            hot_window.append(metrics)

    assert soft_window and hot_window
    soft_small = sum(m["max_small_delta"] for m in soft_window) / len(soft_window)
    hot_small = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    soft_big = sum(m["big_max_render"] for m in soft_window) / len(soft_window)
    hot_big = sum(m["big_max_render"] for m in hot_window) / len(hot_window)
    hot_loud = sum(m["sustained_loud_energy"] for m in hot_window) / len(hot_window)
    hot_activity = hot_small + hot_big

    assert soft_small >= 0.028, "Need a genuinely alive soft window for this runtime-loud regression guard."
    assert hot_loud >= 0.60, "Need a genuinely hot late window for this runtime-loud regression guard."
    assert hot_small >= 0.009, (
        "The restored baseline still needs a minimally alive small lane in late loud windows."
    )
    # Bass-heavy loud holds should feel at least as reactive overall as the
    # softer opener, but they do not need to counterfeit the same mid-rich
    # small-lane profile. Keep the small lane clearly alive, require the hero
    # lane to remain materially present, and ensure the combined visible output
    # stays in a healthy loud-window range.
    assert hot_big >= 0.055, (
        "Late loud windows still leave the hero lane too modest for a sustained hot hold."
    )
    assert hot_activity >= 0.070, (
        "Late loud windows still do not deliver enough combined Bubble activity overall."
    )
    assert hot_big >= hot_small * 2.2, (
        "Late loud windows should bias toward a larger hero lane instead of flattening all lanes together."
    )


@pytest.mark.qt
def test_deep_sea_runtime_log_replay_keeps_loud_window_more_expressive_than_soft(
    qt_app,
    qtbot,
):
    random.seed(10031)
    profile = _deep_sea_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(profile, bar_count=48)

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    # Replay the runtime-shaped profile as one real phrase: a soft opening
    # followed by a long hot section, not an endlessly repeating cycle that
    # reintroduces "soft" frames after the loud bed has already latched.
    replay_frames = profile[:2] * 16 + profile[2:] * 24
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)
    soft_window = metrics_series[12:20]
    hot_window = metrics_series[-16:]

    assert soft_window and hot_window
    soft_small = sum(m["max_small_delta"] for m in soft_window) / len(soft_window)
    hot_small = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    soft_big = sum(m["big_max_render"] for m in soft_window) / len(soft_window)
    hot_big = sum(m["big_max_render"] for m in hot_window) / len(hot_window)
    hot_loud = sum(m["sustained_loud_energy"] for m in hot_window) / len(hot_window)
    hot_clamp = sum(m["big_clamp_hits"] for m in hot_window) / len(hot_window)

    assert soft_small >= 0.022, "Need a still-alive soft lane in the replay bar or this floor guard is meaningless."
    assert hot_loud >= 0.60, "Replay bar must actually stay in a loud sustained state."
    assert hot_small >= 0.010, (
        "Replay loud window still collapses the small lane below the restored alive baseline."
    )
    assert hot_big >= max(0.065, soft_big * 0.58), (
        "Replay loud window still leaves the hero lane below the restored alive baseline."
    )
    assert hot_clamp < 7.2, (
        "Replay loud window is still spending far too much time pinned against hero clamp pressure."
    )


@pytest.mark.qt
def test_deep_sea_runtime_log_replay_vocal_and_snare_events_must_lift_small_lane(
    qt_app,
    qtbot,
):
    random.seed(10031)
    profile = _deep_sea_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(profile, bar_count=48)

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    replay_frames = profile[:2] * 16 + profile[2:] * 24
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)

    # Final hot-cycle windows:
    # - hot_bed: sustained loud plateau before the later vocal/snare lift
    # - vocal_window: authored vocal swell pair
    # - snare_window: authored snare accent plus immediate tail
    hot_bed = metrics_series[264:268]
    vocal_window = metrics_series[268:270]
    snare_window = metrics_series[270:272]

    assert hot_bed and vocal_window and snare_window
    bed_small = sum(m["max_small_delta"] for m in hot_bed) / len(hot_bed)
    vocal_small = sum(m["max_small_delta"] for m in vocal_window) / len(vocal_window)
    snare_small = sum(m["max_small_delta"] for m in snare_window) / len(snare_window)
    bed_big = sum(m["big_max_render"] for m in hot_bed) / len(hot_bed)
    vocal_big = sum(m["big_max_render"] for m in vocal_window) / len(vocal_window)
    snare_big = sum(m["big_max_render"] for m in snare_window) / len(snare_window)
    bed_pulse = sum(m["max_big_pulse"] for m in hot_bed) / len(hot_bed)
    snare_pulse = sum(m["max_big_pulse"] for m in snare_window) / len(snare_window)
    bed_expand = sum(m["top_big_expansion"] for m in hot_bed) / len(hot_bed)
    snare_expand = sum(m["top_big_expansion"] for m in snare_window) / len(snare_window)

    assert bed_small >= 0.010, "Need a genuinely alive hot bed before checking the later event lift."
    assert vocal_small >= bed_small * 0.95, (
        "Replay vocal-swell window still sinks below the restored hot-bed small-lane baseline."
    )
    assert snare_small >= bed_small * 0.95, (
        "Replay snare window still sinks below the restored hot-bed small-lane baseline."
    )
    assert vocal_big >= bed_big + 0.004, (
        "Replay vocal-swell window still is not visibly stepping the hero lane above the hot bed."
    )
    assert snare_big >= bed_big + 0.004, (
        "Replay snare window still is not visibly stepping the hero lane above the hot bed."
    )
    assert snare_pulse >= bed_pulse + 0.015, (
        "Replay snare accent still is not producing a materially stronger hero-lane pulse than the hot bed."
    )
    assert snare_expand >= bed_expand + 0.10, (
        "Replay snare accent still is not opening the crest shape enough above the hot bed."
    )


@pytest.mark.qt
def test_manual_floor_runtime_log_replay_keeps_loud_window_alive_without_support_pressure(
    qt_app,
    qtbot,
):
    random.seed(10043)
    profile = _manual_floor_late_loud_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(
        profile,
        bar_count=48,
        floor_snapshot={
            "dynamic_enabled": False,
            "manual_floor": 0.20,
            "gate_floor": 0.20,
            "support_pressure": 0.0,
            "expansion": 0.0,
        },
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    replay_frames = profile[:2] * 16 + profile[2:] * 24
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)
    soft_window = metrics_series[12:20]
    hot_window = metrics_series[-16:]

    assert soft_window and hot_window
    assert engine.get_floor_snapshot()["support_pressure"] == pytest.approx(0.0)
    assert engine.get_floor_snapshot()["gate_floor"] == pytest.approx(0.20)

    soft_small = sum(m["max_small_delta"] for m in soft_window) / len(soft_window)
    hot_small = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    soft_big = sum(m["big_max_render"] for m in soft_window) / len(soft_window)
    hot_big = sum(m["big_max_render"] for m in hot_window) / len(hot_window)
    hot_feed = sum(m["bass"] for m in hot_window) / len(hot_window)
    hot_loud = sum(m["sustained_loud_energy"] for m in hot_window) / len(hot_window)
    hot_clamp = sum(m["big_clamp_hits"] for m in hot_window) / len(hot_window)
    hot_unique_big = {round(m["big_max_render"], 6) for m in hot_window}
    hot_big_spread = max(m["big_max_render"] for m in hot_window) - min(m["big_max_render"] for m in hot_window)
    hot_activity = hot_small + hot_big

    assert soft_small >= 0.020, "Need an alive soft opener or the late-loud replay bar loses meaning."
    assert hot_loud >= 0.56, "Manual-floor replay bar must stay genuinely loud."
    assert hot_feed >= 0.95, "Manual-floor replay must still carry real Bubble bass authority."
    assert hot_small >= 0.018, (
        "Manual-floor late loud replay still lets the small lane drift too close to dead flicker."
    )
    assert hot_big >= 0.068, (
        "Manual-floor late loud replay still leaves the hero lane too modest for repeated 1.0+ raw bass."
    )
    assert hot_activity >= 0.095, (
        "Manual-floor late loud replay still does not feel alive enough overall for a hot bass-led window."
    )
    assert hot_big >= hot_small * 2.6, (
        "Manual-floor late loud replay should keep the hero lane visibly larger than the small-lane response."
    )
    assert hot_big >= soft_big * 0.40, (
        "Manual-floor late loud replay still lets the hero lane collapse too far relative to the soft opener."
    )
    assert hot_clamp < 7.0, (
        "Manual-floor late loud replay still appears alive mainly because the hero lane is pinned into clamp pressure."
    )
    assert len(hot_unique_big) >= 3 or hot_big_spread > 0.0015, (
        "Manual-floor late loud replay still collapses the hero lane into one narrow visible shape."
    )


@pytest.mark.qt
def test_manual_floor_bass_dominant_tail_replay_stays_alive_without_presence_crutches(
    qt_app,
    qtbot,
):
    random.seed(10044)
    profile = _manual_floor_bass_dominant_tail_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(
        profile,
        bar_count=48,
        floor_snapshot={
            "dynamic_enabled": False,
            "manual_floor": 0.20,
            "gate_floor": 0.20,
            "support_pressure": 0.0,
            "expansion": 0.0,
        },
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    replay_frames = profile[:2] * 18 + profile[2:] * 14
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)
    head_window = metrics_series[20:28]
    weak_tail = metrics_series[-24:-8]
    late_tail = metrics_series[-8:]

    assert head_window and weak_tail and late_tail
    assert engine.get_floor_snapshot()["support_pressure"] == pytest.approx(0.0)
    assert engine.get_floor_snapshot()["gate_floor"] == pytest.approx(0.20)

    head_feed = sum(m["bass"] for m in head_window) / len(head_window)
    weak_feed = sum(m["bass"] for m in weak_tail) / len(weak_tail)
    late_feed = sum(m["bass"] for m in late_tail) / len(late_tail)
    head_big = sum(m["big_max_render"] for m in head_window) / len(head_window)
    weak_big = sum(m["big_max_render"] for m in weak_tail) / len(weak_tail)
    late_big = sum(m["big_max_render"] for m in late_tail) / len(late_tail)
    head_small = sum(m["max_small_delta"] for m in head_window) / len(head_window)
    weak_small = sum(m["max_small_delta"] for m in weak_tail) / len(weak_tail)
    late_small = sum(m["max_small_delta"] for m in late_tail) / len(late_tail)
    weak_pulse = sum(m["max_big_pulse"] for m in weak_tail) / len(weak_tail)
    late_pulse = sum(m["max_big_pulse"] for m in late_tail) / len(late_tail)
    weak_expand = sum(m["top_big_expansion"] for m in weak_tail) / len(weak_tail)
    late_expand = sum(m["top_big_expansion"] for m in late_tail) / len(late_tail)

    assert weak_feed >= 1.20 and late_feed >= 1.20, (
        "Tail replay must stay genuinely hot or this guard is not modeling the real weak-tail family."
    )
    assert weak_feed >= head_feed * 0.96, (
        "Tail replay unexpectedly lost bass authority before the Bubble guard could mean anything."
    )
    assert weak_big >= max(0.118, head_big * 0.95), (
        "Bass-dominant weak tail still lets the hero lane shrink too far despite staying hot."
    )
    assert late_big >= max(0.116, head_big * 0.90), (
        "Later weak tail still decays the hero lane too far in a still-hot section."
    )
    assert weak_small >= max(0.024, head_small * 0.82), (
        "Bass-dominant weak tail still lets the small lane die when presence thins out."
    )
    assert late_small >= max(0.024, head_small * 0.78), (
        "Later weak tail still leaves the small lane too soft for a not-quiet section."
    )
    assert weak_pulse >= 0.74 and late_pulse >= 0.70, (
        "Bass-dominant weak tail still collapses hero-lane pulse authority too much."
    )
    assert weak_expand >= 3.40 and late_expand >= 3.25, (
        "Bass-dominant weak tail still visibly compresses the hero expansion shape too far."
    )


@pytest.mark.qt
def test_latest_live_manual_floor_replay_keeps_small_lane_alive_through_mixed_hot_windows(
    qt_app,
    qtbot,
):
    random.seed(10045)
    profile = _latest_live_manual_floor_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(
        profile,
        bar_count=48,
        floor_snapshot={
            "dynamic_enabled": False,
            "manual_floor": 0.20,
            "gate_floor": 0.20,
            "support_pressure": 0.0,
            "expansion": 0.0,
        },
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    replay_frames = profile[:2] * 18 + profile[2:] * 16
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)
    soft_window = metrics_series[18:26]
    early_hot = metrics_series[40:56]
    late_hot = metrics_series[-16:]

    assert soft_window and early_hot and late_hot
    assert engine.get_floor_snapshot()["support_pressure"] == pytest.approx(0.0)
    assert engine.get_floor_snapshot()["gate_floor"] == pytest.approx(0.20)

    soft_small = sum(m["max_small_delta"] for m in soft_window) / len(soft_window)
    early_feed = sum(m["bass"] for m in early_hot) / len(early_hot)
    late_feed = sum(m["bass"] for m in late_hot) / len(late_hot)
    early_small = sum(m["max_small_delta"] for m in early_hot) / len(early_hot)
    late_small = sum(m["max_small_delta"] for m in late_hot) / len(late_hot)
    early_big = sum(m["big_max_render"] for m in early_hot) / len(early_hot)
    late_big = sum(m["big_max_render"] for m in late_hot) / len(late_hot)
    early_expand = sum(m["top_big_expansion"] for m in early_hot) / len(early_hot)
    late_expand = sum(m["top_big_expansion"] for m in late_hot) / len(late_hot)
    late_activity = late_small + late_big

    assert soft_small >= 0.020, "Need an alive soft opener or this latest-live Bubble oracle loses meaning."
    assert early_feed >= 0.95 and late_feed >= 0.95, (
        "Latest-live manual-floor replay must stay genuinely hot across both hot windows."
    )
    assert early_small >= 0.022, (
        "Latest-live early hot window still leaves the small lane too close to dead flicker."
    )
    assert late_small >= 0.021, (
        "Latest-live late hot window still lets the small lane collapse too far in a still-hot section."
    )
    assert late_small >= early_small * 0.78, (
        "Latest-live late hot window still loses too much small-lane authority relative to the earlier hot window."
    )
    assert early_big >= 0.120 and late_big >= 0.118, (
        "Latest-live replay still leaves the hero lane too modest for repeated hot manual-floor windows."
    )
    assert late_activity >= 0.150, (
        "Latest-live replay still does not keep enough total Bubble activity alive through the late hot window."
    )
    assert early_expand >= 3.20 and late_expand >= 3.10, (
        "Latest-live replay still compresses the hero expansion shape too far during mixed hot windows."
    )


@pytest.mark.qt
def test_bubble_soft_to_loud_audio_fixture_keeps_loud_section_more_expressive_than_soft(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10091)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    blocks = _load_audio_fixture_blocks(np_module, "soft_to_loud_transition")
    metrics_series = _capture_bubble_audio_fixture_metrics(widget, engine, blocks)
    soft_window = metrics_series[4:10]
    hot_window = metrics_series[-10:]

    assert soft_window and hot_window
    soft_raw = sum(m["raw_bass"] for m in soft_window) / len(soft_window)
    hot_raw = sum(m["raw_bass"] for m in hot_window) / len(hot_window)
    soft_feed = sum(m["bubble_feed_bass"] for m in soft_window) / len(soft_window)
    hot_feed = sum(m["bubble_feed_bass"] for m in hot_window) / len(hot_window)
    soft_small = sum(m["max_small_delta"] for m in soft_window) / len(soft_window)
    hot_small = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    soft_big = sum(m["big_max_render"] for m in soft_window) / len(soft_window)
    hot_big = sum(m["big_max_render"] for m in hot_window) / len(hot_window)

    assert hot_raw >= max(1.0, soft_raw * 2.2), "Fixture must really transition from soft into a loud bass-led section."
    assert hot_feed >= soft_feed * 1.35, (
        "Bubble feed still fails to open up materially when the fixture crosses into the loud section."
    )
    assert hot_small >= max(0.010, soft_small * 0.96), (
        "Loud fixture section still leaves the small lane looking less alive than the soft opener."
    )
    assert hot_big >= max(0.070, soft_big * 1.08), (
        "Loud fixture section still does not give the hero lane clearly stronger authority than the soft opener."
    )


@pytest.mark.qt
def test_bubble_loud_bass_hold_audio_fixture_keeps_manual_floor_lanes_alive(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10092)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    blocks = _load_audio_fixture_blocks(np_module, "loud_bass_hold")
    metrics_series = _capture_bubble_audio_fixture_metrics(widget, engine, blocks)
    hot_window = metrics_series[8:]
    early_window = hot_window[:6]
    late_window = hot_window[-6:]

    assert hot_window and early_window and late_window
    avg_raw = sum(m["raw_bass"] for m in hot_window) / len(hot_window)
    avg_feed = sum(m["bubble_feed_bass"] for m in hot_window) / len(hot_window)
    avg_small = sum(m["max_small_delta"] for m in hot_window) / len(hot_window)
    avg_big = sum(m["big_max_render"] for m in hot_window) / len(hot_window)
    avg_clamp = sum(m["big_clamp_hits"] for m in hot_window) / len(hot_window)
    early_big = sum(m["big_max_render"] for m in early_window) / len(early_window)
    late_big = sum(m["big_max_render"] for m in late_window) / len(late_window)
    late_small = sum(m["max_small_delta"] for m in late_window) / len(late_window)
    hot_unique_big = {round(m["big_max_render"], 6) for m in hot_window}
    hot_big_spread = max(m["big_max_render"] for m in hot_window) - min(m["big_max_render"] for m in hot_window)

    assert max(m["support_pressure"] for m in hot_window) == pytest.approx(0.0, abs=1e-6)
    assert avg_raw >= 1.00, "Manual-floor hold fixture must stay genuinely hot."
    assert avg_feed >= 0.24, "Manual-floor Bubble feed still stays too weak through the hold."
    assert avg_small >= 0.010, "Manual-floor loud hold still lets the small lane die."
    assert late_small >= 0.010, "Manual-floor loud hold still loses the small lane by the tail of the hold."
    assert avg_big >= 0.068, "Manual-floor loud hold still leaves the hero lane too modest."
    assert early_big >= 0.062, "Manual-floor loud hold still waits too long before lifting the hero lane."
    assert late_big >= early_big * 0.90, "Manual-floor loud hold still fades the hero lane away instead of sustaining it."
    assert avg_clamp < 7.0, "Manual-floor loud hold still looks alive mostly because clamp pressure is doing the work."
    assert len(hot_unique_big) >= 3 or hot_big_spread > 0.0015, (
        "Manual-floor loud hold still flattens into one narrow hero-lane shape."
    )


@pytest.mark.qt
def test_bubble_current_feel_lock_soft_to_loud_fixture_signature(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(20001)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    blocks = _load_audio_fixture_blocks(np_module, "soft_to_loud_transition")
    metrics_series = _capture_bubble_audio_fixture_metrics(widget, engine, blocks)
    soft_window = metrics_series[4:10]
    hot_window = metrics_series[-10:]

    actual = {
        "soft_feed": sum(m["bubble_feed_bass"] for m in soft_window) / len(soft_window),
        "hot_feed": sum(m["bubble_feed_bass"] for m in hot_window) / len(hot_window),
        "soft_small": sum(m["max_small_delta"] for m in soft_window) / len(soft_window),
        "hot_small": sum(m["max_small_delta"] for m in hot_window) / len(hot_window),
        "soft_big": sum(m["big_max_render"] for m in soft_window) / len(soft_window),
        "hot_big": sum(m["big_max_render"] for m in hot_window) / len(hot_window),
    }
    expected = {
        "soft_feed": 0.160760,
        "hot_feed": 0.770648,
        "soft_small": 0.022480,
        "hot_small": 0.032684,
        "soft_big": 0.093887,
        "hot_big": 0.130797,
    }

    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=0.15, abs=0.002), (
            f"Bubble current feel drifted for {key}: expected near {value:.6f}, got {actual[key]:.6f}."
        )


@pytest.mark.qt
def test_bubble_current_feel_lock_loud_hold_fixture_signature(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(20002)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    blocks = _load_audio_fixture_blocks(np_module, "loud_bass_hold")
    metrics_series = _capture_bubble_audio_fixture_metrics(widget, engine, blocks)
    hot_window = metrics_series[8:]
    early_window = hot_window[:6]
    late_window = hot_window[-6:]

    actual = {
        "avg_feed": sum(m["bubble_feed_bass"] for m in hot_window) / len(hot_window),
        "avg_small": sum(m["max_small_delta"] for m in hot_window) / len(hot_window),
        "avg_big": sum(m["big_max_render"] for m in hot_window) / len(hot_window),
        "early_big": sum(m["big_max_render"] for m in early_window) / len(early_window),
        "late_big": sum(m["big_max_render"] for m in late_window) / len(late_window),
        "late_small": sum(m["max_small_delta"] for m in late_window) / len(late_window),
        "avg_clamp": sum(m["big_clamp_hits"] for m in hot_window) / len(hot_window),
    }
    expected = {
        "avg_feed": 0.770648,
        "avg_small": 0.031891,
        "avg_big": 0.130759,
        "early_big": 0.134491,
        "late_big": 0.125669,
        "late_small": 0.033338,
        "avg_clamp": 6.000000,
    }

    for key, value in expected.items():
        rel = 0.15 if key != "avg_clamp" else 0.10
        abs_tol = 0.002 if key != "avg_clamp" else 0.5
        assert actual[key] == pytest.approx(value, rel=rel, abs=abs_tol), (
            f"Bubble current loud-hold feel drifted for {key}: expected near {value:.6f}, got {actual[key]:.6f}."
        )


@pytest.mark.qt
def test_bubble_current_feel_lock_runtime_log_replay_signature(
    qt_app,
    qtbot,
):
    random.seed(20003)
    profile = _deep_sea_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(profile)

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, profile)
    head_window = metrics_series[:2]
    weak_window = metrics_series[3:8]
    late_window = metrics_series[-2:]

    actual = {
        "head_small": sum(m["max_small_delta"] for m in head_window) / len(head_window),
        "weak_small": sum(m["max_small_delta"] for m in weak_window) / len(weak_window),
        "late_small": sum(m["max_small_delta"] for m in late_window) / len(late_window),
        "weak_big": sum(m["big_max_render"] for m in weak_window) / len(weak_window),
        "late_big": sum(m["big_max_render"] for m in late_window) / len(late_window),
        "weak_pulse": sum(m["max_big_pulse"] for m in weak_window) / len(weak_window),
        "late_pulse": sum(m["max_big_pulse"] for m in late_window) / len(late_window),
        "weak_expand": sum(m["top_big_expansion"] for m in weak_window) / len(weak_window),
        "late_expand": sum(m["top_big_expansion"] for m in late_window) / len(late_window),
    }
    expected = {
        "head_small": 0.001557,
        "weak_small": 0.016080,
        "late_small": 0.031306,
        "weak_big": 0.112027,
        "late_big": 0.135653,
        "weak_pulse": 0.625750,
        "late_pulse": 0.974724,
        "weak_expand": 2.954078,
        "late_expand": 3.480000,
    }

    for key, value in expected.items():
        rel = 0.18 if key == "head_small" else 0.15
        abs_tol = 0.001 if key == "head_small" else 0.002
        assert actual[key] == pytest.approx(value, rel=rel, abs=abs_tol), (
            f"Bubble current log-replay feel drifted for {key}: expected near {value:.6f}, got {actual[key]:.6f}."
        )


@pytest.mark.qt
def test_bubble_current_feel_lock_latest_live_manual_floor_replay_signature(
    qt_app,
    qtbot,
):
    random.seed(20004)
    profile = _latest_live_manual_floor_runtime_log_replay_profile()
    engine = _BubbleDispatchProfileEngine(
        profile,
        bar_count=48,
        floor_snapshot={
            "dynamic_enabled": False,
            "manual_floor": 0.20,
            "gate_floor": 0.20,
            "support_pressure": 0.0,
            "expansion": 0.0,
        },
    )

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea_manual_floor(widget, manual_floor=0.20)

    replay_frames = profile[:2] * 18 + profile[2:] * 16
    metrics_series = _capture_bubble_dispatch_profile_metrics(widget, engine, replay_frames)
    soft_window = metrics_series[18:26]
    early_hot = metrics_series[40:56]
    late_hot = metrics_series[-16:]

    actual = {
        "soft_small": sum(m["max_small_delta"] for m in soft_window) / len(soft_window),
        "early_feed": sum(m["bass"] for m in early_hot) / len(early_hot),
        "late_feed": sum(m["bass"] for m in late_hot) / len(late_hot),
        "early_small": sum(m["max_small_delta"] for m in early_hot) / len(early_hot),
        "late_small": sum(m["max_small_delta"] for m in late_hot) / len(late_hot),
        "early_big": sum(m["big_max_render"] for m in early_hot) / len(early_hot),
        "late_big": sum(m["big_max_render"] for m in late_hot) / len(late_hot),
        "late_expand": sum(m["top_big_expansion"] for m in late_hot) / len(late_hot),
    }
    expected = {
        "soft_small": 0.031724,
        "early_feed": 1.103438,
        "late_feed": 1.118250,
        "early_small": 0.029433,
        "late_small": 0.023371,
        "early_big": 0.136217,
        "late_big": 0.136358,
        "late_expand": 3.438885,
    }

    for key, value in expected.items():
        rel = 0.12
        abs_tol = 0.002
        assert actual[key] == pytest.approx(value, rel=rel, abs=abs_tol), (
            f"Bubble latest-live manual-floor replay feel drifted for {key}: expected near {value:.6f}, got {actual[key]:.6f}."
        )


@pytest.mark.qt
def test_deep_sea_runtime_loud_phrase_kick_crests_still_beat_the_hot_bed(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10093)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    kick_window: list[dict[str, float]] = []
    bed_window: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx < 72:
            continue
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        lane = idx % len(sequence)
        if lane in {5, 9}:
            kick_window.append(metrics)
        elif lane in {3, 4, 6, 7, 8}:
            bed_window.append(metrics)

    assert kick_window and bed_window
    kick_bass = sum(m["bass"] for m in kick_window) / len(kick_window)
    bed_bass = sum(m["bass"] for m in bed_window) / len(bed_window)
    kick_big = sum(m["big_max_render"] for m in kick_window) / len(kick_window)
    bed_big = sum(m["big_max_render"] for m in bed_window) / len(bed_window)
    kick_pulse = sum(m["max_big_pulse"] for m in kick_window) / len(kick_window)
    bed_pulse = sum(m["max_big_pulse"] for m in bed_window) / len(bed_window)
    kick_small = sum(m["max_small_delta"] for m in kick_window) / len(kick_window)
    bed_small = sum(m["max_small_delta"] for m in bed_window) / len(bed_window)
    kick_expand = sum(m["top_big_expansion"] for m in kick_window) / len(kick_window)
    bed_expand = sum(m["top_big_expansion"] for m in bed_window) / len(bed_window)

    assert kick_bass >= bed_bass * 0.98, (
        "Kick/crest moments should not lose Bubble feed authority inside the hot bed: "
        f"kick_bass={kick_bass:.4f} bed_bass={bed_bass:.4f}"
    )
    assert kick_big >= bed_big + 0.0025, (
        "Hero lane still fails to visibly step up on kick crests inside a loud hold: "
        f"kick_big={kick_big:.4f} bed_big={bed_big:.4f}"
    )
    assert kick_pulse >= bed_pulse + 0.032, (
        "Kick crests still are not creating a materially stronger big-lane pulse than the hot bed: "
        f"kick_pulse={kick_pulse:.4f} bed_pulse={bed_pulse:.4f}"
    )
    assert kick_expand >= bed_expand + 0.06, (
        "Kick crests still are not opening the big-bubble crest shape clearly beyond the hot bed: "
        f"kick_expand={kick_expand:.4f} bed_expand={bed_expand:.4f}"
    )
    assert kick_small >= bed_small * 0.95, (
        "Kick crests should not rescue the hero lane by killing the small lane: "
        f"kick_small={kick_small:.4f} bed_small={bed_small:.4f}"
    )


@pytest.mark.qt
def test_deep_sea_runtime_loud_phrase_does_not_flatline_hero_size_while_pulse_decays(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1003)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    late: list[dict[str, float]] = []

    for idx in range(108):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx >= 76:
            late.append(_capture_bubble_lane_metrics(widget, float(idx) * 0.016))

    assert late
    late_big_values = [m["big_max_render"] for m in late]
    late_pulse_values = [m["max_big_pulse"] for m in late]
    plateau_spread = max(late_big_values) - min(late_big_values)
    unique_big_values = {round(v, 6) for v in late_big_values}
    pulse_floor = sum(late_pulse_values) / len(late_pulse_values)

    assert pulse_floor >= 0.45, "Need a still-alive hot window for this flatline regression guard."
    assert len(unique_big_values) >= 3 or plateau_spread > 0.0015, (
        "Hero size still flatlines to one visible value through the late loud window."
    )


@pytest.mark.qt
def test_deep_sea_runtime_loud_phrase_does_not_live_on_pinned_clamp_hits(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(1003)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    hot_window: list[dict[str, float]] = []

    for idx in range(96):
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        if idx >= 36:
            hot_window.append(_capture_bubble_lane_metrics(widget, float(idx) * 0.016))

    assert hot_window
    avg_clamp_hits = sum(m["big_clamp_hits"] for m in hot_window) / len(hot_window)
    max_clamp_hits = max(m["big_clamp_hits"] for m in hot_window)

    assert avg_clamp_hits < 6.2, (
        "Hero lane still spends too much of the runtime loud phrase pinned into clamp saturation."
    )
    assert max_clamp_hits < 8.0, (
        "Hero lane still reaches the same hard clamp-hit ceiling across the runtime loud phrase."
    )


@pytest.mark.qt
def test_runtime_loud_phrase_big_size_and_clamp_edits_free_the_hero_lane(
    qt_app,
    qtbot,
    np_module,
):
    random.seed(10068)
    engine = _SpotifyBeatEngine(48)
    engine._audio_worker._np = np_module
    engine.set_thread_manager(_ImmediateComputeThreadManager())
    engine.set_playback_state(True)
    engine._play_ramp_start_ts = 0.0

    widget = SpotifyVisualizerWidget(parent=None, bar_count=48)
    qtbot.addWidget(widget)
    widget._engine = engine
    widget._enabled = True
    widget._spotify_playing = True
    widget._vis_mode = VisualizerMode.BUBBLE
    _apply_authored_bubble_deep_sea(widget)

    sequence = _deep_sea_sustained_loud_runtime_sequence(np_module)
    before: list[dict[str, float]] = []
    after: list[dict[str, float]] = []

    for idx in range(120):
        if idx == 60:
            widget._bubble_big_size_max = 0.045
            widget._bubble_big_size_clamp = 4.8
            widget._bubble_big_bass_pulse = 0.95
        samples = sequence[idx % len(sequence)]
        engine._audio_buffer.publish(
            _AudioFrame(samples=samples, activation_id=engine.get_activation_id())
        )
        engine.tick()
        metrics = _capture_bubble_lane_metrics(widget, float(idx) * 0.016)
        if 36 <= idx < 60:
            before.append(metrics)
        elif idx >= 84:
            after.append(metrics)

    assert before and after
    before_big_max = sum(m["big_max_render"] for m in before) / len(before)
    after_big_max = sum(m["big_max_render"] for m in after) / len(after)
    before_clamp = sum(m["big_clamp_hits"] for m in before) / len(before)
    after_clamp = sum(m["big_clamp_hits"] for m in after) / len(after)
    before_small = sum(m["max_small_delta"] for m in before) / len(before)
    after_small = sum(m["max_small_delta"] for m in after) / len(after)

    assert after_big_max >= 0.065, (
        "Big-size/clamp edits still cannot keep the hero lane visibly alive at the restored baseline."
    )
    assert after_clamp < 8.5, (
        "Big-size/clamp edits still push the hero lane into blatant clamp saturation."
    )
    assert after_small >= 0.0085, (
        "Big-size/clamp edits still collapse the small lane below the restored alive baseline."
    )


@pytest.mark.qt
def test_mode_switch_deep_sea_first_visible_frame_matches_fresh_activation_oracle(
    qt_app,
    qtbot,
    np_module,
):
    settings = dict(get_preset_settings("bubble", 0) or {})
    bar_count = int(settings.get("bubble_bar_count", 48) or 48)

    live_parent = _PrimingDisplayParent(
        overlay_mode="devcurve",
        pending_mode_resets={"bubble"},
    )
    qtbot.addWidget(live_parent)

    live_engine = _SpotifyBeatEngine(bar_count)
    live_engine._audio_worker._np = np_module
    live_engine.set_thread_manager(_ImmediateComputeThreadManager())
    live_engine.set_playback_state(True)
    live_engine._play_ramp_start_ts = 0.0

    live_widget = SpotifyVisualizerWidget(parent=live_parent, bar_count=bar_count)
    qtbot.addWidget(live_widget)
    live_widget._engine = live_engine
    live_widget._enabled = True
    live_widget._spotify_playing = True
    live_widget._vis_mode = VisualizerMode.DEVCURVE
    _apply_authored_bubble_deep_sea(live_widget)

    hot_samples = _synthetic_audio(np_module, hz=96.0, amp=0.95)
    for _ in range(8):
        live_engine._audio_buffer.publish(_AudioFrame(samples=hot_samples))
        live_engine.tick()
    _poison_audio_worker_state(live_engine)

    assert mode_transition.switch_to_mode(live_widget, "bubble") is True
    now = live_widget._mode_transition_ts + live_widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(live_widget, now)

    live_frame = _capture_first_visible_frame(
        live_widget,
        live_parent,
        live_engine,
        _synthetic_phrase(np_module),
    )

    fresh_parent = _PrimingDisplayParent(
        overlay_mode="bubble",
        pending_mode_resets={"bubble"},
    )
    qtbot.addWidget(fresh_parent)

    fresh_engine = _SpotifyBeatEngine(bar_count)
    fresh_engine._audio_worker._np = np_module
    fresh_engine.set_thread_manager(_ImmediateComputeThreadManager())
    fresh_engine.set_playback_state(True)
    fresh_engine._play_ramp_start_ts = 0.0

    oracle_widget = SpotifyVisualizerWidget(parent=fresh_parent, bar_count=bar_count)
    qtbot.addWidget(oracle_widget)
    oracle_widget._engine = fresh_engine
    oracle_widget._enabled = True
    oracle_widget._spotify_playing = True
    oracle_widget._vis_mode = VisualizerMode.BUBBLE
    oracle_widget.reset_runtime_activation_state(reason="oracle")
    _apply_authored_bubble_deep_sea(oracle_widget)

    fresh_frame = _capture_first_visible_frame(
        oracle_widget,
        fresh_parent,
        fresh_engine,
        _synthetic_phrase(np_module),
    )

    live_bars = list(live_frame["bars"])
    fresh_bars = list(fresh_frame["bars"])
    assert live_frame["vis_mode"] == "bubble"
    assert fresh_frame["vis_mode"] == "bubble"
    assert max(live_bars) >= 0.08
    assert max(fresh_bars) >= 0.08
    assert live_bars == pytest.approx(fresh_bars, abs=0.03)


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
    widget._bubble_last_perf_diag = {  # type: ignore[attr-defined]
        "worker_total_ms": 3.2,
        "tick_ms": 2.4,
        "collision_ms": 1.1,
        "snapshot_ms": 0.6,
        "collision_pairs": 48.0,
        "collision_overlaps": 7.0,
        "collision_passes": 2.0,
        "active_bubbles": 24.0,
        "snapshot_trail_payload_active": 0.0,
        "snapshot_trail_floats": 0.0,
    }

    with caplog.at_level("INFO"):
        widget._log_perf_snapshot(reset=True)  # type: ignore[attr-defined]

    messages = [r.message for r in caplog.records]
    assert any("[PERF] [SPOTIFY_VIS] Tick metrics" in m for m in messages)
    assert any("[PERF] [SPOTIFY_VIS][BUBBLE] worker_ms=3.20" in m for m in messages)


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
def test_spotify_visualizer_watchdog_does_not_force_reveal_when_startup_begins_paused(
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
    vis.set_visualization_mode(VisualizerMode.SPECTRUM)

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
    vis._finish_staged_startup_reveal(reason="startup_watchdog")

    assert vis._startup_reveal_pending is True
    assert fade_calls == []

    vis._waiting_for_fresh_frame = False
    vis.handle_media_update({"state": "playing"})

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

    vis.stop()


@pytest.mark.qt
def test_oscilloscope_watchdog_still_waits_for_play_when_startup_begins_paused(
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
    vis.set_visualization_mode(VisualizerMode.OSCILLOSCOPE)

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.start()
    vis.begin_spotify_secondary_stage()
    qt_app.processEvents()

    assert vis._startup_require_playing_before_reveal is True
    vis._startup_reveal_not_before_ts = 0.0
    vis._finish_staged_startup_reveal(reason="startup_watchdog")

    assert vis._startup_reveal_pending is True
    assert fade_calls == []

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
    vis.set_visualization_mode(VisualizerMode.SPECTRUM)

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
def test_spotify_visualizer_watchdog_does_not_override_authoritative_media_wait(
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
    vis._enabled = True
    vis._startup_reveal_pending = True
    vis._startup_reveal_not_before_ts = 0.0
    vis._startup_require_playing_before_reveal = False
    vis._startup_idle_reveal_requires_authoritative_media = True
    vis._startup_has_authoritative_media_update = False
    vis._waiting_for_fresh_frame = False

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis._finish_staged_startup_reveal(reason="startup_watchdog")

    assert vis._startup_reveal_pending is True
    assert fade_calls == []


@pytest.mark.qt
def test_shared_nonplaying_seed_allows_idle_startup_reveal_for_bubble(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    class _Anchor(QWidget):
        _shared_payload = {"state": "paused"}

        def __init__(self, parent=None):
            super().__init__(parent)
            self.refresh_calls = 0

        @classmethod
        def _get_shared_valid_info(cls):
            return dict(cls._shared_payload)

        def refresh_playback_state(self):
            self.refresh_calls += 1

    anchor = _Anchor(parent)
    anchor.show()

    fake_engine = _FakeEngine(bar_count=10)
    _patch_shared_engine(monkeypatch, lambda *_: fake_engine)

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=10)
    vis.set_anchor_media_widget(anchor)
    vis._enabled = True
    vis._startup_reveal_pending = True
    vis._startup_reveal_not_before_ts = 0.0
    vis._startup_require_playing_before_reveal = False
    vis._waiting_for_fresh_frame = False

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis._seed_playback_state_from_anchor(reason="test_seed", request_refresh_if_missing=True)

    assert vis._startup_idle_reveal_requires_authoritative_media is False
    assert vis._startup_has_authoritative_media_update is False
    assert anchor.refresh_calls >= 1

    vis._finish_staged_startup_reveal(reason="authoritative_wait")

    assert vis._startup_reveal_pending is False
    assert fade_calls == [1500]

@pytest.mark.qt
def test_spotify_visualizer_media_update_sets_playing_state(qt_app):
    """Visualizer should track playing state from media updates."""
    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)
    
    vis._spotify_playing = True
    vis.handle_media_update({"state": "paused"})
    assert vis._spotify_playing is True
    assert vis._pending_playback_pause_timer is not None
    vis._pending_playback_pause_timer.timeout.emit()
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
    assert vis._spotify_playing is True
    assert vis._pending_playback_pause_timer is not None
    vis._pending_playback_pause_timer.timeout.emit()
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
    vis._spotify_playing = True
    vis.show()

    hide_calls = []
    fade_calls = []
    monkeypatch.setattr(vis, "hide", lambda: hide_calls.append(True))
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration_ms=1500: fade_calls.append(duration_ms))

    vis.handle_media_update({"state": "paused"})

    assert vis._spotify_playing is True
    assert engine_states == []
    assert vis._pending_playback_pause_timer is not None
    assert hide_calls == []
    assert fade_calls == []

    vis._pending_playback_pause_timer.timeout.emit()

    assert vis._spotify_playing is False
    assert engine_states == [False]
    assert hide_calls == []
    assert fade_calls == []

    vis.deleteLater()


@pytest.mark.qt
def test_spotify_visualizer_quick_playback_wobble_does_not_commit_pause(qt_app):
    """Rapid paused/playing flaps should not collapse visualizer playback state."""
    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)
    engine_states = []
    try:
        vis._engine = SimpleNamespace(set_playback_state=lambda playing: engine_states.append(bool(playing)))
        vis._spotify_playing = True

        vis.handle_media_update({"state": "paused"})

        assert vis._spotify_playing is True
        assert vis._pending_playback_pause_timer is not None
        assert engine_states == []

        vis.handle_media_update({"state": "playing"})

        assert vis._spotify_playing is True
        assert vis._pending_playback_pause_timer is None
        assert engine_states == []
    finally:
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
    assert vis._startup_wake_deferred_reason == ""
    assert fake_engine.wake_calls == 1
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
def test_spotify_visualizer_start_prefers_live_shared_playing_seed_over_local_paused_cache(qt_app, qtbot, monkeypatch):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    playing_info = SimpleNamespace(
        title="Track",
        artist="Artist",
        album="Album",
        state=SimpleNamespace(value="playing"),
        artwork_url="art://live",
    )

    class _Anchor(QWidget):
        _shared_last_valid_info = playing_info

        def __init__(self, parent=None):
            super().__init__(parent)
            self.refresh_requests = 0
            self._last_info = SimpleNamespace(
                title="Track",
                artist="Artist",
                album="Album",
                state=SimpleNamespace(value="paused"),
                artwork_url="art://retained",
            )

        @classmethod
        def _get_shared_valid_info(cls):
            return cls._shared_last_valid_info

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
