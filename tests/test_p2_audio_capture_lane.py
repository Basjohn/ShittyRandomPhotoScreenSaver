"""P2 capture-owner regression bars.

The native backend may enumerate devices and open a WASAPI stream.  That work
must stay on the one ThreadManager affinity owner even when a start is blocked,
stopped, or woken repeatedly.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from core.threading.manager import ThreadManager
from utils.audio_capture import AudioCaptureBackend
from utils.lockfree import TripleBuffer
from widgets.spotify_visualizer.audio_worker import SpotifyVisualizerAudioWorker
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


class _BlockingBackend(AudioCaptureBackend):
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self.entered = entered
        self.release = release
        self.start_thread = None
        self.stop_calls = 0
        self._callback = None
        self._negotiated_block_size = 1024

    def start(self, callback):
        self.start_thread = threading.get_ident()
        self._callback = callback
        self.entered.set()
        assert self.release.wait(2.0), "test backend was never released"
        self._note_capture_starting()
        callback([0.25] * 32)
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self._callback = None
        self._note_capture_stopped()

    def is_running(self) -> bool:
        return self._callback is not None

    @property
    def sample_rate(self) -> int:
        return 48000

    @property
    def channels(self) -> int:
        return 2

    def restart(self) -> bool:
        callback = self._callback
        self.stop()
        return self.start(callback) if callback is not None else False


class _QueuedLane:
    """Deterministic explicit owner seam; it never runs work on submit()."""

    is_stopped = False

    def __init__(self) -> None:
        self.jobs = []
        self.resource_held = False

    def set_resource_held(self, held):
        self.resource_held = bool(held)

    def submit(self, func) -> bool:
        self.jobs.append(func)
        return True

    def run_next(self) -> None:
        self.jobs.pop(0)()


class _ImmediateBackend(AudioCaptureBackend):
    def __init__(self) -> None:
        self._callback = None
        self._config = type("Config", (), {"block_size": 1024})()
        self._negotiated_block_size = 1024
        self.restart_calls = 0
        self.stop_calls = 0

    def start(self, callback) -> bool:
        self._callback = callback
        self._note_capture_starting()
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self._callback = None
        self._note_capture_stopped()

    def is_running(self) -> bool:
        return self._callback is not None

    @property
    def sample_rate(self) -> int:
        return 48000

    @property
    def channels(self) -> int:
        return 2

    def restart(self) -> bool:
        self.restart_calls += 1
        return True


def test_blocked_native_start_never_blocks_gui_or_revives_after_stop(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    created: list[_BlockingBackend] = []

    def make_backend(_config):
        backend = _BlockingBackend(entered, release)
        created.append(backend)
        return backend

    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture", make_backend
    )
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.visualizer.audio_capture",
        category="visualizer.audio_capture",
        worker="audio_capture_test",
    )
    buffer = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(4, buffer)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)

    try:
        gui_thread = threading.get_ident()
        before = time.perf_counter()
        worker.start()
        assert (time.perf_counter() - before) < 0.1
        assert entered.wait(1.0)
        assert worker.is_capture_starting() is True
        assert created[0].start_thread != gui_thread

        worker.stop()
        release.set()
        assert lane.stop(wait=True, timeout=2.0) is True

        assert created[0].stop_calls == 1
        assert worker.is_running() is False
        assert worker.is_capture_starting() is False
        assert worker.is_capture_stale() is False
        assert buffer.consume_latest() is None, "retired start callback published a frame"
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=2.0)


def test_start_and_wake_restart_admission_stay_bounded(monkeypatch):
    lane = _QueuedLane()
    backend = _ImmediateBackend()
    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture",
        lambda _config: backend,
    )
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)

    worker.start()
    worker.start()
    assert len(lane.jobs) == 1
    assert worker.is_capture_starting() is True

    lane.run_next()
    assert worker.is_running() is True
    assert worker.restart_capture() is True
    assert worker.restart_capture() is True
    assert len(lane.jobs) == 1, "repeated wake must not queue restart work"

    lane.run_next()
    assert backend.restart_calls == 1


def test_beat_engine_uses_one_dedicated_capture_lane(monkeypatch):
    backend = _ImmediateBackend()
    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.create_audio_capture",
        lambda _config: backend,
    )
    manager = ThreadManager()
    engine = _SpotifyBeatEngine(4)
    engine._audio_worker.set_audio_block_size(1024)
    engine.set_thread_manager(manager)

    try:
        engine.ensure_started()
        deadline = time.monotonic() + 1.0
        while not engine._audio_worker.is_running() and time.monotonic() < deadline:
            time.sleep(0.005)

        lane = engine._capture_lane
        assert lane is not None
        assert lane.diagnostic_snapshot()["category"] == "visualizer.audio_capture"
        dedicated = manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"]
        assert set(dedicated) == {"audio_capture"}
        assert dedicated["audio_capture"]["registered_lanes"] == 1
    finally:
        engine.force_stop()
        manager.shutdown(wait=True, timeout=2.0)


@pytest.mark.parametrize("finish_running", [False, True])
def test_blocked_open_coalesces_100_lifecycle_epochs_and_closes_before_replacement(
    monkeypatch, finish_running
):
    entered = threading.Event()
    release = threading.Event()
    latest_opened = threading.Event()
    created = []
    live = set()
    native_threads = set()
    peak_live = []

    class Backend(_ImmediateBackend):
        def __init__(self, config):
            super().__init__()
            self._config = config

        def start(self, callback):
            native_threads.add(threading.get_ident())
            live.add(id(self))
            peak_live.append(len(live))
            if len(created) == 1:
                entered.set()
                assert release.wait(2.0)
            result = super().start(callback)
            callback([0.25] * 32)
            if len(created) > 1:
                latest_opened.set()
            return result

        def stop(self):
            native_threads.add(threading.get_ident())
            live.remove(id(self))
            super().stop()

    def create(config):
        backend = Backend(config)
        created.append(backend)
        return backend

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", create)
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.audio.capture.epochs", category="visualizer.audio_capture",
        worker="audio_capture_test",
    )
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    try:
        worker.start()
        assert entered.wait(1.0)
        for epoch in range(100):
            worker.stop()
            worker.set_audio_block_size(128 if epoch % 2 else 512)
            worker.start()
            assert worker.restart_capture() is True
        if not finish_running:
            worker.stop()
        snapshot = lane.diagnostic_snapshot()
        assert snapshot["submitted"] == 1
        assert snapshot["pending"] == 0
        assert snapshot["active"] == 1
        assert len(created) == 1
        release.set()
        if finish_running:
            assert latest_opened.wait(1.0)
            lane.call(lambda: None, timeout=1.0)
            assert worker.is_running() is True
            assert worker.is_capture_healthy() is True
            assert created[-1]._config.block_size == 128
            assert created[-1].restart_calls == 0
        worker.stop()
        assert lane.stop(wait=True, timeout=2.0) is True
        assert len(created) == (2 if finish_running else 1)
        assert peak_live == [1] * len(created)
        assert len(native_threads) == 1
        assert all(backend.stop_calls == 1 for backend in created)
        assert not live
        assert worker.has_capture_owner_work() is False
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=2.0)


def test_stop_and_replacement_start_share_one_ordered_drain(monkeypatch):
    lane = _QueuedLane()
    events = []
    created = []

    class Backend(_ImmediateBackend):
        def start(self, callback):
            events.append(("start", id(self)))
            return super().start(callback)

        def stop(self):
            events.append(("stop", id(self)))
            super().stop()

    def create(_config):
        backend = Backend()
        created.append(backend)
        return backend

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", create)
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.run_next()
    worker.stop()
    worker.start()
    assert len(lane.jobs) == 1
    lane.run_next()
    assert events == [
        ("start", id(created[0])), ("stop", id(created[0])), ("start", id(created[1]))
    ]
    worker.stop()
    lane.run_next()
    assert all(backend.stop_calls == 1 for backend in created)


@pytest.mark.parametrize("operation", ["start", "restart"])
@pytest.mark.parametrize("raises", [False, True])
def test_failed_native_operation_is_loud_and_released_once(monkeypatch, caplog, operation, raises):
    lane = _QueuedLane()

    class Backend(_ImmediateBackend):
        def fail(self):
            if raises:
                raise RuntimeError("partial native resource failure")
            return False

        def start(self, callback):
            if operation == "start":
                self._callback = callback
                return self.fail()
            return super().start(callback)

        def restart(self):
            return self.fail()

    backend = Backend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.run_next()
    if operation == "restart":
        assert worker.restart_capture() is True
        lane.run_next()
    assert worker.is_running() is False
    assert worker.has_capture_owner_work() is False
    assert backend.stop_calls == 1
    assert any(record.levelname == "ERROR" and "capture" in record.message for record in caplog.records)
    worker.stop()
    assert not lane.jobs


def test_restart_returns_admitted_even_when_lane_finishes_immediately(monkeypatch):
    class ImmediateLane(_QueuedLane):
        def submit(self, func):
            func()
            return True

    backend = _ImmediateBackend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(ImmediateLane())
    worker.set_audio_block_size(1024)
    worker.start()
    assert worker.restart_capture() is True
    assert backend.restart_calls == 1
    assert worker._capture_restart_pending is False
    worker.stop()


def test_first_callback_inside_open_survives_adoption_and_grace_starts_at_open(monkeypatch):
    now = [10.0]
    monkeypatch.setattr(
        "widgets.spotify_visualizer.audio_worker.time",
        SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0]),
    )
    lane = _QueuedLane()

    class Backend(_ImmediateBackend):
        def start(self, callback):
            now[0] = 100.0
            result = super().start(callback)
            callback([0.25] * 32)
            return result

    backend = Backend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    now[0] = 90.0
    assert worker.is_capture_starting() is True
    assert worker.is_capture_stale() is False
    lane.run_next()
    assert worker.is_capture_healthy() is True
    assert worker.is_capture_starting() is False
    now[0] = 100.6
    assert worker.is_capture_stale() is True
    worker.stop()
    lane.run_next()

    # A successful open without a callback gets its full first-callback grace.
    backend = _ImmediateBackend()
    worker.start()
    now[0] = 200.0
    lane.run_next()
    now[0] = 200.9
    assert worker.is_capture_starting() is True
    assert worker.is_capture_stale() is False
    now[0] = 201.1
    assert worker.is_capture_stale() is True
    worker.stop()
    lane.run_next()


def test_stop_during_native_restart_releases_once_and_rejects_callback(monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    class Backend(_ImmediateBackend):
        def restart(self):
            entered.set()
            assert release.wait(2.0)
            self._callback([0.25] * 32)
            return True

    backend = Backend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.audio.capture.restart", category="visualizer.audio_capture",
        worker="audio_capture_test",
    )
    buffer = TripleBuffer()
    worker = SpotifyVisualizerAudioWorker(4, buffer)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    try:
        worker.start()
        lane.call(lambda: None, timeout=1.0)
        assert worker.restart_capture() is True
        assert entered.wait(1.0)
        for _ in range(100):
            assert worker.restart_capture() is True
        assert lane.diagnostic_snapshot()["pending"] == 0
        worker.stop()
        release.set()
        assert lane.stop(wait=True, timeout=2.0) is True
        assert backend.stop_calls == 1
        assert worker.has_capture_owner_work() is False
        assert buffer.consume_latest() is None
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=2.0)


def test_failed_close_retains_native_debt_and_prevents_replacement(monkeypatch):
    lane = _QueuedLane()
    created = []

    class Backend(_ImmediateBackend):
        def stop(self):
            self.stop_calls += 1
            raise RuntimeError("native close failed")

    def create(_config):
        backend = Backend()
        created.append(backend)
        return backend

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", create)
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.run_next()
    worker.stop()
    worker.start()
    with pytest.raises(RuntimeError, match="native close failed"):
        lane.run_next()
    assert len(created) == 1
    assert created[0].stop_calls == 1
    assert worker._backend is created[0]
    assert worker.has_capture_owner_work() is True
    assert worker.is_running() is False
    assert not lane.jobs
    with pytest.raises(RuntimeError, match="admission is closed"):
        worker.start()
    assert not lane.jobs


def test_running_config_changes_coalesce_to_one_latest_restart(monkeypatch):
    backend = _ImmediateBackend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    lane = _QueuedLane()
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.run_next()
    for epoch in range(100):
        worker.set_audio_block_size(128 if epoch % 2 else 512)
    assert len(lane.jobs) == 1
    lane.run_next()
    assert backend.restart_calls == 1
    assert backend._config.block_size == 128
    worker.stop()
    lane.run_next()


def test_engine_reopen_waits_for_retiring_capture_without_registering_empty_lane(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    created = []

    def create(_config):
        backend = _BlockingBackend(entered, release)
        created.append(backend)
        return backend

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", create)
    manager = ThreadManager()
    engine = _SpotifyBeatEngine(4)
    engine._audio_worker.set_audio_block_size(1024)
    engine.set_thread_manager(manager)
    try:
        assert "audio_capture" not in manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"]
        engine.ensure_started()
        assert entered.wait(1.0)
        old_lane = engine._capture_lane
        engine.force_stop()
        with pytest.raises(RuntimeError, match="retirement is pending"):
            engine.ensure_started()
        snapshot = manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"]["audio_capture"]
        assert snapshot["registered_lanes"] == 1
        assert snapshot["queue_depth"] == 0
        assert old_lane.diagnostic_snapshot()["active"] == 1
        release.set()
        assert old_lane.stop(wait=True, timeout=2.0) is True
        engine.ensure_started()
        engine._capture_lane.call(lambda: None, timeout=1.0)
        assert engine._capture_lane is not old_lane
        assert len(created) == 2
        assert created[0].stop_calls == 1
        assert engine._audio_worker.is_running() is True
    finally:
        release.set()
        engine.force_stop()
        manager.shutdown(wait=True, timeout=2.0)


def test_engine_closes_new_lane_when_worker_rejects_unexpected_owner(monkeypatch):
    manager = ThreadManager()
    engine = _SpotifyBeatEngine(4)
    engine.set_thread_manager(manager)

    def reject(_lane):
        raise RuntimeError("unexpected worker owner rejection")

    monkeypatch.setattr(engine._audio_worker, "set_capture_lane", reject)
    try:
        with pytest.raises(RuntimeError, match="unexpected worker owner rejection"):
            engine._ensure_capture_lane()
        snapshot = manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"]["audio_capture"]
        assert snapshot["registered_lanes"] == 0
        assert engine._capture_lane is None
    finally:
        manager.shutdown(wait=True, timeout=2.0)


def test_native_close_failure_remains_visible_to_manager_after_worker_exits(monkeypatch):
    class Backend(_ImmediateBackend):
        def stop(self):
            self.stop_calls += 1
            raise RuntimeError("native close failed")

    backend = Backend()
    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", lambda _: backend)
    manager = ThreadManager()
    lane = manager.create_affinity_lane(
        lane_id="test.audio.capture.release_debt", category="visualizer.audio_capture",
        worker="audio_capture_test",
    )
    worker = SpotifyVisualizerAudioWorker(4)
    worker.set_capture_lane(lane)
    worker.set_audio_block_size(1024)
    worker.start()
    lane.call(lambda: None, timeout=1.0)
    assert lane.diagnostic_snapshot()["resource_held"] is True
    worker.stop()
    assert lane.stop(wait=True, timeout=2.0) is False
    assert backend.stop_calls == 1
    assert manager.shutdown(wait=True, timeout=2.0) is False
    snapshot = manager.get_diagnostic_snapshot()["dedicated_affinity_lanes"]["audio_capture_test"]
    assert snapshot["worker_threads"] == 0
    assert snapshot["registered_lanes"] == 1
    native_work = [
        task for task in manager.get_lifecycle_ownership_snapshot()["active_tasks"]
        if task["category"] == "visualizer.audio_capture"
    ]
    assert len(native_work) == 1
    assert native_work[0]["resource_held"] is True
    assert native_work[0]["active"] is False
    assert native_work[0]["pending"] is False
    assert worker.has_capture_owner_work() is True
    with pytest.raises(RuntimeError, match="admission is closed"):
        worker.start()
    assert manager.shutdown(wait=True, timeout=2.0) is False
    assert backend.stop_calls == 1, "shutdown must not retry native deletion"
