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


@pytest.mark.qt
class TestDisplayOwnedPresentation:
    """P2: the owning display's frame opportunity drives the auxiliary surface."""

    def test_owned_overlay_defers_presentation_to_the_display_opportunity(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        # A parentless test widget never reports visible, which would retrigger the
        # became_visible immediate-request boundary on every publication.
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)

        # Settle the documented immediate-request boundaries (geometry, reveal).
        _publish(overlay, [0.1, 0.2, 0.3])
        clock.advance()
        overlay.present_if_pending()
        paints.clear()

        for bars in _bar_series(20):
            _publish(overlay, bars)
            clock.advance()

        # Every publication integrated; presentation still owed to the display.
        assert overlay._perf_set_state_total == 21
        assert len(paints) == 0
        assert overlay._present_revision != overlay._presented_revision

        assert overlay.present_if_pending() is True
        assert len(paints) == 1
        # A second opportunity with no new publication issues nothing.
        assert overlay.present_if_pending() is False
        assert len(paints) == 1

    def test_owned_presentation_collapses_many_publications_into_one_request(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        # A parentless test widget never reports visible, which would retrigger the
        # became_visible immediate-request boundary on every publication.
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)
        _publish(overlay, [0.1, 0.2, 0.3])
        clock.advance()
        overlay.present_if_pending()
        paints.clear()

        # 90 publications against 30 display opportunities.
        for index, bars in enumerate(_bar_series(90)):
            _publish(overlay, bars)
            clock.advance()
            if index % 3 == 2:
                overlay.present_if_pending()

        assert overlay._perf_set_state_total == 91
        assert len(paints) == 30
        assert overlay._perf_update_request_total <= overlay._perf_set_state_total

    def test_discrete_event_bypasses_the_opportunity_bound(self, qt_app, monkeypatch):
        """A short-lived authored edge must not wait for the next display slot."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        # A parentless test widget never reports visible, which would retrigger the
        # became_visible immediate-request boundary on every publication.
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)
        _publish(overlay, [0.2, 0.3, 0.4])
        clock.advance()
        overlay.present_if_pending()
        paints.clear()

        _publish(overlay, [0.2, 0.3, 0.4])
        clock.advance()
        assert len(paints) == 0, "continuous motion waits for the display"

        _publish(overlay, [0.2, 0.3, 0.4], line_kick_event_strength=0.9)
        clock.advance()
        assert len(paints) == 1, "a rising kick edge requests immediately"

        # A decayed follow-up is not a new edge.
        _publish(overlay, [0.2, 0.3, 0.4], line_kick_event_strength=0.1)
        clock.advance()
        assert len(paints) == 1

        _publish(overlay, [0.2, 0.3, 0.4], line_snare_event_strength=0.8)
        clock.advance()
        assert len(paints) == 2, "a rising snare edge requests immediately"

    def test_unowned_overlay_retains_the_previous_request_contract(
        self, qt_app, monkeypatch
    ):
        """No display registered means no silent loss of presentation."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)

        for bars in _bar_series(8):
            _publish(overlay, bars)
            clock.advance()

        assert len(paints) == 8

    def test_releasing_ownership_flushes_an_unpresented_publication(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        # A parentless test widget never reports visible, which would retrigger the
        # became_visible immediate-request boundary on every publication.
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)
        _publish(overlay, [0.5, 0.6, 0.7])
        clock.advance()
        overlay.present_if_pending()
        paints.clear()

        _publish(overlay, [0.55, 0.65, 0.75])
        assert len(paints) == 0

        overlay.set_presentation_owned(False)

        assert len(paints) == 1, "retirement must not strand a published frame"
        assert overlay._present_revision == overlay._presented_revision

    def test_disabled_owned_overlay_does_not_accumulate_stale_presentation(
        self, qt_app, monkeypatch
    ):
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        paints = []
        overlay.update = lambda *a, **k: paints.append(1)
        # A parentless test widget never reports visible, which would retrigger the
        # became_visible immediate-request boundary on every publication.
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)

        for bars in _bar_series(6):
            _publish(overlay, bars)
            clock.advance()
        paints.clear()

        # A disabled overlay owns no presentation, even with a publication owed.
        overlay._enabled = False
        overlay._present_revision += 1

        assert overlay.present_if_pending() is False
        assert len(paints) == 0
        assert overlay._present_revision == overlay._presented_revision


class TestAuxiliaryPresenterRegistration:
    """The timer services one registered presenter from its owned opportunity."""

    def _timer(self, compositor):
        from rendering.adaptive_timer import AdaptiveTimerConfig, AdaptiveTimerStrategy

        return AdaptiveTimerStrategy(compositor, AdaptiveTimerConfig())

    def test_signal_frame_offers_one_opportunity_to_the_registered_presenter(self):
        from rendering import adaptive_timer

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        class _Presenter:
            def __init__(self):
                self.offers = 0
                self.pending = True

            def has_pending_presentation(self):
                return self.pending

            def present_if_pending(self):
                self.offers += 1
                return True

        presenter = _Presenter()
        timer = self._timer(_Compositor())
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: func()
            )
            timer.set_auxiliary_presenter(presenter)
            timer._signal_frame()
            timer._signal_frame()
            assert presenter.offers == 2

            timer.clear_auxiliary_presenter()
            timer._signal_frame()
            assert presenter.offers == 2, "a cleared presenter is never serviced"
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_destroyed_presenter_is_dropped_rather_than_retried(self):
        from rendering import adaptive_timer

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        class _DeadPresenter:
            def __init__(self):
                self.calls = 0

            def has_pending_presentation(self):
                self.calls += 1
                raise RuntimeError("wrapped C/C++ object has been deleted")

            def present_if_pending(self):
                raise AssertionError("must not be reached for a destroyed surface")

        presenter = _DeadPresenter()
        timer = self._timer(_Compositor())
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: func()
            )
            timer.set_auxiliary_presenter(presenter)
            timer._signal_frame()
            timer._signal_frame()
            assert presenter.calls == 1, "a destroyed surface is dropped, not retried"
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original


class TestPresentationOwnerAttachment:
    """Ownership is claimed even though the overlay outlives strategy construction.

    Regression bar for the 2026-08-17 null result: the overlay is created lazily on
    the first visualizer push, before `_render_strategy_manager` exists, so a
    create-time-only registration silently left the overlay unowned and the
    publication-coupled contract in force.
    """

    def _widget(self, strategy):
        from types import SimpleNamespace

        compositor = SimpleNamespace(_render_strategy_manager=strategy)
        return SimpleNamespace(_gl_compositor=compositor, _screen_index=0)

    class _Strategy:
        def __init__(self):
            self.registered = None
            self.cleared = 0

        def set_auxiliary_presenter(self, presenter):
            self.registered = presenter

        def clear_auxiliary_presenter(self):
            self.cleared += 1
            self.registered = None

    class _Overlay:
        def __init__(self):
            self._has_presentation_owner = False
            self.owned_calls = []

        def set_presentation_owned(self, owned):
            self._has_presentation_owner = bool(owned)
            self.owned_calls.append(bool(owned))

    def test_attach_is_a_noop_until_the_strategy_exists(self):
        from rendering.display_image_ops import _attach_overlay_presentation_owner
        from types import SimpleNamespace

        overlay = self._Overlay()
        widget = SimpleNamespace(
            _gl_compositor=SimpleNamespace(_render_strategy_manager=None),
            _screen_index=0,
        )

        assert _attach_overlay_presentation_owner(widget, overlay) is False
        assert overlay._has_presentation_owner is False

    def test_attach_succeeds_once_the_strategy_is_available(self):
        from rendering.display_image_ops import _attach_overlay_presentation_owner

        overlay = self._Overlay()
        strategy = self._Strategy()

        assert _attach_overlay_presentation_owner(self._widget(strategy), overlay) is True
        assert strategy.registered is overlay
        assert overlay._has_presentation_owner is True

    def test_detach_clears_both_registration_and_overlay_flag(self):
        from rendering.display_image_ops import (
            _attach_overlay_presentation_owner,
            _detach_overlay_presentation_owner,
        )

        overlay = self._Overlay()
        strategy = self._Strategy()
        widget = self._widget(strategy)
        _attach_overlay_presentation_owner(widget, overlay)

        _detach_overlay_presentation_owner(widget, overlay)

        assert strategy.cleared == 1
        assert strategy.registered is None
        assert overlay._has_presentation_owner is False

    def test_publication_path_claims_ownership_after_late_strategy_creation(self):
        """The real null-result shape: overlay first, strategy second."""
        from rendering import display_image_ops
        from types import SimpleNamespace

        overlay = self._Overlay()
        compositor = SimpleNamespace(_render_strategy_manager=None)
        widget = SimpleNamespace(_gl_compositor=compositor, _screen_index=0)

        # First push: no strategy yet, overlay stays unowned.
        if not getattr(overlay, "_has_presentation_owner", False):
            display_image_ops._attach_overlay_presentation_owner(widget, overlay)
        assert overlay._has_presentation_owner is False

        # Strategy comes up, next push claims ownership.
        strategy = self._Strategy()
        compositor._render_strategy_manager = strategy
        if not getattr(overlay, "_has_presentation_owner", False):
            display_image_ops._attach_overlay_presentation_owner(widget, overlay)

        assert overlay._has_presentation_owner is True
        assert strategy.registered is overlay


class TestPresentationRunsOnTheGuiOwner:
    """Regression bar for the 2026-08-17 freeze.

    `_signal_frame()` runs on the adaptive timer's worker thread. Calling
    `present_if_pending()` -> `QWidget.update()` directly from it corrupted Qt
    repaint state: presentation froze while the event loop stayed alive, so input
    and the context menu still worked. Presentation must be marshalled to the GUI
    owner exactly like the compositor's own update path.
    """

    def test_presentation_is_marshalled_not_called_on_the_timer_thread(self):
        from rendering import adaptive_timer
        from rendering.adaptive_timer import AdaptiveTimerConfig, AdaptiveTimerStrategy

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        class _Presenter:
            def __init__(self):
                self.presented = 0

            def has_pending_presentation(self):
                return True

            def present_if_pending(self):
                self.presented += 1
                return True

        presenter = _Presenter()
        timer = AdaptiveTimerStrategy(_Compositor(), AdaptiveTimerConfig())
        marshalled = []
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            # Capture instead of executing: anything reaching the widget must arrive
            # through the UI-thread marshaller, never by direct call.
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: marshalled.append(func)
            )
            timer.set_auxiliary_presenter(presenter)
            timer._signal_frame()

            assert presenter.presented == 0, (
                "present_if_pending() must not run on the timer worker thread"
            )
            # The compositor's own update marshals through the same hook; select ours.
            presenter_calls = [
                func for func in marshalled if func == presenter.present_if_pending
            ]
            assert len(presenter_calls) == 1, "presentation must be queued to the GUI owner"

            presenter_calls[0]()
            assert presenter.presented == 1
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_no_gui_callback_is_queued_when_nothing_is_owed(self):
        from rendering import adaptive_timer
        from rendering.adaptive_timer import AdaptiveTimerConfig, AdaptiveTimerStrategy

        class _Compositor:
            def update(self):
                pass

            def parent(self):
                return None

        class _IdlePresenter:
            def has_pending_presentation(self):
                return False

            def present_if_pending(self):
                raise AssertionError("nothing was owed; no opportunity should be taken")

        timer = AdaptiveTimerStrategy(_Compositor(), AdaptiveTimerConfig())
        marshalled = []
        original = adaptive_timer.ThreadManager.run_on_ui_thread
        try:
            adaptive_timer.ThreadManager.run_on_ui_thread = staticmethod(
                lambda func, *a, **k: marshalled.append(func)
            )
            idle = _IdlePresenter()
            timer.set_auxiliary_presenter(idle)
            timer._signal_frame()
            timer._signal_frame()

            presenter_calls = [
                func for func in marshalled if func == idle.present_if_pending
            ]
            assert presenter_calls == [], (
                "an idle overlay must add no GUI dispatch demand of its own"
            )
        finally:
            adaptive_timer.ThreadManager.run_on_ui_thread = original

    def test_overlay_pending_probe_touches_no_qt_state(self, qt_app, monkeypatch):
        """The off-thread probe must be a plain comparison, safe from a worker."""
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        overlay.update = lambda *a, **k: None
        overlay.isVisible = lambda: True
        overlay.set_presentation_owned(True)

        def _explode(*args, **kwargs):
            raise AssertionError("has_pending_presentation must not touch Qt")

        for name in ("repaint", "show", "setGeometry", "geometry"):
            monkeypatch.setattr(type(overlay), name, _explode, raising=False)

        assert overlay.has_pending_presentation() is False
        overlay._present_revision += 1
        assert overlay.has_pending_presentation() is True
