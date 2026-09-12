"""Regression bars for Qt-native display sleep/wake reconciliation.

The production contract is event-driven: display-manager topology authority must
observe Qt application/screen metric edges in addition to screen add/remove.
There is no recurring poller.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt

import engine.display_manager as display_module
from engine.display_manager import DisplayManager


class _Signal:
    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def connect(self, callback) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def disconnect(self, callback) -> None:
        if callback not in self._callbacks:
            raise TypeError("callback is not connected")
        self._callbacks.remove(callback)

    def emit(self, *args) -> None:
        for callback in tuple(self._callbacks):
            callback(*args)

    @property
    def callback_count(self) -> int:
        return len(self._callbacks)


class _Screen:
    def __init__(self, name: str, x: int, width: int = 1920, height: int = 1080) -> None:
        self._name = name
        self._geometry = QRect(x, 0, width, height)
        self._available = QRect(x, 0, width, height - 40)
        self.geometryChanged = _Signal()
        self.availableGeometryChanged = _Signal()
        self.virtualGeometryChanged = _Signal()
        self.logicalDotsPerInchChanged = _Signal()
        self.physicalDotsPerInchChanged = _Signal()

    def name(self) -> str:
        return self._name

    def manufacturer(self) -> str:
        return "Fixture"

    def model(self) -> str:
        return "Panel"

    def serialNumber(self) -> str:
        return self._name

    def geometry(self) -> QRect:
        return QRect(self._geometry)

    def availableGeometry(self) -> QRect:
        return QRect(self._available)

    def devicePixelRatio(self) -> float:
        return 1.0

    def set_geometry(self, rect: QRect) -> None:
        self._geometry = QRect(rect)
        self._available = QRect(rect.x(), rect.y(), rect.width(), rect.height() - 40)


class _App:
    def __init__(self, screens: list[_Screen]) -> None:
        self.screenAdded = _Signal()
        self.screenRemoved = _Signal()
        self.primaryScreenChanged = _Signal()
        self.applicationStateChanged = _Signal()
        self.screens = list(screens)
        self.primary = screens[0] if screens else None


class _FakeQGuiApplication:
    app: _App | None = None

    @classmethod
    def instance(cls):
        return cls.app

    @classmethod
    def screens(cls):
        return [] if cls.app is None else list(cls.app.screens)

    @classmethod
    def primaryScreen(cls):
        return None if cls.app is None else cls.app.primary


class _Scheduler:
    def __init__(self) -> None:
        self.calls: list[tuple[int, object]] = []

    def single_shot(self, delay_ms: int, callback) -> None:
        self.calls.append((int(delay_ms), callback))

    def run_next(self) -> None:
        _delay, callback = self.calls.pop(0)
        callback()


@dataclass
class _Window:
    revalidations: int = 0

    def revalidate_bound_screen_geometry(self) -> None:
        self.revalidations += 1


@dataclass
class _Runtime:
    window: _Window
    binding_loss: object | None = None


class _Unit:
    def __init__(self, screen_index: int = 0) -> None:
        self.is_retired = False
        self.screen_index = screen_index
        self.runtime = _Runtime(_Window())
        self.reanchors = 0

    def reanchor_for_current_bounds(self) -> None:
        self.reanchors += 1


def _manager(monkeypatch, screens: list[_Screen]):
    app = _App(screens)
    _FakeQGuiApplication.app = app
    monkeypatch.setattr(display_module, "QGuiApplication", _FakeQGuiApplication)
    scheduler = _Scheduler()
    manager = DisplayManager(thread_manager=scheduler)
    return manager, app, scheduler


def test_same_count_screen_metric_change_rebuilds_generation_authority(monkeypatch):
    """A surviving QScreen geometry change must not remain a window-local mutation."""

    screen = _Screen("DISPLAY1", 0, 2560, 1440)
    manager, _app, scheduler = _manager(monkeypatch, [screen])
    changes: list[int] = []
    manager.monitors_changed.connect(changes.append)

    screen.set_geometry(QRect(-1920, 0, 1920, 1080))
    screen.geometryChanged.emit(screen.geometry())
    # A same-burst work-area signal is coalesced onto the same existing one-shot.
    screen.availableGeometryChanged.emit(screen.availableGeometry())

    assert len(scheduler.calls) == 1
    assert manager._monitor_reconcile_pending is True

    scheduler.run_next()

    assert changes == [1]
    assert manager.screen_count == 1
    assert manager._screen_signature[0][-3] == (-1920, 0, 1920, 1080)
    manager.disconnect_monitor_detection()


def test_application_resume_with_same_signature_reapplies_bound_quick_geometry(monkeypatch):
    """Resume must repair a displaced native window even when topology ends identical."""

    screen = _Screen("DISPLAY1", 0, 2560, 1440)
    manager, app, scheduler = _manager(monkeypatch, [screen])
    unit = _Unit()
    monkeypatch.setattr(display_module, "QuickDisplayUnit", _Unit)
    manager.displays = [unit]
    changes: list[int] = []
    manager.monitors_changed.connect(changes.append)

    app.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    assert len(scheduler.calls) == 1
    scheduler.run_next()

    assert changes == []
    assert unit.runtime.window.revalidations == 1
    assert unit.reanchors == 1
    manager.disconnect_monitor_detection()


def test_inactive_application_state_does_not_schedule_reconcile(monkeypatch):
    """Only ApplicationActive is a resume/recovery edge."""

    screen = _Screen("DISPLAY1", 0, 2560, 1440)
    manager, app, scheduler = _manager(monkeypatch, [screen])

    app.applicationStateChanged.emit(Qt.ApplicationState.ApplicationInactive)

    assert scheduler.calls == []
    assert manager._monitor_reconcile_pending is False
    assert manager._monitor_resume_revalidation_pending is False
    manager.disconnect_monitor_detection()


def test_metric_edge_then_resume_edge_preserves_same_signature_revalidation(monkeypatch):
    """Coalescing must not discard resume intent when another edge scheduled first."""

    screen = _Screen("DISPLAY1", 0, 2560, 1440)
    manager, app, scheduler = _manager(monkeypatch, [screen])
    unit = _Unit()
    monkeypatch.setattr(display_module, "QuickDisplayUnit", _Unit)
    manager.displays = [unit]

    # A metric signal can arrive first during wake even when the final signature
    # settles back to exactly what the manager already owns. It schedules the
    # single coalesced pass. The later ApplicationActive edge must add its resume
    # revalidation intent without adding a second timer.
    screen.geometryChanged.emit(screen.geometry())
    app.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)

    assert len(scheduler.calls) == 1
    assert manager._monitor_reconcile_pending is True
    assert manager._monitor_resume_revalidation_pending is True

    scheduler.run_next()

    assert unit.runtime.window.revalidations == 1
    assert unit.reanchors == 1
    assert manager._monitor_resume_revalidation_pending is False
    manager.disconnect_monitor_detection()

def test_primary_screen_change_is_part_of_topology_signature(monkeypatch):
    left = _Screen("DISPLAY1", 0)
    right = _Screen("DISPLAY2", 1920)
    manager, app, scheduler = _manager(monkeypatch, [left, right])
    changes: list[int] = []
    manager.monitors_changed.connect(changes.append)

    assert manager._screen_signature[0][5] is True
    assert manager._screen_signature[1][5] is False

    app.primary = right
    app.primaryScreenChanged.emit(right)
    assert len(scheduler.calls) == 1
    scheduler.run_next()

    assert changes == [2]
    assert manager._screen_signature[0][5] is False
    assert manager._screen_signature[1][5] is True
    manager.disconnect_monitor_detection()


def test_monitor_detection_disconnect_fences_screen_and_resume_edges(monkeypatch):
    screen = _Screen("DISPLAY1", 0)
    manager, app, scheduler = _manager(monkeypatch, [screen])

    # Prove a queued reconcile cannot run after the manager has been detached.
    screen.geometryChanged.emit(screen.geometry())
    assert len(scheduler.calls) == 1
    manager.disconnect_monitor_detection()

    assert screen.geometryChanged.callback_count == 0
    assert screen.availableGeometryChanged.callback_count == 0
    assert app.applicationStateChanged.callback_count == 0
    assert app.primaryScreenChanged.callback_count == 0
    assert manager._monitor_resume_revalidation_pending is False

    scheduler.run_next()
    assert manager._monitor_reconcile_pending is False
    assert manager._monitor_resume_revalidation_pending is False

    # Later stale Qt edges are fully detached and cannot schedule more work.
    screen.geometryChanged.emit(screen.geometry())
    app.applicationStateChanged.emit(Qt.ApplicationState.ApplicationActive)
    assert scheduler.calls == []
