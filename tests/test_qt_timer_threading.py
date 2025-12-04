from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import QObject, qInstallMessageHandler

from widgets.overlay_timers import create_overlay_timer


class _DummyWidget(QObject):
    """Minimal QObject used to host overlay timers in tests."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)


@pytest.mark.qt
def test_overlay_timer_stop_is_safe_from_other_threads(qt_app) -> None:
    """Stopping an overlay timer from a non-UI thread must not trigger Qt warnings.

    This guards against the `QObject::killTimer: Timers cannot be stopped from another
    thread` warning by ensuring OverlayTimerHandle.stop() always routes the stop call
    to the timer's owning thread.
    """

    messages: list[str] = []

    def _handler(mode, context, message):  # type: ignore[override]
        try:
            messages.append(str(message))
        except Exception:
            # Best-effort only; never raise from the Qt message handler.
            pass

    previous = qInstallMessageHandler(_handler)
    try:
        widget = _DummyWidget()

        fired = {"count": 0}

        def _cb() -> None:
            fired["count"] += 1

        handle = create_overlay_timer(widget, 10, _cb, description="cross-thread-stop-test")
        assert handle.is_active()

        # Stop the timer from a background Python thread.
        t = threading.Thread(target=handle.stop)
        t.start()
        t.join(timeout=2.0)

        # Allow the queued stop to execute on the timer's owning thread.
        qt_app.processEvents()

    finally:
        qInstallMessageHandler(previous)

    # No Qt warning about stopping timers from another thread should appear.
    assert not any("Timers cannot be stopped from another thread" in m for m in messages)
