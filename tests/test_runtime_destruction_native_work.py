"""The destruction barrier sees the native core's work (N3.8; the N2.5 audit's L8): a retiring generation is not
complete while the core still has work in flight (``NativeCore.pending_native_work``: jobs queued or running, releases
pending, replaced outputs retiring; audit N38 M3 took live items' textures out). The core is read only when the backend
owner loaded it (``rendering.quick.bootstrap.native_core``), never imported by the barrier."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from engine.runtime_destruction import RuntimeDestructionBarrier


class _EmptyResourceManager:
    @staticmethod
    def get_resources_by_runtime_generation(_generation):
        return ()


class _EmptyThreadManager:
    @staticmethod
    def get_lifecycle_ownership_snapshot():
        return {"active_tasks": (), "ui": {"queued_by_generation": {}, "scheduled_single_shots_by_generation": {}}}


def _engine() -> SimpleNamespace:
    return SimpleNamespace(resource_manager=_EmptyResourceManager(), thread_manager=_EmptyThreadManager(),
                           _pending_runtime_destruction_barrier=None, _terminal_shutdown_requested=False)


class _Core:
    """The loaded core as the barrier reads it: its pending work, as the test sets it."""

    def __init__(self) -> None:
        self.pending = [{"kind": "native_jobs_running", "count": 1}, {"kind": "native_job_images_retiring", "count": 2}]

    def pending_native_work(self):
        return list(self.pending)


def _barrier(engine, generation: int) -> tuple[RuntimeDestructionBarrier, list]:
    completed: list = []
    barrier = RuntimeDestructionBarrier(engine, reason="settings", retiring_generation=generation)
    engine._pending_runtime_destruction_barrier = barrier
    return barrier, completed


def test_the_barrier_waits_for_the_cores_jobs_and_textures(qt_app, qtbot, monkeypatch):
    core = _Core()
    monkeypatch.setitem(sys.modules, "rendering.quick.bootstrap", SimpleNamespace(native_core=lambda: core))
    engine = _engine()
    barrier, completed = _barrier(engine, 71)
    barrier.seal()
    barrier.then(lambda: completed.append(True))

    qtbot.wait(80)
    assert completed == []
    described = barrier.describe()
    assert described["native_work_pending"] == 2

    core.pending = []                                   # the jobs finished, the outputs and textures released
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)


def test_the_barrier_ignores_the_core_when_it_was_never_loaded(qt_app, qtbot, monkeypatch):
    # No backend owner module (never imported), or an owner that loaded no core: nothing native is pending.
    monkeypatch.delitem(sys.modules, "rendering.quick.bootstrap", raising=False)
    engine = _engine()
    barrier, completed = _barrier(engine, 72)
    barrier.seal()
    barrier.then(lambda: completed.append(True))
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)

    monkeypatch.setitem(sys.modules, "rendering.quick.bootstrap", SimpleNamespace(native_core=lambda: None))
    engine = _engine()
    barrier, completed = _barrier(engine, 73)
    barrier.seal()
    barrier.then(lambda: completed.append(True))
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)


def test_control_a_barrier_that_does_not_read_the_core_completes_over_pending_work(qt_app, qtbot, monkeypatch):
    # The negative control: the same pending work with the native reading taken out (the barrier before N3.8)
    # completes at once, which is the failure the first test catches.
    core = _Core()
    monkeypatch.setitem(sys.modules, "rendering.quick.bootstrap", SimpleNamespace(native_core=lambda: core))
    monkeypatch.setattr(RuntimeDestructionBarrier, "_remaining_native_work", lambda self: ())
    engine = _engine()
    barrier, completed = _barrier(engine, 74)
    barrier.seal()
    barrier.then(lambda: completed.append(True))
    qtbot.waitUntil(lambda: completed == [True], timeout=1000)
    assert core.pending                                 # completed although the core still had work
