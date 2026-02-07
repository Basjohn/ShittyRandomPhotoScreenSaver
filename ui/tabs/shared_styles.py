"""Shared QSS styles for settings dialog tabs.

Centralises repeated styling blocks so individual tabs don't duplicate them.
"""

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
