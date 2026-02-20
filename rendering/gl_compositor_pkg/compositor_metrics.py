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
        "[PERF] [GL ANIM] Tick dt spike %.2fms (name=%s frame=%d progress=%.2f target_fps=%d)",
        dt_ms,
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
        "[PERF] [GL ANIM] %s metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
        "dt_min=%.2fms, dt_max=%.2fms, spikes=%d, target_fps=%d, outcome=%s",
        metrics.name.capitalize(),
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
    metrics = widget._paint_metrics
    if metrics is None:
        return
    dt_seconds = metrics.record(paint_duration_ms)
    now = time.time()
    if paint_duration_ms > widget._paint_slow_threshold_ms:
        if now - widget._paint_warning_last_ts > 0.5:
            logger.warning(
                "[PERF] [GL PAINT] Slow paintGL %.2fms (transition=%s)",
                paint_duration_ms,
                metrics.label,
            )
            widget._paint_warning_last_ts = now
    if dt_seconds is not None and dt_seconds * 1000.0 > 120.0:
        if now - widget._paint_warning_last_ts > 0.5:
            logger.warning(
                "[PERF] [GL PAINT] Paint gap %.2fms (transition=%s)",
                dt_seconds * 1000.0,
                metrics.label,
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
    logger.info(
        "[PERF] [GL PAINT] %s metrics: frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "dur_min=%.2fms, dur_max=%.2fms, slow_frames=%d, outcome=%s",
        metrics.label.capitalize(),
        metrics.frame_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.min_duration_ms,
        metrics.max_duration_ms,
        metrics.slow_count,
        outcome,
    )


# ------------------------------------------------------------------
# Render timer metrics
# ------------------------------------------------------------------

def record_render_timer_tick(widget) -> None:
    metrics = widget._render_timer_metrics
    if metrics is None or not is_perf_metrics_enabled():
        return
    dt = metrics.record_tick()
    if dt is None:
        return
    if metrics.should_log_stall(dt):
        log_render_timer_stall(widget, dt, metrics)


def log_render_timer_stall(widget, dt_seconds: float, metrics: _RenderTimerMetrics) -> None:
    if not is_perf_metrics_enabled():
        return
    anim_label = widget._current_anim_metrics.name if widget._current_anim_metrics else "idle"
    logger.warning(
        "[PERF] [GL RENDER] Render timer stall %.2fms (target=%dHz interval=%dms frames=%d anim=%s)",
        dt_seconds * 1000.0,
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
        "[PERF] [GL RENDER] Timer metrics: frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
        "stalls=%d, target=%dHz, outcome=%s",
        metrics.frame_count,
        avg_fps,
        min_dt_ms,
        max_dt_ms,
        metrics.stall_count,
        metrics.target_fps,
        outcome,
    )
