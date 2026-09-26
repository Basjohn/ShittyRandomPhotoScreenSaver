"""Small Settings controls shared by Guided Setup and Quick Start."""
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QLabel, QPushButton, QCheckBox, QListWidget,
    QScrollArea, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QSizePolicy, QVBoxLayout, QWidget)

from ui.tabs import shared_styles
from ui.widgets.dpr_pixmap import scale_pixmap_for_dpr

SILENCE_TEXT = (
    "When SRPSS has no image sources, show the simple No Image Sources popup "
    "instead of opening Guided Setup automatically."
)


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "images" / name


def text_label(text: str, *, heading=False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    shared_styles.apply_shared_label_style(label, "PAGE_TITLE_STYLE" if heading else "INFO_LABEL_STYLE")
    return label


def action(text: str, callback, *, secondary=False) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(36)
    shared_styles.bind_shared_styles(button, "COMPACT_ACTION_BUTTON_STYLE" if secondary else "GHOST_ACTION_BUTTON_STYLE")
    button.clicked.connect(lambda _checked=False: callback())
    return button


def checkbox(text: str, parent=None) -> QCheckBox:
    check = QCheckBox(text, parent)
    check.setProperty("circleIndicator", True)
    shared_styles.bind_shared_styles(check, "CIRCLE_CHECKBOX_STYLE")
    return check


class _CheckRowDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # The real shared QCheckBox owns the label and indicator. Keep the
        # native list selection/keyboard surface without painting them twice.
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        style_option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        option.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, style_option, painter, option.widget)


class CheckList(QListWidget):
    """Selectable preview rows using Settings' actual circular checkboxes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_CheckRowDelegate(self))
        self.itemChanged.connect(self._sync_check)

    def addItem(self, item):
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        super().addItem(item)
        check = checkbox(item.text(), self)
        check.setToolTip(item.toolTip())
        check.setChecked(item.checkState() == Qt.CheckState.Checked)
        item.setSizeHint(QSize(0, max(46, check.sizeHint().height())))
        self.setItemWidget(item, check)
        check.toggled.connect(lambda value: self._toggle_item(item, value))

    def _toggle_item(self, item, checked):
        control = self.itemWidget(item)
        if control is not None and not control.isEnabled():
            return
        self.setCurrentItem(item)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _sync_check(self, item):
        check = self.itemWidget(item)
        if check is not None:
            with QSignalBlocker(check):
                check.setChecked(item.checkState() == Qt.CheckState.Checked)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and self.currentItem() is not None:
            item = self.currentItem()
            self._toggle_item(item, item.checkState() != Qt.CheckState.Checked)
            event.accept()
        else:
            super().keyPressEvent(event)


def silence_check(settings) -> QCheckBox:
    check = checkbox("Silence!")
    check.setToolTip(SILENCE_TEXT)
    check.setChecked(bool(settings.get("sources.guided_setup_silenced")))
    check.toggled.connect(lambda checked: settings.set("sources.guided_setup_silenced", checked))
    return check


class ImagePanel(QLabel):
    """Decode once; rescale on geometry/DPR changes, never from paintEvent."""
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(160, 120)
        self._source = QPixmap(str(path))
        if self._source.isNull():
            raise FileNotFoundError(f"Guided Setup image missing or unreadable: {path}")
        self._last_scale = None

    def set_source(self, path: Path):
        source = QPixmap(str(path))
        if source.isNull():
            raise FileNotFoundError(f"Guided Setup image missing or unreadable: {path}")
        self._source = source
        self._last_scale = None
        self._rescale()

    def minimumSizeHint(self):
        return QSize(160, 120)

    def sizeHint(self):
        return QSize(400, 240)

    def _rescale(self):
        if not hasattr(self, "_source"):
            return
        key = (self.width(), self.height(), self.devicePixelRatioF())
        if key != self._last_scale:
            self._last_scale = key
            self.setPixmap(scale_pixmap_for_dpr(self._source, key[0], key[1], key[2]))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self._rescale()
        return result


class Page(QWidget):
    def __init__(self, settings, parent=None, *, scrollable=False):
        super().__init__(parent)
        self.settings = settings
        content = QWidget(self) if scrollable else self
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(16, 12, 16, 12)
        self.body.setSpacing(16)
        shared_styles.bind_shared_styles(self, "CIRCLE_CHECKBOX_STYLE", "SPINBOX_STYLE", "COMBOBOX_STYLE")
        if scrollable:
            scroll = QScrollArea(self)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
            scroll.setWidget(content)
            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(scroll)

    def refresh(self):
        """Called on page entry; construction must never write settings."""

    def can_continue(self):
        return True

    def leave(self):
        return True
