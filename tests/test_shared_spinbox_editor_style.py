"""Prevent the shared rounded spinbox from styling its embedded editor as a second input."""

import re

from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox, QWidget

from tests._invisible_windows import keep_off_screen
from ui.tabs import shared_styles


def test_spinbox_inner_editor_has_no_standalone_line_edit_min_height(qt_app):
    css = shared_styles.SPINBOX_STYLE
    assert "QSpinBox, QDoubleSpinBox, QLineEdit, QAbstractSpinBox" not in css
    inner_rule = re.search(r"QAbstractSpinBox > QLineEdit\s*\{([^}]+)\}", css)
    assert inner_rule is not None
    assert "min-height: 0px" in inner_rule.group(1)
    assert "padding: 0px" in inner_rule.group(1)

    host = QWidget()
    host.setStyleSheet(css)
    for spin_type in (QSpinBox, QDoubleSpinBox):
        spin = spin_type(host)
        spin.setFixedWidth(220)
        spin.setValue(77)
        keep_off_screen(spin.window())      # the host: never a visible window on the operator's screen
        spin.show()
        keep_off_screen(host)
        host.show()
        qt_app.processEvents()
        # The edit field belongs to the spinbox, not to an independently tall
        # QLineEdit. Its baseline must stay centred at the outer control's height.
        editor = spin.lineEdit()
        assert abs(editor.geometry().center().y() - spin.rect().center().y()) <= 4
        spin.deleteLater()
    host.deleteLater()
