"""Interactive Spline Curve shape editor — node-based spline control.

Left-click on empty space adds a control node (up to MAX_NODES).
Right-click on a node removes it (minimum 1 must remain).
Drag nodes to reshape the bar-height profile curve.

Spline Curve uses the full width editor by default (left→right), with
explicit lane markers for Bass/Vocals/Mids/Transients.
"""
from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
    QLinearGradient, QRadialGradient, QMouseEvent, QPaintEvent,
)
from PySide6.QtWidgets import QWidget


def _desaturate_with_alpha(color: QColor, *, saturation_scale: float, alpha: int) -> QColor:
    h, s, l, _a = color.getHsl()
    if h < 0:
        h = 0
    desaturated = QColor.fromHsl(
        int(h),
        int(max(0, min(255, round(s * saturation_scale)))),
        int(l),
        int(max(0, min(255, alpha))),
    )
    return desaturated

# ── Colours matching the settings dark-glass theme ──────────────────
_BG_COLOR = QColor(18, 18, 18, 240)
_GRID_COLOR = QColor(255, 255, 255, 18)
_GRID_MAJOR_COLOR = QColor(255, 255, 255, 35)
_CURVE_COLOR = QColor(160, 180, 255, 200)
_CURVE_FILL_TOP = QColor(100, 130, 220, 50)
_CURVE_FILL_BOT = QColor(100, 130, 220, 0)
_MIRROR_CURVE_COLOR = QColor(160, 180, 255, 70)
_MIRROR_FILL_TOP = QColor(100, 130, 220, 20)
_NODE_COLOR = QColor(220, 230, 255, 240)
_NODE_BORDER = QColor(255, 255, 255, 200)
_NODE_HOVER = QColor(255, 255, 255, 255)
_NODE_DRAG = QColor(180, 200, 255, 255)
_MIRROR_LINE = QColor(255, 255, 255, 50)
_BORDER_COLOR = QColor(255, 255, 255, 60)
_LABEL_COLOR = QColor(255, 255, 255, 100)
_NOTCH_COLOR = QColor(255, 255, 255, 55)
_ZONE_LABEL_COLOR = QColor(255, 255, 255, 70)
_NOTCH_DRAG_COLOR = QColor(180, 200, 255, 180)
_ARROW_TRACK_COLOR = QColor(255, 255, 255, 38)
_ARROW_COLOR = _desaturate_with_alpha(QColor(190, 214, 255), saturation_scale=0.8, alpha=204)
_ARROW_HOVER_COLOR = _desaturate_with_alpha(QColor(230, 240, 255), saturation_scale=0.8, alpha=204)
_ARROW_DRAG_COLOR = _desaturate_with_alpha(QColor(150, 205, 255), saturation_scale=0.8, alpha=204)
_ARROW_TEXT_COLOR = QColor(255, 255, 255, 150)
_NOTCH_HIT_WIDTH = 28
_NOTCH_MIN_SPACING = 0.06

_NODE_RADIUS = 7
_HIT_RADIUS = 14
_ARROW_HIT_HALF_WIDTH = 16
_ARROW_HEAD_HALF_WIDTH = 5
_ARROW_HEAD_HEIGHT = 8
_MAX_NODES = 5
_MIN_NODES = 1
_SOFT_SNAP_THRESHOLD_PX = 14.0
_SOFT_SNAP_BLEND = 0.45

_PADDING_LEFT = 32
_PADDING_RIGHT = 12
_PADDING_TOP = 44
_PADDING_BOTTOM = 30  # extra room for notch labels

# Default nodes define the authored spline profile.
# x = normalized horizontal position (0 .. 1), y = normalized level (0 .. 1).
DEFAULT_NODES: List[List[float]] = [
    [0.00, 0.58],
    [0.32, 0.65],
    [0.68, 0.52],
    [1.00, 0.60],
]

_LAYER_ORDER = ("bass", "vocals", "mids", "transients")
_LAYER_LABELS = {
    "bass": "Bass",
    "vocals": "Vocals",
    "mids": "Mids",
    "transients": "Transients",
}

# Bottom lane anchors as fractional x values and labels.
_NOTCHES_MIRRORED = [
    (0.08, "Bass"),
    (0.35, "Vocals"),
    (0.66, "Mids"),
    (0.92, "Transients"),
]
_NOTCHES_LINEAR = [
    (0.08, "Bass"),
    (0.35, "Vocals"),
    (0.66, "Mids"),
    (0.92, "Transients"),
]
_LANE_STRENGTHS_MIRRORED = {
    "Bass": 0.34,
    "Vocals": 0.34,
    "Mids": 0.34,
    "Transients": 0.39,
}
_LANE_STRENGTHS_LINEAR = {
    "Bass": 0.34,
    "Vocals": 0.34,
    "Mids": 0.34,
    "Transients": 0.39,
}


def _normalize_lane_strengths(
    strengths: Optional[Mapping[str, float]],
    defaults: Mapping[str, float],
) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    source = strengths if isinstance(strengths, Mapping) else {}
    for label, default in defaults.items():
        try:
            value = float(source.get(label, default))
        except Exception:
            value = float(default)
        normalized[label] = max(0.0, min(1.0, value))
    return normalized


# ── Interpolation (public, used by DSP pipeline) ────────────────────

def interpolate_nodes(nodes: List[List[float]], num_samples: int) -> List[float]:
    """Smoothly interpolate node control points into a sampled curve.

    Args:
        nodes: Sorted list of [x, y] pairs, x in [0,1], y in [0,1].
        num_samples: Number of output samples.

    Returns:
        List of *num_samples* floats in [0, 1].
    """
    if not nodes:
        return [0.5] * num_samples
    if len(nodes) == 1:
        return [max(0.0, min(1.0, nodes[0][1]))] * num_samples

    xs = [n[0] for n in nodes]
    ys = [n[1] for n in nodes]

    result: List[float] = []
    for i in range(num_samples):
        t = i / max(1, num_samples - 1)
        if t <= xs[0]:
            result.append(ys[0])
        elif t >= xs[-1]:
            result.append(ys[-1])
        else:
            for j in range(len(xs) - 1):
                if xs[j] <= t <= xs[j + 1]:
                    seg_len = xs[j + 1] - xs[j]
                    if seg_len < 1e-9:
                        result.append(ys[j])
                    else:
                        frac = (t - xs[j]) / seg_len
                        frac = frac * frac * (3.0 - 2.0 * frac)
                        result.append(ys[j] + (ys[j + 1] - ys[j]) * frac)
                    break
            else:
                result.append(ys[-1])
    return result


def interpolate_nodes_mirrored(nodes: List[List[float]], num_bars: int) -> List[float]:
    """Produce a full mirrored bar-height profile from half-range nodes.

    Nodes define the center-to-edge profile.  This function samples
    *num_bars* values where bar 0 is the left edge, center is the middle,
    and bar num_bars-1 is the right edge.  Both halves mirror the same
    node curve.
    """
    half = num_bars // 2
    half_samples = interpolate_nodes(nodes, max(2, half + 1))
    result: List[float] = []
    center_pos = (float(num_bars) - 1.0) * 0.5
    max_dist = max(center_pos, 1.0)
    for i in range(num_bars):
        dist = abs(float(i) - center_pos)
        sample_pos = (dist / max_dist) * float(len(half_samples) - 1)
        idx0 = int(sample_pos)
        idx1 = min(idx0 + 1, len(half_samples) - 1)
        frac = max(0.0, min(1.0, sample_pos - float(idx0)))
        result.append(half_samples[idx0] + (half_samples[idx1] - half_samples[idx0]) * frac)
    # Smooth the center bar so it doesn't dip below its mirrored
    # neighbors when the node curve starts at a local minimum.
    center = num_bars // 2
    if num_bars % 2 == 1 and num_bars >= 3 and center > 0:
        result[center] = max(result[center], (result[center - 1] + result[center + 1]) * 0.5)
    return result


# ── Widget ───────────────────────────────────────────────────────────

class DevCurveShapeEditor(QWidget):
    """Interactive node-based Spline Curve shape editor widget.

    In mirrored mode the **visible editing area** is the left half of the
    plot (representing the center→edge half of the spectrum).  The right
    half automatically mirrors the curve as a ghost.  Node x-values are
    stored in [0, 1] where 0 = center, 1 = edge.

    In non-mirrored mode the full width is editable and nodes map
    directly to bar positions (0 = leftmost bar, 1 = rightmost bar).
    """

    nodes_changed = Signal(list)
    layer_nodes_changed = Signal(dict)
    active_layer_changed = Signal(str)
    notch_positions_changed = Signal(list)
    lane_strengths_changed = Signal(dict)

    def __init__(self, parent: Optional[QWidget] = None, mirrored: bool = False) -> None:
        super().__init__(parent)
        self._layer_nodes: Dict[str, List[List[float]]] = {
            src: [list(n) for n in DEFAULT_NODES] for src in _LAYER_ORDER
        }
        self._active_layer: str = "bass"
        self._nodes: List[List[float]] = self._layer_nodes[self._active_layer]
        self._mirrored: bool = mirrored
        self._drag_index: int = -1
        self._hover_index: int = -1
        self._notch_drag_index: int = -1
        self._notch_drag_ref: Optional[List] = None
        self._notch_hover_index: int = -1
        self._notches_mirrored: List[List] = [[0.5, _LAYER_LABELS[self._active_layer]]]
        self._notches_linear: List[List] = [[0.5, _LAYER_LABELS[self._active_layer]]]
        self._lane_strengths_mirrored: Dict[str, float] = dict(_LANE_STRENGTHS_MIRRORED)
        self._lane_strengths_linear: Dict[str, float] = dict(_LANE_STRENGTHS_LINEAR)
        self._lane_drag_index: int = -1
        self._lane_hover_index: int = -1
        self.setMinimumHeight(270)
        self.setMaximumHeight(345)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(
            "Left-click: add node (max 5)\n"
            "Right-click node: remove\n"
            "Drag node: reshape bar heights\n"
            "Drag top energy arrow: set active layer power"
        )

    # ── Public API ───────────────────────────────────────────────────

    def get_nodes(self) -> List[List[float]]:
        return [list(n) for n in self._nodes]

    def set_nodes(self, nodes: List[List[float]]) -> None:
        if not nodes:
            nodes = [list(n) for n in DEFAULT_NODES]
        self._nodes = sorted([list(n) for n in nodes], key=lambda n: n[0])
        self._clamp_all()
        self._layer_nodes[self._active_layer] = self._nodes
        self.update()

    def get_active_layer(self) -> str:
        return str(self._active_layer)

    def set_active_layer(self, layer: str) -> None:
        src = str(layer or "").strip().lower()
        if src not in _LAYER_ORDER:
            src = "bass"
        if src == self._active_layer:
            return
        self._active_layer = src
        self._nodes = self._layer_nodes[src]
        self._notches_linear = [[0.5, _LAYER_LABELS[src]]]
        self._notches_mirrored = [[0.5, _LAYER_LABELS[src]]]
        self._drag_index = -1
        self._hover_index = -1
        self.active_layer_changed.emit(src)
        self.update()

    def get_layer_nodes_map(self) -> Dict[str, List[List[float]]]:
        return {
            src: [list(n) for n in self._layer_nodes.get(src, DEFAULT_NODES)]
            for src in _LAYER_ORDER
        }

    def set_layer_nodes_map(self, layer_nodes: Mapping[str, List[List[float]]]) -> None:
        if not isinstance(layer_nodes, Mapping):
            return
        for src in _LAYER_ORDER:
            nodes = layer_nodes.get(src)
            if not isinstance(nodes, list) or not nodes:
                continue
            clamped = sorted(
                [list(n) for n in nodes if isinstance(n, (list, tuple)) and len(n) >= 2],
                key=lambda n: float(n[0]),
            )
            if clamped:
                self._layer_nodes[src] = clamped
        self._nodes = self._layer_nodes[self._active_layer]
        self._clamp_all()
        self.update()

    def set_mirrored(self, mirrored: bool) -> None:
        if self._mirrored != mirrored:
            self._mirrored = mirrored
            self.update()

    def get_lane_strengths(self, mirrored: Optional[bool] = None) -> Dict[str, float]:
        if mirrored is None:
            mirrored = self._mirrored
        src = self._lane_strengths_mirrored if mirrored else self._lane_strengths_linear
        return dict(src)

    def set_lane_strengths(
        self,
        strengths: Mapping[str, float],
        *,
        mirrored: Optional[bool] = None,
    ) -> None:
        if mirrored is None:
            mirrored = self._mirrored
        if mirrored:
            self._lane_strengths_mirrored = _normalize_lane_strengths(strengths, _LANE_STRENGTHS_MIRRORED)
        else:
            self._lane_strengths_linear = _normalize_lane_strengths(strengths, _LANE_STRENGTHS_LINEAR)
        self.update()

    def get_notch_positions(self) -> List[List]:
        """Return current notch positions as [[x_frac, label], ...]."""
        src = self._notches_mirrored if self._mirrored else self._notches_linear
        return [list(n) for n in src]

    def set_notch_positions(self, positions: List[List], mirrored: Optional[bool] = None) -> None:
        """Restore notch positions from settings."""
        if mirrored is None:
            mirrored = self._mirrored
        if not positions or len(positions) < 2:
            return
        target = self._notches_mirrored if mirrored else self._notches_linear
        if len(positions) == len(target):
            for i, (x, lbl) in enumerate(positions):
                target[i] = [float(x), str(lbl)]
            target.sort(key=lambda n: n[0])
            self.update()

    def get_layer_strengths(self) -> Dict[str, float]:
        strengths = self.get_lane_strengths(mirrored=False)
        return {
            src: float(strengths.get(_LAYER_LABELS[src], _LANE_STRENGTHS_LINEAR[_LAYER_LABELS[src]]))
            for src in _LAYER_ORDER
        }

    def set_layer_strengths(self, strengths: Mapping[str, float]) -> None:
        mapped = {
            _LAYER_LABELS[src]: float(strengths.get(src, _LANE_STRENGTHS_LINEAR[_LAYER_LABELS[src]]))
            for src in _LAYER_ORDER
        }
        self.set_lane_strengths(mapped, mirrored=False)

    def get_layer_positions(self) -> Dict[str, float]:
        notches = self.get_notch_positions()
        label_to_x = {str(label): float(x) for x, label in notches}
        return {
            src: float(label_to_x.get(_LAYER_LABELS[src], _NOTCHES_LINEAR[idx][0]))
            for idx, src in enumerate(_LAYER_ORDER)
        }

    def set_layer_positions(self, positions: Mapping[str, float]) -> None:
        mapped: List[List] = []
        for idx, src in enumerate(_LAYER_ORDER):
            x = float(positions.get(src, _NOTCHES_LINEAR[idx][0]))
            mapped.append([max(0.0, min(1.0, x)), _LAYER_LABELS[src]])
        mapped.sort(key=lambda item: float(item[0]))
        self.set_notch_positions(mapped, mirrored=False)

    # ── Coordinate mapping ───────────────────────────────────────────

    def _plot_rect(self) -> QRectF:
        return QRectF(
            _PADDING_LEFT, _PADDING_TOP,
            self.width() - _PADDING_LEFT - _PADDING_RIGHT,
            self.height() - _PADDING_TOP - _PADDING_BOTTOM,
        )

    def _edit_rect(self) -> QRectF:
        """The region the user can place / drag nodes in.

        In mirrored mode this is the left half of the plot.
        In non-mirrored mode it is the full plot.
        """
        r = self._plot_rect()
        if self._mirrored:
            return QRectF(r.left(), r.top(), r.width() * 0.5, r.height())
        return r

    def _node_to_pixel(self, nx: float, ny: float) -> QPointF:
        er = self._edit_rect()
        if self._mirrored:
            # Mirrored editing uses the left half where the center divider is
            # on the RIGHT side of the edit rect.  Keep node semantics as
            # x=0 -> center, x=1 -> edge.
            px = er.right() - nx * er.width()
        else:
            px = er.left() + nx * er.width()
        py = er.bottom() - ny * er.height()
        return QPointF(px, py)

    def _pixel_to_node(self, px: float, py: float) -> Tuple[float, float]:
        er = self._edit_rect()
        if self._mirrored:
            nx = (er.right() - px) / max(1.0, er.width())
        else:
            nx = (px - er.left()) / max(1.0, er.width())
        ny = (er.bottom() - py) / max(1.0, er.height())
        nx = max(0.0, min(1.0, nx))
        ny = max(0.0, min(1.0, ny))
        return nx, ny

    def _soft_snap_axis(self, value_px: float, guides_px: List[float]) -> float:
        nearest = min(guides_px, key=lambda g: abs(value_px - g))
        dist = abs(value_px - nearest)
        if dist >= _SOFT_SNAP_THRESHOLD_PX:
            return value_px
        # Gentle magnetic pull: strongest near guide, but never hard-lock.
        pull = (1.0 - (dist / _SOFT_SNAP_THRESHOLD_PX)) * _SOFT_SNAP_BLEND
        return value_px + (nearest - value_px) * max(0.0, min(1.0, pull))

    def _apply_soft_snap(self, px: float, py: float) -> Tuple[float, float]:
        er = self._edit_rect()
        x_guides = [er.left() + er.width() * frac for frac in (0.0, 0.25, 0.50, 0.75, 1.0)]
        y_guides = [er.bottom() - er.height() * frac for frac in (0.0, 0.25, 0.50, 0.75, 1.0)]
        snapped_x = self._soft_snap_axis(px, x_guides)
        snapped_y = self._soft_snap_axis(py, y_guides)
        return snapped_x, snapped_y

    def _active_notches(self) -> List[List]:
        return self._notches_mirrored if self._mirrored else self._notches_linear

    def _active_lane_strengths(self) -> Dict[str, float]:
        return self._lane_strengths_mirrored if self._mirrored else self._lane_strengths_linear

    def _lane_anchor_x(self, frac: float) -> float:
        r = self._plot_rect()
        if self._mirrored:
            center_x = r.left() + r.width() * 0.5
            half_w = r.width() * 0.5
            return center_x - frac * half_w
        return r.left() + frac * r.width()

    def _arrow_bounds(self) -> Tuple[float, float]:
        plot = self._plot_rect()
        bottom = max(plot.top() + 18.0, plot.bottom() - 9.0)
        top = max(plot.top() + 6.0, bottom - 26.0)
        return top, bottom

    def _lane_strength_to_y(self, strength: float) -> float:
        top, bottom = self._arrow_bounds()
        return bottom - max(0.0, min(1.0, strength)) * (bottom - top)

    def _y_to_lane_strength(self, py: float) -> float:
        top, bottom = self._arrow_bounds()
        if bottom <= top:
            return 0.0
        return max(0.0, min(1.0, (bottom - py) / (bottom - top)))

    def _hit_test(self, px: float, py: float) -> int:
        for i, (nx, ny) in enumerate(self._nodes):
            pt = self._node_to_pixel(nx, ny)
            dx = px - pt.x()
            dy = py - pt.y()
            if dx * dx + dy * dy <= _HIT_RADIUS * _HIT_RADIUS:
                return i
        return -1

    def _clamp_all(self) -> None:
        for n in self._nodes:
            n[0] = max(0.0, min(1.0, n[0]))
            n[1] = max(0.0, min(1.0, n[1]))

    def _arrow_hit_test(self, px: float, py: float) -> int:
        top, bottom = self._arrow_bounds()
        if py < top - 4 or py > bottom + 6:
            return -1
        for idx, (frac, _label) in enumerate(self._active_notches()):
            if abs(px - self._lane_anchor_x(float(frac))) <= _ARROW_HIT_HALF_WIDTH:
                return idx
        return -1

    # ── Mouse handling ───────────────────────────────────────────────

    def _notch_hit_test(self, px: float, py: float) -> int:
        _ = (px, py)
        return -1

    def mousePressEvent(self, event: QMouseEvent) -> None:
        px, py = event.position().x(), event.position().y()

        if event.button() == Qt.MouseButton.LeftButton:
            lane_idx = self._arrow_hit_test(px, py)
            if lane_idx >= 0:
                self._lane_drag_index = lane_idx
                notches = self._active_notches()
                strengths = self._active_lane_strengths()
                label = str(notches[lane_idx][1])
                strengths[label] = self._y_to_lane_strength(py)
                self.setCursor(Qt.CursorShape.SizeVerCursor)
                self.update()
                event.accept()
                return

        idx = self._hit_test(px, py)

        if event.button() == Qt.MouseButton.LeftButton:
            if idx >= 0:
                self._drag_index = idx
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif len(self._nodes) < _MAX_NODES:
                # Only allow adding nodes inside the editable region
                er = self._edit_rect()
                if er.contains(QPointF(px, py)):
                    snap_x, snap_y = self._apply_soft_snap(px, py)
                    nx, ny = self._pixel_to_node(snap_x, snap_y)
                    self._nodes.append([nx, ny])
                    self._nodes.sort(key=lambda n: n[0])
                    self._drag_index = next(
                        i for i, n in enumerate(self._nodes)
                        if abs(n[0] - nx) < 1e-9 and abs(n[1] - ny) < 1e-9
                    )
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                    self._emit_change()
            event.accept()

        elif event.button() == Qt.MouseButton.RightButton:
            if idx >= 0 and len(self._nodes) > _MIN_NODES:
                del self._nodes[idx]
                self._drag_index = -1
                self._hover_index = -1
                self._emit_change()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        px, py = event.position().x(), event.position().y()

        if self._lane_drag_index >= 0:
            notches = self._active_notches()
            if 0 <= self._lane_drag_index < len(notches):
                label = str(notches[self._lane_drag_index][1])
                self._active_lane_strengths()[label] = self._y_to_lane_strength(py)
                self.update()
            event.accept()
            return

        if self._drag_index >= 0:
            snap_x, snap_y = self._apply_soft_snap(px, py)
            nx, ny = self._pixel_to_node(snap_x, snap_y)
            self._nodes[self._drag_index] = [nx, ny]
            self._nodes.sort(key=lambda n: n[0])
            for i, n in enumerate(self._nodes):
                if abs(n[0] - nx) < 1e-6 and abs(n[1] - ny) < 1e-6:
                    self._drag_index = i
                    break
            self.update()
        else:
            old_hover = self._hover_index
            self._hover_index = self._hit_test(px, py)
            old_notch_hover = self._notch_hover_index
            self._notch_hover_index = self._notch_hit_test(px, py)
            old_lane_hover = self._lane_hover_index
            self._lane_hover_index = self._arrow_hit_test(px, py)
            if self._hover_index >= 0:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            elif self._lane_hover_index >= 0:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            if (
                old_hover != self._hover_index
                or old_notch_hover != self._notch_hover_index
                or old_lane_hover != self._lane_hover_index
            ):
                self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._lane_drag_index >= 0:
            self._lane_drag_index = -1
            px, py = event.position().x(), event.position().y()
            self._lane_hover_index = self._arrow_hit_test(px, py)
            self.setCursor(
                Qt.CursorShape.SizeVerCursor if self._lane_hover_index >= 0
                else Qt.CursorShape.CrossCursor
            )
            self.lane_strengths_changed.emit(self.get_lane_strengths())
            self.update()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._drag_index >= 0:
            self._drag_index = -1
            px, py = event.position().x(), event.position().y()
            self._hover_index = self._hit_test(px, py)
            self.setCursor(
                Qt.CursorShape.PointingHandCursor if self._hover_index >= 0
                else Qt.CursorShape.CrossCursor
            )
            self._emit_change()
        event.accept()

    def _emit_change(self) -> None:
        self._clamp_all()
        self._layer_nodes[self._active_layer] = self._nodes
        self.update()
        self.nodes_changed.emit(self.get_nodes())
        self.layer_nodes_changed.emit(self.get_layer_nodes_map())

    # ── Painting ─────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = self._plot_rect()
        er = self._edit_rect()

        # Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_BG_COLOR))
        p.drawRoundedRect(0, 0, w, h, 10, 10)

        # Border
        p.setPen(QPen(_BORDER_COLOR, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        # Grid
        self._draw_grid(p, r)

        # Mirror center divider
        if self._mirrored:
            mid_x = r.left() + r.width() * 0.5
            p.setPen(QPen(_MIRROR_LINE, 1.5, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(mid_x, r.top()), QPointF(mid_x, r.bottom()))

        # Lane energy arrows
        self._draw_lane_strength_arrows(p)

        # Interpolated curves: draw all layers, but dim non-active ones.
        num_pts = max(2, int(er.width()))
        for src in _LAYER_ORDER:
            if src == self._active_layer:
                continue
            samples_bg = interpolate_nodes(self._layer_nodes.get(src, DEFAULT_NODES), num_pts)
            draw_bg = list(reversed(samples_bg)) if self._mirrored else samples_bg
            self._draw_curve_in_rect(p, er, draw_bg, primary=False, layer_alpha=0.22)

        samples = interpolate_nodes(self._layer_nodes.get(self._active_layer, self._nodes), num_pts)
        draw_samples_edit = list(reversed(samples)) if self._mirrored else samples
        self._draw_curve_in_rect(p, er, draw_samples_edit, primary=True, layer_alpha=1.0)

        # Mirrored ghost on the right half
        if self._mirrored:
            mirror_rect = QRectF(
                r.left() + r.width() * 0.5, r.top(),
                r.width() * 0.5, r.height(),
            )
            # Right ghost is center->edge (left->right), same orientation as
            # the underlying sample domain.
            self._draw_curve_in_rect(p, mirror_rect, samples, primary=False, layer_alpha=0.45)

        # Nodes (drawn on top)
        self._draw_nodes(p)

        # Bottom notches & labels
        self._draw_notches(p, r)

        # Y-axis labels
        self._draw_y_labels(p, r)

        p.end()

    def _draw_grid(self, p: QPainter, r: QRectF) -> None:
        for frac in (0.25, 0.50, 0.75):
            y = r.bottom() - frac * r.height()
            color = _GRID_MAJOR_COLOR if frac == 0.50 else _GRID_COLOR
            p.setPen(QPen(color, 1.0))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))

        v_count = 4 if not self._mirrored else 2
        for k in range(1, v_count):
            frac = k / v_count
            x = r.left() + frac * r.width()
            color = _GRID_MAJOR_COLOR if abs(frac - 0.5) < 0.01 else _GRID_COLOR
            p.setPen(QPen(color, 1.0))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

    def _draw_curve_in_rect(
        self,
        p: QPainter,
        rect: QRectF,
        samples: List[float],
        primary: bool,
        layer_alpha: float = 1.0,
    ) -> None:
        if len(samples) < 2:
            return
        n = len(samples)
        path = QPainterPath()
        fill_path = QPainterPath()
        first_pt = QPointF(rect.left(), rect.bottom() - samples[0] * rect.height())
        path.moveTo(first_pt)
        fill_path.moveTo(QPointF(rect.left(), rect.bottom()))
        fill_path.lineTo(first_pt)

        for i in range(1, n):
            x = rect.left() + (i / max(1, n - 1)) * rect.width()
            y = rect.bottom() - samples[i] * rect.height()
            pt = QPointF(x, y)
            path.lineTo(pt)
            fill_path.lineTo(pt)

        fill_path.lineTo(QPointF(rect.right(), rect.bottom()))
        fill_path.closeSubpath()

        alpha_mul = max(0.0, min(1.0, float(layer_alpha)))
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        if primary:
            top_col = QColor(_CURVE_FILL_TOP)
        else:
            top_col = QColor(_MIRROR_FILL_TOP)
        bot_col = QColor(_CURVE_FILL_BOT)
        top_col.setAlpha(int(max(0, min(255, round(top_col.alpha() * alpha_mul)))))
        bot_col.setAlpha(int(max(0, min(255, round(bot_col.alpha() * alpha_mul)))))
        grad.setColorAt(0.0, top_col)
        grad.setColorAt(1.0, bot_col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill_path)

        curve_col = QColor(_CURVE_COLOR if primary else _MIRROR_CURVE_COLOR)
        curve_col.setAlpha(int(max(0, min(255, round(curve_col.alpha() * alpha_mul)))))
        pen_style = Qt.PenStyle.SolidLine if primary else Qt.PenStyle.DashLine
        p.setPen(QPen(curve_col, 2.0 if primary else 1.5, pen_style))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def _draw_nodes(self, p: QPainter) -> None:
        for i, (nx, ny) in enumerate(self._nodes):
            pt = self._node_to_pixel(nx, ny)
            is_hover = (i == self._hover_index)
            is_drag = (i == self._drag_index)

            if is_hover or is_drag:
                glow = QRadialGradient(pt, _NODE_RADIUS * 2.5)
                glow.setColorAt(0.0, QColor(160, 190, 255, 60))
                glow.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(glow))
                p.drawEllipse(pt, _NODE_RADIUS * 2.5, _NODE_RADIUS * 2.5)

            if is_drag:
                fill, border, radius = _NODE_DRAG, _NODE_HOVER, _NODE_RADIUS + 1
            elif is_hover:
                fill, border, radius = _NODE_HOVER, _NODE_BORDER, _NODE_RADIUS + 1
            else:
                fill, border, radius = _NODE_COLOR, _NODE_BORDER, _NODE_RADIUS

            p.setPen(QPen(border, 1.5))
            p.setBrush(QBrush(fill))
            p.drawEllipse(pt, radius, radius)

    def _draw_notches(self, p: QPainter, r: QRectF) -> None:
        """Draw small bottom alignment notches with frequency-zone labels."""
        notches = self._notches_mirrored if self._mirrored else self._notches_linear
        font = p.font()
        font.setPixelSize(8)
        p.setFont(font)

        for idx, (frac, label) in enumerate(notches):
            is_dragging = (idx == self._notch_drag_index)
            if self._mirrored:
                center_x = r.left() + r.width() * 0.5
                half_w = r.width() * 0.5
                x_left = center_x - frac * half_w
                self._draw_single_notch(p, r, x_left, label, highlight=is_dragging)
                x_right = center_x + frac * half_w
                if abs(x_left - x_right) > 4:
                    self._draw_single_notch(p, r, x_right, label, highlight=is_dragging)
            else:
                x = r.left() + frac * r.width()
                self._draw_single_notch(p, r, x, label, highlight=is_dragging)

    def _draw_lane_strength_arrows(self, p: QPainter) -> None:
        label = _LAYER_LABELS.get(self._active_layer, "Bass")
        strengths = self._active_lane_strengths()
        top, bottom = self._arrow_bounds()
        if bottom <= top:
            return

        font = p.font()
        font.setPixelSize(8)
        p.setFont(font)

        notches = [[0.5, label]]
        for idx, (frac, label) in enumerate(notches):
            x = self._lane_anchor_x(float(frac))
            strength = float(strengths.get(str(label), 0.0))
            tip_y = self._lane_strength_to_y(strength)
            is_dragging = idx == self._lane_drag_index
            is_hover = idx == self._lane_hover_index
            line_color = _ARROW_DRAG_COLOR if is_dragging else (_ARROW_HOVER_COLOR if is_hover else _ARROW_COLOR)

            p.setPen(QPen(_ARROW_TRACK_COLOR, 1.0))
            p.drawLine(QPointF(x, top), QPointF(x, bottom))

            p.setPen(QPen(line_color, 2.0))
            p.drawLine(QPointF(x, bottom), QPointF(x, tip_y))
            p.setBrush(QBrush(line_color))
            head = QPainterPath()
            head.moveTo(QPointF(x, tip_y - _ARROW_HEAD_HEIGHT))
            head.lineTo(QPointF(x - _ARROW_HEAD_HALF_WIDTH, tip_y))
            head.lineTo(QPointF(x + _ARROW_HEAD_HALF_WIDTH, tip_y))
            head.closeSubpath()
            p.drawPath(head)

            if is_dragging or is_hover:
                p.setPen(_ARROW_TEXT_COLOR)
                p.drawText(
                    QRectF(x - 16, top - 2, 32, 12),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    f"{int(round(strength * 100.0))}%",
                )

    def _draw_single_notch(self, p: QPainter, r: QRectF, x: float, label: str,
                            *, highlight: bool = False) -> None:
        notch_color = _NOTCH_DRAG_COLOR if highlight else _NOTCH_COLOR
        label_color = _NOTCH_DRAG_COLOR if highlight else _ZONE_LABEL_COLOR
        p.setPen(QPen(notch_color, 1.5 if highlight else 1.0))
        p.drawLine(QPointF(x, r.bottom()), QPointF(x, r.bottom() + 5))
        p.setPen(label_color)
        p.drawText(
            QRectF(x - 22, r.bottom() + 5, 44, 14),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            label,
        )

    def _draw_y_labels(self, p: QPainter, r: QRectF) -> None:
        p.setPen(_LABEL_COLOR)
        font = p.font()
        font.setPixelSize(9)
        p.setFont(font)

        for frac, label in ((0.0, "0"), (0.50, ".5"), (1.0, "1")):
            y = r.bottom() - frac * r.height()
            p.drawText(
                QRectF(0, y - 6, _PADDING_LEFT - 4, 12),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

