"""Foundry windows: the native backdrop is applied when the window is shown, never queued at construction.

A ``QTimer.singleShot(0, lambda: ...)`` queued in ``__init__`` closed over the window and reached it after
construction whether or not it was ever shown (or already closed); the native backdrop needs the window's native
handle, which exists once it is shown. The Defaults Foundry moved it to ``showEvent`` first.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests._invisible_windows import keep_off_screen  # real but never on screen
from tests.test_foundry_widget_ownership import _git_repo

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _join_worker(window) -> None:
    thread = getattr(window, "_task_thread", None)
    if thread is not None:
        thread.join(timeout=60)
        assert not thread.is_alive()


def _theme_foundry(monkeypatch, calls, _tmp_path):
    from tools import theme_foundry

    monkeypatch.setattr(theme_foundry, "apply_native_backdrop", lambda window, _r: calls.append(window) or True)
    return theme_foundry.ThemeFoundryWindow(REPO_ROOT)


def _widget_theme_foundry(monkeypatch, calls, _tmp_path):
    from tools import widget_theme_foundry

    monkeypatch.setattr(widget_theme_foundry, "apply_native_backdrop",
                        lambda window, _r: calls.append(window) or True)
    return widget_theme_foundry.WidgetThemeFoundryWindow(REPO_ROOT, None)


def _godzip_foundry(monkeypatch, calls, tmp_path):
    from tools import godzip_foundry

    monkeypatch.setattr(godzip_foundry.GodzipFoundryWindow, "_apply_native_backdrop_theme",
                        lambda window: calls.append(window) or True)
    return godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path))


def _godzip_workers() -> list:
    import threading

    return [thread for thread in threading.enumerate()
            if thread.name == "godzip-foundry-worker" and thread.is_alive()]


def test_godzip_close_ends_a_read_only_worker(qt_app, monkeypatch, tmp_path):
    """Closing the GODZIP Foundry during its startup repository scan closes it and ends the scan's worker.

    The close fence (no close while a task runs) is for mutations; it also refused a close during the read-only
    startup scan, so the window stayed open and its worker alive. A read-only task's result is dropped at close and
    its worker joined (bounded)."""
    import time

    from tools import godzip_foundry

    def slow_scan(_root):
        time.sleep(0.3)        # still running when the window closes
        return []

    monkeypatch.setattr(godzip_foundry, "collect_repo_files", slow_scan)
    window = godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path))
    try:
        assert window._task_active and _godzip_workers(), "the startup scan is running"
        assert window.close() is True
        assert _godzip_workers() == []
        qt_app.processEvents()
        assert not window.create_tab._loaded, "a closed window received the dropped scan's result"
    finally:
        _join_worker(window)
        window.deleteLater()
        qt_app.processEvents()


def test_godzip_close_still_waits_for_a_mutation(qt_app, monkeypatch, tmp_path):
    """Control: a mutation's worker is never abandoned; the close is refused until it reports."""
    import threading

    from tools import godzip_foundry

    monkeypatch.setattr(godzip_foundry, "collect_repo_files", lambda _root: [])
    window = godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path))
    release = threading.Event()
    try:
        _join_worker(window)
        qt_app.processEvents()
        assert window.run_task("Mutating…", lambda: release.wait(60))
        assert window.close() is False
        assert _godzip_workers()
    finally:
        release.set()
        _join_worker(window)
        qt_app.processEvents()
        assert window.close() is True
        window.deleteLater()
        qt_app.processEvents()


def test_godzip_opening_archive_is_loaded_by_the_window_and_never_after_it_is_gone(qt_app, monkeypatch, tmp_path):
    """``--open``'s archive loads once the event loop runs, through the window: a call queued at construction that
    closed over the window (audit 13 Nov, low 5) still reached it after it had been deleted."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from tools import godzip_foundry

    loads: list[Path] = []
    monkeypatch.setattr(godzip_foundry.ApplyTab, "load_zip", lambda _tab, path, **_k: loads.append(path))
    archive = tmp_path / "opened.zip"

    window = godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path), archive)
    try:
        assert loads == [], "loaded during construction"
        qt_app.processEvents()
        assert loads == [archive]
    finally:
        _join_worker(window)
        window.deleteLater()
        qt_app.processEvents()

    loads.clear()
    (tmp_path / "second").mkdir()
    window = godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path / "second"), archive)
    _join_worker(window)
    window.deleteLater()
    QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)   # gone before the loop runs
    import shiboken6

    assert not shiboken6.isValid(window)
    qt_app.processEvents()
    assert loads == [], "the queued load reached a deleted window"


@pytest.mark.parametrize("build", [_theme_foundry, _widget_theme_foundry, _godzip_foundry],
                         ids=["theme", "widget_theme", "godzip"])
def test_foundry_applies_its_native_backdrop_when_shown_not_when_built(qt_app, monkeypatch, tmp_path, build):
    calls: list[object] = []
    window = build(monkeypatch, calls, tmp_path)
    try:
        _join_worker(window)
        qt_app.processEvents()
        assert calls == [], "a backdrop was queued at construction"
        keep_off_screen(window)
        window.show()
        qt_app.processEvents()
        assert calls == [window]
    finally:
        _join_worker(window)
        qt_app.processEvents()
        window.close()
        window.deleteLater()
        qt_app.processEvents()
