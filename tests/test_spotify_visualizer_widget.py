from __future__ import annotations

import time
from typing import Callable

import pytest

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer import mode_transition
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    SpotifyVisualizerWidget,
    _AudioFrame,
)
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.energy_bands import EnergyBands
import widgets.spotify_visualizer_widget as vis_mod
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
    # Re-enabling dynamic should not disturb the snapped running average.
    assert worker._raw_bass_avg == pytest.approx(worker._min_floor)  # type: ignore[attr-defined]


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
    worker.set_floor_config(dynamic_enabled=True, manual_floor=2.1)
    assert worker._use_dynamic_floor is True
    
    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.5)
    assert worker._use_dynamic_floor is False


def test_sensitivity_config_api_exists(np_module):
    """Verify sensitivity config API exists and accepts parameters."""
    worker = _make_audio_worker(np_module)
    
    # API should exist and not raise
    worker.set_sensitivity_config(recommended=True, sensitivity=1.0)
    worker.set_sensitivity_config(recommended=False, sensitivity=2.5)


class _FakeEngine:
    def __init__(self) -> None:
        self._audio_buffer = object()
        self._audio_worker = object()
        self._bars_result_buffer = object()
        self.last_floor_config = (True, 2.1)
        self.last_sensitivity_config = (True, 1.0)
        self.thread_manager = None
        self.acquired = 0
        self.started = 0
        self.reset_calls = 0

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

    def ensure_started(self) -> None:
        self.started += 1

    def reset_smoothing_state(self) -> None:
        self.reset_calls += 1


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
    fake_engine.last_floor_config = (True, 2.1)
    fake_engine.last_sensitivity_config = (True, 1.0)

    widget.start()
    qt_app.processEvents()

    assert fake_engine.last_floor_config == (False, 0.3)
    assert fake_engine.last_sensitivity_config == (False, 2.4)


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
def test_mode_cycle_replays_cached_config(qt_app, qtbot, monkeypatch):
    """Double-click mode cycle should replay cached kwargs for parity with settings apply."""

    widget = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(widget)

    widget._cached_vis_kwargs = {"sine_travel_line2": 0.42}  # type: ignore[attr-defined]

    original_reset = SpotifyVisualizerWidget._reset_visualizer_state
    replay_flags: dict[str, bool | None] = {"replay": None}

    def _patched_reset(self, *, clear_overlay: bool = False, replay_cached: bool = False):
        replay_flags["replay"] = replay_cached
        return original_reset(self, clear_overlay=clear_overlay, replay_cached=replay_cached)

    monkeypatch.setattr(SpotifyVisualizerWidget, "_reset_visualizer_state", _patched_reset)

    assert mode_transition.cycle_mode(widget) is True
    # Fast-forward fade-out completion (phase 1 → phase 2)
    now = widget._mode_transition_ts + widget._mode_transition_duration + 0.01
    mode_transition.mode_transition_fade_factor(widget, now)

    assert (
        replay_flags["replay"] is True
    ), "Mode cycle should cold-reset and replay cached kwargs for reactivity parity"


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
    assert widget._display_bars == [0.0] * 8
    assert widget._target_bars == [0.0] * 8
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
    assert widget._mode_transition_resume_ts == 0.0


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
def test_shadow_cache_invalidated_once_per_cycle(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=8)
    qtbot.addWidget(widget)

    widget._pending_shadow_cache_invalidation = True  # type: ignore[attr-defined]
    widget.setGraphicsEffect(QGraphicsDropShadowEffect(widget))

    called = {"count": 0}

    def _fake_clear_cache(target_widget: QWidget) -> None:
        called["count"] += 1
        assert target_widget is widget

    monkeypatch.setattr(vis_mod, "clear_cached_shadow_for_widget", _fake_clear_cache)

    widget._invalidate_shadow_cache_if_needed()

    assert called["count"] == 1
    assert widget.graphicsEffect() is None
    assert widget._pending_shadow_cache_invalidation is False  # type: ignore[attr-defined]


@pytest.mark.qt
def test_spotify_visualizer_start_requests_fade_sync(qt_app, qtbot, monkeypatch):
    """Visualizer start should register with parent's overlay fade sync."""

    class _FakeParent(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, object]] = []

        def request_overlay_fade_sync(self, name: str, starter) -> None:
            self.calls.append((name, starter))
            # call immediately to simulate DisplayWidget behavior
            starter()

    parent = _FakeParent()
    qtbot.addWidget(parent)
    parent.resize(400, 200)
    parent.show()

    anchor = QWidget(parent)
    anchor.resize(200, 60)
    anchor.show()

    vis = SpotifyVisualizerWidget(parent=parent, bar_count=14)
    vis.set_anchor_media_widget(anchor)

    fade_calls: list[int] = []
    monkeypatch.setattr(vis, "_start_widget_fade_in", lambda duration=1500: fade_calls.append(duration))

    try:
        vis.start()
        qt_app.processEvents()

        assert parent.calls
        assert parent.calls[0][0] == "spotify_visualizer"
        assert fade_calls == [1500]
    finally:
        vis.deleteLater()
        parent.close()

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
