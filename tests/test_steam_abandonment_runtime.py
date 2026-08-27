"""E1 ownership bars for the Steam Abandonment runtime/model service."""
from __future__ import annotations

import gc
import weakref
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtGui import QImage
import pytest

from core.steam.abandonment_issues import AbandonmentSelection
from core.threading.manager import TaskResult
from rendering.widget_runtime_services import get_runtime_service_spec
from widgets.steam_abandonment_preparation import (
    AbandonmentPreparedPresentation,
    AbandonmentRuntimeConfig,
)
from widgets.steam_abandonment_runtime import (
    AbandonmentRuntimeService,
)


class _Consumer:
    def __init__(self, generation: int = 42) -> None:
        self._runtime_generation = generation
        self.alive = True
        self.presentations: list[tuple[object, bool]] = []
        self.fade_requests = 0
        self.rotation_requests = 0

    def is_abandonment_consumer_alive(self) -> bool:
        return self.alive

    def on_abandonment_presentation(self, presentation, *, animate: bool) -> None:
        self.presentations.append((presentation, animate))

    def request_abandonment_fade(self) -> None:
        self.fade_requests += 1

    def on_abandonment_rotation_due(self) -> bool:
        self.rotation_requests += 1
        return True


class _QueuedIoManager:
    def __init__(self) -> None:
        self.tasks: list[SimpleNamespace] = []

    def submit_io_task(self, func, *, task_id, callback, **kwargs):
        task = SimpleNamespace(
            func=func,
            task_id=task_id,
            callback=callback,
            kwargs=dict(kwargs),
        )
        self.tasks.append(task)
        return task_id


class _TimerHandle:
    def __init__(self) -> None:
        self.active = True
        self.stop_calls = 0

    def is_active(self) -> bool:
        return self.active

    def stop(self) -> None:
        self.stop_calls += 1
        self.active = False


def _config(*, mode: str = "smart_rotation") -> AbandonmentRuntimeConfig:
    return AbandonmentRuntimeConfig(
        selection=AbandonmentSelection(mode=mode),
        show_artwork=False,
        refresh_minutes=5,
    )


def _prepared(identity: str = "fixture") -> AbandonmentPreparedPresentation:
    return AbandonmentPreparedPresentation(
        model=SimpleNamespace(state="content", appid=101),
        artwork=QImage(),
        artwork_identity=identity,
        desaturation_bucket=0,
    )


@pytest.fixture
def inline_ui(monkeypatch):
    monkeypatch.setattr(
        "widgets.steam_abandonment_runtime.ThreadManager.run_on_ui_thread",
        staticmethod(lambda func, *args, **kwargs: func(*args, **kwargs)),
    )


def _service() -> tuple[AbandonmentRuntimeService, _Consumer, _QueuedIoManager]:
    service = AbandonmentRuntimeService(config=_config())
    consumer = _Consumer()
    manager = _QueuedIoManager()
    service.attach_consumer(consumer)
    service.set_thread_manager(manager)
    return service, consumer, manager


def test_construction_configuration_and_attach_are_source_inert(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        "core.steam.credentials.read_credential_metadata",
        lambda: calls.append("credentials") or None,
    )

    service, consumer, manager = _service()

    assert calls == []
    assert manager.tasks == []
    assert consumer.presentations == []
    assert service.runtime_generation == 42
    assert service.is_running() is False


def test_start_queues_tagged_cache_work_without_running_source_inline() -> None:
    service, consumer, manager = _service()

    assert service.start(start_fade_after_load=True) is True

    assert len(manager.tasks) == 1
    task = manager.tasks[0]
    assert task.task_id.startswith("steam_abandonment_cache_load_")
    assert task.kwargs["category"] == "steam_abandonment_cache_load"
    assert task.func._srpss_runtime_generation == 42
    assert task.callback._srpss_runtime_generation == 42
    assert consumer.presentations == []
    assert consumer.fade_requests == 0


def test_two_display_services_submit_distinct_task_identities() -> None:
    manager = _QueuedIoManager()
    consumers: list[_Consumer] = []
    services: list[AbandonmentRuntimeService] = []
    for generation in (42, 43):
        service = AbandonmentRuntimeService(config=_config())
        consumer = _Consumer(generation=generation)
        consumers.append(consumer)
        service.attach_consumer(consumer)
        service.set_thread_manager(manager)
        assert service.start() is True
        services.append(service)

    assert len(manager.tasks) == 2
    assert len({task.task_id for task in manager.tasks}) == 2
    assert {task.func._srpss_runtime_generation for task in manager.tasks} == {42, 43}

    for service in services:
        service.retire()


def test_start_submission_failure_rolls_back_running_state() -> None:
    class _RejectingManager:
        def submit_io_task(self, *_args, **_kwargs):
            raise RuntimeError("queue closed")

    service = AbandonmentRuntimeService(config=_config())
    service.attach_consumer(_Consumer())
    service.set_thread_manager(_RejectingManager())

    assert service.start(start_fade_after_load=True) is False
    assert service.is_running() is False
    assert service.current_presentation is None


def test_queued_callbacks_do_not_strongly_retain_retired_owner() -> None:
    service, _consumer, manager = _service()
    service.start(start_fade_after_load=True)
    owner_ref = weakref.ref(service)

    service.retire()
    del service
    gc.collect()

    assert manager.tasks
    assert owner_ref() is None


def test_late_cache_completion_cannot_commit_after_stop(inline_ui) -> None:
    service, consumer, manager = _service()
    service.start(start_fade_after_load=True)
    task = manager.tasks[0]
    generation_after_start = service.owner_generation

    service.stop()
    generation_after_stop = service.owner_generation
    service.stop()
    assert service.owner_generation == generation_after_stop
    assert generation_after_stop > generation_after_start

    snapshot = SimpleNamespace(cache_age_seconds=30.0, rotation_due_seconds=75.0)
    task.callback(
        TaskResult(
            success=True,
            result=(object(), snapshot, _prepared("late-cache")),
            task_id=task.task_id,
        )
    )

    assert consumer.presentations == []
    assert consumer.fade_requests == 0
    assert service.current_presentation is None


def test_cross_generation_reattach_stops_and_fences_pending_cache(inline_ui) -> None:
    service, first, manager = _service()
    service.start(start_fade_after_load=True)
    task = manager.tasks[0]
    owner_generation = service.owner_generation

    replacement = _Consumer(generation=43)
    service.attach_consumer(replacement)

    assert service.runtime_generation == 43
    assert service.is_running() is False
    assert service.owner_generation > owner_generation

    snapshot = SimpleNamespace(cache_age_seconds=30.0, rotation_due_seconds=75.0)
    task.callback(
        TaskResult(
            success=True,
            result=(object(), snapshot, _prepared("old-generation")),
            task_id=task.task_id,
        )
    )

    assert first.presentations == []
    assert replacement.presentations == []
    assert replacement.fade_requests == 0
    assert service.current_presentation is None


def test_detach_stops_cadence_and_fences_pending_cache(inline_ui) -> None:
    service, consumer, manager = _service()
    service.start(start_fade_after_load=True)
    task = manager.tasks[0]
    owner_generation = service.owner_generation

    service.detach_consumer(consumer)

    assert service._consumer() is None
    assert service.is_running() is False
    assert service.owner_generation > owner_generation

    snapshot = SimpleNamespace(cache_age_seconds=30.0, rotation_due_seconds=75.0)
    task.callback(
        TaskResult(
            success=True,
            result=(object(), snapshot, _prepared("detached")),
            task_id=task.task_id,
        )
    )

    assert consumer.presentations == []
    assert consumer.fade_requests == 0
    assert service.current_presentation is None


def test_late_refresh_completion_cannot_commit_after_retirement(inline_ui) -> None:
    service, consumer, manager = _service()
    service._running = True

    assert service.request_manual_refresh() is True
    task = manager.tasks[0]
    assert task.func._srpss_runtime_generation == 42
    assert task.callback._srpss_runtime_generation == 42
    assert task.kwargs["category"] == "steam_abandonment_refresh"

    service.retire()
    task.callback(
        TaskResult(
            success=True,
            result=(object(), _prepared("late-refresh")),
            task_id=task.task_id,
        )
    )

    assert consumer.presentations == []
    assert service.current_presentation is None
    assert service.is_retired() is True


def test_late_rotation_completion_cannot_commit_after_retirement(inline_ui) -> None:
    service, consumer, manager = _service()
    service._running = True

    assert service.request_cache_rotation() is True
    task = manager.tasks[0]
    assert task.func._srpss_runtime_generation == 42
    assert task.callback._srpss_runtime_generation == 42
    assert task.kwargs["category"] == "steam_abandonment_rotation"

    service.retire()
    task.callback(
        TaskResult(
            success=True,
            result=_prepared("late-rotation"),
            task_id=task.task_id,
        )
    )

    assert consumer.presentations == []
    assert service.current_presentation is None


def test_manual_force_refresh_remains_available_under_noupdates(monkeypatch) -> None:
    service, _consumer, manager = _service()
    service._running = True
    monkeypatch.setattr(
        "widgets.steam_abandonment_runtime.automatic_service_updates_enabled",
        lambda: False,
    )

    assert service.refresh(cache_age_seconds=None, force=False) is False
    assert manager.tasks == []
    assert service.request_manual_refresh() is True
    assert len(manager.tasks) == 1


def test_persisted_rotation_delay_rearms_one_full_interval_and_retires_once(
    monkeypatch,
) -> None:
    service, consumer, _manager = _service()
    service._running = True
    service._activation_rotation_due_seconds = 75.0
    created: list[tuple[int, object, _TimerHandle]] = []

    def _create(_owner, interval_ms, callback, *, description):
        handle = _TimerHandle()
        created.append((interval_ms, callback, handle))
        return handle

    monkeypatch.setattr(
        "widgets.steam_abandonment_runtime.create_overlay_timer",
        _create,
    )

    service.start_rotation_timer()
    assert created[0][0] == 75_000
    created[0][1]()

    assert created[0][2].active is False
    assert created[1][0] == 5 * 60 * 1_000
    assert consumer.rotation_requests == 1

    service.retire()
    service.retire()
    assert created[1][2].stop_calls == 1
    assert service.rotation_timer is None


def test_prepared_state_rebinds_without_provider_recreation() -> None:
    service, first, manager = _service()
    presentation = _prepared("stable")
    service._current_presentation = presentation
    service.detach_consumer(first)
    replacement = _Consumer(generation=43)

    service.attach_consumer(replacement)

    assert replacement.presentations == [(presentation, False)]
    assert manager.tasks == []
    assert service.runtime_generation == 43


def test_running_configuration_change_is_rejected() -> None:
    service, _consumer, _manager = _service()
    service._running = True

    with pytest.raises(RuntimeError, match="immutable while running"):
        service.configure(_config(mode="pinned_game"))


def test_registry_reuse_validator_rejects_missing_edge_and_stopped_active_owner() -> None:
    service, consumer, _manager = _service()
    service._running = True
    consumer._runtime_service = service
    consumer.is_lifecycle_active = lambda: True
    spec = get_runtime_service_spec("abandonment_issues")

    assert spec is not None
    assert spec.reuse_is_valid is not None
    assert spec.reuse_is_valid(consumer, service) is True

    consumer._runtime_service = None
    assert spec.reuse_is_valid(consumer, service) is False

    consumer._runtime_service = service
    service.stop()
    assert spec.reuse_is_valid(consumer, service) is False


def test_retired_abandonment_and_unconverted_steam_qwidget_pixels_have_no_callers() -> None:
    from rendering.widget_descriptors import (
        FACTORY_WIDGET_DESCRIPTORS,
        WIDGET_RUNTIME_DESCRIPTORS,
    )

    retired_paths = (
        Path("widgets/abandonment_issues_widget.py"),
        Path("widgets/steam_abandonment_components.py"),
        Path("widgets/steam_card_widget.py"),
        Path("widgets/steam_components.py"),
    )
    assert all(not path.exists() for path in retired_paths)
    assert all(
        descriptor.settings_key
        not in {"steam_progress", "abandonment_issues", "friend_pulse"}
        for descriptor in FACTORY_WIDGET_DESCRIPTORS
    )
    assert all(
        descriptor.widget_id not in {"steam_progress", "friend_pulse"}
        for descriptor in WIDGET_RUNTIME_DESCRIPTORS
    )

    production_sources = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "rendering/display_input.py",
            "rendering/widget_factories.py",
            "rendering/widget_descriptors.py",
        )
    )
    for retired_marker in (
        "AbandonmentIssuesWidget",
        "SteamCardFactory",
        "steam_abandonment_components",
        "abandonment_issues_widget",
        "steam_progress_widget",
        "friend_pulse_widget",
    ):
        assert retired_marker not in production_sources


def test_neutral_abandonment_owner_contains_no_presenter_geometry_contract() -> None:
    runtime_source = Path("widgets/steam_abandonment_runtime.py").read_text(
        encoding="utf-8"
    )
    preparation_source = Path("widgets/steam_abandonment_preparation.py").read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "capture_abandonment_artwork_target",
        "artwork_target",
        "devicePixelRatio",
    ):
        assert forbidden not in runtime_source
        assert forbidden not in preparation_source
