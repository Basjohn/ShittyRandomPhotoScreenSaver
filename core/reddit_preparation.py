"""Qt-free Reddit result preparation and per-subreddit reservoir persistence.

The Reddit widget owns provider selection and visible Qt state.  This module
owns the detached data work which can safely run on the shared I/O pool after
a provider response arrives.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Iterable, Mapping

from core.logging.logger import get_logger
from core.logging.tags import LOG_FAMILY_CACHE


logger = get_logger(__name__, families=LOG_FAMILY_CACHE)

TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)
RESERVOIR_SCHEMA = 2
# Capacity bound only: posts never expire by age, and a sparse or failed fetch
# never shrinks the reservoir. Eviction happens only when newer valid posts
# would grow it past this size.
REDDIT_RESERVOIR_CAPACITY = 1000
_RESERVOIR_SLUG_RE = re.compile(r"[^a-z0-9_+-]")
_CACHE_LOCKS_GUARD = threading.Lock()
_CACHE_LOCKS: dict[str, threading.RLock] = {}
_TIMESTAMP_REGISTRY_GUARD = threading.Lock()
_TIMESTAMP_REGISTRY: dict[str, datetime | None] = {}


def _normalized_path_key(cache_path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(cache_path)))


def _cache_lock(cache_path: Path) -> threading.RLock:
    key = _normalized_path_key(cache_path)
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CACHE_LOCKS[key] = lock
        return lock


def _record_cached_timestamp(cache_path: Path, timestamp: datetime | None) -> None:
    with _TIMESTAMP_REGISTRY_GUARD:
        _TIMESTAMP_REGISTRY[_normalized_path_key(cache_path)] = timestamp


def get_reddit_cached_timestamp(cache_path: Path) -> datetime | None:
    """Return process-cached file metadata without touching the filesystem."""

    with _TIMESTAMP_REGISTRY_GUARD:
        return _TIMESTAMP_REGISTRY.get(_normalized_path_key(cache_path))


def refresh_reddit_cached_timestamp(cache_path: Path) -> datetime | None:
    """Refresh one path timestamp from disk; callers must own an I/O thread."""

    path = Path(cache_path)
    try:
        timestamp = datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else None
    except Exception:
        logger.debug("[REDDIT] Failed to inspect persisted timestamp: %s", path, exc_info=True)
        timestamp = None
    _record_cached_timestamp(path, timestamp)
    return timestamp


@dataclass(frozen=True)
class RedditPost:
    """Immutable post snapshot shared between worker preparation and Qt."""

    title: str
    url: str
    score: int
    created_utc: float


@dataclass(frozen=True)
class PreparedRedditFeed:
    """One immutable worker result ready for a lightweight GUI commit."""

    candidates: tuple[RedditPost, ...]
    source_id: str | None
    attempted_sources: tuple[str, ...]
    raw_count: int
    skip_reason: str | None = None

    @property
    def filtered_empty(self) -> bool:
        return self.raw_count > 0 and not self.candidates


@dataclass(frozen=True)
class RedditStartupSnapshot:
    """Detached startup cache and persisted gate state loaded by an I/O task."""

    candidates: tuple[RedditPost, ...]
    cache_timestamp: datetime | None
    service_gate_timestamp: datetime | None


def candidate_identity(post: RedditPost) -> str:
    """Return the stable URL-first identity used by sparse-cache merging."""

    url = str(post.url or "").strip().lower()
    if url:
        url = url.split("#", 1)[0].split("?", 1)[0].rstrip("/")
        if url:
            return f"url:{url}"
    title = str(post.title or "").strip().casefold()
    return f"title:{title}"


def dedupe_reddit_candidates(posts: Iterable[RedditPost]) -> tuple[RedditPost, ...]:
    """Deduplicate candidates while keeping the newest duplicate snapshot."""

    deduped: dict[str, RedditPost] = {}
    for post in posts:
        key = candidate_identity(post)
        if not key or key == "title:":
            continue
        existing = deduped.get(key)
        if existing is None or post.created_utc >= existing.created_utc:
            deduped[key] = post
    return tuple(deduped.values())


def sort_reddit_candidates(posts: Iterable[RedditPost]) -> tuple[RedditPost, ...]:
    """Sort dated candidates newest-first and leave undated rows at the end."""

    snapshot = tuple(posts)
    try:
        return tuple(
            sorted(
                snapshot,
                key=lambda post: (
                    1 if float(post.created_utc or 0.0) <= 0.0 else 0,
                    -float(post.created_utc or 0.0),
                ),
            )
        )
    except Exception:
        logger.debug("[REDDIT] Failed to sort prepared Reddit candidates", exc_info=True)
        return snapshot


def normalize_reddit_rows(rows: Iterable[Mapping[str, object]]) -> tuple[RedditPost, ...]:
    """Normalize provider dictionaries into immutable display candidates."""

    posts: list[RedditPost] = []
    for raw in rows:
        if not isinstance(raw, Mapping):
            continue
        title = str(raw.get("title") or "").strip()
        url = str(raw.get("url") or "").strip()
        if not title or not url:
            continue
        if TITLE_FILTER_RE.search(title):
            continue

        try:
            score = int(raw.get("score") or 0)
        except Exception:
            logger.debug("[REDDIT] Invalid score in provider row", exc_info=True)
            score = 0

        try:
            created_utc = float(raw.get("created_utc") or 0.0)
        except Exception:
            logger.debug("[REDDIT] Invalid timestamp in provider row", exc_info=True)
            created_utc = 0.0

        posts.append(
            RedditPost(
                title=title,
                url=url,
                score=score,
                created_utc=created_utc,
            )
        )
    return tuple(posts)


def subreddit_identity(subreddit: object) -> str:
    """Return the case-insensitive identity that owns one reservoir."""

    return str(subreddit or "").strip().casefold()


def reddit_reservoir_path(cache_dir: Path, cache_key: str, subreddit: object) -> Path:
    """Return one member's reservoir file for one subreddit identity.

    The file also records the identity it belongs to; the filename is only a
    sanitized locator, so a sanitizing collision fails closed on read.
    """

    identity = subreddit_identity(subreddit)
    slug = _RESERVOIR_SLUG_RE.sub("_", identity) or "_"
    return Path(cache_dir) / f"{cache_key}__{slug}_posts.json"


def read_reddit_post_cache(cache_path: Path, subreddit: object) -> tuple[RedditPost, ...]:
    """Read one subreddit's persisted reservoir, failing closed on malformed data.

    Payloads without a matching subreddit identity (including the retired
    unidentified list format) are not attributed to ``subreddit``.
    """

    path = Path(cache_path)
    identity = subreddit_identity(subreddit)
    try:
        with _cache_lock(path):
            if not path.exists():
                return ()
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        if (
            not isinstance(data, dict)
            or data.get("schema") != RESERVOIR_SCHEMA
            or not identity
            or data.get("subreddit") != identity
            or not isinstance(data.get("posts"), list)
        ):
            logger.debug("[REDDIT] Ignored unidentified post cache: %s", path)
            return ()
        posts = tuple(RedditPost(**item) for item in data["posts"])
        logger.debug("[REDDIT] Loaded %d posts from cache: %s", len(posts), path)
        return posts
    except Exception:
        logger.debug("[REDDIT] Failed to load post cache: %s", path, exc_info=True)
        return ()


def write_reddit_post_cache(
    cache_path: Path,
    posts: Iterable[RedditPost],
    subreddit: object,
) -> bool:
    """Persist one subreddit's detached reservoir without exposing Qt state."""

    path = Path(cache_path)
    snapshot = tuple(posts)
    identity = subreddit_identity(subreddit)
    if not identity:
        logger.debug("[REDDIT] Refused post cache without subreddit identity: %s", path)
        return False
    temp_path: Path | None = None
    try:
        with _cache_lock(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "schema": RESERVOIR_SCHEMA,
                "subreddit": identity,
                "posts": [asdict(post) for post in snapshot],
            }
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(data, handle, indent=2)
                handle.flush()
            os.replace(temp_path, path)
            temp_path = None
            refresh_reddit_cached_timestamp(path)
        logger.debug("[REDDIT] Saved %d posts to cache: %s", len(snapshot), path)
        return True
    except Exception:
        logger.debug("[REDDIT] Failed to save post cache: %s", path, exc_info=True)
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("[REDDIT] Failed to remove cache temp file: %s", temp_path, exc_info=True)


def load_reddit_startup_snapshot(
    cache_path: Path,
    service_gate_path: Path,
    *,
    subreddit: object,
    candidate_limit: int,
) -> RedditStartupSnapshot:
    """Load the display window and persisted timing metadata for one startup decision."""

    limit = max(1, int(candidate_limit))
    posts = sort_reddit_candidates(read_reddit_post_cache(cache_path, subreddit))[:limit]
    return RedditStartupSnapshot(
        candidates=posts,
        cache_timestamp=refresh_reddit_cached_timestamp(cache_path),
        service_gate_timestamp=refresh_reddit_cached_timestamp(service_gate_path),
    )


def touch_reddit_marker(marker_path: Path, marker_text: str) -> datetime | None:
    """Create/touch one Reddit control marker on an I/O thread."""

    path = Path(marker_path)
    try:
        with _cache_lock(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(str(marker_text), encoding="utf-8")
            now = time.time()
            path.touch()
            os.utime(path, (now, now))
            timestamp = datetime.fromtimestamp(now)
            _record_cached_timestamp(path, timestamp)
            return timestamp
    except Exception:
        logger.debug("[REDDIT] Failed to touch persisted marker: %s", path, exc_info=True)
        return None


def prepare_reddit_feed(
    rows: Iterable[Mapping[str, object]],
    *,
    source_id: str | None,
    attempted_sources: Iterable[str],
    current_candidates: Iterable[RedditPost],
    cache_path: Path | None,
    cache_key: str,
    subreddit: object,
    candidate_limit: int,
) -> PreparedRedditFeed:
    """Merge one provider result into the subreddit reservoir off the GUI thread.

    Every source merges before display selection: incoming rows join the
    persisted reservoir and the accepted in-memory window, so successive small
    batches accumulate instead of replacing one another. ``candidates`` is the
    newest ``candidate_limit`` posts of the merged reservoir. An empty result
    neither writes nor freshens the reservoir.
    """

    raw_rows = tuple(rows)
    attempts = tuple(str(item) for item in attempted_sources)
    incoming = normalize_reddit_rows(raw_rows)
    if not incoming:
        return PreparedRedditFeed(
            candidates=(),
            source_id=source_id,
            attempted_sources=attempts,
            raw_count=len(raw_rows),
        )

    limit = max(1, int(candidate_limit))
    path = Path(cache_path) if cache_path is not None else None
    cache_guard = _cache_lock(path) if path is not None else nullcontext()
    with cache_guard:
        persisted = read_reddit_post_cache(path, subreddit) if path is not None else ()
        retained = dedupe_reddit_candidates((*persisted, *tuple(current_candidates)))
        # Incoming rows come last so a re-fetched post keeps its newest snapshot.
        reservoir = sort_reddit_candidates(
            dedupe_reddit_candidates((*retained, *incoming))
        )[:REDDIT_RESERVOIR_CAPACITY]
        if path is not None:
            write_reddit_post_cache(path, reservoir, subreddit)
        candidates = reservoir[:limit]
        logger.info(
            "[CACHE][REDDIT] Reservoir merged cache_key=%s subreddit=%s source=%s attempted=%s "
            "incoming=%d retained=%d reservoir=%d window=%d",
            cache_key,
            subreddit_identity(subreddit) or "<none>",
            source_id or "<unknown>",
            ",".join(attempts) or "<unknown>",
            len(incoming),
            len(retained),
            len(reservoir),
            len(candidates),
        )

    return PreparedRedditFeed(
        candidates=tuple(candidates),
        source_id=source_id,
        attempted_sources=attempts,
        raw_count=len(raw_rows),
    )


__all__ = [
    "PreparedRedditFeed",
    "REDDIT_RESERVOIR_CAPACITY",
    "RESERVOIR_SCHEMA",
    "RedditPost",
    "RedditStartupSnapshot",
    "TITLE_FILTER_RE",
    "candidate_identity",
    "dedupe_reddit_candidates",
    "get_reddit_cached_timestamp",
    "load_reddit_startup_snapshot",
    "normalize_reddit_rows",
    "prepare_reddit_feed",
    "read_reddit_post_cache",
    "reddit_reservoir_path",
    "refresh_reddit_cached_timestamp",
    "sort_reddit_candidates",
    "subreddit_identity",
    "touch_reddit_marker",
    "write_reddit_post_cache",
]
