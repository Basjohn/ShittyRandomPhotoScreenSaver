"""Generation-shared runtime coordinator for general Feed widgets.

One active runtime generation owns one coordinator, one earliest-due timer and
bounded source jobs. Individual retained cards hold lightweight leases only.
There is no per-widget polling timer, no QML network work and no source owner
while the Feeds family is dormant.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import Event
import time
import weakref
from typing import Any, Callable

from core.feeds.config import CustomFeedConfig
from core.feeds.models import FeedRefreshResult, FeedSourceSpec
from core.feeds.news import NewsFeedConfig, NewsProvider, merge_news_results


@dataclass(frozen=True)
class FeedRuntimeConfig:
    widget_id: str
    source_spec: FeedSourceSpec
    refresh_minutes: int
    show_images: bool
    view_mode: str
    # Rows the card can show; only these stories' artwork is warmed.
    item_limit: int

    @classmethod
    def from_custom(cls, config: CustomFeedConfig) -> "FeedRuntimeConfig":
        return cls(
            widget_id=config.widget_id,
            source_spec=config.source_spec(),
            refresh_minutes=max(5, min(24 * 60, int(config.refresh_minutes))),
            show_images=bool(config.show_images),
            view_mode=config.view_mode,
            item_limit=int(config.item_limit),
        )


@dataclass
class _SourceState:
    spec: FeedSourceSpec
    refresh_minutes: int
    source: object | None = None
    last_result: FeedRefreshResult | None = None
    in_flight: bool = False
    work_token: int = 0
    work_cancel: Event = field(default_factory=Event)
    due_at: float = 0.0
    artwork_attempted_at: float | None = None
    # Leading stories covered by the last artwork job (see _artwork_limit).
    artwork_item_limit: int = 0


_SHARED: dict[tuple[str, object], "_FeedFamilyOwner"] = {}


def shared_feed_owner_count() -> int:
    return len(_SHARED)


def _default_schedule(delay_ms: int, callback: Callable[[], None]) -> Callable[[], bool]:
    """One generation-owned deadline in the shared single-shot registry."""

    from core.threading.manager import ThreadManager

    return ThreadManager.single_shot(max(1, int(delay_ms)), callback).cancel


class _FeedFamilyOwner:
    def __init__(
        self,
        *,
        key: tuple[str, object],
        generation: object,
        manager: Any,
        ui_dispatch: Callable[[Callable[[], None]], object],
        schedule: Callable[[int, Callable[[], None]], object],
        task_priority: object,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._key = key
        self._generation = generation
        self._manager = manager
        self._ui_dispatch = ui_dispatch
        self._schedule = schedule
        self._task_priority = task_priority
        self._now = now
        self._leases: weakref.WeakSet[FeedRuntimeLease] = weakref.WeakSet()
        self._active: weakref.WeakSet[FeedRuntimeLease] = weakref.WeakSet()
        self._states: dict[str, _SourceState] = {}
        self._deadline_cancel: Callable[[], None] | None = None
        self._deadline_token = 0
        self._retired = False
        # Every local image currently published by any source of this owner.
        # Replaced whole on the GUI thread; artwork workers read it when they
        # evict, so a source that publishes meanwhile is protected too.
        self._published_artwork: frozenset[str] = frozenset()

    def _refresh_published_artwork(self) -> None:
        self._published_artwork = frozenset(
            uri for state in self._states.values() if state.last_result is not None
            for _item_id, uri in state.last_result.local_artwork_by_item)

    @property
    def is_retired(self) -> bool:
        return self._retired

    def attach(self, lease: "FeedRuntimeLease") -> None:
        if self._retired:
            raise RuntimeError("retired Feed owner")
        self._leases.add(lease)

    @staticmethod
    def _same_acquisition_spec(left: FeedSourceSpec, right: FeedSourceSpec) -> bool:
        return (
            left.source_id == right.source_id
            and left.url == right.url
            and left.cache_key == right.cache_key
            and left.max_items == right.max_items
            and left.allow_endpoint_migration == right.allow_endpoint_migration
        )

    @staticmethod
    def _release_source(state: _SourceState) -> None:
        source, state.source = state.source, None
        transport = getattr(source, "transport", None) if source is not None else None
        close = getattr(transport, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _release_source_if_idle(self, state: _SourceState) -> None:
        if state.in_flight or self._active_leases_for_state(state):
            return
        self._release_source(state)
        # A retired endpoint must not remain in a still-active family owner.
        # An inactive but attached lease retains its immutable last-good result
        # for cache-first reactivation without opening an HTTP transport.
        if not any(lease.config.source_spec.cache_key == state.spec.cache_key
                   for lease in self._leases):
            if self._states.get(state.spec.cache_key) is state:
                del self._states[state.spec.cache_key]
                self._refresh_published_artwork()

    def _state_for(self, lease: "FeedRuntimeLease") -> _SourceState:
        config = lease.config
        key = config.source_spec.cache_key
        state = self._states.get(key)
        if state is None:
            state = _SourceState(config.source_spec, config.refresh_minutes)
            self._states[key] = state
        elif not self._same_acquisition_spec(state.spec, config.source_spec):
            # CUSTOM cache identity includes the endpoint fingerprint. A changed
            # endpoint therefore cannot silently reuse the old state object.
            self._release_source(state)
            state = _SourceState(config.source_spec, config.refresh_minutes)
            self._states[key] = state
        return state

    def _recompute_state_cadence(self, state: _SourceState) -> None:
        """Derive one source cadence from *currently active* leases only.

        A short-lived fast consumer must not permanently ratchet a shared source
        to that interval after it is hidden or retired.  Cadence is therefore a
        projection of active lease policy, never accumulated mutable history.
        """
        active = self._active_leases_for_state(state)
        if not active:
            return
        refresh_minutes = min(lease.config.refresh_minutes for lease in active)
        if refresh_minutes == state.refresh_minutes:
            return
        state.refresh_minutes = refresh_minutes
        if state.last_result is not None:
            self._update_due(state, state.last_result)

    def activate(self, lease: "FeedRuntimeLease") -> bool:
        if self._retired or lease not in self._leases:
            return False
        self._active.add(lease)
        state = self._state_for(lease)
        self._recompute_state_cadence(state)
        if state.last_result is not None:
            lease._accept(state.last_result, from_cache=False)
        if not state.in_flight:
            if state.last_result is None:
                # First admission needs one bounded disk read. Once a source has
                # an accepted in-memory result, later visibility/reactivation
                # must not reread the same cache merely to recreate an HTTP
                # object; network state is constructed only when actually due.
                self._submit(state, cache_only=True, force=False)
            else:
                # Reactivation is an event: resume an interrupted optional
                # artwork batch only if this accepted snapshot still needs it.
                # A due feed refresh takes precedence over an artwork job.
                if state.due_at <= self._now() + 0.001:
                    self._admit_due_work()
                elif self._artwork_needed(state):
                    state.artwork_attempted_at = state.last_result.snapshot.fetched_at
                    self._submit(state, cache_only=False, force=False, artwork_only=True)
        self._reschedule()
        return True

    def deactivate(self, lease: "FeedRuntimeLease") -> None:
        self._active.discard(lease)
        state = self._states.get(lease.config.source_spec.cache_key)
        if state is not None:
            if not self._active_leases_for_state(state):
                # The cancellation token belongs to this endpoint's current
                # job, not the whole generation or another active source.
                state.work_cancel.set()
            self._recompute_state_cadence(state)
            self._release_source_if_idle(state)
        if not self._active:
            self._cancel_deadline()
        else:
            self._reschedule()

    def detach(self, lease: "FeedRuntimeLease") -> None:
        self.deactivate(lease)
        self._leases.discard(lease)
        state = self._states.get(lease.config.source_spec.cache_key)
        if state is not None:
            self._release_source_if_idle(state)
        if not self._leases:
            self.retire()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._deadline_token += 1
        self._cancel_deadline()
        for state in self._states.values():
            state.work_cancel.set()
            state.work_token += 1
            was_in_flight = state.in_flight
            state.in_flight = False
            # Never close a requests.Session from the GUI while its worker is
            # inside iter_content(); the completion callback closes it instead.
            if not was_in_flight:
                self._release_source(state)
        self._states.clear()
        for lease in tuple(self._leases):
            lease._owner = None
            lease._running = False
        self._active.clear()
        self._leases.clear()
        if _SHARED.get(self._key) is self:
            del _SHARED[self._key]

    def _cancel_deadline(self) -> None:
        cancel, self._deadline_cancel = self._deadline_cancel, None
        if cancel is not None:
            cancel()

    def _active_leases_for_state(self, state: _SourceState) -> tuple["FeedRuntimeLease", ...]:
        key = state.spec.cache_key
        return tuple(
            lease
            for lease in self._active
            if lease.config.source_spec.cache_key == key and lease._running
        )

    def request_refresh(self, lease: "FeedRuntimeLease") -> bool:
        if self._retired or lease not in self._active:
            return False
        state = self._state_for(lease)
        self._recompute_state_cadence(state)
        if state.in_flight:
            return False
        state.due_at = 0.0
        self._cancel_deadline()
        self._submit(state, cache_only=False, force=True)
        return True

    def _source_for(self, state: _SourceState):
        if state.source is None:
            from core.feeds.source import FeedSource

            owner_ref = weakref.ref(self)

            # Only one job per state can run at a time. The callback reads the
            # current per-job event so a retained HTTP session also honors
            # cancellation on later refreshes after an ordinary cache hit.
            def _still_needed() -> bool:
                owner = owner_ref()
                return bool(owner is not None and not owner._retired
                            and not state.work_cancel.is_set())

            def _make_transport():
                from core.feeds.transport import FeedHttpTransport
                return FeedHttpTransport(should_continue=_still_needed)

            state.source = FeedSource(
                state.spec, transport_factory=_make_transport,
                should_continue=_still_needed,
            )
        return state.source

    def _artwork_limit(self, state: _SourceState) -> int:
        """Leading stories whose artwork any active image-showing card can show.

        Rows past a card's item limit never show art, so they are never warmed
        or published. That keeps each source's protected artwork within its
        cards' limits, which keeps the shared cache near its bounds as NEWS
        adds publishers.
        """
        return max(
            (lease.config.item_limit for lease in self._active_leases_for_state(state)
             if lease.config.show_images and lease.config.view_mode != "compact"),
            default=0,
        )

    def _artwork_needed(self, state: _SourceState) -> bool:
        snapshot = state.last_result.snapshot if state.last_result is not None else None
        limit = self._artwork_limit(state)
        return bool(
            snapshot is not None
            and limit > 0
            and (state.artwork_attempted_at != snapshot.fetched_at
                 # A card with a larger limit joined an already-warmed source.
                 or limit > state.artwork_item_limit)
            and any(item.images for item in snapshot.document.items[:limit])
        )

    @staticmethod
    def _warm_artwork(
        result: FeedRefreshResult, *, cancel: Event,
        protected: Callable[[], frozenset[str]], item_limit: int,
    ) -> FeedRefreshResult:
        """One event-admitted follow-on job, never a per-image timer/owner.

        The main source response has already been published cache-first. Optional
        imagery runs on the SAME bounded family IO lane, and emits only one
        complete result at the end. All four attempts share one wall-clock cap.
        """
        snapshot = result.snapshot
        if snapshot is None:
            return result
        from core.feeds.artwork import ArtworkCancelled, FeedArtworkCache
        from core.feeds.artwork_transport import ArtworkFetchError, fetch_artwork_bytes
        from core.settings.storage_paths import detect_current_profile, get_feed_cache_dir
        cache = FeedArtworkCache(get_feed_cache_dir(detect_current_profile()) / "artwork")
        deadline = time.monotonic() + 8.0
        def needed() -> bool:
            return not cancel.is_set()
        def fetch(url: str) -> bytes:
            if not needed():
                raise ArtworkCancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0.1:
                raise ArtworkFetchError("shared artwork deadline exhausted")
            return fetch_artwork_bytes(url, still_needed=needed,
                                       max_seconds=min(7.5, remaining))
        try:
            warm = cache.warm(snapshot.document.items[:max(1, int(item_limit))], fetch_bytes=fetch,
                              still_needed=needed, protected_sources=protected)
        except ArtworkCancelled:
            raise
        except (OSError, ValueError):
            return result  # Images cannot invalidate established article text.
        return replace(result, local_artwork_by_item=tuple(warm.local_by_item.items()))

    def _submit(self, state: _SourceState, *, cache_only: bool, force: bool,
                artwork_only: bool = False) -> None:
        if self._retired or state.in_flight or not self._active_leases_for_state(state):
            return
        state.in_flight = True
        state.work_cancel = Event()
        state.work_token += 1
        token = state.work_token
        cancel = state.work_cancel
        cache_key = state.spec.cache_key
        owner_ref = weakref.ref(self)
        base_artwork_result = state.last_result if artwork_only else None
        artwork_limit = self._artwork_limit(state) if artwork_only else 0
        if artwork_only:
            state.artwork_item_limit = artwork_limit
        # Eviction protection is read when the worker prunes, from the owner's
        # immutable published set (replaced whole on the GUI thread): never a
        # submit-time copy that misses another source publishing meanwhile,
        # and never a worker read of mutable family/lease state.

        def protected() -> frozenset[str]:
            owner = owner_ref()
            return owner._published_artwork if owner is not None else frozenset()

        def _work() -> FeedRefreshResult:
            owner = owner_ref()
            if owner is None or owner._retired or cancel.is_set():
                raise RuntimeError("feed source no longer active")
            if artwork_only:
                if base_artwork_result is None:
                    raise RuntimeError("missing accepted feed artwork source")
                return owner._warm_artwork(base_artwork_result, cancel=cancel,
                                           protected=protected, item_limit=artwork_limit)
            source = owner._source_for(state)
            return source.load_cached() if cache_only else source.refresh(force=force)

        _work._srpss_runtime_generation = self._generation

        def _completed(task_result: object) -> None:
            result = (
                getattr(task_result, "result", None)
                if getattr(task_result, "success", False)
                else None
            )
            owner = owner_ref()
            if owner is None or owner._retired:
                # Completion runs only after the worker returns. An obsolete
                # session can now be closed without racing its HTTP read.
                _FeedFamilyOwner._release_source(state)
                return

            def _deliver() -> None:
                owner = owner_ref()
                if owner is None or owner._retired:
                    _FeedFamilyOwner._release_source(state)
                else:
                    owner._complete(cache_key, state, token, cancel, result,
                                    cache_only=cache_only, artwork_only=artwork_only)

            _deliver._srpss_runtime_generation = self._generation
            try:
                self._ui_dispatch(_deliver)
            except Exception:
                return

        _completed._srpss_runtime_generation = self._generation
        try:
            self._manager.submit_io_task(
                _work,
                callback=_completed,
                category="feeds",
                priority=self._task_priority,
            )
        except Exception:
            state.in_flight = False
            state.due_at = self._now() + 60.0
            self._reschedule()

    def _complete(
        self,
        cache_key: str,
        submitted_state: _SourceState,
        token: int,
        cancel: Event,
        result: object,
        *,
        cache_only: bool,
        artwork_only: bool = False,
    ) -> None:
        if self._retired:
            return
        state = self._states.get(cache_key)
        if (state is not submitted_state or token != state.work_token
            or not state.in_flight):
            self._release_source(submitted_state)
            return
        state.in_flight = False
        if cancel.is_set():
            # An interrupted artwork batch is not a completed attempt. Its
            # next admitted consumer may resume via activation, not a timer.
            if artwork_only:
                state.artwork_attempted_at = None
                state.artwork_item_limit = 0
            # Reattached consumers must get fresh work; no canceled result may
            # publish or persist a synthetic network failure/backoff.
            self._release_source(state)
            if self._active_leases_for_state(state):
                if state.last_result is None:
                    self._submit(state, cache_only=True, force=False)
                else:
                    self._update_due(state, state.last_result)
                    self._admit_due_work()
            else:
                self._release_source_if_idle(state)
            self._reschedule()
            return
        if isinstance(result, FeedRefreshResult):
            previous = state.last_result
            # An unchanged conditional response keeps already-admitted local art
            # until a new grouped artwork generation is ready.
            if (not artwork_only and previous is not None and result.snapshot is not None
                and previous.snapshot is not None
                and previous.snapshot.document == result.snapshot.document
                and previous.local_artwork_by_item):
                result = replace(result, local_artwork_by_item=previous.local_artwork_by_item)
            state.last_result = result
            self._refresh_published_artwork()
            if not artwork_only and not cache_only:
                # A 304 or an identical ordinary refresh must not reissue the
                # same optional image requests at every source cadence. Only a
                # changed document is eligible for another artwork batch.
                if (previous is not None and previous.snapshot is not None
                    and result.snapshot is not None
                    and previous.snapshot.document == result.snapshot.document
                    and state.artwork_attempted_at is not None):
                    state.artwork_attempted_at = result.snapshot.fetched_at
                else:
                    state.artwork_attempted_at = None
            for lease in self._active_leases_for_state(state):
                lease._accept(result, from_cache=cache_only)
            if not artwork_only:
                self._update_due(state, result)
        elif not artwork_only:
            state.due_at = self._now() + 60.0

        if cache_only and self._active_leases_for_state(state) and state.due_at <= self._now() + 0.001:
            # Publish last-good text first; fetch due source before its imagery.
            self._submit(state, cache_only=False, force=False)
        elif not artwork_only and self._artwork_needed(state):
            snapshot = state.last_result.snapshot
            state.artwork_attempted_at = snapshot.fetched_at
            self._submit(state, cache_only=False, force=False, artwork_only=True)
        self._release_source_if_idle(state)
        self._reschedule()

    def _update_due(self, state: _SourceState, result: FeedRefreshResult) -> None:
        now = self._now()
        health = result.health
        if health.backoff_until is not None and health.backoff_until > now:
            state.due_at = float(health.backoff_until)
            return
        success = health.last_success_at
        if success is not None:
            state.due_at = max(now, float(success) + state.refresh_minutes * 60.0)
            return
        # Cache-first startup with no accepted snapshot must proceed directly to
        # one bounded network refresh. Real network/parse failures are persisted
        # by FeedSource with an explicit backoff_until above, so immediate here
        # cannot spin and avoids leaving a brand-new feed blank for one whole
        # refresh interval.
        state.due_at = now

    def _admit_due_work(self) -> None:
        now = self._now()
        for state in tuple(self._states.values()):
            if (
                not state.in_flight
                and self._active_leases_for_state(state)
                and state.due_at <= now
            ):
                self._submit(state, cache_only=False, force=False)

    def _reschedule(self) -> None:
        self._cancel_deadline()
        if self._retired or not self._active:
            return
        candidates = [
            state.due_at
            for state in self._states.values()
            if self._active_leases_for_state(state) and not state.in_flight and state.due_at > 0
        ]
        if not candidates:
            return
        due_at = min(candidates)
        delay_ms = max(1, int(round(max(0.001, due_at - self._now()) * 1000.0)))
        self._deadline_token += 1
        token = self._deadline_token
        owner_ref = weakref.ref(self)

        def _due() -> None:
            owner = owner_ref()
            if owner is None or owner._retired or token != owner._deadline_token:
                return
            owner._deadline_cancel = None
            owner._admit_due_work()
            owner._reschedule()

        _due._srpss_runtime_generation = self._generation
        cancel = self._schedule(delay_ms, _due)
        self._deadline_cancel = cancel if callable(cancel) else None


class FeedRuntimeLease:
    """One retained feed card's lightweight lease on the shared family owner."""

    def __init__(
        self,
        *,
        config: FeedRuntimeConfig,
        generation: object = None,
        manager: Any = None,
        ui_dispatch: Callable[[Callable[[], None]], object] | None = None,
        schedule: Callable[[int, Callable[[], None]], object] | None = None,
        task_priority: object | None = None,
    ) -> None:
        self.config = config
        self._generation = generation
        self._manager = manager
        self._ui_dispatch = ui_dispatch
        self._schedule = schedule
        self._task_priority = task_priority
        self._consumer_ref: weakref.ReferenceType | None = None
        self._owner: _FeedFamilyOwner | None = None
        self._running = False
        self._retired = False

    def attach_consumer(self, consumer: object) -> None:
        if self._retired or self._consumer_ref is not None:
            raise RuntimeError("Feed lease may be attached only once")
        self._consumer_ref = weakref.ref(consumer)
        if self._generation is None:
            self._generation = getattr(consumer, "_runtime_generation", None)

    def set_thread_manager(self, manager: Any, *, generation: object = None) -> None:
        if self._retired or self._running:
            raise RuntimeError("cannot change Feed lease worker after activation")
        self._manager = manager
        if generation is not None:
            self._generation = generation

    def start(self) -> bool:
        if self._retired or self._consumer_ref is None or self._manager is None:
            return False
        if self._running:
            return True
        if self._owner is None:
            ui_dispatch = self._ui_dispatch
            task_priority = self._task_priority
            if ui_dispatch is None or task_priority is None:
                from core.threading.manager import TaskPriority, ThreadManager

                if ui_dispatch is None:
                    ui_dispatch = ThreadManager.run_on_ui_thread
                if task_priority is None:
                    task_priority = TaskPriority.LOW

            key = (
                ("runtime", self._generation)
                if self._generation is not None
                else ("thread_manager", id(self._manager))
            )
            owner = _SHARED.get(key)
            if owner is None or owner.is_retired:
                owner = _FeedFamilyOwner(
                    key=key,
                    generation=self._generation,
                    manager=self._manager,
                    ui_dispatch=ui_dispatch,
                    schedule=self._schedule or _default_schedule,
                    task_priority=task_priority,
                )
                _SHARED[key] = owner
            self._owner = owner
            owner.attach(self)
        self._running = True
        self._running = bool(self._owner.activate(self))
        return self._running

    def _accept(self, result: FeedRefreshResult, *, from_cache: bool) -> None:
        consumer = self._consumer_ref() if self._consumer_ref else None
        if self._retired or not self._running or consumer is None:
            return
        alive = getattr(consumer, "is_feed_consumer_alive", None)
        if callable(alive) and not bool(alive()):
            return
        accept = getattr(consumer, "on_feed_runtime_result", None)
        if callable(accept):
            accept(result, from_cache=bool(from_cache))

    def request_refresh(self) -> bool:
        return bool(self._running and self._owner and self._owner.request_refresh(self))

    def detach_consumer(self, consumer: object | None = None) -> None:
        """Sever the retained presentation callback without retiring twice.

        Presentation retirement and runtime-manager retirement may occur in either
        order during generation teardown.  Detaching only clears the weak callback
        when it matches the supplied consumer; the runtime manager remains the
        service lifetime authority and performs final ``retire()``.
        """
        current = self._consumer_ref() if self._consumer_ref else None
        if consumer is not None and current is not consumer:
            return
        self._consumer_ref = None

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

    def is_running(self) -> bool:
        return self._running and not self._retired


@dataclass(frozen=True)
class NewsRuntimeConfig:
    widget_id: str
    providers: tuple[NewsProvider, ...]
    refresh_minutes: int
    show_images: bool
    view_mode: str
    item_limit: int

    @classmethod
    def from_news(cls, config: NewsFeedConfig) -> "NewsRuntimeConfig":
        return cls(
            widget_id=config.widget_id,
            providers=tuple(config.providers),
            refresh_minutes=max(5, min(24 * 60, int(config.refresh_minutes))),
            show_images=bool(config.show_images),
            view_mode=config.view_mode,
            item_limit=int(config.item_limit),
        )

    def provider_config(self, provider: NewsProvider) -> FeedRuntimeConfig:
        # Any one publisher may supply every visible row of the merged card.
        return FeedRuntimeConfig(
            widget_id=f"{self.widget_id}:{provider.provider_id}",
            source_spec=provider.source_spec(),
            refresh_minutes=self.refresh_minutes,
            show_images=self.show_images,
            view_mode=self.view_mode,
            item_limit=self.item_limit,
        )


class _NewsProviderConsumer:
    """One provider lease's consumer; refers back to its NEWS service weakly."""

    def __init__(self, service: "NewsRuntimeService", provider_id: str, generation: object) -> None:
        self._service_ref = weakref.ref(service)
        self._provider_id = provider_id
        self._runtime_generation = generation

    def is_feed_consumer_alive(self) -> bool:
        service = self._service_ref()
        return bool(service is not None and service._consumer_alive())

    def on_feed_runtime_result(self, result: FeedRefreshResult, *, from_cache: bool) -> None:
        service = self._service_ref()
        if service is not None:
            service._accept_provider(self._provider_id, result, from_cache=from_cache)


class NewsRuntimeService:
    """One NEWS card: an ordinary lease per provider on the shared family owner.

    Providers are plain FEEDS sources, so cadence, cache-first admission,
    conditional fetches, backoff, artwork and retirement belong to the family
    owner exactly as for CUSTOM. This service only keeps each provider's latest
    accepted result and publishes their merge to the one presentation. It has
    the same lifetime API as ``FeedRuntimeLease``.
    """

    def __init__(
        self,
        *,
        config: NewsRuntimeConfig,
        generation: object = None,
        manager: Any = None,
        ui_dispatch: Callable[[Callable[[], None]], object] | None = None,
        schedule: Callable[[int, Callable[[], None]], object] | None = None,
        task_priority: object | None = None,
    ) -> None:
        self.config = config
        self._leases = tuple(
            (
                provider.provider_id,
                FeedRuntimeLease(
                    config=config.provider_config(provider),
                    generation=generation,
                    manager=manager,
                    ui_dispatch=ui_dispatch,
                    schedule=schedule,
                    task_priority=task_priority,
                ),
            )
            for provider in config.providers
        )
        # Leases hold their consumers weakly; the service keeps them alive.
        self._provider_consumers: tuple[_NewsProviderConsumer, ...] = ()
        self._results: dict[str, tuple[FeedRefreshResult, bool]] = {}
        self._consumer_ref: weakref.ReferenceType | None = None
        self._retired = False

    def attach_consumer(self, consumer: object) -> None:
        if self._retired or self._consumer_ref is not None:
            raise RuntimeError("NEWS service may be attached only once")
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        bridges = []
        for provider_id, lease in self._leases:
            bridge = _NewsProviderConsumer(self, provider_id, generation)
            lease.attach_consumer(bridge)
            bridges.append(bridge)
        self._provider_consumers = tuple(bridges)

    def set_thread_manager(self, manager: Any, *, generation: object = None) -> None:
        if self._retired:
            raise RuntimeError("cannot change a retired NEWS service's worker")
        for _provider_id, lease in self._leases:
            lease.set_thread_manager(manager, generation=generation)

    def start(self) -> bool:
        if self._retired:
            return False
        started = [lease.start() for _provider_id, lease in self._leases]
        return any(started)

    def _consumer(self) -> object | None:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if self._retired or consumer is None:
            return False
        alive = getattr(consumer, "is_feed_consumer_alive", None)
        return bool(alive()) if callable(alive) else True

    def _accept_provider(self, provider_id: str, result: FeedRefreshResult, *, from_cache: bool) -> None:
        if self._retired:
            return
        self._results[provider_id] = (result, bool(from_cache))
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        merged = merge_news_results(
            self.config.providers,
            {pid: accepted for pid, (accepted, _cached) in self._results.items()},
        )
        if merged.snapshot is None and (
            len(self._results) < len(self._leases)
            or any(accepted.failure == "no_cache" for accepted, _cached in self._results.values())
        ):
            # No provider has a story yet and one has not finished its first
            # network fetch: the card stays loading rather than failed.
            return
        cached = all(
            was_cached for accepted, was_cached in self._results.values()
            if accepted.snapshot is not None or merged.snapshot is None
        )
        accept = getattr(consumer, "on_feed_runtime_result", None)
        if callable(accept):
            accept(merged, from_cache=cached)

    def request_refresh(self) -> bool:
        if self._retired:
            return False
        admitted = [lease.request_refresh() for _provider_id, lease in self._leases]
        return any(admitted)

    def detach_consumer(self, consumer: object | None = None) -> None:
        current = self._consumer()
        if consumer is not None and current is not consumer:
            return
        self._consumer_ref = None

    def stop(self) -> None:
        for _provider_id, lease in self._leases:
            lease.stop()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        for _provider_id, lease in self._leases:
            lease.retire()
        self._provider_consumers = ()
        self._results.clear()
        self._consumer_ref = None

    def is_retired(self) -> bool:
        return self._retired

    def is_running(self) -> bool:
        return not self._retired and any(lease.is_running() for _provider_id, lease in self._leases)


def reset_shared_feed_runtime_for_tests() -> None:
    for owner in tuple(_SHARED.values()):
        owner.retire()
    _SHARED.clear()
