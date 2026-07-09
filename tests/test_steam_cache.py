from __future__ import annotations

import json
from pathlib import Path

from core.steam.cache import (
    STEAM_CACHE_SCHEMA_VERSION,
    SteamCacheRecord,
    cache_path_for,
    read_cache_record,
    write_cache_record,
    write_success_result,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId


def test_cache_path_uses_opaque_profile_key(tmp_path: Path) -> None:
    path = cache_path_for("76561197960265728", "Achievement Pulse/Recent", root=tmp_path)

    assert "76561197960265728" not in str(path)
    assert path.name == "achievement_pulse_recent.json"


def test_cache_record_roundtrip_is_versioned_and_source_provenanced(tmp_path: Path) -> None:
    path = tmp_path / "recent.json"
    record = SteamCacheRecord(
        cache_key="recent",
        source_id=SteamSourceId.RECENTLY_PLAYED,
        payload={"response": {"games": []}},
        fetched_at=1234.0,
        attempted_sources=(SteamSourceId.RECENTLY_PLAYED,),
    )

    write_cache_record(record, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    result = read_cache_record(path)

    assert raw["schema_version"] == STEAM_CACHE_SCHEMA_VERSION
    assert raw["source_id"] == SteamSourceId.RECENTLY_PLAYED.value
    assert result.status == SteamResultStatus.SUCCESS
    assert result.from_cache is True
    assert result.source_id == SteamSourceId.RECENTLY_PLAYED
    assert result.payload == {"response": {"games": []}}


def test_failed_result_does_not_freshen_or_overwrite_cache(tmp_path: Path) -> None:
    path = tmp_path / "achievements.json"
    existing = SteamCacheRecord(
        cache_key="achievements",
        source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
        payload={"playerstats": {"achievements": [{"name": "A"}]}},
        fetched_at=111.0,
    )
    write_cache_record(existing, path)
    before = path.read_text(encoding="utf-8")

    wrote = write_success_result(
        path=path,
        cache_key="achievements",
        result=SteamResult(
            status=SteamResultStatus.PRIVATE,
            source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
            message="private",
        ),
    )

    assert wrote is None
    assert path.read_text(encoding="utf-8") == before


def test_success_result_writes_cache_with_attempted_sources(tmp_path: Path) -> None:
    path = tmp_path / "news.json"
    result = SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.APP_NEWS,
        payload={"appnews": {"newsitems": []}},
        attempted_sources=(SteamSourceId.APP_NEWS,),
    )

    write_success_result(path=path, cache_key="news", result=result, fetched_at=222.0)
    read = read_cache_record(path)

    assert read.status == SteamResultStatus.SUCCESS
    assert read.attempted_sources == (SteamSourceId.APP_NEWS,)
    assert read.payload == {"appnews": {"newsitems": []}}


def test_corrupt_cache_is_moved_as_loud_non_authoritative_failure(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    result = read_cache_record(path)

    assert result.status == SteamResultStatus.CACHE_CORRUPT
    assert not path.exists()
    assert (tmp_path / "broken.json.corrupt").exists()
