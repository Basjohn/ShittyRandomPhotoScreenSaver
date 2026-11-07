"""A startup whose every display fails to show is a failed start, not a windowless running engine.

``DisplayManager.initialize_displays`` shows the first selected display at once and staggers the rest onto later UI
turns, so ``_initialize_display`` reports success while those are pending. When the last pending show fails too and
none was shown, the manager emits ``no_display_shown`` once and the engine stops through its lifecycle owner
(``stop(exit_app=True, reason="no_display_shown")``), as a failed start. A partial failure stays a success.

The refusals come from the conftest display-window guard (``DisplayWindowBlocked``); no real window is shown. Each
test clears the guard's record before asserting, so it reports its own result. Needs two monitors.
"""
from __future__ import annotations

import sys
import uuid

import pytest


def _display_guard() -> dict:
    return next(module._DISPLAY_GUARD for module in list(sys.modules.values())
                if isinstance(getattr(module, "_DISPLAY_GUARD", None), dict))


@pytest.fixture
def two_monitor_engine(qt_app, tmp_path, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QColor, QGuiApplication, QImage

    from core.settings.settings_manager import SettingsManager
    from engine.screensaver_engine import ScreensaverEngine

    if _display_guard()["allowed"]:
        pytest.skip("--display-disruptive: the guard is off, so a real window would show")
    if len(QGuiApplication.screens()) < 2:
        pytest.skip("needs two monitors: the second display's show is the staggered one")
    settings = SettingsManager(organization="SRPSSFocusedTests", application=f"NoDisplayShown_{uuid.uuid4().hex}",
                               storage_base_dir=tmp_path / "profile")
    settings.set("display.show_on_monitors", [1, 2])
    folder = tmp_path / "images"
    folder.mkdir()
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("#204060"))
    assert image.save(str(folder / "one.jpg"))
    settings.set("sources.folders", [str(folder)])
    settings.save()
    engine = ScreensaverEngine()
    engine.settings_manager = settings

    stops: list[str | None] = []
    original_stop = engine.stop

    def recording_stop(exit_app: bool = True, *, reason: str | None = None) -> None:
        stops.append(reason if exit_app else f"no-exit:{reason}")
        original_stop(exit_app, reason=reason)

    monkeypatch.setattr(engine, "stop", recording_stop)
    quits: list[str] = []
    monkeypatch.setattr("engine.runtime_destruction.request_application_quit",
                        lambda reason: quits.append(reason) or True)
    try:
        yield engine, stops, quits
    finally:
        if engine._running:
            engine.stop(exit_app=False)
        engine.cleanup()
        for _ in range(4):
            QCoreApplication.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _take_guard_record() -> str | None:
    guard = _display_guard()
    blocked = guard.get("blocked")
    guard["blocked"] = None                                        # report this test's own result
    return blocked


def _wait_until(qtbot, condition) -> None:
    try:
        qtbot.waitUntil(condition, timeout=5000)
    except qtbot.TimeoutError:
        pass                                   # the assertions below say what did not happen


def test_every_display_refused_ends_as_a_failed_start(two_monitor_engine, qtbot) -> None:
    engine, stops, quits = two_monitor_engine
    try:
        # Screen 1 is refused inside initialization; screen 2's staggered show is still pending: a success so far.
        initialized = engine.initialize()
        started = engine.start()
        stops_after_init = list(stops)
        # The staggered show is refused as well: nothing is on screen.
        _wait_until(qtbot, lambda: stops != [])
    finally:
        reached = _take_guard_record()
    assert reached, "precondition: the shows reached the display-window guard"
    assert initialized is True and started is True and stops_after_init == []
    # The start fails through the lifecycle owner, exactly once.
    assert stops == ["no_display_shown"]
    assert quits == ["engine_stop"]
    assert engine.display_manager is None
    assert engine._display_initialized is False


def test_one_display_shown_keeps_the_engine_initialized(two_monitor_engine, qtbot, monkeypatch) -> None:
    from rendering.quick.display_unit import QuickDisplayUnit

    engine, stops, quits = two_monitor_engine
    original_show = QuickDisplayUnit.show_on_screen
    shown: list[int] = []

    def show_second_without_a_window(self) -> None:
        if int(self.screen_index) == 1:
            shown.append(1)                    # counts as shown; no real window is created
            return
        original_show(self)                    # screen 0 reaches the guard and is refused

    monkeypatch.setattr(QuickDisplayUnit, "show_on_screen", show_second_without_a_window)
    try:
        initialized = engine.initialize()
        started = engine.start()
        _wait_until(qtbot, lambda: shown == [1])
        qtbot.wait(200)                        # let any failure edge after the staggered show be delivered
    finally:
        reached = _take_guard_record()
    assert reached, "precondition: screen 0's show reached the display-window guard"
    assert initialized is True and started is True and shown == [1]
    assert stops == [] and quits == []
    assert engine._display_initialized is True
    assert [int(display.screen_index) for display in engine.display_manager.displays] == [1]
