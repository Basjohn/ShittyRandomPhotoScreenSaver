"""Durable, account-private Achievement Pulse candidate history.

Steam's recently-played response is a rolling discovery window, not an
account-wide achievement feed.  The successful empty response must remain a
truthful *current* source record while previous per-app achievement snapshots
remain discoverable for the lifetime of the cache.

A compact index avoids re-reading every cached achievement list at every
startup.  If an older installation has no index (or its index is unreadable),
rebuild from the already-existing per-app files.  Discovery never contacts
Steam, guesses credentials, or deletes historical data.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from core.logging.logger import get_logger
from core.settings.storage_paths import ProfileRef
from core.steam.achievement_pulse import latest_unlock_timestamp, recent_games
from core.steam.cache import (
    SteamCacheRecord,
    cache_path_for_profile_key,
    get_steam_source_refresh_lock,
    read_cache_record,
    write_cache_record,
)
from core.steam.models import SteamResult, SteamSourceId

logger = get_logger(__name__)

HISTORY_CACHE_KEY = "achievement_pulse_history"
_ACHIEVEMENT_PREFIX = "achievement_pulse_achievements_"
_OWNED_GAMES_CACHE_KEY = "achievement_pulse_owned_games"


def _appid(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if number > 0 else None


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _clean_game(game: Mapping[str, Any]) -> dict[str, Any] | None:
    appid = _appid(game.get("appid"))
    if appid is None:
        return None
    result: dict[str, Any] = {
        "appid": appid,
        "latest_unlock_time": _nonnegative_int(game.get("latest_unlock_time")),
        "last_seen_at": _nonnegative_int(game.get("last_seen_at")),
    }
    name = game.get("name")
    if isinstance(name, str) and name.strip():
        result["name"] = name.strip()
    playtime = game.get("playtime_forever")
    if playtime is not None:
        try:
            result["playtime_forever"] = max(0, int(playtime))
        except (TypeError, ValueError, OverflowError):
            pass
    return result


def _read_index(path: Path, read_record: Callable[[Path], SteamResult]) -> dict[int, dict[str, Any]] | None:
    result = read_record(path)
    if not result.ok or not isinstance(result.payload, Mapping):
        return None
    if result.source_id != SteamSourceId.RECENTLY_PLAYED:
        return None
    games = result.payload.get("games")
    if not isinstance(games, list):
        return None
    indexed: dict[int, dict[str, Any]] = {}
    for raw_game in games:
        if isinstance(raw_game, Mapping) and (game := _clean_game(raw_game)) is not None:
            indexed[game["appid"]] = game
    return indexed


def _merge_recent(indexed: dict[int, dict[str, Any]], result: SteamResult) -> None:
    seen_at = _nonnegative_int(result.fetched_at)
    for game in recent_games(result):
        normalized = _clean_game(game)
        if normalized is None:
            continue
        appid = normalized["appid"]
        old = indexed.get(appid, {"appid": appid, "latest_unlock_time": 0, "last_seen_at": 0})
        # Live discovery is allowed to change title/playtime; it must not zero
        # the cached achievement timestamp merely because the rolling source
        # has no achievement information.
        merged = dict(old)
        merged.update({k: v for k, v in normalized.items() if k not in {"latest_unlock_time", "last_seen_at", "playtime_forever"}})
        if "playtime_forever" in normalized:
            # Lifetime minutes should not regress because an older source
            # snapshot arrived after a newer owned-games response.
            merged["playtime_forever"] = max(
                _nonnegative_int(old.get("playtime_forever")), normalized["playtime_forever"]
            )
        merged["last_seen_at"] = max(_nonnegative_int(old.get("last_seen_at")), seen_at)
        indexed[appid] = merged


def _merge_owned(indexed: dict[int, dict[str, Any]], result: SteamResult) -> None:
    """Enrich *known achievement apps* from the shared library cache.

    Never treat ownership as evidence of an achievement, and never replace
    historical playtime when Steam omits it or returns a private library.
    """
    if not result.ok or result.source_id != SteamSourceId.OWNED_GAMES or not isinstance(result.payload, Mapping):
        return
    response = result.payload.get("response")
    if not isinstance(response, Mapping) or not isinstance(response.get("games"), list):
        return
    for raw_game in response["games"]:
        if not isinstance(raw_game, Mapping):
            continue
        game = _clean_game(raw_game)
        if game is None or game["appid"] not in indexed:
            continue
        old = indexed[game["appid"]]
        if "playtime_forever" in game:
            old["playtime_forever"] = max(
                _nonnegative_int(old.get("playtime_forever")), game["playtime_forever"]
            )
        if not old.get("name") and game.get("name"):
            old["name"] = game["name"]


def _update_from_achievement(indexed: dict[int, dict[str, Any]], appid: int, result: SteamResult) -> None:
    if not result.ok or not isinstance(result.payload, Mapping):
        return
    playerstats = result.payload.get("playerstats")
    if (
        not isinstance(playerstats, Mapping)
        or playerstats.get("success") is False
        or not isinstance(playerstats.get("achievements"), list)
    ):
        return
    old = indexed.get(appid, {"appid": appid, "latest_unlock_time": 0, "last_seen_at": 0})
    updated = dict(old)
    name = playerstats.get("gameName")
    if not updated.get("name") and isinstance(name, str) and name.strip():
        updated["name"] = name.strip()
    # An actual refreshed achievement list supersedes its old unlock summary.
    updated["latest_unlock_time"] = latest_unlock_timestamp(result)
    updated["last_seen_at"] = max(_nonnegative_int(updated.get("last_seen_at")), _nonnegative_int(result.fetched_at))
    indexed[appid] = updated


def _discover_existing_app_cache(
    indexed: dict[int, dict[str, Any]],
    *,
    cache_dir: Path,
    read_record: Callable[[Path], SteamResult],
    newer_than_ns: int = -1,
) -> None:
    """Read every legacy cache once, then only files newer than the index.

    Other Steam cards may update a shared per-app achievement record without
    running Achievement Pulse.  Directory metadata is cheap to enumerate on
    an IO worker; opening only changed records prevents a stale Pulse index
    from hiding those external unlocks.
    """
    recovered = 0
    for path in cache_dir.glob(f"{_ACHIEVEMENT_PREFIX}*.json"):
        appid = _appid(path.stem.removeprefix(_ACHIEVEMENT_PREFIX))
        if appid is None or path.stem != f"{_ACHIEVEMENT_PREFIX}{appid}":
            continue
        try:
            if path.stat().st_mtime_ns <= newer_than_ns:
                continue
        except OSError:
            continue  # A concurrent cache-clear may unlink the file.
        result = read_record(path)
        if result.ok and result.source_id == SteamSourceId.PLAYER_ACHIEVEMENTS:
            _update_from_achievement(indexed, appid, result)
            recovered += 1
    if recovered:
        logger.info("[STEAM][ACHIEVEMENT_PULSE] Reconciled per-app history apps=%d", recovered)


def _load_index(
    *,
    profile_key: str,
    recent_result: SteamResult,
    profile: ProfileRef,
    root: Path | None,
    read_record: Callable[[Path], SteamResult],
) -> dict[int, dict[str, Any]]:
    path = cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, profile=profile, root=root)
    indexed = _read_index(path, read_record)
    if indexed is None:
        indexed = {}
        # Older versions only stored per-app snapshots, without a persistent
        # way to select those apps once the live recent list rolled off.
        _discover_existing_app_cache(indexed, cache_dir=path.parent, read_record=read_record)
    else:
        try:
            index_mtime_ns = path.stat().st_mtime_ns
        except OSError:
            index_mtime_ns = -1
        _discover_existing_app_cache(
            indexed, cache_dir=path.parent, read_record=read_record,
            newer_than_ns=index_mtime_ns,
        )
    _merge_recent(indexed, recent_result)
    # Both Steam cards share this cache record; use it for playtime without
    # inventing candidate achievements or issuing a provider request.
    owned_result = read_record(cache_path_for_profile_key(
        profile_key, _OWNED_GAMES_CACHE_KEY, profile=profile, root=root
    ))
    _merge_owned(indexed, owned_result)
    return indexed


def cached_achievement_candidates(
    *,
    profile_key: str,
    recent_result: SteamResult,
    profile: ProfileRef = None,
    root: Path | None = None,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> tuple[dict[str, Any], ...]:
    """Return newest known unlocks followed by play-recency fallback.

    Do not mistake a zero-game live response for a cache-clear directive.
    Historical candidates must still have an on-disk achievement record;
    current live games remain candidates even before their first fetch.
    """
    indexed = _load_index(
        profile_key=profile_key,
        recent_result=recent_result,
        profile=profile,
        root=root,
        read_record=read_record,
    )
    current_appids = {int(game["appid"]) for game in recent_games(recent_result)}
    live_order = {int(game["appid"]): position for position, game in enumerate(recent_games(recent_result))}
    eligible = []
    for appid, game in indexed.items():
        if appid not in current_appids and not cache_path_for_profile_key(
            profile_key, f"{_ACHIEVEMENT_PREFIX}{appid}", profile=profile, root=root
        ).is_file():
            continue
        eligible.append(game)
    eligible.sort(key=lambda game: (
        -_nonnegative_int(game.get("latest_unlock_time")),
        0 if game["appid"] in live_order else 1,
        live_order.get(game["appid"], 0),
        -_nonnegative_int(game.get("last_seen_at")),
        game["appid"],
    ))
    return tuple(eligible)


def persist_achievement_history(
    *,
    profile_key: str,
    recent_result: SteamResult,
    observed_appids: tuple[int, ...],
    profile: ProfileRef = None,
    root: Path | None = None,
    now: float | None = None,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> None:
    """Commit only local discovery and already-fetched achievements atomically."""
    with get_steam_source_refresh_lock(profile_key, HISTORY_CACHE_KEY):
        path = cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, profile=profile, root=root)
        indexed = _load_index(
            profile_key=profile_key,
            recent_result=recent_result,
            profile=profile,
            root=root,
            read_record=read_record,
        )
        for appid in dict.fromkeys(observed_appids):
            if _appid(appid) is None:
                continue
            achievement_path = cache_path_for_profile_key(
                profile_key, f"{_ACHIEVEMENT_PREFIX}{appid}", profile=profile, root=root
            )
            result = read_record(achievement_path)
            if result.source_id == SteamSourceId.PLAYER_ACHIEVEMENTS:
                _update_from_achievement(indexed, appid, result)
        previous = _read_index(path, read_record)
        if previous == indexed:
            return
        write_cache_record(
            SteamCacheRecord(
                cache_key=HISTORY_CACHE_KEY,
                source_id=SteamSourceId.RECENTLY_PLAYED,
                payload={"games": list(indexed.values())},
                fetched_at=time.time() if now is None else float(now),
            ),
            path,
        )
        logger.info("[STEAM][ACHIEVEMENT_PULSE] Persisted history candidate_apps=%d", len(indexed))
