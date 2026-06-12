"""Display update logic for the MediaWidget.

Extracted from media_widget.py (M-5 refactor) to reduce monolith size.
Contains the core _update_display method that processes media track info,
builds HTML metadata, handles artwork decoding, and manages visibility.
"""
from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.media.media_controller import MediaTrackInfo
from utils.text_utils import smart_title_case

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def _compute_metadata_layout_budget(widget: "MediaWidget", *, has_artwork: bool = False) -> dict[str, int]:
    width = max(1, int(getattr(widget, "width", lambda: 0)() or 0))
    height = max(1, int(getattr(widget, "height", lambda: 0)() or 0))
    try:
        shrink_r, shrink_b = widget.painted_frame_shadow_card_shrink()
    except Exception:
        shrink_r, shrink_b = 0, 0

    left_margin = 29
    top_margin = 12
    if hasattr(widget, "contentsMargins"):
        try:
            margins = widget.contentsMargins()
            left_margin = int(margins.left())
            top_margin = int(margins.top())
        except Exception:
            pass

    artwork_size = max(0, int(getattr(widget, "_artwork_size", 0) or 0))
    base_right_margin = 12
    if hasattr(widget, "contentsMargins"):
        try:
            base_right_margin = int(widget.contentsMargins().right())
        except Exception:
            pass
    if has_artwork:
        right_reserved = max(artwork_size + 40, 60) + int(shrink_r)
    else:
        right_reserved = max(base_right_margin, 12)
    text_width = max(1, width - left_margin - right_reserved - 8)
    content_height = max(1, height - top_margin - int(shrink_b))
    return {
        "text_width": text_width,
        "content_height": content_height,
        "left_margin": left_margin,
        "top_margin": top_margin,
        "right_reserved": right_reserved,
    }


def _compute_metadata_font_scales(
    title: str,
    artist: str,
    *,
    available_width: int = 0,
    available_height: int = 0,
    base_font: int = 20,
) -> tuple[float, float]:
    """Return title/artist font scales for the current metadata payload.

    The media card is intentionally text-first, but the controls row must keep a
    protected visual lane. We therefore shrink slightly earlier for titles that
    are likely to wrap into three lines even if their raw character count is not
    extremely high.
    """
    title_len = len(title)
    artist_len = len(artist)
    combined_len = title_len + artist_len
    word_count = len([part for part in title.split() if part])

    scale_title = 1.0
    if title_len > 32:
        scale_title = 0.92
    if title_len > 40:
        scale_title = 0.84
    if title_len > 55:
        scale_title = 0.74
    if title_len > 70:
        scale_title = 0.64

    if combined_len > 55:
        scale_title = min(scale_title, 0.88)
    if combined_len > 75:
        scale_title = min(scale_title, 0.80)
    if word_count >= 4 and title_len > 28:
        scale_title = min(scale_title, 0.88)

    # Long-metadata heuristics alone are too weak for small committed CUSTOM
    # cards. When width/height are tight, shrink against the actual card
    # envelope before paint rather than protecting the old authored footprint.
    width_pressure = 1.0
    if available_width > 0:
        if available_width <= 520:
            width_pressure = min(width_pressure, 0.94)
        if available_width <= 460:
            width_pressure = min(width_pressure, 0.88)
        if available_width <= 400:
            width_pressure = min(width_pressure, 0.82)
        if available_width <= 340:
            width_pressure = min(width_pressure, 0.74)

    height_pressure = 1.0
    if available_height > 0:
        if available_height <= 260:
            height_pressure = min(height_pressure, 0.94)
        if available_height <= 232:
            height_pressure = min(height_pressure, 0.86)
        if available_height <= 210:
            height_pressure = min(height_pressure, 0.78)
        if available_height <= 190:
            height_pressure = min(height_pressure, 0.70)

    if base_font <= 16:
        width_pressure = min(width_pressure, 0.96)
    if base_font <= 14:
        height_pressure = min(height_pressure, 0.94)

    scale_title = min(scale_title, width_pressure, height_pressure)
    scale_artist = 1.0 - (1.0 - scale_title) * 0.45
    if artist_len > 28:
        scale_artist = min(scale_artist, 0.92)
    if combined_len > 75:
        scale_artist = min(scale_artist, 0.86)
    if available_width > 0 and available_width <= 400:
        scale_artist = min(scale_artist, 0.84)
    if available_height > 0 and available_height <= 232:
        scale_artist = min(scale_artist, 0.80)

    return scale_title, scale_artist


def _compute_media_header_scale(
    *,
    available_width: int = 0,
    available_height: int = 0,
    base_font: int = 20,
) -> float:
    scale = 1.0
    if available_width > 0:
        if available_width <= 260:
            scale = min(scale, 0.92)
        if available_width <= 220:
            scale = min(scale, 0.84)
        if available_width <= 190:
            scale = min(scale, 0.76)
        if available_width <= 170:
            scale = min(scale, 0.68)
    if available_height > 0:
        if available_height <= 232:
            scale = min(scale, 0.92)
        if available_height <= 210:
            scale = min(scale, 0.84)
        if available_height <= 190:
            scale = min(scale, 0.76)
    if base_font <= 16:
        scale = min(scale, 0.96)
    if base_font <= 14:
        scale = min(scale, 0.92)
    return scale


def update_display(widget: "MediaWidget", info: Optional[MediaTrackInfo]) -> None:
    """Process a media track snapshot and update the widget display.

    This is the main update path — called after each poll cycle. It handles:
    - Lifetime guard (widget may be destroyed by async callback)
    - Shared info cache for multi-display desync prevention
    - Smart polling: diff gating, idle detection, adaptive intervals
    - HTML metadata rendering (title, artist, SPOTIFY header)
    - Artwork decoding and fade-in
    - First-track capture and coordinated fade-in
    """
    # Lifetime guard: async callbacks may fire after the widget has been
    # destroyed. Bail out early and stop timers/handles if the underlying
    # Qt object is no longer valid.
    try:
        if not Shiboken.isValid(widget):
            if getattr(widget, "_update_timer_handle", None) is not None:
                try:
                    widget._update_timer_handle.stop()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                widget._update_timer_handle = None

            if getattr(widget, "_update_timer", None) is not None:
                try:
                    widget._update_timer.stop()
                    widget._update_timer.deleteLater()
                except Exception as e:
                    logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                widget._update_timer = None

            widget._enabled = False
            widget._refresh_in_flight = False
            return
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        return

    # Cache last track snapshot for diagnostics/interaction
    prev_info = widget._last_info
    widget._last_info = info

    # Update shared cache when we have valid info
    if info is not None:
        cls = type(widget)
        cls._shared_last_valid_info = info
        cls._shared_last_valid_info_ts = time.monotonic()
        try:
            widget.cache_retained_display_info(info)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    # Smart polling: diff gating - compute track identity
    metadata_changed = False

    if info is not None:
        current_identity = widget._compute_track_identity(info)
        current_metadata_identity = widget._compute_metadata_identity(info)
        metadata_changed = current_metadata_identity != widget._last_metadata_identity

        # Reset idle counter when we get valid track info
        if widget._consecutive_none_count > 0 or widget._is_idle:
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Media widget exiting idle (track detected)")
            widget._consecutive_none_count = 0
            was_idle = widget._is_idle
            widget._is_idle = False
            # Reset activation time to get fresh grace period after recovery
            widget._activation_time = time.monotonic()
            # Reset to fast polling when resuming from idle
            if was_idle:
                widget._reset_poll_stage()
                # Update timer interval from idle (5s) to fast (1s)
                widget._ensure_timer(force=True)

        # Adaptive polling: advance to slower interval after 2 successful polls
        widget._polls_at_current_stage += 1
        if widget._polls_at_current_stage >= 2:
            widget._advance_poll_stage()

        # Diff gating: skip update if track identity unchanged
        if (
            current_identity == widget._last_track_identity
            and widget._last_track_identity is not None
            and widget._fade_in_completed
        ):
            widget._skipped_identity_updates += 1
            if widget._skipped_identity_updates <= widget._max_identity_skip:
                if is_perf_metrics_enabled():
                    logger.debug(
                        "[PERF] Media widget update skipped (diff gating - %d/%d)",
                        widget._skipped_identity_updates,
                        widget._max_identity_skip,
                    )
                return
            if is_perf_metrics_enabled():
                logger.debug("[PERF] Forcing metadata refresh after repeated skips")

        # Track changed - update identity and proceed
        widget._last_track_identity = current_identity
        widget._last_metadata_identity = current_metadata_identity
        widget._skipped_identity_updates = 0
        widget._last_display_update_ts = time.monotonic()
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget update applied (track changed)")
    else:
        metadata_changed = False

    if info is None:
        # MULTI-DISPLAY FIX: Check if other widgets have valid info
        cls = type(widget)
        shared_info = cls._get_shared_valid_info()
        if shared_info is not None:
            logger.debug("[MEDIA_WIDGET] Using shared info from another display")
            info = shared_info
            widget._last_info = info
            try:
                widget.cache_retained_display_info(info)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        # else: No shared info - proceed with normal None handling

    if info is None:
        try:
            failover_info = widget.try_provider_failover()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            failover_info = None
        if failover_info is not None:
            logger.info("[MEDIA_WIDGET] Alternate provider located; continuing with runtime failover snapshot")
            info = failover_info
            widget._last_info = info
            cls = type(widget)
            cls._shared_last_valid_info = info
            cls._shared_last_valid_info_ts = time.monotonic()
            try:
                widget.cache_retained_display_info(info)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    if info is None:
        retained_info = _handle_no_media(widget)
        if retained_info is None:
            return
        info = retained_info
        widget._last_info = info

    # --- Build metadata HTML ---
    final_metadata_identity = widget._compute_metadata_identity(info)
    metadata_changed = bool(metadata_changed or (final_metadata_identity != widget._last_metadata_identity))
    widget._last_metadata_identity = final_metadata_identity

    _build_and_apply_metadata(widget, info, prev_info, metadata_changed=metadata_changed)


def _update_app_process_state(widget: "MediaWidget") -> None:
    """Check whether the target media app process is running and update widget state.

    Called during idle mode to choose between normal idle (5s) and deep idle (30s).
    The actual check is delegated to the media controller's lightweight process
    detection (ctypes Toolhelp32 on Windows) — no GSMTC overhead.
    """
    try:
        controller = getattr(widget, "_controller", None)
        if controller is not None and hasattr(controller, "is_app_process_running"):
            widget._app_process_running = controller.is_app_process_running()
        else:
            widget._app_process_running = False
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Process detection failed: %s", e)
        widget._app_process_running = False


def _handle_no_media(widget: "MediaWidget") -> Optional[MediaTrackInfo]:
    """Handle case where no media info is available.

    Returns a retained display snapshot when the widget should stay visible,
    otherwise returns ``None`` after performing hide/idle logic.
    """
    # Check grace period after activation - don't hide immediately
    time_since_activation = time.monotonic() - widget._activation_time
    if widget._activation_time > 0 and time_since_activation < widget._post_activation_grace_sec:
        if is_verbose_logging():
            logger.debug(
                "[MEDIA_WIDGET] In grace period after activation (%.1fs), skipping hide",
                time_since_activation,
            )
        return widget.get_retained_display_info()

    # Smart polling: idle detection - track consecutive None results
    widget._consecutive_none_count += 1
    try:
        widget.note_missing_session()
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    # Enter idle mode after threshold consecutive None results (~30s)
    if widget._consecutive_none_count >= widget._idle_threshold and not widget._is_idle:
        widget._is_idle = True
        widget._last_track_identity = None
        # Check if the media app process is still running to choose idle interval
        _update_app_process_state(widget)
        if is_perf_metrics_enabled():
            logger.debug(
                "[PERF] Media widget entering idle mode (process_running=%s, interval=%s)",
                widget._app_process_running,
                widget._idle_poll_interval if widget._app_process_running else widget._deep_idle_poll_interval,
            )
        else:
            logger.info(
                "[MEDIA_WIDGET] Entering idle mode after %d consecutive empty polls (app running: %s)",
                widget._consecutive_none_count,
                widget._app_process_running,
            )
        # Update timer interval from active (2.5s) to idle (5s or 30s)
        widget._ensure_timer(force=True)
    elif widget._is_idle and widget._consecutive_none_count % 6 == 0:
        # Periodically re-check process state during idle to detect app launch/exit
        prev_running = widget._app_process_running
        _update_app_process_state(widget)
        if prev_running != widget._app_process_running:
            logger.info(
                "[MEDIA_WIDGET] App process state changed: %s → %s",
                prev_running, widget._app_process_running,
            )
            widget._ensure_timer(force=True)

    retained_info = None
    try:
        retained_info = widget.get_retained_display_info()
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    if retained_info is not None:
        if widget._telemetry_last_visibility is not True:
            logger.info("[MEDIA_WIDGET] Live session missing; retaining cached media card display")
        widget._telemetry_last_visibility = True
        try:
            widget._emit_media_update(retained_info)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        return retained_info

    # No retained snapshot available – hide widget with graceful fade
    last_vis = widget._telemetry_last_visibility
    if last_vis or last_vis is None:
        logger.info("[MEDIA_WIDGET] No active media session; hiding media card")
    widget._artwork_pixmap = None
    widget._scaled_artwork_cache = None
    widget._scaled_artwork_cache_key = None

    # Graceful fade out instead of instant hide
    if widget.isVisible():
        try:
            from widgets.shadow_utils import ShadowFadeProfile

            ShadowFadeProfile.start_fade_out(
                widget,
                duration_ms=800,
                on_complete=lambda: widget._complete_hide_sequence(),
            )
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Fade out failed, hiding instantly: %s", e)
            widget._complete_hide_sequence()
    else:
        widget._complete_hide_sequence()

    widget._telemetry_last_visibility = False
    return None


def _build_and_apply_metadata(
    widget: "MediaWidget",
    info: MediaTrackInfo,
    prev_info: Optional[MediaTrackInfo],
    *,
    metadata_changed: bool,
) -> None:
    """Build HTML metadata and update widget text/artwork/layout."""
    title = smart_title_case((info.title or "").strip())
    artist = smart_title_case((info.artist or "").strip())
    display_title = title
    display_artist = artist
    if not title and not artist:
        display_title = "(no metadata)"
        display_artist = ""
    else:
        pass

    if metadata_changed or not getattr(widget, "_metadata_paint", None):
        layout_budget = _compute_metadata_layout_budget(
            widget,
            has_artwork=bool(getattr(info, "artwork", None) or getattr(widget, "_artwork_pixmap", None)),
        )
        base_font = max(6, widget._font_size)
        header_scale = _compute_media_header_scale(
            available_width=int(layout_budget["text_width"]),
            available_height=int(layout_budget["content_height"]),
            base_font=base_font,
        )
        header_font = max(6, int(base_font * 1.2 * header_scale))

        title_font_base = max(6, base_font + 3)
        artist_font_base = max(6, base_font - 2)

        scale_title, scale_artist = _compute_metadata_font_scales(
            title,
            artist,
            available_width=int(layout_budget["text_width"]),
            available_height=int(layout_budget["content_height"]),
            base_font=base_font,
        )

        title_font = max(6, int(title_font_base * scale_title))
        artist_font = max(6, int(artist_font_base * scale_artist))

        header_weight = 750
        title_weight = 700
        artist_weight = 600

        if not title and not artist:
            title_font = base_font
            title_weight = 500
            metadata_complexity = 0
        else:
            metadata_complexity = len(title.strip()) + len(artist.strip())

        # Store logo metrics so paintEvent can size/position the glyph
        widget._header_font_pt = header_font
        widget._header_logo_size = max(12, int(header_font * 1.3))
        widget._header_logo_margin = widget._header_logo_size

        # Adjust artwork vertical bias only when the text layout identity changes.
        if metadata_complexity <= 0:
            widget._artwork_vertical_bias = 0.58
        elif metadata_complexity <= 40:
            widget._artwork_vertical_bias = 0.55
        elif metadata_complexity <= 80:
            widget._artwork_vertical_bias = 0.45
        else:
            widget._artwork_vertical_bias = 0.32
    else:
        base_font = int(widget._metadata_paint.get("base_font", max(6, widget._font_size)))
        header_font = int(widget._metadata_paint.get("header_font", max(6, int(base_font * 1.2))))
        title_font = int(widget._metadata_paint.get("title_font", max(6, base_font + 3)))
        artist_font = int(widget._metadata_paint.get("artist_font", max(6, base_font - 2)))
        header_weight = int(widget._metadata_paint.get("header_weight", 750))
        title_weight = int(widget._metadata_paint.get("title_weight", 700))
        artist_weight = int(widget._metadata_paint.get("artist_weight", 600))

    compact_height = int(getattr(widget, "height", lambda: 0)() or 0)
    compact_line_spacing = 4
    compact_body_gap = 8
    if compact_height and compact_height <= 260:
        compact_line_spacing = 3
        compact_body_gap = 6
    if compact_height and compact_height <= 232:
        compact_line_spacing = 2
        compact_body_gap = 4

    widget._metadata_paint = {
        "provider": widget.provider_display_name,
        "title": display_title,
        "artist": display_artist,
        "base_font": base_font,
        "header_font": header_font,
        "title_font": title_font,
        "artist_font": artist_font,
        "header_weight": header_weight,
        "title_weight": title_weight,
        "artist_weight": artist_weight,
        "line_spacing": compact_line_spacing,
        "body_top_gap": compact_body_gap,
    }

    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setText("")

    # Lock the card height after the first track
    if widget._fixed_card_height is None:
        try:
            hint_h = widget.sizeHint().height()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            hint_h = 0
        base_min = widget.minimumHeight()
        control_padding = widget._controls_row_min_height()
        widget._fixed_card_height = max(220, base_min, hint_h + control_padding)

    widget.setMinimumHeight(widget._fixed_card_height)
    widget.setMaximumHeight(widget._fixed_card_height)

    # CRITICAL: Decode artwork BEFORE the first-track early return
    artwork_pm = widget._decode_artwork_pixmap(getattr(info, "artwork", None))
    if artwork_pm is not None:
        widget._artwork_pixmap = artwork_pm
        if is_verbose_logging():
            logger.debug(
                "[MEDIA_WIDGET] Artwork decoded: %dx%d",
                artwork_pm.width(),
                artwork_pm.height(),
            )

    # CRITICAL: Set content margins BEFORE the first-track early return
    shrink_r, shrink_b = widget.painted_frame_shadow_card_shrink()
    right_margin = max(widget._artwork_size + 40, 60) + shrink_r
    widget.setContentsMargins(29, 12, right_margin, widget._controls_row_margin() + shrink_b)

    # On the very first non-empty track update we use this call to
    # establish a stable layout (card stays hidden until fade sync)
    if not widget._has_seen_first_track:
        widget._has_seen_first_track = True
        widget._emit_media_update(info)
        try:
            widget.hide()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        if not widget._telemetry_logged_fade_request:
            logger.info(
                "[MEDIA_WIDGET] First track snapshot captured; waiting for coordinated fade-in"
            )
        parent = widget.parent()

        def _starter() -> None:
            if not Shiboken.isValid(widget):
                return
            widget._start_widget_fade_in(1500)
            widget._notify_spotify_widgets_visibility()
            widget._telemetry_last_visibility = True

        if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
            try:
                parent.request_overlay_fade_sync("media", _starter)
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                _starter()
        else:
            _starter()
        return

    widget._emit_media_update(info)
    _ensure_widget_visible_for_active_metadata(widget)

    # Decode optional artwork bytes (for subsequent updates after first track)
    prev_pm = widget._artwork_pixmap
    had_artwork_before = prev_pm is not None and not prev_pm.isNull()
    widget._artwork_pixmap = None
    artwork_pm = widget._decode_artwork_pixmap(getattr(info, "artwork", None))
    if artwork_pm is not None:
        widget._artwork_pixmap = artwork_pm

        # Fade in artwork whenever it appears for the first time or when metadata changes
        should_fade_artwork = False
        if not had_artwork_before:
            should_fade_artwork = True
        else:
            try:
                if prev_info is None:
                    should_fade_artwork = True
                else:
                    def _norm(s: Optional[str]) -> str:
                        return (s or "").strip()

                    if (
                        _norm(getattr(prev_info, "title", None))
                        != _norm(getattr(info, "title", None))
                        or _norm(getattr(prev_info, "artist", None))
                        != _norm(getattr(info, "artist", None))
                        or _norm(getattr(prev_info, "album", None))
                        != _norm(getattr(info, "album", None))
                    ):
                        should_fade_artwork = True
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
                should_fade_artwork = False

        if should_fade_artwork:
            widget._start_artwork_fade_in()


def _ensure_widget_visible_for_active_metadata(widget: "MediaWidget") -> None:
    """Re-enter the shared fade path when metadata returns after a real hide."""

    parent = widget.parentWidget()
    if getattr(widget, "_custom_layout_shell_active", False) or getattr(parent, "_custom_layout_edit_active", False):
        widget._telemetry_last_visibility = False
        return

    try:
        if widget.isVisible():
            widget._telemetry_last_visibility = True
            return
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        return

    try:
        widget._start_widget_fade_in()
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Failed to restart media fade-in: %s", e)
        try:
            widget.show()
        except Exception as show_exc:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", show_exc)
            return

    try:
        widget._notify_spotify_widgets_visibility()
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
    widget._telemetry_last_visibility = True
