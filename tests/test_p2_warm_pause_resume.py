"""P2: ordinary play/pause must not tear the visualizer down.

The dual-display run showed visualizer tick spikes around 42.9/45.2/49.3 ms
across a playback pause. Ordinary playback transitions are not a lifecycle
boundary: the compositor generation, its visualizer GL programs, the card
texture and a warm audio capture must all survive them.

The 6-second warm-capture grace after pause is deliberate and is preserved.
"""

from __future__ import annotations

import inspect

import pytest

from widgets.spotify_visualizer import media_bridge
from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine


@pytest.fixture
def engine(qt_app):
    instance = _SpotifyBeatEngine(24)
    yield instance
    instance.deleteLater()


class TestPauseDoesNotCrossALifecycleBoundary:
    def test_pause_does_not_advance_the_engine_generation(self, engine):
        engine.set_playback_state(True)
        before = (engine.get_generation_id(), engine.get_activation_id())
        engine.set_playback_state(False)
        assert (engine.get_generation_id(), engine.get_activation_id()) == before

    def test_resume_does_not_advance_the_engine_generation(self, engine):
        engine.set_playback_state(True)
        engine.set_playback_state(False)
        before = (engine.get_generation_id(), engine.get_activation_id())
        engine.set_playback_state(True)
        assert (engine.get_generation_id(), engine.get_activation_id()) == before

    def test_pause_keeps_capture_warm_for_the_authored_grace(self, engine):
        engine._ref_count = 1
        engine.set_playback_state(True)
        engine.set_playback_state(False)
        assert engine._capture_keepalive_grace == pytest.approx(6.0)
        assert engine._capture_keepalive_deadline > 0.0, (
            "pause must schedule the warm grace, not stop capture immediately"
        )

    def test_resume_inside_the_grace_keeps_the_existing_capture(self, engine):
        engine._ref_count = 1
        engine.set_playback_state(True)
        engine.set_playback_state(False)
        assert engine._capture_keepalive_deadline > 0.0
        engine.set_playback_state(True)
        assert engine._capture_keepalive_deadline == 0.0, (
            "a warm resume must adopt the still-running capture"
        )

    def test_a_warm_resume_does_not_re_enter_the_cold_reactivity_ramp(self, engine):
        engine._ref_count = 1
        engine.set_playback_state(True)
        engine.set_playback_state(False)
        engine.set_playback_state(True)
        assert engine._play_ramp_start_ts == 0.0

    def test_a_cold_resume_arms_the_authored_ramp_once(self, engine):
        engine._ref_count = 1
        engine._capture_keepalive_deadline = 0.0
        engine.set_playback_state(True)
        assert engine._play_ramp_start_ts > 0.0


class TestPlaybackTransitionsDoNotTouchGL:
    def test_playback_state_never_destroys_gl(self):
        source = inspect.getsource(_SpotifyBeatEngine.set_playback_state)
        for forbidden in ("cleanup_gl", "_clear_gl_overlay", "_destroy_parent_overlay"):
            assert forbidden not in source

    def test_clearing_overlay_runtime_preserves_gl_resources(self):
        """Hiding is a presentation-state change, never a resource teardown."""
        source = inspect.getsource(media_bridge.clear_parent_overlay_runtime)
        assert "cleanup_gl" not in source
        assert "without destroying the GL object" in source

    def test_absent_anchor_fades_through_the_one_authority(self):
        source = inspect.getsource(media_bridge._fade_out_for_absent_anchor)
        assert "ensure_presentation_fade" in source
        assert "_start_widget_fade_out" in source
        for forbidden in ("cleanup_gl", "_destroy_parent_overlay"):
            assert forbidden not in source

    def test_a_running_hide_is_not_restarted_by_repeated_sync(self, qt_app):
        from widgets.spotify_visualizer.presentation_fade import (
            VisualizerPresentationFade,
        )

        calls: list = []

        class _Widget:
            def __init__(self):
                self._presentation_fade = VisualizerPresentationFade()
                self._presentation_fade.jump_to(1.0)

            def _start_widget_fade_out(self, on_complete=None):
                calls.append(on_complete)
                self._presentation_fade.begin_fade_out(
                    duration_ms=1200, on_finished=on_complete
                )

            def hide(self):
                pass

            def _clear_gl_overlay(self):
                pass

        widget = _Widget()
        media_bridge._fade_out_for_absent_anchor(widget)
        media_bridge._fade_out_for_absent_anchor(widget)
        media_bridge._fade_out_for_absent_anchor(widget)
        assert len(calls) == 1, "the hide animation was restarted mid-flight"

    def test_an_already_invisible_scene_releases_without_animating(self, qt_app):
        from widgets.spotify_visualizer.presentation_fade import (
            VisualizerPresentationFade,
        )

        released: list[str] = []

        class _Widget:
            _presentation_fade = None

            def __init__(self):
                self._presentation_fade = VisualizerPresentationFade()

            def _start_widget_fade_out(self, on_complete=None):
                raise AssertionError("nothing visible to fade")

            def hide(self):
                released.append("hide")

            def _clear_gl_overlay(self):
                released.append("clear")

        media_bridge._fade_out_for_absent_anchor(_Widget())
        assert released == ["hide", "clear"]
