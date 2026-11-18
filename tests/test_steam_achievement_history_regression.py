"""Fixture-only regression gates for Steam Achievement Pulse historical recovery.

No real credentials, network requests, Qt, providers, or tool tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from core.steam.achievement_pulse import AchievementPulseSelection
from core.steam.achievement_pulse_cache import (
    RECENT_GAMES_CACHE_KEY,
    achievement_cache_key_for_app,
    achievement_schema_cache_key_for_app,
    load_achievement_pulse_cache_snapshot,
    load_recent_game_titles_from_cache,
    refresh_achievement_pulse_cache,
)
from core.steam.achievement_pulse_history import HISTORY_CACHE_KEY
from core.steam.cache import (
    SteamCacheRecord,
    cache_path_for_profile_key,
    read_cache_record,
    write_cache_record,
)
from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key
from core.steam.models import SteamSourceId


class _Response:
    status = 200

    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self, _limit: int) -> bytes:
        return self._payload


def _write(path: Path, profile_key: str, cache_key: str, source_id: SteamSourceId, payload: dict, at: float) -> None:
    write_cache_record(
        SteamCacheRecord(cache_key=cache_key, source_id=source_id, payload=payload, fetched_at=at),
        cache_path_for_profile_key(profile_key, cache_key, root=path),
    )


def _achievement(name: str, unlock: int) -> dict:
    return {
        "playerstats": {
            "success": True,
            "gameName": name,
            "achievements": [{"apiname": "AWARD", "achieved": 1, "unlocktime": unlock}],
        }
    }


def _schema(name: str) -> dict:
    return {"game": {"availableGameStats": {"achievements": [{"name": "AWARD", "displayName": f"{name} Award"}]}}}


def test_recovers_preindex_per_app_cache_after_recent_played_was_overwritten_empty(tmp_path: Path) -> None:
    profile_key = "profile_1234567890abcdef12345678"
    _write(tmp_path, profile_key, RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED,
           {"response": {}}, 10_000)
    _write(tmp_path, profile_key, achievement_cache_key_for_app(111), SteamSourceId.PLAYER_ACHIEVEMENTS,
           _achievement("Older Game", 1_000), 1_000)
    _write(tmp_path, profile_key, achievement_cache_key_for_app(222), SteamSourceId.PLAYER_ACHIEVEMENTS,
           _achievement("Newest Game", 2_000), 2_000)
    _write(tmp_path, profile_key, achievement_schema_cache_key_for_app(222), SteamSourceId.ACHIEVEMENT_SCHEMA,
           _schema("Newest Game"), 2_001)

    assert not cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, root=tmp_path).exists()
    snapshot = load_achievement_pulse_cache_snapshot(profile_key=profile_key, root=tmp_path, now=10_100)
    assert snapshot.resolved.ok
    assert snapshot.resolved.appid == 222
    assert snapshot.resolved.latest_achievement == "Newest Game Award"
    assert snapshot.resolved.previous_game_title == "Older Game"
    assert load_recent_game_titles_from_cache(profile_key=profile_key, root=tmp_path) == (
        "Newest Game", "Older Game"
    )
    assert load_achievement_pulse_cache_snapshot(
        profile_key=profile_key, root=tmp_path,
        selection=AchievementPulseSelection(mode="recent_2"),
    ).resolved.appid == 111
    # Cache-only loading is read-only; a refresh subsequently persists the index.
    assert not cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, root=tmp_path).exists()


def test_empty_live_response_refreshes_bounded_cached_history_and_persists_it(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="fake_key", profile_identifier="76561198009000110")
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    for appid, name, unlock in ((111, "Older Game", 10), (222, "Recent Game", 20)):
        _write(tmp_path, profile_key, achievement_cache_key_for_app(appid), SteamSourceId.PLAYER_ACHIEVEMENTS,
               _achievement(name, unlock), 1_000)
    calls = []

    def opener(request, _timeout):
        url = request.full_url
        calls.append(url)
        if "GetRecentlyPlayedGames" in url:
            return _Response({"response": {}})
        if "GetPlayerAchievements" in url:
            return _Response(_achievement("Older Game", 30) if "appid=111" in url else _achievement("Recent Game", 20))
        if "GetSchemaForGame" in url:
            return _Response(_schema("Older Game"))
        raise AssertionError(url)

    outcome = refresh_achievement_pulse_cache(
        credential=credential, root=tmp_path, opener=opener, now=10_000, force=True
    )
    assert outcome.resolved.ok
    assert outcome.resolved.appid == 111
    assert outcome.resolved.latest_achievement == "Older Game Award"
    assert sum("GetRecentlyPlayedGames" in url for url in calls) == 1
    assert sum("GetPlayerAchievements" in url for url in calls) == 2
    assert sum("GetSchemaForGame" in url for url in calls) == 1
    history = read_cache_record(cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, root=tmp_path))
    assert history.ok and len(history.payload["games"]) == 2
    assert load_achievement_pulse_cache_snapshot(profile_key=profile_key, root=tmp_path).resolved.appid == 111


def test_live_recent_does_not_prune_archived_candidates_and_new_unlock_wins(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="fake_key", profile_identifier="76561198009000111")
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    for appid in range(100, 110):
        _write(tmp_path, profile_key, achievement_cache_key_for_app(appid), SteamSourceId.PLAYER_ACHIEVEMENTS,
               _achievement(f"Archived {appid}", appid), 1_000)
    calls = []

    def opener(request, _timeout):
        url = request.full_url
        calls.append(url)
        if "GetRecentlyPlayedGames" in url:
            return _Response({"response": {"games": [{"appid": 900, "name": "Brand New Game"}]}})
        if "GetPlayerAchievements" in url:
            assert "appid=900" in url
            return _Response(_achievement("Brand New Game", 10_000))
        if "GetSchemaForGame" in url:
            assert "appid=900" in url
            return _Response(_schema("Brand New Game"))
        raise AssertionError(url)

    outcome = refresh_achievement_pulse_cache(
        credential=credential, root=tmp_path, opener=opener, now=10_000, force=True
    )
    assert outcome.resolved.appid == 900
    assert outcome.resolved.previous_game_title == "Archived 109"
    assert sum("GetPlayerAchievements" in url for url in calls) == 1
    assert len(read_cache_record(cache_path_for_profile_key(profile_key, HISTORY_CACHE_KEY, root=tmp_path)).payload["games"]) == 11

    _write(tmp_path, profile_key, RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED,
           {"response": {"games": []}}, 11_000)
    reread = load_achievement_pulse_cache_snapshot(profile_key=profile_key, root=tmp_path)
    assert reread.resolved.appid == 900
    assert load_achievement_pulse_cache_snapshot(
        profile_key=profile_key, root=tmp_path,
        selection=AchievementPulseSelection(mode="recent_2")
    ).resolved.appid == 109


def test_successful_http_envelope_with_steam_achievement_failure_never_replaces_last_good(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="fake_key", profile_identifier="76561198009000112")
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    _write(tmp_path, profile_key, RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED,
           {"response": {"games": [{"appid": 111, "name": "Last Good"}]}}, 9_000)
    _write(tmp_path, profile_key, achievement_cache_key_for_app(111), SteamSourceId.PLAYER_ACHIEVEMENTS,
           _achievement("Last Good", 20), 9_000)
    _write(tmp_path, profile_key, achievement_schema_cache_key_for_app(111), SteamSourceId.ACHIEVEMENT_SCHEMA,
           _schema("Last Good"), 9_000)

    def opener(request, _timeout):
        url = request.full_url
        if "GetRecentlyPlayedGames" in url:
            return _Response({"response": {"games": [{"appid": 111, "name": "Last Good"}]}})
        if "GetPlayerAchievements" in url:
            return _Response({"playerstats": {"success": False, "error": "no stats"}})
        if "GetSchemaForGame" in url:
            return _Response(_schema("Last Good"))
        raise AssertionError(url)

    outcome = refresh_achievement_pulse_cache(
        credential=credential, root=tmp_path, opener=opener, now=10_000, force=True
    )
    assert outcome.resolved.ok
    assert outcome.resolved.appid == 111
    assert outcome.resolved.latest_achievement == "Last Good Award"
    saved = read_cache_record(cache_path_for_profile_key(
        profile_key, achievement_cache_key_for_app(111), root=tmp_path
    ))
    assert saved.ok and saved.fetched_at == 9_000
    assert saved.payload["playerstats"]["achievements"][0]["unlocktime"] == 20


def test_index_reconciles_new_unlock_cached_by_another_steam_card(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="fake_key", profile_identifier="76561198009000113")
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    _write(tmp_path, profile_key, RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED,
           {"response": {"games": []}}, 10_000)
    for appid, timestamp in ((111, 100), (222, 200)):
        _write(tmp_path, profile_key, achievement_cache_key_for_app(appid), SteamSourceId.PLAYER_ACHIEVEMENTS,
               _achievement(f"Game {appid}", timestamp), 9_000)

    # Build a durable catalog from the original per-app files.  This also
    # exercises the no-network initial migration path.
    from core.steam.achievement_pulse_history import persist_achievement_history
    recent = read_cache_record(cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, root=tmp_path))
    persist_achievement_history(
        profile_key=profile_key, recent_result=recent, observed_appids=(), root=tmp_path, now=10_000
    )
    assert load_achievement_pulse_cache_snapshot(profile_key=profile_key, root=tmp_path).resolved.appid == 222

    # The shared cache file was updated without invoking Achievement Pulse.
    _write(tmp_path, profile_key, achievement_cache_key_for_app(111), SteamSourceId.PLAYER_ACHIEVEMENTS,
           _achievement("Game 111", 300), 10_001)
    assert load_achievement_pulse_cache_snapshot(profile_key=profile_key, root=tmp_path).resolved.appid == 111


def test_malformed_successful_recent_transport_does_not_overwrite_last_good(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="fake_key", profile_identifier="76561198009000114")
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    _write(tmp_path, profile_key, RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED,
           {"response": {"games": [{"appid": 111, "name": "Retained Game"}]}}, 9_000)
    _write(tmp_path, profile_key, achievement_cache_key_for_app(111), SteamSourceId.PLAYER_ACHIEVEMENTS,
           _achievement("Retained Game", 100), 9_000)
    _write(tmp_path, profile_key, achievement_schema_cache_key_for_app(111), SteamSourceId.ACHIEVEMENT_SCHEMA,
           _schema("Retained Game"), 9_000)

    def opener(request, _timeout):
        url = request.full_url
        if "GetRecentlyPlayedGames" in url:
            return _Response({"error": "temporary provider fault"})
        if "GetPlayerAchievements" in url:
            return _Response(_achievement("Retained Game", 101))
        if "GetSchemaForGame" in url:
            return _Response(_schema("Retained Game"))
        raise AssertionError(url)

    outcome = refresh_achievement_pulse_cache(
        credential=credential, root=tmp_path, opener=opener, now=10_000, force=True
    )
    assert outcome.resolved.appid == 111
    recent = read_cache_record(cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, root=tmp_path))
    assert recent.ok and recent.fetched_at == 9_000
    assert recent.payload["response"]["games"][0]["name"] == "Retained Game"
