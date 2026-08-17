"""Adaptive timer strategy with hybrid state management.

This module provides an optimized timer that:
- Runs continuously during transitions (no thread churn)
- Enters low-power pause state after transitions end
- Goes to deep sleep after idle timeout
- Uses atomic operations for state transitions (no locks in hot path)

Fully integrated with ThreadManager, ResourceManager following project policies.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import ThreadManager, ThreadPoolType
from core.resources.manager import ResourceManager
from utils.lockfree.spsc_queue import SPSCQueue
from PySide6.QtCore import QMetaObject, Qt, QThread

try:
    from shiboken6 import Shiboken
except Exception:  # pragma: no cover - shiboken may be unavailable in some test contexts
    Shiboken = None

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

logger = get_logger(__name__)
_QT_UPDATE_FALLBACK_WARNED = False
_PENDING_UPDATE_LOG_AFTER_MS = 250.0
_PENDING_UPDATE_LOG_INTERVAL_MS = 1000.0
_DEADLINE_SLEEP_CAP_S = 0.004
_DEADLINE_YIELD_WINDOW_S = 0.00075
_DELIVERY_SAMPLE_WINDOW = 4096
_DELIVERY_ACTIVE_SAMPLE_INTERVAL_S = 0.100


def _safe_attr(widget, name: str, default=None):
    try:
        return getattr(widget, name, default)
    except Exception:
        return default


def _delivery_deque(widget, name: str):
    """Return one bounded perf-only delivery sample deque owned by the compositor."""
    samples = _safe_attr(widget, name)
    if not isinstance(samples, deque):
        samples = deque(maxlen=_DELIVERY_SAMPLE_WINDOW)
        try:
            setattr(widget, name, samples)
        except Exception:
            pass
    return samples


def _reset_delivery_perf_window(widget) -> None:
    """Start one transition-local passive delivery attribution window."""
    if widget is None or not is_perf_metrics_enabled():
        return
    now = time.perf_counter()
    try:
        seq = int(_safe_attr(widget, "_srpss_delivery_window_seq", 0) or 0) + 1
        setattr(widget, "_srpss_delivery_window_seq", seq)
        setattr(widget, "_srpss_delivery_window_start_ts", now)
        setattr(widget, "_srpss_delivery_wakeups", 0)
        setattr(widget, "_srpss_delivery_deadline_wakeups", 0)
        setattr(widget, "_srpss_delivery_immediate_requests", 0)
        setattr(widget, "_srpss_delivery_accepted", 0)
        setattr(widget, "_srpss_delivery_dispatch_pending_skips", 0)
        setattr(widget, "_srpss_delivery_paint_pending_skips", 0)
        setattr(widget, "_srpss_delivery_unknown_skips", 0)
        setattr(widget, "_srpss_delivery_dispatch_unknown", 0)
        setattr(widget, "_srpss_delivery_window_active_last", None)
        setattr(widget, "_srpss_delivery_window_active_changes", 0)
        setattr(widget, "_srpss_delivery_window_active_changed_ts", now)
        setattr(widget, "_srpss_delivery_window_active_last_sample_ts", 0.0)
        for name in (
            "_srpss_delivery_wake_late_ms",
            "_srpss_delivery_dispatch_ms",
            "_srpss_delivery_paint_pending_ms",
            "_srpss_delivery_dispatch_skip_age_ms",
            "_srpss_delivery_paint_skip_age_ms",
            "_srpss_delivery_dispatch_active_ms",
            "_srpss_delivery_dispatch_inactive_ms",
            "_srpss_delivery_paint_active_ms",
            "_srpss_delivery_paint_inactive_ms",
        ):
            setattr(widget, name, deque(maxlen=_DELIVERY_SAMPLE_WINDOW))
    except Exception:
        # Diagnostics must never become a delivery failure source.
        pass


def _record_delivery_window_active(widget, now_ts: float) -> bool | None:
    """Low-rate top-level Qt activation sample, only from the GUI owner thread."""
    try:
        owner_thread = widget.thread() if hasattr(widget, "thread") else None
        if owner_thread is not None and QThread.currentThread() is not owner_thread:
            return None
        previous = _safe_attr(widget, "_srpss_delivery_window_active_last", None)
        last_sample_ts = float(
            _safe_attr(widget, "_srpss_delivery_window_active_last_sample_ts", 0.0) or 0.0
        )
        if (
            previous is not None
            and last_sample_ts > 0.0
            and now_ts - last_sample_ts < _DELIVERY_ACTIVE_SAMPLE_INTERVAL_S
        ):
            return bool(previous)
        window = widget.window() if hasattr(widget, "window") else None
        if window is None or not hasattr(window, "isActiveWindow"):
            return previous if previous is None else bool(previous)
        active = bool(window.isActiveWindow())
        setattr(widget, "_srpss_delivery_window_active_last_sample_ts", now_ts)
        if previous is not None and bool(previous) != active:
            setattr(
                widget,
                "_srpss_delivery_window_active_changes",
                int(_safe_attr(widget, "_srpss_delivery_window_active_changes", 0) or 0) + 1,
            )
            setattr(widget, "_srpss_delivery_window_active_changed_ts", now_ts)
        elif previous is None:
            setattr(widget, "_srpss_delivery_window_active_changed_ts", now_ts)
        setattr(widget, "_srpss_delivery_window_active_last", active)
        return active
    except Exception:
        return None


def _record_delivery_wake(
    widget,
    *,
    deadline_ts: float | None,
    immediate: bool,
) -> None:
    if widget is None or not is_perf_metrics_enabled():
        return
    try:
        setattr(
            widget,
            "_srpss_delivery_wakeups",
            int(_safe_attr(widget, "_srpss_delivery_wakeups", 0) or 0) + 1,
        )
        if immediate:
            setattr(
                widget,
                "_srpss_delivery_immediate_requests",
                int(_safe_attr(widget, "_srpss_delivery_immediate_requests", 0) or 0) + 1,
            )
            setattr(widget, "_srpss_timer_last_wake_late_ms", None)
            return
        setattr(
            widget,
            "_srpss_delivery_deadline_wakeups",
            int(_safe_attr(widget, "_srpss_delivery_deadline_wakeups", 0) or 0) + 1,
        )
        wake_late_ms = None
        if isinstance(deadline_ts, (int, float)) and deadline_ts > 0.0:
            wake_late_ms = max(0.0, (time.perf_counter() - float(deadline_ts)) * 1000.0)
            _delivery_deque(widget, "_srpss_delivery_wake_late_ms").append(wake_late_ms)
        setattr(widget, "_srpss_timer_last_wake_late_ms", wake_late_ms)
    except Exception:
        pass


def _record_delivery_result(widget, accepted_update: bool) -> None:
    if widget is None or not is_perf_metrics_enabled():
        return
    try:
        if accepted_update:
            setattr(
                widget,
                "_srpss_delivery_accepted",
                int(_safe_attr(widget, "_srpss_delivery_accepted", 0) or 0) + 1,
            )
            return
        stage = str(_safe_attr(widget, "_srpss_timer_last_skip_stage", "unknown") or "unknown")
        counter = {
            "dispatch": "_srpss_delivery_dispatch_pending_skips",
            "paint": "_srpss_delivery_paint_pending_skips",
        }.get(stage, "_srpss_delivery_unknown_skips")
        setattr(widget, counter, int(_safe_attr(widget, counter, 0) or 0) + 1)
    except Exception:
        pass


def _record_delivery_paint_start(widget, paint_start_ts: float) -> None:
    """Record exact dispatch->paint latency at the existing paint-start boundary."""
    if widget is None or not is_perf_metrics_enabled():
        return
    try:
        dispatched_ts = float(_safe_attr(widget, "_srpss_timer_update_dispatched_ts", 0.0) or 0.0)
        pending_since = float(_safe_attr(widget, "_srpss_timer_update_pending_since", 0.0) or 0.0)
        if pending_since <= 0.0:
            return
        if dispatched_ts <= 0.0:
            setattr(
                widget,
                "_srpss_delivery_dispatch_unknown",
                int(_safe_attr(widget, "_srpss_delivery_dispatch_unknown", 0) or 0) + 1,
            )
            return
        paint_pending_ms = max(0.0, (float(paint_start_ts) - dispatched_ts) * 1000.0)
        _delivery_deque(widget, "_srpss_delivery_paint_pending_ms").append(paint_pending_ms)
        active = _safe_attr(widget, "_srpss_timer_window_active_at_dispatch", None)
        if active is True:
            _delivery_deque(widget, "_srpss_delivery_paint_active_ms").append(paint_pending_ms)
        elif active is False:
            _delivery_deque(widget, "_srpss_delivery_paint_inactive_ms").append(paint_pending_ms)
    except Exception:
        pass


def _delivery_percentile(values, percentile: float) -> float:
    samples = [float(value) for value in values if isinstance(value, (int, float))]
    if not samples:
        return 0.0
    samples.sort()
    index = min(
        len(samples) - 1,
        max(0, int(round((len(samples) - 1) * float(percentile)))),
    )
    return samples[index]


def _delivery_stats(widget, name: str) -> tuple[int, float, float, float]:
    values = list(_safe_attr(widget, name, ()) or ())
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return (
        len(numeric),
        _delivery_percentile(numeric, 0.50),
        _delivery_percentile(numeric, 0.95),
        max(numeric, default=0.0),
    )


def _delivery_transition_label(widget) -> str:
    label = str(_safe_attr(widget, "_current_transition_name", "") or "").strip()
    if label:
        return "_".join(label.split())
    paint_metrics = _safe_attr(widget, "_paint_metrics")
    label = str(_safe_attr(paint_metrics, "label", "") or "").strip()
    return "_".join(label.split()) if label else "<none>"


def _delivery_screen(widget):
    try:
        parent = widget.parent() if widget is not None else None
    except Exception:
        parent = None
    value = _safe_attr(parent, "screen_index", _safe_attr(widget, "_screen_index", "?"))
    return value


def _log_delivery_perf_window(widget, *, outcome: str, target_fps: int) -> None:
    """Emit two bounded summary records; never log one record per frame."""
    if widget is None or not is_perf_metrics_enabled():
        return
    start_ts = float(_safe_attr(widget, "_srpss_delivery_window_start_ts", 0.0) or 0.0)
    if start_ts <= 0.0:
        return
    now = time.perf_counter()
    elapsed_ms = max(0.0, (now - start_ts) * 1000.0)
    seq = int(_safe_attr(widget, "_srpss_delivery_window_seq", 0) or 0)
    wakeups = int(_safe_attr(widget, "_srpss_delivery_wakeups", 0) or 0)
    accepted = int(_safe_attr(widget, "_srpss_delivery_accepted", 0) or 0)
    dispatch_skips = int(_safe_attr(widget, "_srpss_delivery_dispatch_pending_skips", 0) or 0)
    paint_skips = int(_safe_attr(widget, "_srpss_delivery_paint_pending_skips", 0) or 0)
    unknown_skips = int(_safe_attr(widget, "_srpss_delivery_unknown_skips", 0) or 0)
    acceptance_pct = (accepted / wakeups * 100.0) if wakeups > 0 else 0.0
    wake_n, wake_p50, wake_p95, wake_max = _delivery_stats(widget, "_srpss_delivery_wake_late_ms")
    dispatch_n, dispatch_p50, dispatch_p95, dispatch_max = _delivery_stats(widget, "_srpss_delivery_dispatch_ms")
    paint_n, paint_p50, paint_p95, paint_max = _delivery_stats(widget, "_srpss_delivery_paint_pending_ms")
    dispatch_skip_n, _, dispatch_skip_p95, dispatch_skip_max = _delivery_stats(
        widget, "_srpss_delivery_dispatch_skip_age_ms"
    )
    paint_skip_n, _, paint_skip_p95, paint_skip_max = _delivery_stats(
        widget, "_srpss_delivery_paint_skip_age_ms"
    )
    active_dispatch_n, _, active_dispatch_p95, _ = _delivery_stats(widget, "_srpss_delivery_dispatch_active_ms")
    inactive_dispatch_n, _, inactive_dispatch_p95, _ = _delivery_stats(widget, "_srpss_delivery_dispatch_inactive_ms")
    active_paint_n, _, active_paint_p95, _ = _delivery_stats(widget, "_srpss_delivery_paint_active_ms")
    inactive_paint_n, _, inactive_paint_p95, _ = _delivery_stats(widget, "_srpss_delivery_paint_inactive_ms")
    active_last = _safe_attr(widget, "_srpss_delivery_window_active_last", None)
    active_text = "na" if active_last is None else str(int(bool(active_last)))
    active_changed_ts = float(_safe_attr(widget, "_srpss_delivery_window_active_changed_ts", 0.0) or 0.0)
    active_age_ms = max(0.0, (now - active_changed_ts) * 1000.0) if active_changed_ts > 0.0 else -1.0
    common = (
        _delivery_screen(widget),
        _delivery_transition_label(widget),
        seq,
        str(outcome or "unknown"),
        int(target_fps or 0),
        elapsed_ms,
    )
    logger.info(
        "[PERF][DELIVERY_STAGE][CADENCE] screen=%s transition=%s window=%d outcome=%s "
        "target_hz=%d elapsed_ms=%.1f wakeups=%d deadline_wakeups=%d immediate_requests=%d "
        "accepted=%d acceptance_pct=%.2f dispatch_pending_skips=%d paint_pending_skips=%d "
        "unknown_skips=%d wake_late_n=%d wake_late_p50_ms=%.3f wake_late_p95_ms=%.3f "
        "wake_late_max_ms=%.3f dispatch_skip_n=%d dispatch_skip_age_p95_ms=%.3f "
        "dispatch_skip_age_max_ms=%.3f paint_skip_n=%d paint_skip_age_p95_ms=%.3f "
        "paint_skip_age_max_ms=%.3f",
        *common,
        wakeups,
        int(_safe_attr(widget, "_srpss_delivery_deadline_wakeups", 0) or 0),
        int(_safe_attr(widget, "_srpss_delivery_immediate_requests", 0) or 0),
        accepted,
        acceptance_pct,
        dispatch_skips,
        paint_skips,
        unknown_skips,
        wake_n,
        wake_p50,
        wake_p95,
        wake_max,
        dispatch_skip_n,
        dispatch_skip_p95,
        dispatch_skip_max,
        paint_skip_n,
        paint_skip_p95,
        paint_skip_max,
    )
    logger.info(
        "[PERF][DELIVERY_STAGE][GUI] screen=%s transition=%s window=%d outcome=%s "
        "target_hz=%d elapsed_ms=%.1f dispatch_n=%d dispatch_p50_ms=%.3f dispatch_p95_ms=%.3f "
        "dispatch_max_ms=%.3f paint_pending_n=%d paint_pending_p50_ms=%.3f "
        "paint_pending_p95_ms=%.3f paint_pending_max_ms=%.3f dispatch_unknown=%d "
        "window_active_last=%s window_active_changes=%d window_active_age_ms=%.1f "
        "active_dispatch_n=%d active_dispatch_p95_ms=%.3f inactive_dispatch_n=%d "
        "inactive_dispatch_p95_ms=%.3f active_paint_n=%d active_paint_p95_ms=%.3f "
        "inactive_paint_n=%d inactive_paint_p95_ms=%.3f",
        *common,
        dispatch_n,
        dispatch_p50,
        dispatch_p95,
        dispatch_max,
        paint_n,
        paint_p50,
        paint_p95,
        paint_max,
        int(_safe_attr(widget, "_srpss_delivery_dispatch_unknown", 0) or 0),
        active_text,
        int(_safe_attr(widget, "_srpss_delivery_window_active_changes", 0) or 0),
        active_age_ms,
        active_dispatch_n,
        active_dispatch_p95,
        inactive_dispatch_n,
        inactive_dispatch_p95,
        active_paint_n,
        active_paint_p95,
        inactive_paint_n,
        inactive_paint_p95,
    )
    try:
        setattr(widget, "_srpss_delivery_window_start_ts", 0.0)
    except Exception:
        pass


def _mark_widget_update_pending(widget) -> None:
    now = time.perf_counter()
    if not bool(_safe_attr(widget, "_srpss_timer_update_pending", False)):
        setattr(widget, "_srpss_timer_update_pending", True)
        setattr(widget, "_srpss_timer_update_pending_since", now)
    setattr(widget, "_srpss_timer_update_pending_last_log", 0.0)
    setattr(widget, "_srpss_timer_update_dispatch_pending", True)
    if is_perf_metrics_enabled():
        try:
            setattr(widget, "_srpss_timer_update_dispatched_ts", 0.0)
            setattr(widget, "_srpss_timer_dispatch_timing_unknown", False)
            setattr(widget, "_srpss_timer_window_active_at_dispatch", None)
            setattr(widget, "_srpss_timer_last_skip_stage", "none")
        except Exception:
            pass


def _mark_widget_update_dispatched(widget) -> None:
    if widget is None:
        return
    try:
        setattr(widget, "_srpss_timer_update_dispatch_pending", False)
    except Exception:
        pass
    if not is_perf_metrics_enabled():
        return
    try:
        owner_thread = widget.thread() if hasattr(widget, "thread") else None
        if owner_thread is not None and QThread.currentThread() is not owner_thread:
            # Generic invokeMethod("update") fallback only tells us that Qt
            # accepted the queued method, not when the GUI actually ran it.
            setattr(widget, "_srpss_timer_dispatch_timing_unknown", True)
            setattr(widget, "_srpss_timer_update_dispatched_ts", 0.0)
            return
        now = time.perf_counter()
        pending_since = float(_safe_attr(widget, "_srpss_timer_update_pending_since", 0.0) or 0.0)
        if pending_since > 0.0:
            dispatch_ms = max(0.0, (now - pending_since) * 1000.0)
            _delivery_deque(widget, "_srpss_delivery_dispatch_ms").append(dispatch_ms)
            active = _record_delivery_window_active(widget, now)
            if active is True:
                _delivery_deque(widget, "_srpss_delivery_dispatch_active_ms").append(dispatch_ms)
            elif active is False:
                _delivery_deque(widget, "_srpss_delivery_dispatch_inactive_ms").append(dispatch_ms)
            setattr(widget, "_srpss_timer_window_active_at_dispatch", active)
        setattr(widget, "_srpss_timer_dispatch_timing_unknown", False)
        setattr(widget, "_srpss_timer_update_dispatched_ts", now)
    except Exception:
        pass


def _pending_widget_update_age_ms(widget) -> float | None:
    pending_since = _safe_attr(widget, "_srpss_timer_update_pending_since")
    if not isinstance(pending_since, (int, float)) or pending_since <= 0.0:
        return None
    return (time.perf_counter() - float(pending_since)) * 1000.0


def _maybe_log_pending_widget_update(widget) -> None:
    """Report paint-delivery starvation without queuing extra UI work."""
    if not is_perf_metrics_enabled():
        return
    now = time.perf_counter()
    age_ms = _pending_widget_update_age_ms(widget)
    if age_ms is None:
        return
    if age_ms < _PENDING_UPDATE_LOG_AFTER_MS:
        return
    last_log = _safe_attr(widget, "_srpss_timer_update_pending_last_log", 0.0)
    if isinstance(last_log, (int, float)) and last_log > 0.0:
        if (now - float(last_log)) * 1000.0 < _PENDING_UPDATE_LOG_INTERVAL_MS:
            return
    try:
        setattr(widget, "_srpss_timer_update_pending_last_log", now)
    except Exception:
        pass
    logger.warning(
        "[PERF] [GL RENDER] Paint update still pending without delivery "
        "age_ms=%.2f target_fps=%s screen=%s no_requeue=True",
        age_ms,
        _safe_attr(widget, "_render_timer_fps", "<unknown>"),
        _safe_attr(widget, "_screen_index", "<unknown>"),
    )


def _mark_widget_update_consumed(widget) -> None:
    """Release the coalescing flag once a queued update reaches paint consumption."""
    if widget is None:
        return
    if is_perf_metrics_enabled():
        try:
            # paint.py records the authoritative paint-start timestamp immediately
            # before calling this helper. Pause/teardown calls do not have an
            # active paint timestamp, so they cannot contaminate paint latency.
            paint_metrics = _safe_attr(widget, "_paint_metrics")
            paint_start_ts = _safe_attr(paint_metrics, "_active_paint_start_ts")
            if isinstance(paint_start_ts, (int, float)) and paint_start_ts > 0.0:
                _record_delivery_paint_start(widget, float(paint_start_ts))
        except Exception:
            pass
    try:
        setattr(widget, "_srpss_timer_update_pending", False)
        setattr(widget, "_srpss_timer_update_pending_since", 0.0)
        setattr(widget, "_srpss_timer_update_pending_last_log", 0.0)
        setattr(widget, "_srpss_timer_update_dispatch_pending", False)
        if is_perf_metrics_enabled():
            setattr(widget, "_srpss_timer_update_dispatched_ts", 0.0)
            setattr(widget, "_srpss_timer_dispatch_timing_unknown", False)
            setattr(widget, "_srpss_timer_window_active_at_dispatch", None)
    except Exception:
        pass


def _queue_safe_widget_update(widget) -> bool:
    """Queue a QWidget.update() call that tolerates teardown races."""
    if widget is None:
        return False

    try:
        if bool(getattr(widget, "_srpss_timer_update_dispatch_pending", False)):
            if is_perf_metrics_enabled():
                setattr(widget, "_srpss_timer_last_skip_stage", "dispatch")
                age_ms = _pending_widget_update_age_ms(widget)
                if age_ms is not None:
                    _delivery_deque(widget, "_srpss_delivery_dispatch_skip_age_ms").append(age_ms)
            return False
        if bool(getattr(widget, "_srpss_timer_update_pending", False)):
            if is_perf_metrics_enabled():
                stage = (
                    "unknown"
                    if bool(_safe_attr(widget, "_srpss_timer_dispatch_timing_unknown", False))
                    else "paint"
                )
                setattr(widget, "_srpss_timer_last_skip_stage", stage)
            age_ms = _pending_widget_update_age_ms(widget)
            if is_perf_metrics_enabled() and age_ms is not None:
                if stage == "paint":
                    _delivery_deque(widget, "_srpss_delivery_paint_skip_age_ms").append(age_ms)
            if age_ms is not None and age_ms >= _PENDING_UPDATE_LOG_AFTER_MS:
                _maybe_log_pending_widget_update(widget)
            return False
        else:
            _mark_widget_update_pending(widget)
    except Exception:
        # If the widget cannot host the flag, fall back to the old behavior.
        pass

    def _apply_update() -> None:
        if widget is None:
            _mark_widget_update_consumed(widget)
            return
        try:
            if Shiboken is not None:
                try:
                    if not Shiboken.isValid(widget):
                        _mark_widget_update_consumed(widget)
                        return
                except Exception:
                    _mark_widget_update_consumed(widget)
                    return
            widget.update()
            _mark_widget_update_dispatched(widget)
        except RuntimeError as exc:
            logger.debug("[ADAPTIVE_TIMER] Suppressed stale widget update: %s", exc)
            _mark_widget_update_consumed(widget)
        except Exception as exc:
            logger.debug("[ADAPTIVE_TIMER] Widget update failed: %s", exc)
            _mark_widget_update_consumed(widget)
    try:
        owner_thread = widget.thread() if hasattr(widget, "thread") else None
        current_thread = QThread.currentThread()
        if owner_thread is not None and current_thread is owner_thread:
            _apply_update()
            return True
        if owner_thread is not None:
            if callable(getattr(widget, "_srpss_apply_timer_update", None)):
                ok = QMetaObject.invokeMethod(
                    widget,
                    "_srpss_apply_timer_update",
                    Qt.ConnectionType.QueuedConnection,
                )
                if bool(ok):
                    return True
            ok = QMetaObject.invokeMethod(
                widget,
                "update",
                Qt.ConnectionType.QueuedConnection,
            )
            if bool(ok):
                _mark_widget_update_dispatched(widget)
                return True
            global _QT_UPDATE_FALLBACK_WARNED
            if not _QT_UPDATE_FALLBACK_WARNED and is_perf_metrics_enabled():
                _QT_UPDATE_FALLBACK_WARNED = True
                logger.warning(
                    "[PERF] [FALLBACK] Adaptive timer update fell back to UI invoker after queued Qt update dispatch failed"
                )
    except RuntimeError as exc:
        logger.debug("[ADAPTIVE_TIMER] Suppressed queued widget update dispatch: %s", exc)
        _mark_widget_update_consumed(widget)
        return False
    except Exception as exc:
        logger.debug("[ADAPTIVE_TIMER] Queued widget update dispatch failed: %s", exc)

    ThreadManager.run_on_ui_thread(_apply_update)
    return True


def _normalize_next_deadline(next_deadline: float, now_ts: float, interval_s: float) -> float:
    """Return the next frame deadline strictly after ``now_ts``.

    Keeps cadence anchored to the prior deadline instead of pacing each frame
    from "now", which would accumulate callback overhead into visible drift.
    """
    if interval_s <= 0.0:
        return now_ts
    if next_deadline > now_ts:
        return next_deadline
    missed = int((now_ts - next_deadline) / interval_s) + 1
    return next_deadline + (missed * interval_s)


def _wait_until_deadline_without_gil_spin(
    deadline: float,
    stop_event: threading.Event,
    state: AtomicTimerState,
) -> None:
    """Wait for a render deadline without monopolizing the Python GIL.

    The old high-precision tail used a tight ``pass`` loop. At high refresh
    rates that can make the timer metrics look healthy while starving Qt's
    Python paint/event-loop delivery. Sleeping/yielding here may be a hair less
    theoretically precise, but it preserves the UI thread's chance to consume
    the queued paint.
    """

    while True:
        if stop_event.is_set() or state.load() != TimerState.RUNNING:
            return

        remaining = deadline - time.perf_counter()
        if remaining <= 0.0:
            return

        if remaining > _DEADLINE_YIELD_WINDOW_S:
            time.sleep(min(_DEADLINE_SLEEP_CAP_S, remaining - _DEADLINE_YIELD_WINDOW_S))
        else:
            time.sleep(0)


class TimerState(Enum):
    """Adaptive timer states.
    
    IDLE: Deep sleep, minimal CPU usage. Wakes on transition start.
    PAUSED: Recently stopped transition, checking if should go idle.
    RUNNING: Active transition, full timing precision.
    """
    IDLE = auto()
    PAUSED = auto()
    RUNNING = auto()


@dataclass
class AdaptiveTimerConfig:
    """Configuration for adaptive timer strategy."""
    target_fps: int = 0  # Always overridden by compositor; 0 = sentinel
    fallback_on_failure: bool = True
    min_frame_time_ms: float = 8.0
    # New: Time before transitioning PAUSED -> IDLE (seconds)
    idle_timeout_sec: float = 5.0
    # New: Max deep sleep duration before safety check (seconds)
    max_deep_sleep_sec: float = 60.0
    # New: Exit fast-path flag for shutdown (set to True on shutdown)
    exit_immediate: bool = False


@dataclass
class AdaptiveTimerMetrics:
    """Extended metrics for adaptive timer."""
    frame_count: int = 0
    state_transitions: int = 0
    start_ts: float = field(default_factory=time.time)
    time_in_idle_ms: float = 0.0
    time_in_paused_ms: float = 0.0
    time_in_running_ms: float = 0.0
    idle_blocking_waits: int = 0
    paused_blocking_waits: int = 0
    last_state_change_ts: float = field(default_factory=time.time)
    
    def record_state_change(self, old_state: TimerState) -> None:
        """Record transition from old_state to new state."""
        now = time.time()
        elapsed_ms = (now - self.last_state_change_ts) * 1000.0
        
        if old_state == TimerState.IDLE:
            self.time_in_idle_ms += elapsed_ms
        elif old_state == TimerState.PAUSED:
            self.time_in_paused_ms += elapsed_ms
        elif old_state == TimerState.RUNNING:
            self.time_in_running_ms += elapsed_ms
            
        self.state_transitions += 1
        self.last_state_change_ts = now


class AtomicTimerState:
    """Lock-free atomic state container for timer state.
    
    Uses simple compare-and-swap pattern with threading.Lock
    for state transitions (transitions are rare, reads are frequent).
    """
    
    def __init__(self, initial: TimerState = TimerState.IDLE):
        self._state = initial
        self._lock = threading.Lock()
    
    def load(self) -> TimerState:
        """Read current state (fast, no lock for read)."""
        return self._state
    
    def compare_and_swap(self, expected: TimerState, new: TimerState) -> TimerState:
        """Atomic compare-and-swap. Returns actual state (may be expected or different)."""
        with self._lock:
            actual = self._state
            if actual == expected:
                self._state = new
            return actual
    
    def store(self, new: TimerState) -> None:
        """Atomic store."""
        with self._lock:
            self._state = new


class AdaptiveTimerStrategy:
    """Adaptive timer with hybrid state machine for optimal performance.
    
    State Machine:
    - IDLE: Thread blocked on Event.wait(), ~0% CPU
    - PAUSED: Brief sleep checks (1ms), ~0.1% CPU, transitions to IDLE after timeout
    - RUNNING: Full precision timing, ~1-2% CPU per display
    
    Transitions:
    - IDLE -> RUNNING: On start_transition() (wake event)
    - RUNNING -> PAUSED: On end_transition()
    - PAUSED -> IDLE: After idle_timeout_sec of no new transitions
    - Any -> STOPPED: On stop() (app exit)
    
    Thread Safety:
    - State changes use AtomicTimerState (CAS operations)
    - Frame queue uses SPSCQueue (lock-free)
    - Wake event uses threading.Event (standard)
    """
    
    def __init__(self, compositor: "GLCompositorWidget", config: AdaptiveTimerConfig):
        self._compositor = compositor
        self._config = config
        
        # Atomic state management
        self._state = AtomicTimerState(TimerState.IDLE)
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()  # For waking from deep sleep
        
        # Frame request queue (lock-free)
        self._frame_queue: SPSCQueue[bool] = SPSCQueue(4)

        # Display-owned auxiliary presentation opportunity (one per display).
        self._auxiliary_presenter = None
        self._auxiliary_lock = threading.Lock()

        # Threading
        self._task_future = None
        self._task_id: Optional[str] = None
        self._thread_manager: Optional[ThreadManager] = None
        self._loop_stopped_event = threading.Event()
        
        # Resource management
        self._resource_manager: Optional[ResourceManager] = None
        self._timer_resource_id: Optional[str] = None
        
        # Metrics
        self._metrics = AdaptiveTimerMetrics()
        self._transition_ended_at: float = 0.0
        
        # Get managers from compositor context
        try:
            parent = getattr(compositor, 'parent', lambda: None)()
            if parent is not None:
                self._thread_manager = getattr(parent, '_thread_manager', None)
                self._resource_manager = getattr(parent, '_resource_manager', None)
        except Exception:
            pass
    
    def start(self) -> bool:
        """Start adaptive timer (creates thread if not exists, wakes if sleeping)."""
        # Check if already running in any capacity
        if self._task_future is not None:
            # Timer thread exists - just wake it
            current = self._state.load()
            if current != TimerState.RUNNING:
                self._metrics.record_state_change(current)
                self._state.store(TimerState.RUNNING)
                _reset_delivery_perf_window(self._compositor)
                self._wake_event.set()
                if is_perf_metrics_enabled():
                    logger.info("[PERF][ADAPTIVE_TIMER] wake_to_running id=%s state=%s", self._task_id, current.name)
                else:
                    logger.debug("[ADAPTIVE_TIMER] Waking from %s to RUNNING", current.name)
            return True
        
        # Need to create thread - ThreadManager is required
        if self._thread_manager is None:
            logger.error(
                "[ADAPTIVE_TIMER] ThreadManager required but not available. "
                "Ensure compositor has a parent with _thread_manager."
            )
            return False
        
        # Use ThreadManager
        try:
            self._stop_event.clear()
            self._wake_event.clear()
            self._loop_stopped_event.clear()
            self._frame_queue.clear()
            
            # Start in IDLE state, thread will wait for wake
            self._state.store(TimerState.IDLE)
            
            # Submit to ThreadManager COMPUTE pool
            task_id = f"adaptive_timer_{id(self)}"
            self._thread_manager.submit_task(
                ThreadPoolType.COMPUTE,
                self._timer_loop,
                task_id=task_id,
                category="presentation.adaptive_timer",
            )
            # Store task_id to track if thread is running
            self._task_id = task_id
            self._task_future = task_id  # Truthy sentinel so is_active() works
            
            # Register with ResourceManager
            if self._resource_manager is not None:
                try:
                    from core.resources.types import ResourceType
                    self._timer_resource_id = self._resource_manager.register(
                        self,
                        ResourceType.TIMER,
                        f"Adaptive timer ({self._config.target_fps}Hz)",
                    )
                except Exception as e:
                    logger.debug("[ADAPTIVE_TIMER] Could not register: %s", e)
            
            # Immediately wake to RUNNING state
            self._state.store(TimerState.RUNNING)
            _reset_delivery_perf_window(self._compositor)
            self._wake_event.set()
            
            logger.info("[ADAPTIVE_TIMER] Started (target=%dHz, task=%s)", self._config.target_fps, self._task_id)
            return True
            
        except Exception as e:
            logger.error("[ADAPTIVE_TIMER] Failed to start: %s", e)
            return False
    
    def pause(self) -> None:
        """Pause timer (transition RUNNING -> PAUSED)."""
        current = self._state.load()
        if current == TimerState.RUNNING:
            self._metrics.record_state_change(current)
            self._state.store(TimerState.PAUSED)
            self._transition_ended_at = time.monotonic()
            _log_delivery_perf_window(
                self._compositor,
                outcome="paused",
                target_fps=self._config.target_fps,
            )
            if is_perf_metrics_enabled():
                logger.info("[PERF][ADAPTIVE_TIMER] paused id=%s", self._task_id)
            else:
                logger.debug("[ADAPTIVE_TIMER] Paused")
    
    def resume(self) -> None:
        """Resume timer (transition PAUSED/IDLE -> RUNNING)."""
        current = self._state.load()
        if current != TimerState.RUNNING:
            self._metrics.record_state_change(current)
            self._state.store(TimerState.RUNNING)
            _reset_delivery_perf_window(self._compositor)
            self._wake_event.set()
            if is_perf_metrics_enabled():
                logger.info("[PERF][ADAPTIVE_TIMER] resumed_from=%s id=%s", current.name, self._task_id)
            else:
                logger.debug("[ADAPTIVE_TIMER] Resumed from %s", current.name)
    
    def stop(self) -> bool:
        """Stop permanently, retaining ownership if the worker does not drain."""
        # Signal stop
        task_id = self._task_id
        self._stop_event.set()
        self._wake_event.set()

        stopped = True
        if self._task_future is not None:
            # Wait for the loop's finally block, not for the already-set stop event.
            try:
                base_wait = 4 * self._config.min_frame_time_ms / 1000.0
                max_wait = 0.0 if self._config.exit_immediate else max(0.05, min(0.25, base_wait))
                stopped = self._loop_stopped_event.wait(timeout=max_wait)
                if not stopped:
                    logger.warning(
                        "[PERF][ADAPTIVE_TIMER][FALLBACK] Stop timed out before loop acknowledged shutdown "
                        "task=%s timeout=%.3fs",
                        task_id,
                        max_wait,
                    )
            except Exception:
                stopped = False

            if not stopped:
                # The ThreadManager task still owns this strategy's bound loop.
                # Do not erase the only authoritative task/resource handles and
                # let compositor teardown destroy its context underneath it.
                return False
            self._task_future = None
        _log_delivery_perf_window(
            self._compositor,
            outcome="stopped",
            target_fps=self._config.target_fps,
        )
        self._task_id = None
        
        # Unregister from ResourceManager
        if self._timer_resource_id and self._resource_manager:
            try:
                self._resource_manager.unregister(self._timer_resource_id)
            except Exception:
                pass
            self._timer_resource_id = None
        
        if is_perf_metrics_enabled():
            logger.info("[PERF][ADAPTIVE_TIMER] stopped")
        else:
            logger.info("[ADAPTIVE_TIMER] Stopped")
        self._log_metrics()
        return True

    def describe_state(self) -> dict:
        """Return current timer snapshot for diagnostics."""
        state = self._state.load()
        return {
            "task_id": self._task_id,
            "state": state.name,
            "stop_event": self._stop_event.is_set(),
            "wake_event": self._wake_event.is_set(),
            "frames": self._metrics.frame_count,
        }
    
    def _timer_loop(self) -> None:
        """Main timer loop with state machine."""
        fps = self._config.target_fps if self._config.target_fps > 0 else 240.0
        target_interval = max(1.0, 1000.0 / fps) / 1000.0
        next_tick_deadline: Optional[float] = None
        
        logger.debug("[ADAPTIVE_TIMER] Loop started (target=%.2fms)", target_interval * 1000)
        try:
            while not self._stop_event.is_set():
                state = self._state.load()

                if state == TimerState.IDLE:
                    next_tick_deadline = None
                    # Resume and stop both signal ``_wake_event``.  A bounded
                    # blocking wait therefore stays immediately interruptible
                    # without waking a compute worker once per second forever.
                    self._metrics.idle_blocking_waits += 1
                    idle_wait_s = max(
                        0.1,
                        float(self._config.max_deep_sleep_sec),
                    )
                    if self._wake_event.wait(timeout=idle_wait_s):
                        self._wake_event.clear()
                    continue

                elif state == TimerState.PAUSED:
                    next_tick_deadline = None
                    # Check if should go idle
                    elapsed = time.monotonic() - self._transition_ended_at
                    if elapsed > self._config.idle_timeout_sec:
                        # Transition to IDLE
                        old_state = self._state.compare_and_swap(TimerState.PAUSED, TimerState.IDLE)
                        if old_state == TimerState.PAUSED:
                            self._metrics.record_state_change(TimerState.PAUSED)
                            logger.debug("[ADAPTIVE_TIMER] Auto-idle after %.1fs", elapsed)
                        continue

                    # Pause is an interruptible idle deadline, not a 1 kHz
                    # polling mode.  ``resume()`` and ``stop()`` both wake it.
                    self._metrics.paused_blocking_waits += 1
                    remaining_idle_s = max(
                        0.0,
                        float(self._config.idle_timeout_sec) - elapsed,
                    )
                    if self._wake_event.wait(timeout=remaining_idle_s):
                        self._wake_event.clear()
                    continue

                elif state == TimerState.RUNNING:
                    # Full-precision timing
                    try:
                        if next_tick_deadline is None:
                            next_tick_deadline = time.perf_counter() + target_interval

                        # Check for immediate frame requests
                        has_request = False
                        while True:
                            ok, _ = self._frame_queue.try_pop()
                            if not ok:
                                break
                            has_request = True

                        if has_request:
                            self._signal_frame(immediate=True)
                            continue

                        # Precise timing anchored to the carried deadline so callback
                        # overhead does not accumulate into long-run drift.
                        _wait_until_deadline_without_gil_spin(
                            next_tick_deadline,
                            self._stop_event,
                            self._state,
                        )
                        
                        # Only signal if still running
                        if (
                            not self._stop_event.is_set()
                            and self._state.load() == TimerState.RUNNING
                        ):
                            self._signal_frame(deadline_ts=next_tick_deadline)
                            next_tick_deadline = _normalize_next_deadline(
                                next_tick_deadline + target_interval,
                                time.perf_counter(),
                                target_interval,
                            )

                    except Exception as e:
                        logger.error("[ADAPTIVE_TIMER] Loop error: %s", e)
                        break
        finally:
            self._loop_stopped_event.set()
            logger.debug("[ADAPTIVE_TIMER] Loop stopped")
    
    def _signal_frame(
        self,
        *,
        deadline_ts: float | None = None,
        immediate: bool = False,
    ) -> None:
        """Signal UI thread to render."""
        if self._compositor is not None:
            try:
                # Log occasional frame signals for debugging
                if self._metrics.frame_count % 100 == 0:
                    logger.debug("[ADAPTIVE_TIMER] Signaling frame %d", self._metrics.frame_count)
                perf_delivery = is_perf_metrics_enabled()
                if perf_delivery:
                    _record_delivery_wake(
                        self._compositor,
                        deadline_ts=deadline_ts,
                        immediate=immediate,
                    )
                accepted_update = _queue_safe_widget_update(self._compositor)
                if perf_delivery:
                    _record_delivery_result(self._compositor, accepted_update)
                if hasattr(self._compositor, "_record_render_timer_tick"):
                    self._compositor._record_render_timer_tick(accepted_update=accepted_update)
                self._metrics.frame_count += 1
            except Exception as e:
                logger.debug("[ADAPTIVE_TIMER] Frame signal failed: %s", e)
        self._service_auxiliary_presenter()

    def set_auxiliary_presenter(self, presenter) -> None:
        """Register the display's auxiliary surface with this frame opportunity.

        One presenter per display, registered by the owning `DisplayWidget`. This is
        not a second clock: the presenter is serviced from the display's existing
        frame opportunity and never gains a timer, thread or cadence of its own.
        Registration enables presentation deferral on the presenter; clearing it
        releases deferral so a paused opportunity cannot strand the surface (R-61).
        """
        with self._auxiliary_lock:
            self._auxiliary_presenter = presenter
        if presenter is not None:
            try:
                presenter.set_presentation_deferred(True)
            except Exception:
                logger.debug("[ADAPTIVE_TIMER] Failed to enable deferral", exc_info=True)

    def clear_auxiliary_presenter(self) -> None:
        """Detach the auxiliary presenter and restore its immediate presentation."""
        with self._auxiliary_lock:
            presenter = self._auxiliary_presenter
            self._auxiliary_presenter = None
        if presenter is not None:
            try:
                presenter.set_presentation_deferred(False)
            except Exception:
                logger.debug("[ADAPTIVE_TIMER] Failed to release deferral", exc_info=True)

    def _service_auxiliary_presenter(self) -> None:
        """Offer one presentation opportunity through a narrow explicit interface.

        This runs on the timer worker thread. `present_if_pending()` touches QWidget
        state, so it must execute on the GUI owner exactly like the compositor's own
        update path; calling it directly here corrupts Qt repaint state and freezes
        presentation while the event loop stays alive (R-61).

        The pending check is a plain integer comparison performed off-thread purely
        to avoid queueing a GUI callback when nothing is owed. A stale read costs at
        most one deferred opportunity and can never present un-integrated state,
        because the authoritative re-check happens on the GUI thread.
        """
        with self._auxiliary_lock:
            presenter = self._auxiliary_presenter
        if presenter is None:
            return
        try:
            if not presenter.has_pending_presentation():
                return
            ThreadManager.run_on_ui_thread(presenter.present_if_pending)
        except RuntimeError:
            # The owning surface was destroyed between registration and service.
            self.clear_auxiliary_presenter()
        except Exception:
            logger.debug(
                "[ADAPTIVE_TIMER] Auxiliary presentation opportunity failed", exc_info=True
            )
    
    def request_frame(self) -> None:
        """Queue immediate frame request."""
        self._frame_queue.push_drop_oldest(True)
    
    def _log_metrics(self) -> None:
        """Log final metrics."""
        m = self._metrics
        total_time = time.time() - m.start_ts
        logger.info(
            "[ADAPTIVE_TIMER] Metrics: frames=%d, transitions=%d, "
            "time_idle=%.1fms, time_paused=%.1fms, time_running=%.1fms, "
            "idle_waits=%d paused_waits=%d total_runtime=%.1fs",
            m.frame_count, m.state_transitions,
            m.time_in_idle_ms, m.time_in_paused_ms, m.time_in_running_ms,
            m.idle_blocking_waits, m.paused_blocking_waits,
            total_time
        )
    
    def is_active(self) -> bool:
        """Check if timer is active (not stopped)."""
        # _task_future is actually a task_id string (ThreadManager returns task_id, not Future)
        # Just check if timer thread was started (not None) and not explicitly stopped
        return self._task_future is not None
    
    def get_state(self) -> TimerState:
        """Get current timer state."""
        return self._state.load()


class AdaptiveRenderStrategyManager:
    """Manager for adaptive timer render strategy.
    
    Maintains persistent timer across transitions.
    """
    
    def __init__(self, compositor: "GLCompositorWidget"):
        self._compositor = compositor
        self._config = AdaptiveTimerConfig()
        self._timer: Optional[AdaptiveTimerStrategy] = None
        self._lock = threading.Lock()
        # Survives stop/start: the display owns the overlay across restarts.
        # Deferral is applied only while the timer is actually running (R-61).
        self._auxiliary_presenter = None
    
    def configure(self, config: AdaptiveTimerConfig) -> None:
        """Update configuration."""
        with self._lock:
            self._config = config
    
    def start(self) -> bool:
        """Start or resume adaptive timer."""
        with self._lock:
            if self._timer is None:
                self._timer = AdaptiveTimerStrategy(self._compositor, self._config)
            presenter = self._auxiliary_presenter
            if presenter is not None:
                self._timer.set_auxiliary_presenter(presenter)
            result = self._timer.start()
        if is_perf_metrics_enabled():
            logger.info(
                "[PERF][ADAPTIVE_TIMER] manager_start result=%s state=%s compositor=%s",
                result,
                self.describe_state(),
                self._describe_compositor_state(),
            )
        return result
    
    def pause(self) -> None:
        """Pause timer after transition ends."""
        before_state = None
        after_state = None
        with self._lock:
            if self._timer is not None:
                before_state = self._timer.get_state().name
                # A paused opportunity offers no presentation; release deferral so
                # the overlay returns to one-request-per-publication (R-61).
                self._timer.clear_auxiliary_presenter()
                self._timer.pause()
                after_state = self._timer.get_state().name
        if is_perf_metrics_enabled():
            event = "manager_paused" if before_state == "RUNNING" and after_state == "PAUSED" else "manager_pause_noop"
            logger.info(
                "[PERF][ADAPTIVE_TIMER] %s before=%s after=%s state=%s compositor=%s",
                event,
                before_state,
                after_state,
                self.describe_state(),
                self._describe_compositor_state(),
            )
    
    def resume(self) -> None:
        """Resume timer for new transition."""
        before_state = None
        after_state = None
        with self._lock:
            if self._timer is not None:
                before_state = self._timer.get_state().name
                self._timer.resume()
                if self._auxiliary_presenter is not None:
                    self._timer.set_auxiliary_presenter(self._auxiliary_presenter)
                after_state = self._timer.get_state().name
        if is_perf_metrics_enabled():
            event = "manager_resumed" if after_state == "RUNNING" and before_state != "RUNNING" else "manager_resume_noop"
            logger.info(
                "[PERF][ADAPTIVE_TIMER] %s before=%s after=%s state=%s compositor=%s",
                event,
                before_state,
                after_state,
                self.describe_state(),
                self._describe_compositor_state(),
            )
    
    def stop(self) -> bool:
        """Stop timer permanently."""
        stopped = True
        with self._lock:
            if self._timer is not None:
                self._timer.clear_auxiliary_presenter()
                stopped = bool(self._timer.stop())
                if stopped:
                    self._timer = None
        if is_perf_metrics_enabled():
            logger.info(
                "[PERF][ADAPTIVE_TIMER] manager_stopped state=%s compositor=%s",
                self.describe_state(),
                self._describe_compositor_state(),
            )
        return stopped

    def cleanup(self) -> None:
        """Stop the strategy and detach its retired compositor owner."""

        if not self.stop():
            raise RuntimeError(
                "Adaptive render worker did not acknowledge shutdown; "
                "refusing compositor/context destruction"
            )
        with self._lock:
            self._compositor = None
            self._auxiliary_presenter = None
    
    def request_frame(self) -> None:
        """Request immediate frame."""
        with self._lock:
            if self._timer is not None:
                self._timer.request_frame()

    def set_auxiliary_presenter(self, presenter) -> None:
        """Register the display's auxiliary surface for the frame opportunity.

        Deferral is applied only when the timer is actually running; registering
        while stopped or paused records the presenter without deferring, so the
        overlay keeps presenting normally until an opportunity exists (R-61).
        """
        with self._lock:
            self._auxiliary_presenter = presenter
            timer = self._timer
            running = timer is not None and timer.is_active()
        if timer is not None and running:
            timer.set_auxiliary_presenter(presenter)

    def clear_auxiliary_presenter(self) -> None:
        """Detach the auxiliary surface and restore its immediate presentation."""
        with self._lock:
            self._auxiliary_presenter = None
            timer = self._timer
        if timer is not None:
            timer.clear_auxiliary_presenter()
        return None
    
    def is_running(self) -> bool:
        """Check if timer is active."""
        with self._lock:
            return self._timer is not None and self._timer.is_active()

    def get_timer_state_name(self) -> Optional[str]:
        """Return the current timer state name when the timer exists."""
        with self._lock:
            if self._timer is None:
                return None
            return self._timer.get_state().name

    def describe_state(self) -> dict:
        """Snapshot of manager/timer state for diagnostics."""
        with self._lock:
            config_snapshot = asdict(self._config)
            timer_state = self._timer.describe_state() if self._timer else None
        return {
            "config": config_snapshot,
            "timer": timer_state,
        }

    def _describe_compositor_state(self) -> dict | None:
        """Best-effort compositor context for timer state transitions."""
        try:
            if hasattr(self._compositor, "describe_stall_context"):
                return self._compositor.describe_stall_context()
            if hasattr(self._compositor, "describe_state"):
                return self._compositor.describe_state()
        except Exception:
            logger.debug("[ADAPTIVE_TIMER] Failed to describe compositor state", exc_info=True)
        return None
