"""Shared QSS styles and widgets for settings dialog tabs.

Centralises repeated styling blocks and common widgets so individual tabs
don't duplicate them.
"""
import weakref
from typing import Callable

try:
    import shiboken6

    Shiboken = shiboken6.Shiboken
except Exception:  # pragma: no cover - PySide test/import fallback
    Shiboken = None  # type: ignore[assignment]

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QSlider,
    QToolButton,
    QSizePolicy,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStyle,
    QStyleOptionSlider,
)

# Ensure UI resources (e.g., circle checkbox SVGs) are registered even when
# shared_styles is imported before ui/__init__.py. Safe no-op if already loaded.
try:  # pragma: no cover - defensive import
    from ui.resources import assets_rc  # noqa: F401
except Exception:  # pragma: no cover - fallback when resources unavailable
    assets_rc = None  # type: ignore


_JOST_FONT_PATHS = (
    ":/ui/assets/fonts/Jost-Regular.ttf",
    ":/ui/assets/fonts/Jost-SemiBold.ttf",
    ":/ui/assets/fonts/Jost-Bold.ttf",
)
_INTER_FONT_PATHS = (
    ":/ui/assets/fonts/Inter-VariableFont_opsz,wght.ttf",
    ":/ui/assets/fonts/Inter-Italic-VariableFont_opsz,wght.ttf",
)
_FONTS_REGISTERED = False


def _ensure_fonts_registered() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    if QApplication.instance() is None:
        return
    for path in _JOST_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    for path in _INTER_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    _FONTS_REGISTERED = True


def ensure_custom_fonts() -> None:
    _ensure_fonts_registered()


FORM_LABEL_HEIGHT = 34
SWATCH_LABEL_HEIGHT = 34
LABEL_WIDTH = 140

_last_moved_slider: weakref.ref | None = None


def _is_live_qobject(obj) -> bool:
    """Return whether a PySide wrapper still owns a live C++ QObject."""

    if obj is None:
        return False
    if Shiboken is None:
        return True
    try:
        return bool(Shiboken.isValid(obj))
    except RuntimeError:
        return False


FORM_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 14px;"
    "letter-spacing: 0.4px;"
    "color: #ffffff;"
    f"min-height: {FORM_LABEL_HEIGHT}px;"
    "line-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 1px;"
    "margin-top: -1px;"
    "margin-bottom: 0px;"
    "qproperty-alignment: AlignVCenter;"
)

FORM_ROW_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 14px;"
    "letter-spacing: 0.35px;"
    "color: #ffffff;"
    f"min-height: {FORM_LABEL_HEIGHT}px;"
    "line-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 1px;"
    "margin-top: -1px;"
    "margin-bottom: 0px;"
    "qproperty-alignment: AlignVCenter;"
)

FORM_LABEL_STYLE_DISABLED = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 14px;"
    "letter-spacing: 0.35px;"
    "color: #666666;"
    f"min-height: {FORM_LABEL_HEIGHT}px;"
    "line-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 1px;"
    "margin-top: -1px;"
    "margin-bottom: 0px;"
    "qproperty-alignment: AlignVCenter;"
)

FORM_ROW_LABEL_STYLE_DISABLED = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 14px;"
    "letter-spacing: 0.35px;"
    "color: #666666;"
    f"min-height: {FORM_LABEL_HEIGHT}px;"
    "line-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 1px;"
    "margin-top: -1px;"
    "margin-bottom: 0px;"
    "qproperty-alignment: AlignVCenter;"
)


def apply_section_heading_style(
    label: QLabel,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    lock_height: bool = True,
) -> None:
    """Normalize section heading labels so they align with adjacent controls."""

    ensure_custom_fonts()
    if style is None:
        style_sheet = FORM_LABEL_STYLE_DISABLED if disabled else FORM_LABEL_STYLE
    else:
        style_sheet = style
    label.setStyleSheet(style_sheet)
    target_height = height if height is not None else FORM_LABEL_HEIGHT
    if lock_height:
        label.setFixedHeight(target_height)
        label.setWordWrap(False)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    else:
        label.setMinimumHeight(target_height)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        label.setWordWrap(True)
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)


def create_section_label(
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    lock_height: bool = True,
) -> QLabel:
    label = QLabel(text)
    if width is not None:
        label.setFixedWidth(width)
    apply_section_heading_style(
        label,
        disabled=disabled,
        style=style,
        height=height,
        lock_height=lock_height,
    )
    return label


def add_section_label(
    layout,
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
    wrap: bool = True,
) -> QLabel:
    if style is None:
        style = FORM_ROW_LABEL_STYLE_DISABLED if disabled else FORM_ROW_LABEL_STYLE
    label = create_section_label(
        text,
        width,
        disabled=disabled,
        style=style,
        height=height,
        lock_height=not wrap,
    )
    layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignVCenter)
    return label


def add_swatch_label(
    layout,
    text: str,
    width: int | None = None,
) -> QLabel:
    return add_section_label(
        layout,
        text,
        width,
        style=SWATCH_LABEL_STYLE,
        height=SWATCH_LABEL_HEIGHT,
        wrap=False,
    )


def add_aligned_row_widget(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int | None = LABEL_WIDTH,
    wrap: bool = True,
    margins: tuple[int, int, int, int] = (0, 8, 0, 8),
    spacing: int = 12,
    content_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    content_spacing: int = 12,
) -> tuple[QWidget, QHBoxLayout, QLabel]:
    """Add a form row widget with shared spacing + wrap-aware label."""

    row_widget = QWidget()
    row_layout = QHBoxLayout(row_widget)
    row_layout.setContentsMargins(*margins)
    row_layout.setSpacing(spacing)
    label = add_section_label(row_layout, label_text, label_width, wrap=wrap)
    content_layout = QHBoxLayout()
    content_layout.setContentsMargins(*content_margins)
    content_layout.setSpacing(content_spacing)
    row_layout.addLayout(content_layout, 1)
    parent_layout.addWidget(row_widget)
    return row_widget, content_layout, label


def add_aligned_row(
    parent_layout: QVBoxLayout,
    label_text: str,
    *,
    label_width: int | None = LABEL_WIDTH,
    wrap: bool = True,
    margins: tuple[int, int, int, int] = (0, 8, 0, 8),
    spacing: int = 12,
    content_margins: tuple[int, int, int, int] = (0, 0, 0, 0),
    content_spacing: int = 12,
) -> tuple[QHBoxLayout, QLabel]:
    """Convenience wrapper returning just the content row + label."""

    _, content_layout, label = add_aligned_row_widget(
        parent_layout,
        label_text,
        label_width=label_width,
        wrap=wrap,
        margins=margins,
        spacing=spacing,
        content_margins=content_margins,
        content_spacing=content_spacing,
    )
    return content_layout, label


def create_inline_label(
    text: str,
    *,
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft
    | Qt.AlignmentFlag.AlignVCenter,
    minimum_width: int | None = None,
) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(FORM_ROW_LABEL_STYLE)
    if minimum_width is not None:
        label.setMinimumWidth(minimum_width)
    label.setAlignment(alignment)
    return label


class NoWheelSlider(QSlider):
    """Slider that ignores mouse wheel events to prevent accidental changes.

    Also tracks the most-recently-moved slider via a module-level weakref
    so the QSS ``QSlider[lastMoved="true"]`` selector highlights its handle.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("lastMoved", False)
        self.sliderPressed.connect(self._mark_last_moved)
        self.valueChanged.connect(self._mark_last_moved)
        self.destroyed.connect(self._clear_last_moved_ref)

    def _clear_last_moved_ref(self, *_args) -> None:
        global _last_moved_slider
        if _last_moved_slider is not None and _last_moved_slider() is self:
            _last_moved_slider = None

    @staticmethod
    def _set_last_moved_state(slider: "NoWheelSlider", value: bool) -> None:
        if not _is_live_qobject(slider):
            return
        slider.setProperty("lastMoved", value)
        slider.style().unpolish(slider)
        slider.style().polish(slider)

    def _mark_last_moved(self, *_args) -> None:
        global _last_moved_slider
        if not _is_live_qobject(self):
            _last_moved_slider = None
            return
        prev = _last_moved_slider() if _last_moved_slider is not None else None
        if prev is self:
            return
        if prev is not None and _is_live_qobject(prev):
            self._set_last_moved_state(prev, False)
        elif prev is not None:
            _last_moved_slider = None
        self._set_last_moved_state(self, True)
        _last_moved_slider = weakref.ref(self)

    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


class RecommendedMarkSlider(NoWheelSlider):
    """Slider with a subtle recommended-position marker painted on the groove."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._recommended_value: int | None = None
        self._recommended_color = QColor(210, 210, 210, 170)

    def set_recommended_value(self, value: int | None) -> None:
        target = None if value is None else int(value)
        if self._recommended_value == target:
            return
        self._recommended_value = target
        self.update()

    def recommended_value(self) -> int | None:
        return self._recommended_value

    def set_recommended_color(self, color: QColor) -> None:
        next_color = QColor(color)
        if next_color == self._recommended_color:
            return
        self._recommended_color = next_color
        self.update()

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        if self._recommended_value is None:
            return
        if self.orientation() != Qt.Orientation.Horizontal:
            return
        minimum = int(self.minimum())
        maximum = int(self.maximum())
        if maximum <= minimum:
            return

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderGroove,
            self,
        )
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,
            option,
            QStyle.SubControl.SC_SliderHandle,
            self,
        )
        if groove.isNull() or handle.isNull():
            return

        span = max(1, groove.width() - handle.width())
        ratio = (self._recommended_value - minimum) / float(maximum - minimum)
        ratio = max(0.0, min(1.0, ratio))
        center_x = groove.left() + handle.width() * 0.5 + span * ratio
        groove_mid_y = groove.center().y()
        marker_height = max(5.0, groove.height() + 8.0)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._recommended_color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            int(round(center_x)),
            int(round(groove_mid_y - marker_height * 0.5)),
            int(round(center_x)),
            int(round(groove_mid_y + marker_height * 0.5)),
        )
        painter.end()

SPINBOX_STYLE = """
/* Rounded inputs with opaque borders + circular stepper controls */
QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox {
    min-height: 34px;
    padding: 4px 48px 4px 16px;
    margin-bottom: 0px;
    color: #ffffff;
    font-family: 'Jost';
    font-weight: 600;
    background-color: #1f1f1f;
    border: 2px solid #ffffff;
    border-radius: 18px;
}

QSpinBox > QLineEdit,
QDoubleSpinBox > QLineEdit,
QAbstractSpinBox > QLineEdit {
    background-color: #1f1f1f;
    border: none;
    padding: 0px;
    margin: 0px;
}

QLineEdit {
    padding-right: 16px;
}

QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover, QAbstractSpinBox:hover {
    border-color: #ffffff;
}

QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QAbstractSpinBox:focus {
    border-color: #ffffff;
}

QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QAbstractSpinBox:disabled {
    color: rgba(255, 255, 255, 0.45);
    border-color: #6a6a6a;
    background-color: #1f1f1f;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: right;
    width: 10px;
    height: 10px;
    margin: 4px 14px 4px 0px;
    padding: 0px;
    border: none;
    border-radius: 5px;
    background-color: #ffffff;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-position: top right;
    margin-top: 7.5px;
    margin-bottom: -3.5px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-position: bottom right;
    margin-top: -3.5px;
    margin-bottom: 7.5px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4d4d4d;
}

QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #2d2d2d;
}

QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled {
    background-color: #6a6a6a;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0px;
    height: 0px;
    border: none;
}
"""

CIRCLE_CHECKBOX_STYLE = """
/* Circular indicator prototype (feature flag via `circleIndicator` dynamic property). */
QCheckBox[circleIndicator='true'] {
    spacing: 10px;
    padding: 4px 16px 4px 6px;
    min-height: 34px;
}

QCheckBox[circleIndicator='true'][tightSpacing='true'] {
    spacing: 6px;
    padding: 4px 12px 4px 0px;
    min-height: 34px;
}

QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 6px 12px 6px 0px;
    border: none;
    background: transparent;
    image: none;
}

QCheckBox[circleIndicator='true'][tightSpacing='true']::indicator {
    margin: 5px 9px 5px 0px;
}

QCheckBox[circleIndicator='true']::indicator:unchecked {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}

QCheckBox[circleIndicator='true']::indicator:unchecked:hover {
    image: url(:/ui/assets/circle_checkbox_unchecked_hover.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}

QCheckBox[circleIndicator='true']::indicator:checked:hover {
    image: url(:/ui/assets/circle_checkbox_checked_hover.svg);
}

QCheckBox[circleIndicator='true']::indicator:disabled {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}

QCheckBox[circleIndicator='true']::indicator:disabled:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}
"""


COMBOBOX_STYLE = """
/* StyledComboBox base skin */
QComboBox[customCombo='true'] {
    min-height: 34px;
    padding: 4px 56px 4px 18px;
    margin-top: 1px;
    margin-bottom: 10px;
    font-family: 'Jost';
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.4px;
    color: #ffffff;
    border: 2px solid #ffffff;
    border-radius: 18px;
    background-color: #1f1f1f;
}

QComboBox[customCombo='true']:hover {
    background-color: #161616;
}

QComboBox[customCombo='true']:focus,
QComboBox[customCombo='true']:on {
    background-color: #141414;
    border-color: #ffffff;
    outline: none;
}

QComboBox[customCombo='true']:disabled {
    color: rgba(255, 255, 255, 0.45);
    border-color: #6a6a6a;
    background-color: #1f1f1f;
}

QComboBox[customCombo='true']::drop-down,
QComboBox[customCombo='true']::down-arrow {
    width: 0px;
    border: none;
    background: transparent;
    image: none;
    margin: 0px;
    padding: 0px;
}

QComboBox[customCombo='true'][comboSize='regular'] {
    min-width: 188px;
    min-height: 38px;
    padding: 4px 60px 4px 18px;
    border-radius: 20px;
    margin-top: 1px;
    margin-bottom: 10px;
}

QComboBox[customCombo='true'][comboSize='compact'] {
    min-width: 164px;
    min-height: 34px;
    padding: 3px 52px 3px 16px;
    border-radius: 17px;
    font-size: 13px;
    margin-top: 2px;
    margin-bottom: 12px;
}

QComboBox[customCombo='true'][comboSize='mini'] {
    min-width: 136px;
    min-height: 32px;
    padding: 2px 46px 2px 14px;
    border-radius: 16px;
    font-size: 12px;
    margin-top: 2px;
    margin-bottom: 12px;
}

QComboBox[customCombo='true'][comboSize='hero'] {
    min-width: 198px;
    max-width: 306px;
    min-height: 38px;
    padding: 3px 54px 5px 20px;
    border-radius: 20px;
    font-size: 14px;
    margin-top: 1px;
    margin-bottom: 10px;
}
"""

COMBOBOX_POPUP_VIEW_STYLE = """
QListView[customComboPopup='true'],
QListWidget[customComboPopup='true'] {
    background-color: rgba(18, 18, 18, 0.95);
    border: 2px solid #ffffff;
    border-radius: 14px;
    padding: 8px 8px 12px 8px;
    outline: none;
    selection-background-color: rgba(255, 255, 255, 0.22);
    selection-color: #ffffff;
    color: #ffffff;
    font-family: 'Jost';
    font-weight: 600;
    font-size: 14px;
    letter-spacing: 0.4px;
}

QListView[customComboPopup='true']::item,
QListWidget[customComboPopup='true']::item {
    padding: 4px 6px;
    min-height: 22px;
    margin: 0px 2px;
    border-radius: 8px;
    background: transparent;
}
"""

TOOLTIP_STYLE = """
QToolTip {
    background-color: #1e1e1e;
    color: #ffffff;
    border: 1px solid #ffffff;
    padding: 6px;
    font-size: 12px;
}
"""

PAGE_TITLE_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 700;"
    "font-size: 18px;"
    "letter-spacing: 0.5px;"
    "color: #ffffff;"
)

SECTION_HEADING_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 800;"
    "font-size: 15px;"
    "letter-spacing: 0.6px;"
    "color: #ffffff;"
    f"min-height: {FORM_LABEL_HEIGHT + 6}px;"
    "line-height: 36px;"
    "padding-top: 0px;"
    "padding-bottom: 2px;"
    "margin-top: -6px;"
    "margin-bottom: 12px;"
    "qproperty-alignment: AlignVCenter;"
)

SECTION_HEADING_STYLE_DISABLED = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 800;"
    "font-size: 15px;"
    "letter-spacing: 0.6px;"
    "color: #666666;"
    f"min-height: {FORM_LABEL_HEIGHT + 6}px;"
    "line-height: 36px;"
    "padding-top: 0px;"
    "padding-bottom: 2px;"
    "margin-top: -6px;"
    "margin-bottom: 12px;"
    "qproperty-alignment: AlignVCenter;"
)

SWATCH_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 13px;"
    "letter-spacing: 0.4px;"
    "color: #ffffff;"
    f"min-height: {SWATCH_LABEL_HEIGHT}px;"
    "line-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 0px;"
    "margin-top: 0px;"
    "margin-bottom: 0px;"
    "qproperty-alignment: AlignVCenter;"
)

SUBSECTION_DIVIDER_STYLE = (
    "background-color: rgba(60, 60, 60, 115);"
    "border: 2px solid #ffffff;"
    "border-radius: 19px;"
)


def style_group_box(box) -> None:
    """Apply the subsection border + title style to a QGroupBox."""

    box.setStyleSheet(
        (
            f"QGroupBox {{{SUBSECTION_DIVIDER_STYLE}}}"
            "QGroupBox::title {"
            "  subcontrol-origin: margin;"
            "  subcontrol-position: top left;"
            "  padding: 2px 10px;"
            "  margin-top: 5px;"
            "  color: #ffffff;"
            "  font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
            "  font-weight: 800;"
            "  font-size: 16px;"
            "  letter-spacing: 0.6px;"
            "}"
        )
    )

NAV_TAB_FONT_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 13px;"
    "letter-spacing: 0.4px;"
)

NAV_TAB_FONT_STYLE_ACTIVE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 700;"
    "font-size: 13px;"
    "letter-spacing: 0.5px;"
)

STATUS_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 600;"
    "font-size: 11px;"
    "letter-spacing: 0.3px;"
)

INFO_LABEL_STYLE = (
    "color: #aaaaaa;"
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 11px;"
    "letter-spacing: 0.3px;"
)

ADV_HELPER_LABEL_STYLE = (
    "color: rgba(220, 220, 220, 0.6);"
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 11px;"
    "letter-spacing: 0.3px;"
)

INFO_LABEL_STYLE_DISABLED = (
    "color: #555555;"
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 500;"
    "font-size: 11px;"
    "letter-spacing: 0.3px;"
)

SLIDER_STYLE = """
/* Dark glass indented slider with pill-shaped notch handle */
QSlider {
    min-height: 34px;
    margin: 2px 0px 0px 0px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(8, 8, 8, 0.95),
        stop:0.35 rgba(20, 20, 20, 0.9),
        stop:0.65 rgba(30, 30, 30, 0.85),
        stop:1 rgba(45, 45, 45, 0.7));
    border: 1px solid rgba(12, 12, 12, 0.9);
    border-top-color: rgba(0, 0, 0, 0.7);
    border-bottom-color: rgba(70, 70, 70, 0.25);
    border-radius: 2px;
    margin: 0px 0;
}

QSlider::sub-page:horizontal {
    height: 4px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(50, 50, 50, 0.9),
        stop:0.5 rgba(65, 65, 65, 0.85),
        stop:1 rgba(50, 50, 50, 0.75));
    border: 1px solid rgba(35, 35, 35, 0.85);
    border-top-color: rgba(25, 25, 25, 0.7);
    border-bottom-color: rgba(80, 80, 80, 0.25);
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 10px;
    margin: -4px 0;
    border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:0.85 #1a1a1a, stop:1 #111111);
    border: 1px solid #676767;
    
}

QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a3a3a, stop:0.85 #242424, stop:1 #181818);
    border: 1px solid #999999;
    
}

QSlider::handle:horizontal:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #222222, stop:1 #141414);
    border: 1px solid #2a2a2a;
}

QSlider::handle:horizontal:disabled {
    background: #5a5a5a;
}

QSlider#presetModeSlider {
    margin: 3px 0 0 0;
}

QSlider#presetModeSlider::groove:horizontal {
    margin: 1px 0 0 0;
}

QSlider::add-page:horizontal {
    background: transparent;
}

NoWheelSlider#sourcesRatioSlider {
    min-height: 22px;
    margin: 0px;
}

NoWheelSlider#sourcesRatioSlider::handle:horizontal {
    margin-top: -2px;
    margin-bottom: -2px;
}

/* Active indicator on the most-recently-moved slider handle */
QSlider[lastMoved="true"]::handle:horizontal {
    width: 12px;
    height: 6px;
    margin: -4px 0;
    border-radius: 5px;
    border: 1.5px solid #111111;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:0.85 #1a1a1a, stop:1 #111111);
}
"""

SCROLL_AREA_STYLE = """
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""

# Sources-specific field styling
RSS_INPUT_STYLE = (
    "QLineEdit#rssFeedInput {"
    " border: 1px solid rgba(70,70,70,0.6);"
    " border-radius: 6px;"
    " padding: 8px 10px;"
    " background-color: #282828;"
    " box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.45);"
    " }"
    "QLineEdit#rssFeedInput:focus {"
    " border-color: rgba(200,200,200,0.85);"
    " }"
)

# --- Accessibility tab styles ---

ACCESSIBILITY_TITLE_STYLE = "font-size: 18px; font-weight: bold; color: #ffffff;"

ACCESSIBILITY_DESC_STYLE = "color: #aaaaaa; font-size: 11px; margin-bottom: 10px;"

ACCESSIBILITY_SECTION_DESC_STYLE = "color: #888888; font-size: 10px; margin-top: 5px;"


def build_bucket_toggle(
    host_layout: QVBoxLayout,
    title: str,
    expanded: bool = False,
    on_toggle: Callable[[bool], None] | None = None,
    defer_initial_visibility: bool = False,
) -> tuple[QToolButton, QWidget, QVBoxLayout]:
    """Create a collapsible bucket toggle with arrow indicator.

    Matches the established visualizer bucket design: a QToolButton with
    a Down/Right arrow and text beside the icon.  Returns
    ``(toggle_button, body_widget, body_layout)``.
    """
    toggle = QToolButton()
    toggle.setText(title)
    toggle.setCheckable(True)
    toggle.setChecked(expanded)
    toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
    toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    toggle.setAutoRaise(True)

    toggle_row = QHBoxLayout()
    toggle_row.addWidget(toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(12, 0, 0, 8)
    body_layout.setSpacing(4)
    if not defer_initial_visibility:
        body.setVisible(expanded)
    host_layout.addWidget(body)

    def _apply_state(checked: bool) -> None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        if body.isHidden() == bool(checked):
            body.setVisible(checked)
        if on_toggle is not None:
            on_toggle(checked)

    toggle.toggled.connect(_apply_state)
    return toggle, body, body_layout
