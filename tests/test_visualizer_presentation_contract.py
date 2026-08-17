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
