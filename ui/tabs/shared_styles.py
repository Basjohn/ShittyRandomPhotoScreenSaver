"""Shared QSS styles and widgets for settings dialog tabs.

Centralises repeated styling blocks and common widgets so individual tabs
don't duplicate them.
"""
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QSlider

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


class NoWheelSlider(QSlider):
    """Slider that ignores mouse wheel events to prevent accidental changes."""
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()

SPINBOX_STYLE = """
/* Rounded inputs without visible seams */
QSpinBox, QDoubleSpinBox, QLineEdit {
    min-height: 36px;
    padding: 4px 40px 4px 16px;
    color: #ffffff;
    font-family: 'Jost';
    font-weight: 600;
    background-color: #101010;
    border: 2px solid rgba(255, 255, 255, 0.45);
    border-radius: 18px;
}

QLineEdit {
    padding-right: 16px;
}

QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:hover {
    border-color: rgba(255, 255, 255, 0.6);
}

QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: rgba(255, 255, 255, 0.95);
}

QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled {
    color: rgba(255, 255, 255, 0.35);
    border-color: rgba(255, 255, 255, 0.2);
    background-color: #121212;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: right;
    width: 28px;
    border: none;
    background: transparent;
    margin: 3px 6px 3px 0px;
    padding: 0px;
    border-radius: 10px;
}

QSpinBox::up-button {
    subcontrol-position: top right;
}

QSpinBox::down-button {
    subcontrol-position: bottom right;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: rgba(255, 255, 255, 0.12);
}

QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: rgba(255, 255, 255, 0.25);
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 7px solid #ffffff;
    margin-top: 3px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 0px;
    height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 7px solid #ffffff;
    margin-bottom: 3px;
}
"""

CIRCLE_CHECKBOX_STYLE = """
/* Circular indicator prototype (feature flag via `circleIndicator` dynamic property). */
QCheckBox[circleIndicator='true'] {
    spacing: 12px;
    padding: 2px 10px 2px 4px;
    min-height: 28px;
}

QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 2px 8px 2px 2px;
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
    font-family: 'Jost';
    font-weight: 700;
    font-size: 14px;
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

SCROLL_AREA_STYLE = """
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollArea QWidget { background: transparent; }
"""

# --- Accessibility tab styles ---

ACCESSIBILITY_TITLE_STYLE = "font-size: 18px; font-weight: bold; color: #ffffff;"

ACCESSIBILITY_DESC_STYLE = "color: #aaaaaa; font-size: 11px; margin-bottom: 10px;"

ACCESSIBILITY_SECTION_DESC_STYLE = "color: #888888; font-size: 10px; margin-top: 5px;"
