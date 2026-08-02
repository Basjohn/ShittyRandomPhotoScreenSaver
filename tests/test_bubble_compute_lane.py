from __future__ import annotations

import threading
import time

from core.threading.manager import ThreadManager, ThreadPoolType
from widgets.spotify_visualizer.bubble_compute_lane import BubbleComputeLane


class _Owner:
    def __init__(self) -> None:
        self.results: list[int] = []
        self.result_event = threading.Event()

    def worker(self, _dt, energy, _settings, _pulse):
        return int(energy["edge"])

    def on_result(self, result, *, task_token, source_ts, authored_ts):
        assert result.success
        assert source_ts == authored_ts
        assert task_token[0] == 7
        self.results.append(int(result.result))
        self.result_event.set()


def test_managed_lane_runs_many_authored_edges_without_executor_tasks():
    owner = _Owner()
    manager = ThreadManager(
        config={ThreadPoolType.IO: 1, ThreadPoolType.COMPUTE: 1}
    )
    lane = BubbleComputeLane(
        worker=owner.worker,
        result_callback=owner.on_result,
        runtime_generation=5,
        task_id="bubble-test",
    )
    try:
        lane.start(manager)

        for index in range(100):
            owner.result_event.clear()
            deadline = time.monotonic() + 1.0
            while not lane.submit(
                task_token=(7, index + 1),
                dt=0.01,
                energy={"edge": index},
                settings={},
                pulse={},
                source_ts=float(index + 1),
                authored_ts=float(index + 1),
            ):
                assert time.monotonic() < deadline
                time.sleep(0.001)
            assert owner.result_event.wait(1.0)

        assert owner.results == list(range(100))
        metrics = lane.diagnostic_snapshot()
        assert metrics["lane_registrations"] == 1
        assert metrics["executor_task_submissions"] == 0
        assert metrics["logical_steps_accepted"] == 100
        assert metrics["logical_steps_completed"] == 100
        assert metrics["submit_rejected_busy"] == 0

        # The managed lane must not reserve the only general COMPUTE worker.
        compute_finished = threading.Event()
        manager.submit_compute_task(
            lambda: compute_finished.set(),
            category="test.general_compute",
        )
        assert compute_finished.wait(1.0)
    finally:
        lane.stop()
        manager.shutdown(wait=True, timeout=1.0)


def test_runtime_lane_handle_disappears_from_generation_snapshot_after_stop():
    owner = _Owner()
    manager = ThreadManager(
        config={ThreadPoolType.IO: 1, ThreadPoolType.COMPUTE: 1}
    )
    lane = BubbleComputeLane(
        worker=owner.worker,
        result_callback=owner.on_result,
        runtime_generation=91,
        task_id="bubble-lifecycle",
    )
    try:
        lane.start(manager)
        snapshot = manager.get_lifecycle_ownership_snapshot()
        assert any(
            item.get("runtime_generation") == 91
            and item.get("kind") == "compute_lane"
            for item in snapshot["active_tasks"]
        )

        lane.stop()
        deadline = time.monotonic() + 1.0
        while any(
            item.get("runtime_generation") == 91
            for item in manager.get_lifecycle_ownership_snapshot()["active_tasks"]
        ):
            assert time.monotonic() < deadline
            time.sleep(0.001)
    finally:
        manager.shutdown(wait=True, timeout=1.0)
