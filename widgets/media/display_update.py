"""Temporary F4 QWidget state projection for accepted Media snapshots."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.media.media_controller import MediaTrackInfo

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def _update_progress_paint_state(
    widget: "MediaWidget",
    info: MediaTrackInfo | None,
) -> bool:
    """Commit a pixel-quantized F4 progress snapshot and report visual change."""

    visible = False
    fill_width = 0
    paint_key: tuple = (False,)
    if bool(getattr(widget, "_playback_progress_enabled", False)) and info is not None:
        try:
            duration_ms = int(info.duration_ms) if info.duration_ms is not None else 0
            position_ms = int(info.position_ms) if info.position_ms is not None else 0
        except (TypeError, ValueError, OverflowError):
            duration_ms = 0
            position_ms = 0
        if duration_ms > 0:
            layout_getter = getattr(widget, "_compute_controls_layout", None)
            layout = layout_getter() if callable(layout_getter) else None
            progress_rect = (
                layout.get("progress_rect") if isinstance(layout, dict) else None
            )
            if progress_rect is not None and not progress_rect.isEmpty():
                position_ms = max(0, min(duration_ms, position_ms))
                fill_width = int(
                    round(progress_rect.width() * position_ms / duration_ms)
                )
                fill_width = max(0, min(progress_rect.width(), fill_width))
                visible = True
                paint_key = (
                    True,
                    progress_rect.x(),
                    progress_rect.y(),
                    progress_rect.width(),
                    progress_rect.height(),
                    fill_width,
                    getattr(widget, "_playback_progress_fill_color", None).rgba()
                    if getattr(widget, "_playback_progress_fill_color", None)
                    is not None
                    else 0,
                    bool(getattr(widget, "_playback_progress_shadow_enabled", False)),
                    bool(getattr(widget, "_playback_progress_glow_enabled", False)),
                    getattr(widget, "_playback_progress_glow_color", None).rgba()
                    if getattr(widget, "_playback_progress_glow_color", None)
                    is not None
                    else 0,
                )

    old_key = getattr(widget, "_playback_progress_paint_key", None)
    changed = paint_key != old_key
    if old_key is None and paint_key == (False,):
        changed = False
    widget._playback_progress_visible = visible
    widget._playback_progress_fill_width = fill_width
    widget._playback_progress_paint_key = paint_key
    return changed


def _hide_missing_media_presentation(widget: "MediaWidget") -> None:
    """Hide the temporary F4 anchor without mutating the runtime owner."""

    if widget._telemetry_last_visibility in {True, None}:
        logger.info("[MEDIA_WIDGET] No accepted media snapshot; hiding media controls")
    try:
        visible = bool(widget.isVisible())
    except Exception:
        visible = False
    if visible:
        try:
            from widgets.shadow_utils import ShadowFadeProfile

            ShadowFadeProfile.start_fade_out(
                widget,
                duration_ms=800,
                on_complete=lambda: widget._complete_hide_sequence(),
            )
        except Exception as exc:
            logger.debug("[MEDIA_WIDGET] Fade out failed, hiding instantly: %s", exc)
            widget._complete_hide_sequence()
    else:
        widget._complete_hide_sequence()
    widget._telemetry_last_visibility = False


def _ensure_widget_visible_for_active_media(widget: "MediaWidget") -> None:
    """Restore the temporary F4 anchor when accepted playback state returns."""

    parent = widget.parentWidget()
    if bool(getattr(widget, "_custom_layout_shell_active", False)) or bool(
        getattr(parent, "_custom_layout_edit_active", False)
    ):
        widget._telemetry_last_visibility = False
        return
    try:
        if widget.isVisible():
            widget._telemetry_last_visibility = True
            return
    except Exception as exc:
        logger.debug("[MEDIA_WIDGET] Visibility read failed: %s", exc)
        return
    try:
        widget._start_widget_fade_in()
    except Exception as exc:
        logger.debug("[MEDIA_WIDGET] Failed to restart Media controls fade: %s", exc)
        try:
            widget.show()
        except Exception:
            return
    widget._notify_spotify_widgets_visibility()
    widget._telemetry_last_visibility = True


def _publish_first_media_state(widget: "MediaWidget", info: MediaTrackInfo) -> None:
    widget._has_seen_first_track = True
    widget._emit_media_update(info)
    safe_update = getattr(widget, "_safe_update", None)
    if callable(safe_update):
        safe_update()
    try:
        widget.hide()
    except Exception:
        pass
    parent = widget.parent()

    def _starter() -> None:
        try:
            if not Shiboken.isValid(widget):
                return
        except Exception:
            return
        widget._start_widget_fade_in(1500)
        widget._notify_spotify_widgets_visibility()
        widget._telemetry_last_visibility = True

    if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
        try:
            parent.request_overlay_fade_sync("media", _starter)
        except Exception:
            _starter()
    else:
        _starter()


def update_display(
    widget: "MediaWidget",
    info: MediaTrackInfo | None,
) -> None:
    """Project only state still required by the temporary F4 QWidget paths."""

    try:
        if not Shiboken.isValid(widget):
            return
    except Exception as exc:
        logger.debug("[MEDIA_WIDGET] Lifetime check failed: %s", exc)
        return

    widget._perf_media_display_total = (
        int(getattr(widget, "_perf_media_display_total", 0) or 0) + 1
    )
    previous = widget._last_info
    widget._last_info = info
    if info is None:
        widget._last_track_identity = None
        _update_progress_paint_state(widget, None)
        _hide_missing_media_presentation(widget)
        return

    progress_changed = _update_progress_paint_state(widget, info)
    identity = widget._compute_track_identity(info)
    state_changed = identity != widget._last_track_identity
    widget._last_track_identity = identity
    widget._last_display_update_ts = time.monotonic()

    if not widget._has_seen_first_track:
        _publish_first_media_state(widget, info)
        return

    if state_changed:
        widget._emit_media_update(info)
    _ensure_widget_visible_for_active_media(widget)
    if state_changed or progress_changed or previous is None:
        safe_update = getattr(widget, "_safe_update", None)
        if callable(safe_update):
            safe_update()
