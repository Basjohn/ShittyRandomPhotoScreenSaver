"""Qt-free Reddit result preparation and post-cache persistence.

The Reddit widget owns provider selection and visible Qt state.  This module
owns the detached data work which can safely run on the shared I/O pool after
a provider response arrives.
"""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Iterable, Mapping

from core.logging.logger import get_logger
from core.logging.tags import LOG_FAMILY_CACHE


logger = get_logger(__name__, families=LOG_FAMILY_CACHE)

TITLE_FILTER_RE = re.compile(r"\b(daily|weekly|question thread)\b", re.IGNORECASE)
_HTML_SOURCE_IDS = frozenset({"html_old", "html_www"})
_CACHE_LOCKS_GUARD = threading.Lock()
_CACHE_LOCKS: dict[str, threading.RLock] = {}


def _cache_lock(cache_path: Path) -> threading.RLock:
    key = os.path.normcase(os.path.abspath(str(cache_path)))
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CACHE_LOCKS[key] = lock
        return lock


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


def read_reddit_post_cache(cache_path: Path) -> tuple[RedditPost, ...]:
    """Read the persisted candidate window, failing closed on malformed data."""

    path = Path(cache_path)
    try:
        with _cache_lock(path):
            if not path.exists():
                return ()
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        if not isinstance(data, list):
            return ()
        posts = tuple(RedditPost(**item) for item in data)
        logger.debug("[REDDIT] Loaded %d posts from cache: %s", len(posts), path)
        return posts
    except Exception:
        logger.debug("[REDDIT] Failed to load post cache: %s", path, exc_info=True)
        return ()


def write_reddit_post_cache(cache_path: Path, posts: Iterable[RedditPost]) -> bool:
    """Persist a detached candidate window without exposing Qt state."""

    path = Path(cache_path)
    snapshot = tuple(posts)
    temp_path: Path | None = None
    try:
        with _cache_lock(path):
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(post) for post in snapshot]
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


def prepare_reddit_feed(
    rows: Iterable[Mapping[str, object]],
    *,
    source_id: str | None,
    attempted_sources: Iterable[str],
    current_candidates: Iterable[RedditPost],
    cache_path: Path | None,
    cache_key: str,
    candidate_limit: int,
) -> PreparedRedditFeed:
    """Prepare, merge, sort, and persist one provider result off the GUI thread."""

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
        candidates = dedupe_reddit_candidates(incoming)
        source = str(source_id or "")
        is_html_fallback = source in _HTML_SOURCE_IDS or bool(
            _HTML_SOURCE_IDS.intersection(attempts)
        )
        if is_html_fallback and len(incoming) < limit:
            persisted = read_reddit_post_cache(path) if path is not None else ()
            existing = dedupe_reddit_candidates((*tuple(current_candidates), *persisted))
            if len(existing) > len(incoming):
                candidates = dedupe_reddit_candidates((*incoming, *existing))
                candidates = sort_reddit_candidates(candidates)[:limit]
                logger.info(
                    "[CACHE][REDDIT] Sparse fallback merged cache_key=%s source=%s attempted=%s "
                    "incoming=%d existing=%d merged=%d",
                    cache_key,
                    source_id or "<unknown>",
                    ",".join(attempts) or "<unknown>",
                    len(incoming),
                    len(existing),
                    len(candidates),
                )

        candidates = sort_reddit_candidates(candidates)[:limit]
        if path is not None:
            write_reddit_post_cache(path, candidates)

    return PreparedRedditFeed(
        candidates=tuple(candidates),
        source_id=source_id,
        attempted_sources=attempts,
        raw_count=len(raw_rows),
    )


__all__ = [
    "PreparedRedditFeed",
    "RedditPost",
    "TITLE_FILTER_RE",
    "candidate_identity",
    "dedupe_reddit_candidates",
    "normalize_reddit_rows",
    "prepare_reddit_feed",
    "read_reddit_post_cache",
    "sort_reddit_candidates",
    "write_reddit_post_cache",
]
