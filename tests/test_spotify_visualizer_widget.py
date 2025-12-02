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
def test_spotify_visualizer_tick_uses_compute_bars(qt_app, qtbot, monkeypatch):
    """Tick path should consume AudioFrames and delegate bar computation.

    This guards the architecture where heavy FFT/band mapping work lives in the
    UI tick path instead of the high-frequency audio callback.
    """

    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qtbot.addWidget(widget)
    widget.resize(400, 120)

    calls: Dict[str, int] = {"count": 0}

    def _fake_compute(samples):  # type: ignore[override]
        calls["count"] += 1
        # Return a simple, valid bar vector in [0, 1].
        return [0.5] * widget._bar_count  # type: ignore[attr-defined]

    # Ensure compute_bars_from_samples is what _on_tick uses to derive bars.
    monkeypatch.setattr(widget._audio_worker, "compute_bars_from_samples", _fake_compute)  # type: ignore[attr-defined]

    # Feed a synthetic AudioFrame into the lock-free buffer.
    frame = _AudioFrame(samples=b"dummy")
    widget._bars_buffer.publish(frame)  # type: ignore[attr-defined]

    # Mark widget as enabled/playing so tick path applies target bars.
    widget._enabled = True  # type: ignore[attr-defined]
    widget._spotify_playing = True  # type: ignore[attr-defined]

    widget._on_tick()  # type: ignore[attr-defined]
    qt_app.processEvents()

    # We expect exactly one call into compute_bars_from_samples for this tick.
    assert calls["count"] == 1
    assert len(widget._target_bars) == widget._bar_count  # type: ignore[attr-defined]
    assert all(0.0 <= v <= 1.0 for v in widget._target_bars)  # type: ignore[attr-defined]


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
def test_spotify_visualizer_tick_respects_fps_cap(qt_app, qtbot, monkeypatch):
    widget = SpotifyVisualizerWidget(parent=None, bar_count=16)
    qtbot.addWidget(widget)
    widget.resize(400, 120)

    class DummyEngine:
        def tick(self):
            return [1.0] * widget._bar_count  # type: ignore[attr-defined]

    widget._engine = DummyEngine()  # type: ignore[attr-defined]
    widget._enabled = True  # type: ignore[attr-defined]
    widget._spotify_playing = True  # type: ignore[attr-defined]

    calls: Dict[str, int] = {"count": 0}

    def _fake_update() -> None:
        calls["count"] += 1

    widget.update = _fake_update  # type: ignore[assignment]

    times = [0.0, 0.01, 0.02, 0.02]

    def _fake_time() -> float:
        if times:
            value = times[0]
            if len(times) > 1:
                times.pop(0)
            return value
        return 0.02

    monkeypatch.setattr(vis_mod.time, "time", _fake_time)

    widget._on_tick()  # type: ignore[attr-defined]
    widget._on_tick()  # type: ignore[attr-defined]

    assert calls["count"] == 1


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
