"""Process-wide ownership gate for external media-key command bursts.

Windows can surface one physical media-key press through several routes
(``WM_KEYDOWN``, ``WM_APPCOMMAND``, Qt media keys, and raw input).  Only the
first route should drive SRPSS feedback/refresh work.  OS command propagation
remains owned by the native event handlers and is intentionally unaffected.
"""
from __future__ import annotations

import threading
import time

from core.logging.logger import get_logger, is_perf_metrics_enabled

logger = get_logger(__name__)

MEDIA_COMMAND_DEDUP_SECONDS = 0.20

_gate_lock = threading.Lock()
_last_media_command: tuple[str, float] | None = None


def any_display_transition_active() -> bool:
    """Return whether any live display has pending or running transition work."""

    try:
        from rendering.display_widget import DisplayWidget

        displays = list(DisplayWidget.get_all_instances())
    except Exception:
        return False

    for display in displays:
        try:
            checker = getattr(display, "has_transition_work_pending", None)
            if callable(checker) and bool(checker()):
                return True
        except (RuntimeError, ReferenceError):
            continue
        except Exception:
            logger.debug(
                "[MEDIA_INGRESS] Failed to inspect display transition state",
                exc_info=True,
            )
    return False


def claim_external_media_command(
    command: str,
    *,
    route: str,
    now: float | None = None,
) -> bool:
    """Claim one external command before widget lookup, feedback, or refresh.

    Returns ``True`` for the first accepted route and ``False`` for an
    immediate duplicate of the same normalized command.  Rejected duplicates
    do not extend the suppression window.
    """

    normalized = str(command or "").strip().lower()
    if normalized not in {"prev", "play", "next"}:
        return False

    timestamp = time.monotonic() if now is None else float(now)
    duplicate = False
    global _last_media_command
    with _gate_lock:
        previous = _last_media_command
        if previous is not None:
            previous_command, previous_timestamp = previous
            elapsed = timestamp - previous_timestamp
            duplicate = (
                previous_command == normalized
                and 0.0 <= elapsed <= MEDIA_COMMAND_DEDUP_SECONDS
            )
        if not duplicate:
            _last_media_command = (normalized, timestamp)

    if is_perf_metrics_enabled():
        logger.info(
            "[PERF][MEDIA_FEEDBACK] phase=ingress command=%s "
            "duplicate_suppressed=%s transition_active=%s mode=none "
            "duration_ms=0.00 paint_requests=0 route=%s",
            normalized,
            duplicate,
            any_display_transition_active(),
            route,
        )
    return not duplicate


def wake_media_visualizers(origin_display=None) -> None:
    """Wake visualizers once for the accepted process-wide media command."""

    try:
        from rendering.display_widget import DisplayWidget
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        displays = list(DisplayWidget.get_all_instances())
    except Exception:
        displays = []
        SpotifyVisualizerWidget = None

    if origin_display is not None and all(
        candidate is not origin_display for candidate in displays
    ):
        displays.append(origin_display)

    seen: set[int] = set()
    for display in displays:
        try:
            if SpotifyVisualizerWidget is None:
                continue
            for visualizer in display.findChildren(SpotifyVisualizerWidget):
                identity = id(visualizer)
                if identity in seen:
                    continue
                seen.add(identity)
                wake = getattr(visualizer, "_trigger_wake", None)
                if callable(wake):
                    wake(reason="external_media_command")
        except (RuntimeError, ReferenceError):
            continue
        except Exception:
            logger.debug(
                "[MEDIA_INGRESS] Failed to wake media visualizer",
                exc_info=True,
            )


def resolve_media_widget(origin_display=None):
    """Resolve the process media-card owner after an ingress claim."""

    if origin_display is not None:
        resolver = getattr(
            origin_display,
            "_resolve_media_widget_for_transport",
            None,
        )
        if callable(resolver):
            try:
                candidate = resolver()
                if candidate is not None:
                    return candidate
            except Exception:
                logger.debug(
                    "[MEDIA_INGRESS] Origin media resolver failed",
                    exc_info=True,
                )

        candidate = getattr(origin_display, "media_widget", None)
        if candidate is not None:
            return candidate

        manager = getattr(origin_display, "_widget_manager", None)
        if manager is not None:
            try:
                candidate = (
                    manager.get_widget("media")
                    or manager.get_widget("media_widget")
                )
                if candidate is not None:
                    return candidate
            except Exception:
                logger.debug(
                    "[MEDIA_INGRESS] WidgetManager media lookup failed",
                    exc_info=True,
                )

    try:
        from rendering.display_widget import DisplayWidget

        for display in DisplayWidget.get_all_instances():
            candidate = getattr(display, "media_widget", None)
            if candidate is not None:
                return candidate
    except Exception:
        logger.debug(
            "[MEDIA_INGRESS] Cross-display media lookup failed",
            exc_info=True,
        )
    return None


def reset_media_command_ingress_for_tests() -> None:
    """Reset process-wide state for isolated regression tests."""

    global _last_media_command
    with _gate_lock:
        _last_media_command = None
