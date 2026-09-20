"""Generation-shared Games You Follow source/lease. No QML, polling or per-display fetch.

The existing runtime manager will own one lease per admitted display; this module
owns one source and one refresh deadline per *active generation*, never one per
card. The source/worker and private identity remain outside the Qt presentation.
The family registry admits the card only while canonical Steam and member
Settings are enabled and a real retained presenter activates its lease.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import time
import weakref

from core.steam.games_followed_source import FollowedNewsSnapshot


@dataclass(frozen=True)
class FollowedRuntimeConfig:
    refresh_minutes: int

    def normalized(self) -> "FollowedRuntimeConfig":
        return FollowedRuntimeConfig(max(5, min(240, int(self.refresh_minutes))))


# A runtime generation and its worker executor jointly identify the shared owner.
# Never share snapshots across profiles, unrelated app instances or generations.
_SHARED: dict[tuple[str, object], "_FollowedOwner"] = {}


def shared_followed_owner_count() -> int:
    return len(_SHARED)


def _default_load() -> tuple[object, FollowedNewsSnapshot]:
    """Worker-only, privacy-scoped last-good read; no source request on Settings open."""
    from core.steam.credentials import read_credential_metadata
    from core.steam.games_followed_source import FollowedNewsSource
    metadata = read_credential_metadata()
    if metadata is None:
        return None, FollowedNewsSnapshot("unavailable")
    source = FollowedNewsSource(profile_key=metadata.profile_cache_key)
    return source, source.cached() or FollowedNewsSnapshot("unavailable")


def _default_schedule(delay_ms: int, callback: Callable[[], None]) -> Callable[[], None]:
    """One cancellable GUI deadline for the ACTIVE shared Steam news owner.

    Unlike an unowned single-shot closure, this one is stopped and destroyed as
    soon as the final lease retires. No timer exists while the family is off.
    """
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(True)

    def fire() -> None:
        try:
            callback()
        finally:
            timer.deleteLater()

    timer.timeout.connect(fire)
    timer.start(max(1, int(delay_ms)))

    def cancel() -> None:
        timer.stop()
        timer.deleteLater()

    return cancel


def _default_refresh(source: object) -> tuple[object, FollowedNewsSnapshot]:
    """Worker-only selected-profile refresh using the existing bounded G1 source."""
    from core.steam.credentials import load_credentials, derive_profile_cache_key
    credentials = load_credentials()
    if credentials is None:
        return None, FollowedNewsSnapshot("unavailable")
    steamid = credentials.profile_identifier
    key = derive_profile_cache_key(steamid)
    # IMPORTANT: never construct a previously unowned G1 source inside a
    # long-running refresh worker. The GUI owner must already hold this exact
    # source so final-lease retirement can fence its cache commit immediately.
    # A changed profile fails closed; the next cache-stage read binds the new
    # profile without ever delivering an old account's rows to it.
    if source is None or getattr(source, "_profile_key", None) != key:
        return None, FollowedNewsSnapshot("unavailable")
    return source, source.refresh(steamid)


class _FollowedOwner:
    """Single selected-source worker, latest accepted snapshot and refresh deadline."""

    def __init__(
        self,
        *, key: tuple[str, object], generation: object, manager: Any,
        config: FollowedRuntimeConfig,
        load: Callable[[], tuple[object, FollowedNewsSnapshot]],
        refresh: Callable[[object], tuple[object, FollowedNewsSnapshot]],
        ui_dispatch: Callable[[Callable[[], None]], object],
        schedule: Callable[[int, Callable[[], None]], object],
    ) -> None:
        self._key, self._generation, self._manager = key, generation, manager
        self._config = config.normalized()
        self._load, self._refresh = load, refresh
        self._ui_dispatch, self._schedule = ui_dispatch, schedule
        self._leases: weakref.WeakSet[FollowedRuntimeLease] = weakref.WeakSet()
        self._active: weakref.WeakSet[FollowedRuntimeLease] = weakref.WeakSet()
        self._source: object | None = None
        self._snapshot: FollowedNewsSnapshot | None = None
        self._generation_token = self._work_token = self._deadline_token = 0
        self._in_flight = self._running = self._retired = False
        self._deadline_cancel: Callable[[], None] | None = None

    @property
    def is_retired(self) -> bool:
        return self._retired

    def attach(self, lease: "FollowedRuntimeLease") -> None:
        if self._retired:
            raise RuntimeError("retired followed owner")
        self._leases.add(lease)

    def activate(self, lease: "FollowedRuntimeLease") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active.add(lease)
        if self._running:
            if self._snapshot is not None:
                lease._accept(self._snapshot)
            return True
        self._running = True
        self._generation_token += 1
        self._submit(cache_only=True)
        return True

    def deactivate(self, lease: "FollowedRuntimeLease") -> None:
        self._active.discard(lease)
        if self._active or not self._running:
            return
        self._running = False
        self._generation_token += 1
        self._work_token += 1
        self._deadline_token += 1
        self._cancel_deadline()
        self._in_flight = False
        self._snapshot = None
        self._retire_source()

    def detach(self, lease: "FollowedRuntimeLease") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        if not self._leases:
            self.retire()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._running = False
        self._generation_token += 1
        self._work_token += 1
        self._deadline_token += 1
        self._cancel_deadline()
        self._in_flight = False
        self._snapshot = None
        self._retire_source()
        for lease in tuple(self._leases):
            lease._owner = None
            lease._running = False
        self._leases.clear()
        self._active.clear()
        if _SHARED.get(self._key) is self:
            del _SHARED[self._key]

    def _cancel_deadline(self) -> None:
        cancel, self._deadline_cancel = self._deadline_cancel, None
        if cancel is not None:
            cancel()

    def _retire_source(self) -> None:
        source, self._source = self._source, None
        if source is not None:
            retire = getattr(source, "retire", None)
            if callable(retire):
                retire()  # Existing G1 source has its own narrow retirement lock.

    def request_refresh(self) -> bool:
        if not self._running or self._retired or self._in_flight:
            return False
        self._deadline_token += 1  # Supersede the old deadline when explicitly refreshing.
        self._cancel_deadline()
        self._submit(cache_only=self._source is None)
        return True

    def _submit(self, *, cache_only: bool) -> None:
        if self._in_flight or self._retired or not self._running:
            return
        self._in_flight = True
        self._work_token += 1
        token, generation = self._work_token, self._generation_token
        source = self._source

        def work() -> tuple[object, FollowedNewsSnapshot]:
            return self._load() if cache_only else self._refresh(source)

        def completed(result: object) -> None:
            value = getattr(result, "result", None) if getattr(result, "success", False) else None
            def deliver() -> None:
                self._complete(generation, token, value, cache_only=cache_only)
            deliver._srpss_runtime_generation = self._generation
            try:
                admitted = self._ui_dispatch(deliver)
            except Exception:
                admitted = False
            if admitted is False:
                # The worker cannot stop a GUI-owned QTimer or retire a source
                # on a foreign apartment. A rejected GUI dispatch means the
                # app/generation is shutting down; the established UI lifetime
                # owner will retire this lease. Leave the work slot sealed so
                # there can be no second fetch while that teardown proceeds.
                return

        work._srpss_runtime_generation = self._generation
        completed._srpss_runtime_generation = self._generation
        try:
            from core.threading.manager import TaskPriority
            self._manager.submit_io_task(
                work, callback=completed, category="steam_games_followed",
                priority=TaskPriority.LOW,
            )
        except Exception:
            self._fail_closed(generation, token)

    def _fail_closed(self, generation: int, token: int) -> None:
        if self._retired or generation != self._generation_token or token != self._work_token:
            return
        self._running = False
        self._generation_token += 1
        self._work_token += 1
        self._deadline_token += 1
        self._cancel_deadline()
        self._in_flight = False
        self._retire_source()
        for lease in tuple(self._active):
            lease._running = False
        self._active.clear()

    def _complete(self, generation: int, token: int, result: object, *, cache_only: bool) -> None:
        if (
            self._retired or not self._running or generation != self._generation_token
            or token != self._work_token or not self._in_flight
        ):
            return
        self._in_flight = False
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], FollowedNewsSnapshot):
            source, snapshot = result
            if source is not self._source:
                self._retire_source()
                self._source = source
            # Never deliver a previous profile's private snapshot after an
            # explicit identity switch or an empty linked-identity result.
            if snapshot != self._snapshot:
                self._snapshot = snapshot
                for lease in tuple(self._active):
                    lease._accept(snapshot)
        if cache_only and self._source is not None:
            # A fully covered, recent disk snapshot is a real warm start, not
            # an invitation to re-scan 142 games on each widget reactivation.
            # Resume partial sweeps immediately; an explicit user refresh may
            # still supersede this one existing generation-owned deadline.
            warm = self._snapshot
            if (warm is not None and warm.from_cache and warm.fetched_at is not None
                and warm.status in {"available", "no_usable_news", "empty_follow_list"}
                and max(warm.checked_count, warm.covered_count) >= warm.followed_count
                and 0 <= time.time() - warm.fetched_at < self._config.refresh_minutes * 60):
                remaining_ms = (15_000 if warm.maintenance_pending else max(1_000, round(
                    (self._config.refresh_minutes * 60
                     - (time.time() - warm.fetched_at)) * 1_000)))
                self._schedule_next(delay_override_ms=remaining_ms)
            else:
                self.request_refresh()
        else:
            self._schedule_next()

    def _schedule_next(self, *, delay_override_ms: int | None = None) -> None:
        if self._retired or not self._running or not self._active:
            return
        self._deadline_token += 1
        deadline_token, generation = self._deadline_token, self._generation_token
        def due() -> None:
            self._deadline_cancel = None
            if (
                not self._retired and self._running and self._active
                and generation == self._generation_token
                and deadline_token == self._deadline_token
            ):
                self.request_refresh()
        due._srpss_runtime_generation = self._generation
        # Reuse the SAME generation-owned, cancellable deadline to complete a
        # bounded followed-set sweep while the actual widget is active.
        # Four app feeds maximum per source job; no extra timer or polling owner.
        # On a failure/backoff, return to the regular interval, never spin.
        snapshot = self._snapshot
        pending_coverage = (snapshot is not None
            and snapshot.status in {"available", "no_usable_news"}
            and (0 < snapshot.covered_count < snapshot.followed_count
                 or snapshot.maintenance_pending))
        delay_ms = (delay_override_ms if delay_override_ms is not None
                    else 15_000 if pending_coverage
                    else self._config.refresh_minutes * 60_000)
        try:
            cancel = self._schedule(delay_ms, due)
            self._deadline_cancel = cancel if callable(cancel) else None
        except Exception:
            self._fail_closed(generation, self._work_token)


class FollowedRuntimeLease:
    """One display consumer, no independent source, cache, deadline or worker."""

    def __init__(
        self, *, generation: object = None, manager: Any = None,
        config: FollowedRuntimeConfig,
        load: Callable[[], tuple[object, FollowedNewsSnapshot]] = _default_load,
        refresh: Callable[[object], tuple[object, FollowedNewsSnapshot]] = _default_refresh,
        ui_dispatch: Callable[[Callable[[], None]], object] | None = None,
        schedule: Callable[[int, Callable[[], None]], object] | None = None,
    ) -> None:
        self._generation, self._manager = generation, manager
        self._config = config.normalized()
        self._load, self._refresh = load, refresh
        self._ui_dispatch, self._schedule = ui_dispatch, schedule
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _FollowedOwner | None = None
        self._running = self._retired = False

    def attach_consumer(self, consumer: object) -> None:
        if self._retired or self._consumer_ref is not None:
            raise RuntimeError("followed lease may be attached only once")
        self._consumer_ref = weakref.ref(consumer)

    def set_thread_manager(self, manager: Any, *, generation: object = None) -> None:
        if self._retired or self._running:
            raise RuntimeError("cannot change followed lease worker after activation")
        self._manager = manager
        if generation is not None:
            self._generation = generation

    def start(self) -> bool:
        if self._retired or self._manager is None or self._consumer_ref is None:
            return False
        if self._running:
            return True
        if self._owner is None:
            from core.threading.manager import ThreadManager
            key = (
                ("runtime", self._generation)
                if self._generation is not None
                else ("thread_manager", id(self._manager))
            )
            owner = _SHARED.get(key)
            if owner is None or owner.is_retired:
                owner = _FollowedOwner(
                    key=key, generation=self._generation, manager=self._manager,
                    config=self._config, load=self._load, refresh=self._refresh,
                    ui_dispatch=self._ui_dispatch or ThreadManager.run_on_ui_thread,
                    schedule=self._schedule or _default_schedule,
                )
                _SHARED[key] = owner
            self._owner = owner
            owner.attach(self)
        # A joining lease can receive the retained snapshot synchronously from
        # activate(). Mark it live before that handoff, without starting a
        # second request, timer or GUI wake for the same generation.
        self._running = True
        self._running = bool(self._owner.activate(self))
        return self._running

    def _accept(self, snapshot: FollowedNewsSnapshot) -> None:
        consumer = self._consumer_ref() if self._consumer_ref else None
        if not self._retired and self._running and consumer is not None:
            alive = getattr(consumer, "is_games_followed_consumer_alive", None)
            if callable(alive) and not alive():
                return
            accept = getattr(consumer, "on_games_followed_runtime_snapshot", None)
            if callable(accept):
                accept(snapshot)

    def request_refresh(self) -> bool:
        return bool(self._running and self._owner and self._owner.request_refresh())

    def stop(self) -> None:
        self._running = False
        if self._owner is not None:
            self._owner.deactivate(self)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.stop()
        if self._owner is not None:
            self._owner.detach(self)
        self._owner = None
        self._consumer_ref = None
        self._manager = None

    def is_retired(self) -> bool:
        return self._retired


def reset_shared_followed_runtime_for_tests() -> None:
    for owner in tuple(_SHARED.values()):
        owner.retire()
    _SHARED.clear()
