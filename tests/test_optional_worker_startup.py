"""Engine startup never waits on the OPTIONAL image_prefetch child.

Operator evidence (6 Nov 10:30 slow startup): ``_start_workers`` ran
``ProcessSupervisor.start(IMAGE_PREFETCH)`` on the engine init thread. The child
never signalled ready under load, so initialization sat in the 10 s ready wait
(10:30:10 to :20) before the engine could start or show its first image. The
speculative worker is optional (callers already handle "not running"), so its
start now runs on a ThreadManager IO worker; the required IMAGE worker keeps its
inline ready contract.

The tests drive the real ``ScreensaverEngine._start_workers`` and a real
``ProcessSupervisor`` with stand-in child processes. The negative control puts
the old synchronous wait back and must fail the same budget.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import core.process.supervisor as supervisor_module
from core.process.supervisor import ProcessSupervisor
from core.process.types import MessageType, WorkerResponse, WorkerState, WorkerType
from tests.test_process_supervisor_availability import _FakeQueue, _StubbornChild

READY_TIMEOUT_S = 0.8


class _RoleChild(_StubbornChild):
    """Child that posts WORKER_READY ``ready_after_s`` after spawn, or never."""

    def __init__(self, resp_queue, *, ready_after_s=None):
        super().__init__(spawn_s=ready_after_s or 0.0)
        self._resp = resp_queue
        self._signals_ready = ready_after_s is not None

    def start(self):
        super().start()
        if self._signals_ready:
            self._resp.put(WorkerResponse(
                msg_type=MessageType.WORKER_READY, seq_no=0,
                correlation_id="ready", success=True,
            ).to_dict())


class _IoPool:
    """ThreadManager stand-in: IO tasks run on a real thread, like the pool."""

    def __init__(self):
        self.threads = []

    def submit_io_task(self, func, **_kwargs):
        thread = threading.Thread(target=func, daemon=True)
        self.threads.append(thread)
        thread.start()

    def join(self, timeout=5.0):
        for thread in self.threads:
            thread.join(timeout)


def _engine(monkeypatch, prefetch_ready_after_s, ready_timeout_s=READY_TIMEOUT_S):
    from engine.screensaver_engine import ScreensaverEngine

    children = {}

    def make_child(**kwargs):
        role = WorkerType.IMAGE_PREFETCH if "prefetch" in kwargs["name"] else WorkerType.IMAGE
        ready = prefetch_ready_after_s if role == WorkerType.IMAGE_PREFETCH else 0.0
        children[role] = _RoleChild(kwargs["args"][1], ready_after_s=ready)
        return children[role]

    monkeypatch.setattr(supervisor_module, "Queue", _FakeQueue)
    monkeypatch.setattr(supervisor_module, "PROCESS_TERMINATE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(supervisor_module, "mp", SimpleNamespace(Process=make_child))
    monkeypatch.setattr(
        ProcessSupervisor, "_apply_worker_process_priority", lambda *_a, **_k: None
    )
    supervisor = ProcessSupervisor()
    supervisor.WORKER_READY_TIMEOUT_S = ready_timeout_s
    supervisor.register_worker_factory(WorkerType.IMAGE, lambda *_q: None)
    supervisor.register_worker_factory(WorkerType.IMAGE_PREFETCH, lambda *_q: None)
    values = {"workers.max_workers": 2, "workers.image.enabled": True}
    pool = _IoPool()
    engine = SimpleNamespace(
        _process_supervisor=supervisor,
        _prefetch_ahead=4,
        _display_selection_suspended=lambda: False,
        _workers_waiting_for_display=False,
        thread_manager=pool,
        settings_manager=SimpleNamespace(get=values.__getitem__),
    )
    engine._start_optional_worker = lambda *a: ScreensaverEngine._start_optional_worker(engine, *a)
    return ScreensaverEngine, engine, supervisor, pool, children


def test_startup_does_not_wait_for_the_optional_prefetch_child(monkeypatch):
    cls, engine, supervisor, pool, _children = _engine(monkeypatch, None)  # never ready
    try:
        started = time.perf_counter()
        cls._start_workers(engine)
        init_thread_s = time.perf_counter() - started
        # Required worker: ready inline, exactly as before.
        assert supervisor.is_running(WorkerType.IMAGE) is True
        # Optional worker: startup proceeded without it.
        assert init_thread_s < READY_TIMEOUT_S / 2
        assert supervisor.is_running(WorkerType.IMAGE_PREFETCH) is False
        pool.join()
        assert supervisor._health[WorkerType.IMAGE_PREFETCH].state == WorkerState.ERROR
    finally:
        supervisor.shutdown(timeout=0.1)


def test_negative_control_old_synchronous_wait_blocks_init(monkeypatch):
    cls, engine, supervisor, _pool, _children = _engine(monkeypatch, None)

    def synchronous(worker_type, _name, _failure):
        supervisor.start(worker_type)  # the old shape: wait for ready inline
        return True

    engine._start_optional_worker = synchronous
    try:
        started = time.perf_counter()
        cls._start_workers(engine)
        assert time.perf_counter() - started >= READY_TIMEOUT_S
    finally:
        supervisor.shutdown(timeout=0.1)


def test_optional_prefetch_becomes_available_when_it_signals_ready(monkeypatch):
    cls, engine, supervisor, pool, _children = _engine(monkeypatch, 0.3)
    try:
        cls._start_workers(engine)
        assert supervisor.is_running(WorkerType.IMAGE_PREFETCH) is False  # still spawning
        pool.join()
        assert supervisor.is_running(WorkerType.IMAGE_PREFETCH) is True
        assert supervisor._health[WorkerType.IMAGE_PREFETCH].state == WorkerState.RUNNING
    finally:
        supervisor.shutdown(timeout=0.1)


def test_supervisor_shutdown_aborts_the_background_ready_wait_and_retires_the_child(monkeypatch):
    cls, engine, supervisor, pool, children = _engine(monkeypatch, None, ready_timeout_s=30.0)
    cls._start_workers(engine)
    deadline = time.perf_counter() + 2.0
    while WorkerType.IMAGE_PREFETCH not in children and time.perf_counter() < deadline:
        time.sleep(0.005)
    time.sleep(0.1)  # inside the ready wait
    started = time.perf_counter()
    supervisor.shutdown(timeout=1.0)
    pool.join(5.0)
    assert time.perf_counter() - started < 5.0  # not the 30 s ready wait
    assert not any(thread.is_alive() for thread in pool.threads)
    assert children[WorkerType.IMAGE_PREFETCH].killed
    assert WorkerType.IMAGE_PREFETCH not in supervisor._workers


def test_a_refused_background_start_is_reported_failed_without_blocking(monkeypatch):
    cls, engine, supervisor, _pool, _children = _engine(monkeypatch, 0.0)

    def refuse(_func, **_kwargs):
        raise RuntimeError("Thread manager is shut down")

    engine.thread_manager = SimpleNamespace(submit_io_task=refuse)
    try:
        cls._start_workers(engine)
        assert supervisor.is_running(WorkerType.IMAGE) is True
        assert supervisor.is_running(WorkerType.IMAGE_PREFETCH) is False
    finally:
        supervisor.shutdown(timeout=0.1)
