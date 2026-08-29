"""Sine Line 4 UI binding against the current shared Settings controls.

The Settings overhaul centralized colour swatches in ``ui.styled_popup``.
Programmatic ``set_color`` intentionally does not emit ``color_changed`` (loads
must not save); the user-selection signal is what the builder binds to the
attribute/save flow.
"""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget
import pytest

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import bind_color_button


@pytest.mark.qt
def test_programmatic_swatch_load_does_not_trigger_save(qt_app, qtbot):
    class _Tab(QWidget):
        def __init__(self):
            super().__init__()
            self.save_calls = 0

        def _save_settings(self):
            self.save_calls += 1

    tab = _Tab()
    qtbot.addWidget(tab)
    button = ColorSwatchButton(parent=tab, auto_picker=False, title="Line 4 Color")
    bind_color_button(tab, button, "_sine_line4_color")

    button.set_color(QColor(10, 20, 30, 230))

    assert button.color().getRgb() == (10, 20, 30, 230)
    assert not hasattr(tab, "_sine_line4_color")
    assert tab.save_calls == 0


@pytest.mark.qt
def test_line4_user_color_signal_updates_attribute_and_requests_save(qt_app, qtbot):
    class _Tab(QWidget):
        def __init__(self):
            super().__init__()
            self.save_calls = 0

        def _save_settings(self):
            self.save_calls += 1

    tab = _Tab()
    qtbot.addWidget(tab)
    button = ColorSwatchButton(parent=tab, auto_picker=False, title="Line 4 Color")
    bind_color_button(tab, button, "_sine_line4_color")

    chosen = QColor(0, 255, 255, 230)
    button.set_color(chosen)
    button.color_changed.emit(chosen)

    assert tab._sine_line4_color.getRgb() == (0, 255, 255, 230)
    assert tab.save_calls == 1
