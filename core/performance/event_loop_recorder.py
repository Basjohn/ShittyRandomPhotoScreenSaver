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
        self._sample_count = 0
        self._expected_at: float | None = None
        self._last_report_at: float | None = None
        self._running = False
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
        self._sample_count += 1
        # Reset from the observed delivery so a single stall is not counted again
        # by an artificial catch-up sequence.
        self._expected_at = observed_at + self._interval_ms / 1000.0
        return lateness_ms

    def snapshot(self) -> EventLoopLatenessSnapshot:
        values = sorted(self._lateness_ms)

        def percentile(fraction: float) -> float:
            if not values:
                return 0.0
            index = min(
                len(values) - 1,
                max(0, int(round((len(values) - 1) * fraction))),
            )
            return float(values[index])

        return EventLoopLatenessSnapshot(
            samples=self._sample_count,
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
        logger.info(
            "[PERF] [EVENT LOOP] summary samples=%d retained=%d interval_ms=%d "
            "late_p50_ms=%.2f late_p90_ms=%.2f late_p95_ms=%.2f "
            "late_p99_ms=%.2f late_max_ms=%.2f over_25_ms=%d "
            "over_50_ms=%d over_100_ms=%d outcome=%s",
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
            outcome,
        )