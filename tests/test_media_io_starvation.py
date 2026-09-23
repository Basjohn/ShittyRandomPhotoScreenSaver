"""PW-02: Media truth and commands must not queue behind network work.

Four stalled network tasks (e.g. DNS resolution, which ``requests`` timeouts do
not bound) occupy every FIFO IO worker. A Media refresh (the Visualizer's
play/pause truth) and a user transport command submitted through their
production paths still start promptly, because the shared Media runtime owner
runs both on its own serial lane (a dedicated "media" worker), not on the IO
pool and not on the WinRT observation worker.
"""

from __future__ import annotations

import threading
import time

import pytest

from core.threading.manager import ThreadManager

_STALL_S = 1.5
_PROMPT_S = 0.4


@pytest.fixture
def saturated_io_pool():
    manager = ThreadManager()
    release = threading.Event()
    started = threading.Barrier(5)

    def _network_stall():
        started.wait(timeout=5.0)
        release.wait(timeout=_STALL_S)

    for index in range(4):
        manager.submit_io_task(_network_stall, task_id=f"network_stall_{index}", category="network")
    started.wait(timeout=5.0)  # every IO worker is now busy
    try:
        yield manager
    finally:
        release.set()
        manager.shutdown(wait=True, timeout=5.0)


def _started_within(event: threading.Event, seconds: float) -> bool:
    return event.wait(timeout=seconds)


def test_media_transport_command_starts_while_network_stalls_the_io_pool(saturated_io_pool) -> None:
    from core.media.media_controller import BaseMediaController, WindowsGlobalMediaController
    from widgets.media_runtime import _SharedMediaRuntimeOwner

    ran = threading.Event()
    lane_threads: list[str] = []

    class _Controller(BaseMediaController):
        _command_inflight = False

        def _run_coro_in_isolated_loop(self, _factory, on_error=None):
            lane_threads.append(threading.current_thread().name)
            ran.set()
            return True

    controller = _Controller()
    owner = _SharedMediaRuntimeOwner(
        provider="spotify",
        thread_manager=saturated_io_pool,
        runtime_generation=None,
        controller=controller,
    )
    try:
        owner._configure_controller(controller)  # production injection of the Media lane
        queued_at = time.monotonic()
        assert WindowsGlobalMediaController._submit_command(controller, "play_pause", lambda: None)
        assert _started_within(ran, _PROMPT_S), (
            f"command still queued after {time.monotonic() - queued_at:.2f}s"
        )
        assert lane_threads == ["affinity_io_lane:media"]
    finally:
        owner.retire()


def test_media_lane_is_not_the_observation_worker_and_stops_with_its_owner(saturated_io_pool) -> None:
    from widgets.media_runtime import _SharedMediaRuntimeOwner

    observation = saturated_io_pool.create_affinity_lane(
        lane_id="observation_probe", category="media_event_observation"
    )
    owner = _SharedMediaRuntimeOwner(
        provider="spotify", thread_manager=saturated_io_pool, runtime_generation=77
    )
    try:
        lane = owner._ensure_media_lane()
        names = {
            lane.call(lambda: threading.current_thread().name, timeout=1.0),
            observation.call(lambda: threading.current_thread().name, timeout=1.0),
        }
        assert names == {"affinity_io_lane:media", "affinity_io_lane"}
        snapshot = saturated_io_pool.get_diagnostic_snapshot()
        media = snapshot["dedicated_affinity_lanes"]["media"]
        assert [entry["category"] for entry in media["lanes"]] == ["media_runtime"]
        assert media["lanes"][0]["runtime_generation"] == 77
    finally:
        owner.retire()
        observation.stop(wait=True, timeout=1.0)
    assert lane.is_stopped
    assert owner._media_lane is None
    assert not [
        task
        for task in saturated_io_pool.get_lifecycle_ownership_snapshot()["active_tasks"]
        if task.get("category") == "media_runtime"
    ]


def test_media_refresh_starts_while_network_stalls_the_io_pool(qt_app, saturated_io_pool) -> None:
    from widgets.media_runtime import MediaRuntimeService, reset_shared_media_runtime_for_tests
    from core.media.media_controller import MediaPlaybackState, MediaTrackInfo

    queried = threading.Event()
    query_threads: list[str] = []

    class _Controller:
        def set_thread_manager(self, _tm): pass
        def set_runtime_generation(self, _generation): pass
        def set_command_result_handler(self, _handler): pass
        def supports_event_observation(self): return False
        def retire(self): pass

        def get_current_track_from_io_worker(self, fallback_providers=(), *, reuse_artwork_identity=None):
            query_threads.append(threading.current_thread().name)
            queried.set()
            return "spotify", MediaTrackInfo(title="t", state=MediaPlaybackState.PLAYING)

    class _Consumer:
        _thread_manager = saturated_io_pool
        _runtime_generation = 4242
        def is_media_consumer_alive(self): return True
        def on_media_runtime_snapshot(self, _snapshot): pass
        def on_media_runtime_provider_changed(self, *_a, **_k): pass
        def on_media_runtime_volume_target(self, *_a): pass

    reset_shared_media_runtime_for_tests()
    consumer = _Consumer()
    service = MediaRuntimeService(
        provider="spotify",
        shared=True,
        controller_factory=lambda **_kwargs: _Controller(),
    )
    service.set_thread_manager(saturated_io_pool)
    service.attach_consumer(consumer)
    try:
        service.start()  # activation refresh: the first play/pause truth
        assert _started_within(queried, _PROMPT_S), "Media refresh queued behind network stalls"
        assert query_threads == ["affinity_io_lane:media"]
    finally:
        service.stop()
        reset_shared_media_runtime_for_tests()
