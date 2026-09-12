"""Passive app-owned Qt event-loop timer-lateness measurement."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Qt

from core.logging.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class EventLoopLatenessSnapshot:
    samples: int
    retained_samples: int
    interval_ms: int
    p50_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    over_25_ms: int
    over_50_ms: int
    over_100_ms: int


class EventLoopStallRecorder(QObject):
    """Measure GUI-timer lateness without participating in runtime decisions."""

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        interval_ms: int = 50,
        report_interval_s: float = 15.0,
        window_size: int = 2048,
    ) -> None:
        super().__init__(parent)
        self._interval_ms = max(10, int(interval_ms))
        self._report_interval_s = max(1.0, float(report_interval_s))
        self._lateness_ms: deque[float] = deque(maxlen=max(32, int(window_size)))
        # Independent samples since the previous summary.  The rolling deque above
        # remains useful for ordinary long-horizon diagnostics, but causal/named
        # experiment windows must never infer a fresh interval from a percentile
        # that still contains pre-window history.  This bounded period deque lets
        # the logger expose both views without adding another timer/cadence.
        self._period_lateness_ms: deque[float] = deque(
            maxlen=max(32, int(window_size))
        )
        self._sample_count = 0
        self._expected_at: float | None = None
        self._last_report_at: float | None = None
        self._running = False
        self._scoring_reset_seq = 0
        self._scoring_label = "-"
        self._timer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timeout)

    @property
    def interval_ms(self) -> int:
        return self._interval_ms

    def start(self) -> None:
        if self._running:
            return

        now = time.perf_counter()
        self._running = True
        self._lateness_ms.clear()
        self._period_lateness_ms.clear()
        self._expected_at = now + self._interval_ms / 1000.0
        self._last_report_at = now
        self._timer.start()
        logger.info(
            "[PERF] [EVENT LOOP] recorder_start interval_ms=%d window=%d",
            self._interval_ms,
            self._lateness_ms.maxlen,
        )

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._timer.stop()
        self._emit_summary(outcome="stopped")
        self._expected_at = None

    def record_tick(self, now: float | None = None) -> float | None:
        """Record one timer delivery and return lateness in milliseconds."""
        if not self._running or self._expected_at is None:
            return None
        observed_at = time.perf_counter() if now is None else float(now)
        lateness_ms = max(0.0, (observed_at - self._expected_at) * 1000.0)
        self._lateness_ms.append(lateness_ms)
        self._period_lateness_ms.append(lateness_ms)
        self._sample_count += 1
        # Reset from the observed delivery so a single stall is not counted again
        # by an artificial catch-up sequence.
        self._expected_at = observed_at + self._interval_ms / 1000.0
        return lateness_ms

    def _snapshot_values(
        self,
        values_source: deque[float],
        *,
        samples: int,
    ) -> EventLoopLatenessSnapshot:
        values = sorted(values_source)

        def percentile(fraction: float) -> float:
            if not values:
                return 0.0
            index = min(
                len(values) - 1,
                max(0, int(round((len(values) - 1) * fraction))),
            )
            return float(values[index])

        return EventLoopLatenessSnapshot(
            samples=max(0, int(samples)),
            retained_samples=len(values),
            interval_ms=self._interval_ms,
            p50_ms=percentile(0.50),
            p90_ms=percentile(0.90),
            p95_ms=percentile(0.95),
            p99_ms=percentile(0.99),
            max_ms=max(values, default=0.0),
            over_25_ms=sum(value > 25.0 for value in values),
            over_50_ms=sum(value > 50.0 for value in values),
            over_100_ms=sum(value > 100.0 for value in values),
        )

    def snapshot(self) -> EventLoopLatenessSnapshot:
        """Return the bounded rolling diagnostic view."""

        return self._snapshot_values(
            self._lateness_ms,
            samples=self._sample_count,
        )

    def period_snapshot(self) -> EventLoopLatenessSnapshot:
        """Return samples collected since the previous emitted summary/reset.

        Unlike :meth:`snapshot`, this view never overlaps an earlier report once
        ``_emit_summary`` has completed.  It exists specifically so offline causal
        scorers can use independent report periods instead of repeatedly scoring a
        ~102 s rolling history as if each report described a fresh interval.
        """

        return self._snapshot_values(
            self._period_lateness_ms,
            samples=len(self._period_lateness_ms),
        )

    def reset_scoring_window(self, label: str = "") -> int:
        """Start a fresh diagnostic scoring window without restarting the timer.

        The ABC experiment uses this exactly once at each named scored-window
        boundary.  Clearing both retained histories prevents switch/recreation
        transients from contaminating the subsequent steady window while leaving
        timer delivery, expected-deadline continuity and the global sample counter
        untouched.  Re-anchor the report clock so the first period summary covers
        a real post-boundary interval rather than an arbitrary fraction of one.
        """

        self._lateness_ms.clear()
        self._period_lateness_ms.clear()
        self._scoring_reset_seq += 1
        self._scoring_label = str(label or "-").strip() or "-"
        if self._running:
            self._last_report_at = time.perf_counter()
        logger.info(
            "[PERF] [EVENT LOOP] scoring_window_reset seq=%d label=%s "
            "samples_total=%d epoch=%.3f",
            self._scoring_reset_seq,
            self._scoring_label,
            self._sample_count,
            time.time(),
        )
        return self._scoring_reset_seq

    def _on_timeout(self) -> None:
        now = time.perf_counter()
        self.record_tick(now)
        if (
            self._last_report_at is None
            or now - self._last_report_at >= self._report_interval_s
        ):
            self._emit_summary(outcome="sampled")
            self._last_report_at = now

    def _emit_summary(self, *, outcome: str) -> None:
        snapshot = self.snapshot()
        period = self.period_snapshot()
        now = time.perf_counter()
        wall_epoch = time.time()
        period_elapsed_s = (
            max(0.0, now - self._last_report_at)
            if self._last_report_at is not None
            else 0.0
        )
        logger.info(
            "[PERF] [EVENT LOOP] summary samples=%d retained=%d interval_ms=%d "
            "late_p50_ms=%.2f late_p90_ms=%.2f late_p95_ms=%.2f "
            "late_p99_ms=%.2f late_max_ms=%.2f over_25_ms=%d "
            "over_50_ms=%d over_100_ms=%d "
            "period_samples=%d period_elapsed_s=%.3f period_epoch=%.3f "
            "period_p50_ms=%.2f period_p90_ms=%.2f "
            "period_p95_ms=%.2f period_p99_ms=%.2f period_max_ms=%.2f "
            "period_over_25_ms=%d period_over_50_ms=%d period_over_100_ms=%d "
            "score_reset_seq=%d score_label=%s outcome=%s",
            snapshot.samples,
            snapshot.retained_samples,
            snapshot.interval_ms,
            snapshot.p50_ms,
            snapshot.p90_ms,
            snapshot.p95_ms,
            snapshot.p99_ms,
            snapshot.max_ms,
            snapshot.over_25_ms,
            snapshot.over_50_ms,
            snapshot.over_100_ms,
            period.retained_samples,
            period_elapsed_s,
            wall_epoch,
            period.p50_ms,
            period.p90_ms,
            period.p95_ms,
            period.p99_ms,
            period.max_ms,
            period.over_25_ms,
            period.over_50_ms,
            period.over_100_ms,
            self._scoring_reset_seq,
            self._scoring_label,
            outcome,
        )
        self._period_lateness_ms.clear()