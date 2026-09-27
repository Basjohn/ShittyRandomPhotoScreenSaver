"""Seam-free rounded borders for Settings controls.

Qt style sheets draw a rounded border as separate edge and corner segments.
With the translucent border colours most Settings themes use, the overlapping
antialiased ends composite twice and leave bright or dark seams at every join.
Controls here keep an equally wide *transparent* stylesheet border (so padding,
size hints and fills are unchanged) and stroke the border themselves as one
continuous ``QPainterPath``.  See also ``ui/widgets/outlined_button.py``.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QListWidget, QStackedWidget, QToolButton, QWidget

from ui.settings_theme_runtime import get_active_settings_theme


def theme_color(token: str) -> QColor:
    return QColor(*get_active_settings_theme().color(token).as_tuple())


def stroke_rounded_border(widget: QWidget, color: QColor, width: float, radius: float,
                          painter: QPainter | None = None) -> None:
    """Stroke ``widget.rect()``'s rounded outline as one path, fully inside the widget."""
    inset = width / 2.0
    rect = QRectF(widget.rect()).adjusted(inset, inset, -inset, -inset)
    radius = max(0.0, min(radius - inset, rect.height() / 2.0, rect.width() / 2.0))
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    own = painter is None
    if own:
        painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    if own:
        painter.end()


class BucketToggle(QToolButton):
    """The shared collapsible-bucket header with a painted, seam-free border.

    Geometry, fill and text stay in the theme QSS (``QToolButton[autoRaise]``),
    whose border is transparent; the state colours are the same bucket tokens.
    """

    BORDER_WIDTH = 1.5

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def _radius(self) -> float:
        return 4.0 if self.property("bucketSize") == "large" else 3.0

    def _border_token(self) -> str:
        if self.isChecked():
            return "bucket.open.border"
        return "bucket.closed.hover_border" if self.underMouse() else "bucket.closed.border"

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        stroke_rounded_border(self, theme_color(self._border_token()), self.BORDER_WIDTH, self._radius())


class OutlinedListWidget(QListWidget):
    """A Settings list whose rounded frame is painted as one continuous path."""

    BORDER_WIDTH = 1.5
    RADIUS = 8.0

    def event(self, event) -> bool:  # type: ignore[override]
        # QAbstractScrollArea paints its own frame from event(), not paintEvent()
        # (paintEvent is the viewport's); stroke after the stylesheet frame pass.
        handled = super().event(event)
        if event.type() == QEvent.Type.Paint:
            stroke_rounded_border(self, theme_color("control.list.border"), self.BORDER_WIDTH, self.RADIUS)
        return handled


CONTENT_BORDER_WIDTH = 1.75
CONTENT_RADIUS = 8.0


def paint_content_frame(widget: QWidget, *, veil: bool = False) -> None:
    """The Settings content area's border, and optionally a readability veil.

    Themes paint the content surface fully transparent over Glass/Acrylic, so a
    bright desktop behind the window can wash text out.  The veil is 20% black
    behind light text or 20% white behind dark text, clipped inside the border.
    """
    painter = QPainter(widget)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if veil:
        text = theme_color("panel.group.text")
        light_text = text.lightnessF() >= 0.5
        inset = CONTENT_BORDER_WIDTH
        inner = QRectF(widget.rect()).adjusted(inset, inset, -inset, -inset)
        radius = max(0.0, CONTENT_RADIUS - inset)
        path = QPainterPath()
        path.addRoundedRect(inner, radius, radius)
        painter.fillPath(path, QColor(0, 0, 0, 51) if light_text else QColor(255, 255, 255, 51))
    stroke_rounded_border(widget, theme_color("panel.border"), CONTENT_BORDER_WIDTH, CONTENT_RADIUS, painter)
    painter.end()


class OutlinedStackedWidget(QStackedWidget):
    """The Settings content area (``#contentArea``) with a seam-free border."""

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        paint_content_frame(self)


class PopupSurface(QWidget):
    """The shared popup body: Settings panel semantics, seam-free.

    Fill is the theme's ``popup.container.surface`` (popups float over the
    desktop, so they keep an opaque-enough body) and the outline is the same
    ``panel.border`` stroke the Settings content area paints.
    """

    RADIUS = 10.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = CONTENT_BORDER_WIDTH / 2.0
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        path = QPainterPath()
        path.addRoundedRect(rect, self.RADIUS - inset, self.RADIUS - inset)
        painter.fillPath(path, theme_color("popup.container.surface"))
        stroke_rounded_border(self, theme_color("panel.border"), CONTENT_BORDER_WIDTH, self.RADIUS, painter)
        painter.end()
