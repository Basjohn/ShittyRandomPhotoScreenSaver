"""Local, stroke-batched heightfield authoring; no renderer, timer or settings owner."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from rendering.gl_programs.heightfield import heightfield_basin, normalize_heightfield, sample_heightfield
from rendering.gl_programs.neon_terrain_extent import extend_heightfield, horizon_extension_cells
from ui.tabs.media import terrain_angled_view as angled
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


_SIDE_MARGIN = 12.0
_LABEL_MARGIN = 26.0
_MIN_SIDE = 220
_MAX_SIDE = 440


class TerrainCanvas(QWidget):
    terrain_changed = Signal(dict)
    history_changed = Signal()
    HISTORY_LIMIT = 32

    def __init__(self, default_terrain, parent=None):
        super().__init__(parent)
        self._default = normalize_heightfield(default_terrain)
        self._size = self._default["size"]
        self._heights = list(self._default["heights"])
        self._basin = heightfield_basin(self._default)
        self._undo, self._redo = [], []
        self._before = None
        self._last_uv = None
        self._hover = None
        self._image = None
        self._angled = None          # (QImage, projection) of the angled view, rebuilt on change
        self.view = "Top"            # "Top" (the authoring map) or "Angled" (the scene's proportions)
        self._yaw, self._pitch = angled.DEFAULT_YAW, angled.DEFAULT_PITCH
        self._orbit = None
        self.mode = "Raise"
        self.radius = 0.12
        self.strength = 0.35
        self.falloff = 0.5
        self.flatten_height = 0.20
        self._carry = 0.0
        self.setMinimumSize(280, _LABEL_MARGIN * 2 + _MIN_SIDE)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Paint land or restore exact base-level water. Far/back is at the top; near/front is at the bottom.")

    def hasHeightForWidth(self) -> bool:  # type: ignore[override]
        return True

    def heightForWidth(self, width: int) -> int:  # type: ignore[override]
        # A square authoring field as wide as the panel allows, up to a comfortable size.
        side = max(_MIN_SIDE, min(_MAX_SIDE, width - 2 * _SIDE_MARGIN))
        if self.view == "Angled":
            side *= 0.72      # the basin is wider than deep: the angled picture is a landscape
        return int(side + 2 * _LABEL_MARGIN)

    def sizeHint(self):  # type: ignore[override]
        from PySide6.QtCore import QSize
        return QSize(_MAX_SIDE + 2 * _SIDE_MARGIN, self.heightForWidth(_MAX_SIDE + 2 * _SIDE_MARGIN))

    def field_rect(self):
        """The square heightmap field, centred: one heightmap cell is square on screen, so a round brush is
        round in the terrain's own cells whatever the panel's shape (the stored heights are never resampled)."""
        area = QRectF(self.rect()).adjusted(_SIDE_MARGIN, _LABEL_MARGIN, -_SIDE_MARGIN, -_LABEL_MARGIN)
        side = max(1.0, min(area.width(), area.height()))
        return QRectF(area.center().x() - side / 2.0, area.center().y() - side / 2.0, side, side)

    def _invalidate(self):
        self._image = None
        self._angled = None

    def set_view(self, view: str):
        """Top or Angled; both paint the same heights with the same brush."""
        self._cancel_stroke()
        self.view = view
        self._hover = None
        self.updateGeometry()
        self.update()

    def get_heightfield(self):
        record = {"version": 1, "size": self._size, "heights": list(self._heights)}
        if self._basin != (0, 0, self._size - 1):
            record["basin"] = list(self._basin)
        return record

    def set_heightfield(self, value):
        data = normalize_heightfield(value)
        self._size, self._heights = data["size"], data["heights"]
        self._basin = heightfield_basin(data)
        self._undo.clear()
        self._redo.clear()
        self._before = self._last_uv = None
        self._invalidate()
        self.history_changed.emit()
        self.update()

    def _snapshot(self):
        return self._size, tuple(self._heights), self._basin

    def _restore(self, state):
        self._size, values, self._basin = state
        self._heights = list(values)
        self._invalidate()
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
        self._restore((self._default["size"], tuple(self._default["heights"]), heightfield_basin(self._default)))
        self._commit(before)

    def can_extend(self) -> bool:
        return horizon_extension_cells(self.get_heightfield()) is not None

    def extend_toward_horizon(self):
        """Grow the grid back and to the sides; existing cells are kept exactly and the new ones take the
        continuation's heights, keeping the landforms' shape. One undoable step."""
        self._cancel_stroke()
        cells = horizon_extension_cells(self.get_heightfield())
        if cells is None:
            return
        before = self._snapshot()
        extended = extend_heightfield(self.get_heightfield(), *cells)
        self._restore((extended["size"], tuple(extended["heights"]), heightfield_basin(extended)))
        self._commit(before)

    def _cancel_stroke(self):
        if self._before is not None:
            self._restore(self._before)
        self._before = self._last_uv = None
        self._carry = 0.0

    def _uv(self, point):
        """The grid uv under ``point``; None over the angled view's sky."""
        if self.view == "Angled":
            return angled.pick_uv(self._angled_view()[1], (point.x(), point.y()))
        rect = self.field_rect()
        return (max(0.0, min(1.0, (point.x() - rect.left()) / rect.width())),
                max(0.0, min(1.0, (rect.bottom() - point.y()) / rect.height())))

    def _on_field(self, point) -> bool:
        if self.view == "Angled":
            return self._uv(point) is not None
        return self.field_rect().contains(point)

    def _angled_rect(self):
        return QRectF(self.rect()).adjusted(_SIDE_MARGIN, _LABEL_MARGIN, -_SIDE_MARGIN, -_LABEL_MARGIN)

    def _angled_view(self):
        """The angled view's cached picture and projection (rebuilt after any change)."""
        size = (self.width(), self.height())
        if self._angled is None or self._angled[2] != size:
            area = self._angled_rect()
            projection = angled.project_terrain(self._size, self._heights, self._basin,
                                                (area.left(), area.top(), area.width(), area.height()),
                                                yaw=self._yaw, pitch=self._pitch)
            self._angled = (self._paint_angled_terrain(projection), projection, size)
        return self._angled[0], self._angled[1]

    def _paint_angled_terrain(self, projection):
        image = QImage(max(1, self.width()), max(1, self.height()), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        grid = np.asarray(self._heights, dtype=np.float64).reshape(self._size, self._size)
        stride_index = np.unique(np.r_[np.arange(0, self._size, projection.stride), self._size - 1])
        corner = grid[np.ix_(stride_index, stride_index)]
        mean = (corner[:-1, :-1] + corner[1:, :-1] + corner[:-1, 1:] + corner[1:, 1:]) / 4.0
        light = angled.quad_light(projection)
        screen = projection.screen
        for row, col in angled.quad_order(projection):
            height, shade = float(mean[row, col]), 0.5 + 0.5 * float(light[row, col])
            if height <= 0.0:
                base, shade = _WATER_COLOR, 0.85 + 0.15 * shade
            else:
                t = max(0.0, min(1.0, height ** 0.84))
                base = QColor(round(_LAND_LOW.red() + (_LAND_HIGH.red() - _LAND_LOW.red()) * t),
                              round(_LAND_LOW.green() + (_LAND_HIGH.green() - _LAND_LOW.green()) * t),
                              round(_LAND_LOW.blue() + (_LAND_HIGH.blue() - _LAND_LOW.blue()) * t))
            colour = QColor(round(base.red() * shade), round(base.green() * shade), round(base.blue() * shade))
            painter.setPen(QPen(colour, 1.0))    # the outline closes antialiasing seams between quads
            painter.setBrush(colour)
            painter.drawPolygon(QPolygonF([QPointF(*screen[r, c]) for r, c in
                                           ((row, col), (row, col + 1), (row + 1, col + 1), (row + 1, col))]))
        if self._basin != (0, 0, self._size - 1):
            # The scene's basin, draped over the ground of a grid reaching toward the horizon.
            x0, y0, cells = self._basin
            n1 = self._size - 1
            corners = [(x0 / n1, y0 / n1), ((x0 + cells) / n1, y0 / n1), ((x0 + cells) / n1, (y0 + cells) / n1),
                       (x0 / n1, (y0 + cells) / n1)]
            outline = []
            for (ua, va), (ub, vb) in zip(corners, corners[1:] + corners[:1]):
                outline.extend((ua + (ub - ua) * k / 24.0, va + (vb - va) * k / 24.0) for k in range(24))
            outline.append(corners[0])
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(_LABEL_COLOR, 1.2, Qt.PenStyle.DashLine))
            painter.drawPolyline(self._draped(projection, outline))
        painter.end()
        return image

    def _draped(self, projection, uvs) -> QPolygonF:
        """Screen points of grid ``uvs`` resting on the terrain."""
        record = {"size": self._size, "heights": self._heights}
        u = np.array([p[0] for p in uvs])
        v = np.array([p[1] for p in uvs])
        h = np.array([sample_heightfield(record, a, b) for a, b in uvs])
        screen, _depth = projection.project(angled.world_points(self._size, self._basin, u, v, h))
        return QPolygonF([QPointF(float(x), float(y)) for x, y in screen])

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
        self._invalidate()
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
        if event.button() == Qt.MouseButton.RightButton and self.view == "Angled":
            self._orbit = (QPointF(event.position()), self._yaw, self._pitch)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._on_field(event.position()):
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
        if self._orbit is not None:
            # Right-drag turns the angled view (in memory only; nothing is saved).
            start, yaw, pitch = self._orbit
            delta = event.position() - start
            self._yaw = max(angled.YAW_RANGE[0], min(angled.YAW_RANGE[1], yaw - delta.x() * 0.008))
            self._pitch = max(angled.PITCH_RANGE[0], min(angled.PITCH_RANGE[1], pitch + delta.y() * 0.008))
            self._angled = None
            self.update()
            event.accept()
            return
        self._hover = QPointF(event.position()) if self._on_field(event.position()) else None
        if self._before is not None:
            uv = self._uv(event.position())
            if uv is not None:
                self._stroke_to(uv)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self._orbit is not None:
            self._orbit = None
            event.accept()
            return
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
        if self.view == "Angled":
            self._paint_angled()
            return
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
        if self._basin != (0, 0, self._size - 1):
            # The scene's basin inside a grid that reaches toward the horizon.
            x0, y0, cells = self._basin
            n1 = self._size - 1
            basin = QRectF(rect.left() + rect.width() * x0 / n1, rect.bottom() - rect.height() * (y0 + cells) / n1,
                           rect.width() * cells / n1, rect.height() * cells / n1)
            painter.setPen(QPen(_LABEL_COLOR, 1.2, Qt.PenStyle.DashLine))
            painter.drawRect(basin)
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

    def _paint_angled(self):
        image, projection = self._angled_view()
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BG_COLOR)
        painter.drawImage(0, 0, image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(_LABEL_COLOR)
        painter.drawText(QRectF(12.0, 2.0, self.width() - 24.0, 20.0), Qt.AlignmentFlag.AlignCenter, "FAR / BACK")
        painter.drawText(QRectF(12.0, self.height() - 23.0, self.width() - 24.0, 20.0), Qt.AlignmentFlag.AlignCenter,
                         "NEAR / FRONT  •  Right-drag to turn the view")
        uv = self._uv(self._hover) if self._hover is not None else None
        if uv is None:
            return
        # The brush's rim (dashed) and flat core (solid), draped over the ground.
        radius = self._radius()
        for extent, style, width in ((brush_reach(self.falloff), Qt.PenStyle.DashLine, 1.5),
                                     (1.0 - max(0.0, min(1.0, self.falloff)), Qt.PenStyle.SolidLine, 1.0)):
            if extent * radius <= 1e-3:
                continue
            ring = [(max(0.0, min(1.0, uv[0] + extent * radius * math.cos(a))),
                     max(0.0, min(1.0, uv[1] + extent * radius * math.sin(a))))
                    for a in np.linspace(0.0, 2.0 * math.pi, 49)]
            painter.setPen(QPen(_CURSOR_COLOR, width, style))
            painter.drawPolyline(self._draped(projection, ring))
        height = sample_heightfield({"size": self._size, "heights": self._heights}, *uv)
        painter.drawText(self._angled_rect().adjusted(8.0, 6.0, -8.0, -6.0),
                         Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
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
        self.view = StyledComboBox(size_variant="compact")
        self.view.addItems(["Top", "Angled"])
        self.view.setToolTip("Top: the authoring map. Angled: the terrain in the scene's own proportions; paint on "
                             "it directly, right-drag to turn it.")
        tools.addWidget(QLabel("View:"), 0, 2)
        tools.addWidget(self.view, 0, 3)
        self.canvas = TerrainCanvas(default_terrain, self)
        self.view.currentTextChanged.connect(self.canvas.set_view)
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
        self.extend_button = QPushButton("Extend Toward Horizon")
        self.extend_button.setToolTip("Grow the editable terrain further back and to the sides (dashed: the "
                                      "original basin). New ground keeps the shape already there; water painted "
                                      "to the edge keeps flowing to the horizon.")
        for button, callback in ((self.undo_button, self.canvas.undo), (self.redo_button, self.canvas.redo),
                                 (self.extend_button, self.canvas.extend_toward_horizon),
                                 (self.reset_button, self.canvas.reset_default)):
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
        self.extend_button.setEnabled(self.canvas.can_extend())

    def set_heightfield(self, value):
        self.canvas.set_heightfield(value)

    def get_heightfield(self):
        return self.canvas.get_heightfield()
