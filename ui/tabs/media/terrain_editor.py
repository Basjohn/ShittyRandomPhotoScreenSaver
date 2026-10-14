"""Local, stroke-batched heightfield authoring; no renderer, timer or settings owner."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rendering.gl_programs.heightfield import normalize_heightfield, sample_heightfield
from ui.tabs.shared_styles import NoWheelSlider
from ui.widgets import StyledComboBox


# Same dark-glass foundation, grid and labels as the Spectrum/Dev Curve editors.
# Terrain height stays a distinct muted ramp; zero stays unmistakably water.
_BG_COLOR = QColor(18, 18, 18, 240)
_GRID_COLOR = QColor(255, 255, 255, 18)
_GRID_MAJOR_COLOR = QColor(255, 255, 255, 35)
_BORDER_COLOR = QColor(255, 255, 255, 60)
_LABEL_COLOR = QColor(255, 255, 255, 100)
_CURSOR_COLOR = QColor(180, 200, 255, 220)
_WATER_COLOR = QColor(35, 78, 106)
_LAND_LOW = QColor(38, 44, 67)
_LAND_HIGH = QColor(178, 194, 239)


class TerrainCanvas(QWidget):
    terrain_changed = Signal(dict)
    history_changed = Signal()
    HISTORY_LIMIT = 32

    def __init__(self, default_terrain, parent=None):
        super().__init__(parent)
        self._default = normalize_heightfield(default_terrain)
        self._size = self._default["size"]
        self._heights = list(self._default["heights"])
        self._undo, self._redo = [], []
        self._before = None
        self._last_uv = None
        self._hover = None
        self._image = None
        self.mode = "Raise"
        self.radius = 0.12
        self.strength = 0.12
        self.flatten_height = 0.20
        self.setMinimumSize(280, 220)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Paint land or restore exact base-level water. Far/back is at the top; near/front is at the bottom.")

    def field_rect(self):
        return QRectF(self.rect()).adjusted(12.0, 26.0, -12.0, -26.0)

    def get_heightfield(self):
        return {"version": 1, "size": self._size, "heights": list(self._heights)}

    def set_heightfield(self, value):
        data = normalize_heightfield(value)
        self._size, self._heights = data["size"], data["heights"]
        self._undo.clear()
        self._redo.clear()
        self._before = self._last_uv = None
        self._image = None
        self.history_changed.emit()
        self.update()

    def _snapshot(self):
        return self._size, tuple(self._heights)

    def _restore(self, state):
        self._size, values = state
        self._heights = list(values)
        self._image = None
        self.update()

    def _commit(self, before):
        if self._snapshot() == before:
            return
        self._undo.append(before)
        del self._undo[:-self.HISTORY_LIMIT]
        self._redo.clear()
        self.history_changed.emit()
        self.terrain_changed.emit(self.get_heightfield())

    def undo(self):
        if self._before is not None or not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        self.history_changed.emit()
        self.terrain_changed.emit(self.get_heightfield())

    def redo(self):
        if self._before is not None or not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        self.history_changed.emit()
        self.terrain_changed.emit(self.get_heightfield())

    def reset_default(self):
        self._cancel_stroke()
        before = self._snapshot()
        self._restore((self._default["size"], tuple(self._default["heights"])))
        self._commit(before)

    def _cancel_stroke(self):
        if self._before is not None:
            self._restore(self._before)
        self._before = self._last_uv = None

    def _uv(self, point):
        rect = self.field_rect()
        return (max(0.0, min(1.0, (point.x() - rect.left()) / rect.width())),
                max(0.0, min(1.0, (rect.bottom() - point.y()) / rect.height())))

    def _dab(self, u, v):
        n = self._size
        radius = max(0.03, min(0.35, float(self.radius)))
        strength = max(0.01, min(0.50, float(self.strength)))
        lower_x, upper_x = max(0, math.floor((u - radius) * (n - 1))), min(n - 1, math.ceil((u + radius) * (n - 1)))
        lower_y, upper_y = max(0, math.floor((v - radius) * (n - 1))), min(n - 1, math.ceil((v + radius) * (n - 1)))
        rect = self.field_rect()
        width, height = rect.width(), rect.height()
        for y in range(lower_y, upper_y + 1):
            for x in range(lower_x, upper_x + 1):
                # Radius is measured against the shorter screen-space side: a
                # physically round dab, not an ellipse stretched with the editor.
                distance = math.hypot((x / (n - 1) - u) * width,
                                      (y / (n - 1) - v) * height) / (radius * min(width, height))
                if distance > 1.0:
                    continue
                index = y * n + x
                weight = (1.0 - distance * distance) ** 2
                old = self._heights[index]
                if self.mode == "Water":
                    value = 0.0  # water is authored zero, never an asymptotic lower brush
                elif self.mode == "Flatten":
                    value = old + (max(0.0, min(1.0, self.flatten_height)) - old) * min(1.0, strength * 4.0 * weight)
                else:
                    value = old + strength * weight * (-1.0 if self.mode == "Lower" else 1.0)
                self._heights[index] = max(0.0, min(1.0, value))
        self._image = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.field_rect().contains(event.position()):
            self.setFocus()
            self._before = self._snapshot()
            self._last_uv = self._uv(event.position())
            self._hover = QPointF(event.position())
            self._dab(*self._last_uv)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover = QPointF(event.position()) if self.field_rect().contains(event.position()) else None
        if self._before is not None:
            uv = self._uv(event.position())
            distance = math.dist(uv, self._last_uv)
            steps = max(1, min(128, math.ceil(distance / max(0.01, self.radius * 0.25))))
            for step in range(1, steps + 1):
                t = step / steps
                self._dab(self._last_uv[0] * (1.0 - t) + uv[0] * t, self._last_uv[1] * (1.0 - t) + uv[1] * t)
            self._last_uv = uv
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._before is not None:
            before = self._before
            self._before = self._last_uv = None
            self._commit(before)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hover = None
        self.update()
        super().leaveEvent(event)

    def hideEvent(self, event):
        self._cancel_stroke()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_stroke()
            event.accept()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z:
            self.redo() if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else self.undo()
            event.accept()
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Y:
            self.redo()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        # Cached pixels change only on a stroke/load, not on every pointer move.
        if self._image is None:
            n = self._size
            self._image = QImage(n, n, QImage.Format.Format_ARGB32)
            for y in range(n):
                for x in range(n):
                    height = self._heights[(n - 1 - y) * n + x]
                    if height == 0.0:
                        colour = _WATER_COLOR
                    else:
                        t = max(0.0, min(1.0, height ** 0.84))
                        colour = QColor(
                            round(_LAND_LOW.red() + (_LAND_HIGH.red() - _LAND_LOW.red()) * t),
                            round(_LAND_LOW.green() + (_LAND_HIGH.green() - _LAND_LOW.green()) * t),
                            round(_LAND_LOW.blue() + (_LAND_HIGH.blue() - _LAND_LOW.blue()) * t),
                        )
                    self._image.setPixelColor(x, y, colour)
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BG_COLOR)
        rect = self.field_rect()
        painter.drawImage(rect, self._image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for step in range(1, 8):
            fraction = step / 8.0
            painter.setPen(QPen(_GRID_MAJOR_COLOR if step == 4 else _GRID_COLOR, 1.0))
            painter.drawLine(QPointF(rect.left() + fraction * rect.width(), rect.top()),
                             QPointF(rect.left() + fraction * rect.width(), rect.bottom()))
            painter.drawLine(QPointF(rect.left(), rect.top() + fraction * rect.height()),
                             QPointF(rect.right(), rect.top() + fraction * rect.height()))
        painter.setPen(QPen(_BORDER_COLOR, 1.0))
        painter.drawRect(rect)
        painter.setPen(_LABEL_COLOR)
        painter.drawText(QRectF(12.0, 2.0, self.width() - 24.0, 20.0), Qt.AlignmentFlag.AlignCenter, "FAR / BACK")
        painter.drawText(QRectF(12.0, self.height() - 23.0, self.width() - 24.0, 20.0), Qt.AlignmentFlag.AlignCenter,
                         "NEAR / FRONT  •  Blue: base water  •  Light: higher land")
        if self._hover is not None:
            painter.setPen(QPen(_CURSOR_COLOR, 1.5, Qt.PenStyle.DashLine))
            brush_radius_px = min(rect.width(), rect.height()) * self.radius
            painter.drawEllipse(self._hover, brush_radius_px, brush_radius_px)
            u, v = self._uv(self._hover)
            height = sample_heightfield({"size": self._size, "heights": self._heights}, u, v)
            painter.drawText(rect.adjusted(8.0, 6.0, -8.0, -6.0), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                             f"{self.mode}  •  {'WATER' if height == 0.0 else f'Height {height:.0%}'}")


class TerrainEditor(QWidget):
    terrain_changed = Signal(dict)

    def __init__(self, default_terrain, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        tools = QGridLayout()
        layout.addLayout(tools)
        self.mode = StyledComboBox(size_variant="compact")
        self.mode.addItems(["Raise", "Lower", "Flatten", "Water"])
        tools.addWidget(QLabel("Brush:"), 0, 0)
        tools.addWidget(self.mode, 0, 1)
        self.canvas = TerrainCanvas(default_terrain, self)
        for row, name, low, high, initial in ((1, "Radius", 3, 35, 12), (2, "Strength", 1, 50, 12), (3, "Flatten Height", 0, 100, 20)):
            slider = NoWheelSlider(Qt.Orientation.Horizontal)
            slider.setRange(low, high)
            slider.setValue(initial)
            text = QLabel(f"{initial}%")
            tools.addWidget(QLabel(f"{name}:"), row, 0)
            tools.addWidget(slider, row, 1)
            tools.addWidget(text, row, 2)
            attr = {"Radius": "radius", "Strength": "strength", "Flatten Height": "flatten_height"}[name]
            slider.valueChanged.connect(lambda value, attr=attr, text=text: (setattr(self.canvas, attr, value / 100.0), text.setText(f"{value}%"), self.canvas.update()))
            setattr(self, attr, slider)
        self.flatten_height.setEnabled(False)
        self.mode.currentTextChanged.connect(lambda mode: (setattr(self.canvas, "mode", mode), self.flatten_height.setEnabled(mode == "Flatten"), self.canvas.update()))
        actions = QHBoxLayout()
        self.undo_button, self.redo_button = QPushButton("Undo"), QPushButton("Redo")
        self.reset_button = QPushButton("Reset Terrain to Default")
        for button, callback in ((self.undo_button, self.canvas.undo), (self.redo_button, self.canvas.redo), (self.reset_button, self.canvas.reset_default)):
            actions.addWidget(button)
            button.clicked.connect(callback)
        layout.addLayout(actions)
        layout.addWidget(self.canvas)
        self.canvas.terrain_changed.connect(self.terrain_changed)
        self.canvas.history_changed.connect(self._refresh_history)
        self._refresh_history()

    def _refresh_history(self):
        self.undo_button.setEnabled(bool(self.canvas._undo))
        self.redo_button.setEnabled(bool(self.canvas._redo))

    def set_heightfield(self, value):
        self.canvas.set_heightfield(value)

    def get_heightfield(self):
        return self.canvas.get_heightfield()
