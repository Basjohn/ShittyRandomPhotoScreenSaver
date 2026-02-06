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

    # Smart polling: diff gating - compute track identity
    if info is not None:
        current_identity = widget._compute_track_identity(info)

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
        widget._skipped_identity_updates = 0
        widget._last_display_update_ts = time.monotonic()
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget update applied (track changed)")

    if info is None:
        # MULTI-DISPLAY FIX: Check if other widgets have valid info
        cls = type(widget)
        shared_info = cls._get_shared_valid_info()
        if shared_info is not None:
            logger.debug("[MEDIA_WIDGET] Using shared info from another display")
            info = shared_info
            widget._last_info = info
        # else: No shared info - proceed with normal None handling

    if info is None:
        _handle_no_media(widget)
        return

    # --- Build metadata HTML ---
    _build_and_apply_metadata(widget, info, prev_info)


def _handle_no_media(widget: "MediaWidget") -> None:
    """Handle case where no media info is available — idle/hide logic."""
    # Check grace period after activation - don't hide immediately
    time_since_activation = time.monotonic() - widget._activation_time
    if widget._activation_time > 0 and time_since_activation < widget._post_activation_grace_sec:
        if is_verbose_logging():
            logger.debug(
                "[MEDIA_WIDGET] In grace period after activation (%.1fs), skipping hide",
                time_since_activation,
            )
        return

    # Smart polling: idle detection - track consecutive None results
    widget._consecutive_none_count += 1

    # Enter idle mode after threshold consecutive None results (~30s)
    if widget._consecutive_none_count >= widget._idle_threshold and not widget._is_idle:
        widget._is_idle = True
        widget._last_track_identity = None
        if is_perf_metrics_enabled():
            logger.debug("[PERF] Media widget entering idle mode (Spotify closed)")
        else:
            logger.info(
                "[MEDIA_WIDGET] Entering idle mode after %d consecutive empty polls",
                widget._consecutive_none_count,
            )
        # Update timer interval from active (2.5s) to idle (5s)
        widget._ensure_timer(force=True)

    # No active media session – hide widget with graceful fade
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


def _build_and_apply_metadata(
    widget: "MediaWidget",
    info: MediaTrackInfo,
    prev_info: Optional[MediaTrackInfo],
) -> None:
    """Build HTML metadata and update widget text/artwork/layout."""
    title = smart_title_case((info.title or "").strip())
    artist = smart_title_case((info.artist or "").strip())

    base_font = max(6, widget._font_size)
    header_font = max(6, int(base_font * 1.2))

    title_font_base = max(6, base_font + 3)
    artist_font_base = max(6, base_font - 2)

    title_len = len(title)
    scale_title = 1.0
    if title_len > 40:
        scale_title = 0.86
    if title_len > 55:
        scale_title = 0.76
    if title_len > 70:
        scale_title = 0.66

    scale_artist = 1.0 - (1.0 - scale_title) * 0.4

    title_font = max(6, int(title_font_base * scale_title))
    artist_font = max(6, int(artist_font_base * scale_artist))

    header_weight = 750
    title_weight = 700
    artist_weight = 600

    # Store logo metrics so paintEvent can size/position the glyph
    widget._header_font_pt = header_font
    widget._header_logo_size = max(12, int(header_font * 1.3))
    widget._header_logo_margin = widget._header_logo_size

    # Build metadata lines with per-line font sizes/weights
    if not title and not artist:
        body_html = (
            f"<div style='font-size:{base_font}pt; font-weight:500;'>(no metadata)</div>"
        )
        metadata_complexity = 0
    else:
        body_lines_html = []
        if title:
            body_lines_html.append(
                f"<div style='font-size:{title_font}pt; font-weight:{title_weight};'>{title}</div>"
            )
        if artist:
            body_lines_html.append(
                f"<div style='margin-top:4px; font-size:{artist_font}pt; font-weight:{artist_weight}; opacity:0.95;'>{artist}</div>"
            )
        body_html = "".join(body_lines_html)
        metadata_complexity = len(title.strip()) + len(artist.strip())

    header_html = (
        f"<div style='font-size:{header_font}pt; font-weight:{header_weight}; "
        f"letter-spacing:1px; margin-left:{widget._header_logo_margin + 5}px; "
        f"color:rgba(255,255,255,255);'>SPOTIFY</div>"
    )
    body_wrapper = f"<div style='margin-top:8px;'>{body_html}</div>"

    html_parts = ["<div style='line-height:1.25'>", header_html, body_wrapper]
    html_parts.append("</div>")
    html = "".join(html_parts)

    widget.setTextFormat(Qt.TextFormat.RichText)
    widget.setText(html)

    # Adjust artwork vertical bias
    if metadata_complexity <= 0:
        widget._artwork_vertical_bias = 0.58
    elif metadata_complexity <= 40:
        widget._artwork_vertical_bias = 0.55
    elif metadata_complexity <= 80:
        widget._artwork_vertical_bias = 0.45
    else:
        widget._artwork_vertical_bias = 0.32

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
    right_margin = max(widget._artwork_size + 40, 60)
    widget.setContentsMargins(29, 12, right_margin, widget._controls_row_margin())

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
