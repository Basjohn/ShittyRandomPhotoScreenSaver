"""Image-macro and cache-lifetime fixtures for Steam Games You Follow.

No Steam or Qt process/network is needed. Native QML component acceptance lives
in the separate Qt gate, because source tests cannot prove visual correctness.
"""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image

from core.steam.assets import cache_asset_from_bytes, prune_asset_cache
from core.steam.credentials import derive_profile_cache_key
from core.steam.followed_news_inline_artwork import (
    inline_image_url, news_inline_refs, prune_inline_image_cache, validated_inline_ref,
)
from core.steam.games_followed_projection import project_followed_news
from core.steam.games_followed_source import (
    FollowedNewsSnapshot, FollowedNewsSource, FollowedNewsStory, _plain_preview,
    _snapshot_from_cache, normalize_app_news,
)
from core.steam.cache import SteamCacheRecord, write_cache_record
from core.steam.models import SteamSourceId

_PROFILE = derive_profile_cache_key("76561197960265728")
_REF1 = "43587230/92588faa5a24cef677abae2b14efb2249cb7d8a8.png"
_REF2 = "43587230/3006a56a6d49d1ca6191f7adb37ac0d94fb5b63e.png"
_REF3 = "43587230/941fe944dbd248efa81852786d20de5bb4ae6132.png"
_CONTENT = (f"<p>{{STEAM_CLAN_IMAGE}}/{_REF1} /{_REF2} /{_REF3} "
            "[b]New identities incoming[/b]</p>")


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (24, 24), (30, 80, 120)).save(output, format="PNG")
    return output.getvalue()


def _snapshot(appid: int = 101) -> FollowedNewsSnapshot:
    return FollowedNewsSnapshot("available", (
        FollowedNewsStory(appid, "1234567", "Announcement", 1700000000,
                            "Announcements", True, _plain_preview(_CONTENT),
                            "Known game", news_inline_refs(_CONTENT)),
    ), followed_count=1, checked_count=1)


def test_source_extracts_up_to_three_safe_images_and_never_displays_raw_image_paths():
    assert news_inline_refs(_CONTENT) == (_REF1, _REF2, _REF3)
    assert _plain_preview(_CONTENT) == "New identities incoming"
    assert news_inline_refs("ordinary update, no image") == ()
    assert news_inline_refs("https://evil.example/images/" + _REF1) == ()
    assert validated_inline_ref("../../private.png") == ""
    assert validated_inline_ref("43587230/abcdefff.png?token=secret") == ""
    assert inline_image_url("../../private.png") == ""
    assert inline_image_url(_REF1) == "https://clan.akamai.steamstatic.com/images/" + _REF1
    payload = {"appnews": {"appid": 101, "newsitems": [{
        "gid": "1234567", "title": "New identity preview", "date": 1700000000,
        "feedlabel": "Announcements", "contents": _CONTENT,
    }]}}
    story, = normalize_app_news(payload, 101)
    assert story.inline_image_refs == (_REF1, _REF2, _REF3)
    assert story.preview == "New identities incoming"
    assert "steamstatic.com" not in str(vars(story))


def test_inline_images_are_locally_warmed_once_and_survive_restart(tmp_path, monkeypatch):
    import core.steam.assets as assets

    urls: list[str] = []
    def local_fixture_fetch(url: str, **_kwargs) -> bytes:
        urls.append(url)
        assert url.startswith("https://")
        assert "steamstatic.com" in url
        return _png()
    monkeypatch.setattr(assets, "_default_fetch_asset", local_fixture_fetch)
    source = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    first = source._decorate(_snapshot(), allow_network=True)
    assert first.stories[0].game_name == "Known game"
    assert len(first.inline_image_paths[0]) == 3
    assert all(Path(path).exists() for path in first.inline_image_paths[0])
    assert [path.startswith("https://clan.akamai.steamstatic.com/images/") for path in urls].count(True) == 3
    shown = project_followed_news(first)
    assert shown.rows[0].local_inline_artwork_sources == tuple(
        Path(path).as_uri() for path in first.inline_image_paths[0])
    assert "http" not in shown.rows[0].preview
    assert all("http" not in ref for ref in first.stories[0].inline_image_refs)
    source.retire()
    restored = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path,
                                  metadata_lookup=lambda appid: (_ for _ in ()).throw(AssertionError("network")))
    offline = restored._decorate(_snapshot(), allow_network=False)
    assert offline.inline_image_paths == first.inline_image_paths
    assert offline.artwork_paths == first.artwork_paths


def test_missing_or_corrupt_inline_art_is_optional_and_bounded(tmp_path, monkeypatch):
    import core.steam.assets as assets
    calls: list[str] = []
    def fail_inline(url: str, **_kwargs) -> bytes:
        calls.append(url)
        if "clan." in url:
            raise OSError("temporary outage")
        return _png()
    monkeypatch.setattr(assets, "_default_fetch_asset", fail_inline)
    source = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    original = _snapshot()
    failed = source._decorate(original, allow_network=True)
    assert failed.inline_image_paths == ((),)
    assert project_followed_news(failed).rows[0].title == "Announcement"
    attempts = len([url for url in calls if "clan." in url])
    assert attempts == 3
    source._decorate(original, allow_network=True)
    assert len([url for url in calls if "clan." in url]) == attempts
    source.retire()
    restarted = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    restarted._decorate(original, allow_network=True)
    assert len([url for url in calls if "clan." in url]) == attempts


def test_cache_validation_rejects_bogus_inline_ref_without_erasing_valid_cache(tmp_path):
    source = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    record = SteamCacheRecord(
        cache_key="games_you_follow_news", source_id=SteamSourceId.GAMES_FOLLOWED,
        payload={"schema": 1, "followed_count": 1, "checked_count": 1,
                 "covered_count": 1, "maintenance_pending": False, "window_offset": 0,
                 "stories": [{"appid": 101, "gid": "1234567", "title": "Announcement",
                              "published_at": 1700000000, "feed_name": "Announcements",
                              "preview": "Text", "game_name": "Known game", "action_available": True,
                              "inline_image_refs": [_REF1]}]},
        fetched_at=1700000000.0,
    )
    from time import time
    record = replace(record, fetched_at=time())
    write_cache_record(record, source._path)
    assert source.cached().stories[0].inline_image_refs == (_REF1,)
    bad = replace(record, payload={**record.payload, "stories": [
        {**record.payload["stories"][0], "inline_image_refs": ["../../private.jpg"]}]})
    write_cache_record(bad, source._path)
    assert _snapshot_from_cache(source._path) is None



def test_old_persisted_preview_recovers_inline_images_without_waiting_for_the_games_next_news_turn(tmp_path, monkeypatch):
    """Physical regression: old rows kept /group/hash.png but no inline refs.

    The rolling four-AppID maintenance can retain that row for many sessions;
    fixing fresh Steam normalization alone leaves visible old rows broken.
    """
    import core.steam.assets as assets
    from core.steam.games_followed_source import _cached_news_buckets

    old_preview = f"/{_REF1} /{_REF2} /{_REF3} Patch information"
    row = {"appid": 101, "gid": "1234567", "title": "New Identity Preview",
           "published_at": 1700000000, "feed_name": "Community Announcements",
           "preview": old_preview, "game_name": "Limbus Company", "action_available": True}
    source = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    write_cache_record(SteamCacheRecord(
        cache_key="games_you_follow_news", source_id=SteamSourceId.GAMES_FOLLOWED,
        payload={"schema": 1, "followed_count": 1, "checked_count": 1,
                 "covered_count": 1, "window_offset": 0, "maintenance_pending": False,
                 "stories": [row], "per_game_stories": {"101": [row]}},
        fetched_at=__import__("time").time(),
    ), source._path)

    # Both read paths must repair together. The per-game bucket is what gets
    # re-ranked and written at the next four-app session, not just top rows.
    cached = source.cached()
    assert cached is not None
    story, = cached.stories
    assert story.preview == "Patch information"
    assert story.inline_image_refs == (_REF1, _REF2, _REF3)
    retained, = _cached_news_buckets(source._path, (101,))[101]
    assert retained.preview == story.preview
    assert retained.inline_image_refs == story.inline_image_refs

    network: list[str] = []
    def fake_fetch(url: str, **_kwargs) -> bytes:
        network.append(url)
        return _png()
    monkeypatch.setattr(assets, "_default_fetch_asset", fake_fetch)
    hydrated = source._decorate(cached, allow_network=True)
    assert len(hydrated.inline_image_paths[0]) == 3
    assert len([url for url in network if "clan." in url]) == 3
    assert project_followed_news(hydrated).rows[0].preview == "Patch information"
    source.retire()
    offline = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    restored = offline.cached()
    assert restored is not None and restored.stories[0].inline_image_refs == (_REF1, _REF2, _REF3)
    assert len(restored.inline_image_paths[0]) == 3
    assert [url for url in network if "clan." in url] == [inline_image_url(_REF1), inline_image_url(_REF2), inline_image_url(_REF3)]


def test_cache_repair_preserves_known_refs_and_removes_legacy_paths_from_preview(tmp_path):
    source = FollowedNewsSource(profile_key=_PROFILE, cache_root=tmp_path)
    row = {"appid": 101, "gid": "1234567", "title": "Announcement",
           "published_at": 1700000000, "feed_name": "Announcements",
           "preview": f"/{_REF1} /{_REF2} /{_REF3} Extra info", "game_name": "Known game",
           "inline_image_refs": [_REF1], "action_available": True}
    write_cache_record(SteamCacheRecord(
        cache_key="games_you_follow_news", source_id=SteamSourceId.GAMES_FOLLOWED,
        payload={"schema": 1, "followed_count": 1, "checked_count": 1,
                 "covered_count": 1, "window_offset": 0, "maintenance_pending": False,
                 "stories": [row]}, fetched_at=__import__("time").time(),
    ), source._path)
    story, = source.cached().stories
    assert story.inline_image_refs == (_REF1, _REF2, _REF3)
    assert story.preview == "Extra info"

def test_preview_cleanup_strips_partial_or_extra_image_garbage_beyond_visible_limit():
    from core.steam.games_followed_source import _plain_preview

    text = f"/{_REF1} /{_REF2} /43587230/941fe944dbd248efa81852786d20de5... Story details"
    assert _plain_preview(text) == "Story details"


def test_worker_pruning_respects_byte_budget_and_current_publications(tmp_path):
    url = "https://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg"
    asset = cache_asset_from_bytes(cache_dir=tmp_path, url=url, data=_png())
    assert hasattr(asset, "path")
    (tmp_path / ("a" * 24 + ".png")).write_bytes(b"A" * 50)
    (tmp_path / ("b" * 24 + ".png")).write_bytes(b"B" * 50)
    removed = prune_asset_cache(tmp_path, max_files=3, max_bytes=90,
                                protected=frozenset((asset.path,)))
    assert removed >= 1 and asset.path.exists()
    # News inline artwork has its own smaller directory and does not prune
    # neighboring game artwork or an image currently published in this source.
    inline = tmp_path / "news_inline"
    inline.mkdir()
    old = inline / "old.png"
    retained = inline / "retained.png"
    old.write_bytes(b"a" * 70)
    retained.write_bytes(b"b" * 70)
    assert prune_inline_image_cache(inline, protected=frozenset((retained,)),
                                   max_files=1, max_bytes=80) == 1
    assert retained.exists() and asset.path.exists()


def test_asset_write_enforces_rotation_without_touching_unknown_files(tmp_path, monkeypatch):
    import core.steam.assets as assets

    # Inject a tiny budget at the ordinary on-write prune seam rather than
    # replacing a Python default argument after it was bound at definition.
    real_prune = assets.prune_asset_cache
    monkeypatch.setattr(assets, "prune_asset_cache", lambda directory, *, protected:
                        real_prune(directory, max_files=3, max_bytes=4096, protected=protected))
    unrelated = tmp_path / "user_notes.json"
    unrelated.write_text("keep", encoding="utf-8")
    last = None
    for appid in range(100, 106):
        last = assets.cache_asset_from_bytes(
            cache_dir=tmp_path,
            url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            data=_png(),
        )
        assert hasattr(last, "path")
    assert last.path.is_file() and unrelated.read_text(encoding="utf-8") == "keep"
    assert len(tuple(tmp_path.glob("[0-9a-f]*.png"))) == 3
