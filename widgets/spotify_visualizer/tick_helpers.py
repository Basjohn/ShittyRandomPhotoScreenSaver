"""Qt-free visualizer logical-tick diagnostics retained after Phase I cleanup.

Only logical dt-spike and PERF snapshot reporting remain here.  QWidget timer,
geometry-cache, transition-parent and visual-smoothing helpers were presenter-era
residue with no production caller after the retained Quick cutover.
"""
from __future__ import annotations

import time
from typing import Any, Dict

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)


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
            bubble_perf = getattr(widget, "_bubble_last_perf_diag", None)
            if isinstance(bubble_perf, dict) and bubble_perf:
                logger.info(
                    "[PERF] [SPOTIFY_VIS][BUBBLE] integration_ms=%.2f tick_ms=%.2f collision_ms=%.2f snapshot_ms=%.2f pairs=%d overlaps=%d passes=%d active=%d trail_payload=%s trail_floats=%d",
                    float(bubble_perf.get("integration_total_ms", 0.0) or 0.0),
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
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble PERF diagnostics logging failed", exc_info=True)
        try:
            cadence = getattr(widget, "_bubble_cadence_state", None)
            if cadence is not None:
                cadence_diag = cadence.diagnostic_snapshot(reset=reset)
                logger.info(
                    "[PERF] [SPOTIFY_VIS][BUBBLE_CADENCE] requested=%d integrated=%d "
                    "integration_ratio=%.3f integration_failures=%d",
                    int(cadence_diag.get("requested_steps", 0)),
                    int(cadence_diag.get("integrated_steps", 0)),
                    float(cadence_diag.get("integration_ratio", 0.0)),
                    int(cadence_diag.get("integration_failures", 0)),
                )
        except Exception:
            logger.debug("[SPOTIFY_VIS] Bubble cadence PERF logging failed", exc_info=True)
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
                    "dsp_state_rebuilds=%d dsp_state_reuses=%d "
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
                    int(analysis_diag.get("dsp_state_rebuilds", 0)),
                    int(analysis_diag.get("dsp_state_reuses", 0)),
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

