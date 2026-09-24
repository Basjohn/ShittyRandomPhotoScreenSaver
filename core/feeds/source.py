"""One-shot cache-first feed source transaction.

There is deliberately no scheduler here.  ``widgets.feed_runtime`` owns due
times and workers; this source makes one bounded transaction and cannot create
polling/churn on its own.
"""
from __future__ import annotations

from dataclasses import replace
import logging
import time
from typing import TYPE_CHECKING, Callable

from .cache import FeedCacheStore
from .models import FeedCacheRecord, FeedHealth, FeedRefreshResult, FeedSnapshot, FeedSourceSpec
from .normalization import endpoint_fingerprint

if TYPE_CHECKING:
    from .transport import FeedHttpTransport


logger = logging.getLogger(__name__)


class FeedRefreshCancelled(RuntimeError):
    """An unobserved source was retired; not a provider failure or backoff."""


_BACKOFF_SECONDS = (60, 5 * 60, 15 * 60, 60 * 60, 6 * 60 * 60)


def _backoff_until(now: float, failures: int) -> float:
    index = min(max(1, failures), len(_BACKOFF_SECONDS)) - 1
    return now + _BACKOFF_SECONDS[index]


class FeedSource:
    def __init__(
        self,
        spec: FeedSourceSpec,
        *,
        transport: "FeedHttpTransport | None" = None,
        transport_factory: Callable[[], "FeedHttpTransport"] | None = None,
        cache: FeedCacheStore | None = None,
        should_continue: Callable[[], bool] | None = None,
        now=time.time,
        document_adapter: Callable[[bytes, str, int], object] | None = None,
    ) -> None:
        if transport is not None and transport_factory is not None:
            raise ValueError("provide transport or transport_factory, not both")
        self.spec = spec
        # Keep transport/parser machinery asleep during cache-only admission.
        # A fresh last-good snapshot can therefore paint without constructing a
        # requests.Session or importing feedparser at all.
        self.transport: "FeedHttpTransport | None" = transport
        self._transport_factory = transport_factory
        self.cache = cache or FeedCacheStore()
        self.now = now
        self._should_continue = should_continue
        # Optional reader for structured non-feed sources (wallpaper image
        # listings); FEEDS widgets never pass one.
        self._document_adapter = document_adapter

    def _ensure_needed(self) -> None:
        if self._should_continue is not None and not self._should_continue():
            raise FeedRefreshCancelled("feed source no longer active")

    def _transport_for_refresh(self) -> "FeedHttpTransport":
        if self.transport is None:
            if self._transport_factory is not None:
                self.transport = self._transport_factory()
            else:
                from .transport import FeedHttpTransport
                self.transport = FeedHttpTransport()
        return self.transport

    @property
    def fingerprint(self) -> str:
        return endpoint_fingerprint(self.spec.url)

    def load_cached(self) -> FeedRefreshResult:
        record = self._load_compatible_record()
        if record is None:
            return FeedRefreshResult("unavailable", None, FeedHealth(), failure="no_cache")
        return FeedRefreshResult(
            "available" if record.snapshot is not None else "unavailable",
            record.snapshot,
            record.health,
            failure=record.health.last_failure,
        )

    def refresh(self, *, force: bool = False) -> FeedRefreshResult:
        self._ensure_needed()
        now = float(self.now())
        record = self._load_compatible_record()
        if record is None:
            record = FeedCacheRecord(source_id=self.spec.source_id, endpoint_fingerprint=self.fingerprint)
        self._ensure_needed()
        health = record.health
        if not force and health.backoff_until is not None and now < health.backoff_until:
            return FeedRefreshResult(
                "backoff_cache" if record.snapshot is not None else "unavailable",
                record.snapshot,
                health,
                failure=health.last_failure or "backoff_active",
            )

        # Parser and HTTP dependencies are imported only for an actual network
        # refresh, never for cache-only startup.
        from .discovery import resolve_feed
        from .normalization import redacted_url_for_log
        from .parser import FeedParseError
        from .transport import FeedTransportError

        try:
            same_endpoint = record.endpoint_fingerprint == self.fingerprint
            # A site address resolves once to its feed; steady refreshes go
            # straight to that feed with its own validators. Discovery runs
            # again only when the resolution is gone or no longer a feed.
            resolved_url = record.resolved_url if same_endpoint else ""
            home_url = (
                record.snapshot.document.home_url
                if same_endpoint and record.snapshot is not None else ""
            )
            resolution = resolve_feed(
                self._transport_for_refresh().fetch,
                resolved_url or self.spec.url,
                etag=record.etag if same_endpoint else "",
                last_modified=record.last_modified if same_endpoint else "",
                configured_url=self.spec.url,
                home_url=home_url,
                max_items=self.spec.max_items,
                should_continue=self._should_continue,
                document_adapter=self._document_adapter,
            )
            self._ensure_needed()
            response = resolution.response
            if response.status == "not_modified":
                if record.snapshot is None or not same_endpoint:
                    return self._failure(record, now, "not_modified_without_matching_cache")
                updated = replace(
                    record,
                    etag=response.etag or record.etag,
                    last_modified=response.last_modified or record.last_modified,
                    health=FeedHealth(
                        last_checked_at=now,
                        last_success_at=now,
                        consecutive_failures=0,
                    ),
                )
                self._persist_best_effort(updated)
                return FeedRefreshResult("not_modified", updated.snapshot, updated.health, changed=False)

            document = resolution.document
            if document is None or not document.items:
                # A syntactically valid but empty replacement is not allowed to
                # erase established state.  Treat it like a transient source
                # failure and retain last-good under normal backoff.
                raise FeedParseError("feed contains no usable items")
            if resolution.discovered:
                logger.info(
                    "[FEEDS][DISCOVERY] source=%s address=%s feed=%s via=%s fetches=%d",
                    self.spec.source_id, redacted_url_for_log(self.spec.url),
                    redacted_url_for_log(resolution.feed_url), resolution.via, resolution.attempts,
                )
            snapshot = FeedSnapshot(document=document, fetched_at=now)
            changed = record.snapshot is None or record.snapshot.document != document
            updated = FeedCacheRecord(
                source_id=self.spec.source_id,
                endpoint_fingerprint=self.fingerprint,
                snapshot=snapshot,
                health=FeedHealth(last_checked_at=now, last_success_at=now),
                etag=response.etag,
                last_modified=response.last_modified,
                resolved_url="" if resolution.feed_url == self.spec.url else resolution.feed_url,
            )
            self._persist_best_effort(updated)
            return FeedRefreshResult("available", snapshot, updated.health, changed=changed)
        except (FeedTransportError, FeedParseError, ValueError, OSError) as exc:
            self._ensure_needed()
            return self._failure(record, now, type(exc).__name__)


    def _persist_best_effort(self, record: FeedCacheRecord) -> bool:
        self._ensure_needed()
        try:
            self.cache.write(self.spec.cache_key, record)
            return True
        except (OSError, ValueError) as exc:
            # A cache/storage failure must not convert a valid in-memory feed
            # generation into a runtime outage or destroy an already-loaded
            # last-good snapshot.  The next coordinator pulse may retry.
            logger.warning("Feed cache write failed for %s: %s", self.spec.source_id, type(exc).__name__)
            return False

    def _load_compatible_record(self) -> FeedCacheRecord | None:
        record = self.cache.read(self.spec.cache_key)
        if record is None:
            return None
        if record.source_id != self.spec.source_id:
            return None
        if record.endpoint_fingerprint != self.fingerprint and not self.spec.allow_endpoint_migration:
            return None
        return record

    def _failure(self, record: FeedCacheRecord, now: float, failure: str) -> FeedRefreshResult:
        failures = min(999, record.health.consecutive_failures + 1)
        health = FeedHealth(
            last_checked_at=now,
            last_success_at=record.health.last_success_at,
            consecutive_failures=failures,
            last_failure=str(failure)[:240],
            backoff_until=_backoff_until(now, failures),
        )
        updated = replace(record, health=health)
        self._persist_best_effort(updated)
        return FeedRefreshResult(
            "stale_cache" if record.snapshot is not None else "unavailable",
            record.snapshot,
            health,
            changed=False,
            failure=health.last_failure,
        )
