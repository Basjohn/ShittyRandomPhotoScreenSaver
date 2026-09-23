"""PW-02 validation telemetry: executor queue wait attributed per task category.

Pool-level queue wait was already recorded; which category waited was not. The
per-category total/max is diagnostics (--perf/--usage) only and adds nothing to
task accounting when diagnostics are off.
"""

from __future__ import annotations

import threading
import time

import core.threading.manager as manager_module
from core.threading.manager import ThreadManager


def _run_behind_saturated_pool(monkeypatch, *, diagnostics: bool) -> dict:
    monkeypatch.setattr(manager_module, "_category_queue_wait_enabled", lambda: diagnostics)
    manager = ThreadManager()
    release = threading.Event()
    started = threading.Barrier(5)
    done = threading.Event()
    try:
        for index in range(4):
            manager.submit_io_task(
                lambda: (started.wait(timeout=5.0), release.wait(timeout=5.0)),
                task_id=f"stall_{index}",
                category="network",
            )
        started.wait(timeout=5.0)  # every IO worker is busy
        manager.submit_io_task(done.set, task_id="refresh", category="media_refresh")
        time.sleep(0.12)
        release.set()
        assert done.wait(timeout=5.0)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            stats = manager.get_task_category_stats()
            if stats.get("media_refresh", {}).get("completed"):
                return stats
            time.sleep(0.01)
        return manager.get_task_category_stats()
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=5.0)


def test_queue_wait_is_attributed_to_the_waiting_category(monkeypatch) -> None:
    stats = _run_behind_saturated_pool(monkeypatch, diagnostics=True)

    refresh = stats["media_refresh"]
    assert refresh["queue_wait_ms_max"] >= 100.0
    assert refresh["queue_wait_ms_total"] >= refresh["queue_wait_ms_max"]
    assert stats["network"]["queue_wait_ms_max"] < 100.0


def test_no_queue_wait_accounting_without_diagnostics(monkeypatch) -> None:
    stats = _run_behind_saturated_pool(monkeypatch, diagnostics=False)

    assert "queue_wait_ms_max" not in stats["media_refresh"]
    assert "queue_wait_ms_total" not in stats["network"]
