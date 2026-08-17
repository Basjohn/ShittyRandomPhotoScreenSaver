"""Positive presentation/fidelity contract for the auxiliary visualizer overlay.

`tests/test_visualizer_presentation_negative_controls.py` proves which admission
designs are rejected. This file owns the other half: what the production
presentation owner must still guarantee once P2 stops requesting one
`QOpenGLWidget.update()` per accepted logical publication.

Every assertion here holds against the current 1:1 implementation *and* against a
correct coalescing presentation owner. A test that only passes while publication
and presentation are coupled would block P2 instead of protecting it.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


class _FakeClock:
    """Deterministic stand-in for the module's wall/monotonic clock reads."""

    def __init__(self, start: float = 1_000.0, step: float = 0.010) -> None:
        self._now = float(start)
        self._step = float(step)

    def advance(self, seconds: float | None = None) -> float:
        self._now += self._step if seconds is None else float(seconds)
        return self._now

    def time(self) -> float:
        return self._now

    def perf_counter(self) -> float:
        return self._now

    def monotonic(self) -> float:
        return self._now


def _install_fake_clock(monkeypatch, clock: _FakeClock) -> None:
    from widgets import spotify_bars_gl_overlay

    monkeypatch.setattr(spotify_bars_gl_overlay, "time", clock, raising=True)


def _publish(overlay: SpotifyBarsGLOverlay, bars, *, vis_mode="spectrum", **kwargs):
    overlay.set_state(
        rect=QRect(0, 0, 320, 180),
        bars=list(bars),
        bar_count=len(bars),
        segments=4,
        fill_color=QColor(255, 255, 255),
        border_color=QColor(255, 255, 255),
        fade=1.0,
        playing=True,
        visible=True,
        vis_mode=vis_mode,
        **kwargs,
    )


def _logical_digest(overlay: SpotifyBarsGLOverlay) -> dict:
    """Mode-owned logical state that presentation coalescing must not disturb."""
    return {
        "vis_mode": overlay._vis_mode,
        "bar_count": overlay._bar_count,
        "segments": overlay._segments,
        "bars": [round(float(value), 9) for value in list(overlay._bars or [])],
        "peaks": [round(float(value), 9) for value in list(overlay._peaks or [])],
        "accumulated_time": round(float(overlay._accumulated_time), 9),
        "waveform_count": int(overlay._waveform_count or 0),
        "waveform": [round(float(value), 9) for value in list(overlay._waveform or [])],
        "bubble_count": int(overlay._bubble_count or 0),
        "set_state_total": int(overlay._perf_set_state_total),
    }


def _bar_series(count: int) -> list[list[float]]:
    """Distinct, non-monotonic publications so a dropped input is detectable."""
    series = []
    for index in range(count):
        base = ((index * 7) % 11) / 10.0
        series.append([base, min(1.0, base + 0.15), max(0.0, base - 0.15)])
    return series


@pytest.mark.qt
class TestPublicationVersusPresentation:
    """Logical publication and presentation opportunity are separate contracts."""

    def test_every_accepted_publication_is_integrated_once(self, qt_app, monkeypatch):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)

        series = _bar_series(24)
        for bars in series:
            _publish(overlay, bars)
            clock.advance()

        assert overlay._perf_set_state_total == len(series)
        # Latest integrated state wins; the final publication is fully visible.
        assert list(overlay._bars) == pytest.approx(series[-1])
        # Peak-hold is an accumulator: it proves earlier publications were
        # integrated rather than skipped straight to the final input.
        assert any(
            peak > value + 1e-9
            for peak, value in zip(overlay._peaks, series[-1])
        )

    def test_presentation_requests_may_not_exceed_accepted_publications(
        self, qt_app, monkeypatch
    ):
        """Presentation may coalesce; it must never amplify into extra repaints."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)

        series = _bar_series(24)
        for bars in series:
            _publish(overlay, bars)
            clock.advance()

        assert overlay._perf_update_request_total <= overlay._perf_set_state_total
        assert overlay._perf_update_request_total >= 1

    def test_suppressed_presentation_leaves_logical_state_identical(
        self, qt_app, monkeypatch
    ):
        """The A/B result P2 must preserve: withholding repaints changes nothing logical.

        This is the core P1 bar. If a future presentation owner derives logical
        state from paint opportunities, or drops an input before integration,
        these two digests diverge.
        """
        series = _bar_series(32)

        clock_a = _FakeClock()
        _install_fake_clock(monkeypatch, clock_a)
        presented = SpotifyBarsGLOverlay(None)
        for bars in series:
            _publish(presented, bars)
            clock_a.advance()
        presented_digest = _logical_digest(presented)

        # Depth 1: Qt never actually paints, but the request is still issued.
        clock_b = _FakeClock()
        _install_fake_clock(monkeypatch, clock_b)
        unpainted = SpotifyBarsGLOverlay(None)
        unpainted_paints = []
        # Instance-level sinks: production classes are never patched.
        unpainted.update = lambda *args, **kwargs: unpainted_paints.append(1)
        for bars in series:
            _publish(unpainted, bars)
            clock_b.advance()

        # Depth 2: the presentation request itself is withheld, exactly as the
        # retired A/B/C probe's B_SUPPRESS_REQUESTS state did.
        clock_c = _FakeClock()
        _install_fake_clock(monkeypatch, clock_c)
        unrequested = SpotifyBarsGLOverlay(None)
        unrequested._request_frame_update = lambda **kwargs: None
        for bars in series:
            _publish(unrequested, bars)
            clock_c.advance()

        assert _logical_digest(unpainted) == presented_digest
        assert _logical_digest(unrequested) == presented_digest
        assert presented_digest["set_state_total"] == len(series)
        assert unpainted_paints, "the unpainted control must still request presentation"

    def test_logical_cadence_does_not_depend_on_presentation_frequency(
        self, qt_app, monkeypatch
    ):
        """Publishing faster than any display refresh must still integrate every input."""
        clock = _FakeClock(step=0.002)  # 500 Hz logical publication
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)

        series = _bar_series(100)
        for bars in series:
            _publish(overlay, bars)
            clock.advance()

        assert overlay._perf_set_state_total == len(series)
        assert list(overlay._bars) == pytest.approx(series[-1])


@pytest.mark.qt
class TestPublicationAdmission:
    """Admission stays owned by state identity, never by presentation state."""

    def test_invisible_publication_is_rejected_before_integration(
        self, qt_app, monkeypatch
    ):
        """An invisible overlay clears its buffer instead of integrating the frame."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)

        _publish(overlay, [0.4, 0.5, 0.6])
        accepted_after_first = overlay._perf_set_state_total
        assert accepted_after_first == 1
        assert list(overlay._bars) == pytest.approx([0.4, 0.5, 0.6])

        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[0.9, 0.9, 0.9],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=False,
            vis_mode="spectrum",
        )

        # The rejected frame is never integrated, and the hidden overlay does not
        # retain a stale visible buffer that a later paint could present.
        assert overlay._perf_set_state_total == accepted_after_first
        assert list(overlay._bars) == []
        assert overlay._bar_count == 0

    def test_mode_change_clears_mode_owned_state_regardless_of_presentation(
        self, qt_app, monkeypatch
    ):
        """Activation resets are logical events, not repaint side effects."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        overlay.update = lambda *args, **kwargs: None  # no presentation at all

        _publish(overlay, [0.7, 0.8, 0.9], vis_mode="spectrum")
        assert list(overlay._bars) == pytest.approx([0.7, 0.8, 0.9])

        clock.advance()
        _publish(
            overlay,
            [1.0, 1.0, 1.0],
            vis_mode="devcurve",
            devcurve_sample_count=4,
            devcurve_curve_bass=[0.2, 0.3, 0.2, 0.1],
        )

        assert overlay._vis_mode == "devcurve"
        assert list(overlay._peaks) == []
        assert overlay._accumulated_time == pytest.approx(0.0)


def _shared_gui_delivery(
    *,
    lane_capacity_hz: float,
    display_hz: dict[str, float],
    visualizer_request_hz: float,
) -> dict[str, float]:
    """Model the serial GUI dispatch lane both display compositors share.

    Qt dispatches queued widget updates on one GUI thread. Each display
    compositor needs one dispatch per frame it intends to present, and any
    auxiliary visualizer surface that requests its own repaints adds a third
    independent demand stream to the same lane.

    Under saturation the lane is shared fairly, so every consumer meets the same
    fraction of its deadlines: ``capacity / total_demand``. This is deliberately
    coarse - it models contention for dispatch opportunities, not exact Qt
    scheduling - and it is the property the P2 presentation owner must satisfy.
    """
    total_demand = sum(display_hz.values()) + max(0.0, float(visualizer_request_hz))
    if total_demand <= 0.0:
        return {name: 1.0 for name in display_hz}
    met = min(1.0, float(lane_capacity_hz) / total_demand)
    return {name: met for name in display_hz}


def _coupled_request_hz(logical_hz: float, display_hz: dict[str, float]) -> float:
    """Current baseline: one auxiliary update request per logical publication."""
    del display_hz
    return float(logical_hz)


def _presentation_owned_request_hz(
    logical_hz: float, display_hz: dict[str, float]
) -> float:
    """P2 target: the owning display presents the visualizer within its own frame.

    The auxiliary surface stops being an independent repaint source, so it adds
    no dispatch demand of its own no matter how fast logical state publishes.
    """
    del logical_hz, display_hz
    return 0.0


class TestMixedRefreshDeliveryBar:
    """One display's visualizer must not starve the sibling display's delivery.

    The mixed-refresh bar required by `Current_Plan.md` P1. It is expressed as a
    property of the presentation *policy* rather than a live dual-monitor
    measurement, so it can gate P2 deterministically. Installed dual-display
    validation remains the acceptance authority under P5-F.
    """

    LANE_CAPACITY_HZ = 300.0
    DISPLAY_HZ = {"display_0_165hz": 165.0, "display_1_60hz": 60.0}
    LOGICAL_PUBLICATION_HZ = 100.0
    REQUIRED_MET_FRACTION = 0.99

    def test_publication_coupled_requests_starve_the_sibling_display(self):
        """The rejected baseline: one update request per logical publication."""
        delivery = _shared_gui_delivery(
            lane_capacity_hz=self.LANE_CAPACITY_HZ,
            display_hz=self.DISPLAY_HZ,
            visualizer_request_hz=self.LOGICAL_PUBLICATION_HZ,
        )

        # Both displays lose deadlines, including the one with no visualizer -
        # exactly the shared-GUI amplifier the A/B/C evidence measured.
        assert delivery["display_1_60hz"] < self.REQUIRED_MET_FRACTION
        assert delivery["display_0_165hz"] < self.REQUIRED_MET_FRACTION

    def test_presentation_owned_requests_meet_the_mixed_refresh_bar(self):
        """The P2 target: the owning display presents its visualizer, adding no stream."""
        delivery = _shared_gui_delivery(
            lane_capacity_hz=self.LANE_CAPACITY_HZ,
            display_hz=self.DISPLAY_HZ,
            visualizer_request_hz=0.0,
        )

        assert delivery["display_1_60hz"] >= self.REQUIRED_MET_FRACTION
        assert delivery["display_0_165hz"] >= self.REQUIRED_MET_FRACTION

    def test_bar_rejects_a_merely_rate_capped_request_stream(self):
        """Capping the stream at display refresh is not enough to clear the bar.

        This blocks the tempting shortcut of gating requests to a display-FPS
        number, which `test_visualizer_presentation_negative_controls.py` already
        rejects on fidelity grounds. It also fails the delivery bar.
        """
        delivery = _shared_gui_delivery(
            lane_capacity_hz=self.LANE_CAPACITY_HZ,
            display_hz=self.DISPLAY_HZ,
            visualizer_request_hz=self.DISPLAY_HZ["display_0_165hz"],
        )

        assert delivery["display_1_60hz"] < self.REQUIRED_MET_FRACTION

    @pytest.mark.parametrize("logical_hz", [60.0, 100.0, 165.0, 500.0])
    def test_sibling_delivery_is_independent_of_logical_publication_rate(
        self, logical_hz
    ):
        """A correct owner decouples sibling delivery from visualizer think-rate.

        Both policies are evaluated at the same logical rate so the parameter
        genuinely drives the comparison: the coupled policy degrades as the
        visualizer thinks faster, the presentation-owned policy does not.
        """
        coupled = _shared_gui_delivery(
            lane_capacity_hz=self.LANE_CAPACITY_HZ,
            display_hz=self.DISPLAY_HZ,
            visualizer_request_hz=_coupled_request_hz(logical_hz, self.DISPLAY_HZ),
        )
        owned = _shared_gui_delivery(
            lane_capacity_hz=self.LANE_CAPACITY_HZ,
            display_hz=self.DISPLAY_HZ,
            visualizer_request_hz=_presentation_owned_request_hz(
                logical_hz, self.DISPLAY_HZ
            ),
        )

        assert owned["display_1_60hz"] >= self.REQUIRED_MET_FRACTION
        assert owned["display_1_60hz"] >= coupled["display_1_60hz"]
        if logical_hz >= 100.0:
            # A visualizer thinking at or above 100 Hz measurably starves the
            # sibling display under the coupled policy.
            assert coupled["display_1_60hz"] < self.REQUIRED_MET_FRACTION


@pytest.mark.qt
class TestPerDisplayPresentationIndependence:
    """Two displays own separate overlays, counters and logical state."""

    def test_one_display_overlay_never_mutates_its_sibling(self, qt_app, monkeypatch):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        display_0 = SpotifyBarsGLOverlay(None)
        display_1 = SpotifyBarsGLOverlay(None)
        display_0.update = lambda *args, **kwargs: None
        display_1.update = lambda *args, **kwargs: None

        for bars in _bar_series(12):
            _publish(display_0, bars)
            clock.advance()

        assert display_0._perf_set_state_total == 12
        assert display_1._perf_set_state_total == 0
        assert display_1._perf_update_request_total == 0
        assert list(display_1._bars) == []
        assert display_1._peaks is not display_0._peaks

    def test_each_display_accounts_its_own_presentation_requests(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        display_0 = SpotifyBarsGLOverlay(None)
        display_1 = SpotifyBarsGLOverlay(None)
        display_0.update = lambda *args, **kwargs: None
        display_1.update = lambda *args, **kwargs: None

        for bars in _bar_series(9):
            _publish(display_0, bars)
            clock.advance()
        for bars in _bar_series(4):
            _publish(display_1, bars)
            clock.advance()

        assert display_0._perf_update_request_total <= 9
        assert display_1._perf_update_request_total <= 4
        assert display_0._perf_set_state_total == 9
        assert display_1._perf_set_state_total == 4


@pytest.mark.qt
class TestPresentationOwnership:
    """One named presentation seam owns repaint requests."""

    def test_presentation_requests_flow_through_the_single_named_seam(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)

        direct_updates = []
        overlay.update = lambda *args, **kwargs: direct_updates.append(1)

        before_requests = overlay._perf_update_request_total
        _publish(overlay, [0.3, 0.4, 0.5])
        after_requests = overlay._perf_update_request_total

        # Whatever the admission policy becomes, a repaint that reaches Qt must be
        # accounted for by the overlay's own presentation counter.
        assert len(direct_updates) <= after_requests - before_requests
        assert after_requests - before_requests <= 1

    def test_paint_consumes_the_latest_integrated_state_not_a_queued_backlog(
        self, qt_app, monkeypatch
    ):
        """Coalescing presents the newest state; it never replays stale snapshots."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        overlay.update = lambda *args, **kwargs: None

        series = _bar_series(16)
        for bars in series:
            _publish(overlay, bars)
            clock.advance()

        assert list(overlay._bars) == pytest.approx(series[-1])
        assert overlay._bar_count == len(series[-1])


class TestPresentationOpportunitySourceEligibility:
    """R-61 anti-regression: presentation must survive a paused presentation source.

    The rejected P2 implementation made the transition-scoped
    `AdaptiveTimerStrategy` the *sole* presentation source, so the visualizer
    froze permanently once a transition ended.

    The invariant is survival, not abstinence: a display presentation opportunity
    may legitimately drive the overlay *while it is running*, provided the overlay
    still presents when that source is paused or absent. This bar must not forbid
    using the opportunity - `Current_Plan.md` P1 explicitly requires proving that
    logical publication can outrun presentation without one `update()` per
    publication.
    """

    def test_adaptive_timer_is_documented_as_transition_scoped(self):
        import inspect

        from rendering.gl_compositor import GLCompositorWidget

        start = inspect.getsource(GLCompositorWidget._start_render_timer)
        pause = inspect.getsource(GLCompositorWidget._pause_render_strategy)

        assert "during transitions" in start.lower(), (
            "render strategy start no longer documents its transition scope; "
            "re-verify eligibility before relying on it as a presentation source"
        )
        assert "after transition ends" in pause.lower(), (
            "render strategy pause no longer documents its transition scope; "
            "re-verify eligibility before relying on it as a presentation source"
        )

    @pytest.mark.qt
    def test_overlay_presents_when_no_presentation_source_is_running(
        self, qt_app, monkeypatch
    ):
        """With no transition active, every publication must still reach Qt.

        This is the executable form of R-61: whatever presentation ownership
        exists, an idle/paused display presentation source may never leave the
        visualizer unpresented.
        """
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        overlay.isVisible = lambda: True

        for bars in _bar_series(12):
            _publish(overlay, bars)
            clock.advance()

        assert len(paints) >= 12, (
            "with no presentation source running the overlay must keep requesting "
            "one repaint per accepted publication (R-61)"
        )


@pytest.mark.qt
class TestTransitionScopedPresentationDeferral:
    """P2: defer auxiliary presentation only while a display opportunity is running.

    Scope, per the approved candidate:

        no transition / source paused -> unchanged behaviour, one request per
                                          accepted publication
        transition active             -> integrate every publication, mark the
                                          latest render state dirty, and present
                                          when the display's existing presentation
                                          opportunity arrives

    This targets the measured shared-GUI pressure window without introducing a
    timer, thread, producer gate, paint latch or source throttle, and without
    depending solely on a transition-scoped source (R-61).
    """

    def _overlay(self, monkeypatch):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        overlay.isVisible = lambda: True
        # Settle the geometry/reveal immediate-request boundaries.
        _publish(overlay, [0.1, 0.2, 0.3])
        clock.advance()
        paints.clear()
        return overlay, paints, clock

    def test_default_behaviour_is_one_request_per_publication(self, qt_app, monkeypatch):
        """With no presentation opportunity running, nothing changes (R-61)."""
        overlay, paints, clock = self._overlay(monkeypatch)

        for bars in _bar_series(10):
            _publish(overlay, bars)
            clock.advance()

        assert len(paints) == 10

    def test_active_opportunity_defers_publications(self, qt_app, monkeypatch):
        overlay, paints, clock = self._overlay(monkeypatch)
        overlay.set_presentation_deferred(True)

        for bars in _bar_series(10):
            _publish(overlay, bars)
            clock.advance()

        assert overlay._perf_set_state_total == 11, "every publication still integrates"
        assert len(paints) == 0, "presentation is owed to the display opportunity"
        assert overlay.has_pending_presentation() is True

        assert overlay.present_if_pending() is True
        assert len(paints) == 1
        assert overlay.present_if_pending() is False, "no new publication, no request"

    def test_ending_deferral_flushes_and_restores_immediate_requests(
        self, qt_app, monkeypatch
    ):
        """R-61: a paused source must never strand the visualizer."""
        overlay, paints, clock = self._overlay(monkeypatch)
        overlay.set_presentation_deferred(True)

        _publish(overlay, [0.4, 0.5, 0.6])
        clock.advance()
        assert len(paints) == 0

        overlay.set_presentation_deferred(False)
        assert len(paints) == 1, "the owed publication is flushed on release"

        for bars in _bar_series(6):
            _publish(overlay, bars)
            clock.advance()
        assert len(paints) == 7, "immediate requests resume once deferral ends"

    def test_discrete_event_bypasses_deferral(self, qt_app, monkeypatch):
        """A one-publication authored edge must not wait for the next slot."""
        overlay, paints, clock = self._overlay(monkeypatch)
        overlay.set_presentation_deferred(True)

        _publish(overlay, [0.2, 0.3, 0.4])
        clock.advance()
        assert len(paints) == 0, "continuous motion defers"

        _publish(overlay, [0.2, 0.3, 0.4], line_kick_event_strength=0.9)
        clock.advance()
        assert len(paints) == 1, "a rising kick edge presents immediately"

        _publish(overlay, [0.2, 0.3, 0.4], line_kick_event_strength=0.1)
        clock.advance()
        assert len(paints) == 1, "a decayed follow-up is not a new edge"

    def test_deferral_never_reproduces_the_r27_stutter_signature(
        self, qt_app, monkeypatch
    ):
        """R-27 bar: set_state ~90-100 Hz must not collapse paint to ~39-40 Hz.

        The rejected July mechanism throttled the producer. Here the producer is
        untouched and presentation is driven by the display opportunity, so at a
        60 Hz opportunity rate the presented rate must track the opportunity, not
        halve to a divisor.
        """
        overlay, paints, clock = self._overlay(monkeypatch)
        overlay.set_presentation_deferred(True)

        publications = 0
        opportunities = 0
        # 96 publications at ~96 Hz against a 60 Hz opportunity stream.
        for index, bars in enumerate(_bar_series(96)):
            _publish(overlay, bars)
            publications += 1
            clock.advance()
            if index % 8 in (0, 2, 4, 6, 7):  # 5 opportunities per 8 publications
                overlay.present_if_pending()
                opportunities += 1

        assert overlay._perf_set_state_total == publications + 1
        # Presentation must track the opportunity stream, not collapse below it.
        assert len(paints) == opportunities, (
            f"presented {len(paints)} of {opportunities} opportunities; "
            "a divisor collapse is the R-27 failure signature"
        )
        assert len(paints) / publications > 0.5, "presented rate collapsed below half"

    def test_logical_state_is_identical_with_and_without_deferral(
        self, qt_app, monkeypatch
    ):
        """Deferral is presentation-only: logical integration must be bit-identical."""
        series = _bar_series(24)

        clock_a = _FakeClock()
        _install_fake_clock(monkeypatch, clock_a)
        immediate = SpotifyBarsGLOverlay(None)
        immediate.update = lambda *a, **k: None
        immediate.isVisible = lambda: True
        for bars in series:
            _publish(immediate, bars)
            clock_a.advance()

        clock_b = _FakeClock()
        _install_fake_clock(monkeypatch, clock_b)
        deferred = SpotifyBarsGLOverlay(None)
        deferred.update = lambda *a, **k: None
        deferred.isVisible = lambda: True
        deferred.set_presentation_deferred(True)
        for bars in series:
            _publish(deferred, bars)
            clock_b.advance()

        assert _logical_digest(deferred) == _logical_digest(immediate)


class TestDisplayOpportunityWiring:
    """The display drives deferral only while its opportunity actually runs."""

    def _timer(self, presenter=None):
        from rendering.adaptive_timer import AdaptiveTimerConfig, AdaptiveTimerStrategy

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        timer = AdaptiveTimerStrategy(_Compositor(), AdaptiveTimerConfig())
        if presenter is not None:
            timer.set_auxiliary_presenter(presenter)
        return timer

    class _Presenter:
        def __init__(self, pending=True):
            self.pending = pending
            self.presented = 0
            self.deferred = None

        def has_pending_presentation(self):
            return self.pending

        def present_if_pending(self):
            self.presented += 1
            return True

        def set_presentation_deferred(self, value):
            self.deferred = bool(value)

    def test_presentation_is_marshalled_never_called_on_the_timer_thread(self):
        """R-61 defect 1: QWidget work must not run on the timer worker thread."""
        from rendering import adaptive_timer

        presenter = self._Presenter()
        timer = self._timer(presenter)
        marshalled = []
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: marshalled.append(func)
            )
            timer._signal_frame()

            assert presenter.presented == 0, (
                "present_if_pending() must not run on the timer worker thread"
            )
            ours = [f for f in marshalled if f == presenter.present_if_pending]
            assert len(ours) == 1, "presentation must be queued to the GUI owner"
            ours[0]()
            assert presenter.presented == 1
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_idle_presenter_queues_no_gui_callback(self):
        from rendering import adaptive_timer

        presenter = self._Presenter(pending=False)
        timer = self._timer(presenter)
        marshalled = []
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: marshalled.append(func)
            )
            timer._signal_frame()
            timer._signal_frame()
            ours = [f for f in marshalled if f == presenter.present_if_pending]
            assert ours == [], "an idle overlay must add no GUI dispatch demand"
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_registration_enables_deferral_and_clearing_releases_it(self):
        """R-61: releasing the source must restore immediate presentation."""
        presenter = self._Presenter()
        timer = self._timer()

        timer.set_auxiliary_presenter(presenter)
        assert presenter.deferred is True

        timer.clear_auxiliary_presenter()
        assert presenter.deferred is False

    def test_destroyed_presenter_is_dropped_before_any_gui_work(self):
        from rendering import adaptive_timer

        class _Dead:
            def __init__(self):
                self.calls = 0

            def has_pending_presentation(self):
                self.calls += 1
                raise RuntimeError("wrapped C/C++ object has been deleted")

            def present_if_pending(self):
                raise AssertionError("must not be reached for a destroyed surface")

            def set_presentation_deferred(self, value):
                pass

        presenter = _Dead()
        timer = self._timer(presenter)
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: func()
            )
            timer._signal_frame()
            timer._signal_frame()
            assert presenter.calls == 1, "a destroyed surface is dropped, not retried"
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original


class TestDeferralFollowsStrategyLifecycle:
    """R-61 core guarantee: deferral is on only while the opportunity runs.

    `AdaptiveRenderStrategyManager` starts for a transition and pauses when it
    ends. Deferral must track that exactly, so once the opportunity stops the
    overlay returns to one-request-per-publication instead of freezing.
    """

    class _Presenter:
        def __init__(self):
            self.deferred = None
            self.history = []

        def has_pending_presentation(self):
            return False

        def present_if_pending(self):
            return False

        def set_presentation_deferred(self, value):
            self.deferred = bool(value)
            self.history.append(bool(value))

    def _manager(self):
        from rendering.adaptive_timer import AdaptiveRenderStrategyManager

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        return AdaptiveRenderStrategyManager(_Compositor())

    def test_pause_releases_deferral_and_resume_restores_it(self):
        from rendering import adaptive_timer

        presenter = self._Presenter()
        manager = self._manager()
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: None
            )
            manager.set_auxiliary_presenter(presenter)
            manager.start()
            assert presenter.deferred is True, "a running opportunity defers"

            manager.pause()
            assert presenter.deferred is False, (
                "a paused opportunity must restore immediate presentation (R-61)"
            )

            manager.resume()
            assert presenter.deferred is True
        finally:
            try:
                manager.stop()
            except Exception:
                pass
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_stop_releases_deferral(self):
        from rendering import adaptive_timer

        presenter = self._Presenter()
        manager = self._manager()
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: None
            )
            manager.set_auxiliary_presenter(presenter)
            manager.start()
            manager.stop()
            assert presenter.deferred is False, (
                "a stopped opportunity must restore immediate presentation (R-61)"
            )
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_registering_before_start_does_not_defer_until_running(self):
        presenter = self._Presenter()
        manager = self._manager()

        manager.set_auxiliary_presenter(presenter)

        assert presenter.deferred is not True, (
            "registration alone must not defer; no opportunity is running yet"
        )
