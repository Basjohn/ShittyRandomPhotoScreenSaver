from __future__ import annotations

from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import (
    SteamBackoffPolicy,
    SteamRequestCoordinator,
    SteamRequestKey,
    backoff_result,
)


def test_request_coordinator_coalesces_same_key_without_second_owner() -> None:
    coordinator = SteamRequestCoordinator()
    key = SteamRequestKey.from_params(
        profile_key="profile_abc",
        source_id=SteamSourceId.RECENTLY_PLAYED,
        category="recent",
        params={"count": 5},
    )

    first = coordinator.begin(key)
    second = coordinator.begin(key)

    assert first.owner is True
    assert second.owner is False
    assert first.token == second.token
    assert coordinator.active_count() == 1


def test_request_coordinator_drops_stale_generation_completion() -> None:
    coordinator = SteamRequestCoordinator()
    key = SteamRequestKey.from_params(
        profile_key="profile_abc",
        source_id=SteamSourceId.APP_NEWS,
        category="news",
        appid=730,
    )
    handle = coordinator.begin(key)
    coordinator.advance_generation()

    result = coordinator.complete(
        handle,
        SteamResult(status=SteamResultStatus.SUCCESS, source_id=SteamSourceId.APP_NEWS, payload={"ok": True}),
    )

    assert result.status == SteamResultStatus.STALE_GENERATION
    assert coordinator.active_count() == 0


def test_request_coordinator_rejects_joined_handle_completion() -> None:
    coordinator = SteamRequestCoordinator()
    key = SteamRequestKey.from_params(
        profile_key="profile_abc",
        source_id=SteamSourceId.OWNED_GAMES,
        category="owned",
    )
    coordinator.begin(key)
    joined = coordinator.begin(key)

    result = coordinator.complete(
        joined,
        SteamResult(status=SteamResultStatus.SUCCESS, source_id=SteamSourceId.OWNED_GAMES, payload={"bad": "owner"}),
    )

    assert result.status == SteamResultStatus.STALE_GENERATION
    assert coordinator.active_count() == 1


def test_backoff_policy_blocks_after_terminal_provider_failure_and_resets_on_success() -> None:
    key = SteamRequestKey.from_params(
        profile_key="profile_abc",
        source_id=SteamSourceId.FRIEND_LIST,
        category="friends",
    )
    policy = SteamBackoffPolicy(base_seconds=30.0, max_seconds=120.0)

    assert policy.check(key, now=100.0).allowed is True
    policy.record_result(
        key,
        SteamResult(status=SteamResultStatus.RATE_LIMITED, source_id=SteamSourceId.FRIEND_LIST),
        now=100.0,
    )

    blocked = policy.check(key, now=110.0)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 20.0
    assert backoff_result(key, blocked).status == SteamResultStatus.BACKOFF_ACTIVE

    policy.record_result(
        key,
        SteamResult(status=SteamResultStatus.SUCCESS, source_id=SteamSourceId.FRIEND_LIST, payload={"ok": True}),
        now=120.0,
    )
    assert policy.check(key, now=121.0).allowed is True
