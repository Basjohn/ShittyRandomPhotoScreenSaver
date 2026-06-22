from __future__ import annotations

from typing import Any

import widgets.overlay_timers as overlay_timers


class _FakeThread:
    pass


class _FakeTimer:
    def __init__(self, owner_thread: _FakeThread) -> None:
        self.owner_thread = owner_thread
        self.stop_calls = 0

    def thread(self) -> _FakeThread:
        return self.owner_thread

    def stop(self) -> None:
        self.stop_calls += 1

    def isActive(self) -> bool:
        return self.stop_calls == 0


def test_overlay_timer_stop_runs_directly_on_owner_thread(monkeypatch) -> None:
    owner_thread = _FakeThread()
    timer = _FakeTimer(owner_thread)

    class _FakeQThread:
        @staticmethod
        def currentThread() -> _FakeThread:
            return owner_thread

    queued_calls: list[tuple[Any, str, Any]] = []

    class _FakeQMetaObject:
        @staticmethod
        def invokeMethod(timer_arg, method_name: str, connection_type) -> None:
            queued_calls.append((timer_arg, method_name, connection_type))

    monkeypatch.setattr(overlay_timers, "QThread", _FakeQThread)
    monkeypatch.setattr(overlay_timers, "QMetaObject", _FakeQMetaObject)

    handle = overlay_timers.OverlayTimerHandle(timer)  # type: ignore[arg-type]
    handle.stop()

    assert timer.stop_calls == 1
    assert queued_calls == []
    assert not handle.is_active()


def test_overlay_timer_stop_queues_to_owner_thread_when_called_off_thread(monkeypatch) -> None:
    owner_thread = _FakeThread()
    caller_thread = _FakeThread()
    timer = _FakeTimer(owner_thread)

    class _FakeQThread:
        @staticmethod
        def currentThread() -> _FakeThread:
            return caller_thread

    queued_calls: list[tuple[Any, str, Any]] = []

    class _FakeQMetaObject:
        @staticmethod
        def invokeMethod(timer_arg, method_name: str, connection_type) -> None:
            queued_calls.append((timer_arg, method_name, connection_type))

    monkeypatch.setattr(overlay_timers, "QThread", _FakeQThread)
    monkeypatch.setattr(overlay_timers, "QMetaObject", _FakeQMetaObject)

    handle = overlay_timers.OverlayTimerHandle(timer)  # type: ignore[arg-type]
    handle.stop()

    assert timer.stop_calls == 0
    assert queued_calls == [(timer, "stop", overlay_timers.Qt.ConnectionType.QueuedConnection)]
    assert not handle.is_active()
