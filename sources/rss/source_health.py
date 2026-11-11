"""Wallpaper source identity and stored health, read without a fetch.

``RSSCoordinator`` names each wallpaper source's ``FeedSource`` record with the helpers here, and Settings reads the
health ``FeedSource`` persisted into those records (last check, last success, consecutive failures, last failure). No
network, timer, worker, directory creation or write lives here: a source that has never been fetched reads as
untried.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.feeds.cache import peek_feed_health
from core.feeds.models import FeedHealth
from core.feeds.normalization import endpoint_fingerprint
from core.feeds.transport import normalize_feed_address
from sources.rss.cache import pool_state_dir
from sources.rss.pools import pool_endpoint_source_ids

VALID = "valid"
FAILING = "failing"
UNTRIED = "untried"


@dataclass(frozen=True)
class SourceHealth:
    """One source's state as Settings shows it."""

    status: str = UNTRIED
    last_checked_at: float | None = None
    last_success_at: float | None = None
    reason: str = ""


def custom_feed_source_id(feed_url: str) -> str:
    """The ``FeedSource`` id of a custom feed URL (normalised as the coordinator admits it)."""
    return "wallpaper:endpoint:" + endpoint_fingerprint(normalize_feed_address(feed_url))


def pool_source_id(endpoint_source_id: str) -> str:
    """The ``FeedSource`` id of one pool endpoint (``PoolEndpoint.source_id``)."""
    return "wallpaper:pool:" + endpoint_source_id


def source_cache_key(source_id: str) -> str:
    return source_id.replace(":", "_")


def feed_store_dir(cache_dir: Path) -> Path:
    """Where the wallpaper pool's ``FeedCacheStore`` keeps its records, under the pool's cache directory."""
    return pool_state_dir(cache_dir) / "feeds"


def _health(health: FeedHealth | None) -> SourceHealth:
    if health is None or health.last_checked_at is None:
        return SourceHealth()
    if health.consecutive_failures > 0:
        return SourceHealth(FAILING, health.last_checked_at, health.last_success_at, health.last_failure)
    if health.last_success_at is not None:
        return SourceHealth(VALID, health.last_checked_at, health.last_success_at)
    return SourceHealth(UNTRIED, health.last_checked_at)


def _default_cache_dir() -> Path:
    from core.settings.storage_paths import get_rss_cache_dir

    return get_rss_cache_dir()


def read_custom_feed_health(feed_url: str, cache_dir: Path | None = None) -> SourceHealth:
    try:
        source_id = custom_feed_source_id(feed_url)
    except ValueError:
        return SourceHealth()
    store = feed_store_dir(cache_dir if cache_dir is not None else _default_cache_dir())
    return _health(peek_feed_health(store, source_cache_key(source_id)))


def read_pool_health(pool_id: str, cache_dir: Path | None = None) -> SourceHealth:
    """A pool's state from its most recently checked endpoint (NASA keeps one record per subject)."""
    store = feed_store_dir(cache_dir if cache_dir is not None else _default_cache_dir())
    records = [health for endpoint in pool_endpoint_source_ids(pool_id)
               if (health := peek_feed_health(store, source_cache_key(pool_source_id(endpoint)))) is not None
               and health.last_checked_at is not None]
    if not records:
        return SourceHealth()
    latest = max(records, key=lambda health: health.last_checked_at)
    successes = [health.last_success_at for health in records if health.last_success_at is not None]
    state = _health(latest)
    return SourceHealth(state.status, state.last_checked_at, max(successes) if successes else None, state.reason)
