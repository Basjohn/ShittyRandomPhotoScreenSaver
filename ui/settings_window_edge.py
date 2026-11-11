"""The rounded window edge of SRPSS's frameless top-level windows (Settings and the Studio).

The edge geometry is renderer-owned by design (``Docs/Architecture/Settings_Theme_Architecture.md``). The native
window stays a rectangle (a rectangular HWND whose AccentPolicy material covers the whole rectangle); the rounded
silhouette is the rounded outer border itself (``chrome.outer_border``). Outside that border the window is left
see-through: every corner pixel beyond the border's outer edge is cleared to ``CORNER_OUTSIDE_ALPHA`` (1/255), so
the corner shows the desktop through the window's material and never a painted colour. Maximised, the edge is a
plain rectangle and nothing is cleared.

Why 1/255 and not 0: Settings is a layered window (per-pixel alpha), and Windows passes the mouse through a layered
window's alpha-0 pixels. One level of alpha is invisible but keeps every corner pixel the window's own for input, so
hit-testing, drag and resize are exactly what they were when the corners were painted opaque.

Until 11 Nov 2026 the corners were *forged*: opaque caps and a 6 px backing stroke in the title-bar colour (forced
opaque) camouflaged the rectangle outside a 4 px border. The border's outer arc already reaches almost to the
window corner, so the caps left a small wedge of flat camouflage colour at each corner (a near-white speck on
light themes) and the backing showed as a 1 px line just inside the border. Both are gone (measurements in the
architecture doc, "Native corner measurements").

Both windows call :func:`paint_forged_window_edge` with these exact constants: there is one edge, not one per window.
A painter can only clear what is beneath it in its own surface: Settings' overlay paints into the dialog's backing
store, so it clears the shell surfaces beneath it; the Studio's edge is a Quick item with its own texture, so the
Studio's full-window fills (window surface, title bar) are themselves rounded to stay inside the border.

The edge is painted over the window's content, never beneath it. The Studio's edge item sits at the top of its
scene; Settings paints it from :class:`ForgedWindowEdgeOverlay`, a mouse-transparent child kept above every other
child. (Settings painted it in its own ``paintEvent``, beneath its children: the shell surfaces filling the window,
``window.dialog_glass`` and the title bar, then covered the border and the corners. Dark themes author those
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
# Alpha left in every pixel outside the rounded border: invisible, but non-zero so a layered window still owns it
# for hit-testing.
CORNER_OUTSIDE_ALPHA = 1

BORDER_GROWTH_MODES = ("centre", "outward")


def forged_edge_geometry(dpr: float, extra_border_device_px: float = 0.0,
                         border_growth: str = "centre") -> tuple[float, float, float]:
    """``(path inset, path radius, border width)`` in logical px.

    ``extra_border_device_px`` widens the border by that many DEVICE pixels (divided by ``dpr``); ``centre`` grows
    the stroke on both sides of the unchanged path, ``outward`` moves the path out by half the extra (concentric,
    the inner edge stays put). Both are measurement parameters of ``tools/settings_native_corners.py`` only: no
    product caller passes them (thicker borders were measured and rejected, Settings_Theme_Architecture.md)."""
    if border_growth not in BORDER_GROWTH_MODES:
        raise ValueError(f"unknown border growth {border_growth!r}")
    extra = max(0.0, float(extra_border_device_px)) / max(1.0, float(dpr))
    shift = extra * 0.5 if border_growth == "outward" else 0.0
    return 0.5 - shift, SETTINGS_OUTER_CORNER_RADIUS + shift, SETTINGS_OUTER_BORDER_WIDTH + extra


def border_outer_path(outer_rect: QRectF, dpr: float = 1.0, extra_border_device_px: float = 0.0,
                      border_growth: str = "centre") -> QPainterPath:
    """The border stroke's outer edge: the window's rounded silhouette (it extends past the straight window edges,
    which clip it, so only its corner arcs matter)."""
    inset, radius, border_width = forged_edge_geometry(dpr, extra_border_device_px, border_growth)
    half = border_width * 0.5
    path = QPainterPath()
    path.addRoundedRect(QRectF(outer_rect).adjusted(inset - half, inset - half, half - inset, half - inset),
                        radius + half, radius + half)
    return path


def paint_forged_window_edge(painter: QPainter, outer_rect: QRectF, dpr: float, *, maximized: bool,
                             outer_border: QColor, underlay: QColor | None = None,
                             extra_border_device_px: float = 0.0, border_growth: str = "centre") -> None:
    """Paint the window's edge into ``outer_rect`` (the whole window). ``underlay``: an opaque material substitute
    painted inside the rounded outline first (non-Windows Glass/Acrylic). ``extra_border_device_px`` /
    ``border_growth``: measurement-only (``forged_edge_geometry``); product callers leave the defaults."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    inset, radius, border_width = forged_edge_geometry(dpr, extra_border_device_px, border_growth)
    border_rect = QRectF(outer_rect).adjusted(inset, inset, -inset, -inset)
    if underlay is not None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(underlay)
        if maximized:
            painter.drawRect(outer_rect)
        else:
            painter.drawRoundedRect(border_rect, radius, radius)
    if not maximized:
        _clear_outside_border(painter, outer_rect,
                              border_outer_path(outer_rect, dpr, extra_border_device_px, border_growth))

    border_pen = QPen(outer_border, border_width)
    border_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin if maximized else Qt.PenJoinStyle.RoundJoin)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if maximized:
        painter.drawRect(border_rect)
    else:
        painter.drawRoundedRect(border_rect, radius, radius)


def _clear_outside_border(painter: QPainter, outer_rect: QRectF, silhouette: QPainterPath) -> None:
    """Leave everything outside the rounded border see-through (alpha ``CORNER_OUTSIDE_ALPHA``), whatever the
    window's content painted there; the border then strokes its own antialiased outer arc over the boundary."""
    outside = QPainterPath()
    outside.addRect(outer_rect)
    outside = outside.subtracted(silhouette)
    painter.save()
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, CORNER_OUTSIDE_ALPHA))
    painter.drawPath(outside)
    painter.restore()


class ForgedWindowEdgeOverlay(QWidget):
    """Paints the rounded edge of its parent window over all of the window's other children.

    ``edge_state`` returns ``(maximized, outer_border)`` at paint time, so a theme change needs only a repaint. The
    overlay takes no input (``WA_TransparentForMouseEvents``) and fills nothing else; the parent keeps painting any
    opaque material underlay beneath its content. The parent calls :meth:`track_parent` from its ``resizeEvent``
    (geometry, and staying on top of children created later).
    """

    def __init__(self, parent: QWidget, edge_state: Callable[[], tuple[bool, QColor]]) -> None:
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
        maximized, outer_border = self._edge_state()
        painter = QPainter(self)
        try:
            paint_forged_window_edge(painter, QRectF(self.rect()), float(self.devicePixelRatioF()),
                                     maximized=maximized, outer_border=outer_border)
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
    "CORNER_OUTSIDE_ALPHA",
    "ForgedWindowEdgeOverlay",
    "SETTINGS_OUTER_BORDER_WIDTH",
    "SETTINGS_OUTER_CORNER_RADIUS",
    "border_outer_path",
    "forged_edge_geometry",
    "paint_forged_window_edge",
    "paint_material_underlay",
]
