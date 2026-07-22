"""Spotify Visualizer Tick Helpers - Extracted from spotify_visualizer_widget.py.

Contains tick-related utility functions, perf metrics, geometry cache,
and visual smoothing logic. All functions accept the widget instance as
the first parameter to preserve the original interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, TYPE_CHECKING
import time
import math
import threading

from PySide6.QtCore import QRect

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.threading.manager import TaskPriority, ThreadManager

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

logger = get_logger(__name__)


# ------------------------------------------------------------------
# Transition context & FPS helpers
# ------------------------------------------------------------------

def _parent_transition_running(widget: Any) -> bool:
    parent = widget.parent()
    if parent is None:
        return False
    if hasattr(parent, "get_transition_snapshot"):
        try:
            snapshot = parent.get_transition_snapshot()
            return bool(snapshot.get("running", False)) if isinstance(snapshot, dict) else False
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to read transition snapshot", exc_info=True)
            return False
    if hasattr(parent, "has_running_transition"):
        try:
            return bool(parent.has_running_transition())
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to query transition state", exc_info=True)
            return False
    return False


def attach_to_animation_manager(widget: Any, animation_manager: Any) -> None:
    """Remember the transition AnimationManager without subscribing to it.

    Visualizer ticks must not run inside the transition animation manager.  The
    logs showed that doing full visualizer work as an animation tick listener
    can collapse transition callback cadence (notably the 60Hz display into a
    stable ~40Hz lane).  The visualizer keeps its own steady tick source so the
    transition manager remains responsible for transition timing only.
    """
    if widget._animation_manager is not None and widget._anim_listener_id is not None:
        disable_animation_tick_listener(widget)
    widget._animation_manager = animation_manager
    widget._using_animation_ticks = False
    ensure_tick_source(widget)


def enable_animation_tick_listener(widget: Any) -> None:
    """Legacy helper kept inert unless a future caller explicitly opts in.

    Normal runtime must not call this from transition handoff; visualizer ticks
    stay on the dedicated recurring timer.
    """
    if widget._animation_manager is None or widget._anim_listener_id is not None:
        return

    try:
        def _tick_listener(dt: float) -> None:
            if not widget._enabled:
                return
            if not _parent_transition_running(widget):
                disable_animation_tick_listener(widget)
                pause_timer_during_transition(widget, False)
                return
            widget._on_tick()

        listener_id = widget._animation_manager.add_tick_listener(_tick_listener)
        widget._anim_listener_id = listener_id
        widget._using_animation_ticks = True
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to attach to AnimationManager", exc_info=True)
        widget._anim_listener_id = None
        widget._using_animation_ticks = False


def disable_animation_tick_listener(widget: Any) -> None:
    """Detach any legacy AnimationManager tick listener."""
    am = widget._animation_manager
    listener_id = widget._anim_listener_id
    if am is not None and listener_id is not None and hasattr(am, "remove_tick_listener"):
        try:
            am.remove_tick_listener(listener_id)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager", exc_info=True)
    widget._anim_listener_id = None
    widget._using_animation_ticks = False


def detach_from_animation_manager(widget: Any) -> None:
    """Fully detach from AnimationManager and keep steady timer ownership."""
    disable_animation_tick_listener(widget)
    widget._animation_manager = None
    ensure_tick_source(widget)


def ensure_tick_source(widget: Any) -> None:
    """Ensure the steady recurring timer exists when the visualizer is enabled."""
    if not widget._enabled:
        return
    if widget._thread_manager is not None and widget._bars_timer is None:
        try:
            widget._bars_timer = widget._thread_manager.schedule_recurring(16, widget._on_tick)
            widget._target_timer_interval_ms = 16
            widget._current_timer_interval_ms = 16
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to create tick source timer", exc_info=True)
            widget._bars_timer = None

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
    if not bool(getattr(widget, "_spotify_playing", False)):
        # Paused idle-reveal modes remain animated, but they must not inherit
        # the no-transition live-playback boost. Keep oversampling headroom for
        # low-refresh owners instead of dropping accepted overlay repaints.
        max_fps = min(
            max_fps,
            float(getattr(widget, "_paused_idle_max_fps", 75.0)),
        )
    elif idle_age is not None and idle_age >= widget._idle_fps_boost_delay:
        max_fps = min(widget._idle_max_fps, widget._base_max_fps + 10.0)
    return max(15.0, float(max_fps))


def update_timer_interval(widget: Any, max_fps: float) -> None:
    """Retune the ThreadManager recurring timer interval if needed."""
    interval_ms = max(4, int(round(1000.0 / max_fps)))
    current_target = int(
        getattr(
            widget,
            "_target_timer_interval_ms",
            getattr(widget, "_current_timer_interval_ms", interval_ms),
        )
    )
    current_live = int(getattr(widget, "_current_timer_interval_ms", current_target))
    if interval_ms == current_target and current_live == interval_ms:
        return
    widget._target_timer_interval_ms = interval_ms
    timer = widget._bars_timer
    if timer is not None:
        try:
            timer.setInterval(interval_ms)
            widget._current_timer_interval_ms = interval_ms
        except Exception as e:
            logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def pause_timer_during_transition(widget: Any, is_transition_active: bool) -> None:
    """Keep the visualizer on its own tick source during transitions."""
    timer = widget._bars_timer
    if timer is None:
        ensure_tick_source(widget)
        return

    try:
        if getattr(widget, "_using_animation_ticks", False):
            disable_animation_tick_listener(widget)
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
    mode = str(getattr(widget, "_vis_mode_str", "unknown") or "unknown")
    phase = int(getattr(widget, "_mode_transition_phase", 0) or 0)
    pending = getattr(widget, "_mode_transition_pending", None)
    pending_mode = getattr(pending, "name", None) if pending is not None else None
    waiting_engine = bool(getattr(widget, "_waiting_for_fresh_engine_frame", False))
    waiting_frame = bool(getattr(widget, "_waiting_for_fresh_frame", False))
    logger.warning(
        "[PERF] [SPOTIFY_VIS] Tick dt spike_ms=%.2f mode=%s phase=%d pending=%s waiting_engine=%s waiting_frame=%s transition_running=%s transition_name=%s transition_elapsed=%s idle_age=%s",
        dt * 1000.0,
        mode,
        phase,
        pending_mode or "<none>",
        waiting_engine,
        waiting_frame,
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
    decay_mult = 2.0
    if getattr(widget, '_vis_mode_str', '') == 'spectrum':
        drop = max(0.5, min(3.0, getattr(widget, '_spectrum_drop_speed', 1.0)))
        decay_mult = max(0.3, 2.0 / drop)
    tau_decay = tau_rise * decay_mult
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

@dataclass(frozen=True, slots=True)
class VisualizerPerfSnapshot:
    tick: Optional[tuple[float, int, float, float, float]]
    paint: Optional[tuple[float, int, float, float, float]]
    audio_lag: Optional[tuple[float, float, float]]
    bar_count: int
    bubble_result_skips: int
    bubble: Optional[tuple[float, float, float, float, int, int, int, int, bool, int]]
    devcurve: Optional[tuple[float, bool]]


_PERF_EMIT_LOCK = threading.Lock()
_PERF_EMIT_INFLIGHT: set[int] = set()


def _window_metrics(
    start_ts: Any,
    end_ts: Any,
    frame_count: Any,
    min_dt: Any,
    max_dt: Any,
) -> Optional[tuple[float, int, float, float, float]]:
    try:
        frames = int(frame_count or 0)
        if start_ts is None or end_ts is None or frames <= 0:
            return None
        elapsed = max(0.0, float(end_ts) - float(start_ts))
        if elapsed <= 0.0:
            return None
        return (
            elapsed * 1000.0,
            frames,
            frames / elapsed,
            max(0.0, float(min_dt or 0.0) * 1000.0),
            max(0.0, float(max_dt or 0.0) * 1000.0),
        )
    except (TypeError, ValueError):
        return None


def capture_perf_snapshot(widget: Any, *, reset: bool = False) -> VisualizerPerfSnapshot:
    """Capture primitive diagnostics on the owner thread without log I/O."""

    tick = _window_metrics(
        getattr(widget, "_perf_tick_start_ts", None),
        getattr(widget, "_perf_tick_last_ts", None),
        getattr(widget, "_perf_tick_frame_count", 0),
        getattr(widget, "_perf_tick_min_dt", 0.0),
        getattr(widget, "_perf_tick_max_dt", 0.0),
    )
    paint = _window_metrics(
        getattr(widget, "_perf_paint_start_ts", None),
        getattr(widget, "_perf_paint_last_ts", None),
        getattr(widget, "_perf_paint_frame_count", 0),
        getattr(widget, "_perf_paint_min_dt", 0.0),
        getattr(widget, "_perf_paint_max_dt", 0.0),
    )
    audio_lag = None
    try:
        last_audio_lag = float(getattr(widget, "_perf_audio_lag_last_ms", 0.0) or 0.0)
        if last_audio_lag > 0.0:
            audio_lag = (
                last_audio_lag,
                float(getattr(widget, "_perf_audio_lag_min_ms", 0.0) or 0.0),
                float(getattr(widget, "_perf_audio_lag_max_ms", 0.0) or 0.0),
            )
    except (TypeError, ValueError):
        audio_lag = None

    bubble_result_skips = int(
        getattr(widget, "_bubble_pending_result_skip_count", 0) or 0
    )
    bubble = None
    bubble_perf = getattr(widget, "_bubble_last_perf_diag", None)
    if isinstance(bubble_perf, dict) and bubble_perf:
        bubble = (
            float(bubble_perf.get("worker_total_ms", 0.0) or 0.0),
            float(bubble_perf.get("tick_ms", 0.0) or 0.0),
            float(bubble_perf.get("collision_ms", 0.0) or 0.0),
            float(bubble_perf.get("snapshot_ms", 0.0) or 0.0),
            int(bubble_perf.get("collision_pairs", 0.0) or 0),
            int(bubble_perf.get("collision_overlaps", 0.0) or 0),
            int(bubble_perf.get("collision_passes", 0.0) or 0),
            int(bubble_perf.get("active_bubbles", 0.0) or 0),
            bool(bubble_perf.get("snapshot_trail_payload_active", 0.0)),
            int(bubble_perf.get("snapshot_trail_floats", 0.0) or 0),
        )

    devcurve = None
    devcurve_perf = getattr(widget, "_devcurve_last_perf_diag", None)
    if isinstance(devcurve_perf, dict) and devcurve_perf:
        has_pending_devcurve = getattr(widget, "_has_pending_devcurve_work", None)
        devcurve = (
            float(devcurve_perf.get("worker_total_ms", 0.0) or 0.0),
            bool(has_pending_devcurve()) if callable(has_pending_devcurve) else False,
        )

    if bubble_result_skips > 0:
        widget._bubble_pending_result_skip_count = 0
    if reset:
        for name, value in (
            ("_perf_tick_start_ts", None),
            ("_perf_tick_last_ts", None),
            ("_perf_tick_frame_count", 0),
            ("_perf_tick_min_dt", 0.0),
            ("_perf_tick_max_dt", 0.0),
            ("_perf_paint_start_ts", None),
            ("_perf_paint_last_ts", None),
            ("_perf_paint_frame_count", 0),
            ("_perf_paint_min_dt", 0.0),
            ("_perf_paint_max_dt", 0.0),
            ("_perf_audio_lag_last_ms", 0.0),
            ("_perf_audio_lag_min_ms", 0.0),
            ("_perf_audio_lag_max_ms", 0.0),
        ):
            setattr(widget, name, value)

    return VisualizerPerfSnapshot(
        tick=tick,
        paint=paint,
        audio_lag=audio_lag,
        bar_count=int(getattr(widget, "_bar_count", 0) or 0),
        bubble_result_skips=bubble_result_skips,
        bubble=bubble,
        devcurve=devcurve,
    )


def emit_perf_snapshot(snapshot: VisualizerPerfSnapshot) -> None:
    """Format and emit an immutable snapshot from an IO worker."""

    if snapshot.tick is not None:
        duration_ms, frames, avg_fps, min_dt_ms, max_dt_ms = snapshot.tick
        logger.info(
            "[PERF] [SPOTIFY_VIS] Tick metrics: duration=%.1fms, frames=%d, "
            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
            duration_ms,
            frames,
            avg_fps,
            min_dt_ms,
            max_dt_ms,
            snapshot.bar_count,
        )
    if snapshot.paint is not None:
        duration_ms, frames, avg_fps, min_dt_ms, max_dt_ms = snapshot.paint
        logger.info(
            "[PERF] [SPOTIFY_VIS] Paint metrics: duration=%.1fms, frames=%d, "
            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
            duration_ms,
            frames,
            avg_fps,
            min_dt_ms,
            max_dt_ms,
            snapshot.bar_count,
        )
    if snapshot.audio_lag is not None:
        logger.info(
            "[PERF] [SPOTIFY_VIS] AudioLag metrics: last=%.2fms, min=%.2fms, max=%.2fms",
            *snapshot.audio_lag,
        )
    if snapshot.bubble_result_skips > 0:
        logger.warning(
            "[PERF] [SPOTIFY_VIS][BUBBLE] result_apply_backpressure_skips=%d",
            snapshot.bubble_result_skips,
        )
    if snapshot.bubble is not None:
        logger.info(
            "[PERF] [SPOTIFY_VIS][BUBBLE] worker_ms=%.2f tick_ms=%.2f "
            "collision_ms=%.2f snapshot_ms=%.2f pairs=%d overlaps=%d passes=%d "
            "active=%d trail_payload=%s trail_floats=%d",
            *snapshot.bubble,
        )
    if snapshot.devcurve is not None:
        logger.info(
            "[PERF] [SPOTIFY_VIS][DEVCURVE] worker_ms=%.2f pending=%s",
            *snapshot.devcurve,
        )


def log_perf_snapshot(widget: Any, reset: bool = False) -> None:
    """Capture on the owner thread and emit through the shared IO pool."""

    if not is_perf_metrics_enabled():
        return
    snapshot = capture_perf_snapshot(widget, reset=reset)
    owner_id = id(widget)
    with _PERF_EMIT_LOCK:
        if owner_id in _PERF_EMIT_INFLIGHT:
            return
        _PERF_EMIT_INFLIGHT.add(owner_id)

    def _emit() -> None:
        try:
            emit_perf_snapshot(snapshot)
        finally:
            with _PERF_EMIT_LOCK:
                _PERF_EMIT_INFLIGHT.discard(owner_id)

    manager = getattr(widget, "_thread_manager", None) or ThreadManager.get_app_shared()
    try:
        if manager is None:
            raise RuntimeError("app-shared ThreadManager unavailable")
        manager.submit_io_task(
            _emit,
            priority=TaskPriority.LOW,
        )
    except Exception:
        with _PERF_EMIT_LOCK:
            _PERF_EMIT_INFLIGHT.discard(owner_id)
        if reset:
            emit_perf_snapshot(snapshot)
