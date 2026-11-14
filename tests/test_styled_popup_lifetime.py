"""A StyledPopup lives only as long as its owner holds it.

Its buttons once answered through lambdas that captured the popup; Qt keeps a slot alive with the button, and the
button is the popup's child, so the popup kept itself alive behind the garbage collector's back. Every popup ever
made then lived until interpreter teardown, where it was destroyed after the QApplication (exit 127 / 0xC0000409).

No window is shown: the popup is never exec'd; its buttons are clicked programmatically.
"""
from __future__ import annotations

import gc

import pytest
from PySide6.QtWidgets import QPushButton

from ui.styled_popup import StyledPopup

pytestmark = pytest.mark.usefixtures("qt_app")

_BUTTONS = [("First", "first"), ("Second", "second")]


def _popup() -> StyledPopup:
    return StyledPopup(None, "Title", "Message", icon_type="warning", buttons=list(_BUTTONS))


def test_a_parentless_popup_is_destroyed_when_its_last_reference_goes():
    destroyed = []
    popup = _popup()
    popup.destroyed.connect(lambda *_: destroyed.append(True))
    del popup
    gc.collect()
    assert destroyed == [True], "the popup outlived its last Python reference (a slot retains it)"


def test_each_button_still_answers_with_its_own_value():
    for index, (label, value) in enumerate(_BUTTONS):
        popup = _popup()
        buttons = [b for b in popup.findChildren(QPushButton) if b.text() == label]
        assert len(buttons) == 1
        buttons[0].click()
        assert popup.result_value == value
        assert popup.result() == StyledPopup.DialogCode.Accepted
        popup.deleteLater()
