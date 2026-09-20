"""Presentation-safe, layout-independent projection of followed-game news.

This is a pure source -> view boundary, NOT a second Steam runtime owner. It
never reads a cache, schedules a refresh, opens an article, or exposes account,
AppID, GID, provider URLs, or arbitrary feed HTML to a retained QML item.
The QML owner will resolve a user click against the private accepted snapshot
again, only after the secure Steam action route has been admitted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .games_followed_source import FollowedNewsSnapshot


@dataclass(frozen=True)
class FollowedNewsDisplayRow:
    slot: int
    title: str
    source_label: str
    published_label: str
    # Intentionally not a capability flag until the action helper is proven.
    action_enabled: bool = False
    local_artwork_source: str = ""


@dataclass(frozen=True)
class FollowedNewsDisplay:
    status: str
    status_label: str
    rows: tuple[FollowedNewsDisplayRow, ...]
    remaining_followed_count: int
    checked_count: int
    stale: bool
    # This is *not* the count of all apps with news, only this bounded window.
    selected_story_count: int


def _display_text(value: str, max_chars: int) -> str:
    """Plain-text-only label with bounded controls and normalized whitespace."""
    if type(value) is not str:
        return ""
    normalized = " ".join(value.split())
    return "".join(c for c in normalized if c.isprintable())[:max_chars]


def project_followed_news(snapshot: FollowedNewsSnapshot) -> FollowedNewsDisplay:
    """Project one accepted source revision, not one display or resize event."""
    if not isinstance(snapshot, FollowedNewsSnapshot):
        raise TypeError("A normalized followed-news snapshot is required")
    rows = tuple(
        FollowedNewsDisplayRow(
            slot=index,
            title=_display_text(story.title, 300),
            source_label=_display_text(story.feed_name, 80) or "Steam News",
            published_label=datetime.fromtimestamp(
                story.published_at, tz=timezone.utc
            ).strftime("%d %b %Y"),
        )
        for index, story in enumerate(snapshot.stories[:8])
    )
    status = snapshot.status
    if status == "empty_follow_list":
        label = "No games followed"
    elif status in {"available", "stale_cache"} and rows:
        label = "Cached updates" if snapshot.from_cache or status == "stale_cache" else "Latest updates"
    elif status == "no_usable_news":
        label = "No updates in checked games"
    elif status == "retired":
        label = ""
    else:
        label = "Updates temporarily unavailable"
    return FollowedNewsDisplay(
        status=status,
        status_label=label,
        rows=rows,
        remaining_followed_count=max(0, snapshot.followed_count - snapshot.checked_count),
        checked_count=snapshot.checked_count,
        stale=bool(snapshot.from_cache or status == "stale_cache"),
        selected_story_count=len(rows),
    )
