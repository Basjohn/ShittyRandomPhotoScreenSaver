"""Temporary top-level edit shell used by CUSTOM widget layout mode."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRect, Qt, QEvent, Signal
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPaintEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QPushButton, QWidget


class EditShellWidget(QWidget):
    """Top-level temporary shell that mirrors a widget snapshot during edit mode."""

    _CORNER_CURSOR_GUTTER_PX = 28
    _RESIZE_CORNER_TOP_LEFT = "top_left"
    _RESIZE_CORNER_TOP_RIGHT = "top_right"
    _RESIZE_CORNER_BOTTOM_LEFT = "bottom_left"
    _RESIZE_CORNER_BOTTOM_RIGHT = "bottom_right"

    drag_finished = Signal(str, QRect, QPoint)
    geometry_live_changed = Signal(str, QRect)
    resize_wheel_requested = Signal(str, int)
    resize_drag_started = Signal(str, str, QRect)
    resize_drag_live_changed = Signal(str, str, QRect, QPoint)
    resize_drag_finished = Signal(str, str, QRect, QPoint)
    reset_size_requested = Signal(str)
    reset_position_requested = Signal(str)
    remove_requested = Signal(str)
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
        self._resizing = False
        self._resize_corner: str | None = None
        self._drag_offset = QPoint()
        self._pressed_button: QPushButton | None = None
        self._transfer_blocked = False
        self._transfer_block_reason = ""
        self._live_geometry_resolver = live_geometry_resolver
        self._active_vertical_guides: tuple[tuple[int, str], ...] = ()
        self._active_horizontal_guides: tuple[tuple[int, str], ...] = ()
        self._active_vertical_assists: tuple[tuple[int, str], ...] = ()
        self._active_horizontal_assists: tuple[tuple[int, str], ...] = ()

        button_stylesheet = """
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
            QPushButton:disabled {
                background-color: rgba(25, 25, 25, 140);
                color: rgba(255, 255, 255, 120);
                border-color: rgba(255, 255, 255, 120);
            }
            """
        self._reset_position_btn = QPushButton("Reset Position", self)
        self._reset_size_btn = QPushButton("Reset Size", self)
        self._remove_btn = QPushButton("×", self)
        self._reset_size_btn.clicked.connect(self._on_reset_size_clicked)
        self._reset_position_btn.clicked.connect(self._on_reset_position_clicked)
        self._remove_btn.clicked.connect(self._on_remove_clicked)
        self._reset_size_btn.installEventFilter(self)
        self._reset_position_btn.installEventFilter(self)
        self._remove_btn.installEventFilter(self)
        self._reset_size_btn.setStyleSheet(button_stylesheet)
        self._reset_position_btn.setStyleSheet(button_stylesheet)
        self._reset_size_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_position_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(65, 20, 20, 215);
                color: rgba(255, 255, 255, 235);
                border: 2px solid rgba(255, 255, 255, 220);
                border-radius: 8px;
                padding: 0px;
                font-size: 14px;
                font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
                font-weight: 800;
            }
            QPushButton:hover {
                background-color: rgba(110, 30, 30, 230);
            }
            QPushButton:disabled {
                background-color: rgba(65, 20, 20, 120);
                color: rgba(255, 255, 255, 120);
                border-color: rgba(255, 255, 255, 120);
            }
            """
        )
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reset_size_btn.setEnabled(False)
        self._reset_position_btn.setEnabled(False)
        self._remove_btn.hide()
        self._remove_btn.setEnabled(False)

        self.setGeometry(initial_global_rect)
        self._reposition_reset_button()
        self._update_hover_cursor()

    def eventFilter(self, watched, event):  # type: ignore[override]
        reset_size_btn = getattr(self, "_reset_size_btn", None)
        reset_position_btn = getattr(self, "_reset_position_btn", None)
        remove_btn = getattr(self, "_remove_btn", None)
        if watched in (reset_size_btn, reset_position_btn, remove_btn):
            if event.type() == QEvent.Type.MouseButtonPress:
                if isinstance(watched, QPushButton) and watched.isEnabled():
                    self._pressed_button = watched
                event.accept()
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                pressed = self._pressed_button
                self._pressed_button = None
                if pressed is self._reset_size_btn and self._reset_size_btn.isEnabled():
                    self._on_reset_size_clicked()
                elif pressed is self._reset_position_btn and self._reset_position_btn.isEnabled():
                    self._on_reset_position_clicked()
                elif pressed is self._remove_btn and self._remove_btn.isEnabled():
                    self._on_remove_clicked()
                event.accept()
                return True
        return super().eventFilter(watched, event)

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

    def set_alignment_guides(
        self,
        *,
        vertical: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        horizontal: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        vertical_assists: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        horizontal_assists: tuple[tuple[int, str], ...] | list[tuple[int, str]],
    ) -> None:
        self._active_vertical_guides = tuple((int(pos), str(kind)) for pos, kind in vertical)
        self._active_horizontal_guides = tuple((int(pos), str(kind)) for pos, kind in horizontal)
        self._active_vertical_assists = tuple((int(pos), str(kind)) for pos, kind in vertical_assists)
        self._active_horizontal_assists = tuple((int(pos), str(kind)) for pos, kind in horizontal_assists)
        self.update()

    def set_reset_size_enabled(self, enabled: bool) -> None:
        self._reset_size_btn.setEnabled(bool(enabled) and self._resizable)

    def set_reset_position_enabled(self, enabled: bool) -> None:
        self._reset_position_btn.setEnabled(bool(enabled))

    def set_remove_enabled(self, enabled: bool) -> None:
        visible = bool(enabled)
        self._remove_btn.setVisible(visible)
        self._remove_btn.setEnabled(visible)
        if visible:
            self._remove_btn.raise_()

    def _reposition_reset_button(self) -> None:
        size_hint = self._reset_size_btn.sizeHint()
        pos_hint = self._reset_position_btn.sizeHint()
        remove_size = self._remove_btn.sizeHint()
        self._reset_size_btn.resize(size_hint)
        self._reset_position_btn.resize(pos_hint)
        self._remove_btn.resize(max(22, remove_size.width()), max(22, remove_size.height()))
        spacing = 8
        total_width = size_hint.width() + pos_hint.width() + spacing
        start_x = max(6, int((self.width() - total_width) / 2))
        y = max(6, self.height() - max(size_hint.height(), pos_hint.height()) - 10)
        self._reset_size_btn.move(start_x, y)
        self._reset_position_btn.move(start_x + size_hint.width() + spacing, y)
        self._remove_btn.move(max(6, self.width() - self._remove_btn.width() - 8), 8)
        self._reset_size_btn.raise_()
        self._reset_position_btn.raise_()
        if self._remove_btn.isVisible():
            self._remove_btn.raise_()

    def _on_reset_size_clicked(self) -> None:
        self.reset_size_requested.emit(self.widget_id)

    def _on_reset_position_clicked(self) -> None:
        self.reset_position_requested.emit(self.widget_id)

    def _on_remove_clicked(self) -> None:
        self.remove_requested.emit(self.widget_id)

    def _resize_corner_cursor_for_pos(self, local_pos: QPoint) -> Qt.CursorShape | None:
        corner = self._resize_corner_for_pos(local_pos)
        if corner in (self._RESIZE_CORNER_TOP_LEFT, self._RESIZE_CORNER_BOTTOM_RIGHT):
            return Qt.CursorShape.SizeFDiagCursor
        if corner in (self._RESIZE_CORNER_TOP_RIGHT, self._RESIZE_CORNER_BOTTOM_LEFT):
            return Qt.CursorShape.SizeBDiagCursor
        return None

    def _resize_corner_for_pos(self, local_pos: QPoint) -> str | None:
        if not self._resizable:
            return None
        gutter = max(16, min(self._CORNER_CURSOR_GUTTER_PX, min(self.width(), self.height()) // 3 or 16))
        near_left = local_pos.x() <= gutter
        near_right = local_pos.x() >= max(0, self.width() - gutter)
        near_top = local_pos.y() <= gutter
        near_bottom = local_pos.y() >= max(0, self.height() - gutter)

        if near_top and near_left:
            return self._RESIZE_CORNER_TOP_LEFT
        if near_top and near_right:
            return self._RESIZE_CORNER_TOP_RIGHT
        if near_bottom and near_left:
            return self._RESIZE_CORNER_BOTTOM_LEFT
        if near_bottom and near_right:
            return self._RESIZE_CORNER_BOTTOM_RIGHT
        return None

    def _resolve_cursor_shape(self, local_pos: QPoint) -> Qt.CursorShape:
        if self._resizing:
            resize_corner = self._resize_corner
            if resize_corner in (self._RESIZE_CORNER_TOP_LEFT, self._RESIZE_CORNER_BOTTOM_RIGHT):
                return Qt.CursorShape.SizeFDiagCursor
            if resize_corner in (self._RESIZE_CORNER_TOP_RIGHT, self._RESIZE_CORNER_BOTTOM_LEFT):
                return Qt.CursorShape.SizeBDiagCursor
            resize_cursor = self._resize_corner_cursor_for_pos(local_pos)
            if resize_cursor is not None:
                return resize_cursor
        if self._dragging:
            return Qt.CursorShape.ClosedHandCursor
        if self._reset_size_btn.geometry().contains(local_pos):
            return Qt.CursorShape.PointingHandCursor
        if self._reset_position_btn.geometry().contains(local_pos):
            return Qt.CursorShape.PointingHandCursor
        if self._remove_btn.isVisible() and self._remove_btn.geometry().contains(local_pos):
            return Qt.CursorShape.PointingHandCursor
        resize_cursor = self._resize_corner_cursor_for_pos(local_pos)
        if resize_cursor is not None:
            return resize_cursor
        return Qt.CursorShape.OpenHandCursor

    def _update_hover_cursor(self, local_pos: QPoint | None = None) -> None:
        if local_pos is None:
            local_pos = self.mapFromGlobal(QCursor.pos())
        self.setCursor(self._resolve_cursor_shape(local_pos))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        local_pos = event.position().toPoint()
        if (
            self._reset_size_btn.geometry().contains(local_pos)
            or self._reset_position_btn.geometry().contains(local_pos)
            or self._remove_btn.geometry().contains(local_pos)
        ):
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.context_menu_requested.emit(event.globalPosition().toPoint())
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            resize_corner = self._resize_corner_for_pos(local_pos)
            if resize_corner is not None:
                self._resizing = True
                self._resize_corner = resize_corner
                self.resize_drag_started.emit(self.widget_id, resize_corner, QRect(self.geometry()))
                self._update_hover_cursor(local_pos)
                event.accept()
                return
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._resizing:
            self.resize_drag_live_changed.emit(
                self.widget_id,
                str(self._resize_corner or ""),
                QRect(self.geometry()),
                event.globalPosition().toPoint(),
            )
            event.accept()
            return
        if not self._dragging:
            self._update_hover_cursor(event.position().toPoint())
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
        local_pos = event.position().toPoint()
        if (
            self._reset_size_btn.geometry().contains(local_pos)
            or self._reset_position_btn.geometry().contains(local_pos)
            or self._remove_btn.geometry().contains(local_pos)
        ):
            self._pressed_button = None
            event.accept()
            return
        if self._resizing and event.button() == Qt.MouseButton.LeftButton:
            self._resizing = False
            resize_corner = str(self._resize_corner or "")
            self._resize_corner = None
            global_pos = event.globalPosition().toPoint()
            self._update_hover_cursor(local_pos)
            self.resize_drag_finished.emit(self.widget_id, resize_corner, QRect(self.geometry()), global_pos)
            event.accept()
            return
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            global_pos = event.globalPosition().toPoint()
            if callable(self._live_geometry_resolver):
                try:
                    next_rect = QRect(self._live_geometry_resolver(QRect(self.geometry()), global_pos))
                    self.setGeometry(next_rect)
                except Exception:
                    pass
            self._update_hover_cursor(local_pos)
            self.drag_finished.emit(self.widget_id, QRect(self.geometry()), global_pos)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_button = None
            self._update_hover_cursor(local_pos)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._resizable:
            self.resize_wheel_requested.emit(self.widget_id, int(event.angleDelta().y()))
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._reposition_reset_button()
        self._update_hover_cursor()

    def enterEvent(self, event) -> None:  # type: ignore[override]
        super().enterEvent(event)
        self._update_hover_cursor()

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        super().leaveEvent(event)
        self.unsetCursor()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Ensure the full shell bounds remain a mouse-hit region even for
        # highly transparent snapshots such as analogue clocks.
        painter.fillRect(self.rect(), QColor(255, 255, 255, 1))

        if self._snapshot is not None and not self._snapshot.isNull():
            painter.drawPixmap(self.rect(), self._snapshot)

        assist_pen = QPen(QColor(180, 110, 255, 235), 3.0)
        shell_rect = self.geometry()
        primary_vertical_local = None
        primary_horizontal_local = None
        if self._active_vertical_guides:
            candidate = int(self._active_vertical_guides[0][0]) - shell_rect.x()
            if 0 <= candidate < self.width():
                primary_vertical_local = candidate
        if self._active_horizontal_guides:
            candidate = int(self._active_horizontal_guides[0][0]) - shell_rect.y()
            if 0 <= candidate < self.height():
                primary_horizontal_local = candidate

        def _draw_vertical_guide(local_x: int, pen: QPen, preferred_y: int | None = None) -> None:
            painter.setPen(pen)
            if preferred_y is not None and 0 <= preferred_y < self.height():
                anchor_y = 0 if preferred_y <= (self.height() / 2) else self.height() - 1
                painter.drawLine(local_x, anchor_y, local_x, preferred_y)
                return
            painter.drawLine(local_x, 0, local_x, self.height())

        def _draw_horizontal_guide(local_y: int, pen: QPen, preferred_x: int | None = None) -> None:
            painter.setPen(pen)
            if preferred_x is not None and 0 <= preferred_x < self.width():
                anchor_x = 0 if preferred_x <= (self.width() / 2) else self.width() - 1
                painter.drawLine(anchor_x, local_y, preferred_x, local_y)
                return
            painter.drawLine(0, local_y, self.width(), local_y)

        for x, _kind in self._active_vertical_assists:
            local_x = int(x) - shell_rect.x()
            if 0 <= local_x < self.width():
                _draw_vertical_guide(local_x, assist_pen, primary_horizontal_local)
        for y, _kind in self._active_horizontal_assists:
            local_y = int(y) - shell_rect.y()
            if 0 <= local_y < self.height():
                _draw_horizontal_guide(local_y, assist_pen, primary_vertical_local)

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
