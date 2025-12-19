import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from rendering.input_handler import InputHandler


@pytest.mark.qt
def test_hotkeys_work_with_empty_event_text(qt_app, qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)

    handler = InputHandler(parent)

    counts = {
        "prev": 0,
        "next": 0,
        "cycle": 0,
        "settings": 0,
    }

    handler.previous_image_requested.connect(lambda: counts.__setitem__("prev", counts["prev"] + 1))
    handler.next_image_requested.connect(lambda: counts.__setitem__("next", counts["next"] + 1))
    handler.cycle_transition_requested.connect(lambda: counts.__setitem__("cycle", counts["cycle"] + 1))
    handler.settings_requested.connect(lambda: counts.__setitem__("settings", counts["settings"] + 1))

    assert handler.handle_key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Z, Qt.KeyboardModifier.NoModifier, ""))
    assert handler.handle_key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier, ""))
    assert handler.handle_key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.NoModifier, ""))
    assert handler.handle_key_press(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S, Qt.KeyboardModifier.NoModifier, ""))

    assert counts["prev"] == 1
    assert counts["next"] == 1
    assert counts["cycle"] == 1
    assert counts["settings"] == 1
