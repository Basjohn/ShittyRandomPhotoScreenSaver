from __future__ import annotations

import time
from typing import Dict

import pytest

from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer_widget import (
    SpotifyVisualizerAudioWorker,
    SpotifyVisualizerWidget,
    _AudioFrame,
)
import widgets.spotify_visualizer_widget as vis_mod


@pytest.mark.qt
def test_spotify_visualizer_tick_consumes_engine_smoothed_bars(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qtbot.addWidget(widget)
    widget.resize(400, 120)

    monkeypatch.setattr(vis_mod, "_global_beat_engine", None)
    widget._engine = vis_mod.get_shared_spotify_beat_engine(widget._bar_count)  # type: ignore[attr-defined]
    engine = widget._engine
    assert engine is not None

    bars = [0.5] * widget._bar_count  # type: ignore[attr-defined]

    calls: Dict[str, int] = {"tick": 0, "get": 0}

    def _fake_tick():
        calls["tick"] += 1

    def _fake_get_smoothed():
        calls["get"] += 1
        return list(bars)

    monkeypatch.setattr(engine, "tick", _fake_tick)
    monkeypatch.setattr(engine, "get_smoothed_bars", _fake_get_smoothed)

    widget._enabled = True  # type: ignore[attr-defined]
    widget._spotify_playing = True  # type: ignore[attr-defined]

    widget._on_tick()  # type: ignore[attr-defined]
    qt_app.processEvents()

    assert calls["tick"] == 1
    assert calls["get"] == 1
    assert len(widget._display_bars) == widget._bar_count  # type: ignore[attr-defined]
    assert all(abs(v - 0.5) < 1e-6 for v in widget._display_bars)  # type: ignore[attr-defined]


def test_spotify_visualizer_compute_bars_reasonable_runtime():
    """compute_bars_from_samples should remain reasonably fast.

    This is a coarse regression guard: if heavy per-sample work accidentally
    migrates into Python, or if bar mapping becomes pathologically slow, this
    test will fail. It does not target an exact FPS, only a sane upper bound
    for a batch of computations.
    """

    try:
        import numpy as np  # type: ignore[import]
    except Exception:
        pytest.skip("numpy not available for Spotify visualiser tests")

    buf: TripleBuffer[_AudioFrame] = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(bar_count=16, buffer=buf)

    # Seed the worker with a numpy module so compute_bars_from_samples works
    # without needing to start a real audio stream.
    worker._np = np  # type: ignore[attr-defined]

    samples = np.random.rand(4096).astype("float32")

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
