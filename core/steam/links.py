"""Validated Steam-client and HTTPS targets for semantic widget actions."""

from __future__ import annotations

from dataclasses import dataclass


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
    "normalize_appid",
    "normalize_steam_id",
    "store_target",
]
