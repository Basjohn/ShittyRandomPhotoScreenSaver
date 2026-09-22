"""Fixture-only three-pillar followed-news metadata and artwork regression gates."""
from __future__ import annotations

import json
from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image

from core.steam.assets import cache_asset_from_bytes, steam_app_artwork_url
from core.steam.followed_app_metadata import (
    FAILED_LOOKUP_RETRY_SECONDS, FollowedAppMetadata, parse_store_metadata,
    valid_store_artwork_url,
)
from core.steam.followed_artwork_readiness import valid_local_artwork
from core.steam.games_followed_projection import project_followed_news
from core.steam.games_followed_source import FollowedNewsSnapshot, FollowedNewsSource, FollowedNewsStory
from core.steam.credentials import derive_profile_cache_key

PROFILE_KEY = derive_profile_cache_key("76561197960265728")


def _stories(*ids: int) -> FollowedNewsSnapshot:
    return FollowedNewsSnapshot(
        "available", tuple(FollowedNewsStory(
            appid, str(99000 + index), "A headline with no game name", 1700000000 + index,
            "News", True,
        ) for index, appid in enumerate(ids)), followed_count=len(ids), checked_count=len(ids),
    )


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 32), (15, 50, 60)).save(output, "PNG")
    return output.getvalue()


def test_store_metadata_accepts_only_exact_appid_and_verified_artwork_host():
    url = "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/101/header.jpg"
    valid = {"101": {"success": True, "data": {"name": "  The Named Game  ", "header_image": url}}}
    assert parse_store_metadata(valid, 101) == ("The Named Game", url)
    assert parse_store_metadata(valid, 102) == ("", "")
    assert parse_store_metadata({"101": {"success": False, "data": {"name": "False"}}}, 101) == ("", "")
    assert valid_store_artwork_url("https://evil.example/steam/apps/101/header.jpg", 101) == ""
    assert valid_store_artwork_url(url.replace("/101/", "/102/"), 101) == ""
    assert valid_store_artwork_url("https://shared.akamai.steamstatic.com:bad/steam/apps/101/header.jpg", 101) == ""


def test_metadata_hydrates_unknown_not_owned_once_and_survives_restart_without_network(tmp_path):
    calls: list[int] = []
    def lookup(appid: int) -> tuple[str, str]:
        calls.append(appid)
        return f"Known game {appid}", ""
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                metadata_lookup=lookup)
    snap = _stories(101, 101, 102)
    # A cache-only admission never issues a Store request, even with an injected fixture.
    pending = source._decorate(snap, allow_network=False)
    assert calls == []
    assert [row.game_label for row in project_followed_news(pending).rows] == [
        "Steam App 101", "Steam App 101", "Steam App 102",
    ]
    resolved = source._decorate(snap, allow_network=False, allow_metadata_network=True)
    assert calls == [101, 102]
    assert [row.game_label for row in project_followed_news(resolved).rows] == [
        "Known game 101", "Known game 101", "Known game 102",
    ]
    source._decorate(snap, allow_network=False, allow_metadata_network=True)
    assert calls == [101, 102]
    reopened = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                  metadata_lookup=lambda _: (_ for _ in ()).throw(AssertionError("no Store lookup")))
    offline = reopened._decorate(snap, allow_network=False)
    assert [story.game_name for story in offline.stories] == [story.game_name for story in resolved.stories]
    saved = (tmp_path / "games_followed_app_metadata.json").read_text("utf-8")
    assert "76561197960265728" not in saved


def test_metadata_failure_is_bounded_and_does_not_destroy_last_good(tmp_path):
    metadata = FollowedAppMetadata(profile_key=PROFILE_KEY, root=tmp_path)
    attempts: list[int] = []
    def missing(appid: int) -> tuple[str, str]:
        attempts.append(appid)
        return "", ""
    now = 1_700_000_000.0
    assert metadata.hydrate(101, lookup=missing, now=now)
    assert not metadata.hydrate(101, lookup=missing, now=now + 3600)
    assert attempts == [101]
    metadata.persist()
    reopened = FollowedAppMetadata(profile_key=PROFILE_KEY, root=tmp_path)
    assert not reopened.hydrate(101, lookup=missing, now=now + 3600)
    assert reopened.hydrate(101, lookup=lambda _: ("Recovered title", ""),
                            now=now + FAILED_LOOKUP_RETRY_SECONDS + 1)
    reopened.persist()
    established = FollowedAppMetadata(profile_key=PROFILE_KEY, root=tmp_path)
    assert established.names[101] == "Recovered title"
    assert not established.hydrate(101, lookup=missing, now=now + 3 * FAILED_LOOKUP_RETRY_SECONDS)


def test_mixed_cached_artwork_keeps_valid_game_art_and_stable_row_identity(tmp_path):
    cache_dir = tmp_path / "assets"
    art = cache_asset_from_bytes(cache_dir=cache_dir,
                                 url=steam_app_artwork_url(101, "wide"), data=_png())
    assert hasattr(art, "path")
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path)
    snapshot = _stories(101, 102, 101)
    decorated = source._decorate(snapshot, allow_network=False)
    assert decorated.artwork_paths == (str(art.path), "", str(art.path))
    shown = project_followed_news(decorated)
    assert [bool(row.local_artwork_source) for row in shown.rows] == [True, False, True]
    assert [row.title for row in shown.rows] == [story.title for story in snapshot.stories]
    assert all(row.game_label for row in shown.rows)
    # A malformed cached file is never advertised as a ready Qt image.
    art.path.write_bytes(b"not an image")
    assert valid_local_artwork(art.path) is None
    corrupted = source._decorate(snapshot, allow_network=False)
    assert corrupted.artwork_paths == ("", "", "")
    assert len(project_followed_news(corrupted).rows) == 3


def test_source_name_projection_survives_stale_cache_and_article_reorder(tmp_path):
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                metadata_lookup=lambda appid: (f"Game {appid}", ""))
    initial = source._decorate(_stories(101, 102), allow_network=False, allow_metadata_network=True)
    stale = source._decorate(replace(initial, status="stale_cache"), allow_network=False)
    reordered = source._decorate(_stories(102, 101), allow_network=False)
    assert [story.game_name for story in stale.stories] == ["Game 101", "Game 102"]
    assert [story.game_name for story in reordered.stories] == ["Game 102", "Game 101"]
    assert [row.title for row in project_followed_news(reordered).rows] == [
        "A headline with no game name", "A headline with no game name",
    ]


def test_refresh_uses_one_bounded_name_lookup_per_appid_and_stale_result_keeps_art(tmp_path, monkeypatch):
    """Real refresh orchestration without live Steam, Qt or network."""
    from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
    import core.steam.games_followed_source as source_module
    import core.steam.assets as assets

    ids = (101, 102)
    monkeypatch.setattr(source_module, "fetch_followed_appids_for_news_probe",
                        lambda *_args, **_kwargs: ("confirmed_nonempty", ids))
    def fixture_news(endpoint, *, opener=None):
        appid = int(endpoint.params["appid"]) if isinstance(endpoint.params, dict) else 0
        # Some endpoint implementations use tuple-of-pairs, so use URL independent
        # fixture routing through the public app-id attribute if available.
        return SteamResult(SteamResultStatus.SUCCESS, SteamSourceId.APP_NEWS, {
            "appnews": {"appid": appid, "newsitems": [{
                "gid": str(45000 + appid), "title": "Update with no game title",
                "date": 1_700_000_000 + appid, "feedlabel": "Updates",
            }]},
        })
    monkeypatch.setattr(source_module, "fetch_json", fixture_news)
    calls: list[int] = []
    def lookup(appid):
        calls.append(appid)
        return f"Followed game {appid}", ""
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                metadata_lookup=lookup)
    fresh = source.refresh("76561197960265728", opener=lambda *_: None)
    assert fresh.status == "available" and calls == [102, 101]
    assert all(story.game_name == f"Followed game {story.appid}" for story in fresh.stories)
    assert [story.appid for story in fresh.stories] == [102, 101]
    # The next source job must not rename, relookup or rewire article identities.
    next_batch = source.refresh("76561197960265728", opener=lambda *_: None)
    assert calls == [102, 101]
    assert [story.game_name for story in next_batch.stories] == [story.game_name for story in fresh.stories]
    source.retire()
    reopened = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                  metadata_lookup=lambda _: (_ for _ in ()).throw(AssertionError("network in cache")))
    assert reopened.cached().stories == next_batch.stories


def test_emergency_fallback_is_never_promoted_to_canonical_cache(tmp_path):
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                metadata_lookup=lambda appid: (f"Verified game {appid}", ""))
    transient = source._decorate(_stories(101), allow_network=False)
    assert transient.stories[0].game_name == "Steam App 101"
    verified = source._decorate(transient, allow_network=False, allow_metadata_network=True)
    assert verified.stories[0].game_name == "Verified game 101"
    reopened = FollowedAppMetadata(profile_key=PROFILE_KEY, root=tmp_path)
    assert reopened.names[101] == "Verified game 101"


def test_failed_metadata_disk_write_recovers_on_next_source_admission(tmp_path, monkeypatch):
    source = FollowedNewsSource(profile_key=PROFILE_KEY, cache_root=tmp_path,
                                metadata_lookup=lambda appid: (f"Last-good {appid}", ""))
    from core.steam.followed_app_metadata import FollowedAppMetadata
    write = FollowedAppMetadata.persist
    failed = []
    def fail_once(instance):
        if not failed:
            failed.append(True)
            raise OSError("disk temporarily unavailable")
        return write(instance)
    monkeypatch.setattr(FollowedAppMetadata, "persist", fail_once)
    first = source._decorate(_stories(101), allow_network=False, allow_metadata_network=True)
    assert first.stories[0].game_name == "Last-good 101"
    assert source._metadata_dirty and not (tmp_path / "games_followed_app_metadata.json").exists()
    next_result = source._decorate(_stories(101), allow_network=False)
    assert next_result.stories[0].game_name == "Last-good 101"
    assert not source._metadata_dirty
    assert FollowedAppMetadata(profile_key=PROFILE_KEY, root=tmp_path).names[101] == "Last-good 101"
