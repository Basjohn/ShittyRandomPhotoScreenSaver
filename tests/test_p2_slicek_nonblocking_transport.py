"""Slice K - transport commands must not block the GUI on WinRT completion.

`Current_Plan.md` Slice K.

`MediaWidget.play_pause()` calls the controller synchronously, and the Windows
GSMTC controller's `_invoke_simple_action` used `_run_coroutine`, which submits
the WinRT work to the IO pool and then blocks the caller on `done.wait()` until
completion. On the GUI thread that stalls the event loop across the Pause/Play
edge - the installed run's `dispatch_pending_skips` and the visible hitch.

These bars use a real background IO runner and a deliberately delayed backend
coroutine to prove the command owner is now fire-and-forget: it returns before
the backend completes, runs the backend exactly once, preserves dedup, and the
old blocking path still blocks (the negative control).
"""

from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

from core.media.media_controller import WindowsGlobalMediaController


class _ThreadedIOManager:
    """Runs submit_io_task on a real daemon thread, like the IO pool."""

    def __init__(self):
        self.submitted: list[str] = []

    def submit_io_task(self, func, *, task_id=None, priority=None, callback=None):
        self.submitted.append(task_id or "task")

        def _run():
            result = func()
            if callback is not None:
                callback(SimpleNamespace(result=result))

        threading.Thread(target=_run, daemon=True).start()
        return task_id or "task"


def _controller():
    return WindowsGlobalMediaController(thread_manager=_ThreadedIOManager())


class TestCommandIsFireAndForget:
    def test_submit_command_returns_before_the_backend_completes(self):
        ctrl = _controller()
        runs: list[int] = []
        backend_done = threading.Event()

        async def _slow():
            runs.append(1)
            await asyncio.sleep(0.3)
            backend_done.set()

        start = time.perf_counter()
        ctrl._submit_command("play_pause", lambda: _slow())
        elapsed = time.perf_counter() - start

        assert elapsed < 0.10, (
            f"the transport command blocked the caller for {elapsed*1000:.0f}ms"
        )
        # GUI/event-loop follow-up work would run here, before the backend.
        assert not backend_done.is_set(), "the backend completed synchronously"
        assert backend_done.wait(2.0), "the backend never completed off-thread"
        assert runs == [1], "the backend did not run exactly once"

    def test_provider_boolean_is_reported_after_submission_completes(self):
        ctrl = _controller()
        completed = threading.Event()
        results = []
        ctrl.set_command_result_handler(
            lambda result: (results.append(result), completed.set())
        )

        async def _rejected():
            return False

        assert ctrl._submit_command("seek", lambda: _rejected()) is True
        assert completed.wait(2.0), "the provider completion was not reported"
        assert len(results) == 1
        assert results[0].action == "seek"
        assert results[0].succeeded is False
        assert results[0].provider_result is False

    def test_the_blocking_run_coroutine_is_the_negative_control(self):
        """The old path `_invoke_simple_action` used must actually block."""
        ctrl = _controller()

        async def _slow():
            await asyncio.sleep(0.3)

        start = time.perf_counter()
        ctrl._run_coroutine(lambda: _slow())
        elapsed = time.perf_counter() - start

        assert elapsed >= 0.25, (
            "the blocking query path returned early; the control is invalid, so "
            "the non-blocking assertion above proves nothing"
        )

    def test_transport_actions_route_through_the_nonblocking_owner(self, monkeypatch):
        ctrl = _controller()
        ctrl._available = True
        ctrl._MediaManager = object()  # truthy so _invoke_simple_action proceeds

        calls: list[str] = []
        monkeypatch.setattr(
            ctrl,
            "_submit_command",
            lambda name, factory, **_kwargs: calls.append(name) or True,
        )

        ctrl.play_pause()
        ctrl.next()
        ctrl.previous()
        ctrl.seek_fraction(0.5)

        assert calls == ["play_pause", "next", "previous", "seek"], (
            "a transport action still uses the blocking controller path"
        )


class TestCommandDedup:
    def test_a_duplicate_while_inflight_is_dropped_then_a_later_one_runs(self):
        ctrl = _controller()
        runs: list[int] = []
        started = threading.Event()
        release = threading.Event()

        async def _held():
            runs.append(1)
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)

        ctrl._submit_command("play_pause", lambda: _held())
        assert started.wait(1.0), "the first command never started"

        # A duplicate arriving while one command is inflight must be dropped.
        ctrl._submit_command("play_pause", lambda: _held())
        time.sleep(0.1)
        assert runs == [1], "a duplicate command ran while one was inflight"

        # Let the first finish and the inflight guard clear.
        release.set()
        deadline = time.time() + 1.0
        while ctrl._command_inflight and time.time() < deadline:
            time.sleep(0.01)
        assert not ctrl._command_inflight, "the inflight guard never cleared"

        async def _quick():
            runs.append(1)

        ctrl._submit_command("play_pause", lambda: _quick())
        deadline = time.time() + 1.0
        while len(runs) < 2 and time.time() < deadline:
            time.sleep(0.01)
        assert len(runs) == 2, "a fresh command after completion was not accepted"

    def test_no_thread_manager_is_a_safe_noop(self):
        ctrl = WindowsGlobalMediaController(thread_manager=None)
        # Must not raise and must not mark a command inflight forever.
        ctrl._submit_command("play_pause", lambda: None)
        assert ctrl._command_inflight is False
