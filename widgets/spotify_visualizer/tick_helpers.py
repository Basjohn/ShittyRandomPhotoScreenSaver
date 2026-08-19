"""Spotify Visualizer Tick Helpers - Extracted from spotify_visualizer_widget.py.

Contains tick-related utility functions, perf metrics, geometry cache,
and visual smoothing logic. All functions accept the widget instance as
the first parameter to preserve the original interface.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, TYPE_CHECKING
import time
import math

from PySide6.QtCore import QRect

from core.logging.logger import get_logger, is_perf_metrics_enabled

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


def init_cadence_state(widget: Any) -> None:
    """Install the visualizer's cadence-ownership attributes.

    `_bars_timer` is the GUI fallback tick; `_logical_runtime` is the
    authoritative Qt-free owner whenever one exists. Exactly one of them drives
    the simulation at a time.
    """

    from widgets.spotify_visualizer.logical_runtime import LatestStateMailbox

    widget._bars_timer = None
    widget._logical_runtime = None
    widget._logical_mailbox = LatestStateMailbox()
    widget._logical_present_pending = False


def authored_logical_interval_s(widget: Any) -> float:
    """The authored logical cadence, independent of transition or playback state.

    Current_Plan section 7.6: the old paused 75-Hz cap and the transition-driven
    retuning belonged to the QTimer architecture. The logical runtime keeps one
    authored service class across active and idle; a genuinely static idle scene
    costs nothing extra because it stops changing its scene revision and physical
    presentation suppression already drops the duplicate redraws.
    """

    try:
        target = float(getattr(widget, "_base_max_fps", 90.0) or 90.0)
    except (TypeError, ValueError):
        target = 90.0
    return 1.0 / max(15.0, target)


def ensure_tick_source(widget: Any) -> None:
    """Ensure the visualizer has exactly one cadence owner.

    The GUI recurring timer is deliberately still that owner.
    `VisualizerLogicalRuntime` exists and is correct, but the logical half of
    `on_tick()` is not yet separable from the GUI: `check_mode_teardown_ready()`
    reaches `begin_mode_fade_in()`, which invalidates the shadow cache, applies
    the pending transition layout and starts the widget fade. Driving that from
    a worker thread silently failed inside the broad handlers and left every
    mode switch with data flowing but nothing visible
    (`set_state=338 paint=0 visible=False`).

    Current_Plan section 7.3 requires the GUI-owned mode-activation/fade work to
    move out of the logical path *before* the thread can own cadence. Until that
    lands, one owner - this timer - drives both halves.

    The interval is the authored logical cadence rather than the old 16ms
    default plus per-tick retuning, so the target service class is unchanged.
    """
    if not widget._enabled:
        return
    if widget._thread_manager is None:
        return
    if widget._bars_timer is not None:
        return
    interval_ms = max(4, int(round(authored_logical_interval_s(widget) * 1000.0)))
    try:
        widget._bars_timer = widget._thread_manager.schedule_recurring(
            interval_ms, widget._on_tick
        )
        widget._target_timer_interval_ms = interval_ms
        widget._current_timer_interval_ms = interval_ms
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to create tick source timer", exc_info=True)
        widget._bars_timer = None


def stop_tick_source(widget: Any) -> None:
    """Quiesce and join the logical runtime, and drop any GUI fallback tick."""
    runtime = getattr(widget, "_logical_runtime", None)
    if runtime is not None:
        widget._logical_runtime = None
        try:
            runtime.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to stop logical runtime", exc_info=True)
    timer = getattr(widget, "_bars_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to stop fallback tick timer", exc_info=True)
        widget._bars_timer = None
    mailbox = getattr(widget, "_logical_mailbox", None)
    if mailbox is not None:
        mailbox.clear()
    widget._logical_present_pending = False

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
        try:
            bubble_result_skips = int(getattr(widget, "_bubble_pending_result_skip_count", 0) or 0)
            if bubble_result_skips > 0:
                logger.warning(
                    "[PERF] [SPOTIFY_VIS][BUBBLE] result_apply_backpressure_skips=%d",
                    bubble_result_skips,
                )
                widget._bubble_pending_result_skip_count = 0
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble PERF metrics logging failed", exc_info=True)
        try:
            bubble_perf = getattr(widget, "_bubble_last_perf_diag", None)
            if isinstance(bubble_perf, dict) and bubble_perf:
                logger.info(
                    "[PERF] [SPOTIFY_VIS][BUBBLE] worker_ms=%.2f tick_ms=%.2f collision_ms=%.2f snapshot_ms=%.2f batch_size=%d pairs=%d overlaps=%d passes=%d active=%d trail_payload=%s trail_floats=%d",
                    float(bubble_perf.get("worker_total_ms", 0.0) or 0.0),
                    float(bubble_perf.get("tick_ms", 0.0) or 0.0),
                    float(bubble_perf.get("collision_ms", 0.0) or 0.0),
                    float(bubble_perf.get("snapshot_ms", 0.0) or 0.0),
                    int(bubble_perf.get("batch_size", 1.0) or 1),
                    int(bubble_perf.get("collision_pairs", 0.0) or 0),
                    int(bubble_perf.get("collision_overlaps", 0.0) or 0),
                    int(bubble_perf.get("collision_passes", 0.0) or 0),
                    int(bubble_perf.get("active_bubbles", 0.0) or 0),
                    bool(bubble_perf.get("snapshot_trail_payload_active", 0.0)),
                    int(bubble_perf.get("snapshot_trail_floats", 0.0) or 0),
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble PERF diagnostics logging failed", exc_info=True)
        try:
            cadence = getattr(widget, "_bubble_cadence_state", None)
            if cadence is not None:
                cadence_diag = cadence.diagnostic_snapshot(reset=reset)
                logger.info(
                    "[PERF] [SPOTIFY_VIS][BUBBLE_CADENCE] offered=%d submitted_tasks=%d "
                    "publish_ratio=%.3f worker_busy_deferrals=%d "
                    "result_waiting_deferrals=%d submission_failures=%d stale_results=%d",
                    int(cadence_diag.get("offered_ticks", 0)),
                    int(cadence_diag.get("submitted_tasks", 0)),
                    float(cadence_diag.get("publish_ratio", 0.0)),
                    int(cadence_diag.get("worker_busy_deferrals", 0)),
                    int(cadence_diag.get("result_waiting_deferrals", 0)),
                    int(cadence_diag.get("submission_failures", 0)),
                    int(getattr(widget, "_bubble_stale_result_count", 0) or 0),
                )
                if reset:
                    widget._bubble_stale_result_count = 0
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble cadence PERF logging failed", exc_info=True)
        try:
            lane = getattr(widget, "_bubble_compute_lane", None)
            if lane is not None:
                lane_diag = lane.diagnostic_snapshot()
                logger.info(
                    "[PERF] [SPOTIFY_VIS][BUBBLE_LANE] lane_registrations=%d "
                    "executor_tasks=%d logical_steps=%d completed=%d published=%d "
                    "rejected_busy=%d rejected_stopped=%d cancelled=%d "
                    "handoff_ms_mean=%.3f handoff_ms_max=%.3f "
                    "execution_ms_mean=%.3f execution_ms_max=%.3f "
                    "callback_ms_mean=%.3f callback_ms_max=%.3f",
                    int(lane_diag.get("lane_registrations", 0)),
                    int(lane_diag.get("executor_task_submissions", 0)),
                    int(lane_diag.get("logical_steps_accepted", 0)),
                    int(lane_diag.get("logical_steps_completed", 0)),
                    int(lane_diag.get("logical_steps_published", 0)),
                    int(lane_diag.get("submit_rejected_busy", 0)),
                    int(lane_diag.get("submit_rejected_stopped", 0)),
                    int(lane_diag.get("pending_cancelled", 0)),
                    float(lane_diag.get("handoff_ms_mean", 0.0)),
                    float(lane_diag.get("handoff_ms_max", 0.0)),
                    float(lane_diag.get("execution_ms_mean", 0.0)),
                    float(lane_diag.get("execution_ms_max", 0.0)),
                    float(lane_diag.get("callback_ms_mean", 0.0)),
                    float(lane_diag.get("callback_ms_max", 0.0)),
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble lane PERF logging failed", exc_info=True)
        try:
            engine = getattr(widget, "_engine", None)
            take_lane_diag = getattr(
                engine,
                "take_analysis_lane_diagnostics_for_log",
                None,
            )
            analysis_diag = (
                take_lane_diag(min_interval_seconds=2.0)
                if callable(take_lane_diag)
                else {}
            )
            if analysis_diag:
                logger.info(
                    "[PERF] [SPOTIFY_VIS][AUDIO_LANE] lane_registrations=%d "
                    "executor_tasks=%d logical_steps=%d completed=%d published=%d "
                    "rejected_busy=%d rejected_stopped=%d cancelled=%d "
                    "handoff_ms_mean=%.3f handoff_ms_max=%.3f "
                    "execution_ms_mean=%.3f execution_ms_max=%.3f "
                    "callback_ms_mean=%.3f callback_ms_max=%.3f",
                    int(analysis_diag.get("lane_registrations", 0)),
                    int(analysis_diag.get("executor_task_submissions", 0)),
                    int(analysis_diag.get("logical_steps_accepted", 0)),
                    int(analysis_diag.get("logical_steps_completed", 0)),
                    int(analysis_diag.get("logical_steps_published", 0)),
                    int(analysis_diag.get("submit_rejected_busy", 0)),
                    int(analysis_diag.get("submit_rejected_stopped", 0)),
                    int(analysis_diag.get("pending_cancelled", 0)),
                    float(analysis_diag.get("handoff_ms_mean", 0.0)),
                    float(analysis_diag.get("handoff_ms_max", 0.0)),
                    float(analysis_diag.get("execution_ms_mean", 0.0)),
                    float(analysis_diag.get("execution_ms_max", 0.0)),
                    float(analysis_diag.get("callback_ms_mean", 0.0)),
                    float(analysis_diag.get("callback_ms_max", 0.0)),
                )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Audio-analysis lane PERF logging failed",
                exc_info=True,
            )
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
            if hasattr(widget, "_bubble_pending_result_skip_count"):
                widget._bubble_pending_result_skip_count = 0
