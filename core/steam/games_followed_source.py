"""Bounded, opt-in source/cache foundation for Games You Follow.

No Qt, worker, timer, widget or Settings access. One existing Steam worker/owner
may call refresh() on demand after an explicit linked-identity admission. Only
accepted, validated private records reach the existing profile-scoped cache;
failed/partial fetches never overwrite its last-good snapshot.
"""
from __future__ import annotations

import time
import threading
import html
import re
from html.parser import HTMLParser
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from core.logging.logger import get_logger
from core.steam.followed_app_metadata import FollowedAppMetadata, fetch_store_metadata, valid_game_name, FAILED_LOOKUP_RETRY_SECONDS
from core.steam.followed_news_inline_artwork import (
    news_inline_refs, validated_inline_ref, inline_image_url, prune_inline_image_cache,
    MAX_INLINE_IMAGE_FETCHES_PER_REFRESH, MAX_INLINE_IMAGES_PER_STORY,
)

from core.steam.backend import build_endpoint, fetch_json
from core.steam.cache import (
    SteamCacheRecord, cache_path_for_profile_key, get_steam_source_refresh_lock,
    read_cache_record, write_cache_record,
)
from core.steam.games_followed_probe import (
    fetch_followed_appids_for_news_probe, normalize_followed_appids,
)
from core.steam.credentials import derive_profile_cache_key
from core.steam.links import news_article_target
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import SteamBackoffPolicy, SteamRequestCoordinator, SteamRequestKey

logger = get_logger(__name__)

CACHE_KEY = "games_you_follow_news"
CACHE_PAYLOAD_VERSION = 1
MAX_NEWS_APPS_PER_REFRESH = 4
MAX_NEWS_ITEMS_PER_APP = 8
MAX_SELECTED_STORIES = 8
# A normally sized followed set retains all eight normalized public-news rows
# per app. Bound the private JSON record so a pathological 4,096-app profile
# cannot force tens of megabytes of rewriting on every four-app batch.
MAX_PERSISTED_FOLLOWED_APPS = 512
# Membership is a different, much slower-changing source than per-app news.
# Revalidate it once per day, not for every bounded maintenance session.
FOLLOWED_MEMBERSHIP_TTL_SECONDS = 24 * 60 * 60
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
    preview: str = ""
    game_name: str = ""
    inline_image_refs: tuple[str, ...] = ()
    article_url: str = ""  # Validated private source URL; never projected to QML.


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
    artwork_paths: tuple[str, ...] = ()  # Transient, validated local cache hits only.
    inline_image_paths: tuple[tuple[str, ...], ...] = ()  # Local files, aligned to story identity.
    covered_count: int = 0  # Best-effort rolling coverage, never a claim of Steam personalized-feed parity.
    maintenance_pending: bool = False  # Second four-app slice of one post-coverage refresh session.


class _NewsText(HTMLParser):
    """Bounded plain-text extraction; discard script/style and provider markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0
        self.length = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "iframe", "svg"}:
            self.hidden += 1
        elif tag in {"p", "br", "li", "div"} and not self.hidden:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "iframe", "svg"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "br", "li", "div"} and not self.hidden:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.hidden and self.length < 1800:
            fragment = data[:1800 - self.length]
            self.parts.append(fragment)
            self.length += len(fragment)


def _plain_preview(contents: object) -> str:
    if type(contents) is not str or not contents:
        return ""
    parser = _NewsText()
    try:
        # Remove the *whole* Steam image macro including its path. Removing
        # just {STEAM_CLAN_IMAGE} leaked /group/hash.png as visible preview.
        from core.steam.followed_news_inline_artwork import _ABSOLUTE_CLAN_IMAGE, _CLAN_IMAGE, _STANDALONE_IMAGE
        clean_contents = _ABSOLUTE_CLAN_IMAGE.sub(" ", _STANDALONE_IMAGE.sub(" ", _CLAN_IMAGE.sub(" ", contents[:8192])))
        parser.feed(clean_contents)
        text = " ".join("".join(parser.parts).split())
        # Steam descriptions use BBCode as well as HTML and image macros.
        # Neither belongs in an ordinary plain-text news preview.
        text = re.sub(r"\{STEAM_[A-Z0-9_]+(?:\s+[^}]*)?\}", " ", text, flags=re.I)
        text = re.sub(r"\[/?[a-z][a-z0-9_]*(?:=[^]\r\n]{0,200})?\]", " ", text, flags=re.I)
        text = re.sub(r"(?:https?://|www\.)\S+", "", text, flags=re.I)
        # Provider text can also contain an image path *without* its macro.
        text = re.sub(r"(?<!\w)/?[1-9][0-9]{0,11}/[A-Za-z0-9_-]{8,128}(?:\.(?:png|jpe?g|webp))?(?:\?[^\s]{0,128})?(?:\.\.\.)?", " ", text, flags=re.I)
        return " ".join(c for c in html.unescape(text).split() if c.isprintable())[:320].strip()
    except (ValueError, AssertionError):
        return ""


def _cached_preview_and_inline_refs(preview: str, refs: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Reconcile old *private* news rows with the current image/text contract.

    Earlier records persisted Steam Clan image paths in `preview` without an
    inline-image field. These records may survive for many rolling four-app
    batches, so fresh-news normalization alone cannot repair the visible row.
    Recover only allowlisted relative image identities, never provider URLs;
    sanitize the previously accepted text in the same cache-read operation.
    The next ordinary source commit then persists the repaired row without a
    one-time migration, UI retry loop, or extra network owner.
    """
    recovered = news_inline_refs(preview)
    if not recovered and not re.search(r"(?:\{STEAM_CLAN_IMAGE\}|/[1-9][0-9]{0,11}/)", preview, re.I):
        return preview, refs
    merged = tuple(dict.fromkeys((*refs, *recovered)))[:MAX_INLINE_IMAGES_PER_STORY]
    return _plain_preview(preview), merged


def _appid(value: object) -> bool:
    return type(value) is int and 0 < value <= 0xFFFFFFFF


def _valid_title(value: object) -> bool:
    return type(value) is str and bool(value.strip()) and len(value) <= 300


_NON_ENGLISH_LABEL = re.compile(
    r"(?:^|[\s\[\(\-])(?:french|français|francais|german|deutsch|spanish|español|"
    r"italian|italiano|russian|русский|portuguese|português|polish|polski|"
    r"japanese|日本語|korean|한국어|chinese|中文|turkish|türkçe|ukrainian|"
    r"українська|brazilian|brasil|indonesian|thai|ภาษาไทย|arabic|العربية|"
    r"fr|de|es|ru|pt-br|zh-cn|zh-tw|ja|ko)(?:[\s\]\)\-:]|$)", re.I)
_ENGLISH_LABEL = re.compile(r"(?:^|[\s\[\(\-])(?:english|en-us|en-gb|en)(?:[\s\]\)\-:]|$)", re.I)


def _news_language(row: Mapping[str, Any], title: str) -> str:
    """Reject known translations; unknown English-looking titles remain provisional.

    Steam's public API does not guarantee a language code. This is deliberately
    conservative rather than an invented claim that we can classify all languages.
    """
    language = row.get("language", row.get("lang"))
    if language is not None:
        if type(language) is str:
            value = language.lower().strip().replace("_", "-")
            if value in {"english", "en", "en-us", "en-gb"}:
                return "english"
            if value:
                return "non_english"
        elif type(language) is int and language == 0:
            return "english"  # Steam's English language enum.
        else:
            return "non_english"
    if _NON_ENGLISH_LABEL.search(title) and not _ENGLISH_LABEL.search(title):
        return "non_english"
    # Non-Latin titles are not English. Avoid stripping accented game names
    # within otherwise Latin titles, which would discard legitimate English.
    if re.search(r"[\u0400-\u052f\u0600-\u06ff\u0900-\u097f\u0e00-\u0e7f\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", title):
        return "non_english"
    return "english" if _ENGLISH_LABEL.search(title) else "unknown"


def _event_key(story: FollowedNewsStory) -> tuple[int, str]:
    """Recognize repeated translated/labelled versions of the SAME headline."""
    headline = re.sub(r"\[[^]\n]{1,32}\]|\([^)]{1,32}\)", " ", story.title)
    headline = re.sub(r"\W+", " ", headline.casefold()).strip()
    return story.appid, headline


def _latest_unique(stories: list[FollowedNewsStory]) -> tuple[FollowedNewsStory, ...]:
    """Newest-first across all observed apps, not follow order or provider order."""
    seen_ids: set[tuple[int, str]] = set()
    seen_titles: dict[tuple[int, str], int] = {}
    seen_publication: set[tuple[int, int]] = set()
    chosen: list[FollowedNewsStory] = []
    for story in sorted(stories, key=lambda item: (-item.published_at, item.appid, item.gid)):
        identity, title_key = (story.appid, story.gid), _event_key(story)
        if identity in seen_ids:
            continue
        seen_ids.add(identity)
        previous_date = seen_titles.get(title_key)
        if previous_date is not None and abs(previous_date - story.published_at) <= 7 * 86400:
            continue
        # Steam sometimes publishes translated copies as separate GIDs with
        # distinct titles but the identical per-app event timestamp. Treat a
        # same-second same-app item as one event. Do not coalesce nearby minutes:
        # two real patches may be published one after the other.
        publication = (story.appid, story.published_at)
        if publication in seen_publication:
            continue
        seen_publication.add(publication)
        seen_titles[title_key] = story.published_at
        chosen.append(story)
        if len(chosen) == MAX_SELECTED_STORIES:
            break
    return tuple(chosen)


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
        # The Steam news GID is NOT necessarily the URL's /view/ event ID.
        # Keep only the exact, validated article URL from this app-bound API
        # response. External or unrecognized links remain non-clickable.
        target = news_article_target(appid, gid, row.get("url"))
        # Every validated app news row can open its app-bound news index. A
        # verified article URL takes precedence; missing/unsupported URLs never
        # manufacture a purported article address or disable the whole tile.
        action = True
        language = _news_language(row, title)
        # An explicit non-English record is NOT a separate selectable story.
        # Unsupported scripts are excluded rather than guessed as English.
        if language == "non_english":
            continue
        clean_title = re.sub(r"\s*[\[(](?:english|en(?:-us|-gb)?)[\])]\s*$", "", title.strip(), flags=re.I).strip()
        normalized.append(FollowedNewsStory(appid, gid, clean_title or title.strip(), date,
                                            feed.strip(), action, _plain_preview(row.get("contents")),
                                            inline_image_refs=news_inline_refs(row.get("contents")),
                                            article_url=target.browser_url if target else ""))
    return tuple(normalized)


def _snapshot_from_cache(path: Path, *, record: SteamResult | None = None) -> FollowedNewsSnapshot | None:
    result = record if record is not None else read_cache_record(path)
    if not result.ok or result.source_id != SteamSourceId.GAMES_FOLLOWED:
        return None
    p = result.payload
    if not isinstance(p, Mapping) or type(p.get("schema")) is not int or p["schema"] != CACHE_PAYLOAD_VERSION:
        return None
    follow, checked, offset = p.get("followed_count"), p.get("checked_count"), p.get("window_offset")
    rows = p.get("stories")
    covered = p.get("covered_count", checked)
    pending = p.get("maintenance_pending", False)
    if (type(follow) is not int or not 0 <= follow <= 4096
        or type(checked) is not int or not 0 <= checked <= min(follow, MAX_NEWS_APPS_PER_REFRESH)
        or type(offset) is not int or not 0 <= offset <= max(0, follow - 1)
        or type(covered) is not int or not checked <= covered <= follow
        or type(pending) is not bool or (pending and covered != follow)
        or not isinstance(rows, list) or len(rows) > MAX_SELECTED_STORIES):
        return None
    stories: list[FollowedNewsStory] = []
    seen: set[tuple[int, str]] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        appid, gid, title, date = row.get("appid"), row.get("gid"), row.get("title"), row.get("published_at")
        feed, action = row.get("feed_name"), row.get("action_available")
        preview, game_name = row.get("preview", ""), row.get("game_name", "")
        refs = row.get("inline_image_refs", ())
        article_url = row.get("article_url", "")
        if type(article_url) is not str:
            return None
        target = news_article_target(appid, gid, article_url) if article_url else None
        # An untrusted old URL cannot become a click target or erase the
        # otherwise valid private last-good news record. Use the safe app hub.
        if (not isinstance(refs, (list, tuple)) or len(refs) > MAX_INLINE_IMAGES_PER_STORY
            or any(not validated_inline_ref(ref) for ref in refs) or len(set(refs)) != len(refs)):
            return None
        if (not _appid(appid) or type(gid) is not str or not gid.isascii() or not gid.isdecimal()
            or not 1 <= len(gid) <= 32 or not _valid_title(title)
            or type(date) is not int or not 0 < date < 4_102_444_800
            or type(feed) is not str or len(feed) > 80 or type(action) is not bool
            or type(preview) is not str or len(preview) > 320 or not preview.isprintable()
            or type(game_name) is not str or len(game_name) > 160 or not game_name.isprintable()
            or (appid, gid) in seen or follow == 0):
            return None
        seen.add((appid, gid))
        preview, normalized_refs = _cached_preview_and_inline_refs(preview, tuple(refs))
        stories.append(FollowedNewsStory(appid, gid, title, date, feed,
                                         True, preview, game_name,
                                         normalized_refs, target.browser_url if target else ""))
    if result.fetched_at is None or not 0 < result.fetched_at <= time.time() + 60:
        return None
    return FollowedNewsSnapshot("available" if stories else "no_usable_news" if follow else "empty_follow_list",
                                tuple(stories), follow, checked, offset, result.fetched_at, from_cache=True,
                                covered_count=covered, maintenance_pending=pending)


def _persisted_followed_ids(path: Path, snapshot: FollowedNewsSnapshot | None, *,
                            record: SteamResult | None = None) -> tuple[int, ...] | None:
    """Profile-private, validated membership of the current last-good result."""
    if snapshot is None:
        return None
    result = record if record is not None else read_cache_record(path)
    if not result.ok or result.source_id != SteamSourceId.GAMES_FOLLOWED:
        return None
    ids = result.payload.get("followed_appids")
    if not isinstance(ids, list) or len(ids) != snapshot.followed_count:
        return None
    normalized = normalize_followed_appids({"response": {"appids": ids}})
    return normalized if normalized is not None and len(normalized) == snapshot.followed_count else None


def _unfinished_followed_ids(path: Path, snapshot: FollowedNewsSnapshot | None, *,
                             record: SteamResult | None = None) -> tuple[int, ...] | None:
    """Resume one already admitted sweep without re-fetching its entire follow set.

    A complete sweep is never pinned to an old list: the next ordinary refresh
    fetches the live membership again. The profile-private cache is validated
    afresh after process restart and never read without a valid last-good
    snapshot from that very same file.
    """
    if snapshot is None or not 0 < snapshot.covered_count < snapshot.followed_count:
        return None
    return _persisted_followed_ids(path, snapshot, record=record)


def _recent_complete_followed_ids(path: Path, snapshot: FollowedNewsSnapshot | None,
                                  *, now: float, record: SteamResult | None = None) -> tuple[tuple[int, ...], float] | None:
    """Reuse complete membership between independent, bounded maintenance sessions."""
    if (snapshot is None or snapshot.followed_count == 0
        or snapshot.covered_count != snapshot.followed_count):
        return None
    result = record if record is not None else read_cache_record(path)
    if not result.ok or result.source_id != SteamSourceId.GAMES_FOLLOWED:
        return None
    checked_at = result.payload.get("membership_checked_at")
    if (type(checked_at) not in (float, int) or type(checked_at) is bool
        or not 0 <= now - checked_at < FOLLOWED_MEMBERSHIP_TTL_SECONDS):
        return None
    ids = _persisted_followed_ids(path, snapshot, record=result)
    return (ids, float(checked_at)) if ids is not None else None


def _cached_news_buckets(path: Path, followed: tuple[int, ...], *,
                         record: SteamResult | None = None) -> dict[int, tuple[FollowedNewsStory, ...]]:
    """Bounded, private, durable per-app winners for accurate global re-ranking.

    Never trust cache entries to introduce app IDs outside the newly confirmed
    followed set. Older top-eight-only records upgrade on the next successful
    source commit without any parallel cache or one-time migration authority.
    """
    if len(followed) > MAX_PERSISTED_FOLLOWED_APPS:
        return {}
    result = record if record is not None else read_cache_record(path)
    if not result.ok or result.source_id != SteamSourceId.GAMES_FOLLOWED:
        return {}
    raw = result.payload.get("per_game_stories")
    if not isinstance(raw, dict) or len(raw) > len(followed):
        return {}
    allowed = set(followed)
    buckets: dict[int, tuple[FollowedNewsStory, ...]] = {}
    for key, rows in raw.items():
        if (type(key) is not str or not key.isascii() or not key.isdecimal()
            or int(key) not in allowed or not isinstance(rows, list)
            or len(rows) > MAX_NEWS_ITEMS_PER_APP):
            return {}
        appid = int(key)
        selected: list[FollowedNewsStory] = []
        seen_gids: set[str] = set()
        for value in rows:
            if not isinstance(value, Mapping):
                return {}
            gid, title, date = value.get("gid"), value.get("title"), value.get("published_at")
            feed, preview = value.get("feed_name"), value.get("preview", "")
            refs = value.get("inline_image_refs", ())
            if (not isinstance(refs, (tuple, list)) or len(refs) > MAX_INLINE_IMAGES_PER_STORY
                or any(not validated_inline_ref(ref) for ref in refs) or len(set(refs)) != len(refs)):
                return {}
            if (value.get("appid") != appid or type(gid) is not str or not gid.isascii()
                or not gid.isdecimal() or not 1 <= len(gid) <= 32 or gid in seen_gids
                or not _valid_title(title) or type(date) is not int
                or not 0 < date < 4_102_444_800 or type(feed) is not str
                or len(feed) > 80 or type(preview) is not str
                or len(preview) > 320 or not preview.isprintable()
                or type(value.get("action_available")) is not bool):
                return {}
            seen_gids.add(gid)
            article_url = value.get("article_url", "")
            if type(article_url) is not str:
                return {}
            target = news_article_target(appid, gid, article_url) if article_url else None
            # Never open an invalid cached article link; retain the news row
            # and provide its fixed app-bound news index as the click fallback.
            preview, normalized_refs = _cached_preview_and_inline_refs(preview, tuple(refs))
            selected.append(FollowedNewsStory(
                appid, gid, title, date, feed,
                True, preview,
                inline_image_refs=normalized_refs,
                article_url=target.browser_url if target else "",
            ))
        buckets[appid] = tuple(selected)
    return buckets


class FollowedNewsSource:
    """One explicit source invocation; the future Steam owner supplies its worker."""

    def __init__(self, *, profile_key: str, cache_root: Path | None = None,
                 coordinator: SteamRequestCoordinator | None = None,
                 backoff: SteamBackoffPolicy | None = None,
                 clock: Callable[[], float] = time.monotonic,
                 metadata_lookup: Callable[[int], tuple[str, str]] | None = None) -> None:
        if not isinstance(profile_key, str) or not profile_key.startswith("profile_"):
            raise ValueError("Expected an opaque Steam profile cache key")
        self._profile_key = profile_key
        self._path = cache_path_for_profile_key(profile_key, CACHE_KEY, root=cache_root)
        self._cache_root = cache_root
        self._coordinator = coordinator or SteamRequestCoordinator()
        self._backoff = backoff or SteamBackoffPolicy()
        self._clock = clock
        self._state_lock = threading.RLock()
        self._closed = False
        self._metadata: FollowedAppMetadata | None = None
        self._metadata_dirty = False
        self._owned_names_loaded = False
        self._owned_names: dict[int, str] = {}
        self._metadata_lookup = metadata_lookup or fetch_store_metadata
        self._allow_fixture_metadata = metadata_lookup is not None

    def cached(self) -> FollowedNewsSnapshot | None:
        snapshot = _snapshot_from_cache(self._path)
        return self._decorate(snapshot, allow_network=False) if snapshot is not None else None

    def _decorate(self, snapshot: FollowedNewsSnapshot, *, allow_network: bool,
                  allow_metadata_network: bool = False) -> FollowedNewsSnapshot:
        """Worker-only, bounded name/artwork projection. No GUI work."""
        if not snapshot.stories or self._closed:
            return snapshot
        from core.settings.storage_paths import get_steam_cache_dir
        from core.steam.followed_artwork_readiness import valid_local_artwork
        from core.steam.abandonment_cache import load_owned_game_choices_from_cache
        from core.steam.assets import (
            SteamAssetRecord, fetch_steam_app_artwork, find_cached_steam_app_artwork,
            find_cached_asset, fetch_and_cache_asset, _default_fetch_asset,
        )
        # One canonical per-AppID cache survives changes to owned-library state,
        # app restarts and failed Store requests. The article is never a name source.
        if self._metadata is None:
            self._metadata = FollowedAppMetadata(profile_key=self._profile_key, root=self._cache_root)
        metadata = self._metadata
        changed = False
        if not self._owned_names_loaded:
            try:
                self._owned_names = dict(load_owned_game_choices_from_cache(
                    profile_key=self._profile_key, root=self._cache_root, limit=5000,
                ))
                self._owned_names_loaded = True
            except Exception:
                pass  # Retry the one-time local read if local storage was unavailable.
        for story in snapshot.stories:
            title = self._owned_names.get(story.appid, "")
            if title and story.appid not in metadata.names:
                changed |= metadata.remember(story.appid, title)
        # Preserve last-good names present in old news snapshots. Never replace
        # an established name with a transient empty Store response.
        for story in snapshot.stories:
            if (valid_game_name(story.game_name)
                and story.game_name not in (f"Steam App {story.appid}", f"App {story.appid}")
                and story.appid not in metadata.names):
                changed |= metadata.remember(story.appid, story.game_name)
        # Hydrate only missing AppIDs belonging to this admitted visible result.
        # Four is a hard bound per ordinary refresh, independent of story count.
        if allow_metadata_network:
            attempted = 0
            for story in snapshot.stories:
                if self._closed or attempted >= MAX_NEWS_APPS_PER_REFRESH:
                    break
                if (story.appid in metadata.names or
                    time.time() - metadata.failed_at.get(story.appid, 0) < FAILED_LOOKUP_RETRY_SECONDS):
                    continue
                attempted += 1
                changed |= metadata.hydrate(story.appid, lookup=self._metadata_lookup, now=time.time())
        try:
            asset_dir = (self._cache_root / "assets" if self._cache_root is not None
                         else get_steam_cache_dir(profile_key=self._profile_key) / "assets")
        except Exception:
            asset_dir = None
        paths: dict[int, str] = {}
        # Reuse validated local cache hits for every story; cap fresh image work
        # to four AppIDs in this source job, including previously sampled winners.
        fetched = 0
        for story in snapshot.stories:
            if self._closed:
                return FollowedNewsSnapshot("retired")
            if story.appid in paths:
                continue
            path = None
            if asset_dir is not None:
                try:
                    path = valid_local_artwork(find_cached_steam_app_artwork(
                        cache_dir=asset_dir, appid=story.appid, artwork_shape="wide",
                    ))
                    store_art = metadata.artwork_urls.get(story.appid, "")
                    if path is None and store_art:
                        path = valid_local_artwork(find_cached_asset(asset_dir, store_art))
                    # One failed app art source cannot induce retries every six minutes.
                    retry_due = time.time() - metadata.art_failed_at.get(story.appid, 0.0) >= 86400
                    if path is None and allow_network and retry_due and fetched < MAX_NEWS_APPS_PER_REFRESH:
                        fetched += 1
                        result = fetch_steam_app_artwork(
                            cache_dir=asset_dir, appid=story.appid, artwork_shape="wide",
                        )
                        if isinstance(result, SteamAssetRecord):
                            path = valid_local_artwork(result.path)
                        if path is None and store_art:
                            # The Store's validated header URL can recover titles
                            # without a library_hero or legacy header asset.
                            alternative = fetch_and_cache_asset(
                                cache_dir=asset_dir, url=store_art, fetcher=_default_fetch_asset,
                            )
                            if isinstance(alternative, SteamAssetRecord):
                                path = valid_local_artwork(alternative.path)
                        if path is None:
                            metadata.art_failed_at[story.appid] = time.time()
                            changed = True
                        elif story.appid in metadata.art_failed_at:
                            metadata.art_failed_at.pop(story.appid, None)
                            changed = True
                except Exception:
                    path = None  # Image failure never makes an article invalid.
            paths[story.appid] = str(path) if path is not None else ""
        # News-body thumbnails are distinct from per-game artwork: they live
        # in the preview rail, never replace the game identity image. Only
        # allowlisted, URL-free refs from the accepted news payload are used.
        # Cache hits work offline; new image work shares this admitted source
        # worker and never causes per-image GUI publication.
        inline_rows: list[tuple[str, ...]] = []
        inline_fetched = 0
        inline_wrote = False
        inline_dir = asset_dir / "news_inline" if asset_dir is not None else None
        for story in snapshot.stories:
            if self._closed:
                return FollowedNewsSnapshot("retired")
            row_images: list[str] = []
            for ref in story.inline_image_refs:
                if inline_dir is None:
                    continue
                url = inline_image_url(ref)
                if not url:
                    continue
                try:
                    path = valid_local_artwork(find_cached_asset(inline_dir, url))
                    retry_due = time.time() - metadata.inline_failed_at.get(ref, 0.0) >= 86400
                    if path is None and allow_network and retry_due and inline_fetched < MAX_INLINE_IMAGE_FETCHES_PER_REFRESH:
                        inline_fetched += 1
                        outcome = fetch_and_cache_asset(
                            cache_dir=inline_dir, url=url,
                            fetcher=lambda address: _default_fetch_asset(address, timeout_seconds=5.0),
                            allowed_hosts=("clan.akamai.steamstatic.com",),
                        )
                        if isinstance(outcome, SteamAssetRecord):
                            path = valid_local_artwork(outcome.path)
                            inline_wrote |= path is not None
                        if path is None:
                            metadata.inline_failed_at[ref] = time.time()
                            if len(metadata.inline_failed_at) > 256:
                                metadata.inline_failed_at.pop(next(iter(metadata.inline_failed_at)))
                            changed = True
                        elif ref in metadata.inline_failed_at:
                            metadata.inline_failed_at.pop(ref, None)
                            changed = True
                    if path is not None:
                        row_images.append(str(path))
                except Exception:
                    # Optional thumbnail failures never invalidate the story.
                    continue
            inline_rows.append(tuple(row_images))
        if inline_wrote and inline_dir is not None:
            prune_inline_image_cache(
                inline_dir,
                protected=frozenset(Path(path) for row in inline_rows for path in row),
            )
        if self._closed:
            return FollowedNewsSnapshot("retired")
        # One source-worker summary per admitted snapshot, not per image, card,
        # Qt frame or consumer. Next physical log can distinguish no recovered
        # source refs, failed CDN warming and projection/presentation problems.
        inline_refs_count = sum(len(story.inline_image_refs) for story in snapshot.stories)
        if inline_refs_count:
            logger.info(
                "[STEAM][FOLLOWED_INLINE] stories=%d refs=%d local_images=%d "
                "network_attempts=%d new_local_files=%d cache_only=%s",
                len(snapshot.stories), inline_refs_count,
                sum(len(row) for row in inline_rows), inline_fetched,
                int(inline_wrote), not allow_network,
            )
        self._metadata_dirty |= changed
        if self._metadata_dirty:
            try:
                metadata.persist()
                self._metadata_dirty = False
            except Exception:
                pass  # Retry at the next normal worker admission, never per card/frame.
        return replace(
            snapshot,
            stories=tuple(replace(story, game_name=metadata.names.get(story.appid)
                                  or valid_game_name(story.game_name)
                                  or f"Steam App {story.appid}") for story in snapshot.stories),
            artwork_paths=tuple(paths.get(story.appid, "") for story in snapshot.stories),
            inline_image_paths=tuple(inline_rows),
        )

    def retire(self) -> None:
        with self._state_lock:
            self._closed = True
            self._coordinator.advance_generation()

    def refresh(self, steamid: str, *, opener: Callable[..., Any] | None = None,
                window_offset: int | None = None) -> FollowedNewsSnapshot:
        """Call from one admitted Steam worker, never the GUI/render or resize path."""
        if self._closed:
            return FollowedNewsSnapshot("retired")
        if window_offset is not None and (type(window_offset) is not int or window_offset < 0):
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
            record = read_cache_record(self._path)
            previous = _snapshot_from_cache(self._path, record=record)
            key = SteamRequestKey.from_params(profile_key=self._profile_key,
                                               source_id=SteamSourceId.GAMES_FOLLOWED,
                                               category=CACHE_KEY)
            decision = self._backoff.check(key, now=self._clock())
            if not decision.allowed:
                # Never reissue the followed-set request or any app-news work
                # while a denied/rate-limited source is cooling down. Cached
                # rows retain their original fetched_at and private identity.
                return (replace(self._decorate(previous, allow_network=False),
                                status="stale_cache", failure="backoff_active")
                        if previous is not None else FollowedNewsSnapshot("backoff_active"))
            handle = self._coordinator.begin(key)
            if not handle.owner:
                return previous or FollowedNewsSnapshot("already_refreshing")
            now = time.time()
            saved_followed = _persisted_followed_ids(self._path, previous, record=record)
            recent_membership = (_recent_complete_followed_ids(self._path, previous, now=now,
                                 record=record)
                                 if window_offset is None else None)
            followed = (_unfinished_followed_ids(self._path, previous, record=record)
                        if window_offset is None else None)
            membership_checked_at = None
            if followed is not None:
                # During the initial sweep, the already verified follow list is
                # pinned so individual four-feed jobs never repeat membership I/O.
                membership_checked_at = record.payload.get("membership_checked_at") if record.ok else None
            elif recent_membership is not None:
                followed, membership_checked_at = recent_membership
            if followed is None:
                status, followed = fetch_followed_appids_for_news_probe(steamid, opener=opener)
                if status != "confirmed_nonempty" and status != "confirmed_empty":
                    return self._finish_failure(handle, previous, status)
                assert followed is not None
                membership_checked_at = now
            membership_changed = (saved_followed is not None and set(saved_followed) != set(followed))
            if not followed:
                selected: tuple[int, ...] = ()
                offset = 0
            else:
                offset = ((previous.window_offset + previous.checked_count) if previous is not None
                          and previous.followed_count == len(followed)
                          and not membership_changed and window_offset is None
                          else (window_offset or 0)) % len(followed)
                # Rotate a bounded selection in canonical follow order. Card
                # width/height cannot change this window or perform a request.
                batch_size = min(len(followed), MAX_NEWS_APPS_PER_REFRESH)
                # The initial sweep must reach every game exactly once, without
                # wrapping and rechecking early games in its final short batch.
                if (window_offset is None and
                    (previous is None or previous.covered_count < previous.followed_count
                     or membership_changed)):
                    batch_size = min(batch_size, len(followed) - offset)
                selected = tuple(followed[(offset + i) % len(followed)] for i in range(batch_size))
            candidates: list[FollowedNewsStory] = []
            newly_checked: dict[int, tuple[FollowedNewsStory, ...]] = {}
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
                newly_checked[appid] = rows
                candidates.extend(rows)
            # Keep the latest eight discovered across successive bounded source
            # windows. Rechecking an app replaces its older entries (including
            # when that app now has no news), while unfollowed apps are removed.
            # This is still a sampled public-news view, NOT Steam's separately
            # personalized What's New feed or proof all follows were checked.
            selected_ids = set(selected)
            followed_ids = set(followed)
            buckets = _cached_news_buckets(self._path, followed, record=record)
            if not buckets and previous is not None:
                # Existing compact caches still retain their last-good eight.
                for story in previous.stories:
                    if story.appid in followed_ids and story.appid not in selected_ids:
                        buckets.setdefault(story.appid, ())
                        buckets[story.appid] += (story,)
            buckets.update(newly_checked)
            if len(followed) <= MAX_PERSISTED_FOLLOWED_APPS:
                candidates = [story for rows in buckets.values() for story in rows]
            elif previous is not None:
                candidates.extend(story for story in previous.stories
                                  if story.appid in followed_ids and story.appid not in selected_ids)
            accepted = _latest_unique(candidates)
            # Initial complete coverage is a durable milestone, NOT an excuse
            # to trigger another accelerated 142-game sweep every six minutes.
            # After that, each maintenance session admits up to TWO four-feed
            # jobs, then returns to the ordinary shared refresh interval.
            previous_covered = (previous.covered_count if previous is not None
                                and previous.followed_count == len(followed)
                                and not membership_changed else 0)
            was_complete = (previous is not None and previous_covered == len(followed)
                            and not membership_changed)
            covered = (len(followed) if was_complete else
                       min(len(followed), previous_covered + len(selected)))
            maintenance_pending = bool(
                was_complete and window_offset is None and len(followed) > MAX_NEWS_APPS_PER_REFRESH
                and not previous.maintenance_pending)
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
                    "covered_count": covered,
                    "maintenance_pending": maintenance_pending,
                    "window_offset": offset,
                    "membership_checked_at": membership_checked_at,
                    # Private stable membership for this progressive sweep.
                    # Avoid 36 redundant membership calls for 142 follows.
                    # The completed sweep refreshes membership normally.
                    "followed_appids": list(followed),
                    "stories": [vars(story).copy() for story in accepted],
                }
                if len(followed) <= MAX_PERSISTED_FOLLOWED_APPS:
                    payload["per_game_stories"] = {
                        str(appid): [vars(story).copy() for story in rows]
                        for appid, rows in buckets.items()
                    }
                timestamp = time.time()
                write_cache_record(SteamCacheRecord(
                    cache_key=CACHE_KEY, source_id=SteamSourceId.GAMES_FOLLOWED,
                    payload=payload, fetched_at=timestamp,
                    attempted_sources=(SteamSourceId.GAMES_FOLLOWED, SteamSourceId.APP_NEWS),
                ), self._path)
                snapshot = FollowedNewsSnapshot(
                    "available" if accepted else "no_usable_news" if followed else "empty_follow_list",
                    accepted, len(followed), len(selected), offset, timestamp,
                    covered_count=covered, maintenance_pending=maintenance_pending,
                )
            # Image work is bounded, off-GUI and outside the source commit lock.
            return self._decorate(snapshot, allow_network=opener is None,
                                  allow_metadata_network=(opener is None or self._allow_fixture_metadata)) if not self._closed else FollowedNewsSnapshot("retired")

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
            return replace(self._decorate(previous, allow_network=False),
                           status="stale_cache", failure=failure)
        return FollowedNewsSnapshot(failure)
