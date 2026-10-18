"""Visual Settings controls shared by every Settings builder: a two-handle range slider, a triangle
mapper (three shares placed by one node) and a direction mapper (a direction placed on a disc).

They paint with the active Settings theme's slider tokens, so they read as the shared slider does
(the same 4 px glass groove, its fill, the 16 x 10 pill handle with hover/pressed states), and repaint
when the theme changes (``ui/tabs/shared_styles.py`` refreshes live themed painters). Each offers:

* ``valueChanged(object)`` while the value moves (labels, previews) and ``valueCommitted(object)``
  once per gesture or discrete keyboard step (the persistence boundary, as ``NoWheelSlider``);
* ``value()`` / ``setValue(value)`` (programmatic, emits nothing);
* keyboard control (arrows, Page Up/Down, Home/End) and an accessible description of the value;
* no wheel input (a scrolling page never changes a setting).

Values: ``RangeSlider`` integer positions ``(low, high)``; ``TriangleMapper`` three shares summing
to 1; ``DirectionMapper`` ``(around, height)`` in degrees (around wraps in [-180, 180); height lies
in the control's range, the disc's centre at its top, its rim at its bottom).
"""
from __future__ import annotations

import math
import weakref

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

# Live widgets repainted when the Settings theme changes.
LIVE_THEMED_PAINTERS: weakref.WeakSet = weakref.WeakSet()

_GROOVE_HEIGHT = 6.0      # QSS: 4 px content plus its 1 px border above and below
_HANDLE_W, _HANDLE_H = 16.0, 10.0


def _theme():
    from ui.tabs import shared_styles

    return shared_styles._SETTINGS_THEME


def _colour(token: str) -> QColor:
    return QColor(*_theme().color(token).as_tuple())


def _vertical_gradient(token: str, top: float, bottom: float) -> QLinearGradient:
    gradient = QLinearGradient(0.0, top, 0.0, bottom)
    for stop in _theme().gradient(token).stops:
        gradient.setColorAt(stop.position, QColor(*stop.color.as_tuple()))
    return gradient


def _paint_groove(painter: QPainter, rect: QRectF, fill: bool) -> None:
    surface, border = ("slider.fill.surface", "slider.fill.border") if fill else \
        ("slider.groove.surface", "slider.groove.border")
    painter.setPen(QPen(_colour(border), 1.0))
    painter.setBrush(_vertical_gradient(surface, rect.top(), rect.bottom()))
    painter.drawRoundedRect(rect, 2.0, 2.0)


def _paint_handle(painter: QPainter, centre: QPointF, state: str, enabled: bool, *, round_: bool = False) -> None:
    """The shared pill handle (or a round one of the same height) in a state: '', 'hover', 'pressed', 'active'."""
    width = _HANDLE_H + 2.0 if round_ else _HANDLE_W
    height = _HANDLE_H + 2.0 if round_ else _HANDLE_H
    if state == "active" and not round_:
        width, height = 15.0, 9.0          # QSS lastMoved: 12 x 6 content plus a 1.5 px border
    rect = QRectF(centre.x() - width / 2, centre.y() - height / 2, width, height)
    if not enabled:
        painter.setPen(QPen(_colour("slider.handle.border"), 1.0))
        painter.setBrush(_colour("slider.handle.disabled_surface"))
    else:
        surface = {"hover": "slider.handle.hover_surface", "pressed": "slider.handle.pressed_surface",
                   "active": "slider.handle.active_surface"}.get(state, "slider.handle.surface")
        border = {"hover": "slider.handle.hover_border", "pressed": "slider.handle.pressed_border",
                  "active": "slider.handle.active_border"}.get(state, "slider.handle.border")
        painter.setPen(QPen(_colour(border), 1.5 if state == "active" else 1.0))
        painter.setBrush(_vertical_gradient(surface, rect.top(), rect.bottom()))
    painter.drawRoundedRect(rect, height / 2, height / 2)


class _VisualControl(QWidget):
    valueChanged = Signal(object)
    valueCommitted = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._hover = False
        self._dragging = False
        self._moved_in_drag = False
        self.setProperty("lastMoved", False)
        LIVE_THEMED_PAINTERS.add(self)

    def _state(self, *, primary: bool = True) -> str:
        if self._dragging and primary:
            return "pressed"
        if self.property("lastMoved") and primary:
            return "active"
        return "hover" if self._hover and primary else ""

    def event(self, event):  # type: ignore[override]
        # Another control taking the page's last-moved highlight clears ours: repaint.
        if event.type() == QEvent.Type.DynamicPropertyChange and bytes(event.propertyName()) == b"lastMoved":
            self.update()
        return super().event(event)

    # A scrolling page never changes a setting.
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()

    def enterEvent(self, event):  # type: ignore[override]
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # type: ignore[override]
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def _changed(self, *, commit: bool) -> None:
        # The page highlights only the most recently moved control, sliders included.
        from ui.tabs.shared_styles import mark_last_moved_control
        mark_last_moved_control(self)
        self.setAccessibleDescription(self.describe())
        self.update()
        self.valueChanged.emit(self.value())
        if commit:
            self.valueCommitted.emit(self.value())
        elif self._dragging:
            self._moved_in_drag = True

    def mouseReleaseEvent(self, event):  # type: ignore[override]
        if self._dragging:
            self._dragging = False
            if self._moved_in_drag:
                self.valueCommitted.emit(self.value())
            self._moved_in_drag = False
            self.update()
        super().mouseReleaseEvent(event)

    def describe(self) -> str:  # pragma: no cover - overridden
        return ""

    def value(self):  # pragma: no cover - overridden
        raise NotImplementedError


class RangeSlider(_VisualControl):
    """Two handles on the shared slider's groove: a low and a high position, low <= high."""

    def __init__(self, minimum: int = 0, maximum: int = 100, parent=None) -> None:
        super().__init__(parent)
        self._min, self._max = int(minimum), int(maximum)
        self._low, self._high = self._min, self._max
        self._active = 0           # the handle the keyboard moves (0 low, 1 high)
        self._grab_offset = 0.0
        self._tie_x: float | None = None
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleDescription(self.describe())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(160, 34)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._min, self._max = int(minimum), max(int(minimum), int(maximum))
        self.setValue((self._low, self._high))

    def minimum(self) -> int:
        return self._min

    def maximum(self) -> int:
        return self._max

    def value(self) -> tuple[int, int]:
        return self._low, self._high

    def setValue(self, value) -> None:
        low, high = (int(round(v)) for v in value)
        low, high = sorted((max(self._min, min(self._max, low)), max(self._min, min(self._max, high))))
        self._low, self._high = low, high
        self.setAccessibleDescription(self.describe())
        self.update()

    def describe(self) -> str:
        return f"Range {self._low} to {self._high}"

    # Geometry: the handle centres travel the groove inset by half a handle, as QSlider's do.
    def _groove(self) -> QRectF:
        top = 2.0 + (self.height() - 2.0) / 2 - _GROOVE_HEIGHT / 2
        return QRectF(0.5, top, self.width() - 1.0, _GROOVE_HEIGHT)

    def _x(self, position: int) -> float:
        span = max(1, self._max - self._min)
        return _HANDLE_W / 2 + (self.width() - _HANDLE_W) * (position - self._min) / span

    def _position(self, x: float) -> int:
        span = max(1.0, self.width() - _HANDLE_W)
        ratio = max(0.0, min(1.0, (x - _HANDLE_W / 2) / span))
        return int(round(self._min + ratio * (self._max - self._min)))

    def handle_centre(self, which: int) -> QPointF:
        return QPointF(self._x(self._low if which == 0 else self._high), self._groove().center().y())

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        groove = self._groove()
        _paint_groove(painter, groove, fill=False)
        fill = QRectF(self._x(self._low), groove.top(), max(0.0, self._x(self._high) - self._x(self._low)),
                      groove.height())
        if fill.width() > 0.5:
            _paint_groove(painter, fill, fill=True)
        enabled = self.isEnabled()
        for which in (0, 1) if self._active == 1 else (1, 0):   # the active handle on top
            state = self._state(primary=which == self._active)
            _paint_handle(painter, self.handle_centre(which), state, enabled)

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        x = event.position().x()
        low_x, high_x = self._x(self._low), self._x(self._high)
        if abs(low_x - high_x) < 1.0 and abs(x - low_x) <= _HANDLE_W / 2:
            self._tie_x = x                 # stacked handles: the drag's direction picks one
            self._active = 1
        else:
            self._tie_x = None
            self._active = 0 if abs(x - low_x) <= abs(x - high_x) else 1
        centre = low_x if self._active == 0 else high_x
        on_handle = abs(x - centre) <= _HANDLE_W / 2
        self._grab_offset = x - centre if on_handle else 0.0
        self._dragging = True
        self._moved_in_drag = False
        if not on_handle:
            self._move_active(self._position(x), commit=False)  # a click on the groove brings the nearer handle
        self.update()

    def mouseMoveEvent(self, event):  # type: ignore[override]
        if not self._dragging:
            return super().mouseMoveEvent(event)
        x = event.position().x()
        if self._tie_x is not None:
            if abs(x - self._tie_x) < 2.0:
                return
            self._active = 1 if x > self._tie_x else 0
            self._tie_x = None
        self._move_active(self._position(x - self._grab_offset), commit=False)

    def _move_active(self, position: int, *, commit: bool) -> None:
        if self._active == 0:
            position = max(self._min, min(self._high, position))
            if position == self._low:
                return
            self._low = position
        else:
            position = max(self._low, min(self._max, position))
            if position == self._high:
                return
            self._high = position
        self._changed(commit=commit)

    def keyPressEvent(self, event):  # type: ignore[override]
        key = event.key()
        page = max(1, (self._max - self._min) // 10)
        current = self._low if self._active == 0 else self._high
        steps = {Qt.Key.Key_Left: -1, Qt.Key.Key_Down: -1, Qt.Key.Key_Right: 1, Qt.Key.Key_Up: 1,
                 Qt.Key.Key_PageDown: -page, Qt.Key.Key_PageUp: page}
        if key in steps:
            self._move_active(current + steps[key], commit=True)
        elif key == Qt.Key.Key_Home:
            self._move_active(self._min, commit=True)
        elif key == Qt.Key.Key_End:
            self._move_active(self._max, commit=True)
        else:
            return super().keyPressEvent(event)
        event.accept()

    def focusNextPrevChild(self, next_: bool) -> bool:  # type: ignore[override]
        # Tab moves from the low handle to the high one, then on out of the control (Shift+Tab back).
        if next_ and self._active == 0:
            self._active = 1
            self.update()
            return True
        if not next_ and self._active == 1:
            self._active = 0
            self.update()
            return True
        return super().focusNextPrevChild(next_)


class TriangleMapper(_VisualControl):
    """Three shares placed by one node inside a triangle: the nearer a corner, the larger its share."""

    def __init__(self, corners: tuple[str, str, str] = ("A", "B", "C"), parent=None) -> None:
        super().__init__(parent)
        self._corners = tuple(corners)
        self._shares = (1 / 3, 1 / 3, 1 / 3)
        self.setMinimumSize(200, 168)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleDescription(self.describe())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(200, 168)

    def value(self) -> tuple[float, float, float]:
        return self._shares

    def setValue(self, value) -> None:
        self._shares = _normalised_shares(value)
        self.setAccessibleDescription(self.describe())
        self.update()

    def describe(self) -> str:
        return ", ".join(f"{name} {round(share * 100)}%" for name, share in zip(self._corners, self._shares))

    def vertices(self) -> tuple[QPointF, QPointF, QPointF]:
        """Top, bottom-left, bottom-right corners (the corner names' order)."""
        margin_x, top, bottom = 26.0, 20.0, self.height() - 24.0
        side = min(self.width() - 2 * margin_x, (bottom - top) * 2 / math.sqrt(3))
        centre_x = self.width() / 2
        height = side * math.sqrt(3) / 2
        top_y = top + ((bottom - top) - height) / 2
        return (QPointF(centre_x, top_y), QPointF(centre_x - side / 2, top_y + height),
                QPointF(centre_x + side / 2, top_y + height))

    def node(self) -> QPointF:
        a, b, c = self.vertices()
        wa, wb, wc = self._shares
        return QPointF(a.x() * wa + b.x() * wb + c.x() * wc, a.y() * wa + b.y() * wb + c.y() * wc)

    def shares_at(self, point: QPointF) -> tuple[float, float, float]:
        """The shares of the nearest point inside the triangle to ``point``; within 8 px of a corner or the
        centre it snaps there."""
        a, b, c = self.vertices()
        for index, corner in enumerate((a, b, c)):
            if math.hypot(point.x() - corner.x(), point.y() - corner.y()) <= 8.0:
                return tuple(1.0 if i == index else 0.0 for i in range(3))
        centre = QPointF((a.x() + b.x() + c.x()) / 3, (a.y() + b.y() + c.y()) / 3)
        if math.hypot(point.x() - centre.x(), point.y() - centre.y()) <= 6.0:
            return (1 / 3, 1 / 3, 1 / 3)
        return _barycentric_clamped(point, a, b, c)

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        a, b, c = self.vertices()
        triangle = QPolygonF([a, b, c])
        painter.setPen(QPen(_colour("slider.groove.border"), 1.0))
        painter.setBrush(_vertical_gradient("slider.groove.surface", a.y(), b.y()))
        painter.drawPolygon(triangle)
        # Guides from the node to each corner, stronger toward the corner holding more.
        node = self.node()
        guide = _colour("slider.handle.hover_border")
        for corner, share in zip((a, b, c), self._shares):
            colour = QColor(guide)
            colour.setAlphaF(0.15 + 0.55 * share)
            painter.setPen(QPen(colour, 1.0 + 1.5 * share))
            painter.drawLine(node, corner)
        # Corner names, the largest share's brightest.
        font = QFont(self.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5))
        painter.setFont(font)
        leader = max(range(3), key=lambda i: self._shares[i])
        for index, (corner, name) in enumerate(zip((a, b, c), self._corners)):
            painter.setPen(_colour("text.primary" if index == leader and self.isEnabled() else "text.secondary"))
            if index == 0:
                rect = QRectF(corner.x() - 60, corner.y() - 19, 120, 16)
                align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
            else:
                rect = QRectF(corner.x() - 60, corner.y() + 4, 120, 16)
                align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
            painter.drawText(rect, align, name)
        _paint_handle(painter, node, self._state(), self.isEnabled(), round_=True)

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        self._dragging = True
        self._moved_in_drag = False
        self._place(event.position())

    def mouseMoveEvent(self, event):  # type: ignore[override]
        if self._dragging:
            self._place(event.position())
        else:
            super().mouseMoveEvent(event)

    def _place(self, point: QPointF, *, commit: bool = False) -> None:
        shares = self.shares_at(point)
        if all(abs(x - y) < 1e-6 for x, y in zip(shares, self._shares)):
            return
        self._shares = shares
        self._changed(commit=commit)

    def keyPressEvent(self, event):  # type: ignore[override]
        step = 3.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
        moves = {Qt.Key.Key_Left: (-step, 0.0), Qt.Key.Key_Right: (step, 0.0),
                 Qt.Key.Key_Up: (0.0, -step), Qt.Key.Key_Down: (0.0, step)}
        if event.key() in moves:
            dx, dy = moves[event.key()]
            node = self.node()
            # Keys never snap: place directly by barycentric clamp.
            a, b, c = self.vertices()
            shares = _barycentric_clamped(QPointF(node.x() + dx * 2.0, node.y() + dy * 2.0), a, b, c)
            if any(abs(x - y) > 1e-6 for x, y in zip(shares, self._shares)):
                self._shares = shares
                self._changed(commit=True)
            event.accept()
            return
        super().keyPressEvent(event)


class DirectionMapper(_VisualControl):
    """A direction placed on a disc: the angle round it is ``around`` (0 up, clockwise), the distance
    from the centre is ``height`` (centre = the top of the range, rim = its bottom). ``centre_text``
    names the centre (``"Overhead"``, ``"Into Scene"``); ``marker`` draws the point as an arrow from
    the centre (a stream) or a glowing dot (a light). A collapsed height range (low == high) is a plain
    angle dial: the point rides a ring and only ``around`` changes (gradient, shadow or screen directions)."""

    def __init__(self, height_range: tuple[float, float] = (0.0, 90.0), *, centre_text: str = "",
                 marker: str = "arrow", parent=None) -> None:
        super().__init__(parent)
        self._low, self._high = float(height_range[0]), float(height_range[1])
        self._centre_text = centre_text
        self._marker = marker
        self._around, self._height = 0.0, self._high
        side = 96 if self.is_dial() else 150          # a plain angle needs less room than a full disc
        self.setMinimumSize(side, side)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleDescription(self.describe())

    def sizeHint(self) -> QSize:  # type: ignore[override]
        side = 96 if self.is_dial() else 150
        return QSize(side, side)

    def value(self) -> tuple[float, float]:
        return self._around, self._height

    def setValue(self, value) -> None:
        around, height = (float(v) for v in value)
        self._around = _wrap_degrees(around)
        self._height = max(self._low, min(self._high, height))
        self.setAccessibleDescription(self.describe())
        self.update()

    def describe(self) -> str:
        if self.is_dial():
            return f"Angle {round(self._around)} degrees"
        return f"Around {round(self._around)} degrees, height {round(self._height)} degrees"

    def disc(self) -> tuple[QPointF, float]:
        radius = min(self.width(), self.height()) / 2 - 10.0
        return QPointF(self.width() / 2, self.height() / 2), radius

    def point(self) -> QPointF:
        centre, radius = self.disc()
        if self.is_dial():
            r = radius * 0.8
        else:
            r = radius * (self._high - self._height) / (self._high - self._low)
        angle = math.radians(self._around)
        return QPointF(centre.x() + r * math.sin(angle), centre.y() - r * math.cos(angle))

    def is_dial(self) -> bool:
        return self._high - self._low < 1e-6

    def value_at(self, point: QPointF) -> tuple[float, float]:
        centre, radius = self.disc()
        dx, dy = point.x() - centre.x(), point.y() - centre.y()
        distance = min(1.0, math.hypot(dx, dy) / max(radius, 1e-6))
        if self.is_dial():
            distance = max(distance, 0.8)        # a dial reads only the angle
        # Snap to the centre and to each 45 degree spoke within a few pixels.
        if distance * radius <= 5.0:
            return self._around, self._high
        around = math.degrees(math.atan2(dx, -dy))
        nearest = round(around / 45.0) * 45.0
        if abs(around - nearest) * math.pi / 180.0 * distance * radius <= 4.0:
            around = nearest
        height = self._high - distance * (self._high - self._low)
        return _wrap_degrees(around), height

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        centre, radius = self.disc()
        painter.setPen(QPen(_colour("slider.groove.border"), 1.0))
        painter.setBrush(_vertical_gradient("slider.groove.surface", centre.y() - radius, centre.y() + radius))
        painter.drawEllipse(centre, radius, radius)
        # Height rings and the eight spokes, faint.
        faint = _colour("slider.groove.bottom_border")
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(faint, 1.0))
        for ring in ((0.8,) if self.is_dial() else (1 / 3, 2 / 3)):
            painter.drawEllipse(centre, radius * ring, radius * ring)
        for k in range(8):
            angle = math.radians(45.0 * k)
            painter.drawLine(centre, QPointF(centre.x() + radius * math.sin(angle), centre.y() - radius * math.cos(angle)))
        if self._centre_text:
            font = QFont(self.font())
            font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
            painter.setFont(font)
            painter.setPen(_colour("text.tertiary"))
            painter.drawText(QRectF(centre.x() - 50, centre.y() + 6, 100, 14), Qt.AlignmentFlag.AlignHCenter,
                             self._centre_text)
        point = self.point()
        accent = _colour("slider.handle.hover_border" if self.isEnabled() else "slider.handle.border")
        if self._marker == "arrow" and math.hypot(point.x() - centre.x(), point.y() - centre.y()) > 6.0:
            pen = QPen(accent, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(centre, point)
            angle = math.atan2(point.y() - centre.y(), point.x() - centre.x())
            head = QPainterPath()
            head.moveTo(point)
            for side in (-1, 1):
                head.lineTo(QPointF(point.x() - 8 * math.cos(angle + side * 0.45),
                                    point.y() - 8 * math.sin(angle + side * 0.45)))
                head.moveTo(point)
            painter.drawPath(head)
        elif self._marker == "light":
            # The light: a glow, and three short rays fanning from it toward the scene (where its shafts fall).
            dx, dy = centre.x() - point.x(), centre.y() - point.y()
            reach = math.hypot(dx, dy)
            if reach > 8.0:
                angle = math.atan2(dy, dx)
                length = reach - 6.0                     # all the way in, as the stream arrow spans the disc
                for spread, alpha in ((-0.28, 0.45), (0.0, 0.85), (0.28, 0.45)):
                    ray = QColor(accent)
                    ray.setAlphaF(alpha)
                    pen = QPen(ray, 1.6)
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    painter.setPen(pen)
                    start = QPointF(point.x() + 9.0 * math.cos(angle + spread), point.y() + 9.0 * math.sin(angle + spread))
                    painter.drawLine(start, QPointF(point.x() + length * math.cos(angle + spread),
                                                    point.y() + length * math.sin(angle + spread)))
            glow = QColor(accent)
            for size, alpha in ((14.0, 0.12), (10.0, 0.22)):
                glow.setAlphaF(alpha)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                painter.drawEllipse(point, size, size)
        _paint_handle(painter, point, self._state(), self.isEnabled(), round_=True)

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        self._dragging = True
        self._moved_in_drag = False
        self._place(event.position())

    def mouseMoveEvent(self, event):  # type: ignore[override]
        if self._dragging:
            self._place(event.position())
        else:
            super().mouseMoveEvent(event)

    def _place(self, point: QPointF) -> None:
        around, height = self.value_at(point)
        if abs(around - self._around) < 1e-6 and abs(height - self._height) < 1e-6:
            return
        self._around, self._height = around, height
        self._changed(commit=False)

    def keyPressEvent(self, event):  # type: ignore[override]
        step = 15.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 5.0
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._around = _wrap_degrees(self._around + (step if key == Qt.Key.Key_Right else -step))
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = step if key == Qt.Key.Key_Up else -step
            self._height = max(self._low, min(self._high, self._height + delta))
        else:
            return super().keyPressEvent(event)
        self._changed(commit=True)
        event.accept()


def _wrap_degrees(value: float) -> float:
    return (float(value) + 180.0) % 360.0 - 180.0


def _normalised_shares(value) -> tuple[float, float, float]:
    try:
        shares = [max(0.0, float(v)) for v in list(value)[:3]]
    except (TypeError, ValueError):
        shares = []
    if len(shares) != 3 or not all(math.isfinite(s) for s in shares) or sum(shares) <= 0.0:
        return (1 / 3, 1 / 3, 1 / 3)
    total = sum(shares)
    return tuple(s / total for s in shares)  # type: ignore[return-value]


def _barycentric_clamped(p: QPointF, a: QPointF, b: QPointF, c: QPointF) -> tuple[float, float, float]:
    """Barycentric weights of the point of triangle abc nearest ``p`` (each >= 0, summing to 1)."""
    v0x, v0y = b.x() - a.x(), b.y() - a.y()
    v1x, v1y = c.x() - a.x(), c.y() - a.y()
    v2x, v2y = p.x() - a.x(), p.y() - a.y()
    den = v0x * v1y - v1x * v0y
    if abs(den) < 1e-9:
        return (1 / 3, 1 / 3, 1 / 3)
    wb = (v2x * v1y - v1x * v2y) / den
    wc = (v0x * v2y - v2x * v0y) / den
    wa = 1.0 - wb - wc
    if min(wa, wb, wc) >= 0.0:
        return (wa, wb, wc)
    # Outside: the nearest point on the nearest edge.
    best, best_d = (1 / 3, 1 / 3, 1 / 3), float("inf")
    corners = ((a, 0), (b, 1), (c, 2))
    for (p0, i0), (p1, i1) in ((corners[0], corners[1]), (corners[1], corners[2]), (corners[2], corners[0])):
        ex, ey = p1.x() - p0.x(), p1.y() - p0.y()
        t = max(0.0, min(1.0, ((p.x() - p0.x()) * ex + (p.y() - p0.y()) * ey) / max(ex * ex + ey * ey, 1e-9)))
        qx, qy = p0.x() + t * ex, p0.y() + t * ey
        d = (qx - p.x()) ** 2 + (qy - p.y()) ** 2
        if d < best_d:
            weights = [0.0, 0.0, 0.0]
            weights[i0], weights[i1] = 1.0 - t, t
            best, best_d = tuple(weights), d
    return best  # type: ignore[return-value]


__all__ = ["DirectionMapper", "LIVE_THEMED_PAINTERS", "RangeSlider", "TriangleMapper"]
