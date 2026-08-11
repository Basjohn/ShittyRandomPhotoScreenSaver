"""Ordered settings persistence ownership, revision, and durability tests."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from core.settings.json_store import JsonSettingsStore
from core.settings.persistence import (
    OrderedSettingsPersistence,
    flush_and_close_settings_persistence,
    flush_settings_persistence,
    get_settings_persistence,
)
from core.settings.settings_manager import SettingsManager
import core.settings.persistence as persistence_module


@pytest.fixture(autouse=True)
def _clean_process_persistence() -> None:
    flush_and_close_settings_persistence(timeout=2.0)
    yield
    flush_and_close_settings_persistence(timeout=2.0)


def _make_store(tmp_path: Path, name: str = "settings.json") -> JsonSettingsStore:
    return JsonSettingsStore(
        storage_path=(tmp_path / name).resolve(),
        profile="TestProfile",
    )


def _read_value(path: Path, section: str, key: str):
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["snapshot"][section][key]


def test_normal_sync_returns_before_writer_serialization_and_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    real_write = persistence_module._write_snapshot

    def blocked_write(request) -> None:
        entered.set()
        assert release.wait(2.0)
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", blocked_write)
    store.setValue("test.value", "authoritative-now")

    started = time.perf_counter()
    assert store.sync() is True
    elapsed = time.perf_counter() - started

    assert elapsed < 0.2
    assert store.value("test.value") == "authoritative-now"
    assert entered.wait(1.0)
    assert not Path(store.fileName()).exists()

    release.set()
    assert store.flush(timeout=2.0) is True
    assert _read_value(Path(store.fileName()), "test", "value") == "authoritative-now"


def test_same_owner_pending_revisions_coalesce_to_newest_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    first_started = threading.Event()
    release_first = threading.Event()
    real_write = persistence_module._write_snapshot
    calls: list[int] = []
    initial_revision = store.persistence_snapshot()["state_revision"]

    def controlled_write(request) -> None:
        calls.append(request.state_revision)
        if len(calls) == 1:
            first_started.set()
            assert release_first.wait(2.0)
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", controlled_write)

    store.setValue("ordered.value", 1)
    assert store.sync() is True
    assert first_started.wait(1.0)

    store.setValue("ordered.value", 2)
    assert store.sync() is True
    store.setValue("ordered.value", 3)
    assert store.sync() is True

    release_first.set()
    assert store.flush(timeout=2.0) is True

    assert _read_value(Path(store.fileName()), "ordered", "value") == 3
    assert calls == [initial_revision + 1, initial_revision + 3]
    metrics = get_settings_persistence().metrics_snapshot()
    assert metrics["enqueued"] == 3
    assert metrics["coalesced"] == 1
    assert metrics["writes_completed"] == 2


def test_flush_waits_for_acknowledgement_and_reports_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    entered = threading.Event()
    release = threading.Event()
    real_write = persistence_module._write_snapshot

    def blocked_write(request) -> None:
        entered.set()
        assert release.wait(2.0)
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", blocked_write)
    store.setValue("flush.value", "pending")
    store.sync()
    assert entered.wait(1.0)

    assert store.flush(timeout=0.02) is False
    assert store.persistence_snapshot()["dirty"] is True

    release.set()
    assert store.flush(timeout=2.0) is True
    assert store.persistence_snapshot()["dirty"] is False
    assert get_settings_persistence().metrics_snapshot()["flush_timeouts"] >= 1


def test_failed_write_remains_dirty_and_later_flush_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    real_write = persistence_module._write_snapshot
    attempts = 0

    def fail_once(request) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("injected replace failure")
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", fail_once)
    store.setValue("retry.value", 7)

    assert store.sync(wait=True, timeout=2.0) is False
    failed = store.persistence_snapshot()
    assert failed["dirty"] is True
    assert "injected replace failure" in str(failed["last_error"])

    assert store.flush(timeout=2.0) is True
    assert attempts == 2
    assert _read_value(Path(store.fileName()), "retry", "value") == 7


def test_settings_manager_critical_mutation_is_immediate_but_io_is_async(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SettingsManager(
        organization="TestOrg",
        application="AsyncCriticalProfile",
        storage_base_dir=tmp_path,
    )
    entered = threading.Event()
    release = threading.Event()
    real_write = persistence_module._write_snapshot
    received: list[tuple[str, object]] = []
    manager.settings_changed.connect(lambda key, value: received.append((key, value)))

    def blocked_write(request) -> None:
        entered.set()
        assert release.wait(2.0)
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", blocked_write)
    started = time.perf_counter()
    manager.set("widgets.clock.enabled", False)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.2
    assert manager.get("widgets.clock.enabled") is False
    assert received == [("widgets.clock.enabled", False)]
    assert entered.wait(1.0)

    release.set()
    assert manager.flush(timeout=2.0) is True


def test_noncritical_mutation_is_included_in_terminal_process_flush(
    tmp_path: Path,
) -> None:
    manager = SettingsManager(
        organization="TestOrg",
        application="TerminalNoncriticalProfile",
        storage_base_dir=tmp_path,
    )
    manager.set("ui.last_tab_index", 4)

    metrics = flush_and_close_settings_persistence(timeout=2.0)

    assert metrics["close_success"] is True
    assert _read_value(manager.get_storage_path(), "ui", "last_tab_index") == 4


def test_store_lock_prevents_older_sync_from_submitting_after_newer_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    controller = get_settings_persistence()
    original_submit = controller.submit
    first_state_revision = store.persistence_snapshot()["state_revision"] + 1
    first_in_submit = threading.Event()
    release_first = threading.Event()
    second_finished = threading.Event()

    def controlled_submit(**kwargs):
        if kwargs["state_revision"] == first_state_revision:
            first_in_submit.set()
            assert release_first.wait(2.0)
        return original_submit(**kwargs)

    monkeypatch.setattr(controller, "submit", controlled_submit)
    store.setValue("race.value", 1)
    first = threading.Thread(target=store.sync)
    first.start()
    assert first_in_submit.wait(1.0)

    def mutate_and_sync_newer() -> None:
        store.setValue("race.value", 2)
        store.sync()
        second_finished.set()

    second = threading.Thread(target=mutate_and_sync_newer)
    second.start()
    assert not second_finished.wait(0.05)

    release_first.set()
    first.join(2.0)
    second.join(2.0)
    assert second_finished.is_set()
    assert store.flush(timeout=2.0) is True
    assert _read_value(Path(store.fileName()), "race", "value") == 2


def test_same_profile_managers_share_one_mutable_store_authority(
    tmp_path: Path,
) -> None:
    app_name = "SharedStoreProfile"
    first = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    first.set("shared.value", "old")
    second = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )

    assert second._settings is first._settings
    second.set("shared.value", "new")
    first.set("shared.sibling", "preserved")
    assert first.flush(timeout=2.0) is True

    assert _read_value(first.get_storage_path(), "shared", "value") == "new"
    assert _read_value(first.get_storage_path(), "shared", "sibling") == "preserved"


def test_same_profile_manager_cache_and_signal_follow_peer_mutation(
    tmp_path: Path,
) -> None:
    app_name = "SharedManagerNotificationProfile"
    first = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    second = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    first.set("peer.value", "before")
    assert second.get("peer.value") == "before"
    received: list[tuple[str, object]] = []
    second.settings_changed.connect(lambda key, value: received.append((key, value)))

    first.set("peer.value", "after")

    assert second.get("peer.value") == "after"
    assert received == [("peer.value", "after")]


def test_peer_invalidation_waits_for_shared_cache_read_lock(
    tmp_path: Path,
) -> None:
    app_name = "SharedCacheLockProfile"
    first = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    second = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    first.set("cache.race", "before")
    assert second.get("cache.race") == "before"
    cache_key = f"cache.race:{id(None)}"
    read_entered = threading.Event()
    release_read = threading.Event()
    writer_finished = threading.Event()

    class PausingCache(dict):
        def get(self, key, default=None):
            if key == cache_key:
                read_entered.set()
                assert release_read.wait(2.0)
            return super().get(key, default)

    pausing_cache = PausingCache(second._cache)
    first._cache = pausing_cache
    second._cache = pausing_cache
    first._settings._manager_cache = pausing_cache

    read_result: list[object] = []
    reader = threading.Thread(target=lambda: read_result.append(second.get("cache.race")))
    reader.start()
    assert read_entered.wait(1.0)

    def mutate() -> None:
        first.set("cache.race", "after")
        writer_finished.set()

    writer = threading.Thread(target=mutate)
    writer.start()
    assert not writer_finished.wait(0.05)

    release_read.set()
    reader.join(2.0)
    writer.join(2.0)

    assert read_result == ["before"]
    assert writer_finished.is_set()
    assert second.get("cache.race") == "after"


def test_same_profile_mutation_cannot_be_followed_by_stale_cache_repopulation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_name = "SharedCacheReadProfile"
    first = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    second = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    first.set("cache.miss_race", "before")
    first._clear_cache_locked()

    real_value = first._settings.value
    read_entered = threading.Event()
    release_read = threading.Event()
    writer_finished = threading.Event()

    def pausing_value(key, default=None):
        value = real_value(key, default)
        if key == "cache.miss_race" and not read_entered.is_set():
            read_entered.set()
            assert release_read.wait(2.0)
        return value

    monkeypatch.setattr(first._settings, "value", pausing_value)
    read_result: list[object] = []
    reader = threading.Thread(
        target=lambda: read_result.append(second.get("cache.miss_race"))
    )
    reader.start()
    assert read_entered.wait(1.0)

    def mutate() -> None:
        first.set("cache.miss_race", "after")
        writer_finished.set()

    writer = threading.Thread(target=mutate)
    writer.start()
    assert not writer_finished.wait(0.05)

    release_read.set()
    reader.join(2.0)
    writer.join(2.0)

    assert read_result == ["before"]
    assert writer_finished.is_set()
    assert second.get("cache.miss_race") == "after"


def test_load_fails_closed_when_same_path_durability_cannot_be_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.settings.json_store.flush_settings_path",
        lambda *_args, **_kwargs: False,
    )

    with pytest.raises(RuntimeError, match="durability flush failed before load"):
        _make_store(tmp_path)


def test_manager_reload_durability_failure_does_not_reset_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SettingsManager(
        organization="TestOrg",
        application="ManagerLoadFailureProfile",
        storage_base_dir=tmp_path,
    )
    manager.set("reload.guard", "preserve")
    resets: list[bool] = []
    monkeypatch.setattr(manager._settings, "flush", lambda **_kwargs: False)
    monkeypatch.setattr(manager, "reset_to_defaults", lambda: resets.append(True))

    manager.load()

    assert manager.get("reload.guard") == "preserve"
    assert resets == []


def test_reload_retries_when_peer_mutates_after_flush_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_name = "ReloadPeerRaceProfile"
    first = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    second = SettingsManager(
        organization="TestOrg",
        application=app_name,
        storage_base_dir=tmp_path,
    )
    first.set("reload.race", "before")
    assert first.flush(timeout=2.0) is True

    real_flush_path = persistence_module.flush_settings_path
    barrier_entered = threading.Event()
    release_barrier = threading.Event()
    first_call = True

    def controlled_flush_path(path: Path, *, timeout: float = 5.0) -> bool:
        nonlocal first_call
        if first_call:
            first_call = False
            barrier_entered.set()
            assert release_barrier.wait(2.0)
        return real_flush_path(path, timeout=timeout)

    monkeypatch.setattr(
        "core.settings.json_store.flush_settings_path",
        controlled_flush_path,
    )
    reload_thread = threading.Thread(target=first.load)
    reload_thread.start()
    assert barrier_entered.wait(1.0)

    second.set("reload.race", "after")
    release_barrier.set()
    reload_thread.join(3.0)

    assert not reload_thread.is_alive()
    assert first.get("reload.race") == "after"
    assert second.get("reload.race") == "after"
    assert first.flush(timeout=2.0) is True
    assert _read_value(first.get_storage_path(), "reload", "race") == "after"


def test_explicit_reload_keeps_owner_revision_monotonic(
    tmp_path: Path,
) -> None:
    store = _make_store(tmp_path)
    store.setValue("reload.value", 1)
    assert store.sync(wait=True, timeout=2.0) is True
    before_reload = store.persistence_snapshot()["state_revision"]

    store.load()
    after_reload = store.persistence_snapshot()["state_revision"]
    store.setValue("reload.value", 2)
    assert store.sync(wait=True, timeout=2.0) is True

    assert after_reload > before_reload
    assert _read_value(Path(store.fileName()), "reload", "value") == 2


def test_one_process_writer_serializes_distinct_profile_paths(tmp_path: Path) -> None:
    first = _make_store(tmp_path, "first.json")
    second = _make_store(tmp_path, "second.json")
    controller = get_settings_persistence()

    first.setValue("profile.name", "first")
    second.setValue("profile.name", "second")
    first.sync()
    second.sync()

    assert flush_settings_persistence(timeout=2.0) is True
    assert _read_value(Path(first.fileName()), "profile", "name") == "first"
    assert _read_value(Path(second.fileName()), "profile", "name") == "second"
    assert get_settings_persistence() is controller
    assert controller.writer_thread.name == "SRPSSSettingsWriter"
    assert controller.metrics_snapshot()["writes_completed"] == 2


def test_controller_close_drains_and_rejects_late_submission(tmp_path: Path) -> None:
    controller = OrderedSettingsPersistence()
    path = (tmp_path / "direct.json").resolve()
    callback_results: list[tuple[int, int, bool, str | None]] = []

    ticket = controller.submit(
        owner_key=1,
        path=path,
        profile="Direct",
        snapshot_version=2,
        state_revision=1,
        data={"direct.value": 1},
        metadata={},
        callback=lambda *result: callback_results.append(result),
    )
    metrics = controller.close(timeout=2.0)

    assert ticket.wait(0.0) is True
    assert metrics["close_success"] is True
    assert metrics["writer_alive"] is False
    assert callback_results == [(1, 1, True, None)]
    assert _read_value(path, "direct", "value") == 1

    with pytest.raises(RuntimeError, match="closing"):
        controller.submit(
            owner_key=1,
            path=path,
            profile="Direct",
            snapshot_version=2,
            state_revision=2,
            data={"direct.value": 2},
            metadata={},
            callback=lambda *_args: None,
        )


def test_json_serialization_and_write_run_on_persistence_thread(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(tmp_path)
    caller_thread = threading.current_thread().name
    writer_threads: list[str] = []
    real_write = persistence_module._write_snapshot

    def recording_write(request) -> None:
        writer_threads.append(threading.current_thread().name)
        real_write(request)

    monkeypatch.setattr(persistence_module, "_write_snapshot", recording_write)
    store.setValue("thread.owner", "writer")
    assert store.sync(wait=True, timeout=2.0) is True

    assert writer_threads == ["SRPSSSettingsWriter"]
    assert writer_threads[0] != caller_thread
