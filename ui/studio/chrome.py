"""Studio window chrome painted by Settings' own owners: the forged window edge, panel frames and their casts.

* ``StudioWindowEdge`` paints ``ui.settings_window_edge.paint_forged_window_edge``: the same rounded outer border
  the Settings window paints, at the same geometry, see-through outside it. (A Quick item cannot clear the scene
  beneath it, so the shell's full-window fills are rounded inside the border: ``StudioShell.qml``.)
* ``StudioFrame`` paints one card or section: Settings' hard outside-only cast shadow
  (``ui.widgets.control_shadow.cast_shadow_path``), the fill and the border stroked as ONE continuous path
  (``ui.widgets.continuous_border.rounded_border_path``), so a translucent border never seams.

Both are ``QQuickPaintedItem``s: they paint only when a property or their size changes (a cached texture
otherwise), so they cost nothing per frame and never ask the window, or the viewport under it, for a frame.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtQuick import QQuickPaintedItem

QML_MODULE = "SRPSS.StudioChrome"
_registered = False


def _colour_property(name: str):
    """A QColor Qt property whose change repaints the item."""
    attr = "_" + name

    def getter(self) -> QColor:
        return getattr(self, attr)

    def setter(self, value) -> None:
        colour = QColor(value)
        if colour != getattr(self, attr):
            setattr(self, attr, colour)
            self.changed.emit()
            self.update()
    return getter, setter


def _real_property(name: str):
    attr = "_" + name

    def getter(self) -> float:
        return getattr(self, attr)

    def setter(self, value) -> None:
        value = float(value)
        if value != getattr(self, attr):
            setattr(self, attr, value)
            self.changed.emit()
            self.update()
    return getter, setter


def _bool_property(name: str):
    attr = "_" + name

    def getter(self) -> bool:
        return getattr(self, attr)

    def setter(self, value) -> None:
        value = bool(value)
        if value != getattr(self, attr):
            setattr(self, attr, value)
            self.changed.emit()
            self.update()
    return getter, setter


class _PaintedChrome(QQuickPaintedItem):
    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAntialiasing(True)
        self.paints = 0                                  # how often it actually painted (tests: static at rest)
        self.widthChanged.connect(self.update)
        self.heightChanged.connect(self.update)


class StudioFrame(_PaintedChrome):
    """One rounded card/section: cast shadow (outside only), fill, one-path border.

    The frame's base rectangle is the item minus the shadow offset on the right and bottom, so the item is laid
    out as the card plus its cast. ``strokeOnly`` paints only the border (drawn above content it must frame, such
    as the viewport's scene)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._radius = 10.0
        self._strokeWidth = 1.5
        self._surfaceColor = QColor(0, 0, 0, 0)
        self._surfaceTopColor = QColor(0, 0, 0, 0)
        self._strokeColor = QColor(0, 0, 0, 0)
        self._shadowColor = QColor(0, 0, 0, 0)
        self._shadowX = 0.0
        self._shadowY = 0.0
        self._strokeOnly = False

    radius = Property(float, *_real_property("radius"), notify=_PaintedChrome.changed)
    strokeWidth = Property(float, *_real_property("strokeWidth"), notify=_PaintedChrome.changed)
    shadowX = Property(float, *_real_property("shadowX"), notify=_PaintedChrome.changed)
    shadowY = Property(float, *_real_property("shadowY"), notify=_PaintedChrome.changed)
    surfaceColor = Property(QColor, *_colour_property("surfaceColor"), notify=_PaintedChrome.changed)
    surfaceTopColor = Property(QColor, *_colour_property("surfaceTopColor"), notify=_PaintedChrome.changed)
    strokeColor = Property(QColor, *_colour_property("strokeColor"), notify=_PaintedChrome.changed)
    shadowColor = Property(QColor, *_colour_property("shadowColor"), notify=_PaintedChrome.changed)
    strokeOnly = Property(bool, *_bool_property("strokeOnly"), notify=_PaintedChrome.changed)

    def base_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, max(0.0, self.width() - max(0.0, self._shadowX)),
                      max(0.0, self.height() - max(0.0, self._shadowY)))

    def border_path(self):
        """The border: one continuous path (stroked once)."""
        from ui.widgets.continuous_border import rounded_border_path
        return rounded_border_path(self.base_rect(), self._strokeWidth, self._radius)

    def paint(self, painter: QPainter) -> None:  # noqa: D401 - Qt override
        self.paints += 1
        base = self.base_rect()
        if base.width() <= 0.0 or base.height() <= 0.0:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        border = self.border_path()
        if not self._strokeOnly:
            if self._shadowColor.alpha() > 0 and (self._shadowX > 0.0 or self._shadowY > 0.0):
                from ui.widgets.control_shadow import cast_shadow_path
                painter.fillPath(cast_shadow_path(base, self._radius, QPointF(self._shadowX, self._shadowY)),
                                 self._shadowColor)
            if self._surfaceColor.alpha() > 0 or self._surfaceTopColor.alpha() > 0:
                if self._surfaceTopColor.alpha() > 0:
                    gradient = QLinearGradient(0.0, base.top(), 0.0, base.bottom())
                    gradient.setColorAt(0.0, self._surfaceTopColor)
                    gradient.setColorAt(0.35, self._surfaceColor)
                    gradient.setColorAt(1.0, self._surfaceColor)
                    painter.fillPath(border, gradient)
                else:
                    painter.fillPath(border, self._surfaceColor)
        if self._strokeColor.alpha() > 0 and self._strokeWidth > 0.0:
            from PySide6.QtGui import QPen
            pen = QPen(self._strokeColor, self._strokeWidth)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(border)


class StudioWindowEdge(_PaintedChrome):
    """The frameless Studio window's rounded edge, exactly as Settings paints its own."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._outerBorder = QColor(255, 255, 255)
        self._maximized = False

    outerBorder = Property(QColor, *_colour_property("outerBorder"), notify=_PaintedChrome.changed)
    maximized = Property(bool, *_bool_property("maximized"), notify=_PaintedChrome.changed)

    def paint(self, painter: QPainter) -> None:  # noqa: D401 - Qt override
        from ui.settings_window_edge import paint_forged_window_edge
        self.paints += 1
        window = self.window()
        dpr = float(window.effectiveDevicePixelRatio()) if window is not None else 1.0
        paint_forged_window_edge(painter, QRectF(0.0, 0.0, self.width(), self.height()), dpr,
                                 maximized=self._maximized, outer_border=self._outerBorder)


def register_chrome_types() -> None:
    """Make the chrome items importable from QML (``import SRPSS.StudioChrome``); once per process."""
    global _registered
    if _registered:
        return
    from PySide6.QtQml import qmlRegisterType
    qmlRegisterType(StudioFrame, QML_MODULE, 1, 0, "StudioFrame")
    qmlRegisterType(StudioWindowEdge, QML_MODULE, 1, 0, "StudioWindowEdge")
    _registered = True


__all__ = ["QML_MODULE", "StudioFrame", "StudioWindowEdge", "register_chrome_types"]
