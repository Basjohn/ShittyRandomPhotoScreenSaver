"""Card paint / painted-frame-shadow logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument.

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from core.logging.logger import get_logger

logger = get_logger(__name__)


def update_card_style(widget: Any) -> None:
    """Rebuild the QSS stylesheet for the card surface."""
    selector = f"#{widget.objectName()}" if widget.objectName() else "QWidget"
    if widget.uses_painted_frame_shadow():
        widget.setStyleSheet(
            f"""
            {selector} {{
                background-color: transparent;
                border: 0px solid transparent;
                border-radius: 8px;
            }}
            """
        )
    elif widget._show_background:
        bg = QColor(widget._bg_color)
        alpha = int(255 * max(0.0, min(1.0, widget._bg_opacity)))
        bg.setAlpha(alpha)
        widget.setStyleSheet(
            f"""
            {selector} {{
                background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                border: {widget._border_width}px solid rgba({widget._card_border_color.red()}, {widget._card_border_color.green()}, {widget._card_border_color.blue()}, {widget._card_border_color.alpha()});
                border-radius: 8px;
            }}
            """
        )
    else:
        widget.setStyleSheet(
            f"""
            {selector} {{
                background-color: transparent;
                border: 0px solid transparent;
                border-radius: 8px;
            }}
            """
        )


def painted_frame_shadow_card_rect(widget: Any) -> QRectF:
    """Return the card rectangle used for painted-frame-shadow rendering."""
    from widgets.base_overlay_widget import PAINTED_FRAME_SHADOW_TUNING

    tuning = PAINTED_FRAME_SHADOW_TUNING
    return QRectF(
        0.0,
        0.0,
        max(1.0, float(widget.width() - int(tuning["card_shrink_right"]))),
        max(1.0, float(widget.height() - int(tuning["card_shrink_bottom"]))),
    )


def ensure_painted_frame_shadow_pixmap(widget: Any) -> Optional[QPixmap]:
    """Build (or return cached) painted-frame-shadow pixmap."""
    from widgets.base_overlay_widget import PAINTED_FRAME_SHADOW_TUNING

    if not widget.uses_painted_frame_shadow() or widget.width() <= 0 or widget.height() <= 0:
        return None
    try:
        dpr = max(1.0, float(widget.devicePixelRatioF()))
    except Exception:
        dpr = 1.0
    bg = QColor(widget._bg_color)
    bg.setAlpha(int(255 * max(0.0, min(1.0, widget._bg_opacity))))
    tuning = PAINTED_FRAME_SHADOW_TUNING
    key = (
        widget.width(),
        widget.height(),
        round(dpr, 3),
        bg.getRgb(),
        widget._card_border_color.getRgb(),
        int(widget._border_width),
        tuple(sorted(tuning.items())),
    )
    if (
        widget._painted_frame_shadow_pixmap is not None
        and not widget._painted_frame_shadow_pixmap.isNull()
        and widget._painted_frame_shadow_cache_key == key
    ):
        return widget._painted_frame_shadow_pixmap

    pixmap = QPixmap(max(1, int(widget.width() * dpr)), max(1, int(widget.height() * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        card_rect = painted_frame_shadow_card_rect(widget).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = max(0.0, float(8 + int(tuning["radius_extra"])))
        offset_x = float(tuning["offset_x"])
        offset_y = float(tuning["offset_y"])
        steps = max(1, int(tuning["blur_steps"]))
        spread = max(0.0, float(tuning["spread"]))
        max_alpha = max(0, min(255, int(tuning["max_alpha"])))

        for layer in range(steps, 0, -1):
            frac = layer / float(steps)
            grow = spread * frac
            alpha = int(max_alpha * (1.0 - (frac * 0.86)))
            if alpha <= 0:
                continue
            shadow_rect = card_rect.translated(offset_x, offset_y).adjusted(-grow, -grow, grow, grow)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, radius + grow, radius + grow)
            painter.fillPath(shadow_path, QColor(0, 0, 0, alpha))

        frame_path = QPainterPath()
        frame_path.addRoundedRect(card_rect, radius, radius)
        painter.fillPath(frame_path, bg)
        if widget._border_width > 0 and widget._card_border_color.alpha() > 0:
            pen = QPen(widget._card_border_color, max(1, int(widget._border_width)))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(frame_path)
    finally:
        painter.end()

    widget._painted_frame_shadow_pixmap = pixmap
    widget._painted_frame_shadow_cache_key = key
    return pixmap


def paint_painted_frame_shadow(widget: Any) -> None:
    """Paint the cached shadow pixmap onto the widget surface."""
    if not widget.uses_painted_frame_shadow():
        return
    painter = QPainter(widget)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(widget.rect(), Qt.GlobalColor.transparent)
    finally:
        painter.end()
    pixmap = ensure_painted_frame_shadow_pixmap(widget)
    if pixmap is not None and not pixmap.isNull():
        painter = QPainter(widget)
        try:
            painter.drawPixmap(0, 0, pixmap)
        finally:
            painter.end()
