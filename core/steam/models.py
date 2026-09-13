"""Typed Steam provider/result models for the Steam widget family."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SteamSourceId(str, Enum):
    """Supported Steam data-source identifiers."""

    RECENTLY_PLAYED = "recently_played"
    OWNED_GAMES = "owned_games"
    PLAYER_ACHIEVEMENTS = "player_achievements"
    ACHIEVEMENT_SCHEMA = "achievement_schema"
    FRIEND_LIST = "friend_list"
    PLAYER_SUMMARIES = "player_summaries"
    APP_NEWS = "app_news"
    SINGLE_GAME_PLAYTIME = "single_game_playtime"
    NEWS_AUTHED = "news_authed"
    CHECK_APP_OWNERSHIP = "check_app_ownership"
    PUBLISHER_APP_OWNERSHIP = "publisher_app_ownership"


class SteamSourceStatus(str, Enum):
    """Source feasibility status used before user-facing cards are enabled."""

    CONFIRMED = "confirmed"
    CONDITIONAL = "conditional"
    UNAVAILABLE = "unavailable"
    EXCLUDED = "excluded"


class SteamResultStatus(str, Enum):
    """Provider/cache result classification safe for cards and settings UI."""

    SUCCESS = "success"
    NOT_CONFIGURED = "not_configured"
    PRIVATE = "private"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    PUBLISHER_ONLY = "publisher_only"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"
    CACHE_MISS = "cache_miss"
    CACHE_CORRUPT = "cache_corrupt"
    STALE_GENERATION = "stale_generation"
    BACKOFF_ACTIVE = "backoff_active"
    ASSET_INVALID = "asset_invalid"


@dataclass(frozen=True)
class SteamSourceEvidence:
    """Documented source capability/provenance for a Steam endpoint."""

    source_id: SteamSourceId
    status: SteamSourceStatus
    endpoint: str
    requires_user_key: bool
    publisher_only: bool = False
    public_without_key: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SteamResult:
    """Normalized provider/cache result with safe provenance."""

    status: SteamResultStatus
    source_id: SteamSourceId | None = None
    payload: Mapping[str, Any] | None = None
    message: str = ""
    http_status: int | None = None
    attempted_sources: tuple[SteamSourceId, ...] = field(default_factory=tuple)
    from_cache: bool = False
    fetched_at: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == SteamResultStatus.SUCCESS


@dataclass(frozen=True)
class SteamGameSummary:
    """Small normalized owned/recent game record."""

    appid: int
    name: str | None = None
    playtime_forever_minutes: int | None = None
    playtime_recent_minutes: int | None = None
    last_played_at: float | None = None
    last_played_confidence: str = "unknown"


@dataclass(frozen=True)
class SteamAchievementProgress:
    """Normalized achievement-progress snapshot for one app."""

    appid: int
    unlocked: int
    total: int
    percent: float | None = None


@dataclass(frozen=True)
class SteamFriendSummary:
    """Privacy-aware friend summary record."""

    steamid_fingerprint: str
    persona_name: str | None = None
    current_game_appid: int | None = None
    avatar_url: str | None = None
    relationship: str | None = None


@dataclass(frozen=True)
class SteamNewsItem:
    """Public app-news item with source-owned timestamp."""

    appid: int
    title: str
    url: str | None = None
    published_at: float | None = None
    feed_name: str | None = None
