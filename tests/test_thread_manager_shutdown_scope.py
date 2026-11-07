"""Only the terminal ThreadManager cancels every pending ``single_shot`` (checklist AC-13).

``ThreadManager.single_shot`` callbacks are process-wide (owned by their runtime generation, not by any manager).
A Settings/CONFIG helper manager's shutdown used to call ``cancel_all_scheduled_single_shots()`` and so cancelled
unrelated owners' delayed callbacks. Now only the runtime engine's manager (``terminal_owner=True``) does.
"""
from __future__ import annotations

import time

from core.threading.manager import ThreadManager


def _pending(fired: list):
    return ThreadManager.single_shot(60_000, lambda: fired.append(1))


def test_a_helper_managers_shutdown_leaves_another_owners_single_shot_pending(qt_app):
    fired = []
    handle = _pending(fired)
    try:
        helper = ThreadManager.create_helper_manager()
        helper.shutdown(wait=True)
        assert handle.active and not handle.cancelled, "a helper manager's shutdown cancelled another owner's single_shot"
        # And it still fires.
        quick = ThreadManager.single_shot(1, lambda: fired.append(2))
        deadline = time.monotonic() + 5.0
        while not quick.fired and time.monotonic() < deadline:
            qt_app.processEvents()
            time.sleep(0.005)
        assert 2 in fired
    finally:
        handle.cancel()


def test_the_terminal_managers_shutdown_still_cancels_every_single_shot_negative_control(qt_app):
    fired = []
    handle = _pending(fired)
    terminal = ThreadManager(config=None, terminal_owner=True) if _accepts_terminal_owner() else ThreadManager()
    terminal.shutdown(wait=True)
    assert handle.cancelled and fired == []


def _accepts_terminal_owner() -> bool:
    import inspect
    return "terminal_owner" in inspect.signature(ThreadManager.__init__).parameters
