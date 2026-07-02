"""Display Overlays & Window Management - Extracted from display_widget.py.

Contains overlay fade orchestration, Spotify secondary fades,
window state diagnostics, and activation refresh logic.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, TYPE_CHECKING

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager
from rendering.overlay_startup_policy import get_overlay_startup_fade_policy

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def _schedule_overlay_starter(delay_ms: int, starter: Callable[[], None]) -> None:
    """Schedule overlay startup work without raw QTimer ownership."""

    ThreadManager.single_shot(max(0, int(delay_ms)), starter)


def _startup_policy():
    """Return the canonical startup timing policy for overlay fades."""

    return get_overlay_startup_fade_policy()


# Compatibility aliases for callers/tests that still import the legacy names.
PRIMARY_OVERLAY_STARTUP_WARMUP_MS = _startup_policy().primary_warmup_ms
PRIMARY_OVERLAY_POST_FADE_BUFFER_MS = _startup_policy().primary_post_fade_buffer_ms
SPOTIFY_SECONDARY_STARTUP_DELAY_MS = _startup_policy().spotify_secondary_startup_delay_ms
SPOTIFY_SECONDARY_DIRECT_DELAY_MS = _startup_policy().spotify_secondary_direct_delay_ms


def _mark_spotify_secondary_not_before(widget, *, delay_ms: int) -> None:
    """Record when Spotify secondary startup work is allowed to begin."""

    try:
        widget._spotify_secondary_not_before_ts = time.monotonic() + (
            max(0, int(delay_ms)) / 1000.0
        )
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)


def start_overlay_fades(widget, force: bool = False) -> None:
    """Kick off any pending overlay fade callbacks."""

    if getattr(widget, "_overlay_fade_started", False):
        return
    widget._overlay_fade_started = True

    timeout = getattr(widget, "_overlay_fade_timeout", None)
    if timeout is not None:
        try:
            timeout.stop()
            timeout.deleteLater()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        widget._overlay_fade_timeout = None

    pending = getattr(widget, "_overlay_fade_pending", {})
    try:
        starters = list(pending.values())
        names = list(pending.keys())
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        starters = []
        names = []
    logger.debug(
        "[OVERLAY_FADE] starting overlay fades (force=%s, overlays=%s)",
        force,
        sorted(names),
    )
    widget._overlay_fade_pending = {}

    # Primary overlays should begin fading as soon as the compositor is
    # ready. Delaying the first wave creates a visible "wallpaper only"
    # dead zone and defeats the purpose of the gentle coordinated fade.
    # The heavy startup delay belongs to the Spotify secondary stage, not
    # to the primary overlay wave.
    policy = _startup_policy()
    warmup_delay_ms = 0 if force else int(policy.primary_warmup_ms)

    if warmup_delay_ms <= 0:
        for starter in starters:
            try:
                starter()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

        spotify_delay_ms = (
            int(policy.spotify_secondary_direct_delay_ms)
            if force
            else int(policy.spotify_secondary_startup_delay_ms)
        )
        try:
            _mark_spotify_secondary_not_before(
                widget,
                delay_ms=spotify_delay_ms,
            )
            widget._run_spotify_secondary_fades(
                base_delay_ms=spotify_delay_ms,
            )
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return

    for starter in starters:
        try:
            _schedule_overlay_starter(warmup_delay_ms, starter)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                starter()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    # Schedule Spotify secondary fades to start a little after the
    # coordinated primary warm-up, so the volume slider and visualiser
    # card feel attached to the wave without blocking it.
    try:
        spotify_delay_ms = warmup_delay_ms + int(policy.spotify_secondary_startup_delay_ms)
        _mark_spotify_secondary_not_before(
            widget,
            delay_ms=spotify_delay_ms,
        )
        widget._run_spotify_secondary_fades(
            base_delay_ms=spotify_delay_ms,
        )
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def run_spotify_secondary_fades(widget, *, base_delay_ms: int) -> None:
    """Start any queued Spotify second-wave fade callbacks."""

    starters = getattr(widget, "_spotify_secondary_fade_starters", None)
    if not starters:
        return
    try:
        queued = list(starters)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        queued = []
    widget._spotify_secondary_fade_starters = []

    delay_ms = max(0, int(base_delay_ms))
    for starter in queued:
        try:
            if delay_ms <= 0:
                starter()
            else:
                _schedule_overlay_starter(delay_ms, starter)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                starter()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def register_spotify_secondary_fade(widget, starter: Callable[[], None]) -> None:
    """Register a Spotify second-wave fade to run after primary overlays.

    When there is no primary overlay coordination active, or when the
    primary group has already started, the starter is run with a small
    delay so it still feels like a secondary pass without popping in
    ahead of other widgets.
    """

    try:
        expected = widget._overlay_fade_expected
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        expected = set()

    starters = getattr(widget, "_spotify_secondary_fade_starters", None)
    if not isinstance(starters, list):
        starters = []
        widget._spotify_secondary_fade_starters = starters

    # If no primary overlays are coordinated for this display, or the
    # primary wave has already started, run this as a tiny second wave
    # instead of waiting for a coordinator that will never fire.
    if not expected or getattr(widget, "_overlay_fade_started", False):
        policy = _startup_policy()
        try:
            _mark_spotify_secondary_not_before(
                widget,
                delay_ms=int(policy.spotify_secondary_direct_delay_ms),
            )
            _schedule_overlay_starter(int(policy.spotify_secondary_direct_delay_ms), starter)
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            try:
                starter()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
        return

    starters.append(starter)

def debug_window_state(widget, label: str, *, extra: str = "") -> None:
    if not win_diag_logger.isEnabledFor(logging.DEBUG):
        return
    try:
        try:
            hwnd = int(widget.winId())
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            hwnd = 0
        try:
            active = bool(widget.isActiveWindow())
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            active = False
        try:
            visible = bool(widget.isVisible())
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            visible = False
        try:
            ws = int(widget.windowState())
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            ws = -1
        try:
            upd = bool(widget.updatesEnabled())
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
            upd = False

        win_diag_logger.debug(
            "[WIN_STATE] %s screen=%s hwnd=%s visible=%s active=%s windowState=%s updatesEnabled=%s %s",
            label,
            getattr(widget, "screen_index", "?"),
            hex(hwnd) if hwnd else "?",
            visible,
            active,
            ws,
            upd,
            extra,
        )
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

def perform_activation_refresh(widget, reason: str) -> None:
    # Debounce: skip if called too recently (< 2 seconds)
    try:
        now = time.monotonic()
        last_refresh = getattr(widget, "_last_activation_refresh_ts", 0.0)
        if now - last_refresh < 2.0:
            logger.debug("[ACTIVATE_REFRESH] Debounced (%.2fs since last)", now - last_refresh)
            return
        widget._last_activation_refresh_ts = now
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        widget._pending_activation_refresh = False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        widget._base_fallback_paint_logged = False
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    if win_diag_logger.isEnabledFor(logging.DEBUG):
        try:
            win_diag_logger.debug(
                "[ACTIVATE_REFRESH] screen=%s reason=%s",
                getattr(widget, "screen_index", "?"),
                reason,
            )
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    comp = getattr(widget, "_gl_compositor", None)
    if comp is not None:
        try:
            comp.update()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        widget.update()
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    try:
        bars_gl = getattr(widget, "_spotify_bars_overlay", None)
        if bars_gl is not None:
            try:
                bars_gl.update()
            except Exception as e:
                logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)
    except Exception as e:
        logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)

    for name in (
        "clock_widget",
        "clock2_widget",
        "clock3_widget",
        "weather_widget",
        "media_widget",
        "spotify_visualizer_widget",
        "spotify_volume_widget",
        "reddit_widget",
        "reddit2_widget",
    ):
        w = getattr(widget, name, None)
        if w is None:
            continue
        try:
            if w.isVisible():
                w.update()
        except Exception as e:
            logger.debug("[DISPLAY_WIDGET] Exception suppressed: %s", e)


