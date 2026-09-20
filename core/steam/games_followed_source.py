"""Bounded, opt-in source/cache foundation for Games You Follow.

No Qt, worker, timer, widget or Settings access. One existing Steam worker/owner
may call refresh() on demand after an explicit linked-identity admission. Only
accepted, validated private records reach the existing profile-scoped cache;
failed/partial fetches never overwrite its last-good snapshot.
"""
from __future__ import annotations

import time
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.steam.backend import build_endpoint, fetch_json
from core.steam.cache import (
    SteamCacheRecord, cache_path_for_profile_key, get_steam_source_refresh_lock,
    read_cache_record, write_cache_record,
)
from core.steam.games_followed_probe import fetch_followed_appids_for_news_probe
from core.steam.credentials import derive_profile_cache_key
from core.steam.links import news_article_target
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import SteamBackoffPolicy, SteamRequestCoordinator, SteamRequestKey

CACHE_KEY = "games_you_follow_news"
CACHE_PAYLOAD_VERSION = 1
MAX_NEWS_APPS_PER_REFRESH = 4
MAX_NEWS_ITEMS_PER_APP = 3
MAX_SELECTED_STORIES = 8
NEWS_MAX_RESPONSE_BYTES = 192_000
NEWS_TIMEOUT_SECONDS = 6.0

# Existing source backoff, not a new schedule or a recurring retry owner.
_RETRYABLE_FAILURES = frozenset({
    SteamResultStatus.NETWORK_ERROR.value,
    SteamResultStatus.RATE_LIMITED.value,
    SteamResultStatus.UNAUTHORIZED.value,
    SteamResultStatus.PRIVATE.value,
    SteamResultStatus.INVALID_RESPONSE.value,
})


@dataclass(frozen=True)
class FollowedNewsStory:
    """Private source identity; UI must project display fields separately."""
    appid: int
    gid: str
    title: str
    published_at: int
    feed_name: str
    action_available: bool


@dataclass(frozen=True)
class FollowedNewsSnapshot:
    status: str
    stories: tuple[FollowedNewsStory, ...] = ()
    followed_count: int = 0
    checked_count: int = 0
    window_offset: int = 0
    fetched_at: float | None = None
    from_cache: bool = False
    failure: str | None = None


def _appid(value: object) -> bool:
    return type(value) is int and 0 < value <= 0xFFFFFFFF


def _valid_title(value: object) -> bool:
    return type(value) is str and bool(value.strip()) and len(value) <= 300


def normalize_app_news(payload: Mapping[str, Any], appid: int) -> tuple[FollowedNewsStory, ...] | None:
    """Exact requested AppID, bounded data, no HTML or provider URLs in result."""
    if not isinstance(payload, Mapping) or not _appid(appid):
        return None
    news = payload.get("appnews")
    if not isinstance(news, Mapping) or type(news.get("appid")) is not int or news.get("appid") != appid:
        return None
    rows = news.get("newsitems")
    if not isinstance(rows, list) or len(rows) > MAX_NEWS_ITEMS_PER_APP:
        return None
    seen: set[str] = set()
    normalized: list[FollowedNewsStory] = []
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        gid, title, date = row.get("gid"), row.get("title"), row.get("date")
        feed = row.get("feedlabel", "")
        if (
            type(gid) is not str or not gid.isascii() or not gid.isdecimal()
            or not 1 <= len(gid) <= 32 or gid in seen
            or not _valid_title(title)
            or type(date) is not int or not 0 < date < 4_102_444_800
            or type(feed) is not str or len(feed) > 80
        ):
            return None
        seen.add(gid)
        # A canonical URL may permit a later owner-side action revalidation.
        # Never carry provider URL, HTML, image references or article bodies.
        action = news_article_target(appid, gid, row.get("url")) is not None
        normalized.append(FollowedNewsStory(appid, gid, title.strip(), date, feed.strip(), action))
    return tuple(normalized)


def _snapshot_from_cache(path: Path) -> FollowedNewsSnapshot | None:
    result = read_cache_record(path)
    if not result.ok or result.source_id != SteamSourceId.GAMES_FOLLOWED:
        return None
    p = result.payload
    if not isinstance(p, Mapping) or type(p.get("schema")) is not int or p["schema"] != CACHE_PAYLOAD_VERSION:
        return None
    follow, checked, offset = p.get("followed_count"), p.get("checked_count"), p.get("window_offset")
    rows = p.get("stories")
    if (type(follow) is not int or not 0 <= follow <= 4096
        or type(checked) is not int or not 0 <= checked <= min(follow, MAX_NEWS_APPS_PER_REFRESH)
        or type(offset) is not int or not 0 <= offset <= max(0, follow - 1)
        or not isinstance(rows, list) or len(rows) > MAX_SELECTED_STORIES):
        return None
    stories: list[FollowedNewsStory] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        appid, gid, title, date = row.get("appid"), row.get("gid"), row.get("title"), row.get("published_at")
        feed, action = row.get("feed_name"), row.get("action_available")
        if (not _appid(appid) or type(gid) is not str or not gid.isascii() or not gid.isdecimal()
            or not 1 <= len(gid) <= 32 or not _valid_title(title)
            or type(date) is not int or not 0 < date < 4_102_444_800
            or type(feed) is not str or len(feed) > 80 or type(action) is not bool
            or (appid, gid) in seen or follow == 0):
            return None
        seen.add((appid, gid))
        stories.append(FollowedNewsStory(appid, gid, title, date, feed, action))
    if result.fetched_at is None or not 0 < result.fetched_at <= time.time() + 60:
        return None
    return FollowedNewsSnapshot("available" if stories else "no_usable_news" if follow else "empty_follow_list",
                                tuple(stories), follow, checked, offset, result.fetched_at, from_cache=True)


class FollowedNewsSource:
    """One explicit source invocation; the future Steam owner supplies its worker."""

    def __init__(self, *, profile_key: str, cache_root: Path | None = None,
                 coordinator: SteamRequestCoordinator | None = None,
                 backoff: SteamBackoffPolicy | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not isinstance(profile_key, str) or not profile_key.startswith("profile_"):
            raise ValueError("Expected an opaque Steam profile cache key")
        self._profile_key = profile_key
        self._path = cache_path_for_profile_key(profile_key, CACHE_KEY, root=cache_root)
        self._coordinator = coordinator or SteamRequestCoordinator()
        self._backoff = backoff or SteamBackoffPolicy()
        self._clock = clock
        self._state_lock = threading.RLock()
        self._closed = False

    def cached(self) -> FollowedNewsSnapshot | None:
        return _snapshot_from_cache(self._path)

    def retire(self) -> None:
        with self._state_lock:
            self._closed = True
            self._coordinator.advance_generation()

    def refresh(self, steamid: str, *, opener: Callable[..., Any] | None = None,
                window_offset: int = 0) -> FollowedNewsSnapshot:
        """Call from one admitted Steam worker, never the GUI/render or resize path."""
        if self._closed:
            return FollowedNewsSnapshot("retired")
        if type(window_offset) is not int or window_offset < 0:
            return FollowedNewsSnapshot("invalid_request")
        # A caller may not accidentally read or overwrite another account's
        # last-good snapshot after a linked-identity or display-generation swap.
        if (type(steamid) is not str or len(steamid) != 17 or not steamid.isascii()
            or not steamid.isdecimal() or derive_profile_cache_key(steamid) != self._profile_key):
            return FollowedNewsSnapshot("invalid_identity")
        # This lock is the existing profile-private cache/source serialization,
        # not a timer or an independently scheduled worker.
        with get_steam_source_refresh_lock(self._profile_key, CACHE_KEY):
            if self._closed:
                return FollowedNewsSnapshot("retired")
            previous = self.cached()
            key = SteamRequestKey.from_params(profile_key=self._profile_key,
                                               source_id=SteamSourceId.GAMES_FOLLOWED,
                                               category=CACHE_KEY)
            decision = self._backoff.check(key, now=self._clock())
            if not decision.allowed:
                # Never reissue the followed-set request or any app-news work
                # while a denied/rate-limited source is cooling down. Cached
                # rows retain their original fetched_at and private identity.
                return (replace(previous, status="stale_cache", failure="backoff_active")
                        if previous is not None else FollowedNewsSnapshot("backoff_active"))
            handle = self._coordinator.begin(key)
            if not handle.owner:
                return previous or FollowedNewsSnapshot("already_refreshing")
            status, followed = fetch_followed_appids_for_news_probe(steamid, opener=opener)
            if status != "confirmed_nonempty" and status != "confirmed_empty":
                return self._finish_failure(handle, previous, status)
            assert followed is not None
            if not followed:
                selected: tuple[int, ...] = ()
                offset = 0
            else:
                offset = window_offset % len(followed)
                # Rotate a bounded selection in canonical follow order. Card
                # width/height cannot change this window or perform a request.
                selected = tuple(followed[(offset + i) % len(followed)]
                                 for i in range(min(len(followed), MAX_NEWS_APPS_PER_REFRESH)))
            candidates: list[FollowedNewsStory] = []
            for appid in selected:
                endpoint = replace(
                    build_endpoint(SteamSourceId.APP_NEWS, appid=appid, count=MAX_NEWS_ITEMS_PER_APP),
                    timeout_seconds=NEWS_TIMEOUT_SECONDS,
                    max_response_bytes=NEWS_MAX_RESPONSE_BYTES,
                )
                result = fetch_json(endpoint, opener=opener)
                if result.status is not SteamResultStatus.SUCCESS:
                    return self._finish_failure(handle, previous, result.status.value)
                rows = normalize_app_news(result.payload or {}, appid)
                if rows is None:
                    return self._finish_failure(handle, previous, "invalid_response")
                candidates.extend(rows)
            # A bounded deterministic selection; separate the complete followed
            # count from this request's intentionally limited app/news window.
            candidates.sort(key=lambda item: (-item.published_at, item.appid, item.gid))
            accepted = tuple(candidates[:MAX_SELECTED_STORIES])
            # Retirement and final cache commit share this narrow lock. An
            # outstanding network response cannot republish after retirement.
            with self._state_lock:
                final = self._coordinator.complete(handle, SteamResult(
                    SteamResultStatus.SUCCESS, SteamSourceId.GAMES_FOLLOWED,
                    attempted_sources=(SteamSourceId.GAMES_FOLLOWED, SteamSourceId.APP_NEWS),
                ))
                if self._closed or final.status is SteamResultStatus.STALE_GENERATION:
                    return FollowedNewsSnapshot("retired")
                self._backoff.record_result(key, final, now=self._clock())
                payload = {
                    "schema": CACHE_PAYLOAD_VERSION,
                    "followed_count": len(followed),
                    "checked_count": len(selected),
                    "window_offset": offset,
                    "stories": [vars(story).copy() for story in accepted],
                }
                timestamp = time.time()
                write_cache_record(SteamCacheRecord(
                    cache_key=CACHE_KEY, source_id=SteamSourceId.GAMES_FOLLOWED,
                    payload=payload, fetched_at=timestamp,
                    attempted_sources=(SteamSourceId.GAMES_FOLLOWED, SteamSourceId.APP_NEWS),
                ), self._path)
                return FollowedNewsSnapshot(
                    "available" if accepted else "no_usable_news" if followed else "empty_follow_list",
                    accepted, len(followed), len(selected), offset, timestamp,
                )

    def _finish_failure(self, handle: object, previous: FollowedNewsSnapshot | None,
                        failure: str) -> FollowedNewsSnapshot:
        # One brief retirement/commit fence; never hold it during network IO.
        # A late failure from a retired generation may not arm a new backoff.
        with self._state_lock:
            status = (SteamResultStatus(failure) if failure in _RETRYABLE_FAILURES
                      else SteamResultStatus.INVALID_RESPONSE)
            result = self._coordinator.complete(handle, SteamResult(
                status, SteamSourceId.GAMES_FOLLOWED,
            ))
            if self._closed or result.status is SteamResultStatus.STALE_GENERATION:
                return FollowedNewsSnapshot("retired")
            self._backoff.record_result(handle.key, result, now=self._clock())
            if previous is not None:
                return replace(previous, status="stale_cache", failure=failure)
            return FollowedNewsSnapshot(failure)
