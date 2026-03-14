"""Interactive spectrum shape editor — node-based curve control.

Left-click on empty space adds a control node (up to MAX_NODES).
Right-click on a node removes it (minimum 1 must remain).
Drag nodes to reshape the bar-height profile curve.

In **mirrored** mode the user edits only the left half of the widget
(representing center→edge) and the right half is drawn as a mirrored
ghost.  Stored node x-values always span [0, 1] regardless of mode.

In **non-mirrored** mode the full width is editable (Low→High).

The resulting curve is the **sole** driver of bar heights in the DSP
pipeline — the old parametric wave / gaussian math is removed.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
    QLinearGradient, QRadialGradient, QMouseEvent, QPaintEvent,
)
from PySide6.QtWidgets import QWidget

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

_NODE_RADIUS = 7
_HIT_RADIUS = 14
_MAX_NODES = 5
_MIN_NODES = 1

_PADDING_LEFT = 32
_PADDING_RIGHT = 12
_PADDING_TOP = 12
_PADDING_BOTTOM = 30  # extra room for notch labels

# Default nodes — these directly define bar-height profile.
# x = normalised bar position (0 .. 1), y = height multiplier (0 .. 1).
# For mirrored mode x represents center-to-edge; 0 = center, 1 = edge.
DEFAULT_NODES: List[List[float]] = [
    [0.0, 0.40],
    [0.35, 0.75],
    [0.65, 0.55],
    [1.0, 0.80],
]

# Bottom notch positions — fractional x values and labels.
# These differ between mirrored and non-mirrored modes.
_NOTCHES_MIRRORED = [
    (0.0, "Mid"),
    (0.30, "Vocal"),
    (0.65, "Low-Mid"),
    (1.0, "Bass"),
]
_NOTCHES_LINEAR = [
    (0.0, "Bass"),
    (0.25, "Low"),
    (0.50, "Mid"),
    (0.75, "Hi-Mid"),
    (1.0, "Treble"),
]


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
    center = num_bars // 2
    for i in range(num_bars):
        dist = abs(i - center)
        idx = min(dist, len(half_samples) - 1)
        result.append(half_samples[idx])
    return result


# ── Widget ───────────────────────────────────────────────────────────

class SpectrumShapeEditor(QWidget):
    """Interactive node-based spectrum shape editor widget.

    In mirrored mode the **visible editing area** is the left half of the
    plot (representing the center→edge half of the spectrum).  The right
    half automatically mirrors the curve as a ghost.  Node x-values are
    stored in [0, 1] where 0 = center, 1 = edge.

    In non-mirrored mode the full width is editable and nodes map
    directly to bar positions (0 = leftmost bar, 1 = rightmost bar).
    """

    nodes_changed = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None, mirrored: bool = True) -> None:
        super().__init__(parent)
        self._nodes: List[List[float]] = [list(n) for n in DEFAULT_NODES]
        self._mirrored: bool = mirrored
        self._drag_index: int = -1
        self._hover_index: int = -1
        self.setMinimumHeight(150)
        self.setMaximumHeight(190)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip(
            "Left-click: add node (max 5)\n"
            "Right-click node: remove\n"
            "Drag node: reshape bar heights"
        )

    # ── Public API ───────────────────────────────────────────────────

    def get_nodes(self) -> List[List[float]]:
        return [list(n) for n in self._nodes]

    def set_nodes(self, nodes: List[List[float]]) -> None:
        if not nodes:
            nodes = [list(n) for n in DEFAULT_NODES]
        self._nodes = sorted([list(n) for n in nodes], key=lambda n: n[0])
        self._clamp_all()
        self.update()

    def set_mirrored(self, mirrored: bool) -> None:
        if self._mirrored != mirrored:
            self._mirrored = mirrored
            self.update()

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

    # ── Mouse handling ───────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        px, py = event.position().x(), event.position().y()
        idx = self._hit_test(px, py)

        if event.button() == Qt.MouseButton.LeftButton:
            if idx >= 0:
                self._drag_index = idx
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            elif len(self._nodes) < _MAX_NODES:
                # Only allow adding nodes inside the editable region
                er = self._edit_rect()
                if er.contains(QPointF(px, py)):
                    nx, ny = self._pixel_to_node(px, py)
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

        if self._drag_index >= 0:
            nx, ny = self._pixel_to_node(px, py)
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
            if self._hover_index >= 0:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            if old_hover != self._hover_index:
                self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
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
        self.update()
        self.nodes_changed.emit(self.get_nodes())

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

        # Interpolated curve — editing half
        num_pts = max(2, int(er.width()))
        samples = interpolate_nodes(self._nodes, num_pts)
        # Node semantics are center->edge.  The editable half is left->right
        # edge->center, so mirrored mode draws the editable curve reversed.
        draw_samples_edit = list(reversed(samples)) if self._mirrored else samples
        self._draw_curve_in_rect(p, er, draw_samples_edit, primary=True)

        # Mirrored ghost on the right half
        if self._mirrored:
            mirror_rect = QRectF(
                r.left() + r.width() * 0.5, r.top(),
                r.width() * 0.5, r.height(),
            )
            # Right ghost is center->edge (left->right), same orientation as
            # the underlying sample domain.
            self._draw_curve_in_rect(p, mirror_rect, samples, primary=False)

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
        self, p: QPainter, rect: QRectF, samples: List[float], primary: bool,
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

        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        if primary:
            grad.setColorAt(0.0, _CURVE_FILL_TOP)
        else:
            grad.setColorAt(0.0, _MIRROR_FILL_TOP)
        grad.setColorAt(1.0, _CURVE_FILL_BOT)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill_path)

        curve_col = _CURVE_COLOR if primary else _MIRROR_CURVE_COLOR
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
        notches = _NOTCHES_MIRRORED if self._mirrored else _NOTCHES_LINEAR
        font = p.font()
        font.setPixelSize(8)
        p.setFont(font)

        for frac, label in notches:
            if self._mirrored:
                center_x = r.left() + r.width() * 0.5
                half_w = r.width() * 0.5
                # Left half notch
                x_left = center_x - frac * half_w
                self._draw_single_notch(p, r, x_left, label)
                # Right half mirrored notch
                x_right = center_x + frac * half_w
                if abs(x_left - x_right) > 4:
                    self._draw_single_notch(p, r, x_right, label)
            else:
                x = r.left() + frac * r.width()
                self._draw_single_notch(p, r, x, label)

    def _draw_single_notch(self, p: QPainter, r: QRectF, x: float, label: str) -> None:
        p.setPen(QPen(_NOTCH_COLOR, 1.0))
        p.drawLine(QPointF(x, r.bottom()), QPointF(x, r.bottom() + 5))
        p.setPen(_ZONE_LABEL_COLOR)
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
