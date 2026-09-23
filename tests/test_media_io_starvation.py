"""PW-02 evidence: Media truth and commands share the FIFO IO pool with network work.

Four stalled network tasks (e.g. DNS resolution, which ``requests`` timeouts do
not bound) occupy every IO worker. A Media refresh (the Visualizer's play/pause
truth) and a user transport command submitted through their production paths
must still start promptly. Today they queue behind the stalls; these bars are
strict xfails until Media gets an executor that network work cannot starve.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

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


@pytest.mark.xfail(strict=True, reason="PW-02: Media commands queue behind stalled network work")
def test_media_transport_command_starts_while_network_stalls_the_io_pool(saturated_io_pool) -> None:
    from core.media.media_controller import WindowsGlobalMediaController

    ran = threading.Event()
    controller = SimpleNamespace(
        _retired=False,
        _thread_manager=saturated_io_pool,
        _command_inflight=False,
        _command_result_handler=None,
        _task_owner_id="pw02",
        _runtime_generation=None,
        _run_coro_in_isolated_loop=lambda _factory, on_error=None: ran.set() or True,
    )
    queued_at = time.monotonic()
    assert WindowsGlobalMediaController._submit_command(controller, "play_pause", lambda: None)
    assert _started_within(ran, _PROMPT_S), (
        f"command still queued after {time.monotonic() - queued_at:.2f}s"
    )


@pytest.mark.xfail(strict=True, reason="PW-02: Media refresh queues behind stalled network work")
def test_media_refresh_starts_while_network_stalls_the_io_pool(saturated_io_pool) -> None:
    from widgets.media_runtime import MediaRuntimeService, reset_shared_media_runtime_for_tests
    from core.media.media_controller import MediaPlaybackState, MediaTrackInfo

    queried = threading.Event()

    class _Controller:
        def set_thread_manager(self, _tm): pass
        def set_runtime_generation(self, _generation): pass
        def set_command_result_handler(self, _handler): pass
        def supports_event_observation(self): return False
        def retire(self): pass

        def get_current_track_from_io_worker(self, fallback_providers=(), *, reuse_artwork_identity=None):
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
    finally:
        service.stop()
        reset_shared_media_runtime_for_tests()
