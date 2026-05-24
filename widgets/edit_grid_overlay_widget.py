"""Temporary top-level grid overlay for CUSTOM layout edit mode."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class EditGridOverlayWidget(QWidget):
    """Display-local grid overlay shown only during active edit sessions.

    This stays above the compositor/wallpaper surface and below the temporary
    edit shells so the user can see the snap grid and edge gutters without
    affecting interaction routing or runtime widgets.
    """

    def __init__(
        self,
        *,
        global_rect: QRect,
        grid_step_px: int,
        gutter_px: int,
        parent: QWidget | None = None,
    ) -> None:
        if parent is not None:
            super().__init__(parent)
        else:
            flags = (
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )
            super().__init__(parent, flags)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._grid_step_px = max(4, int(grid_step_px))
        self._gutter_px = max(0, int(gutter_px))
        self._active_vertical_guides: tuple[tuple[int, str], ...] = ()
        self._active_horizontal_guides: tuple[tuple[int, str], ...] = ()
        self._active_vertical_assists: tuple[tuple[int, str], ...] = ()
        self._active_horizontal_assists: tuple[tuple[int, str], ...] = ()
        self._static_grid_cache: QPixmap | None = None
        if parent is not None:
            self.setGeometry(0, 0, max(1, global_rect.width()), max(1, global_rect.height()))
        else:
            self.setGeometry(global_rect)

    def set_active_guides(
        self,
        *,
        vertical: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        horizontal: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        vertical_assists: tuple[tuple[int, str], ...] | list[tuple[int, str]],
        horizontal_assists: tuple[tuple[int, str], ...] | list[tuple[int, str]],
    ) -> None:
        next_vertical = tuple((int(pos), str(kind)) for pos, kind in vertical)
        next_horizontal = tuple((int(pos), str(kind)) for pos, kind in horizontal)
        next_vertical_assists = tuple((int(pos), str(kind)) for pos, kind in vertical_assists)
        next_horizontal_assists = tuple((int(pos), str(kind)) for pos, kind in horizontal_assists)
        if (
            next_vertical == self._active_vertical_guides
            and next_horizontal == self._active_horizontal_guides
            and next_vertical_assists == self._active_vertical_assists
            and next_horizontal_assists == self._active_horizontal_assists
        ):
            return
        self._active_vertical_guides = next_vertical
        self._active_horizontal_guides = next_horizontal
        self._active_vertical_assists = next_vertical_assists
        self._active_horizontal_assists = next_horizontal_assists
        self.update()

    def _build_static_grid_cache(self) -> QPixmap:
        width = max(1, self.width())
        height = max(1, self.height())
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        major_step = self._grid_step_px * 4
        minor_pen = QPen(QColor(255, 255, 255, 28), 1)
        major_pen = QPen(QColor(255, 255, 255, 58), 1)
        gutter_pen = QPen(QColor(255, 232, 184, 76), 1)

        for x in range(0, width, self._grid_step_px):
            painter.setPen(major_pen if (x % major_step) == 0 else minor_pen)
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, self._grid_step_px):
            painter.setPen(major_pen if (y % major_step) == 0 else minor_pen)
            painter.drawLine(0, y, width, y)

        if self._gutter_px > 0:
            painter.setPen(gutter_pen)
            x_positions = {
                self._gutter_px,
                max(0, width - self._gutter_px - 1),
            }
            y_positions = {
                self._gutter_px,
                max(0, height - self._gutter_px - 1),
            }
            for x in sorted(x_positions):
                painter.drawLine(x, 0, x, height)
            for y in sorted(y_positions):
                painter.drawLine(0, y, width, y)
        painter.end()
        return pixmap

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self._static_grid_cache = None
        super().resizeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        width = max(1, self.width())
        height = max(1, self.height())
        if (
            self._static_grid_cache is None
            or self._static_grid_cache.isNull()
            or self._static_grid_cache.width() != width
            or self._static_grid_cache.height() != height
        ):
            self._static_grid_cache = self._build_static_grid_cache()
        if self._static_grid_cache is not None and not self._static_grid_cache.isNull():
            painter.drawPixmap(0, 0, self._static_grid_cache)

        assist_pen = QPen(QColor(180, 110, 255, 235), 3.0)
        for x, _kind in self._active_vertical_assists:
            painter.setPen(assist_pen)
            clamped_x = max(0, min(int(x), width - 1))
            painter.drawLine(clamped_x, 0, clamped_x, height)
        for y, _kind in self._active_horizontal_assists:
            painter.setPen(assist_pen)
            clamped_y = max(0, min(int(y), height - 1))
            painter.drawLine(0, clamped_y, width, clamped_y)

        painter.end()
