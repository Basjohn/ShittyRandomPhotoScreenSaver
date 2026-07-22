"""GL Compositor Metrics — Extracted from gl_compositor.py.

Contains all perf-gated animation, paint, and render-timer metric
instrumentation.  Every function takes the compositor widget as the
first argument so the main class stays lean.
"""
from __future__ import annotations

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

_PAINT_PATH_WINDOW_S = 10.0
_PAINT_PATHS = (
    "idle_gl",
    "transition_gl",
    "idle_qpainter_fallback",
    "transition_qpainter_fallback",
)


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


def record_paint_metrics(widget, paint_duration_ms: float) -> None:
    if not is_perf_metrics_enabled():
        return
    _record_paint_path_window(widget, paint_duration_ms)
    metrics = widget._paint_metrics
    if metrics is None:
        return
    dt_seconds = metrics.record(paint_duration_ms)
    now = time.time()
    stall_context = _get_stall_context(widget)
    active_transition_window = _is_active_transition_paint_window(stall_context)
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


def _record_paint_path_window(widget, paint_duration_ms: float) -> None:
    """Aggregate paint architecture evidence without per-frame logging."""

    path = str(getattr(widget, "_last_paint_path", "") or "")
    if path not in _PAINT_PATHS:
        return
    now = time.monotonic()
    window = getattr(widget, "_paint_path_window", None)
    if not isinstance(window, dict):
        window = {
            "started": now,
            "counts": [0, 0, 0, 0],
            "totals": [0.0, 0.0, 0.0, 0.0],
            "maxima": [0.0, 0.0, 0.0, 0.0],
        }
        widget._paint_path_window = window

    index = _PAINT_PATHS.index(path)
    counts = window["counts"]
    totals = window["totals"]
    maxima = window["maxima"]
    counts[index] += 1
    totals[index] += float(paint_duration_ms)
    maxima[index] = max(maxima[index], float(paint_duration_ms))

    elapsed_s = max(0.0, now - float(window["started"]))
    if elapsed_s < _PAINT_PATH_WINDOW_S:
        return

    payload: list[object] = [
        _get_screen_index(widget),
        elapsed_s * 1000.0,
        sum(counts),
    ]
    for path_index in range(len(_PAINT_PATHS)):
        count = int(counts[path_index])
        payload.extend(
            [
                count,
                (float(totals[path_index]) / count) if count else 0.0,
                float(maxima[path_index]),
            ]
        )
    logger.info(
        "[PERF] [GL PAINT PATH] screen=%s elapsed_ms=%.1f total=%d "
        "idle_gl=%d idle_gl_avg_ms=%.3f idle_gl_max_ms=%.3f "
        "transition_gl=%d transition_gl_avg_ms=%.3f transition_gl_max_ms=%.3f "
        "idle_qpainter_fallback=%d idle_qpainter_avg_ms=%.3f idle_qpainter_max_ms=%.3f "
        "transition_qpainter_fallback=%d transition_qpainter_avg_ms=%.3f "
        "transition_qpainter_max_ms=%.3f",
        *payload,
    )
    widget._paint_path_window = {
        "started": now,
        "counts": [0, 0, 0, 0],
        "totals": [0.0, 0.0, 0.0, 0.0],
        "maxima": [0.0, 0.0, 0.0, 0.0],
    }


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
    logger.info(
        "[PERF] [GL PAINT] %s metrics: screen=%s, frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "dur_min=%.2fms, dur_max=%.2fms, slow_frames=%d, target_fps=%d, outcome=%s",
        metrics.label.capitalize(),
        _get_screen_index(widget),
        metrics.frame_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.min_duration_ms,
        metrics.max_duration_ms,
        metrics.slow_count,
        target_fps,
        outcome,
    )


# ------------------------------------------------------------------
# Render timer metrics
# ------------------------------------------------------------------

def record_render_timer_tick(widget, *, accepted_update: bool = True) -> None:
    metrics = widget._render_timer_metrics
    if metrics is None or not is_perf_metrics_enabled():
        return
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
    dirty_generation = int(
        getattr(widget, "_presentation_dirty_generation", 0) or 0
    )
    ack_generation = int(
        getattr(widget, "_presentation_ack_generation", 0) or 0
    )
    generation_lag = max(0, dirty_generation - ack_generation)
    source_counts = getattr(widget, "_presentation_source_counts", {})
    visualizer_requests = (
        int(source_counts.get("visualizer", 0) or 0)
        if isinstance(source_counts, dict)
        else 0
    )
    logger.info(
        "[PERF] [GL RENDER] Timer metrics: screen=%s, frames=%d, wakeups=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "stalls=%d, pending_skips=%d, target=%dHz, dirty_generation=%d, "
        "ack_generation=%d, generation_lag=%d, visualizer_requests=%d, outcome=%s",
        _get_screen_index(widget),
        metrics.frame_count,
        metrics.wakeup_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.stall_count,
        metrics.pending_skip_count,
        metrics.target_fps,
        dirty_generation,
        ack_generation,
        generation_lag,
        visualizer_requests,
        outcome,
    )
