"""Cache-first, bounded Friend Pulse source preparation.

No Qt/runtime/timer ownership lives here.  All writes are sanitized before they
reach the generic account-private cache envelope.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from core.steam.backend import build_endpoint, fetch_json
from core.steam.cache import cache_path_for_profile_key, get_steam_source_refresh_lock, read_cache_record, write_success_result
from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key
from core.steam.friend_pulse import (
    FriendPulseSnapshot,
    build_friend_pulse_snapshot,
    friend_ids_from_payload,
    sanitize_friend_list_payload,
    sanitize_player_summaries_payload,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import SteamBackoffPolicy, SteamRequestCoordinator, SteamRequestKey, backoff_result


FRIEND_LIST_CACHE_KEY = "friend_pulse_friend_list"
PLAYER_SUMMARIES_CACHE_KEY = "friend_pulse_player_summaries"
MAX_PLAYER_SUMMARIES_BATCH = 100
DEFAULT_SOURCE_FRESH_SECONDS = 10.0 * 60.0
_request_coordinator = SteamRequestCoordinator()
_request_backoff = SteamBackoffPolicy()


def load_friend_pulse_cache_snapshot(
    *,
    profile_key: str,
    profile: str | None = None,
    root: Path | None = None,
    now: float | None = None,
    previous: FriendPulseSnapshot | None = None,
) -> FriendPulseSnapshot:
    """Load only already-sanitized cache records; no credential/network work."""

    friend = read_cache_record(cache_path_for_profile_key(profile_key, FRIEND_LIST_CACHE_KEY, profile=profile, root=root))
    summaries = read_cache_record(cache_path_for_profile_key(profile_key, PLAYER_SUMMARIES_CACHE_KEY, profile=profile, root=root))
    stale = _is_stale(friend, now) or _is_stale(summaries, now)
    return build_friend_pulse_snapshot(friend_result=friend, summaries_result=summaries, now=now, previous=previous, stale=stale)


def refresh_friend_pulse_cache(
    *,
    credential: SteamCredentialPayload,
    profile: str | None = None,
    root: Path | None = None,
    opener: Callable | None = None,
    now: float | None = None,
    force: bool = False,
    previous: FriendPulseSnapshot | None = None,
) -> FriendPulseSnapshot:
    """Fetch FriendList then bounded PlayerSummaries batches, cache sanitized data."""

    reference_now = time.time() if now is None else float(now)
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    friend = _fetch_cached_source(
        profile_key=profile_key, cache_key=FRIEND_LIST_CACHE_KEY, source_id=SteamSourceId.FRIEND_LIST,
        credential=credential, profile=profile, root=root, opener=opener, now=reference_now, force=force,
    )
    if not friend.ok:
        cached = load_friend_pulse_cache_snapshot(profile_key=profile_key, profile=profile, root=root, now=reference_now, previous=previous)
        return cached if cached.usable else build_friend_pulse_snapshot(friend_result=friend, summaries_result=None, now=reference_now, previous=previous)
    # A fresh FriendList response is raw only in this stack frame.  A cache hit
    # is already sanitized and therefore cannot (and must not) be turned back
    # into request identifiers; use its existing sanitized summaries instead.
    live_ids = friend_ids_from_payload(friend.payload or {})
    if not live_ids and friend.from_cache:
        summaries = read_cache_record(cache_path_for_profile_key(profile_key, PLAYER_SUMMARIES_CACHE_KEY, profile=profile, root=root))
        return build_friend_pulse_snapshot(friend_result=friend, summaries_result=summaries, now=reference_now, previous=previous, stale=_is_stale(friend, reference_now) or _is_stale(summaries, reference_now))
    if not live_ids:
        empty = SteamResult(status=SteamResultStatus.SUCCESS, source_id=SteamSourceId.PLAYER_SUMMARIES, payload={"players": []}, fetched_at=reference_now)
        _write_sanitized(profile_key, PLAYER_SUMMARIES_CACHE_KEY, empty, profile=profile, root=root, now=reference_now)
        return build_friend_pulse_snapshot(friend_result=_sanitized_friend_result(friend), summaries_result=empty, now=reference_now, previous=previous)
    summaries = _fetch_summaries(
        profile_key=profile_key, friend_ids=live_ids, credential=credential, profile=profile, root=root,
        opener=opener, now=reference_now, force=force,
    )
    safe_friend = _sanitized_friend_result(friend)
    return build_friend_pulse_snapshot(friend_result=safe_friend, summaries_result=summaries, now=reference_now, previous=previous)


def _fetch_summaries(**kwargs) -> SteamResult:
    profile_key, friend_ids, credential = kwargs["profile_key"], kwargs["friend_ids"], kwargs["credential"]
    profile, root, opener, now, force = kwargs["profile"], kwargs["root"], kwargs["opener"], kwargs["now"], kwargs["force"]
    with get_steam_source_refresh_lock(profile_key, PLAYER_SUMMARIES_CACHE_KEY):
        path = cache_path_for_profile_key(profile_key, PLAYER_SUMMARIES_CACHE_KEY, profile=profile, root=root)
        cached = read_cache_record(path)
        if not force and cached.ok and not _is_stale(cached, now):
            return cached
        players: list[dict] = []
        for start in range(0, len(friend_ids), MAX_PLAYER_SUMMARIES_BATCH):
            batch = friend_ids[start:start + MAX_PLAYER_SUMMARIES_BATCH]
            result = _fetch_live(profile_key=profile_key, source_id=SteamSourceId.PLAYER_SUMMARIES, credential=credential, params={"steamids": ",".join(batch)}, opener=opener, now=now)
            if not result.ok:
                return cached if cached.ok else result
            safe = sanitize_player_summaries_payload(result.payload or {}, friend_ids=batch)
            players.extend(safe["players"])
        combined = SteamResult(status=SteamResultStatus.SUCCESS, source_id=SteamSourceId.PLAYER_SUMMARIES, payload={"players": players}, fetched_at=now)
        _write_sanitized(profile_key, PLAYER_SUMMARIES_CACHE_KEY, combined, profile=profile, root=root, now=now)
        return combined


def _fetch_cached_source(*, profile_key: str, cache_key: str, source_id: SteamSourceId, credential: SteamCredentialPayload, profile: str | None, root: Path | None, opener, now: float, force: bool) -> SteamResult:
    with get_steam_source_refresh_lock(profile_key, cache_key):
        path = cache_path_for_profile_key(profile_key, cache_key, profile=profile, root=root)
        cached = read_cache_record(path)
        if not force and cached.ok and not _is_stale(cached, now):
            return cached
        result = _fetch_live(profile_key=profile_key, source_id=source_id, credential=credential, params={}, opener=opener, now=now)
        if result.ok:
            safe = _sanitized_friend_result(result)
            _write_sanitized(profile_key, cache_key, safe, profile=profile, root=root, now=now)
            return result
        return cached if cached.ok else result


def _fetch_live(*, profile_key: str, source_id: SteamSourceId, credential: SteamCredentialPayload, params: dict[str, str], opener, now: float) -> SteamResult:
    key = SteamRequestKey.from_params(profile_key=profile_key, source_id=source_id, category="friend_pulse", params=params)
    decision = _request_backoff.check(key, now=now)
    if not decision.allowed:
        return backoff_result(key, decision)
    handle = _request_coordinator.begin(key)
    if not handle.owner:
        return SteamResult(status=SteamResultStatus.STALE_GENERATION, source_id=source_id, message="Friend Pulse request already in flight.")
    endpoint = build_endpoint(source_id, api_key=credential.api_key, steamid=credential.profile_identifier, **params)
    result = _request_coordinator.complete(handle, fetch_json(endpoint, opener=opener))
    _request_backoff.record_result(key, result, now=now)
    return result


def _sanitized_friend_result(result: SteamResult) -> SteamResult:
    return SteamResult(status=result.status, source_id=result.source_id, payload=sanitize_friend_list_payload(result.payload or {}), attempted_sources=result.attempted_sources, from_cache=result.from_cache, fetched_at=result.fetched_at)


def _write_sanitized(profile_key: str, cache_key: str, result: SteamResult, *, profile: str | None, root: Path | None, now: float) -> None:
    write_success_result(path=cache_path_for_profile_key(profile_key, cache_key, profile=profile, root=root), cache_key=cache_key, result=result, fetched_at=now)


def _is_stale(result: SteamResult, now: float | None) -> bool:
    if not result.ok or result.fetched_at is None:
        return False
    reference = time.time() if now is None else float(now)
    return not (0.0 <= reference - result.fetched_at < DEFAULT_SOURCE_FRESH_SECONDS)
