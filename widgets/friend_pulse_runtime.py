"""Shared, lease-based runtime ownership for the Friend Pulse source state.

The owner is deliberately presentation-neutral: it owns cache/source work and
one immutable accepted snapshot per runtime generation.  Per-display leases
only project that state for their own privacy policy and never start a second
Steam request cadence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import weakref
from typing import Any, Callable

from core.settings.storage_paths import get_steam_cache_dir
from core.steam.assets import SteamAssetRecord, fetch_steam_avatar
from core.steam.credentials import (
    derive_profile_cache_key,
    load_credentials,
    read_credential_metadata,
)
from core.steam.friend_pulse import (
    FriendPulseSnapshot,
    project_friend_pulse,
)
from core.steam.models import SteamResultStatus
from core.steam.friend_pulse_cache import (
    load_friend_pulse_cache_snapshot,
    refresh_friend_pulse_cache,
)
from core.threading.manager import TaskPriority, ThreadManager


@dataclass(frozen=True)
class FriendPulseRuntimeConfig:
    refresh_minutes: int = 6
    privacy_mode: str = "Rich"
    capacity: int = 4

    def normalized(self) -> "FriendPulseRuntimeConfig":
        try:
            refresh = int(self.refresh_minutes)
        except (TypeError, ValueError):
            refresh = 6
        try:
            capacity = int(self.capacity)
        except (TypeError, ValueError):
            capacity = 4
        mode = str(self.privacy_mode or "Rich").strip().title()
        return replace(
            self,
            refresh_minutes=max(5, min(240, refresh)),
            capacity=max(1, min(12, capacity)),
            privacy_mode=mode if mode in {"Strict", "Balanced", "Rich"} else "Rich",
        )


_SHARED_OWNERS: dict[tuple[str, object], "_SharedFriendPulseOwner"] = {}


def _owner_key(runtime_generation: Any, thread_manager: Any) -> tuple[str, object]:
    return (
        ("runtime", runtime_generation)
        if runtime_generation is not None
        else ("thread_manager", id(thread_manager))
    )


def shared_friend_pulse_owner_count() -> int:
    return len(_SHARED_OWNERS)


def reset_shared_friend_pulse_runtime_for_tests() -> None:
    for owner in tuple(_SHARED_OWNERS.values()):
        owner.retire()
    _SHARED_OWNERS.clear()


class _SharedFriendPulseOwner:
    def __init__(
        self,
        *,
        config: FriendPulseRuntimeConfig,
        thread_manager: Any,
        runtime_generation: Any,
        registry_key: tuple[str, object],
        cache_loader: Callable = load_friend_pulse_cache_snapshot,
        refresh_loader: Callable = refresh_friend_pulse_cache,
        credentials_loader: Callable = load_credentials,
        metadata_loader: Callable = read_credential_metadata,
        ui_dispatch: Callable = ThreadManager.run_on_ui_thread,
        scheduler: Callable = ThreadManager.single_shot,
        avatar_fetcher: Callable = fetch_steam_avatar,
        avatar_cache_dir_resolver: Callable[[str], Path] | None = None,
    ) -> None:
        self._config = config.normalized()
        self._thread_manager = thread_manager
        self._runtime_generation = runtime_generation
        self._registry_key = registry_key
        self._cache_loader, self._refresh_loader = cache_loader, refresh_loader
        self._credentials_loader, self._metadata_loader = (
            credentials_loader,
            metadata_loader,
        )
        self._ui_dispatch, self._scheduler = ui_dispatch, scheduler
        self._avatar_fetcher = avatar_fetcher
        self._avatar_cache_dir_resolver = avatar_cache_dir_resolver or (
            lambda profile_key: get_steam_cache_dir(profile_key=profile_key)
            / "friend_pulse_avatars"
        )
        self._leases: weakref.WeakSet[FriendPulseRuntimeService] = weakref.WeakSet()
        self._active: weakref.WeakSet[FriendPulseRuntimeService] = weakref.WeakSet()
        self._running = self._retired = False
        self._owner_generation = self._request_id = self._schedule_token = 0
        self._in_flight = False
        self._snapshot: FriendPulseSnapshot | None = None
        self._snapshot_revision = self._avatar_epoch = 0
        self._avatar_in_flight = False
        self._avatar_request_id = 0
        self._avatar_sources: dict[str, str] = {}
        self._avatar_source_urls: dict[str, str] = {}
        self._friend_steam_ids: dict[str, str] = {}
        self._profile_key: str | None = None

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    @property
    def owner_generation(self) -> int:
        return self._owner_generation

    @property
    def snapshot(self) -> FriendPulseSnapshot | None:
        return self._snapshot

    def attach(self, lease: "FriendPulseRuntimeService") -> None:
        if self._retired:
            raise RuntimeError("cannot attach to retired Friend Pulse owner")
        self._leases.add(lease)
        self.configure_refresh_minutes(lease.config.refresh_minutes)

    def configure_refresh_minutes(self, refresh_minutes: int) -> None:
        """Apply the one canonical Steam cadence to this shared owner."""

        normalized = FriendPulseRuntimeConfig(
            refresh_minutes=refresh_minutes
        ).normalized().refresh_minutes
        if normalized == self._config.refresh_minutes:
            return
        self._config = replace(self._config, refresh_minutes=normalized)
        if not self._running:
            return
        # Invalidate an already queued deadline.  An in-flight completion will
        # schedule from its completion edge using the new interval; otherwise
        # establish the replacement deadline now.
        self._schedule_token += 1
        if not self._in_flight:
            self._schedule_next()

    def detach(self, lease: "FriendPulseRuntimeService") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not self._leases:
            self.retire()

    def activate(self, lease: "FriendPulseRuntimeService") -> bool:
        if self._retired or lease not in self._leases or self._thread_manager is None:
            return False
        self._active.add(lease)
        if self._running:
            if self._snapshot is not None:
                lease._deliver(self._snapshot)
                self.request_avatar_hydration()
            return True
        self._running = True
        self._owner_generation += 1
        self._schedule_token += 1
        self._submit_cache_load()
        return True

    def deactivate(self, lease: "FriendPulseRuntimeService") -> None:
        self._active.discard(lease)
        if self._active or not self._running:
            return
        self._running = False
        self._owner_generation += 1
        self._schedule_token += 1
        self._in_flight = False
        self._avatar_in_flight = False
        self._avatar_request_id += 1
        self._avatar_epoch += 1
        self._snapshot = None  # comparison history/state dies with the last lease
        self._avatar_sources.clear()
        self._avatar_source_urls.clear()
        self._friend_steam_ids.clear()

    def retire(self) -> None:
        if self._retired:
            return
        self._running = False
        self._retired = True
        self._owner_generation += 1
        self._schedule_token += 1
        self._in_flight = False
        self._avatar_in_flight = False
        self._avatar_request_id += 1
        self._avatar_epoch += 1
        self._snapshot = None
        self._avatar_sources.clear()
        self._avatar_source_urls.clear()
        self._friend_steam_ids.clear()
        self._active.clear()
        self._leases.clear()
        if _SHARED_OWNERS.get(self._registry_key) is self:
            _SHARED_OWNERS.pop(self._registry_key, None)

    def refresh(self) -> bool:
        if self._retired or not self._running or self._in_flight:
            return False
        self._submit_refresh()
        return True

    def _submit_cache_load(self) -> None:
        self._submit_work("friend_pulse_cache_load", self._cache_worker)

    def _submit_refresh(self) -> None:
        self._submit_work("friend_pulse_refresh", self._refresh_worker)

    def _submit_work(
        self, category: str, worker: Callable[[], FriendPulseSnapshot | None]
    ) -> None:
        if self._retired or not self._running or self._in_flight:
            return
        self._in_flight = True
        self._request_id += 1
        request_id, owner_generation = self._request_id, self._owner_generation

        def completed(result: Any) -> None:
            snapshot = (
                getattr(result, "result", None)
                if getattr(result, "success", False)
                else None
            )

            def deliver() -> None:
                self._complete(
                    owner_generation,
                    request_id,
                    snapshot,
                    completed_refresh=(category == "friend_pulse_refresh"),
                )

            deliver._srpss_runtime_generation = self._runtime_generation
            try:
                dispatched = self._ui_dispatch(deliver)
            except Exception:
                dispatched = False
            if dispatched is False:
                self._fail_closed_ui_dispatch(
                    owner_generation,
                    request_id=request_id,
                )

        # Bound methods cannot carry runtime metadata themselves.  Keep the
        # worker closure generation-tagged so ThreadManager can reject it once
        # the owning Quick generation has retired.
        def tagged_worker() -> FriendPulseSnapshot | None:
            return worker()

        tagged_worker._srpss_runtime_generation = self._runtime_generation
        completed._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(
                tagged_worker,
                callback=completed,
                category=category,
                priority=TaskPriority.LOW,
            )
        except Exception:
            self._complete(
                owner_generation,
                request_id,
                None,
                completed_refresh=(category == "friend_pulse_refresh"),
            )

    def _cache_worker(self) -> FriendPulseSnapshot | None:
        metadata = self._metadata_loader()
        if metadata is None:
            return FriendPulseSnapshot(status=SteamResultStatus.NOT_CONFIGURED)
        self._profile_key = metadata.profile_cache_key
        return self._cache_loader(profile_key=metadata.profile_cache_key, previous=None)

    def _refresh_worker(self) -> FriendPulseSnapshot | None:
        credential = self._credentials_loader()
        if credential is None:
            return FriendPulseSnapshot(status=SteamResultStatus.NOT_CONFIGURED)
        profile_identifier = getattr(credential, "profile_identifier", None)
        if isinstance(profile_identifier, str) and profile_identifier.strip():
            self._profile_key = derive_profile_cache_key(profile_identifier)
        return self._refresh_loader(
            credential=credential,
            previous=self._snapshot,
            force=True,
        )

    def _complete(
        self,
        owner_generation: int,
        request_id: int,
        snapshot: FriendPulseSnapshot | None,
        *,
        completed_refresh: bool,
    ) -> None:
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or request_id != self._request_id
        ):
            return
        self._in_flight = False
        action_targets_changed = False
        if snapshot is not None:
            friend_steam_ids = {
                entry.identity_fingerprint: entry.steam_id
                for entry in snapshot.entries
                if entry.steam_id
            }
            snapshot = replace(
                snapshot,
                entries=tuple(
                    replace(entry, steam_id=None) for entry in snapshot.entries
                ),
            )
            action_targets_changed = friend_steam_ids != self._friend_steam_ids
            self._friend_steam_ids = friend_steam_ids
        snapshot_changed = snapshot is not None and snapshot != self._snapshot
        if snapshot is not None and (snapshot_changed or action_targets_changed):
            if snapshot_changed:
                accepted_avatar_urls = {
                    entry.identity_fingerprint: entry.avatar_url
                    for entry in snapshot.entries
                    if entry.avatar_url
                }
                self._avatar_sources = {
                    fingerprint: source
                    for fingerprint, source in self._avatar_sources.items()
                    if self._avatar_source_urls.get(fingerprint)
                    == accepted_avatar_urls.get(fingerprint)
                }
                self._avatar_source_urls = {
                    fingerprint: accepted_avatar_urls[fingerprint]
                    for fingerprint in self._avatar_sources
                }
                self._snapshot = snapshot
                self._snapshot_revision += 1
                self._avatar_epoch += 1
            for lease in tuple(self._active):
                lease._deliver(snapshot)
            if snapshot_changed:
                self.request_avatar_hydration()
        if completed_refresh:
            self._schedule_next()
        elif self._running:
            # Cache-first startup is an immediate display opportunity, not a
            # refresh delay.  The credentialed refresh remains source-owned and
            # starts only after this cache worker has completed.
            self._submit_refresh()

    def request_avatar_hydration(self) -> None:
        """Hydrate the union of visible Rich rows once for every source state."""

        snapshot = self._snapshot
        if (
            self._retired
            or not self._running
            or snapshot is None
            or self._avatar_in_flight
            or not self._profile_key
        ):
            return
        wanted: list[tuple[str, str]] = []
        for lease in tuple(self._active):
            if not lease._wants_rich_avatars():
                continue
            for entry in snapshot.entries[: lease.config.capacity]:
                candidate = (entry.identity_fingerprint, entry.avatar_url)
                if (
                    entry.avatar_url
                    and entry.identity_fingerprint not in self._avatar_sources
                    and candidate not in wanted
                ):
                    wanted.append(candidate)
        if not wanted:
            return
        self._avatar_in_flight = True
        self._avatar_request_id += 1
        avatar_request_id = self._avatar_request_id
        owner_generation, revision, epoch = (
            self._owner_generation,
            self._snapshot_revision,
            self._avatar_epoch,
        )
        profile_key = self._profile_key
        requested_urls = dict(wanted)

        def worker() -> dict[str, str]:
            cache_dir = self._avatar_cache_dir_resolver(profile_key)
            resolved: dict[str, str] = {}
            for fingerprint, url in wanted:
                result = self._avatar_fetcher(cache_dir=cache_dir, url=url)
                if isinstance(result, SteamAssetRecord):
                    resolved[fingerprint] = result.path.resolve().as_uri()
            return resolved

        def completed(result: Any) -> None:
            resolved = (
                getattr(result, "result", {})
                if getattr(result, "success", False)
                else {}
            )

            def deliver() -> None:
                self._complete_avatars(
                    avatar_request_id,
                    owner_generation,
                    revision,
                    epoch,
                    resolved,
                    requested_urls,
                )

            deliver._srpss_runtime_generation = self._runtime_generation
            try:
                dispatched = self._ui_dispatch(deliver)
            except Exception:
                dispatched = False
            if dispatched is False:
                self._fail_closed_ui_dispatch(
                    owner_generation,
                    avatar_request_id=avatar_request_id,
                )

        worker._srpss_runtime_generation = self._runtime_generation
        completed._srpss_runtime_generation = self._runtime_generation
        try:
            self._thread_manager.submit_io_task(
                worker,
                callback=completed,
                category="friend_pulse_avatar_hydration",
                priority=TaskPriority.LOW,
            )
        except Exception:
            self._avatar_in_flight = False

    def _complete_avatars(
        self,
        avatar_request_id: int,
        owner_generation: int,
        revision: int,
        epoch: int,
        resolved: object,
        requested_urls: object | None = None,
    ) -> None:
        if avatar_request_id != self._avatar_request_id:
            return
        self._avatar_in_flight = False
        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
        ):
            return
        if revision != self._snapshot_revision or epoch != self._avatar_epoch:
            self.request_avatar_hydration()
            return
        if not isinstance(resolved, dict):
            return
        current_urls = {
            entry.identity_fingerprint: entry.avatar_url
            for entry in (self._snapshot.entries if self._snapshot else ())
            if entry.avatar_url
        }
        source_urls = requested_urls if isinstance(requested_urls, dict) else current_urls
        valid = {
            str(key): str(value)
            for key, value in resolved.items()
            if str(value).startswith("file:")
            and str(source_urls.get(str(key), ""))
            == current_urls.get(str(key))
        }
        changed = {
            key: value
            for key, value in valid.items()
            if self._avatar_sources.get(key) != value
            or self._avatar_source_urls.get(key) != current_urls.get(key)
        }
        if not changed:
            return
        self._avatar_sources.update(changed)
        self._avatar_source_urls.update(
            {key: current_urls[key] for key in changed if key in current_urls}
        )
        if self._snapshot is not None:
            for lease in tuple(self._active):
                if lease._wants_rich_avatars():
                    lease._deliver(self._snapshot)

    def _fail_closed_ui_dispatch(
        self,
        owner_generation: int,
        *,
        request_id: int | None = None,
        avatar_request_id: int | None = None,
    ) -> None:
        """Fence all work when the owning UI generation rejects publication."""

        if (
            self._retired
            or not self._running
            or owner_generation != self._owner_generation
            or (request_id is not None and request_id != self._request_id)
            or (
                avatar_request_id is not None
                and avatar_request_id != self._avatar_request_id
            )
        ):
            return
        self._running = False
        self._owner_generation += 1
        self._request_id += 1
        self._schedule_token += 1
        self._in_flight = False
        self._avatar_in_flight = False
        self._avatar_request_id += 1
        self._avatar_epoch += 1
        self._snapshot = None
        self._avatar_sources.clear()
        self._avatar_source_urls.clear()
        self._friend_steam_ids.clear()
        for lease in tuple(self._active):
            lease._running = False

    def _schedule_next(self) -> None:
        if self._retired or not self._running or not self._active:
            return
        self._schedule_token += 1
        token, generation = self._schedule_token, self._owner_generation

        def due() -> None:
            if (
                self._retired
                or not self._running
                or token != self._schedule_token
                or generation != self._owner_generation
            ):
                return
            if not self._in_flight:
                self._submit_refresh()

        due._srpss_runtime_generation = self._runtime_generation
        self._scheduler(self._config.refresh_minutes * 60_000, due)


class FriendPulseRuntimeService:
    """Per-display lease joining one generation-scoped neutral owner."""

    def __init__(
        self,
        *,
        config: FriendPulseRuntimeConfig | None = None,
        runtime_generation: Any = None,
        cache_loader: Callable = load_friend_pulse_cache_snapshot,
        refresh_loader: Callable = refresh_friend_pulse_cache,
        credentials_loader: Callable = load_credentials,
        metadata_loader: Callable = read_credential_metadata,
        ui_dispatch: Callable = ThreadManager.run_on_ui_thread,
        scheduler: Callable = ThreadManager.single_shot,
        avatar_fetcher: Callable = fetch_steam_avatar,
        avatar_cache_dir_resolver: Callable[[str], Path] | None = None,
    ) -> None:
        self._config = (config or FriendPulseRuntimeConfig()).normalized()
        self._runtime_generation = runtime_generation
        self._thread_manager: Any = None
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _SharedFriendPulseOwner | None = None
        self._running = self._retired = False
        self._seams = (
            cache_loader,
            refresh_loader,
            credentials_loader,
            metadata_loader,
            ui_dispatch,
            scheduler,
            avatar_fetcher,
            avatar_cache_dir_resolver,
        )

    @property
    def shared_owner(self) -> _SharedFriendPulseOwner | None:
        return self._owner

    @property
    def runtime_generation(self) -> Any:
        return self._runtime_generation

    def is_retired(self) -> bool:
        return self._retired

    def is_running(self) -> bool:
        return self._running and self._owner is not None and self._owner.is_running()

    def current_snapshot(self) -> FriendPulseSnapshot | None:
        return self._owner.snapshot if self._owner else None

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach to retired Friend Pulse lease")
        current = self._consumer_ref() if self._consumer_ref is not None else None
        if current is not None and current is not consumer:
            raise RuntimeError("Friend Pulse lease already belongs to another consumer")
        if self._owner is not None:
            return
        self._consumer_ref = weakref.ref(consumer)
        if self._runtime_generation is None:
            self._runtime_generation = getattr(consumer, "_runtime_generation", None)
        if self._thread_manager is None:
            self._thread_manager = getattr(consumer, "_thread_manager", None)
        if self._runtime_generation is None and self._thread_manager is None:
            raise RuntimeError(
                "Friend Pulse lease requires runtime generation or ThreadManager"
            )
        key = _owner_key(self._runtime_generation, self._thread_manager)
        owner = _SHARED_OWNERS.get(key)
        if owner is None or owner.is_retired():
            owner = _SharedFriendPulseOwner(
                config=self._config,
                thread_manager=self._thread_manager,
                runtime_generation=self._runtime_generation,
                registry_key=key,
                cache_loader=self._seams[0],
                refresh_loader=self._seams[1],
                credentials_loader=self._seams[2],
                metadata_loader=self._seams[3],
                ui_dispatch=self._seams[4],
                scheduler=self._seams[5],
                avatar_fetcher=self._seams[6],
                avatar_cache_dir_resolver=self._seams[7],
            )
            _SHARED_OWNERS[key] = owner
        self._owner = owner
        owner.attach(self)

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer_ref() if self._consumer_ref is not None else None
        if consumer is not None and current is not consumer:
            return
        owner = self._owner
        if owner is not None:
            owner.detach(self)
        self._owner = None
        self._consumer_ref = None
        self._running = False

    def start(self) -> bool:
        if self._retired or self._owner is None:
            return False
        self._running = self._owner.activate(self)
        return self._running

    def stop(self) -> None:
        self._running = False
        if self._owner:
            self._owner.deactivate(self)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.detach_consumer()
        self._thread_manager = None

    def refresh(self) -> bool:
        return bool(self._owner and self._owner.refresh())

    def friend_steam_id(self, identity_fingerprint: str) -> str | None:
        if not self.is_running() or self._owner is None:
            return None
        return self._owner._friend_steam_ids.get(str(identity_fingerprint or ""))

    def configure(self, config: FriendPulseRuntimeConfig) -> None:
        self._config = config.normalized()
        if self._owner is not None:
            self._owner.configure_refresh_minutes(self._config.refresh_minutes)
        snapshot = self.current_snapshot()
        if snapshot is not None:
            self._deliver(snapshot)
        if self._owner is not None:
            self._owner.request_avatar_hydration()

    @property
    def config(self) -> FriendPulseRuntimeConfig:
        return self._config

    def _wants_rich_avatars(self) -> bool:
        return self._config.privacy_mode == "Rich"

    def _consumer_alive(self) -> bool:
        consumer = self._consumer_ref() if self._consumer_ref else None
        return bool(
            consumer
            and getattr(consumer, "is_friend_pulse_consumer_alive", lambda: False)()
        )

    def _deliver(self, snapshot: FriendPulseSnapshot) -> None:
        consumer = self._consumer_ref() if self._consumer_ref else None
        if not self._running or not self._consumer_alive() or consumer is None:
            return
        consumer.on_friend_pulse_runtime_snapshot(
            snapshot,
            project_friend_pulse(
                snapshot,
                privacy_mode=self._config.privacy_mode,
                capacity=self._config.capacity,
                avatar_sources=(self._owner._avatar_sources if self._owner else {}),
                friend_action_identities=(
                    self._owner._friend_steam_ids.keys() if self._owner else ()
                ),
            ),
        )
