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


class ScenePathMapper(_VisualControl):
    """Physical 3D scene segment: two independently draggable XY nodes and depth rails.

    The disc maps X left/right and Y floor/surface; the two rails independently
    map Z front/back. All coordinates normalized to [-1,1]. Tab selects a node;
    arrows move it in XY and Page Up/Down in depth; Shift makes fine steps.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._coords = [0., -1., 0., 0., 1., 0.]
        self._active = 0
        self._drag_axis = ''
        self.setMinimumSize(200, 236)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleDescription(self.describe())

    def sizeHint(self) -> QSize:
        return QSize(200, 236)

    def value(self) -> tuple[float, ...]:
        return tuple(self._coords)

    def setValue(self, value) -> None:
        new = [float(v) for v in value]
        if len(new) != 6:
            raise ValueError('Scene path expects source and endpoint xyz')
        self._coords = [max(-1., min(1., v)) for v in new]
        self.setAccessibleDescription(self.describe())
        self.update()

    def describe(self) -> str:
        s = self._coords
        return (f'Source x {s[0]:+.2f}, y {s[1]:+.2f}, depth {s[2]:+.2f}; '
                f'End x {s[3]:+.2f}, y {s[4]:+.2f}, depth {s[5]:+.2f}')

    def _disc(self):
        return QPointF(self.width() / 2, 83), 73.

    def _node(self, idx: int):
        c, radius = self._disc()
        i = idx * 3
        from core.settings.visualizer_paths import square_to_disc
        x, y = square_to_disc(self._coords[i], self._coords[i+1])
        return QPointF(c.x() + x * radius, c.y() - y * radius)

    def _rail(self, idx: int):
        y = 181 + idx * 31
        return QRectF(25, y, self.width() - 50, 6)

    def _depth_x(self, idx: int):
        r = self._rail(idx)
        return r.left() + (self._coords[idx*3+2] + 1.) * 0.5 * r.width()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center, rad = self._disc()
        faint = _colour('slider.groove.bottom_border')
        p.setPen(QPen(_colour('slider.groove.border'), 1.))
        p.setBrush(_vertical_gradient('slider.groove.surface', center.y()-rad, center.y()+rad))
        p.drawEllipse(center, rad, rad)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(faint, 1.))
        for r in (rad/3, 2*rad/3):
            p.drawEllipse(center, r, r)
        p.drawLine(QPointF(center.x()-rad, center.y()), QPointF(center.x()+rad, center.y()))
        p.drawLine(QPointF(center.x(), center.y()-rad), QPointF(center.x(), center.y()+rad))
        src, end = self._node(0), self._node(1)
        pen = QPen(_colour('slider.handle.hover_border'), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(src, end)
        for i, point in enumerate((src, end)):
            active = i == self._active
            _paint_handle(p, point, self._state(primary=active), self.isEnabled(), round_=True)
            p.setPen(_colour('text.tertiary'))
            p.drawText(QRectF(point.x()-12, point.y()-22, 24, 14), Qt.AlignmentFlag.AlignCenter,
                       'S' if i == 0 else 'E')
        p.setPen(_colour('text.tertiary'))
        p.drawText(QRectF(10, 163, self.width()-20, 16), Qt.AlignmentFlag.AlignCenter,
                   'Depth: front −1  ·  back +1')
        for i in range(2):
            rail = self._rail(i)
            _paint_groove(p, rail, fill=False)
            _paint_handle(p, QPointF(self._depth_x(i), rail.center().y()),
                          self._state(primary=i == self._active), self.isEnabled(), round_=False)
            p.setPen(_colour('text.tertiary'))
            p.drawText(QRectF(3, rail.top()-2, 18, 14), Qt.AlignmentFlag.AlignCenter,
                       'S' if i == 0 else 'E')

    def _move_to(self, pos):
        i = self._active * 3
        if self._drag_axis == 'depth':
            r = self._rail(self._active)
            self._coords[i+2] = max(-1., min(1., 2. * (pos.x()-r.left()) / r.width() - 1.))
        else:
            c, radius = self._disc()
            x = (pos.x() - c.x()) / radius
            y = (c.y() - pos.y()) / radius
            from core.settings.visualizer_paths import disc_to_square
            self._coords[i:i+2] = list(disc_to_square(x, y))
        self._changed(commit=False)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            return super().mousePressEvent(event)
        pos = event.position()
        self._drag_axis = 'depth' if pos.y() > 167 else 'xy'
        if self._drag_axis == 'depth':
            self._active = 0 if pos.y() < 197 else 1
        else:
            self._active = min(range(2), key=lambda idx:
                               (self._node(idx).x()-pos.x())**2 + (self._node(idx).y()-pos.y())**2)
        self._dragging = True
        self._moved_in_drag = False
        self._move_to(pos)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._move_to(event.position())
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Tab:
            self._active = 1 - self._active
            self.update()
            event.accept()
            return
        step = 0.015 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 0.05
        axis, change = {
            Qt.Key.Key_Left: (0, -step), Qt.Key.Key_Right: (0, step),
            Qt.Key.Key_Up: (1, step), Qt.Key.Key_Down: (1, -step),
            Qt.Key.Key_PageUp: (2, step), Qt.Key.Key_PageDown: (2, -step),
        }.get(key, (None, 0.))
        if axis is None:
            return super().keyPressEvent(event)
        i = self._active*3 + axis
        self._coords[i] = max(-1., min(1., self._coords[i]+change))
        self._changed(commit=True)
        event.accept()


class DirectionMapper(_VisualControl):
    """A direction placed on a disc: the angle round it is ``around`` (0 up, clockwise), the distance
    from the centre is ``height`` (centre = the top of the range, rim = its bottom). ``centre_text``
    names the centre (``"Overhead"``, ``"Into Scene"``); ``marker`` draws the point as an arrow from
    the centre (a stream) or a glowing dot (a light). A collapsed height range (low == high) is a plain
    angle dial: the point rides a ring and only ``around`` changes (gradient, shadow or screen directions)."""

    def __init__(self, height_range: tuple[float, float] = (0.0, 90.0), *, centre_text: str = "",
                 marker: str = "arrow", midline: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._low, self._high = float(height_range[0]), float(height_range[1])
        self._centre_text = centre_text
        self._marker = marker
        self._midline = bool(midline)
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
        if self._midline and not self.is_dial():
            # The X (horizontal) axis is the subtle water-surface / halfway guide in a full
            # direction disc; never give an angle-only dial a fictitious height reference.
            guide = QPen(faint, 2.0)
            guide.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(guide)
            painter.drawLine(QPointF(centre.x() - radius, centre.y()),
                             QPointF(centre.x() + radius, centre.y()))
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

class SceneVolumeMapper(_VisualControl):
    """Oblique 3D world-volume editor, sharing EB's normalized XYZ geometry.

    No FOV-dependent projection or alternate renderer. Drag a point to adjust its
    X/Y plane; Shift+drag or right-drag adjusts physical depth Z. Source/end
    use coloured unlettered handles. The live eye is a movable diamond, whether
    this editor is in a stream, light, ray, or camera Settings bucket.
    """
    cameraOffsetChanged = Signal(tuple)
    cameraOffsetCommitted = Signal(tuple)
    cameraAimChanged = Signal(tuple)
    cameraAimCommitted = Signal(tuple)
    linkedSourceChanged = Signal(tuple)
    linkedSourceCommitted = Signal(tuple)

    def __init__(self, *, camera_only=False, parent=None):
        super().__init__(parent)
        self._camera_only = bool(camera_only)
        self._coords = [0., -1., 0., 0., 1., 0.] if not camera_only else [0., 0., 0.]
        self._camera_offset = (0., 0., 0.)
        self._base_eye = (0., 0., 0.)
        self._camera_angles = (0., 0.)
        self._linked_source = None
        self._coverage_geometry = 'BEAM'
        self._scene_direction = (0., 1., 0.)
        self._scene_source = (0., -1., 0.)
        self._references = {}
        self._active = 0
        self._drag_axis = ''
        self._drag_role = ''
        self._drag_start = None
        self._drag_start_z = 0.
        self.setMinimumSize(268, 265)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleDescription(self.describe())

    def sizeHint(self):
        return QSize(268, 265)

    def value(self):
        return tuple(self._coords)

    def setValue(self, value):
        seq = [float(v) for v in value]
        if len(seq) != (3 if self._camera_only else 6):
            raise ValueError('Scene volume value must have three camera or six path coordinates')
        self._coords = [max(-8., min(8., x)) if self._camera_only else max(-1., min(1., x)) for x in seq]
        if self._camera_only:
            self._camera_offset = tuple(self._coords)
        self.setAccessibleDescription(self.describe())
        self.update()

    def setSceneReferences(self, *, paths=None, base_eye=(0., 0., 0.), camera_offset=(0., 0., 0.),
                           camera_angles=(0., 0.), linked_source=None,
                           coverage_geometry='BEAM', scene_direction=(0., 1., 0.),
                           scene_source=(0., -1., 0.)):
        self._references = dict(paths or {})
        self._coverage_geometry = coverage_geometry
        self._scene_direction = tuple(float(v) for v in scene_direction)
        self._scene_source = tuple(float(v) for v in scene_source)
        self._base_eye = tuple(float(x) for x in base_eye)
        self._camera_angles = tuple(float(x) for x in camera_angles)
        self._linked_source = tuple(linked_source) if linked_source is not None else None
        if not self._camera_only:
            self._camera_offset = tuple(float(x) for x in camera_offset)
        self.update()

    def describe(self):
        if self._camera_only:
            return 'Camera world translation ' + ', '.join(f'{x:+.2f}' for x in self._coords)
        return 'Source XYZ ' + ', '.join(f'{x:+.2f}' for x in self._coords[:3]) + '; End XYZ ' + ', '.join(f'{x:+.2f}' for x in self._coords[3:])

    def _eye(self):
        return tuple(self._base_eye[i] + self._camera_offset[i] for i in range(3))

    def _forward(self):
        # Exactly the production camera's yaw/pitch basis, independent of FOV.
        turn, tilt = self._camera_angles
        pitch = math.radians(16.0 + 90.0 * tilt)
        yaw = math.pi * turn
        return (-math.sin(yaw)*math.cos(pitch), math.sin(pitch), -math.cos(yaw)*math.cos(pitch))

    def _aim(self):
        from core.constants.extruded_bubble_world import WORLD_HALF
        eye, forward = self._eye(), self._forward()
        return tuple(eye[i] + 13.0*forward[i]/WORLD_HALF[i] for i in range(3))

    def _path_point(self, idx):
        if idx == 0 and self._linked_source is not None:
            return self._linked_source
        return self._coords[idx*3:idx*3+3]

    def _point(self, xyz):
        # One fixed oblique projection of the same [-1,1]³ world box.
        x, y, z = (float(t) for t in xyz)
        return QPointF(self.width()*.5 + 67.*x - 38.*z,
                       139. - 62.*y + 21.*z + 13.*x)

    def _marker(self, xyz):
        # Keep an outside camera visible and draggable against the boundary.
        return self._point(tuple(max(-1., min(1., float(v))) for v in xyz))

    def _paint_wire(self, p, y):
        path = QPainterPath()
        import math
        for i in range(81):
            t = (2.*math.pi*i)/80.
            # Circumscribe the normalized square's corners; its full X/Z
            # authored span remains visible inside the 3/4 elliptical cage.
            pt = self._point((math.sqrt(2.)*math.cos(t),y,math.sqrt(2.)*math.sin(t)))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        p.drawPath(path)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        edge = _colour('slider.groove.border')
        faint = _colour('slider.groove.bottom_border')
        active = _colour('slider.handle.hover_border')
        p.setPen(QPen(edge,1.2))
        p.setBrush(_vertical_gradient('slider.groove.surface', 60, 215))
        self._paint_wire(p, -1.)
        self._paint_wire(p, 1.)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(faint, 1.))
        for x,z in ((-1.,0.),(1.,0.),(0.,-1.),(0.,1.)):
            p.drawLine(self._point((x,-1.,z)), self._point((x,1.,z)))
        self._paint_wire(p, 0.)
        if not self._camera_only and self._coverage_geometry == 'SCENE':
            # Boundary regions of this editor's own authored path. Motion uses
            # them for inlet/outlet faces; light uses them as source/end guides,
            # not particle admission or a crop of positional light scattering.
            from widgets.spotify_visualizer.extruded_bubble_geometry import scene_source_face_weights
            faces = scene_source_face_weights(self._scene_source, self._scene_direction)
            for axis, component in enumerate(self._scene_direction):
                if faces[axis] < 1e-6:
                    continue
                for is_inlet in (True, False):
                    side = (-1. if component > 0 else 1.) * (1. if is_inlet else -1.)
                    vertices = []
                    others = [k for k in range(3) if k != axis]
                    for u, v in ((-1., -1.), (1., -1.), (1., 1.), (-1., 1.)):
                        point = [0., 0., 0.]
                        point[axis] = side
                        point[others[0]], point[others[1]] = u, v
                        vertices.append(self._point(point))
                    col = QColor(94, 223, 231, 32) if is_inlet else QColor(255, 195, 99, 23)
                    outline = QColor(94, 223, 231, 100) if is_inlet else QColor(255, 195, 99, 85)
                    p.setBrush(col)
                    p.setPen(QPen(outline, 1.4))
                    p.drawPolygon(QPolygonF(vertices))
            p.setBrush(Qt.BrushStyle.NoBrush)
        # Faint neighbouring path references; no second coordinate authority.
        colors = {'stream': QColor(87, 197, 212, 90), 'light': QColor(250, 183, 92, 90),
                  'rays': QColor(210, 157, 236, 90)}
        for role, coords in self._references.items():
            if not isinstance(coords,(list,tuple)) or len(coords)!=6:
                continue
            p.setPen(QPen(colors.get(role, faint),1.5,Qt.PenStyle.DashLine))
            p.drawLine(self._point(coords[:3]),self._point(coords[3:]))
        if not self._camera_only:
            src,end = self._marker(self._path_point(0)),self._marker(self._path_point(1))
            p.setPen(QPen(active, 2.5))
            p.drawLine(src,end)
            for i, pt in enumerate((src,end)):
                p.setBrush(QColor(94, 223, 231) if i==0 else QColor(255, 195, 99))
                p.setPen(QPen(edge, 1.5 if self._active!=i else 2.5))
                p.drawEllipse(pt, 7. if self._active==i else 6., 7. if self._active==i else 6.)
        eye=self._eye()
        cp=self._marker(eye)
        aim = self._marker(self._aim())
        # Two sight guides and the true forward point, all derived from the
        # renderer's current yaw/pitch. The editor never adjusts the FOV.
        direction = self._forward()
        from core.constants.extruded_bubble_world import WORLD_HALF
        side = (math.cos(math.pi*self._camera_angles[0]),0.,-math.sin(math.pi*self._camera_angles[0]))
        for sign in (-1.,1.):
            guide = tuple(eye[i] + (13.0*direction[i] + 2.0*sign*side[i])/WORLD_HALF[i] for i in range(3))
            p.setPen(QPen(QColor(205,165,229,100),1.2))
            p.drawLine(cp,self._marker(guide))
        p.setPen(QPen(QColor(205,165,229,145),1.,Qt.PenStyle.DashLine))
        p.drawLine(cp,aim)
        p.setBrush(QColor(244,211,253))
        p.setPen(QPen(QColor(155,100,190),1.4))
        p.drawEllipse(aim,5.5,5.5)
        p.setBrush(QColor(236, 156, 237))
        p.setPen(QPen(edge, 2.))
        diamond=QPolygonF((QPointF(cp.x(),cp.y()-9),QPointF(cp.x()+9,cp.y()),
                           QPointF(cp.x(),cp.y()+9),QPointF(cp.x()-9,cp.y())))
        p.drawPolygon(diamond)
        if any(abs(t)>1. for t in eye):
            p.setPen(faint)
            p.drawText(QRectF(5,12,self.width()-10,20),Qt.AlignmentFlag.AlignCenter,'Camera outside the source volume')
        # Fully coloured symbols and text; no verbose coordinates or keyboard
        # instructions cluttering the visual controller (screen readers retain describe()).
        for x, name, colour in ((9, '● Start', QColor(94,223,231)),
                                (79, '● End', QColor(255,195,99)),
                                (143, '◆ Camera', QColor(236,156,237)),
                                (221, '● Aim', QColor(244,211,253))):
            p.setPen(colour)
            p.drawText(QRectF(x,240,85,19),Qt.AlignmentFlag.AlignLeft,name)

    def _move_to(self, position):
        if self._drag_role == 'aim':
            from core.constants.extruded_bubble_world import WORLD_HALF
            eye = self._eye()
            aim = list(self._aim())
            z = aim[2]
            x = (position.x()-self.width()*.5+38.*z)/67.
            y = (139.+21.*z+13.*x-position.y())/62.
            target = (x*WORLD_HALF[0], y*WORLD_HALF[1], z*WORLD_HALF[2])
            difference = tuple(target[i]-eye[i]*WORLD_HALF[i] for i in range(3))
            planar = math.hypot(difference[0], difference[2])
            if planar < 1e-5:
                return
            yaw = math.atan2(-difference[0],-difference[2])/math.pi
            pitch = math.degrees(math.atan2(difference[1], planar))
            angles = (max(-1.,min(1.,yaw)),max(-0.5,min(0.5,(pitch-16.)/90.)))
            self._camera_angles = angles
            self.cameraAimChanged.emit(angles)
            self.update()
            return
        camera = self._drag_role == 'camera'
        if camera:
            coords = list(self._eye())
        else:
            offset = self._active*3
            coords = list(self._path_point(self._active))
        if self._drag_axis == 'depth':
            z = self._drag_start_z + (position.x()-self._drag_start.x())/52.
            coords[2]=max(-1.,min(1.,z))
        else:
            z=coords[2]
            x=(position.x()-self.width()*.5+38.*z)/67.
            y=(139.+21.*z+13.*x-position.y())/62.
            coords[0]=max(-1.,min(1.,x))
            coords[1]=max(-1.,min(1.,y))
        if camera:
            self._camera_offset=tuple(max(-8.,min(8.,coords[i]-self._base_eye[i])) for i in range(3))
            if self._camera_only:
                self._coords=list(self._camera_offset)
                self._changed(commit=False)
            else:
                self.cameraOffsetChanged.emit(self._camera_offset)
                self.update()
        else:
            self._coords[self._active*3:self._active*3+3]=coords
            if self._active == 0 and self._linked_source is not None:
                self._linked_source = tuple(coords)
                self.linkedSourceChanged.emit(tuple(coords))
            self._changed(commit=False)

    def mousePressEvent(self,event):
        if event.button() not in (Qt.MouseButton.LeftButton,Qt.MouseButton.RightButton) or not self.isEnabled():
            return super().mousePressEvent(event)
        pos=event.position()
        cam=self._marker(self._eye())
        aim=self._marker(self._aim())
        is_aim=(aim.x()-pos.x())**2+(aim.y()-pos.y())**2 < 12.**2
        is_cam=(self._camera_only or (cam.x()-pos.x())**2+(cam.y()-pos.y())**2 < 14.**2) and not is_aim
        if not is_cam:
            self._active=min(range(2),key=lambda i:(self._marker(self._path_point(i)).x()-pos.x())**2 + (self._marker(self._path_point(i)).y()-pos.y())**2)
        self._drag_role='aim' if is_aim else ('camera' if is_cam else 'path')
        self._drag_axis='depth' if event.button()==Qt.MouseButton.RightButton or event.modifiers()&Qt.KeyboardModifier.ShiftModifier else 'xy'
        self._drag_start=pos
        self._drag_start_z=(self._eye()[2] if is_cam else self._coords[self._active*3+2])
        self._dragging=True
        self._moved_in_drag=False
        self.update()

    def mouseMoveEvent(self,event):
        if self._dragging:
            self._move_to(event.position())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._dragging and self._drag_role == 'aim':
            self._dragging=False
            self.cameraAimCommitted.emit(self._camera_angles)
            self.update()
            return
        if self._dragging and self._drag_role == 'path' and self._active == 0 and self._linked_source is not None:
            self.linkedSourceCommitted.emit(tuple(self._linked_source))
        if self._dragging and self._drag_role=='camera' and not self._camera_only:
            self._dragging=False
            self.cameraOffsetCommitted.emit(self._camera_offset)
            self.update()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self,event):
        key=event.key()
        if key==Qt.Key.Key_Tab and not self._camera_only:
            self._active=1-self._active
            self.update()
            event.accept()
            return
        step=.015 if event.modifiers()&Qt.KeyboardModifier.ShiftModifier else .05
        axis,delta={Qt.Key.Key_Left:(0,-step),Qt.Key.Key_Right:(0,step),
                    Qt.Key.Key_Up:(1,step),Qt.Key.Key_Down:(1,-step),
                    Qt.Key.Key_PageUp:(2,step),Qt.Key.Key_PageDown:(2,-step)}.get(key,(None,0))
        if axis is None:
            return super().keyPressEvent(event)
        index=(0 if self._camera_only else self._active*3)+axis
        if self._camera_only:
            # Keyboard editing moves the real eye INSIDE the same authored
            # world volume, regardless of how far the orbit baseline begins.
            proposed=self._base_eye[axis]+self._coords[index]+delta
            self._coords[index]=max(-8.,min(8.,max(-1.,min(1.,proposed))-self._base_eye[axis]))
            self._camera_offset=tuple(self._coords)
        else:
            self._coords[index]=max(-1.,min(1.,self._coords[index]+delta))
        self._changed(commit=True)
        event.accept()
