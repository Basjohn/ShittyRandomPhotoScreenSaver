"""Self-contained overlay that paints the StyledComboBox knob crisply at runtime."""
from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QObject, QEvent, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

KnobState = Literal["normal", "hover", "pressed", "disabled"]


class ComboKnobOverlay(QWidget):
    """Paints a single circular indicator matching the spinbox dots."""

    _SPINBOX_DOT_DIAMETER = 10.0
    _DOT_SCALE = 1.2  # 20% larger than spinbox dots
    _DOT_DIAMETER = _SPINBOX_DOT_DIAMETER * _DOT_SCALE
    _RIGHT_PADDING = 14.0
    _VERTICAL_MARGIN = 3.0
    _VERTICAL_OFFSET = 5.5
    _MIN_CLEARANCE = 2.0

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._host_ref = parent
        self._state: KnobState = "normal"
        self._paint_rect = QRectF()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_state(self, state: KnobState) -> None:
        if state == self._state:
            return
        self._state = state
        self.update()

    def set_paint_rect(self, rect: QRectF) -> None:
        if rect == self._paint_rect:
            return
        self._paint_rect = rect
        self.update()

    # ------------------------------------------------------------------
    # QWidget overrides
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        if self._paint_rect.isEmpty():
            return

        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )
        self._paint_custom_knob(painter, self._paint_rect)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _paint_custom_knob(self, painter: QPainter, rect: QRectF) -> None:
        if rect.isEmpty():
            return

        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform,
            True,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._resolve_color())
        painter.drawEllipse(rect)

    def _resolve_color(self) -> QColor:
        host = self._host_ref
        if host is None or not host.isEnabled():
            return QColor("#6a6a6a")
        if self._state == "pressed":
            return QColor("#2d2d2d")
        if self._state == "hover":
            return QColor("#4d4d4d")
        return QColor("#ffffff")


class ComboKnobController(QObject):
    """Attaches the overlay to any combobox-like widget and keeps it in sync."""

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self._overlay = ComboKnobOverlay(host)
        self._overlay.show()
        self._hovered = False
        self._pressed = False
        host.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        host.installEventFilter(self)
        self._position_overlay()
        self._update_state()

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def eventFilter(self, watched, event):  # type: ignore[override]
        if watched is not self._host:
            return super().eventFilter(watched, event)

        etype = event.type()
        if etype == QEvent.Type.Resize:
            self._position_overlay()
        elif etype == QEvent.Type.HoverEnter:
            self._hovered = True
            self._update_state()
        elif etype == QEvent.Type.HoverLeave:
            self._hovered = False
            self._update_state()
        elif etype == QEvent.Type.FocusIn:
            self._hovered = True
            self._update_state()
        elif etype == QEvent.Type.FocusOut:
            self._hovered = False
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.EnabledChange:
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._update_state()
        elif etype == QEvent.Type.MouseButtonRelease:
            self._pressed = False
            self._update_state()
        elif etype == QEvent.Type.Hide:
            self._overlay.hide()
        elif etype == QEvent.Type.Show:
            self._overlay.show()
            self._position_overlay()
            self._update_state()

        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _position_overlay(self) -> None:
        if not self._host.isVisible():
            return

        host_rect: QRect = self._host.rect()
        if host_rect.height() <= 0:
            return

        diameter = min(
            self._overlay._DOT_DIAMETER,
            host_rect.height() - (self._overlay._VERTICAL_MARGIN * 2),
        )
        diameter = max(8.0, diameter)  # guard for very small combos

        dynamic_offset = min(
            self._overlay._VERTICAL_OFFSET,
            max(3.2, host_rect.height() * 0.13),
        )

        x = host_rect.width() - diameter - self._overlay._RIGHT_PADDING
        y = (host_rect.height() - diameter) / 2 - dynamic_offset

        if y < self._overlay._MIN_CLEARANCE:
            y = self._overlay._MIN_CLEARANCE
        elif y + diameter > host_rect.height() - self._overlay._MIN_CLEARANCE:
            y = host_rect.height() - diameter - self._overlay._MIN_CLEARANCE

        if host_rect.width() <= diameter:
            x = host_rect.width() - diameter

        geom = QRectF(x, y, diameter, diameter)
        self._overlay.setGeometry(
            int(round(geom.x())),
            int(round(geom.y())),
            max(1, int(round(geom.width()))),
            max(1, int(round(geom.height()))),
        )
        self._overlay.set_paint_rect(QRectF(0.0, 0.0, geom.width(), geom.height()))
        self._overlay.raise_()

    def _update_state(self) -> None:
        if not self._host.isEnabled():
            state: KnobState = "disabled"
        elif self._pressed:
            state = "pressed"
        elif self._hovered:
            state = "hover"
        else:
            state = "normal"
        self._overlay.set_state(state)


__all__ = ["ComboKnobController"]
