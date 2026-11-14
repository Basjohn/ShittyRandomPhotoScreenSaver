"""``release_quick_windows_then`` is bounded (Current_Plan.md item 8b, N2.7 leftovers).

A failing route's exit waits for its Quick windows' ``destroyed`` (R-209). A deletion posted at one loop level waits
for that level: a modal loop entered after the release (a popup's or a dialog's ``exec()``) holds every ``destroyed``
until it ends, which on an unattended screensaver may be never. The exit then runs anyway after
``_RELEASE_BOUND_MS``, logged critical; the timer is admitted there only, because the process is ending on a failure.

In process, with never-shown ``QWindow`` objects standing in for the display windows (the selection of live windows is
the one patched seam). The negative controls show each stuck case really blocks without the bound.
"""
from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QEventLoop, QObject, QTimer
from PySide6.QtGui import QWindow

import engine.runtime_destruction as destruction

BOUND_MS = 150


class _NeverDestroyed(QObject):
    """A window whose destruction never comes: its deletion request is lost."""

    def queue_close(self) -> None:
        return None

    def deleteLater(self) -> None:  # noqa: N802 - Qt name
        return None


def _windows(monkeypatch, windows: list) -> None:
    monkeypatch.setattr(destruction, "_live_quick_display_windows", lambda: list(windows))


def _run_loop_for(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


@pytest.mark.qt
def test_a_window_whose_destruction_never_comes_still_exits_after_the_bound(qt_app, monkeypatch, caplog):
    monkeypatch.setattr(destruction, "_RELEASE_BOUND_MS", BOUND_MS)
    stuck = _NeverDestroyed()
    _windows(monkeypatch, [stuck])
    ran: list[str] = []
    caplog.set_level(logging.INFO, logger=destruction.logger.name)
    assert destruction.release_quick_windows_then("probe", lambda: ran.append("exit")) == 1
    assert ran == []                                       # it waits for the window first
    _run_loop_for(BOUND_MS * 4)
    assert ran == ["exit"]
    assert any(record.levelno == logging.CRITICAL and "exiting anyway" in record.getMessage()
               for record in caplog.records)
    _run_loop_for(BOUND_MS * 2)
    assert ran == ["exit"]                                 # once only


@pytest.mark.qt
def test_without_the_bound_a_window_whose_destruction_never_comes_blocks_the_exit_negative_control(
        qt_app, monkeypatch):
    monkeypatch.setattr(destruction, "_RELEASE_BOUND_MS", 60_000)
    stuck = _NeverDestroyed()
    _windows(monkeypatch, [stuck])
    ran: list[str] = []
    destruction.release_quick_windows_then("probe", lambda: ran.append("exit"))
    _run_loop_for(BOUND_MS * 4)
    assert ran == []


@pytest.mark.qt
def test_destroyed_windows_exit_at_once_and_the_bound_never_fires_after(qt_app, monkeypatch, caplog):
    monkeypatch.setattr(destruction, "_RELEASE_BOUND_MS", BOUND_MS)
    windows = [QWindow(), QWindow()]                       # never shown
    _windows(monkeypatch, windows)
    ran: list[str] = []
    caplog.set_level(logging.INFO, logger=destruction.logger.name)
    destruction.release_quick_windows_then("probe", lambda: ran.append("exit"))
    del windows[:]
    _run_loop_for(BOUND_MS // 3)
    assert ran == ["exit"]
    _run_loop_for(BOUND_MS * 3)
    assert ran == ["exit"]
    assert not any(record.levelno == logging.CRITICAL for record in caplog.records)


def _release_then_modal(monkeypatch, *, modal_ms: int) -> dict:
    """At the main loop's level: release one window, then enter a modal loop that runs ``modal_ms`` unless the exit
    (here: ending that modal loop, as ``QCoreApplication.exit`` leaves every loop) comes first."""
    window = QWindow()                                     # never shown
    _windows(monkeypatch, [window])
    seen: dict = {"events": []}
    outer = QEventLoop()

    def at_main_level() -> None:
        window.destroyed.connect(lambda *_a: seen["events"].append("destroyed"))
        modal = QEventLoop()
        destruction.release_quick_windows_then("probe", lambda: (seen["events"].append("exit"), modal.quit()))
        QTimer.singleShot(modal_ms, modal.quit)
        modal.exec()
        seen["events"].append("modal ended")
        QTimer.singleShot(BOUND_MS, outer.quit)

    QTimer.singleShot(0, at_main_level)
    outer.exec()
    return seen


@pytest.mark.qt
def test_a_modal_loop_entered_after_the_release_holds_the_deletion_and_the_bound_ends_it(qt_app, monkeypatch):
    monkeypatch.setattr(destruction, "_RELEASE_BOUND_MS", BOUND_MS)
    seen = _release_then_modal(monkeypatch, modal_ms=BOUND_MS * 20)
    # The deletion waited for the modal loop; the bound ran the exit inside it; the window went after it ended.
    assert seen["events"] == ["exit", "modal ended", "destroyed"]


@pytest.mark.qt
def test_without_the_bound_the_modal_loop_holds_the_exit_until_it_ends_negative_control(qt_app, monkeypatch):
    monkeypatch.setattr(destruction, "_RELEASE_BOUND_MS", 60_000)
    seen = _release_then_modal(monkeypatch, modal_ms=BOUND_MS * 3)
    # Nothing ran while the modal loop lasted: the window's destruction, and so the exit, came only after it.
    assert seen["events"] == ["modal ended", "destroyed", "exit"]
