"""Explicit, read-only G0 news feasibility probe for confirmed followed games.

This is NOT a widget source, cache, scheduled scan, article launcher or asset
hydrator. It deliberately selects at most two verified follows, makes at most
one bounded public-news request per app, and returns counts/statuses only.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from core.steam.backend import build_endpoint, fetch_json
from core.steam.games_followed_probe import MAX_FOLLOWED_GAMES
from core.steam.models import SteamResultStatus, SteamSourceId

NEWS_PROBE_MAX_APPS = 2
NEWS_PROBE_ITEMS_PER_APP = 2
NEWS_PROBE_MAX_BYTES = 192_000
NEWS_PROBE_TIMEOUT_SECONDS = 6.0


@dataclass(frozen=True)
class FollowedNewsProbeResult:
    status: str
    apps_checked: int = 0
    usable_items: int = 0


def _is_appid(value: Any) -> bool:
    return type(value) is int and 0 < value <= 0xFFFFFFFF


def normalize_news_sample(payload: Mapping[str, Any], appid: int) -> int | None:
    """Validate one app-bound response; never accept or return provider URLs.

    Empty newsitems is a real empty response only when its enclosing response
    has the matching requested AppID and a correctly typed items list.
    """
    news = payload.get("appnews")
    if not isinstance(news, Mapping) or type(news.get("appid")) is not int or news.get("appid") != appid:
        return None
    items = news.get("newsitems")
    if not isinstance(items, list) or len(items) > NEWS_PROBE_ITEMS_PER_APP:
        return None
    seen: set[str] = set()
    for row in items:
        if not isinstance(row, Mapping):
            return None
        gid = row.get("gid")
        title = row.get("title")
        published_at = row.get("date")
        if (
            not isinstance(gid, str) or not gid.isdecimal() or not 1 <= len(gid) <= 32
            or gid in seen or not isinstance(title, str) or not 1 <= len(title.strip()) <= 300
            or type(published_at) is not int or not 0 < published_at < 4_102_444_800
        ):
            return None
        seen.add(gid)
        # News URLs/content/image refs are deliberately ignored. They may not
        # become QML roles or clickable targets from a G0 probe.
    return len(items)


def probe_followed_news(
    followed_appids: Sequence[int],
    *,
    opener: Callable[..., Any] | None = None,
) -> FollowedNewsProbeResult:
    """Make <=2 public APP_NEWS calls for a *verified* supplied followed set.

    The caller owns the preceding read-only followed-set confirmation; this
    function does not discover follows, fetch a library or persist anything.
    """
    if (
        not isinstance(followed_appids, (tuple, list))
        or not 0 < len(followed_appids) <= MAX_FOLLOWED_GAMES
        or any(not _is_appid(value) for value in followed_appids)
        or len(set(followed_appids)) != len(followed_appids)
    ):
        return FollowedNewsProbeResult("invalid_followed_set")

    checked = 0
    usable = 0
    for appid in followed_appids[:NEWS_PROBE_MAX_APPS]:
        endpoint = replace(
            build_endpoint(SteamSourceId.APP_NEWS, appid=appid, count=NEWS_PROBE_ITEMS_PER_APP),
            timeout_seconds=NEWS_PROBE_TIMEOUT_SECONDS,
            max_response_bytes=NEWS_PROBE_MAX_BYTES,
        )
        result = fetch_json(endpoint, opener=opener)
        checked += 1
        if result.status is not SteamResultStatus.SUCCESS:
            return FollowedNewsProbeResult(result.status.value, checked, usable)
        sample_count = normalize_news_sample(result.payload or {}, appid)
        if sample_count is None:
            return FollowedNewsProbeResult("invalid_response", checked, usable)
        usable += sample_count
    return FollowedNewsProbeResult(
        "confirmed_nonempty_news" if usable else "confirmed_empty_news",
        checked,
        usable,
    )
