from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from core.steam.abandonment_cache import (
    MAX_CACHED_ACHIEVEMENT_PROBES,
    _load_cached_achievement_progress,
    load_abandonment_cache_snapshot,
    refresh_abandonment_cache,
)
from core.steam.abandonment_issues import (
    AbandonmentAchievementProgress,
    AbandonmentResolved,
    AbandonmentSelection,
    LAST_PLAYED_UNKNOWN,
    LAST_PLAYED_VERIFIED,
    achievement_progress_from_result,
    build_abandonment_candidates,
    format_appid_list,
    parse_appid_list,
    resolve_abandonment_issues,
)
from core.steam.achievement_pulse_cache import (
    OWNED_GAMES_CACHE_KEY,
    RECENT_GAMES_CACHE_KEY,
    achievement_cache_key_for_app,
    refresh_achievement_pulse_cache,
)
from core.steam.assets import (
    SteamAssetRecord,
    abandonment_desaturation_bucket,
    prepare_desaturated_steam_artwork,
)
from core.steam.cache import (
    SteamCacheRecord,
    cache_path_for_profile_key,
    read_cache_record,
    write_cache_record,
)
from core.steam.credentials import (
    SteamCredentialPayload,
    derive_profile_cache_key,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.threading.manager import TaskResult
from widgets.steam_abandonment_runtime import (
    AbandonmentRuntimeService,
    achievement_evidence_requested as _achievement_evidence_requested,
)
from widgets.steam_abandonment_preparation import (
    AbandonmentRuntimeConfig,
    decode_abandonment_artwork as _decode_abandonment_artwork,
    prepare_abandonment_presentation,
)
from widgets.steam_abandonment_layout import normalize_abandonment_artwork_shape
from widgets.steam_abandonment_models import (
    ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES,
    ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE,
    _rediscovery_message_for_bucket,
    abandonment_archive_class,
    abandonment_rediscovery_message,
    abandonment_shelf_diagnostics,
    build_abandonment_view_model,
    format_abandonment_last_played,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "steam"
NOW = 2_000_000_000.0


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _result(name: str, source_id: SteamSourceId, *, from_cache: bool = True) -> SteamResult:
    return SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=source_id,
        payload=_fixture(name),
        from_cache=from_cache,
        fetched_at=NOW - 60,
    )


def _owned_result() -> SteamResult:
    return _result("owned_games_last_played.json", SteamSourceId.OWNED_GAMES)


def _recent_result() -> SteamResult:
    return _result("recent_games_for_abandonment.json", SteamSourceId.RECENTLY_PLAYED)


def test_abandonment_appid_list_normalizes_only_positive_unique_ids() -> None:
    assert parse_appid_list("440, 570; 440\n730 invalid -2 0") == (440, 570, 730)
    assert parse_appid_list([10, "20", 10, None]) == (10, 20)


def test_abandonment_portrait_shape_promotes_legacy_square_token() -> None:
    assert normalize_abandonment_artwork_shape("portrait") == "portrait"
    assert normalize_abandonment_artwork_shape("square") == "portrait"
    assert normalize_abandonment_artwork_shape("wide") == "wide"
    assert format_appid_list((440, 570, 440)) == "440, 570"


def test_abandonment_achievement_hydration_follows_dependent_shelf_visibility() -> None:
    assert _achievement_evidence_requested({}) is True
    assert _achievement_evidence_requested(
        {"achievements": False, "last_unlock": True}
    ) is True
    assert _achievement_evidence_requested(
        {"achievements": False, "last_unlock": False}
    ) is False


def test_abandonment_smart_candidates_require_meaningful_play_and_verified_age() -> None:
    candidates = build_abandonment_candidates(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(),
        now=NOW,
    )

    assert {candidate.appid for candidate in candidates} == {101, 102, 106}
    assert [candidate.appid for candidate in candidates] == [102, 101, 106]
    assert all(candidate.last_played_confidence == "verified" for candidate in candidates)
    assert 103 not in {candidate.appid for candidate in candidates}
    assert 104 not in {candidate.appid for candidate in candidates}
    assert 105 not in {candidate.appid for candidate in candidates}
    assert 107 not in {candidate.appid for candidate in candidates}


def test_abandonment_prefers_old_short_low_unlock_games_without_forbidding_others() -> None:
    old_timestamp = NOW - 400 * 24 * 60 * 60
    younger_timestamp = NOW - 100 * 24 * 60 * 60
    owned = SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.OWNED_GAMES,
        payload={
            "response": {
                "games": [
                    {"appid": 1, "name": "Short Low", "playtime_forever": 90, "rtime_last_played": old_timestamp},
                    {"appid": 2, "name": "Short High", "playtime_forever": 90, "rtime_last_played": old_timestamp},
                    {"appid": 3, "name": "Long Low", "playtime_forever": 600, "rtime_last_played": old_timestamp},
                    {"appid": 4, "name": "Likely Complete", "playtime_forever": 600, "rtime_last_played": old_timestamp},
                    {"appid": 5, "name": "Too Recent To Prefer", "playtime_forever": 90, "rtime_last_played": younger_timestamp},
                    {"appid": 6, "name": "Accidental Launch", "playtime_forever": 10, "rtime_last_played": old_timestamp},
                ]
            }
        },
    )
    progress = {
        1: AbandonmentAchievementProgress(unlocked_count=1, total_count=20),
        2: AbandonmentAchievementProgress(unlocked_count=6, total_count=20),
        3: AbandonmentAchievementProgress(unlocked_count=1, total_count=20),
        4: AbandonmentAchievementProgress(unlocked_count=20, total_count=20),
        5: AbandonmentAchievementProgress(unlocked_count=1, total_count=20),
    }

    candidates = build_abandonment_candidates(
        owned_result=owned,
        recent_result=None,
        achievement_progress_by_appid=progress,
        now=NOW,
    )

    assert [candidate.appid for candidate in candidates] == [1, 2, 3, 4, 5]
    assert [candidate.preference_tier for candidate in candidates] == [0, 2, 3, 6, 10]


def test_abandonment_user_shelves_require_and_format_cached_evidence() -> None:
    last_played = 1_493_424_000.0  # 29/04/2017 UTC
    latest_unlock = 1_609_459_200.0
    owned = SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.OWNED_GAMES,
        payload={
            "response": {
                "games": [
                    {
                        "appid": 77,
                        "name": "Shelf Fixture",
                        "playtime_forever": 90,
                        "rtime_last_played": last_played,
                    }
                ]
            }
        },
        from_cache=True,
    )
    achievement_result = SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
        payload={
            "playerstats": {
                "achievements": [
                    {"name": "ONE", "achieved": 1, "unlocktime": latest_unlock - 100},
                    {"name": "TWO", "achieved": 1, "unlocktime": latest_unlock},
                    {"name": "THREE", "achieved": 0, "unlocktime": 0},
                    {"name": "FOUR", "achieved": 0},
                ]
            }
        },
        from_cache=True,
    )
    progress = achievement_progress_from_result(achievement_result)

    assert progress is not None
    assert progress.latest_unlock_at == latest_unlock
    resolved = resolve_abandonment_issues(
        owned_result=owned,
        recent_result=None,
        achievement_progress_by_appid={77: progress},
        now=NOW,
    )
    fields = {field.field_id: field for field in build_abandonment_view_model(resolved).fields}

    assert fields["achievements"].enabled is True
    assert fields["achievements"].value == "2 / 4"
    assert fields["last_unlock"].enabled is True
    assert str(fields["last_unlock"].value).endswith("YEARS AGO")
    assert fields["last_played"].enabled is True
    assert fields["last_played"].value == "29/04/2017"
    assert fields["archive_class"].value == "Barely Started"
    assert fields["queue"].enabled is False
    assert abandonment_archive_class(resolved) == "Barely Started"
    assert build_abandonment_view_model(resolved).status == "BACKLOG 01/01"


def test_abandonment_last_played_and_unlock_shelves_hide_unproven_values() -> None:
    resolved = AbandonmentResolved(
        status="ok",
        appid=88,
        title="Unknown Evidence",
        playtime_minutes=400,
        last_played_at=1_493_424_000.0,
        last_played_confidence=LAST_PLAYED_UNKNOWN,
        unlocked_achievement_count=None,
        total_achievement_count=None,
    )
    fields = {field.field_id: field for field in build_abandonment_view_model(resolved).fields}

    assert format_abandonment_last_played(
        resolved.last_played_at,
        resolved.last_played_confidence,
    ) is None
    assert fields["last_played"].enabled is False
    assert fields["achievements"].enabled is False
    assert fields["last_unlock"].enabled is False


def test_abandonment_shelf_diagnostics_report_requested_missing_evidence_without_values() -> None:
    resolved = AbandonmentResolved(
        status="ok",
        appid=88,
        title="Private Title Must Not Enter Diagnostics",
        playtime_minutes=400,
        last_played_at=1_493_424_000.0,
        last_played_confidence=LAST_PLAYED_UNKNOWN,
        queue_position=1,
        queue_count=12,
    )
    visibility = {
        "playtime": True,
        "achievements": True,
        "last_unlock": True,
        "last_played": True,
        "archive_class": True,
        "queue": True,
        "source": False,
        "pinned": False,
    }
    model = build_abandonment_view_model(resolved, field_visibility=visibility)

    requested, rendered, unavailable, evidence = abandonment_shelf_diagnostics(
        resolved,
        model,
        visibility,
    )

    assert requested == (
        "playtime",
        "achievements",
        "last_unlock",
        "last_played",
        "archive_class",
        "queue",
    )
    assert rendered == ("playtime", "archive_class", "queue")
    assert unavailable == ("achievements", "last_unlock", "last_played")
    assert "achievements:missing" in evidence
    assert "last_played:missing" in evidence
    assert all("Private Title" not in item for item in evidence)


def test_abandonment_zero_unlock_snapshot_proves_no_unlocks() -> None:
    resolved = AbandonmentResolved(
        status="ok",
        appid=89,
        title="No Unlock Fixture",
        playtime_minutes=45,
        last_played_at=1_493_424_000.0,
        last_played_confidence=LAST_PLAYED_VERIFIED,
        unlocked_achievement_count=0,
        total_achievement_count=12,
    )
    fields = {field.field_id: field for field in build_abandonment_view_model(resolved).fields}

    assert fields["achievements"].value == "0 / 12"
    assert fields["last_unlock"].enabled is True
    assert fields["last_unlock"].value == "No Unlocks"


def test_abandonment_never_show_and_pinned_unknown_history_remain_honest() -> None:
    smart = build_abandonment_candidates(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(never_show_appids=(101,)),
        now=NOW,
    )
    pinned = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(mode="pinned_game", pinned_appid=104),
        now=NOW,
    )

    assert 101 not in {candidate.appid for candidate in smart}
    assert pinned.ok is False
    assert pinned.appid == 104
    assert pinned.last_played_confidence == LAST_PLAYED_UNKNOWN
    assert "unavailable" in pinned.unavailable_reason.lower()


def test_abandonment_rotation_retains_current_until_advance_and_honors_cooldown() -> None:
    initial = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )
    retained = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW + 60,
        current_appid=initial.appid,
        exposure_timestamps={initial.appid: NOW},
    )
    advanced = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW + 60,
        current_appid=initial.appid,
        advance_rotation=True,
        exposure_timestamps={initial.appid: NOW},
    )

    assert retained.appid == initial.appid
    assert advanced.appid != initial.appid


def test_abandonment_weighted_rotation_is_varied_biased_and_repeatable() -> None:
    draws = [
        resolve_abandonment_issues(
            owned_result=_owned_result(),
            recent_result=_recent_result(),
            now=NOW,
            rotation_seed=seed,
        ).appid
        for seed in range(256)
    ]
    repeated = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
        rotation_seed=67,
    )
    repeated_again = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
        rotation_seed=67,
    )

    assert len(set(draws)) >= 2
    assert draws.count(102) > sum(draws.count(appid) for appid in (101, 106))
    assert repeated.appid == repeated_again.appid


def test_abandonment_persisted_draws_shuffle_backlog_ranks(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000999")
    owned_payload = {
        "response": {
            "game_count": 18,
            "games": [
                {
                    "appid": 5_000 + index,
                    "name": f"Archive Game {index:02d}",
                    "playtime_forever": 30,
                    "rtime_last_played": NOW - (500 + index) * 24 * 60 * 60,
                }
                for index in range(18)
            ],
        }
    }
    recent_payload = {"response": {"total_count": 0, "games": []}}
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, owned_payload),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, recent_payload),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    draws = [
        load_abandonment_cache_snapshot(
            profile_key=profile_key,
            root=tmp_path,
            now=NOW + index,
            force_rotation=index > 0,
        ).resolved
        for index in range(10)
    ]
    backlog_ranks = [draw.queue_position for draw in draws]
    appids = [draw.appid for draw in draws]

    assert len(set(appids)) == len(appids)
    assert backlog_ranks != sorted(backlog_ranks)
    assert any(
        abs(backlog_ranks[index] - backlog_ranks[index - 1]) > 1
        for index in range(1, len(backlog_ranks))
    )


def test_abandonment_advanced_rotation_never_immediately_repeats_when_alternatives_exist() -> None:
    appids = {
        resolve_abandonment_issues(
            owned_result=_owned_result(),
            recent_result=_recent_result(),
            now=NOW,
            current_appid=102,
            advance_rotation=True,
            rotation_seed=seed,
        ).appid
        for seed in range(128)
    }

    assert 102 not in appids
    assert appids


def test_abandonment_profile_rotation_is_shared_across_display_followers(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000001")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    first = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW,
        refresh_interval_minutes=30,
    )
    follower = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 1,
        advance_rotation=True,
        refresh_interval_minutes=30,
    )
    advanced = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 30 * 60 - 1,
        advance_rotation=True,
        refresh_interval_minutes=30,
    )

    assert first.resolved.ok is True
    assert follower.resolved.appid == first.resolved.appid
    assert advanced.resolved.appid != first.resolved.appid
    assert first.rotation_due_seconds == 30 * 60
    assert follower.rotation_due_seconds == 30 * 60 - 1
    assert advanced.rotation_due_seconds == 30 * 60
    state_payload = json.loads((tmp_path / "profile_state.json").read_text(encoding="utf-8"))
    assert state_payload["rotations"]["abandonment_issues"]["appid"] == advanced.resolved.appid
    assert state_payload["rotations"]["abandonment_issues"]["rotation_index"] == 2


def test_abandonment_shared_refresh_interval_rebases_remaining_duration(
    tmp_path,
) -> None:
    profile_key = derive_profile_cache_key("shared_refresh_interval_fixture")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (
            RECENT_GAMES_CACHE_KEY,
            SteamSourceId.RECENTLY_PLAYED,
            _fixture("recent_games_for_abandonment.json"),
        ),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    first = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW,
        refresh_interval_minutes=15,
    )
    shortened = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 4 * 60,
        advance_rotation=True,
        refresh_interval_minutes=5,
    )
    due = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 5 * 60,
        advance_rotation=True,
        refresh_interval_minutes=5,
    )

    assert shortened.resolved.appid == first.resolved.appid
    assert shortened.rotation_due_seconds == 60
    assert due.resolved.appid != first.resolved.appid
    assert due.rotation_due_seconds == 5 * 60


def test_abandonment_forced_rotation_does_not_wait_for_interval(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000022")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    first = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW,
        refresh_interval_minutes=30,
    )
    forced = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 1,
        force_rotation=True,
        refresh_interval_minutes=30,
    )

    assert forced.resolved.appid != first.resolved.appid
    assert forced.rotation_due_seconds == 30 * 60


def test_abandonment_recomputes_profile_rotation_when_preference_policy_changes(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000020")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    high_playtime_policy = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        selection=AbandonmentSelection(preferred_max_playtime_minutes=30),
        root=tmp_path,
        now=NOW,
    )
    high_playtime_state = json.loads((tmp_path / "profile_state.json").read_text(encoding="utf-8"))
    short_start_policy = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        selection=AbandonmentSelection(),
        root=tmp_path,
        now=NOW + 1,
    )
    short_start_state = json.loads((tmp_path / "profile_state.json").read_text(encoding="utf-8"))

    assert high_playtime_policy.resolved.appid in {101, 102}
    assert short_start_policy.resolved.appid in {101, 102, 106}
    assert short_start_policy.resolved.appid != high_playtime_policy.resolved.appid
    assert (
        high_playtime_state["rotations"]["abandonment_issues"]["policy_signature"]
        != short_start_state["rotations"]["abandonment_issues"]["policy_signature"]
    )
    assert short_start_state["rotations"]["abandonment_issues"]["rotation_index"] == 1
    assert short_start_state["rotations"]["abandonment_issues"]["changed_at"] == NOW + 1


def test_abandonment_uses_bounded_cached_achievement_signal_without_provider_work(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000021")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
        (
            achievement_cache_key_for_app(102),
            SteamSourceId.PLAYER_ACHIEVEMENTS,
            {
                "playerstats": {
                    "achievements": [
                        {"name": "ONE", "achieved": 1},
                        {"name": "TWO", "achieved": 1},
                    ]
                }
            },
        ),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    snapshot = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW,
    )

    assert snapshot.resolved.appid == 101


def test_abandonment_achievement_hint_probe_has_a_hard_exact_path_cap(tmp_path) -> None:
    old_timestamp = NOW - 400 * 24 * 60 * 60
    owned = SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.OWNED_GAMES,
        payload={
            "response": {
                "games": [
                    {
                        "appid": appid,
                        "name": f"Candidate {appid}",
                        "playtime_forever": 90,
                        "rtime_last_played": old_timestamp,
                    }
                    for appid in range(1, 31)
                ]
            }
        },
    )
    candidates = build_abandonment_candidates(
        owned_result=owned,
        recent_result=None,
        now=NOW,
    )
    reads: list[Path] = []

    def _read(path: Path) -> SteamResult:
        reads.append(path)
        return SteamResult(status=SteamResultStatus.CACHE_MISS, from_cache=True)

    progress = _load_cached_achievement_progress(
        profile_key=derive_profile_cache_key("76561198000000022"),
        candidates=candidates,
        preferred_appids=(30, None),
        profile=None,
        root=tmp_path,
        read_record=_read,
    )

    assert progress == {}
    assert len(reads) == MAX_CACHED_ACHIEVEMENT_PROBES
    assert achievement_cache_key_for_app(30) in reads[0].stem


def test_abandonment_refresh_uses_owned_and_recent_sources_and_persists_success(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_123456",
        profile_identifier="76561198000000002",
    )
    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        raise AssertionError(request.full_url)

    outcome = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)

    assert outcome.snapshot.resolved.ok is True
    assert len(requests) == 2
    assert any("include_appinfo=True" in url for url in requests)
    owned_cache = read_cache_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path)
    )
    assert owned_cache.ok is True
    assert owned_cache.fetched_at == NOW


def test_abandonment_hydrates_only_selected_achievement_evidence_and_reuses_it(
    tmp_path,
    monkeypatch,
) -> None:
    from core.steam import abandonment_cache

    credential = SteamCredentialPayload(
        api_key="fixture_api_key_selected_evidence_123456",
        profile_identifier="76561198000000023",
    )
    selected_appid = 77
    old_timestamp = NOW - 400 * 24 * 60 * 60
    latest_unlock = NOW - 200 * 24 * 60 * 60
    requests: list[str] = []
    log_messages: list[str] = []
    monkeypatch.setattr(
        abandonment_cache.logger,
        "info",
        lambda message, *args: log_messages.append(message % args),
    )

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(
                {
                    "response": {
                        "game_count": 1,
                        "games": [
                            {
                                "appid": selected_appid,
                                "name": "Selected Evidence Fixture",
                                "playtime_forever": 90,
                                "rtime_last_played": old_timestamp,
                            }
                        ],
                    }
                }
            )
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response({"response": {"total_count": 0, "games": []}})
        if "GetPlayerAchievements" in request.full_url:
            assert f"appid={selected_appid}" in request.full_url
            return _Response(
                {
                    "playerstats": {
                        "gameName": "Selected Evidence Fixture",
                        "achievements": [
                            {"name": "ONE", "achieved": 1, "unlocktime": latest_unlock},
                            {"name": "TWO", "achieved": 0, "unlocktime": 0},
                        ],
                        "success": True,
                    }
                }
            )
        raise AssertionError(request.full_url)

    first = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
        hydrate_achievement_evidence=True,
    )
    second = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW + 5 * 60,
        hydrate_achievement_evidence=True,
    )

    assert first.snapshot.resolved.appid == selected_appid
    assert first.snapshot.resolved.unlocked_achievement_count == 1
    assert first.snapshot.resolved.total_achievement_count == 2
    assert first.snapshot.resolved.latest_unlock_at == latest_unlock
    hydrated_fields = {
        field.field_id: field
        for field in build_abandonment_view_model(first.snapshot.resolved).fields
    }
    assert hydrated_fields["achievements"].enabled is True
    assert hydrated_fields["achievements"].value == "1 / 2"
    assert hydrated_fields["last_unlock"].enabled is True
    assert second.snapshot.resolved.appid == selected_appid
    assert sum("GetPlayerAchievements" in url for url in requests) == 1
    assert len(requests) == 3
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    achievement_cache = read_cache_record(
        cache_path_for_profile_key(
            profile_key,
            achievement_cache_key_for_app(selected_appid),
            root=tmp_path,
        )
    )
    assert achievement_cache.ok is True
    assert achievement_cache.fetched_at == NOW
    assert any(
        "[STEAM][ABANDONMENT_ACHIEVEMENTS]" in message
        and "outcome=hydrated" in message
        for message in log_messages
    )
    assert any(
        "[STEAM][ABANDONMENT_ACHIEVEMENTS]" in message
        and "outcome=cache_hit" in message
        for message in log_messages
    )


def test_abandonment_reuses_daily_library_but_manual_refreshes_both_sources(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_source_ttl_123456",
        profile_identifier="76561198000000011",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    for cache_key, source_id, payload, age in (
        (
            OWNED_GAMES_CACHE_KEY,
            SteamSourceId.OWNED_GAMES,
            _fixture("owned_games_last_played.json"),
            30 * 60,
        ),
        (
            RECENT_GAMES_CACHE_KEY,
            SteamSourceId.RECENTLY_PLAYED,
            _fixture("recent_games_for_abandonment.json"),
            11 * 60,
        ),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - age,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        raise AssertionError(request.full_url)

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    assert sum("GetOwnedGames" in url for url in requests) == 0
    assert sum("GetRecentlyPlayedGames" in url for url in requests) == 1

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW + 1,
        force=True,
    )
    assert sum("GetOwnedGames" in url for url in requests) == 1
    assert sum("GetRecentlyPlayedGames" in url for url in requests) == 2


def test_abandonment_and_achievement_share_fresh_recent_games_source(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_shared_source_123456",
        profile_identifier="76561198000000012",
    )
    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        if "GetPlayerAchievements" in request.full_url:
            return _Response(
                {
                    "playerstats": {
                        "gameName": "Archive Candidate",
                        "achievements": [{"name": "FIRST", "achieved": 1}],
                    }
                }
            )
        if "GetSchemaForGame" in request.full_url:
            return _Response(
                {
                    "game": {
                        "availableGameStats": {
                            "achievements": [
                                {"name": "FIRST", "displayName": "First Visit"}
                            ]
                        }
                    }
                }
            )
        raise AssertionError(request.full_url)

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW + 5 * 60,
    )

    recent_requests = [url for url in requests if "GetRecentlyPlayedGames" in url]
    assert len(recent_requests) == 1


def test_abandonment_failed_refresh_preserves_valid_cached_library(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_654321",
        profile_identifier="76561198000000003",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    write_cache_record(
        SteamCacheRecord(
            cache_key=OWNED_GAMES_CACHE_KEY,
            source_id=SteamSourceId.OWNED_GAMES,
            payload=_fixture("owned_games_last_played.json"),
            fetched_at=NOW - 1000,
        ),
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path),
    )

    class _Forbidden:
        status = 403

        def read(self, _limit: int) -> bytes:
            return b"{}"

    outcome = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=lambda _request, _timeout: _Forbidden(),
        now=NOW,
    )

    assert outcome.connection_needs_attention is True
    assert outcome.snapshot.resolved.ok is True
    preserved = read_cache_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path)
    )
    assert preserved.fetched_at == NOW - 1000


def test_guilt_desaturater_is_smooth_capped_and_decoded_outside_paint(tmp_path) -> None:
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 48), (230, 70, 40)).save(source)

    at_threshold = abandonment_desaturation_bucket(
        inactivity_days=84,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    later = abandonment_desaturation_bucket(
        inactivity_days=365,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    much_later = abandonment_desaturation_bucket(
        inactivity_days=5_000,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    prepared = prepare_desaturated_steam_artwork(
        source_path=source,
        cache_dir=tmp_path,
        desaturation_percent=later,
    )

    assert at_threshold == 0
    assert 0 < later < 55
    assert much_later == 55
    assert prepared != source
    assert prepared.is_file()
    assert prepare_desaturated_steam_artwork(
        source_path=source,
        cache_dir=tmp_path,
        desaturation_percent=later,
    ) == prepared
    decoded = _decode_abandonment_artwork(prepared)
    assert (decoded.width(), decoded.height()) == (32, 48)


def _runtime_config(
    *,
    field_visibility: dict[str, bool] | None = None,
    show_artwork: bool = True,
    artwork_shape: str = "portrait",
    refresh_minutes: int = 10,
) -> AbandonmentRuntimeConfig:
    return AbandonmentRuntimeConfig(
        selection=AbandonmentSelection(),
        field_visibility=field_visibility or {},
        show_artwork=show_artwork,
        artwork_shape=artwork_shape,
        guilt_desaturater=False,
        guilt_desaturation_strength=55,
        refresh_minutes=refresh_minutes,
        show_connection_info_icon=True,
        show_rediscovery_message=True,
    )


def test_abandonment_preparation_hydrates_one_missing_selected_artwork(
    tmp_path,
    monkeypatch,
) -> None:
    from core.settings import storage_paths
    from core.steam import assets

    source = tmp_path / "selected.png"
    image = QImage(120, 180, QImage.Format.Format_RGB32)
    image.fill(QColor(190, 90, 45))
    assert image.save(str(source), "PNG")
    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )

    class _Snapshot:
        cache_age_seconds = 60.0

        def __init__(self):
            self.resolved = resolved

    fetches: list[int] = []
    monkeypatch.setattr(storage_paths, "get_steam_cache_dir", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(assets, "find_cached_steam_app_artwork", lambda **_kwargs: None)

    def _fetch(**kwargs):
        fetches.append(kwargs["appid"])
        return SteamAssetRecord(
            url_fingerprint="fixture",
            path=source,
            bytes_written=source.stat().st_size,
            image_kind="png",
        )

    monkeypatch.setattr(assets, "fetch_steam_app_artwork", _fetch)
    presentation = prepare_abandonment_presentation(
        _runtime_config(artwork_shape="portrait"),
        _Snapshot(),
        profile_key="profile_fixture",
        allow_asset_network=True,
    )

    assert fetches == [resolved.appid]
    assert presentation.artwork_identity == str(source)
    assert (presentation.artwork.width(), presentation.artwork.height()) == (120, 180)


def test_abandonment_preparation_falls_back_to_wide_artwork_after_portrait_404(
    tmp_path,
    monkeypatch,
) -> None:
    from core.settings import storage_paths
    from core.steam import assets

    source = tmp_path / "fallback-wide.png"
    image = QImage(180, 100, QImage.Format.Format_RGB32)
    image.fill(QColor(45, 90, 190))
    assert image.save(str(source), "PNG")
    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )

    class _Snapshot:
        cache_age_seconds = 60.0

        def __init__(self):
            self.resolved = resolved

    fetch_shapes: list[str] = []
    monkeypatch.setattr(storage_paths, "get_steam_cache_dir", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(assets, "find_cached_steam_app_artwork", lambda **_kwargs: None)

    def _fetch(**kwargs):
        shape = kwargs["artwork_shape"]
        fetch_shapes.append(shape)
        if shape == "portrait":
            return SteamResult(
                status=SteamResultStatus.NOT_FOUND,
                http_status=404,
            )
        return SteamAssetRecord(
            url_fingerprint="fallback",
            path=source,
            bytes_written=source.stat().st_size,
            image_kind="png",
        )

    monkeypatch.setattr(assets, "fetch_steam_app_artwork", _fetch)
    presentation = prepare_abandonment_presentation(
        _runtime_config(artwork_shape="portrait"),
        _Snapshot(),
        profile_key="profile_fixture",
        allow_asset_network=True,
    )

    assert fetch_shapes == ["portrait", "wide"]
    assert presentation.artwork_identity == str(source)
    assert (presentation.artwork.width(), presentation.artwork.height()) == (180, 100)


def test_abandonment_preparation_does_not_retry_transient_artwork_failure(
    tmp_path,
    monkeypatch,
) -> None:
    from core.settings import storage_paths
    from core.steam import assets

    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )

    class _Snapshot:
        cache_age_seconds = 60.0

        def __init__(self):
            self.resolved = resolved

    fetch_shapes: list[str] = []
    monkeypatch.setattr(storage_paths, "get_steam_cache_dir", lambda **_kwargs: tmp_path)
    monkeypatch.setattr(assets, "find_cached_steam_app_artwork", lambda **_kwargs: None)

    def _fetch(**kwargs):
        fetch_shapes.append(kwargs["artwork_shape"])
        return SteamResult(status=SteamResultStatus.NETWORK_ERROR)

    monkeypatch.setattr(assets, "fetch_steam_app_artwork", _fetch)
    presentation = prepare_abandonment_presentation(
        _runtime_config(artwork_shape="portrait"),
        _Snapshot(),
        profile_key="profile_fixture",
        allow_asset_network=True,
    )

    assert fetch_shapes == ["portrait"]
    assert presentation.artwork.isNull()


def test_abandonment_rediscovery_messages_use_exact_stable_60_40_buckets() -> None:
    expected_alternates = (
        "You Don't Even Remember Buying This One Do You?",
        "Was The Sale Really THAT Good?",
        "Your Mother Was Right About You.",
        "I Mean, We All Make Bad Decisions Sometimes...",
        "It's Not Like The Game Has Feelings Or Anything.",
        "Your Library Looks On Judgingly As You Force Feed It",
        "This One Hid Behind 7 Proxies.",
        "You Could - And Do - Play Worse.",
        "That Bundle Sure Seems Silly Now Doesn't It?",
        "If They Remake This Will You Buy And Ignore That Too?",
    )
    messages = tuple(_rediscovery_message_for_bucket(bucket) for bucket in range(100))

    assert ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE == "Long Forgotten"
    assert ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES == expected_alternates
    assert messages.count(ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE) == 60
    assert all(messages.count(message) == 4 for message in expected_alternates)
    assert abandonment_rediscovery_message(101, "Fixture Game") == abandonment_rediscovery_message(
        101,
        "Fixture Game",
    )


def test_abandonment_rediscovery_message_can_be_hidden() -> None:
    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )

    assert build_abandonment_view_model(resolved).subtitle
    assert build_abandonment_view_model(
        resolved,
        show_rediscovery_message=False,
    ).subtitle == ""


@pytest.mark.parametrize(
    (
        "updates_enabled",
        "field_visibility",
        "expected_asset_network",
        "expected_evidence_calls",
    ),
    (
        (True, {}, True, 1),
        (True, {"achievements": False, "last_unlock": False}, True, 0),
        (False, {}, False, 0),
    ),
)
def test_abandonment_automatic_rotation_hydrates_only_when_updates_are_allowed(
    qt_app,
    monkeypatch,
    updates_enabled: bool,
    field_visibility: dict[str, bool],
    expected_asset_network: bool,
    expected_evidence_calls: int,
) -> None:
    from core.steam import abandonment_cache, credentials

    class _Metadata:
        profile_cache_key = "profile_fixture"

    class _InlineThreadManager:
        def submit_io_task(self, func, *, task_id, callback, **_kwargs):
            callback(TaskResult(success=True, result=func(), task_id=task_id))
            return task_id

    snapshot = object()
    prepared = object()
    preparation_calls: list[dict[str, object]] = []
    evidence_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "widgets.steam_abandonment_runtime.automatic_service_updates_enabled",
        lambda: updates_enabled,
    )
    monkeypatch.setattr(credentials, "read_credential_metadata", lambda: _Metadata())
    monkeypatch.setattr(credentials, "load_credentials", lambda: object())
    monkeypatch.setattr(
        abandonment_cache,
        "load_abandonment_cache_snapshot",
        lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        abandonment_cache,
        "hydrate_selected_achievement_evidence",
        lambda **kwargs: (
            evidence_calls.append(kwargs) or snapshot,
            SteamResult(
                status=SteamResultStatus.SUCCESS,
                source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
            ),
        ),
    )
    service = AbandonmentRuntimeService(
        config=_runtime_config(field_visibility=field_visibility),
    )
    try:
        service.set_thread_manager(_InlineThreadManager())
        service._running = True

        def _prepare(_snapshot, **kwargs):
            preparation_calls.append(kwargs)
            return prepared

        monkeypatch.setattr(
            "widgets.steam_abandonment_runtime.prepare_abandonment_presentation",
            lambda _config, snapshot, **kwargs: _prepare(snapshot, **kwargs),
        )
        assert service.request_cache_rotation() is True
        qt_app.processEvents()

        assert preparation_calls[0]["allow_asset_network"] is expected_asset_network
        assert len(evidence_calls) == expected_evidence_calls
    finally:
        service.retire()


def test_abandonment_rebuild_arms_persisted_remaining_rotation_delay(
    qt_app,
    monkeypatch,
) -> None:
    created: list[tuple[int, object, object]] = []

    class _Handle:
        def __init__(self) -> None:
            self.active = True

        def is_active(self) -> bool:
            return self.active

        def stop(self) -> None:
            self.active = False

    def _create(_widget, interval_ms, callback, *, description):
        handle = _Handle()
        created.append((interval_ms, callback, handle))
        return handle

    monkeypatch.setattr(
        "widgets.steam_abandonment_runtime.create_overlay_timer",
        _create,
    )
    rotations: list[bool] = []

    class _Consumer:
        def is_abandonment_consumer_alive(self) -> bool:
            return True

        def on_abandonment_rotation_due(self) -> bool:
            rotations.append(True)
            return True

    consumer = _Consumer()
    service = AbandonmentRuntimeService(
        config=_runtime_config(show_artwork=False, refresh_minutes=5),
    )
    try:
        service.attach_consumer(consumer)
        service._running = True
        service._activation_rotation_due_seconds = 75.0

        service.start_rotation_timer()
        assert created[0][0] == 75_000
        created[0][1]()

        assert created[0][2].active is False
        assert created[1][0] == 5 * 60 * 1_000
        assert rotations == [True]
    finally:
        service.retire()
