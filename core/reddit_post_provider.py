"""Reddit post-provider seam for the branded Reddit widget.

The widget owns rendering, cache authority, cooldown UX, visible-count slicing,
and URL routing. This module owns only *where* post rows come from.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import html
from html.parser import HTMLParser
import re
from threading import Event
from typing import Any, Optional, Protocol
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.widget_capacity_policy import (
    LIST_WIDGET_MAX_CAPACITY,
    clamp_list_capacity,
)

logger = get_logger(__name__)

REDDIT_PROVIDER_RSS = "rss"
REDDIT_PROVIDER_PULLPUSH = "pullpush"
REDDIT_PROVIDER_PUBLIC_JSON = "public_json"
REDDIT_PROVIDER_HTML = "html"
_VALID_PROVIDER_IDS = {
    REDDIT_PROVIDER_RSS,
    REDDIT_PROVIDER_PULLPUSH,
    REDDIT_PROVIDER_PUBLIC_JSON,
    REDDIT_PROVIDER_HTML,
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


class RedditProviderHttpError(RuntimeError):
    """Provider HTTP failure with enough context for composite fallback policy."""

    def __init__(self, provider_id: str, subreddit: str, status_code: int, url: str) -> None:
        self.provider_id = str(provider_id)
        self.subreddit = str(subreddit)
        self.status_code = int(status_code)
        self.url = str(url)
        super().__init__(
            f"Reddit provider {self.provider_id} failed for r/{self.subreddit} "
            f"with HTTP {self.status_code}: {self.url}"
        )


def normalize_reddit_provider_id(raw: object) -> str:
    """Normalize persisted/provider input to a supported provider id."""

    provider_id = str(raw or "").strip().lower()
    if provider_id in _VALID_PROVIDER_IDS:
        return provider_id
    return REDDIT_PROVIDER_RSS


def _acquire_widget_reddit_request_slot(request: RedditFetchRequest) -> str:
    """Acquire a shared Reddit-family request slot for widget fetches."""

    from core.reddit_rate_limiter import (
        RateLimitPriority,
        RedditRateLimiter,
    )

    reserved_quota = RedditRateLimiter.reserve_quota(count=1, namespace="widget")
    if not reserved_quota:
        logger.warning("[RATE_LIMIT] Could not reserve quota for widget, waiting...")
    try:
        return RedditRateLimiter.acquire_request_slot(
            priority=RateLimitPriority.HIGH,
            namespace="widget",
            shutdown_event=request.shutdown_event,
            skip_if_blocked=True,
        )
    finally:
        if reserved_quota:
            RedditRateLimiter.release_quota(count=1, namespace="widget")


def _record_reddit_blocked_response(reason: str) -> None:
    """Refresh the shared blocked cooldown after a Reddit-family block."""

    from core.reddit_rate_limiter import RedditRateLimiter

    try:
        RedditRateLimiter.record_blocked_response(reason=reason)
    except Exception:
        logger.debug("[REDDIT] Failed to record blocked Reddit response", exc_info=True)


def _build_reddit_request_headers(stable_key: str, *, accept: str) -> dict[str, str]:
    """Build stable persona headers for public Reddit-family endpoints."""

    from core.reddit_rate_limiter import get_reddit_request_persona

    persona = get_reddit_request_persona(stable_key)
    return {
        "User-Agent": persona.user_agent,
        **persona.headers,
        "Accept": accept,
    }


def _raise_for_reddit_http_status(
    resp: requests.Response,
    *,
    provider_id: str,
    subreddit: str,
    url: str,
    record_blocked: bool = True,
) -> None:
    """Raise a provider-aware error and optionally refresh the blocked gate."""

    status_code = int(getattr(resp, "status_code", 0) or 0)
    if status_code in {403, 429} and record_blocked:
        _record_reddit_blocked_response(f"{provider_id}:{subreddit}:{status_code}")
    if status_code >= 400:
        raise RedditProviderHttpError(provider_id, subreddit, status_code, url)


def _normalize_posts_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize heterogeneous provider rows into the widget's post shape."""

    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        title = str(row.get("title") or "").strip()
        if not title:
            continue

        url_str = str(row.get("url") or "").strip()
        if not url_str:
            continue

        try:
            score = int(row.get("score") or 0)
        except Exception:
            score = 0
        try:
            created_utc = float(row.get("created_utc") or 0.0)
        except Exception:
            created_utc = 0.0

        post = {
            "title": title,
            "url": url_str,
            "score": score,
            "created_utc": created_utc,
        }
        existing = deduped.get(url_str)
        if existing is None:
            deduped[url_str] = post
            continue
        if created_utc > float(existing.get("created_utc") or 0.0):
            deduped[url_str] = post
            continue
        if created_utc == float(existing.get("created_utc") or 0.0) and score > int(existing.get("score") or 0):
            deduped[url_str] = post

    posts = list(deduped.values())
    posts.sort(
        key=lambda post: (
            -float(post.get("created_utc") or 0.0),
            -int(post.get("score") or 0),
            str(post.get("title") or ""),
        )
    )
    return posts


def _parse_reddit_timestamp(value: object) -> float:
    """Parse Atom/RSS date strings into epoch seconds."""

    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(parsedate_to_datetime(text).timestamp())
    except Exception:
        pass
    try:
        normalized = text.replace("Z", "+00:00")
        return float(datetime.fromisoformat(normalized).timestamp())
    except Exception:
        return 0.0


class RedditRssProvider:
    """Fresh subreddit feed provider using Reddit's public RSS/Atom endpoint."""

    provider_id = REDDIT_PROVIDER_RSS

    def __init__(self, *, record_blocked: bool = True) -> None:
        self._record_blocked = bool(record_blocked)

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        slot_state = _acquire_widget_reddit_request_slot(request)
        if slot_state == "shutdown":
            return RedditProviderResult.skipped("shutdown")
        if slot_state == "blocked":
            logger.warning("[RATE_LIMIT] Reddit RSS widget skipping fetch after blocked cooldown re-check")
            return RedditProviderResult.skipped("blocked_cooldown")

        url = f"https://www.reddit.com/r/{request.subreddit}/.rss"
        headers = _build_reddit_request_headers(
            f"{request.cache_key}:{request.subreddit}:rss",
            accept="application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
        )
        logger.debug("[REDDIT] Fetching RSS feed: subreddit=%s", request.subreddit)
        resp = requests.get(url, headers=headers, timeout=10)
        _raise_for_reddit_http_status(
            resp,
            provider_id=self.provider_id,
            subreddit=request.subreddit,
            url=url,
            record_blocked=self._record_blocked,
        )
        resp.raise_for_status()
        posts = self._parse_feed(resp.content)
        logger.debug(
            "[REDDIT] RSS feed normalized: subreddit=%s rows=%s",
            request.subreddit,
            len(posts),
        )
        return RedditProviderResult.with_posts(posts)

    def _parse_feed(self, payload: bytes) -> list[dict[str, Any]]:
        root = ET.fromstring(payload)
        rows: list[dict[str, Any]] = []
        for entry in root.findall(".//{*}entry"):
            title = "".join(entry.findtext("{*}title", default="")).strip()
            if not title:
                continue

            link_href = ""
            for link_node in entry.findall("{*}link"):
                href = str(link_node.attrib.get("href") or "").strip()
                rel = str(link_node.attrib.get("rel") or "").strip().lower()
                if href and rel in {"alternate", ""}:
                    link_href = href
                    break
                if href and not link_href:
                    link_href = href
            if not link_href:
                link_href = str(entry.findtext("{*}id", default="")).strip()
            if not link_href:
                continue

            created_utc = _parse_reddit_timestamp(
                entry.findtext("{*}updated", default="") or entry.findtext("{*}published", default="")
            )
            rows.append(
                {
                    "title": title,
                    "url": link_href,
                    "score": 0,
                    "created_utc": created_utc,
                }
            )
        return _normalize_posts_from_rows(rows)


class PullPushProvider:
    """Hosted PullPush provider for low-volume subreddit post retrieval."""

    provider_id = REDDIT_PROVIDER_PULLPUSH

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        rows = self._fetch_rows(
            request.subreddit,
            size=max(1, clamp_list_capacity(request.limit)),
        )
        posts = self._normalize_rows(rows)
        logger.debug(
            "[REDDIT] PullPush feed normalized: subreddit=%s rows=%s",
            request.subreddit,
            len(posts),
        )
        return RedditProviderResult.with_posts(posts)

    def _fetch_rows(self, subreddit: str, *, size: int) -> list[dict[str, Any]]:
        params = {
            "subreddit": subreddit,
            "size": int(size),
        }
        logger.debug(
            "[REDDIT] Fetching PullPush feed: subreddit=%s size=%s",
            subreddit,
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
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _normalize_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
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

            normalized_rows.append(
                {
                    "title": title,
                    "url": url_str,
                    "score": row.get("score") or 0,
                    "created_utc": row.get("created_utc") or 0.0,
                }
            )
        return _normalize_posts_from_rows(normalized_rows)


class RedditPublicJsonProvider:
    """Current public-JSON provider for the branded Reddit widget.

    This preserves the exact current public-endpoint behavior while giving the
    widget a swappable provider seam for future authenticated or external-feed
    backends.
    """

    provider_id = REDDIT_PROVIDER_PUBLIC_JSON

    def __init__(self, *, record_blocked: bool = True) -> None:
        self._record_blocked = bool(record_blocked)

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        import time

        from core.reddit_rate_limiter import get_reddit_request_persona

        start_time = time.perf_counter()
        slot_state = _acquire_widget_reddit_request_slot(request)

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
        _raise_for_reddit_http_status(
            resp,
            provider_id=self.provider_id,
            subreddit=request.subreddit,
            url=url,
            record_blocked=self._record_blocked,
        )
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


class _RedditHtmlPostParser(HTMLParser):
    """Small targeted parser for Reddit listing HTML variants."""

    _COMMENT_RE = re.compile(r"/r/[^/]+/comments/[^/\s\"']+", re.IGNORECASE)

    def __init__(self, subreddit: str, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.subreddit = str(subreddit or "").strip()
        self.base_url = str(base_url)
        self.rows: list[dict[str, Any]] = []
        self._active_row: dict[str, Any] | None = None
        self._capture_title: dict[str, Any] | None = None
        self._capture_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {str(key).lower(): str(value or "") for key, value in attrs}
        tag_l = tag.lower()
        if tag_l == "shreddit-post":
            row = self._row_from_shreddit_attrs(attr_map)
            if row is not None:
                self.rows.append(row)
            return

        if tag_l == "div":
            classes = attr_map.get("class", "").lower()
            permalink = attr_map.get("data-permalink") or attr_map.get("data-url") or ""
            if "thing" in classes and self._is_comment_url(permalink):
                self._active_row = {
                    "title": "",
                    "url": self._absolute_url(permalink),
                    "score": self._parse_score(attr_map.get("data-score")),
                    "created_utc": self._parse_timestamp(attr_map.get("data-timestamp")),
                }
            return

        if tag_l == "time" and self._active_row is not None:
            created = attr_map.get("datetime") or attr_map.get("title")
            parsed = self._parse_timestamp(created)
            if parsed > 0:
                self._active_row["created_utc"] = parsed
            return

        if tag_l != "a":
            return

        href = attr_map.get("href") or ""
        if not self._is_comment_url(href):
            return
        classes = attr_map.get("class", "").lower()
        data_testid = attr_map.get("data-testid", "").lower()
        slot = attr_map.get("slot", "").lower()
        should_capture = (
            "title" in classes
            or "post-title" in data_testid
            or slot == "title"
            or self._active_row is not None
        )
        if not should_capture:
            return
        self._capture_title = self._active_row or {
            "title": "",
            "url": self._absolute_url(href),
            "score": 0,
            "created_utc": 0.0,
        }
        self._capture_title["url"] = self._absolute_url(href)
        self._capture_parts = []

    def handle_data(self, data: str) -> None:
        if self._capture_title is not None:
            self._capture_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l == "a" and self._capture_title is not None:
            title = " ".join("".join(self._capture_parts).split()).strip()
            if title:
                row = dict(self._capture_title)
                row["title"] = title
                if row not in self.rows:
                    self.rows.append(row)
            self._capture_title = None
            self._capture_parts = []
            return
        if tag_l == "div" and self._active_row is not None:
            if str(self._active_row.get("title") or "").strip():
                self.rows.append(dict(self._active_row))
            self._active_row = None

    def _row_from_shreddit_attrs(self, attrs: dict[str, str]) -> dict[str, Any] | None:
        title = html.unescape(attrs.get("post-title") or attrs.get("title") or "").strip()
        url = attrs.get("permalink") or attrs.get("content-href") or attrs.get("url") or ""
        if not title or not self._is_comment_url(url):
            return None
        return {
            "title": title,
            "url": self._absolute_url(url),
            "score": self._parse_score(attrs.get("score")),
            "created_utc": self._parse_timestamp(
                attrs.get("created-timestamp")
                or attrs.get("created_timestamp")
                or attrs.get("data-created")
            ),
        }

    def _absolute_url(self, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return urljoin(self.base_url, html.unescape(text))

    def _is_comment_url(self, value: object) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        return self._COMMENT_RE.search(text) is not None

    def _parse_score(self, value: object) -> int:
        text = str(value or "").strip().lower().replace(",", "")
        if not text:
            return 0
        multiplier = 1
        if text.endswith("k"):
            multiplier = 1000
            text = text[:-1]
        try:
            return int(float(text) * multiplier)
        except Exception:
            return 0

    def _parse_timestamp(self, value: object) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            numeric = float(text)
            if numeric > 10_000_000_000:
                numeric = numeric / 1000.0
            return numeric
        except Exception:
            return _parse_reddit_timestamp(text)


class RedditHtmlProvider:
    """Subreddit listing provider using Reddit's ordinary HTML pages."""

    provider_id = REDDIT_PROVIDER_HTML

    def __init__(self, *, record_blocked: bool = True) -> None:
        self._record_blocked = bool(record_blocked)

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        slot_state = _acquire_widget_reddit_request_slot(request)
        if slot_state == "shutdown":
            return RedditProviderResult.skipped("shutdown")
        if slot_state == "blocked":
            logger.warning("[RATE_LIMIT] Reddit HTML widget skipping fetch after blocked cooldown re-check")
            return RedditProviderResult.skipped("blocked_cooldown")

        errors: list[Exception] = []
        for base_url, label in (
            (f"https://www.reddit.com/r/{request.subreddit}/", "www"),
            (f"https://old.reddit.com/r/{request.subreddit}/", "old"),
        ):
            url = base_url
            headers = _build_reddit_request_headers(
                f"{request.cache_key}:{request.subreddit}:html:{label}",
                accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            )
            try:
                logger.debug("[REDDIT] Fetching HTML feed: subreddit=%s source=%s", request.subreddit, label)
                resp = requests.get(url, headers=headers, timeout=10)
                _raise_for_reddit_http_status(
                    resp,
                    provider_id=f"{self.provider_id}:{label}",
                    subreddit=request.subreddit,
                    url=url,
                    record_blocked=self._record_blocked,
                )
                resp.raise_for_status()
                posts = self._parse_html(resp.content, request.subreddit, base_url=url)
                if posts:
                    logger.warning(
                        "[CACHE][REDDIT] Designed HTML provider succeeded cache_key=%s source=%s posts=%d",
                        request.cache_key,
                        label,
                        len(posts),
                    )
                    return RedditProviderResult.with_posts(posts[: max(1, clamp_list_capacity(request.limit))])
                errors.append(RuntimeError(f"html:{label}: empty listing"))
            except Exception as exc:
                errors.append(exc)
                logger.warning(
                    "[CACHE][REDDIT] HTML provider source failed cache_key=%s source=%s error=%s",
                    request.cache_key,
                    label,
                    exc,
                )
        if errors:
            raise RuntimeError("; ".join(str(error) for error in errors))
        return RedditProviderResult.with_posts([])

    def _parse_html(self, payload: bytes | str, subreddit: str, *, base_url: str) -> list[dict[str, Any]]:
        text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload or "")
        parser = _RedditHtmlPostParser(subreddit, base_url=base_url)
        parser.feed(text)
        parser.close()
        return _normalize_posts_from_rows(parser.rows)


class FallbackRedditPostProvider:
    """Selected Reddit provider with a designed HTML fallback source."""

    def __init__(self, primary: RedditPostProvider, html_provider: RedditHtmlProvider | None = None) -> None:
        self.primary = primary
        self.html_provider = html_provider or RedditHtmlProvider(record_blocked=False)
        self.provider_id = getattr(primary, "provider_id", REDDIT_PROVIDER_RSS)

    def fetch_posts(self, request: RedditFetchRequest) -> RedditProviderResult:
        primary_error: Exception | None = None
        try:
            result = self.primary.fetch_posts(request)
            if result.skip_reason:
                return result
            if result.posts:
                return result
            primary_error = RuntimeError("primary provider returned no posts")
            logger.warning(
                "[CACHE][REDDIT] Primary provider returned no posts; trying designed HTML fallback "
                "cache_key=%s provider=%s",
                request.cache_key,
                getattr(self.primary, "provider_id", "<unknown>"),
            )
        except Exception as exc:
            primary_error = exc
            logger.warning(
                "[CACHE][REDDIT] Primary provider failed; trying designed HTML fallback "
                "cache_key=%s provider=%s error=%s",
                request.cache_key,
                getattr(self.primary, "provider_id", "<unknown>"),
                exc,
            )

        try:
            html_result = self.html_provider.fetch_posts(request)
            if html_result.skip_reason:
                return html_result
            if html_result.posts:
                return html_result
            raise RuntimeError("html fallback returned no posts")
        except Exception as html_error:
            status_error = primary_error if isinstance(primary_error, RedditProviderHttpError) else html_error
            if isinstance(status_error, RedditProviderHttpError) and status_error.status_code in {403, 429}:
                _record_reddit_blocked_response(
                    f"composite:{status_error.provider_id}:{request.subreddit}:{status_error.status_code}"
                )
            if primary_error is not None:
                raise RuntimeError(f"{primary_error}; html fallback failed: {html_error}") from html_error
            raise


def build_reddit_post_provider(provider: object | None = None) -> RedditPostProvider:
    """Build the configured provider for the branded Reddit widget."""

    provider_id = normalize_reddit_provider_id(provider)
    if provider_id == REDDIT_PROVIDER_HTML:
        return RedditHtmlProvider()
    if provider_id == REDDIT_PROVIDER_RSS:
        return FallbackRedditPostProvider(RedditRssProvider(record_blocked=False))
    if provider_id == REDDIT_PROVIDER_PUBLIC_JSON:
        return FallbackRedditPostProvider(RedditPublicJsonProvider(record_blocked=False))
    return FallbackRedditPostProvider(PullPushProvider())


def build_default_reddit_post_provider(provider: object | None = None) -> RedditPostProvider:
    """Return the configured default provider for the branded Reddit widget."""

    return build_reddit_post_provider(provider)
