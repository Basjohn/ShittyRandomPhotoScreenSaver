"""Read-only G0 viability check, never an admitted Steam widget runtime.

No scheduler, account-state mutation, article request or cache write. The caller
must explicitly request this one network operation. Only non-identifying status
and item count are suitable for stdout; app IDs stay private in this process.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.steam.backend import build_endpoint, fetch_json
from core.steam.models import SteamResultStatus, SteamSourceId

MAX_FOLLOWED_GAMES = 4096  # Input safety bound, NOT a requested-news fan-out budget.


@dataclass(frozen=True)
class FollowedGamesProbeResult:
    status: str
    count: int | None = None


def normalize_followed_appids(payload: Mapping[str, Any]) -> tuple[int, ...] | None:
    """Accept only the documented response/appids shape; never infer empty."""
    response = payload.get("response")
    if not isinstance(response, Mapping):
        return None
    rows = response.get("appids")
    if not isinstance(rows, list) or len(rows) > MAX_FOLLOWED_GAMES:
        return None
    result: list[int] = []
    seen: set[int] = set()
    for appid in rows:
        if type(appid) is not int or not 0 < appid <= 0xFFFFFFFF or appid in seen:
            return None
        seen.add(appid)
        result.append(appid)
    return tuple(result)


def fetch_followed_appids_for_news_probe(
    steamid: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> tuple[str, tuple[int, ...] | None]:
    """One explicit follow request, private IDs only in the caller's stack."""
    endpoint = build_endpoint(SteamSourceId.GAMES_FOLLOWED, steamid=steamid)
    result = fetch_json(endpoint, opener=opener)
    if result.status is not SteamResultStatus.SUCCESS:
        return result.status.value, None
    appids = normalize_followed_appids(result.payload or {})
    if appids is None:
        return SteamResultStatus.INVALID_RESPONSE.value, None
    return ("confirmed_nonempty" if appids else "confirmed_empty"), appids


def probe_followed_games(
    steamid: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> FollowedGamesProbeResult:
    """One bounded read through SRPSS's existing redacted Steam transport."""
    status, appids = fetch_followed_appids_for_news_probe(steamid, opener=opener)
    return FollowedGamesProbeResult(status, len(appids) if appids is not None else None)
