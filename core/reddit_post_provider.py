"""Reddit post-provider seam for the branded Reddit widget.

The widget owns rendering, cache authority, staged growth, cooldown UX, and
URL routing. This module owns only *where* post rows come from.
"""
from __future__ import annotations

from dataclasses import dataclass
from threading import Event
from typing import Any, Optional, Protocol

import requests

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.widget_capacity_policy import (
    LIST_WIDGET_MAX_CAPACITY,
    clamp_list_capacity,
)

logger = get_logger(__name__)

REDDIT_PROVIDER_PULLPUSH = "pullpush"
REDDIT_PROVIDER_PUBLIC_JSON = "public_json"
_VALID_PROVIDER_IDS = {
    REDDIT_PROVIDER_PULLPUSH,
    REDDIT_PROVIDER_PUBLIC_JSON,
}


@dataclass(frozen=True)
class RedditFetchRequest:
    """Normalized request payload for Reddit-like post retrieval."""

    subreddit: str
    sort: str
    limit: int
    cache_key: str
    shutdown_event: Optional[Event] = None


@dataclass(frozen=True)
class RedditProviderResult:
    """Provider result for the Reddit widget."""

    posts: list[dict[str, Any]] | None = None
    skip_reason: str | None = None

    @classmethod
    def with_posts(cls, posts: list[dict[str, Any]]) -> "RedditProviderResult":
        return cls(posts=list(posts), skip_reason=None)

    @classmethod
    def skipped(cls, reason: str) -> "RedditProviderResult":
        return cls(posts=None, skip_reason=str(reason or "skipped"))


class RedditPostProvider(Protocol):
    """Minimal provider contract for Reddit widget post retrieval."""

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        """Return normalized post rows or a skip reason."""


def normalize_reddit_provider_id(raw: object) -> str:
    """Normalize persisted/provider input to a supported provider id."""

    provider_id = str(raw or "").strip().lower()
    if provider_id in _VALID_PROVIDER_IDS:
        return provider_id
    return REDDIT_PROVIDER_PULLPUSH


class PullPushProvider:
    """Hosted PullPush provider for low-volume subreddit post retrieval."""

    provider_id = REDDIT_PROVIDER_PULLPUSH

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        effective_limit = clamp_list_capacity(request.limit)
        params = {
            "subreddit": request.subreddit,
            "sort": "desc",
            "sort_type": "created_utc",
            "size": min(LIST_WIDGET_MAX_CAPACITY, max(1, effective_limit)),
        }
        logger.debug(
            "[REDDIT] Fetching PullPush feed: subreddit=%s size=%s",
            request.subreddit,
            params["size"],
        )
        resp = requests.get(
            "https://api.pullpush.io/reddit/search/submission/",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()

        rows = payload.get("data")
        if not isinstance(rows, list):
            rows = []

        posts: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue

            permalink = str(row.get("permalink") or "").strip()
            direct_url = str(row.get("url") or "").strip()
            if permalink:
                url_str = permalink if permalink.startswith("http") else f"https://www.reddit.com{permalink}"
            elif direct_url:
                url_str = direct_url
            else:
                continue

            try:
                score = int(row.get("score") or 0)
            except Exception:
                score = 0
            try:
                created_utc = float(row.get("created_utc") or 0.0)
            except Exception:
                created_utc = 0.0

            posts.append(
                {
                    "title": title,
                    "url": url_str,
                    "score": score,
                    "created_utc": created_utc,
                }
            )

        return RedditProviderResult.with_posts(posts)


class RedditPublicJsonProvider:
    """Current public-JSON provider for the branded Reddit widget.

    This preserves the exact current public-endpoint behavior while giving the
    widget a swappable provider seam for future authenticated or external-feed
    backends.
    """

    provider_id = REDDIT_PROVIDER_PUBLIC_JSON

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        import time

        from core.reddit_rate_limiter import (
            RateLimitPriority,
            RedditRateLimiter,
            get_reddit_request_persona,
        )

        start_time = time.perf_counter()

        reserved_quota = RedditRateLimiter.reserve_quota(count=1, namespace="widget")
        if not reserved_quota:
            logger.warning("[RATE_LIMIT] Could not reserve quota for widget, waiting...")
        try:
            slot_state = RedditRateLimiter.acquire_request_slot(
                priority=RateLimitPriority.HIGH,
                namespace="widget",
                shutdown_event=request.shutdown_event,
                skip_if_blocked=True,
            )
        finally:
            if reserved_quota:
                RedditRateLimiter.release_quota(count=1, namespace="widget")

        if slot_state == "shutdown":
            return RedditProviderResult.skipped("shutdown")
        if slot_state == "blocked":
            logger.warning("[RATE_LIMIT] Reddit widget skipping fetch after blocked cooldown re-check")
            return RedditProviderResult.skipped("blocked_cooldown")

        url = f"https://www.reddit.com/r/{request.subreddit}/{request.sort}.json"
        persona = get_reddit_request_persona(
            f"{request.cache_key}:{request.subreddit}:{request.sort}"
        )
        headers = {"User-Agent": persona.user_agent, **persona.headers}

        effective_limit = clamp_list_capacity(request.limit)
        params = {"limit": LIST_WIDGET_MAX_CAPACITY}

        if is_perf_metrics_enabled():
            logger.debug(
                "[PERF] Reddit API call starting: subreddit=%s sort=%s",
                request.subreddit,
                request.sort,
            )
        else:
            logger.debug(
                "[REDDIT] Fetching feed: subreddit=%s sort=%s limit=%s (visible_limit=%s persona=%s)",
                request.subreddit,
                request.sort,
                params["limit"],
                effective_limit,
                persona.label,
            )

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 403:
            try:
                RedditRateLimiter.record_blocked_response(reason=f"widget:{request.subreddit}")
            except Exception:
                logger.debug("[REDDIT] Failed to record blocked Reddit response", exc_info=True)
        resp.raise_for_status()
        payload = resp.json()

        if is_perf_metrics_enabled():
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "[PERF] Reddit API call completed in %.2fms: subreddit=%s posts=%d",
                elapsed_ms,
                request.subreddit,
                len(payload.get("data", {}).get("children", [])),
            )

        children = payload.get("data", {}).get("children", [])
        posts: list[dict[str, Any]] = []
        for child in children:
            data = child.get("data") or {}
            title = str(data.get("title") or "").strip()
            if not title:
                continue
            try:
                score = int(data.get("score") or 0)
            except Exception:
                score = 0
            try:
                created_utc = float(data.get("created_utc") or 0.0)
            except Exception:
                created_utc = 0.0
            permalink = data.get("permalink")
            if permalink:
                url_str = f"https://www.reddit.com{permalink}"
            else:
                direct_url = data.get("url") or data.get("url_overridden_by_dest")
                if not direct_url:
                    continue
                url_str = str(direct_url)
            posts.append(
                {
                    "title": title,
                    "url": url_str,
                    "score": score,
                    "created_utc": created_utc,
                }
            )

        return RedditProviderResult.with_posts(posts)


def build_reddit_post_provider(provider: object | None = None) -> RedditPostProvider:
    """Build the configured provider for the branded Reddit widget."""

    provider_id = normalize_reddit_provider_id(provider)
    if provider_id == REDDIT_PROVIDER_PUBLIC_JSON:
        return RedditPublicJsonProvider()
    return PullPushProvider()


def build_default_reddit_post_provider(provider: object | None = None) -> RedditPostProvider:
    """Return the configured default provider for the branded Reddit widget."""

    return build_reddit_post_provider(provider)
