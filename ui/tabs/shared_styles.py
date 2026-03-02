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
QSpinBox, QDoubleSpinBox {
    background-color: #1e1e1e;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding-right: 28px;
    min-height: 24px;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 24px;
    height: 12px;
    background: #2a2a2a;
    border-left: 1px solid #3a3a3a;
    border-top: 1px solid #3a3a3a;
    border-right: 1px solid #3a3a3a;
    border-bottom: 1px solid #3a3a3a;
    margin: 0px;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 24px;
    height: 12px;
    background: #2a2a2a;
    border-left: 1px solid #3a3a3a;
    border-right: 1px solid #3a3a3a;
    border-bottom: 1px solid #3a3a3a;
    margin: 0px;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #3a3a3a;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background: #505050;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 6px solid #ffffff;
    margin-top: 2px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #ffffff;
    margin-bottom: 2px;
}
"""

CIRCLE_CHECKBOX_STYLE = """
/* Circular indicator prototype (feature flag via `circleIndicator` dynamic property). */
QCheckBox[circleIndicator='true'] {
    spacing: 12px;
}

QCheckBox[circleIndicator='true']::indicator {
    width: 22px;
    height: 22px;
    border-radius: 11px;
    margin: 2px 10px 2px 2px;
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
/* Cursor Halo Shape combobox prototype */
QComboBox[customCombo='true'] {
    min-width: 188px;
    max-width: 200px;
    min-height: 42px;
    max-height: 42px;
    padding: 4px 48px 4px 16px;
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

QComboBox[customCombo='true'] QAbstractItemView {
    background-color: transparent;
    border: 2px solid rgba(255, 255, 255, 0.55);
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

QComboBox[customCombo='true'] QAbstractItemView::viewport {
    background-color: rgba(18, 18, 18, 0.9);
    border-radius: 12px;
}

QComboBox[customCombo='true'] QAbstractItemView::item {
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
