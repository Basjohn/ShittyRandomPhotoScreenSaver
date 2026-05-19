"""Temporary top-level edit shell used by CUSTOM widget layout mode."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPaintEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QPushButton, QWidget


class EditShellWidget(QWidget):
    """Top-level temporary shell that mirrors a widget snapshot during edit mode."""

    drag_finished = Signal(str, QRect, QPoint)
    geometry_live_changed = Signal(str, QRect)
    resize_wheel_requested = Signal(str, int)
    reset_size_requested = Signal(str)
    context_menu_requested = Signal(QPoint)

    def __init__(
        self,
        *,
        widget_id: str,
        snapshot: QPixmap,
        initial_global_rect: QRect,
        resizable: bool,
        live_geometry_resolver: Optional[Callable[[QRect, QPoint], QRect]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.widget_id = widget_id
        self._snapshot = snapshot
        self._resizable = bool(resizable)
        self._dragging = False
        self._drag_offset = QPoint()
        self._transfer_blocked = False
        self._transfer_block_reason = ""
        self._live_geometry_resolver = live_geometry_resolver

        self._reset_btn = QPushButton("Reset", self)
        self._reset_btn.setVisible(self._resizable)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        self._reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(25, 25, 25, 210);
                color: rgba(255, 255, 255, 235);
                border: 2px solid rgba(255, 255, 255, 220);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: rgba(55, 55, 55, 225);
            }
            """
        )

        self.setGeometry(initial_global_rect)
        self._reposition_reset_button()

    def set_shell_geometry(self, global_rect: QRect) -> None:
        self.setGeometry(global_rect)
        self._reposition_reset_button()
        self.geometry_live_changed.emit(self.widget_id, QRect(self.geometry()))
        self.update()

    def current_global_rect(self) -> QRect:
        return QRect(self.geometry())

    def set_transfer_blocked(self, blocked: bool, reason: str = "") -> None:
        self._transfer_blocked = bool(blocked)
        self._transfer_block_reason = str(reason or "")
        self.update()

    def set_snapshot(self, snapshot: QPixmap) -> None:
        self._snapshot = snapshot
        self.update()

    def set_reset_enabled(self, enabled: bool) -> None:
        self._reset_btn.setEnabled(bool(enabled))

    def _reposition_reset_button(self) -> None:
        if not self._resizable:
            return
        hint = self._reset_btn.sizeHint()
        self._reset_btn.resize(hint)
        x = max(6, int((self.width() - hint.width()) / 2))
        y = max(6, self.height() - hint.height() - 10)
        self._reset_btn.move(x, y)
        self._reset_btn.raise_()

    def _on_reset_clicked(self) -> None:
        self.reset_size_requested.emit(self.widget_id)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.childAt(event.position().toPoint()) is self._reset_btn:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            super().mouseMoveEvent(event)
            return
        top_left = event.globalPosition().toPoint() - self._drag_offset
        next_rect = QRect(top_left, self.size())
        if callable(self._live_geometry_resolver):
            try:
                next_rect = QRect(self._live_geometry_resolver(QRect(next_rect), event.globalPosition().toPoint()))
            except Exception:
                next_rect = QRect(top_left, self.size())
        self.setGeometry(next_rect)
        self.geometry_live_changed.emit(self.widget_id, QRect(self.geometry()))
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            global_pos = event.globalPosition().toPoint()
            if callable(self._live_geometry_resolver):
                try:
                    next_rect = QRect(self._live_geometry_resolver(QRect(self.geometry()), global_pos))
                    self.setGeometry(next_rect)
                except Exception:
                    pass
            self.drag_finished.emit(self.widget_id, QRect(self.geometry()), global_pos)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._resizable and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.resize_wheel_requested.emit(self.widget_id, int(event.angleDelta().y()))
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition_reset_button()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Ensure the full shell bounds remain a mouse-hit region even for
        # highly transparent snapshots such as analogue clocks.
        painter.fillRect(self.rect(), QColor(255, 255, 255, 1))

        if self._snapshot is not None and not self._snapshot.isNull():
            painter.drawPixmap(self.rect(), self._snapshot)

        if self._transfer_blocked:
            overlay_pen = QPen(QColor(255, 179, 71, 245), 3)
        else:
            overlay_pen = QPen(Qt.GlobalColor.white, 2)
        painter.setPen(overlay_pen)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 10, 10)

        guide_pen = QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.DashLine)
        guide_pen.setColor(QColor(255, 214, 153, 235) if self._transfer_blocked else Qt.GlobalColor.white)
        painter.setPen(guide_pen)
        painter.drawRoundedRect(self.rect().adjusted(6, 6, -7, -7), 8, 8)

        if self._transfer_blocked and self._transfer_block_reason:
            badge_rect = self.rect().adjusted(10, 10, -10, -10)
            badge_rect.setHeight(28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(18, 18, 18, 220))
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(255, 214, 153, 245))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(9, font.pointSize()))
            painter.setFont(font)
            painter.drawText(
                badge_rect.adjusted(10, 0, -10, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._transfer_block_reason,
            )
        painter.end()
