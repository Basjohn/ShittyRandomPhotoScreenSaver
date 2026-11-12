"""The rows of Sources' online wallpaper list: active Just Make It Work pools and the custom feeds, each with a
right-aligned status mark painted from the theme.

A pool row reads ``JMIT POOL → <Pool Name>``: the ``JMIT POOL`` tag in the list's accent, the arrow glyph, then the
pool name in the row's normal text. It is managed by the pool chooser, never selectable, edited or removed here.
A custom feed row is the URL, selectable for Remove Selected as before. The mark comes from the health the wallpaper
sources already persist (``sources.rss.source_health``): read on the tab's existing load and change edges only, never
by a fetch, a timer or polling.

The list wears the shared Settings list style (``shared_styles.apply_settings_list_style``: typography and row
geometry) over the root list colours; this delegate draws with the font the style gives the list and sets none.
"""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from sources.rss import source_health as health_owner
from ui.settings_theme_runtime import get_active_settings_theme
from ui.widgets.theme_list import LIST_GLYPH_STROKE

KIND_ROLE = Qt.ItemDataRole.UserRole
KEY_ROLE = Qt.ItemDataRole.UserRole + 1
STATUS_ROLE = Qt.ItemDataRole.UserRole + 2
NAME_ROLE = Qt.ItemDataRole.UserRole + 3

POOL = "pool"
FEED = "feed"
EMPTY = "empty"

POOL_TAG = "JMIT POOL"
POOL_ARROW = "→"
# The row's plain text (accessibility, tooltips, tests): the operator's wording.
POOL_ROW_PREFIX = f"{POOL_TAG} -> "
EMPTY_TEXT = "No pools or custom feeds yet."
_POOL_TOOLTIP = "Managed by Just Make It Work: change pools with the Just Make It Work button."

# Theme roles of the mark per status, and of each painted text part.
MARK_TOKENS = {
    health_owner.VALID: "popup.icon.success",
    health_owner.FAILING: "popup.icon.error",
    health_owner.UNTRIED: "text.tertiary",
}
TAG_TOKEN = "control.list.selected_accent"
ARROW_TOKEN = "text.secondary"
NAME_TOKEN = "control.list.text"
EMPTY_TOKEN = "text.secondary"


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
        item.setData(NAME_ROLE, pool.label)
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


def active_pools(settings) -> tuple:
    """The active pools in their canonical order (a settings store or the Guided Setup draft)."""
    from sources.rss.pools import WALLPAPER_POOLS, read_pool_selection
    active = read_pool_selection(settings).active_ids
    return tuple(pool for pool in WALLPAPER_POOLS if pool.pool_id in active)


def refresh_online_source_list(list_widget: QListWidget, settings, *, cache_dir=None) -> tuple:
    """The one read both Settings' Sources tab and Guided Setup's sources page make: the active pools and the
    custom feeds of ``settings`` become the list's rows. Returns the active pools."""
    pools = active_pools(settings)
    populate_online_source_rows(list_widget, pools, list(settings.get("sources.rss_feeds") or ()), cache_dir=cache_dir)
    return pools


def build_online_source_list(min_height: int) -> QListWidget:
    """The online sources list as Settings shows it: the outlined list in the shared Settings list style, the row
    delegate, and URLs that elide inside the row instead of scrolling sideways."""
    from ui.tabs import shared_styles
    from ui.widgets.continuous_border import OutlinedListWidget
    list_widget = OutlinedListWidget()
    list_widget.setMinimumHeight(min_height)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    shared_styles.apply_settings_list_style(list_widget)
    list_widget.setItemDelegate(OnlineSourceRowDelegate(list_widget))
    return list_widget


def selected_feed_url(list_widget: QListWidget) -> str | None:
    """The custom feed URL of the current row, or None (a pool row is managed by the pool chooser)."""
    item = list_widget.currentItem()
    if item is None or item.data(KIND_ROLE) != FEED:
        return None
    return item.data(KEY_ROLE)


def rows_of_kind(list_widget: QListWidget, kind: str) -> list[QListWidgetItem]:
    return [list_widget.item(row) for row in range(list_widget.count()) if list_widget.item(row).data(KIND_ROLE) == kind]


def _token_colour(theme, token: str) -> QColor:
    return QColor(*theme.color(token).as_tuple())


class OnlineSourceRowDelegate(QStyledItemDelegate):
    """Rows drawn like the Themes list's: the style's own item panel (surface, hover, selection) and text, the
    status mark at the right edge where the Themes rows carry their palette square.

    A feed URL elides in the middle and stops short of the mark. A pool row paints its tag, arrow and name in their
    theme roles with the list's font; nothing is slanted or emboldened.
    """

    MARGIN = 10  # the Themes rows' right margin
    GAP = 10     # the Themes rows' gap between text and decoration
    PART_GAP_EM = 0.35  # space between tag, arrow and name, in ems of the list's font

    def sizeHint(self, option, index):
        result = super().sizeHint(option, index)
        # Text elides inside the viewport; a long URL must never widen the row past it (as the Themes rows).
        result.setWidth(2 * self.MARGIN + self.GAP)
        return result

    @classmethod
    def mark_rect(cls, row: QRect, font) -> QRectF:
        """The mark's square: the font's cap height, its centre on the text's cap line (same box as the text's
        vertical centring), at the row's right margin."""
        metrics = QFontMetricsF(font)
        side = metrics.capHeight()
        baseline = row.top() + (row.height() - metrics.height()) / 2.0 + metrics.ascent()
        return QRectF(row.right() + 1 - cls.MARGIN - side, baseline - side, side, side)

    def paint(self, painter: QPainter, option, index) -> None:
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        kind = index.data(KIND_ROLE)
        status = index.data(STATUS_ROLE)
        style = styled.widget.style() if styled.widget is not None else QApplication.style()
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, styled, styled.widget)
        mark = self.mark_rect(styled.rect, styled.font) if status in MARK_TOKENS else None
        right = int(mark.left()) - self.GAP if mark is not None else styled.rect.right() + 1 - self.MARGIN
        area = QRect(text_rect.left(), text_rect.top(), max(0, right - text_rect.left()), text_rect.height())
        theme = get_active_settings_theme()
        if kind == FEED:
            styled.text = styled.fontMetrics.elidedText(styled.text, Qt.TextElideMode.ElideMiddle, area.width())
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        else:
            styled.text = ""
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
            if kind == POOL:
                parts = ((POOL_TAG, TAG_TOKEN), (POOL_ARROW, ARROW_TOKEN),
                         (str(index.data(NAME_ROLE) or ""), NAME_TOKEN))
            else:
                parts = ((str(index.data(Qt.ItemDataRole.DisplayRole) or ""), EMPTY_TOKEN),)
            # The style insets item text by the focus-frame margin + 1 inside the text rect; painted parts match it.
            inset = style.pixelMetric(QStyle.PixelMetric.PM_FocusFrameHMargin, None, styled.widget) + 1
            self._paint_parts(painter, styled, area.adjusted(inset, 0, -inset, 0), parts, theme)
        if mark is not None:
            self._paint_mark(painter, mark, status, _token_colour(theme, MARK_TOKENS[status]))

    def _paint_parts(self, painter: QPainter, styled, area: QRect, parts, theme) -> None:
        painter.save()
        painter.setFont(styled.font)  # the list's own font, from the shared list style
        metrics = painter.fontMetrics()
        gap = round(metrics.height() * self.PART_GAP_EM)
        x = area.left()
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for number, (text, token) in enumerate(parts):
            room = area.right() + 1 - x
            if room <= 0:
                break
            last = number == len(parts) - 1
            shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, room) if last else text
            painter.setPen(_token_colour(theme, token))
            painter.drawText(QRect(x, area.top(), room, area.height()), flags, shown)
            x += metrics.horizontalAdvance(shown) + gap
        painter.restore()

    @staticmethod
    def _paint_mark(painter: QPainter, box: QRectF, status: str, colour: QColor) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(colour, LIST_GLYPH_STROKE)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inner = box.adjusted(LIST_GLYPH_STROKE / 2, LIST_GLYPH_STROKE / 2,
                             -LIST_GLYPH_STROKE / 2, -LIST_GLYPH_STROKE / 2)
        path = QPainterPath()
        if status == health_owner.VALID:
            path.moveTo(QPointF(inner.left(), inner.center().y() + inner.height() * 0.08))
            path.lineTo(QPointF(inner.left() + inner.width() * 0.36, inner.bottom()))
            path.lineTo(QPointF(inner.right(), inner.top()))
        elif status == health_owner.FAILING:
            cross = inner.adjusted(inner.width() * 0.08, inner.height() * 0.08,
                                   -inner.width() * 0.08, -inner.height() * 0.08)
            path.moveTo(cross.topLeft())
            path.lineTo(cross.bottomRight())
            path.moveTo(cross.topRight())
            path.lineTo(cross.bottomLeft())
        else:
            path.addEllipse(inner.center(), inner.width() * 0.36, inner.height() * 0.36)
        painter.drawPath(path)
        painter.restore()
