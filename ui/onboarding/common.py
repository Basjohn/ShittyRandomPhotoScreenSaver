"""Small Settings controls shared by Guided Setup and Quick Start."""
import re
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QLabel, QPushButton, QCheckBox, QListWidget,
    QScrollArea, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QSizePolicy, QVBoxLayout, QWidget)

from ui.tabs import shared_styles
from ui.widgets.continuous_border import OutlinedListWidget
from ui.widgets.dpr_pixmap import scale_pixmap_for_dpr

SILENCE_TEXT = (
    "When SRPSS has no image sources, show the simple No Image Sources popup "
    "instead of opening Guided Setup automatically."
)


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "images" / name


# Units and abbreviations that stay as written inside Title Case copy.
_KEEP_CASE = {"px", "ms", "e.g", "i.e", "vs"}
# User data and addresses are never re-cased: URLs, drive/UNC/absolute paths,
# e-mail addresses and bare domains.
_DATA_TOKEN = re.compile(
    r"^r/|://|^[A-Za-z]:[/\\]|\\|@|^/|^www\.|\.(?:com|org|net|io|rss|xml|png|jpg|ogg|wav|mp3)\b",
    re.IGNORECASE,
)


def _capitalise(segment: str) -> str:
    for index, char in enumerate(segment):
        if char.isalpha():
            return segment[:index] + char.upper() + segment[index + 1:]
        if char.isdigit():
            return segment
    return segment


# Short joining words stay lowercase inside Title Case, as established Settings
# copy does ("Widget Glow on Hover", "Reset All Colours to Theme").
_SMALL_WORDS = frozenset({
    "a", "an", "the", "and", "but", "or", "nor", "for",
    "as", "at", "by", "in", "of", "on", "to", "via", "per", "vs",
    # Prepositions stay lowercase too ("Share Style with Main Clock").
    "with", "from", "into", "onto", "over", "under", "about", "after", "before",
    "between", "through", "without", "within", "than",
})


def title_case(text: str) -> str:
    """SRPSS copy casing: Title Case, leaving data and units alone.

    Only a word's first letter changes, so acronyms (RSS, OSD) and mixed-case
    names keep their inner capitals.  Short joining words stay lowercase except
    at the start of a sentence.  Hyphen and slash compounds capitalise each
    part ("Right-Click", "Previous/Next").  Paths, URLs and e-mail addresses
    pass through untouched.
    """
    sentence_start = [True]

    def word(match):
        token = match.group(0)
        starts = sentence_start[0]
        sentence_start[0] = token.endswith((".", "!", "?", ":"))
        bare = token.lower().strip("().,;:!?\"'")
        if bare in _KEEP_CASE or _DATA_TOKEN.search(token):
            return token
        ends = token.endswith((".", "!", "?", ":", ")", ",")) or match.end() >= len(str(text).rstrip())
        if bare in _SMALL_WORDS and not starts and not ends and not token.startswith("("):
            return token[0].lower() + token[1:] if token[:1].isupper() and token[1:].islower() else token
        return re.sub(r"[^/-]+", lambda part: _capitalise(part.group(0)), token)
    return re.sub(r"\S+", word, str(text))


class CopyLabel(QLabel):
    """A wrapped Settings label whose text always follows the Title Case rule."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setText(text)

    def setText(self, text):  # type: ignore[override]
        super().setText(title_case(text))


def text_label(text: str, *, heading=False) -> QLabel:
    label = CopyLabel(text)
    label.setWordWrap(True)
    shared_styles.apply_shared_label_style(label, "PAGE_TITLE_STYLE" if heading else "INFO_LABEL_STYLE")
    return label


def action(text: str, callback) -> QPushButton:
    # Settings' ordinary button semantics: theme surface at rest, hover surface
    # on hover. No wizard button is permanently emphasized (a filled accent pill
    # reads as a stuck hover).
    from ui.widgets.outlined_button import OutlinedButton
    button = OutlinedButton(title_case(text), role="secondary")
    button.setMinimumHeight(36)
    button.clicked.connect(lambda _checked=False: callback())
    return button


def checkbox(text: str, parent=None) -> QCheckBox:
    check = QCheckBox(title_case(text), parent)
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


class CheckList(OutlinedListWidget):
    """Selectable preview rows using Settings' actual circular checkboxes."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_CheckRowDelegate(self))
        self.itemChanged.connect(self._sync_check)

    def addItem(self, item):
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        super().addItem(item)
        check = checkbox(item.text(), self)
        # Row checkboxes never take focus: inside Settings a focusable row was
        # focused by merely hovering it, which made it current and scrolled the
        # list under the cursor. The list keeps focus; Space toggles the row.
        check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
    """Decode once; rescale on geometry/DPR changes, never from paintEvent.

    ``upscale=False`` (previews) never draws more than one source pixel per
    physical pixel: a small preview stays sharp at its true size instead of
    being stretched blurry on a high-DPI display.
    """
    def __init__(self, path: Path, parent=None, *, upscale=True):
        super().__init__(parent)
        self._upscale = upscale
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
            width, height, dpr = key
            if not self._upscale:
                dpr = max(1.0, dpr)
                width = min(width, self._source.width() / dpr)
                height = min(height, self._source.height() / dpr)
            self.setPixmap(scale_pixmap_for_dpr(self._source, width, height, key[2]))

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
