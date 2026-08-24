"""Focused ownership regressions for the shared Gmail E1 runtime."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QThread

from core.gmail.gmail_backend import GmailBackendMode
from core.gmail.gmail_client import EmailMetadata, GmailFetchCancelled
from core.gmail.gmail_preparation import PreparedGmailStartup
from core.threading.manager import ThreadManager
from widgets import gmail_runtime
from widgets.gmail_runtime import (
    GmailRuntimeConfig,
    GmailRuntimeService,
    reset_shared_gmail_runtime_for_tests,
    shared_gmail_owner_count,
)


def test_registry_import_is_gmail_implementation_dormant_in_fresh_process() -> None:
    probe = r"""
import json
import sys
import rendering.widget_runtime_services  # noqa: F401

forbidden = {
    "widgets.gmail_runtime",
    "widgets.gmail_widget",
    "core.gmail.gmail_backend",
    "core.gmail.gmail_client",
    "core.gmail.gmail_imap",
    "core.gmail.gmail_oauth",
    "core.audio.notification_sound",
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


def _email(
    message_id: str = "message",
    *,
    unread: bool = True,
    provider: str = "gmail_api",
) -> EmailMetadata:
    return EmailMetadata(
        id=message_id,
        thread_id=f"thread-{message_id}",
        sender="Sender",
        subject=f"Subject {message_id}",
        date=datetime.now(),
        labels=("INBOX", "UNREAD") if unread else ("INBOX",),
        is_unread=unread,
        provider=provider,
    )


class _Timer:
    def __init__(self, interval: int, callback: Any) -> None:
        self.interval = interval
        self.callback = callback
        self.active = True

    def stop(self) -> None:
        self.active = False

    def isActive(self) -> bool:
        return self.active

    def thread(self):
        return QThread.currentThread()


class _QueuedIoManager:
    def __init__(self) -> None:
        self.tasks: list[SimpleNamespace] = []
        self.timers: list[_Timer] = []
        self.reject_categories: set[str] = set()
        self.fail_timer = False

    def submit_io_task(
        self,
        func,
        *args,
        callback=None,
        category="uncategorized",
        **kwargs,
    ):
        if category in self.reject_categories:
            raise RuntimeError(f"rejected {category}")
        task = SimpleNamespace(
            func=func,
            args=args,
            kwargs=kwargs,
            callback=callback,
            category=category,
        )
        self.tasks.append(task)
        return f"task-{len(self.tasks)}"

    def schedule_recurring(self, interval, callback, **_kwargs):
        if self.fail_timer:
            raise RuntimeError("timer setup failed")
        timer = _Timer(interval, callback)
        self.timers.append(timer)
        return timer

    def pop(self, category: str) -> SimpleNamespace:
        for index, task in enumerate(self.tasks):
            if task.category == category:
                return self.tasks.pop(index)
        raise AssertionError(f"missing queued category {category}: {self.categories}")

    @property
    def categories(self) -> list[str]:
        return [task.category for task in self.tasks]


def _run_task(task: SimpleNamespace) -> None:
    try:
        value = task.func(*task.args, **task.kwargs)
        result = SimpleNamespace(success=True, result=value, error=None)
    except Exception as exc:
        result = SimpleNamespace(success=False, result=None, error=exc)
    if task.callback is not None:
        task.callback(result)


class _Client:
    def __init__(self, emails: list[EmailMetadata] | None = None) -> None:
        self.emails = list(emails or [])
        self.list_calls: list[dict[str, Any]] = []
        self.actions: list[tuple[str, str]] = []
        self.raise_error: Exception | None = None

    def list_messages(self, **kwargs):
        self.list_calls.append(dict(kwargs))
        should_cancel = kwargs.get("should_cancel")
        if callable(should_cancel) and should_cancel():
            raise GmailFetchCancelled("retired")
        if self.raise_error is not None:
            raise self.raise_error
        return list(self.emails)

    def _action(self, name: str, message_id: str) -> bool:
        self.actions.append((name, message_id))
        return True

    def mark_as_read(self, message_id: str) -> bool:
        return self._action("mark_read", message_id)

    def mark_as_unread(self, message_id: str) -> bool:
        return self._action("mark_unread", message_id)

    def archive_message(self, message_id: str) -> bool:
        return self._action("archive", message_id)

    def spam_message(self, message_id: str) -> bool:
        return self._action("spam", message_id)

    def trash_message(self, message_id: str) -> bool:
        return self._action("trash", message_id)

    def open_message_in_browser(self, message_id: str) -> None:
        self.actions.append(("open", message_id))


class _Backend:
    def __init__(
        self,
        client: _Client | None = None,
        *,
        initialized: bool = True,
        authenticated: bool = True,
        mode: GmailBackendMode = GmailBackendMode.OAUTH,
    ) -> None:
        self.client = client or _Client()
        self.is_initialized = initialized
        self.is_authenticated = authenticated
        self.mode = mode
        self.ensure_calls = 0
        self.ensure_callbacks: list[Any] = []
        self.auth_calls = 0
        self.shutdown_calls = 0

    def ensure_initialized(self, _manager, callback) -> bool:
        self.ensure_calls += 1
        if self.is_initialized:
            callback(True)
        else:
            self.ensure_callbacks.append(callback)
        return True

    def complete_bootstrap(self, *, success: bool = True) -> None:
        self.is_initialized = bool(success)
        callbacks = list(self.ensure_callbacks)
        self.ensure_callbacks.clear()
        for callback in callbacks:
            callback(success)

    def start_oauth_flow(self) -> bool:
        self.auth_calls += 1
        return True

    def shutdown(self) -> None:
        self.shutdown_calls += 1


class _Consumer:
    def __init__(
        self,
        manager: _QueuedIoManager | None,
        *,
        generation: int = 41,
    ) -> None:
        self._thread_manager = manager
        self._runtime_generation = generation
        self.alive = True
        self.snapshots = []

    def is_gmail_consumer_alive(self) -> bool:
        return self.alive

    def on_gmail_runtime_snapshot(self, snapshot) -> None:
        self.snapshots.append(snapshot)


def _lease(
    consumer: _Consumer,
    *,
    config: GmailRuntimeConfig | None = None,
    shared: bool = True,
    backend: _Backend | None = None,
) -> GmailRuntimeService:
    service = GmailRuntimeService(
        config=config,
        shared=shared,
        backend=backend,
    )
    if consumer._thread_manager is not None:
        service.set_thread_manager(consumer._thread_manager)
    service.attach_consumer(consumer)
    return service


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch, tmp_path):
    reset_shared_gmail_runtime_for_tests()
    backend = _Backend(_Client([_email("live")]))
    monkeypatch.setattr(
        gmail_runtime.GmailBackend,
        "instance",
        classmethod(lambda _cls: backend),
    )
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (), None, "missing"
        ),
    )
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: True)
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args, **kwargs: callback(*args, **kwargs)),
    )
    yield backend, tmp_path
    reset_shared_gmail_runtime_for_tests()


def test_two_display_leases_share_one_bootstrap_cache_timer_fetch_and_snapshot(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cached = _email("cached")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer)
    second = _lease(second_consumer)

    assert first.shared_owner is second.shared_owner
    assert shared_gmail_owner_count() == 1
    assert first.start() is True
    assert second.start() is True
    assert len(manager.timers) == 1
    assert manager.categories == ["gmail_startup_cache"]
    assert backend.ensure_calls == 0

    _run_task(manager.pop("gmail_startup_cache"))

    assert [item.emails[0].id for item in first_consumer.snapshots] == ["cached"]
    assert [item.emails[0].id for item in second_consumer.snapshots] == ["cached"]
    assert backend.client.list_calls == []


def test_first_and_last_lease_lifetime_preserves_remaining_display(
    _isolated_runtime,
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    first_consumer = _Consumer(manager)
    second_consumer = _Consumer(manager)
    first = _lease(first_consumer)
    second = _lease(second_consumer)
    first.start()
    second.start()
    owner = first.shared_owner
    assert owner is not None

    first.retire()
    assert owner.is_running() is True
    assert owner.active_consumer_count() == 1
    assert owner.attached_consumer_count() == 1
    assert manager.timers[0].active is True

    second.stop()
    assert owner.is_running() is False
    assert manager.timers[0].active is False
    second.retire()
    assert owner.is_retired() is True
    assert shared_gmail_owner_count() == 0
    assert backend.shutdown_calls == 0


def test_active_second_lease_replays_snapshot_without_duplicate_work(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cached = _email("cached")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )
    first_consumer = _Consumer(manager)
    first = _lease(first_consumer)
    first.start()
    _run_task(manager.pop("gmail_startup_cache"))

    second_consumer = _Consumer(manager)
    second = _lease(second_consumer)
    assert second.start() is True

    assert len(manager.timers) == 1
    assert manager.tasks == []
    assert [snapshot.emails[0].id for snapshot in second_consumer.snapshots] == [
        "cached"
    ]


def test_distinct_runtime_generations_do_not_share_owner(_isolated_runtime) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    first = _lease(_Consumer(manager, generation=41))
    second = _lease(_Consumer(manager, generation=42))
    assert first.shared_owner is not second.shared_owner
    assert shared_gmail_owner_count() == 2
    first.retire()
    second.retire()


def test_every_shared_lease_reads_the_canonical_owner_config(
    _isolated_runtime,
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    first = _lease(
        _Consumer(manager),
        config=GmailRuntimeConfig(
            refresh_minutes=9,
            filter_label="CATEGORY_PRIMARY",
        ),
    )
    second = _lease(_Consumer(manager), config=GmailRuntimeConfig())

    assert second.config.refresh_minutes == 9
    assert second.config.filter_label == "CATEGORY_PRIMARY"

    first.configure(
        GmailRuntimeConfig(
            refresh_minutes=17,
            filter_label="CATEGORY_UPDATES",
        )
    )
    assert first.config.refresh_minutes == 17
    assert second.config.refresh_minutes == 17
    assert second.config.filter_label == "CATEGORY_UPDATES"


def test_standalone_services_never_join_production_owner(_isolated_runtime) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    first = _lease(_Consumer(manager), shared=False, backend=backend)
    second = _lease(_Consumer(manager), shared=False, backend=backend)
    assert first.shared_owner is not second.shared_owner
    assert shared_gmail_owner_count() == 0


def test_timer_creation_failure_rolls_back_activation(_isolated_runtime) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    manager.fail_timer = True
    service = _lease(_Consumer(manager))
    owner = service.shared_owner
    assert owner is not None

    assert service.start() is False
    assert service.is_running() is False
    assert owner.is_running() is False
    assert owner.active_consumer_count() == 0
    assert manager.tasks == []


def test_noupdates_keeps_cache_startup_and_manual_refresh_but_no_timer_or_auto_fetch(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    service = _lease(_Consumer(manager))

    assert service.start() is True
    assert manager.timers == []
    assert manager.categories == ["gmail_startup_cache"]
    _run_task(manager.pop("gmail_startup_cache"))
    assert backend.client.list_calls == []

    assert service.refresh() is True
    assert manager.categories == ["gmail_fetch"]
    assert service.refresh() is False


def test_missing_thread_manager_admits_no_work(_isolated_runtime) -> None:
    backend, _tmp_path = _isolated_runtime
    service = _lease(_Consumer(None), shared=False, backend=backend)
    assert service.start() is False
    assert backend.ensure_calls == 0


def test_pending_refresh_waits_for_single_backend_bootstrap(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    backend.is_initialized = False
    manager = _QueuedIoManager()
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (_email("cached"),), datetime.now(), "fresh"
        ),
    )
    service = _lease(_Consumer(manager))
    assert service.start() is True
    assert backend.ensure_calls == 1
    _run_task(manager.pop("gmail_startup_cache"))

    assert service.refresh() is True
    assert backend.ensure_calls == 1
    assert "gmail_fetch" not in manager.categories
    backend.complete_bootstrap()
    assert manager.categories == ["gmail_fetch"]


def test_late_backend_callback_is_rejected_after_stop(_isolated_runtime) -> None:
    backend, _tmp_path = _isolated_runtime
    backend.is_initialized = False
    manager = _QueuedIoManager()
    consumer = _Consumer(manager)
    service = _lease(consumer)
    service.start()
    owner = service.shared_owner
    assert owner is not None
    service.stop()

    backend.complete_bootstrap()

    assert owner.backend_ready is False
    assert "gmail_fetch" not in manager.categories
    assert consumer.snapshots == []


def test_startup_cache_load_is_io_then_ui_and_late_cache_is_fenced(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    queued_ui = []
    cached = _email("cached")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs))),
    )
    consumer = _Consumer(manager)
    service = _lease(consumer)
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    assert consumer.snapshots == []
    assert len(queued_ui) == 1

    service.stop()
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)
    assert consumer.snapshots == []


def test_live_fetch_supersedes_older_startup_cache(_isolated_runtime, monkeypatch) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    backend.client.emails = [_email("live")]
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (_email("cached"),), datetime.now(), "fresh"
        ),
    )
    consumer = _Consumer(manager)
    service = _lease(consumer)
    service.start()
    assert service.refresh() is True

    _run_task(manager.pop("gmail_fetch"))
    _run_task(manager.pop("gmail_startup_cache"))

    assert service.current_snapshot().emails[0].id == "live"
    assert all(
        not snapshot.emails or snapshot.emails[0].id != "cached"
        for snapshot in consumer.snapshots
    )


def test_early_fetch_error_is_replaced_by_later_valid_startup_cache(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    backend.client.raise_error = RuntimeError("early network failure")
    manager = _QueuedIoManager()
    cached = _email("cached-after-error")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )
    service = _lease(_Consumer(manager))
    service.start()
    assert service.refresh() is True

    _run_task(manager.pop("gmail_fetch"))
    error_snapshot = service.current_snapshot()
    assert error_snapshot is not None
    assert error_snapshot.error == "early network failure"

    _run_task(manager.pop("gmail_startup_cache"))
    snapshot = service.current_snapshot()
    assert snapshot is not None
    assert snapshot.emails == (cached,)
    assert snapshot.error is None
    assert snapshot.source == "cache"


def test_invalid_startup_cache_triggers_one_automatic_live_refresh(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup((), None, "invalid"),
    )
    service = _lease(_Consumer(manager))
    service.start()

    _run_task(manager.pop("gmail_startup_cache"))
    assert manager.categories == ["gmail_fetch"]
    _run_task(manager.pop("gmail_fetch"))

    snapshot = service.current_snapshot()
    assert snapshot is not None
    assert snapshot.emails[0].id == "live"
    assert snapshot.source == "live"


def test_authoritative_empty_live_result_supersedes_older_startup_cache(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    backend.client.emails = []
    manager = _QueuedIoManager()
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (_email("cached"),), datetime.now(), "fresh"
        ),
    )
    service = _lease(_Consumer(manager))
    service.start()
    service.refresh()

    _run_task(manager.pop("gmail_fetch"))
    _run_task(manager.pop("gmail_startup_cache"))

    snapshot = service.current_snapshot()
    assert snapshot is not None
    assert snapshot.emails == ()
    assert snapshot.source == "live"


def test_error_and_empty_fetch_preserve_accepted_cache(_isolated_runtime, monkeypatch) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cached = _email("cached")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )
    service = _lease(_Consumer(manager))
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))

    backend.client.raise_error = RuntimeError("network failed")
    service.refresh()
    _run_task(manager.pop("gmail_fetch"))
    snapshot = service.current_snapshot()
    assert snapshot.emails == (cached,)
    assert snapshot.error is None

    backend.client.raise_error = None
    backend.client.emails = []
    service.refresh()
    _run_task(manager.pop("gmail_fetch"))
    snapshot = service.current_snapshot()
    assert snapshot.emails == (cached,)
    assert snapshot.error is None


def test_fetch_uses_fixed_window_and_dispatch_failure_has_no_sync_fallback(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    service = _lease(_Consumer(manager))
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    service.refresh()
    _run_task(manager.pop("gmail_fetch"))
    assert backend.client.list_calls[-1]["max_results"] == 25
    assert backend.client.list_calls[-1]["label_ids"] == ["INBOX"]

    manager.reject_categories.add("gmail_fetch")
    call_count = len(backend.client.list_calls)
    assert service.refresh() is False
    assert len(backend.client.list_calls) == call_count


def test_presenter_config_sync_preserves_custom_filter_for_next_fetch(
    _isolated_runtime, qt_app
) -> None:
    from widgets.gmail_widget import GmailWidget

    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    widget = GmailWidget(build_default_runtime=False)
    widget.set_thread_manager(manager)
    service = GmailRuntimeService(
        config=GmailRuntimeConfig(filter_label="CATEGORY_PRIMARY"),
        shared=False,
        backend=backend,
    )
    widget.set_runtime_service(service, owns_service=True)
    try:
        widget.set_sound_volume_percent(37)
        assert service.config.filter_label == "CATEGORY_PRIMARY"
        assert service.start() is True
        _run_task(manager.pop("gmail_startup_cache"))
        _run_task(manager.pop("gmail_fetch"))
        assert backend.client.list_calls[-1]["label_ids"] == [
            "CATEGORY_PRIMARY"
        ]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_accepted_cache_write_is_detached_from_lease_retirement(
    _isolated_runtime, monkeypatch, tmp_path
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cache_path = tmp_path / "gmail.json"
    writes = []
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    monkeypatch.setattr(gmail_runtime, "reserve_gmail_cache_write", lambda _path: 7)
    monkeypatch.setattr(
        gmail_runtime,
        "write_gmail_email_cache",
        lambda path, emails, *, write_id: writes.append(
            (Path(path), tuple(email.id for email in emails), write_id)
        ),
    )
    config = GmailRuntimeConfig(cache_path=cache_path)
    service = _lease(_Consumer(manager), config=config)
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    service.refresh()
    _run_task(manager.pop("gmail_fetch"))
    persist = manager.pop("gmail_cache_persist")

    closure_values = tuple(
        cell.cell_contents
        for cell in (getattr(persist.func, "__closure__", None) or ())
    )
    assert all(not hasattr(value, "on_gmail_runtime_snapshot") for value in closure_values)
    service.retire()
    _run_task(persist)
    assert writes == [(cache_path, ("live",), 7)]


def test_cache_reservation_failure_does_not_suppress_accepted_snapshot(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    monkeypatch.setattr(
        gmail_runtime,
        "reserve_gmail_cache_write",
        lambda _path: (_ for _ in ()).throw(RuntimeError("reservation failed")),
    )
    service = _lease(_Consumer(manager))
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    service.refresh()
    _run_task(manager.pop("gmail_fetch"))

    snapshot = service.current_snapshot()
    assert snapshot is not None
    assert snapshot.emails[0].id == "live"
    assert "gmail_cache_persist" not in manager.categories


def test_stale_fetch_result_crossing_stop_is_not_published(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    queued_ui = []
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs))),
    )
    consumer = _Consumer(manager)
    service = _lease(consumer)
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    # Deliver startup cache completion first.
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)

    service.refresh()
    _run_task(manager.pop("gmail_fetch"))
    service.stop()
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)

    assert all(snapshot.source != "live" for snapshot in consumer.snapshots)
    owner = service.shared_owner
    assert owner is not None and owner.refresh_in_progress is False


def test_serialized_action_owns_one_post_action_refresh(_isolated_runtime, monkeypatch) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    service = _lease(_Consumer(manager))
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))

    assert service.dispatch_action("mark_read", "m1") is True
    assert service.dispatch_action("trash", "m2") is False
    _run_task(manager.pop("gmail_action"))

    assert backend.client.actions == [("mark_read", "m1")]
    assert manager.categories == ["gmail_fetch"]


def test_late_action_completion_cannot_refresh_retired_owner(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    queued_ui = []
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda callback, *args, **kwargs: queued_ui.append((callback, args, kwargs))),
    )
    service = _lease(_Consumer(manager))
    service.start()
    _run_task(manager.pop("gmail_startup_cache"))
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)
    service.dispatch_action("trash", "m1")
    _run_task(manager.pop("gmail_action"))
    service.retire()
    callback, args, kwargs = queued_ui.pop()
    callback(*args, **kwargs)

    assert backend.client.actions == [("trash", "m1")]
    assert "gmail_fetch" not in manager.categories


def test_action_ui_dispatch_failure_releases_serialization(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    service = _lease(_Consumer(manager))
    service.start()
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("UI dispatcher rejected completion")
            )
        ),
    )

    assert service.dispatch_action("trash", "m1") is True
    _run_task(manager.pop("gmail_action"))
    owner = service.shared_owner
    assert owner is not None and owner.action_in_progress is False
    assert service.dispatch_action("mark_read", "m2") is True


def test_silently_declined_action_completion_releases_serialization(
    _isolated_runtime, monkeypatch
) -> None:
    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    service = _lease(_Consumer(manager))
    service.start()
    monkeypatch.setattr(
        ThreadManager,
        "run_on_ui_thread",
        staticmethod(lambda *_args, **_kwargs: False),
    )

    assert service.dispatch_action("trash", "m1") is True
    _run_task(manager.pop("gmail_action"))
    owner = service.shared_owner
    assert owner is not None and owner.action_in_progress is False
    assert service.dispatch_action("mark_read", "m2") is True


def test_notification_decision_runs_once_for_all_displays(
    _isolated_runtime, monkeypatch
) -> None:
    backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    player = SimpleNamespace(
        file_path=None,
        volume_percent=0,
        plays=0,
        set_file_path=lambda path: setattr(player, "file_path", path),
        set_volume=lambda value: setattr(player, "volume_percent", value),
        play=lambda: setattr(player, "plays", player.plays + 1),
    )
    import core.audio.notification_sound as notification_sound

    monkeypatch.setattr(
        notification_sound.NotificationSoundPlayer,
        "instance",
        classmethod(lambda _cls: player),
    )
    monkeypatch.setattr(gmail_runtime, "automatic_service_updates_enabled", lambda: False)
    config = GmailRuntimeConfig(
        play_sound_on_new_mail=True,
        sound_file_path="sound.wav",
        sound_volume_percent=37,
    )
    first = _lease(_Consumer(manager), config=config)
    second = _lease(_Consumer(manager), config=config)
    first.start()
    second.start()
    _run_task(manager.pop("gmail_startup_cache"))

    backend.client.emails = [_email("existing")]
    first.refresh()
    _run_task(manager.pop("gmail_fetch"))
    manager.tasks.clear()  # cache persistence is not relevant to notification count
    backend.client.emails = [_email("existing"), _email("new")]
    second.refresh()
    _run_task(manager.pop("gmail_fetch"))

    assert player.plays == 1
    assert player.file_path == "sound.wav"
    assert player.volume_percent == 37


def test_production_gmail_factory_suppresses_standalone_owner(monkeypatch) -> None:
    from rendering.widget_factories import GmailWidgetFactory
    from widgets import gmail_widget

    created = []

    class _Widget:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.thread_manager = None
            created.append(self)

        def set_thread_manager(self, manager):
            self.thread_manager = manager

        def __getattr__(self, name):
            if name.startswith("set_"):
                return lambda *_args, **_kwargs: None
            raise AttributeError(name)

    manager = object()
    monkeypatch.setattr(gmail_widget, "GmailWidget", _Widget)
    factory = GmailWidgetFactory(SimpleNamespace(), manager)

    widget = factory.create(
        SimpleNamespace(),
        {
            "enabled": True,
            "position": "Top Left",
            "refresh_minutes": 7,
        },
    )

    assert widget is created[0]
    assert widget.kwargs["build_default_runtime"] is False
    assert widget.thread_manager is manager


def test_production_setup_injects_starts_and_reuses_one_live_gmail_owner(
    _isolated_runtime, monkeypatch, qt_app
) -> None:
    from PySide6.QtWidgets import QWidget

    from core.resources.manager import ResourceManager
    from rendering.widget_manager import WidgetManager

    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cached = _email("production-cache")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )

    class _Signal:
        def connect(self, *_args, **_kwargs):
            return None

        def disconnect(self, *_args, **_kwargs):
            return None

    class _Settings:
        settings_changed = _Signal()

        def get_widgets_map(self):
            return {
                "gmail": {
                    "enabled": True,
                    "monitor": "ALL",
                    "position": "Top Left",
                    "refresh_minutes": 5,
                },
                "family_activation": {"gmail": True},
            }

        def get(self, key, default=None):
            return self.get_widgets_map() if key == "widgets" else default

    parent = QWidget()
    parent._thread_manager = manager
    parent._runtime_generation = 41
    parent.screen_index = 0
    owner = WidgetManager(parent, ResourceManager())
    settings = _Settings()
    service = None
    try:
        created = owner.setup_all_widgets(
            settings,
            screen_index=0,
            thread_manager=manager,
        )
        widget = created["gmail_widget"]
        service = owner._runtime_manager.get_widget_service("gmail")
        assert service is widget._runtime_service
        assert widget._owns_runtime_service is False
        assert widget.is_lifecycle_active() is True
        assert service.is_running() is True
        assert shared_gmail_owner_count() == 1
        assert len(manager.timers) == 1
        assert manager.categories == ["gmail_startup_cache"]

        _run_task(manager.pop("gmail_startup_cache"))
        assert [email.id for email in widget._emails] == ["production-cache"]
        shared_owner = service.shared_owner

        recreated = owner.setup_all_widgets(
            settings,
            screen_index=0,
            thread_manager=manager,
        )
        assert recreated["gmail_widget"] is widget
        assert owner._runtime_manager.get_widget_service("gmail") is service
        assert service.shared_owner is shared_owner
        assert service.is_running() is True
        assert len(manager.timers) == 1
        assert manager.tasks == []
    finally:
        owner.cleanup()
        parent.deleteLater()

    assert service is not None and service.is_retired() is True
    assert shared_gmail_owner_count() == 0
    assert manager.timers[0].active is False


def test_two_production_displays_share_owner_until_final_cleanup(
    _isolated_runtime, monkeypatch, qt_app
) -> None:
    from PySide6.QtWidgets import QWidget

    from core.resources.manager import ResourceManager
    from rendering.widget_manager import WidgetManager

    _backend, _tmp_path = _isolated_runtime
    manager = _QueuedIoManager()
    cached = _email("shared-production-cache")
    monkeypatch.setattr(
        gmail_runtime,
        "load_gmail_startup_snapshot",
        lambda *_args, **_kwargs: PreparedGmailStartup(
            (cached,), datetime.now(), "fresh"
        ),
    )

    class _Signal:
        def connect(self, *_args, **_kwargs):
            return None

        def disconnect(self, *_args, **_kwargs):
            return None

    class _Settings:
        settings_changed = _Signal()

        def get_widgets_map(self):
            return {
                "gmail": {
                    "enabled": True,
                    "monitor": "ALL",
                    "position": "Top Left",
                    "refresh_minutes": 5,
                },
                "family_activation": {"gmail": True},
            }

        def get(self, key, default=None):
            return self.get_widgets_map() if key == "widgets" else default

    parents = [QWidget(), QWidget()]
    widget_managers = []
    for screen_index, parent in enumerate(parents):
        parent._thread_manager = manager
        parent._runtime_generation = 41
        parent.screen_index = screen_index
        widget_managers.append(WidgetManager(parent, ResourceManager()))

    settings = _Settings()
    first_cleaned = False
    second_cleaned = False
    first_service = None
    second_service = None
    try:
        first_widgets = widget_managers[0].setup_all_widgets(
            settings,
            screen_index=0,
            thread_manager=manager,
        )
        second_widgets = widget_managers[1].setup_all_widgets(
            settings,
            screen_index=1,
            thread_manager=manager,
        )
        first_widget = first_widgets["gmail_widget"]
        second_widget = second_widgets["gmail_widget"]
        first_service = first_widget._runtime_service
        second_service = second_widget._runtime_service
        shared_owner = first_service.shared_owner

        assert first_widget is not second_widget
        assert first_service is not second_service
        assert shared_owner is not None
        assert second_service.shared_owner is shared_owner
        assert shared_owner.active_consumer_count() == 2
        assert shared_owner.attached_consumer_count() == 2
        assert shared_gmail_owner_count() == 1
        assert len(manager.timers) == 1
        assert manager.categories == ["gmail_startup_cache"]

        _run_task(manager.pop("gmail_startup_cache"))
        assert [email.id for email in first_widget._emails] == [
            "shared-production-cache"
        ]
        assert [email.id for email in second_widget._emails] == [
            "shared-production-cache"
        ]

        widget_managers[0].cleanup()
        first_cleaned = True
        assert first_service.is_retired() is True
        assert second_service.is_running() is True
        assert shared_owner.is_running() is True
        assert shared_owner.active_consumer_count() == 1
        assert shared_owner.attached_consumer_count() == 1
        assert shared_gmail_owner_count() == 1
        assert manager.timers[0].active is True

        widget_managers[1].cleanup()
        second_cleaned = True
        assert second_service.is_retired() is True
        assert shared_owner.is_retired() is True
        assert shared_gmail_owner_count() == 0
        assert manager.timers[0].active is False
    finally:
        if not first_cleaned:
            widget_managers[0].cleanup()
        if not second_cleaned:
            widget_managers[1].cleanup()
        for parent in parents:
            parent.deleteLater()
