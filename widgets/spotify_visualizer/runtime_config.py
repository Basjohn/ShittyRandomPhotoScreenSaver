from __future__ import annotations

from typing import Optional

from core.logging.logger import get_logger
from core.process import ProcessSupervisor
from core.threading.manager import ThreadManager

from widgets.spotify_visualizer.beat_engine import (
    _SpotifyBeatEngine,
    get_shared_spotify_beat_engine,
)

logger = get_logger(__name__)


def _has_authoritative_replay_contract(widget) -> bool:
    """Return True when engine replay can read authoritative mode config safely."""
    model = getattr(widget, "_settings_model", None)
    if model is None:
        return False
    cache = getattr(widget, "_technical_config_cache", None)
    if not isinstance(cache, dict) or not cache:
        return False
    mode = getattr(widget, "_vis_mode", None)
    try:
        mode_key = str(mode.name).lower()
    except Exception:
        return False
    return mode_key in cache


def set_thread_manager(widget, thread_manager: ThreadManager) -> None:
    widget._thread_manager = thread_manager
    try:
        engine = get_shared_spotify_beat_engine(widget._bar_count)
        widget._engine = engine
        engine.set_thread_manager(thread_manager)
        if _has_authoritative_replay_contract(widget):
            from widgets.spotify_visualizer.activation_runtime import (
                apply_authoritative_runtime_handoff,
            )

            apply_authoritative_runtime_handoff(
                widget,
                widget._vis_mode,
                reason="thread_manager_attach",
                replay_engine=True,
            )
        bind_engine_aliases(widget, engine)
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to propagate ThreadManager to shared beat engine",
            exc_info=True,
        )


def set_process_supervisor(widget, supervisor: Optional[ProcessSupervisor]) -> None:
    widget._process_supervisor = supervisor
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
        if engine is not None:
            engine.set_process_supervisor(supervisor)
            logger.debug("[SPOTIFY_VIS] ProcessSupervisor set on beat engine")
    except Exception:
        logger.debug(
            "[SPOTIFY_VIS] Failed to set ProcessSupervisor on beat engine",
            exc_info=True,
        )
    if widget._enabled:
        widget._ensure_tick_source()


def apply_floor_config(widget, dynamic_enabled: bool, manual_floor: float) -> None:
    widget._last_floor_config = (bool(dynamic_enabled), float(manual_floor))
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        engine = None
    if engine is not None:
        try:
            engine.set_floor_config(dynamic_enabled, manual_floor)
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to push floor config via apply_floor_config",
                exc_info=True,
            )


def apply_sensitivity_config(widget, recommended: bool, sensitivity: float) -> None:
    widget._last_sensitivity_config = (bool(recommended), float(sensitivity))
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        engine = None
    if engine is not None:
        try:
            engine.set_sensitivity_config(recommended, sensitivity)
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to push sensitivity config via apply_sensitivity_config",
                exc_info=True,
            )


def apply_energy_boost(widget, boost: float) -> None:
    try:
        value = float(boost)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        value = 1.0
    if abs(value - widget._last_energy_boost) <= 1e-4:
        return
    widget._last_energy_boost = value
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        engine = None
    if engine is None:
        return
    try:
        engine.set_energy_boost(value)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push energy boost config", exc_info=True)


def apply_input_gain(widget, gain: float) -> None:
    try:
        value = float(gain)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        value = 1.0
    if abs(value - widget._last_input_gain) <= 1e-4:
        return
    widget._last_input_gain = value
    try:
        engine = widget._engine or get_shared_spotify_beat_engine(widget._bar_count)
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        engine = None
    if engine is None:
        return
    try:
        engine.set_input_gain(value)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push input gain config", exc_info=True)


def apply_agc_strength(widget, value: float) -> None:
    try:
        engine = widget._engine
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        engine = None
    if engine is None:
        return
    try:
        engine.set_agc_strength(value)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push agc strength config", exc_info=True)


def compute_energy_boost(enabled: bool) -> float:
    return 1.18 if enabled else 0.85


def clear_runtime_bar_state(widget) -> None:
    count = max(1, int(getattr(widget, "_bar_count", 1) or 1))
    widget._display_bars = [0.0] * count
    widget._target_bars = [0.0] * count
    widget._per_bar_energy = [0.0] * count
    widget._visual_bars = [0.0] * count
    widget._last_update_ts = -1.0
    widget._last_smooth_ts = 0.0


def apply_audio_block_size(widget, block_size: int) -> None:
    try:
        value = max(0, int(block_size))
    except Exception as exc:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", exc)
        value = 0
    if value == widget._last_audio_block_size:
        return
    widget._last_audio_block_size = value
    engine = widget._engine
    if engine is None:
        try:
            engine = get_shared_spotify_beat_engine(widget._bar_count)
            widget._engine = engine
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] Failed to resolve beat engine for block size",
                exc_info=True,
            )
            engine = None
    worker = getattr(engine, "_audio_worker", None) if engine is not None else None
    if worker is None or not hasattr(worker, "set_audio_block_size"):
        return
    try:
        worker.set_audio_block_size(value)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to push audio block size", exc_info=True)


def resize_bar_buffers(widget, new_bar_count: int) -> None:
    new_count = max(1, int(new_bar_count))
    if new_count == widget._bar_count:
        return
    was_enabled = widget._enabled
    engine = widget._engine
    widget._bar_count = new_count
    widget._display_bars = [0.0] * new_count
    widget._target_bars = [0.0] * new_count
    widget._per_bar_energy = [0.0] * new_count
    widget._visual_bars = [0.0] * new_count
    widget._geom_cache_rect = None
    widget._geom_cache_bar_count = new_count
    widget._geom_bar_x = []
    widget._geom_seg_y = []
    widget._geom_bar_width = 0
    widget._geom_seg_height = 0
    widget._last_gpu_geom = None
    widget._last_gpu_fade_sent = -1.0
    widget._has_pushed_first_frame = False
    widget._waiting_for_fresh_engine_frame = True
    widget._waiting_for_fresh_frame = True
    try:
        if engine is None:
            engine = get_shared_spotify_beat_engine(new_count)
        else:
            engine.reconfigure_bar_count(new_count)
        widget._engine = engine
        if widget._thread_manager is not None:
            engine.set_thread_manager(widget._thread_manager)
        if widget._process_supervisor is not None:
            engine.set_process_supervisor(widget._process_supervisor)
        bind_engine_aliases(widget, engine)
        if was_enabled:
            engine.acquire()
            widget._replay_engine_config(engine)
            if widget._should_capture_audio_now():
                engine.ensure_started()
            else:
                engine.set_playback_state(False)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to resize beat engine", exc_info=True)


def bind_engine_aliases(widget, engine: Optional[_SpotifyBeatEngine]) -> None:
    if engine is None:
        return
    try:
        widget._bars_buffer = engine._audio_buffer
        widget._audio_worker = engine._audio_worker
        widget._bars_result_buffer = engine._bars_result_buffer
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to bind beat engine aliases", exc_info=True)
