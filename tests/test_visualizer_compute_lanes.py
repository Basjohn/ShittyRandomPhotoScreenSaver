from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


class _ImmediateLane:
    def __init__(self, worker, callback, *, lane_id: str, category: str) -> None:
        self.worker = worker
        self.callback = callback
        self.lane_id = lane_id
        self.category = category
        self.is_stopped = False
        self.submissions = 0

    def submit(self, payload) -> bool:
        if self.is_stopped:
            return False
        self.submissions += 1
        try:
            value = self.worker(payload)
            result = SimpleNamespace(success=True, result=value, error=None)
        except Exception as exc:  # pragma: no cover - mirrors lane result envelope
            result = SimpleNamespace(success=False, result=None, error=exc)
        self.callback(result, payload=payload)
        return True

    def cancel_pending(self) -> int:
        return 0

    def diagnostic_snapshot(self) -> dict[str, object]:
        return {"lane_id": self.lane_id, "category": self.category}

    def stop(self) -> None:
        self.is_stopped = True


class _ImmediateManager:
    supports_persistent_compute_lanes = True

    def __init__(self) -> None:
        self.create_lane_calls = 0
        self.general_submissions = 0
        self.lane: _ImmediateLane | None = None

    def create_compute_lane(self, worker, callback, *, lane_id, category):
        self.create_lane_calls += 1
        self.lane = _ImmediateLane(
            worker,
            callback,
            lane_id=str(lane_id),
            category=str(category),
        )
        return self.lane

    def submit_compute_task(self, *_args, **_kwargs):
        self.general_submissions += 1
        raise AssertionError(
            "visualizer audio analysis must not fall back to per-frame Future/task submission"
        )


def _install_fake_analysis(monkeypatch, engine: _SpotifyBeatEngine):
    worker_state = object()
    snapshot_calls: list[object] = []
    committed_states: list[object] = []

    def make_snapshot():
        snapshot_calls.append(worker_state)
        return worker_state

    monkeypatch.setattr(engine._audio_worker, "make_compute_snapshot", make_snapshot)
    monkeypatch.setattr(
        engine._audio_worker,
        "commit_compute_snapshot",
        lambda state: committed_states.append(state),
    )

    from widgets.spotify_visualizer import bar_computation

    monkeypatch.setattr(
        bar_computation,
        "compute_bars_from_samples",
        lambda state, _samples: [0.1, 0.2, 0.3, 0.4]
        if state is worker_state
        else None,
    )
    return worker_state, snapshot_calls, committed_states


def test_audio_analysis_uses_persistent_lane_not_general_executor(monkeypatch):
    manager = _ImmediateManager()
    engine = _SpotifyBeatEngine(bar_count=4)
    worker_state, _snapshot_calls, committed_states = _install_fake_analysis(
        monkeypatch, engine
    )

    engine.set_thread_manager(manager)
    engine._schedule_compute_bars_task(object())

    assert manager.create_lane_calls == 1
    assert manager.lane is not None
    assert manager.lane.category == "visualizer.audio_analysis"
    assert manager.lane.lane_id.startswith("spotify_visualizer.audio_analysis:")
    assert manager.lane.submissions == 1
    assert manager.general_submissions == 0
    assert engine._compute_task_active is False
    assert engine._latest_bars == [0.1, 0.2, 0.3, 0.4]
    assert committed_states == [worker_state]


def test_audio_analysis_reuses_detached_dsp_state_until_config_invalidates_it(monkeypatch):
    manager = _ImmediateManager()
    engine = _SpotifyBeatEngine(bar_count=4)
    _worker_state, snapshot_calls, _committed_states = _install_fake_analysis(
        monkeypatch, engine
    )

    engine.set_thread_manager(manager)
    engine._schedule_compute_bars_task(object())
    engine._schedule_compute_bars_task(object())

    assert len(snapshot_calls) == 1
    assert engine._analysis_compute_state_rebuilds == 1
    assert engine._analysis_compute_state_reuses == 1

    monkeypatch.setattr(engine._audio_worker, "set_input_gain", lambda _gain: None)
    engine.set_input_gain(1.25)
    engine._schedule_compute_bars_task(object())

    assert len(snapshot_calls) == 2
    assert engine._analysis_compute_state_rebuilds == 2
    assert engine._analysis_compute_state_reuses == 1
    assert manager.general_submissions == 0


def test_audio_analysis_previous_bars_are_stable_for_the_serial_packet(monkeypatch):
    manager = _ImmediateManager()
    engine = _SpotifyBeatEngine(bar_count=4)
    captured_previous: list[tuple[float, ...]] = []

    class _CapturingLane(_ImmediateLane):
        def submit(self, payload) -> bool:
            captured_previous.append(tuple(payload.previous_bars))
            # Mutate the live list after admission. The request must retain the
            # previously admitted vector rather than a moving shared list.
            engine._smoothed_bars[:] = [0.9, 0.9, 0.9, 0.9]
            return super().submit(payload)

    def create_lane(worker, callback, *, lane_id, category):
        manager.create_lane_calls += 1
        manager.lane = _CapturingLane(
            worker, callback, lane_id=str(lane_id), category=str(category)
        )
        return manager.lane

    manager.create_compute_lane = create_lane
    _install_fake_analysis(monkeypatch, engine)
    engine._smoothed_bars = [0.11, 0.22, 0.33, 0.44]

    engine.set_thread_manager(manager)
    engine._schedule_compute_bars_task(object())

    assert captured_previous == [(0.11, 0.22, 0.33, 0.44)]
    assert manager.general_submissions == 0


def test_required_audio_lane_creation_failure_is_loud_and_has_no_future_fallback():
    class _BrokenManager:
        supports_persistent_compute_lanes = True

        def __init__(self) -> None:
            self.general_submissions = 0

        def create_compute_lane(self, *_args, **_kwargs):
            raise RuntimeError("lane unavailable")

        def submit_compute_task(self, *_args, **_kwargs):
            self.general_submissions += 1
            raise AssertionError("forbidden fallback")

    manager = _BrokenManager()
    engine = _SpotifyBeatEngine(bar_count=4)

    with pytest.raises(RuntimeError, match="lane unavailable"):
        engine.set_thread_manager(manager)

    assert manager.general_submissions == 0
    assert engine._analysis_lane is None
