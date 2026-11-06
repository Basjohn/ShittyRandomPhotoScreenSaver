"""The forged rounded window edge of SRPSS's frameless top-level windows (Settings and the Studio).

Fragile forged-edge geometry is renderer-owned by design (``Docs/Architecture/Settings_Theme_Architecture.md``):
the window itself stays a rectangle (its native backdrop is a rectangular HWND), and the rounded corner is forged by
painting opaque corner caps outside the rounded outline, a backing stroke and the outer border on top. The caps'
camouflage colour follows the adjacent shell surface (``window.titlebar.surface``, forced opaque); the border is
``chrome.outer_border``. Neither is independently themeable. Maximised, the edge is a plain rectangle.

Both windows call :func:`paint_forged_window_edge` with these exact constants: there is one edge, not one per window.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

SETTINGS_OUTER_CORNER_RADIUS = 6.5
SETTINGS_OUTER_BORDER_WIDTH = 4.0
SETTINGS_OUTER_BORDER_BACKING_WIDTH = 6.0


def forged_edge_colours(theme) -> tuple[QColor, QColor]:
    """(outer border, opaque forged-edge camouflage) of ``theme``."""
    border = QColor(*theme.color("chrome.outer_border").as_tuple())
    edge = theme.color("window.titlebar.surface")
    return border, QColor(edge.r, edge.g, edge.b, 255)


def paint_forged_window_edge(painter: QPainter, outer_rect: QRectF, dpr: float, *, maximized: bool,
                             outer_border: QColor, forged_edge: QColor, underlay: QColor | None = None) -> None:
    """Paint the window's edge into ``outer_rect`` (the whole window). ``underlay``: an opaque material substitute
    painted inside the rounded outline first (non-Windows Glass/Acrylic)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    border_rect = QRectF(outer_rect).adjusted(0.5, 0.5, -0.5, -0.5)
    if underlay is not None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(underlay)
        if maximized:
            painter.drawRect(outer_rect)
        else:
            painter.drawRoundedRect(border_rect, SETTINGS_OUTER_CORNER_RADIUS, SETTINGS_OUTER_CORNER_RADIUS)
    if not maximized:
        _paint_outer_corner_caps(painter, outer_rect, border_rect, dpr, forged_edge)
        backing_pen = QPen(forged_edge, SETTINGS_OUTER_BORDER_BACKING_WIDTH)
        backing_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(backing_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, SETTINGS_OUTER_CORNER_RADIUS, SETTINGS_OUTER_CORNER_RADIUS)

    border_pen = QPen(outer_border, SETTINGS_OUTER_BORDER_WIDTH)
    border_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin if maximized else Qt.PenJoinStyle.RoundJoin)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if maximized:
        painter.drawRect(border_rect)
    else:
        painter.drawRoundedRect(border_rect, SETTINGS_OUTER_CORNER_RADIUS, SETTINGS_OUTER_CORNER_RADIUS)


def _paint_outer_corner_caps(painter: QPainter, outer_rect: QRectF, border_rect: QRectF, dpr: float,
                             colour: QColor) -> None:
    """Forge rounded corner fills without altering the real (rectangular) window edge."""
    dpr = max(1.0, float(dpr))
    cover_overlap = max(
        1.75,
        ((SETTINGS_OUTER_BORDER_BACKING_WIDTH - SETTINGS_OUTER_BORDER_WIDTH) * 0.5) + (1.25 / dpr),
    )
    cover_radius = SETTINGS_OUTER_CORNER_RADIUS + (SETTINGS_OUTER_BORDER_BACKING_WIDTH * 0.25) + cover_overlap
    outer_path = QPainterPath()
    outer_path.addRect(outer_rect)
    rounded_path = QPainterPath()
    rounded_path.addRoundedRect(
        border_rect.adjusted(-cover_overlap, -cover_overlap, cover_overlap, cover_overlap),
        cover_radius,
        cover_radius,
    )
    cover_path = outer_path.subtracted(rounded_path)

    painter.save()
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(colour)
    painter.drawPath(cover_path)
    painter.restore()


__all__ = [
    "SETTINGS_OUTER_BORDER_BACKING_WIDTH",
    "SETTINGS_OUTER_BORDER_WIDTH",
    "SETTINGS_OUTER_CORNER_RADIUS",
    "forged_edge_colours",
    "paint_forged_window_edge",
]
