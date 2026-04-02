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
_ARROW_HANDLE_RADIUS = 5
_ARROW_DEFAULT_LENGTH = 22.0
_ARROW_MIN_LENGTH = 14.0
_ARROW_MAX_LENGTH = 42.0
_EDITOR_SIZE = 338
_CIRCLE_RADIUS = 90
_BORDER_COLOR = QColor(255, 255, 255, 45)
_RING_INNER_COLOR = QColor(20, 20, 26)
_SNAP_DISTANCE_PX = 14
_INTERP_STEPS = 128

# 4 cardinal nodes (top, right, bottom, left) at radius 1.0
_DEFAULT_NODES_CIRCLE: list[list[float]] = [
    [0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0],
]
# Ring mode: 4 outer + 4 inner nodes
_DEFAULT_NODES_RING_OUTER: list[list[float]] = [
    [0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0],
]
_DEFAULT_NODES_RING_INNER: list[list[float]] = [
    [0.0, 0.6], [0.25, 0.6], [0.5, 0.6], [0.75, 0.6],
]


def _catmull_rom(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    """Catmull-Rom spline interpolation between p1 and p2."""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def _sample_profile_smooth(sorted_nodes: list[list[float]], angle_frac: float) -> float:
    """Sample the profile at angle_frac using catmull-rom through sorted nodes.

    Wraps around: the profile is cyclic (angle 1.0 == angle 0.0).
    The wrap segment from the last node past 1.0 back to the first node is
    handled explicitly so there is no seam at angle 0.
    """
    normalized_map: dict[float, float] = {}
    for point in sorted_nodes:
        try:
            raw_x = float(point[0])
            x = raw_x % 1.0
            y = float(point[1])
        except Exception:
            continue
        key = round(x, 6)
        previous = normalized_map.get(key)
        is_wrap_alias = key == 0.0 and abs(raw_x) > 1e-6
        if previous is None:
            normalized_map[key] = y
        elif not is_wrap_alias and y > previous:
            normalized_map[key] = y
    normalized = [[key, value] for key, value in normalized_map.items()]
    sorted_nodes = sorted(normalized, key=lambda n: n[0])
    n = len(sorted_nodes)
    if n == 0:
        return 1.0
    if n == 1:
        return sorted_nodes[0][1]
    # Find which segment angle_frac falls in.
    # Segments: [node0->node1], [node1->node2], ..., [nodeN-1 -> node0+1.0 (wrap)]
    # If angle_frac is past the last node OR before the first node, we're in
    # the wrap segment (last -> first).
    if angle_frac >= sorted_nodes[-1][0] or angle_frac < sorted_nodes[0][0]:
        seg_idx = n - 1
    else:
        seg_idx = 0
        for j in range(n - 1):
            if sorted_nodes[j][0] <= angle_frac:
                seg_idx = j
    lo_x = sorted_nodes[seg_idx][0]
    hi_x = sorted_nodes[(seg_idx + 1) % n][0]
    # Compute segment length accounting for cyclic wrap
    if seg_idx == n - 1:
        seg_len = (1.0 - lo_x) + hi_x
        # local_t within the wrap segment
        if angle_frac >= lo_x:
            local_t = (angle_frac - lo_x) / seg_len if seg_len > 1e-6 else 0.0
        else:
            local_t = (angle_frac + 1.0 - lo_x) / seg_len if seg_len > 1e-6 else 0.0
    else:
        seg_len = hi_x - lo_x
        local_t = (angle_frac - lo_x) / seg_len if seg_len > 1e-6 else 0.0
    local_t = max(0.0, min(1.0, local_t))
    p0 = sorted_nodes[(seg_idx - 1) % n][1]
    p1 = sorted_nodes[seg_idx][1]
    p2 = sorted_nodes[(seg_idx + 1) % n][1]
    p3 = sorted_nodes[(seg_idx + 2) % n][1]
    return _catmull_rom(p0, p1, p2, p3, local_t)


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
        self._nodes: list[list[float]] = [list(n) for n in _DEFAULT_NODES_CIRCLE]
        self._energy_nodes: list[dict[str, Any]] = []
        self._drag_idx: int = -1
        self._drag_energy_idx: int = -1
        self._drag_energy_arrow_idx: int = -1
        self._ring_mode: bool = False
        self._ring_thickness: float = 0.3
        self._placement_type: str | None = None
        self.setMinimumSize(_EDITOR_SIZE, _EDITOR_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(_EDITOR_SIZE, _EDITOR_SIZE)
        self.setMouseTracking(True)

    def set_profile_nodes(self, nodes: list[list[float]]) -> None:
        self._nodes = [list(n) for n in nodes] if nodes else [list(n) for n in _DEFAULT_NODES_CIRCLE]
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

    def _node_direction_vector(self, node: dict) -> tuple[float, float]:
        dx = float(node.get("dir_x", 0.0))
        dy = float(node.get("dir_y", -1.0))
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return (0.0, -1.0)
        return (dx / length, dy / length)

    def _energy_arrow_handle_to_screen(self, node: dict) -> QPointF:
        anchor = self._energy_node_to_screen(node)
        dx, dy = self._node_direction_vector(node)
        length = float(node.get("dir_len", _ARROW_DEFAULT_LENGTH))
        length = max(_ARROW_MIN_LENGTH, min(_ARROW_MAX_LENGTH, length))
        return QPointF(anchor.x() + dx * length, anchor.y() + dy * length)

    def _screen_to_energy_pos(self, pos: QPointF) -> tuple[float, float]:
        s = max(1.0, min(self.width(), self.height()))
        ex = max(0.0, min(1.0, pos.x() / s))
        ey = max(0.0, min(1.0, pos.y() / s))
        return (ex, ey)

    def _default_energy_direction(self, screen_pos: QPointF) -> tuple[float, float]:
        center = self._center()
        dx = screen_pos.x() - center.x()
        dy = screen_pos.y() - center.y()
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return (0.0, -1.0)
        return (dx / length, dy / length)

    def _apply_energy_arrow_drag(self, index: int, pos: QPointF) -> None:
        if index < 0 or index >= len(self._energy_nodes):
            return
        anchor = self._energy_node_to_screen(self._energy_nodes[index])
        dx = pos.x() - anchor.x()
        dy = pos.y() - anchor.y()
        length = math.hypot(dx, dy)
        if length <= 1e-6:
            return
        self._energy_nodes[index]["dir_x"] = dx / length
        self._energy_nodes[index]["dir_y"] = dy / length
        self._energy_nodes[index]["dir_len"] = max(_ARROW_MIN_LENGTH, min(_ARROW_MAX_LENGTH, length))

    def _snap_energy_to_profile(self, screen_pos: QPointF) -> QPointF | None:
        """If screen_pos is close to a profile node or line segment, return snapped pos."""
        # Snap to profile nodes first
        for node in self._nodes:
            sp = self._node_to_screen(node[0], node[1])
            if (screen_pos - sp).manhattanLength() < _SNAP_DISTANCE_PX:
                return sp
        # Snap to profile line/curve segments
        if len(self._nodes) >= 2:
            sorted_nodes = sorted(self._nodes, key=lambda n: n[0])
            steps = 64
            best_dist = _SNAP_DISTANCE_PX
            best_pt: QPointF | None = None
            for i in range(steps):
                t = i / steps
                rm = _sample_profile_smooth(sorted_nodes, t)
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

    def _hit_test_energy_arrow(self, pos: QPointF) -> int:
        for i, node in enumerate(self._energy_nodes):
            sp = self._energy_arrow_handle_to_screen(node)
            if (pos - sp).manhattanLength() < _ARROW_HANDLE_RADIUS * 2.8:
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

        # Reference circles (dashed)
        p.setPen(QPen(QColor(70, 70, 90), 1.0, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, r, r)
        if self._ring_mode:
            inner_r = r * max(0.05, 1.0 - self._ring_thickness)
            p.setPen(QPen(QColor(90, 70, 70), 1.0, Qt.PenStyle.DashLine))
            p.drawEllipse(c, inner_r, inner_r)

        # Profile shape — smooth catmull-rom polygon
        if len(self._nodes) >= 2:
            sorted_nodes = sorted(self._nodes, key=lambda n: n[0])
            # Separate outer and inner nodes for ring mode
            if self._ring_mode:
                # Runtime ring topology derives a hollow band from one authored
                # contour plus the ring-thickness control. Preview the same
                # contract here instead of pretending inner/outer contours are
                # independently authored.
                ring_half_width = max(0.025, self._ring_thickness * 0.5)
                outer_pts = []
                inner_pts = []
                for i in range(_INTERP_STEPS):
                    t = i / _INTERP_STEPS
                    rm = _sample_profile_smooth(sorted_nodes, t)
                    rm_o = min(2.0, rm + ring_half_width)
                    rm_i = max(0.1, rm - ring_half_width)
                    outer_pts.append(self._node_to_screen(t, rm_o))
                    inner_pts.append(self._node_to_screen(t, rm_i))
                donut_pts = outer_pts + list(reversed(inner_pts))
                p.setPen(QPen(QColor(100, 200, 255, 160), 1.5))
                p.setBrush(QBrush(QColor(60, 140, 220, 40)))
                p.drawPolygon(QPolygonF(donut_pts))
                # Fill hollow center dark
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(_RING_INNER_COLOR))
                p.drawPolygon(QPolygonF(inner_pts))
            else:
                pts = []
                for i in range(_INTERP_STEPS):
                    t = i / _INTERP_STEPS
                    rm = _sample_profile_smooth(sorted_nodes, t)
                    pts.append(self._node_to_screen(t, rm))
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
            handle = self._energy_arrow_handle_to_screen(node)
            p.setPen(QPen(color.lighter(145), 2.0))
            p.drawLine(sp, handle)
            # Arrow head
            direction = QPointF(handle.x() - sp.x(), handle.y() - sp.y())
            dlen = math.hypot(direction.x(), direction.y())
            if dlen > 1e-6:
                ux = direction.x() / dlen
                uy = direction.y() / dlen
                left = QPointF(
                    handle.x() - ux * 8.0 - uy * 4.0,
                    handle.y() - uy * 8.0 + ux * 4.0,
                )
                right = QPointF(
                    handle.x() - ux * 8.0 + uy * 4.0,
                    handle.y() - uy * 8.0 - ux * 4.0,
                )
                p.setBrush(QBrush(color.lighter(130)))
                p.drawPolygon(QPolygonF([handle, left, right]))
            p.setPen(QPen(color.lighter(150), 1.4))
            p.setBrush(QBrush(QColor(28, 28, 34)))
            p.drawEllipse(handle, _ARROW_HANDLE_RADIUS, _ARROW_HANDLE_RADIUS)
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
            dir_x, dir_y = self._default_energy_direction(place_pos)
            self._energy_nodes.append(
                {
                    "type": self._placement_type,
                    "x": ex,
                    "y": ey,
                    "strength": 1.0,
                    "dir_x": dir_x,
                    "dir_y": dir_y,
                    "dir_len": _ARROW_DEFAULT_LENGTH,
                }
            )
            self.energy_placed.emit(self._placement_type, ex, ey)
            self.set_placement_type(None)
            self.nodes_changed.emit()
            self.update()
            return

        # Hit-test existing nodes
        arrow_idx = self._hit_test_energy_arrow(pos)
        if arrow_idx >= 0:
            self._drag_energy_arrow_idx = arrow_idx
            self._drag_energy_idx = -1
            self._drag_idx = -1
            self._apply_energy_arrow_drag(arrow_idx, pos)
            self.nodes_changed.emit()
            self.update()
            return
        eidx = self._hit_test_energy(pos)
        if eidx >= 0:
            self._drag_energy_idx = eidx
            self._drag_energy_arrow_idx = -1
            self._drag_idx = -1
            return
        pidx = self._hit_test_profile(pos)
        if pidx >= 0:
            self._drag_idx = pidx
            self._drag_energy_idx = -1
            self._drag_energy_arrow_idx = -1
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
        elif self._drag_energy_arrow_idx >= 0 and self._drag_energy_arrow_idx < len(self._energy_nodes):
            self._apply_energy_arrow_drag(self._drag_energy_arrow_idx, pos)
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
        self._drag_energy_arrow_idx = -1

    def add_energy_node(self, etype: str, x: float, y: float) -> None:
        screen_pos = QPointF(x * min(self.width(), self.height()), y * min(self.width(), self.height()))
        dir_x, dir_y = self._default_energy_direction(screen_pos)
        self._energy_nodes.append(
            {
                "type": etype,
                "x": x,
                "y": y,
                "strength": 1.0,
                "dir_x": dir_x,
                "dir_y": dir_y,
                "dir_len": _ARROW_DEFAULT_LENGTH,
            }
        )
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
        reset_btn.setFixedSize(72, 28)
        reset_btn.setStyleSheet(
            "QPushButton {"
            " color: #f4f4f6;"
            " font-size: 11px;"
            " font-weight: 600;"
            " padding: 4px 12px;"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "   stop:0 #494955, stop:1 #32323d);"
            " border: 1px solid rgba(210, 210, 220, 90);"
            " border-radius: 7px;"
            "}"
            "QPushButton:hover {"
            " background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            "   stop:0 #565664, stop:1 #3a3a46);"
            "}"
            "QPushButton:pressed {"
            " background: #2e2e37;"
            " padding-top: 5px;"
            "}"
        )
        reset_btn.setToolTip("Reset all profile and energy nodes to defaults")
        reset_btn.clicked.connect(self.reset_nodes)
        palette_layout.addWidget(reset_btn)

        main_layout.addLayout(palette_layout)

        hint = QLabel(
            "Click an energy chip, then click on an editor to place it. "
            "Drag the small arrow handle to choose inward or outward response. "
            "Double-click to add profile nodes. Right-click to remove."
        )
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
        default_profile = [list(n) for n in _DEFAULT_NODES_CIRCLE]
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
