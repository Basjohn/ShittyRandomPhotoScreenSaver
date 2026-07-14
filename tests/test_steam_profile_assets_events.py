from __future__ import annotations

from pathlib import Path

import pytest

from core.events.event_system import EventSystem
from core.steam.assets import (
    SteamAssetRecord,
    cache_asset_from_bytes,
    fetch_and_cache_asset,
    fetch_steam_achievement_icon,
    fetch_steam_app_artwork,
    fetch_steam_app_header,
    prune_asset_cache,
)
from core.steam.events import STEAM_DATA_READY_EVENT, publish_steam_data_ready
from core.steam.mock_backend import SteamFixtureBackend
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.profile_state import (
    SteamProfilePolicyState,
    read_profile_state,
    write_profile_state,
)


def test_profile_state_roundtrip_and_corrupt_quarantine(tmp_path: Path) -> None:
    path = tmp_path / "profile_state.json"
    state = SteamProfilePolicyState(
        rotations={"achievement_pulse": {"appid": 730}},
        cooldowns={"friend_pulse": 123.5},
        dismissals={"abandonment_issues": ["730"]},
        updated_at=456.0,
    )

    write_profile_state(path, state)
    read = read_profile_state(path)

    assert read.rotations == {"achievement_pulse": {"appid": 730}}
    assert read.cooldowns == {"friend_pulse": 123.5}
    assert read.dismissals == {"abandonment_issues": ["730"]}

    path.write_text("{broken", encoding="utf-8")
    recovered = read_profile_state(path)
    assert recovered == SteamProfilePolicyState()
    assert (tmp_path / "profile_state.json.corrupt").exists()


def test_asset_cache_rejects_bad_host_and_bad_image_signature(tmp_path: Path) -> None:
    bad_host = cache_asset_from_bytes(
        cache_dir=tmp_path,
        url="https://example.com/not-steam.png",
        data=b"\x89PNG\r\n\x1a\npayload",
    )
    bad_signature = cache_asset_from_bytes(
        cache_dir=tmp_path,
        url="https://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg",
        data=b"not an image",
    )
    bad_scheme = cache_asset_from_bytes(
        cache_dir=tmp_path,
        url="http://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg",
        data=b"\xff\xd8\xffnot-https",
    )

    assert isinstance(bad_host, SteamResult)
    assert bad_host.status == SteamResultStatus.ASSET_INVALID
    assert isinstance(bad_signature, SteamResult)
    assert bad_signature.status == SteamResultStatus.ASSET_INVALID
    assert isinstance(bad_scheme, SteamResult)
    assert bad_scheme.status == SteamResultStatus.ASSET_INVALID


def test_asset_cache_writes_valid_image_with_injected_fetcher_and_prunes(tmp_path: Path) -> None:
    url = "https://cdn.akamai.steamstatic.com/steam/apps/730/header.jpg"
    asset = fetch_and_cache_asset(
        cache_dir=tmp_path,
        url=url,
        fetcher=lambda requested: b"\xff\xd8\xfffake-jpeg",
    )

    assert isinstance(asset, SteamAssetRecord)
    assert asset.path.exists()
    assert asset.image_kind == "jpg"

    for idx in range(3):
        (tmp_path / f"extra_{idx}.png").write_bytes(b"\x89PNG\r\n\x1a\nx")
    removed = prune_asset_cache(tmp_path, max_files=2)
    assert removed >= 2


def test_steam_app_header_reuses_the_validated_cached_file(tmp_path: Path) -> None:
    calls: list[str] = []

    first = fetch_steam_app_header(
        cache_dir=tmp_path,
        appid=1086940,
        fetcher=lambda url: calls.append(url) or b"\xff\xd8\xfffake-jpeg",
    )
    second = fetch_steam_app_header(
        cache_dir=tmp_path,
        appid=1086940,
        fetcher=lambda url: calls.append(url) or b"\xff\xd8\xffshould-not-fetch",
    )

    assert isinstance(first, SteamAssetRecord)
    assert isinstance(second, SteamAssetRecord)
    assert first.path == second.path
    assert calls == ["https://cdn.akamai.steamstatic.com/steam/apps/1086940/header.jpg"]


@pytest.mark.parametrize("artwork_shape", ("square", "portrait"))
def test_compact_steam_artwork_uses_the_portrait_library_capsule(
    tmp_path: Path,
    artwork_shape: str,
) -> None:
    calls: list[str] = []

    asset = fetch_steam_app_artwork(
        cache_dir=tmp_path,
        appid=1086940,
        artwork_shape=artwork_shape,
        fetcher=lambda url: calls.append(url) or b"\xff\xd8\xfffake-jpeg",
    )

    assert isinstance(asset, SteamAssetRecord)
    assert calls == ["https://cdn.akamai.steamstatic.com/steam/apps/1086940/library_600x900.jpg"]


def test_achievement_icon_accepts_schema_host_and_reuses_cache(tmp_path: Path) -> None:
    calls: list[str] = []
    url = (
        "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/"
        "1086940/achievement.jpg"
    )

    first = fetch_steam_achievement_icon(
        cache_dir=tmp_path,
        url=url,
        fetcher=lambda requested: calls.append(requested) or b"\xff\xd8\xfficon",
    )
    second = fetch_steam_achievement_icon(
        cache_dir=tmp_path,
        url=url,
        fetcher=lambda requested: calls.append(requested) or b"\xff\xd8\xffunused",
    )
    rejected = fetch_steam_achievement_icon(
        cache_dir=tmp_path,
        url="http://steamcdn-a.akamaihd.net/not-https.jpg",
        fetcher=lambda requested: b"\xff\xd8\xffunsafe",
    )

    assert isinstance(first, SteamAssetRecord)
    assert isinstance(second, SteamAssetRecord)
    assert first.path == second.path
    assert calls == [url]
    assert isinstance(rejected, SteamResult)
    assert rejected.status == SteamResultStatus.ASSET_INVALID


def test_fixture_backend_reads_checked_in_payload_without_network() -> None:
    fixture = Path("tests/fixtures/steam/recently_played.json")
    backend = SteamFixtureBackend({SteamSourceId.RECENTLY_PLAYED: fixture})

    result = backend.fetch(SteamSourceId.RECENTLY_PLAYED)

    assert result.status == SteamResultStatus.SUCCESS
    assert result.payload is not None
    assert result.payload["response"]["games"][0]["appid"] == 730
    assert backend.requests == [SteamSourceId.RECENTLY_PLAYED]


def test_steam_data_ready_event_uses_non_secret_payload() -> None:
    events = EventSystem()
    received = []
    events.subscribe(STEAM_DATA_READY_EVENT, lambda event: received.append(event.data))

    publish_steam_data_ready(
        events,
        source_id=SteamSourceId.APP_NEWS,
        profile_key="profile_opaque",
        cache_key="steam_progress_news_730",
        result=SteamResult(
            status=SteamResultStatus.SUCCESS,
            source_id=SteamSourceId.APP_NEWS,
            payload={"secret_should_not_publish": "payload is intentionally omitted"},
            attempted_sources=(SteamSourceId.APP_NEWS,),
            from_cache=True,
        ),
    )

    assert received == [
        {
            "source_id": "app_news",
            "profile_key": "profile_opaque",
            "cache_key": "steam_progress_news_730",
            "status": "success",
            "from_cache": True,
            "attempted_sources": ["app_news"],
        }
    ]
