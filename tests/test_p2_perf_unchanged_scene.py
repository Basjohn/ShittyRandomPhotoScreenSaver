"""P2-PERF-A: do not physically present an unchanged visualizer scene.

A representative 10-second window with the visualizer on the 165-Hz display:

    logical/state publications     ~86.6 / sec
    physical paints                ~140.7 / sec
    display refresh                ~164.8 Hz

P1 forbids paint-local visualizer simulation, so a published render state that
has not advanced has no new authored state to reveal. Roughly 54 paints/sec were
presenting the identical scene again.

The correction keeps the compositor timer as the sole physical presentation
authority. It still wakes at the display rate; it just declines to queue a GUI
paint for a scene revision it has already requested, and only ever in
visualizer-only, transition-free operation.

This is not a cadence cap, a refresh divisor, producer-owned paint scheduling, a
second clock or source decimation - and the bars below pin each of those.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering import adaptive_timer
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.visualizer_layer import (
    CompositorVisualizerLayer,
    VisualizerRenderState,
)

TRANSITION = GLCompositorWidget.PRESENTATION_TRANSITION_ACTIVE
VIS_ACTIVE = GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE
VIS_PREPARING = GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING


# ---------------------------------------------------------------------------
# The scene revision itself
# ---------------------------------------------------------------------------


class TestSceneRevision:
    def _layer(self):
        return CompositorVisualizerLayer(SimpleNamespace())

    def test_a_fresh_layer_starts_at_a_stable_revision(self):
        layer = self._layer()
        assert layer.scene_revision == layer.scene_revision

    def test_every_publication_advances_the_revision(self):
        layer = self._layer()
        before = layer.scene_revision
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        assert layer.scene_revision == before + 1
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        assert layer.scene_revision == before + 2

    def test_clearing_advances_the_revision(self):
        """Hiding the card is a scene change that must be presented."""
        layer = self._layer()
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        before = layer.scene_revision
        layer.clear()
        assert layer.scene_revision == before + 1

    def test_the_revision_is_monotonic(self):
        layer = self._layer()
        seen = [layer.scene_revision]
        for _ in range(20):
            layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
            seen.append(layer.scene_revision)
        assert seen == sorted(seen)
        assert len(set(seen)) == len(seen)

    def test_explicit_invalidation_advances_it(self):
        layer = self._layer()
        before = layer.scene_revision
        layer.invalidate_scene()
        assert layer.scene_revision == before + 1


# ---------------------------------------------------------------------------
# Only visualizer-only, transition-free operation is eligible for suppression
# ---------------------------------------------------------------------------


def _compositor(reasons, revision=7):
    layer = SimpleNamespace(scene_revision=revision)
    return SimpleNamespace(
        _presentation_reasons=set(reasons),
        _visualizer_layer=layer,
        PRESENTATION_TRANSITION_ACTIVE=TRANSITION,
        PRESENTATION_VISUALIZER_ACTIVE=VIS_ACTIVE,
        PRESENTATION_VISUALIZER_PREPARING=VIS_PREPARING,
    )


class TestEligibility:
    def _revision(self, comp):
        return GLCompositorWidget.presentation_scene_revision(comp)

    def test_visualizer_only_reports_its_scene_revision(self):
        assert self._revision(_compositor({VIS_ACTIVE})) == 7

    def test_preparing_only_reports_its_scene_revision(self):
        assert self._revision(_compositor({VIS_PREPARING})) == 7

    def test_an_active_transition_is_always_eligible(self):
        """Transitions must keep every admitted display deadline."""
        assert self._revision(_compositor({VIS_ACTIVE, TRANSITION})) is None
        assert self._revision(_compositor({TRANSITION})) is None

    def test_any_other_liveness_reason_is_always_eligible(self):
        assert self._revision(_compositor({VIS_ACTIVE, "SOMETHING_ELSE"})) is None

    def test_no_liveness_reason_is_always_eligible(self):
        assert self._revision(_compositor(set())) is None

    def test_a_missing_layer_is_always_eligible(self):
        comp = _compositor({VIS_ACTIVE})
        comp._visualizer_layer = None
        assert self._revision(comp) is None


# ---------------------------------------------------------------------------
# The presentation deadline
# ---------------------------------------------------------------------------


class _Widget:
    def __init__(self, reasons=(VIS_ACTIVE,), revision=1):
        self.update_count = 0
        self.accepted = 0
        self.skipped = 0
        self._presentation_reasons = set(reasons)
        self._visualizer_layer = SimpleNamespace(scene_revision=revision)
        self.PRESENTATION_TRANSITION_ACTIVE = TRANSITION
        self.PRESENTATION_VISUALIZER_ACTIVE = VIS_ACTIVE
        self.PRESENTATION_VISUALIZER_PREPARING = VIS_PREPARING

    def presentation_scene_revision(self):
        return GLCompositorWidget.presentation_scene_revision(self)

    def publish(self):
        self._visualizer_layer.scene_revision += 1

    def update(self):
        self.update_count += 1

    def _record_render_timer_tick(self, *, accepted_update=True):
        if accepted_update:
            self.accepted += 1
        else:
            self.skipped += 1


@pytest.fixture
def strategy(monkeypatch):
    monkeypatch.setattr(
        adaptive_timer.ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda func, *a, **k: func()),
    )
    monkeypatch.setattr(adaptive_timer, "Shiboken", None)

    def _make(widget):
        config = adaptive_timer.AdaptiveTimerConfig(target_fps=165)
        return adaptive_timer.AdaptiveTimerStrategy(widget, config)

    return _make


class TestDeadlineSuppression:
    def test_the_first_deadline_always_presents(self, strategy):
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        assert widget.update_count == 1
        assert widget.accepted == 1

    def test_an_unchanged_scene_is_not_presented_again(self, strategy):
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        for _ in range(10):
            timer._signal_frame()
        assert widget.update_count == 1, (
            "the identical visualizer scene was presented repeatedly"
        )
        assert widget.skipped == 10

    def test_a_new_scene_revision_is_presented(self, strategy):
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        widget.publish()
        timer._signal_frame()
        assert widget.update_count == 2

    def test_an_active_transition_presents_every_deadline(self, strategy):
        widget = _Widget(reasons=(VIS_ACTIVE, TRANSITION))
        timer = strategy(widget)
        for _ in range(12):
            timer._signal_frame()
        assert widget.update_count == 12, (
            "transition delivery must not be suppressed"
        )
        assert widget.skipped == 0

    def test_60hz_display_with_90hz_publication_loses_no_state(self, strategy):
        """Almost every 60-Hz deadline still has a new state; nothing is lost."""
        widget = _Widget()
        timer = strategy(widget)
        presented = 0
        # 90 publications interleaved with 60 deadlines.
        for i in range(180):
            if i % 2 == 0:
                widget.publish()
            if i % 3 == 0:
                before = widget.update_count
                timer._signal_frame()
                presented += widget.update_count - before
        assert presented == 60, "a 60-Hz display should still present every deadline"

    def test_165hz_display_tracks_publications_not_refresh(self, strategy):
        """The whole point: useful paints follow authored scene revisions."""
        widget = _Widget()
        timer = strategy(widget)
        # ~87 publications against ~165 deadlines, as installed.
        publications = 0
        for i in range(165):
            if i % 2 == 0:
                widget.publish()
                publications += 1
            timer._signal_frame()
        assert widget.update_count <= publications + 1
        assert widget.update_count >= publications - 1
        assert widget.skipped > 60, "no redundant presentation was avoided"

    def test_a_cleared_scene_is_presented_once(self, strategy):
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        widget.publish()  # stands in for clear(), which also advances
        timer._signal_frame()
        for _ in range(5):
            timer._signal_frame()
        assert widget.update_count == 2

    def test_an_explicit_frame_request_is_always_eligible(self, strategy):
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        timer.request_frame()
        timer._signal_frame()
        assert widget.update_count == 2, (
            "an explicit request exists because something outside the visualizer "
            "scene needs presenting"
        )

    def test_a_compositor_without_the_seam_presents_every_deadline(self, strategy):
        class _NoSeam(_Widget):
            presentation_scene_revision = None

        widget = _NoSeam()
        timer = strategy(widget)
        for _ in range(5):
            timer._signal_frame()
        assert widget.update_count == 5


# ---------------------------------------------------------------------------
# The counter is evidence, not control flow
# ---------------------------------------------------------------------------


class TestSuppressionAccounting:
    def test_a_suppressed_deadline_is_labelled_unchanged_scene(self, strategy, monkeypatch):
        monkeypatch.setattr(adaptive_timer, "is_perf_metrics_enabled", lambda: True)
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        timer._signal_frame()
        assert getattr(widget, "_srpss_timer_last_skip_stage") == "unchanged_scene"
        assert int(getattr(widget, "_srpss_delivery_unchanged_scene_skips", 0)) == 1

    def test_suppression_is_not_counted_as_a_dispatch_failure(self, strategy, monkeypatch):
        monkeypatch.setattr(adaptive_timer, "is_perf_metrics_enabled", lambda: True)
        widget = _Widget()
        timer = strategy(widget)
        timer._signal_frame()
        for _ in range(4):
            timer._signal_frame()
        assert int(getattr(widget, "_srpss_delivery_dispatch_pending_skips", 0)) == 0
        assert int(getattr(widget, "_srpss_delivery_unknown_skips", 0)) == 0
        assert int(getattr(widget, "_srpss_delivery_unchanged_scene_skips", 0)) == 4

    def test_the_counter_is_reported_in_the_existing_summary(self):
        source = inspect.getsource(adaptive_timer._log_delivery_perf_window)
        assert "unchanged_scene_skips=%d" in source
        # It extends the existing cadence record; it is not a new family.
        # It extends the existing cadence record rather than starting a new
        # diagnostic family: same logger call, same record prefix.
        assert "[PERF][DELIVERY_STAGE][CADENCE]" in source
        assert source.count("[PERF][DELIVERY_STAGE]") == 2, (
            "the counter must ride the existing summary records"
        )

    def test_acceptance_excludes_intentional_suppression(self):
        source = inspect.getsource(adaptive_timer._log_delivery_perf_window)
        assert "useful_wakeups" in source, (
            "intentional no-change suppression must not read as an acceptance miss"
        )


# ---------------------------------------------------------------------------
# The forbidden shapes
# ---------------------------------------------------------------------------


class TestForbiddenShapes:
    def test_the_timer_still_wakes_at_the_display_rate(self, strategy):
        """Suppression must not change the wake cadence."""
        widget = _Widget()
        timer = strategy(widget)
        for _ in range(20):
            timer._signal_frame()
        # Every deadline was serviced; only the GUI paint was declined.
        assert widget.accepted + widget.skipped == 20

    def test_no_producer_owned_paint_scheduling_was_added(self):
        source = inspect.getsource(adaptive_timer.AdaptiveTimerStrategy._signal_frame)
        for forbidden in ("QTimer", "single_shot", "sleep", "repaint"):
            assert forbidden not in source

    def test_suppression_never_touches_logical_state(self):
        source = inspect.getsource(
            adaptive_timer.AdaptiveTimerStrategy._scene_is_already_requested
        )
        for forbidden in ("set_state", "tick", "publish", "_on_tick"):
            assert forbidden not in source

    def test_no_visualizer_mode_evolves_from_paint_local_wall_clock(self):
        """u_time comes from logical accumulation, never from paint."""
        from widgets.spotify_visualizer import overlay_uniforms

        source = inspect.getsource(overlay_uniforms)
        assert "_accumulated_time" in source
        for forbidden in ("time.time()", "time.monotonic()", "perf_counter()"):
            assert forbidden not in source, (
                "a mode evolving from paint-local wall clock would turn duplicate "
                "physical paints into a hidden simulation clock"
            )

    def test_accumulated_time_advances_in_the_logical_publication(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        source = inspect.getsource(SpotifyBarsGLOverlay.set_state)
        assert "_accumulated_time += dt" in source

    def test_paint_layer_does_not_advance_accumulated_time(self):
        from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        assert "_accumulated_time" not in source
