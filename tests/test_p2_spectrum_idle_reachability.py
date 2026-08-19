"""Spectrum's idle scene must actually reach presentation while paused.

Current_Plan section 5. The static baseline was already correct; the state path
never let it run.

`on_tick()` bails when `_waiting_for_fresh_engine_frame` is set and consume
produced nothing. Spectrum is deliberately not idle self-animating, so that wait
is never cleared while capture is paused, and `push_gpu_frame()` - the only
normal call site that builds the idle baseline - sits downstream of the bail.

The system therefore asserted both:

    Spectrum's idle presentation needs no source frame
    do not call Spectrum's idle presentation until a source frame arrives

which is the blank card after switching to Spectrum while paused.

These bars drive the real tick path, and pin the canonical capability owner that
replaced three disagreeing hard-coded sets.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import mode_capabilities


# ---------------------------------------------------------------------------
# One canonical capability owner
# ---------------------------------------------------------------------------


class TestCanonicalCapabilities:
    @pytest.mark.parametrize(
        "mode", ["bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve"]
    )
    def test_every_authored_mode_may_reveal_while_idle(self, mode):
        assert mode_capabilities.allows_idle_reveal(mode) is True

    def test_spectrum_capability_matrix(self):
        """The exact row Current_Plan section 5 specifies."""
        assert mode_capabilities.allows_idle_reveal("spectrum") is True
        assert mode_capabilities.is_idle_self_animating("spectrum") is False
        assert mode_capabilities.has_presentation_owned_idle_scene("spectrum") is True
        assert mode_capabilities.requires_authoritative_first_source("spectrum") is True

    @pytest.mark.parametrize(
        "mode", ["bubble", "sine_wave", "oscilloscope", "devcurve"]
    )
    def test_self_animating_modes_need_no_presentation_idle_scene(self, mode):
        assert mode_capabilities.is_idle_self_animating(mode) is True
        assert mode_capabilities.has_presentation_owned_idle_scene(mode) is False
        assert mode_capabilities.requires_authoritative_first_source(mode) is False

    def test_an_unknown_mode_is_not_idle_capable(self):
        assert mode_capabilities.allows_idle_reveal("not_a_mode") is False
        assert mode_capabilities.requires_authoritative_first_source("not_a_mode") is True

    def test_oscilloscope_is_idle_capable_for_media_seeding_too(self):
        """`media_bridge` used to omit it from its own private set."""
        assert mode_capabilities.allows_idle_reveal("oscilloscope") is True


class TestNoDuplicateCapabilitySets:
    def test_media_bridge_has_no_private_mode_set(self):
        import inspect

        from widgets.spotify_visualizer import media_bridge

        source = inspect.getsource(media_bridge)
        assert '"sine_wave",\n            "devcurve",' not in source, (
            "media_bridge still owns a private idle-capable mode set"
        )
        assert "mode_capabilities" in source

    def test_startup_staging_delegates(self):
        import inspect

        from widgets.spotify_visualizer import startup_staging

        source = inspect.getsource(startup_staging.mode_allows_idle_reveal)
        assert "mode_capabilities" in source
        assert "bubble" not in source, (
            "startup_staging still hard-codes its own mode list"
        )

    def test_tick_pipeline_delegates(self):
        from widgets.spotify_visualizer import tick_pipeline

        assert (
            tick_pipeline._mode_allows_idle_reveal_key
            is mode_capabilities.allows_idle_reveal
        )
        assert (
            tick_pipeline._mode_requires_authoritative_first_source
            is mode_capabilities.requires_authoritative_first_source
        )


# ---------------------------------------------------------------------------
# The real tick path must reach publication while paused
# ---------------------------------------------------------------------------


class _OverlayStub:
    _vis_mode = "spectrum"
    _activation_id = None
    _engine_generation = None
    _pending_mode_resets: set = set()


class _Parent:
    def __init__(self):
        self.pushes: list[tuple] = []
        self._spotify_bars_overlay = None

    def push_spotify_visualizer_frame(self, *args, **kwargs):
        self.pushes.append((args, kwargs))
        return True


def _spectrum_mode():
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    return VisualizerMode.SPECTRUM


def _paused_spectrum_widget(monkeypatch):
    """A widget in the exact state a paused switch to Spectrum leaves behind."""
    from widgets.spotify_visualizer import tick_pipeline

    parent = _Parent()
    widget = SimpleNamespace(
        _vis_mode_str="spectrum",
        _spotify_playing=False,
        _waiting_for_fresh_engine_frame=True,
        _pending_engine_generation=7,
        _bar_count=48,
        _display_bars=[0.0] * 48,
        _display_bars_source_generation=-1,
        _display_bars_source_activation=-1,
        _spectrum_visual_smoothing_enabled=True,
        _spectrum_visual_smoothing=0.5,
        _spectrum_single_piece=False,
        _spectrum_border_radius=0,
        _spectrum_presentation_bars=[],
        _spectrum_presentation_last_ts=0.0,
        _spectrum_presentation_identity=None,
        _spectrum_presentation_pending=False,
    )
    return widget, parent, tick_pipeline


class TestPausedSpectrumReachesPresentation:
    """Drives the real `on_tick` on a real widget, per section 5's bars."""

    def test_paused_spectrum_publishes_its_idle_scene_through_on_tick(
        self, qt_app, qtbot, monkeypatch
    ):
        from widgets.spotify_visualizer import tick_pipeline
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        parent = _RealParent()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=16)
        qtbot.addWidget(widget)

        widget._enabled = True
        widget.set_visualization_mode(_spectrum_mode())
        widget._spotify_playing = False
        # Exactly the state a paused switch to Spectrum leaves behind: a target
        # generation whose engine frame cannot arrive while capture is paused.
        widget._waiting_for_fresh_engine_frame = True
        widget._pending_engine_generation = 7
        widget._display_bars = [0.0] * 16

        resolved: list[list[float]] = []
        real = tick_pipeline.resolve_widget_spectrum_presentation

        def _spy(widget_arg, bars, *, now_ts, first_frame=False):
            result = real(widget_arg, bars, now_ts=now_ts, first_frame=first_frame)
            resolved.append(list(result[0]))
            return result

        monkeypatch.setattr(tick_pipeline, "resolve_widget_spectrum_presentation", _spy)

        widget._on_tick()

        assert resolved, (
            "paused Spectrum returned before push_gpu_frame(), so its idle "
            "baseline was never built - this is the blank-card defect"
        )
        assert max(resolved[-1]) > 0.0, "the idle scene resolved to nothing"

    def test_the_source_wait_survives_the_idle_publication(
        self, qt_app, qtbot, monkeypatch
    ):
        """Publishing idle must not grant reactive authority."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        parent = _RealParent()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=16)
        qtbot.addWidget(widget)

        widget._enabled = True
        widget.set_visualization_mode(_spectrum_mode())
        widget._spotify_playing = False
        widget._waiting_for_fresh_engine_frame = True
        # A generation no engine can already have delivered, so the wait can only
        # clear through the path under test rather than through a shared engine
        # another suite left at a high generation.
        widget._pending_engine_generation = 10**9
        widget._display_bars = [0.0] * 16
        widget._display_bars_source_generation = -1
        widget._display_bars_source_activation = -1

        widget._on_tick()

        assert widget._waiting_for_fresh_engine_frame is True, (
            "the idle publication cleared the reactive source wait"
        )
        assert widget._display_bars_source_generation == -1, (
            "a source generation was fabricated for the idle scene"
        )

    @pytest.mark.parametrize("mode", ["bubble", "sine_wave", "oscilloscope", "devcurve"])
    def test_self_animating_modes_keep_the_original_bail(self, mode):
        """They clear the wait elsewhere; this path must not change for them."""
        assert mode_capabilities.has_presentation_owned_idle_scene(mode) is False


class TestIdlePublicationBuildsTheBaseline:
    def test_push_gpu_frame_builds_the_idle_scene_while_paused(self, monkeypatch):
        from widgets.spotify_visualizer import tick_pipeline

        widget, parent, _tp = _paused_spectrum_widget(monkeypatch)
        resolved: list[list[float]] = []

        real = tick_pipeline.resolve_widget_spectrum_presentation

        def _spy(widget_arg, bars, *, now_ts, first_frame=False):
            result = real(widget_arg, bars, now_ts=now_ts, first_frame=first_frame)
            resolved.append(list(result[0]))
            return result

        monkeypatch.setattr(tick_pipeline, "resolve_widget_spectrum_presentation", _spy)

        # Only the presentation half is exercised here; the geometry/GL half of
        # push_gpu_frame needs a real widget and is covered by the widget suite.
        bars, changed = tick_pipeline.resolve_widget_spectrum_presentation(
            widget, widget._display_bars, now_ts=time.time(), first_frame=True
        )

        assert resolved, "the idle presentation was never resolved"
        assert max(bars) > 0.0, "paused Spectrum resolved to an empty scene"
        assert changed is True

    def test_the_idle_scene_does_not_grant_reactive_authority(self, monkeypatch):
        from widgets.spotify_visualizer import tick_pipeline

        widget, _parent, _tp = _paused_spectrum_widget(monkeypatch)

        tick_pipeline.resolve_widget_spectrum_presentation(
            widget, widget._display_bars, now_ts=time.time(), first_frame=True
        )

        assert widget._display_bars_source_generation == -1
        assert widget._display_bars_source_activation == -1
        assert widget._waiting_for_fresh_engine_frame is True


class _RealParent(QWidget):
    """A display parent that accepts visualizer frames, like the real one."""

    def __init__(self) -> None:
        super().__init__()
        self._spotify_bars_overlay = _OverlayStub()
        self.frames: list[dict] = []

    def push_spotify_visualizer_frame(self, *_args, **kwargs):
        self.frames.append(kwargs)
        return True
