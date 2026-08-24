"""Playback freshness and optimistic transport at the neutral Media boundary.

The shared Media runtime owns controller/query generations, playback epochs and
bounded command confirmation. These tests deliberately use lightweight
consumers instead of requiring a ``MediaWidget`` to expose those owner details.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from core.threading.manager import ThreadManager
from widgets.media_runtime import (
    MediaRuntimeService,
    reset_shared_media_runtime_for_tests,
    shared_media_owner_count,
)


PLAYING = MediaPlaybackState.PLAYING
PAUSED = MediaPlaybackState.PAUSED


def _info(state, *, title="Song", artist="Artist", album="Album"):
    return MediaTrackInfo(
        title=title,
        artist=artist,
        album=album,
        state=state,
        can_play_pause=True,
    )


class _TaskResult:
    success = True

    def __init__(self, result):
        self.result = result


class _HoldingThreadManager:
    def __init__(self):
        self.jobs = []
        self.recurring = []

    def submit_io_task(self, worker, callback=None, **_kwargs):
        self.jobs.append((worker, callback))

    def schedule_recurring(self, _interval, callback, **_kwargs):
        handle = _TimerHandle(callback)
        self.recurring.append(handle)
        return handle


class _TimerHandle:
    def __init__(self, callback):
        self.callback = callback
        self.stopped = False
        self.interval = 1000

    def stop(self):
        self.stopped = True

    def is_active(self):
        return not self.stopped

    def isActive(self):
        return not self.stopped

    def setInterval(self, interval):
        self.interval = int(interval)

    def start(self):
        self.stopped = False

    def deleteLater(self):
        return None


class _Controller:
    def __init__(self, info=None):
        self.info = info
        self.play_pause_calls = 0
        self.next_calls = 0
        self.previous_calls = 0
        self.retired = False

    def set_thread_manager(self, _thread_manager):
        pass

    def get_current_track_from_io_worker(self, _providers):
        return None, self.info

    def get_current_track(self):
        return self.info

    def play_pause(self):
        self.play_pause_calls += 1

    def next(self):
        self.next_calls += 1

    def previous(self):
        self.previous_calls += 1

    def retire(self):
        self.retired = True


class _Consumer:
    def __init__(self, thread_manager, runtime_generation="media-test-generation"):
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self.alive = True
        self.snapshots = []
        self.provider_changes = []
        self.volume_targets = []

    def is_media_consumer_alive(self):
        return self.alive

    def on_media_runtime_snapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def on_media_runtime_provider_changed(self, *args, **kwargs):
        self.provider_changes.append((args, kwargs))

    def on_media_runtime_volume_target(self, *args):
        self.volume_targets.append(args)


@pytest.fixture(autouse=True)
def _reset_shared_owner():
    reset_shared_media_runtime_for_tests()
    yield
    reset_shared_media_runtime_for_tests()


def _service(
    tm,
    consumer,
    *,
    controller=None,
    controller_factory=None,
    shared=False,
):
    service = MediaRuntimeService(
        provider="spotify",
        shared=shared,
        controller=controller,
        controller_factory=controller_factory or (lambda **_kwargs: controller),
        runtime_generation=consumer._runtime_generation,
    )
    service.set_thread_manager(tm)
    service.attach_consumer(consumer)
    assert service.start() is True
    return service


def _complete_job(tm, index=0):
    worker, callback = tm.jobs.pop(index)
    callback(_TaskResult(worker()))


def _owner(service):
    owner = service.shared_owner
    assert owner is not None
    return owner


class TestExpectedStateOwnership:
    def test_an_optimistic_edge_owns_expected_state_epoch_and_deadline(self):
        tm = _HoldingThreadManager()
        consumer = _Consumer(tm)
        service = _service(tm, consumer, controller=_Controller())
        owner = _owner(service)
        before_epoch = owner.playback_epoch
        before_time = time.monotonic()

        owner._begin_playback_confirmation(PAUSED)

        assert owner.playback_epoch == before_epoch + 1
        assert owner.expected_playback_state == PAUSED
        assert owner.expected_playback_epoch == owner.playback_epoch
        assert owner.playback_confirmation_deadline > before_time

    def test_the_optimistic_edge_invalidates_the_runtime_query_cache(self):
        tm = _HoldingThreadManager()
        consumer = _Consumer(tm)
        service = _service(tm, consumer, controller=_Controller())
        owner = _owner(service)
        owner._query_cache_info = _info(PLAYING)

        owner._begin_playback_confirmation(PAUSED)

        assert owner._query_cache_info is None

    def test_confirmation_refresh_is_owner_scheduled_and_keeps_expectation(self, monkeypatch):
        tm = _HoldingThreadManager()
        consumer = _Consumer(tm)
        service = _service(tm, consumer, controller=_Controller())
        owner = _owner(service)
        scheduled = []
        refreshes = []
        monkeypatch.setattr(
            ThreadManager,
            "single_shot",
            staticmethod(lambda delay, callback, **_kwargs: scheduled.append((delay, callback))),
        )
        owner.refresh = lambda **kwargs: refreshes.append(kwargs) or True

        owner._begin_playback_confirmation(PAUSED)
        assert len(scheduled) == 1
        delay, callback = scheduled[0]
        callback()

        assert delay == owner._PLAYBACK_CONFIRMATION_REFRESH_DELAY_MS
        assert refreshes == [{"bust_cache": True}]
        assert owner.expected_playback_state == PAUSED
        assert owner.expected_playback_epoch == owner.playback_epoch


def test_runtime_entry_clears_an_expectation_on_deactivation():
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._begin_playback_confirmation(PAUSED)

    service.stop()

    assert owner.expected_playback_state is None
    assert owner.expected_playback_epoch is None
    assert owner.playback_confirmation_deadline == 0.0


def test_provider_switch_clears_the_previous_provider_expectation():
    tm = _HoldingThreadManager()
    controller = _Controller()
    replacement = _Controller()
    consumer = _Consumer(tm)
    service = _service(
        tm,
        consumer,
        controller=controller,
        controller_factory=lambda **_kwargs: replacement,
    )
    owner = _owner(service)
    owner._begin_playback_confirmation(PAUSED)

    changed = service.set_provider_runtime("musicbee")

    assert changed is True
    assert owner.expected_playback_state is None
    assert owner.expected_playback_epoch is None
    assert owner.playback_confirmation_deadline == 0.0
    assert controller.retired is True
    assert owner.controller is replacement


def test_async_refresh_result_cannot_publish_after_stop(monkeypatch):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    controller = _Controller(_info(PLAYING))
    service = _service(tm, consumer, controller=controller)

    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    assert tm.jobs

    service.stop()
    _complete_job(tm)

    assert consumer.snapshots == []
    assert _owner(service).refresh_in_flight is False


def test_old_refresh_cannot_publish_or_clear_new_work_after_stop_and_restart(monkeypatch):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    controller = _Controller(_info(PLAYING, title="Old runtime"))
    service = _service(tm, consumer, controller=controller)
    owner = _owner(service)

    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    old_worker, old_callback = tm.jobs.pop(0)

    service.stop()
    controller.info = _info(PAUSED, title="New runtime")
    assert service.start() is True
    new_worker, new_callback = tm.jobs.pop(0)

    old_callback(_TaskResult(old_worker()))

    assert consumer.snapshots == []
    assert owner.refresh_in_flight is True

    new_callback(_TaskResult(new_worker()))

    assert [snapshot.info.title for snapshot in consumer.snapshots] == ["New runtime"]
    assert owner.refresh_in_flight is False


@pytest.mark.parametrize(
    ("expected_state", "stale_state"),
    ((PAUSED, PLAYING), (PLAYING, PAUSED)),
)
def test_stale_pre_command_refresh_is_pinned_in_both_directions(
    expected_state,
    stale_state,
):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._current_info = _info(expected_state)
    refresh_epoch = owner.playback_epoch
    owner._begin_playback_confirmation(expected_state)

    stale = _info(stale_state, title="Fresh metadata", artist="New Artist")
    reconciled = owner._reconcile_playback_epoch(stale, refresh_epoch)

    assert reconciled.state == expected_state
    assert reconciled.title == "Fresh metadata"
    assert reconciled.artist == "New Artist"
    assert owner.expected_playback_state == expected_state


def test_an_older_refresh_cannot_confirm_the_current_expectation():
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    refresh_epoch = owner.playback_epoch
    owner._current_info = _info(PAUSED)
    owner._begin_playback_confirmation(PAUSED)

    reconciled = owner._reconcile_playback_epoch(_info(PAUSED), refresh_epoch)

    assert reconciled.state == PAUSED
    assert owner.expected_playback_state == PAUSED


def test_an_older_result_from_the_first_of_two_commands_cannot_reverse_the_second():
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    first_refresh_epoch = owner.playback_epoch
    owner._current_info = _info(PAUSED)
    owner._begin_playback_confirmation(PAUSED)
    owner._current_info = _info(PLAYING)
    owner._begin_playback_confirmation(PLAYING)
    latest_epoch = owner.playback_epoch

    reconciled = owner._reconcile_playback_epoch(
        _info(PAUSED, title="Metadata after two commands"),
        first_refresh_epoch,
    )

    assert reconciled.state == PLAYING
    assert reconciled.title == "Metadata after two commands"
    assert owner.expected_playback_state == PLAYING
    assert owner.expected_playback_epoch == latest_epoch


@pytest.mark.parametrize("expected_state", (PAUSED, PLAYING))
def test_matching_same_epoch_refresh_confirms_and_clears(expected_state):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._current_info = _info(expected_state)
    owner._begin_playback_confirmation(expected_state)
    refresh_epoch = owner.playback_epoch

    reconciled = owner._reconcile_playback_epoch(_info(expected_state), refresh_epoch)

    assert reconciled.state == expected_state
    assert owner.expected_playback_state is None
    assert owner.expected_playback_epoch is None
    assert owner.playback_confirmation_deadline == 0.0


@pytest.mark.parametrize(
    ("expected_state", "contradictory_state"),
    ((PAUSED, PLAYING), (PLAYING, PAUSED)),
)
def test_same_epoch_contradiction_is_pinned_before_deadline_with_metadata_flow(
    expected_state,
    contradictory_state,
):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._current_info = _info(expected_state)
    owner._begin_playback_confirmation(expected_state)
    refresh_epoch = owner.playback_epoch
    contradiction = _info(
        contradictory_state,
        title="Backend metadata",
        artist="Backend artist",
    )

    reconciled = owner._reconcile_playback_epoch(contradiction, refresh_epoch)

    assert reconciled.state == expected_state
    assert reconciled.title == contradiction.title
    assert reconciled.artist == contradiction.artist
    assert owner.expected_playback_state == expected_state


@pytest.mark.parametrize(
    ("expected_state", "contradictory_state"),
    ((PAUSED, PLAYING), (PLAYING, PAUSED)),
)
def test_same_epoch_contradiction_becomes_authoritative_after_expiry(
    expected_state,
    contradictory_state,
):
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._current_info = _info(expected_state)
    owner._begin_playback_confirmation(expected_state)
    refresh_epoch = owner.playback_epoch
    owner._playback_confirmation_deadline_monotonic = time.monotonic() - 1.0

    reconciled = owner._reconcile_playback_epoch(
        _info(contradictory_state),
        refresh_epoch,
    )

    assert reconciled.state == contradictory_state
    assert owner.expected_playback_state is None
    assert owner.expected_playback_epoch is None
    assert owner.playback_confirmation_deadline == 0.0


def test_one_shared_transport_edge_reaches_two_consumers():
    tm = _HoldingThreadManager()
    controller = _Controller()
    first = _Consumer(tm)
    second = _Consumer(tm)

    def factory(**_kwargs):
        return controller

    first_service = _service(
        tm,
        first,
        controller_factory=factory,
        shared=True,
    )
    second_service = MediaRuntimeService(
        provider="spotify",
        shared=True,
        controller_factory=factory,
        runtime_generation=second._runtime_generation,
    )
    second_service.set_thread_manager(tm)
    second_service.attach_consumer(second)
    assert second_service.start() is True
    owner = _owner(first_service)
    assert _owner(second_service) is owner
    assert shared_media_owner_count() == 1

    owner._current_info = _info(PLAYING)
    first.snapshots.clear()
    second.snapshots.clear()

    assert first_service.play_pause(execute=False) is True

    assert [snapshot.info.state for snapshot in first.snapshots] == [PAUSED]
    assert [snapshot.info.state for snapshot in second.snapshots] == [PAUSED]
    assert owner.playback_epoch == 1
    assert owner.expected_playback_state == PAUSED


def test_runtime_snapshot_reaches_visualizer_through_media_widget_signal(
    qt_app,
    monkeypatch,
):
    from widgets.media_widget import MediaWidget
    from widgets.spotify_visualizer import media_bridge

    tm = _HoldingThreadManager()
    controller = _Controller(_info(PLAYING, title="Original"))
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, **_kwargs: scheduled.append((delay, callback))),
    )
    widget = MediaWidget(controller=controller, thread_manager=tm)
    emitted = []
    visualizer_edges = []
    visualizer = SimpleNamespace(
        _spotify_playing=True,
        _last_committed_playback_state=PLAYING.value,
        _pending_playback_pause_timer=None,
        _pending_playback_pause_state=None,
        _last_media_state_ts=0.0,
        _fallback_logged=False,
        _startup_has_authoritative_media_update=False,
        _startup_idle_reveal_requires_authoritative_media=False,
        _startup_require_playing_before_reveal=False,
        _startup_reveal_pending=False,
        _startup_hot_start_started=False,
        _waiting_for_fresh_frame=False,
        _last_artwork_hash=0,
        _has_seen_media=True,
        _engine=SimpleNamespace(
            set_playback_state=lambda playing: visualizer_edges.append(bool(playing))
        ),
        _reset_latency_diagnostics=lambda: None,
        _trigger_wake=lambda **_kwargs: None,
        _finish_staged_startup_reveal=lambda **_kwargs: None,
        sync_visibility_with_anchor=lambda: None,
    )

    def _listener(payload):
        emitted.append(payload)
        media_bridge.handle_media_update(visualizer, payload)

    try:
        widget.start()
        _complete_job(tm)
        widget.media_updated.connect(_listener)
        widget._handle_control_feedback = lambda *args, **kwargs: None
        widget._has_seen_first_track = True
        widget._fixed_card_height = 220
        widget._fade_in_completed = True
        widget.isVisible = lambda: True

        widget.play_pause(execute=False)

        assert emitted[-1]["state"] == PAUSED.value
        assert visualizer_edges == [False]
        owner = _owner(widget._runtime_service)
        assert owner.expected_playback_state is PAUSED
        assert scheduled

        controller.info = _info(
            PLAYING,
            title="New title from backend",
            artist="New artist from backend",
        )
        assert widget._runtime_service.refresh(bust_cache=True) is True
        _complete_job(tm)
        assert emitted[-1]["title"] == "New title from backend"
        assert emitted[-1]["artist"] == "New artist from backend"
        assert emitted[-1]["state"] == PAUSED.value
        assert visualizer_edges == [False]

        owner._playback_confirmation_deadline_monotonic = time.monotonic() - 1.0
        assert widget._runtime_service.refresh(bust_cache=True) is True
        _complete_job(tm)
        assert emitted[-1]["state"] == PLAYING.value
        assert visualizer_edges == [False, True]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_a_none_result_is_passed_through_without_releasing_expectation():
    tm = _HoldingThreadManager()
    consumer = _Consumer(tm)
    service = _service(tm, consumer, controller=_Controller())
    owner = _owner(service)
    owner._begin_playback_confirmation(PAUSED)

    assert owner._reconcile_playback_epoch(None, owner.playback_epoch) is None
    assert owner.expected_playback_state == PAUSED


def test_visualizer_has_no_playback_confirm_debounce_constant():
    from widgets.spotify_visualizer import media_bridge

    assert not hasattr(media_bridge, "_PLAYBACK_PAUSE_CONFIRM_MS")
