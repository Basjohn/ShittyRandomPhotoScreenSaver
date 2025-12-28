from __future__ import annotations

import time
from typing import Callable

import pytest

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    SpotifyVisualizerWidget,
    _AudioFrame,
)
import widgets.spotify_visualizer_widget as vis_mod
from PySide6.QtWidgets import QWidget


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


def test_manual_floor_produces_higher_energy_than_dynamic(np_module):
    worker = _make_audio_worker(np_module)
    fft = _synth_fft(np_module, magnitude=2.5)

    worker.set_floor_config(dynamic_enabled=True, manual_floor=2.1)
    bars_dynamic = worker._fft_to_bars(fft)

    worker.set_floor_config(dynamic_enabled=False, manual_floor=0.2)
    bars_manual = worker._fft_to_bars(fft)

    assert isinstance(bars_dynamic, list)
    assert isinstance(bars_manual, list)
    assert max(bars_manual) > max(bars_dynamic)


def test_sensitivity_config_affects_noise_floor(np_module):
    worker = _make_audio_worker(np_module)
    worker.set_floor_config(dynamic_enabled=False, manual_floor=2.1)
    fft = _synth_fft(np_module, magnitude=2.5)

    worker.set_sensitivity_config(recommended=True, sensitivity=1.0)
    bars_rec = worker._fft_to_bars(fft)

    worker.set_sensitivity_config(recommended=False, sensitivity=2.5)
    bars_manual = worker._fft_to_bars(fft)

    assert isinstance(bars_rec, list)
    assert isinstance(bars_manual, list)
    assert max(bars_manual) > max(bars_rec)


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

    widget._perf_tick_start_ts = 0.0  # type: ignore[attr-defined]
    widget._perf_tick_last_ts = 1.0  # type: ignore[attr-defined]
    widget._perf_tick_frame_count = 60  # type: ignore[attr-defined]
    widget._perf_tick_min_dt = 1.0 / 120.0  # type: ignore[attr-defined]
    widget._perf_tick_max_dt = 1.0 / 20.0  # type: ignore[attr-defined]

    with caplog.at_level("INFO"):
        widget._log_perf_snapshot(reset=True)  # type: ignore[attr-defined]

    messages = [r.message for r in caplog.records]
    assert any("[PERF] [SPOTIFY_VIS] Tick metrics" in m for m in messages)


def test_spotify_visualizer_bars_not_stuck_at_top():
    try:
        import numpy as np  # type: ignore[import]
    except Exception:
        pytest.skip("numpy not available for Spotify visualiser tests")

    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=15, buffer=buf)
    worker._np = np  # type: ignore[attr-defined]

    n_samples = 2048
    sample_rate = 48000
    t = np.arange(n_samples, dtype=np.float32) / np.float32(sample_rate)

    bars_center = []
    frames = 120
    for frame in range(frames):
        intensity = np.float32(0.1 + 0.9 * (0.5 + 0.5 * np.sin(np.float32(2.0 * np.pi) * np.float32(frame) / np.float32(60.0))))
        env = np.exp(-t * np.float32(20.0)).astype(np.float32)
        base = (np.sin(np.float32(2.0 * np.pi * 80.0) * t) * env).astype(np.float32)
        samples = (base * (np.float32(0.03) * intensity)).astype(np.float32)
        bars = worker.compute_bars_from_samples(samples)
        if not isinstance(bars, list) or not bars:
            continue
        center_idx = len(bars) // 2
        bars_center.append(float(bars[center_idx]))

    assert bars_center

    center_arr = np.asarray(bars_center, dtype=np.float32)
    cmin = float(center_arr.min())
    cmax = float(center_arr.max())
    stuck_frac = float(np.mean(center_arr >= np.float32(0.98)))
    crange = cmax - cmin

    assert cmax >= 0.25
    assert crange >= 0.15
    assert stuck_frac <= 0.55


def test_spotify_visualizer_kick_emphasizes_center_more_than_vocals():
    try:
        import numpy as np  # type: ignore[import]
    except Exception:
        pytest.skip("numpy not available for Spotify visualiser tests")

    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=15, buffer=buf)
    worker._np = np  # type: ignore[attr-defined]

    n_samples = 2048
    sample_rate = 48000
    t = np.arange(n_samples, dtype=np.float32) / np.float32(sample_rate)

    env = np.exp(-t * np.float32(18.0)).astype(np.float32)
    kick_base = (np.sin(np.float32(2.0 * np.pi * 80.0) * t) * env).astype(np.float32)
    vocal_base = (
        np.sin(np.float32(2.0 * np.pi * 1000.0) * t) * np.float32(0.7)
        + np.sin(np.float32(2.0 * np.pi * 2000.0) * t) * np.float32(0.5)
    ).astype(np.float32)

    kick_samples = (kick_base * np.float32(0.03)).astype(np.float32)
    vocal_samples = (vocal_base * np.float32(0.03)).astype(np.float32)

    kick_bars = worker.compute_bars_from_samples(kick_samples)
    vocal_bars = worker.compute_bars_from_samples(vocal_samples)

    assert isinstance(kick_bars, list) and len(kick_bars) >= 5
    assert isinstance(vocal_bars, list) and len(vocal_bars) >= 5

    n = len(kick_bars)
    c = n // 2
    q = n // 4
    tq = (3 * n) // 4

    center_kick = float(np.mean(kick_bars[max(0, c - 1):min(n, c + 2)]))
    shoulder_kick = float((kick_bars[q] + kick_bars[tq]) * 0.5)

    center_vocal = float(np.mean(vocal_bars[max(0, c - 1):min(n, c + 2)]))
    shoulder_vocal = float((vocal_bars[q] + vocal_bars[tq]) * 0.5)

    assert (center_kick - shoulder_kick) > (center_vocal - shoulder_vocal)


@pytest.mark.qt
def test_spotify_visualizer_media_update_requires_visible_anchor(qt_app, qtbot, monkeypatch):
    """Visualizer should only fade in when anchor media widget is visible."""

    vis = SpotifyVisualizerWidget(parent=None, bar_count=12)
    qtbot.addWidget(vis)

    anchor = QWidget()
    qtbot.addWidget(anchor)
    anchor.resize(200, 80)
    anchor.hide()

    vis.set_anchor_media_widget(anchor)
    vis.hide()

    fade_calls: list[int] = []

    def _fake_fade(duration_ms: int = 1500) -> None:
        fade_calls.append(duration_ms)
        vis.show()

    monkeypatch.setattr(vis, "_start_widget_fade_in", _fake_fade)

    vis.handle_media_update({"state": "playing"})
    qt_app.processEvents()

    assert fade_calls == []
    assert not vis.isVisible()

    anchor.show()
    qt_app.processEvents()

    vis.handle_media_update({"state": "playing"})
    qt_app.processEvents()

    assert fade_calls == [1500]


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
def test_spotify_visualizer_media_update_zeroes_bars_when_not_playing(qt_app):
    """Visualizer should zero target bars when Spotify stops playing."""

    vis = SpotifyVisualizerWidget(parent=None, bar_count=10)

    vis._target_bars = [0.5] * vis._bar_count  # type: ignore[attr-defined]
    vis._spotify_playing = True  # type: ignore[attr-defined]

    vis.handle_media_update({"state": "paused"})

    assert vis._spotify_playing is False  # type: ignore[attr-defined]
    assert all(value == 0.0 for value in vis._target_bars)  # type: ignore[attr-defined]
    vis.deleteLater()
