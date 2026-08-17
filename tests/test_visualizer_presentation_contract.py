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
    """Mode-owned logical state that presentation coalescing must not disturb.

    Deliberately mode-sensitive. An earlier revision covered only
    bars/peaks/waveform/counts, which let "logical state is bit-identical" be
    claimed while the Bubble positional payload and the discrete event envelopes
    -- the state that actually carries the protected visible edge -- went
    unchecked. Presentation-side coverage still does not replace the versioned
    Bubble/Spectrum/replay goldens; see the P1 audit follow-up in Current_Plan.md.
    """

    def _seq(name):
        return [round(float(v), 9) for v in list(getattr(overlay, name, None) or [])]

    def _num(name):
        value = getattr(overlay, name, 0.0)
        try:
            return round(float(value or 0.0), 9)
        except (TypeError, ValueError):
            return 0.0

    return {
        # identity / shape
        "vis_mode": overlay._vis_mode,
        "bar_count": overlay._bar_count,
        "segments": overlay._segments,
        "accumulated_time": _num("_accumulated_time"),
        "set_state_total": int(overlay._perf_set_state_total),
        # spectrum-family
        "bars": _seq("_bars"),
        "peaks": _seq("_peaks"),
        # waveform-family
        "waveform": _seq("_waveform"),
        "prev_waveform": _seq("_prev_waveform"),
        "waveform_count": int(getattr(overlay, "_waveform_count", 0) or 0),
        # bubble payload -- carries the protected visible positional edge
        "bubble_count": int(getattr(overlay, "_bubble_count", 0) or 0),
        "bubble_pos_data": _seq("_bubble_pos_data"),
        "bubble_extra_data": _seq("_bubble_extra_data"),
        "bubble_trail_data": _seq("_bubble_trail_data"),
        # discrete event envelopes -- short-lived authored responses
        "kick_event_strength": _num("_line_kick_event_strength"),
        "snare_event_strength": _num("_line_snare_event_strength"),
        "kick_event_envelope": _num("_line_kick_event_envelope"),
        "snare_event_envelope": _num("_line_snare_event_envelope"),
        "transient_energy": _num("_transient_energy"),
        # line/sine smoothed band state
        "line_smoothed_bass": _num("_line_smoothed_bass"),
        "line_smoothed_mid": _num("_line_smoothed_mid"),
        "line_smoothed_high": _num("_line_smoothed_high"),
        # devcurve payload
        "devcurve_sample_count": int(getattr(overlay, "_devcurve_sample_count", 0) or 0),
        "devcurve_curve_bass": _seq("_devcurve_curve_bass"),
        "devcurve_curve_vocals": _seq("_devcurve_curve_vocals"),
        "devcurve_curve_mids": _seq("_devcurve_curve_mids"),
        "devcurve_curve_transients": _seq("_devcurve_curve_transients"),
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
        """Anti-amplification guard only.

        Necessary but **not sufficient**. A candidate can satisfy this while
        presenting stale state, raising state-to-paint age, or erasing a
        protected edge. Never cite it as evidence of correct presentation or
        preserved fidelity (P1 audit follow-up, Current_Plan.md).
        """
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


class TestMixedRefreshDeliveryPolicyModel:
    """HAZARD LIGHT ONLY -- an architectural policy model, not a delivery oracle.

    This class evaluates closed-form arithmetic over a fixed notional lane
    capacity. It does **not** execute Qt's dispatch, invalidation or composition
    path, and its target case models the visualizer contributing *zero*
    independent GUI dispatch demand -- a state no candidate that still owns a
    separate `QOpenGLWidget` can reach.

    Therefore it may **not** be cited as evidence that a production P2
    implementation fixes mixed-refresh delivery, and it cannot close P2.
    Equivalent installed dual-display evidence remains the authority (P5-F).

    It is retained because it still fails loudly if someone proposes a policy
    that provably starves a sibling display.
    """

    HAZARD_LIGHT_ONLY = True

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

    def test_stored_overlay_state_is_the_latest_publication_not_a_backlog(
        self, qt_app, monkeypatch
    ):
        """The overlay stores the newest publication rather than a queued backlog.

        Scope limit, stated deliberately: `update()` is stubbed here, so this
        proves only what the overlay *holds*. It does **not** prove a paint
        consumed it. Real paint-receipt coverage is owed by the P2 test bars in
        `Current_Plan.md` Step 3 and does not exist yet.
        """
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


class TestPresentationSourceLiveness:
    """A presentation source must be live whenever the visualizer is live.

    Replaces the earlier `TestPresentationOpportunitySourceEligibility`, which
    was wrong twice: it read R-61 as barring only *sole* dependence on
    `AdaptiveTimerStrategy` (R-62 disqualified it in **any** scope), and it
    asserted an idle overlay must keep one repaint request per publication --
    the very 1:1 coupling P2 exists to remove.

    These assertions are source-independent. They constrain liveness and
    survival; they prescribe no request ratio.
    """

    def test_adaptive_timer_is_transition_scoped_and_therefore_ineligible(self):
        """R-61/R-62: the render strategy starts for a transition and pauses after.

        Documentation bar. If these docstrings change, the disqualification in
        `Current_Plan.md` and `Docs/Guardrails/Visualizer_Presentation.md` must be
        re-verified against the new lifecycle before anything relies on it.
        """
        import inspect

        from rendering.gl_compositor import GLCompositorWidget

        start = inspect.getsource(GLCompositorWidget._start_render_timer)
        pause = inspect.getsource(GLCompositorWidget._pause_render_strategy)

        assert "during transitions" in start.lower()
        assert "after transition ends" in pause.lower()

    def test_no_visualizer_presentation_is_wired_to_the_render_strategy(self):
        """The disqualified source must not become the visualizer's presenter.

        Structural bar against reintroducing R-61/R-62. It permits any other
        presentation ownership design, including ones that reduce request count.
        """
        import inspect

        from rendering import adaptive_timer

        source = inspect.getsource(adaptive_timer)
        for forbidden in ("SpotifyBarsGLOverlay", "spotify_bars"):
            assert forbidden not in source, (
                f"adaptive_timer references {forbidden!r}: the transition-scoped "
                "render strategy is disqualified as a visualizer presentation "
                "source in any scope (R-61, R-62)"
            )

    @pytest.mark.qt
    def test_publications_keep_reaching_qt_with_no_presentation_source_running(
        self, qt_app, monkeypatch
    ):
        """Liveness, not abstinence: state must keep reaching Qt when nothing paces it.

        Asserts only that presentation does not stop. It deliberately sets no
        upper or lower bound tied to the publication count, so a future design
        may legitimately present fewer times than it publishes.
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

        assert paints, (
            "with no presentation source running the overlay stopped presenting "
            "entirely; a paused or absent source must never strand the visualizer "
            "(R-61)"
        )
        assert list(overlay._bars) == pytest.approx(_bar_series(12)[-1]), (
            "the latest publication must still be the state available to paint"
        )


@pytest.mark.qt
class TestModeSensitiveSuppressionEquivalence:
    """The suppression oracle must actually exercise mode-owned payload.

    P1 audit follow-up: the Spectrum-only suppression test leaves every Bubble
    and event field in `_logical_digest()` empty, so a strengthened digest proves
    nothing there. These cases publish real Bubble positional/extra/trail payload
    and discrete event envelopes so the added fields carry signal.

    This is presentation-side equivalence only. It does not replace the versioned
    Bubble/Spectrum/replay goldens.
    """

    def _bubble_publish(self, overlay, index, *, edge=False):
        """Publish a Bubble frame; `edge` injects a one-tick positional response."""
        base = ((index * 7) % 11) / 10.0
        overlay.set_state(
            rect=QRect(0, 0, 320, 180),
            bars=[base, base + 0.1, base],
            bar_count=3,
            segments=4,
            fill_color=QColor(255, 255, 255),
            border_color=QColor(255, 255, 255),
            fade=1.0,
            playing=True,
            visible=True,
            vis_mode="bubble",
            bubble_count=2,
            bubble_pos_data=[
                0.1 * index, 0.2, 1.0 if edge else 0.0, 1.0,
                0.3, 0.4 * index, 0.0, 1.0,
            ],
            bubble_extra_data=[0.5, 0.6, 0.7, 0.8, 0.1, 0.2, 0.3, 0.4],
            bubble_trail_data=[0.05 * index, 0.06, 0.07, 0.08],
            line_kick_event_strength=0.9 if edge else 0.0,
            transient_energy=0.8 if edge else 0.1,
        )

    def _run(self, monkeypatch, *, suppress):
        """Return (overlay, trajectory) -- a digest captured after every publication.

        Endpoint-only comparison cannot detect a transient divergence: a protected
        one-tick edge injected at publication 7 is already gone from final state by
        publication 19. The trajectory is what makes this oracle able to fail.
        """
        clock = _FakeClock()
        _install_fake_clock(monkeypatch, clock)
        overlay = SpotifyBarsGLOverlay(None)
        overlay.isVisible = lambda: True
        if suppress:
            overlay._request_frame_update = lambda **kwargs: None
        else:
            overlay.update = lambda *a, **k: None
        trajectory = []
        for index in range(20):
            self._bubble_publish(overlay, index, edge=(index == 7))
            trajectory.append(_logical_digest(overlay))
            clock.advance()
        return overlay, trajectory

    def test_bubble_payload_is_populated_so_the_digest_carries_signal(
        self, qt_app, monkeypatch
    ):
        """Guard the guard: an empty payload would make the oracle vacuous."""
        overlay, trajectory = self._run(monkeypatch, suppress=False)
        digest = _logical_digest(overlay)

        assert digest["vis_mode"] == "bubble"
        assert digest["bubble_count"] == 2
        assert digest["bubble_pos_data"], "bubble positional payload must be populated"
        assert digest["bubble_extra_data"], "bubble extra payload must be populated"
        assert digest["bubble_trail_data"], "bubble trail payload must be populated"
        # The injected one-tick edge must be visible somewhere in the trajectory,
        # otherwise the equivalence test below cannot detect its erasure.
        assert any(
            step["bubble_pos_data"] and step["bubble_pos_data"][2] > 0.5
            for step in trajectory
        ), "the protected one-tick edge never appeared in the trajectory"
        assert trajectory[-1]["bubble_pos_data"][2] == pytest.approx(0.0), (
            "the edge must be transient, so endpoint comparison alone cannot see it"
        )

    def test_bubble_logical_trajectory_identical_with_presentation_suppressed(
        self, qt_app, monkeypatch
    ):
        """Per-publication equivalence, not endpoint equivalence.

        Compares the full state trajectory so a transient divergence -- such as a
        protected one-tick Bubble edge being erased when presentation is
        requested -- fails the test. An endpoint-only oracle passes that mutation.
        """
        _, presented = self._run(monkeypatch, suppress=False)
        _, suppressed = self._run(monkeypatch, suppress=True)

        assert len(suppressed) == len(presented) == 20
        for index, (want, got) in enumerate(zip(presented, suppressed)):
            assert got == want, f"logical state diverged at publication {index}"
