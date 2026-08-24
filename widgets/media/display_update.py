"""Pure QWidget projection for accepted Media runtime snapshots.

The neutral owner has already resolved provider/query/cache state and decoded
changed artwork into a source-resolution QImage. This module performs only the
per-display metadata, progress, visibility, layout and prepared-artwork handoff.
"""
from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, SIGNAL
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.media.media_controller import MediaTrackInfo
from utils.text_utils import smart_title_case

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def _has_stable_visible_presentation(widget: "MediaWidget") -> bool:
    """Return True when an unchanged card needs no visibility reconciliation."""
    try:
        parent = widget.parentWidget()
    except Exception:
        parent = None
    if (
        bool(getattr(widget, "_custom_layout_shell_active", False))
        or bool(getattr(parent, "_custom_layout_edit_active", False))
    ):
        return True
    try:
        return bool(widget.isVisible())
    except Exception:
        return False


def _suppress_unchanged_refresh(
    widget: "MediaWidget",
    *,
    budget_exhausted: bool,
) -> None:
    """Keep the periodic unchanged-card diagnostic passive and transition-safe."""
    transition_active = False
    try:
        checker = getattr(type(widget), "_has_transition_work_on_any_display", None)
        transition_active = bool(checker()) if callable(checker) else False
    except Exception:
        transition_active = False

    pending = bool(getattr(widget, "_unchanged_refresh_diag_pending", False))
    if budget_exhausted and transition_active:
        widget._unchanged_refresh_diag_pending = True
        return
    if not budget_exhausted and not pending:
        return
    if transition_active:
        return

    widget._unchanged_refresh_diag_pending = False
    if is_perf_metrics_enabled():
        logger.debug(
            "[PERF][MEDIA_PRESENTATION] event=unchanged_refresh_suppressed "
            "deferred_for_transition=%s update_requested=False layout_mutations=0",
            pending,
        )




def _accept_prepared_artwork_for_info(
    widget: "MediaWidget",
    info: MediaTrackInfo,
    prepared_artwork,
    artwork_generation: int,
) -> bool:
    """Promote or apply prepared artwork belonging to one resolved snapshot."""

    try:
        final_artwork_key = widget._compute_artwork_key(info)
    except Exception:
        final_artwork_key = None

    prepared_for_final_info = prepared_artwork
    if final_artwork_key != getattr(prepared_artwork, "key", None):
        pending = getattr(widget, "_pending_artwork", None)
        if pending is not None and getattr(pending, "key", None) == final_artwork_key:
            prepared_for_final_info = pending
        else:
            prepared_for_final_info = None

    if prepared_for_final_info is None:
        return False

    try:
        return bool(
            widget._accept_prepared_artwork(
                prepared_for_final_info,
                artwork_generation,
                refresh_layout_after_apply=False,
            )
        )
    except Exception:
        logger.debug(
            "[MEDIA_WIDGET] Failed to accept prepared artwork",
            exc_info=True,
        )
        return False


def _prepared_artwork_requires_acceptance(
    widget: "MediaWidget",
    info: MediaTrackInfo,
    prepared_artwork,
) -> bool:
    """Return whether a prepared result can change the card's artwork state.

    A normal unchanged poll carries a ``PreparedArtwork`` marker with the
    already-applied key and no image.  Sending that marker through the
    transition/artwork owner is harmless today, but it is needless UI-path
    work during the short first-card fade window.  Keep the call when it can
    promote a pending key or clear a stale deferred replacement.
    """

    try:
        final_key = widget._compute_artwork_key(info)
    except Exception:
        return True

    pending = getattr(widget, "_pending_artwork", None)
    prepared_key = getattr(prepared_artwork, "key", None)
    if final_key != prepared_key:
        return pending is not None and getattr(pending, "key", None) == final_key

    applied_key = getattr(widget, "_applied_artwork_key", None)
    return final_key != applied_key or pending is not None


def _has_fixed_metadata_presentation(widget: "MediaWidget") -> bool:
    """Return whether first-track layout is already authoritative while fading."""

    return bool(
        getattr(widget, "_has_seen_first_track", False)
        and getattr(widget, "_fixed_card_height", None) is not None
        and getattr(widget, "_metadata_paint", None)
    )


def _update_progress_paint_state(
    widget: "MediaWidget",
    info: Optional[MediaTrackInfo],
) -> bool:
    """Commit a pixel-quantized progress snapshot and report visual change."""

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
            progress_rect = layout.get("progress_rect") if isinstance(layout, dict) else None
            if progress_rect is not None and not progress_rect.isEmpty():
                position_ms = max(0, min(duration_ms, position_ms))
                fill_width = int(round(progress_rect.width() * position_ms / duration_ms))
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
                    if getattr(widget, "_playback_progress_fill_color", None) is not None
                    else 0,
                    bool(getattr(widget, "_playback_progress_shadow_enabled", False)),
                    bool(getattr(widget, "_playback_progress_glow_enabled", False)),
                    getattr(widget, "_playback_progress_glow_color", None).rgba()
                    if getattr(widget, "_playback_progress_glow_color", None) is not None
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


def update_display(
    widget: "MediaWidget",
    info: Optional[MediaTrackInfo],
    *,
    prepared_artwork=None,
    artwork_generation: int | None = None,
) -> None:
    """Project one accepted neutral runtime snapshot into QWidget state."""

    try:
        if not Shiboken.isValid(widget):
            return
    except Exception as exc:
        logger.debug("[MEDIA_WIDGET] Lifetime check failed: %s", exc)
        return

    widget._perf_media_display_total = (
        int(getattr(widget, "_perf_media_display_total", 0) or 0) + 1
    )
    prev_info = widget._last_info
    widget._last_info = info

    if info is None:
        widget._last_track_identity = None
        widget._last_metadata_identity = None
        widget._skipped_identity_updates = 0
        widget._unchanged_refresh_diag_pending = False
        _update_progress_paint_state(widget, None)
        _hide_missing_media_presentation(widget)
        return

    progress_changed = _update_progress_paint_state(widget, info)
    current_identity = widget._compute_track_identity(info)
    current_metadata_identity = widget._compute_metadata_identity(info)
    metadata_changed = current_metadata_identity != widget._last_metadata_identity
    artwork_changed = False

    # The neutral owner supplies a source-resolution QImage plus stable key.
    # QPixmap creation, transition deferral and per-display caches stay here.
    if (
        prepared_artwork is not None
        and artwork_generation is not None
        and _prepared_artwork_requires_acceptance(widget, info, prepared_artwork)
    ):
        artwork_changed = _accept_prepared_artwork_for_info(
            widget,
            info,
            prepared_artwork,
            int(artwork_generation),
        )

    if (
        current_identity == widget._last_track_identity
        and widget._last_track_identity is not None
        and not artwork_changed
        and (
            (
                widget._fade_in_completed
                and _has_stable_visible_presentation(widget)
            )
            or (
                not metadata_changed
                and _has_fixed_metadata_presentation(widget)
            )
        )
    ):
        widget._skipped_identity_updates += 1
        budget_exhausted = (
            widget._skipped_identity_updates > widget._max_identity_skip
        )
        if budget_exhausted:
            widget._skipped_identity_updates = 0
        elif is_perf_metrics_enabled():
            logger.debug(
                "[PERF] Media widget update skipped (diff gating - %d/%d)",
                widget._skipped_identity_updates,
                widget._max_identity_skip,
            )
        _suppress_unchanged_refresh(
            widget,
            budget_exhausted=budget_exhausted,
        )
        if progress_changed:
            safe_update = getattr(widget, "_safe_update", None)
            if callable(safe_update):
                safe_update()
        return

    widget._last_track_identity = current_identity
    widget._last_metadata_identity = current_metadata_identity
    widget._skipped_identity_updates = 0
    widget._unchanged_refresh_diag_pending = False
    widget._last_display_update_ts = time.monotonic()
    if is_perf_metrics_enabled():
        logger.debug("[PERF] Media widget accepted runtime snapshot")

    _build_and_apply_metadata(
        widget,
        info,
        prev_info,
        metadata_changed=bool(metadata_changed or artwork_changed),
    )


def _hide_missing_media_presentation(widget: "MediaWidget") -> None:
    """Hide an empty accepted snapshot without owning runtime/retention policy."""

    last_visibility = widget._telemetry_last_visibility
    if last_visibility or last_visibility is None:
        logger.info("[MEDIA_WIDGET] No accepted media snapshot; hiding media card")

    clear_artwork = getattr(widget, "_clear_artwork_for_missing_media", None)
    if callable(clear_artwork):
        clear_artwork()
    else:
        widget._artwork_pixmap = None
        widget._scaled_artwork_cache = None
        widget._scaled_artwork_cache_key = None
        widget._applied_artwork_key = (0, "")

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


def _ensure_painter_owned_label_contract(widget: "MediaWidget") -> int:
    """Keep QLabel inert without invalidating it on every metadata refresh."""

    mutations = 0
    missing = object()
    try:
        current_format = widget.textFormat()
    except Exception:
        current_format = missing
    if current_format != Qt.TextFormat.PlainText:
        widget.setTextFormat(Qt.TextFormat.PlainText)
        mutations += 1

    try:
        current_text = widget.text()
    except Exception:
        current_text = missing
    if current_text != "":
        widget.setText("")
        mutations += 1
    return mutations


def _ensure_card_geometry_contract(
    widget: "MediaWidget",
    *,
    fixed_height: int,
    right_margin: int,
    bottom_margin: int,
) -> int:
    """Apply fixed card geometry only when the actual Qt state differs."""

    mutations = 0
    try:
        minimum_height = int(widget.minimumHeight())
    except Exception:
        minimum_height = -1
    if minimum_height != fixed_height:
        widget.setMinimumHeight(fixed_height)
        mutations += 1

    try:
        maximum_height = int(widget.maximumHeight())
    except Exception:
        maximum_height = -1
    if maximum_height != fixed_height:
        widget.setMaximumHeight(fixed_height)
        mutations += 1

    expected_margins = (29, 12, int(right_margin), int(bottom_margin))
    try:
        margins = widget.contentsMargins()
        current_margins = (
            int(margins.left()),
            int(margins.top()),
            int(margins.right()),
            int(margins.bottom()),
        )
    except Exception:
        current_margins = None
    if current_margins != expected_margins:
        widget.setContentsMargins(*expected_margins)
        mutations += 1
    return mutations


def _log_metadata_publication(
    widget: "MediaWidget",
    *,
    event: str,
    metadata_changed: bool,
    presentation_changed: bool,
    layout_mutations: int,
    update_requested: bool,
    layout_ms: float,
    emit_ms: float,
) -> None:
    if not is_perf_metrics_enabled():
        return
    transition_active = False
    try:
        checker = getattr(type(widget), "_has_transition_work_on_any_display", None)
        transition_active = bool(checker()) if callable(checker) else False
    except Exception:
        transition_active = False
    try:
        subscriber_count = int(
            widget.receivers(SIGNAL("media_updated(QVariantMap)"))
        )
    except Exception:
        subscriber_count = -1
    logger.info(
        "[PERF][MEDIA_PRESENTATION] event=%s metadata_changed=%s "
        "presentation_changed=%s deferred_for_transition=False "
        "transition_active=%s layout_mutations=%d update_requested=%s "
        "layout_ms=%.2f emit_ms=%.2f subscriber_count=%d generation=%d",
        event,
        bool(metadata_changed),
        bool(presentation_changed),
        transition_active,
        int(layout_mutations),
        bool(update_requested),
        max(0.0, float(layout_ms)),
        max(0.0, float(emit_ms)),
        subscriber_count,
        int(getattr(widget, "_artwork_update_generation", 0)),
    )


def _build_and_apply_metadata(
    widget: "MediaWidget",
    info: MediaTrackInfo,
    prev_info: Optional[MediaTrackInfo],
    *,
    metadata_changed: bool,
    layout_only: bool = False,
) -> None:
    """Build HTML metadata and update widget text/artwork/layout."""
    update_started = time.monotonic()
    previous_state = getattr(prev_info, "state", None) if prev_info is not None else None
    current_state = getattr(info, "state", None)
    presentation_changed = prev_info is None or previous_state != current_state
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
            has_artwork=_has_applied_artwork(widget),
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

    layout_mutations = _ensure_painter_owned_label_contract(widget)

    # Lock the card height after the first track
    if widget._fixed_card_height is None:
        try:
            hint_h = widget.sizeHint().height()
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
            hint_h = 0
        base_min = widget.minimumHeight()
        reserved_height = getattr(widget, "_controls_reserved_height", None)
        control_padding = (
            reserved_height()
            if callable(reserved_height)
            else widget._controls_row_min_height()
        )
        widget._fixed_card_height = max(220, base_min, hint_h + control_padding)

    # Artwork and its reserved lane become visible atomically. Deferred
    # worker results therefore leave both the current pixmap and margins alone.
    shrink_r, shrink_b = widget.painted_frame_shadow_card_shrink()
    if _has_applied_artwork(widget):
        right_margin = max(widget._artwork_size + 40, 60) + shrink_r
    else:
        right_margin = 12 + shrink_r
    layout_mutations += _ensure_card_geometry_contract(
        widget,
        fixed_height=int(widget._fixed_card_height),
        right_margin=right_margin,
        bottom_margin=widget._controls_row_margin() + shrink_b,
    )
    refresh_metadata_boundary = getattr(widget, "_refresh_metadata_paint_boundary", None)
    if callable(refresh_metadata_boundary):
        refresh_metadata_boundary()
    refresh_progress_snapshot = getattr(widget, "_refresh_playback_progress_snapshot", None)
    if callable(refresh_progress_snapshot):
        refresh_progress_snapshot()
    layout_ms = max(0.0, (time.monotonic() - update_started) * 1000.0)

    if layout_only:
        safe_update = getattr(widget, "_safe_update", None)
        if callable(safe_update):
            safe_update()
        _log_metadata_publication(
            widget,
            event="layout_refresh",
            metadata_changed=metadata_changed,
            presentation_changed=presentation_changed,
            layout_mutations=layout_mutations,
            update_requested=True,
            layout_ms=layout_ms,
            emit_ms=0.0,
        )
        return

    # On the very first non-empty track update we use this call to
    # establish a stable layout (card stays hidden until fade sync)
    if not widget._has_seen_first_track:
        widget._has_seen_first_track = True
        emit_started = time.monotonic()
        widget._emit_media_update(info)
        emit_ms = max(0.0, (time.monotonic() - emit_started) * 1000.0)
        safe_update = getattr(widget, "_safe_update", None)
        if callable(safe_update):
            safe_update()
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
        _log_metadata_publication(
            widget,
            event="first_track",
            metadata_changed=metadata_changed,
            presentation_changed=presentation_changed,
            layout_mutations=layout_mutations,
            update_requested=True,
            layout_ms=layout_ms,
            emit_ms=emit_ms,
        )
        return

    emit_started = time.monotonic()
    widget._emit_media_update(info)
    emit_ms = max(0.0, (time.monotonic() - emit_started) * 1000.0)
    _ensure_widget_visible_for_active_metadata(widget)
    update_requested = bool(metadata_changed or presentation_changed or layout_mutations)
    if update_requested:
        safe_update = getattr(widget, "_safe_update", None)
        if callable(safe_update):
            safe_update()
    if metadata_changed or presentation_changed or layout_mutations:
        _log_metadata_publication(
            widget,
            event="published",
            metadata_changed=metadata_changed,
            presentation_changed=presentation_changed,
            layout_mutations=layout_mutations,
            update_requested=update_requested,
            layout_ms=layout_ms,
            emit_ms=emit_ms,
        )


def _has_applied_artwork(widget: "MediaWidget") -> bool:
    pixmap = getattr(widget, "_artwork_pixmap", None)
    if pixmap is None:
        return False
    try:
        return not pixmap.isNull()
    except Exception:
        return False


def refresh_artwork_layout(widget: "MediaWidget") -> None:
    """Refresh only the art-dependent layout after a deferred UI handoff."""

    info = getattr(widget, "_last_info", None)
    if info is None:
        return
    _build_and_apply_metadata(
        widget,
        info,
        prev_info=info,
        metadata_changed=True,
        layout_only=True,
    )


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
