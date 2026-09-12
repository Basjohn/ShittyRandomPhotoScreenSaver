from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key, safe_fingerprint
from core.steam.friend_pulse import (
    build_friend_pulse_snapshot,
    project_friend_pulse,
    sanitize_friend_list_payload,
    sanitize_player_summaries_payload,
)
from core.steam.friend_pulse_cache import (
    FRIEND_LIST_CACHE_KEY,
    MAX_PLAYER_SUMMARIES_BATCH,
    PLAYER_SUMMARIES_CACHE_KEY,
    load_friend_pulse_cache_snapshot,
    refresh_friend_pulse_cache,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId


FIXTURES = Path(__file__).parent / "fixtures" / "steam"
RAW_ID_A = "76561198000000001"
RAW_ID_B = "76561198000000002"


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self._stream = BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _result(source: SteamSourceId, payload: dict, *, cache: bool = False, at: float = 100.0) -> SteamResult:
    return SteamResult(SteamResultStatus.SUCCESS, source, payload, from_cache=cache, fetched_at=at)


def test_sanitizers_remove_raw_ids_and_keep_only_safe_fingerprints() -> None:
    friends = _fixture("friend_list.json")
    players = _fixture("player_summaries.json")
    safe_friends = sanitize_friend_list_payload(friends)
    safe_players = sanitize_player_summaries_payload(players, friend_ids=(RAW_ID_A, RAW_ID_B))

    rendered = json.dumps({"friends": safe_friends, "players": safe_players})
    assert RAW_ID_A not in rendered and RAW_ID_B not in rendered
    assert safe_friends["friends"] == [{"identity_fingerprint": safe_fingerprint(RAW_ID_A)}, {"identity_fingerprint": safe_fingerprint(RAW_ID_B)}]
    assert safe_players["players"][0]["identity_fingerprint"] == safe_fingerprint(RAW_ID_A)


def test_snapshot_projects_private_empty_and_privacy_modes_honestly() -> None:
    private = build_friend_pulse_snapshot(
        friend_result=SteamResult(SteamResultStatus.PRIVATE, SteamSourceId.FRIEND_LIST), summaries_result=None
    )
    assert project_friend_pulse(private, privacy_mode="Rich", capacity=3).state == "private"

    empty = build_friend_pulse_snapshot(
        friend_result=_result(SteamSourceId.FRIEND_LIST, {"friends": []}),
        summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, {"players": []}),
    )
    assert project_friend_pulse(empty, privacy_mode="Balanced", capacity=3).primary_metric == "No friends playing"

    snapshot = build_friend_pulse_snapshot(
        friend_result=_result(SteamSourceId.FRIEND_LIST, sanitize_friend_list_payload(_fixture("friend_list.json"))),
        summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, sanitize_player_summaries_payload(_fixture("player_summaries.json"), friend_ids=(RAW_ID_A, RAW_ID_B))),
    )
    strict = project_friend_pulse(snapshot, privacy_mode="Strict", capacity=1)
    balanced = project_friend_pulse(snapshot, privacy_mode="Balanced", capacity=1)
    rich = project_friend_pulse(snapshot, privacy_mode="Rich", capacity=1)
    assert strict.rows[0].primary == "Counter-Strike" and "Ada" not in str(strict)
    assert balanced.rows[0].primary == "Ada" and balanced.rows[0].avatar_url is None
    assert rich.rows[0].avatar_url == "https://avatars.example/ada.jpg"


def test_change_evidence_requires_two_fresh_coherent_accepted_snapshots() -> None:
    friend = sanitize_friend_list_payload(_fixture("friend_list.json"))
    first_players = sanitize_player_summaries_payload(_fixture("player_summaries.json"), friend_ids=(RAW_ID_A, RAW_ID_B))
    first = build_friend_pulse_snapshot(friend_result=_result(SteamSourceId.FRIEND_LIST, friend), summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, first_players))
    assert not first.entries[0].changed
    changed_raw = _fixture("player_summaries.json")
    changed_raw["response"]["players"][0]["gameid"] = "20"
    changed_raw["response"]["players"][0]["gameextrainfo"] = "Team Fortress 2"
    second = build_friend_pulse_snapshot(friend_result=_result(SteamSourceId.FRIEND_LIST, friend, at=200), summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, sanitize_player_summaries_payload(changed_raw, friend_ids=(RAW_ID_A, RAW_ID_B)), at=200), previous=first)
    assert second.entries[0].changed is True
    stale = build_friend_pulse_snapshot(friend_result=_result(SteamSourceId.FRIEND_LIST, friend, cache=True, at=300), summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, sanitize_player_summaries_payload(changed_raw, friend_ids=(RAW_ID_A, RAW_ID_B)), cache=True, at=300), previous=first, stale=True)
    assert stale.entries[0].changed is False


def test_newly_playing_friend_is_changed_only_after_a_prior_fresh_snapshot() -> None:
    friend = {"friends": [{"identity_fingerprint": safe_fingerprint(RAW_ID_A)}]}
    idle = build_friend_pulse_snapshot(
        friend_result=_result(SteamSourceId.FRIEND_LIST, friend),
        summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, {"players": [{"identity_fingerprint": safe_fingerprint(RAW_ID_A), "persona_state": 1}]}),
    )
    playing = build_friend_pulse_snapshot(
        friend_result=_result(SteamSourceId.FRIEND_LIST, friend, at=200),
        summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, {"players": [{"identity_fingerprint": safe_fingerprint(RAW_ID_A), "game_appid": 10, "game_name": "Game"}]}, at=200),
        previous=idle,
    )
    assert playing.entries[0].changed is True


def test_refresh_batches_summaries_and_persists_no_raw_ids(tmp_path: Path) -> None:
    ids = tuple(f"7656119800{index:07d}" for index in range(MAX_PLAYER_SUMMARIES_BATCH + 1))
    calls: list[str] = []

    def opener(request, timeout):
        calls.append(request.full_url)
        if "GetFriendList" in request.full_url:
            return _Response({"friendslist": {"friends": [{"steamid": value} for value in ids]}})
        requested = parse_qs(urlparse(request.full_url).query)["steamids"][0].split(",")
        assert len(requested) <= MAX_PLAYER_SUMMARIES_BATCH
        return _Response({"response": {"players": [{"steamid": value, "personaname": "Player", "personastate": 1, "gameid": 10, "gameextrainfo": "Game"} for value in requested]}})

    credential = SteamCredentialPayload(api_key="A" * 20, profile_identifier="profile-id")
    snapshot = refresh_friend_pulse_cache(credential=credential, root=tmp_path, opener=opener, now=100.0)
    assert snapshot.playing_count == len(ids)
    assert len([url for url in calls if "GetPlayerSummaries" in url]) == 2
    profile_key = derive_profile_cache_key("profile-id")
    raw_cache = "".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.json"))
    assert ids[0] not in raw_cache
    assert (tmp_path / f"{FRIEND_LIST_CACHE_KEY}.json").exists()
    assert (tmp_path / f"{PLAYER_SUMMARIES_CACHE_KEY}.json").exists()
    assert profile_key.startswith("profile_")


def test_cache_first_rate_limit_and_malformed_payload_are_honest(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="B" * 20, profile_identifier="cache-profile")
    payloads = [_fixture("friend_list.json"), _fixture("player_summaries.json")]

    def success(request, timeout):
        return _Response(payloads.pop(0))

    first = refresh_friend_pulse_cache(credential=credential, root=tmp_path, opener=success, now=100.0)
    assert first.authoritative is True
    calls = 0

    def rate_limited(request, timeout):
        nonlocal calls
        calls += 1
        return _Response({}, status=429)

    cached = refresh_friend_pulse_cache(credential=credential, root=tmp_path, opener=rate_limited, now=101.0)
    assert calls == 0 and cached.from_cache is True
    stale = load_friend_pulse_cache_snapshot(profile_key=derive_profile_cache_key("cache-profile"), root=tmp_path, now=1000.0)
    assert stale.stale is True and stale.status == SteamResultStatus.SUCCESS
    malformed = build_friend_pulse_snapshot(
        friend_result=_result(SteamSourceId.FRIEND_LIST, {"friends": [{"identity_fingerprint": "safe"}]}),
        summaries_result=_result(SteamSourceId.PLAYER_SUMMARIES, {"players": [{"identity_fingerprint": "safe", "game_appid": "bad"}]}),
    )
    assert malformed.playing_count == 0


def test_rate_limited_without_cache_is_unavailable(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="C" * 20, profile_identifier="rate-profile")

    def rate_limited(request, timeout):
        return _Response({}, status=429)

    result = refresh_friend_pulse_cache(credential=credential, root=tmp_path, opener=rate_limited, now=100.0)
    assert result.status == SteamResultStatus.RATE_LIMITED
    assert project_friend_pulse(result, privacy_mode="Strict", capacity=3).state == "unavailable"


def test_fresh_empty_friend_list_clears_previous_summary_cache(tmp_path: Path) -> None:
    credential = SteamCredentialPayload(api_key="D" * 20, profile_identifier="empty-profile")

    def populated(request, timeout):
        if "GetFriendList" in request.full_url:
            return _Response(_fixture("friend_list.json"))
        return _Response(_fixture("player_summaries.json"))

    first = refresh_friend_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=populated,
        now=100.0,
    )
    assert first.playing_count == 1

    def empty_friends(request, timeout):
        assert "GetFriendList" in request.full_url
        return _Response({"friendslist": {"friends": []}})

    empty = refresh_friend_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=empty_friends,
        now=1000.0,
        force=True,
        previous=first,
    )
    assert empty.status == SteamResultStatus.SUCCESS
    assert empty.authoritative is True
    assert empty.playing_count == 0
    summary_cache = (tmp_path / f"{PLAYER_SUMMARIES_CACHE_KEY}.json").read_text(
        encoding="utf-8"
    )
    assert RAW_ID_A not in summary_cache
    assert '"players": []' in summary_cache
