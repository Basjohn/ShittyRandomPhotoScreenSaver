"""P3 attribution probe: sampled in-callback self-time inside set_state().

Bars for the diagnostic itself. The probe must be observational only: PERF-off
must take no timestamps and change no scheduling, an early-return publication
must contribute nothing rather than a partial sample, and category 4 must
measure only the direct update() call so its downstream delivery cost stays
with Bad Smell 1 / P2.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay, _P3_SAMPLE_STRIDE


def _publish(overlay, bars, *, vis_mode="spectrum", visible=True, **kw):
    overlay.set_state(
        rect=QRect(0, 0, 320, 180),
        bars=list(bars),
        bar_count=len(bars),
        segments=4,
        fill_color=QColor(255, 255, 255),
        border_color=QColor(255, 255, 255),
        fade=1.0,
        playing=True,
        visible=visible,
        vis_mode=vis_mode,
        **kw,
    )


def _overlay(monkeypatch, *, perf: bool):
    overlay = SpotifyBarsGLOverlay(None)
    overlay.update = lambda *a, **k: None
    overlay.isVisible = lambda: True
    monkeypatch.setattr(overlay, "_perf_metrics_enabled", perf, raising=False)
    return overlay


@pytest.mark.qt
class TestP3ProbeIsObservational:
    def test_perf_off_takes_no_samples_and_creates_no_state(self, qt_app, monkeypatch):
        overlay = _overlay(monkeypatch, perf=False)

        for index in range(_P3_SAMPLE_STRIDE * 3):
            _publish(overlay, [0.1 * (index % 5), 0.2, 0.3])

        assert overlay._p3_sample_counter == 0, "PERF-off must not advance the sampler"
        assert overlay._p3_steady == {}
        assert overlay._p3_activation == {}

    def test_perf_off_and_perf_on_integrate_identically(self, qt_app, monkeypatch):
        """The probe must not change logical outcomes, only observe them."""
        series = [[0.1 * (i % 7), 0.2, 0.3] for i in range(_P3_SAMPLE_STRIDE * 2)]

        off = _overlay(monkeypatch, perf=False)
        for bars in series:
            _publish(off, bars)

        on = _overlay(monkeypatch, perf=True)
        for bars in series:
            _publish(on, bars)

        assert on._perf_set_state_total == off._perf_set_state_total
        assert list(on._bars) == pytest.approx(list(off._bars))
        assert list(on._peaks) == pytest.approx(list(off._peaks))

    def test_sampling_is_strided_not_every_publication(self, qt_app, monkeypatch):
        overlay = _overlay(monkeypatch, perf=True)
        count = _P3_SAMPLE_STRIDE * 4

        for index in range(count):
            _publish(overlay, [0.1 * (index % 5), 0.2, 0.3])

        activation = int(overlay._p3_activation.get("samples", 0))
        steady = int(overlay._p3_steady.get("samples", 0))

        # A bounded activation window is force-sampled, then sampling is strided.
        assert activation <= 4, "the activation window must be bounded"
        assert steady <= count // _P3_SAMPLE_STRIDE, "steady sampling must be strided"
        assert (activation + steady) < count // 4, (
            "observer cost must stay a small fraction of publications"
        )


@pytest.mark.qt
class TestP3AccountingIntegrity:
    def _drive(self, overlay, count):
        for index in range(count):
            _publish(overlay, [0.1 * (index % 5), 0.2, 0.3])

    def test_regions_are_non_negative_and_sum_within_total(self, qt_app, monkeypatch):
        overlay = _overlay(monkeypatch, perf=True)
        self._drive(overlay, _P3_SAMPLE_STRIDE * 6)

        acc = overlay._p3_steady if overlay._p3_steady.get("samples") else overlay._p3_activation
        assert int(acc.get("samples", 0)) > 0

        regions = (
            "temporal",
            "static_config",
            "dynamic_payload",
            "qt_geometry",
            "present_request",
            "residual",
        )
        for name in regions:
            assert acc.get(name, 0) >= 0, f"{name} must never be negative"

        # Regions are contiguous slices of the same wall interval, so their sum
        # cannot exceed the measured total.
        assert sum(acc.get(name, 0) for name in regions) <= acc["total"] + 1_000

    def test_categories_are_accumulated_from_non_contiguous_slices(
        self, qt_app, monkeypatch
    ):
        """Categories interleave in set_state(); each is a sum of separated slices.

        Regression bar for the mislabelled first probe, whose contiguous source
        ranges mixed static config into temporal, bubble/devcurve payload into
        static config, and Spectrum hysteresis/peaks into dynamic payload.
        """
        import inspect

        from widgets import spotify_bars_gl_overlay as mod

        source = inspect.getsource(mod.SpotifyBarsGLOverlay.set_state)
        for key, minimum in (
            ("static_config", 2),
            ("dynamic_payload", 2),
            ("temporal", 2),
        ):
            found = source.count(f'_p3_slice(_p3_regions, "{key}"')
            assert found >= minimum, (
                f"{key} must be accumulated from at least {minimum} separated "
                f"slices; found {found}. Contiguous slicing reintroduces the "
                "semantic contamination this probe exists to avoid."
            )

    def test_probe_helpers_are_not_present_in_constructor(self, qt_app, monkeypatch):
        """Slice anchors must land in set_state(), not other methods.

        An earlier revision matched a comment that also appears in __init__ and
        injected undefined probe locals into the constructor.
        """
        import inspect

        from widgets import spotify_bars_gl_overlay as mod

        init_source = inspect.getsource(mod.SpotifyBarsGLOverlay.__init__)
        assert "_p3_slice" not in init_source
        assert "_p3_regions" not in init_source

    def test_early_return_contributes_no_partial_sample(self, qt_app, monkeypatch):
        """A rejected publication must not add region time with no sample divisor.

        `set_state()` returns early on an invisible frame. Committing region times
        before that point would inflate every mean, because the divisor only
        increments at the end.
        """
        overlay = _overlay(monkeypatch, perf=True)

        # Land exactly on a sampled publication, then reject it.
        for _ in range(_P3_SAMPLE_STRIDE - 1):
            _publish(overlay, [0.2, 0.3, 0.4])
        before_steady = dict(overlay._p3_steady)
        before_activation = dict(overlay._p3_activation)

        _publish(overlay, [0.2, 0.3, 0.4], visible=False)

        assert overlay._p3_steady == before_steady, "rejected frame contributed region time"
        assert overlay._p3_activation == before_activation

    def test_activation_samples_are_separated_from_steady_state(
        self, qt_app, monkeypatch
    ):
        """Initialization spikes must not distort steady-state conclusions."""
        overlay = _overlay(monkeypatch, perf=True)

        # The first accepted publications are force-sampled into the activation
        # bucket, so initialization cost never lands in the steady-state mean.
        self._drive(overlay, 4)
        assert int(overlay._p3_activation.get("samples", 0)) == 4
        assert int(overlay._p3_steady.get("samples", 0)) == 0

        # Once the activation window closes, samples accrue to steady state only.
        self._drive(overlay, _P3_SAMPLE_STRIDE * 3)
        assert int(overlay._p3_activation.get("samples", 0)) == 4, (
            "the activation bucket must stop growing after its window closes"
        )
        assert int(overlay._p3_steady.get("samples", 0)) >= 1
