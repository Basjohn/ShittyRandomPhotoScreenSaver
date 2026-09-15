from __future__ import annotations

import threading
import time

import pytest

import core.threading.background_tasks as background_tasks
from core.threading.background_tasks import BackgroundTaskScheduler


def test_background_scheduler_is_lazy_and_serial(monkeypatch):
    monkeypatch.setattr(
        background_tasks,
        "_apply_background_thread_priority",
        lambda: (True, "test_below_normal", -1),
    )
    scheduler = BackgroundTaskScheduler(max_pending=1)
    assert scheduler.diagnostic_snapshot()["worker_threads"] == 0

    release = threading.Event()
    started = threading.Event()
    completed = threading.Event()
    callbacks = []

    def work():
        started.set()
        assert release.wait(2.0)
        return 42

    def done(result):
        callbacks.append(result)
        completed.set()

    scheduler.submit(
        work,
        callback=done,
        task_id="background-one",
        category="image.prefetch_scaled",
        runtime_generation=7,
        owner_class="Owner",
        owner_id=123,
    )
    assert started.wait(2.0)
    snap = scheduler.diagnostic_snapshot()
    assert snap["worker_threads"] == 1
    assert snap["worker_active"] == 1
    assert snap["priority_applied"] is True
    assert snap["priority_mode"] == "test_below_normal"
    assert scheduler.lifecycle_work_snapshot()[0]["category"] == "image.prefetch_scaled"

    release.set()
    assert completed.wait(2.0)
    assert callbacks[0].success is True
    assert callbacks[0].result == 42
    assert scheduler.shutdown(wait=True, timeout=2.0) is True


def test_background_scheduler_bounds_pending_work(monkeypatch):
    monkeypatch.setattr(
        background_tasks,
        "_apply_background_thread_priority",
        lambda: (True, "test_below_normal", -1),
    )
    scheduler = BackgroundTaskScheduler(max_pending=1)
    active_started = threading.Event()
    active_release = threading.Event()

    def active():
        active_started.set()
        assert active_release.wait(2.0)

    scheduler.submit(
        active,
        callback=None,
        task_id="active",
        category="test",
        runtime_generation=None,
        owner_class=None,
        owner_id=None,
    )
    assert active_started.wait(2.0)
    scheduler.submit(
        lambda: None,
        callback=None,
        task_id="pending",
        category="test",
        runtime_generation=None,
        owner_class=None,
        owner_id=None,
    )
    with pytest.raises(RuntimeError, match="queue is full"):
        scheduler.submit(
            lambda: None,
            callback=None,
            task_id="overflow",
            category="test",
            runtime_generation=None,
            owner_class=None,
            owner_id=None,
        )

    active_release.set()
    deadline = time.monotonic() + 2.0
    while scheduler.diagnostic_snapshot()["tasks_completed"] < 2:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert scheduler.shutdown(wait=True, timeout=2.0) is True


def test_background_scheduler_failure_still_completes_callback(monkeypatch):
    monkeypatch.setattr(
        background_tasks,
        "_apply_background_thread_priority",
        lambda: (True, "test_below_normal", -1),
    )
    scheduler = BackgroundTaskScheduler()
    completed = threading.Event()
    results = []

    def explode():
        raise ValueError("boom")

    def done(result):
        results.append(result)
        completed.set()

    scheduler.submit(
        explode,
        callback=done,
        task_id="explode",
        category="test",
        runtime_generation=None,
        owner_class=None,
        owner_id=None,
    )
    assert completed.wait(2.0)
    assert results[0].success is False
    assert isinstance(results[0].error, ValueError)
    assert scheduler.diagnostic_snapshot()["tasks_failed"] == 1
    assert scheduler.shutdown(wait=True, timeout=2.0) is True
