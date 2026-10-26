"""Theme catalogue row decorations; palette data and favourites stay separate from activation."""
from __future__ import annotations

from collections import Counter
import math

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QToolTip

from ui.settings_theme_runtime import get_active_settings_theme
from ui.widgets.continuous_border import OutlinedListWidget


PALETTE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
FAVOURITE_ROLE = PALETTE_ROLE + 1
_ORDER_ROLE = FAVOURITE_ROLE + 1
FAVOURITES_KEY = "ui.theme_favourites"


def dominant_theme_colours(theme) -> tuple[tuple[int, int, int], ...]:
    """Four representative authored RGBs, ranked by semantic-role prevalence.

    Alpha weights translucent roles; invisible and shadow roles do not swamp the
    palette with effect black. Nearby shades share a cluster, represented by its
    most prevalent actual colour. This is preview data, never a rendering palette.
    Fully transparent palettes still preview their authored (latent) RGBs.
    """
    counts = Counter()
    colours = [colour for role, colour in theme.colors.items() if "shadow" not in role]
    visible = any(colour.a for colour in colours)
    for colour in colours:
        weight = colour.a if visible else 1
        if weight:
            counts[(colour.r, colour.g, colour.b)] += weight
    ranked = sorted(counts, key=lambda rgb: (-counts[rgb], rgb))
    if not ranked:
        raise ValueError("A theme preview requires visible semantic colours")
    clusters = []
    for rgb in ranked:
        near = next((cluster for cluster in clusters
                     if sum((a - b) ** 2 for a, b in zip(rgb, cluster[0])) < 32 ** 2), None)
        if near is None:
            clusters.append([rgb, counts[rgb]])
        else:
            near[1] += counts[rgb]
    selected = [rgb for rgb, _ in sorted(clusters, key=lambda cluster: (-cluster[1], cluster[0]))[:4]]
    selected.extend(rgb for rgb in ranked if rgb not in selected)
    return tuple((selected * 4)[:4])


def read_theme_favourites(settings, kind: str) -> set[str]:
    raw = settings.get(FAVOURITES_KEY, {})
    values = raw.get(kind, ()) if isinstance(raw, dict) else ()
    return {value for value in values if isinstance(value, str) and value} if isinstance(values, (list, tuple)) else set()


class _ThemeRowDelegate(QStyledItemDelegate):
    SIDE = 24
    MARGIN = 10
    GAP = 10
    STAR = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._star_path = QPainterPath()
        for number in range(10):
            radius = self.STAR * (.46 if number % 2 == 0 else .21)
            angle = math.radians(number * 36 - 90)
            point = QPointF(radius * math.cos(angle), radius * math.sin(angle))
            if number == 0:
                self._star_path.moveTo(point)
            else:
                self._star_path.lineTo(point)
        self._star_path.closeSubpath()

    @classmethod
    def decoration_rects(cls, row: QRect) -> tuple[QRect, QRect]:
        square = QRect(row.right() - cls.MARGIN - cls.SIDE + 1,
                       row.center().y() - cls.SIDE // 2 + 1, cls.SIDE, cls.SIDE)
        star = QRect(square.left() - cls.GAP - cls.STAR,
                     row.center().y() - cls.STAR // 2 + 1, cls.STAR, cls.STAR)
        return star, square

    def sizeHint(self, option, index):
        result = super().sizeHint(option, index)
        result.setHeight(max(result.height(), self.SIDE + 8))
        # Names elide inside the viewport; their length must never push the
        # decorations beyond the visible right edge.
        result.setWidth(self.SIDE + self.STAR + self.GAP + 2 * self.MARGIN)
        return result

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        star, square = self.decoration_rects(styled.rect)
        style = styled.widget.style() if styled.widget is not None else QApplication.style()
        text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, styled, styled.widget)
        styled.text = styled.fontMetrics.elidedText(styled.text, Qt.TextElideMode.ElideRight,
                                                   max(0, star.left() - self.GAP - text_rect.left()))
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        theme = get_active_settings_theme()
        painter.save()
        colours = index.data(PALETTE_ROLE) or ()
        for number, rgb in enumerate(colours[:4]):
            cell = QRect(square.left() + (number % 2) * self.SIDE // 2,
                         square.top() + (number // 2) * self.SIDE // 2, self.SIDE // 2, self.SIDE // 2)
            painter.fillRect(cell, QColor(*rgb))
        painter.setPen(QPen(QColor(*theme.color("control.list.border").as_tuple()), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(square).adjusted(1., 1., -1., -1.))
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        accent = QColor(*theme.color("control.list.selected_accent").as_tuple())
        painter.setPen(QPen(accent, 1.25))
        painter.setBrush(accent if index.data(FAVOURITE_ROLE) else Qt.BrushStyle.NoBrush)
        painter.translate(QRectF(star).center())
        painter.drawPath(self._star_path)
        painter.restore()


class ThemeListWidget(OutlinedListWidget):
    """One delegate per list, with star hit-testing before selection/activation."""
    favouriteToggled = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_ThemeRowDelegate(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self._star_press = None

    def add_theme_item(self, item, theme):
        item.setData(PALETTE_ROLE, dominant_theme_colours(theme))
        item.setData(_ORDER_ROLE, self.count())
        self.addItem(item)

    def set_favourites(self, favourites):
        current = self.currentItem()
        scroll = self.verticalScrollBar().value()
        blocker = QSignalBlocker(self)
        updates = self.updatesEnabled()
        self.setUpdatesEnabled(False)
        try:
            items = [self.item(row) for row in range(self.count())]
            for item in items:
                favourite = item.data(Qt.ItemDataRole.UserRole) in favourites
                item.setData(FAVOURITE_ROLE, favourite)
                item.setData(Qt.ItemDataRole.AccessibleDescriptionRole,
                             ("Favourite theme. " if favourite else "") + "Ctrl+D toggles favourite.")
            ordered = sorted(items, key=lambda item: (not item.data(FAVOURITE_ROLE), item.data(_ORDER_ROLE)))
            if ordered != items:
                while self.count():
                    self.takeItem(0)
                for item in ordered:
                    self.addItem(item)
                if current is not None:
                    self.setCurrentItem(current)
                self.verticalScrollBar().setValue(scroll)
        finally:
            self.setUpdatesEnabled(updates)
            del blocker

    def _star_at(self, point):
        index = self.indexAt(point)
        if index.isValid() and _ThemeRowDelegate.decoration_rects(self.visualRect(index))[0].adjusted(-3, -3, 3, 3).contains(point):
            return str(index.data(Qt.ItemDataRole.UserRole))
        return None

    def mousePressEvent(self, event):
        star = self._star_at(event.position().toPoint())
        if event.button() == Qt.MouseButton.LeftButton and star is not None:
            self._star_press = star
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        pressed, self._star_press = self._star_press, None
        if pressed is not None:
            if event.button() == Qt.MouseButton.LeftButton and self._star_at(event.position().toPoint()) == pressed:
                self.favouriteToggled.emit(pressed)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._star_at(event.position().toPoint()) is not None:
            self._star_press = None
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if self._star_at(event.position().toPoint())
                                  else Qt.CursorShape.ArrowCursor)
        if self._star_press is not None:
            event.accept()
            return
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_D and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if self.currentItem() is not None:
                self.favouriteToggled.emit(str(self.currentItem().data(Qt.ItemDataRole.UserRole)))
            event.accept()
            return
        super().keyPressEvent(event)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip and self._star_at(event.pos()) is not None:
            index = self.indexAt(event.pos())
            message = "Remove favourite" if index.data(FAVOURITE_ROLE) else "Add favourite"
            QToolTip.showText(event.globalPos(), message + " (Ctrl+D)", self)
            return True
        return super().viewportEvent(event)
