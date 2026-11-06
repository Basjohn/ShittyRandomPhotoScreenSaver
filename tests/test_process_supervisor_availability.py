"""A worker start/stop never freezes the callers that only ask about the worker.

Operator evidence (6 Nov 10:30 slow startup): the heartbeat thread restarted a
child that never signalled ready. ``stop()`` and ``start()`` held the one
supervisor state lock across the graceful join / terminate / kill and the
10 s ready wait, so the GUI thread's ``is_running(IMAGE)`` (inside the first
image change, nested in a Feeds delivery callback) and the usage sampler's
``get_image_worker_usage_snapshot()`` both queued behind it for ~7 s and ~10 s.

These tests drive the real ProcessSupervisor with stand-in child processes and
measure the slowest availability call made while a transition is running.
Each scenario has a negative control that reproduces the old shape (the whole
transition inside the state lock) and must fail the same budget.
"""
from __future__ import annotations

import queue
import threading
import time
from types import SimpleNamespace

import pytest

import core.process.supervisor as supervisor_module
from core.process.supervisor import ProcessSupervisor
from core.process.types import (
    MessageType,
    WorkerResponse,
    WorkerState,
    WorkerType,
)

ROLE = WorkerType.IMAGE_PREFETCH
# An availability call is microseconds of dictionary work; anything near this
# budget means it waited on a transition.
CALL_BUDGET_S = 0.15


class _FakeQueue(queue.Queue):
    def __init__(self, maxsize=0):
        super().__init__(maxsize)

    def cancel_join_thread(self):
        pass

    def close(self):
        pass

    def join_thread(self):
        pass


class _StubbornChild:
    """A child that ignores SHUTDOWN and TERMINATE and only dies to kill()."""

    pid = 4242424

    def __init__(self, *, spawn_s=0.0, ready_queue=None):
        self._dead = threading.Event()
        self._spawn_s = spawn_s
        self._ready_queue = ready_queue
        self.terminated = False
        self.killed = False
        self.closed = False
        self.joining = threading.Event()

    def start(self):
        time.sleep(self._spawn_s)

    def is_alive(self):
        return not self._dead.is_set()

    def join(self, timeout=None):
        self.joining.set()
        self._dead.wait(timeout)

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True
        self._dead.set()

    def close(self):
        self.closed = True


def _supervisor(monkeypatch, child, *, ready_s=0.6):
    monkeypatch.setattr(supervisor_module, "Queue", _FakeQueue)
    monkeypatch.setattr(supervisor_module, "PROCESS_TERMINATE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(
        supervisor_module, "mp", SimpleNamespace(Process=lambda **_kwargs: child)
    )
    monkeypatch.setattr(
        ProcessSupervisor, "_apply_worker_process_priority", lambda *_a, **_k: None
    )
    supervisor = ProcessSupervisor()
    supervisor.WORKER_READY_TIMEOUT_S = ready_s
    supervisor.register_worker_factory(ROLE, lambda *_queues: None)
    return supervisor


def _hold_state_lock(monkeypatch, method_name):
    """Reproduce the old shape: the whole transition runs inside ``_lock``."""
    original = getattr(ProcessSupervisor, method_name)

    def held(self, *args, **kwargs):
        with self._lock:
            return original(self, *args, **kwargs)

    monkeypatch.setattr(ProcessSupervisor, method_name, held)


def _slowest_availability_call(supervisor, transition, ready, extra=None):
    """Run the GUI-thread / sampler calls until ``transition`` ends.

    Returns the slowest call and, per call kind, every answer given meanwhile.
    ``extra`` (the heartbeat monitor) is exercised once, mid-transition.
    """
    assert ready.wait(2.0), "transition never reached its blocking wait"
    probes = {
        "is_running": lambda: supervisor.is_running(ROLE),
        "send_message": lambda: supervisor.send_message(ROLE, MessageType.HEARTBEAT, {}),
        "usage_snapshot": lambda: supervisor.get_image_worker_usage_snapshot(),
        "get_health": lambda: supervisor.get_health(ROLE),
    }
    answers = {name: [] for name in probes}
    worst = 0.0
    while transition.is_alive():
        calls = list(probes.items())
        if extra is not None:
            calls.append(("extra", extra))
            extra = None
        for name, call in calls:
            started = time.perf_counter()
            outcome = call()
            worst = max(worst, time.perf_counter() - started)
            if name in answers:
                answers[name].append(outcome)
        time.sleep(0.005)
    assert all(answers.values())
    return worst, answers


def _run_stop(monkeypatch, *, old_shape):
    child = _StubbornChild()
    supervisor = _supervisor(monkeypatch, child)
    supervisor._workers[ROLE] = child
    supervisor._request_queues[ROLE] = _FakeQueue()
    supervisor._response_queues[ROLE] = _FakeQueue()
    supervisor._health[ROLE].state = WorkerState.RUNNING
    if old_shape:
        _hold_state_lock(monkeypatch, "_stop_role")
    stopped = []
    transition = threading.Thread(
        target=lambda: stopped.append(supervisor.stop(ROLE, timeout=0.6)), daemon=True
    )
    started = time.perf_counter()
    transition.start()
    try:
        worst, results = _slowest_availability_call(supervisor, transition, child.joining)
        transition.join(5.0)
        assert stopped == [True]
        assert time.perf_counter() - started >= 0.6  # a genuinely long stop
        assert child.terminated and child.killed and child.closed
        assert ROLE not in supervisor._workers
        return worst, results
    finally:
        supervisor.shutdown(timeout=0.1)


def _run_start(monkeypatch, *, old_shape):
    child = _StubbornChild(spawn_s=0.15)  # never signals ready
    supervisor = _supervisor(monkeypatch, child, ready_s=0.6)
    if old_shape:
        _hold_state_lock(monkeypatch, "_start_role")
    restarts = []
    monkeypatch.setattr(supervisor, "restart", lambda role: restarts.append(role))
    result = []
    entered = threading.Event()
    real_get = _FakeQueue.get

    def watched_get(self, *args, **kwargs):
        entered.set()  # the ready wait has begun
        return real_get(self, *args, **kwargs)

    monkeypatch.setattr(_FakeQueue, "get", watched_get)
    transition = threading.Thread(target=lambda: result.append(supervisor.start(ROLE)), daemon=True)
    transition.start()
    try:
        # The heartbeat monitor must neither stall nor judge a role mid-start.
        worst, results = _slowest_availability_call(
            supervisor, transition, entered, extra=supervisor._heartbeat_check
        )
        transition.join(5.0)
        assert result == [False]  # never signalled ready: the existing outcome
        assert supervisor._health[ROLE].state == WorkerState.ERROR
        return worst, results, restarts
    finally:
        child.kill()
        supervisor.shutdown(timeout=0.1)


def test_stop_does_not_block_availability_calls(monkeypatch):
    worst, results = _run_stop(monkeypatch, old_shape=False)
    assert worst < CALL_BUDGET_S
    # While the role is being torn down it is simply not available.
    assert not any(results["is_running"])
    assert not any(results["send_message"])


def test_stop_negative_control_old_shape_blocks_callers(monkeypatch):
    worst, _results = _run_stop(monkeypatch, old_shape=True)
    assert worst >= CALL_BUDGET_S


def test_start_does_not_block_availability_calls_or_the_heartbeat(monkeypatch):
    worst, results, restarts = _run_start(monkeypatch, old_shape=False)
    assert worst < CALL_BUDGET_S
    assert not any(results["is_running"])  # not available until ready
    assert restarts == []  # the monitor left the role alone while it started


def test_start_negative_control_old_shape_blocks_callers(monkeypatch):
    worst, _results, _restarts = _run_start(monkeypatch, old_shape=True)
    assert worst >= CALL_BUDGET_S


def test_a_ready_worker_becomes_available_and_stops_cleanly(monkeypatch):
    """Happy path: availability is withheld only while the transition runs."""
    child = _StubbornChild()
    supervisor = _supervisor(monkeypatch, child, ready_s=2.0)
    real_start = child.start
    # The stand-in posts its ready signal once it is "running".
    def start_and_signal():
        real_start()
        supervisor._response_queues[ROLE].put(WorkerResponse(
            msg_type=MessageType.WORKER_READY, seq_no=0,
            correlation_id="ready", success=True,
        ).to_dict())
    child.start = start_and_signal
    try:
        assert supervisor.start(ROLE) is True
        assert supervisor.is_running(ROLE) is True
        assert ROLE not in supervisor._transitioning
        assert supervisor._health[ROLE].state == WorkerState.RUNNING
        assert supervisor.send_message(ROLE, MessageType.HEARTBEAT, {}) is not None
        assert supervisor.stop(ROLE, timeout=0.1) is True
        assert supervisor.is_running(ROLE) is False
        assert ROLE not in supervisor._transitioning
    finally:
        child.kill()
        supervisor.shutdown(timeout=0.1)
