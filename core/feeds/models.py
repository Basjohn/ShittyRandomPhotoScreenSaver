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

    def __post_init__(self) -> None:
        """Keep item identity usable by cache, artwork and retained rows."""
        item_ids = tuple(item.item_id for item in self.items)
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("feed document contains duplicate item identities")

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
    # Durable accepted artwork binding for warm-start presentation. Values are
    # cache-owned PNG filenames, never arbitrary paths or remote URLs. Older
    # schema-1 records omit this optional field and read as empty.
    artwork_files_by_item: tuple[tuple[str, str], ...] = ()


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
    # Accepted local file URIs projected from the durable artwork binding.
    # Immutable so two retained consumers share exactly one accepted generation.
    local_artwork_by_item: tuple[tuple[str, str], ...] = ()
    # Cache-owned filenames backing ``local_artwork_by_item``.  These are never
    # exposed to QML; they travel with the immutable accepted generation so an
    # artwork worker can atomically persist the item -> file association into
    # the durable last-good feed record without reverse-engineering file URIs.
    artwork_files_by_item: tuple[tuple[str, str], ...] = ()
    # Presentation settlement is runtime-only coordination metadata. FeedSource
    # itself returns a complete text snapshot, so standalone results default to
    # settled. The shared FEEDS owner temporarily projects False while one
    # source bundle still has immediate remote/artwork follow-on work. NEWS then
    # combines provider settlement so presentation never animates each hydration
    # step as a separate content replacement. This field is never persisted.
    presentation_settled: bool = True
    # Runtime-only startup barrier. The shared FEEDS owner keeps this False
    # until *all currently active sources* have completed their first cache ->
    # due network -> optional artwork admission. Presentation may retain one
    # cache-first body while False, but must not arm article-change fades. Once
    # True it is sticky for the accepted source generation and later ordinary
    # refreshes are eligible for the slow body transition. Standalone results
    # default True so non-runtime projection/tests keep their historical meaning.
    initial_admission_complete: bool = True
