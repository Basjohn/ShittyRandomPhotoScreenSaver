from __future__ import annotations

from types import SimpleNamespace

from widgets.spotify_visualizer.bubble_compute_lane import BubbleComputeLane


class _ImmediateManager:
    supports_persistent_compute_lanes = True

    def __init__(self) -> None:
        self.submissions: list[tuple[str, str | None]] = []
        self.create_lane_calls = 0

    def create_compute_lane(self, *_args, **_kwargs):
        self.create_lane_calls += 1
        raise AssertionError("Bubble recovery path must not create a persistent lane")

    def submit_compute_task(
        self,
        worker,
        *args,
        callback=None,
        task_id=None,
        category="uncategorized",
        **kwargs,
    ):
        self.submissions.append((str(category), task_id))
        try:
            value = worker(*args, **kwargs)
            result = SimpleNamespace(success=True, result=value, error=None)
        except Exception as exc:
            result = SimpleNamespace(success=False, result=None, error=exc)
        if callback is not None:
            callback(result)
        return task_id or "immediate-task"

    def cancel_task(self, _task_id: str) -> bool:
        return False


class _Owner:
    def __init__(self) -> None:
        self.worker_tokens: list[object] = []
        self.results: list[tuple[int, tuple[int, int], float, float]] = []

    def worker(self, _dt, energy, _settings, _pulse, **kwargs):
        self.worker_tokens.append(kwargs.get("task_token"))
        return int(energy["edge"])

    def on_result(self, result, *, task_token, source_ts, authored_ts):
        assert result.success
        self.results.append(
            (int(result.result), task_token, float(source_ts), float(authored_ts))
        )


def test_bubble_facade_uses_general_executor_and_preserves_publication_metadata():
    owner = _Owner()
    manager = _ImmediateManager()
    adapter = BubbleComputeLane(
        worker=owner.worker,
        result_callback=owner.on_result,
        runtime_generation=5,
        task_id="bubble-test",
    )

    adapter.start(manager)
    assert adapter.submit(
        task_token=(7, 1),
        dt=0.01,
        energy={"edge": 23},
        settings={},
        pulse={},
        source_ts=1.25,
        authored_ts=1.50,
    )

    assert manager.create_lane_calls == 0
    assert manager.submissions == [("visualizer.bubble_simulation", "bubble-test")]
    assert owner.worker_tokens == [None]
    assert owner.results == [(23, (7, 1), 1.25, 1.50)]

    metrics = adapter.diagnostic_snapshot()
    assert metrics["adapter"] == "general_compute"
    assert metrics["lane_registrations"] == 0
    assert metrics["executor_task_submissions"] == 1
    assert metrics["logical_steps_accepted"] == 1
    assert metrics["logical_steps_completed"] == 1
    assert metrics["logical_steps_published"] == 1


def test_bubble_facade_rejects_new_work_after_stop():
    owner = _Owner()
    manager = _ImmediateManager()
    adapter = BubbleComputeLane(
        worker=owner.worker,
        result_callback=owner.on_result,
        runtime_generation=9,
        task_id="bubble-stop",
    )
    adapter.start(manager)
    adapter.stop()

    assert not adapter.submit(
        task_token=(9, 1),
        dt=0.01,
        energy={"edge": 1},
        settings={},
        pulse={},
        source_ts=0.0,
        authored_ts=0.0,
    )
    assert adapter.diagnostic_snapshot()["submit_rejected_stopped"] == 1
