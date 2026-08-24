"""Card paint / painted-frame-shadow logic for SpotifyVisualizerWidget.

Extracted to reduce the main widget below the 2000-line threshold.
All functions take the widget instance as the first argument.

Phase 3 of the Visualizer Architecture Split.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QRectF, QSize, Qt
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


def painted_frame_shadow_card_rect(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
) -> QRectF:
    """Return the card rectangle used for the compositor card visual.

    ``logical_size`` overrides the live widget geometry. The compositor passes
    the authoritative published presentation size so a momentarily stale live
    QWidget rect cannot give the card a different size from the bars. The retired
    painted-card drop shadow reserved a right/bottom shrink margin; with that
    shadow removed (F0.5 audit correction) the card uses the full rect.
    """
    width = widget.width() if logical_size is None else logical_size.width()
    height = widget.height() if logical_size is None else logical_size.height()
    return QRectF(
        0.0,
        0.0,
        max(1.0, float(width)),
        max(1.0, float(height)),
    )


def painted_frame_shadow_cache_key(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
    dpr: Optional[float] = None,
) -> tuple:
    """Canonical identity of the authored card pixels.

    This is the ONE definition of "these card pixels changed". Both the QPixmap
    rebuild and the compositor GL texture re-upload derive from it, so the two
    can never disagree - a second hand-maintained revision would eventually let
    the pixmap invalidate correctly while the GL texture stayed stale.

    Cheap enough to call per frame; only a changed key does real work.
    """
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


def ensure_painted_frame_shadow_pixmap(
    widget: Any,
    *,
    logical_size: Optional[QSize] = None,
    dpr: Optional[float] = None,
) -> Optional[QPixmap]:
    """Build (or return cached) the compositor card-visual pixmap.

    ``logical_size`` and ``dpr`` let the compositor render the authored card
    visual **for the target dimensions** rather than scaling a stale pixmap
    afterwards, which would change border and radius. Both participate in the
    cache key, so a geometry or DPR change rebuilds rather than reusing a
    mismatched card.

    The generic painted-card *drop shadow* (the old shadowtuning.json blur
    profile) was removed in the F0.5 audit correction; this now paints only the
    card background and border, which the compositor uploads as the card texture.
    """
    if not widget.uses_painted_frame_shadow():
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
    key = painted_frame_shadow_cache_key(
        widget, logical_size=QSize(width, height), dpr=dpr
    )
    if (
        widget._painted_frame_shadow_pixmap is not None
        and not widget._painted_frame_shadow_pixmap.isNull()
        and widget._painted_frame_shadow_cache_key == key
    ):
        return widget._painted_frame_shadow_pixmap

    pixmap = QPixmap(max(1, int(width * dpr)), max(1, int(height * dpr)))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        card_rect = painted_frame_shadow_card_rect(
            widget, logical_size=QSize(width, height)
        ).adjusted(1.0, 1.0, -1.0, -1.0)
        radius = 8.0

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
