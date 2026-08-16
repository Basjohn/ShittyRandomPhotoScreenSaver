"""TEMPORARY Phase 5 visualizer-presentation A/B/C causal probe.

Enable only for the current presentation-owner experiment by launching SRPSS
with::

    /s --perf --viz-present-abc

Keep whatever other diagnostic flags are useful (including ``--gpu-timing``).
``/s`` is recommended first so this temporary flag never participates in mode
selection. There is deliberately no environment-variable path.

While enabled, press **Shift+/** (normally ``?`` on a US-style keyboard) to
cycle one process, one runtime generation through:

A_NORMAL
    Existing behaviour. ``SpotifyBarsGLOverlay._request_frame_update()`` and
    ``show()`` behave exactly as production does.

B_SUPPRESS_REQUESTS
    Logical visualizer source sampling, ticks, Bubble/Spectrum/Dev Curve/etc.
    simulation, ``set_state()`` publication, geometry/state updates and the
    visible auxiliary overlay all remain alive, but the normal
    ``_request_frame_update() -> QOpenGLWidget.update()`` request is withheld.
    The last painted visualizer frame therefore remains visible/frozen apart
    from any unrelated incidental Qt paint.

C_HIDDEN_SURFACE
    Everything in B continues, and the auxiliary ``SpotifyBarsGLOverlay`` is
    hidden. Attempts by the normal ``set_state()`` path to ``show()`` it are
    temporarily blocked so C does not thrash show/hide at logical publication
    cadence. The widget/context still exist; this state tests whether a visible
    auxiliary QOpenGLWidget surface adds pressure beyond its update-request
    stream.

The next Shift+/ returns to A_NORMAL, restores eligible overlay visibility and
issues one normal presentation request so the latest logical state becomes
visible again.

The CLI flag, hotkey, class wrappers and event-loop-recorder install hook are
expected to be removed after this causal run. This module is not a production
cadence policy, frame cap, repaint coalescer or visualizer scheduler.
"""
from __future__ import annotations

import functools
import sys
from enum import Enum
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger


logger = get_logger(__name__)

CLI_FLAG = "--viz-present-abc"
HOTKEY_LABEL = "Shift+/"


class PresentationABCState(str, Enum):
    A_NORMAL = "A_NORMAL"
    B_SUPPRESS_REQUESTS = "B_SUPPRESS_REQUESTS"
    C_HIDDEN_SURFACE = "C_HIDDEN_SURFACE"


_STATE_ORDER = (
    PresentationABCState.A_NORMAL,
    PresentationABCState.B_SUPPRESS_REQUESTS,
    PresentationABCState.C_HIDDEN_SURFACE,
)

_state = PresentationABCState.A_NORMAL
_installed = False
_event_filter: QObject | None = None
_overlay_type: type | None = None
_original_request_frame_update: Callable[..., Any] | None = None
_original_show: Callable[..., Any] | None = None
_suppressed_request_total = 0
_blocked_show_total = 0
_last_boundary_suppressed_total = 0
_last_boundary_blocked_show_total = 0


def cli_enabled(argv: list[str] | tuple[str, ...] | None = None) -> bool:
    """Return whether the explicit temporary A/B/C CLI gate is present."""
    values = sys.argv[1:] if argv is None else argv
    return any(str(value).strip().lower() == CLI_FLAG for value in values)


def current_state() -> PresentationABCState:
    """Return the current process-wide A/B/C presentation state."""
    return _state


def _live_overlays() -> list[Any]:
    overlay_cls = _overlay_type
    app = QApplication.instance()
    if overlay_cls is None or app is None:
        return []
    try:
        return [widget for widget in app.allWidgets() if isinstance(widget, overlay_cls)]
    except Exception:
        return []


def _screen_index(overlay: Any) -> str:
    try:
        parent = overlay.parent()
    except Exception:
        parent = None
    for attr in ("screen_index", "_screen_index"):
        try:
            value = getattr(parent, attr, None)
            if value is not None:
                return str(int(value))
        except Exception:
            continue
    return "?"


def _overlay_snapshot_text() -> str:
    """Return compact bounded state/counter evidence at a toggle boundary."""
    overlays = _live_overlays()
    set_state_total = 0
    update_total = 0
    paint_total = 0
    visible_count = 0
    enabled_count = 0
    parts: list[str] = []
    for overlay in overlays:
        try:
            set_state_total += int(getattr(overlay, "_perf_set_state_total", 0) or 0)
            update_total += int(getattr(overlay, "_perf_update_request_total", 0) or 0)
            paint_total += int(getattr(overlay, "_perf_paint_total", 0) or 0)
            visible = bool(overlay.isVisible())
            enabled = bool(getattr(overlay, "_enabled", False))
            visible_count += int(visible)
            enabled_count += int(enabled)
            parts.append(
                f"s{_screen_index(overlay)}:{getattr(overlay, '_vis_mode', '?')}"
                f":v{int(visible)}:e{int(enabled)}"
            )
        except Exception:
            continue
    detail = ",".join(parts) if parts else "none"
    return (
        f"overlays={len(overlays)} visible={visible_count} enabled={enabled_count} "
        f"set_state_total={set_state_total} update_total={update_total} "
        f"paint_total={paint_total} overlay_state={detail}"
    )


def _hide_live_overlays() -> int:
    hidden = 0
    for overlay in _live_overlays():
        try:
            if overlay.isVisible():
                overlay.hide()
                hidden += 1
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Failed to hide overlay", exc_info=True)
    return hidden


def _restore_live_overlays() -> tuple[int, int]:
    """Restore normal visibility and request one current-state presentation."""
    shown = 0
    refreshed = 0
    original_show = _original_show
    original_request = _original_request_frame_update
    if original_show is None or original_request is None:
        return shown, refreshed

    for overlay in _live_overlays():
        try:
            enabled = bool(getattr(overlay, "_enabled", False))
            fade = float(getattr(overlay, "_fade", 0.0) or 0.0)
            if enabled and fade > 0.0 and not overlay.isVisible():
                original_show(overlay)
                shown += 1
            if enabled:
                original_request(overlay, force=True)
                refreshed += 1
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Failed to restore overlay", exc_info=True)
    return shown, refreshed


def set_state(state: PresentationABCState, *, source: str) -> PresentationABCState:
    """Enter one causal state and emit an exact log boundary."""
    global _state, _last_boundary_suppressed_total, _last_boundary_blocked_show_total

    target = PresentationABCState(state)
    previous = _state
    if target == previous:
        return _state

    # Publish the target before visibility restoration so the patched show()
    # follows target-state semantics during this boundary operation.
    _state = target
    hidden = 0
    shown = 0
    refreshed = 0
    if target is PresentationABCState.C_HIDDEN_SURFACE:
        hidden = _hide_live_overlays()
    elif previous is PresentationABCState.C_HIDDEN_SURFACE:
        shown, refreshed = _restore_live_overlays()

    suppressed_delta = max(
        0, _suppressed_request_total - _last_boundary_suppressed_total
    )
    blocked_show_delta = max(
        0, _blocked_show_total - _last_boundary_blocked_show_total
    )
    _last_boundary_suppressed_total = _suppressed_request_total
    _last_boundary_blocked_show_total = _blocked_show_total

    logger.info(
        "[PERF][VIS_PRESENT_ABC] state=%s previous=%s source=%s hotkey=%s "
        "hidden_now=%d restored_now=%d refresh_now=%d "
        "suppressed_requests_since_boundary=%d suppressed_requests_total=%d "
        "blocked_shows_since_boundary=%d blocked_shows_total=%d %s",
        target.value,
        previous.value,
        str(source or "unknown"),
        HOTKEY_LABEL,
        hidden,
        shown,
        refreshed,
        suppressed_delta,
        _suppressed_request_total,
        blocked_show_delta,
        _blocked_show_total,
        _overlay_snapshot_text(),
    )
    return _state


def cycle_state(*, source: str = "hotkey") -> PresentationABCState:
    """Cycle A -> B -> C -> A."""
    try:
        index = _STATE_ORDER.index(_state)
    except ValueError:
        index = 0
    return set_state(_STATE_ORDER[(index + 1) % len(_STATE_ORDER)], source=source)


class _PresentationABCEventFilter(QObject):
    """Consume only Shift+/ while the explicit temporary CLI gate is active."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        del watched
        try:
            if event.type() != QEvent.Type.KeyPress:
                return False
            modifiers = event.modifiers()
            if not bool(modifiers & Qt.KeyboardModifier.ShiftModifier):
                return False

            key = event.key()
            text = str(event.text() or "")
            native_vk = (
                int(event.nativeVirtualKey() or 0)
                if hasattr(event, "nativeVirtualKey")
                else 0
            )
            key_question = getattr(Qt.Key, "Key_Question", None)
            matches = (
                key == Qt.Key.Key_Slash
                or (key_question is not None and key == key_question)
                or text in {"?", "/"}
                or native_vk == 0xBF  # Windows VK_OEM_2 on common layouts.
            )
            if not matches:
                return False
            if hasattr(event, "isAutoRepeat") and bool(event.isAutoRepeat()):
                return True

            cycle_state(source="hotkey_shift_slash")
            return True
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Temporary hotkey filter failed", exc_info=True)
            return False


def install_visualizer_presentation_abc_if_requested() -> bool:
    """Install the temporary A/B/C probe iff ``--viz-present-abc`` is present."""
    global _installed, _event_filter, _overlay_type
    global _original_request_frame_update, _original_show

    if not cli_enabled():
        return False
    if _installed:
        return True

    app = QApplication.instance()
    if app is None:
        logger.warning(
            "[PERF][VIS_PRESENT_ABC] CLI gate present but QApplication is unavailable"
        )
        return False

    from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

    original_request = SpotifyBarsGLOverlay._request_frame_update
    original_show = SpotifyBarsGLOverlay.show
    _overlay_type = SpotifyBarsGLOverlay
    _original_request_frame_update = original_request
    _original_show = original_show

    @functools.wraps(original_request)
    def _abc_request_frame_update(self, *args: Any, **kwargs: Any):
        global _suppressed_request_total
        if _state in (
            PresentationABCState.B_SUPPRESS_REQUESTS,
            PresentationABCState.C_HIDDEN_SURFACE,
        ):
            _suppressed_request_total += 1
            return None
        return original_request(self, *args, **kwargs)

    @functools.wraps(original_show)
    def _abc_show(self, *args: Any, **kwargs: Any):
        global _blocked_show_total
        if _state is PresentationABCState.C_HIDDEN_SURFACE:
            _blocked_show_total += 1
            return None
        return original_show(self, *args, **kwargs)

    SpotifyBarsGLOverlay._request_frame_update = _abc_request_frame_update
    SpotifyBarsGLOverlay.show = _abc_show

    event_filter = _PresentationABCEventFilter(app)
    app.installEventFilter(event_filter)
    _event_filter = event_filter
    _installed = True

    logger.info(
        "[PERF][VIS_PRESENT_ABC] installed cli=%s hotkey=%s initial_state=%s "
        "states=A_NORMAL>B_SUPPRESS_REQUESTS>C_HIDDEN_SURFACE>A_NORMAL "
        "logical_state_untouched=1 temporary_probe=1 %s",
        CLI_FLAG,
        HOTKEY_LABEL,
        _state.value,
        _overlay_snapshot_text(),
    )
    return True


def uninstall_visualizer_presentation_abc() -> None:
    """Restore original class methods/filter; intended for cleanup/test hygiene."""
    global _installed, _state, _event_filter, _overlay_type
    global _original_request_frame_update, _original_show
    global _suppressed_request_total, _blocked_show_total
    global _last_boundary_suppressed_total, _last_boundary_blocked_show_total

    if _state is PresentationABCState.C_HIDDEN_SURFACE:
        _state = PresentationABCState.A_NORMAL
        _restore_live_overlays()

    overlay_cls = _overlay_type
    if overlay_cls is not None and _original_request_frame_update is not None:
        try:
            overlay_cls._request_frame_update = _original_request_frame_update
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Failed to restore request method", exc_info=True)
    if overlay_cls is not None and _original_show is not None:
        try:
            overlay_cls.show = _original_show
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Failed to restore show method", exc_info=True)

    app = QApplication.instance()
    if app is not None and _event_filter is not None:
        try:
            app.removeEventFilter(_event_filter)
        except Exception:
            logger.debug("[VIS_PRESENT_ABC] Failed to remove event filter", exc_info=True)

    _installed = False
    _state = PresentationABCState.A_NORMAL
    _event_filter = None
    _overlay_type = None
    _original_request_frame_update = None
    _original_show = None
    _suppressed_request_total = 0
    _blocked_show_total = 0
    _last_boundary_suppressed_total = 0
    _last_boundary_blocked_show_total = 0
