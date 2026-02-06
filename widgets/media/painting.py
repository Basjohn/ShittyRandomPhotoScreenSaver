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
    QPixmap,
    QPainter,
    QPainterPath,
    QFontMetrics,
    QLinearGradient,
)

from core.logging.logger import get_logger
from core.media.media_controller import MediaPlaybackState
from widgets.shadow_utils import draw_rounded_rect_with_shadow

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def load_brand_pixmap() -> Optional[QPixmap]:
    """Best-effort load of a Spotify logo from the shared images folder.

    We prefer the high-resolution primary logo asset when present so that
    the glyph remains sharp even when scaled up on high-DPI displays.
    """
    try:
        images_dir = Path(__file__).resolve().parent.parent.parent / "images"
        candidates = [
            "Spotify_Primary_Logo_RGB_Black.png",
            "spotify_logo.png",
            "SpotifyLogo.png",
            "spotify.png",
        ]
        for name in candidates:
            candidate = images_dir / name
            if candidate.exists() and candidate.is_file():
                pm = QPixmap(str(candidate))
                if not pm.isNull():
                    return pm
    except Exception:
        logger.debug("[MEDIA] Failed to load Spotify logo", exc_info=True)
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

    margins = widget.contentsMargins()
    left = margins.left() - 5
    top = margins.top() + 3

    try:
        header_font_pt = int(widget._header_font_pt) if widget._header_font_pt > 0 else widget._font_size
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        header_font_pt = widget._font_size

    font = QFont(widget._font_family, header_font_pt, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    text_w = fm.horizontalAdvance("SPOTIFY")
    text_h = fm.height()

    logo_size = max(1, int(widget._header_logo_size))
    gap = max(6, widget._header_logo_margin - logo_size)

    pad_x = 10
    pad_y = 6

    inner_w = logo_size + gap + text_w
    row_h = max(text_h, logo_size)

    extra_right_pad = 24
    width = int(inner_w + pad_x * 2 + extra_right_pad)
    height = int(row_h + pad_y * 2)

    max_width = max(0, widget.width() - margins.right() - left - 10)
    if max_width and width > max_width:
        width = max_width

    if width <= 0 or height <= 0:
        return

    rect = QRect(left, top, width, height)
    radius = min(widget._bg_corner_radius + 1, min(rect.width(), rect.height()) / 2)

    draw_rounded_rect_with_shadow(
        painter,
        rect,
        radius,
        widget._bg_border_color,
        max(1, widget._bg_border_width),
    )


def paint_header_logo(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint the Spotify logo glyph next to the SPOTIFY header text.

    This is drawn separately from the rich-text header so that we can
    control DPI scaling and alignment precisely while keeping the
    markup simple on the QLabel side.
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

    margins = widget.contentsMargins()
    x = margins.left() + 7

    try:
        header_font_pt = int(widget._header_font_pt) if widget._header_font_pt > 0 else widget._font_size
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        header_font_pt = widget._font_size

    font = QFont(widget._font_family, header_font_pt, QFont.Weight.Bold)
    fm = QFontMetrics(font)
    line_height = fm.height()
    line_centre = margins.top() + (line_height * 0.6)
    icon_half = float(widget._header_logo_size) / 2.0
    y = int(line_centre - icon_half) + 4
    if y < margins.top() + 4:
        y = margins.top() + 4

    painter.save()
    try:
        painter.drawPixmap(x, y, scaled)
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
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, prev_sym)
    elif key == "next":
        painter.setPen(inactive_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, next_sym)
    elif key == "play":
        pause_font_size = widget._font_size - 4 if centre_sym == "||" else widget._font_size - 2
        font_centre = QFont(widget._font_family, pause_font_size, QFont.Weight.Bold)
        painter.setFont(font_centre)
        painter.setPen(active_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, centre_sym)


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

        # 3D slab effect: filled darker border 4px right/4px down, with light shadow
        if widget._slab_effect_enabled:
            shadow_offset_x = 4
            shadow_offset_y = 4
            slab_rect = row_rect.adjusted(shadow_offset_x, shadow_offset_y, shadow_offset_x, shadow_offset_y)

            slab_matte_top = QColor(matte_top).darker(115)
            slab_matte_bottom = QColor(matte_bottom).darker(115)

            shadow_color = QColor(0, 0, 0, 40)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(shadow_color)
            shadow_rect = slab_rect.adjusted(-2, -2, 2, 2)
            painter.drawRoundedRect(shadow_rect, widget._controls_row_radius + 1, widget._controls_row_radius + 1)

            slab_gradient = QLinearGradient(slab_rect.topLeft(), slab_rect.bottomLeft())
            slab_gradient.setColorAt(0.0, slab_matte_top)
            slab_gradient.setColorAt(1.0, slab_matte_bottom)
            painter.setBrush(slab_gradient)
            painter.drawRoundedRect(slab_rect, widget._controls_row_radius, widget._controls_row_radius)

            slab_outline = QColor(255, 255, 255, widget._controls_row_outline_alpha).darker(110)
            painter.setPen(slab_outline)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(slab_rect, widget._controls_row_radius, widget._controls_row_radius)

        # Main gradient fill (drawn on top of shadow)
        gradient = QLinearGradient(row_rect.topLeft(), row_rect.bottomLeft())
        gradient.setColorAt(0.0, matte_top)
        gradient.setColorAt(1.0, matte_bottom)

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
        painter.setPen(outline)
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

    max_by_height = max(24, widget.height() - 60)
    size = max(48, min(widget._artwork_size, max_by_height))
    if size <= 0:
        return

    try:
        dpr = float(widget.devicePixelRatioF())
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        dpr = 1.0
    scale_dpr = max(1.0, dpr)

    frame_w = size
    frame_h = size

    try:
        src_w = float(pm.width())
        src_h = float(pm.height())
        aspect = src_w / src_h if (src_w > 0.0 and src_h > 0.0) else 1.0
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        aspect = 1.0

    if aspect > 0.0:
        if aspect >= 1.4:
            natural_w = int(size * min(aspect, 2.4))
            max_card_w = max(48, widget.width() - 80)
            frame_w = max(48, min(natural_w, max_card_w))
            frame_h = size
        elif aspect <= 0.7:
            natural_h = int(size * min(1.0 / max(aspect, 0.1), 2.4))
            max_card_h = max(48, widget.height() - 80)
            frame_h = max(48, min(natural_h, max_card_h))

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
    x = max(pad, widget.width() - pad - frame_w)
    y = pad
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

        # Album artwork
        paint_artwork(widget, painter)

        # Spotify logo
        paint_header_logo(widget, painter)

        # Transport controls row
        paint_controls_row(widget, painter)
    except Exception:
        logger.debug("[MEDIA] Failed to paint artwork pixmap", exc_info=True)
