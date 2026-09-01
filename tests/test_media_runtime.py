from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

import pytest
from PySide6.QtGui import QImage

from core.media.media_controller import (
    MediaCommandResult,
    MediaPlaybackState,
    MediaTrackInfo,
)
from core.threading.manager import ThreadManager
from widgets import media_runtime
from widgets.media_runtime import (
    MediaRuntimeService,
    reset_shared_media_runtime_for_tests,
    shared_media_owner_count,
)


def test_registry_import_is_media_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import sys
import rendering.widget_runtime_services  # noqa: F401

forbidden = {
    "widgets.media_runtime",
    "widgets.media_widget",
    "widgets.media.display_update",
    "core.media.media_controller",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


@dataclass
class _TaskResult:
    success: bool
    result: Any = None


class _Timer:
    def __init__(self, interval: int, callback) -> None:
        self.interval = int(interval)
        self.callback = callback
        self.active = True
        self.stop_calls = 0
        self.delete_calls = 0

    def isActive(self) -> bool:
        return self.active

    def setInterval(self, interval: int) -> None:
        self.interval = int(interval)

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.active = False

    def deleteLater(self) -> None:
        self.delete_calls += 1


class _ThreadManager:
    def __init__(self) -> None:
        self.jobs: list[tuple[Any, Any, dict[str, Any]]] = []
        self.timers: list[_Timer] = []

    def schedule_recurring(self, interval, callback, **_kwargs):
        timer = _Timer(interval, callback)
        self.timers.append(timer)
        return timer

    def submit_io_task(self, worker, callback=None, **kwargs) -> None:
        self.jobs.append((worker, callback, dict(kwargs)))

    def complete(self, index: int = 0, *, success: bool = True) -> Any:
        worker, callback, _kwargs = self.jobs.pop(index)
        result = worker() if success else None
        if callback is not None:
            callback(_TaskResult(success=success, result=result))
        return result


class _Controller:
    def __init__(
        self,
        *,
        info: MediaTrackInfo | None,
        selected_provider: str | None,
    ) -> None:
        self.info = info
        self.selected_provider = selected_provider
        self.thread_manager = None
        self.runtime_generation = None
        self.query_calls: list[tuple[str, ...]] = []
        self.play_pause_calls = 0
        self.play_pause_states: list[MediaPlaybackState | None] = []
        self.next_calls = 0
        self.previous_calls = 0
        self.seek_calls: list[float] = []
        self.retire_calls = 0
        self.command_result_handler = None
        # Event observation surface.
        self.event_on_dirty = None
        self.event_on_established = None
        self.observation_started = 0
        self.observation_stopped = 0
        self.observation_active = False
        self.supports_observation = True

    def supports_event_observation(self) -> bool:
        return self.supports_observation

    def start_event_observation(self, on_dirty, on_established=None) -> bool:
        if not self.supports_observation:
            return False
        self.event_on_dirty = on_dirty
        self.event_on_established = on_established
        self.observation_started += 1
        self.observation_active = True
        if on_established is not None:
            on_established(True, "session")
        return True

    def stop_event_observation(self) -> None:
        self.observation_stopped += 1
        self.observation_active = False
        self.event_on_dirty = None
        self.event_on_established = None

    def is_event_observation_active(self) -> bool:
        return self.observation_active

    def fire_dirty(self, reason: str) -> None:
        cb = self.event_on_dirty
        assert cb is not None, "native observation is not started"
        cb(reason)

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def set_runtime_generation(self, runtime_generation) -> None:
        self.runtime_generation = runtime_generation

    def set_command_result_handler(self, handler) -> None:
        self.command_result_handler = handler

    def retire(self) -> None:
        self.retire_calls += 1

    def get_current_track_from_io_worker(self, fallback_providers=()):
        self.query_calls.append(tuple(fallback_providers))
        selected = self.selected_provider
        if selected is None and self.info is not None:
            selected = "spotify"
        return selected, self.info

    def get_current_track(self):
        raise AssertionError("shared owner must use its existing I/O worker")

    def play_pause(self, desired_state=None) -> bool:
        self.play_pause_calls += 1
        self.play_pause_states.append(desired_state)
        return True

    def next(self) -> bool:
        self.next_calls += 1
        return True

    def previous(self) -> bool:
        self.previous_calls += 1
        return True

    def seek_fraction(self, fraction: float) -> bool:
        self.seek_calls.append(float(fraction))
        return True

    def complete_command(
        self,
        action: str,
        *,
        succeeded: bool,
        operation: str | None = None,
    ) -> None:
        assert self.command_result_handler is not None
        self.command_result_handler(
            MediaCommandResult(
                action=action,
                operation=operation or action,
                succeeded=succeeded,
                provider_result=succeeded,
            )
        )

    def is_app_process_running(self) -> bool:
        return True


class _ControllerFactory:
    def __init__(self, infos: dict[str, MediaTrackInfo | None]) -> None:
        self.infos = infos
        self.selected_providers: dict[str, str | None] = {}
        self.controllers: list[tuple[str, _Controller]] = []

    def __call__(self, *, thread_manager, app_filter):
        provider = str(app_filter)
        controller = _Controller(
            info=self.infos.get(provider),
            selected_provider=self.selected_providers.get(provider, provider),
        )
        controller.set_thread_manager(thread_manager)
        self.controllers.append((provider, controller))
        return controller


class _Consumer:
    def __init__(self, thread_manager, generation: int = 41) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []
        self.provider_changes = []
        self.volume_targets = []

    def is_media_consumer_alive(self) -> bool:
        return self.alive

    def on_media_runtime_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)

    def on_media_runtime_provider_changed(
        self,
        old_provider,
        provider,
        *,
        source,
        persist,
    ) -> None:
        self.provider_changes.append(
            (old_provider, provider, source, bool(persist))
        )

    def on_media_runtime_volume_target(self, provider, source_id) -> None:
        self.volume_targets.append((provider, source_id))


def _track(
    state: MediaPlaybackState = MediaPlaybackState.PLAYING,
    *,
    title: str = "Track",
    artwork: bytes | None = None,
    source_id: str = "Spotify.exe",
) -> MediaTrackInfo:
    return MediaTrackInfo(
        title=title,
        artist="Artist",
        album="Album",
        state=state,
        can_play_pause=True,
        can_next=True,
        can_previous=True,
        can_seek=True,
        artwork=artwork,
        source_app_user_model_id=source_id,
        position_ms=1200,
        duration_ms=9000,
    )


def _lease(
    consumer: _Consumer,
    factory: _ControllerFactory,
    *,
    provider: str = "spotify",
    shared: bool = True,
) -> MediaRuntimeService:
    service = MediaRuntimeService(
        provider=provider,
        shared=shared,
        controller_factory=factory,
    )
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


@pytest.fixture(autouse=True)
def _isolated_shared_owner(monkeypatch):
    reset_shared_media_runtime_for_tests()
    confirmations = []
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay_ms, callback, *_args, **_kwargs: confirmations.append((delay_ms, callback))),
    )
    yield confirmations
    reset_shared_media_runtime_for_tests()


def test_two_display_leases_share_one_controller_poll_and_query() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)

    assert first.shared_owner is second.shared_owner
    assert shared_media_owner_count() == 1
    assert first.start() is True
    assert second.start() is True

    owner = first.shared_owner
    assert owner is not None
    assert owner.active_consumer_count() == 2
    assert len(factory.controllers) == 1
    assert len(tm.timers) == 1
    assert len(tm.jobs) == 1
    assert tm.jobs[0][2]["task_id"].startswith("media_runtime_query_41_")

    tm.complete()
    assert [snapshot.info.title for snapshot in first_consumer.snapshots] == ["Track"]
    assert [snapshot.info.title for snapshot in second_consumer.snapshots] == ["Track"]


def test_healthy_event_runtime_arms_only_a_slow_reconcile_watchdog() -> None:
    """The retired 1000/2000/2500 ms active poll cadence must not exist.

    Under event-driven observation the only timer is the deep-idle-scale
    reconcile/liveness watchdog, and it never retunes to a fast poll stage when
    successful queries land (the pre-migration behaviour this replaces).
    """

    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]

    # Exactly one timer, at the deep-idle reconcile interval — never 1000/2000.
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == owner._RECONCILE_INTERVAL_MS
    assert tm.timers[0].interval >= 30000
    assert controller.observation_started == 1
    assert owner.event_observation_active is True

    # Repeated successful queries must not create or retune any fast poll timer.
    tm.complete()
    assert service.refresh(bust_cache=True) is True
    tm.complete()
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == owner._RECONCILE_INTERVAL_MS


def test_two_leases_start_event_observation_exactly_once() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)

    assert first.start() is True
    assert second.start() is True
    owner = first.shared_owner
    assert owner is not None
    assert len(factory.controllers) == 1
    controller = factory.controllers[0][1]
    # One shared owner => observation established once, not per lease.
    assert controller.observation_started == 1
    assert len(tm.timers) == 1


def test_dirty_edge_triggers_one_shared_refresh_and_reason_is_counted() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Live")})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    first.start()
    second.start()
    owner = first.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    tm.complete()  # activation refresh
    first_consumer.snapshots.clear()
    second_consumer.snapshots.clear()

    controller.fire_dirty("playback")
    # Exactly one shared refresh job — no per-display fan-out.
    assert len(tm.jobs) == 1
    tm.complete()
    assert [s.info.title for s in first_consumer.snapshots] == ["Live"]
    assert [s.info.title for s in second_consumer.snapshots] == ["Live"]
    telemetry = owner.event_telemetry()
    assert telemetry["event_counts"]["playback"] == 1
    assert telemetry["refresh_sources"]["event"] >= 1


def test_event_storm_coalesces_to_one_inflight_and_one_pending() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    tm.complete()  # activation refresh settles

    # First edge launches one refresh (now in flight).
    controller.fire_dirty("playback")
    assert owner.refresh_in_flight is True
    assert len(tm.jobs) == 1

    # A storm while one refresh is in flight collapses to a single pending edge.
    for _ in range(10):
        controller.fire_dirty("media_properties")
    assert len(tm.jobs) == 1
    assert owner._event_refresh_pending is True
    assert owner.event_telemetry()["dirty_coalesced"] >= 9

    # Completing the in-flight refresh launches exactly one more (the pending).
    tm.complete()
    assert len(tm.jobs) == 1
    assert owner._event_refresh_pending is False
    tm.complete()
    assert len(tm.jobs) == 0


def test_chatty_timeline_edges_are_bounded_by_the_coalescing_floor(
    _isolated_shared_owner, monkeypatch
) -> None:
    confirmations = _isolated_shared_owner
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    tm.complete()  # activation settles; nothing in flight

    clock = [1000.0]
    monkeypatch.setattr(media_runtime.time, "monotonic", lambda: clock[0])

    # First timeline edge refreshes promptly and stamps the timeline clock.
    controller.fire_dirty("timeline")
    assert len(tm.jobs) == 1
    tm.complete()
    assert len(tm.jobs) == 0

    # A second timeline edge within the floor must NOT spin a second query; it
    # is deferred to one event-armed single-shot flush (never a poll cadence).
    clock[0] += 0.2  # 200 ms < the 1000 ms floor
    before = len(confirmations)
    controller.fire_dirty("timeline")
    assert len(tm.jobs) == 0
    assert len(confirmations) == before + 1
    delay_ms, flush = confirmations[-1]
    assert 0 < delay_ms <= owner._TIMELINE_COALESCE_MS

    # Firing the flush at the boundary launches exactly one refresh.
    clock[0] += delay_ms / 1000.0
    flush()
    assert len(tm.jobs) == 1


def test_stale_generation_dirty_edge_is_rejected_after_stop() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    captured_on_dirty = controller.event_on_dirty
    tm.complete()

    # A stop bumps the owner generation and detaches observation.
    service.stop()
    assert controller.observation_stopped >= 1
    jobs_before = len(tm.jobs)
    # A late native callback captured before stop must not publish or query.
    if captured_on_dirty is not None:
        captured_on_dirty("timeline")
    assert len(tm.jobs) == jobs_before


def test_routine_success_does_not_reopen_activation_grace(monkeypatch) -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    owner = service.shared_owner
    assert owner is not None
    owner._activation_time = 123.0
    monkeypatch.setattr(media_runtime.time, "monotonic", lambda: 500.0)

    owner._accept_info(_track())
    assert owner._activation_time == 123.0

    owner._consecutive_none_count = 1
    owner._accept_info(_track())
    assert owner._activation_time == 500.0


def test_activation_failure_rolls_back_owner_and_lease_for_retry() -> None:
    class _FailingTimerManager(_ThreadManager):
        fail_timer = True

        def schedule_recurring(self, interval, callback, **kwargs):
            if self.fail_timer:
                raise RuntimeError("timer setup failed")
            return super().schedule_recurring(interval, callback, **kwargs)

    tm = _FailingTimerManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    owner = service.shared_owner
    assert owner is not None

    assert service.start() is False
    assert service.is_running() is False
    assert owner.is_running() is False
    assert owner.active_consumer_count() == 0
    assert owner.reconcile_timer_handle is None

    tm.fail_timer = False
    assert service.start() is True
    assert service.is_running() is True
    assert owner.active_consumer_count() == 1
    assert len(factory.controllers) == 1
    assert len(tm.timers) == 1
    assert len(tm.jobs) == 1


def test_lease_start_rolls_back_if_owner_activation_raises(monkeypatch) -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    owner = service.shared_owner
    assert owner is not None
    monkeypatch.setattr(owner, "activate", lambda _lease: (_ for _ in ()).throw(RuntimeError("boom")))

    assert service.start() is False
    assert service.is_running() is False


def test_first_and_last_consumer_lifetime_preserves_remaining_display() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    first.start()
    second.start()
    owner = first.shared_owner
    assert owner is not None

    first.retire()
    assert owner.is_running() is True
    assert owner.active_consumer_count() == 1
    assert owner.attached_consumer_count() == 1
    tm.complete()
    assert first_consumer.snapshots == []
    assert len(second_consumer.snapshots) == 1
    assert tm.timers[0].active is True

    second.stop()
    assert owner.is_running() is False
    assert tm.timers[0].active is False
    second.retire()
    assert owner.is_retired() is True
    assert shared_media_owner_count() == 0
    assert factory.controllers[0][1].retire_calls == 1


def test_one_source_decode_is_replayed_to_all_presenters(monkeypatch, qt_app) -> None:
    tm = _ThreadManager()
    payload = b"one-artwork-payload"
    factory = _ControllerFactory({"spotify": _track(artwork=payload)})
    consumers = [_Consumer(tm), _Consumer(tm)]
    services = [_lease(consumer, factory) for consumer in consumers]
    decoded = QImage(32, 24, QImage.Format.Format_ARGB32)
    decode_calls = []
    monkeypatch.setattr(
        media_runtime,
        "decode_media_artwork",
        lambda candidate: decode_calls.append(candidate) or decoded,
    )

    services[0].start()
    services[1].start()
    tm.complete()
    assert decode_calls == [payload]
    assert consumers[0].snapshots[-1].artwork.image is decoded
    assert consumers[1].snapshots[-1].artwork.image is decoded

    third_consumer = _Consumer(tm)
    third = _lease(third_consumer, factory)
    third.start()
    assert third_consumer.snapshots[-1].artwork.image is decoded
    assert len(tm.jobs) == 0

    assert services[0].refresh(bust_cache=True) is True
    tm.complete()
    assert decode_calls == [payload]


def test_artwork_decode_runs_in_io_job_and_delivery_crosses_ui_boundary(
    monkeypatch,
) -> None:
    tm = _ThreadManager()
    payload = b"thread-boundary-artwork"
    factory = _ControllerFactory({"spotify": _track(artwork=payload)})
    callback_threads = []

    class _ThreadRecordingConsumer(_Consumer):
        def on_media_runtime_snapshot(self, snapshot) -> None:
            callback_threads.append(threading.get_ident())
            super().on_media_runtime_snapshot(snapshot)

    consumer = _ThreadRecordingConsumer(tm)
    service = _lease(consumer, factory)
    decode_threads = []
    ui_callbacks = []
    image = QImage(16, 12, QImage.Format.Format_ARGB32)
    monkeypatch.setattr(
        media_runtime,
        "decode_media_artwork",
        lambda candidate: decode_threads.append(threading.get_ident()) or image,
    )
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: ui_callbacks.append(callback)),
    )

    service.start()
    # Activation also hops the (no-op here) observation-established callback to
    # the UI thread; this test measures only the artwork snapshot delivery, so
    # drain that unrelated hop first.
    ui_callbacks.clear()
    worker, callback, _kwargs = tm.jobs.pop()

    def _run_worker() -> None:
        callback(_TaskResult(success=True, result=worker()))

    thread = threading.Thread(target=_run_worker)
    thread.start()
    thread.join()

    assert decode_threads and decode_threads[0] != threading.get_ident()
    assert consumer.snapshots == []
    assert len(ui_callbacks) == 1
    ui_callbacks.pop()()
    assert callback_threads == [threading.get_ident()]
    assert consumer.snapshots[-1].artwork.image is image


def test_inflight_query_is_coalesced_and_stale_stop_restart_result_is_rejected() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Fresh")})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    assert service.refresh(bust_cache=True) is False
    service.wake_from_idle()
    assert len(tm.jobs) == 1

    service.stop()
    service.start()
    assert len(tm.jobs) == 2
    tm.complete(0)
    assert consumer.snapshots == []
    owner = service.shared_owner
    assert owner is not None and owner.refresh_in_flight is True

    tm.complete(0)
    assert [snapshot.info.title for snapshot in consumer.snapshots] == ["Fresh"]
    assert owner.refresh_in_flight is False


def test_stop_restart_waits_for_fresh_snapshot_instead_of_replaying_old_state() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Accepted before stop")})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    tm.complete()
    controller = factory.controllers[0][1]
    consumer.snapshots.clear()

    service.stop()
    controller.info = _track(title="Fresh after restart")
    assert service.start() is True

    assert consumer.snapshots == []
    assert len(tm.jobs) == 1
    tm.complete()
    assert [snapshot.info.title for snapshot in consumer.snapshots] == [
        "Fresh after restart"
    ]


def test_missing_session_retains_accepted_snapshot_without_idle_poll() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Retained")})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    tm.complete()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    controller.info = None
    owner._activation_time = time.monotonic() - 10.0
    consumer.snapshots.clear()

    assert service.refresh(bust_cache=True) is True
    tm.complete()

    retained = consumer.snapshots[-1].info
    assert retained is not None
    assert retained.title == "Retained"
    assert retained.state is MediaPlaybackState.PAUSED
    # A missing session must NOT spin up any idle poll cadence: the only timer
    # remains the deep-idle reconcile watchdog at its fixed interval.
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == owner._RECONCILE_INTERVAL_MS


def test_provider_generation_rejects_old_result_and_retires_old_controller() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory(
        {
            "spotify": _track(title="Old"),
            "musicbee": _track(title="New", source_id="MusicBee.exe"),
        }
    )
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    old_controller = factory.controllers[0][1]

    assert service.set_provider_runtime("musicbee") is True
    assert old_controller.retire_calls == 1
    assert len(factory.controllers) == 2
    assert len(tm.jobs) == 2
    tm.complete(0)
    assert consumer.snapshots == []
    tm.complete(0)
    assert consumer.snapshots[-1].provider == "musicbee"
    assert consumer.snapshots[-1].info.title == "New"


def test_retired_last_lease_rejects_late_query_and_drops_shared_owner() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Too Late")})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    assert len(tm.jobs) == 1

    service.retire()
    assert owner.is_retired() is True
    assert shared_media_owner_count() == 0
    tm.complete()

    assert consumer.snapshots == []
    assert factory.controllers[0][1].retire_calls == 1


def test_optimistic_playback_epoch_is_shared_and_pins_contradictory_result(
    _isolated_shared_owner,
) -> None:
    confirmations = _isolated_shared_owner
    tm = _ThreadManager()
    controller_info = _track(MediaPlaybackState.PLAYING)
    factory = _ControllerFactory({"spotify": controller_info})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    first.start()
    second.start()
    tm.complete()
    first_consumer.snapshots.clear()
    second_consumer.snapshots.clear()

    assert first.play_pause() is True
    owner = first.shared_owner
    assert owner is not None
    assert owner.playback_epoch == 1
    assert owner.expected_playback_state == MediaPlaybackState.PAUSED
    assert [s.info.state for s in first_consumer.snapshots] == [MediaPlaybackState.PAUSED]
    assert [s.info.state for s in second_consumer.snapshots] == [MediaPlaybackState.PAUSED]
    assert factory.controllers[0][1].play_pause_calls == 1
    assert factory.controllers[0][1].play_pause_states == [
        MediaPlaybackState.PAUSED
    ]
    assert confirmations[0][0] == 300

    first_consumer.snapshots.clear()
    second_consumer.snapshots.clear()
    assert first.refresh(bust_cache=True) is True
    tm.complete()
    assert first_consumer.snapshots[-1].info.state == MediaPlaybackState.PAUSED
    assert owner.expected_playback_state == MediaPlaybackState.PAUSED

    owner._playback_confirmation_deadline_monotonic = time.monotonic() - 1.0
    assert first.refresh(bust_cache=True) is True
    tm.complete()
    assert first_consumer.snapshots[-1].info.state == MediaPlaybackState.PLAYING
    assert second_consumer.snapshots[-1].info.state == MediaPlaybackState.PLAYING
    assert owner.expected_playback_state is None


def test_seek_routes_clamped_fraction_without_optimistic_timeline_authority() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    tm.complete()
    accepted_position = consumer.snapshots[-1].info.position_ms

    assert service.seek_fraction(1.5) is True
    assert factory.controllers[0][1].seek_calls == [1.0]
    assert consumer.snapshots[-1].info.position_ms == accepted_position
    assert service.refresh(bust_cache=True) is True
    assert len(tm.jobs) == 1
    factory.controllers[0][1].complete_command("seek", succeeded=True)
    assert len(tm.jobs) == 1
    assert service.shared_owner._command_refresh_pending is True
    tm.complete()
    assert len(tm.jobs) == 1
    assert service.shared_owner._command_refresh_pending is False
    assert service.seek_fraction(float("nan")) is False
    assert factory.controllers[0][1].seek_calls == [1.0]

    service.shared_owner._current_info = replace(
        service.shared_owner._current_info,
        can_seek=False,
    )
    assert service.seek_fraction(0.25) is False
    assert factory.controllers[0][1].seek_calls == [1.0]


def test_rejected_play_pause_completion_clears_optimism_and_reconciles() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(MediaPlaybackState.PLAYING)})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    tm.complete()

    assert service.play_pause() is True
    owner = service.shared_owner
    controller = factory.controllers[0][1]
    assert owner.expected_playback_state == MediaPlaybackState.PAUSED
    assert consumer.snapshots[-1].info.state == MediaPlaybackState.PAUSED
    assert len(tm.jobs) == 0

    controller.complete_command(
        "play_pause",
        succeeded=False,
        operation="pause",
    )

    assert owner.expected_playback_state is None
    assert len(tm.jobs) == 1
    tm.complete()
    assert consumer.snapshots[-1].info.state == MediaPlaybackState.PLAYING


def test_failover_persists_once_and_syncs_every_display_volume_target() -> None:
    tm = _ThreadManager()
    accepted = _track(title="Browser", source_id="firefox.exe")
    factory = _ControllerFactory(
        {"spotify": accepted, "spotify_browser": accepted}
    )
    factory.selected_providers["spotify"] = "spotify_browser"
    consumers = [_Consumer(tm), _Consumer(tm)]
    services = [_lease(consumer, factory) for consumer in consumers]
    services[0].start()
    services[1].start()

    tm.complete()

    changes = [change for consumer in consumers for change in consumer.provider_changes]
    assert len(changes) == 2
    assert all(change[:3] == ("spotify", "spotify_browser", "media_runtime_autofallback") for change in changes)
    assert sum(1 for change in changes if change[3]) == 1
    assert all(
        consumer.volume_targets == [("spotify_browser", "firefox.exe")]
        for consumer in consumers
    )
    assert all(consumer.snapshots[-1].provider == "spotify_browser" for consumer in consumers)


def test_standalone_services_never_join_production_shared_owner() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first_consumer = _Consumer(tm)
    second_consumer = _Consumer(tm)
    first = _lease(first_consumer, factory, shared=False)
    second = _lease(second_consumer, factory, shared=False)

    assert first.shared_owner is not second.shared_owner
    assert shared_media_owner_count() == 0
    first.start()
    second.start()
    assert len(factory.controllers) == 2
    assert len(tm.timers) == 2
    assert len(tm.jobs) == 2


def test_shared_lease_requires_a_real_runtime_scope() -> None:
    service = MediaRuntimeService(shared=True)
    consumer = _Consumer(None)
    consumer._runtime_generation = None

    with pytest.raises(RuntimeError, match="runtime generation or ThreadManager"):
        service.attach_consumer(consumer)


def test_one_lease_cannot_be_rebound_to_a_second_consumer() -> None:
    tm = _ThreadManager()
    service = MediaRuntimeService(shared=True)
    first = _Consumer(tm)
    second = _Consumer(tm)
    service.set_thread_manager(tm)
    service.attach_consumer(first)

    with pytest.raises(RuntimeError, match="another consumer"):
        service.attach_consumer(second)


def test_same_generation_rejects_a_second_thread_manager_without_leaking_lease() -> None:
    first_tm = _ThreadManager()
    second_tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first = _lease(_Consumer(first_tm, generation=91), factory)
    second_consumer = _Consumer(second_tm, generation=91)
    second = MediaRuntimeService(
        provider="spotify",
        shared=True,
        controller_factory=factory,
    )
    second.set_thread_manager(second_tm)

    with pytest.raises(RuntimeError, match="one ThreadManager"):
        second.attach_consumer(second_consumer)

    assert second.shared_owner is None
    assert second._consumer() is None
    assert shared_media_owner_count() == 1
    first.retire()
    assert shared_media_owner_count() == 0


def test_distinct_runtime_generations_own_and_retire_independent_media_families() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    first = _lease(_Consumer(tm, generation=101), factory)
    second = _lease(_Consumer(tm, generation=102), factory)

    assert shared_media_owner_count() == 2
    assert first.shared_owner is not second.shared_owner
    assert first.start() is True
    assert second.start() is True
    assert len(factory.controllers) == 2
    assert len(tm.timers) == 2

    first.retire()
    assert shared_media_owner_count() == 1
    assert second.is_running() is True
    second.retire()
    assert shared_media_owner_count() == 0


def test_command_result_and_native_event_share_one_coalescing_owner() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(MediaPlaybackState.PLAYING)})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    tm.complete()

    # A command result while a refresh is in flight sets the command-pending
    # edge; a native event arriving in the same window collapses into the same
    # single-in-flight coalescing owner rather than fanning out a second query.
    assert service.refresh(bust_cache=True) is True
    assert owner.refresh_in_flight is True
    controller.complete_command("play_pause", succeeded=True, operation="toggle_play_pause")
    controller.fire_dirty("playback")
    assert owner._command_refresh_pending is True
    assert len(tm.jobs) == 1  # still just the in-flight refresh

    tm.complete()
    # Exactly one follow-up refresh launches for the pending edge (command wins).
    assert len(tm.jobs) == 1
    sources = owner.event_telemetry()["refresh_sources"]
    assert sources.get("command", 0) >= 1


def test_reconcile_watchdog_flags_missed_event_on_untracked_change() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="First")})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    tm.complete()  # accept "First"
    assert owner.event_telemetry()["missed_events"] == 0

    # The track changed but (hypothetically) no native event delivered it: the
    # reconcile heartbeat discovers the non-position change and flags it.
    controller.info = _track(title="Second changed without event")
    owner._reconcile()
    tm.complete()
    telemetry = owner.event_telemetry()
    assert telemetry["missed_events"] == 1
    assert telemetry["refresh_sources"].get("reconcile", 0) >= 1

    # A pure position advance on the same track is NOT counted as a missed event.
    controller.info = replace(
        _track(title="Second changed without event"),
        position_ms=5000,
    )
    owner._reconcile()
    tm.complete()
    assert owner.event_telemetry()["missed_events"] == 1


def test_unsupported_observation_is_degraded_and_never_fast_polls() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    factory.selected_providers["spotify"] = "spotify"
    consumer = _Consumer(tm)
    service = MediaRuntimeService(
        provider="spotify", shared=True, controller_factory=factory
    )
    service.set_thread_manager(tm)
    service.attach_consumer(consumer)
    owner = service.shared_owner
    assert owner is not None
    # Force the controller to report no native observation support.
    service.start()
    owner._stop_event_observation()
    controller = factory.controllers[0][1]
    controller.supports_observation = False
    owner._start_event_observation()

    assert owner.event_observation_active is False
    assert owner.event_observation_degraded is True
    # Degraded must NOT reactivate a fast poll: the only timer is the slow
    # reconcile watchdog, still at its deep-idle interval.
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == owner._RECONCILE_INTERVAL_MS


def test_retire_stops_observation_exactly_once_and_blocks_late_publish() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    controller = factory.controllers[0][1]
    late_dirty = controller.event_on_dirty
    tm.complete()
    consumer.snapshots.clear()

    service.retire()
    assert owner.is_retired() is True
    # Observation detached (owner.stop + controller.retire both request it, but
    # the fake counts each stop_event_observation call).
    assert controller.observation_stopped >= 1
    assert controller.retire_calls == 1

    # A callback captured before retirement cannot publish afterwards.
    if late_dirty is not None:
        late_dirty("media_properties")
    assert consumer.snapshots == []
    assert shared_media_owner_count() == 0
