"""The Themes tab's type-in theme filter: a themed line edit with word autocomplete.

Filtering is view state only (nothing persisted) and only hides ``ThemeListWidget`` rows; see
``Docs/Architecture/Settings_Theme_Architecture.md`` "Theme filter". It filters on ``textChanged``: no timers.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, QSize, QStringListModel, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QCompleter, QLineEdit, QListView, QSizePolicy, QWidget

from ui.settings_theme_runtime import get_active_settings_theme
from ui.tabs import shared_styles
from ui.widgets.continuous_border import rounded_border_path, stroke_rounded_border, theme_color

FILTER_PLACEHOLDER = "Filter by Name, Colour or Material"
FILTER_TOOLTIP = ("Type a name, Dark or Light, a material such as Glass, or a colour such as Blue; "
                  "several words narrow the list together.")
CLEAR_TOOLTIP = "Clear the Filter"


def _clear_icon() -> QIcon:
    """A painted cross in the input's own ink (never the native style's clear glyph)."""
    ink = get_active_settings_theme().color("control.input.text")
    color = QColor(ink.r, ink.g, ink.b, max(1, int(ink.a * 0.75)))
    icon = QIcon()
    for size in (16, 20, 24, 32):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, max(1.5, size / 10.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        inset = size * 0.3
        cross = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
        painter.drawLine(cross.topLeft(), cross.bottomRight())
        painter.drawLine(cross.topRight(), cross.bottomLeft())
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class ThemedCompleterPopup(QListView):
    """A completer's popup in the theme: the shared combo popup skin, its outline painted as one continuous path.
    The one autocomplete popup of Settings (the theme filter, the Weather location)."""

    BORDER_WIDTH = 2.0
    RADIUS = 14.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("customComboPopup", True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(True)
        shared_styles.bind_shared_styles(
            self, "COMBOBOX_POPUP_VIEW_STYLE", base_style="",
            # QCompleter sizes the popup for its rows plus a 3 px frame each side: the padding fits that,
            # so the last visible row is never cut.
            trailing_style=("QListView[customComboPopup='true'] "
                            "{ border-color: transparent; background-color: transparent; padding: 1px 6px; }"),
        )

    def event(self, event) -> bool:  # noqa: D401 - the scroll area paints its frame from event()
        if event.type() == QEvent.Type.Paint:
            # A translucent top-level popup gets no stylesheet background: fill the rounded body here, under
            # the frame pass, then stroke the outline once on top. A suggestion list floats over the theme
            # list, so its body is the theme's popup colour at full density: nothing behind may bleed through.
            surface = theme_color("combo.popup.surface")
            surface.setAlpha(255)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillPath(rounded_border_path(QRectF(self.rect()), self.BORDER_WIDTH, self.RADIUS), surface)
            painter.end()
        handled = super().event(event)
        if event.type() == QEvent.Type.Paint:
            stroke_rounded_border(self, theme_color("combo.popup.border"), self.BORDER_WIDTH, self.RADIUS)
        return handled


class _WordCompleter(QCompleter):
    """Completes the last word of a multi-word filter, keeping the words before it."""

    def splitPath(self, path: str) -> list[str]:  # noqa: N802
        return [path.rsplit(" ", 1)[-1]]

    def pathFromIndex(self, index) -> str:  # noqa: N802
        widget = self.widget()
        text = widget.text() if isinstance(widget, QLineEdit) else ""
        head = text.rsplit(" ", 1)[0] + " " if " " in text else ""
        return head + str(index.data(Qt.ItemDataRole.DisplayRole) or "")


class ThemeFilterField(QLineEdit):
    """A type-in filter bound to one ``ThemeListWidget``; its height follows ``height_buddy`` (the Linked button)."""

    BORDER_WIDTH = 2.0
    RADIUS = 14.0

    def __init__(self, theme_list, *, height_buddy: QWidget | None = None, parent=None) -> None:
        super().__init__(parent)
        self._theme_list = theme_list
        self._height_buddy = height_buddy
        self._vocabulary_revision = -1
        self._clear_icon_key = None
        self._clear_action = QAction(self)
        self.setObjectName("themeFilterInput")
        self.setPlaceholderText(FILTER_PLACEHOLDER)
        self.setToolTip(FILTER_TOOLTIP)
        self.setAccessibleName("Theme Filter")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        shared_styles.bind_shared_styles(self, "THEME_FILTER_INPUT_STYLE", base_style="")

        self._clear_action.setToolTip(CLEAR_TOOLTIP)
        self._clear_action.triggered.connect(self.clear)
        self._refresh_clear_icon()
        self.addAction(self._clear_action, QLineEdit.ActionPosition.TrailingPosition)
        self._clear_action.setVisible(False)

        self._model = QStringListModel(self)
        completer = _WordCompleter(self._model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setModelSorting(QCompleter.ModelSorting.UnsortedModel)
        completer.setMaxVisibleItems(8)
        completer.setPopup(ThemedCompleterPopup())
        self.setCompleter(completer)
        self._completer = completer

        self.textChanged.connect(self._on_text_changed)

    # -- completions ---------------------------------------------------------------------------------

    def completion_model(self) -> QStringListModel:
        """The completer's model, rebuilt from the list's current themes when they changed."""
        revision = self._theme_list.vocabulary_revision
        if revision != self._vocabulary_revision:
            self._vocabulary_revision = revision
            self._model.setStringList(list(self._theme_list.filter_vocabulary()))
        return self._model

    def completer_popup(self) -> QListView:
        return self._completer.popup()

    def focusInEvent(self, event) -> None:  # noqa: N802
        self.completion_model()
        super().focusInEvent(event)

    def _on_text_changed(self, text: str) -> None:
        self.completion_model()
        self._clear_action.setVisible(bool(text))
        self._theme_list.set_filter_text(text)

    # -- look ----------------------------------------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802
        hint = super().sizeHint()
        if self._height_buddy is not None:
            hint.setHeight(self._height_buddy.sizeHint().height())
        return hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        if self._height_buddy is not None:
            hint.setHeight(self._height_buddy.sizeHint().height())
        return hint

    def _refresh_clear_icon(self) -> None:
        key = get_active_settings_theme().color("control.input.text").as_tuple()
        if key != self._clear_icon_key:
            self._clear_icon_key = key
            self._clear_action.setIcon(_clear_icon())

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._refresh_clear_icon()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        token = "control.input.disabled_border" if not self.isEnabled() else "control.input.border"
        stroke_rounded_border(self, theme_color(token), self.BORDER_WIDTH, self.RADIUS)
