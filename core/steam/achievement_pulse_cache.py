"""Cache-first Achievement Pulse snapshot assembly.

This adapter consumes only account-private, versioned cache records addressed
by their opaque profile key.  It never decrypts credentials, starts provider
work, or touches Qt, so service widgets can paint trustworthy cached content
before deciding whether a refresh is appropriate.
"""
from __future__ import annotations

import time
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from core.steam.achievement_pulse import (
    AchievementPulseResolved,
    AchievementPulseSelection,
    recent_game_appids,
    recent_game_titles,
    resolve_achievement_pulse,
)
from core.logging.logger import get_logger
from core.settings.storage_paths import ProfileRef
from core.steam.cache import cache_path_for_profile_key, read_cache_record
from core.steam.achievement_pulse_history import (
    cached_achievement_candidates,
    persist_achievement_history,
)
from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.request_policy import (
    SteamBackoffPolicy,
    SteamRequestCoordinator,
    SteamRequestKey,
    backoff_result,
)

logger = get_logger(__name__)

RECENT_GAMES_CACHE_KEY = "achievement_pulse_recent_games"
OWNED_GAMES_CACHE_KEY = "achievement_pulse_owned_games"
ACHIEVEMENTS_CACHE_KEY_PREFIX = "achievement_pulse_achievements_"
ACHIEVEMENT_SCHEMA_CACHE_KEY_PREFIX = "achievement_pulse_schema_"
_REFRESH_FRESH_WINDOW_SECONDS = 60.0
DEFAULT_SOURCE_FRESH_SECONDS = 10.0 * 60.0
OWNED_GAMES_FRESH_SECONDS = 24.0 * 60.0 * 60.0
RECENT_ACHIEVEMENT_CANDIDATE_LIMIT = 5
_refresh_coordinator = SteamRequestCoordinator()
_refresh_backoff = SteamBackoffPolicy()
_refresh_locks: dict[str, threading.Lock] = {}
_refresh_locks_guard = threading.Lock()
_RefreshIdentity = tuple[str, str, str, str, int | None]
_refresh_success_at: dict[_RefreshIdentity, float] = {}
_refresh_success_guard = threading.Lock()


@dataclass(frozen=True)
class AchievementPulseCacheSnapshot:
    """One cache-only resolution plus the source timestamps it depended on."""

    resolved: AchievementPulseResolved
    recent_result: SteamResult
    library_result: SteamResult
    achievement_result: SteamResult | None
    achievement_results: tuple[tuple[int, SteamResult], ...]
    schema_result: SteamResult | None
    cache_age_seconds: float | None
    candidate_cache_complete: bool

    @property
    def has_usable_cache(self) -> bool:
        return bool(
            self.recent_result.ok
            or self.library_result.ok
            or (self.achievement_result is not None and self.achievement_result.ok)
            or any(result.ok for _appid, result in self.achievement_results)
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


def achievement_schema_cache_key_for_app(appid: int) -> str:
    """Return a stable cache key for one app's achievement display schema."""
    return f"{ACHIEVEMENT_SCHEMA_CACHE_KEY_PREFIX}{max(0, int(appid))}"


def _selection_candidate_appids(
    recent_result: SteamResult,
    selection: AchievementPulseSelection,
) -> tuple[int, ...]:
    if selection.mode == "custom":
        try:
            appid = int(selection.custom_appid or 0)
        except (TypeError, ValueError):
            return ()
        return (appid,) if appid > 0 else ()
    return recent_game_appids(
        recent_result,
        limit=RECENT_ACHIEVEMENT_CANDIDATE_LIMIT,
    )


def _read_candidate_achievement_results(
    *,
    profile_key: str,
    appids: tuple[int, ...],
    profile: str | None,
    root: Path | None,
    read_record: Callable[[Path], SteamResult],
) -> dict[int, SteamResult]:
    return {
        appid: read_record(
            cache_path_for_profile_key(
                profile_key,
                achievement_cache_key_for_app(appid),
                profile=profile,
                root=root,
            )
        )
        for appid in appids
    }


def _resolved_candidate_result(
    *,
    profile_key: str,
    recent_result: SteamResult,
    profile: ProfileRef,
    root: Path | None,
    read_record: Callable[[Path], SteamResult],
) -> SteamResult:
    """Combine the current rolling discovery window with durable local history.

    This projection is for card selection only.  Its source/cache provenance
    remains separate from the raw recently-played response used for freshness
    and network admissions.
    """
    candidates = cached_achievement_candidates(
        profile_key=profile_key,
        recent_result=recent_result,
        profile=profile,
        root=root,
        read_record=read_record,
    )
    if not candidates:
        return recent_result
    return SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=SteamSourceId.RECENTLY_PLAYED,
        payload={"response": {"games": list(candidates)}},
        from_cache=True,
        fetched_at=recent_result.fetched_at,
    )


def load_recent_game_titles_from_cache(
    *,
    profile_key: str,
    profile: ProfileRef = None,
    root: Path | None = None,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> tuple[str, ...]:
    """Read only the bounded recent-games record for Settings display labels."""

    result = read_record(
        cache_path_for_profile_key(
            profile_key,
            RECENT_GAMES_CACHE_KEY,
            profile=profile,
            root=root,
        )
    )
    candidates = _resolved_candidate_result(
        profile_key=profile_key,
        recent_result=result,
        profile=profile,
        root=root,
        read_record=read_record,
    )
    achievement_results = _read_candidate_achievement_results(
        profile_key=profile_key,
        appids=recent_game_appids(
            candidates,
            limit=RECENT_ACHIEVEMENT_CANDIDATE_LIMIT,
        ),
        profile=profile,
        root=root,
        read_record=read_record,
    )
    return recent_game_titles(
        candidates,
        achievement_results=achievement_results,
        limit=5,
    )


def load_achievement_pulse_cache_snapshot(
    *,
    profile_key: str,
    selection: AchievementPulseSelection = AchievementPulseSelection(),
    profile: ProfileRef = None,
    root: Path | None = None,
    now: float | None = None,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> AchievementPulseCacheSnapshot:
    """Resolve the selected Achievement Pulse state from cache records only."""
    recent_result = read_record(
        cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, profile=profile, root=root)
    )
    library_result = read_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, profile=profile, root=root)
    )
    candidate_result = _resolved_candidate_result(
        profile_key=profile_key,
        recent_result=recent_result,
        profile=profile,
        root=root,
        read_record=read_record,
    )
    candidate_appids = _selection_candidate_appids(candidate_result, selection)
    achievement_results = _read_candidate_achievement_results(
        profile_key=profile_key,
        appids=candidate_appids,
        profile=profile,
        root=root,
        read_record=read_record,
    )
    selection_probe = resolve_achievement_pulse(
        recent_result=candidate_result,
        achievement_results=achievement_results,
        selection=selection,
        library_result=library_result,
        playtime_recent_result=recent_result,
    )
    achievement_result = achievement_results.get(selection_probe.appid)
    schema_result: SteamResult | None = None
    if selection_probe.appid is not None:
        schema_result = read_record(
            cache_path_for_profile_key(
                profile_key,
                achievement_schema_cache_key_for_app(selection_probe.appid),
                profile=profile,
                root=root,
            )
        )
    resolved = resolve_achievement_pulse(
        recent_result=candidate_result,
        achievement_results=achievement_results,
        selection=selection,
        library_result=library_result,
        schema_result=schema_result,
        playtime_recent_result=recent_result,
    )
    timestamp_results = (
        *((recent_result,) if selection.mode != "custom" else ()),
        *achievement_results.values(),
        schema_result,
    )
    timestamps = [
        result.fetched_at
        for result in timestamp_results
        if result is not None and result.ok and result.fetched_at is not None
    ]
    reference_now = time.time() if now is None else float(now)
    cache_age_seconds = max(0.0, reference_now - min(timestamps)) if timestamps else None
    return AchievementPulseCacheSnapshot(
        resolved=resolved,
        recent_result=recent_result,
        library_result=library_result,
        achievement_result=achievement_result,
        achievement_results=tuple(achievement_results.items()),
        schema_result=schema_result,
        cache_age_seconds=cache_age_seconds,
        candidate_cache_complete=(
            (selection.mode == "custom" or recent_result.ok)
            and all(result.ok for result in achievement_results.values())
            and (selection_probe.appid is None or bool(schema_result and schema_result.ok))
        ),
    )


def refresh_achievement_pulse_cache(
    *,
    credential: SteamCredentialPayload,
    selection: AchievementPulseSelection = AchievementPulseSelection(),
    profile: ProfileRef = None,
    root: Path | None = None,
    opener=None,
    now: float | None = None,
    force: bool = False,
    source_fresh_seconds: float = DEFAULT_SOURCE_FRESH_SECONDS,
) -> AchievementPulseRefreshOutcome:
    """Refresh the selected app through the cache boundary without owning scheduling.

    Callers must run this explicit IO operation through ``ThreadManager``.
    Concurrent display instances share a profile lock; a follower returns the
    freshly written cache instead of issuing a duplicate startup request.
    """
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    reference_now = time.time() if now is None else float(now)
    refresh_identity = _refresh_identity(
        profile_key=profile_key,
        selection=selection,
        profile=profile,
        root=root,
    )
    lock = _refresh_lock_for(profile_key)
    with lock:
        source_fresh_window = max(
            _REFRESH_FRESH_WINDOW_SECONDS,
            float(source_fresh_seconds),
        )
        existing = load_achievement_pulse_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
        )
        needs_owned_refresh = (
            existing.resolved.appid is not None
            and existing.resolved.playtime_forever_minutes is None
            and _owned_games_cache_expired(existing.library_result, now=reference_now)
        )
        if (
            not force
            and not needs_owned_refresh
            and (
                (
                    existing.candidate_cache_complete
                    and existing.cache_age_seconds is not None
                    and existing.cache_age_seconds < source_fresh_window
                )
                or _has_recent_success(refresh_identity, now=reference_now)
            )
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
                fresh_seconds=0.0 if force else source_fresh_window,
            )
            refresh_results.append(recent_result)
            if recent_result.ok:
                # The successful transport result has no fetched_at yet.
                # Re-read its just-persisted source record so the history's
                # last-seen ordering uses the actual cache timestamp.
                recent_result = read_cache_record(cache_path_for_profile_key(
                    profile_key, RECENT_GAMES_CACHE_KEY, profile=profile, root=root
                ))
            else:
                recent_result = existing.recent_result

        candidate_appids = _selection_candidate_appids(recent_result, selection)
        current_recent_count = len(candidate_appids) if selection.mode != "custom" else 0
        if selection.mode != "custom" and not candidate_appids:
            # Steam can return a successful empty rolling recent-play window.
            # Keep discovering changes in at most five previously cached apps;
            # never scan the whole library or invent a global unlock feed.
            candidate_appids = recent_game_appids(
                _resolved_candidate_result(
                    profile_key=profile_key,
                    recent_result=recent_result,
                    profile=profile,
                    root=root,
                    read_record=read_cache_record,
                ),
                limit=RECENT_ACHIEVEMENT_CANDIDATE_LIMIT,
            )
        if selection.mode != "custom":
            logger.info(
                "[STEAM][ACHIEVEMENT_PULSE] Source selection recent_status=%s recent_candidates=%d "
                "refresh_candidates=%d historical_fallback=%s",
                recent_result.status.value,
                current_recent_count,
                len(candidate_appids),
                bool(not current_recent_count and candidate_appids),
            )
        for appid in candidate_appids:
            refresh_results.append(_fetch_and_cache(
                profile_key=profile_key,
                cache_key=achievement_cache_key_for_app(appid),
                source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
                credential=credential,
                appid=appid,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
                fresh_seconds=0.0 if force else source_fresh_window,
            ))

        provisional = load_achievement_pulse_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
        )
        if (
            provisional.resolved.appid is not None
            and provisional.resolved.playtime_forever_minutes is None
            and _owned_games_cache_expired(provisional.library_result, now=reference_now)
        ):
            # Only a missing playtime triggers an owned-library request. This
            # source is shared with Abandonment Issues and is limited to one
            # successful refresh per 24 hours, including manual Pulse refresh.
            refresh_results.append(_fetch_and_cache(
                profile_key=profile_key,
                cache_key=OWNED_GAMES_CACHE_KEY,
                source_id=SteamSourceId.OWNED_GAMES,
                credential=credential,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
                fresh_seconds=OWNED_GAMES_FRESH_SECONDS,
            ))
        if selection.mode != "custom":
            persist_achievement_history(
                profile_key=profile_key,
                recent_result=recent_result,
                observed_appids=candidate_appids,
                profile=profile,
                root=root,
                now=reference_now,
            )
        provisional = load_achievement_pulse_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
        )
        selected_appid = provisional.resolved.appid
        if selected_appid is not None:
            refresh_results.append(_fetch_and_cache(
                profile_key=profile_key,
                cache_key=achievement_schema_cache_key_for_app(selected_appid),
                source_id=SteamSourceId.ACHIEVEMENT_SCHEMA,
                credential=credential,
                appid=selected_appid,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
                fresh_seconds=0.0 if force else source_fresh_window,
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
        if refresh_results and all(result.ok for result in refresh_results):
            _record_refresh_success(refresh_identity, now=reference_now)
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
    fresh_seconds: float = DEFAULT_SOURCE_FRESH_SECONDS,
) -> SteamResult:
    from core.steam.cache import get_steam_source_refresh_lock

    with get_steam_source_refresh_lock(profile_key, cache_key):
        cache_path = cache_path_for_profile_key(
            profile_key,
            cache_key,
            profile=profile,
            root=root,
        )
        cached = read_cache_record(cache_path)
        if (
            fresh_seconds > 0.0
            and cached.ok
            and cached.fetched_at is not None
            and 0.0 <= now - cached.fetched_at < float(fresh_seconds)
        ):
            return cached
        return _fetch_and_cache_unlocked(
            profile_key=profile_key,
            cache_key=cache_key,
            source_id=source_id,
            credential=credential,
            profile=profile,
            root=root,
            opener=opener,
            now=now,
            appid=appid,
        )


def _fetch_and_cache_unlocked(
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
    if source_id == SteamSourceId.OWNED_GAMES:
        endpoint_params.update(include_appinfo=True, include_played_free_games=True)
    endpoint = build_endpoint(
        source_id,
        api_key=credential.api_key,
        steamid=credential.profile_identifier,
        **endpoint_params,
    )
    result = _refresh_coordinator.complete(handle, fetch_json(endpoint, opener=opener))
    if result.ok and source_id == SteamSourceId.RECENTLY_PLAYED:
        payload = result.payload
        response = payload.get("response") if isinstance(payload, Mapping) else None
        if not isinstance(response, Mapping) or (
            "games" in response and not isinstance(response["games"], list)
        ):
            # An empty *valid* game list is fine, but a 200 error envelope
            # must not destroy the last truthful recent-play discovery record.
            result = SteamResult(
                status=SteamResultStatus.INVALID_RESPONSE,
                source_id=source_id,
                message="Steam did not return a recognizable recently-played response.",
                attempted_sources=(source_id,),
            )
            logger.warning(
                "[STEAM][ACHIEVEMENT_PULSE] Invalid recent-play response; "
                "last-good recent-play cache preserved"
            )
    if result.ok and source_id == SteamSourceId.PLAYER_ACHIEVEMENTS:
        payload = result.payload
        playerstats = payload.get("playerstats") if isinstance(payload, Mapping) else None
        if (
            not isinstance(playerstats, Mapping)
            or playerstats.get("success") is False
            or not isinstance(playerstats.get("achievements"), list)
        ):
            # HTTP 200 with Steam's per-app error/empty envelope is not a
            # successful achievement snapshot.  Never overwrite last-good
            # unlock data with it.
            result = SteamResult(
                status=SteamResultStatus.INVALID_RESPONSE,
                source_id=source_id,
                message="Steam did not return a usable per-app achievement list.",
                attempted_sources=(source_id,),
            )
            logger.warning(
                "[STEAM][ACHIEVEMENT_PULSE] Per-app HTTP success contained no usable achievement rows; "
                "last-good cache preserved"
            )
    _refresh_backoff.record_result(request_key, result, now=now)
    if result.ok:
        write_success_result(path=cache_path, cache_key=cache_key, result=result, fetched_at=now)
    return result


def _owned_games_cache_expired(result: SteamResult, *, now: float) -> bool:
    if not result.ok or result.source_id != SteamSourceId.OWNED_GAMES or result.fetched_at is None:
        return True
    age = now - result.fetched_at
    return not (0.0 <= age < OWNED_GAMES_FRESH_SECONDS)


def _refresh_lock_for(profile_key: str) -> threading.Lock:
    with _refresh_locks_guard:
        lock = _refresh_locks.get(profile_key)
        if lock is None:
            lock = threading.Lock()
            _refresh_locks[profile_key] = lock
        return lock


def _refresh_identity(
    *,
    profile_key: str,
    selection: AchievementPulseSelection,
    profile: str | None,
    root: Path | None,
) -> _RefreshIdentity:
    return (
        profile_key,
        str(profile or ""),
        str(root or ""),
        selection.mode,
        selection.custom_appid,
    )


def _has_recent_success(identity: _RefreshIdentity, *, now: float) -> bool:
    with _refresh_success_guard:
        completed_at = _refresh_success_at.get(identity)
        if completed_at is None:
            return False
        age = now - completed_at
        if 0.0 <= age < _REFRESH_FRESH_WINDOW_SECONDS:
            return True
        _refresh_success_at.pop(identity, None)
        return False


def _record_refresh_success(identity: _RefreshIdentity, *, now: float) -> None:
    with _refresh_success_guard:
        expired = [
            key
            for key, completed_at in _refresh_success_at.items()
            if not 0.0 <= now - completed_at < _REFRESH_FRESH_WINDOW_SECONDS
        ]
        for key in expired:
            _refresh_success_at.pop(key, None)
        _refresh_success_at[identity] = now
