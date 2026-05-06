"""Painting routines for the MediaWidget.

Extracted from media_widget.py (M-5 refactor) to reduce monolith size.
Contains all QPainter-based rendering: artwork, controls row, header
frame, header logo, and the top-level paint dispatcher.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import (
    QFont,
    QColor,
    QPen,
    QPixmap,
    QPainter,
    QPainterPath,
    QFontMetrics,
    QLinearGradient,
)

from core.logging.logger import get_logger
from widgets.media.artwork_layout import compute_artwork_frame_size
from core.settings.shadow_tuning import CONTROL_SHADOW_TUNING
from core.media.media_controller import MediaPlaybackState
from widgets.shadow_utils import (
    draw_pixmap_drop_shadow,
    draw_rounded_rect_with_shadow,
    draw_text_with_shadow,
    draw_text_rect_with_shadow,
    header_shadows_enabled,
    shadow_config_enabled,
    text_shadows_enabled,
)

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def _qt_font_weight(value: object, fallback: QFont.Weight) -> QFont.Weight:
    try:
        numeric = int(value)
    except Exception:
        return fallback
    if numeric >= 700:
        return QFont.Weight.Bold
    if numeric >= 600:
        return QFont.Weight.DemiBold
    if numeric >= 500:
        return QFont.Weight.Medium
    return QFont.Weight.Normal


def _ensure_controls_shadow_pixmap(widget: "MediaWidget", row_rect: QRect) -> tuple[Optional[QPixmap], int, int]:
    if not shadow_config_enabled(widget._shadow_config, "enabled", True):
        return None, 0, 0
    if row_rect.width() <= 0 or row_rect.height() <= 0:
        return None, 0, 0
    try:
        dpr = max(1.0, float(widget.devicePixelRatioF()))
    except Exception:
        dpr = 1.0

    tuning = CONTROL_SHADOW_TUNING
    offset_x = int(tuning.get("offset_x", 2))
    offset_y = int(tuning.get("offset_y", 2))
    alpha = max(0, min(255, int(tuning.get("alpha", 80))))
    spread = max(1, int(tuning.get("spread", max(5, int(widget._controls_row_radius * 0.65)))))
    passes = max(1, int(tuning.get("passes", 5)))
    radius = max(1.0, float(widget._controls_row_radius))
    shadow_w = row_rect.width() + spread * 2 + abs(offset_x)
    shadow_h = row_rect.height() + spread * 2 + abs(offset_y)
    key = (
        row_rect.width(),
        row_rect.height(),
        round(dpr, 3),
        radius,
        spread,
        passes,
        offset_x,
        offset_y,
        alpha,
    )
    cached = getattr(widget, "_controls_shadow_cache", None)
    origin_x = spread + max(0, -offset_x)
    origin_y = spread + max(0, -offset_y)
    if cached is not None and not cached.isNull() and getattr(widget, "_controls_shadow_cache_key", None) == key:
        return cached, origin_x, origin_y

    pixmap = QPixmap(max(1, int(shadow_w * dpr)), max(1, int(shadow_h * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    shadow_painter = QPainter(pixmap)
    shadow_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        base_rect = QRectF(
            origin_x + offset_x,
            origin_y + offset_y,
            row_rect.width(),
            row_rect.height(),
        )
        for layer in range(passes, 0, -1):
            frac = layer / float(passes)
            grow = spread * frac
            layer_alpha = int(alpha * (1.0 - frac * 0.78))
            if layer_alpha <= 0:
                continue
            shadow_painter.setPen(Qt.PenStyle.NoPen)
            shadow_painter.setBrush(QColor(0, 0, 0, layer_alpha))
            shadow_painter.drawRoundedRect(
                base_rect.adjusted(-grow, -grow, grow, grow),
                radius + grow,
                radius + grow,
            )
    finally:
        shadow_painter.end()

    widget._controls_shadow_cache = pixmap
    widget._controls_shadow_cache_key = key
    return pixmap, spread + max(0, -offset_x), spread + max(0, -offset_y)


def _header_layout(widget: "MediaWidget") -> dict[str, object]:
    margins = widget.contentsMargins()
    try:
        header_font_pt = int(widget._header_font_pt) if widget._header_font_pt > 0 else widget._font_size
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        header_font_pt = widget._font_size

    font = QFont(widget._font_family, header_font_pt, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    provider_name = widget.provider_display_name
    text_w = max(fm.horizontalAdvance(provider_name), fm.boundingRect(provider_name).width())
    text_w += max(12, int(round(header_font_pt * 0.45)))
    text_h = fm.height()
    logo_size = max(1, int(widget._header_logo_size))
    gap = max(6, int(widget._header_logo_margin) - logo_size)
    pad_x = 17
    pad_y = 6
    left = int(margins.left()) - 5
    top = int(margins.top()) + 3
    row_h = max(text_h, logo_size)
    width = int(logo_size + gap + text_w + pad_x * 2)
    height = int(row_h + pad_y * 2)

    shrink_r, _ = widget.painted_frame_shadow_card_shrink()
    effective_w = max(1, int(widget.width() - shrink_r))
    max_width = max(0, effective_w - left - 10)
    artwork_pm = getattr(widget, "_artwork_pixmap", None)
    artwork_size = max(0, int(getattr(widget, "_artwork_size", 0)))
    if artwork_pm is not None and not artwork_pm.isNull() and artwork_size > 0:
        _, shrink_b = widget.painted_frame_shadow_card_shrink()
        effective_h = max(1, int(widget.height() - shrink_b))
        max_art_h = max(24, effective_h - 60)
        art_target = max(48, min(artwork_size, max_art_h))
        frame_size = compute_artwork_frame_size(artwork_pm, art_target)
        art_width = max(1, int(frame_size.width()))
        artwork_left = max(20, effective_w - 20 - art_width)
        max_width = max(0, artwork_left - left - 18)
    if max_width and width > max_width:
        width = max_width

    rect = QRect(left, top, max(1, width), max(1, height))
    logo_x = rect.left() + pad_x
    logo_y = rect.top() + int(round((rect.height() - logo_size) / 2.0))
    text_x = logo_x + logo_size + gap
    baseline_y = rect.top() + int(round((rect.height() - text_h) / 2.0)) + fm.ascent()
    text_width = max(1, rect.right() - text_x - pad_x + 1)
    return {
        "rect": rect,
        "font": font,
        "metrics": fm,
        "font_pt": header_font_pt,
        "logo_x": logo_x,
        "logo_y": logo_y,
        "text_x": text_x,
        "baseline_y": baseline_y,
        "text_width": text_width,
    }


_BRAND_LOGO_CANDIDATES: dict[str, list[str]] = {
    "spotify": [
        "Spotify_Primary_Logo_RGB_Black.png",
        "spotify_logo.png",
        "SpotifyLogo.png",
        "spotify.png",
    ],
    "musicbee": [
        "icons8-musicbee-96.png",
        "MusicBee_Logo.png",
        "musicbee_logo.png",
        "musicbee.png",
    ],
}


def load_brand_pixmap(provider: str = "spotify") -> Optional[QPixmap]:
    """Best-effort load of a brand logo from the shared images folder.

    Args:
        provider: Media provider name ('spotify' or 'musicbee').

    We prefer the high-resolution primary logo asset when present so that
    the glyph remains sharp even when scaled up on high-DPI displays.
    """
    try:
        images_dir = Path(__file__).resolve().parent.parent.parent / "images"
        candidates = _BRAND_LOGO_CANDIDATES.get(provider.lower(), _BRAND_LOGO_CANDIDATES["spotify"])
        for name in candidates:
            candidate = images_dir / name
            if candidate.exists() and candidate.is_file():
                pm = QPixmap(str(candidate))
                if not pm.isNull():
                    return pm
    except Exception:
        logger.debug("[MEDIA] Failed to load %s logo", provider, exc_info=True)
    return None


def paint_header_frame(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint a rounded sub-frame around the logo + SPOTIFY header.

    The frame inherits the media widget's background and border colours
    and opacities so it feels like a lighter inner container instead of a
    separate widget. It is confined to the left text column and never
    overlaps the artwork on the right.
    """
    if not widget._show_header_frame:
        return
    if not widget._show_background:
        return
    if widget._bg_border_width <= 0 or widget._bg_border_color.alpha() <= 0:
        return

    layout = _header_layout(widget)
    rect = layout["rect"]
    if rect.width() <= 0 or rect.height() <= 0:
        return
    radius = min(widget._bg_corner_radius + 1, min(rect.width(), rect.height()) / 2)

    outer_width = max(1, widget._bg_border_width)
    inner_width = max(2, outer_width - 3)
    draw_rounded_rect_with_shadow(
        painter,
        rect,
        radius,
        widget._bg_border_color,
        inner_width,
        shadow_enabled=header_shadows_enabled(widget._shadow_config),
    )


def paint_header_logo(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint the Spotify logo glyph next to the SPOTIFY header text.

    This is drawn separately from the rich-text header so that we can
    control DPI scaling and alignment precisely while text is painted
    by the shared metadata painter.
    """
    pm = widget._brand_pixmap
    size = widget._header_logo_size
    if pm is None or pm.isNull() or size <= 0:
        return

    try:
        dpr = float(widget.devicePixelRatioF())
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        dpr = 1.0

    target_px = int(size * max(1.0, dpr))
    if target_px <= 0:
        return

    scaled = pm.scaled(
        target_px,
        target_px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    try:
        scaled.setDevicePixelRatio(max(1.0, dpr))
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

    layout = _header_layout(widget)
    x = int(layout["logo_x"])
    y = int(layout["logo_y"])

    painter.save()
    try:
        draw_pixmap_drop_shadow(
            painter,
            QRect(x, y, int(size), int(size)),
            pm,
            owner=widget,
            cache_attr="_header_logo_shadow_cache",
            shadow_config=widget._shadow_config,
        )
        painter.drawPixmap(x, y, scaled)
    finally:
        painter.restore()


def paint_metadata_text(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint provider/title/artist text with deterministic painter shadows."""
    metadata = getattr(widget, "_metadata_paint", None)
    if not isinstance(metadata, dict):
        return

    provider = str(metadata.get("provider") or widget.provider_display_name)
    title = str(metadata.get("title") or "")
    artist = str(metadata.get("artist") or "")
    if not provider and not title and not artist:
        return

    header_layout = _header_layout(widget)
    header_rect = header_layout["rect"]
    margins = widget.contentsMargins()
    shrink_r, _ = widget.painted_frame_shadow_card_shrink()
    left = int(margins.left())
    right = int(widget.width() - margins.right() - shrink_r - 8)
    max_width = max(40, right - left)

    color = QColor(widget._text_color)
    enabled = text_shadows_enabled(widget._shadow_config)

    header_font_pt = int(metadata.get("header_font") or widget._header_font_pt or widget._font_size)
    title_font_pt = int(metadata.get("title_font") or max(6, widget._font_size + 3))
    artist_font_pt = int(metadata.get("artist_font") or max(6, widget._font_size - 2))
    header_weight = int(metadata.get("header_weight") or 750)
    title_weight = int(metadata.get("title_weight") or 700)
    artist_weight = int(metadata.get("artist_weight") or 600)
    line_spacing = int(metadata.get("line_spacing") or 4)
    body_top_gap = int(metadata.get("body_top_gap") or 8)

    painter.save()
    try:
        # Header text, aligned to the separately painted brand logo and frame.
        header_font = header_layout["font"]
        painter.setFont(header_font)
        painter.setPen(color)
        header_fm = header_layout["metrics"]
        header_x = int(header_layout["text_x"])
        header_y = int(header_layout["baseline_y"])
        header_max_width = int(header_layout["text_width"])
        header_text = header_fm.elidedText(provider, Qt.TextElideMode.ElideRight, header_max_width)
        draw_text_with_shadow(
            painter,
            header_x,
            header_y,
            header_text,
            font_size=header_font_pt,
            enabled=enabled,
        )

        y = int(header_rect.bottom() + 1 + body_top_gap)
        body_flags = (
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
            | Qt.TextFlag.TextWordWrap
        )

        if title:
            title_font = QFont(
                widget._font_family,
                title_font_pt,
                _qt_font_weight(title_weight, QFont.Weight.Bold),
            )
            title_fm = QFontMetrics(title_font)
            title_bounds = title_fm.boundingRect(
                QRect(left, y, max_width, 1000),
                int(body_flags),
                title,
            )
            title_rect = QRect(left, y, max_width, max(title_fm.height(), title_bounds.height()))
            painter.setFont(title_font)
            painter.setPen(color)
            draw_text_rect_with_shadow(
                painter,
                title_rect,
                body_flags,
                title,
                font_size=title_font_pt,
                enabled=enabled,
            )
            y = title_rect.bottom() + 1 + line_spacing

        if artist:
            artist_font = QFont(
                widget._font_family,
                artist_font_pt,
                _qt_font_weight(artist_weight, QFont.Weight.DemiBold),
            )
            artist_color = QColor(color)
            artist_color.setAlpha(int(artist_color.alpha() * 0.95))
            artist_fm = QFontMetrics(artist_font)
            artist_rect = QRect(left, y, max_width, artist_fm.height() + 2)
            artist_text = artist_fm.elidedText(artist, Qt.TextElideMode.ElideRight, max_width)
            painter.setFont(artist_font)
            painter.setPen(artist_color)
            draw_text_rect_with_shadow(
                painter,
                artist_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                artist_text,
                font_size=artist_font_pt,
                enabled=enabled,
            )
    finally:
        painter.restore()


def draw_control_icon(
    widget: "MediaWidget", painter: QPainter, rect: QRect, key: str
) -> None:
    """Draw a single control icon (prev/play/next)."""
    state = MediaPlaybackState.UNKNOWN
    if widget._last_info:
        state = widget._last_info.state

    prev_sym = "\u2190"  # LEFTWARDS ARROW
    next_sym = "\u2192"  # RIGHTWARDS ARROW
    if state == MediaPlaybackState.PLAYING:
        centre_sym = "||"  # pause
    else:
        centre_sym = "\u25b6"  # play

    inactive_color = QColor(200, 200, 200, 230)
    active_color = QColor(255, 255, 255, 255)

    if key == "prev":
        painter.setPen(inactive_color)
        draw_text_rect_with_shadow(
            painter,
            rect,
            Qt.AlignmentFlag.AlignCenter,
            prev_sym,
            font_size=widget._font_size,
            enabled=False,
        )
    elif key == "next":
        painter.setPen(inactive_color)
        draw_text_rect_with_shadow(
            painter,
            rect,
            Qt.AlignmentFlag.AlignCenter,
            next_sym,
            font_size=widget._font_size,
            enabled=False,
        )
    elif key == "play":
        pause_font_size = widget._font_size - 4 if centre_sym == "||" else widget._font_size - 2
        font_centre = QFont("Segoe UI", pause_font_size, QFont.Weight.Bold)
        painter.setFont(font_centre)
        painter.setPen(active_color)
        draw_text_rect_with_shadow(
            painter,
            rect,
            Qt.AlignmentFlag.AlignCenter,
            centre_sym,
            font_size=pause_font_size,
            enabled=False,
        )


def paint_controls_row(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint transport controls aligned with the click hit regions."""
    layout = widget._compute_controls_layout()
    if layout is None:
        return

    font: QFont = layout["font"]
    row_rect: QRect = layout["row_rect"]
    button_rects: dict = layout["button_rects"]

    painter.save()
    try:
        base_color = QColor(widget._bg_color)
        matte_top = QColor(base_color)
        matte_bottom = QColor(base_color)
        matte_top.setAlpha(min(255, int(base_color.alpha() * 0.95) + 30))
        matte_bottom.setAlpha(min(255, int(base_color.alpha() * 0.85)))

        # Main gradient fill
        gradient = QLinearGradient(row_rect.topLeft(), row_rect.bottomLeft())
        gradient.setColorAt(0.0, matte_top)
        gradient.setColorAt(1.0, matte_bottom)

        shadow, origin_dx, origin_dy = _ensure_controls_shadow_pixmap(widget, row_rect)
        if shadow is not None and not shadow.isNull():
            painter.drawPixmap(row_rect.left() - origin_dx, row_rect.top() - origin_dy, shadow)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(row_rect, widget._controls_row_radius, widget._controls_row_radius)

        # Inner matte outline (2px thicker outer border)
        outline = QColor(255, 255, 255, widget._controls_row_outline_alpha)
        painter.setPen(QColor(0, 0, 0, widget._controls_row_shadow_alpha))
        painter.drawRoundedRect(
            row_rect.adjusted(2, 2, -2, -2),
            widget._controls_row_radius - 1,
            widget._controls_row_radius - 1,
        )
        outline_pen = QPen(outline, 1.75)
        painter.setPen(outline_pen)
        painter.drawRoundedRect(
            row_rect.adjusted(0, 0, 0, 0),
            widget._controls_row_radius,
            widget._controls_row_radius,
        )

        # Divider lines (relative to row_rect)
        divider_color = QColor(255, 255, 255, 55)
        painter.setPen(divider_color)
        top_divider = row_rect.top() + int(row_rect.height() * 0.15)
        bottom_divider = row_rect.bottom() - int(row_rect.height() * 0.15)
        for i in range(1, 3):
            x = row_rect.left() + int(row_rect.width() * i / 3.0)
            painter.drawLine(x, top_divider, x, bottom_divider)

        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 225))
        for key, rect in button_rects.items():
            draw_control_icon(widget, painter, rect, key)

        # Click feedback overlay
        if widget._controls_feedback:
            painter.setPen(Qt.PenStyle.NoPen)
            for key, rect in button_rects.items():
                intensity = max(0.0, min(1.0, widget._controls_feedback_progress.get(key, 0.0)))
                if intensity <= 0.0:
                    continue

                base_rect = QRectF(rect)
                scale = 1.0 + widget._controls_feedback_scale_boost * intensity
                if scale > 1.0:
                    delta_w = base_rect.width() * (scale - 1.0) * 0.5
                    delta_h = base_rect.height() * (scale - 1.0) * 0.5
                    highlight_rect = base_rect.adjusted(-delta_w, -delta_h, delta_w, delta_h)
                else:
                    highlight_rect = base_rect

                radius = max(4.0, min(highlight_rect.width(), highlight_rect.height()) * 0.3)
                glow_expand = max(2.0, min(highlight_rect.width(), highlight_rect.height()) * 0.12)

                # Soft outer glow
                glow_rect = highlight_rect.adjusted(-glow_expand, -glow_expand, glow_expand, glow_expand)
                glow_color = QColor(255, 255, 255, int(90 * intensity))
                painter.setBrush(glow_color)
                painter.drawRoundedRect(glow_rect, radius + glow_expand, radius + glow_expand)

                # Bright gradient core
                fb_gradient = QLinearGradient(
                    highlight_rect.topLeft(), highlight_rect.bottomLeft()
                )
                fb_gradient.setColorAt(0.0, QColor(255, 255, 255, int(255 * intensity)))
                fb_gradient.setColorAt(0.6, QColor(255, 255, 255, int(215 * intensity)))
                fb_gradient.setColorAt(1.0, QColor(255, 255, 255, int(170 * intensity)))
                painter.setBrush(fb_gradient)
                painter.drawRoundedRect(highlight_rect, radius, radius)
    finally:
        painter.restore()


def paint_artwork(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint album artwork with clipping, shadow, and border."""
    pm = widget._artwork_pixmap
    if pm is None or pm.isNull():
        return

    shrink_r, shrink_b = widget.painted_frame_shadow_card_shrink()
    effective_w = widget.width() - shrink_r
    effective_h = widget.height() - shrink_b
    max_by_height = max(24, effective_h - 60)
    size = max(48, min(widget._artwork_size, max_by_height))
    if size <= 0:
        return

    try:
        dpr = float(widget.devicePixelRatioF())
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        dpr = 1.0
    scale_dpr = max(1.0, dpr)

    frame_size = compute_artwork_frame_size(pm, size)
    frame_w = max(1, frame_size.width())
    frame_h = max(1, frame_size.height())

    # PERF: Cache scaled artwork to avoid expensive SmoothTransformation on every paint
    cache_key = (id(pm), frame_w, frame_h, scale_dpr)
    if widget._scaled_artwork_cache_key == cache_key and widget._scaled_artwork_cache is not None:
        scaled = widget._scaled_artwork_cache
    else:
        target_w_px = int(frame_w * scale_dpr)
        target_h_px = int(frame_h * scale_dpr)
        scaled = pm.scaled(
            target_w_px,
            target_h_px,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            scaled.setDevicePixelRatio(scale_dpr)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        widget._scaled_artwork_cache = scaled
        widget._scaled_artwork_cache_key = cache_key

    scaled_logical_w = max(1, int(round(scaled.width() / scale_dpr)))
    scaled_logical_h = max(1, int(round(scaled.height() / scale_dpr)))

    pad = 20
    x = max(pad, effective_w - pad - frame_w)
    bias = max(0.0, min(1.0, float(getattr(widget, "_artwork_vertical_bias", 0.4))))
    y = pad + int(round((size - frame_h) * bias))
    widget._last_artwork_rect = QRect(x, y, frame_w, frame_h)
    painter.save()
    try:
        if widget._artwork_opacity != 1.0:
            painter.setOpacity(max(0.0, min(1.0, float(widget._artwork_opacity))))

        border_rect = QRect(x, y, frame_w, frame_h).adjusted(-1, -1, 1, 1)

        # Multi-pass drop shadow for softer feathering
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        shadow_passes = [
            (2, 25),
            (4, 35),
            (6, 45),
            (8, 30),
        ]
        for offset, alpha in shadow_passes:
            shadow_rect = border_rect.adjusted(offset, offset, offset, offset)
            shadow_path = QPainterPath()
            if widget._rounded_artwork_border:
                radius = min(shadow_rect.width(), shadow_rect.height()) / 8.0
                shadow_path.addRoundedRect(shadow_rect, radius, radius)
            else:
                shadow_path.addRect(shadow_rect)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawPath(shadow_path)
        painter.restore()

        # Clip artwork to rounded/square frame
        path = QPainterPath()
        if widget._rounded_artwork_border:
            radius = min(border_rect.width(), border_rect.height()) / 8.0
            path.addRoundedRect(border_rect, radius, radius)
        else:
            path.addRect(border_rect)
        painter.setClipPath(path)

        # Centre the scaled artwork inside the frame
        cx = x + frame_w // 2
        cy = y + frame_h // 2
        offset_x = int(round(cx - scaled_logical_w / 2))
        offset_y = int(round(cy - scaled_logical_h / 2))

        painter.drawPixmap(offset_x, offset_y, scaled)

        # Artwork border matching the widget frame colour/opacity
        if widget._bg_border_width > 0 and widget._bg_border_color.alpha() > 0:
            pen = painter.pen()
            pen.setColor(widget._bg_border_color)
            pen.setWidth(max(1, widget._bg_border_width + 2))
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if widget._rounded_artwork_border:
                painter.drawPath(path)
            else:
                painter.drawRect(border_rect)
    finally:
        painter.restore()


def paint_contents(widget: "MediaWidget", event) -> None:
    """Internal paint implementation — dispatches to sub-painters."""
    # Call base class paintEvent for background frame
    from widgets.base_overlay_widget import BaseOverlayWidget
    BaseOverlayWidget.paintEvent(widget, event)

    try:
        painter = QPainter(widget)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception as e:
            logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

        # Optional header frame on the left side around logo + SPOTIFY.
        paint_header_frame(widget, painter)

        # Provider/title/artist text is painter-owned; QLabel rich text is not used.
        paint_metadata_text(widget, painter)

        # Album artwork
        paint_artwork(widget, painter)

        # Spotify logo
        paint_header_logo(widget, painter)

        # Transport controls row
        paint_controls_row(widget, painter)
    except Exception:
        logger.debug("[MEDIA] Failed to paint artwork pixmap", exc_info=True)
