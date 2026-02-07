"""Spotify Visualizer Tick Helpers - Extracted from spotify_visualizer_widget.py.

Contains tick-related utility functions, perf metrics, geometry cache,
and visual smoothing logic. All functions accept the widget instance as
the first parameter to preserve the original interface.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, TYPE_CHECKING
import time
import math
import random

from PySide6.QtCore import QRect

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Transition context & FPS helpers
# ------------------------------------------------------------------

def get_transition_context(widget: Any, parent: Optional[QWidget]) -> Dict[str, Any]:
    """Return lightweight transition metrics from the parent DisplayWidget."""
    ctx: Dict[str, Any] = {
        "running": False,
        "name": None,
        "elapsed": None,
        "first_run": False,
        "idle_age": None,
    }
    if parent is None:
        return ctx
    snapshot = None
    if hasattr(parent, "get_transition_snapshot"):
        try:
            snapshot = parent.get_transition_snapshot()
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
            snapshot = None
    if isinstance(snapshot, dict):
        ctx.update(snapshot)
    elif hasattr(parent, "has_running_transition") and parent.has_running_transition():
        ctx["running"] = True
        ctx["name"] = None
        ctx["elapsed"] = None
    return ctx


def resolve_max_fps(widget: Any, transition_ctx: Dict[str, Any]) -> float:
    """Determine the FPS cap based on transition activity."""
    max_fps = widget._base_max_fps  # 90Hz default
    idle_age = transition_ctx.get("idle_age")
    if idle_age is not None and idle_age >= widget._idle_fps_boost_delay:
        max_fps = min(widget._idle_max_fps, widget._base_max_fps + 10.0)
    return max(15.0, float(max_fps))


def update_timer_interval(widget: Any, max_fps: float) -> None:
    """Retune the ThreadManager recurring timer interval if needed."""
    interval_ms = max(4, int(round(1000.0 / max_fps)))
    if interval_ms == widget._current_timer_interval_ms:
        return
    widget._current_timer_interval_ms = interval_ms
    # Add a tiny jitter so we don't align perfectly with compositor vsync.
    jitter = random.randint(0, 2) if interval_ms >= 8 else 0
    new_interval = interval_ms + jitter
    timer = widget._bars_timer
    if timer is not None:
        try:
            timer.setInterval(new_interval)
            widget._current_timer_interval_ms = new_interval
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def pause_timer_during_transition(widget: Any, is_transition_active: bool) -> None:
    """Pause dedicated timer during transitions to avoid contention.

    PERFORMANCE FIX: When AnimationManager is active during transitions,
    it provides tick callbacks. Running BOTH the dedicated timer AND
    AnimationManager causes timer contention and 50-100ms dt spikes.

    Pause the dedicated timer during transitions, resume when idle.
    """
    timer = widget._bars_timer
    if timer is None:
        return

    try:
        if is_transition_active and widget._using_animation_ticks:
            # Transition active with AnimationManager - pause dedicated timer
            if timer.isActive():
                timer.stop()
        else:
            # No transition or no AnimationManager - ensure timer is running
            if not timer.isActive() and widget._enabled:
                timer.start()
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def log_tick_spike(widget: Any, dt: float, transition_ctx: Dict[str, Any]) -> None:
    """Log dt spikes with surrounding transition context."""
    now = time.time()
    if (now - widget._last_tick_spike_log_ts) < widget._dt_spike_log_cooldown:
        return
    widget._last_tick_spike_log_ts = now
    running = transition_ctx.get("running")
    name = transition_ctx.get("name")
    elapsed = transition_ctx.get("elapsed")
    idle_age = transition_ctx.get("idle_age")
    logger.warning(
        "[PERF] [SPOTIFY_VIS] Tick dt spike %.2fms (running=%s name=%s elapsed=%s idle_age=%s)",
        dt * 1000.0,
        running,
        name or "<none>",
        f"{elapsed:.2f}" if isinstance(elapsed, (int, float)) else "<n/a>",
        f"{idle_age:.2f}" if isinstance(idle_age, (int, float)) else "<n/a>",
    )


# ------------------------------------------------------------------
# Geometry cache
# ------------------------------------------------------------------

def rebuild_geometry_cache(widget: Any, rect: QRect) -> None:
    """Recompute cached bar/segment layout for the current geometry."""

    count = widget._bar_count
    if hasattr(widget, '_dynamic_bar_segments'):
        segments = max(1, widget._dynamic_bar_segments())
    else:
        segments = max(1, getattr(widget, "_bar_segments_base", 18))
    if rect.width() <= 0 or rect.height() <= 0 or count <= 0:
        widget._geom_cache_rect = QRect()
        widget._geom_cache_bar_count = count
        widget._geom_cache_segments = segments
        widget._geom_bar_x = []
        widget._geom_seg_y = []
        widget._geom_bar_width = 0
        widget._geom_seg_height = 0
        return

    margin_x = 8
    margin_y = 6
    inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
    if inner.width() <= 0 or inner.height() <= 0:
        widget._geom_cache_rect = inner
        widget._geom_cache_bar_count = count
        widget._geom_cache_segments = segments
        widget._geom_bar_x = []
        widget._geom_seg_y = []
        widget._geom_bar_width = 0
        widget._geom_seg_height = 0
        return

    gap = 2
    total_gap = gap * (count - 1) if count > 1 else 0
    bars_inset = 5
    bar_region_width = inner.width() - (bars_inset * 2)
    if bar_region_width <= 0:
        widget._geom_cache_rect = inner
        widget._geom_cache_bar_count = count
        widget._geom_cache_segments = segments
        widget._geom_bar_x = []
        widget._geom_seg_y = []
        widget._geom_bar_width = 0
        widget._geom_seg_height = 0
        return

    usable_width = max(0, bar_region_width - total_gap)
    bar_width = max(1, int(usable_width / max(1, count)))
    span = bar_width * count + total_gap
    remaining = max(0, bar_region_width - span)
    # Center the bar field horizontally within the usable region so rounding
    # differences never bias to the right.
    x0 = inner.left() + bars_inset + (remaining // 2)
    bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

    seg_gap = 1
    total_seg_gap = seg_gap * max(0, segments - 1)
    seg_height = max(1, int((inner.height() - total_seg_gap) / max(1, segments)))
    base_bottom = inner.bottom()
    seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

    widget._geom_cache_rect = inner
    widget._geom_cache_bar_count = count
    widget._geom_cache_segments = segments
    widget._geom_bar_x = bar_x
    widget._geom_seg_y = seg_y
    widget._geom_bar_width = bar_width
    widget._geom_seg_height = seg_height


# ------------------------------------------------------------------
# Visual smoothing
# ------------------------------------------------------------------

def apply_visual_smoothing(widget: Any, target_bars: List[float], now_ts: float) -> bool:
    """Lightweight post-bar smoothing to calm jitter without hurting response."""
    changed = False
    visual = widget._visual_bars
    count = widget._bar_count
    last_ts = widget._last_visual_smooth_ts

    if last_ts <= 0.0 or (now_ts - last_ts) > 0.4:
        for i in range(count):
            val = target_bars[i] if i < len(target_bars) else 0.0
            if i < len(visual):
                if abs(visual[i] - val) > 1e-4:
                    changed = True
                visual[i] = val
            else:
                visual.append(val)
                changed = True
        widget._visual_bars = visual[:count]
        widget._last_visual_smooth_ts = now_ts
        return changed

    dt = max(1e-4, now_ts - last_ts)
    tau_rise = widget._visual_smoothing_tau
    tau_decay = tau_rise * 2.6
    alpha_rise = 1.0 - math.exp(-dt / tau_rise)
    alpha_decay = 1.0 - math.exp(-dt / tau_decay)
    alpha_rise = max(0.0, min(1.0, alpha_rise))
    alpha_decay = max(0.0, min(1.0, alpha_decay))

    for i in range(count):
        cur = visual[i] if i < len(visual) else 0.0
        tgt = target_bars[i] if i < len(target_bars) else 0.0
        alpha = alpha_rise if tgt >= cur else alpha_decay
        nxt = cur + (tgt - cur) * alpha
        if abs(nxt) < 1e-4:
            nxt = 0.0
        if abs(nxt - cur) > 1e-4:
            changed = True
        if i < len(visual):
            visual[i] = nxt
        else:
            visual.append(nxt)

    if len(visual) > count:
        del visual[count:]

    widget._visual_bars = visual
    widget._last_visual_smooth_ts = now_ts
    return changed


# ------------------------------------------------------------------
# PERF metrics snapshot
# ------------------------------------------------------------------

def log_perf_snapshot(widget: Any, reset: bool = False) -> None:
    """Emit a PERF metrics snapshot for the current tick/paint window.

    When ``reset`` is True, internal counters are cleared afterwards so
    subsequent snapshots start a fresh window (used on widget stop).
    When ``reset`` is False, counters are left intact so that periodic
    logging during runtime does not disturb the measurement window.
    """

    if not is_perf_metrics_enabled():
        return

    try:
        if (
            widget._perf_tick_start_ts is not None
            and widget._perf_tick_last_ts is not None
            and widget._perf_tick_frame_count > 0
        ):
            elapsed = max(0.0, widget._perf_tick_last_ts - widget._perf_tick_start_ts)
            if elapsed > 0.0:
                duration_ms = elapsed * 1000.0
                avg_fps = widget._perf_tick_frame_count / elapsed
                min_dt_ms = widget._perf_tick_min_dt * 1000.0 if widget._perf_tick_min_dt > 0.0 else 0.0
                max_dt_ms = widget._perf_tick_max_dt * 1000.0 if widget._perf_tick_max_dt > 0.0 else 0.0
                logger.info(
                    "[PERF] [SPOTIFY_VIS] Tick metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                    "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                    duration_ms,
                    widget._perf_tick_frame_count,
                    avg_fps,
                    min_dt_ms,
                    max_dt_ms,
                    widget._bar_count,
                )

        if (
            widget._perf_paint_start_ts is not None
            and widget._perf_paint_last_ts is not None
            and widget._perf_paint_frame_count > 0
        ):
            elapsed_p = max(0.0, widget._perf_paint_last_ts - widget._perf_paint_start_ts)
            if elapsed_p > 0.0:
                duration_ms_p = elapsed_p * 1000.0
                avg_fps_p = widget._perf_paint_frame_count / elapsed_p
                min_dt_ms_p = widget._perf_paint_min_dt * 1000.0 if widget._perf_paint_min_dt > 0.0 else 0.0
                max_dt_ms_p = widget._perf_paint_max_dt * 1000.0 if widget._perf_paint_max_dt > 0.0 else 0.0
                logger.info(
                    "[PERF] [SPOTIFY_VIS] Paint metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                    "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                    duration_ms_p,
                    widget._perf_paint_frame_count,
                    avg_fps_p,
                    min_dt_ms_p,
                    max_dt_ms_p,
                    widget._bar_count,
                )
        # Emit a separate AudioLag metrics line so tools that parse
        # Tick/Paint summaries remain compatible.
        try:
            if widget._perf_audio_lag_last_ms > 0.0:
                logger.info(
                    "[PERF] [SPOTIFY_VIS] AudioLag metrics: last=%.2fms, min=%.2fms, max=%.2fms",
                    widget._perf_audio_lag_last_ms,
                    widget._perf_audio_lag_min_ms,
                    widget._perf_audio_lag_max_ms,
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] AudioLag PERF metrics logging failed", exc_info=True)
    except Exception:
        logger.debug("[SPOTIFY_VIS] PERF metrics logging failed", exc_info=True)
    finally:
        if reset:
            widget._perf_tick_start_ts = None
            widget._perf_tick_last_ts = None
            widget._perf_tick_frame_count = 0
            widget._perf_tick_min_dt = 0.0
            widget._perf_tick_max_dt = 0.0
            widget._perf_paint_start_ts = None
            widget._perf_paint_last_ts = None
            widget._perf_paint_frame_count = 0
            widget._perf_paint_min_dt = 0.0
            widget._perf_paint_max_dt = 0.0
            widget._perf_audio_lag_last_ms = 0.0
            widget._perf_audio_lag_min_ms = 0.0
            widget._perf_audio_lag_max_ms = 0.0
