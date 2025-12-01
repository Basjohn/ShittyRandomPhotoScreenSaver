from __future__ import annotations

from typing import Dict, Any

import pytest
from PySide6.QtCore import QObject

from widgets.overlay_timers import create_overlay_timer, OverlayTimerHandle


class _DummyWidget(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # ThreadManager, when present, is looked up via this attribute.
        self._thread_manager: Any | None = None


class _StubTimer:
    def __init__(self) -> None:
        self._active = True

    def stop(self) -> None:
        self._active = False

    def isActive(self) -> bool:  # type: ignore[override]
        return self._active


class _StubThreadManager:
    def __init__(self) -> None:
        self.calls: list[tuple[int, Any]] = []

    def schedule_recurring(self, interval_ms: int, callback):
        # Record call and return a stub timer so OverlayTimerHandle can wrap it.
        self.calls.append((interval_ms, callback))
        return _StubTimer()


@pytest.mark.qt
def test_overlay_timer_uses_thread_manager_when_available(qt_app):
    """When a ThreadManager is present, create_overlay_timer should use it.

    This locks in the centralised timing path instead of ad-hoc QTimers for
    overlay widgets.
    """

    widget = _DummyWidget()
    tm = _StubThreadManager()
    widget._thread_manager = tm  # type: ignore[attr-defined]

    fired: Dict[str, int] = {"count": 0}

    def _cb() -> None:
        fired["count"] += 1

    handle = create_overlay_timer(widget, 1000, _cb, description="test-timer")

    assert isinstance(handle, OverlayTimerHandle)
    # schedule_recurring should have been called exactly once with the interval.
    assert len(tm.calls) == 1
    interval, cb = tm.calls[0]
    assert interval >= 1
    assert cb is _cb

    # Stub timer should report active until stopped via handle.
    assert handle.is_active()
    handle.stop()
    assert not handle.is_active()


@pytest.mark.qt
def test_overlay_timer_falls_back_to_qtimer_without_thread_manager(qt_app, qtbot):
    """Without a ThreadManager, create_overlay_timer should use a local QTimer.

    We verify that the timer fires at least once and that the OverlayTimerHandle
    correctly tracks active/stop state.
    """

    widget = _DummyWidget()
    # No _thread_manager attribute set → forces QTimer path.

    fired: Dict[str, int] = {"count": 0}

    def _cb() -> None:
        fired["count"] += 1

    handle = create_overlay_timer(widget, 5, _cb, description="local-qtimer")
    assert isinstance(handle, OverlayTimerHandle)
    assert handle.is_active()

    # Allow a short period for the QTimer to fire.
    qtbot.wait(30)
    assert fired["count"] >= 1

    # After stop(), timer should no longer be active and should not fire again.
    handle.stop()
    active_after_stop = handle.is_active()
    fired_before = fired["count"]
    qtbot.wait(30)
    assert not active_after_stop
    assert fired["count"] == fired_before
