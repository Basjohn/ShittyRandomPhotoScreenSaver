"""AC-03: the application-service tier above display generations.

A service registered on the engine survives a full Settings round trip (the strict display teardown, its destruction
barrier, the modal dialog and the dialog's own barrier), is reachable only through leases of live generations, and is
retired exactly once by terminal shutdown. Standard SRPSS declares no service and creates nothing.

The display generation here is a QObject stand-in for ``DisplayManager`` built through the engine's real
``_initialize_display``; the Settings dialog is the real ``SettingsDialog`` with its ``exec`` patched (never shown).
"""
from __future__ import annotations

import uuid
import weakref
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Signal

from core.settings import SettingsManager
from engine.screensaver_engine import EngineState, ScreensaverEngine

STUB = "stub.player"


class _StubService:
    """An application service: the instance must outlive every generation that leases it."""

    def __init__(self, events: list) -> None:
        self._events = events
        self.retire_calls = 0

    def retire(self) -> None:
        self.retire_calls += 1
        self._events.append("service_retire")


class _GenerationConsumer:
    """A display-generation object holding its generation's lease (watched by the destruction barrier)."""

    def __init__(self, lease) -> None:
        self.lease = lease


def _fake_display_manager_class(engine: ScreensaverEngine, events: list, leases: list, consumers: list):
    class _FakeDisplayManager(QObject):
        exit_requested = Signal()
        monitors_changed = Signal(int)
        displays_ready = Signal(int)
        no_display_shown = Signal(int)
        authoritative_first_frames_ready = Signal(int)
        startup_reveal_completed = Signal(int)
        transition_completed = Signal(int)
        transition_batch_idle = Signal()
        previous_requested = Signal()
        next_requested = Signal()
        save_image_requested = Signal(int)
        ban_image_requested = Signal(int)
        clear_image_bans_requested = Signal()
        cycle_transition_requested = Signal()
        settings_requested = Signal()
        settings_target_requested = Signal(str)
        custom_layout_reload_requested = Signal(str, int, object)
        jedi_mode_requested = Signal(str, str)

        def __init__(self, *, runtime_generation, **_kwargs):
            super().__init__()
            self._runtime_generation = runtime_generation
            lease = engine.application_services.lease(STUB, generation=runtime_generation)
            leases.append(lease)   # the test keeps it, as a late callback closure would
            consumer = _GenerationConsumer(lease)
            consumers.append(weakref.ref(consumer))
            self._consumer = consumer

        def set_random_transition_selection(self, _selection) -> None:
            return None

        def initialize_displays(self) -> int:
            return 1

        def get_display_count(self) -> int:
            return 1

        def collect_runtime_retirement_roots(self):
            return [self], [self._consumer]

        def cleanup(self) -> None:
            events.append(("display_cleanup", self._runtime_generation))

        def retire_runtime(self) -> None:
            self._consumer = None
            self.deleteLater()

    return _FakeDisplayManager


def _drain_until(qtbot, predicate, timeout: int = 15000) -> None:
    def _check() -> None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert predicate()

    qtbot.waitUntil(_check, timeout=timeout)


@pytest.mark.qt
def test_settings_round_trip_keeps_the_service_and_fences_the_retired_generation(
    monkeypatch, qt_app, qtbot, tmp_path,
):
    from engine import engine_handlers, runtime_destruction
    from ui.settings_dialog import SettingsDialog
    from ui.styled_popup import StyledPopup

    events: list = []
    leases: list = []
    consumers: list = []
    dialog_leases: list = []
    barriers: list = []
    built: list = []

    class _TrackingBarrier(runtime_destruction.RuntimeDestructionBarrier):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.watched: list[str] = []
            barriers.append(self)

        def watch_qobject(self, obj, *, label=None):
            self.watched.append(label or type(obj).__name__)
            super().watch_qobject(obj, label=label)

        def watch_python_owner(self, owner, *, label=None):
            self.watched.append(label or type(owner).__name__)
            super().watch_python_owner(owner, label=label)

    engine = ScreensaverEngine()
    engine.settings_manager = SettingsManager(
        organization="Test", application=f"AppServices_{uuid.uuid4().hex}", storage_base_dir=tmp_path,
    )

    def _start(*, show_first_image=True):
        engine._transition_state(EngineState.RUNNING)
        return True

    def _settings_exec(dialog):
        # The dialog generation leases the same instance through its own lease.
        lease = engine.application_services.lease(STUB, generation=dialog._runtime_generation)
        dialog_leases.append(lease)
        events.append(("dialog_exec", lease is not None and lease.service is built[0]))
        return 0

    monkeypatch.setattr(
        "engine.screensaver_engine.DisplayManager",
        _fake_display_manager_class(engine, events, leases, consumers),
    )
    monkeypatch.setattr(engine, "_initialize_image_sources", lambda: True)
    monkeypatch.setattr(engine, "_start_rss_background_refresh_if_needed", lambda: None)
    monkeypatch.setattr(engine, "_setup_rotation_timer", lambda: None)
    monkeypatch.setattr(engine, "_arm_replacement_watchdog", lambda label=None: None)
    monkeypatch.setattr(engine, "start", _start)
    monkeypatch.setattr(runtime_destruction, "RuntimeDestructionBarrier", _TrackingBarrier)
    monkeypatch.setattr(engine_handlers, "log_lifecycle_resource_snapshot", lambda *_a, **_k: None)
    monkeypatch.setattr(engine_handlers, "suppress_runtime_pointer_input", lambda *_a, **_k: None)
    monkeypatch.setattr(SettingsDialog, "exec", _settings_exec)
    monkeypatch.setattr(StyledPopup, "exec", lambda popup: 0)

    engine._initialize_application_services()
    engine.application_services.register(STUB, lambda: built.append(_StubService(events)) or built[-1])
    assert engine._initialize_display()
    engine._transition_state(EngineState.RUNNING)
    service = engine.application_services.get(STUB)
    assert service is not None and built == [service]
    old_generation = leases[0].generation

    engine_handlers.on_settings_requested(engine)
    _drain_until(
        qtbot,
        lambda: len(leases) == 2 and engine._get_state() is EngineState.RUNNING
        and not engine._settings_dialog_active,
    )

    # The service instance is identical before and after: Settings never retired or rebuilt it.
    assert engine.application_services.get(STUB) is service
    assert built == [service] and service.retire_calls == 0
    assert ("dialog_exec", True) in events

    # Both barriers (the retiring display generation, the Settings dialog) completed with an empty watch list,
    # and neither ever watched the service: no display-generation object survives, the service is not one.
    assert len(barriers) == 2
    display_barrier, dialog_barrier = barriers
    assert {"_FakeDisplayManager", "_GenerationConsumer"} <= set(display_barrier.watched)
    assert "SettingsDialog" in dialog_barrier.watched
    for barrier in barriers:
        state = barrier.describe()
        assert barrier.is_complete
        assert state["qobjects_pending"] == 0 and state["python_owners_pending"] == 0
        assert "_StubService" not in barrier.watched
    assert consumers[0]() is None

    # A stale generation's lease cannot reach the service, and the retired generations cannot lease again.
    stale_lease, live_lease = leases
    assert live_lease.generation != old_generation
    assert live_lease.service is service
    assert stale_lease.service is None and not stale_lease.is_live
    assert dialog_leases[0].service is None
    assert engine.application_services.lease(STUB, generation=old_generation) is None
    assert engine.application_services.lease(STUB, generation=dialog_leases[0].generation) is None

    # Terminal cleanup retires the service exactly once: after the display teardown, before the ThreadManager.
    terminal_quits: list = []
    engine.thread_manager = SimpleNamespace(
        shutdown=lambda *_a, **_k: events.append("thread_manager_shutdown") or True,
    )
    monkeypatch.setattr(
        "core.network.bounded_dns.close_network_admission", lambda: events.append("network_fence"),
    )
    monkeypatch.setattr(runtime_destruction, "request_application_quit", lambda reason: terminal_quits.append(reason))
    engine.cleanup()
    _drain_until(qtbot, lambda: bool(terminal_quits))
    engine.cleanup()

    assert service.retire_calls == 1
    assert events.count("service_retire") == 1
    assert engine.application_services.get(STUB) is None
    assert live_lease.service is None
    assert events.index(("display_cleanup", live_lease.generation)) < events.index("service_retire")
    assert events.index("service_retire") < events.index("thread_manager_shutdown")


def test_standard_profile_start_registers_and_creates_no_service(monkeypatch):
    from core import application_services
    from core.application_services import ApplicationServiceDescriptor

    def _must_not_build():
        raise AssertionError("an unavailable application service was built")

    monkeypatch.setattr(
        application_services,
        "APPLICATION_SERVICE_CATALOG",
        (ApplicationServiceDescriptor(name="smp.library", available=lambda: False, factory=_must_not_build),),
    )
    monkeypatch.setattr("core.settings.display_selection.resolve_monitor_numbers", lambda _settings: ())
    engine = ScreensaverEngine()
    for name, result in (
        ("_initialize_core_systems", True),
        ("_initialize_display_power", None),
        ("_load_settings", True),
        ("_initialize_display", True),
        ("_start_workers", None),
        ("_setup_rotation_timer", None),
        ("_subscribe_to_events", None),
        ("_start_rss_background_refresh_if_needed", None),
    ):
        monkeypatch.setattr(engine, name, lambda result=result: result)

    assert engine.initialize()

    services = engine.application_services
    assert services is not None
    assert services.registered_names() == ()
    assert services.describe()["live"] == ()
    engine.cleanup()
    assert services.is_retired


def test_a_declared_service_is_created_only_by_a_lease_while_its_capability_is_active():
    from core.application_services import ApplicationServiceDescriptor, ApplicationServices

    events: list = []
    active = {"on": False}
    built: list = []
    services = ApplicationServices()
    services.register_catalog((
        ApplicationServiceDescriptor(
            name=STUB,
            available=lambda: True,
            factory=lambda: built.append(_StubService(events)) or built[-1],
            capability=lambda: active["on"],
        ),
    ))
    services.admit_generation(3)

    assert services.registered_names() == (STUB,)
    assert services.lease(STUB, generation=3) is None
    assert built == [] and services.get(STUB) is None

    active["on"] = True
    first = services.lease(STUB, generation=3)
    second = services.lease(STUB, generation=3)
    assert built == [first.service] and second.service is first.service
    assert services.lease(STUB, generation=4) is None   # never admitted


def test_terminal_stop_retires_services_after_the_network_fence_and_before_the_pool(monkeypatch):
    import engine.runtime_destruction as runtime_destruction

    events: list = []
    engine = ScreensaverEngine()
    engine._state = EngineState.RUNNING
    engine.thread_manager = SimpleNamespace(
        shutdown=lambda *_a, **_k: events.append("thread_manager_shutdown") or True,
    )
    engine._initialize_application_services()
    engine.application_services.register(STUB, lambda: _StubService(events))
    engine.application_services.admit_generation(0)
    service = engine.application_services.lease(STUB, generation=0).service
    monkeypatch.setattr(
        "core.network.bounded_dns.close_network_admission", lambda: events.append("network_fence"),
    )
    monkeypatch.setattr(runtime_destruction, "request_application_quit", lambda reason: events.append("quit"))

    engine.stop(exit_app=True)
    engine.cleanup()

    assert service.retire_calls == 1
    assert events.index("network_fence") < events.index("service_retire") < events.index("thread_manager_shutdown")


def test_settings_teardown_failure_retires_live_services_before_the_process_exits(monkeypatch):
    from core.application_services import ApplicationServices
    from engine import engine_handlers

    events: list = []
    services = ApplicationServices()
    services.register(STUB, lambda: _StubService(events))
    services.admit_generation(5)
    service = services.lease(STUB, generation=5).service
    engine = SimpleNamespace(
        display_manager=SimpleNamespace(displays=[]),
        application_services=services,
        _settings_dialog_active=False,
        stop=lambda exit_app=False, reason=None: (_ for _ in ()).throw(RuntimeError("GL deletion failed")),
    )
    monkeypatch.setattr(
        engine_handlers.QCoreApplication, "exit", staticmethod(lambda code: events.append(("exit", int(code)))),
    )

    engine_handlers.on_settings_requested(engine)

    assert events == ["service_retire", ("exit", 1)]
    assert service.retire_calls == 1 and services.is_retired
