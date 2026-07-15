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


def maybe_log_oscilloscope_diagnostics(overlay: Any, logger: logging.Logger) -> None:
    if not (
        is_viz_diagnostics_enabled()
        and logger.isEnabledFor(logging.DEBUG)
        and overlay._vis_mode == "oscilloscope"
    ):
        return
    now_diag = time.time()
    sig = (
        round(float(getattr(overlay, "_line_speed", 0.0)), 3),
        round(float(getattr(overlay, "_osc_last_waveform_blend_alpha", 0.0)), 3),
        int(len(getattr(overlay, "_ghost_waveform_ring", []) or [])),
        int(getattr(overlay, "_ghost_delay_frames", 0)),
        round(float(getattr(overlay, "_osc_ghost_alpha", 0.0)), 3),
        round(float(getattr(overlay, "_osc_transient_width_mix", 0.0)), 3),
    )
    if (
        (now_diag - getattr(overlay, "_osc_diag_last_ts", 0.0)) < 1.5
        and sig == getattr(overlay, "_osc_diag_last_sig", None)
    ):
        return
    logger.debug(
        (
            "[SPOTIFY_VIS][OSC] speed=%.3f alpha=%.3f waveform_delta=%.3f "
            "ghost_alpha=%.3f ghost_ring=%d/%d transient_mix=%.3f "
            "transient_drive=%.3f sensitivity=%.3f bass=%.3f mid=%.3f high=%.3f overall=%.3f"
        ),
        float(getattr(overlay, "_line_speed", 0.0)),
        float(getattr(overlay, "_osc_last_waveform_blend_alpha", 0.0)),
        float(getattr(overlay, "_osc_last_waveform_delta", 0.0)),
        float(getattr(overlay, "_osc_ghost_alpha", 0.0)),
        int(len(getattr(overlay, "_ghost_waveform_ring", []) or [])),
        int(getattr(overlay, "_ghost_delay_frames", 0)),
        float(getattr(overlay, "_osc_transient_width_mix", 0.0)),
        float(getattr(overlay, "_osc_last_transient_width_drive", 0.0)),
        float(getattr(overlay, "_osc_last_sensitivity_mod", 0.0)),
        float(getattr(overlay, "_line_smoothed_bass", 0.0)),
        float(getattr(overlay, "_line_smoothed_mid", 0.0)),
        float(getattr(overlay, "_line_smoothed_high", 0.0)),
        float(getattr(getattr(overlay, "_energy_bands", None), "overall", 0.0) or 0.0),
    )
    overlay._osc_diag_last_ts = now_diag
    overlay._osc_diag_last_sig = sig


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
