"""Overlay runtime-state helpers for the Spotify GL visualizer.

These helpers intentionally stay on the state/reset side of the overlay
contract. They do not touch shader authority, first-frame push timing, or the
paintGL stencil-mask path.
"""
from __future__ import annotations

import time
from typing import Any

from core.logging.logger import get_logger
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    is_mode_active,
)
from widgets.spotify_visualizer.blob_pockets import reset_blob_pocket_state
from widgets.spotify_visualizer.spectrum_solid_hysteresis import (
    reset_overlay_spectrum_solid_hysteresis_state,
)

logger = get_logger(__name__)

VALID_OVERLAY_MODES = {
    "spectrum",
    "oscilloscope",
    "blob",
    "sine_wave",
    "bubble",
    "devcurve",
}


def request_mode_reset(overlay: Any, mode: str) -> None:
    """Schedule a manual reset for a known overlay mode."""
    if not mode:
        return
    normalized = str(mode).lower()
    if normalized not in VALID_OVERLAY_MODES:
        return
    overlay._pending_mode_resets.add(normalized)


def reset_blob_state(overlay: Any) -> None:
    overlay._blob_smoothed_energy = 0.0
    overlay._blob_glow_energy = 0.0
    overlay._blob_raw_bass_energy = 0.0
    overlay._blob_raw_mid_energy = 0.0
    overlay._blob_raw_high_energy = 0.0
    overlay._blob_raw_overall_energy = 0.0
    overlay._blob_live_bass_energy = 0.0
    overlay._blob_live_mid_energy = 0.0
    overlay._blob_live_high_energy = 0.0
    overlay._blob_live_overall_energy = 0.0
    overlay._blob_peak_energy = 0.0
    overlay._blob_peak_bass = 0.0
    overlay._blob_peak_mid = 0.0
    overlay._blob_peak_high = 0.0
    overlay._blob_peak_overall = 0.0
    overlay._blob_peak_hold_remaining = 0.0
    overlay._blob_stage_progress_raw = (-1.0, -1.0, -1.0)
    overlay._blob_stage_progress_filtered = (0.0, 0.0, 0.0)
    overlay._blob_stage_progress_ready = False
    overlay._blob_seed_pending = True
    overlay._blob_kick_event_strength = 0.0
    overlay._blob_snare_event_strength = 0.0
    overlay._blob_kick_event_envelope = 0.0
    overlay._blob_snare_event_envelope = 0.0
    overlay._blob_pocket_state = reset_blob_pocket_state(
        getattr(overlay, "_blob_pocket_state", None)
    )
    overlay._blob_diag_last_ts = 0.0
    overlay._blob_diag_last_sig = None


def reset_mode_state(overlay: Any, mode: str, *, reason: str) -> None:
    """Cold-reset overlay-local accumulators for a mode handoff."""
    mode_key = str(mode).lower() if mode else "spectrum"
    overlay._accumulated_time = 0.0
    overlay._last_time_ts = 0.0
    overlay._peaks = []
    overlay._last_peak_ts = 0.0

    # Clear every mode bucket because one overlay instance survives runtime
    # mode and preset switches.
    reset_blob_state(overlay)
    overlay._waveform = []
    overlay._prev_waveform = []
    overlay._ghost_waveform_ring = []
    overlay._ghost_ring_idx = 0
    overlay._waveform_count = 0
    overlay._line_smoothed_bass = 0.0
    overlay._line_smoothed_mid = 0.0
    overlay._line_smoothed_high = 0.0
    overlay._line_kick_event_strength = 0.0
    overlay._line_snare_event_strength = 0.0
    overlay._line_kick_event_envelope = 0.0
    overlay._line_snare_event_envelope = 0.0
    overlay._sine_peak_bass = 0.0
    overlay._sine_peak_mid = 0.0
    overlay._sine_peak_high = 0.0
    overlay._sine_peak_hold_remaining = 0.0
    overlay._bubble_pos_data = []
    overlay._bubble_extra_data = []
    overlay._bubble_trail_data = []
    overlay._bubble_count = 0
    reset_overlay_spectrum_solid_hysteresis_state(overlay)
    overlay._devcurve_curve_bass = []
    overlay._devcurve_curve_vocals = []
    overlay._devcurve_curve_mids = []
    overlay._devcurve_curve_transients = []
    overlay._devcurve_sample_count = 0
    overlay._devcurve_foreground_layer_id = -1
    overlay._devcurve_specular_slot0 = [0.0, 0.0, 0.0, 0.0]
    overlay._devcurve_specular_slot1 = [0.0, 0.0, 0.0, 0.0]
    overlay._devcurve_specular_slot2 = [0.0, 0.0, 0.0, 0.0]
    overlay._last_vis_mode = None

    logger.info(
        "[SPOTIFY_VIS][OVERLAY][RESET] mode=%s reason=%s",
        mode_key,
        reason,
    )
    overlay._last_reset_mode = mode_key
    overlay._last_reset_reason = reason
    try:
        overlay._last_reset_ts = time.time()
    except Exception:
        overlay._last_reset_ts = 0.0


def apply_state_handoff(
    overlay: Any,
    *,
    visible: bool,
    vis_mode: str,
    activation_id: int | None,
    engine_generation: int | None,
    latest_frame_generation: int | None,
    latest_waveform_generation: int | None,
    floor_snapshot: dict | None,
    border_width_px: float,
) -> bool:
    """Apply overlay-local identity/reset bookkeeping before heavy frame work."""
    if not visible:
        overlay.clear_overlay_buffer()
        return False

    overlay._activation_id = activation_id
    overlay._engine_generation = engine_generation
    overlay._latest_frame_generation = latest_frame_generation
    overlay._latest_waveform_generation = latest_waveform_generation
    overlay._apply_floor_snapshot(floor_snapshot)

    prev_mode = overlay._vis_mode
    requested_mode = (
        vis_mode if is_mode_active(vis_mode) else get_default_visualizer_mode_id()
    )
    overlay._vis_mode = requested_mode

    manual_reset = requested_mode in overlay._pending_mode_resets
    if manual_reset:
        overlay._pending_mode_resets.discard(requested_mode)
    if prev_mode != requested_mode or manual_reset:
        reason = "mode_change" if prev_mode != requested_mode else "manual_reset"
        reset_mode_state(overlay, requested_mode, reason=reason)
        overlay._last_vis_mode = requested_mode

    try:
        overlay._border_width_px = max(0.0, float(border_width_px))
    except Exception:
        overlay._border_width_px = 0.0

    return True
