"""The forged rounded window edge of SRPSS's frameless top-level windows (Settings and the Studio).

Fragile forged-edge geometry is renderer-owned by design (``Docs/Architecture/Settings_Theme_Architecture.md``):
the window itself stays a rectangle (its native backdrop is a rectangular HWND), and the rounded corner is forged by
painting opaque corner caps outside the rounded outline, a backing stroke and the outer border on top. The caps'
camouflage colour follows the adjacent shell surface (``window.titlebar.surface``, forced opaque); the border is
``chrome.outer_border``. Neither is independently themeable. Maximised, the edge is a plain rectangle.

Both windows call :func:`paint_forged_window_edge` with these exact constants: there is one edge, not one per window.

The edge is painted over the window's content, never beneath it. The Studio's edge item sits at the top of its
scene; Settings paints it from :class:`ForgedWindowEdgeOverlay`, a mouse-transparent child kept above every other
child. (Settings painted it in its own ``paintEvent``, beneath its children: the shell surfaces filling the window,
``window.dialog_glass`` and the title bar, then covered the border and the corner caps. Dark themes author those
surfaces nearly clear, so the edge showed through; light themes author them nearly opaque and pale, which washed
the border out to the shell colour and left square pale corners.)
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

SETTINGS_OUTER_CORNER_RADIUS = 6.5
SETTINGS_OUTER_BORDER_WIDTH = 4.0
SETTINGS_OUTER_BORDER_BACKING_WIDTH = 6.0


def forged_edge_colours(theme) -> tuple[QColor, QColor]:
    """(outer border, opaque forged-edge camouflage) of ``theme``."""
    border = QColor(*theme.color("chrome.outer_border").as_tuple())
    edge = theme.color("window.titlebar.surface")
    return border, QColor(edge.r, edge.g, edge.b, 255)


BORDER_GROWTH_MODES = ("centre", "outward")


def forged_edge_geometry(dpr: float, extra_border_device_px: float = 0.0,
                         border_growth: str = "centre") -> tuple[float, float, float, float]:
    """``(path inset, path radius, border width, backing width)`` in logical px.

    ``extra_border_device_px`` widens the border and its backing by that many DEVICE pixels (divided by ``dpr``);
    ``centre`` grows the stroke on both sides of the unchanged path, ``outward`` moves the path out by half the
    extra (concentric, the inner edge stays put). Both are measurement parameters of
    ``tools/settings_native_corners.py`` only: no product caller passes them (Settings_Theme_Architecture.md,
    "Native corner measurements")."""
    if border_growth not in BORDER_GROWTH_MODES:
        raise ValueError(f"unknown border growth {border_growth!r}")
    extra = max(0.0, float(extra_border_device_px)) / max(1.0, float(dpr))
    shift = extra * 0.5 if border_growth == "outward" else 0.0
    return (0.5 - shift, SETTINGS_OUTER_CORNER_RADIUS + shift, SETTINGS_OUTER_BORDER_WIDTH + extra,
            SETTINGS_OUTER_BORDER_BACKING_WIDTH + extra)


def paint_forged_window_edge(painter: QPainter, outer_rect: QRectF, dpr: float, *, maximized: bool,
                             outer_border: QColor, forged_edge: QColor, underlay: QColor | None = None,
                             extra_border_device_px: float = 0.0, border_growth: str = "centre") -> None:
    """Paint the window's edge into ``outer_rect`` (the whole window). ``underlay``: an opaque material substitute
    painted inside the rounded outline first (non-Windows Glass/Acrylic). ``extra_border_device_px`` /
    ``border_growth``: measurement-only (``forged_edge_geometry``); product callers leave the defaults."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    inset, radius, border_width, backing_width = forged_edge_geometry(dpr, extra_border_device_px, border_growth)
    border_rect = QRectF(outer_rect).adjusted(inset, inset, -inset, -inset)
    if underlay is not None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(underlay)
        if maximized:
            painter.drawRect(outer_rect)
        else:
            painter.drawRoundedRect(border_rect, radius, radius)
    if not maximized:
        _paint_outer_corner_caps(painter, outer_rect, border_rect, dpr, forged_edge, radius)
        backing_pen = QPen(forged_edge, backing_width)
        backing_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(backing_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, radius, radius)

    border_pen = QPen(outer_border, border_width)
    border_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin if maximized else Qt.PenJoinStyle.RoundJoin)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if maximized:
        painter.drawRect(border_rect)
    else:
        painter.drawRoundedRect(border_rect, radius, radius)


def _paint_outer_corner_caps(painter: QPainter, outer_rect: QRectF, border_rect: QRectF, dpr: float,
                             colour: QColor, radius: float = SETTINGS_OUTER_CORNER_RADIUS) -> None:
    """Forge rounded corner fills without altering the real (rectangular) window edge."""
    dpr = max(1.0, float(dpr))
    cover_overlap = max(
        1.75,
        ((SETTINGS_OUTER_BORDER_BACKING_WIDTH - SETTINGS_OUTER_BORDER_WIDTH) * 0.5) + (1.25 / dpr),
    )
    cover_radius = radius + (SETTINGS_OUTER_BORDER_BACKING_WIDTH * 0.25) + cover_overlap
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


class ForgedWindowEdgeOverlay(QWidget):
    """Paints the forged edge of its parent window over all of the window's other children.

    ``edge_state`` returns ``(maximized, outer_border, forged_edge)`` at paint time, so a theme change needs only a
    repaint. The overlay takes no input (``WA_TransparentForMouseEvents``) and fills nothing else; the parent keeps
    painting any opaque material underlay beneath its content. The parent calls :meth:`track_parent` from its
    ``resizeEvent`` (geometry, and staying on top of children created later).
    """

    def __init__(self, parent: QWidget, edge_state: Callable[[], tuple[bool, QColor, QColor]]) -> None:
        super().__init__(parent)
        self.setObjectName("forgedWindowEdge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._edge_state = edge_state
        self.track_parent()

    def track_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.raise_()

    def paintEvent(self, event) -> None:  # noqa: D401 - Qt override
        del event
        maximized, outer_border, forged_edge = self._edge_state()
        painter = QPainter(self)
        try:
            paint_forged_window_edge(painter, QRectF(self.rect()), float(self.devicePixelRatioF()),
                                     maximized=maximized, outer_border=outer_border, forged_edge=forged_edge)
        finally:
            painter.end()


def paint_material_underlay(painter: QPainter, outer_rect: QRectF, *, maximized: bool, underlay: QColor) -> None:
    """Paint only the opaque material substitute inside the rounded outline (beneath the window's content)."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(underlay)
    if maximized:
        painter.drawRect(outer_rect)
    else:
        border_rect = QRectF(outer_rect).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(border_rect, SETTINGS_OUTER_CORNER_RADIUS, SETTINGS_OUTER_CORNER_RADIUS)


__all__ = [
    "BORDER_GROWTH_MODES",
    "ForgedWindowEdgeOverlay",
    "SETTINGS_OUTER_BORDER_BACKING_WIDTH",
    "SETTINGS_OUTER_BORDER_WIDTH",
    "SETTINGS_OUTER_CORNER_RADIUS",
    "forged_edge_colours",
    "forged_edge_geometry",
    "paint_forged_window_edge",
    "paint_material_underlay",
]
