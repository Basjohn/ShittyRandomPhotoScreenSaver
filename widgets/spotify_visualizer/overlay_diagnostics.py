from __future__ import annotations

import logging
import time
from typing import Any

from core.logging.logger import is_viz_diagnostics_enabled


def maybe_log_glow_diagnostics(overlay: Any, logger: logging.Logger) -> None:
    if not (
        is_viz_diagnostics_enabled()
        and logger.isEnabledFor(logging.DEBUG)
        and overlay._vis_mode in ("oscilloscope", "sine_wave", "spectrum")
    ):
        return

    now_diag = time.time()
    if overlay._vis_mode == "spectrum":
        diag_sig = (
            overlay._vis_mode,
            int(overlay._spectrum_glow_enabled),
            round(float(overlay._spectrum_glow_intensity), 3),
            int(overlay._spectrum_glow_color.rgba()),
            int(overlay._bar_count),
        )
    else:
        diag_sig = (
            overlay._vis_mode,
            int(overlay._glow_enabled),
            round(float(overlay._glow_intensity), 3),
            round(float(overlay._glow_reactivity), 3),
            int(overlay._reactive_glow),
            int(overlay._line_count),
            int(overlay._osc_ghost_line2_enabled),
            int(overlay._osc_ghost_line3_enabled),
        )

    if (
        (now_diag - overlay._glow_diag_last_ts) < 12.0
        and diag_sig == overlay._glow_diag_last_sig
    ):
        return

    if overlay._vis_mode == "spectrum":
        glow_color = tuple(int(c) for c in overlay._spectrum_glow_color.getRgb())
        logger.debug(
            "[SPOTIFY_VIS][GLOW] mode=%s enabled=%s intensity=%.3f color=%s bar_count=%d energy_b=%.3f energy_m=%.3f energy_h=%.3f energy_o=%.3f",
            overlay._vis_mode,
            overlay._spectrum_glow_enabled,
            overlay._spectrum_glow_intensity,
            glow_color,
            int(overlay._bar_count),
            float(getattr(overlay._energy_bands, "bass", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "mid", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "high", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "overall", 0.0) or 0.0),
        )
    else:
        logger.debug(
            "[SPOTIFY_VIS][GLOW] mode=%s enabled=%s intensity=%.3f reactivity=%.3f reactive=%s lines=%d ghost2=%s ghost3=%s energy_b=%.3f energy_m=%.3f energy_h=%.3f energy_o=%.3f",
            overlay._vis_mode,
            overlay._glow_enabled,
            overlay._glow_intensity,
            overlay._glow_reactivity,
            overlay._reactive_glow,
            int(overlay._line_count),
            overlay._osc_ghost_line2_enabled,
            overlay._osc_ghost_line3_enabled,
            float(getattr(overlay._energy_bands, "bass", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "mid", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "high", 0.0) or 0.0),
            float(getattr(overlay._energy_bands, "overall", 0.0) or 0.0),
        )

    overlay._glow_diag_last_ts = now_diag
    overlay._glow_diag_last_sig = diag_sig


def maybe_log_sine_idle_state(overlay: Any, logger: logging.Logger, *, dt_seconds: float) -> None:
    if not (
        is_viz_diagnostics_enabled()
        and overlay._vis_mode == "sine_wave"
        and not overlay._playing
    ):
        return
    now_diag = time.time()
    if now_diag - overlay._last_sine_idle_diag_ts < 0.9:
        return
    logger.debug(
        (
            "[SPOTIFY_VIS][SINE][IDLE_STATE] t=%.3f dt=%.4f speed=%.3f "
            "travel=(%d,%d,%d,%d,%d,%d) line_count=%d"
        ),
        float(overlay._accumulated_time),
        float(dt_seconds),
        float(overlay._line_speed),
        int(overlay._sine_wave_travel),
        int(overlay._sine_travel_line2),
        int(overlay._sine_travel_line3),
        int(overlay._sine_travel_line4),
        int(overlay._sine_travel_line5),
        int(overlay._sine_travel_line6),
        int(overlay._line_count),
    )
    overlay._last_sine_idle_diag_ts = now_diag


def maybe_log_blob_diagnostics(
    overlay: Any,
    logger: logging.Logger,
    *,
    dt_seconds: float,
    blob_dt: float,
    kick_raw: float,
    snare_raw: float,
    raw_live: tuple[float, float, float, float],
    filtered_live: tuple[float, float, float, float],
    prev_smoothed: float,
    raw_e: float,
    smoothed_e: float,
    stage_raw: tuple[float, float, float],
    stage_filtered: tuple[float, float, float],
    prev_stage_filtered: tuple[float, float, float],
) -> None:
    if not is_viz_diagnostics_enabled() or overlay._vis_mode != "blob":
        return
    now_ts = time.time()
    hitch_clamped = dt_seconds > (blob_dt + 0.020)
    energy_jump = abs(raw_e - prev_smoothed) > 0.18 or abs(smoothed_e - prev_smoothed) > 0.14
    stage_jump = max(abs(cur - prev) for cur, prev in zip(stage_filtered, prev_stage_filtered)) > 0.20
    hot_event = kick_raw > 0.55 or snare_raw > 0.55
    sig = (
        round(raw_e, 2),
        round(smoothed_e, 2),
        round(overlay._blob_kick_event_strength, 2),
        round(overlay._blob_snare_event_strength, 2),
        tuple(round(v, 2) for v in stage_filtered),
    )
    should_log = hitch_clamped or energy_jump or stage_jump or hot_event
    if not should_log and (now_ts - overlay._blob_diag_last_ts) < 0.75:
        return
    if not should_log and sig == overlay._blob_diag_last_sig:
        return
    logger.debug(
        (
            "[SPOTIFY_VIS][BLOB] dt=%.3f blob_dt=%.3f kick=%.2f/%.2f "
            "snare=%.2f/%.2f base=(%.3f,%.3f,%.3f,%.3f) "
            "trans=(%.3f,%.3f,%.3f) raw_live=(%.3f,%.3f,%.3f,%.3f) "
            "live=(%.3f,%.3f,%.3f,%.3f) smooth=%.3f->%.3f "
            "stage_raw=(%.2f,%.2f,%.2f) stage_filt=(%.2f,%.2f,%.2f) "
            "stage_prev=(%.2f,%.2f,%.2f) flags[hitch=%s energy=%s stage=%s hot=%s]"
        ),
        dt_seconds,
        blob_dt,
        kick_raw,
        overlay._blob_kick_event_strength,
        snare_raw,
        overlay._blob_snare_event_strength,
        float(getattr(overlay, "_blob_diag_base_bass", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_base_mid", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_base_high", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_base_overall", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_transient_bass", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_transient_mid", 0.0) or 0.0),
        float(getattr(overlay, "_blob_diag_transient_high", 0.0) or 0.0),
        raw_live[0],
        raw_live[1],
        raw_live[2],
        raw_live[3],
        filtered_live[0],
        filtered_live[1],
        filtered_live[2],
        filtered_live[3],
        prev_smoothed,
        smoothed_e,
        stage_raw[0],
        stage_raw[1],
        stage_raw[2],
        stage_filtered[0],
        stage_filtered[1],
        stage_filtered[2],
        prev_stage_filtered[0],
        prev_stage_filtered[1],
        prev_stage_filtered[2],
        hitch_clamped,
        energy_jump,
        stage_jump,
        hot_event,
    )
    overlay._blob_diag_last_ts = now_ts
    overlay._blob_diag_last_sig = sig
