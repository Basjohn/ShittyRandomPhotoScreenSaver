"""Validated Steam-client and HTTPS targets for semantic widget actions."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class SteamLinkTarget:
    """One validated Steam deep link with its browser-safe equivalent."""

    kind: str
    steam_url: str
    browser_url: str


def friend_message_target(steam_id: object) -> SteamLinkTarget | None:
    """Build a best-effort directed-chat target with a profile fallback."""

    normalized = normalize_steam_id(steam_id)
    if normalized is None:
        return None
    return SteamLinkTarget(
        kind="friend_message",
        steam_url=f"steam://friends/message/{normalized}",
        browser_url=f"https://steamcommunity.com/profiles/{normalized}",
    )


def friend_profile_target(steam_id: object) -> SteamLinkTarget | None:
    """Build one public profile target without exposing the ID to QML."""

    normalized = normalize_steam_id(steam_id)
    if normalized is None:
        return None
    profile_url = f"https://steamcommunity.com/profiles/{normalized}"
    return SteamLinkTarget(
        kind="friend_profile",
        steam_url=profile_url,
        browser_url=profile_url,
    )


def store_target(appid: object) -> SteamLinkTarget | None:
    """Build the Steam-client and public-store targets for one app."""

    normalized = normalize_appid(appid)
    if normalized is None:
        return None
    return SteamLinkTarget(
        kind="store",
        steam_url=f"steam://store/{normalized}",
        browser_url=f"https://store.steampowered.com/app/{normalized}/",
    )



def news_article_target(appid: object, gid: object, supplied_url: object) -> SteamLinkTarget | None:
    """Allow only a canonical app-bound Steam Store news URL from public feeds.

    The URL is never trusted from QML, article scraping or an unverified feed.
    Provider links to other hosts, encoded paths, ports, redirects or generic
    community pages remain unclickable until independently proved safe. This
    constructs a typed target only; the G0 probe does not launch it.
    """
    normalized = normalize_appid(appid)
    if normalized is None or type(gid) is not str or not gid.isascii() or not gid.isdecimal() or not 1 <= len(gid) <= 32:
        return None
    if type(supplied_url) is not str or len(supplied_url) > 512:
        return None
    canonical = f"https://store.steampowered.com/news/app/{normalized}/view/{gid}"
    try:
        parts = urlsplit(supplied_url)
    except ValueError:
        return None
    if (
        parts.scheme != "https"
        or parts.netloc != "store.steampowered.com"
        or parts.path != f"/news/app/{normalized}/view/{gid}"
        or parts.query or parts.fragment or supplied_url != canonical
    ):
        return None
    return SteamLinkTarget(kind="news_article", steam_url=canonical, browser_url=canonical)

def normalize_steam_id(value: object) -> str | None:
    text = str(value or "").strip()
    if not text.isascii() or not text.isdigit() or not 15 <= len(text) <= 20:
        return None
    return text if int(text) > 0 else None


def normalize_appid(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 < parsed <= 0xFFFFFFFF else None


__all__ = [
    "SteamLinkTarget",
    "friend_message_target",
    "news_article_target",
    "friend_profile_target",
    "normalize_appid",
    "normalize_steam_id",
    "store_target",
]
