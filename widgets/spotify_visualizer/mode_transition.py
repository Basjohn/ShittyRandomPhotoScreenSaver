"""Mode-transition logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 1500-line monolith threshold.
All functions take the widget instance as the first argument and read/write
its ``_mode_transition_*`` state attributes.
"""
from __future__ import annotations

import time
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)


def cycle_mode(widget: Any) -> bool:
    """Cycle to the next visualizer mode with a crossfade.

    Returns True if a cycle was initiated, False if already transitioning.
    """
    from widgets.spotify_visualizer.audio_worker import VisualizerMode

    if widget._mode_transition_phase != 0:
        return False

    _CYCLE_MODES = [
        VisualizerMode.SPECTRUM,
        VisualizerMode.OSCILLOSCOPE,
        VisualizerMode.SINE_WAVE,
        VisualizerMode.BLOB,
        VisualizerMode.BUBBLE,
    ]
    try:
        idx = _CYCLE_MODES.index(widget._vis_mode)
    except ValueError:
        idx = -1
    next_mode = _CYCLE_MODES[(idx + 1) % len(_CYCLE_MODES)]
    widget._mode_transition_pending = next_mode
    widget._mode_transition_phase = 1  # start fade-out
    widget._mode_transition_ts = time.time()
    logger.info("[SPOTIFY_VIS] Mode cycle requested: %s -> %s", widget._vis_mode.name, next_mode.name)
    return True


def mode_transition_fade_factor(widget: Any, now_ts: float) -> float:
    """Return a 0..1 fade multiplier for the mode crossfade.

    Driven entirely from the existing tick — no timers or polling.
    Returns 1.0 when no transition is active (zero cost).
    """
    phase = widget._mode_transition_phase
    if phase == 0:
        return 1.0

    elapsed = now_ts - widget._mode_transition_ts
    dur = widget._mode_transition_duration

    if phase == 1:
        # Fading out
        t = min(1.0, elapsed / dur) if dur > 0 else 1.0
        if t >= 1.0:
            # Fade-out complete: switch mode, begin fade-in
            pending = widget._mode_transition_pending
            if pending is not None:
                try:
                    setattr(widget, "_mode_transition_resume_ts", now_ts)
                except Exception:
                    setattr(widget, "_mode_transition_resume_ts", 0.0)
                try:
                    widget._reset_visualizer_state(
                        clear_overlay=False,
                        replay_cached=bool(getattr(widget, "_cached_vis_kwargs", None)),
                    )
                except Exception:
                    logger.debug("[SPOTIFY_VIS] Mode reset helper failed", exc_info=True)
                widget.set_visualization_mode(pending)
                widget._mode_transition_pending = None
            widget._mode_transition_phase = 3  # waiting-for-ready
            widget._mode_transition_ts = now_ts
            return 0.0
        return 1.0 - t

    if phase == 3:
        # Waiting for teardown → reinit pipeline to finish. Bars stay hidden.
        return 0.0

    if phase == 2:
        # Fading in
        t = min(1.0, elapsed / dur) if dur > 0 else 1.0
        if t >= 1.0:
            # Transition complete — persist mode
            widget._mode_transition_phase = 0
            widget._mode_transition_ts = 0.0
            try:
                widget._mode_transition_resume_ts = 0.0
            except Exception:
                pass
            persist_vis_mode(widget)
            return 1.0
        return t

    return 1.0


def persist_vis_mode(widget: Any) -> None:
    """Save the current visualizer mode to SettingsManager (if available)."""
    wm = getattr(widget, '_widget_manager', None)
    if wm is None:
        return
    sm = getattr(wm, '_settings_manager', None)
    if sm is None:
        return
    try:
        mode_str = widget._vis_mode_str
        cfg = sm.get('widgets', {}) or {}
        vis_cfg = cfg.get('spotify_visualizer', {}) or {}
        if vis_cfg.get('mode') != mode_str:
            vis_cfg['mode'] = mode_str
            cfg['spotify_visualizer'] = vis_cfg
            sm.set('widgets', cfg)
            logger.debug("[SPOTIFY_VIS] Persisted vis mode: %s", mode_str)
    except Exception:
        logger.debug("[SPOTIFY_VIS] Failed to persist vis mode", exc_info=True)
