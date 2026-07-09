"""Cache-first Achievement Pulse snapshot assembly.

This adapter consumes only account-private, versioned cache records addressed
by their opaque profile key.  It never decrypts credentials, starts provider
work, or touches Qt, so service widgets can paint trustworthy cached content
before deciding whether a refresh is appropriate.
"""
from __future__ import annotations

import time
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.steam.achievement_pulse import (
    AchievementPulseResolved,
    AchievementPulseSelection,
    resolve_achievement_pulse,
)
from core.steam.cache import cache_path_for_profile_key, read_cache_record
from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import (
    SteamBackoffPolicy,
    SteamRequestCoordinator,
    SteamRequestKey,
    backoff_result,
)

RECENT_GAMES_CACHE_KEY = "achievement_pulse_recent_games"
OWNED_GAMES_CACHE_KEY = "achievement_pulse_owned_games"
ACHIEVEMENTS_CACHE_KEY_PREFIX = "achievement_pulse_achievements_"
_REFRESH_FRESH_WINDOW_SECONDS = 60.0
_refresh_coordinator = SteamRequestCoordinator()
_refresh_backoff = SteamBackoffPolicy()
_refresh_locks: dict[str, threading.Lock] = {}
_refresh_locks_guard = threading.Lock()


@dataclass(frozen=True)
class AchievementPulseCacheSnapshot:
    """One cache-only resolution plus the source timestamps it depended on."""

    resolved: AchievementPulseResolved
    recent_result: SteamResult
    library_result: SteamResult
    achievement_result: SteamResult | None
    cache_age_seconds: float | None

    @property
    def has_usable_cache(self) -> bool:
        return bool(
            self.recent_result.ok
            or self.library_result.ok
            or (self.achievement_result is not None and self.achievement_result.ok)
        )


@dataclass(frozen=True)
class AchievementPulseRefreshOutcome:
    """Refresh result that preserves cache content and safe connection attention."""

    snapshot: AchievementPulseCacheSnapshot
    connection_needs_attention: bool = False

    @property
    def resolved(self) -> AchievementPulseResolved:
        return self.snapshot.resolved

    @property
    def cache_age_seconds(self) -> float | None:
        return self.snapshot.cache_age_seconds


def achievement_cache_key_for_app(appid: int) -> str:
    """Return a stable, non-secret cache key for one Steam app achievement set."""
    return f"{ACHIEVEMENTS_CACHE_KEY_PREFIX}{max(0, int(appid))}"


def load_achievement_pulse_cache_snapshot(
    *,
    profile_key: str,
    selection: AchievementPulseSelection = AchievementPulseSelection(),
    profile: str | None = None,
    root: Path | None = None,
    now: float | None = None,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> AchievementPulseRefreshOutcome:
    """Resolve the selected Achievement Pulse state from cache records only."""
    recent_result = read_record(
        cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, profile=profile, root=root)
    )
    library_result = read_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, profile=profile, root=root)
    )
    selection_probe = resolve_achievement_pulse(
        recent_result=recent_result,
        achievement_results={},
        selection=selection,
        library_result=library_result,
    )
    achievement_result: SteamResult | None = None
    achievement_results: dict[int, SteamResult] = {}
    if selection_probe.appid is not None:
        achievement_result = read_record(
            cache_path_for_profile_key(
                profile_key,
                achievement_cache_key_for_app(selection_probe.appid),
                profile=profile,
                root=root,
            )
        )
        achievement_results[selection_probe.appid] = achievement_result
    resolved = resolve_achievement_pulse(
        recent_result=recent_result,
        achievement_results=achievement_results,
        selection=selection,
        library_result=library_result,
    )
    timestamps = [
        result.fetched_at
        for result in (recent_result, library_result, achievement_result)
        if result is not None and result.ok and result.fetched_at is not None
    ]
    reference_now = time.time() if now is None else float(now)
    cache_age_seconds = max(0.0, reference_now - min(timestamps)) if timestamps else None
    return AchievementPulseCacheSnapshot(
        resolved=resolved,
        recent_result=recent_result,
        library_result=library_result,
        achievement_result=achievement_result,
        cache_age_seconds=cache_age_seconds,
    )


def refresh_achievement_pulse_cache(
    *,
    credential: SteamCredentialPayload,
    selection: AchievementPulseSelection = AchievementPulseSelection(),
    profile: str | None = None,
    root: Path | None = None,
    opener=None,
    now: float | None = None,
    force: bool = False,
) -> AchievementPulseCacheSnapshot:
    """Refresh the selected app through the cache boundary without owning scheduling.

    Callers must run this explicit IO operation through ``ThreadManager``.
    Concurrent display instances share a profile lock; a follower returns the
    freshly written cache instead of issuing a duplicate startup request.
    """
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    reference_now = time.time() if now is None else float(now)
    lock = _refresh_lock_for(profile_key)
    with lock:
        existing = load_achievement_pulse_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
        )
        if (
            not force
            and existing.cache_age_seconds is not None
            and existing.cache_age_seconds < _REFRESH_FRESH_WINDOW_SECONDS
        ):
            return AchievementPulseRefreshOutcome(snapshot=existing)

        recent_result = existing.recent_result
        refresh_results: list[SteamResult] = []
        if selection.mode != "custom":
            recent_result = _fetch_and_cache(
                profile_key=profile_key,
                cache_key=RECENT_GAMES_CACHE_KEY,
                source_id=SteamSourceId.RECENTLY_PLAYED,
                credential=credential,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
            )
            refresh_results.append(recent_result)
            if not recent_result.ok:
                recent_result = existing.recent_result

        selection_probe = resolve_achievement_pulse(
            recent_result=recent_result,
            achievement_results={},
            selection=selection,
            library_result=existing.library_result,
        )
        if selection_probe.appid is not None:
            refresh_results.append(_fetch_and_cache(
                profile_key=profile_key,
                cache_key=achievement_cache_key_for_app(selection_probe.appid),
                source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
                credential=credential,
                appid=selection_probe.appid,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
            ))
        snapshot = load_achievement_pulse_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
        )
        needs_attention = any(
            result.status == SteamResultStatus.UNAUTHORIZED
            for result in refresh_results
        )
        return AchievementPulseRefreshOutcome(
            snapshot=snapshot,
            connection_needs_attention=needs_attention,
        )


def _fetch_and_cache(
    *,
    profile_key: str,
    cache_key: str,
    source_id: SteamSourceId,
    credential: SteamCredentialPayload,
    profile: str | None,
    root: Path | None,
    opener,
    now: float,
    appid: int | None = None,
) -> SteamResult:
    """Fetch one allowed source and only freshen its cache on success."""
    from core.steam.backend import build_endpoint, fetch_json
    from core.steam.cache import write_success_result

    request_key = SteamRequestKey.from_params(
        profile_key=profile_key,
        source_id=source_id,
        category="achievement_pulse",
        appid=appid,
    )
    decision = _refresh_backoff.check(request_key, now=now)
    if not decision.allowed:
        return backoff_result(request_key, decision)
    handle = _refresh_coordinator.begin(request_key)
    cache_path = cache_path_for_profile_key(profile_key, cache_key, profile=profile, root=root)
    if not handle.owner:
        return read_cache_record(cache_path)
    endpoint_params = {"appid": appid} if appid is not None else {}
    endpoint = build_endpoint(
        source_id,
        api_key=credential.api_key,
        steamid=credential.profile_identifier,
        **endpoint_params,
    )
    result = _refresh_coordinator.complete(handle, fetch_json(endpoint, opener=opener))
    _refresh_backoff.record_result(request_key, result, now=now)
    if result.ok:
        cached = read_cache_record(cache_path)
        if cached.ok and cached.source_id == result.source_id and cached.payload == result.payload:
            return result
        write_success_result(path=cache_path, cache_key=cache_key, result=result, fetched_at=now)
    return result


def _refresh_lock_for(profile_key: str) -> threading.Lock:
    with _refresh_locks_guard:
        lock = _refresh_locks.get(profile_key)
        if lock is None:
            lock = threading.Lock()
            _refresh_locks[profile_key] = lock
        return lock
