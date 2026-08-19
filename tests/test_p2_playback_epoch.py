"""Task 2 - playback-state freshness ownership via a command/state epoch.

An accepted transport edge emits optimistic state immediately, but a GSMTC
refresh that STARTED before that command reflects pre-command reality. Applying
its stale playback state reverses the optimistic state, so the visualizer flaps
pause->play->pause from one pause command. The fix: each optimistic edge advances
a playback epoch; a refresh captures the epoch it began under; a stale
(pre-command) result cannot reverse the new state, while a refresh started after
the command may confirm or genuinely reverse it.
"""

from __future__ import annotations

import pytest

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_widget import MediaWidget

PLAYING = MediaPlaybackState.PLAYING
PAUSED = MediaPlaybackState.PAUSED


def _info(state, *, title="Song", artist="Artist"):
    return MediaTrackInfo(title=title, artist=artist, state=state, can_play_pause=True)


@pytest.fixture
def widget(qt_app):
    w = MediaWidget()
    yield w
    w.deleteLater()


class TestEpochAdvancesOnAcceptedEdge:
    def test_an_optimistic_edge_advances_the_epoch(self, widget):
        before = widget._playback_epoch
        widget._apply_pending_state_override(PAUSED)
        assert widget._playback_epoch == before + 1

    def test_the_optimistic_edge_invalidates_the_gsmtc_cache(self, widget):
        widget._gsmtc_cached_result = _info(PLAYING)
        widget._apply_pending_state_override(PAUSED)
        assert widget._gsmtc_cached_result is None


class TestStalePreCommandRefreshIsRejected:
    def test_pause_command_then_stale_playing_refresh_is_pinned_to_paused(self, widget):
        widget._last_info = _info(PLAYING)
        refresh_epoch = widget._playback_epoch  # query started while PLAYING

        # Command optimistically PAUSES.
        widget._last_info = _info(PAUSED)
        widget._apply_pending_state_override(PAUSED)

        # The stale PLAYING query returns.
        stale = _info(PLAYING)
        reconciled = widget._reconcile_refresh_playback_epoch(stale, refresh_epoch)

        assert reconciled.state == PAUSED, "a stale PLAYING refresh reversed the pause"
        # Non-state fields still flow from the refresh.
        assert reconciled.title == stale.title

    def test_play_command_then_stale_paused_refresh_is_pinned_to_playing(self, widget):
        widget._last_info = _info(PAUSED)
        refresh_epoch = widget._playback_epoch

        widget._last_info = _info(PLAYING)
        widget._apply_pending_state_override(PLAYING)

        stale = _info(PAUSED)
        reconciled = widget._reconcile_refresh_playback_epoch(stale, refresh_epoch)

        assert reconciled.state == PLAYING, "a stale PAUSED refresh reversed the play"

    def test_a_same_epoch_refresh_confirms(self, widget):
        widget._last_info = _info(PLAYING)
        widget._apply_pending_state_override(PAUSED)
        widget._last_info = _info(PAUSED)

        # A refresh started AFTER the command carries the current epoch.
        refresh_epoch = widget._playback_epoch
        authoritative = _info(PAUSED)
        reconciled = widget._reconcile_refresh_playback_epoch(authoritative, refresh_epoch)

        assert reconciled.state == PAUSED

    def test_a_genuinely_newer_state_may_reverse(self, widget):
        # User paused, but the media app itself resumed. A refresh started after
        # the command (same epoch) returning PLAYING is authoritative and reverses.
        widget._last_info = _info(PLAYING)
        widget._apply_pending_state_override(PAUSED)
        widget._last_info = _info(PAUSED)

        refresh_epoch = widget._playback_epoch  # after the command
        newer = _info(PLAYING)
        reconciled = widget._reconcile_refresh_playback_epoch(newer, refresh_epoch)

        assert reconciled.state == PLAYING, (
            "a genuinely newer authoritative state was wrongly pinned"
        )


class TestOnlyOnePlaybackEdgePerCommand:
    def test_stale_refresh_yields_no_contradictory_state(self, widget):
        # The visualizer/listener sees state only via the reconciled info, so a
        # stale refresh reconciled to the optimistic state cannot emit a second,
        # contradictory playback edge for one command.
        widget._last_info = _info(PLAYING)
        refresh_epoch = widget._playback_epoch
        widget._last_info = _info(PAUSED)
        widget._apply_pending_state_override(PAUSED)

        # Three stale results arriving out of order all reconcile to PAUSED.
        for stale_state in (PLAYING, PLAYING, PLAYING):
            reconciled = widget._reconcile_refresh_playback_epoch(
                _info(stale_state), refresh_epoch
            )
            assert reconciled.state == PAUSED

    def test_a_none_result_is_passed_through(self, widget):
        assert widget._reconcile_refresh_playback_epoch(None, 0) is None


class TestNoBlindDebounce:
    def test_no_playback_confirm_debounce_constant_returned(self):
        # The fix is an epoch, not a reintroduced timed debounce.
        from widgets.spotify_visualizer import media_bridge

        assert not hasattr(media_bridge, "_PLAYBACK_PAUSE_CONFIRM_MS")
