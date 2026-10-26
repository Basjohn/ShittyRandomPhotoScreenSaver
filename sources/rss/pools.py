"""Wallpaper discovery intents, projected into the existing RSS acquisition pass.

No network, Settings writes, queue, worker or clock lives here. Custom feed URLs
remain independent; a pool is a bounded opportunity to ask one upstream listing.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Mapping
from urllib.parse import urlencode

logger = logging.getLogger(__name__)
POOL_SETTINGS_KEY = "sources.wallpaper_pools"
DISCOVERY_ORDERS = (
    ("random", "Random"), ("latest", "Latest"), ("popular", "Popular"),
    ("today", "Top Today"), ("week", "Top This Week"),
    ("month", "Top This Month"), ("year", "Top This Year"),
)
_ORDER_IDS = frozenset(key for key, _ in DISCOVERY_ORDERS)
MAX_DOCUMENTS_PER_PASS = 2
MAX_STARTUP_DOCUMENTS = 6
STARTUP_ACQUISITION_SECONDS = 20.0
MAX_LISTING_PAGES = 3


@dataclass(frozen=True)
class WallpaperPool:
    pool_id: str
    label: str
    provider: str
    query: str = ""


# Queries are separate opportunities, never an AND of checked themes. Keep
# provider syntax here rather than adding site-specific branches to the parser.
WALLPAPER_POOLS = (
    WallpaperPool("wallhaven.nature", "Nature & Landscapes", "wallhaven", "landscape"),
    WallpaperPool("wallhaven.space", "Space", "wallhaven", "space"),
    WallpaperPool("wallhaven.cities", "Cities & Architecture", "wallhaven", "cityscape"),
    WallpaperPool("wallhaven.fantasy", "Fantasy", "wallhaven", "fantasy landscape"),
    WallpaperPool("wallhaven.scifi", "Science Fiction", "wallhaven", "science fiction"),
    WallpaperPool("wallhaven.cyberpunk", "Cyberpunk", "wallhaven", "cyberpunk"),
    WallpaperPool("wallhaven.abstract", "Abstract", "wallhaven", "abstract"),
    WallpaperPool("wallhaven.minimal", "Minimalism", "wallhaven", "minimalism"),
    WallpaperPool("wallhaven.anime", "Anime Scenery", "wallhaven", "anime scenery"),
    WallpaperPool("wallhaven.dark", "Dark Wallpapers", "wallhaven", "dark"),
    WallpaperPool("nasa.space", "Space — Sun, Mars, Solar System & Universe", "nasa"),
    WallpaperPool("bing.daily", "Image of the Day", "bing"),
    WallpaperPool("konachan.safe", "Anime Wallpapers — Safe-rated", "konachan"),
    WallpaperPool("safebooru.general", "Anime Illustrations — General-rated", "safebooru"),
    WallpaperPool("yandere.safe", "Anime Illustrations — Safe-rated", "yandere"),
)
_BY_ID = {pool.pool_id: pool for pool in WALLPAPER_POOLS}
_SOLAR_BODIES = ("Mercury", "Venus", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Asteroid")


def get_wallpaper_pool(pool_id: str) -> WallpaperPool:
    return _BY_ID[pool_id]


@dataclass(frozen=True)
class WallpaperPoolSelection:
    enabled: bool
    selected: tuple[str, ...]
    discovery_order: str

    @classmethod
    def from_mapping(cls, raw: object) -> "WallpaperPoolSelection":
        from core.settings.default_contract import require_canonical_default

        defaults = require_canonical_default(POOL_SETTINGS_KEY)
        source = raw if isinstance(raw, Mapping) else defaults
        enabled = source.get("enabled", defaults["enabled"])
        selected = source.get("selected", defaults["selected"])
        order = source.get("discovery_order", defaults["discovery_order"])
        if type(enabled) is not bool:
            logger.warning("[WALLPAPER_POOLS] Invalid enablement %r; using canonical default", enabled)
            enabled = defaults["enabled"]
        if not isinstance(selected, (list, tuple)) or any(not isinstance(key, str) or key not in _BY_ID for key in selected):
            logger.warning("[WALLPAPER_POOLS] Invalid pool selection %r; using canonical default", selected)
            selected = defaults["selected"]
        if not isinstance(order, str) or order not in _ORDER_IDS:
            logger.warning("[WALLPAPER_POOLS] Invalid discovery order %r; using canonical default", order)
            order = defaults["discovery_order"]
        return cls(enabled, tuple(dict.fromkeys(selected)), order)

    @property
    def active_ids(self) -> tuple[str, ...]:
        return self.selected if self.enabled else ()

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "selected": list(self.selected), "discovery_order": self.discovery_order}


def read_pool_selection(settings) -> WallpaperPoolSelection:
    from core.settings.default_contract import require_canonical_default
    defaults = require_canonical_default(POOL_SETTINGS_KEY)
    # Sources uses the existing flat persistence projection, unlike Widgets.
    return WallpaperPoolSelection.from_mapping({key: settings.get(f"{POOL_SETTINGS_KEY}.{key}", value) for key, value in defaults.items()})


def write_pool_selection(settings, selection: WallpaperPoolSelection) -> None:
    for key, value in selection.to_dict().items():
        settings.set(f"{POOL_SETTINGS_KEY}.{key}", value)
    settings.save()  # SettingsDraft deliberately defers this until Finish


def online_source_count(settings) -> int:
    """Cheap configuration count; no endpoint expansion or network admission."""
    return len(settings.get("sources.rss_feeds") or ()) + len(read_pool_selection(settings).active_ids)


@dataclass(frozen=True)
class PoolEndpoint:
    source_id: str
    url: str
    pool_id: str = ""
    item_index: int = 0


def pool_endpoint(pool_id: str, order: str, *, turn: int = 0, seed: str = "") -> PoolEndpoint:
    """One endpoint per intent/turn; unsupported ranking remains native order."""
    pool = _BY_ID[pool_id]
    if order not in _ORDER_IDS or turn < 0:
        raise ValueError("invalid wallpaper discovery order/turn")
    if pool.provider == "wallhaven":
        params = {"q": pool.query, "categories": "110", "purity": "100",
                  "page": str(1 + turn % MAX_LISTING_PAGES)}
        if order == "random":
            params.update(sorting="random", seed=seed)
        elif order == "latest":
            params["sorting"] = "date_added"
        elif order == "popular":
            params["sorting"] = "favorites"
        else:
            params.update(sorting="toplist", topRange={"today": "1d", "week": "1w", "month": "1M", "year": "1y"}[order])
        return PoolEndpoint(pool_id, "https://wallhaven.cc/api/v1/search?" + urlencode(params), pool_id)
    if pool.provider == "bing":
        return PoolEndpoint(pool_id, "https://www.bing.com/HPImageArchive.aspx?format=rss&idx=0&n=8&mkt=en-US", pool_id)
    if pool.provider in {"konachan", "yandere"}:
        host = "konachan.net" if pool.provider == "konachan" else "yande.re"
        tags = "rating:safe width:>=1920 height:>=1080"
        if pool.provider == "konachan":
            tags += " order:score" if order == "popular" else " order:id_desc"
        params = {"limit": "24", "page": str(1 + turn % MAX_LISTING_PAGES), "tags": tags}
        return PoolEndpoint(pool_id, f"https://{host}/post.json?" + urlencode(params), pool_id)
    if pool.provider == "safebooru":
        params = {"page": "dapi", "s": "post", "q": "index", "json": "1", "limit": "24",
                  "pid": str(turn % MAX_LISTING_PAGES), "tags": "rating:general width:>=1920 height:>=1080"}
        return PoolEndpoint(pool_id, "https://safebooru.org/index.php?" + urlencode(params), pool_id)
    if pool.provider != "nasa":
        raise ValueError(f"Unsupported wallpaper pool provider: {pool.provider}")
    # One Space choice gets equal opportunities for the four named subjects;
    # Solar System rotates a single body, without fetching all bodies in a pass.
    subject = ("Galaxy", "Mars", "Sun", _SOLAR_BODIES[(turn // 4) % len(_SOLAR_BODIES)])[turn % 4]
    params = {"title": subject, "center": "JPL", "media_type": "image", "year_start": "2018",
              "page_size": "24", "page": str(1 + (turn // 4 // 24) % MAX_LISTING_PAGES)}
    return PoolEndpoint(f"{pool_id}.{subject.casefold()}", "https://images-api.nasa.gov/search?" + urlencode(params), pool_id, turn // 4)


class WallpaperPoolRotation:
    """Finite cursor state inside one coordinator, advanced only by real passes."""

    def __init__(self, custom_urls: list[str], selection: WallpaperPoolSelection, *, seed: str):
        self._custom = tuple(dict.fromkeys(custom_urls))
        self._selection = selection
        self._ids = (*self._custom, *selection.active_ids)
        self._cursor = 0
        self._turns: dict[str, int] = {}
        self._seed = seed

    def next_endpoints(self, limit: int = MAX_DOCUMENTS_PER_PASS) -> tuple[PoolEndpoint, ...]:
        budget = max(0, int(limit))
        result = []
        seen_urls = set()
        for _ in range(len(self._ids)):
            key = self._ids[self._cursor % len(self._ids)]
            cost = 2 if key == "nasa.space" else 1
            if cost > budget:
                break
            budget -= cost
            self._cursor += 1
            if key in self._selection.active_ids:
                turn = self._turns.get(key, 0)
                endpoint = pool_endpoint(key, self._selection.discovery_order, turn=turn, seed=self._seed)
                self._turns[key] = turn + 1
            else:
                endpoint = PoolEndpoint(key, key)
            if endpoint.url not in seen_urls:
                result.append(endpoint)
                seen_urls.add(endpoint.url)
        return tuple(result)


def migrate_legacy_curated_sources(raw: object) -> dict | None:
    """Promote exact retired curated URLs, preserving every other custom URL.

    Called before defaults on the persisted Sources root. Presence of the new
    pool key proves this profile has already chosen/declined the new policy.
    """
    from sources.rss.constants import LEGACY_CURATED_RSS_FEEDS

    if not isinstance(raw, Mapping) or any(str(key) == "wallpaper_pools" or str(key).startswith("wallpaper_pools.") for key in raw):
        return None
    feeds = raw.get("rss_feeds")
    if not isinstance(feeds, list) or any(not isinstance(url, str) for url in feeds):
        return None
    legacy = LEGACY_CURATED_RSS_FEEDS
    nasa_urls = {legacy["NASA Image of the Day"], legacy["NASA JPL Photojournal"]}
    selections = []
    preserved = []
    for url in feeds:
        if url in nasa_urls:
            selections.append("nasa.space")
        elif url == legacy["Wallhaven SFW Wallpapers"]:
            selections.extend(pool.pool_id for pool in WALLPAPER_POOLS if pool.provider == "wallhaven")
        elif url == legacy["Bing Image of the Day"]:
            selections.append("bing.daily")
        else:
            preserved.append(url)
    if not selections:
        return None
    result = dict(raw)
    result["rss_feeds"] = preserved
    # Legacy URLs authored no ranking preference. A merge import must not
    # overwrite an existing discovery order; startup/replace use canonical fill.
    result["wallpaper_pools"] = {"enabled": True, "selected": list(dict.fromkeys(selections))}
    return result


def project_imported_pool_section(raw: Mapping) -> dict:
    """Accept nested canonical snapshots and the existing flat SST projection."""
    result = migrate_legacy_curated_sources(raw) or dict(raw)
    nested = result.pop("wallpaper_pools", None)
    if nested is not None:
        if not isinstance(nested, Mapping):
            raise ValueError("sources.wallpaper_pools must be a mapping")
        for key, value in nested.items():
            dotted = f"wallpaper_pools.{key}"
            if dotted in result and result[dotted] != value:
                raise ValueError(f"Conflicting Sources pool import values: {dotted}")
            result[dotted] = value
    return result


def examine_pool_response(response, request_url: str, max_items: int, *, provider: str):
    """Strict one-document provider admission; never discover a replacement feed.

    The configured pool owns its protocol/rating contract even if the remote
    endpoint redirects, emits a valid RSS document, or advertises another feed.
    Custom URL sources retain the ordinary generic discovery path.
    """
    from core.feeds.parser import FeedParseError, parse_feed_bytes
    from sources.rss.json_listing import safe_pool_image_listing
    from sources.rss.nasa_listing import nasa_image_listing

    url = response.final_url or request_url
    if provider == "bing":
        document = parse_feed_bytes(response.payload, source_url=url, max_items=max_items)
        if document.format != "rss20":
            raise FeedParseError("Bing wallpaper pool did not return its RSS image archive")
    elif provider == "nasa":
        document = nasa_image_listing(response.payload, url, max_items)
    else:
        document = safe_pool_image_listing(response.payload, url, max_items, provider=provider)
    if document is None:
        raise FeedParseError(f"Wallpaper pool returned no admissible {provider} document")
    return document, ()
