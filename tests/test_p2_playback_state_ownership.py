"""Visible playback state must not wait on a debounce timer.

Current_Plan section 6. `media_bridge` held `_PLAYBACK_PAUSE_CONFIRM_MS = 700`
and armed a Qt timer on every paused/stopped update while playing. Any wobbling
update re-armed it, so the nominal 700 ms became many seconds of visible limbo:

    deferred pause at 13:15:14, :16, :17, :19, :23
    engine finally non-playing at 13:15:24

That is the operator's worst edge - pause/resume far worse than ordinary mode
switching.

The debounce was never needed to protect capture. `SpotifyBeatEngine` already
holds `_capture_keepalive_grace = 6.0s` and warm-resumes inside that window, so
the two concerns are separable:

    logical/presentation playback target -> prompt, from trusted media state
    capture/service lifetime             -> engine policy, bounded grace

No replacement timer was introduced.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import media_bridge


class _Engine:
    def __init__(self):
        self.states: list[bool] = []

    def set_playback_state(self, playing):
        self.states.append(bool(playing))


@pytest.fixture
def vis(qt_app):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    widget = SpotifyVisualizerWidget(parent=None, bar_count=10)
    widget._engine = _Engine()
    widget._spotify_playing = True
    yield widget
    widget.deleteLater()


class TestPauseIsPrompt:
    def test_a_paused_update_enters_idle_immediately(self, vis):
        vis.handle_media_update({"state": "paused"})

        assert vis._spotify_playing is False, (
            "the visualizer still defers its visible playback state"
        )

    def test_a_stopped_update_enters_idle_immediately(self, vis):
        vis.handle_media_update({"state": "stopped"})

        assert vis._spotify_playing is False

    def test_the_engine_is_told_at_once(self, vis):
        vis.handle_media_update({"state": "paused"})

        assert vis._engine.states == [False], (
            "the engine's own keepalive cannot start until it is told"
        )

    def test_no_pending_pause_timer_is_armed(self, vis):
        vis.handle_media_update({"state": "paused"})

        assert getattr(vis, "_pending_playback_pause_timer", None) is None

    def test_resume_is_prompt_too(self, vis):
        vis.handle_media_update({"state": "paused"})
        vis.handle_media_update({"state": "playing"})

        assert vis._spotify_playing is True
        assert vis._engine.states == [False, True]

    def test_a_wobbling_provider_cannot_extend_visible_limbo(self, vis):
        """The installed failure: repeats used to re-arm the confirm timer."""
        for _ in range(6):
            vis.handle_media_update({"state": "paused"})

        assert vis._spotify_playing is False
        assert vis._engine.states == [False], (
            "repeated paused snapshots re-notified the engine"
        )

    def test_repeated_playing_updates_are_idempotent(self, vis):
        for _ in range(4):
            vis.handle_media_update({"state": "playing"})

        assert vis._spotify_playing is True
        assert vis._engine.states == []


class TestNoTimerSurvives:
    def test_the_confirm_constant_is_gone(self):
        assert not hasattr(media_bridge, "_PLAYBACK_PAUSE_CONFIRM_MS"), (
            "the visible playback debounce constant is back"
        )

    def test_the_scheduler_is_gone(self):
        assert not hasattr(media_bridge, "_schedule_nonplaying_commit")

    def test_media_bridge_owns_no_qt_timer_at_all(self):
        source = inspect.getsource(media_bridge)
        assert "QTimer" not in source, (
            "section 6 forbids replacing the debounce with another timer"
        )

    def test_clear_pending_playback_pause_remains_for_lifecycle_owners(self):
        """Engine acquire/release and edit suspend/resume still call it."""
        assert callable(media_bridge.clear_pending_playback_pause)
        widget = SimpleNamespace(_pending_playback_pause_timer=None)
        media_bridge.clear_pending_playback_pause(widget)


class TestCaptureKeepaliveIsTheRealAntiChurnOwner:
    def test_the_engine_still_holds_capture_warm(self):
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        source = inspect.getsource(_SpotifyBeatEngine.__init__)
        assert "_capture_keepalive_grace" in source, (
            "the visualizer dropped its debounce on the understanding that the "
            "engine keeps capture warm; that policy must still exist"
        )

    def test_the_grace_is_long_enough_to_cover_short_wobble(self):
        from widgets.spotify_visualizer import beat_engine

        source = inspect.getsource(beat_engine._SpotifyBeatEngine.__init__)
        assert "_capture_keepalive_grace: float = 6.0" in source
