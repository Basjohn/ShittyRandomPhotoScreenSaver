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
from core.feeds.source import FeedRefreshCancelled
from core.task_control import ExpectedTaskCancellation
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
    def from_custom(cls, config: CustomFeedConfig, refresh_minutes: int) -> "FeedRuntimeConfig":
        return cls(
            widget_id=config.widget_id,
            source_spec=config.source_spec(),
            refresh_minutes=max(5, min(24 * 60, int(refresh_minutes))),
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
    # A persisted failure backoff is a floor, never pulled early to share a
    # wake-up with other sources.
    due_is_backoff: bool = False
    artwork_attempted_at: float | None = None
    # Leading stories covered by the last artwork job (see _artwork_limit).
    artwork_item_limit: int = 0
    # A manual refresh requested while another source owns the family remote
    # lane stays queued and retains force semantics until it is admitted.
    force_refresh_pending: bool = False
    # False while this source still has immediate work in its current
    # presentation bundle (cache -> due refresh -> optional artwork). Consumers
    # may retain the latest intermediate state but should animate only once the
    # bundle is settled. Later refreshes reopen settlement for the same reason.
    presentation_settled: bool = False
    # Needed only when the family startup barrier republishes the accepted
    # result with ``initial_admission_complete=True``. Preserve whether the last
    # accepted generation was cache-origin so its status label does not change
    # merely because startup coordination completed.
    last_from_cache: bool = False


_SHARED: dict[tuple[str, object], "_FeedFamilyOwner"] = {}


def shared_feed_owner_count() -> int:
    return len(_SHARED)


# Remote FEEDS work is intentionally serialized across the family.  The old
# batching policy pulled sources due within 25% of their interval into one
# simultaneous burst (3m45s on the normal 15-minute NEWS cadence), which made
# independent HTTP/parse jobs fight for the GIL together.  One source bundle
# (refresh plus its optional artwork follow-on) now owns the remote lane, then
# leaves a small event-driven gap before the next source may enter.
_REMOTE_SOURCE_STAGGER_S = 2.5


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
        self._remote_bundle_key: str | None = None
        self._remote_not_before = 0.0
        # Startup is one family-wide presentation admission. Individual cards
        # must not arm body fades while serialized source/artwork jobs are still
        # arriving one after another. The barrier flips only when every active
        # source is settled; later refreshes never reopen it.
        self._initial_admission_complete = False
        # Every local image currently published by any source of this owner.
        # Replaced whole on the GUI thread; artwork workers read it when they
        # evict, so a source that publishes meanwhile is protected too.
        self._published_artwork: frozenset[str] = frozenset()
        # One lazy child parser belongs to the active FEEDS family.  It owns no
        # cadence/network/cache/presentation authority; it exists only to keep
        # feedparser + normalization outside the Qt/main-process GIL domain.
        self._parse_process: object | None = None

    def _maybe_complete_initial_admission(self) -> None:
        """Close the family startup barrier once every active source is settled.

        FEEDS source work is intentionally staggered. Without one family-level
        barrier each card can independently decide that its cache is "done" and
        then animate again when another startup source/artwork bundle arrives.
        That produced the visible 5-20 fade procession. Completion is derived
        entirely from source/job events; there is no polling or presentation
        timer.
        """

        if self._retired or self._initial_admission_complete:
            return
        active_states = {
            id(state): state
            for lease in self._active
            if lease._running
            for state in [self._states.get(lease.config.source_spec.cache_key)]
            if state is not None
        }.values()
        states = tuple(active_states)
        if not states or self._remote_bundle_key is not None:
            return
        now = self._now()
        for state in states:
            if (
                state.last_result is None
                or state.in_flight
                or not state.presentation_settled
                or state.force_refresh_pending
                or self._artwork_needed(state)
                or state.due_at <= now + 0.001
            ):
                return

        self._initial_admission_complete = True
        # Republish metadata only. Every consumer has already retained at least
        # one source result; this final event quietly commits the latest startup
        # body and arms future fades without another network/cache operation.
        for state in states:
            accepted = state.last_result
            if accepted is None:
                continue
            accepted = replace(accepted, initial_admission_complete=True)
            state.last_result = accepted
            for lease in self._active_leases_for_state(state):
                lease._accept(accepted, from_cache=state.last_from_cache)

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

    def _parser(self):
        parser = self._parse_process
        if parser is None:
            from core.feeds.process_parser import FeedParseProcess
            parser = FeedParseProcess()
            self._parse_process = parser
        return parser

    def _parse_document(self, payload: bytes, source_url: str, max_items: int):
        return self._parser().parse(payload, source_url=source_url, max_items=max_items)

    def _examine_response(self, response: object, request_url: str, max_items: int):
        return self._parser().examine(
            response, request_url=request_url, max_items=max_items,
        )

    def _close_parse_process(self) -> None:
        parser, self._parse_process = self._parse_process, None
        close = getattr(parser, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

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
                # A manual refresh request is meaningful only while this source
                # has an active consumer. Do not let it survive dormancy and
                # fire unexpectedly on a later reactivation.
                state.force_refresh_pending = False
            self._recompute_state_cadence(state)
            self._release_source_if_idle(state)
        if not self._active:
            self._cancel_deadline()
            # Dormant FEEDS retains immutable last-good data only.  The parser
            # child is recreated lazily on the next real remote parse.
            self._close_parse_process()
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
        self._remote_bundle_key = None
        self._remote_not_before = 0.0
        self._deadline_token += 1
        self._cancel_deadline()
        self._close_parse_process()
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
        # A second click on this source while its own work is already active is
        # not another admission.  A click while a *different* source owns the
        # family lane is accepted and queued without creating parallel work.
        if state.in_flight:
            return False
        state.force_refresh_pending = True
        state.due_at = self._now()
        state.due_is_backoff = False
        self._cancel_deadline()
        self._admit_due_work()
        self._reschedule()
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

            def _parse_document(payload: bytes, source_url: str, max_items: int):
                owner = owner_ref()
                if owner is None or owner._retired or state.work_cancel.is_set():
                    raise FeedRefreshCancelled("feed source no longer active")
                return owner._parse_document(payload, source_url, max_items)

            def _examine_response(response: object, request_url: str, max_items: int):
                owner = owner_ref()
                if owner is None or owner._retired or state.work_cancel.is_set():
                    raise FeedRefreshCancelled("feed source no longer active")
                return owner._examine_response(response, request_url, max_items)

            state.source = FeedSource(
                state.spec, transport_factory=_make_transport,
                should_continue=_still_needed,
                document_parser=_parse_document,
                response_examiner=_examine_response,
            )
        return state.source

    def _artwork_limit(self, state: _SourceState) -> int:
        """Leading stories whose artwork any active image-showing card can show.

        Rows past a card's item limit never show art, so they are never warmed
        or published. A NEWS publisher's lease narrows that to its share of the
        merged card (``FeedRuntimeLease.limit_artwork_rows``), so a card warms
        about as many images as it has rows however many publishers it merges.
        That keeps each source's protected artwork, and the shared cache, near
        its bounds.
        """
        return max(
            (lease.artwork_rows for lease in self._active_leases_for_state(state)
             if lease.config.show_images and lease.config.view_mode != "compact"),
            default=0,
        )

    def artwork_rows_changed(self, lease: "FeedRuntimeLease") -> None:
        """A lease's visible share grew: warm the newly visible art now (an event, not a timer)."""
        if self._retired or lease not in self._active:
            return
        state = self._states.get(lease.config.source_spec.cache_key)
        if state is None or state.in_flight or not self._artwork_needed(state):
            return
        state.presentation_settled = False
        # A stale/due source refresh outranks artwork. NEWS discovers publisher
        # artwork shares while cache callbacks are still unwinding; without
        # this guard that callback could seize the remote lane for stale artwork
        # just before cache completion admits the due text refresh.
        if state.due_at <= self._now() + 0.001:
            self._admit_due_work()
            self._reschedule()
            return
        if not self._submit(state, cache_only=False, force=False, artwork_only=True):
            self._reschedule()

    def _artwork_needed(self, state: _SourceState) -> bool:
        snapshot = state.last_result.snapshot if state.last_result is not None else None
        limit = self._artwork_limit(state)
        return bool(
            snapshot is not None
            and limit > 0
            and (state.artwork_attempted_at != snapshot.fetched_at
                 # A card with a larger limit joined an already-warmed source.
                 or limit > state.artwork_item_limit)
            # A story without feed images may still get its article's share
            # image as a last resort (remembered, so usually a disk-only pass).
            and any(item.images or item.action_url for item in snapshot.document.items[:limit])
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
        from core.feeds.artwork_transport import ArtworkFetchError, fetch_article_head, fetch_artwork_bytes
        from core.settings.storage_paths import detect_current_profile, get_feed_cache_dir
        cache = FeedArtworkCache(get_feed_cache_dir(detect_current_profile()) / "artwork")
        deadline = time.monotonic() + 8.0
        def needed() -> bool:
            return not cancel.is_set()
        def remaining_seconds() -> float:
            if not needed():
                raise ArtworkCancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0.1:
                # Never started, so nothing about this URL is remembered.
                raise ArtworkFetchError("shared artwork deadline exhausted", retry_seconds=None)
            return min(7.5, remaining)
        def fetch(url: str) -> bytes:
            return fetch_artwork_bytes(url, still_needed=needed, max_seconds=remaining_seconds())
        def fetch_page(url: str) -> bytes:
            return fetch_article_head(url, still_needed=needed, max_seconds=remaining_seconds())
        try:
            warm = cache.warm(snapshot.document.items[:max(1, int(item_limit))], fetch_bytes=fetch,
                              still_needed=needed, protected_sources=protected, fetch_page=fetch_page)
        except ArtworkCancelled:
            raise
        except (OSError, ValueError):
            return result  # Images cannot invalidate established article text.
        return replace(
            result,
            local_artwork_by_item=tuple(warm.local_by_item.items()),
            artwork_files_by_item=tuple(warm.files_by_item.items()),
        )

    def _submit(self, state: _SourceState, *, cache_only: bool, force: bool,
                artwork_only: bool = False) -> bool:
        if self._retired or state.in_flight or not self._active_leases_for_state(state):
            return False
        remote_work = not cache_only
        cache_key = state.spec.cache_key
        if remote_work:
            # A source bundle owns refresh + optional artwork as one serialized
            # remote transaction.  No other source may overlap it.
            if self._remote_bundle_key not in (None, cache_key):
                return False
            if self._remote_bundle_key is None and self._now() < self._remote_not_before:
                return False
            self._remote_bundle_key = cache_key
            state.presentation_settled = False
        state.in_flight = True
        state.work_cancel = Event()
        state.work_token += 1
        token = state.work_token
        cancel = state.work_cancel
        owner_ref = weakref.ref(self)
        base_artwork_result = state.last_result if artwork_only else None
        artwork_limit = self._artwork_limit(state) if artwork_only else 0
        if artwork_only:
            state.artwork_item_limit = artwork_limit
            if state.last_result is not None and state.last_result.snapshot is not None:
                state.artwork_attempted_at = state.last_result.snapshot.fetched_at
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
                raise ExpectedTaskCancellation("feed source no longer active")
            if artwork_only:
                if base_artwork_result is None:
                    raise RuntimeError("missing accepted feed artwork source")
                from core.feeds.artwork import ArtworkCancelled
                try:
                    warmed = owner._warm_artwork(
                        base_artwork_result, cancel=cancel,
                        protected=protected, item_limit=artwork_limit,
                    )
                    # Persist the accepted item -> cache-file association on the
                    # same IO worker that owns artwork work. Warm startup can
                    # then publish cached stories *with cached images* before
                    # any network refresh or rediscovery.
                    source = owner._source_for(state)
                    persist = getattr(source, "persist_artwork_bindings", None)
                    return persist(warmed) if callable(persist) else warmed
                except (ArtworkCancelled, FeedRefreshCancelled):
                    raise ExpectedTaskCancellation("feed artwork no longer active") from None
            source = owner._source_for(state)
            try:
                return source.load_cached() if cache_only else source.refresh(force=force)
            except FeedRefreshCancelled as exc:
                raise ExpectedTaskCancellation(str(exc) or "feed source no longer active") from None

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
            if remote_work and self._remote_bundle_key == cache_key:
                self._finish_remote_bundle(cache_key)
            state.due_at = self._now() + 60.0
            self._reschedule()
            return False
        return True

    def _finish_remote_bundle(self, cache_key: str) -> None:
        if self._remote_bundle_key != cache_key:
            return
        self._remote_bundle_key = None
        self._remote_not_before = self._now() + _REMOTE_SOURCE_STAGGER_S

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
        remote_work = not cache_only
        if (state is not submitted_state or token != state.work_token
            or not state.in_flight):
            self._release_source(submitted_state)
            if remote_work:
                self._finish_remote_bundle(cache_key)
                self._admit_due_work()
                self._reschedule()
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
            if remote_work:
                self._finish_remote_bundle(cache_key)
                self._admit_due_work()
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
                result = replace(
                    result,
                    local_artwork_by_item=previous.local_artwork_by_item,
                    artwork_files_by_item=previous.artwork_files_by_item,
                )
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
            if not artwork_only:
                self._update_due(state, result)

            # Settlement belongs to the whole source bundle, not each callback.
            # Cache publication may still have an immediate due network refresh
            # or artwork pass. A remote text refresh likewise remains unsettled
            # until any admitted artwork follow-on completes.
            artwork_needed = self._artwork_needed(state)
            if artwork_only:
                state.presentation_settled = True
            elif cache_only:
                state.presentation_settled = bool(
                    state.due_at > self._now() + 0.001 and not artwork_needed
                )
            else:
                state.presentation_settled = not artwork_needed

            result = replace(
                result,
                presentation_settled=bool(state.presentation_settled),
                initial_admission_complete=bool(self._initial_admission_complete),
            )
            state.last_from_cache = bool(cache_only)
            state.last_result = result
            self._refresh_published_artwork()
            for lease in self._active_leases_for_state(state):
                lease._accept(result, from_cache=cache_only)
        elif not artwork_only:
            state.due_at = self._now() + 60.0
            state.presentation_settled = True

        if cache_only:
            # Cache-first publication never bypasses the shared remote lane.
            # A due source joins the serialized admission queue instead of
            # launching beside another source that happened to wake with it.
            self._admit_due_work()
        elif not artwork_only and self._artwork_needed(state):
            # Keep this source's artwork in the same owned bundle. Only after
            # the bundle finishes does the next source receive admission.
            if not self._submit(state, cache_only=False, force=False, artwork_only=True):
                self._finish_remote_bundle(cache_key)
                self._admit_due_work()
        else:
            if remote_work:
                self._finish_remote_bundle(cache_key)
                self._admit_due_work()
        self._maybe_complete_initial_admission()
        self._release_source_if_idle(state)
        self._reschedule()

    def _update_due(self, state: _SourceState, result: FeedRefreshResult) -> None:
        now = self._now()
        health = result.health
        state.due_is_backoff = False
        if health.backoff_until is not None and health.backoff_until > now:
            state.due_at = float(health.backoff_until)
            state.due_is_backoff = True
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
        """Admit at most one due remote source bundle.

        Remote source work is intentionally family-serialized. Sources are
        never pulled early to align cadences; after one refresh (+ optional
        artwork) completes, a small single-shot cooldown separates the next
        source.  Successful timestamps therefore remain naturally phase-shifted
        rather than collapsing back into one 15-minute contention burst.
        """
        if self._retired or self._remote_bundle_key is not None:
            return
        now = self._now()
        if now < self._remote_not_before:
            return

        candidates = [
            state for state in self._states.values()
            if (not state.in_flight
                and self._active_leases_for_state(state)
                and state.due_at <= now + 0.001)
        ]
        if candidates:
            state = min(candidates, key=lambda item: (item.due_at, item.spec.cache_key))
            force = bool(state.force_refresh_pending)
            if self._submit(state, cache_only=False, force=force):
                state.force_refresh_pending = False
            return

        # Optional artwork also uses the same remote lane, but never outranks a
        # due text/source refresh. Activation or a newly enlarged card can leave
        # an artwork request pending here without introducing another timer.
        artwork_candidates = [
            state for state in self._states.values()
            if (not state.in_flight
                and self._active_leases_for_state(state)
                and self._artwork_needed(state))
        ]
        if artwork_candidates:
            state = min(
                artwork_candidates,
                key=lambda item: (item.due_at, item.spec.cache_key),
            )
            self._submit(state, cache_only=False, force=False, artwork_only=True)

    def _reschedule(self) -> None:
        self._cancel_deadline()
        if self._retired or not self._active or self._remote_bundle_key is not None:
            return
        now = self._now()
        candidates = [
            state.due_at
            for state in self._states.values()
            if self._active_leases_for_state(state) and not state.in_flight and state.due_at > 0
        ]
        if any(
            not state.in_flight
            and self._active_leases_for_state(state)
            and self._artwork_needed(state)
            for state in self._states.values()
        ):
            candidates.append(now)
        if not candidates:
            return
        due_at = max(self._remote_not_before, min(candidates))
        delay_ms = max(1, int(round(max(0.001, due_at - now) * 1000.0)))
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
        # Leading stories whose art this lease's card can show; None means the
        # card's item limit (a CUSTOM card shows its own rows).
        self._artwork_rows: int | None = None

    @property
    def artwork_rows(self) -> int:
        limit = int(self.config.item_limit)
        return limit if self._artwork_rows is None else min(limit, self._artwork_rows)

    def limit_artwork_rows(self, rows: int) -> None:
        """Warm art only for this source's leading ``rows`` stories.

        A NEWS card sets this to each publisher's share of its merged rows. A
        larger share admits the newly visible art at once; a smaller one warms
        nothing and evicts nothing already published.
        """
        rows = max(0, int(rows))
        if rows == self._artwork_rows:
            return
        grew = rows > self.artwork_rows or self._artwork_rows is None
        self._artwork_rows = rows
        if grew and self._running and self._owner is not None:
            self._owner.artwork_rows_changed(self)

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

    @property
    def presentation_settled(self) -> bool:
        owner = self._owner
        if self._retired or not self._running or owner is None or owner.is_retired:
            return False
        state = owner._states.get(self.config.source_spec.cache_key)
        return bool(state is not None and state.presentation_settled and not state.in_flight)

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
    def from_news(cls, config: NewsFeedConfig, refresh_minutes: int) -> "NewsRuntimeConfig":
        return cls(
            widget_id=config.widget_id,
            providers=tuple(config.providers),
            refresh_minutes=max(5, min(24 * 60, int(refresh_minutes))),
            show_images=bool(config.show_images),
            view_mode=config.view_mode,
            item_limit=int(config.item_limit),
        )

    def provider_config(self, provider: NewsProvider) -> FeedRuntimeConfig:
        # Any one publisher may supply every visible row of the merged card.
        source_spec = replace(
            provider.source_spec(),
            # NEWS used to normalize forty stories from every selected
            # publisher even though the card ordinarily shows twelve.  That
            # multiplied pure-Python feedparser/HTML-normalization GIL work
            # across the whole family cadence.  Retain a twelve-story floor,
            # and grow only when the card is explicitly configured to show
            # more rows.
            max_items=max(12, int(self.item_limit)),
        )
        return FeedRuntimeConfig(
            widget_id=f"{self.widget_id}:{provider.provider_id}",
            source_spec=source_spec,
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
        # No art until the merge says which publishers' stories are on the card.
        for _provider_id, lease in self._leases:
            lease.limit_artwork_rows(0)
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

        # Do not paint a publisher-by-publisher cache parade at startup. Wait
        # until every provider has answered its cache admission before showing
        # the first aggregate. A brand-new card with no cached stories remains
        # loading until the first remote provider produces usable content.
        if len(self._results) < len(self._leases):
            return

        # Determine visible publisher shares before publishing settlement. This
        # may immediately admit artwork for one or more providers and therefore
        # reopen their source bundle. Presentation stays on its last settled
        # aggregate until every provider's current immediate work is done.
        self._limit_artwork_to_visible_rows(merged)
        settled = all(lease.presentation_settled for _pid, lease in self._leases)
        initial_complete = bool(
            len(self._results) >= len(self._leases)
            and all(
                accepted.initial_admission_complete
                for accepted, _cached in self._results.values()
            )
        )
        merged = replace(
            merged,
            presentation_settled=bool(settled),
            initial_admission_complete=initial_complete,
        )
        self._publish(consumer, merged)

    def _publish(self, consumer: object, merged: FeedRefreshResult) -> None:
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

    def _limit_artwork_to_visible_rows(self, merged: FeedRefreshResult) -> None:
        """Give each publisher's lease its share of the rows this card can show.

        A share is counted in that publisher's own feed order (what the artwork
        warm walks), up to its last story among the card's leading rows. Until
        every publisher has answered, the shares are not final and no art is
        warmed; answers arrive within one bounded fetch, cached ones at once.
        """
        rows: dict[str, int] = {pid: 0 for pid, _lease in self._leases}
        if merged.snapshot is not None and len(self._results) >= len(self._leases):
            positions = {
                pid: {item.item_id: index for index, item in enumerate(accepted.snapshot.document.items)}
                for pid, (accepted, _cached) in self._results.items() if accepted.snapshot is not None
            }
            for item in merged.snapshot.document.items[:max(0, int(self.config.item_limit))]:
                pid, _sep, item_id = item.item_id.partition(":")
                index = positions.get(pid, {}).get(item_id)
                if index is not None:
                    rows[pid] = max(rows[pid], index + 1)
        for pid, lease in self._leases:
            lease.limit_artwork_rows(rows[pid])

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
