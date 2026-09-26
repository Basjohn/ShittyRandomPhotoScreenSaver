"""Built-in NEWS categories: vetted no-signup publisher feeds, merged newest first.

Each NEWS widget is one category card over the catalog's official publisher
RSS endpoints for that category, of which the user selects any subset. Every provider is an ordinary FEEDS source (shared
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
    NewsCategory("feeds_news_anime", "anime", "Anime News"),
)

NEWS_WIDGET_IDS: tuple[str, ...] = tuple(category.widget_id for category in NEWS_CATEGORIES)


@dataclass(frozen=True)
class NewsPublisher:
    name: str
    home_url: str
    # The publisher's own feed directory, when it has one: the endpoints'
    # provenance and the reference for their terms of use.
    directory_url: str = ""


# ---------------------------------------------------------------------------
# Catalog. Plain data: nothing else in the product names a publisher.
#
# Add a publisher: one _PUBLISHERS entry, then one row per category it covers.
# Withdraw an endpoint: delete its row. A stored selection of a withdrawn ID
# is ignored, so no migration is needed; remove it from the category's
# canonical ``providers`` default if it was one (a test enforces that).
# Never rename or reuse a provider ID: it is persistence and cache identity.
# An endpoint that moves keeps its ID and just gets the new URL.
#
# Every endpoint passed the production probe (tools/feed_probe.py --catalog)
# with fresh stories on 2026-09-26. Left out: dead (Washington Post, USA
# Today, PlayStation Blog), long stale (CNN, VG247, Otaku USA) or misdated
# feeds. Publishers without usable item images (CBS, Al Jazeera, DW,
# Euronews, Anime News Network...) show text-only stories by design.
# ---------------------------------------------------------------------------

_PUBLISHERS: dict[str, NewsPublisher] = {
    "abc": NewsPublisher("ABC News", "https://abcnews.go.com/", "https://abcnews.go.com/Site/page/rss-feeds-3520115"),
    "aljazeera": NewsPublisher("Al Jazeera", "https://www.aljazeera.com/"),
    "animecorner": NewsPublisher("Anime Corner", "https://animecorner.me/"),
    "animefeminist": NewsPublisher("Anime Feminist", "https://www.animefeminist.com/"),
    "animeherald": NewsPublisher("Anime Herald", "https://www.animeherald.com/"),
    "animehunch": NewsPublisher("Animehunch", "https://animehunch.com/"),
    "ann": NewsPublisher("Anime News Network", "https://www.animenewsnetwork.com/"),
    "animeuk": NewsPublisher("Anime UK News", "https://animeuknews.net/"),
    "anitrendz": NewsPublisher("Anime Trending", "https://anitrendz.net/"),
    "ars": NewsPublisher("Ars Technica", "https://arstechnica.com/", "https://arstechnica.com/rss-feeds/"),
    "axios": NewsPublisher("Axios", "https://www.axios.com/"),
    "bbc": NewsPublisher("BBC News", "https://www.bbc.com/news", "https://www.bbc.co.uk/news/10628494"),
    "bleepingcomputer": NewsPublisher("BleepingComputer", "https://www.bleepingcomputer.com/"),
    "cartoonbrew": NewsPublisher("Cartoon Brew", "https://www.cartoonbrew.com/"),
    "cbc": NewsPublisher("CBC News", "https://www.cbc.ca/news", "https://www.cbc.ca/rss/"),
    "cbr": NewsPublisher("CBR", "https://www.cbr.com/"),
    "cbs": NewsPublisher("CBS News", "https://www.cbsnews.com/", "https://www.cbsnews.com/rss/"),
    "cnet": NewsPublisher("CNET", "https://www.cnet.com/", "https://www.cnet.com/rss/"),
    "crunchyroll": NewsPublisher("Crunchyroll News", "https://www.crunchyroll.com/news"),
    "csm": NewsPublisher("Christian Science Monitor", "https://www.csmonitor.com/"),
    "destructoid": NewsPublisher("Destructoid", "https://www.destructoid.com/"),
    "dw": NewsPublisher("DW", "https://www.dw.com/en/"),
    "engadget": NewsPublisher("Engadget", "https://www.engadget.com/"),
    "euronews": NewsPublisher("Euronews", "https://www.euronews.com/"),
    "eurogamer": NewsPublisher("Eurogamer", "https://www.eurogamer.net/"),
    "fox": NewsPublisher("Fox News", "https://www.foxnews.com/"),
    "france24": NewsPublisher("France 24", "https://www.france24.com/en/"),
    "gameinformer": NewsPublisher("Game Informer", "https://www.gameinformer.com/"),
    "gamerant": NewsPublisher("Game Rant", "https://gamerant.com/"),
    "gamesindustry": NewsPublisher("GamesIndustry.biz", "https://www.gamesindustry.biz/"),
    "gamespot": NewsPublisher("GameSpot", "https://www.gamespot.com/"),
    "gamesradar": NewsPublisher("GamesRadar+", "https://www.gamesradar.com/"),
    "gematsu": NewsPublisher("Gematsu", "https://www.gematsu.com/"),
    "gizmodo": NewsPublisher("Gizmodo", "https://gizmodo.com/"),
    "guardian": NewsPublisher("The Guardian", "https://www.theguardian.com/", "https://www.theguardian.com/help/feeds"),
    "hill": NewsPublisher("The Hill", "https://thehill.com/"),
    "ign": NewsPublisher("IGN", "https://www.ign.com/"),
    "independent": NewsPublisher("The Independent", "https://www.independent.co.uk/"),
    "kotaku": NewsPublisher("Kotaku", "https://kotaku.com/"),
    "mal": NewsPublisher("MyAnimeList", "https://myanimelist.net/news"),
    "mittr": NewsPublisher("MIT Technology Review", "https://www.technologyreview.com/"),
    "nationalreview": NewsPublisher("National Review", "https://www.nationalreview.com/"),
    "nbc": NewsPublisher("NBC News", "https://www.nbcnews.com/"),
    "neowin": NewsPublisher("Neowin", "https://www.neowin.net/"),
    "newsweek": NewsPublisher("Newsweek", "https://www.newsweek.com/"),
    "nintendolife": NewsPublisher("Nintendo Life", "https://www.nintendolife.com/"),
    "npr": NewsPublisher("NPR", "https://www.npr.org/", "https://www.npr.org/rss/"),
    "nyt": NewsPublisher("The New York Times", "https://www.nytimes.com/", "https://www.nytimes.com/rss"),
    "otakunews": NewsPublisher("Otaku News", "https://www.otakunews.com/"),
    "pbs": NewsPublisher("PBS News", "https://www.pbs.org/newshour/"),
    "pcgamer": NewsPublisher("PC Gamer", "https://www.pcgamer.com/"),
    "pcgamesn": NewsPublisher("PCGamesN", "https://www.pcgamesn.com/"),
    "politico": NewsPublisher("Politico", "https://www.politico.com/"),
    "polygon": NewsPublisher("Polygon", "https://www.polygon.com/"),
    "propublica": NewsPublisher("ProPublica", "https://www.propublica.org/"),
    "purexbox": NewsPublisher("Pure Xbox", "https://www.purexbox.com/"),
    "pushsquare": NewsPublisher("Push Square", "https://www.pushsquare.com/"),
    "realclear": NewsPublisher("RealClearPolitics", "https://www.realclearpolitics.com/"),
    "reason": NewsPublisher("Reason", "https://reason.com/"),
    "register": NewsPublisher("The Register", "https://www.theregister.com/"),
    "rollcall": NewsPublisher("Roll Call", "https://rollcall.com/"),
    "rps": NewsPublisher("Rock Paper Shotgun", "https://www.rockpapershotgun.com/"),
    "sakugablog": NewsPublisher("Sakuga Blog", "https://blog.sakugabooru.com/"),
    "scmp": NewsPublisher("South China Morning Post", "https://www.scmp.com/"),
    "screenrant": NewsPublisher("Screen Rant", "https://screenrant.com/"),
    "semafor": NewsPublisher("Semafor", "https://www.semafor.com/"),
    "siliconera": NewsPublisher("Siliconera", "https://www.siliconera.com/"),
    "sky": NewsPublisher("Sky News", "https://news.sky.com/"),
    "slashdot": NewsPublisher("Slashdot", "https://slashdot.org/"),
    "techcrunch": NewsPublisher("TechCrunch", "https://techcrunch.com/"),
    "techradar": NewsPublisher("TechRadar", "https://www.techradar.com/"),
    "techspot": NewsPublisher("TechSpot", "https://www.techspot.com/"),
    "time": NewsPublisher("TIME", "https://time.com/"),
    "tomshardware": NewsPublisher("Tom's Hardware", "https://www.tomshardware.com/"),
    "un": NewsPublisher("UN News", "https://news.un.org/en/"),
    "upi": NewsPublisher("UPI", "https://www.upi.com/"),
    "verge": NewsPublisher("The Verge", "https://www.theverge.com/"),
    "vgc": NewsPublisher("Video Games Chronicle", "https://www.videogameschronicle.com/"),
    "wired": NewsPublisher("WIRED", "https://www.wired.com/"),
    "wsj": NewsPublisher("The Wall Street Journal", "https://www.wsj.com/"),
    "zdnet": NewsPublisher("ZDNET", "https://www.zdnet.com/"),
}

# category -> (provider ID, publisher key, feed URL), in Settings order.
_CATALOG: dict[str, tuple[tuple[str, str, str], ...]] = {
    "world": (
        ("cbs_world", "cbs", "https://www.cbsnews.com/latest/rss/world"),
        ("bbc_world", "bbc", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("npr_world", "npr", "https://feeds.npr.org/1004/rss.xml"),
        ("abc_world", "abc", "https://abcnews.go.com/abcnews/internationalheadlines"),
        ("guardian_world", "guardian", "https://www.theguardian.com/world/rss"),
        ("nyt_world", "nyt", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("aljazeera_world", "aljazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
        ("nbc_world", "nbc", "https://feeds.nbcnews.com/nbcnews/public/world"),
        ("wsj_world", "wsj", "https://feeds.content.dowjones.io/public/rss/RSSWorldNews"),
        ("dw_world", "dw", "https://rss.dw.com/rdf/rss-en-world"),
        ("france24_world", "france24", "https://www.france24.com/en/rss"),
        ("sky_world", "sky", "https://feeds.skynews.com/feeds/rss/world.xml"),
        ("cbc_world", "cbc", "https://www.cbc.ca/webfeed/rss/rss-world"),
        ("independent_world", "independent", "https://www.independent.co.uk/news/world/rss"),
        ("euronews_world", "euronews", "https://www.euronews.com/rss?level=theme&name=news"),
        ("scmp_world", "scmp", "https://www.scmp.com/rss/91/feed"),
        ("pbs_world", "pbs", "https://www.pbs.org/newshour/feeds/rss/world"),
        ("un_world", "un", "https://news.un.org/feed/subscribe/en/news/all/rss.xml"),
    ),
    "us": (
        ("cbs_us", "cbs", "https://www.cbsnews.com/latest/rss/us"),
        ("abc_us", "abc", "https://abcnews.go.com/abcnews/usheadlines"),
        ("npr_us", "npr", "https://feeds.npr.org/1003/rss.xml"),
        ("nyt_us", "nyt", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"),
        ("nbc_us", "nbc", "https://feeds.nbcnews.com/nbcnews/public/news"),
        ("fox_us", "fox", "https://moxie.foxnews.com/google-publisher/us.xml"),
        ("guardian_us", "guardian", "https://www.theguardian.com/us-news/rss"),
        ("wsj_us", "wsj", "https://feeds.content.dowjones.io/public/rss/RSSUSnews"),
        ("bbc_us", "bbc", "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        ("pbs_us", "pbs", "https://www.pbs.org/newshour/feeds/rss/nation"),
        ("axios_us", "axios", "https://api.axios.com/feed/"),
        ("time_us", "time", "https://time.com/feed/"),
        ("newsweek_us", "newsweek", "https://www.newsweek.com/rss"),
        ("upi_us", "upi", "https://rss.upi.com/news/top_news.rss"),
        ("csm_us", "csm", "https://rss.csmonitor.com/feeds/usa"),
        ("sky_us", "sky", "https://feeds.skynews.com/feeds/rss/us.xml"),
    ),
    "politics": (
        ("cbs_politics", "cbs", "https://www.cbsnews.com/latest/rss/politics"),
        ("abc_politics", "abc", "https://abcnews.go.com/abcnews/politicsheadlines"),
        ("npr_politics", "npr", "https://feeds.npr.org/1014/rss.xml"),
        ("politico_politics", "politico", "https://rss.politico.com/politics-news.xml"),
        ("hill_politics", "hill", "https://thehill.com/homenews/feed/"),
        ("nyt_politics", "nyt", "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml"),
        ("fox_politics", "fox", "https://moxie.foxnews.com/google-publisher/politics.xml"),
        ("nbc_politics", "nbc", "https://feeds.nbcnews.com/nbcnews/public/politics"),
        ("guardian_politics", "guardian", "https://www.theguardian.com/us-news/us-politics/rss"),
        ("wsj_politics", "wsj", "https://feeds.content.dowjones.io/public/rss/socialpoliticsfeed"),
        ("pbs_politics", "pbs", "https://www.pbs.org/newshour/feeds/rss/politics"),
        ("semafor_politics", "semafor", "https://www.semafor.com/rss.xml"),
        ("rollcall_politics", "rollcall", "https://rollcall.com/feed/"),
        ("realclear_politics", "realclear", "https://www.realclearpolitics.com/index.xml"),
        ("nationalreview_politics", "nationalreview", "https://www.nationalreview.com/feed/"),
        ("reason_politics", "reason", "https://reason.com/feed/"),
        ("propublica_politics", "propublica", "https://www.propublica.org/feeds/propublica/main"),
        ("csm_politics", "csm", "https://rss.csmonitor.com/feeds/politics"),
    ),
    "gaming": (
        ("ars_gaming", "ars", "https://feeds.arstechnica.com/arstechnica/gaming"),
        ("pcgamer_all", "pcgamer", "https://www.pcgamer.com/rss/"),
        ("eurogamer_all", "eurogamer", "https://www.eurogamer.net/feed"),
        ("ign_gaming", "ign", "https://feeds.ign.com/ign/all"),
        ("polygon_gaming", "polygon", "https://www.polygon.com/rss/index.xml"),
        ("gamespot_gaming", "gamespot", "https://www.gamespot.com/feeds/news/"),
        ("kotaku_gaming", "kotaku", "https://kotaku.com/rss"),
        ("rps_gaming", "rps", "https://www.rockpapershotgun.com/feed"),
        ("gamesradar_gaming", "gamesradar", "https://www.gamesradar.com/rss/"),
        ("vgc_gaming", "vgc", "https://www.videogameschronicle.com/feed/"),
        ("verge_gaming", "verge", "https://www.theverge.com/rss/games/index.xml"),
        ("gameinformer_gaming", "gameinformer", "https://www.gameinformer.com/news.xml"),
        ("destructoid_gaming", "destructoid", "https://www.destructoid.com/feed/"),
        ("pcgamesn_gaming", "pcgamesn", "https://www.pcgamesn.com/mainrss.xml"),
        ("gematsu_gaming", "gematsu", "https://www.gematsu.com/feed"),
        ("siliconera_gaming", "siliconera", "https://www.siliconera.com/feed/"),
        ("nintendolife_gaming", "nintendolife", "https://www.nintendolife.com/feeds/latest"),
        ("pushsquare_gaming", "pushsquare", "https://www.pushsquare.com/feeds/latest"),
        ("purexbox_gaming", "purexbox", "https://www.purexbox.com/feeds/latest"),
        ("gamesindustry_gaming", "gamesindustry", "https://www.gamesindustry.biz/feed"),
    ),
    "tech": (
        ("cbs_technology", "cbs", "https://www.cbsnews.com/latest/rss/technology"),
        ("abc_technology", "abc", "https://abcnews.go.com/abcnews/technologyheadlines"),
        ("ars_all", "ars", "https://feeds.arstechnica.com/arstechnica/index"),
        ("verge_tech", "verge", "https://www.theverge.com/rss/index.xml"),
        ("engadget_tech", "engadget", "https://www.engadget.com/rss.xml"),
        ("wired_tech", "wired", "https://www.wired.com/feed/rss"),
        ("techcrunch_tech", "techcrunch", "https://techcrunch.com/feed/"),
        ("bbc_tech", "bbc", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
        ("nyt_tech", "nyt", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
        ("guardian_tech", "guardian", "https://www.theguardian.com/technology/rss"),
        ("npr_tech", "npr", "https://feeds.npr.org/1019/rss.xml"),
        ("register_tech", "register", "https://www.theregister.com/headlines.atom"),
        ("tomshardware_tech", "tomshardware", "https://www.tomshardware.com/feeds/all"),
        ("cnet_tech", "cnet", "https://www.cnet.com/rss/news/"),
        ("zdnet_tech", "zdnet", "https://www.zdnet.com/news/rss.xml"),
        ("techradar_tech", "techradar", "https://www.techradar.com/rss"),
        ("gizmodo_tech", "gizmodo", "https://gizmodo.com/rss"),
        ("mittr_tech", "mittr", "https://www.technologyreview.com/feed/"),
        ("bleepingcomputer_tech", "bleepingcomputer", "https://www.bleepingcomputer.com/feed/"),
        ("techspot_tech", "techspot", "https://www.techspot.com/backend.xml"),
        ("neowin_tech", "neowin", "https://www.neowin.net/news/rss/"),
        ("slashdot_tech", "slashdot", "https://rss.slashdot.org/Slashdot/slashdotMain"),
    ),
    "anime": (
        ("mal_anime", "mal", "https://myanimelist.net/rss/news.xml"),
        ("ann_anime", "ann", "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us"),
        ("crunchyroll_anime", "crunchyroll", "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss"),
        ("animecorner_anime", "animecorner", "https://animecorner.me/feed/"),
        ("animeuk_anime", "animeuk", "https://animeuknews.net/feed/"),
        ("otakunews_anime", "otakunews", "https://www.otakunews.com/rss/rss.xml"),
        ("anitrendz_anime", "anitrendz", "https://anitrendz.net/news/feed/"),
        ("cbr_anime", "cbr", "https://www.cbr.com/feed/category/anime/"),
        ("siliconera_anime", "siliconera", "https://www.siliconera.com/category/anime/feed/"),
        ("animehunch_anime", "animehunch", "https://animehunch.com/feed/"),
        ("animeherald_anime", "animeherald", "https://www.animeherald.com/feed/"),
        ("kotaku_anime", "kotaku", "https://kotaku.com/tag/anime/rss"),
        ("cartoonbrew_anime", "cartoonbrew", "https://www.cartoonbrew.com/category/anime/feed"),
        ("sakugablog_anime", "sakugablog", "https://blog.sakugabooru.com/feed/"),
        ("animefeminist_anime", "animefeminist", "https://www.animefeminist.com/feed/"),
        ("gamerant_anime", "gamerant", "https://gamerant.com/feed/anime/"),
        ("screenrant_anime", "screenrant", "https://screenrant.com/feed/anime/"),
    ),
}


def _catalog_providers() -> tuple[NewsProvider, ...]:
    providers = []
    for category, rows in _CATALOG.items():
        for provider_id, publisher_key, url in rows:
            publisher = _PUBLISHERS[publisher_key]
            providers.append(NewsProvider(
                provider_id, publisher.name, category, url, publisher.home_url,
                publisher.directory_url or publisher.home_url,
            ))
    return tuple(providers)


NEWS_PROVIDERS: tuple[NewsProvider, ...] = _catalog_providers()

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
