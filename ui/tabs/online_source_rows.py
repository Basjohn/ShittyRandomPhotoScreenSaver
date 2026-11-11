"""The rows of Sources' online wallpaper list: active Just Make It Work pools and the custom feeds, each with a
right-aligned status mark painted from the theme.

A pool row is ``JMIT POOL -> <Pool Name>``: managed by the pool chooser, never selectable, edited or removed here.
A custom feed row is the URL, selectable for Remove Selected as before. The mark comes from the health the wallpaper
sources already persist (``sources.rss.source_health``): read on the tab's existing load and change edges only, never
by a fetch, a timer or polling.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from sources.rss import source_health as health_owner
from ui.settings_theme_runtime import get_active_settings_theme

KIND_ROLE = Qt.ItemDataRole.UserRole
KEY_ROLE = Qt.ItemDataRole.UserRole + 1
STATUS_ROLE = Qt.ItemDataRole.UserRole + 2

POOL = "pool"
FEED = "feed"
EMPTY = "empty"

POOL_ROW_PREFIX = "JMIT POOL -> "
EMPTY_TEXT = "No pools or custom feeds yet."
_POOL_TOOLTIP = "Managed by Just Make It Work: change pools with the Just Make It Work button."

# Theme roles of the mark per status, and of the row text per kind.
MARK_TOKENS = {
    health_owner.VALID: "popup.icon.success",
    health_owner.FAILING: "popup.icon.error",
    health_owner.UNTRIED: "text.tertiary",
}
_TEXT_TOKENS = {FEED: "control.list.text", POOL: "text.secondary", EMPTY: "text.tertiary"}


def _when(stamp: float | None) -> str:
    return datetime.fromtimestamp(stamp).strftime("%d %b %Y, %H:%M") if stamp else ""


def status_tooltip(state: health_owner.SourceHealth) -> str:
    """Why the mark is what it is: the last success, or the failure reason, or that it has not been tried."""
    if state.status == health_owner.VALID:
        return f"Valid: last fetched {_when(state.last_success_at)}."
    if state.status == health_owner.FAILING:
        reason = state.reason or "unknown error"
        last_good = f" Last success {_when(state.last_success_at)}." if state.last_success_at else " Never succeeded."
        return f"Failing: {reason} (checked {_when(state.last_checked_at)}).{last_good}"
    return "Not tried yet: it is fetched when the screensaver next needs images."


def populate_online_source_rows(list_widget: QListWidget, pools, feeds, *, cache_dir=None) -> None:
    """Rebuild the list: one row per active pool (``pools``: ``WallpaperPool`` records), then one per custom feed
    URL; one empty-state row when there are neither."""
    list_widget.clear()
    for pool in pools:
        state = health_owner.read_pool_health(pool.pool_id, cache_dir)
        item = QListWidgetItem(POOL_ROW_PREFIX + pool.label)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setData(KIND_ROLE, POOL)
        item.setData(KEY_ROLE, pool.pool_id)
        item.setData(STATUS_ROLE, state.status)
        item.setToolTip(f"{_POOL_TOOLTIP}\n{status_tooltip(state)}")
        list_widget.addItem(item)
    for url in feeds:
        state = health_owner.read_custom_feed_health(url, cache_dir)
        item = QListWidgetItem(url)
        item.setData(KIND_ROLE, FEED)
        item.setData(KEY_ROLE, url)
        item.setData(STATUS_ROLE, state.status)
        item.setToolTip(f"{url}\n{status_tooltip(state)}")
        list_widget.addItem(item)
    if list_widget.count() == 0:
        item = QListWidgetItem(EMPTY_TEXT)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(KIND_ROLE, EMPTY)
        list_widget.addItem(item)


def rows_of_kind(list_widget: QListWidget, kind: str) -> list[QListWidgetItem]:
    return [list_widget.item(row) for row in range(list_widget.count()) if list_widget.item(row).data(KIND_ROLE) == kind]


class OnlineSourceRowDelegate(QStyledItemDelegate):
    """Row text in its kind's theme role (pool rows italic and secondary), and the status mark at the right edge,
    painted as strokes in the status's theme role so it reads on light and dark themes alike."""

    MARK = 12
    MARGIN = 10
    GAP = 8

    def sizeHint(self, option, index):
        result = super().sizeHint(option, index)
        result.setHeight(max(result.height(), self.MARK + 10))
        return result

    @classmethod
    def mark_rect(cls, row: QRect) -> QRect:
        return QRect(row.right() - cls.MARGIN - cls.MARK + 1, row.center().y() - cls.MARK // 2 + 1, cls.MARK, cls.MARK)

    def paint(self, painter: QPainter, option, index) -> None:
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        kind = index.data(KIND_ROLE)
        status = index.data(STATUS_ROLE)
        text = styled.text
        style = styled.widget.style() if styled.widget is not None else QApplication.style()
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, styled, styled.widget)
        styled.text = ""
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        theme = get_active_settings_theme()
        mark = self.mark_rect(styled.rect)
        right = mark.left() - self.GAP if status in MARK_TOKENS else styled.rect.right() - self.MARGIN
        painter.save()
        font = styled.font
        font.setItalic(kind in (POOL, EMPTY))
        painter.setFont(font)
        painter.setPen(QColor(*theme.color(_TEXT_TOKENS.get(kind, "control.list.text")).as_tuple()))
        area = QRect(text_rect.left(), text_rect.top(), max(0, right - text_rect.left()), text_rect.height())
        metrics = painter.fontMetrics()
        painter.drawText(area, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         metrics.elidedText(text, Qt.TextElideMode.ElideRight, area.width()))
        if status in MARK_TOKENS:
            self._paint_mark(painter, QRectF(mark), status, QColor(*theme.color(MARK_TOKENS[status]).as_tuple()))
        painter.restore()

    @staticmethod
    def _paint_mark(painter: QPainter, box: QRectF, status: str, colour: QColor) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(colour, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inner = box.adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        if status == health_owner.VALID:
            path.moveTo(QPointF(inner.left(), inner.center().y() + inner.height() * 0.05))
            path.lineTo(QPointF(inner.left() + inner.width() * 0.38, inner.bottom() - inner.height() * 0.1))
            path.lineTo(QPointF(inner.right(), inner.top() + inner.height() * 0.12))
        elif status == health_owner.FAILING:
            path.moveTo(inner.topLeft())
            path.lineTo(inner.bottomRight())
            path.moveTo(inner.topRight())
            path.lineTo(inner.bottomLeft())
        else:
            path.addEllipse(inner.center(), inner.width() * 0.32, inner.height() * 0.32)
        painter.drawPath(path)
