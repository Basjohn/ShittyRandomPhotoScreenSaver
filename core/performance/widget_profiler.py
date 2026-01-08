"""Widget-level performance instrumentation helpers.

This module centralises the lightweight counters we emit for overlay widgets
so we can spot idle timers or expensive paint events. Metrics are aggregated
per widget/metric pair and periodically flushed to the dedicated
``perf_widgets.log`` file when ``SRPSS_PERF_METRICS`` is enabled.
"""
from __future__ import annotations

import atexit
import threading
import time
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.logging.tags import TAG_WIDGET_PERF


__all__ = [
    "widget_timer_sample",
    "widget_paint_sample",
    "record_widget_timer_result",
    "record_widget_paint_result",
    "flush_widget_perf_metrics",
]


_LOGGER = get_logger("widgets.perf")
_BUCKET_LOCK = threading.Lock()
_BUCKETS: Dict[Tuple[str, str, str], "_PerfBucket"] = {}
_LOG_INTERVAL_SECONDS = 5.0
_MAX_CALLS_BEFORE_LOG = 50
_SLOW_THRESHOLDS_MS = {
    "timer": 16.0,  # >1 frame at 60Hz = suspicious timer callback
    "paint": 6.0,   # paints longer than ~6ms risk visible hitching
}


@dataclass
class _PerfBucket:
    widget: str
    metric: str
    kind: str  # "timer" or "paint"
    call_count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    slow_count: int = 0
    interval_ms: Optional[int] = None
    area_px: Optional[int] = None
    last_log_monotonic: float = field(default_factory=time.monotonic)

    def reset(self, now_monotonic: float | None = None) -> None:
        self.call_count = 0
        self.total_ms = 0.0
        self.max_ms = 0.0
        self.slow_count = 0
        if now_monotonic is not None:
            self.last_log_monotonic = now_monotonic


class _WidgetPerfContext(AbstractContextManager["_WidgetPerfContext"]):
    __slots__ = (
        "_enabled",
        "_start",
        "_widget_name",
        "_metric_name",
        "_kind",
        "_interval_ms",
        "_area_px",
    )

    def __init__(
        self,
        widget: object,
        metric_name: str,
        kind: str,
        interval_ms: Optional[int] = None,
    ) -> None:
        self._enabled = is_perf_metrics_enabled()
        if not self._enabled:
            return
        self._start = time.perf_counter()
        self._widget_name = _coerce_widget_name(widget)
        self._metric_name = metric_name
        self._kind = kind
        self._interval_ms = interval_ms
        self._area_px: Optional[int] = None
        if kind == "paint":
            self._area_px = _safe_widget_area(widget)

    def __exit__(self, exc_type, exc, exc_tb) -> bool:
        if not self._enabled:
            return False
        duration_ms = (time.perf_counter() - self._start) * 1000.0
        if self._kind == "timer":
            record_widget_timer_result(
                self._widget_name,
                self._metric_name,
                duration_ms,
                self._interval_ms,
            )
        else:
            record_widget_paint_result(
                self._widget_name,
                self._metric_name,
                duration_ms,
                self._area_px,
            )
        return False


def widget_timer_sample(
    widget: object,
    metric_name: str,
    interval_ms: Optional[int] = None,
) -> _WidgetPerfContext:
    """Context manager that records a timer callback duration."""

    return _WidgetPerfContext(widget, metric_name, "timer", interval_ms)


def widget_paint_sample(
    widget: object,
    metric_name: str,
) -> _WidgetPerfContext:
    """Context manager that records a paint event duration."""

    return _WidgetPerfContext(widget, metric_name, "paint")


def record_widget_timer_result(
    widget_name: str,
    metric_name: str,
    duration_ms: float,
    interval_ms: Optional[int],
) -> None:
    """Record an ad-hoc timer measurement (without using the context manager)."""

    _record_sample(widget_name, metric_name, "timer", duration_ms, interval_ms, None)


def record_widget_paint_result(
    widget_name: str,
    metric_name: str,
    duration_ms: float,
    area_px: Optional[int],
) -> None:
    """Record an ad-hoc paint measurement (without using the context manager)."""

    _record_sample(widget_name, metric_name, "paint", duration_ms, None, area_px)


def flush_widget_perf_metrics(force: bool = False) -> None:
    """Flush any pending buckets to the perf log."""

    if not is_perf_metrics_enabled():
        return
    now = time.monotonic()
    buckets_copy: list[_PerfBucket] = []
    with _BUCKET_LOCK:
        for key, bucket in _BUCKETS.items():
            if bucket.call_count == 0:
                continue
            if force or (now - bucket.last_log_monotonic) >= _LOG_INTERVAL_SECONDS:
                buckets_copy.append((_copy_bucket(bucket)))
                bucket.reset(now)
    for bucket in buckets_copy:
        _emit_bucket(bucket)


def _record_sample(
    widget_name: str,
    metric_name: str,
    kind: str,
    duration_ms: float,
    interval_ms: Optional[int],
    area_px: Optional[int],
) -> None:
    if not is_perf_metrics_enabled():
        return

    now = time.monotonic()
    key = (widget_name, metric_name, kind)
    with _BUCKET_LOCK:
        bucket = _BUCKETS.get(key)
        if bucket is None:
            bucket = _PerfBucket(widget=widget_name, metric=metric_name, kind=kind)
            _BUCKETS[key] = bucket
        bucket.call_count += 1
        bucket.total_ms += duration_ms
        if duration_ms > bucket.max_ms:
            bucket.max_ms = duration_ms
        if interval_ms is not None:
            bucket.interval_ms = interval_ms
        if area_px is not None:
            bucket.area_px = area_px
        slow_threshold = _SLOW_THRESHOLDS_MS.get(kind, 0.0)
        if slow_threshold and duration_ms >= slow_threshold:
            bucket.slow_count += 1

        should_emit = (
            bucket.call_count >= _MAX_CALLS_BEFORE_LOG
            or (now - bucket.last_log_monotonic) >= _LOG_INTERVAL_SECONDS
            or duration_ms >= slow_threshold * 4
        )
        if should_emit:
            snapshot = _copy_bucket(bucket)
            bucket.reset(now)
        else:
            snapshot = None

    if snapshot is not None:
        _emit_bucket(snapshot)


def _emit_bucket(bucket: _PerfBucket) -> None:
    if bucket.call_count <= 0:
        return
    avg_ms = bucket.total_ms / bucket.call_count if bucket.call_count else 0.0
    summary = (
        f"{TAG_WIDGET_PERF} widget={bucket.widget} kind={bucket.kind} metric={bucket.metric} "
        f"calls={bucket.call_count} avg_ms={avg_ms:.2f} max_ms={bucket.max_ms:.2f} "
        f"slow_calls={bucket.slow_count}"
    )
    if bucket.interval_ms is not None:
        summary += f" interval_ms={bucket.interval_ms}"
    if bucket.area_px is not None:
        summary += f" area_px={bucket.area_px}"
    _LOGGER.info(summary)


def _coerce_widget_name(widget: object) -> str:
    try:
        overlay_name = getattr(widget, "_overlay_name", None)
        if overlay_name:
            return str(overlay_name)
    except Exception:
        overlay_name = None
    try:
        return widget.__class__.__name__
    except Exception:
        return "UnknownWidget"


def _safe_widget_area(widget: object) -> Optional[int]:
    try:
        width = int(getattr(widget, "width", lambda: 0)())
        height = int(getattr(widget, "height", lambda: 0)())
        if width > 0 and height > 0:
            return width * height
    except Exception:
        return None
    return None


def _copy_bucket(bucket: _PerfBucket) -> _PerfBucket:
    return _PerfBucket(
        widget=bucket.widget,
        metric=bucket.metric,
        kind=bucket.kind,
        call_count=bucket.call_count,
        total_ms=bucket.total_ms,
        max_ms=bucket.max_ms,
        slow_count=bucket.slow_count,
        interval_ms=bucket.interval_ms,
        area_px=bucket.area_px,
        last_log_monotonic=bucket.last_log_monotonic,
    )


atexit.register(flush_widget_perf_metrics, True)
