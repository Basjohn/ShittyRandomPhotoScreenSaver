"""The shared Settings spinbox skin must centre actual values, not just padding.

Changing editor padding cannot correct a default-left QAbstractSpinBox. Qt's
``text-align`` QSS property does not apply to spinboxes: use the ``alignment``
Q_PROPERTY owned by QAbstractSpinBox, for both whole and decimal values.
"""

import pytest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit, QSpinBox, QWidget

from tests._invisible_windows import keep_off_screen
from ui.tabs import shared_styles


@pytest.mark.parametrize("spin_class", (QSpinBox, QDoubleSpinBox))
@pytest.mark.parametrize("skin_first", (True, False))
def test_shared_settings_spinbox_value_is_centered(qt_app, spin_class, skin_first):
    """Verify the Qt property after actual stylesheet polish, including lazy rows."""
    host = QWidget()
    if skin_first:
        host.setStyleSheet(shared_styles.SPINBOX_STYLE)

    spin = spin_class(host)
    spin.setFixedWidth(320)
    spin.setSuffix(" px")
    spin.setValue(77)
    if not skin_first:
        host.setStyleSheet(shared_styles.SPINBOX_STYLE)

    try:
        keep_off_screen(host)
        host.show()
        keep_off_screen(spin.window())      # the same host: the guard reads each show's own top-level
        spin.show()
        spin.ensurePolished()
        qt_app.processEvents()

        assert bool(spin.alignment() & Qt.AlignmentFlag.AlignHCenter)
        assert not bool(spin.alignment() & Qt.AlignmentFlag.AlignLeft)
        editor = spin.findChild(QLineEdit)
        assert editor is not None
        assert bool(editor.alignment() & Qt.AlignmentFlag.AlignHCenter)
    finally:
        host.close()
        host.deleteLater()


def test_direct_shared_style_binding_centers_spinbox(qt_app):
    """Controls with their own shared style, not just styled tab parents, agree."""
    spin = QSpinBox()
    try:
        shared_styles.bind_shared_styles(spin, "SPINBOX_STYLE")
        spin.ensurePolished()
        qt_app.processEvents()
        assert bool(spin.alignment() & Qt.AlignmentFlag.AlignHCenter)
    finally:
        spin.deleteLater()
