"""Temporary QWidget painting retained only for Phase-F4 Media controls."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen

from core.logging.logger import get_logger
from core.media.media_controller import MediaPlaybackState
from widgets.shadow_utils import draw_text_rect_with_shadow

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def draw_control_icon(
    widget: "MediaWidget", painter: QPainter, rect: QRect, key: str
) -> None:
    """Draw one temporary QWidget transport-control glyph."""

    state = MediaPlaybackState.UNKNOWN
    if widget._last_info:
        state = widget._last_info.state

    prev_sym = "\u2190"
    next_sym = "\u2192"
    centre_sym = "||" if state == MediaPlaybackState.PLAYING else "\u25b6"
    inactive_color = QColor(200, 200, 200, 230)
    active_color = QColor(255, 255, 255, 255)

    if key in {"prev", "next"}:
        painter.setPen(inactive_color)
        draw_text_rect_with_shadow(
            painter,
            rect,
            Qt.AlignmentFlag.AlignCenter,
            prev_sym if key == "prev" else next_sym,
            font_size=widget._font_size,
            enabled=False,
        )
    elif key == "play":
        pause_font_size = (
            widget._font_size - 4 if centre_sym == "||" else widget._font_size - 2
        )
        painter.setFont(QFont("Segoe UI", pause_font_size, QFont.Weight.Bold))
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
    """Paint transport controls aligned with their surviving hit regions."""

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

        gradient = QLinearGradient(row_rect.topLeft(), row_rect.bottomLeft())
        gradient.setColorAt(0.0, matte_top)
        gradient.setColorAt(1.0, matte_bottom)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(
            row_rect, widget._controls_row_radius, widget._controls_row_radius
        )

        outline = QColor(255, 255, 255, widget._controls_row_outline_alpha)
        painter.setPen(QColor(0, 0, 0, widget._controls_row_shadow_alpha))
        painter.drawRoundedRect(
            row_rect.adjusted(2, 2, -2, -2),
            widget._controls_row_radius - 1,
            widget._controls_row_radius - 1,
        )
        painter.setPen(QPen(outline, 1.75))
        painter.drawRoundedRect(
            row_rect,
            widget._controls_row_radius,
            widget._controls_row_radius,
        )

        painter.setPen(QColor(255, 255, 255, 55))
        top_divider = row_rect.top() + int(row_rect.height() * 0.15)
        bottom_divider = row_rect.bottom() - int(row_rect.height() * 0.15)
        for index in range(1, 3):
            x = row_rect.left() + int(row_rect.width() * index / 3.0)
            painter.drawLine(x, top_divider, x, bottom_divider)

        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 225))
        for key, rect in button_rects.items():
            draw_control_icon(widget, painter, rect, key)

        if widget._controls_feedback:
            painter.setPen(Qt.PenStyle.NoPen)
            for key, rect in button_rects.items():
                intensity = max(
                    0.0,
                    min(1.0, widget._controls_feedback_progress.get(key, 0.0)),
                )
                if intensity <= 0.0:
                    continue
                base_rect = QRectF(rect)
                scale = 1.0 + widget._controls_feedback_scale_boost * intensity
                if scale > 1.0:
                    delta_w = base_rect.width() * (scale - 1.0) * 0.5
                    delta_h = base_rect.height() * (scale - 1.0) * 0.5
                    highlight_rect = base_rect.adjusted(
                        -delta_w, -delta_h, delta_w, delta_h
                    )
                else:
                    highlight_rect = base_rect
                radius = max(
                    4.0,
                    min(highlight_rect.width(), highlight_rect.height()) * 0.3,
                )
                glow_expand = max(
                    2.0,
                    min(highlight_rect.width(), highlight_rect.height()) * 0.12,
                )
                glow_rect = highlight_rect.adjusted(
                    -glow_expand, -glow_expand, glow_expand, glow_expand
                )
                painter.setBrush(QColor(255, 255, 255, int(90 * intensity)))
                painter.drawRoundedRect(
                    glow_rect,
                    radius + glow_expand,
                    radius + glow_expand,
                )
                feedback_gradient = QLinearGradient(
                    highlight_rect.topLeft(), highlight_rect.bottomLeft()
                )
                feedback_gradient.setColorAt(
                    0.0, QColor(255, 255, 255, int(255 * intensity))
                )
                feedback_gradient.setColorAt(
                    0.6, QColor(255, 255, 255, int(215 * intensity))
                )
                feedback_gradient.setColorAt(
                    1.0, QColor(255, 255, 255, int(170 * intensity))
                )
                painter.setBrush(feedback_gradient)
                painter.drawRoundedRect(highlight_rect, radius, radius)
    finally:
        painter.restore()


def paint_playback_progress(widget: "MediaWidget", painter: QPainter) -> None:
    """Paint the temporary F4 scalar playback-progress pill."""

    if not bool(getattr(widget, "_playback_progress_visible", False)):
        return
    layout = widget._compute_controls_layout()
    if not layout:
        return
    rect = layout.get("progress_rect")
    if not isinstance(rect, QRect) or rect.isEmpty():
        return

    fill_width = max(
        0,
        min(
            rect.width(),
            int(getattr(widget, "_playback_progress_fill_width", 0) or 0),
        ),
    )
    track_rect = QRectF(rect)
    track_radius = max(1.5, track_rect.height() * 0.5)
    fill_color = QColor(
        getattr(
            widget,
            "_playback_progress_fill_color",
            QColor(255, 255, 255, 230),
        )
    )

    painter.save()
    try:
        painter.setPen(Qt.PenStyle.NoPen)
        if bool(getattr(widget, "_playback_progress_shadow_enabled", False)):
            painter.setBrush(QColor(0, 0, 0, 90))
            painter.drawRoundedRect(
                track_rect.translated(0.0, 2.0),
                track_radius,
                track_radius,
            )

        track_color = QColor(fill_color)
        track_color.setAlpha(max(32, min(90, int(fill_color.alpha() * 0.28))))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)
        if fill_width <= 0:
            return

        fill_rect = QRectF(
            track_rect.left(),
            track_rect.top(),
            float(fill_width),
            track_rect.height(),
        )
        fill_radius = max(0.5, min(fill_rect.width(), fill_rect.height()) * 0.5)
        if bool(getattr(widget, "_playback_progress_glow_enabled", False)):
            glow_base = QColor(
                getattr(
                    widget,
                    "_playback_progress_glow_color",
                    QColor(255, 255, 255, 180),
                )
            )
            for expansion, alpha_scale in (
                (4.0, 0.18),
                (2.5, 0.28),
                (1.25, 0.42),
            ):
                glow_color = QColor(glow_base)
                glow_color.setAlpha(max(1, int(glow_base.alpha() * alpha_scale)))
                glow_rect = fill_rect.adjusted(
                    -expansion, -expansion, expansion, expansion
                )
                painter.setBrush(glow_color)
                painter.drawRoundedRect(
                    glow_rect,
                    fill_radius + expansion,
                    fill_radius + expansion,
                )
        painter.setBrush(fill_color)
        painter.drawRoundedRect(fill_rect, fill_radius, fill_radius)
    finally:
        painter.restore()


def _is_feedback_only_repaint(widget: "MediaWidget", event) -> bool:
    if not getattr(widget, "_controls_feedback", None):
        return False
    if not getattr(widget, "_show_controls", False):
        return False
    try:
        from widgets.media.feedback import _feedback_dirty_rect

        dirty = _feedback_dirty_rect(widget)
        return bool(
            dirty is not None and not dirty.isNull() and dirty.contains(event.rect())
        )
    except Exception:
        return False


def paint_contents(widget: "MediaWidget", event) -> None:
    """Paint only the temporary F4 controls/progress compatibility surface."""

    from widgets.base_overlay_widget import BaseOverlayWidget

    BaseOverlayWidget.paintEvent(widget, event)
    feedback_only = _is_feedback_only_repaint(widget, event)
    try:
        painter = QPainter(widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if not feedback_only:
            paint_playback_progress(widget, painter)
        paint_controls_row(widget, painter)
    except Exception:
        logger.debug("[MEDIA] Failed to paint F4 compatibility controls", exc_info=True)
