"""Resolved activation payload and runtime replay helpers for Spotify visualizer.

This module extracts settings-model / activation-payload application logic from
the widget coordinator without touching fresh-frame, startup-stage, or GL
authority gates.
"""
from __future__ import annotations

import copy
from typing import Any

from core.logging.logger import get_logger
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_presets import (
    VisualizerActivationPayload,
    resolve_visualizer_activation_payload,
)
from widgets.spotify_visualizer.audio_worker import VisualizerMode

logger = get_logger(__name__)


def set_settings_model(
    widget: Any,
    model: SpotifyVisualizerSettings,
    *,
    apply_now: bool = True,
) -> None:
    if model is None:
        return
    try:
        snapshot = copy.deepcopy(model)
    except Exception:
        snapshot = model
    widget._settings_model = snapshot
    widget._technical_config_cache = widget._build_technical_cache(snapshot)
    target_mode = widget._vis_mode
    try:
        mode_name = str(getattr(snapshot, "mode", "") or "").lower()
        target_mode = widget._map_mode_key_to_enum(mode_name)
    except Exception:
        target_mode = widget._vis_mode
    if apply_now:
        widget._apply_technical_config_for_mode(target_mode, reason="settings_model_update")


def log_live_activation_state(
    widget: Any,
    mode: VisualizerMode,
    payload: VisualizerActivationPayload,
    *,
    reason: str,
) -> None:
    try:
        mode_key = mode.name.lower()
        technical_cache = dict(widget._technical_config_cache.get(mode_key, {}))
        engine = widget._engine
        worker = getattr(engine, "_audio_worker", None) if engine is not None else None
        overlay = getattr(widget.parent(), "_spotify_bars_overlay", None) if widget.parent() is not None else None
        logger.info(
            (
                "[SPOTIFY_VIS][LIVE] reason=%s mode=%s preset_index=%d preset_kind=%s preset_name=%s "
                "preset_path=%s cache_manual=%.3f worker_manual=%.3f worker_dynamic=%s worker_sensitivity=%.3f "
                "worker_recommended=%s worker_block=%d worker_input_gain=%.3f worker_agc=%.3f "
                "widget_fill=%s widget_border=%s widget_border_opacity=%.3f "
                "widget_ghost=%s widget_ghost_alpha=%.3f widget_ghost_decay=%.3f "
                "overlay_fill=%s overlay_border=%s overlay_peak_decay=%.3f "
                "engine_generation=%s engine_activation=%s overlay_activation=%s overlay_generation=%s"
            ),
            reason,
            mode_key,
            int(payload.preset_index),
            "custom" if payload.is_custom else "curated",
            payload.preset_name,
            payload.preset_path or "<custom>",
            float(technical_cache.get("manual_floor", 0.12)),
            float(getattr(worker, "_manual_floor", 0.12) if worker is not None else 0.12),
            bool(getattr(worker, "_use_dynamic_floor", True) if worker is not None else True),
            float(getattr(worker, "_user_sensitivity", 1.0) if worker is not None else 1.0),
            bool(getattr(worker, "_use_recommended", True) if worker is not None else True),
            int(getattr(worker, "_preferred_block_size", 0) if worker is not None else 0),
            float(getattr(worker, "_input_gain", 1.0) if worker is not None else 1.0),
            float(getattr(worker, "_agc_strength", 0.5) if worker is not None else 0.5),
            widget._bar_fill_color.getRgb(),
            widget._bar_border_color.getRgb(),
            float(widget._bar_border_color.alphaF()),
            bool(widget._ghosting_enabled),
            float(widget._ghost_alpha),
            float(widget._ghost_decay_rate),
            getattr(overlay, "_fill_color", None).getRgb() if overlay is not None and getattr(overlay, "_fill_color", None) is not None else None,
            getattr(overlay, "_border_color", None).getRgb() if overlay is not None and getattr(overlay, "_border_color", None) is not None else None,
            float(getattr(overlay, "_peak_decay_per_sec", 0.0) if overlay is not None else 0.0),
            getattr(engine, "get_generation_id", lambda: None)(),
            getattr(engine, "get_activation_id", lambda: None)(),
            getattr(overlay, "_activation_id", None),
            getattr(overlay, "_engine_generation", None),
        )
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to log live activation state", exc_info=True)


def apply_resolved_activation_payload(
    widget: Any,
    model: SpotifyVisualizerSettings,
    payload: VisualizerActivationPayload,
    *,
    reason: str,
    force_runtime_reset: bool = False,
) -> None:
    try:
        snapshot = copy.deepcopy(model)
    except Exception:
        snapshot = model
    widget._settings_model = snapshot
    widget._technical_config_cache = widget._build_technical_cache(snapshot)

    vm = widget._map_mode_key_to_enum(payload.mode)
    mode_changed = vm != widget._vis_mode
    if mode_changed:
        widget._vis_mode = vm

    from rendering.spotify_widget_creators import apply_spotify_vis_model_config

    apply_spotify_vis_model_config(widget, snapshot, apply_mode=False)
    widget._sync_active_mode_legacy_ghost_bridge(vm)

    widget._last_gpu_geom = None
    widget._last_gpu_fade_sent = -1.0
    widget._has_pushed_first_frame = False
    widget._mode_transition_apply_height_on_resume = True
    if widget._mode_transition_phase == 0:
        widget._apply_pending_mode_transition_layout()

    widget._apply_technical_config_for_mode(vm, reason=f"{reason}:activation_payload")

    if force_runtime_reset or mode_changed:
        widget._waiting_for_fresh_engine_frame = True
        widget._waiting_for_fresh_frame = True
        widget._reset_mode_owned_runtime_state(reason=reason)
        widget._clear_gl_overlay()
        widget._prepare_engine_for_mode_reset()
        widget._clear_runtime_bar_state()

    log_live_activation_state(widget, vm, payload, reason=reason)


def apply_full_runtime_config_for_mode(
    widget: Any,
    mode: VisualizerMode,
    *,
    reason: str,
) -> None:
    wm = getattr(widget, "_widget_manager", None)
    sm = getattr(wm, "_settings_manager", None) if wm is not None else None
    if sm is None:
        return

    mode_str = mode.name.lower()
    try:
        cfg = sm.get("widgets", {}) or {}
        vis_cfg = dict(cfg.get("spotify_visualizer", {}) or {})
        payload = resolve_visualizer_activation_payload(vis_cfg, mode=mode_str)
        model = SpotifyVisualizerSettings.from_mapping(
            payload.resolved_config,
            apply_preset_overlay=False,
            resolve_preset_indices=False,
        )
        apply_resolved_activation_payload(
            widget,
            model,
            payload,
            reason=reason,
            force_runtime_reset=False,
        )
        logger.debug("[SPOTIFY_VIS] Applied full runtime config for mode=%s reason=%s", mode_str, reason)
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to apply full runtime config for mode=%s reason=%s",
            mode_str,
            reason,
            exc_info=True,
        )
