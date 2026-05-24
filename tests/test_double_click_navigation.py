import pytest
import sys
from unittest.mock import MagicMock, PropertyMock
from PySide6.QtCore import QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QWidget
from types import SimpleNamespace
from PySide6.QtCore import Qt

# Ensure project root is in path for running as script or via pytest
if __name__ == "__main__":
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    sys.exit(pytest.main(["-v", __file__]))

from rendering.input_handler import InputHandler
from rendering.display_widget import DisplayWidget
from rendering.widget_manager import WidgetManager


def _make_event():
    """Create a mock QMouseEvent with globalPosition."""
    event = MagicMock(spec=QMouseEvent)
    gp = MagicMock()
    gp.toPoint.return_value = QPoint(100, 100)
    event.globalPosition.return_value = gp
    return event


# ======================================================================
# Legacy navigation (fallback when no widget consumes)
# ======================================================================

def test_double_click_triggers_next_image():
    """Double click event should trigger next_image_requested when no widget consumes."""
    handler = InputHandler(None)

    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)

    event = _make_event()
    handler.handle_mouse_double_click(event)

    mock_slot.assert_called_once()


def test_double_click_ignored_when_menu_active():
    """Double click should be ignored if context menu is active."""
    handler = InputHandler(None)
    handler.set_context_menu_active(True)

    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)

    event = _make_event()
    handler.handle_mouse_double_click(event)

    mock_slot.assert_not_called()


# ======================================================================
# WidgetManager dispatch
# ======================================================================

def test_widget_manager_dispatch_consumed():
    """When a widget consumes the double-click, next_image is NOT emitted."""
    wm = MagicMock(spec=WidgetManager)
    wm.dispatch_double_click.return_value = True

    handler = InputHandler(None, widget_manager=wm)
    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)

    event = _make_event()
    result = handler.handle_mouse_double_click(event)

    assert result is True
    wm.dispatch_double_click.assert_called_once()
    mock_slot.assert_not_called()


def test_widget_manager_dispatch_not_consumed():
    """When no widget consumes, next_image IS emitted (fallback)."""
    wm = MagicMock(spec=WidgetManager)
    wm.dispatch_double_click.return_value = False

    handler = InputHandler(None, widget_manager=wm)
    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)

    event = _make_event()
    result = handler.handle_mouse_double_click(event)

    assert result is True
    wm.dispatch_double_click.assert_called_once()
    mock_slot.assert_called_once()


def test_widget_manager_dispatch_exception_falls_back():
    """If dispatch raises, fall back to next_image gracefully."""
    wm = MagicMock(spec=WidgetManager)
    wm.dispatch_double_click.side_effect = RuntimeError("boom")

    handler = InputHandler(None, widget_manager=wm)
    mock_slot = MagicMock()
    handler.next_image_requested.connect(mock_slot)

    event = _make_event()
    result = handler.handle_mouse_double_click(event)

    assert result is True
    mock_slot.assert_called_once()


def test_display_widget_mouse_double_click_suppressed_during_recreation_guard(monkeypatch):
    DisplayWidget.suppress_pointer_input_globally(500, reason="test_guard")

    accepted = []
    event = MagicMock(spec=QMouseEvent)
    event.accept.side_effect = lambda: accepted.append("accepted")
    handler = MagicMock()

    class _PointerGuardStub:
        _pointer_input_suppressed_until_ts = 0.0
        _pointer_input_suppression_reason = ""

        def __init__(self):
            self.screen_index = 0
            self._input_handler = handler

        def _should_suppress_runtime_pointer_input(self, source: str) -> bool:
            self.__class__._pointer_input_suppressed_until_ts = DisplayWidget._pointer_input_suppressed_until_ts
            self.__class__._pointer_input_suppression_reason = DisplayWidget._pointer_input_suppression_reason
            return DisplayWidget._should_suppress_runtime_pointer_input(self, source)

    stub = _PointerGuardStub()

    DisplayWidget.mouseDoubleClickEvent(stub, event)

    assert accepted == ["accepted"]
    handler.handle_mouse_double_click.assert_not_called()
    DisplayWidget.clear_pointer_input_suppression()


def test_display_widget_edit_mode_background_click_schedules_global_restack(monkeypatch):
    scheduled: list[str] = []
    event = MagicMock()
    event.button.return_value = Qt.MouseButton.LeftButton
    event.accept.side_effect = lambda: scheduled.append("accepted")

    monkeypatch.setattr(
        "rendering.display_widget.CustomLayoutManager.schedule_raise_all_active_shells",
        classmethod(lambda cls: scheduled.append("restack")),
    )

    stub = SimpleNamespace(
        _custom_layout_edit_active=True,
        _should_suppress_runtime_pointer_input=lambda source: False,
    )

    DisplayWidget.mousePressEvent(stub, event)

    assert scheduled == ["restack", "accepted"]


# ======================================================================
# WidgetManager.dispatch_double_click hit-testing
# ======================================================================

class TestWidgetManagerDispatch:
    """Unit tests for WidgetManager.dispatch_double_click."""

    def _make_wm(self):
        parent = MagicMock()
        parent.screen_index = 0
        type(parent)._has_rendered_first_frame = PropertyMock(return_value=True)
        wm = WidgetManager(parent, resource_manager=None)
        return wm

    def test_dispatch_to_visible_widget(self):
        wm = self._make_wm()
        widget = MagicMock(spec=QWidget)
        widget.isVisible.return_value = True
        widget.mapFromGlobal.return_value = QPoint(5, 5)
        widget.rect.return_value = MagicMock()
        widget.rect.return_value.contains.return_value = True
        widget.handle_double_click = MagicMock(return_value=True)

        wm.register_widget("test", widget)
        assert wm.dispatch_double_click(QPoint(100, 100)) is True
        widget.handle_double_click.assert_called_once()

    def test_dispatch_skips_hidden_widget(self):
        wm = self._make_wm()
        widget = MagicMock(spec=QWidget)
        widget.isVisible.return_value = False
        widget.handle_double_click = MagicMock(return_value=True)

        wm.register_widget("test", widget)
        assert wm.dispatch_double_click(QPoint(100, 100)) is False
        widget.handle_double_click.assert_not_called()

    def test_dispatch_skips_widget_outside_bounds(self):
        wm = self._make_wm()
        widget = MagicMock(spec=QWidget)
        widget.isVisible.return_value = True
        widget.mapFromGlobal.return_value = QPoint(500, 500)
        widget.rect.return_value = MagicMock()
        widget.rect.return_value.contains.return_value = False
        widget.handle_double_click = MagicMock(return_value=True)

        wm.register_widget("test", widget)
        assert wm.dispatch_double_click(QPoint(100, 100)) is False
        widget.handle_double_click.assert_not_called()

    def test_dispatch_widget_without_handler_is_skipped(self):
        wm = self._make_wm()
        widget = MagicMock(spec=QWidget)
        widget.isVisible.return_value = True
        widget.mapFromGlobal.return_value = QPoint(5, 5)
        widget.rect.return_value = MagicMock()
        widget.rect.return_value.contains.return_value = True
        # No handle_double_click attribute
        if hasattr(widget, 'handle_double_click'):
            del widget.handle_double_click

        wm.register_widget("test", widget)
        assert wm.dispatch_double_click(QPoint(100, 100)) is False

    def test_dispatch_returns_false_when_no_widgets(self):
        wm = self._make_wm()
        assert wm.dispatch_double_click(QPoint(100, 100)) is False
