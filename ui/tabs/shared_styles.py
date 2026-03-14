"""Shared QSS styles and widgets for settings dialog tabs.

Centralises repeated styling blocks and common widgets so individual tabs
don't duplicate them.
"""
import weakref

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QLabel, QSlider

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
_JOST_REGISTERED = False


def _ensure_jost_registered() -> None:
    global _JOST_REGISTERED
    if _JOST_REGISTERED:
        return
    if QApplication.instance() is None:
        return
    for path in _JOST_FONT_PATHS:
        QFontDatabase.addApplicationFont(path)
    _JOST_REGISTERED = True


def ensure_custom_fonts() -> None:
    _ensure_jost_registered()


FORM_LABEL_HEIGHT = 34
SWATCH_LABEL_HEIGHT = 28

_last_moved_slider: weakref.ref | None = None


def apply_section_heading_style(
    label: QLabel,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
) -> None:
    """Normalize section heading labels so they align with adjacent controls."""

    ensure_custom_fonts()
    style_sheet = style or (
        SECTION_HEADING_STYLE_DISABLED if disabled else SECTION_HEADING_STYLE
    )
    label.setStyleSheet(style_sheet)
    label.setFixedHeight(height if height is not None else FORM_LABEL_HEIGHT)
    label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)


def create_section_label(
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
) -> QLabel:
    label = QLabel(text)
    if width is not None:
        label.setFixedWidth(width)
    apply_section_heading_style(label, disabled=disabled, style=style, height=height)
    return label


def add_section_label(
    layout,
    text: str,
    width: int | None = None,
    *,
    disabled: bool = False,
    style: str | None = None,
    height: int | None = None,
) -> QLabel:
    label = create_section_label(
        text,
        width,
        disabled=disabled,
        style=style,
        height=height,
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
    )


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

    def _mark_last_moved(self, *_args) -> None:
        global _last_moved_slider
        prev = _last_moved_slider() if _last_moved_slider is not None else None
        if prev is self:
            return
        if prev is not None:
            prev.setProperty("lastMoved", False)
            prev.style().unpolish(prev)
            prev.style().polish(prev)
        self.setProperty("lastMoved", True)
        self.style().unpolish(self)
        self.style().polish(self)
        _last_moved_slider = weakref.ref(self)

    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()

SPINBOX_STYLE = """
/* Rounded inputs with opaque borders + circular stepper controls */
QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox {
    min-height: 36px;
    padding: 4px 48px 4px 16px;
    margin-bottom: 14px;
    color: #ffffff;
    font-family: 'Jost';
    font-weight: 600;
    background-color: #282828;
    border: 2px solid #ffffff;
    border-radius: 18px;
}

QSpinBox > QLineEdit,
QDoubleSpinBox > QLineEdit,
QAbstractSpinBox > QLineEdit {
    background-color: #282828;
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
    background-color: #282828;
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
    min-height: 28px;
}

QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 2px 12px 2px 0px;
    border: none;
    background: transparent;
    image: none;
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
    min-height: 38px;
    padding: 4px 44px 4px 16px;
    margin-bottom: 14px;
    font-family: 'Jost';
    font-weight: 700;
    font-size: 14px;
    letter-spacing: 0.4px;
    color: #ffffff;
    border: none;
    background: transparent;
    border-image: url(:/ui/assets/combobox_closed.svg) 0 0 0 0 stretch stretch;
}

QComboBox[customCombo='true']:hover,
QComboBox[customCombo='true']:focus,
QComboBox[customCombo='true']:on {
    border-image: url(:/ui/assets/combobox_closed_hover.svg) 0 0 0 0 stretch stretch;
    outline: none;
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
    max-height: 44px;
    padding: 4px 48px 4px 16px;
}

QComboBox[customCombo='true'][comboSize='compact'] {
    min-width: 164px;
    max-height: 40px;
    padding: 2px 42px 2px 14px;
    font-size: 13px;
}

QComboBox[customCombo='true'][comboSize='mini'] {
    min-width: 136px;
    max-height: 36px;
    padding: 2px 36px 2px 12px;
    font-size: 12px;
}

QComboBox[customCombo='true'][comboSize='hero'] {
    min-width: 220px;
    max-width: 340px;
    max-height: 46px;
    padding: 6px 54px 6px 18px;
    font-size: 15px;
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
    "font-weight: 700;"
    "font-size: 14px;"
    "letter-spacing: 0.5px;"
    "color: #ffffff;"
    "min-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 0px;"
    "margin-top: -12px;"
    "margin-bottom: 10px;"
    "qproperty-alignment: AlignVCenter;"
)

SECTION_HEADING_STYLE_DISABLED = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 700;"
    "font-size: 14px;"
    "letter-spacing: 0.5px;"
    "color: #666666;"
    "min-height: 34px;"
    "padding-top: 0px;"
    "padding-bottom: 0px;"
    "margin-top: -12px;"
    "margin-bottom: 10px;"
    "qproperty-alignment: AlignVCenter;"
)

SWATCH_LABEL_STYLE = (
    "font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';"
    "font-weight: 700;"
    "font-size: 13px;"
    "letter-spacing: 0.4px;"
    "color: #ffffff;"
    f"min-height: {SWATCH_LABEL_HEIGHT}px;"
    "padding-top: 0px;"
    "padding-bottom: 0px;"
    "margin-top: 2px;"
    "margin-bottom: 4px;"
    "qproperty-alignment: AlignVCenter;"
)

SUBSECTION_DIVIDER_STYLE = (
    "border: 1px solid rgba(255, 255, 255, 0.8);"
    "border-radius: 18px;"
)


def style_group_box(box) -> None:
    """Apply the subsection border style to a QGroupBox.

    Only sets border + border-radius per-widget.  All other QGroupBox
    properties (background, padding, margins, ::title font/color) are
    inherited from the dialog-level stylesheet in settings_theme.py.
    Keeping the per-widget rule minimal avoids overriding the theme.
    """
    box.setStyleSheet(f"QGroupBox {{{SUBSECTION_DIVIDER_STYLE}}}")

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
    border: 1px solid #444444;
    border-bottom-color: rgba(0, 0, 0, 0.6);
}

QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a3a3a, stop:0.85 #242424, stop:1 #181818);
    border: 1px solid #555555;
    border-bottom-color: rgba(0, 0, 0, 0.55);
}

QSlider::handle:horizontal:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #222222, stop:1 #141414);
    border: 1px solid #2a2a2a;
}

QSlider::handle:horizontal:disabled {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(50, 50, 50, 0.5), stop:1 rgba(35, 35, 35, 0.5));
    border: 1px solid rgba(40, 40, 40, 0.4);
}

QSlider::add-page:horizontal {
    background: transparent;
}

/* Active indicator on the most-recently-moved slider handle */
QSlider[lastMoved="true"]::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:0.85 #1a1a1a, stop:1 #111111);
    margin: -4px 0;
    border-radius: 5px;
    border: 2px solid #202020;
    border-bottom-color: rgba(0, 0, 0, 0.85);
}
"""

SCROLL_AREA_STYLE = """
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
"""

# --- Accessibility tab styles ---

ACCESSIBILITY_TITLE_STYLE = "font-size: 18px; font-weight: bold; color: #ffffff;"

ACCESSIBILITY_DESC_STYLE = "color: #aaaaaa; font-size: 11px; margin-bottom: 10px;"

ACCESSIBILITY_SECTION_DESC_STYLE = "color: #888888; font-size: 10px; margin-top: 5px;"
