"""Layout-owned connector rails for the children of a Settings disclosure.

The QWidget/layout tree is the hierarchy. In particular, a nested bucket's
header is a child here, but its body paints its own descendants. No registration
or copy of the settings schema is needed, including for lazily added controls.
"""
from __future__ import annotations

from collections.abc import Iterator

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QLayout, QVBoxLayout, QWidget

from ui.settings_theme_runtime import get_active_settings_theme


BUCKET_CHILD_INDENT = 18  # logical pixels; one shared gutter per hierarchy level


def _first_visible_widget(layout: QLayout, owner: QWidget) -> QWidget | None:
    """Find the leading visible label/control, without entering a child bucket."""
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            if (isinstance(widget, BucketTreeBody) or not widget.isVisibleTo(owner)
                    or widget.property("settingsAnnotation")):
                continue
            if isinstance(widget, QLabel) and not widget.text() and widget.pixmap().isNull():
                continue  # empty alignment placeholders are not visible controls
            inner = widget.layout()
            if inner is not None:
                leading = _first_visible_widget(inner, owner)
                if leading is not None:
                    return leading
                continue
            return widget
        inner = item.layout()
        if inner is not None:
            leading = _first_visible_widget(inner, owner)
            if leading is not None:
                return leading
    return None


def _row_widgets(layout: QLayout, owner: QWidget) -> Iterator[QWidget]:
    """Unwrap vertical grouping hosts, but preserve horizontal form rows.

    Settings uses both bare layouts and transparent QWidgets to group rows.
    Neither creates a hierarchy level. Only a bucket body owns descendants.
    """
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            if (isinstance(widget, BucketTreeBody) or not widget.isVisibleTo(owner)
                    or widget.property("settingsAnnotation")):
                continue
            if isinstance(widget, QLabel) and not widget.text() and widget.pixmap().isNull():
                continue
            inner = widget.layout()
            if isinstance(inner, QVBoxLayout):
                yield from _row_widgets(inner, owner)
            elif inner is not None:
                leading = _first_visible_widget(inner, owner)
                if leading is not None:
                    yield leading
            else:
                yield widget
        else:
            inner = item.layout()
            if isinstance(inner, QVBoxLayout):
                yield from _row_widgets(inner, owner)
            elif inner is not None:
                leading = _first_visible_widget(inner, owner)
                if leading is not None:
                    yield leading


class BucketTreeBody(QWidget):
    """A normal bucket body with a subtle rail behind its immediate child rows.

    Layout requests already own insertion, conditions and disclosure reflow.
    They also invalidate this decoration; no child observers, timers, retained
    endpoints or geometry writes are involved. Paint only visits this level's
    layout items and the leading widget of each row, never descendant bodies.
    """

    def event(self, event) -> bool:  # type: ignore[override]
        handled = super().event(event)
        if event.type() == QEvent.Type.LayoutRequest:
            self.update()
        return handled

    def branch_anchors(self) -> tuple[QPointF, ...]:
        """Current visible row/header starts in body-local logical coordinates."""
        layout = self.layout()
        if layout is None:
            return ()
        anchors = []
        for leading in _row_widgets(layout, self):
            if leading.width() <= 0 or leading.height() <= 0:
                continue
            origin = leading.mapTo(self, QPoint(0, 0))
            anchors.append(QPointF(origin.x(), origin.y() + leading.height() / 2.0))
        return tuple(anchors)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        anchors = self.branch_anchors()
        if not anchors:
            return
        # The current layout margin defines the gutter; endpoints always come
        # from the actual widgets, including after resize/DPI/condition changes.
        gutter = self.layout().contentsMargins().left()
        rail_x = gutter / 2.0
        anchors = tuple(point for point in anchors if point.x() > rail_x + 2.0)
        if not anchors:
            return
        path = QPainterPath(QPointF(rail_x, 0.0))
        path.lineTo(rail_x, max(point.y() for point in anchors))
        for point in anchors:
            path.moveTo(rail_x, point.y())
            path.lineTo(point.x() - 3.0, point.y())
        color = QColor(*get_active_settings_theme().color("bucket.open.border").as_tuple())
        color.setAlphaF(color.alphaF() * 0.42)
        painter = QPainter(self)
        painter.setClipRect(event.rect())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 1.0)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
