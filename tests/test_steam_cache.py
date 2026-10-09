from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import pytest

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


def test_concurrent_cache_writers_use_distinct_owned_temp_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two overlapping GYF refreshes cannot trample the same fixed .json.tmp."""
    path = tmp_path / "games_you_follow_news.json"
    barrier = threading.Barrier(2)
    owned_paths: list[Path] = []
    original_open = Path.open

    def overlap_temp_creates(source: Path, mode: str = "r", *args, **kwargs):
        stream = original_open(source, mode, *args, **kwargs)
        if mode == "x" and source.name.startswith(".games_you_follow_news.json."):
            owned_paths.append(source)
            # Both temp files must exist concurrently before either may
            # publish. A fixed-name writer cannot satisfy this contract.
            barrier.wait(timeout=5)
        return stream

    monkeypatch.setattr(Path, "open", overlap_temp_creates)

    def write(index: int) -> None:
        record = SteamCacheRecord(
            cache_key="games_you_follow_news",
            source_id=SteamSourceId.GAMES_FOLLOWED,
            payload={"writer": index},
            fetched_at=float(index),
        )
        # Exercise the real file writer concurrently; no alternate cache path.
        write_cache_record(record, path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(write, index) for index in (1, 2)]
        for future in futures:
            future.result(timeout=10)
    result = read_cache_record(path)
    assert result.ok
    assert result.payload in ({"writer": 1}, {"writer": 2})
    assert len(owned_paths) == 2 and owned_paths[0] != owned_paths[1]
    assert list(tmp_path.glob("*.tmp")) == []



def test_same_cache_destination_publishes_sequentially_without_serializing_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reproduce Windows WinError 5 if two writers replace the same target at once.

    Stage both unique temp files concurrently, hold the first publish open, and
    verify the second writer waits to publish rather than entering replace().
    """
    path = tmp_path / "games_you_follow_news.json"
    first_inside_replace = threading.Event()
    allow_first_replace_to_finish = threading.Event()
    second_temp_opened = threading.Event()
    replacement_guard = threading.Lock()
    active_replacements = 0
    replacement_count = 0
    original_open = Path.open
    original_replace = Path.replace

    def capture_staging(source: Path, mode: str = "r", *args, **kwargs):
        stream = original_open(source, mode, *args, **kwargs)
        if mode == "x" and source.name.startswith(".games_you_follow_news.json."):
            if first_inside_replace.is_set():
                second_temp_opened.set()
        return stream

    def windows_like_replace(source: Path, target: Path) -> Path:
        nonlocal active_replacements, replacement_count
        if target != path:
            return original_replace(source, target)
        with replacement_guard:
            active_replacements += 1
            replacement_count += 1
            active = active_replacements
            first = replacement_count == 1
        try:
            if active > 1:
                raise PermissionError("synthetic Windows WinError 5: overlapping cache publish")
            if first:
                first_inside_replace.set()
                assert allow_first_replace_to_finish.wait(timeout=5)
            return original_replace(source, target)
        finally:
            with replacement_guard:
                active_replacements -= 1

    monkeypatch.setattr(Path, "open", capture_staging)
    monkeypatch.setattr(Path, "replace", windows_like_replace)

    def write(index: int) -> None:
        write_cache_record(SteamCacheRecord(
            "games_you_follow_news", SteamSourceId.GAMES_FOLLOWED,
            {"writer": index}, float(index),
        ), path)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(write, 1)
            assert first_inside_replace.wait(timeout=5)
            second = executor.submit(write, 2)
            assert second_temp_opened.wait(timeout=5)
            # The first rename is deliberately paused while the second writer
            # has finished staging its own file.  Same-target replacement must
            # not have been entered by the second writer.
            with replacement_guard:
                assert active_replacements == 1
                assert replacement_count == 1
            allow_first_replace_to_finish.set()
            first.result(timeout=5)
            second.result(timeout=5)
    finally:
        allow_first_replace_to_finish.set()

    assert replacement_count == 2
    assert read_cache_record(path).payload == {"writer": 2}
    assert list(tmp_path.glob("*.tmp")) == []


def test_distinct_cache_targets_do_not_share_publication_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unrelated Steam cache must publish while another target is stalled."""
    slow = tmp_path / "games_you_follow_news.json"
    fast = tmp_path / "achievement_pulse.json"
    slow_entered = threading.Event()
    release_slow = threading.Event()
    original_replace = Path.replace

    def delayed_replace(source: Path, target: Path) -> Path:
        if target == slow:
            slow_entered.set()
            assert release_slow.wait(timeout=5)
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", delayed_replace)

    def record(key: str) -> SteamCacheRecord:
        return SteamCacheRecord(key, SteamSourceId.GAMES_FOLLOWED, {"key": key}, 1.0)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(write_cache_record, record("games_you_follow_news"), slow)
            assert slow_entered.wait(timeout=5)
            second = executor.submit(write_cache_record, record("achievement_pulse"), fast)
            assert second.result(timeout=3) == fast
            release_slow.set()
            assert first.result(timeout=5) == slow
    finally:
        release_slow.set()
    assert read_cache_record(fast).ok and read_cache_record(slow).ok



def test_publication_locks_are_not_retained_after_writers_finish(tmp_path: Path) -> None:
    """Publishing many per-profile caches must not grow permanent lock state."""
    import gc
    import weakref
    from core.steam.cache import _cache_publish_lock_for

    path = tmp_path / "ephemeral.json"
    owner = _cache_publish_lock_for(path)
    same_owner = _cache_publish_lock_for(path)
    other_owner = _cache_publish_lock_for(tmp_path / "different.json")
    assert owner is same_owner
    assert owner is not other_owner
    reference = weakref.ref(owner)
    del owner, same_owner
    gc.collect()
    assert reference() is None


def test_failed_cache_replacement_retains_last_good_and_cleans_owned_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "games_you_follow_news.json"
    prior = SteamCacheRecord("games_you_follow_news", SteamSourceId.GAMES_FOLLOWED,
                             {"writer": "old"}, 1.0)
    write_cache_record(prior, path)
    prior_bytes = path.read_bytes()
    original_replace = Path.replace

    def block_replace(source: Path, target: Path) -> Path:
        if target == path:
            raise PermissionError("simulated WinError 32 during publish")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", block_replace)
    recent = SteamCacheRecord("games_you_follow_news", SteamSourceId.GAMES_FOLLOWED,
                              {"writer": "new"}, 2.0)
    with pytest.raises(PermissionError, match="WinError 32"):
        write_cache_record(recent, path)
    assert path.read_bytes() == prior_bytes
    assert list(tmp_path.glob("*.tmp")) == []


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
