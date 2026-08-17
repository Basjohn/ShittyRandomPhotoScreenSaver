"""GL Compositor Metrics — Extracted from gl_compositor.py.

Contains all perf-gated animation, paint, and render-timer metric
instrumentation.  Every function takes the compositor widget as the
first argument so the main class stays lean.
"""
from __future__ import annotations

from collections import deque

import gc
import time
from typing import Optional, Callable, TYPE_CHECKING

from core.logging.logger import get_logger, is_perf_metrics_enabled
from rendering.gl_compositor_pkg.metrics import (
    _AnimationRunMetrics,
    _PaintMetrics,
    _RenderTimerMetrics,
)

if TYPE_CHECKING:
    from core.animation.animator import AnimationManager

logger = get_logger(__name__)


def _get_screen_index(widget) -> int | None:
    parent = None
    try:
        parent = widget.parent()
    except Exception:
        parent = None
    for owner in (parent, widget):
        try:
            screen_index = getattr(owner, "screen_index", None)
            if screen_index is not None:
                return int(screen_index)
        except Exception:
            continue
    return None


def _get_stall_context(widget) -> dict | None:
    try:
        if hasattr(widget, "describe_stall_context"):
            return widget.describe_stall_context()
    except Exception:
        return None
    return None


def _is_active_transition_paint_window(stall_context: dict | None) -> bool:
    """Return True when transition paint cadence should still be active."""
    if not isinstance(stall_context, dict):
        return False

    if stall_context.get("current_transition") or bool(stall_context.get("has_frame_state")):
        return True

    display_transition = stall_context.get("display_transition")
    if not isinstance(display_transition, dict):
        return False

    return bool(display_transition.get("running")) or bool(display_transition.get("pending"))


def _counter_delta(
    current: dict,
    previous: dict,
    key: str,
) -> int:
    """Return a non-negative display-local delta for a cumulative counter."""
    if key not in previous:
        return 0
    try:
        return max(0, int(current.get(key, 0) or 0) - int(previous.get(key, 0) or 0))
    except Exception:
        return 0


def _compact_field(value, fallback: str = "<none>") -> str:
    """Keep one-line owner logs machine-readable without leaking payload data."""
    text = str(value if value not in (None, "") else fallback)
    return "_".join(text.split())


def _timestamp_age_ms(now_ts: float, timestamp) -> float | None:
    """Return passive wall-clock age, or None when no authority exists yet."""
    try:
        source_ts = float(timestamp or 0.0)
    except Exception:
        return None
    if source_ts <= 0.0:
        return None
    return max(0.0, (float(now_ts) - source_ts) * 1000.0)


def _frame_owner_snapshot(widget) -> dict:
    """Read passive cumulative owner counters without scheduling any work."""
    try:
        parent = widget.parent()
    except Exception:
        parent = None
    visualizer = getattr(parent, "spotify_visualizer_widget", None)
    media = getattr(parent, "media_widget", None)
    overlay = getattr(parent, "_spotify_bars_overlay", None)
    manager = getattr(parent, "_thread_manager", None)
    if manager is None:
        manager = getattr(visualizer, "_thread_manager", None)
    if manager is None:
        manager = getattr(media, "_thread_manager", None)
    if manager is None:
        try:
            from core.threading.manager import ThreadManager

            manager = ThreadManager.get_app_shared()
        except Exception:
            manager = None

    thread_snapshot: dict = {}
    getter = getattr(manager, "get_frame_delivery_snapshot", None)
    if callable(getter):
        try:
            thread_snapshot = dict(getter())
        except Exception:
            thread_snapshot = {}

    snapshot = {
        **thread_snapshot,
        "media_display_total": int(
            getattr(media, "_perf_media_display_total", 0) or 0
        ),
        "media_emit_total": int(getattr(media, "_perf_media_emit_total", 0) or 0),
        "media_update_total": int(
            getattr(media, "_perf_media_update_request_total", 0) or 0
        ),
        "overlay_set_total": int(
            getattr(overlay, "_perf_set_state_total", 0) or 0
        ),
        "overlay_update_total": int(
            getattr(overlay, "_perf_update_request_total", 0) or 0
        ),
        "overlay_paint_total": int(
            getattr(overlay, "_perf_paint_total", 0) or 0
        ),
        "vis_mode": getattr(visualizer, "_vis_mode_str", "<none>"),
        "vis_phase": int(
            getattr(visualizer, "_mode_transition_phase", 0) or 0
        ),
        "vis_waiting_engine": bool(
            getattr(visualizer, "_waiting_for_fresh_engine_frame", False)
        ),
        "vis_waiting_frame": bool(
            getattr(visualizer, "_waiting_for_fresh_frame", False)
        ),
        "bubble_worker_pending": bool(
            getattr(visualizer, "_bubble_compute_pending", False)
        ),
        "bubble_result_pending": bool(
            getattr(visualizer, "_bubble_pending_result", None) is not None
        ),
        "bubble_visible_source_ts": float(
            getattr(visualizer, "_bubble_visible_source_ts", 0.0) or 0.0
        ),
        "bubble_visible_simulation_ts": float(
            getattr(visualizer, "_bubble_visible_simulation_ts", 0.0) or 0.0
        ),
        "bubble_visible_render_state_ts": float(
            getattr(visualizer, "_bubble_visible_render_state_ts", 0.0) or 0.0
        ),
    }
    return snapshot


def _transition_label(stall_context: dict | None) -> str:
    if not isinstance(stall_context, dict):
        return "<none>"
    current = stall_context.get("current_transition")
    if current:
        return _compact_field(current)
    display_transition = stall_context.get("display_transition")
    if isinstance(display_transition, dict):
        for key in ("name", "transition", "current_transition", "last_transition"):
            value = display_transition.get(key)
            if value:
                return _compact_field(value)
    return "<none>"


def _log_frame_gap_owner(
    widget,
    metrics: _PaintMetrics,
    *,
    gap_ms: float,
    paint_duration_ms: float,
    stall_context: dict | None,
    active_transition_window: bool,
    current: dict,
    previous: dict,
) -> None:
    """Emit exactly one compact owner record for each >33 ms paint gap."""
    request_age_ms = None
    if metrics.samples:
        request_age_ms = metrics.samples[-1].request_to_paint_age_ms
    target_hz = int(getattr(widget, "_render_timer_fps", 0) or 0)
    if target_hz <= 0:
        target_hz = int(
            getattr(getattr(widget, "_animation_manager", None), "fps", 0) or 0
        )
    try:
        gc_counts = "/".join(str(value) for value in gc.get_count())
    except Exception:
        gc_counts = "na"
    wall_now_ts = time.time()
    ui_completed_ts = float(current.get("ui_last_completed_ts", 0.0) or 0.0)
    ui_callback_age_ms = (
        max(0.0, (wall_now_ts - ui_completed_ts) * 1000.0)
        if ui_completed_ts > 0.0
        else -1.0
    )
    source_age_ms = _timestamp_age_ms(
        wall_now_ts,
        current.get("bubble_visible_source_ts"),
    )
    simulation_age_ms = _timestamp_age_ms(
        wall_now_ts,
        current.get("bubble_visible_simulation_ts"),
    )
    render_state_age_ms = _timestamp_age_ms(
        wall_now_ts,
        current.get("bubble_visible_render_state_ts"),
    )
    severity = "over_50" if gap_ms > 50.0 else "over_33"
    logger.warning(
        "[PERF][FRAME_GAP_OWNER] severity=%s screen=%s gap_ms=%.2f "
        "paint_ms=%.2f request_age_ms=%s source_age_ms=%s "
        "simulation_age_ms=%s render_state_age_ms=%s target_hz=%d "
        "transition_active=%d transition=%s vis_mode=%s vis_phase=%d "
        "waiting_engine=%d waiting_frame=%d bubble_worker=%d bubble_result=%d "
        "io_queue=%d compute_queue=%d io_active=%d compute_active=%d "
        "io_callbacks=%d compute_callbacks=%d "
        "io_queue_wait_ms=%.2f compute_queue_wait_ms=%.2f "
        "io_exec_ms=%.2f compute_exec_ms=%.2f "
        "io_callback_ms=%.2f compute_callback_ms=%.2f "
        "ui_callbacks=%d ui_active=%d ui_queue=%d ui_failed=%d "
        "last_ui=%s last_ui_ms=%.2f last_ui_age_ms=%.2f "
        "media_display=%d media_emit=%d media_repaints=%d "
        "overlay_set=%d overlay_repaints=%d overlay_paints=%d "
        "render_requests=%d skipped_requests=%d gc_enabled=%d gc_counts=%s",
        severity,
        _get_screen_index(widget),
        gap_ms,
        paint_duration_ms,
        f"{request_age_ms:.2f}" if request_age_ms is not None else "na",
        f"{source_age_ms:.2f}" if source_age_ms is not None else "na",
        f"{simulation_age_ms:.2f}" if simulation_age_ms is not None else "na",
        f"{render_state_age_ms:.2f}" if render_state_age_ms is not None else "na",
        target_hz,
        int(active_transition_window),
        _transition_label(stall_context),
        _compact_field(current.get("vis_mode")),
        int(current.get("vis_phase", 0) or 0),
        int(bool(current.get("vis_waiting_engine", False))),
        int(bool(current.get("vis_waiting_frame", False))),
        int(bool(current.get("bubble_worker_pending", False))),
        int(bool(current.get("bubble_result_pending", False))),
        int(current.get("io_queue_depth", -1) or 0),
        int(current.get("compute_queue_depth", -1) or 0),
        int(current.get("io_worker_active", 0) or 0),
        int(current.get("compute_worker_active", 0) or 0),
        _counter_delta(current, previous, "io_callbacks_delivered"),
        _counter_delta(current, previous, "compute_callbacks_delivered"),
        float(current.get("io_last_queue_wait_ms", 0.0) or 0.0),
        float(current.get("compute_last_queue_wait_ms", 0.0) or 0.0),
        float(current.get("io_last_execution_ms", 0.0) or 0.0),
        float(current.get("compute_last_execution_ms", 0.0) or 0.0),
        float(current.get("io_last_callback_ms", 0.0) or 0.0),
        float(current.get("compute_last_callback_ms", 0.0) or 0.0),
        _counter_delta(current, previous, "ui_delivered"),
        int(current.get("ui_active", 0) or 0),
        int(current.get("ui_queue_depth", 0) or 0),
        _counter_delta(current, previous, "ui_failed"),
        _compact_field(current.get("ui_last_callback")),
        float(current.get("ui_last_duration_ms", 0.0) or 0.0),
        ui_callback_age_ms,
        _counter_delta(current, previous, "media_display_total"),
        _counter_delta(current, previous, "media_emit_total"),
        _counter_delta(current, previous, "media_update_total"),
        _counter_delta(current, previous, "overlay_set_total"),
        _counter_delta(current, previous, "overlay_update_total"),
        _counter_delta(current, previous, "overlay_paint_total"),
        metrics.render_request_count
        - int(previous.get("render_request_count", metrics.render_request_count) or 0),
        metrics.skipped_request_count
        - int(previous.get("skipped_request_count", metrics.skipped_request_count) or 0),
        int(gc.isenabled()),
        gc_counts,
    )


# ------------------------------------------------------------------
# Animation metrics
# ------------------------------------------------------------------

def begin_animation_metrics(
    widget,
    transition_label: str,
    duration_ms: int,
    animation_manager: "AnimationManager",
) -> Optional[_AnimationRunMetrics]:
    if not is_perf_metrics_enabled():
        widget._current_anim_metrics = None
        return None
    target_fps = getattr(animation_manager, "fps", 60)
    metrics = _AnimationRunMetrics(
        name=transition_label,
        duration_ms=int(duration_ms),
        target_fps=int(target_fps or 60),
        dt_spike_threshold_ms=widget._anim_dt_spike_threshold_ms,
    )
    widget._current_anim_metrics = metrics
    return metrics


def wrap_animation_update(
    widget,
    update_callback: Callable[[float], None],
    metrics: Optional[_AnimationRunMetrics],
) -> Callable[[float], None]:
    if metrics is None:
        return update_callback

    def _instrumented(progress: float, *, _inner=update_callback) -> None:
        dt = metrics.record_tick(progress)
        if dt is not None and metrics.should_log_spike(dt):
            log_animation_spike(widget, metrics, dt)
        _inner(progress)

    return _instrumented


def log_animation_spike(
    widget,
    metrics: _AnimationRunMetrics,
    dt_seconds: float,
) -> None:
    if not is_perf_metrics_enabled():
        return
    dt_ms = dt_seconds * 1000.0
    logger.warning(
        "[PERF] [GL ANIM] Tick dt spike %.2fms (screen=%s name=%s frame=%d progress=%.2f target_fps=%d)",
        dt_ms,
        _get_screen_index(widget),
        metrics.name,
        metrics.frame_count,
        metrics.last_progress,
        metrics.target_fps,
    )


def finalize_animation_metrics(widget, outcome: str) -> None:
    metrics = widget._current_anim_metrics
    widget._current_anim_metrics = None
    if metrics is None or not is_perf_metrics_enabled():
        return

    elapsed_s = metrics.elapsed_seconds()
    duration_ms = elapsed_s * 1000.0
    avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
    min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
    max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0

    logger.info(
        "[PERF] [GL ANIM] %s metrics: screen=%s, duration=%.1fms, frames=%d, avg_fps=%.1f, "
        "dt_min=%.2fms, dt_max=%.2fms, spikes=%d, target_fps=%d, outcome=%s",
        metrics.name.capitalize(),
        _get_screen_index(widget),
        duration_ms,
        metrics.frame_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.dt_spike_count,
        metrics.target_fps,
        outcome,
    )


# ------------------------------------------------------------------
# Paint metrics
# ------------------------------------------------------------------

def begin_paint_metrics(widget, label: str) -> None:
    if not is_perf_metrics_enabled():
        widget._paint_metrics = None
        return
    widget._paint_metrics = _PaintMetrics(
        label=label,
        slow_threshold_ms=widget._paint_slow_threshold_ms,
    )


def record_paint_start_metrics(widget, paint_start_ts: float) -> None:
    """Record paint delivery before the existing pending-update flag is consumed."""
    if not is_perf_metrics_enabled():
        return
    metrics = widget._paint_metrics
    if metrics is None:
        return
    metrics.record_paint_start(
        paint_start_ts,
        int(getattr(widget, "_transition_animation_generation", 0) or 0),
    )


def _retain_diagnostic_paint_sample(widget) -> None:
    """Retain one paint sample in compositor-local history that outlives transitions.

    `_PaintMetrics` is transition-local and is replaced when a new transition
    begins. Asynchronous GPU results belonging to the previous generation can
    drain after that replacement, and would then find no paint samples to join
    against - which is why the first association run left ~243 of 344 GPU
    samples unmatched and produced no BlockSpin output at all.

    Generation identity remains authoritative, so retaining history across
    transitions cannot cause cross-matching between them. Gated to GPU
    diagnostic mode so ordinary PERF runs do not pay for it.
    """
    timer_queries = getattr(widget, "_gpu_timer_queries", None)
    if timer_queries is None or not getattr(timer_queries, "supported", False):
        return
    metrics = getattr(widget, "_paint_metrics", None)
    if metrics is None or not metrics.samples:
        return
    history = getattr(widget, "_gpu_assoc_paint_history", None)
    if history is None:
        history = deque(maxlen=4096)
        widget._gpu_assoc_paint_history = history
    history.append(metrics.samples[-1])


def reset_diagnostic_paint_history(widget) -> None:
    """Clear cross-transition association history at compositor/runtime teardown.

    Deliberately not called per transition: retention across transitions is the
    entire point of this history.
    """
    try:
        widget._gpu_assoc_paint_history = None
    except Exception:
        pass


def record_paint_metrics(
    widget,
    paint_duration_ms: float,
    *,
    paint_start_ts: Optional[float] = None,
    paint_end_ts: Optional[float] = None,
) -> None:
    if not is_perf_metrics_enabled():
        return
    metrics = widget._paint_metrics
    if metrics is None:
        return
    dt_seconds = metrics.record(
        paint_duration_ms,
        paint_start_ts=paint_start_ts,
        paint_end_ts=paint_end_ts,
    )
    _retain_diagnostic_paint_sample(widget)
    now = time.time()
    stall_context = _get_stall_context(widget)
    active_transition_window = _is_active_transition_paint_window(stall_context)
    owner_snapshot = _frame_owner_snapshot(widget)
    owner_snapshot["render_request_count"] = metrics.render_request_count
    owner_snapshot["skipped_request_count"] = metrics.skipped_request_count
    previous_owner_snapshot = metrics.owner_snapshot
    metrics.owner_snapshot = owner_snapshot
    if dt_seconds is not None:
        gap_ms = dt_seconds * 1000.0
        if gap_ms > 33.0:
            _log_frame_gap_owner(
                widget,
                metrics,
                gap_ms=gap_ms,
                paint_duration_ms=paint_duration_ms,
                stall_context=stall_context,
                active_transition_window=active_transition_window,
                current=owner_snapshot,
                previous=previous_owner_snapshot,
            )
    if paint_duration_ms > widget._paint_slow_threshold_ms:
        if active_transition_window and now - widget._paint_warning_last_ts > 0.5:
            logger.warning(
                "[PERF] [GL PAINT] Slow paintGL %.2fms (transition=%s context=%s)",
                paint_duration_ms,
                metrics.label,
                stall_context,
            )
            widget._paint_warning_last_ts = now
    if dt_seconds is not None and dt_seconds * 1000.0 > 120.0:
        if active_transition_window and now - widget._paint_warning_last_ts > 0.5:
            logger.warning(
                "[PERF] [GL PAINT] Paint gap %.2fms (transition=%s context=%s)",
                dt_seconds * 1000.0,
                metrics.label,
                stall_context,
            )
            widget._paint_warning_last_ts = now


def finalize_paint_metrics(widget, outcome: str = "stopped") -> None:
    metrics = widget._paint_metrics
    widget._paint_metrics = None
    if metrics is None or not is_perf_metrics_enabled():
        return
    elapsed_s = metrics.elapsed_seconds()
    avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
    min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
    max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0
    target_fps = int(getattr(widget, "_render_timer_fps", 0) or 0)
    if target_fps <= 0:
        try:
            target_fps = int(getattr(getattr(widget, "_animation_manager", None), "fps", 0) or 0)
        except Exception:
            target_fps = 0
    timing = metrics.timing_summary()
    logger.info(
        "[PERF] [GL PAINT] %s metrics: screen=%s, frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "dur_min=%.2fms, dur_max=%.2fms, slow_frames=%d, target_fps=%d, outcome=%s, "
        "window_frames=%d, render_requests=%d, skipped_requests=%d, "
        "request_acceptance_pct=%.2f, last_presented_frame=%d, scene_generation=%d, "
        "dt_p50_ms=%.2f, dt_p90_ms=%.2f, dt_p95_ms=%.2f, dt_p99_ms=%.2f, dt_max_ms=%.2f, "
        "dt_over_25_ms=%d, dt_over_33_ms=%d, dt_over_50_ms=%d, dt_over_100_ms=%d, "
        "paint_p50_ms=%.2f, paint_p90_ms=%.2f, paint_p95_ms=%.2f, paint_p99_ms=%.2f, paint_max_ms=%.2f, "
        "request_age_p50_ms=%.2f, request_age_p90_ms=%.2f, request_age_p95_ms=%.2f, request_age_p99_ms=%.2f, request_age_max_ms=%.2f",
        metrics.label.capitalize(), _get_screen_index(widget), metrics.frame_count, avg_fps,
        min_dt_ms, max_dt_ms, metrics.min_duration_ms, metrics.max_duration_ms,
        metrics.slow_count, target_fps, outcome, timing["window_frames"], timing["requests"],
        timing["skipped_requests"], timing["request_acceptance_pct"],
        timing["last_presented_frame_index"], timing["last_scene_generation"],
        timing["interval_p50_ms"], timing["interval_p90_ms"],
        timing["interval_p95_ms"], timing["interval_p99_ms"], timing["interval_max_ms"],
        timing["interval_over_25_ms"], timing["interval_over_33_ms"],
        timing["interval_over_50_ms"], timing["interval_over_100_ms"],
        timing["duration_p50_ms"], timing["duration_p90_ms"], timing["duration_p95_ms"],
        timing["duration_p99_ms"], timing["duration_max_ms"], timing["request_age_p50_ms"],
        timing["request_age_p90_ms"], timing["request_age_p95_ms"], timing["request_age_p99_ms"],
        timing["request_age_max_ms"],
    )


# ------------------------------------------------------------------
# Render timer metrics
# ------------------------------------------------------------------

def record_render_timer_tick(widget, *, accepted_update: bool = True) -> None:
    metrics = widget._render_timer_metrics
    if metrics is None or not is_perf_metrics_enabled():
        return
    paint_metrics = getattr(widget, "_paint_metrics", None)
    if paint_metrics is not None:
        paint_metrics.record_render_request(accepted_update=accepted_update)
    dt = metrics.record_tick(accepted_update=accepted_update)
    if dt is None:
        return
    if metrics.should_log_stall(dt):
        log_render_timer_stall(widget, dt, metrics)


def log_render_timer_stall(widget, dt_seconds: float, metrics: _RenderTimerMetrics) -> None:
    if not is_perf_metrics_enabled():
        return
    anim_label = widget._current_anim_metrics.name if widget._current_anim_metrics else "idle"
    logger.warning(
        "[PERF] [GL RENDER] Render timer stall %.2fms (screen=%s target=%dHz interval=%dms frames=%d anim=%s)",
        dt_seconds * 1000.0,
        _get_screen_index(widget),
        metrics.target_fps,
        metrics.interval_ms,
        metrics.frame_count,
        anim_label,
    )


def finalize_render_timer_metrics(widget, outcome: str = "stopped") -> None:
    metrics = widget._render_timer_metrics
    widget._render_timer_metrics = None
    if metrics is None or not is_perf_metrics_enabled():
        return
    elapsed_s = metrics.elapsed_seconds()
    avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
    min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
    max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0
    logger.info(
        "[PERF] [GL RENDER] Timer metrics: screen=%s, frames=%d, wakeups=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "stalls=%d, pending_skips=%d, target=%dHz, outcome=%s",
        _get_screen_index(widget),
        metrics.frame_count,
        metrics.wakeup_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.stall_count,
        metrics.pending_skip_count,
        metrics.target_fps,
        outcome,
    )
