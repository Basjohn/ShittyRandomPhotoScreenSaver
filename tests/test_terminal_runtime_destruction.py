"""Terminal-purpose runtime destruction barrier (H1b).

Replacement teardown already proves a retiring generation's Quick/QObject/Python
roots drained before a replacement is constructed. Terminal Exit previously did
NOT: `application_exit` armed no barrier, so `QApplication.quit()` ran while the
asynchronous Quick retirement was still in flight, destroying live roots at GC
(BackgroundRenderItem slot error / Windows access violation, Clock null-model
storm).

`RuntimeDestructionBarrier` now takes a `purpose`. These bars pin the two
semantics that must hold:

- a terminal-purpose barrier observes tracked roots to completion even while
  terminal shutdown is requested (it must not self-cancel), then runs its
  terminal finalization exactly once;
- a replacement-purpose barrier still refuses to run its continuation during
  terminal shutdown, and still completes and runs it normally otherwise.
"""
from __future__ import annotations

import gc

import pytest
from PySide6.QtCore import QObject

from engine.runtime_destruction import (
    RuntimeDestructionBarrier,
    qt_replacement_may_run,
)


class _State:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeEngine:
    def __init__(self, *, terminal: bool, state: str) -> None:
        self._terminal_shutdown_requested = terminal
        self._state = _State(state)
        self.resource_manager = None
        self.thread_manager = None
        self._pending_runtime_destruction_barrier = None

    def _get_state(self) -> _State:
        return self._state


class _Root:
    """A plain weak-referenceable retiring-generation root."""


def test_terminal_barrier_waits_for_roots_then_finalizes_exactly_once(qt_app) -> None:
    engine = _FakeEngine(terminal=True, state="SHUTTING_DOWN")
    # Terminal shutdown is requested: replacement is (correctly) forbidden.
    assert qt_replacement_may_run(engine) is False

    barrier = RuntimeDestructionBarrier(
        engine,
        reason="application_exit",
        retiring_generation=7,
        purpose="terminal",
    )
    root = _Root()
    barrier.watch_python_owner(root, label="Root")

    calls: list[int] = []
    barrier.then(lambda: calls.append(1))
    barrier.seal()

    # A tracked root is still live: terminal observation must NOT self-cancel
    # just because terminal shutdown was requested.
    assert barrier.is_complete is False
    assert calls == []

    del root
    gc.collect()

    # The root drained: terminal finalization runs exactly once, despite
    # qt_replacement_may_run() being False.
    assert barrier.is_complete is True
    assert calls == [1]

    # Idempotent: further completion attempts never re-run finalization.
    barrier._maybe_complete()
    assert calls == [1]


def test_replacement_continuation_is_refused_during_terminal_shutdown(qt_app) -> None:
    engine = _FakeEngine(terminal=True, state="SHUTTING_DOWN")

    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=7,
        purpose="replacement",
    )
    calls: list[int] = []
    barrier.then(lambda: calls.append(1))
    barrier.seal()

    # A replacement barrier under terminal shutdown cancels its observation and
    # never runs a replacement continuation.
    assert barrier.is_complete is True
    assert calls == []


def test_replacement_barrier_still_completes_and_runs_when_not_terminal(qt_app) -> None:
    engine = _FakeEngine(terminal=False, state="RUNNING")
    assert qt_replacement_may_run(engine) is True

    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings",
        retiring_generation=7,
        purpose="replacement",
    )
    root = _Root()
    barrier.watch_python_owner(root, label="Root")

    calls: list[int] = []
    barrier.then(lambda: calls.append(1))
    barrier.seal()

    assert barrier.is_complete is False
    assert calls == []

    del root
    gc.collect()

    assert barrier.is_complete is True
    assert calls == [1]


def test_terminal_barrier_completion_is_reported_once_for_stacked_then(qt_app) -> None:
    engine = _FakeEngine(terminal=True, state="SHUTTING_DOWN")
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="application_exit",
        retiring_generation=7,
        purpose="terminal",
    )
    root = _Root()
    barrier.watch_python_owner(root, label="Root")
    barrier.seal()

    del root
    gc.collect()
    assert barrier.is_complete is True

    # A continuation registered AFTER completion runs immediately, exactly once.
    late: list[int] = []
    barrier.then(lambda: late.append(1))
    assert late == [1]


# ---------------------------------------------------------------------------------- every exiting stop is terminal


class _ManagerRoot(QObject):
    """The retiring generation's Quick roots, as the display manager publishes them (one QObject stands for them)."""

    def __init__(self) -> None:
        super().__init__()
        self._runtime_generation = 11
        self.window = QObject()

    def collect_runtime_retirement_roots(self):
        return [self.window], []

    def get_display_count(self) -> int:
        return 1

    def cleanup(self) -> None:
        pass


class _StoppingEngine:
    """``engine_lifecycle.stop``'s collaborators up to the terminal deferral (the function under test is the real one)."""

    def __init__(self, manager: _ManagerRoot) -> None:
        from engine.screensaver_engine import EngineState

        self._state = EngineState.RUNNING
        self._running = True
        self.display_manager = manager
        self.thread_manager = None
        self.resource_manager = None
        self._pending_runtime_destruction_barrier = None
        self._terminal_shutdown_requested = False
        self._rotation_timer = None
        self._runtime_generation = 11

    def _get_state(self):
        return self._state

    def _transition_state(self, target, expected_from=()):
        self._state = target
        return True

    def _advance_runtime_generation(self, _reason: str) -> None:
        self._runtime_generation += 1


@pytest.mark.parametrize("reason", [None, "cli_exit_after", "no_display_shown"])
def test_every_exiting_stop_waits_for_its_quick_roots_before_the_quit(reason, qt_app, qtbot, monkeypatch) -> None:
    # Keyed on the reason "application_exit" alone, an exiting stop for any other reason (--exit-after's
    # "cli_exit_after", a failed start's "no_display_shown") armed a replacement barrier, which cancels itself under
    # terminal shutdown: the quit ran while the Quick windows were still alive (on Vulkan, 0xC0000005 at exit).
    from shiboken6 import isValid

    from core.windows import reddit_helper_runtime
    from engine import engine_lifecycle

    finalized: list[bool] = []
    monkeypatch.setattr(engine_lifecycle, "_run_stop_finalization",
                        lambda engine, exit_app: finalized.append(exit_app))
    monkeypatch.setattr(reddit_helper_runtime, "clear_session_ticket", lambda **_kwargs: False)
    manager = _ManagerRoot()
    engine = _StoppingEngine(manager)
    window = manager.window
    try:
        engine_lifecycle.stop(engine, exit_app=True, reason=reason)
        barrier = engine._pending_runtime_destruction_barrier
        assert barrier is not None and barrier.is_complete is False
        assert finalized == []                       # no quit while the generation's Quick roots live
        window.deleteLater()
        qtbot.waitUntil(lambda: finalized == [True], timeout=2000)
    finally:
        for obj in (window, manager):
            if isValid(obj):
                obj.deleteLater()
        qt_app.processEvents()
