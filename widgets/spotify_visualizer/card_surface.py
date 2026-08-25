"""Spotify Visualizer compositor card-surface painting and caching.

The retained QWidget owns card geometry and style.  The compositor requests
these exact authored background/border pixels for its GL texture.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


def update_card_surface_style(widget: Any) -> None:
    """Keep QWidget styling transparent while compositor card pixels are active."""
    selector = f"#{widget.objectName()}" if widget.objectName() else "QWidget"
    if widget.uses_compositor_card_surface():
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


def compositor_card_surface_rect(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
) -> QRectF:
    """Return the full logical rect used for the compositor card texture."""
    width = widget.width() if logical_size is None else logical_size.width()
    height = widget.height() if logical_size is None else logical_size.height()
    return QRectF(0.0, 0.0, max(1.0, float(width)), max(1.0, float(height)))


def compositor_card_surface_cache_key(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
    dpr: Optional[float] = None,
) -> tuple:
    """Return the canonical identity of the authored card pixels."""
    width = widget.width() if logical_size is None else int(logical_size.width())
    height = widget.height() if logical_size is None else int(logical_size.height())
    if dpr is None:
        try:
            dpr = max(1.0, float(widget.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
    dpr = max(1.0, float(dpr))

    bg = QColor(widget._bg_color)
    bg.setAlpha(int(255 * max(0.0, min(1.0, widget._bg_opacity))))
    return (
        width,
        height,
        round(dpr, 3),
        bg.getRgb(),
        widget._card_border_color.getRgb(),
        int(widget._border_width),
    )


def ensure_compositor_card_surface_pixmap(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
    dpr: Optional[float] = None,
) -> Optional[QPixmap]:
    """Build or return the cached card background/border texture source."""
    if not widget.uses_compositor_card_surface():
        return None
    width = widget.width() if logical_size is None else int(logical_size.width())
    height = widget.height() if logical_size is None else int(logical_size.height())
    if width <= 0 or height <= 0:
        return None
    if dpr is None:
        try:
            dpr = max(1.0, float(widget.devicePixelRatioF()))
        except Exception:
            dpr = 1.0
    dpr = max(1.0, float(dpr))
    bg = QColor(widget._bg_color)
    bg.setAlpha(int(255 * max(0.0, min(1.0, widget._bg_opacity))))
    key = compositor_card_surface_cache_key(
        widget, logical_size=QSize(width, height), dpr=dpr
    )
    if (
        widget._compositor_card_surface_pixmap is not None
        and not widget._compositor_card_surface_pixmap.isNull()
        and widget._compositor_card_surface_cache_key == key
    ):
        return widget._compositor_card_surface_pixmap

    pixmap = QPixmap(max(1, int(width * dpr)), max(1, int(height * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        card_rect = compositor_card_surface_rect(
            widget, logical_size=QSize(width, height)
        ).adjusted(1.0, 1.0, -1.0, -1.0)
        frame_path = QPainterPath()
        frame_path.addRoundedRect(card_rect, 8.0, 8.0)
        painter.fillPath(frame_path, bg)
        if widget._border_width > 0 and widget._card_border_color.alpha() > 0:
            pen = QPen(widget._card_border_color, max(1, int(widget._border_width)))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(frame_path)
    finally:
        painter.end()

    widget._compositor_card_surface_pixmap = pixmap
    widget._compositor_card_surface_cache_key = key
    return pixmap


def paint_compositor_card_surface(widget: Any) -> None:
    """Paint the cached card surface when the QWidget temporarily owns pixels."""
    if not widget.uses_compositor_card_surface():
        return
    painter = QPainter(widget)
    try:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(widget.rect(), Qt.GlobalColor.transparent)
    finally:
        painter.end()
    pixmap = ensure_compositor_card_surface_pixmap(widget)
    if pixmap is not None and not pixmap.isNull():
        painter = QPainter(widget)
        try:
            painter.drawPixmap(0, 0, pixmap)
        finally:
            painter.end()
