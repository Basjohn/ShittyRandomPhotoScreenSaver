from __future__ import annotations

import logging
import time


def test_transition_profiler_complete_uses_canonical_perf_flag(monkeypatch, caplog):
    from rendering.gl_profiler import TransitionProfiler

    profiler = TransitionProfiler()
    profiler.start("burn")
    profile = profiler._profiles["burn"]
    profile.start_ts = time.time() - 0.25
    profile.frame_count = 5
    profile.min_dt = 0.01
    profile.max_dt = 0.03

    monkeypatch.setattr("rendering.gl_profiler.is_perf_metrics_enabled", lambda: False)

    with caplog.at_level(logging.INFO):
        profiler.complete("burn", viewport_size=(100, 100))

    assert profiler.is_active("burn") is False
    assert not any("[PERF] [GL COMPOSITOR]" in message for message in caplog.messages)


def test_transition_profiler_complete_logs_when_perf_enabled(monkeypatch, caplog):
    from rendering.gl_profiler import TransitionProfiler

    profiler = TransitionProfiler()
    profiler.start("burn")
    profile = profiler._profiles["burn"]
    profile.start_ts = time.time() - 0.25
    profile.frame_count = 5
    profile.min_dt = 0.01
    profile.max_dt = 0.03

    monkeypatch.setattr("rendering.gl_profiler.is_perf_metrics_enabled", lambda: True)

    with caplog.at_level(logging.INFO):
        profiler.complete("burn", viewport_size=(100, 100))

    assert profiler.is_active("burn") is False
    assert any("[PERF] [GL COMPOSITOR] Burn metrics:" in message for message in caplog.messages)
