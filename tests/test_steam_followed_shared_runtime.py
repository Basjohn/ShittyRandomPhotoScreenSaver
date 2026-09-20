"""Games You Follow generation-shared event/source tests, no live credentials."""
from __future__ import annotations

import sys
import time
import types
import unittest
from dataclasses import replace
from unittest.mock import patch

from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsStory
from widgets.steam_followed_runtime import (
    FollowedRuntimeConfig, FollowedRuntimeLease, shared_followed_owner_count,
    reset_shared_followed_runtime_for_tests,
)


class _Result:
    def __init__(self, value):
        self.success, self.result = True, value


class _Manager:
    def __init__(self):
        self.jobs = []
        self.submissions = 0

    def submit_io_task(self, worker, *, callback, category, priority):
        assert category == "steam_games_followed"
        self.submissions += 1
        self.jobs.append((worker, callback))
        return str(self.submissions)

    def complete(self):
        worker, completed = self.jobs.pop(0)
        completed(_Result(worker()))


class _Consumer:
    def __init__(self):
        self.snapshots = []

    def on_games_followed_runtime_snapshot(self, snapshot):
        self.snapshots.append(snapshot)


class _Source:
    def __init__(self):
        self.retired = 0

    def retire(self):
        self.retired += 1


def _snapshot(index=0):
    return FollowedNewsSnapshot(
        "available", (FollowedNewsStory(10, str(100 + index), f"A{index}",
                                       1700000000, "News", False),), followed_count=1,
    )


class FollowedLeaseTests(unittest.TestCase):
    def setUp(self):
        reset_shared_followed_runtime_for_tests()
        self.context = patch.dict(sys.modules, {
            "core.threading.manager": types.SimpleNamespace(
                TaskPriority=types.SimpleNamespace(LOW="low"),
                ThreadManager=types.SimpleNamespace(
                    run_on_ui_thread=lambda cb: cb(),
                    single_shot=lambda ms, cb: None,
                ),
            ),
        })
        self.context.start()
        self.manager = _Manager()
        self.queue = []
        self.deadlines = []
        self.source = _Source()
        self.loads = 0
        self.refreshes = 0
        self.config = FollowedRuntimeConfig(6)

    def tearDown(self):
        reset_shared_followed_runtime_for_tests()
        self.context.stop()

    def _lease(self, consumer):
        lease = FollowedRuntimeLease(
            generation=27, manager=self.manager, config=self.config,
            load=self._load, refresh=self._refresh,
            ui_dispatch=lambda cb: self.queue.append(cb) or True,
            schedule=lambda ms, cb: self.deadlines.append((ms, cb)),
        )
        lease.attach_consumer(consumer)
        return lease

    def _load(self):
        self.loads += 1
        return self.source, _snapshot()

    def _refresh(self, source):
        self.assertIs(source, self.source)
        self.refreshes += 1
        return source, _snapshot(self.refreshes)

    def _complete(self):
        self.manager.complete()
        self.queue.pop(0)()

    def test_two_displays_share_one_source_and_only_one_refresh_deadline(self):
        a, b = _Consumer(), _Consumer()
        first, second = self._lease(a), self._lease(b)
        self.assertTrue(first.start())
        self.assertTrue(second.start())
        self.assertEqual(shared_followed_owner_count(), 1)
        self.assertEqual(self.manager.submissions, 1)
        self._complete()   # cache-first startup, then one source refresh
        self.assertEqual(a.snapshots, [_snapshot()])
        self.assertEqual(b.snapshots, [_snapshot()])
        self.assertEqual(self.manager.submissions, 2)
        self._complete()
        self.assertEqual((self.loads, self.refreshes), (1, 1))
        self.assertEqual(len(self.deadlines), 1)
        self.assertEqual(self.deadlines[0][0], 6 * 60_000)
        # Identity of both leases and source remains unchanged through repeats.
        self.assertTrue(first.request_refresh())
        self.assertFalse(second.request_refresh())
        self.assertEqual(self.manager.submissions, 3)
        self._complete()
        self.assertEqual(self.refreshes, 2)
        self.assertEqual(len(self.deadlines), 2)
        first.retire()
        self.assertEqual(shared_followed_owner_count(), 1)
        self.assertFalse(self.source.retired)
        second.retire()
        self.assertEqual(shared_followed_owner_count(), 0)
        self.assertEqual(self.source.retired, 1)
        # A queued old deadline is inert after both displays retire.
        count = self.manager.submissions
        for _, callback in self.deadlines:
            callback()
        self.assertEqual(self.manager.submissions, count)

    def test_same_generation_different_display_managers_still_share_source(self):
        first_consumer, second_consumer = _Consumer(), _Consumer()
        first = self._lease(first_consumer)
        second = self._lease(second_consumer)
        other_manager = _Manager()
        second.set_thread_manager(other_manager, generation=27)
        self.assertTrue(first.start())
        self.assertTrue(second.start())
        self._complete()
        self._complete()
        self.assertEqual(shared_followed_owner_count(), 1)
        self.assertEqual(other_manager.submissions, 0)
        self.assertEqual(second_consumer.snapshots, [_snapshot(), _snapshot(1)])
        first.retire()
        second.retire()
        self.assertEqual(self.source.retired, 1)

    def test_recent_complete_disk_cache_does_not_immediately_rescan_followed_games(self):
        target = _Consumer()
        lease = self._lease(target)
        age_seconds = 20
        last_good = replace(_snapshot(), from_cache=True, checked_count=1,
                            covered_count=1, fetched_at=time.time() - age_seconds)
        lease._load = lambda: (self.source, last_good)
        self.assertTrue(lease.start())
        self._complete()
        self.assertEqual(target.snapshots, [last_good])
        self.assertEqual(self.manager.submissions, 1)  # Cache read only.
        self.assertEqual(self.refreshes, 0)
        self.assertEqual(len(self.deadlines), 1)
        self.assertGreater(self.deadlines[0][0], 5 * 60_000)
        self.assertLess(self.deadlines[0][0], 6 * 60_000)
        # The manual refresh uses the SAME shared owner and supersedes its
        # pending warm-cache deadline, never a second source or worker.
        self.assertTrue(lease.request_refresh())
        self.assertEqual(self.manager.submissions, 2)
        self._complete()
        self.assertEqual(self.refreshes, 1)
        lease.retire()

    def test_complete_cache_maintenance_uses_one_short_second_slice_then_regular_interval(self):
        consumer = _Consumer()
        lease = self._lease(consumer)
        source = self.source
        calls = [0]

        def next_batch(actual):
            self.assertIs(actual, source)
            calls[0] += 1
            return source, FollowedNewsSnapshot(
                "available", followed_count=142, checked_count=4,
                covered_count=142, window_offset=(calls[0] - 1) * 4,
                maintenance_pending=calls[0] % 2 == 1,
            )

        lease._refresh = next_batch
        recent = FollowedNewsSnapshot(
            "available", followed_count=142, checked_count=2,
            covered_count=142, window_offset=140, from_cache=True,
            fetched_at=time.time() - 10,
        )
        lease._load = lambda: (source, recent)
        self.assertTrue(lease.start())
        self._complete()
        self.assertEqual(self.manager.submissions, 1)
        self.assertGreater(self.deadlines[-1][0], 5 * 60_000)
        self.deadlines.pop()[1]()
        self._complete()
        self.assertEqual(calls[0], 1)
        self.assertEqual(self.deadlines[-1][0], 15_000)
        self.deadlines.pop()[1]()
        self._complete()
        self.assertEqual(calls[0], 2)
        self.assertEqual(self.deadlines[-1][0], 6 * 60_000)
        lease.retire()

    def test_pending_maintenance_restored_from_disk_uses_same_short_deadline(self):
        target = _Consumer()
        lease = self._lease(target)
        recent = FollowedNewsSnapshot(
            "available", followed_count=142, checked_count=4,
            covered_count=142, window_offset=0, from_cache=True,
            fetched_at=time.time() - 10, maintenance_pending=True,
        )
        lease._load = lambda: (self.source, recent)
        self.assertTrue(lease.start())
        self._complete()
        self.assertEqual(self.manager.submissions, 1)
        self.assertEqual(self.deadlines[-1][0], 15_000)
        lease.retire()

    def test_late_worker_completion_cannot_resurrect_source_or_presenter(self):
        target = _Consumer()
        lease = self._lease(target)
        lease.start()
        self.manager.complete()  # callback queued; retire before Qt delivery
        lease.retire()
        self.queue.pop(0)()
        self.assertEqual(target.snapshots, [])
        self.assertEqual(self.refreshes, 0)
        self.assertEqual(shared_followed_owner_count(), 0)
        self.assertEqual(self.manager.submissions, 1)

    def test_rejoined_lease_receives_last_snapshot_without_second_worker(self):
        target, later = _Consumer(), _Consumer()
        first = self._lease(target)
        first.start()
        self._complete()
        self._complete()
        before = self.manager.submissions
        second = self._lease(later)
        second.start()
        self.assertEqual(later.snapshots, [_snapshot(1)])
        self.assertEqual(self.manager.submissions, before)
        first.retire()
        second.retire()

    def test_attached_but_dormant_lease_never_constructs_source_or_timer(self):
        target = _Consumer()
        lease = self._lease(target)
        self.assertEqual(shared_followed_owner_count(), 0)
        self.assertEqual((self.loads, self.refreshes, self.manager.submissions), (0, 0, 0))
        self.assertEqual(self.deadlines, [])
        self.assertFalse(lease.request_refresh())
        lease.retire()
        self.assertEqual(shared_followed_owner_count(), 0)

    def test_last_lease_retires_inflight_source_and_rejects_late_commit(self):
        target = _Consumer()
        lease = self._lease(target)
        lease.start()
        self._complete()  # source from cache-stage is already retained
        self.assertEqual(self.manager.submissions, 2)
        lease.retire()  # Must retire source before worker finishes its network request.
        self.assertEqual(self.source.retired, 1)
        self.manager.complete()  # Fake result arrives after retirement.
        self.queue.pop(0)()
        self.assertEqual(target.snapshots, [_snapshot()])
        self.assertEqual(shared_followed_owner_count(), 0)
        self.assertFalse(self.deadlines)

    def test_final_lease_cancels_retained_deadline_not_only_generation_fences_it(self):
        target = _Consumer()
        cancellations = []
        lease = FollowedRuntimeLease(
            generation=27, manager=self.manager, config=self.config,
            load=self._load, refresh=self._refresh,
            ui_dispatch=lambda cb: self.queue.append(cb) or True,
            schedule=lambda ms, cb: self.deadlines.append((ms, cb)) or
                (lambda: cancellations.append(ms)),
        )
        lease.attach_consumer(target)
        lease.start()
        self._complete()
        self._complete()
        self.assertEqual(cancellations, [])
        lease.retire()
        self.assertEqual(cancellations, [6 * 60_000])
        self.assertEqual(self.source.retired, 1)

    def test_rejected_gui_dispatch_leaves_gui_owned_timer_for_ui_retirement(self):
        target = _Consumer()
        lease = self._lease(target)
        lease._ui_dispatch = lambda _callback: False
        lease.start()
        # The worker callback must not manipulate GUI-owned QTimer/source
        # lifetime on the worker thread when Qt refuses a shutdown-time wake.
        self.manager.complete()
        self.assertEqual(target.snapshots, [])
        self.assertEqual(self.source.retired, 0)
        self.assertFalse(lease.request_refresh())  # One sealed work slot.
        lease.retire()  # The owning GUI teardown retires the source.
        self.assertEqual(shared_followed_owner_count(), 0)
        self.assertEqual(self.source.retired, 0)  # Startup load was never admitted.
        self.assertFalse(lease.start())

    def test_neutral_service_registry_builds_only_a_dormant_followed_lease(self):
        from rendering.widget_runtime_services import (
            get_runtime_service_spec, get_runtime_service_ids_for_presentation,
        )
        spec = get_runtime_service_spec("steam_progress")
        self.assertIsNotNone(spec)
        self.assertEqual(get_runtime_service_ids_for_presentation("steam_progress"),
                         ("steam_progress",))
        lease = spec.build("steam_progress", {"steam": {"refresh_minutes": 9}})
        self.assertEqual(lease._config.refresh_minutes, 9)
        self.assertIsNone(lease._owner)
        self.assertFalse(lease._running)
        self.assertEqual(shared_followed_owner_count(), 0)
        spec.retire(lease)
        self.assertTrue(lease.is_retired())

    def test_stale_deadline_cannot_schedule_after_explicit_refresh(self):
        target = _Consumer()
        lease = self._lease(target)
        lease.start()
        self._complete()
        self._complete()
        stale = self.deadlines[-1][1]
        lease.request_refresh()
        before = self.manager.submissions
        stale()
        self.assertEqual(self.manager.submissions, before)
        self._complete()
        lease.retire()


if __name__ == "__main__":
    unittest.main()


def test_progressive_followed_sweep_reuses_one_shared_deadline_and_retires_it():
    """Four-app batches advance only while a real shared lease is active."""
    reset_shared_followed_runtime_for_tests()
    context = patch.dict(sys.modules, {
        "core.threading.manager": types.SimpleNamespace(
            TaskPriority=types.SimpleNamespace(LOW="low"),
            ThreadManager=types.SimpleNamespace(run_on_ui_thread=lambda cb: cb()),
        ),
    })
    context.start()
    manager = _Manager()
    deadlines, cancelled = [], []
    source = _Source()
    counter = [0]
    def snapshot(covered):
        return FollowedNewsSnapshot(
            "available", (FollowedNewsStory(41, "123", "Patch", 1700000000,
                                             "News", True),),
            followed_count=142, checked_count=4, covered_count=covered,
        )
    def schedule(ms, callback):
        deadlines.append((ms, callback))
        return lambda: cancelled.append(ms)
    def refresh(actual):
        assert actual is source
        counter[0] += 1
        return source, snapshot(8 if counter[0] == 1 else 142)
    consumer = _Consumer()
    queue = []
    lease = FollowedRuntimeLease(
        generation=103, manager=manager, config=FollowedRuntimeConfig(6),
        load=lambda: (source, snapshot(4)), refresh=refresh,
        ui_dispatch=lambda cb: queue.append(cb) or True,
        schedule=schedule,
    )
    lease.attach_consumer(consumer)
    try:
        assert lease.start()
        manager.complete(); queue.pop(0)()  # cached revision, immediate first batch
        assert manager.submissions == 2 and deadlines == []
        manager.complete(); queue.pop(0)()
        assert len(deadlines) == 1 and deadlines[0][0] == 15000
        assert counter[0] == 1
        deadlines.pop(0)[1]()  # same owner's single-shot deadline
        assert manager.submissions == 3
        manager.complete(); queue.pop(0)()
        assert len(deadlines) == 1 and deadlines[0][0] == 360000
        assert counter[0] == 2
        stale_callback = deadlines[0][1]
    finally:
        lease.retire()
        reset_shared_followed_runtime_for_tests()
        context.stop()
    stale_callback()
    assert counter[0] == 2 and cancelled == [360000]
    assert source.retired == 1
