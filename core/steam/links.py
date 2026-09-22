"""Validated Steam-client and HTTPS targets for semantic widget actions."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlsplit


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



def news_hub_target(appid: object) -> SteamLinkTarget | None:
    """Safe, app-bound destination when an exact Steam article URL is unavailable.

    Never substitute an API news GID for a Steam news *event* ID. The hub is
    explicitly a game news index, not a claim to have resolved a particular post.
    """
    if type(appid) is not int or not 0 < appid <= 0xFFFFFFFF:
        return None
    url = f"https://store.steampowered.com/news/app/{appid}/"
    return SteamLinkTarget(kind="news_hub", steam_url=url, browser_url=url)


def news_article_target(appid: object, gid: object, supplied_url: object) -> SteamLinkTarget | None:
    """Accept the actual app-news article address, not an invented GID route.

    The caller must have obtained this URL from an app-bound GetNewsForApp
    response (or the validated private cache). Steam event URL IDs are not
    necessarily the news API GID. Only HTTPS article paths on two exact Steam
    hosts are eligible, plus Steam's exact news/externalpost redirect route
    for syndicated news. Do not turn the API news GID into a Store /view/ ID.
    A community /games/<slug>/... route is bound by the trusted app-news
    response, not by the human-readable slug in its URL.
    """
    normalized = normalize_appid(appid)
    if (normalized is None or type(gid) is not str or not gid.isascii()
        or not gid.isdecimal() or not 1 <= len(gid) <= 32
        or type(supplied_url) is not str or not 20 <= len(supplied_url) <= 512
        or any(ord(c) < 32 or ord(c) > 126 for c in supplied_url)):
        return None
    try:
        parts = urlsplit(supplied_url)
    except ValueError:
        return None
    if (parts.scheme != "https" or parts.netloc not in
        ("store.steampowered.com", "steamcommunity.com", "steamstore-a.akamaihd.net")
        or parts.query or parts.fragment or parts.username is not None
        or parts.password is not None or parts.port is not None):
        return None
    path = parts.path
    # The public app-news API uses Steam's own /externalpost/<feed>/<GID>
    # endpoint for syndicated publisher news. It redirects to the *article*,
    # rather than the game's news index. The externalpost GID is an API GID;
    # unlike Store /view/ event IDs, it must match the accepted news item.
    # Feed labels can contain a literal space ("PC Gamer"). Normalize ONLY
    # that bounded path segment into URL encoding, not an arbitrary redirect.
    if parts.netloc in ("steamstore-a.akamaihd.net", "store.steampowered.com") and path.startswith("/news/externalpost/"):
        segments = path.split("/")
        if len(segments) != 5 or segments[:3] != ["", "news", "externalpost"]:
            return None
        raw_feed, source_gid = segments[3:]
        # Steam may supply a literal space or %20 in a feed such as PC Gamer;
        # no other percent escapes or URL components are allowed.
        feed = raw_feed.replace("%20", " ")
        if (not 1 <= len(feed) <= 80 or not feed[0].isascii() or not feed[0].isalnum()
            or not feed[-1].isascii() or not feed[-1].isalnum() or "  " in feed
            or not all(c.isascii() and (c.isalnum() or c in "_ -") for c in feed)
            or source_gid != gid):
            return None
        url = (f"https://{parts.netloc}/news/externalpost/"
               f"{quote(feed, safe='_-')}/{gid}")
        return SteamLinkTarget(kind="news_article", steam_url=url, browser_url=url)
    if parts.netloc == "store.steampowered.com":
        prefix = f"/news/app/{normalized}/view/"
        event = path[len(prefix):] if path.startswith(prefix) else ""
    else:
        prefix = f"/app/{normalized}/announcements/detail/"
        if path.startswith(prefix):
            event = path[len(prefix):]
        else:
            # Steam's own game-announcement links often use a community
            # vanity slug, not an AppID. The link is admitted only from the
            # validated AppID-specific Steam API response / private cache.
            segments = path.split("/")
            event = (segments[5] if len(segments) == 6
                     and segments[0] == "" and segments[1] == "games"
                     and 1 <= len(segments[2]) <= 80
                     and segments[2].isascii()
                     and all(c.isalnum() or c in "_-" for c in segments[2])
                     and segments[3:5] == ["announcements", "detail"] else "")
    if not event or len(event) > 32 or not event.isascii() or not event.isdecimal():
        return None
    # Preserve Steam's source-provided *article* ID (which may differ from
    # the API news GID); do not synthesize another URL from the GID.
    return SteamLinkTarget(kind="news_article", steam_url=supplied_url, browser_url=supplied_url)


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
    "news_hub_target",
    "friend_profile_target",
    "normalize_appid",
    "normalize_steam_id",
    "store_target",
]
