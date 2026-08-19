"""Gate 7 - Pause/Play preserves identity and cadence on the logical runtime.

`Docs/P2_Behavioral_Gates.md` Gate 7 / Current_Plan Slice E.

The old ~700ms visible-playback debounce is already removed (Slice/Section 6 of
the earlier round) and must not be reintroduced. `_SpotifyBeatEngine` keeps its
own independent 6s capture keepalive/warm-resume grace. This gate proves that
quick Pause/Play toggles, now running on the qualified logical runtime, do not
disturb runtime/mode/card identity and do not stop the cadence owner.

Per the plan: if a visible edge hitch remains after this gate is green, the next
step is auditing synchronous wake/source-handoff work from fresh installed
evidence - not something to speculate into existence here.
"""

from __future__ import annotations

import inspect

import pytest
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import media_bridge, tick_helpers


class _RealishThreadManager:
    def __init__(self):
        self.timers_created = 0

    def schedule_recurring(self, interval_ms, callback):
        self.timers_created += 1
        raise AssertionError("a GUI recurring timer was created")

    def run_on_ui_thread(self, func, *args, **kwargs):
        func(*args, **kwargs)


@pytest.fixture
def live_widget(qt_app, qtbot):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._thread_manager = _RealishThreadManager()
    widget._engine = None
    widget._spotify_playing = True
    tick_helpers.ensure_tick_source(widget)
    yield widget
    widget.cleanup()


class TestQuickPauseResumePreservesIdentity:
    def test_the_logical_runtime_identity_is_unchanged(self, live_widget):
        runtime = live_widget._logical_runtime

        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._logical_runtime is runtime, (
            "a pause/play edge replaced the logical runtime identity"
        )

    def test_the_runtime_generation_is_unchanged(self, live_widget):
        generation = live_widget._runtime_generation

        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._runtime_generation == generation

    def test_the_mode_activation_is_unchanged(self, live_widget):
        activation = live_widget._last_engine_activation_seen

        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._last_engine_activation_seen == activation, (
            "pausing/resuming advanced mode activation with no real mode change"
        )

    def test_cadence_continues_across_the_edge(self, live_widget):
        live_widget.handle_media_update({"state": "paused"})
        assert live_widget._logical_runtime.is_running() is True, (
            "pausing stopped the logical cadence owner"
        )

        live_widget.handle_media_update({"state": "playing"})
        assert live_widget._logical_runtime.is_running() is True

    def test_pause_is_immediate_not_debounced(self, live_widget):
        live_widget.handle_media_update({"state": "paused"})

        assert live_widget._spotify_playing is False
        assert getattr(live_widget, "_pending_playback_pause_timer", None) is None

    def test_repeated_quick_toggles_create_no_second_runtime(self, live_widget):
        runtime = live_widget._logical_runtime

        for _ in range(6):
            live_widget.handle_media_update({"state": "paused"})
            live_widget.handle_media_update({"state": "playing"})

        assert live_widget._logical_runtime is runtime

    def test_no_gui_recurring_timer_is_created_across_the_edge(self, live_widget):
        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._thread_manager.timers_created == 0
        assert live_widget._bars_timer is None


class TestNoVisibleStateDebounce:
    def test_the_debounce_constant_is_gone(self):
        assert not hasattr(media_bridge, "_PLAYBACK_PAUSE_CONFIRM_MS")

    def test_no_qt_timer_is_used_for_playback_state(self):
        source = inspect.getsource(media_bridge)
        assert "QTimer" not in source

    def test_capture_keepalive_remains_independent_engine_policy(self):
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine

        source = inspect.getsource(_SpotifyBeatEngine.__init__)
        assert "_capture_keepalive_grace" in source


class TestWarmResumeDoesNotColdStart:
    def test_resume_does_not_re_enter_staged_startup(self, live_widget):
        live_widget._startup_hot_start_started = True
        live_widget._startup_secondary_stage_pending = False

        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._startup_secondary_stage_pending is False, (
            "warm resume re-armed staged startup"
        )

    def test_resume_does_not_recreate_the_gl_overlay(self, live_widget):
        marker = object()
        live_widget._spotify_bars_overlay = marker

        live_widget.handle_media_update({"state": "paused"})
        live_widget.handle_media_update({"state": "playing"})

        assert live_widget._spotify_bars_overlay is marker
