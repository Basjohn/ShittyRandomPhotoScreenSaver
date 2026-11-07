"""No non-daemon thread outlives a test that reaches the display-window guard (the ``test_s_hotkey_workflow.py`` hang).

``test_display_initialized_flag_lifecycle`` builds a real display runtime and reaches the display window's show,
which ``tests/conftest.py`` refuses (no real window on the operator's monitors). The refusal used to be a
``pytest.skip``: a BaseException, so it escaped production's ``except Exception`` show-failure path, the started
Visualizer's non-daemon logical runtime (``srpss-visualizer-logical``) was never retired, and the pytest process never
exited (900 s gate timeout). The refusal is now an ordinary error inside production, which retires what it started;
the test is still reported as skipped.

This test reaches the guard on purpose (no window is shown), then clears the guard's record so it reports its own
result.
"""
from __future__ import annotations

import sys
import threading
import uuid

import pytest


def _non_daemon_threads() -> set:
    return {t for t in threading.enumerate() if not t.daemon and t is not threading.main_thread() and t.is_alive()}


def _display_guard() -> dict:
    return next(module._DISPLAY_GUARD for module in list(sys.modules.values())
                if isinstance(getattr(module, "_DISPLAY_GUARD", None), dict))


def test_reaching_the_display_window_guard_leaves_no_non_daemon_thread(qt_app, tmp_path):
    from PySide6.QtCore import QCoreApplication, QEvent
    from core.settings.settings_manager import SettingsManager
    from engine.screensaver_engine import ScreensaverEngine
    guard = _display_guard()
    if guard["allowed"]:
        pytest.skip("--display-disruptive: the guard is off, so a real window would show")
    before = _non_daemon_threads()
    settings = SettingsManager(organization="SRPSSFocusedTests", application=f"GuardThreads_{uuid.uuid4().hex}",
                               storage_base_dir=tmp_path / "profile")
    engine = ScreensaverEngine()
    engine.settings_manager = settings
    left = []
    try:
        try:
            initialized = engine._initialize_display()
        except BaseException as exc:                                   # noqa: BLE001 - the defect's own shape
            escaped = f"{type(exc).__name__}: {exc}"
        else:
            escaped = ""
        # Measured before cleanup: the runtime that reached the guard must already be retired.
        left = sorted(t.name for t in _non_daemon_threads() - before)
    finally:
        engine.cleanup()
        for _ in range(4):
            QCoreApplication.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        reached = guard.get("blocked") or "would show a real display window" in escaped
        guard["blocked"] = None                                        # report this test's own result
    assert reached, "precondition: display initialization reached the display-window guard"
    assert escaped == "", f"the guard's refusal escaped production's show-failure path: {escaped[:90]}"
    assert initialized is False
    assert left == [], f"non-daemon threads left running by the refused show: {left}"
