"""Gate 1 - paused Spectrum must actually become visible.

`Docs/P2_Behavioral_Gates.md` Gate 1. The previous Spectrum test asserted that
`resolve_widget_spectrum_presentation()` had been called. That is exactly the
class of gate that let a broken product pass: the resolver ran, produced a
correct idle baseline, and the frame was still published with fade forced to
zero, so the operator saw nothing until Play.

The blocker was `_collect_first_frame_primer_problems()`. Spectrum requires
authoritative source for reactive playback, so with no source generation or
activation it reported `display_source_generation_missing` /
`display_source_activation_missing`. Those became `primer_problems`, and:

    effective_fade      = 0.0 if primer_problems else scene_fade
    effective_bars_fade = 0.0 if primer_problems else bars_fade
    ... if not primer_problems: _has_pushed_first_frame = True
                                _on_first_frame_after_cold_start()

so the card never faded in and the first-frame handoff never completed.

These bars assert what the operator sees: a real widget pushes a real Spectrum
frame carrying the non-zero baseline, with non-zero fade, and completes the
reveal handoff - while source authority stays locked for future Play.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import tick_pipeline
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
    _IDLE_BASELINE_MAX,
)


class _OverlayStub:
    _vis_mode = "spectrum"
    _activation_id = None
    _engine_generation = None
    _pending_mode_resets: set = set()


class _RecordingParent(QWidget):
    """A display parent that records exactly what the compositor would receive."""

    def __init__(self) -> None:
        super().__init__()
        self._spotify_bars_overlay = _OverlayStub()
        self.frames: list[dict] = []

    def push_spotify_visualizer_frame(self, **kwargs):
        self.frames.append(dict(kwargs))
        return True


def _paused_spectrum(qtbot, *, bar_count=16):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = _RecordingParent()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=bar_count)
    qtbot.addWidget(widget)

    widget._enabled = True
    widget.set_visualization_mode(VisualizerMode.SPECTRUM)
    widget._spotify_playing = False
    # Exactly the paused state: a target generation whose engine frame cannot
    # arrive while capture is stopped, and no source identity at all.
    widget._waiting_for_fresh_engine_frame = True
    widget._pending_engine_generation = 10**9
    widget._display_bars = [0.0] * bar_count
    widget._display_bars_source_generation = -1
    widget._display_bars_source_activation = -1
    widget._has_pushed_first_frame = False
    # The defect under test is the primer *overriding* the fade authority, so
    # the authority is pinned fully open. A zero published fade then means the
    # primer forced it, not that a reveal animation had not started yet.
    widget._get_scene_fade_factor = lambda _now: 1.0
    widget._get_gpu_fade_factor = lambda _now: 1.0
    widget._mode_transition_fade_factor = lambda _now: 1.0
    # No engine: paused capture supplies nothing, which is the real state and
    # keeps `_display_bars` under the test's control.
    widget._engine = None
    return widget, parent


def _spectrum_frames(parent):
    return [f for f in parent.frames if f.get("vis_mode") == "spectrum"]


class TestPausedSpectrumIsVisible:
    def test_the_parent_receives_a_spectrum_frame(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert _spectrum_frames(parent), (
            "paused Spectrum never reached the compositor at all"
        )

    def test_the_frame_carries_the_non_zero_idle_baseline(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        bars = list(_spectrum_frames(parent)[-1]["bars"])
        assert max(bars) > 0.0, "the published Spectrum scene was empty"
        assert max(bars) <= _IDLE_BASELINE_MAX + 1e-6, (
            "the idle scene is louder than the authored resting baseline"
        )

    def test_the_scene_fade_is_not_forced_to_zero(self, qt_app, qtbot):
        """The exact defect: a correct scene published invisibly."""
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        frame = _spectrum_frames(parent)[-1]
        assert float(frame["fade"]) > 0.0, (
            "the first-frame primer forced scene fade to zero for a "
            "presentation-owned idle scene"
        )

    def test_the_bars_fade_is_not_forced_to_zero(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        frame = _spectrum_frames(parent)[-1]
        assert float(frame["bars_fade"]) > 0.0

    def test_the_first_frame_handoff_completes(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert widget._has_pushed_first_frame is True, (
            "the reveal handoff never completed, so the reveal watchdog would "
            "expire with the card still hidden"
        )

    def test_the_frame_reports_not_playing(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert _spectrum_frames(parent)[-1]["playing"] is False


class TestSourceAuthorityStaysLocked:
    def test_the_fresh_source_wait_is_retained(self, qt_app, qtbot):
        widget, _parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert widget._waiting_for_fresh_engine_frame is True, (
            "making the idle scene visible also granted reactive source authority"
        )

    def test_no_source_identity_is_fabricated(self, qt_app, qtbot):
        widget, _parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert widget._display_bars_source_generation == -1
        assert widget._display_bars_source_activation == -1

    def test_the_pending_generation_is_untouched(self, qt_app, qtbot):
        widget, _parent = _paused_spectrum(qtbot)

        widget._on_tick()

        assert widget._pending_engine_generation == 10**9

    def test_a_playing_spectrum_without_source_still_blocks(self, qt_app, qtbot):
        """The guard must keep working where it is genuinely right."""
        widget, parent = _paused_spectrum(qtbot)
        widget._spotify_playing = True

        widget._on_tick()

        frames = _spectrum_frames(parent)
        if frames:
            assert float(frames[-1]["fade"]) == 0.0, (
                "a playing Spectrum with no source identity was revealed"
            )
        assert widget._has_pushed_first_frame is False


class TestOtherModesAreUnaffected:
    @pytest.mark.parametrize(
        "mode,name",
        [
            (VisualizerMode.BUBBLE, "bubble"),
            (VisualizerMode.SINE_WAVE, "sine_wave"),
            (VisualizerMode.OSCILLOSCOPE, "oscilloscope"),
        ],
    )
    def test_self_animating_modes_are_not_presentation_owned(self, mode, name):
        assert tick_pipeline.presentation_owned_idle_is_active(
            SimpleNamespace(_vis_mode_str=name, _spotify_playing=False)
        ) is False

    def test_spectrum_only_qualifies_while_paused(self):
        playing = SimpleNamespace(_vis_mode_str="spectrum", _spotify_playing=True)
        paused = SimpleNamespace(_vis_mode_str="spectrum", _spotify_playing=False)

        assert tick_pipeline.presentation_owned_idle_is_active(playing) is False
        assert tick_pipeline.presentation_owned_idle_is_active(paused) is True


class TestPlayReplacesIdleInPlace:
    def test_real_bars_take_over_without_a_blank(self, qt_app, qtbot):
        widget, parent = _paused_spectrum(qtbot)
        widget._on_tick()
        idle_bars = list(_spectrum_frames(parent)[-1]["bars"])
        assert max(idle_bars) > 0.0

        # Play arrives with a genuine current-generation source frame.
        widget._spotify_playing = True
        widget._waiting_for_fresh_engine_frame = False
        widget._display_bars = [0.85] * len(idle_bars)
        widget._spectrum_visual_smoothing_enabled = False
        widget._display_bars_source_generation = 11
        widget._display_bars_source_activation = 4
        parent._spotify_bars_overlay._engine_generation = 11
        parent._spotify_bars_overlay._activation_id = 4

        widget._on_tick()

        live = _spectrum_frames(parent)[-1]
        assert max(live["bars"]) > _IDLE_BASELINE_MAX, (
            "real Spectrum bars never replaced the idle baseline"
        )
        assert len(live["bars"]) == len(idle_bars), "the bar layout was recreated"
        assert float(live["fade"]) > 0.0, "the card blanked while taking over"
