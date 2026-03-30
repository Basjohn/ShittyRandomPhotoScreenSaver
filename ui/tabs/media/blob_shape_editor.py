"""Blob Shaper spatial editor -- two side-by-side square polar editors + energy palette.

Each square contains a circle/ring preview.  Draggable nodes on the circle
perimeter define the base shape (left) and reaction limit (right).  An energy
source palette at the bottom supports click-to-place: clicking a source chip
sets a placement mode, then clicking inside either editor places the node.
"""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QMouseEvent, QPaintEvent, QPolygonF,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy,
)

from core.logging.logger import get_logger

logger = get_logger(__name__)

ENERGY_TYPES: list[tuple[str, QColor]] = [
    ("bass", QColor(220, 50, 50)),
    ("mid", QColor(50, 180, 50)),
    ("vocals", QColor(80, 120, 255)),
    ("treble", QColor(220, 180, 40)),
    ("transient", QColor(200, 80, 220)),
]

_NODE_RADIUS = 5
_ENERGY_NODE_RADIUS = 6
_EDITOR_SIZE = 270
_CIRCLE_RADIUS = 90
_BORDER_COLOR = QColor(255, 255, 255, 45)
_RING_INNER_COLOR = QColor(20, 20, 26)
_SNAP_DISTANCE_PX = 14


def _energy_color(etype: str) -> QColor:
    for name, color in ENERGY_TYPES:
        if name == etype:
            return color
    return QColor(180, 180, 180)


class _PolarEditorCanvas(QWidget):
    """Square canvas that draws a circle and draggable profile nodes."""

    nodes_changed = Signal()
    energy_placed = Signal(str, float, float)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._nodes: list[list[float]] = [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]]
        self._energy_nodes: list[dict[str, Any]] = []
        self._drag_idx: int = -1
        self._drag_energy_idx: int = -1
        self._ring_mode: bool = False
        self._ring_thickness: float = 0.3
        self._placement_type: str | None = None
        self.setMinimumSize(_EDITOR_SIZE, _EDITOR_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(_EDITOR_SIZE, _EDITOR_SIZE)
        self.setMouseTracking(True)

    def set_profile_nodes(self, nodes: list[list[float]]) -> None:
        self._nodes = [list(n) for n in nodes] if nodes else [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]]
        self.update()

    def get_profile_nodes(self) -> list[list[float]]:
        return [list(n) for n in self._nodes]

    def set_energy_nodes(self, nodes: list[dict[str, Any]]) -> None:
        self._energy_nodes = [dict(n) for n in nodes] if nodes else []
        self.update()

    def get_energy_nodes(self) -> list[dict[str, Any]]:
        return [dict(n) for n in self._energy_nodes]

    def set_ring_mode(self, ring: bool, thickness: float = 0.3) -> None:
        self._ring_mode = ring
        self._ring_thickness = max(0.05, min(1.0, thickness))
        self.update()

    def set_placement_type(self, etype: str | None) -> None:
        self._placement_type = etype
        self.setCursor(
            Qt.CursorShape.CrossCursor if etype else Qt.CursorShape.ArrowCursor
        )

    def _center(self) -> QPointF:
        s = min(self.width(), self.height())
        return QPointF(s / 2.0, s / 2.0)

    def _radius(self) -> float:
        return _CIRCLE_RADIUS

    def _node_to_screen(self, angle_frac: float, radius_mult: float) -> QPointF:
        c = self._center()
        r = self._radius() * max(0.1, min(2.0, radius_mult))
        angle = angle_frac * 2.0 * math.pi - math.pi / 2.0
        return QPointF(c.x() + r * math.cos(angle), c.y() + r * math.sin(angle))

    def _screen_to_node(self, pos: QPointF) -> tuple[float, float]:
        c = self._center()
        dx = pos.x() - c.x()
        dy = pos.y() - c.y()
        angle = math.atan2(dy, dx) + math.pi / 2.0
        if angle < 0:
            angle += 2.0 * math.pi
        angle_frac = angle / (2.0 * math.pi)
        dist = math.hypot(dx, dy)
        radius_mult = max(0.1, min(2.0, dist / max(1.0, self._radius())))
        return (angle_frac % 1.0, radius_mult)

    def _energy_node_to_screen(self, node: dict) -> QPointF:
        ex = float(node.get("x", 0.5))
        ey = float(node.get("y", 0.5))
        s = min(self.width(), self.height())
        return QPointF(ex * s, ey * s)

    def _screen_to_energy_pos(self, pos: QPointF) -> tuple[float, float]:
        s = max(1.0, min(self.width(), self.height()))
        ex = max(0.0, min(1.0, pos.x() / s))
        ey = max(0.0, min(1.0, pos.y() / s))
        return (ex, ey)

    def _snap_energy_to_profile(self, screen_pos: QPointF) -> QPointF | None:
        """If screen_pos is close to a profile node or line segment, return snapped pos."""
        # Snap to profile nodes first
        for node in self._nodes:
            sp = self._node_to_screen(node[0], node[1])
            if (screen_pos - sp).manhattanLength() < _SNAP_DISTANCE_PX:
                return sp
        # Snap to profile line segments
        if len(self._nodes) >= 2:
            sorted_nodes = sorted(self._nodes, key=lambda n: n[0])
            steps = max(len(sorted_nodes) * 8, 64)
            best_dist = _SNAP_DISTANCE_PX
            best_pt: QPointF | None = None
            for i in range(steps):
                t = i / steps
                lo_idx = 0
                for j in range(len(sorted_nodes) - 1):
                    if sorted_nodes[j][0] <= t:
                        lo_idx = j
                lo = sorted_nodes[lo_idx]
                hi = sorted_nodes[min(lo_idx + 1, len(sorted_nodes) - 1)]
                seg = hi[0] - lo[0]
                frac = (t - lo[0]) / seg if seg > 1e-6 else 0.0
                frac = max(0.0, min(1.0, frac))
                rm = lo[1] + (hi[1] - lo[1]) * frac
                sp = self._node_to_screen(t, rm)
                d = (screen_pos - sp).manhattanLength()
                if d < best_dist:
                    best_dist = d
                    best_pt = sp
            return best_pt
        return None

    def _hit_test_profile(self, pos: QPointF) -> int:
        for i, node in enumerate(self._nodes):
            sp = self._node_to_screen(node[0], node[1])
            if (pos - sp).manhattanLength() < _NODE_RADIUS * 2.5:
                return i
        return -1

    def _hit_test_energy(self, pos: QPointF) -> int:
        for i, node in enumerate(self._energy_nodes):
            sp = self._energy_node_to_screen(node)
            if (pos - sp).manhattanLength() < _ENERGY_NODE_RADIUS * 2.5:
                return i
        return -1

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = min(self.width(), self.height())
        c = self._center()
        r = self._radius()

        # Background
        p.fillRect(self.rect(), QColor(30, 30, 38))

        if self._ring_mode:
            inner_r = r * max(0.05, 1.0 - self._ring_thickness)
            # Draw ring band: fill between outer and inner circle
            # Outer circle filled with semi-transparent band color
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(50, 80, 120, 30)))
            p.drawEllipse(c, r, r)
            # Inner circle (hollow center) filled dark
            p.setBrush(QBrush(_RING_INNER_COLOR))
            p.drawEllipse(c, inner_r, inner_r)
            # Draw reference circles as dashed outlines
            p.setPen(QPen(QColor(70, 70, 90), 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, r, r)
            p.setPen(QPen(QColor(90, 70, 70), 1.0, Qt.PenStyle.DashLine))
            p.drawEllipse(c, inner_r, inner_r)
        else:
            p.setPen(QPen(QColor(70, 70, 90), 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, r, r)

        # Profile shape polygon
        if len(self._nodes) >= 2:
            pts = []
            steps = max(len(self._nodes) * 8, 64)
            sorted_nodes = sorted(self._nodes, key=lambda n: n[0])
            for i in range(steps):
                t = i / steps
                lo_idx = 0
                for j in range(len(sorted_nodes) - 1):
                    if sorted_nodes[j][0] <= t:
                        lo_idx = j
                lo = sorted_nodes[lo_idx]
                hi = sorted_nodes[min(lo_idx + 1, len(sorted_nodes) - 1)]
                seg = hi[0] - lo[0]
                frac = (t - lo[0]) / seg if seg > 1e-6 else 0.0
                frac = max(0.0, min(1.0, frac))
                rm = lo[1] + (hi[1] - lo[1]) * frac
                sp = self._node_to_screen(t, rm)
                pts.append(sp)
            if pts:
                p.setPen(QPen(QColor(100, 200, 255, 160), 1.5))
                p.setBrush(QBrush(QColor(60, 140, 220, 40)))
                p.drawPolygon(QPolygonF(pts))

        # Profile nodes
        for node in self._nodes:
            sp = self._node_to_screen(node[0], node[1])
            p.setPen(QPen(QColor(255, 255, 255), 1.5))
            p.setBrush(QBrush(QColor(100, 200, 255)))
            p.drawEllipse(sp, _NODE_RADIUS, _NODE_RADIUS)

        # Energy nodes
        for node in self._energy_nodes:
            sp = self._energy_node_to_screen(node)
            color = _energy_color(str(node.get("type", "bass")))
            p.setPen(QPen(color.darker(120), 1.5))
            p.setBrush(QBrush(color))
            p.drawEllipse(sp, _ENERGY_NODE_RADIUS, _ENERGY_NODE_RADIUS)
            label = str(node.get("type", "?"))[0].upper()
            p.setPen(QPen(QColor(255, 255, 255)))
            font = p.font()
            font.setPixelSize(10)
            font.setBold(True)
            p.setFont(font)
            p.drawText(QRectF(sp.x() - 6, sp.y() - 6, 12, 12), Qt.AlignmentFlag.AlignCenter, label)

        # Title
        p.setPen(QPen(QColor(180, 180, 200)))
        font = p.font()
        font.setPixelSize(11)
        p.setFont(font)
        p.drawText(QRectF(4, 2, s - 8, 16), Qt.AlignmentFlag.AlignLeft, self._title)

        # 1px border
        p.setPen(QPen(_BORDER_COLOR, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1))

        # Placement mode indicator
        if self._placement_type:
            color = _energy_color(self._placement_type)
            p.setPen(QPen(color, 2.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(1, 1, self.width() - 2, self.height() - 2))

        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click: cancel placement or delete energy node
            if self._placement_type:
                self.set_placement_type(None)
                self.update()
                return
            eidx = self._hit_test_energy(pos)
            if eidx >= 0:
                self._energy_nodes.pop(eidx)
                self.nodes_changed.emit()
                self.update()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Placement mode: place energy node (snap to profile if close)
        if self._placement_type:
            snapped = self._snap_energy_to_profile(pos)
            place_pos = snapped if snapped else pos
            ex, ey = self._screen_to_energy_pos(place_pos)
            self._energy_nodes.append({"type": self._placement_type, "x": ex, "y": ey, "strength": 1.0})
            self.energy_placed.emit(self._placement_type, ex, ey)
            self.set_placement_type(None)
            self.nodes_changed.emit()
            self.update()
            return

        # Hit-test existing nodes
        eidx = self._hit_test_energy(pos)
        if eidx >= 0:
            self._drag_energy_idx = eidx
            self._drag_idx = -1
            return
        pidx = self._hit_test_profile(pos)
        if pidx >= 0:
            self._drag_idx = pidx
            self._drag_energy_idx = -1
            return
        # Double-click: add new profile node
        if event.type() == event.Type.MouseButtonDblClick:
            af, rm = self._screen_to_node(pos)
            self._nodes.append([af, rm])
            self._nodes.sort(key=lambda n: n[0])
            self.nodes_changed.emit()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if self._drag_idx >= 0 and self._drag_idx < len(self._nodes):
            af, rm = self._screen_to_node(pos)
            self._nodes[self._drag_idx] = [af, rm]
            self.nodes_changed.emit()
            self.update()
        elif self._drag_energy_idx >= 0 and self._drag_energy_idx < len(self._energy_nodes):
            snapped = self._snap_energy_to_profile(pos)
            place_pos = snapped if snapped else pos
            ex, ey = self._screen_to_energy_pos(place_pos)
            self._energy_nodes[self._drag_energy_idx]["x"] = ex
            self._energy_nodes[self._drag_energy_idx]["y"] = ey
            self.nodes_changed.emit()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_idx = -1
        self._drag_energy_idx = -1

    def add_energy_node(self, etype: str, x: float, y: float) -> None:
        self._energy_nodes.append({"type": etype, "x": x, "y": y, "strength": 1.0})
        self.nodes_changed.emit()
        self.update()


class _EnergyChip(QWidget):
    """Clickable energy source chip in the palette. Click to enter placement mode."""

    chip_clicked = Signal(str)

    def __init__(self, etype: str, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._type = etype
        self._color = color
        self._active = False
        self.setFixedSize(70, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Click, then click on an editor to place {etype} energy source")

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        border_color = QColor(255, 255, 255) if self._active else self._color.darker(120)
        p.setPen(QPen(border_color, 2.0 if self._active else 1.0))
        fill = self._color.lighter(130) if self._active else self._color
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 4, 4)
        p.setPen(QPen(QColor(255, 255, 255)))
        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._type.capitalize())
        p.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.chip_clicked.emit(self._type)


class BlobShapeEditor(QWidget):
    """Complete Blob Shaper editor: two polar canvases + energy palette."""

    nodes_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._chips: list[_EnergyChip] = []
        self._active_chip_type: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Editor canvases side by side with tight spacing
        editors_layout = QHBoxLayout()
        editors_layout.setContentsMargins(0, 0, 0, 0)
        editors_layout.setSpacing(4)

        self._base_canvas = _PolarEditorCanvas("Base Shape")
        self._react_canvas = _PolarEditorCanvas("Reaction Limit")

        editors_layout.addWidget(self._base_canvas)
        editors_layout.addWidget(self._react_canvas)
        editors_layout.addStretch()
        main_layout.addLayout(editors_layout)

        # Energy source palette + reset button
        palette_layout = QHBoxLayout()
        palette_layout.setSpacing(4)
        palette_label = QLabel("Energy:")
        palette_label.setFixedWidth(48)
        palette_label.setStyleSheet("color: #aab; font-size: 10px;")
        palette_layout.addWidget(palette_label)

        for etype, color in ENERGY_TYPES:
            chip = _EnergyChip(etype, color)
            chip.chip_clicked.connect(self._on_chip_clicked)
            palette_layout.addWidget(chip)
            self._chips.append(chip)

        palette_layout.addStretch()

        reset_btn = QPushButton("Reset")
        reset_btn.setFixedSize(48, 22)
        reset_btn.setStyleSheet(
            "QPushButton { color: #ccc; background: #3a3a46; border: 1px solid #555; "
            "border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background: #4a4a56; }"
        )
        reset_btn.setToolTip("Reset all profile and energy nodes to defaults")
        reset_btn.clicked.connect(self.reset_nodes)
        palette_layout.addWidget(reset_btn)

        main_layout.addLayout(palette_layout)

        hint = QLabel("Click an energy chip, then click on an editor to place it. Double-click to add profile nodes. Right-click to remove.")
        hint.setStyleSheet("color: #667; font-size: 9px;")
        hint.setWordWrap(True)
        main_layout.addWidget(hint)

        # Wire canvas signals
        self._base_canvas.nodes_changed.connect(self._on_canvas_changed)
        self._react_canvas.nodes_changed.connect(self._on_canvas_changed)
        self._base_canvas.energy_placed.connect(self._on_energy_placed)
        self._react_canvas.energy_placed.connect(self._on_energy_placed)

    def _on_chip_clicked(self, etype: str) -> None:
        if self._active_chip_type == etype:
            self._clear_placement()
            return
        self._active_chip_type = etype
        for chip in self._chips:
            chip.set_active(chip._type == etype)
        self._base_canvas.set_placement_type(etype)
        self._react_canvas.set_placement_type(etype)

    def _on_energy_placed(self, etype: str, x: float, y: float) -> None:
        self._clear_placement()

    def _clear_placement(self) -> None:
        self._active_chip_type = None
        for chip in self._chips:
            chip.set_active(False)
        self._base_canvas.set_placement_type(None)
        self._react_canvas.set_placement_type(None)

    def _on_canvas_changed(self) -> None:
        self.nodes_changed.emit()

    def reset_nodes(self) -> None:
        """Reset all profile and energy nodes to defaults."""
        default_profile = [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]]
        self._base_canvas.set_profile_nodes(list(default_profile))
        self._react_canvas.set_profile_nodes(list(default_profile))
        self._base_canvas.set_energy_nodes([])
        self._react_canvas.set_energy_nodes([])
        self._clear_placement()
        self.nodes_changed.emit()

    # --- Public data API ---

    def set_ring_mode(self, ring: bool, thickness: float = 0.3) -> None:
        self._base_canvas.set_ring_mode(ring, thickness)
        self._react_canvas.set_ring_mode(ring, thickness)

    def set_nodes(
        self,
        base_nodes: list[list[float]],
        react_nodes: list[list[float]],
        energy_nodes: list[dict[str, Any]],
    ) -> None:
        self._base_canvas.set_profile_nodes(base_nodes)
        self._react_canvas.set_profile_nodes(react_nodes)
        base_energy = [n for n in energy_nodes if n.get("canvas") != "react"]
        react_energy = [n for n in energy_nodes if n.get("canvas") == "react"]
        self._base_canvas.set_energy_nodes(base_energy)
        self._react_canvas.set_energy_nodes(react_energy)

    def get_nodes(self) -> tuple[list[list[float]], list[list[float]], list[dict[str, Any]]]:
        base = self._base_canvas.get_profile_nodes()
        react = self._react_canvas.get_profile_nodes()
        base_energy = self._base_canvas.get_energy_nodes()
        react_energy = self._react_canvas.get_energy_nodes()
        for n in base_energy:
            n["canvas"] = "base"
        for n in react_energy:
            n["canvas"] = "react"
        return base, react, base_energy + react_energy
