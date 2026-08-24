"""E1 ownership bars for the Steam Achievement Pulse runtime service."""
from __future__ import annotations

import gc
import subprocess
import sys
import threading
import weakref
from dataclasses import replace
from pathlib import Path
from types import MethodType, SimpleNamespace

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget
import pytest

from core.resources.manager import ResourceManager
from core.steam.achievement_pulse import AchievementPulseSelection
from core.threading.manager import TaskResult, ThreadManager
from rendering.widget_manager import WidgetManager
from rendering.widget_runtime_services import get_runtime_service_spec
from widgets.steam_card_models import build_mock_steam_view_model
from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget
from widgets.steam_achievement_preparation import (
    AchievementPulsePreparedPresentation,
    AchievementPulseRuntimeConfig,
)
from widgets.steam_achievement_runtime import AchievementPulseRuntimeService


class _Consumer:
    def __init__(self, generation: int = 42) -> None:
        self._runtime_generation = generation
        self.alive = True
        self.presentations: list[tuple[object, bool]] = []
        self.fade_requests = 0

    def is_achievement_consumer_alive(self) -> bool:
        return self.alive

    def on_achievement_presentation(self, presentation, *, animate: bool) -> None:
        self.presentations.append((presentation, animate))

    def request_achievement_fade(self) -> None:
        self.fade_requests += 1


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


def _config(
    *,
    selection_mode: str = "most_recent",
    show_artwork: bool = False,
    show_latest_artwork: bool = False,
) -> AchievementPulseRuntimeConfig:
    return AchievementPulseRuntimeConfig(
        selection=AchievementPulseSelection(mode=selection_mode),
        show_artwork=show_artwork,
        show_latest_artwork=show_latest_artwork,
        refresh_minutes=5,
    )


def _model(*, appid: int = 101, icon_url: str = ""):
    return replace(
        build_mock_steam_view_model("achievement_pulse"),
        appid=appid,
        title=f"Game {appid}",
        latest_unlock_icon_url=icon_url,
    )


def _prepared(*, appid: int = 101) -> AchievementPulsePreparedPresentation:
    return AchievementPulsePreparedPresentation(model=_model(appid=appid))


def _image() -> QImage:
    image = QImage(2, 2, QImage.Format.Format_ARGB32)
    image.fill(0xFFFFFFFF)
    return image


@pytest.fixture
def inline_ui(monkeypatch):
    monkeypatch.setattr(
        "widgets.steam_achievement_runtime.ThreadManager.run_on_ui_thread",
        staticmethod(lambda func, *args, **kwargs: func(*args, **kwargs)),
    )


def _service(
    *,
    config: AchievementPulseRuntimeConfig | None = None,
) -> tuple[AchievementPulseRuntimeService, _Consumer, _QueuedIoManager]:
    service = AchievementPulseRuntimeService(config=config or _config())
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
    assert task.task_id.startswith("steam_achievement_cache_load_")
    assert task.kwargs["category"] == "steam_achievement_cache_load"
    assert task.func._srpss_runtime_generation == 42
    assert task.callback._srpss_runtime_generation == 42
    assert consumer.presentations == []
    assert consumer.fade_requests == 0


def test_two_display_services_submit_distinct_task_identities() -> None:
    manager = _QueuedIoManager()
    services: list[AchievementPulseRuntimeService] = []
    for generation in (42, 43):
        service = AchievementPulseRuntimeService(config=_config())
        service.attach_consumer(_Consumer(generation=generation))
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

    service = AchievementPulseRuntimeService(config=_config())
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


def test_refresh_and_artwork_callbacks_do_not_retain_retired_owner() -> None:
    service, _consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    service._running = True
    service.request_manual_refresh()
    service._accept_model(
        _model(icon_url="https://cdn.akamai.steamstatic.com/icon.png"),
        profile_key="profile",
        animate=False,
    )
    owner_ref = weakref.ref(service)

    service.retire()
    del service
    gc.collect()

    assert len(manager.tasks) == 3
    assert owner_ref() is None


def test_cache_result_commits_before_fade_and_tags_image_streams(inline_ui) -> None:
    service, consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    service.start(start_fade_after_load=True)
    cache_task = manager.tasks[0]
    snapshot = SimpleNamespace(cache_age_seconds=30.0)
    model = _model(icon_url="https://cdn.akamai.steamstatic.com/icon.png")

    cache_task.callback(
        TaskResult(
            success=True,
            result=(SimpleNamespace(profile_cache_key="profile"), snapshot, model),
            task_id=cache_task.task_id,
        )
    )

    assert service.current_presentation is not None
    assert service.current_presentation.model is model
    assert consumer.presentations[-1][0].model is model
    assert consumer.fade_requests == 1
    assert [task.kwargs["category"] for task in manager.tasks[1:]] == [
        "steam_achievement_artwork",
        "steam_achievement_latest_artwork",
    ]
    assert all(
        task.func._srpss_runtime_generation == 42
        and task.callback._srpss_runtime_generation == 42
        for task in manager.tasks[1:]
    )
    assert not hasattr(service, "rotation_timer")


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

    task.callback(
        TaskResult(
            success=True,
            result=(
                SimpleNamespace(profile_cache_key="profile"),
                SimpleNamespace(cache_age_seconds=30.0),
                _model(),
            ),
            task_id=task.task_id,
        )
    )

    assert consumer.presentations == []
    assert consumer.fade_requests == 0
    assert service.current_presentation is None


def test_real_queued_ui_delivery_is_fenced_when_service_stops_before_dispatch(
    qt_app,
) -> None:
    resource_manager = ResourceManager()
    thread_manager = ThreadManager(resource_manager=resource_manager)
    queued_tasks: list[SimpleNamespace] = []

    def _queue_io_task(self, func, *, task_id, callback, **kwargs):
        task = SimpleNamespace(
            func=func,
            task_id=task_id,
            callback=callback,
            kwargs=dict(kwargs),
        )
        queued_tasks.append(task)
        return task_id

    thread_manager.submit_io_task = MethodType(_queue_io_task, thread_manager)
    service = AchievementPulseRuntimeService(config=_config())
    consumer = _Consumer()
    service.attach_consumer(consumer)
    service.set_thread_manager(thread_manager)
    try:
        assert service.start(start_fade_after_load=True) is True
        task = queued_tasks[0]
        task_result = TaskResult(
            success=True,
            result=(
                SimpleNamespace(profile_cache_key="profile"),
                SimpleNamespace(cache_age_seconds=30.0),
                _model(),
            ),
            task_id=task.task_id,
        )
        callback_thread = threading.Thread(
            target=lambda: task.callback(task_result),
            name="achievement-runtime-test-callback",
        )
        callback_thread.start()
        callback_thread.join(timeout=5.0)
        assert callback_thread.is_alive() is False

        service.stop()
        qt_app.processEvents()

        assert consumer.presentations == []
        assert consumer.fade_requests == 0
        assert service.current_presentation is None
    finally:
        service.retire()
        thread_manager.shutdown()


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
    task.callback(
        TaskResult(
            success=True,
            result=(
                SimpleNamespace(profile_cache_key="profile"),
                SimpleNamespace(cache_age_seconds=30.0),
                _model(),
            ),
            task_id=task.task_id,
        )
    )
    assert first.presentations == []
    assert replacement.presentations == []
    assert service.current_presentation is None


def test_detach_stops_and_fences_pending_cache(inline_ui) -> None:
    service, consumer, manager = _service()
    service.start(start_fade_after_load=True)
    task = manager.tasks[0]
    owner_generation = service.owner_generation

    service.detach_consumer(consumer)

    assert service._consumer() is None
    assert service.is_running() is False
    assert service.owner_generation > owner_generation
    task.callback(
        TaskResult(
            success=True,
            result=(
                SimpleNamespace(profile_cache_key="profile"),
                SimpleNamespace(cache_age_seconds=30.0),
                _model(),
            ),
            task_id=task.task_id,
        )
    )
    assert consumer.presentations == []
    assert consumer.fade_requests == 0


def test_refresh_threshold_noupdates_and_manual_force(monkeypatch) -> None:
    service, _consumer, manager = _service()
    service._running = True
    monkeypatch.setattr(
        "widgets.steam_achievement_runtime.automatic_service_updates_enabled",
        lambda: False,
    )

    assert service.refresh(cache_age_seconds=300.0, force=False) is False
    assert manager.tasks == []
    assert service.request_manual_refresh() is True
    assert len(manager.tasks) == 1
    assert manager.tasks[0].kwargs["category"] == "steam_achievement_refresh"

    service._refresh_in_progress = False
    service._refresh_request_id += 1
    manager.tasks.clear()
    monkeypatch.setattr(
        "widgets.steam_achievement_runtime.automatic_service_updates_enabled",
        lambda: True,
    )
    assert service.refresh(cache_age_seconds=299.0, force=False) is False
    assert manager.tasks == []
    assert service.refresh(cache_age_seconds=300.0, force=False) is True
    assert len(manager.tasks) == 1


def test_credential_failure_rebuilds_the_cached_attention_model(
    monkeypatch,
    inline_ui,
) -> None:
    from core.steam.credentials import SteamCredentialError

    service, consumer, manager = _service()
    service._running = True
    snapshot = SimpleNamespace(cache_age_seconds=99_000.0)
    expected_model = _model()
    monkeypatch.setattr(
        "core.steam.credentials.load_credentials",
        lambda: (_ for _ in ()).throw(SteamCredentialError("locked")),
    )
    monkeypatch.setattr(
        "core.steam.credentials.read_credential_metadata",
        lambda: SimpleNamespace(profile_cache_key="profile"),
    )
    monkeypatch.setattr(
        "core.steam.achievement_pulse_cache.load_achievement_pulse_cache_snapshot",
        lambda **_kwargs: snapshot,
    )
    observed_attention: list[bool] = []

    def _prepare(_config, received, *, connection_needs_attention=False):
        assert received is snapshot
        observed_attention.append(bool(connection_needs_attention))
        return expected_model

    monkeypatch.setattr(
        "widgets.steam_achievement_runtime.prepare_achievement_model",
        _prepare,
    )

    assert service.request_manual_refresh() is True
    task = manager.tasks[0]
    result = task.func()
    task.callback(
        TaskResult(success=True, result=result, task_id=task.task_id)
    )

    assert observed_attention == [True]
    assert result[0] == "profile"
    assert result[1].connection_needs_attention is True
    assert service.current_presentation is not None
    assert service.current_presentation.model is expected_model
    assert consumer.presentations[-1][0].model is expected_model


def test_noupdates_keeps_existing_cache_first_asset_hydration_policy(
    monkeypatch,
) -> None:
    service, _consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    service._running = True
    monkeypatch.setattr(
        "widgets.steam_achievement_runtime.automatic_service_updates_enabled",
        lambda: False,
    )

    service._accept_model(
        _model(icon_url="https://cdn.akamai.steamstatic.com/icon.png"),
        profile_key="profile",
        animate=False,
    )

    # The old widget gated source refresh, not the existing cache-first public
    # asset helpers. Preserve that policy while moving ownership.
    assert [task.kwargs["category"] for task in manager.tasks] == [
        "steam_achievement_artwork",
        "steam_achievement_latest_artwork",
    ]


def test_late_refresh_and_artwork_completions_cannot_commit_after_retire(
    inline_ui,
) -> None:
    service, consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    service._running = True
    assert service.request_manual_refresh() is True
    refresh_task = manager.tasks[0]
    service._accept_model(
        _model(icon_url="https://cdn.akamai.steamstatic.com/icon.png"),
        profile_key="profile",
        animate=False,
    )
    artwork_tasks = manager.tasks[1:]
    assert len(artwork_tasks) == 2
    consumer.presentations.clear()

    service.retire()
    refresh_task.callback(
        TaskResult(
            success=True,
            result=("profile", object(), _model(appid=202)),
            task_id=refresh_task.task_id,
        )
    )
    for task in artwork_tasks:
        task.callback(
            TaskResult(
                success=True,
                result=(_image(), "late-image"),
                task_id=task.task_id,
            )
        )

    assert consumer.presentations == []
    assert service.current_presentation is None
    assert service.is_retired() is True


def test_old_model_artwork_cannot_commit_into_new_model(inline_ui) -> None:
    service, consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    service._running = True
    first_url = "https://cdn.akamai.steamstatic.com/first.png"
    second_url = "https://cdn.akamai.steamstatic.com/second.png"
    service._accept_model(
        _model(appid=101, icon_url=first_url),
        profile_key="profile",
        animate=False,
    )
    old_tasks = tuple(manager.tasks)
    service._accept_model(
        _model(appid=202, icon_url=second_url),
        profile_key="profile",
        animate=True,
    )
    consumer.presentations.clear()

    for task in old_tasks:
        task.callback(
            TaskResult(
                success=True,
                result=(_image(), f"old:{task.task_id}"),
                task_id=task.task_id,
            )
        )

    assert service.current_presentation is not None
    assert service.current_presentation.model.appid == 202
    assert service.current_presentation.artwork_identity == ""
    assert service.current_presentation.latest_artwork_identity == ""
    assert consumer.presentations == []


def test_prepared_state_replay_does_not_refetch_images() -> None:
    service, consumer, manager = _service(
        config=_config(show_artwork=True, show_latest_artwork=True)
    )
    image = _image()
    presentation = AchievementPulsePreparedPresentation(
        model=_model(icon_url="https://cdn.akamai.steamstatic.com/icon.png"),
        artwork=image,
        artwork_identity="app-path",
        artwork_key="101:portrait",
        latest_artwork=image,
        latest_artwork_identity="icon-path",
        latest_artwork_key="https://cdn.akamai.steamstatic.com/icon.png",
    )
    service._current_presentation = presentation
    service._current_profile_key = "profile"

    assert service.start(start_fade_after_load=True) is True

    assert manager.tasks == []
    assert consumer.presentations[-1][0] is presentation
    assert consumer.fade_requests == 1


def test_running_configuration_change_is_rejected() -> None:
    service, _consumer, _manager = _service()
    service._running = True

    with pytest.raises(RuntimeError, match="immutable while running"):
        service.configure(_config(selection_mode="recent_2"))


def test_registry_reuse_validator_rejects_missing_edge_and_stopped_active_owner() -> None:
    service, consumer, _manager = _service()
    service._running = True
    consumer._achievement_runtime_service = service
    consumer.is_lifecycle_active = lambda: True
    spec = get_runtime_service_spec("achievement_pulse")

    assert spec is not None
    assert spec.reuse_is_valid is not None
    assert spec.reuse_is_valid(consumer, service) is True
    consumer._achievement_runtime_service = None
    assert spec.reuse_is_valid(consumer, service) is False
    consumer._achievement_runtime_service = service
    service.stop()
    assert spec.reuse_is_valid(consumer, service) is False


def test_standalone_widget_owns_and_retires_one_convenience_service(qt_app) -> None:
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_show_artwork=False,
    )
    service = widget._achievement_runtime_service

    assert service is not None
    assert widget._owns_achievement_runtime_service is True
    widget.cleanup()

    assert widget._achievement_runtime_service is None
    assert service.is_retired() is True


def test_production_suppressed_widget_detaches_external_owner(qt_app) -> None:
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_show_artwork=False,
        build_default_runtime=False,
    )
    service = AchievementPulseRuntimeService(config=_config())
    widget.set_achievement_runtime_service(service)

    widget.cleanup()

    assert widget._achievement_runtime_service is None
    assert service.is_retired() is False
    assert service._consumer() is None
    service.retire()


def test_cleanup_makes_late_widget_deferred_callbacks_inert(qt_app) -> None:
    class _ExternalService:
        def __init__(self) -> None:
            self.manual_refreshes = 0
            self.detach_calls = 0

        def configure(self, _config) -> None:
            return None

        def attach_consumer(self, _consumer) -> None:
            return None

        def detach_consumer(self, _consumer) -> None:
            self.detach_calls += 1

        def is_running(self) -> bool:
            return False

        def request_manual_refresh(self) -> bool:
            self.manual_refreshes += 1
            return True

    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_show_artwork=False,
        build_default_runtime=False,
    )
    service = _ExternalService()
    widget.set_achievement_runtime_service(service)
    initial_model = widget._view_model
    widget._pending_achievement_manual_refresh = True
    widget._deferred_achievement_presentation = (_prepared(appid=202), True)
    late_callbacks = (
        widget._run_deferred_manual_refresh,
        widget._apply_deferred_achievement_presentation,
    )

    widget.cleanup()
    for callback in late_callbacks:
        callback()

    assert service.manual_refreshes == 0
    assert service.detach_calls == 1
    assert widget._view_model is initial_model


def test_production_setup_reuses_one_live_owner_without_recurring_timer(
    qt_app,
    inline_ui,
) -> None:
    class _Settings:
        def get_widgets_map(self) -> dict:
            return {
                "steam": {"enabled": True, "refresh_minutes": 5},
                "achievement_pulse": {
                    "enabled": True,
                    "monitor": "ALL",
                    "position": "Top Right",
                    "show_artwork": False,
                    "show_latest_achievement_artwork": False,
                },
                "family_activation": {"steam": True},
                "shadows": {"enabled": True},
            }

    parent = QWidget()
    parent.resize(1280, 720)
    parent._runtime_generation = 88
    resource_manager = ResourceManager()
    thread_manager = ThreadManager(resource_manager=resource_manager)
    queued_tasks: list[SimpleNamespace] = []

    def _queue_io_task(self, func, *, task_id, callback, **kwargs):
        task = SimpleNamespace(
            func=func,
            task_id=task_id,
            callback=callback,
            kwargs=dict(kwargs),
        )
        queued_tasks.append(task)
        return task_id

    thread_manager.submit_io_task = MethodType(_queue_io_task, thread_manager)
    parent._thread_manager = thread_manager
    manager = WidgetManager(parent, resource_manager)
    service = None
    try:
        created = manager.setup_all_widgets(
            _Settings(),
            screen_index=0,
            thread_manager=thread_manager,
        )
        widget = created["achievement_pulse_widget"]
        service = manager._runtime_manager.get_widget_service("achievement_pulse")

        assert service is widget._achievement_runtime_service
        assert widget._owns_achievement_runtime_service is False
        assert widget._thread_manager is thread_manager
        assert service._thread_manager is thread_manager
        assert service.is_running() is True
        assert len(queued_tasks) == 1
        cache_task = queued_tasks[0]
        assert cache_task.kwargs["category"] == "steam_achievement_cache_load"
        assert cache_task.func._srpss_runtime_generation == 88
        assert cache_task.callback._srpss_runtime_generation == 88

        cache_task.callback(
            TaskResult(
                success=True,
                result=(
                    SimpleNamespace(profile_cache_key="profile"),
                    SimpleNamespace(cache_age_seconds=30.0),
                    _model(),
                ),
                task_id=cache_task.task_id,
            )
        )
        assert service.current_presentation is not None
        assert service.current_presentation.model.appid == 101
        assert len(queued_tasks) == 1

        created_again = manager.setup_all_widgets(
            _Settings(),
            screen_index=0,
            thread_manager=thread_manager,
        )
        assert created_again["achievement_pulse_widget"] is widget
        assert manager._runtime_manager.get_widget_service("achievement_pulse") is service
        assert widget._achievement_runtime_service is service
        assert service.is_running() is True
        assert len(queued_tasks) == 1
        assert not hasattr(service, "rotation_timer")

        assert manager.cleanup_widget("achievement_pulse") is True
        assert service.is_retired() is True
        assert manager._runtime_manager.get_widget_service("achievement_pulse") is None
    finally:
        if service is not None and not service.is_retired():
            service.retire()
        thread_manager.shutdown()
        parent.deleteLater()


def test_registry_import_is_achievement_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import sys
import rendering.widget_runtime_services  # noqa: F401

forbidden = {
    "widgets.steam_achievement_runtime",
    "widgets.steam_achievement_preparation",
    "widgets.steam_card_widget",
    "core.steam.achievement_pulse_cache",
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
    import json

    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []


def test_deactivated_achievement_family_is_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QWidget
from core.resources.manager import ResourceManager
from rendering.widget_manager import WidgetManager

class Settings:
    def get_widgets_map(self):
        return {
            "steam": {"enabled": True},
            "achievement_pulse": {"enabled": True, "monitor": "ALL"},
            "family_activation": {"steam": False},
        }

app = QApplication.instance() or QApplication([])
parent = QWidget()
manager = WidgetManager(parent, ResourceManager())
created = manager.setup_all_widgets(Settings(), screen_index=0, thread_manager=None)
forbidden = {
    "widgets.steam_achievement_runtime",
    "widgets.steam_achievement_preparation",
    "widgets.steam_card_widget",
    "core.steam.achievement_pulse_cache",
}
print(json.dumps({
    "created": sorted(created),
    "forbidden": sorted(forbidden & set(sys.modules)),
}))
manager.cleanup()
parent.deleteLater()
"""
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    import json

    payload = json.loads(
        next(
            line
            for line in reversed(proc.stdout.strip().splitlines())
            if line.startswith("{")
        )
    )
    assert payload == {"created": [], "forbidden": []}


def test_disabled_achievement_instance_owns_no_widget_or_service(qt_app) -> None:
    class _Settings:
        def get_widgets_map(self) -> dict:
            return {
                "steam": {"enabled": True},
                "achievement_pulse": {"enabled": False, "monitor": "ALL"},
                "family_activation": {"steam": True},
            }

    parent = QWidget()
    manager = WidgetManager(parent, ResourceManager())
    try:
        created = manager.setup_all_widgets(
            _Settings(),
            screen_index=0,
            thread_manager=None,
        )
        assert "achievement_pulse_widget" not in created
        assert manager._runtime_manager.get_widget_service("achievement_pulse") is None
    finally:
        manager.cleanup()
        parent.deleteLater()


def test_legacy_widget_contains_no_achievement_source_or_task_owner() -> None:
    source = Path("widgets/steam_card_widget.py").read_text(encoding="utf-8")
    for forbidden in (
        "load_achievement_pulse_cache_snapshot",
        "refresh_achievement_pulse_cache",
        "fetch_steam_app_artwork",
        "fetch_steam_achievement_icon",
        "submit_io_task",
        "_achievement_cache_generation",
        "_achievement_artwork_generation",
        "_achievement_latest_artwork_generation",
    ):
        assert forbidden not in source

    runtime_source = Path("widgets/steam_achievement_runtime.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "from PySide6.QtWidgets",
        "QPainter(",
        "QPixmap(",
        "QTimer(",
        "create_overlay_timer(",
    ):
        assert forbidden not in runtime_source

    model_source = Path("widgets/steam_card_models.py").read_text(encoding="utf-8")
    assert "from PySide6" not in model_source
