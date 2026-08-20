"""Playback-state freshness and bounded command-confirmation ownership.

An accepted transport edge emits optimistic state immediately. A refresh that
started before that command is stale, while a new same-epoch refresh can still
briefly expose the backend's pre-command state. MediaWidget therefore owns one
bounded expected state: matching state confirms it, an early contradiction is
pinned without blocking metadata, and expiry restores backend authority.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_widget import MediaWidget


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


@pytest.fixture
def widget(qt_app):
    w = MediaWidget()
    yield w
    w.deleteLater()


class TestExpectedStateOwnership:
    def test_an_optimistic_edge_owns_expected_state_epoch_and_deadline(self, widget):
        before_epoch = widget._playback_epoch
        before_time = time.monotonic()

        widget._begin_playback_confirmation(PAUSED)

        assert widget._playback_epoch == before_epoch + 1
        assert widget._expected_playback_state == PAUSED
        assert widget._expected_playback_epoch == widget._playback_epoch
        assert widget._playback_confirmation_deadline_monotonic > before_time

    def test_the_optimistic_edge_invalidates_the_gsmtc_cache(self, widget):
        widget._gsmtc_cached_result = _info(PLAYING)

        widget._begin_playback_confirmation(PAUSED)

        assert widget._gsmtc_cached_result is None

    def test_confirmation_refresh_timer_does_not_erase_the_expectation(self, widget):
        refreshes = []
        widget._enabled = True
        widget._thread_manager = object()
        widget._refresh_async = lambda: refreshes.append("refresh")

        widget._begin_playback_confirmation(PAUSED)
        timer = widget._playback_confirmation_refresh_timer
        assert timer is not None

        timer.timeout.emit()
        timer.stop()

        assert refreshes == ["refresh"]
        assert widget._playback_confirmation_refresh_timer is None
        assert widget._expected_playback_state == PAUSED
        assert widget._expected_playback_epoch == widget._playback_epoch


@pytest.mark.parametrize("entrypoint", ("start", "_activate_impl"))
def test_runtime_entry_clears_an_expectation_created_while_disabled(widget, entrypoint):
    widget._begin_playback_confirmation(PAUSED)
    widget._thread_manager = object()
    widget._ensure_thread_manager = lambda _owner: True
    widget._refresh = lambda: None
    widget._ensure_timer = lambda *args, **kwargs: None
    widget._refresh_async = lambda: None

    getattr(widget, entrypoint)()

    assert widget._expected_playback_state is None
    assert widget._expected_playback_epoch is None
    assert widget._playback_confirmation_deadline_monotonic == 0.0


def test_provider_switch_clears_the_previous_provider_expectation(widget, monkeypatch):
    controller = SimpleNamespace(set_thread_manager=lambda _manager: None)
    monkeypatch.setattr(
        "widgets.media_widget.create_media_controller",
        lambda **_kwargs: controller,
    )
    widget._begin_playback_confirmation(PAUSED)

    changed = widget.set_provider_runtime("musicbee")

    assert changed is True
    assert widget._expected_playback_state is None
    assert widget._expected_playback_epoch is None
    assert widget._playback_confirmation_deadline_monotonic == 0.0


def test_async_refresh_result_cannot_publish_after_stop(widget, monkeypatch):
    from core.threading.manager import ThreadManager

    jobs = []
    displayed = []
    info = _info(PLAYING)

    class _HoldingThreadManager:
        def submit_io_task(self, worker, callback):
            jobs.append((worker, callback))

    class _Controller:
        def get_current_track(self):
            return info

    class _TaskResult:
        success = True

        def __init__(self, result):
            self.result = result

    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    widget._thread_manager = _HoldingThreadManager()
    widget._controller = _Controller()
    widget._enabled = True
    widget._update_display = lambda *args: displayed.append(args)

    widget._refresh_async()
    worker, callback = jobs.pop()
    widget.stop()
    callback(_TaskResult(worker()))

    assert displayed == []
    assert widget._refresh_in_flight is False


def test_stop_then_start_cannot_replay_a_retired_cached_snapshot(widget):
    jobs = []
    displayed = []

    class _HoldingThreadManager:
        def submit_io_task(self, worker, callback):
            jobs.append((worker, callback))

    widget._thread_manager = _HoldingThreadManager()
    widget._controller = SimpleNamespace(get_current_track=lambda: _info(PAUSED))
    widget._enabled = True
    widget._ensure_thread_manager = lambda _owner: True
    widget._ensure_timer = lambda: None
    widget._update_display = lambda *args: displayed.append(args)
    widget._gsmtc_cached_result = _info(PLAYING, title="Retired cache")
    widget._gsmtc_cached_prepared_artwork = object()
    widget._gsmtc_cached_artwork_generation = widget._artwork_update_generation
    widget._gsmtc_cache_ts = time.time()

    widget.stop()
    widget.start()

    assert displayed == []
    assert len(jobs) == 1
    assert widget._gsmtc_cached_result is None
    assert widget._gsmtc_cached_prepared_artwork is None
    assert widget._gsmtc_cached_artwork_generation == 0
    assert widget._gsmtc_cache_ts == 0.0


def test_old_refresh_cannot_publish_or_clear_new_work_after_stop_and_restart(
    widget,
    monkeypatch,
):
    from core.threading.manager import ThreadManager

    jobs = []
    displayed = []
    results = [_info(PLAYING, title="Old runtime"), _info(PAUSED, title="New runtime")]

    class _HoldingThreadManager:
        def submit_io_task(self, worker, callback):
            jobs.append((worker, callback))

    class _Controller:
        def get_current_track(self):
            return results.pop(0)

    class _TaskResult:
        success = True

        def __init__(self, result):
            self.result = result

    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback: callback()),
    )
    widget._thread_manager = _HoldingThreadManager()
    widget._controller = _Controller()
    widget._enabled = True
    widget._ensure_thread_manager = lambda _owner: True
    widget._ensure_timer = lambda: None
    widget._update_display = lambda *args: displayed.append(args)

    widget._refresh_async()
    old_worker, old_callback = jobs.pop(0)
    old_result = _TaskResult(old_worker())

    widget.stop()
    widget.start()
    new_worker, new_callback = jobs.pop(0)

    old_callback(old_result)

    assert displayed == []
    assert widget._refresh_in_flight is True

    new_callback(_TaskResult(new_worker()))

    assert [args[0].title for args in displayed] == ["New runtime"]
    assert widget._refresh_in_flight is False


@pytest.mark.parametrize(
    ("initial_state", "expected_state", "stale_state"),
    (
        (PLAYING, PAUSED, PLAYING),
        (PAUSED, PLAYING, PAUSED),
    ),
)
def test_stale_pre_command_refresh_is_pinned_in_both_directions(
    widget,
    initial_state,
    expected_state,
    stale_state,
):
    widget._last_info = _info(initial_state)
    refresh_epoch = widget._playback_epoch
    widget._last_info = _info(expected_state)
    widget._begin_playback_confirmation(expected_state)

    stale = _info(stale_state, title="Fresh metadata", artist="New Artist")
    reconciled = widget._reconcile_refresh_playback_epoch(stale, refresh_epoch)

    assert reconciled.state == expected_state
    assert reconciled.title == "Fresh metadata"
    assert reconciled.artist == "New Artist"
    assert widget._expected_playback_state == expected_state


def test_an_older_refresh_cannot_confirm_the_current_expectation(widget):
    refresh_epoch = widget._playback_epoch
    widget._last_info = _info(PAUSED)
    widget._begin_playback_confirmation(PAUSED)

    reconciled = widget._reconcile_refresh_playback_epoch(
        _info(PAUSED),
        refresh_epoch,
    )

    assert reconciled.state == PAUSED
    assert widget._expected_playback_state == PAUSED


def test_an_older_result_from_the_first_of_two_commands_cannot_reverse_the_second(widget):
    first_refresh_epoch = widget._playback_epoch
    widget._last_info = _info(PAUSED)
    widget._begin_playback_confirmation(PAUSED)
    widget._last_info = _info(PLAYING)
    widget._begin_playback_confirmation(PLAYING)
    latest_epoch = widget._playback_epoch

    reconciled = widget._reconcile_refresh_playback_epoch(
        _info(PAUSED, title="Metadata after two commands"),
        first_refresh_epoch,
    )

    assert reconciled.state == PLAYING
    assert reconciled.title == "Metadata after two commands"
    assert widget._expected_playback_state == PLAYING
    assert widget._expected_playback_epoch == latest_epoch


@pytest.mark.parametrize("expected_state", (PAUSED, PLAYING))
def test_matching_same_epoch_refresh_confirms_and_clears(widget, expected_state):
    widget._last_info = _info(expected_state)
    widget._begin_playback_confirmation(expected_state)
    refresh_epoch = widget._playback_epoch

    reconciled = widget._reconcile_refresh_playback_epoch(
        _info(expected_state),
        refresh_epoch,
    )

    assert reconciled.state == expected_state
    assert widget._expected_playback_state is None
    assert widget._expected_playback_epoch is None
    assert widget._playback_confirmation_deadline_monotonic == 0.0


@pytest.mark.parametrize(
    ("expected_state", "contradictory_state"),
    (
        (PAUSED, PLAYING),
        (PLAYING, PAUSED),
    ),
)
def test_same_epoch_contradiction_is_pinned_before_deadline_with_metadata_flow(
    widget,
    expected_state,
    contradictory_state,
):
    widget._last_info = _info(expected_state)
    widget._begin_playback_confirmation(expected_state)
    refresh_epoch = widget._playback_epoch
    contradiction = _info(
        contradictory_state,
        title="Backend metadata",
        artist="Backend artist",
    )

    reconciled = widget._reconcile_refresh_playback_epoch(
        contradiction,
        refresh_epoch,
    )

    assert reconciled.state == expected_state
    assert reconciled.title == contradiction.title
    assert reconciled.artist == contradiction.artist
    assert widget._expected_playback_state == expected_state


@pytest.mark.parametrize(
    ("expected_state", "contradictory_state"),
    (
        (PAUSED, PLAYING),
        (PLAYING, PAUSED),
    ),
)
def test_same_epoch_contradiction_becomes_authoritative_after_expiry(
    widget,
    expected_state,
    contradictory_state,
):
    widget._last_info = _info(expected_state)
    widget._begin_playback_confirmation(expected_state)
    refresh_epoch = widget._playback_epoch
    widget._playback_confirmation_deadline_monotonic = time.monotonic() - 1.0

    reconciled = widget._reconcile_refresh_playback_epoch(
        _info(contradictory_state),
        refresh_epoch,
    )

    assert reconciled.state == contradictory_state
    assert widget._expected_playback_state is None
    assert widget._expected_playback_epoch is None
    assert widget._playback_confirmation_deadline_monotonic == 0.0


@pytest.mark.parametrize(
    ("initial_state", "expected_state", "contradictory_state"),
    (
        (PLAYING, PAUSED, PLAYING),
        (PAUSED, PLAYING, PAUSED),
    ),
)
def test_one_transport_edge_reaches_listener_until_later_authority(
    widget,
    initial_state,
    expected_state,
    contradictory_state,
):
    from widgets.spotify_visualizer import media_bridge

    emitted = []
    visualizer_edges = []
    visualizer = SimpleNamespace(
        _spotify_playing=initial_state == PLAYING,
        _last_committed_playback_state=initial_state.value,
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

    widget.media_updated.connect(_listener)
    widget._enabled = False
    widget._show_controls = False
    widget._controller = SimpleNamespace(play_pause=lambda: None)
    widget._handle_control_feedback = lambda *args, **kwargs: None
    widget._last_info = _info(initial_state, title="Original")
    widget._last_track_identity = widget._compute_track_identity(widget._last_info)
    widget._last_metadata_identity = widget._compute_metadata_identity(widget._last_info)
    widget._has_seen_first_track = True
    widget._fixed_card_height = 220
    widget._fade_in_completed = True
    widget.isVisible = lambda: True

    widget.play_pause()

    assert widget._last_info.state == expected_state
    assert visualizer_edges == [expected_state == PLAYING]
    refresh_epoch = widget._playback_epoch

    contradiction = _info(
        contradictory_state,
        title="New title from backend",
        artist="New artist from backend",
    )
    pinned = widget._reconcile_refresh_playback_epoch(contradiction, refresh_epoch)
    widget._update_display(pinned)

    assert emitted[-1]["title"] == contradiction.title
    assert emitted[-1]["artist"] == contradiction.artist
    assert emitted[-1]["state"] == expected_state.value
    assert visualizer_edges == [expected_state == PLAYING]

    widget._playback_confirmation_deadline_monotonic = time.monotonic() - 1.0
    authoritative = widget._reconcile_refresh_playback_epoch(
        contradiction,
        refresh_epoch,
    )
    widget._update_display(authoritative)

    assert visualizer_edges == [
        expected_state == PLAYING,
        contradictory_state == PLAYING,
    ]


def test_a_none_result_is_passed_through_without_releasing_expectation(widget):
    widget._begin_playback_confirmation(PAUSED)

    assert widget._reconcile_refresh_playback_epoch(None, widget._playback_epoch) is None
    assert widget._expected_playback_state == PAUSED


def test_visualizer_has_no_playback_confirm_debounce_constant():
    from widgets.spotify_visualizer import media_bridge

    assert not hasattr(media_bridge, "_PLAYBACK_PAUSE_CONFIRM_MS")
