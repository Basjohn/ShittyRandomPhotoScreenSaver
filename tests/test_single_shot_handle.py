"""PW-05: ThreadManager.single_shot returns a cancellation handle, not a QTimer.

The handle exists before the UI-thread timer (off-thread calls create it
later), cancels through the existing registry path, releases the callback
payload, and never becomes a second lifecycle authority: generation retirement
still cancels everything.
"""

from __future__ import annotations

import gc
import threading
import weakref

import pytest

import core.threading.manager as manager_module
from core.threading.manager import SingleShotHandle, ThreadManager
import widgets.feed_runtime as feed_runtime
import widgets.steam_followed_runtime as steam_followed_runtime


def _scheduled(generation: int) -> int:
    with manager_module._ui_diagnostic_lock:
        return int(
            manager_module._ui_diagnostics["scheduled_single_shots_by_generation"].get(
                str(generation), 0
            )
        )


def _registered(generation: int) -> int:
    with manager_module._single_shot_registry_lock:
        return len(manager_module._single_shot_timers.get(str(generation), ()))


def _callback(generation: int, calls: list):
    def _run() -> None:
        calls.append(True)

    _run._srpss_runtime_generation = generation
    return _run


@pytest.mark.qt
def test_cancel_after_timer_creation(qt_app, qtbot) -> None:
    calls: list = []
    handle = ThreadManager.single_shot(20, _callback(9101, calls))

    assert isinstance(handle, SingleShotHandle)
    assert handle.active and _registered(9101) == 1
    assert handle.cancel() is True
    assert handle.cancelled and not handle.active
    assert handle.cancel() is False
    assert _registered(9101) == 0 and _scheduled(9101) == 0
    qtbot.wait(60)
    assert calls == []


@pytest.mark.qt
def test_cancel_after_fire_is_a_no_op(qt_app, qtbot) -> None:
    calls: list = []
    handle = ThreadManager.single_shot(1, _callback(9102, calls))

    qtbot.waitUntil(lambda: calls == [True], timeout=1000)
    assert handle.fired and not handle.active
    assert handle.cancel() is False
    assert not handle.cancelled
    assert _scheduled(9102) == 0


@pytest.mark.qt
def test_cancel_before_the_ui_thread_creates_the_timer(qt_app, qtbot) -> None:
    calls: list = []
    handles: list = []

    def _worker() -> None:
        handle = ThreadManager.single_shot(1, _callback(9103, calls))
        # The UI thread has not run yet, so no timer exists to cancel.
        assert _registered(9103) == 0
        assert handle.cancel() is True
        handles.append(handle)

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join(timeout=2.0)
    assert not thread.is_alive()
    handle = handles[0]
    assert handle.cancelled

    qtbot.wait(60)  # the queued creation runs, sees the cancel and skips
    assert calls == []
    assert _registered(9103) == 0 and _scheduled(9103) == 0


@pytest.mark.qt
def test_off_thread_cancel_of_a_created_timer_wins_the_race(qt_app, qtbot) -> None:
    calls: list = []
    handle = ThreadManager.single_shot(5, _callback(9104, calls))
    assert _registered(9104) == 1

    thread = threading.Thread(target=handle.cancel)
    thread.start()
    thread.join(timeout=2.0)
    assert handle.cancelled

    qtbot.wait(60)
    assert calls == []
    assert _registered(9104) == 0 and _scheduled(9104) == 0


@pytest.mark.qt
def test_cancel_releases_the_callback_payload_without_gc(qt_app, qtbot) -> None:
    class _PlainOwner:
        pass

    def _schedule():
        owner = _PlainOwner()

        def _publish():
            return owner

        _publish._srpss_runtime_generation = 9105
        return ThreadManager.single_shot(60_000, _publish), weakref.ref(owner)

    was_enabled = gc.isenabled()
    gc.disable()
    try:
        handle, owner_ref = _schedule()
        assert owner_ref() is not None
        assert handle.cancel() is True
        qtbot.waitUntil(lambda: owner_ref() is None, timeout=1000)
    finally:
        if was_enabled:
            gc.enable()


@pytest.mark.qt
def test_generation_retirement_still_cancels_handles(qt_app, qtbot) -> None:
    calls: list = []
    handle = ThreadManager.single_shot(20, _callback(9106, calls))

    assert ThreadManager.cancel_scheduled_single_shots(9106) == 1
    assert handle.cancelled
    assert handle.cancel() is False
    qtbot.wait(60)
    assert calls == []


@pytest.mark.qt
@pytest.mark.parametrize("module", [feed_runtime, steam_followed_runtime])
def test_feed_and_followed_deadlines_live_in_the_shared_registry(
    qt_app, qtbot, module
) -> None:
    calls: list = []
    cancel = module._default_schedule(60_000, _callback(9107, calls))

    assert _registered(9107) == 1, "deadline must be generation-owned, not parentless"
    assert cancel() is True
    assert _registered(9107) == 0 and _scheduled(9107) == 0
    assert calls == []


@pytest.mark.qt
@pytest.mark.parametrize("module", [feed_runtime, steam_followed_runtime])
def test_feed_and_followed_deadlines_fire_once_and_leave_no_residue(
    qt_app, qtbot, module
) -> None:
    # The physical "wait for a FEEDS timer" check, made deterministic: a due
    # deadline fires its refresh callback exactly once through the shared
    # registry, and nothing stays registered or cancellable afterwards.
    calls: list = []
    cancel = module._default_schedule(15, _callback(9108, calls))
    assert _registered(9108) == 1

    qtbot.waitUntil(lambda: calls == [True], timeout=2000)
    qtbot.wait(40)
    assert calls == [True]
    assert _registered(9108) == 0 and _scheduled(9108) == 0
    assert cancel() is False
