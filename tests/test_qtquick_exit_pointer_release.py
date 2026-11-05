"""Exit must leave the desktop pointer as the arrow, with nothing captured.

Operator report (5 Nov): after the saver exits, the last cursor it showed (a link's
pointing hand) stays on screen until a click. The production retirement entry
(`QuickDisplayRuntime.close_runtime` -> `QuickDisplayWindow.queue_close`) set the arrow
once, but the retiring window kept forwarding pointer motion into Qt Quick hover,
which re-installed the hovered item's pointing hand, and Qt's implicit press capture
from the exit click stayed on the HWND through the synchronous teardown.

The window is never shown (operator rule). Hover is delivered through the real
QQuickWindow event path; Qt's own implicit capture is the same `SetCapture` this test
issues, since Qt refuses an explicit grab for a hidden window.
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QMouseEvent
from PySide6.QtQml import QQmlComponent, qmlEngine
from PySide6.QtQuick import QQuickWindow

from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow

_LINK_QML = b"""
import QtQuick
Item {
    width: 200; height: 100
    Rectangle { objectName: "linkA"; x: 0; width: 80; height: 80
        HoverHandler { cursorShape: Qt.PointingHandCursor } }
    Rectangle { objectName: "linkB"; x: 120; width: 80; height: 80
        HoverHandler { cursorShape: Qt.PointingHandCursor } }
}
"""
_ON_A = QPointF(40.0, 40.0)
_BETWEEN = QPointF(100.0, 40.0)
_ON_B = QPointF(160.0, 40.0)


class _Win32Pointer:
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetCapture.restype = wintypes.HWND
        self.user32.SetCapture.argtypes = [wintypes.HWND]
        self.user32.SetCapture.restype = wintypes.HWND
        self.user32.ShowCursor.argtypes = [wintypes.BOOL]
        self.user32.ShowCursor.restype = ctypes.c_int

    def capture(self) -> int:
        return int(self.user32.GetCapture() or 0)

    def show_count(self) -> int:
        count = int(self.user32.ShowCursor(True))
        self.user32.ShowCursor(False)
        return count - 1


def _move(window: QQuickWindow, pos: QPointF) -> None:
    QGuiApplication.sendEvent(window, QMouseEvent(
        QEvent.Type.MouseMove, pos, QPointF(window.mapToGlobal(pos.toPoint())),
        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
    ))


def _hovered_exit(qt_app, qtbot) -> dict[str, object]:
    """Hover a link (pointing hand), hold the press capture, exit, keep moving."""

    win32 = _Win32Pointer() if sys.platform == "win32" else None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0, runtime_generation=5511, screen=qt_app.primaryScreen(),
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=True),
        interaction_mode_enabled=True,
    )
    window = runtime.window
    window.resize(240, 120)
    component = QQmlComponent(qmlEngine(runtime.scene_controller.scene_root))
    component.setData(_LINK_QML, QUrl())
    links = component.create()
    assert links is not None, component.errors()
    links.setParentItem(window.contentItem())
    facts: dict[str, object] = {}
    try:
        show_count = None if win32 is None else win32.show_count()
        _move(window, _BETWEEN)
        _move(window, _ON_A)
        assert window.cursor().shape() == Qt.CursorShape.PointingHandCursor
        hwnd = int(window.winId())
        if win32 is not None:
            win32.user32.SetCapture(hwnd)
            assert win32.capture() == hwnd

        assert runtime.close_runtime() is True
        facts["capture_after_close"] = None if win32 is None else win32.capture()
        # The pointer keeps moving while the retiring window is still on screen.
        _move(window, _BETWEEN)
        _move(window, _ON_B)
        facts["cursor_after_motion"] = window.cursor().shape()
        qtbot.waitUntil(lambda: runtime.describe_runtime_state()["window_delete_queued"], timeout=5000)
        facts["final_cursor"] = window.cursor().shape()
        facts["grabber_item"] = window.mouseGrabberItem()
        facts["override_cursor"] = QGuiApplication.overrideCursor()
        facts["other_windows"] = [
            (w.objectName(), w.cursor().shape())
            for w in QGuiApplication.topLevelWindows()
            if isinstance(w, QuickDisplayWindow) and w is not window
            and w.cursor().shape() != Qt.CursorShape.ArrowCursor
        ]
        if win32 is not None:
            facts["capture_final"] = win32.capture()
            facts["show_count_balanced"] = win32.show_count() == show_count
    finally:
        if win32 is not None and win32.capture() == int(window.winId()):
            win32.user32.ReleaseCapture()
        links.deleteLater()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
    return facts


@pytest.mark.qt
def test_exit_from_a_hovered_link_leaves_arrow_and_no_capture(qt_app, qtbot) -> None:
    facts = _hovered_exit(qt_app, qtbot)

    assert facts["cursor_after_motion"] == Qt.CursorShape.ArrowCursor
    assert facts["final_cursor"] == Qt.CursorShape.ArrowCursor
    assert facts["grabber_item"] is None
    assert facts["override_cursor"] is None
    assert facts["other_windows"] == []
    if sys.platform == "win32":
        # Released at the retirement edge, not later by the queued hide/destroy.
        assert facts["capture_after_close"] == 0
        assert facts["capture_final"] == 0
        assert facts["show_count_balanced"] is True


@pytest.mark.qt
def test_negative_control_old_retirement_keeps_hand_and_capture(qt_app, qtbot, monkeypatch) -> None:
    """Without the retirement fence the reported state reproduces at this seam."""

    monkeypatch.setattr(QuickDisplayWindow, "_relinquish_pointer", lambda self: None)
    monkeypatch.setattr(QuickDisplayWindow, "_retiring_pointer_event", lambda self, kind: False)
    facts = _hovered_exit(qt_app, qtbot)

    assert facts["cursor_after_motion"] == Qt.CursorShape.PointingHandCursor
    if sys.platform == "win32":
        assert facts["capture_after_close"] != 0
