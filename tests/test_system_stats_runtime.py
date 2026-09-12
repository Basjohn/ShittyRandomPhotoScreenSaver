"""Focused shared-owner/cardinality contracts for the CPU/RAM sampler lease."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.system_stats.source import CpuRamSample
from widgets.system_stats_runtime import (
    SAMPLE_INTERVAL_MS,
    SystemStatsRuntimeService,
    reset_shared_system_stats_runtime_for_tests,
    shared_system_stats_owner_count,
)


class _Source:
    def __init__(self) -> None:
        self.calls = 0
        self.closed = 0

    def sample(self) -> CpuRamSample:
        self.calls += 1
        return CpuRamSample(
            "warming" if self.calls == 1 else "ok",
            None if self.calls == 1 else 25.0,
            "ok",
            4,
            8,
        )

    def close(self) -> None:
        self.closed += 1


class _Harness:
    def __init__(self) -> None:
        self.scheduled: list[tuple[int, object]] = []
        self.submissions: list[tuple[object, object, str]] = []

    def schedule(self, delay, callback):
        self.scheduled.append((delay, callback))

    def submit_factory(self, _manager):
        def submit(work, complete, task_id):
            self.submissions.append((work, complete, task_id))
            return task_id

        return submit

    @staticmethod
    def ui_dispatch(callback):
        callback()
        return True

    def fire_next_timer(self):
        _delay, callback = self.scheduled.pop(0)
        callback()

    def fire_timer(self, delay):
        index = next(index for index, (candidate, _callback) in enumerate(self.scheduled) if candidate == delay)
        _delay, callback = self.scheduled.pop(index)
        callback()

    def finish_next(self):
        work, complete, _task_id = self.submissions.pop(0)
        complete(SimpleNamespace(success=True, result=work()))


class _Consumer:
    def __init__(self, manager, generation=9) -> None:
        self._thread_manager = manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []

    def is_system_stats_consumer_alive(self):
        return self.alive

    def on_system_stats_runtime_snapshot(self, snapshot):
        self.snapshots.append(snapshot)


@pytest.fixture(autouse=True)
def _reset():
    reset_shared_system_stats_runtime_for_tests()
    yield
    reset_shared_system_stats_runtime_for_tests()


def _lease(consumer, harness, sources):
    service = SystemStatsRuntimeService(
        source_factory=lambda: sources.append(_Source()) or sources[-1],
        schedule=harness.schedule,
        submit_factory=harness.submit_factory,
        ui_dispatch=harness.ui_dispatch,
    )
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


def test_dormant_until_first_lease_then_one_source_and_immediate_warm_sample():
    harness, sources = _Harness(), []
    consumer = _Consumer(object())
    service = _lease(consumer, harness, sources)
    owner = service.shared_owner
    assert sources == [] and harness.scheduled == [] and harness.submissions == []
    assert service.start() is True
    assert len(sources) == 1
    assert [delay for delay, _ in harness.scheduled] == [0]
    harness.fire_next_timer()
    assert len(harness.submissions) == 1
    harness.finish_next()
    assert consumer.snapshots[-1].sample.cpu_status == "warming"
    assert [delay for delay, _ in harness.scheduled] == [SAMPLE_INTERVAL_MS]
    assert owner.cardinality()["in_flight"] is False


def test_two_display_leases_share_one_owner_source_timer_and_snapshot():
    harness, sources = _Harness(), []
    first, second = _Consumer(object(), 12), _Consumer(None, 12)
    second._thread_manager = first._thread_manager
    a, b = _lease(first, harness, sources), _lease(second, harness, sources)
    assert a.shared_owner is b.shared_owner
    assert shared_system_stats_owner_count() == 1
    assert a.start() and b.start()
    assert len(sources) == 1 and len(harness.scheduled) == 1
    harness.fire_next_timer()
    harness.finish_next()
    assert len(first.snapshots) == len(second.snapshots) == 1
    assert first.snapshots[0] is second.snapshots[0]
    assert a.shared_owner.active_consumer_count() == 2


def test_one_in_flight_skips_extra_edge_without_queue_growth():
    harness, sources = _Harness(), []
    service = _lease(_Consumer(object()), harness, sources)
    service.start()
    harness.fire_next_timer()
    owner = service.shared_owner
    owner._sample_edge(owner._owner_generation, owner._token)
    assert len(harness.submissions) == 1
    assert owner.skipped_edges == 1


def test_last_lease_stops_source_and_rejects_stale_completion_then_restart_is_fresh():
    harness, sources = _Harness(), []
    consumer = _Consumer(object(), 20)
    service = _lease(consumer, harness, sources)
    service.start()
    harness.fire_next_timer()
    owner = service.shared_owner
    assert len(harness.submissions) == 1
    service.stop()
    assert sources[0].closed == 1
    assert owner.cardinality()["source_live"] is False
    harness.finish_next()
    assert consumer.snapshots == []
    service.start()
    assert len(sources) == 2
    harness.fire_next_timer()
    harness.finish_next()
    assert len(consumer.snapshots) == 1


def test_final_release_clears_snapshot_before_restart_but_keeps_revision_monotonic():
    harness, sources = _Harness(), []
    consumer = _Consumer(object(), 22)
    service = _lease(consumer, harness, sources)
    service.start()
    harness.fire_next_timer()
    harness.finish_next()
    first = consumer.snapshots[-1]
    service.stop()
    assert service.current_snapshot() is None
    service.start()
    assert consumer.snapshots == [first]
    harness.fire_timer(0)
    harness.finish_next()
    assert consumer.snapshots[-1].revision > first.revision
    assert consumer.snapshots[-1].sample.cpu_status == "warming"


def test_old_completion_cannot_clear_newly_restarted_in_flight_request():
    harness, sources = _Harness(), []
    consumer = _Consumer(object(), 21)
    service = _lease(consumer, harness, sources)
    service.start()
    harness.fire_next_timer()
    owner = service.shared_owner
    assert len(harness.submissions) == 1 and owner.cardinality()["in_flight"] is True
    service.stop()
    assert owner.cardinality()["in_flight"] is False
    service.start()
    harness.fire_next_timer()
    assert len(harness.submissions) == 2 and owner.cardinality()["in_flight"] is True
    old_work, old_complete, _old_id = harness.submissions.pop(0)
    assert _old_id != harness.submissions[0][2]
    old_complete(SimpleNamespace(success=True, result=old_work()))
    assert owner.cardinality()["in_flight"] is True
    harness.finish_next()
    assert owner.cardinality()["in_flight"] is False
    assert len(consumer.snapshots) == 1


def test_final_retire_drops_registry_and_no_queued_timer_can_restart_work():
    harness, sources = _Harness(), []
    consumer = _Consumer(object(), 33)
    service = _lease(consumer, harness, sources)
    service.start()
    assert shared_system_stats_owner_count() == 1
    service.retire()
    assert shared_system_stats_owner_count() == 0
    assert sources[0].closed == 1
    harness.fire_next_timer()
    assert harness.submissions == []


def test_old_generation_completion_cannot_publish_into_recreated_generation():
    harness, sources = _Harness(), []
    old_consumer = _Consumer(object(), 40)
    old_service = _lease(old_consumer, harness, sources)
    old_service.start()
    harness.fire_next_timer()
    assert len(harness.submissions) == 1
    old_service.retire()

    new_consumer = _Consumer(old_consumer._thread_manager, 41)
    new_service = _lease(new_consumer, harness, sources)
    new_service.start()
    # Deliver the old worker after a distinct runtime-generation owner exists.
    harness.finish_next()
    assert old_consumer.snapshots == []
    assert new_consumer.snapshots == []
    harness.fire_next_timer()
    harness.finish_next()
    assert len(new_consumer.snapshots) == 1


@pytest.mark.parametrize("dispatch", [lambda _callback: False, lambda _callback: (_ for _ in ()).throw(RuntimeError("ui unavailable"))])
def test_rejected_or_failed_ui_delivery_fails_closed_without_wedging_in_flight(dispatch):
    harness, sources = _Harness(), []
    consumer = _Consumer(object(), 50)
    service = SystemStatsRuntimeService(
        source_factory=lambda: sources.append(_Source()) or sources[-1],
        schedule=harness.schedule,
        submit_factory=harness.submit_factory,
        ui_dispatch=dispatch,
    )
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    service.start()
    owner = service.shared_owner
    harness.fire_next_timer()
    harness.finish_next()
    assert owner.cardinality()["in_flight"] is False
    assert owner.cardinality()["source_live"] is False
    assert owner.is_running() is False
    assert service.is_running() is False
    assert sources[0].closed == 1
    assert consumer.snapshots == []
    assert harness.scheduled == []
