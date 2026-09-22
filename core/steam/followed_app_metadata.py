"""Profile-private, durable AppID metadata for the admitted followed-news source.

This is a cache, not a new owner or scheduler. Read once per source lifetime;
only its existing bounded background refresh may hydrate an unknown AppID.
"""
from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urlsplit

from core.steam.cache import SteamCacheRecord, cache_path_for_profile_key, read_cache_record, write_cache_record
from core.steam.models import SteamSourceId
from core.steam.followed_news_inline_artwork import validated_inline_ref

METADATA_KEY = "games_followed_app_metadata"
MAX_METADATA_APPS = 4096
MAX_METADATA_RESPONSE_BYTES = 256_000
FAILED_LOOKUP_RETRY_SECONDS = 6 * 3600
_ALLOWED_IMAGE_HOSTS = frozenset(("cdn.akamai.steamstatic.com", "shared.akamai.steamstatic.com"))


def valid_game_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    title = " ".join(value.split())
    return title if title and len(title) <= 160 and title.isprintable() else ""


def valid_store_artwork_url(value: object, appid: int) -> str:
    if not isinstance(value, str) or len(value) > 500:
        return ""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return ""
    if (parsed.scheme != "https" or parsed.hostname not in _ALLOWED_IMAGE_HOSTS
        or port not in (None, 443) or parsed.username or parsed.password
        or not parsed.path.startswith((f"/steam/apps/{appid}/", f"/store_item_assets/steam/apps/{appid}/"))
        or parsed.query or parsed.fragment):
        return ""
    return value


def parse_store_metadata(payload: object, appid: int) -> tuple[str, str]:
    if not isinstance(payload, Mapping):
        return "", ""
    result = payload.get(str(appid))
    if not isinstance(result, Mapping) or result.get("success") is not True:
        return "", ""
    info = result.get("data")
    if not isinstance(info, Mapping):
        return "", ""
    return valid_game_name(info.get("name")), valid_store_artwork_url(info.get("header_image"), appid)


def fetch_store_metadata(appid: int) -> tuple[str, str]:
    """Single-AppID public Store lookup, worker-only and bounded in time/bytes."""
    if type(appid) is not int or not 0 < appid <= 0xFFFFFFFF:
        return "", ""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
    request = urllib.request.Request(url, headers={"User-Agent": "SRPSS-Steam/0.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=4.0) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "store.steampowered.com":
                return "", ""
            data = response.read(MAX_METADATA_RESPONSE_BYTES + 1)
            if len(data) > MAX_METADATA_RESPONSE_BYTES:
                return "", ""
        return parse_store_metadata(json.loads(data), appid)
    except (OSError, ValueError, TypeError, OverflowError):
        return "", ""


class FollowedAppMetadata:
    """One source-local view of the durable profile cache; no background tasks."""

    def __init__(self, *, profile_key: str, root: Path | None = None) -> None:
        self.path = cache_path_for_profile_key(profile_key, METADATA_KEY, root=root)
        self.names: dict[int, str] = {}
        self.artwork_urls: dict[int, str] = {}
        self.failed_at: dict[int, float] = {}
        self.art_failed_at: dict[int, float] = {}
        self.inline_failed_at: dict[str, float] = {}
        record = read_cache_record(self.path)
        if not record.ok or record.source_id != SteamSourceId.GAMES_FOLLOWED:
            return
        failed_inline = record.payload.get("inline_failed_at", {})
        if isinstance(failed_inline, dict) and len(failed_inline) <= 256:
            for ref, failed_at in failed_inline.items():
                if (validated_inline_ref(ref) and type(failed_at) in (float, int)
                    and 0 < failed_at <= time.time()):
                    self.inline_failed_at[ref] = float(failed_at)
        entries = record.payload.get("apps")
        if not isinstance(entries, dict) or len(entries) > MAX_METADATA_APPS:
            return
        for key, entry in entries.items():
            if (not isinstance(key, str) or not key.isascii() or not key.isdecimal()
                or not isinstance(entry, Mapping)):
                continue
            appid = int(key)
            if not 0 < appid <= 0xFFFFFFFF:
                continue
            name = valid_game_name(entry.get("name"))
            if name and name not in (f"Steam App {appid}", f"App {appid}"):
                self.names[appid] = name
                art = valid_store_artwork_url(entry.get("artwork_url"), appid)
                if art:
                    self.artwork_urls[appid] = art
            artwork_failed = entry.get("art_failed_at")
            if type(artwork_failed) in (float, int) and 0 < artwork_failed <= time.time():
                self.art_failed_at[appid] = float(artwork_failed)
            failed = entry.get("failed_at")
            if not name and type(failed) in (float, int) and 0 < failed <= time.time():
                self.failed_at[appid] = float(failed)

    def remember(self, appid: int, name: str, artwork_url: str = "") -> bool:
        title = valid_game_name(name)
        if (not title or title in (f"Steam App {appid}", f"App {appid}")
            or (self.names.get(appid) == title and (not artwork_url or self.artwork_urls.get(appid) == artwork_url))):
            return False
        if appid not in self.names and len(self.names) >= MAX_METADATA_APPS:
            return False
        self.names[appid] = title
        art = valid_store_artwork_url(artwork_url, appid)
        if art:
            self.artwork_urls[appid] = art
        self.failed_at.pop(appid, None)
        return True

    def hydrate(self, appid: int, *, lookup: Callable[[int], tuple[str, str]], now: float) -> bool:
        """Attempt once per AppID until success or a bounded failure retry."""
        if appid in self.names or now - self.failed_at.get(appid, 0.0) < FAILED_LOOKUP_RETRY_SECONDS:
            return False
        try:
            name, art = lookup(appid)
        except Exception:
            name, art = "", ""
        if self.remember(appid, name, art):
            return True
        self.failed_at[appid] = now
        return True

    def persist(self) -> None:
        keys = tuple(dict.fromkeys((*self.names, *self.failed_at, *self.art_failed_at)))[:MAX_METADATA_APPS]
        entries = {
            str(appid): {"name": self.names.get(appid, ""),
                         "artwork_url": self.artwork_urls.get(appid, ""),
                         "failed_at": self.failed_at.get(appid, 0.0),
                         "art_failed_at": self.art_failed_at.get(appid, 0.0)}
            for appid in keys
        }
        write_cache_record(SteamCacheRecord(
            cache_key=METADATA_KEY, source_id=SteamSourceId.GAMES_FOLLOWED,
            payload={"schema": 1, "apps": entries, "inline_failed_at":
                     dict(list(self.inline_failed_at.items())[-256:])}, fetched_at=time.time(),
        ), self.path)
