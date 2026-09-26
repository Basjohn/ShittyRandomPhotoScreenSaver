"""Generation cancellation: permanent in production, scoped to one test in the suite.

A retired generation must keep rejecting late UI publications forever. Tests
reuse small generation numbers, so the conftest boundary forgets cancelled
generations that have no queued or scheduled work left, and keeps the ones that
still do so their stale callbacks stay rejected.
"""
from __future__ import annotations

import threading

from core.threading import manager
from core.threading.manager import ThreadManager, forget_idle_generation_cancellations_for_tests


def _tagged(generation, sink):
    def callback():
        sink.append(generation)

    callback._srpss_runtime_generation = generation
    return callback


def test_a_cancelled_generation_rejects_until_the_test_boundary_forgets_it(qt_app):
    sink: list = []
    ThreadManager.cancel_queued_ui_callbacks(9101)
    assert ThreadManager.run_on_ui_thread(_tagged(9101, sink)) is False
    assert ThreadManager.run_on_ui_thread(_tagged(9101, sink)) is False  # still, without a boundary
    assert forget_idle_generation_cancellations_for_tests() >= 1
    assert ThreadManager.run_on_ui_thread(_tagged(9101, sink)) is True
    assert sink == [9101]


def test_a_cancelled_generation_with_queued_work_stays_cancelled(qt_app):
    sink: list = []
    manager._ensure_ui_invoker()  # created on the UI thread, as in production
    worker = threading.Thread(target=lambda: ThreadManager.run_on_ui_thread(_tagged(9102, sink)))
    worker.start()
    worker.join()
    ThreadManager.cancel_queued_ui_callbacks(9102)

    forget_idle_generation_cancellations_for_tests()  # one callback still queued
    qt_app.processEvents()
    assert sink == []  # the stale queued callback was rejected

    forget_idle_generation_cancellations_for_tests()  # nothing queued any more
    assert ThreadManager.run_on_ui_thread(_tagged(9102, sink)) is True
    assert sink == [9102]
