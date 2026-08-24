from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from PySide6.QtWidgets import QWidget

from core.threading.manager import ThreadManager
from widgets.system_mute_runtime import (
    SystemMuteRuntimeService,
    reset_shared_system_mute_runtime_for_tests,
    shared_system_mute_owner_count,
)


def test_registry_import_is_system_mute_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import sys
import rendering.widget_runtime_services  # noqa: F401

forbidden = {
    "widgets.system_mute_runtime",
    "widgets.mute_button_widget",
    "core.media.system_mute",
}
print(json.dumps(sorted(forbidden & set(sys.modules))))
"""
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


class _Backend:
    def __init__(self) -> None:
        self.available = True
        self.muted = False
        self.volume = 0.5
        self.read_calls = 0
        self.toggle_calls = 0
        self.step_calls: list[float] = []

    def is_available(self) -> bool:
        return self.available

    def get_mute(self) -> bool:
        self.read_calls += 1
        return self.muted

    def toggle_mute(self) -> bool:
        self.toggle_calls += 1
        self.muted = not self.muted
        return self.muted

    def step_volume(self, delta: float) -> float:
        self.step_calls.append(float(delta))
        self.volume = max(0.0, min(1.0, self.volume + float(delta)))
        return self.volume


class _BackendFactory:
    def __init__(self) -> None:
        self.backends: list[_Backend] = []

    def __call__(self) -> _Backend:
        backend = _Backend()
        self.backends.append(backend)
        return backend


class _Consumer:
    def __init__(self, thread_manager: object, generation: int = 81) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []

    def is_system_mute_consumer_alive(self) -> bool:
        return self.alive

    def on_system_mute_runtime_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)


def _lease(
    consumer: _Consumer,
    factory: _BackendFactory,
    *,
    shared: bool = True,
) -> SystemMuteRuntimeService:
    service = SystemMuteRuntimeService(shared=shared, backend_factory=factory)
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


@pytest.fixture(autouse=True)
def _isolated_shared_mute_owner():
    reset_shared_system_mute_runtime_for_tests()
    yield
    reset_shared_system_mute_runtime_for_tests()


def test_two_display_leases_share_one_backend_and_one_poll_chain(monkeypatch) -> None:
    manager = object()
    factory = _BackendFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback))),
    )

    assert first.start() is True
    assert second.start() is True
    assert shared_system_mute_owner_count() == 1
    assert len(factory.backends) == 1
    assert [delay for delay, _callback in scheduled] == [30_000]

    factory.backends[0].muted = True
    scheduled.pop(0)[1]()

    assert factory.backends[0].read_calls == 1
    assert first_consumer.snapshots[-1].muted is True
    assert second_consumer.snapshots[-1].muted is True
    assert [delay for delay, _callback in scheduled] == [30_000]


def test_first_display_retirement_preserves_owner_until_final_lease(monkeypatch) -> None:
    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    manager = object()
    factory = _BackendFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    assert first.start() is True
    assert second.start() is True
    owner = first.shared_owner

    first.retire()

    assert owner is not None and owner.is_retired() is False
    assert owner.active_consumer_count() == 1
    assert shared_system_mute_owner_count() == 1

    second.retire()

    assert owner.is_retired() is True
    assert shared_system_mute_owner_count() == 0


def test_queued_poll_cannot_cross_final_stop_and_restart(monkeypatch) -> None:
    manager = object()
    factory = _BackendFactory()
    consumer = _Consumer(manager)
    service = _lease(consumer, factory)
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: scheduled.append(callback)),
    )
    assert service.start() is True
    old_poll = scheduled[0]

    service.stop()
    assert service.start() is True
    assert len(scheduled) == 2

    old_poll()
    assert factory.backends[0].read_calls == 0
    assert len(scheduled) == 2

    scheduled[1]()
    assert factory.backends[0].read_calls == 1
    assert len(scheduled) == 3


def test_retired_generation_poll_cannot_mutate_replacement_owner(monkeypatch) -> None:
    manager = object()
    factory = _BackendFactory()
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: scheduled.append(callback)),
    )
    old_consumer = _Consumer(manager, generation=81)
    old_service = _lease(old_consumer, factory)
    assert old_service.start() is True
    old_poll = scheduled[0]
    old_service.retire()

    new_consumer = _Consumer(manager, generation=82)
    new_service = _lease(new_consumer, factory)
    assert new_service.start() is True
    assert len(factory.backends) == 2
    factory.backends[0].muted = True
    factory.backends[1].muted = True

    old_poll()

    assert factory.backends[0].read_calls == 0
    assert factory.backends[1].read_calls == 0
    assert new_consumer.snapshots[-1].muted is False

    scheduled[1]()
    assert factory.backends[1].read_calls == 1
    assert new_consumer.snapshots[-1].muted is True


def test_shared_toggle_executes_once_and_fans_out_to_all_projections(monkeypatch) -> None:
    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    manager = object()
    factory = _BackendFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    assert first.start() is True
    assert second.start() is True

    assert second.toggle_mute() is True

    assert factory.backends[0].toggle_calls == 1
    assert first_consumer.snapshots[-1].muted is True
    assert second_consumer.snapshots[-1].muted is True
    assert first_consumer.snapshots[-1].source == "toggle"


def test_system_volume_step_refreshes_mute_once_and_fans_out(monkeypatch) -> None:
    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    manager = object()
    factory = _BackendFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    assert first.start() is True
    assert second.start() is True
    factory.backends[0].muted = True

    assert first.step_system_volume(0.05) == pytest.approx(0.55)

    assert factory.backends[0].step_calls == [pytest.approx(0.05)]
    assert factory.backends[0].read_calls == 1
    assert first_consumer.snapshots[-1].muted is True
    assert second_consumer.snapshots[-1].muted is True


def test_external_refreshes_are_coalesced_across_display_leases(monkeypatch) -> None:
    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    manager = object()
    factory = _BackendFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    assert first.start() is True
    assert second.start() is True

    assert first.request_refresh(source="native_key") is True
    assert second.request_refresh(source="native_key") is False
    assert factory.backends[0].read_calls == 1


def test_shared_lease_requires_generation_or_thread_manager() -> None:
    consumer = type(
        "Consumer",
        (),
        {
            "_runtime_generation": None,
            "_thread_manager": None,
            "is_system_mute_consumer_alive": lambda self: True,
            "on_system_mute_runtime_snapshot": lambda self, snapshot: None,
            "parent": lambda self: None,
        },
    )()
    service = SystemMuteRuntimeService(
        shared=True, backend_factory=_BackendFactory()
    )

    with pytest.raises(RuntimeError, match="requires runtime generation or ThreadManager"):
        service.attach_consumer(consumer)

    assert shared_system_mute_owner_count() == 0


def test_backend_calls_remain_on_the_owner_ui_thread(monkeypatch) -> None:
    ui_thread_id = threading.get_ident()
    call_threads: list[int] = []

    class _ThreadRecordingBackend(_Backend):
        def is_available(self) -> bool:
            call_threads.append(threading.get_ident())
            return super().is_available()

        def get_mute(self) -> bool:
            call_threads.append(threading.get_ident())
            return super().get_mute()

        def toggle_mute(self) -> bool:
            call_threads.append(threading.get_ident())
            return super().toggle_mute()

        def step_volume(self, delta: float) -> float:
            call_threads.append(threading.get_ident())
            return super().step_volume(delta)

    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: scheduled.append(callback)),
    )
    manager = object()
    consumer = _Consumer(manager)

    def _build_backend():
        call_threads.append(threading.get_ident())
        return _ThreadRecordingBackend()

    service = SystemMuteRuntimeService(
        shared=False,
        backend_factory=_build_backend,
    )
    service.set_thread_manager(manager)
    service.attach_consumer(consumer)
    assert service.start() is True

    scheduled[0]()
    assert service.toggle_mute() is True
    assert service.step_system_volume(0.05) == pytest.approx(0.55)

    assert call_threads
    assert set(call_threads) == {ui_thread_id}


def test_global_authority_requires_known_generation_for_shared_lease(
    qt_app, monkeypatch
) -> None:
    from widgets.mute_button_widget import MuteButtonWidget

    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    parent = QWidget()
    parent._runtime_generation = None
    manager = object()
    button = MuteButtonWidget(parent, build_default_runtime=False)
    shared_service = SystemMuteRuntimeService(
        shared=True,
        backend_factory=_BackendFactory(),
    )
    button.set_thread_manager(manager)
    try:
        button.set_runtime_service(shared_service)
        button.set_enabled(True)

        assert shared_service.is_running() is True
        assert button.has_live_system_mute_runtime() is False
    finally:
        button.cleanup()
        button.deleteLater()
        parent.deleteLater()


def test_generationless_isolated_widget_remains_live_for_standalone_use(
    qt_app, monkeypatch
) -> None:
    from widgets.mute_button_widget import MuteButtonWidget

    monkeypatch.setattr(ThreadManager, "single_shot", staticmethod(lambda *args, **kwargs: None))
    parent = QWidget()
    parent._runtime_generation = None
    button = MuteButtonWidget(parent, build_default_runtime=False)
    isolated_service = SystemMuteRuntimeService(
        shared=False,
        backend=_Backend(),
    )
    try:
        button.set_runtime_service(isolated_service)
        button.set_enabled(True)

        assert isolated_service.is_running() is True
        assert button.has_live_system_mute_runtime() is True
    finally:
        button.cleanup()
        button.deleteLater()
        parent.deleteLater()


def test_real_secondary_setup_injects_mute_owner_before_enable_and_reuses_it(
    qt_app, monkeypatch
) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    manager_thread = object()
    factory = _BackendFactory()
    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["mute_button"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "mute_button",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: SystemMuteRuntimeService(
                shared=True, backend_factory=factory
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback))),
    )

    parent = QWidget()
    parent._thread_manager = manager_thread
    parent._runtime_generation = 101
    parent.spotify_volume_widget = None
    parent.mute_button_widget = None
    anchor = QWidget(parent)
    manager = WidgetManager(parent, ResourceManager())
    monkeypatch.setattr(
        manager, "create_spotify_volume_widget", lambda *args, **kwargs: None
    )
    config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "mute_button_enabled": True,
            "spotify_volume_enabled": False,
        }
    }
    created = {"media_widget": anchor}
    try:
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager, created, config, {}, 0, manager_thread, anchor
        )
        button = created["mute_button_widget"]
        service = manager._runtime_manager.get_widget_service("mute_button")

        assert button._runtime_service is service
        assert service is not None and service.is_running() is True
        assert button.is_lifecycle_active() is True
        assert len(factory.backends) == 1
        assert [delay for delay, _callback in scheduled if delay == 30_000] == [30_000]

        recreated = {"media_widget": anchor}
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager, recreated, config, {}, 0, manager_thread, anchor
        )

        assert recreated["mute_button_widget"] is button
        assert manager._runtime_manager.get_widget_service("mute_button") is service
        assert len(factory.backends) == 1
        assert [delay for delay, _callback in scheduled if delay == 30_000] == [30_000]
    finally:
        manager.cleanup()
        anchor.deleteLater()
        parent.deleteLater()

    assert shared_system_mute_owner_count() == 0


def test_two_real_managers_share_owner_until_final_cleanup(qt_app, monkeypatch) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    manager_thread = object()
    factory = _BackendFactory()
    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["mute_button"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "mute_button",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: SystemMuteRuntimeService(
                shared=True, backend_factory=factory
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback))),
    )
    config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "mute_button_enabled": True,
            "spotify_volume_enabled": False,
        }
    }
    entries = []

    def _setup_one(screen_index: int):
        parent = QWidget()
        parent._thread_manager = manager_thread
        parent._runtime_generation = 111
        parent.spotify_volume_widget = None
        parent.mute_button_widget = None
        anchor = QWidget(parent)
        manager = WidgetManager(parent, ResourceManager())
        monkeypatch.setattr(
            manager, "create_spotify_volume_widget", lambda *args, **kwargs: None
        )
        created = {"media_widget": anchor}
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager,
            created,
            config,
            {},
            screen_index,
            manager_thread,
            anchor,
        )
        service = manager._runtime_manager.get_widget_service("mute_button")
        entry = (parent, anchor, manager, created["mute_button_widget"], service)
        entries.append(entry)
        return entry

    first_cleaned = False
    second_cleaned = False
    try:
        first = _setup_one(0)
        second = _setup_one(1)
        first_service = first[4]
        second_service = second[4]
        owner = first_service.shared_owner

        assert owner is second_service.shared_owner
        assert len(factory.backends) == 1
        assert [delay for delay, _callback in scheduled if delay == 30_000] == [30_000]
        assert owner.active_consumer_count() == 2

        first[2].cleanup()
        first_cleaned = True

        assert owner.is_retired() is False
        assert owner.active_consumer_count() == 1
        assert second_service.is_running() is True
        assert second[3].has_live_system_mute_runtime() is True
        assert second_service.toggle_mute() is True
        assert factory.backends[0].toggle_calls == 1

        second[2].cleanup()
        second_cleaned = True

        assert owner.is_retired() is True
        assert shared_system_mute_owner_count() == 0
    finally:
        if entries and not first_cleaned:
            entries[0][2].cleanup()
        if len(entries) > 1 and not second_cleaned:
            entries[1][2].cleanup()
        for parent, anchor, _manager, _button, _service in entries:
            anchor.deleteLater()
            parent.deleteLater()


def test_real_setup_old_generation_poll_cannot_cross_recreation(qt_app, monkeypatch) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    manager_thread = object()
    factory = _BackendFactory()
    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["mute_button"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "mute_button",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: SystemMuteRuntimeService(
                shared=True, backend_factory=factory
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    scheduled = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, *args, **kwargs: scheduled.append((delay, callback))),
    )
    config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "mute_button_enabled": True,
            "spotify_volume_enabled": False,
        }
    }
    entries = []

    def _setup_generation(generation: int):
        parent = QWidget()
        parent._thread_manager = manager_thread
        parent._runtime_generation = generation
        parent.spotify_volume_widget = None
        parent.mute_button_widget = None
        anchor = QWidget(parent)
        manager = WidgetManager(parent, ResourceManager())
        monkeypatch.setattr(
            manager, "create_spotify_volume_widget", lambda *args, **kwargs: None
        )
        created = {"media_widget": anchor}
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager, created, config, {}, 0, manager_thread, anchor
        )
        entry = (parent, anchor, manager, created["mute_button_widget"])
        entries.append(entry)
        return entry

    first_cleaned = False
    second_cleaned = False
    try:
        first = _setup_generation(121)
        old_poll = [callback for delay, callback in scheduled if delay == 30_000][0]
        first[2].cleanup()
        first_cleaned = True

        second = _setup_generation(122)
        current_polls = [callback for delay, callback in scheduled if delay == 30_000]
        assert len(current_polls) == 2
        assert len(factory.backends) == 2
        factory.backends[0].muted = True
        factory.backends[1].muted = True

        old_poll()

        assert factory.backends[0].read_calls == 0
        assert factory.backends[1].read_calls == 0
        assert second[3]._muted is False

        current_polls[1]()
        assert factory.backends[1].read_calls == 1
        assert second[3]._muted is True

        second[2].cleanup()
        second_cleaned = True
    finally:
        if entries and not first_cleaned:
            entries[0][2].cleanup()
        if len(entries) > 1 and not second_cleaned:
            entries[1][2].cleanup()
        for parent, anchor, _manager, _button in entries:
            anchor.deleteLater()
            parent.deleteLater()


def test_secondary_setup_fails_closed_when_mute_service_build_is_lost(
    qt_app, monkeypatch
) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["mute_button"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "mute_button",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: (_ for _ in ()).throw(
                RuntimeError("mute service build lost")
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    parent = QWidget()
    parent._thread_manager = object()
    parent._runtime_generation = 102
    parent.spotify_volume_widget = None
    parent.mute_button_widget = None
    anchor = QWidget(parent)
    manager = WidgetManager(parent, ResourceManager())
    monkeypatch.setattr(
        manager, "create_spotify_volume_widget", lambda *args, **kwargs: None
    )
    created = {"media_widget": anchor}
    try:
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager,
            created,
            {
                "media": {
                    "enabled": True,
                    "monitor": "ALL",
                    "mute_button_enabled": True,
                    "spotify_volume_enabled": False,
                }
            },
            {},
            0,
            parent._thread_manager,
            anchor,
        )

        assert "mute_button_widget" not in created
        assert manager.get_widget("mute_button") is None
        assert parent.mute_button_widget is None
        assert manager._runtime_manager.get_widget_service("mute_button") is None
        assert shared_system_mute_owner_count() == 0
    finally:
        manager.cleanup()
        anchor.deleteLater()
        parent.deleteLater()


def test_disabled_mute_button_builds_no_owner_or_backend(qt_app, monkeypatch) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    factory = _BackendFactory()
    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["mute_button"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "mute_button",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: SystemMuteRuntimeService(
                shared=True, backend_factory=factory
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    parent = QWidget()
    parent._thread_manager = object()
    parent._runtime_generation = 103
    parent.spotify_volume_widget = None
    parent.mute_button_widget = None
    anchor = QWidget(parent)
    manager = WidgetManager(parent, ResourceManager())
    monkeypatch.setattr(
        manager, "create_spotify_volume_widget", lambda *args, **kwargs: None
    )
    created = {"media_widget": anchor}
    try:
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager,
            created,
            {
                "media": {
                    "enabled": True,
                    "monitor": "ALL",
                    "mute_button_enabled": False,
                    "spotify_volume_enabled": False,
                }
            },
            {},
            0,
            parent._thread_manager,
            anchor,
        )

        assert "mute_button_widget" not in created
        assert factory.backends == []
        assert shared_system_mute_owner_count() == 0
    finally:
        manager.cleanup()
        anchor.deleteLater()
        parent.deleteLater()
