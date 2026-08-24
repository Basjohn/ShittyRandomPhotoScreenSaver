from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from PySide6.QtWidgets import QWidget

from core.threading.manager import ThreadManager
from widgets.media_volume_runtime import (
    MediaVolumeRuntimeService,
    reset_shared_media_volume_runtime_for_tests,
    shared_media_volume_owner_count,
)


def test_registry_import_is_media_volume_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import sys
import rendering.widget_runtime_services  # noqa: F401

forbidden = {
    "widgets.media_volume_runtime",
    "widgets.spotify_volume_widget",
    "core.media.spotify_volume",
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


@dataclass
class _TaskResult:
    success: bool
    result: Any = None


class _ThreadManager:
    def __init__(self) -> None:
        self.jobs: list[tuple[Any, Any]] = []

    def submit_io_task(self, worker, callback=None, **_kwargs) -> None:
        self.jobs.append((worker, callback))

    def complete(self, index: int = 0, *, success: bool = True) -> Any:
        worker, callback = self.jobs.pop(index)
        result = worker() if success else None
        if callback is not None:
            callback(_TaskResult(success=success, result=result))
        return result


class _Controller:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self.level = 0.4
        self.configure_calls: list[tuple[object, object]] = []
        self.read_calls = 0
        self.write_calls: list[float] = []

    def is_available(self) -> bool:
        return True

    def configure_volume_target(self, provider, source_app_user_model_id="") -> bool:
        self.provider = str(provider)
        self.configure_calls.append((provider, source_app_user_model_id))
        return provider != "spotify_browser" or bool(source_app_user_model_id)

    def get_volume(self) -> float:
        self.read_calls += 1
        return self.level

    def set_volume(self, level: float) -> bool:
        self.level = float(level)
        self.write_calls.append(float(level))
        return True


class _ControllerFactory:
    def __init__(self) -> None:
        self.controllers: list[_Controller] = []

    def __call__(self, provider: str) -> _Controller:
        controller = _Controller(provider)
        self.controllers.append(controller)
        return controller


class _Consumer:
    def __init__(self, thread_manager: _ThreadManager, generation: int = 71) -> None:
        self._thread_manager = thread_manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []

    def is_media_volume_consumer_alive(self) -> bool:
        return self.alive

    def on_media_volume_runtime_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)


def _lease(
    consumer: _Consumer,
    factory: _ControllerFactory,
    *,
    provider: str = "spotify",
    shared: bool = True,
) -> MediaVolumeRuntimeService:
    service = MediaVolumeRuntimeService(
        provider=provider,
        shared=shared,
        controller_factory=factory,
    )
    service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


@pytest.fixture(autouse=True)
def _isolated_volume_owner(monkeypatch):
    reset_shared_media_volume_runtime_for_tests()
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args, **kwargs: (callback(*args, **kwargs), True)[1]),
    )
    yield
    reset_shared_media_volume_runtime_for_tests()


def test_two_display_leases_share_one_controller_read_debounce_and_projection(
    monkeypatch,
) -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer, factory)
    second = _lease(second_consumer, factory)
    delayed = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda delay, callback, *args, **kwargs: delayed.append((delay, callback))),
    )

    assert first.start() is True
    assert second.start() is True
    assert shared_media_volume_owner_count() == 1
    assert len(factory.controllers) == 1
    assert len(manager.jobs) == 1

    manager.complete()

    assert first_consumer.snapshots[-1].level == pytest.approx(0.4)
    assert second_consumer.snapshots[-1].level == pytest.approx(0.4)
    assert first.set_volume_optimistic(0.73) is True
    assert first_consumer.snapshots[-1].level == pytest.approx(0.73)
    assert second_consumer.snapshots[-1].level == pytest.approx(0.73)
    assert [delay for delay, _callback in delayed] == [80]

    delayed.pop()[1]()
    assert len(manager.jobs) == 1
    manager.complete()

    assert factory.controllers[0].write_calls == [pytest.approx(0.73)]


def test_first_display_retirement_preserves_owner_until_final_lease() -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
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
    assert shared_media_volume_owner_count() == 1

    second.retire()

    assert owner.is_retired() is True
    assert shared_media_volume_owner_count() == 0


def test_pending_write_is_invalidated_before_provider_retarget(monkeypatch) -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    service = _lease(_Consumer(manager), factory)
    delayed = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: delayed.append(callback)),
    )
    assert service.start() is True
    manager.complete()

    assert service.set_volume_optimistic(0.2) is True
    assert service.set_provider_runtime("musicbee") is True
    delayed.pop()()

    # Only the new-target sync was submitted; the old pending write vanished.
    assert len(manager.jobs) == 1
    manager.complete()
    assert factory.controllers[0].write_calls == []


def test_read_result_queued_before_stop_cannot_mutate_projection() -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    consumer = _Consumer(manager)
    service = _lease(consumer, factory)
    assert service.start() is True
    snapshots_before = list(consumer.snapshots)

    service.stop()
    manager.complete()

    assert consumer.snapshots == snapshots_before
    assert service.is_running() is False


def test_old_target_read_cannot_overwrite_new_provider_result() -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    consumer = _Consumer(manager)
    service = _lease(consumer, factory)
    assert service.start() is True
    controller = factory.controllers[0]

    controller.level = 0.1
    assert service.set_provider_runtime("musicbee") is True
    controller.level = 0.8

    # The first worker observes its stale target generation and returns None.
    manager.complete(0)
    assert consumer.snapshots[-1].source == "provider"
    manager.complete(0)

    assert consumer.snapshots[-1].source == "read"
    assert consumer.snapshots[-1].level == pytest.approx(0.8)


def test_stopped_generation_debounce_callback_does_not_write_or_reschedule(
    monkeypatch,
) -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    service = _lease(_Consumer(manager), factory)
    delayed = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: delayed.append(callback)),
    )
    assert service.start() is True
    manager.complete()
    assert service.set_volume_optimistic(0.9) is True

    service.stop()
    delayed.pop()()

    assert manager.jobs == []
    assert factory.controllers[0].write_calls == []


def test_queued_write_cannot_cross_final_stop_and_restart(monkeypatch) -> None:
    manager = _ThreadManager()
    factory = _ControllerFactory()
    service = _lease(_Consumer(manager), factory)
    delayed = []
    monkeypatch.setattr(
        ThreadManager,
        "single_shot",
        staticmethod(lambda _delay, callback, *args, **kwargs: delayed.append(callback)),
    )
    assert service.start() is True
    manager.complete()
    assert service.set_volume_optimistic(0.31) is True
    delayed.pop()()
    assert len(manager.jobs) == 1

    service.stop()
    assert service.start() is True
    assert len(manager.jobs) == 2

    # Complete the pre-stop write first. Its owner generation is retired.
    manager.complete(0)
    assert factory.controllers[0].write_calls == []
    manager.complete(0)
    assert factory.controllers[0].read_calls == 2


def test_shared_lease_requires_generation_or_thread_manager() -> None:
    consumer = type(
        "Consumer",
        (),
        {
            "_runtime_generation": None,
            "_thread_manager": None,
            "is_media_volume_consumer_alive": lambda self: True,
            "on_media_volume_runtime_snapshot": lambda self, snapshot: None,
            "parent": lambda self: None,
        },
    )()
    service = MediaVolumeRuntimeService(
        provider="spotify", shared=True, controller_factory=_ControllerFactory()
    )

    with pytest.raises(RuntimeError, match="requires runtime generation or ThreadManager"):
        service.attach_consumer(consumer)

    assert shared_media_volume_owner_count() == 0


def test_real_secondary_setup_injects_before_start_and_reuses_active_owner(
    qt_app, monkeypatch
) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    manager_thread = _ThreadManager()
    factory = _ControllerFactory()
    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["spotify_volume"]
    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "spotify_volume",
        widget_runtime_services.RuntimeServiceSpec(
            build=lambda _widget_id, _config: MediaVolumeRuntimeService(
                provider="spotify", shared=True, controller_factory=factory
            ),
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )

    parent = QWidget()
    parent._thread_manager = manager_thread
    parent._runtime_generation = 91
    parent.spotify_volume_widget = None
    parent.mute_button_widget = None
    anchor = QWidget(parent)
    parent.show()
    anchor.show()
    manager = WidgetManager(parent, ResourceManager())
    monkeypatch.setattr(
        manager, "create_mute_button_widget", lambda *args, **kwargs: None
    )
    config = {
        "media": {
            "enabled": True,
            "monitor": "ALL",
            "provider": "spotify",
            "spotify_volume_enabled": True,
        }
    }
    created = {"media_widget": anchor}
    try:
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager,
            created,
            config,
            {},
            0,
            manager_thread,
            anchor,
        )
        volume = created["spotify_volume_widget"]
        service = manager._runtime_manager.get_widget_service("spotify_volume")

        assert volume._runtime_service is service
        assert service is not None and service.is_running() is False
        assert len(factory.controllers) == 1
        volume._start_widget_fade_in = lambda *args, **kwargs: None
        assert volume.start() is True
        assert service.is_running() is True
        assert len(manager_thread.jobs) == 1

        recreated = {"media_widget": anchor}
        widget_setup_all._setup_media_owned_spotify_dependents(
            manager,
            recreated,
            config,
            {},
            0,
            manager_thread,
            anchor,
        )

        assert recreated["spotify_volume_widget"] is volume
        assert manager._runtime_manager.get_widget_service("spotify_volume") is service
        assert len(factory.controllers) == 1
        assert len(manager_thread.jobs) == 1
    finally:
        manager.cleanup()
        anchor.deleteLater()
        parent.deleteLater()

    assert shared_media_volume_owner_count() == 0


def test_secondary_setup_fails_closed_when_volume_service_build_is_lost(
    qt_app, monkeypatch
) -> None:
    from core.resources.manager import ResourceManager
    from rendering import widget_runtime_services, widget_setup_all
    from rendering.widget_manager import WidgetManager

    original_spec = widget_runtime_services._RUNTIME_SERVICE_SPECS["spotify_volume"]

    def _boom(_widget_id, _config):
        raise RuntimeError("volume service build lost")

    monkeypatch.setitem(
        widget_runtime_services._RUNTIME_SERVICE_SPECS,
        "spotify_volume",
        widget_runtime_services.RuntimeServiceSpec(
            build=_boom,
            inject=original_spec.inject,
            retire=original_spec.retire,
            reuse_is_valid=original_spec.reuse_is_valid,
        ),
    )
    manager_thread = _ThreadManager()
    parent = QWidget()
    parent._thread_manager = manager_thread
    parent._runtime_generation = 92
    parent.spotify_volume_widget = None
    parent.mute_button_widget = None
    anchor = QWidget(parent)
    manager = WidgetManager(parent, ResourceManager())
    monkeypatch.setattr(
        manager, "create_mute_button_widget", lambda *args, **kwargs: None
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
                    "provider": "spotify",
                    "spotify_volume_enabled": True,
                }
            },
            {},
            0,
            manager_thread,
            anchor,
        )

        assert "spotify_volume_widget" not in created
        assert manager.get_widget("spotify_volume") is None
        assert parent.spotify_volume_widget is None
        assert manager._runtime_manager.get_widget_service("spotify_volume") is None
        assert shared_media_volume_owner_count() == 0
    finally:
        manager.cleanup()
        anchor.deleteLater()
        parent.deleteLater()


def test_dormant_generic_factory_is_explicitly_inert_without_manager_injection(
    qt_app,
) -> None:
    from rendering.widget_factories import SpotifyVolumeFactory

    parent = QWidget()
    widget = SpotifyVolumeFactory(object()).create(
        parent,
        {
            "fill_color": "#ffffff",
            "border_color": "#ffffff",
            "bg_color": "#222222",
        },
    )
    try:
        assert widget is not None
        assert widget._runtime_service is None
        assert widget.start() is False
    finally:
        if widget is not None:
            widget.deleteLater()
        parent.deleteLater()
