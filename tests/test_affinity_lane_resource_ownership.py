"""Affinity work can finish while its owner still holds a native resource."""

from __future__ import annotations

import threading

from core.threading.affinity_lanes import AffinityLaneScheduler


def _lane(scheduler):
    return scheduler.register_lane(
        lane_id="test.native_resource", category="test.native_resource",
        runtime_generation=None, owner_class="TestNativeOwner", owner_id=1,
    )


def test_idle_native_resource_debt_survives_stop_and_joined_shutdown():
    scheduler = AffinityLaneScheduler()
    lane = _lane(scheduler)
    lane.call(lambda: lane.set_resource_held(True), timeout=1.0)
    assert lane.stop(wait=True, timeout=1.0) is False
    assert scheduler.shutdown(wait=True, timeout=1.0) is False
    snapshot = scheduler.diagnostic_snapshot()
    assert snapshot["worker_threads"] == 0
    assert snapshot["registered_lanes"] == 1
    assert snapshot["queue_depth"] == 0
    assert scheduler.lifecycle_work_snapshot() == ({
        "task_id": "test.native_resource", "kind": "affinity_lane",
        "category": "test.native_resource", "pool": "affinity_lane",
        "owner_class": "TestNativeOwner", "owner_id": 1,
        "runtime_generation": None, "active": False, "pending": False,
        "resource_held": True,
    },)
    assert scheduler.shutdown(wait=True, timeout=1.0) is False


def test_stop_drains_already_queued_native_release_and_clears_resource_observation():
    scheduler = AffinityLaneScheduler()
    lane = _lane(scheduler)
    entered = threading.Event()
    release = threading.Event()

    def native_transaction():
        lane.set_resource_held(True)
        entered.set()
        assert release.wait(2.0)
        # Native release succeeded on its owning thread.
        lane.set_resource_held(False)

    try:
        assert lane.submit(native_transaction) is True
        assert entered.wait(1.0)
        assert lane.stop(wait=False) is False
        snapshot = lane.diagnostic_snapshot()
        assert snapshot["active"] == 1
        assert snapshot["resource_held"] is True
        release.set()
        assert lane.stop(wait=True, timeout=1.0) is True
        assert scheduler.lifecycle_work_snapshot() == ()
        assert scheduler.shutdown(wait=True, timeout=1.0) is True
    finally:
        release.set()
        scheduler.shutdown(wait=True, timeout=2.0)
