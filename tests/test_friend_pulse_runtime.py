from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from core.steam.friend_pulse import FriendPulseEntry, FriendPulseSnapshot
from core.steam.models import SteamResultStatus
from widgets.friend_pulse_runtime import (
    FriendPulseRuntimeConfig,
    FriendPulseRuntimeService,
    reset_shared_friend_pulse_runtime_for_tests,
    shared_friend_pulse_owner_count,
)


class _Manager:
    def __init__(self) -> None:
        self.tasks = []

    def submit_io_task(self, worker, *, callback, category, priority):
        self.tasks.append((worker, callback, category, priority))
        return str(len(self.tasks))

    def complete(self, index: int, value) -> None:
        worker, callback, _category, _priority = self.tasks[index]
        del worker
        callback(SimpleNamespace(success=True, result=value))


class _Consumer:
    def __init__(self, generation: int, manager: _Manager) -> None:
        self._runtime_generation = generation
        self._thread_manager = manager
        self.received = []

    def is_friend_pulse_consumer_alive(self):
        return True

    def on_friend_pulse_runtime_snapshot(self, snapshot, projection):
        self.received.append((snapshot, projection))


def _snapshot(
    *,
    game: str = "Game",
    changed: bool = False,
    avatar: str | None = None,
    steam_id: str | None = None,
) -> FriendPulseSnapshot:
    return FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        authoritative=True,
        playing_count=1,
        entries=(
            FriendPulseEntry(
                "safe-id",
                "Ada",
                10,
                game,
                avatar_url=avatar,
                changed=changed,
                steam_id=steam_id,
            ),
        ),
    )


def _service(
    manager,
    *,
    mode="Rich",
    refresh_minutes=6,
    cache=None,
    refresh=None,
    scheduled=None,
    avatar_fetcher=None,
    ui_dispatch=None,
):
    return FriendPulseRuntimeService(
        config=FriendPulseRuntimeConfig(
            privacy_mode=mode,
            refresh_minutes=refresh_minutes,
        ),
        runtime_generation=9,
        cache_loader=cache or (lambda **_kwargs: _snapshot()),
        refresh_loader=refresh or (lambda **_kwargs: _snapshot()),
        credentials_loader=lambda: object(),
        metadata_loader=lambda: SimpleNamespace(profile_cache_key="profile_safe"),
        ui_dispatch=ui_dispatch or (lambda callback: callback()),
        scheduler=(
            scheduled if scheduled is not None else lambda _delay, _callback: None
        ),
        avatar_fetcher=avatar_fetcher,
        avatar_cache_dir_resolver=lambda _profile_key: Path("C:/safe/avatar-cache"),
    )


@pytest.fixture(autouse=True)
def _reset():
    reset_shared_friend_pulse_runtime_for_tests()
    yield
    reset_shared_friend_pulse_runtime_for_tests()


def test_zero_work_before_lease_start_and_one_shared_owner_for_two_displays():
    manager = _Manager()
    first, second = _service(manager), _service(manager)
    first.attach_consumer(_Consumer(9, manager))
    second.attach_consumer(_Consumer(9, manager))
    assert manager.tasks == [] and shared_friend_pulse_owner_count() == 1
    assert first.start() is True
    assert second.start() is True
    assert len(manager.tasks) == 1
    assert first.shared_owner is second.shared_owner


def test_detach_consumer_releases_the_last_shared_owner():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(manager)
    service.attach_consumer(consumer)
    assert shared_friend_pulse_owner_count() == 1

    service.detach_consumer(consumer)

    assert service.shared_owner is None
    assert service.is_running() is False
    assert shared_friend_pulse_owner_count() == 0


def test_last_lease_stops_work_and_fences_late_completion():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(manager)
    service.attach_consumer(consumer)
    service.start()
    service.retire()
    manager.complete(0, _snapshot())
    assert shared_friend_pulse_owner_count() == 0
    assert consumer.received == []


def test_restart_has_new_owner_and_rejects_prior_generation_completion():
    manager = _Manager()
    old_consumer = _Consumer(9, manager)
    old = _service(manager)
    old.attach_consumer(old_consumer)
    old.start()
    old.retire()
    fresh_consumer = _Consumer(9, manager)
    fresh = _service(manager)
    fresh.attach_consumer(fresh_consumer)
    fresh.start()
    manager.complete(0, _snapshot(game="old"))
    manager.complete(1, _snapshot(game="new"))
    assert old_consumer.received == []
    assert fresh_consumer.received[-1][0].entries[0].game_name == "new"


def test_unchanged_snapshot_does_not_churn_notifications_and_privacy_reprojects_without_refresh():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(manager)
    service.attach_consumer(consumer)
    service.start()
    first = _snapshot()
    manager.complete(0, first)
    assert len(consumer.received) == 1
    manager.complete(1, first)
    assert len(consumer.received) == 1
    assert service.refresh() is True
    manager.complete(2, first)
    assert len(consumer.received) == 1
    task_count = len(manager.tasks)
    service.configure(FriendPulseRuntimeConfig(privacy_mode="Strict"))
    assert len(manager.tasks) == task_count
    assert len(consumer.received) == 2
    assert consumer.received[-1][1].rows[0].primary == "Game"


def test_one_in_flight_skips_due_edges_and_schedules_only_after_completion():
    manager = _Manager()
    callbacks = []
    service = _service(
        manager, scheduled=lambda delay, callback: callbacks.append((delay, callback))
    )
    service.attach_consumer(_Consumer(9, manager))
    service.start()
    assert service.refresh() is False
    manager.complete(0, _snapshot())
    assert len(manager.tasks) == 2
    assert callbacks == []
    manager.complete(1, _snapshot())
    assert len(callbacks) == 1
    callbacks[0][1]()
    assert len(manager.tasks) == 3
    callbacks[0][1]()  # missed edge while request is in flight; it is skipped
    assert len(manager.tasks) == 3


def test_cache_completion_immediately_queues_one_forced_shared_refresh():
    manager = _Manager()
    credentials = []
    refresh_calls = []

    def refresh_loader(**kwargs):
        refresh_calls.append(kwargs)
        return _snapshot()

    service = FriendPulseRuntimeService(
        runtime_generation=9,
        cache_loader=lambda **_kwargs: None,
        refresh_loader=refresh_loader,
        credentials_loader=lambda: credentials.append(True)
        or SimpleNamespace(profile_identifier="profile-safe"),
        metadata_loader=lambda: SimpleNamespace(profile_cache_key="profile_safe"),
        ui_dispatch=lambda callback: callback(),
        scheduler=lambda _delay, _callback: None,
    )
    second = _service(manager)
    first_consumer, second_consumer = _Consumer(9, manager), _Consumer(9, manager)
    service.attach_consumer(first_consumer)
    second.attach_consumer(second_consumer)
    assert credentials == []
    service.start()
    second.start()
    assert len(manager.tasks) == 1
    manager.complete(0, None)
    # Cache completion is source-inert, but it immediately admits exactly one
    # credentialed forced refresh shared by both display leases.
    assert credentials == []
    assert len(manager.tasks) == 2
    assert service.refresh() is False
    manager.tasks[1][0]()
    assert credentials == [True]
    assert refresh_calls[0]["force"] is True


def test_missing_metadata_and_credentials_publish_not_configured():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = FriendPulseRuntimeService(
        runtime_generation=9,
        cache_loader=lambda **_kwargs: pytest.fail("cache requires metadata"),
        refresh_loader=lambda **_kwargs: pytest.fail("refresh requires credential"),
        credentials_loader=lambda: None,
        metadata_loader=lambda: None,
        ui_dispatch=lambda callback: callback(),
        scheduler=lambda _delay, _callback: None,
    )
    service.attach_consumer(consumer)
    service.start()
    manager.complete(0, manager.tasks[0][0]())
    assert consumer.received[-1][0].status == SteamResultStatus.NOT_CONFIGURED
    manager.complete(1, manager.tasks[1][0]())
    assert consumer.received[-1][0].status == SteamResultStatus.NOT_CONFIGURED


def test_rich_visible_rows_hydrate_once_with_local_sources_and_fence_stale_completion(
    tmp_path: Path,
):
    manager = _Manager()
    fetched = []
    image = tmp_path / "avatar.jpg"
    image.write_bytes(b"avatar")

    def avatar_fetcher(*, cache_dir, url):
        fetched.append((cache_dir, url))
        from core.steam.assets import SteamAssetRecord

        return SteamAssetRecord("safe", image, image.stat().st_size, "jpg")

    accepted = _snapshot(avatar="https://avatars.steamstatic.com/safe.jpg")
    rich_consumer, balanced_consumer = _Consumer(9, manager), _Consumer(9, manager)
    rich = _service(
        manager,
        mode="Rich",
        cache=lambda **_kwargs: accepted,
        avatar_fetcher=avatar_fetcher,
    )
    balanced = _service(manager, mode="Balanced", avatar_fetcher=avatar_fetcher)
    rich.attach_consumer(rich_consumer)
    balanced.attach_consumer(balanced_consumer)
    rich.start()
    balanced.start()
    manager.complete(0, manager.tasks[0][0]())
    # Cache completion queues source refresh plus exactly one shared avatar chain.
    avatar_index = next(
        i
        for i, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_avatar_hydration"
    )
    manager.complete(avatar_index, manager.tasks[avatar_index][0]())
    assert len(fetched) == 1
    assert rich_consumer.received[-1][1].rows[0].avatar_url.startswith("file:")
    assert balanced_consumer.received[-1][1].rows[0].avatar_url is None
    assert "https://" not in str(rich_consumer.received[-1][1])
    # Replacing accepted state before a second avatar completion makes that
    # late completion inert rather than mutating the new row list.
    rich.shared_owner._complete_avatars(  # noqa: SLF001 - fence regression seam
        rich.shared_owner._avatar_request_id,  # noqa: SLF001
        rich.shared_owner.owner_generation,
        0,
        0,
        {"safe-id": image.resolve().as_uri()},
    )
    assert len(fetched) == 1


def test_stale_avatar_completion_releases_slot_and_hydrates_new_snapshot(
    tmp_path: Path,
):
    manager = _Manager()
    image = tmp_path / "avatar.jpg"
    image.write_bytes(b"avatar")
    fetched: list[str] = []

    def avatar_fetcher(*, cache_dir, url):
        del cache_dir
        fetched.append(url)
        from core.steam.assets import SteamAssetRecord

        return SteamAssetRecord("safe", image, image.stat().st_size, "jpg")

    first = _snapshot(avatar="https://avatars.steamstatic.com/first.jpg")
    second = _snapshot(
        game="New Game",
        avatar="https://avatars.steamstatic.com/second.jpg",
    )
    consumer = _Consumer(9, manager)
    service = _service(
        manager,
        cache=lambda **_kwargs: first,
        avatar_fetcher=avatar_fetcher,
    )
    service.attach_consumer(consumer)
    service.start()
    manager.complete(0, manager.tasks[0][0]())
    avatar_index = next(
        index
        for index, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_avatar_hydration"
    )
    refresh_index = next(
        index
        for index, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_refresh"
    )

    manager.complete(refresh_index, second)
    manager.complete(avatar_index, manager.tasks[avatar_index][0]())

    avatar_tasks = [
        task for task in manager.tasks if task[2] == "friend_pulse_avatar_hydration"
    ]
    assert len(avatar_tasks) == 2
    assert fetched == ["https://avatars.steamstatic.com/first.jpg"]
    new_avatar_index = len(manager.tasks) - 1
    manager.complete(new_avatar_index, manager.tasks[new_avatar_index][0]())
    assert fetched[-1] == "https://avatars.steamstatic.com/second.jpg"
    assert consumer.received[-1][1].rows[0].avatar_url.startswith("file:")


def test_changed_avatar_url_invalidates_hydrated_path_and_fetches_replacement(
    tmp_path: Path,
):
    manager = _Manager()
    first_image = tmp_path / "first.jpg"
    second_image = tmp_path / "second.jpg"
    first_image.write_bytes(b"first")
    second_image.write_bytes(b"second")
    fetched: list[str] = []

    def avatar_fetcher(*, cache_dir, url):
        del cache_dir
        fetched.append(url)
        from core.steam.assets import SteamAssetRecord

        image = second_image if url.endswith("second.jpg") else first_image
        return SteamAssetRecord("safe", image, image.stat().st_size, "jpg")

    first = _snapshot(avatar="https://avatars.steamstatic.com/first.jpg")
    second = _snapshot(
        game="New Game",
        avatar="https://avatars.steamstatic.com/second.jpg",
    )
    consumer = _Consumer(9, manager)
    service = _service(
        manager,
        cache=lambda **_kwargs: first,
        avatar_fetcher=avatar_fetcher,
    )
    service.attach_consumer(consumer)
    service.start()
    manager.complete(0, manager.tasks[0][0]())
    avatar_index = next(
        index
        for index, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_avatar_hydration"
    )
    refresh_index = next(
        index
        for index, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_refresh"
    )

    manager.complete(avatar_index, manager.tasks[avatar_index][0]())
    assert consumer.received[-1][1].rows[0].avatar_url == first_image.as_uri()

    manager.complete(refresh_index, second)
    assert consumer.received[-1][1].rows[0].avatar_url is None
    replacement_index = len(manager.tasks) - 1
    assert manager.tasks[replacement_index][2] == "friend_pulse_avatar_hydration"
    manager.complete(replacement_index, manager.tasks[replacement_index][0]())

    assert fetched == [
        "https://avatars.steamstatic.com/first.jpg",
        "https://avatars.steamstatic.com/second.jpg",
    ]
    assert consumer.received[-1][1].rows[0].avatar_url == second_image.as_uri()


def test_live_refresh_cadence_change_replaces_shared_owner_deadline():
    manager = _Manager()
    callbacks = []
    service = _service(
        manager,
        scheduled=lambda delay, callback: callbacks.append((delay, callback)),
    )
    service.attach_consumer(_Consumer(9, manager))
    service.start()
    manager.complete(0, _snapshot())
    manager.complete(1, _snapshot())
    assert [delay for delay, _callback in callbacks] == [6 * 60_000]

    service.configure(FriendPulseRuntimeConfig(refresh_minutes=15))

    assert [delay for delay, _callback in callbacks] == [
        6 * 60_000,
        15 * 60_000,
    ]
    callbacks[0][1]()
    assert len(manager.tasks) == 2
    callbacks[1][1]()
    assert len(manager.tasks) == 3
    assert manager.tasks[-1][2] == "friend_pulse_refresh"


def test_private_steam_id_stays_owner_only_and_dies_with_final_lease():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(
        manager,
        cache=lambda **_kwargs: _snapshot(steam_id="76561198000000001"),
    )
    service.attach_consumer(consumer)
    service.start()
    manager.complete(0, manager.tasks[0][0]())

    assert consumer.received[-1][0].entries[0].steam_id is None
    assert service.friend_steam_id("safe-id") == "76561198000000001"
    service.stop()
    assert service.friend_steam_id("safe-id") is None


def test_live_id_only_change_reprojects_action_availability():
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(
        manager,
        cache=lambda **_kwargs: _snapshot(),
        refresh=lambda **_kwargs: _snapshot(steam_id="76561198000000001"),
    )
    service.attach_consumer(consumer)
    service.start()

    manager.complete(0, manager.tasks[0][0]())
    assert consumer.received[-1][1].rows[0].friend_action_available is False
    manager.complete(1, manager.tasks[1][0]())

    assert len(consumer.received) == 2
    assert consumer.received[-1][1].rows[0].friend_action_available is True
    assert service.friend_steam_id("safe-id") == "76561198000000001"


@pytest.mark.parametrize(
    "dispatch",
    [
        lambda _callback: False,
        lambda _callback: (_ for _ in ()).throw(RuntimeError("ui unavailable")),
    ],
)
def test_rejected_source_ui_dispatch_fails_closed_without_wedging(dispatch):
    manager = _Manager()
    consumer = _Consumer(9, manager)
    service = _service(manager, ui_dispatch=dispatch)
    service.attach_consumer(consumer)
    service.start()
    owner = service.shared_owner

    manager.complete(0, _snapshot())

    assert owner.is_running() is False
    assert owner._in_flight is False  # noqa: SLF001 - cardinality regression
    assert service.is_running() is False
    assert service.current_snapshot() is None
    assert consumer.received == []


def test_rejected_avatar_ui_dispatch_fails_closed_and_fences_source_work(
    tmp_path: Path,
):
    manager = _Manager()
    dispatch_count = 0
    image = tmp_path / "avatar.jpg"
    image.write_bytes(b"avatar")

    def dispatch(callback):
        nonlocal dispatch_count
        dispatch_count += 1
        if dispatch_count == 1:
            callback()
            return True
        return False

    def avatar_fetcher(*, cache_dir, url):
        del cache_dir, url
        from core.steam.assets import SteamAssetRecord

        return SteamAssetRecord("safe", image, image.stat().st_size, "jpg")

    consumer = _Consumer(9, manager)
    service = _service(
        manager,
        cache=lambda **_kwargs: _snapshot(
            avatar="https://avatars.steamstatic.com/safe.jpg"
        ),
        avatar_fetcher=avatar_fetcher,
        ui_dispatch=dispatch,
    )
    service.attach_consumer(consumer)
    service.start()
    owner = service.shared_owner
    manager.complete(0, manager.tasks[0][0]())
    avatar_index = next(
        index
        for index, task in enumerate(manager.tasks)
        if task[2] == "friend_pulse_avatar_hydration"
    )

    manager.complete(avatar_index, manager.tasks[avatar_index][0]())

    assert owner.is_running() is False
    assert owner._avatar_in_flight is False  # noqa: SLF001 - cardinality regression
    assert owner._in_flight is False  # noqa: SLF001 - source request was fenced
    assert service.is_running() is False
