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

# Brush model. Distances are in brush radii, measured physically (against the field's shorter side),
# so a stroke's effect depends on its path, never on mouse speed or event granularity.
DAB_SPACING = 0.15        # radii between dabs along a stroke
PRESS_DEPOSIT = 0.25      # a press that never moves applies this much stroke (in radii), once
MAX_RATE = 0.5            # height Raise/Lower add per radius of stroke at 100% strength
FLATTEN_RATE = 6.0        # Flatten's approach per radius of stroke at 100% (100% itself snaps the core)
MIN_LAND = 0.005          # Lower never turns land into water; only the Water brush authors exact zero


def brush_weight(distance: float, falloff: float) -> float:
    """The brush profile at ``distance`` radii: flat in a core of (1 - falloff), then a cosine skirt
    that reaches a little past the drawn radius as falloff grows (hard disc at 0)."""
    falloff = max(0.0, min(1.0, float(falloff)))
    core, outer = 1.0 - falloff, 1.0 + 0.5 * falloff
    if distance <= core:
        return 1.0
    if distance >= outer:
        return 0.0
    return 0.5 * (1.0 + math.cos(math.pi * (distance - core) / (outer - core)))


def brush_reach(falloff: float) -> float:
    """How far (in radii) the brush touches anything."""
    return 1.0 + 0.5 * max(0.0, min(1.0, float(falloff)))


def stroke_rate(strength: float) -> float:
    """Height per radius of stroke: quadratic, so low strengths are genuinely gradual."""
    strength = max(0.0, min(1.0, float(strength)))
    return MAX_RATE * strength * strength


def apply_brush(old: float, mode: str, weight: float, amount: float, strength: float, target: float) -> float:
    """One dab's effect on one height; ``amount`` is the stroke length it stands for, in radii."""
    if weight <= 0.0:
        return old
    if mode == "Water":
        return 0.0 if weight >= 0.5 else old   # water is authored zero, inside the brush's half-weight contour
    if mode == "Flatten":
        target = max(0.0, min(1.0, float(target)))
        if old > 0.0:
            target = max(MIN_LAND, target)
        if strength >= 1.0:
            share = weight
        else:
            share = 1.0 - math.exp(-FLATTEN_RATE * strength * strength * weight * amount)
        return max(0.0, min(1.0, old + (target - old) * share))
    delta = stroke_rate(strength) * weight * amount
    if mode == "Lower":
        if old <= 0.0:
            return old
        return max(MIN_LAND, old - delta)
    return min(1.0, old + delta)


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
        self.strength = 0.35
        self.falloff = 0.5
        self.flatten_height = 0.20
        self._carry = 0.0
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
        self._carry = 0.0

    def _uv(self, point):
        rect = self.field_rect()
        return (max(0.0, min(1.0, (point.x() - rect.left()) / rect.width())),
                max(0.0, min(1.0, (rect.bottom() - point.y()) / rect.height())))

    def _radius(self) -> float:
        return max(0.03, min(0.35, float(self.radius)))

    def _physical(self, du: float, dv: float) -> float:
        """A uv offset's length in brush radii (against the shorter side: a round brush)."""
        rect = self.field_rect()
        return math.hypot(du * rect.width(), dv * rect.height()) / (self._radius() * min(rect.width(), rect.height()))

    def _dab(self, u, v, amount):
        """One dab at (u, v) standing for ``amount`` radii of stroke."""
        n = self._size
        radius = self._radius()
        reach = radius * brush_reach(self.falloff)
        rect = self.field_rect()
        short = min(rect.width(), rect.height())
        reach_u, reach_v = reach * short / rect.width(), reach * short / rect.height()
        lower_x, upper_x = max(0, math.floor((u - reach_u) * (n - 1))), min(n - 1, math.ceil((u + reach_u) * (n - 1)))
        lower_y, upper_y = max(0, math.floor((v - reach_v) * (n - 1))), min(n - 1, math.ceil((v + reach_v) * (n - 1)))
        strength = max(0.01, min(1.0, float(self.strength)))
        for y in range(lower_y, upper_y + 1):
            for x in range(lower_x, upper_x + 1):
                weight = brush_weight(self._physical(x / (n - 1) - u, y / (n - 1) - v), self.falloff)
                if weight > 0.0:
                    index = y * n + x
                    self._heights[index] = apply_brush(self._heights[index], self.mode, weight, amount, strength,
                                                       self.flatten_height)
        self._image = None
        self.update()

    def _stroke_to(self, uv):
        """Dabs every DAB_SPACING radii along the path; the leftover distance carries to the next move."""
        u0, v0 = self._last_uv
        length = self._physical(uv[0] - u0, uv[1] - v0)
        if length <= 0.0:
            return
        position = DAB_SPACING - self._carry
        while position <= length:
            t = position / length
            self._dab(u0 + (uv[0] - u0) * t, v0 + (uv[1] - v0) * t, DAB_SPACING)
            position += DAB_SPACING
        self._carry = length - (position - DAB_SPACING)
        self._last_uv = uv

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.field_rect().contains(event.position()):
            self.setFocus()
            self._before = self._snapshot()
            self._last_uv = self._uv(event.position())
            self._carry = 0.0
            self._hover = QPointF(event.position())
            self._dab(*self._last_uv, PRESS_DEPOSIT)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._hover = QPointF(event.position()) if self.field_rect().contains(event.position()) else None
        if self._before is not None:
            self._stroke_to(self._uv(event.position()))
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._before is not None:
            before = self._before
            self._before = self._last_uv = None
            self._carry = 0.0
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
            # The flat core (solid) and where the soft skirt ends (dashed).
            brush_radius_px = min(rect.width(), rect.height()) * self._radius()
            core_px = brush_radius_px * (1.0 - max(0.0, min(1.0, self.falloff)))
            painter.setPen(QPen(_CURSOR_COLOR, 1.5, Qt.PenStyle.DashLine))
            reach_px = brush_radius_px * brush_reach(self.falloff)
            painter.drawEllipse(self._hover, reach_px, reach_px)
            if core_px >= 1.0:
                painter.setPen(QPen(_CURSOR_COLOR, 1.0))
                painter.drawEllipse(self._hover, core_px, core_px)
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
        tips = {
            "Radius": "The brush size.",
            "Strength": "How much a stroke changes the land per brush-width it travels. Low values build up "
                        "gently; Flatten snaps to its height only at 100%.",
            "Falloff": "How soft the brush edge is: 0 is a hard disc, higher values ease out over a wider rim "
                       "(the cursor shows the flat core and where the rim ends).",
            "Flatten Height": "The height Flatten moves land toward.",
        }
        for row, name, low, high, initial in ((1, "Radius", 3, 35, 12), (2, "Strength", 1, 100, 35),
                                              (3, "Falloff", 0, 100, 50), (4, "Flatten Height", 0, 100, 20)):
            slider = NoWheelSlider(Qt.Orientation.Horizontal)
            slider.setRange(low, high)
            slider.setValue(initial)
            text = QLabel(f"{initial}%")
            slider.setToolTip(tips[name])
            tools.addWidget(QLabel(f"{name}:"), row, 0)
            tools.addWidget(slider, row, 1)
            tools.addWidget(text, row, 2)
            attr = {"Radius": "radius", "Strength": "strength", "Falloff": "falloff",
                    "Flatten Height": "flatten_height"}[name]
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
