"""Presentation-neutral Reddit/Reddit2 runtime ownership.

``RedditRuntimeService`` owns the non-pixel lifecycle for one configured Reddit
family member: provider use, startup cache, accepted candidate state, periodic
and manual cadence, blocked-gate persistence, request generations and clean
retirement.  It deliberately knows nothing about QWidget/QML geometry, paint
caches, hit regions, spinners or transition effects.

Retained Quick consumers implement this small callback protocol:

* ``is_reddit_consumer_alive()``
* ``on_reddit_runtime_posts(posts, *, from_cache, source_id, attempted_sources)``
* ``on_reddit_runtime_refreshing(refreshing)``
* ``on_reddit_runtime_error(error)``
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import random
import threading
import time
from typing import Any, Mapping, Optional
import weakref

from core.logging.logger import get_logger
from core.reddit_post_provider import RedditFetchRequest, RedditPostProvider
from core.reddit_preparation import (
    PreparedRedditFeed,
    RedditPost,
    RedditStartupSnapshot,
    get_reddit_cached_timestamp,
    load_reddit_startup_snapshot,
    prepare_reddit_feed,
    touch_reddit_marker,
)
from core.runtime_flags import automatic_service_updates_enabled
from core.settings.widget_capacity_policy import LIST_WIDGET_MAX_CAPACITY
from core.threading.manager import ThreadManager
from widgets.service_widget_runtime import StartupRefreshDecision


logger = get_logger(__name__)
_REDDIT_CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "reddit"


def normalize_subreddit(value: object) -> str:
    """Normalize a subreddit name, ``r/name`` path or Reddit URL."""

    slug = str(value or "").strip().replace("\\", "/")
    lowered = slug.lower()
    if "reddit.com" in lowered and "/r/" in lowered:
        slug = slug[lowered.index("/r/") + 3 :].split("/", 1)[0]
    elif lowered.startswith("/r/"):
        slug = slug[3:]
    elif lowered.startswith("r/"):
        slug = slug[2:]
    return slug.strip("/ ")


@dataclass(frozen=True)
class RedditRuntimeConfig:
    """Provider-independent settings required to maintain one Reddit feed."""

    widget_id: str
    subreddit: str
    cache_key: str
    sort: str = "hot"

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        widget_id: str,
    ) -> "RedditRuntimeConfig":
        member_id = str(widget_id or "reddit")
        return cls(
            widget_id=member_id,
            subreddit=normalize_subreddit(values.get("subreddit", "pics")) or "pics",
            cache_key=member_id,
            sort=str(values.get("sort", "hot") or "hot"),
        )


_PERIODIC_DUE_BY_CACHE_KEY: dict[str, float] = {}
_PERIODIC_DUE_REASON_BY_CACHE_KEY: dict[str, str] = {}
_MANUAL_DUE_BY_CACHE_KEY: dict[str, float] = {}


class RedditRuntimeService:
    """Own one Reddit member's cache/cadence/fetch lifecycle."""

    REFRESH_INTERVAL = timedelta(minutes=15)
    MANUAL_REFRESH_INTERVAL = timedelta(minutes=3)
    SECONDARY_WIDGET_STAGGER = timedelta(seconds=30)
    STARTUP_STALE_PACE = timedelta(seconds=30)
    REFRESH_TIMER_JITTER_MS = 2000

    # Exposed as class attributes for focused cadence tests and deliberate
    # preservation across presenter/service rebuilds in the same process.
    periodic_due_by_cache_key = _PERIODIC_DUE_BY_CACHE_KEY
    periodic_due_reason_by_cache_key = _PERIODIC_DUE_REASON_BY_CACHE_KEY
    manual_due_by_cache_key = _MANUAL_DUE_BY_CACHE_KEY

    def __init__(
        self,
        *,
        config: RedditRuntimeConfig,
        provider: RedditPostProvider,
        runtime_generation: Any = None,
    ) -> None:
        self._config = config
        self._provider = provider
        self._runtime_generation = runtime_generation
        self._consumer_ref: Optional[weakref.ref] = None
        self._thread_manager: Any = None
        self._shutdown_event = threading.Event()

        self._candidates: tuple[RedditPost, ...] = ()
        self._startup_request_id = 0
        self._fetch_request_id = 0
        self._accepted_revision = 0
        self._due_token = 0
        self._due_pending = False
        self._fetch_in_progress = False
        self._running = False
        self._retired = False

    # ------------------------------------------------------------------
    # Consumer/configuration
    # ------------------------------------------------------------------
    @property
    def config(self) -> RedditRuntimeConfig:
        return self._config

    @property
    def provider(self) -> RedditPostProvider:
        return self._provider

    @property
    def provider_id(self) -> str | None:
        """Return the configured provider identity for diagnostics/contracts."""

        value = getattr(self._provider, "provider_id", None)
        return str(value) if value is not None else None

    @property
    def candidates(self) -> tuple[RedditPost, ...]:
        return self._candidates

    @property
    def accepted_revision(self) -> int:
        return self._accepted_revision

    def attach_consumer(self, consumer: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot attach a consumer to a retired Reddit runtime service")
        self._consumer_ref = weakref.ref(consumer)
        generation = getattr(consumer, "_runtime_generation", None)
        if generation is None:
            try:
                generation = getattr(consumer.parent(), "_runtime_generation", None)
            except Exception:
                generation = None
        if generation is not None:
            self._runtime_generation = generation

    def detach_consumer(self, consumer: Any = None) -> None:
        current = self._consumer()
        if consumer is None or current is consumer:
            self._consumer_ref = None

    def _consumer(self) -> Any:
        return self._consumer_ref() if self._consumer_ref is not None else None

    def _consumer_alive(self) -> bool:
        consumer = self._consumer()
        if consumer is None:
            return False
        try:
            return bool(consumer.is_reddit_consumer_alive())
        except Exception:
            return False

    def set_thread_manager(self, thread_manager: Any) -> None:
        self._thread_manager = thread_manager

    def set_subreddit(self, subreddit: str) -> bool:
        normalized = normalize_subreddit(subreddit)
        if normalized.casefold() == self._config.subreddit.casefold():
            return False
        self._config = RedditRuntimeConfig(
            widget_id=self._config.widget_id,
            subreddit=normalized,
            cache_key=self._config.cache_key,
            sort=self._config.sort,
        )
        self._invalidate_async_results()
        self._fetch_in_progress = False
        self._candidates = ()
        if self._running:
            self._begin_startup_snapshot_load()
        return True

    def is_running(self) -> bool:
        return self._running and not self._retired

    def is_retired(self) -> bool:
        return self._retired

    # ------------------------------------------------------------------
    # Consumer delivery
    # ------------------------------------------------------------------
    def _deliver_posts(
        self,
        posts: tuple[RedditPost, ...],
        *,
        from_cache: bool,
        source_id: str | None = None,
        attempted_sources: tuple[str, ...] = (),
    ) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_reddit_runtime_posts(
                posts,
                from_cache=from_cache,
                source_id=source_id,
                attempted_sources=attempted_sources,
            )
        except Exception:
            logger.debug("[REDDIT_RT] post delivery failed", exc_info=True)

    def _deliver_refreshing(self, refreshing: bool) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_reddit_runtime_refreshing(bool(refreshing))
        except Exception:
            logger.debug("[REDDIT_RT] refreshing delivery failed", exc_info=True)

    def _deliver_error(self, error: str) -> None:
        consumer = self._consumer()
        if consumer is None or not self._consumer_alive():
            return
        try:
            consumer.on_reddit_runtime_error(str(error))
        except Exception:
            logger.debug("[REDDIT_RT] error delivery failed", exc_info=True)

    # ------------------------------------------------------------------
    # Lifecycle/startup cache
    # ------------------------------------------------------------------
    def start(self) -> bool:
        if self._retired or not self._config.subreddit:
            return False
        if self._thread_manager is None:
            logger.error("[REDDIT_RT] start unavailable: ThreadManager is not configured")
            return False
        if self._running:
            return True
        self._running = True
        self._shutdown_event.clear()
        if self._candidates:
            # A reusable service's accepted in-memory state outranks an older
            # persisted snapshot while the snapshot still supplies cadence/gate
            # metadata for this activation.
            self._deliver_posts(self._candidates, from_cache=False)
        self._begin_startup_snapshot_load()
        return True

    def _invalidate_async_results(self) -> None:
        self._startup_request_id += 1
        self._fetch_request_id += 1
        self._due_token += 1
        self._due_pending = False

    def _begin_startup_snapshot_load(self) -> None:
        if self._retired or not self._running:
            return
        tm = self._thread_manager
        if tm is None:
            return
        self._startup_request_id += 1
        request_id = self._startup_request_id
        accepted_revision = self._accepted_revision
        cache_path = self._cache_file_path()
        gate_path = self._service_gate_file_path()
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _load() -> RedditStartupSnapshot:
            return load_reddit_startup_snapshot(cache_path, gate_path)

        _load._srpss_runtime_generation = runtime_generation

        def _on_result(result: Any) -> None:
            snapshot = None
            error = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, RedditStartupSnapshot):
                    snapshot = candidate
                else:
                    error = "No Reddit startup snapshot returned"
            else:
                error = str(getattr(result, "error", None) or "No Reddit startup snapshot returned")

            def _deliver() -> None:
                owner = self_ref()
                if owner is None:
                    return
                if snapshot is not None:
                    owner._commit_startup_snapshot(request_id, accepted_revision, snapshot)
                else:
                    owner._commit_startup_error(request_id, accepted_revision, str(error))

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = runtime_generation
        try:
            tm.submit_io_task(_load, callback=_on_result)
        except Exception as exc:
            self._commit_startup_error(request_id, accepted_revision, str(exc))

    def _commit_startup_snapshot(
        self,
        request_id: int,
        accepted_revision: int,
        snapshot: RedditStartupSnapshot,
    ) -> None:
        if (
            self._retired
            or not self._running
            or request_id != self._startup_request_id
            or accepted_revision != self._accepted_revision
        ):
            return
        if snapshot.candidates and not self._candidates:
            self._candidates = tuple(snapshot.candidates)
            self._deliver_posts(self._candidates, from_cache=True)
        self._run_startup_refresh_flow(snapshot)

    def _commit_startup_error(
        self,
        request_id: int,
        accepted_revision: int,
        error: str,
    ) -> None:
        if (
            self._retired
            or not self._running
            or request_id != self._startup_request_id
            or accepted_revision != self._accepted_revision
        ):
            return
        logger.warning("[REDDIT_RT] Startup cache snapshot failed: %s", error)
        self._run_startup_refresh_flow(
            RedditStartupSnapshot((), None, None)
        )

    def _startup_refresh_decision(
        self, snapshot: RedditStartupSnapshot
    ) -> StartupRefreshDecision:
        if not automatic_service_updates_enabled():
            return StartupRefreshDecision(False, "automatic_updates_disabled", None)
        cache_age = None
        if snapshot.cache_timestamp is not None:
            cache_age = datetime.now() - snapshot.cache_timestamp
            if cache_age < self.REFRESH_INTERVAL:
                return StartupRefreshDecision(False, "cache_fresh", cache_age)
        try:
            from core.reddit_rate_limiter import RedditRateLimiter

            if snapshot.service_gate_timestamp is not None:
                gate_age = datetime.now() - snapshot.service_gate_timestamp
                if gate_age < timedelta(seconds=RedditRateLimiter.BLOCK_COOLDOWN_SECONDS):
                    return StartupRefreshDecision(
                        False, "blocked_cooldown_cache_stale", gate_age
                    )
        except Exception:
            logger.debug("[REDDIT_RT] blocked startup gate evaluation failed", exc_info=True)
        return StartupRefreshDecision(
            True,
            "missing_cache_timestamp" if cache_age is None else "cache_stale",
            cache_age,
        )

    def _run_startup_refresh_flow(self, snapshot: RedditStartupSnapshot) -> None:
        if not automatic_service_updates_enabled():
            logger.info("[REDDIT_RT] Automatic updates disabled; manual refresh only")
            return
        decision = self._startup_refresh_decision(snapshot)
        if decision.run:
            delay_ms = (
                int(self.STARTUP_STALE_PACE.total_seconds() * 1000)
                if self._config.cache_key == "reddit2"
                else 0
            )
            if delay_ms <= 0:
                if not self.fetch():
                    self._set_periodic_due_delay_ms(60_000, "startup_no_submit_retry_due")
                    self._schedule_timer()
            else:
                self._set_periodic_due_delay_ms(delay_ms, "startup_stale_paced_due")
                self._schedule_timer()
            return
        self._schedule_timer()

    # ------------------------------------------------------------------
    # Cadence
    # ------------------------------------------------------------------
    def _cache_file_path(self) -> Path:
        return _REDDIT_CACHE_DIR / f"{self._config.cache_key}_posts.json"

    def _service_gate_file_path(self) -> Path:
        return _REDDIT_CACHE_DIR / "_startup_gate.touch"

    def _cache_timestamp(self):
        return get_reddit_cached_timestamp(self._cache_file_path())

    def _gate_timestamp(self):
        return get_reddit_cached_timestamp(self._service_gate_file_path())

    def _refresh_interval_ms(self) -> int:
        return max(1, int(self.REFRESH_INTERVAL.total_seconds() * 1000))

    def _refresh_phase_delay_ms(self) -> tuple[int, int]:
        index = 1 if self._config.cache_key == "reddit2" else 0
        base = int(self.SECONDARY_WIDGET_STAGGER.total_seconds() * 1000) * index
        jitter = random.randint(-self.REFRESH_TIMER_JITTER_MS, self.REFRESH_TIMER_JITTER_MS)
        return max(0, base + jitter), jitter

    def _blocked_gate_remaining_delay_ms(self, phase_delay_ms: int = 0) -> Optional[int]:
        try:
            from core.reddit_rate_limiter import RedditRateLimiter

            timestamp = self._gate_timestamp()
            if timestamp is None:
                return None
            age = max(0.0, (datetime.now() - timestamp).total_seconds())
            remaining = RedditRateLimiter.BLOCK_COOLDOWN_SECONDS - age
            if remaining <= 0:
                return None
            return max(0, int(remaining * 1000) + max(0, int(phase_delay_ms)))
        except Exception:
            logger.debug("[REDDIT_RT] blocked periodic gate evaluation failed", exc_info=True)
            return None

    def _refresh_due_delay_ms(self, phase_delay_ms: int) -> tuple[int, str]:
        now_mono = time.monotonic()
        key = self._config.cache_key
        due = _PERIODIC_DUE_BY_CACHE_KEY.get(key)
        if due is not None:
            return (
                max(0, int((due - now_mono) * 1000)),
                _PERIODIC_DUE_REASON_BY_CACHE_KEY.get(key, "preserved_due"),
            )
        blocked = self._blocked_gate_remaining_delay_ms(phase_delay_ms)
        if blocked is not None:
            _PERIODIC_DUE_BY_CACHE_KEY[key] = now_mono + blocked / 1000.0
            _PERIODIC_DUE_REASON_BY_CACHE_KEY[key] = "blocked_cooldown_due"
            return blocked, "blocked_cooldown_due"
        timestamp = self._cache_timestamp()
        if timestamp is not None:
            age_ms = int(max(0.0, (datetime.now() - timestamp).total_seconds() * 1000))
            if age_ms < self._refresh_interval_ms():
                delay = self._refresh_interval_ms() - age_ms
                _PERIODIC_DUE_BY_CACHE_KEY[key] = now_mono + delay / 1000.0
                _PERIODIC_DUE_REASON_BY_CACHE_KEY[key] = "cache_fresh_due"
                return delay, "cache_fresh_due"
        delay = max(0, int(phase_delay_ms))
        _PERIODIC_DUE_BY_CACHE_KEY[key] = now_mono + delay / 1000.0
        _PERIODIC_DUE_REASON_BY_CACHE_KEY[key] = "cache_stale_staggered_due"
        return delay, "cache_stale_staggered_due"

    def _set_periodic_due_delay_ms(self, delay_ms: int, reason: str) -> bool:
        key = self._config.cache_key
        due = time.monotonic() + max(0, int(delay_ms)) / 1000.0
        old = _PERIODIC_DUE_BY_CACHE_KEY.get(key)
        if old is not None and due >= old:
            return False
        _PERIODIC_DUE_BY_CACHE_KEY[key] = due
        _PERIODIC_DUE_REASON_BY_CACHE_KEY[key] = str(reason)
        return True

    def _schedule_timer(self) -> None:
        if self._retired or not self._running or self._due_pending:
            return
        phase_delay, jitter = self._refresh_phase_delay_ms()
        delay, reason = self._refresh_due_delay_ms(phase_delay)
        logger.info(
            "[CACHE][REDDIT_RT] due timer armed cache_key=%s cadence_s=%.1f "
            "phase_delay_s=%.1f jitter_ms=%+d due_delay_s=%.1f reason=%s",
            self._config.cache_key,
            self.REFRESH_INTERVAL.total_seconds(),
            phase_delay / 1000.0,
            jitter,
            delay / 1000.0,
            reason,
        )
        if delay <= 0:
            self._on_periodic_due()
            return
        self._due_token += 1
        token = self._due_token
        self._due_pending = True
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _fire() -> None:
            owner = self_ref()
            if owner is not None:
                owner._on_due_timeout(token)

        _fire._srpss_runtime_generation = runtime_generation
        ThreadManager.single_shot(delay, _fire)

    def _on_due_timeout(self, token: int) -> None:
        if self._retired or not self._running or token != self._due_token:
            return
        self._due_pending = False
        self._on_periodic_due()

    def _on_periodic_due(self) -> None:
        key = self._config.cache_key
        _PERIODIC_DUE_BY_CACHE_KEY.pop(key, None)
        _PERIODIC_DUE_REASON_BY_CACHE_KEY.pop(key, None)
        if not self.fetch():
            self._set_periodic_due_delay_ms(60_000, "no_submit_retry_due")
            self._schedule_timer()

    def _mark_periodic_terminal(self, reason: str) -> None:
        key = self._config.cache_key
        _PERIODIC_DUE_BY_CACHE_KEY[key] = time.monotonic() + self.REFRESH_INTERVAL.total_seconds()
        _PERIODIC_DUE_REASON_BY_CACHE_KEY[key] = str(reason)
        if self._running:
            self._schedule_timer()

    # ------------------------------------------------------------------
    # Fetch/manual action
    # ------------------------------------------------------------------
    def request_refresh(self) -> bool:
        if self._retired or not self._running or not self._config.subreddit:
            return False
        skip = self._manual_refresh_skip_reason()
        if skip is not None:
            logger.info(
                "[CACHE][REDDIT_RT] Manual refresh skipped cache_key=%s reason=%s remaining_s=%.1f",
                self._config.cache_key,
                skip[0],
                skip[1],
            )
            return True
        if self._fetch_in_progress:
            return False
        self._deliver_refreshing(True)
        submitted = self.fetch(mark_manual_attempt=True)
        if not submitted:
            self._deliver_refreshing(False)
        return submitted

    def _manual_refresh_skip_reason(self) -> Optional[tuple[str, float]]:
        blocked_ms = self._blocked_gate_remaining_delay_ms()
        if blocked_ms is not None and blocked_ms > 0:
            remaining = blocked_ms / 1000.0
            timestamp = self._gate_timestamp()
            if timestamp is not None:
                age = max(0.0, (datetime.now() - timestamp).total_seconds())
                remaining = min(
                    remaining,
                    max(0.0, self.MANUAL_REFRESH_INTERVAL.total_seconds() - age),
                )
            if remaining > 0:
                return "blocked_cooldown", remaining
        timestamp = self._cache_timestamp()
        if timestamp is not None:
            age = max(0.0, (datetime.now() - timestamp).total_seconds())
            remaining = self.MANUAL_REFRESH_INTERVAL.total_seconds() - age
            if remaining > 0:
                return "cache_fresh", remaining
        key = self._config.cache_key
        manual_due = _MANUAL_DUE_BY_CACHE_KEY.get(key)
        if manual_due is not None:
            remaining = manual_due - time.monotonic()
            if remaining > 0:
                return "manual_attempt_due", remaining
            _MANUAL_DUE_BY_CACHE_KEY.pop(key, None)
        periodic_due = _PERIODIC_DUE_BY_CACHE_KEY.get(key)
        if periodic_due is not None:
            remaining = periodic_due - time.monotonic()
            reason = _PERIODIC_DUE_REASON_BY_CACHE_KEY.get(key, "periodic_due_pending")
            if remaining > 0 and reason in {
                "post_attempt_due",
                "manual_attempt_due",
                "success",
                "all_sources_failed",
            }:
                attempt_age = self.REFRESH_INTERVAL.total_seconds() - remaining
                manual_remaining = self.MANUAL_REFRESH_INTERVAL.total_seconds() - attempt_age
                if manual_remaining > 0:
                    return reason, manual_remaining
        return None

    def _mark_manual_attempt(self) -> None:
        _MANUAL_DUE_BY_CACHE_KEY[self._config.cache_key] = (
            time.monotonic() + self.MANUAL_REFRESH_INTERVAL.total_seconds()
        )

    def fetch(self, *, mark_manual_attempt: bool = False) -> bool:
        if (
            self._retired
            or not self._running
            or self._fetch_in_progress
            or self._thread_manager is None
            or not self._config.subreddit
        ):
            return False
        bypass_blocked_cooldown = False
        try:
            from core.reddit_rate_limiter import RedditRateLimiter

            blocked_wait = RedditRateLimiter.get_blocked_cooldown_remaining()
            if blocked_wait > 0:
                if mark_manual_attempt:
                    timestamp = self._gate_timestamp()
                    manual_remaining = blocked_wait
                    if timestamp is not None:
                        age = max(0.0, (datetime.now() - timestamp).total_seconds())
                        manual_remaining = self.MANUAL_REFRESH_INTERVAL.total_seconds() - age
                    if manual_remaining <= 0:
                        bypass_blocked_cooldown = True
                    else:
                        self._deliver_refreshing(False)
                        return True
                else:
                    self._set_periodic_due_delay_ms(
                        int(blocked_wait * 1000), "blocked_cooldown_due"
                    )
                    self._schedule_timer()
                    return True
        except ImportError:
            pass

        self._fetch_in_progress = True
        if mark_manual_attempt:
            self._mark_manual_attempt()
        self._fetch_request_id += 1
        request_id = self._fetch_request_id
        config = self._config
        provider = self._provider
        current_candidates = self._candidates
        shutdown_event = self._shutdown_event
        cache_path = self._cache_file_path()
        runtime_generation = self._runtime_generation
        self_ref = weakref.ref(self)

        def _do_fetch() -> PreparedRedditFeed:
            result = provider.fetch_posts(
                RedditFetchRequest(
                    subreddit=config.subreddit,
                    sort=config.sort,
                    limit=LIST_WIDGET_MAX_CAPACITY,
                    cache_key=config.cache_key,
                    shutdown_event=shutdown_event,
                    bypass_blocked_cooldown=bypass_blocked_cooldown,
                )
            )
            if result.skip_reason:
                return PreparedRedditFeed(
                    (), result.source_id, tuple(result.attempted_sources), 0,
                    skip_reason=str(result.skip_reason),
                )
            rows = result.posts if isinstance(result.posts, list) else []
            return prepare_reddit_feed(
                rows,
                source_id=result.source_id,
                attempted_sources=result.attempted_sources,
                current_candidates=current_candidates,
                cache_path=cache_path,
                cache_key=config.cache_key,
                candidate_limit=LIST_WIDGET_MAX_CAPACITY,
            )

        _do_fetch._srpss_runtime_generation = runtime_generation

        def _on_result(result: Any) -> None:
            prepared = None
            error = None
            if getattr(result, "success", False):
                candidate = getattr(result, "result", None)
                if isinstance(candidate, PreparedRedditFeed):
                    prepared = candidate
                else:
                    error = "No Reddit data returned"
            else:
                error = str(getattr(result, "error", None) or "No Reddit data returned")

            def _deliver() -> None:
                owner = self_ref()
                if owner is None:
                    return
                if prepared is not None:
                    owner._commit_fetch(request_id, config, prepared)
                else:
                    owner._commit_fetch_error(request_id, config, str(error))

            _deliver._srpss_runtime_generation = runtime_generation
            ThreadManager.run_on_ui_thread(_deliver)

        _on_result._srpss_runtime_generation = runtime_generation
        try:
            self._thread_manager.submit_io_task(_do_fetch, callback=_on_result)
            return True
        except Exception as exc:
            self._fetch_in_progress = False
            self._deliver_refreshing(False)
            logger.exception("[REDDIT_RT] fetch submission failed: %s", exc)
            return False

    def _fetch_is_current(self, request_id: int, config: RedditRuntimeConfig) -> bool:
        return (
            not self._retired
            and self._running
            and request_id == self._fetch_request_id
            and config == self._config
        )

    def _commit_fetch(
        self,
        request_id: int,
        config: RedditRuntimeConfig,
        prepared: PreparedRedditFeed,
    ) -> None:
        if not self._fetch_is_current(request_id, config):
            return
        self._fetch_in_progress = False
        self._deliver_refreshing(False)
        if prepared.skip_reason:
            self._mark_periodic_terminal("all_sources_failed")
            return
        if not prepared.candidates:
            self._mark_periodic_terminal("all_sources_failed")
            self._deliver_error(
                "No authoritative Reddit posts remained after filtering"
                if prepared.filtered_empty
                else "No Reddit posts returned"
            )
            return
        self._startup_request_id += 1
        self._accepted_revision += 1
        self._candidates = tuple(prepared.candidates)
        self._mark_periodic_terminal("success")
        self._deliver_posts(
            self._candidates,
            from_cache=False,
            source_id=prepared.source_id,
            attempted_sources=tuple(prepared.attempted_sources),
        )

    def _commit_fetch_error(
        self,
        request_id: int,
        config: RedditRuntimeConfig,
        error: str,
    ) -> None:
        if not self._fetch_is_current(request_id, config):
            return
        self._fetch_in_progress = False
        self._deliver_refreshing(False)
        lowered = str(error or "").lower()
        if "403" in lowered or "429" in lowered or "blocked for url" in lowered:
            try:
                from core.reddit_rate_limiter import RedditRateLimiter

                RedditRateLimiter.record_blocked_response(reason=error)
            except Exception:
                logger.debug("[REDDIT_RT] blocked response record failed", exc_info=True)
            self._queue_service_gate_touch()
        self._mark_periodic_terminal("all_sources_failed")
        self._deliver_error(error)

    def _queue_service_gate_touch(self) -> None:
        if self._thread_manager is None:
            return
        path = self._service_gate_file_path()
        try:
            self._thread_manager.submit_io_task(
                touch_reddit_marker,
                path,
                "reddit_startup_gate\n",
            )
        except Exception:
            logger.debug("[REDDIT_RT] blocked gate persistence failed", exc_info=True)

    def stop(self) -> None:
        self._running = False
        self._shutdown_event.set()
        self._invalidate_async_results()
        self._fetch_in_progress = False
        self._deliver_refreshing(False)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self.stop()
        self._candidates = ()
        self._consumer_ref = None
        self._thread_manager = None


__all__ = [
    "RedditRuntimeConfig",
    "RedditRuntimeService",
    "normalize_subreddit",
]
