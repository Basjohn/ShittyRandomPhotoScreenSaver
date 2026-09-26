"""Built-in NEWS categories: vetted no-signup publisher feeds, merged newest first.

Each NEWS widget is one category card over a small fixed set of official
publisher RSS endpoints. Every provider is an ordinary FEEDS source (shared
transport, parser, cache and runtime owner); this module only names them and
merges their accepted snapshots. SRPSS does not rank, score or suppress
stories: order is publication time and deduplication is exact identity only.

Provider IDs are persistence and cache identity. An official endpoint may move
under the same ID (``allow_endpoint_migration``): the last-good snapshot stays
visible while the new address validates, and its validators are never sent to
the new address.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from urllib.parse import urlsplit, urlunsplit

from core.settings.default_contract import require_canonical_default

from .models import (
    FeedDocument,
    FeedHealth,
    FeedRefreshResult,
    FeedSnapshot,
    FeedSourceSpec,
    FeedViewMode,
)


@dataclass(frozen=True)
class NewsProvider:
    provider_id: str
    display_name: str
    category: str
    url: str
    home_url: str
    # The publisher's own feed directory: the endpoint's provenance and the
    # reference for its terms of use.
    directory_url: str

    def source_spec(self) -> FeedSourceSpec:
        return FeedSourceSpec(
            source_id=f"news:{self.provider_id}",
            url=self.url,
            cache_key=f"news_{self.provider_id}",
            display_name=self.display_name,
            max_items=40,
            allow_endpoint_migration=True,
        )


@dataclass(frozen=True)
class NewsCategory:
    widget_id: str
    category: str
    label: str


NEWS_CATEGORIES: tuple[NewsCategory, ...] = (
    NewsCategory("feeds_news_world", "world", "World News"),
    NewsCategory("feeds_news_us", "us", "US News"),
    NewsCategory("feeds_news_politics", "politics", "Politics"),
    NewsCategory("feeds_news_gaming", "gaming", "Gaming News"),
    NewsCategory("feeds_news_tech", "tech", "Tech News"),
)

NEWS_WIDGET_IDS: tuple[str, ...] = tuple(category.widget_id for category in NEWS_CATEGORIES)

_CBS = ("CBS News", "https://www.cbsnews.com/", "https://www.cbsnews.com/rss/")
_ABC = ("ABC News", "https://abcnews.go.com/", "https://abcnews.go.com/Site/page/rss-feeds-3520115")
_BBC = ("BBC News", "https://www.bbc.com/news", "https://www.bbc.co.uk/news/10628494")
_NPR = ("NPR", "https://www.npr.org/", "https://www.npr.org/rss/")
_ARS = ("Ars Technica", "https://arstechnica.com/", "https://arstechnica.com/rss-feeds/")
_PCGAMER = ("PC Gamer", "https://www.pcgamer.com/", "https://www.pcgamer.com/")
_EUROGAMER = ("Eurogamer", "https://www.eurogamer.net/", "https://www.eurogamer.net/")


def _provider(provider_id: str, publisher: tuple[str, str, str], category: str, url: str) -> NewsProvider:
    name, home, directory = publisher
    return NewsProvider(provider_id, name, category, url, home, directory)


# Native probe evidence (tools/feed_probe.py --catalog), 2026-09-24 and
# 2026-09-26: every endpoint below passed direct. ABC's world feed was empty on
# both days and is not listed. CBS publishes only 60x60 item thumbnails, so its
# stories are text-only by design.
NEWS_PROVIDERS: tuple[NewsProvider, ...] = (
    _provider("cbs_world", _CBS, "world", "https://www.cbsnews.com/latest/rss/world"),
    _provider("bbc_world", _BBC, "world", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    _provider("npr_world", _NPR, "world", "https://feeds.npr.org/1004/rss.xml"),
    _provider("cbs_us", _CBS, "us", "https://www.cbsnews.com/latest/rss/us"),
    _provider("abc_us", _ABC, "us", "https://abcnews.go.com/abcnews/usheadlines"),
    _provider("npr_us", _NPR, "us", "https://feeds.npr.org/1003/rss.xml"),
    _provider("cbs_politics", _CBS, "politics", "https://www.cbsnews.com/latest/rss/politics"),
    _provider("abc_politics", _ABC, "politics", "https://abcnews.go.com/abcnews/politicsheadlines"),
    _provider("npr_politics", _NPR, "politics", "https://feeds.npr.org/1014/rss.xml"),
    _provider("ars_gaming", _ARS, "gaming", "https://feeds.arstechnica.com/arstechnica/gaming"),
    _provider("pcgamer_all", _PCGAMER, "gaming", "https://www.pcgamer.com/rss/"),
    _provider("eurogamer_all", _EUROGAMER, "gaming", "https://www.eurogamer.net/feed"),
    _provider("cbs_technology", _CBS, "tech", "https://www.cbsnews.com/latest/rss/technology"),
    _provider("abc_technology", _ABC, "tech", "https://abcnews.go.com/abcnews/technologyheadlines"),
    _provider("ars_all", _ARS, "tech", "https://feeds.arstechnica.com/arstechnica/index"),
)

_CATEGORY_BY_WIDGET = {category.widget_id: category for category in NEWS_CATEGORIES}
_VALID_VIEW_MODES = frozenset({"list", "grid", "compact"})

# Merged stories kept per card; the card's own item limit (at most 40) then
# projects the visible rows.
NEWS_MERGED_ITEM_CAP = 40


def news_category(widget_id: str) -> NewsCategory:
    try:
        return _CATEGORY_BY_WIDGET[widget_id]
    except KeyError:
        raise ValueError(f"unknown NEWS widget: {widget_id!r}") from None


def news_providers_for(widget_id: str) -> tuple[NewsProvider, ...]:
    category = news_category(widget_id).category
    return tuple(provider for provider in NEWS_PROVIDERS if provider.category == category)


def _coerce_bool(raw: object, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().casefold()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        return bool(default)
    if raw is None:
        return bool(default)
    return bool(raw)


def _bounded_int(raw: object, default: object, low: int, high: int) -> int:
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        value = int(default)  # type: ignore[arg-type]
    return max(low, min(high, value))


@dataclass(frozen=True)
class NewsFeedConfig:
    """Headless settings of one NEWS card; field-compatible with CUSTOM where shared."""

    widget_id: str
    category: str
    enabled: bool
    name: str
    providers: tuple[NewsProvider, ...]
    view_mode: FeedViewMode
    item_limit: int
    refresh_minutes: int
    show_images: bool
    show_subtitle: bool

    @classmethod
    def from_mapping(cls, widget_id: str, value: Mapping[str, object] | None) -> "NewsFeedConfig":
        category = news_category(widget_id)
        defaults = require_canonical_default(f"widgets.{widget_id}")
        if not isinstance(defaults, Mapping):
            raise TypeError(f"canonical widgets.{widget_id} default must be a mapping")
        raw = value if isinstance(value, Mapping) else {}
        available = news_providers_for(widget_id)
        selected_raw = raw.get("providers", defaults["providers"])
        if not isinstance(selected_raw, (list, tuple)):
            selected_raw = defaults["providers"]
        selected = {str(entry).strip() for entry in selected_raw}
        view = str(raw.get("view_mode", defaults["view_mode"]) or defaults["view_mode"]).strip().casefold()
        if view not in _VALID_VIEW_MODES:
            view = str(defaults["view_mode"]).casefold()
        return cls(
            widget_id=widget_id,
            category=category.category,
            enabled=_coerce_bool(raw.get("enabled", defaults["enabled"]), bool(defaults["enabled"])),
            name=category.label,
            # Catalog order, not stored order; a withdrawn provider ID is ignored.
            providers=tuple(provider for provider in available if provider.provider_id in selected),
            view_mode=view,  # type: ignore[arg-type]
            item_limit=_bounded_int(raw.get("item_limit"), defaults["item_limit"], 3, 40),
            refresh_minutes=_bounded_int(raw.get("refresh_minutes"), defaults["refresh_minutes"], 5, 24 * 60),
            show_images=_coerce_bool(raw.get("show_images", defaults["show_images"]), bool(defaults["show_images"])),
            show_subtitle=_coerce_bool(
                raw.get("show_subtitle", defaults["show_subtitle"]), bool(defaults["show_subtitle"])),
        )

    @property
    def configured(self) -> bool:
        return bool(self.providers)


def _canonical_story_url(url: str) -> str:
    """Exact story identity: scheme/host case, default port and fragment only."""

    text = str(url or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return ""
    scheme = parts.scheme.casefold()
    host = (parts.hostname or "").casefold()
    if not scheme or not host:
        return ""
    port = parts.port if parts.port not in {None, 80, 443} else None
    netloc = f"{host}:{port}" if port else host
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def merge_news_results(
    providers: Sequence[NewsProvider],
    results: Mapping[str, FeedRefreshResult],
    *,
    max_items: int = NEWS_MERGED_ITEM_CAP,
) -> FeedRefreshResult:
    """Merge each provider's accepted snapshot into one card snapshot.

    Newest first by publication time (undated stories after dated ones, in
    provider then feed order). A story whose exact URL already appeared from a
    newer or earlier-listed provider is dropped; nothing fuzzier is inferred.
    Each row's author is its publisher, and item IDs are namespaced by provider
    so local artwork stays attached to the right story. A provider without a
    snapshot simply contributes nothing; it cannot blank the others.
    """

    contributing = [
        (provider, results[provider.provider_id])
        for provider in providers
        if provider.provider_id in results and results[provider.provider_id].snapshot is not None
    ]
    if not contributing:
        failure = next(
            (results[provider.provider_id].failure for provider in providers
             if provider.provider_id in results and results[provider.provider_id].failure),
            "no_provider_snapshot",
        )
        return FeedRefreshResult("unavailable", None, FeedHealth(), failure=failure)

    entries = []
    for provider_index, (provider, result) in enumerate(contributing):
        artwork = dict(result.local_artwork_by_item)
        for item_index, item in enumerate(result.snapshot.document.items):
            entries.append((provider_index, item_index, provider, item, artwork.get(item.item_id, "")))
    entries.sort(key=lambda entry: (
        entry[3].published_at is None, -(entry[3].published_at or 0), entry[0], entry[1]))

    items = []
    local_artwork = []
    seen_urls: set[str] = set()
    seen_ids: set[str] = set()
    for _provider_index, _item_index, provider, item, artwork in entries:
        story_url = _canonical_story_url(item.action_url)
        merged_id = f"{provider.provider_id}:{item.item_id}"
        if (story_url and story_url in seen_urls) or merged_id in seen_ids:
            continue
        if story_url:
            seen_urls.add(story_url)
        seen_ids.add(merged_id)
        items.append(replace(item, item_id=merged_id, author=provider.display_name))
        if artwork:
            local_artwork.append((merged_id, artwork))
        if len(items) >= max(1, int(max_items)):
            break

    snapshots = [result.snapshot for _provider, result in contributing]
    healths = [result.health for _provider, result in contributing]
    checked = [health.last_checked_at for health in healths if health.last_checked_at is not None]
    succeeded = [health.last_success_at for health in healths if health.last_success_at is not None]
    fresh = any(result.status in {"available", "not_modified"} for _provider, result in contributing)
    document = FeedDocument(
        title=" · ".join(provider.display_name for provider, _result in contributing),
        home_url="",
        format="news",
        items=tuple(items),
    )
    return FeedRefreshResult(
        "available" if fresh else "stale_cache",
        FeedSnapshot(document=document, fetched_at=max(snapshot.fetched_at for snapshot in snapshots)),
        FeedHealth(
            last_checked_at=max(checked) if checked else None,
            last_success_at=max(succeeded) if succeeded else None,
        ),
        changed=any(result.changed for _provider, result in contributing),
        local_artwork_by_item=tuple(local_artwork),
    )


__all__ = [
    "NEWS_CATEGORIES",
    "NEWS_MERGED_ITEM_CAP",
    "NEWS_PROVIDERS",
    "NEWS_WIDGET_IDS",
    "NewsCategory",
    "NewsFeedConfig",
    "NewsProvider",
    "merge_news_results",
    "news_category",
    "news_providers_for",
]
