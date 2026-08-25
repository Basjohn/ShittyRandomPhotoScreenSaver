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

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
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
        self.next_calls = 0
        self.previous_calls = 0
        self.seek_calls: list[float] = []
        self.retire_calls = 0

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def set_runtime_generation(self, runtime_generation) -> None:
        self.runtime_generation = runtime_generation

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

    def play_pause(self) -> None:
        self.play_pause_calls += 1

    def next(self) -> None:
        self.next_calls += 1

    def previous(self) -> None:
        self.previous_calls += 1

    def seek_fraction(self, fraction: float) -> None:
        self.seek_calls.append(float(fraction))

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


def test_shared_poll_cadence_retunes_one_timer_without_duplication() -> None:
    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track()})
    consumer = _Consumer(tm)
    service = _lease(consumer, factory)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == 1000

    tm.complete()
    assert service.refresh(bust_cache=True) is True
    tm.complete()

    assert len(tm.timers) == 1
    assert tm.timers[0].interval == 2000
    owner._reset_poll_stage()
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == 1000


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
    assert owner.update_timer_handle is None

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


def test_missing_session_retains_accepted_snapshot_and_enters_idle_cadence() -> None:
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
    owner._idle_threshold = 1
    consumer.snapshots.clear()

    assert service.refresh(bust_cache=True) is True
    tm.complete()

    retained = consumer.snapshots[-1].info
    assert retained is not None
    assert retained.title == "Retained"
    assert retained.state is MediaPlaybackState.PAUSED
    assert owner._is_idle is True
    assert len(tm.timers) == 1
    assert tm.timers[0].interval == owner._idle_poll_interval


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
    assert len(tm.jobs) == 1
    assert service.seek_fraction(float("nan")) is False
    assert factory.controllers[0][1].seek_calls == [1.0]

    service.shared_owner._current_info = replace(
        service.shared_owner._current_info,
        can_seek=False,
    )
    assert service.seek_fraction(0.25) is False
    assert factory.controllers[0][1].seek_calls == [1.0]


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


def test_production_setup_activates_reuses_and_retires_real_media_owner(
    qt_app,
    monkeypatch,
) -> None:
    from PySide6.QtWidgets import QWidget

    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services as runtime_services
    from rendering.widget_manager import WidgetManager

    tm = _ThreadManager()
    factory = _ControllerFactory({"spotify": _track(title="Production")})
    original_spec = runtime_services._RUNTIME_SERVICE_SPECS["media"]
    test_spec = runtime_services.RuntimeServiceSpec(
        build=lambda _widget_id, _config: MediaRuntimeService(
            provider="spotify",
            shared=True,
            controller_factory=factory,
        ),
        inject=original_spec.inject,
        retire=original_spec.retire,
        reuse_is_valid=original_spec.reuse_is_valid,
    )
    monkeypatch.setitem(
        runtime_services._RUNTIME_SERVICE_SPECS,
        "media",
        test_spec,
    )
    monkeypatch.setattr(
        WidgetManager,
        "create_spotify_visualizer_widget",
        lambda self, *args, **kwargs: None,
    )

    class _Signal:
        def connect(self, *_args, **_kwargs) -> None:
            return None

        def disconnect(self, *_args, **_kwargs) -> None:
            return None

    class _Settings:
        settings_changed = _Signal()

        def get_widgets_map(self) -> dict:
            return {
                "media": {
                    "enabled": True,
                    "monitor": "ALL",
                    "position": "WidgetPosition.TOP_CENTER",
                    "provider": "spotify",
                    "spotify_volume_enabled": False,
                    "mute_button_enabled": False,
                },
                "family_activation": {"media": True, "visualizers": False},
            }

        def get(self, key, default=None):
            return self.get_widgets_map() if key == "widgets" else default

    parent = QWidget()
    parent._thread_manager = tm
    parent._runtime_generation = 41
    parent.screen_index = 0
    manager = WidgetManager(parent, ResourceManager())
    settings = _Settings()
    service = None
    try:
        created = manager.setup_all_widgets(settings, screen_index=0, thread_manager=tm)
        widget = created["media_widget"]
        service = manager._runtime_manager.get_widget_service("media")
        assert service is widget._runtime_service
        assert widget.is_lifecycle_active() is True
        assert service.is_running() is True
        assert len(factory.controllers) == 1
        assert len(tm.timers) == 1
        assert len(tm.jobs) == 1

        tm.complete()
        assert widget.current_media_info().title == "Production"
        owner = service.shared_owner
        assert owner is not None

        recreated = manager.setup_all_widgets(
            settings,
            screen_index=0,
            thread_manager=tm,
        )
        assert recreated["media_widget"] is widget
        assert manager._runtime_manager.get_widget_service("media") is service
        assert service.shared_owner is owner
        assert service.is_running() is True
        assert len(factory.controllers) == 1
        assert len(tm.timers) == 1
        assert len(tm.jobs) == 0
    finally:
        manager.cleanup()
        parent.deleteLater()

    assert service is not None and service.is_retired() is True
    assert shared_media_owner_count() == 0
    assert factory.controllers[0][1].retire_calls == 1
    assert tm.timers[0].active is False
