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
