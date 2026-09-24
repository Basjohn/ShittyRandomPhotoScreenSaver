"""Immutable normalized models for RSS/Atom widget feeds."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FeedViewMode = Literal["list", "grid", "compact"]
FeedRefreshStatus = Literal[
    "available",
    "not_modified",
    "stale_cache",
    "backoff_cache",
    "unavailable",
]


@dataclass(frozen=True)
class FeedImageCandidate:
    url: str
    mime_type: str = ""
    width: int | None = None
    height: int | None = None
    relation: str = "feed"


@dataclass(frozen=True)
class FeedEnclosure:
    url: str
    mime_type: str = ""
    length: int | None = None


@dataclass(frozen=True)
class FeedItem:
    item_id: str
    title: str
    action_url: str = ""
    summary: str = ""
    author: str = ""
    published_at: int | None = None
    images: tuple[FeedImageCandidate, ...] = ()
    enclosures: tuple[FeedEnclosure, ...] = ()


@dataclass(frozen=True)
class FeedDocument:
    title: str
    home_url: str
    format: str
    items: tuple[FeedItem, ...]

    @property
    def image_item_count(self) -> int:
        return sum(1 for item in self.items if item.images)

    @property
    def image_coverage(self) -> float:
        return self.image_item_count / len(self.items) if self.items else 0.0


@dataclass(frozen=True)
class FeedSnapshot:
    document: FeedDocument
    fetched_at: float


@dataclass(frozen=True)
class FeedHealth:
    last_checked_at: float | None = None
    last_success_at: float | None = None
    consecutive_failures: int = 0
    last_failure: str = ""
    backoff_until: float | None = None


@dataclass(frozen=True)
class FeedCacheRecord:
    source_id: str
    endpoint_fingerprint: str
    snapshot: FeedSnapshot | None = None
    health: FeedHealth = FeedHealth()
    etag: str = ""
    last_modified: str = ""
    schema_version: int = 1
    # The discovered feed serving this endpoint when the configured address is
    # a site page (``""``: the configured address is the feed). ETag and
    # Last-Modified belong to this URL. An optional field inside schema 1:
    # older records read as ``""`` and older readers ignore it.
    resolved_url: str = ""


@dataclass(frozen=True)
class FeedSourceSpec:
    """One logical source and its cache identity.

    ``cache_key`` is deliberately caller-authored.  Custom slots include the
    endpoint fingerprint in their cache key so changing a URL can never render
    the previous URL's state.  Built-in NEWS providers may later keep a stable
    provider cache key across endpoint replacement, allowing last-good state to
    survive an official URL migration until the replacement validates.
    """

    source_id: str
    url: str
    cache_key: str
    display_name: str = ""
    max_items: int = 50
    allow_endpoint_migration: bool = False


@dataclass(frozen=True)
class FeedRefreshResult:
    status: FeedRefreshStatus
    snapshot: FeedSnapshot | None
    health: FeedHealth
    changed: bool = False
    failure: str = ""
    # Worker-only local file URIs; never persisted with the article snapshot.
    # Immutable so two retained consumers share exactly one accepted generation.
    local_artwork_by_item: tuple[tuple[str, str], ...] = ()
