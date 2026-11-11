"""A retiring display window tells WINDOWS the arrow, not only Qt (R-183).

Every earlier round asserted ``QWindow.cursor().shape()``, a Qt property. Qt passes a window's cursor to Windows
only while its own window-under-mouse is that window (qwindowswindow.cpp ``applyNewCursor``), and Windows never
re-queries a still pointer when the window hides or the process ends (native harness:
``tools/cursor_exit_native_harness.py``). So these tests assert the native-facing action: the retire owner
(``QuickDisplayWindow.queue_close`` -> ``_relinquish_pointer``) calls ``SetCursor(IDC_ARROW)`` through
``pointer_capture.show_native_arrow_for_retiring_window`` with its own HWND, and that function issues the
Win32 call. No window is shown (operator rule): "was on screen" is the window's own visibility edge.
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtCore import Qt

from rendering.quick import pointer_capture
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="the native arrow is a Windows remedy")


def _window(qt_app) -> QuickDisplayWindow:
    return QuickDisplayWindow(
        screen_index=0, runtime_generation=1830, screen=qt_app.primaryScreen(),
        policy=QuickWindowPolicy(always_on_top=False, accepts_focus=False),
    )


def _record_native_arrow(monkeypatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(pointer_capture, "show_native_arrow_for_retiring_window",
                        lambda hwnd: calls.append(int(hwnd)) or True, raising=False)
    return calls


@windows_only
@pytest.mark.qt
def test_retiring_window_that_was_on_screen_sets_the_native_arrow(qt_app, monkeypatch) -> None:
    calls = _record_native_arrow(monkeypatch)
    window = _window(qt_app)
    try:
        window._on_window_visibility_changed(True)     # the real show edge (visibleChanged) without showing
        hwnd = int(window.winId())
        window.queue_close()
        assert calls == [hwnd], "the retire owner never told Windows the arrow"
        assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
        window.queue_close()                           # idempotent: retirement runs once
        assert calls == [hwnd]
    finally:
        window.deleteLater()
        qt_app.processEvents()


@windows_only
@pytest.mark.qt
def test_never_shown_window_creates_no_native_window_for_the_arrow(qt_app, monkeypatch) -> None:
    calls = _record_native_arrow(monkeypatch)
    window = _window(qt_app)
    try:
        window.queue_close()
        assert calls == []
    finally:
        window.deleteLater()
        qt_app.processEvents()


class _FakeWin32:
    """The six Win32 calls of the native arrow, recorded."""

    def __init__(self, *, root: int, root_thread: int, current_thread: int = 7) -> None:
        self.root, self.root_thread, self.current_thread = root, root_thread, current_thread
        self.set_cursor: list[int] = []

    # user32
    def GetCursorPos(self, point) -> int:
        return 1

    def WindowFromPoint(self, point) -> int:
        return self.root + 1                          # a child of the root

    def GetAncestor(self, hwnd, flags) -> int:
        assert flags == 2                             # GA_ROOT
        return self.root

    def GetWindowThreadProcessId(self, hwnd, pid) -> int:
        return self.root_thread

    def LoadCursorW(self, instance, resource) -> int:
        assert instance is None and resource.value == 32512   # IDC_ARROW, the shared system arrow
        return 0x10003

    def SetCursor(self, handle) -> int:
        self.set_cursor.append(handle)
        return 0

    # kernel32
    def GetCurrentThreadId(self) -> int:
        return self.current_thread


@pytest.mark.parametrize(
    ("root", "root_thread", "expected"),
    [
        (0x500, 7, [0x10003]),     # the pointer is over the retiring window itself
        (0x900, 99, [0x10003]),    # over another process's window: a frozen saver shape is reset to the arrow
        (0x900, 7, []),            # over another live window of this GUI thread: it owns its own cursor
    ],
)
def test_native_arrow_issues_set_cursor_with_the_system_arrow(monkeypatch, root, root_thread, expected) -> None:
    fake = _FakeWin32(root=root, root_thread=root_thread)
    monkeypatch.setattr(pointer_capture, "_retire_api", lambda: (fake, fake))
    assert pointer_capture.show_native_arrow_for_retiring_window(0x500) is bool(expected)
    assert fake.set_cursor == expected


def test_native_arrow_ignores_a_missing_window(monkeypatch) -> None:
    def _no_api():
        raise AssertionError("no Win32 call without a window")

    monkeypatch.setattr(pointer_capture, "_retire_api", _no_api)
    assert pointer_capture.show_native_arrow_for_retiring_window(0) is False
