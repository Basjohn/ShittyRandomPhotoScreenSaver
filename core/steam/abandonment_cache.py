"""Cache-first provider adapter for Steam Abandonment Issues."""
from __future__ import annotations

import hashlib
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.settings.storage_paths import get_steam_cache_dir
from core.steam.abandonment_issues import (
    AbandonmentAchievementProgress,
    AbandonmentCandidate,
    AbandonmentResolved,
    AbandonmentSelection,
    achievement_progress_from_result,
    build_abandonment_candidates,
    parse_appid_list,
    resolve_abandonment_issues,
)
from core.steam.achievement_pulse_cache import (
    OWNED_GAMES_CACHE_KEY,
    RECENT_GAMES_CACHE_KEY,
    achievement_cache_key_for_app,
)
from core.steam.cache import (
    cache_path_for_profile_key,
    read_cache_record,
    write_success_result,
)
from core.steam.credentials import SteamCredentialPayload, derive_profile_cache_key
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.steam.profile_state import (
    SteamProfilePolicyState,
    read_profile_state,
    write_profile_state,
)
from core.steam.request_policy import (
    SteamBackoffPolicy,
    SteamRequestCoordinator,
    SteamRequestKey,
    backoff_result,
)


ABANDONMENT_ROTATION_STATE_KEY = "abandonment_issues"
ABANDONMENT_COOLDOWN_PREFIX = "abandonment_issues:"
DEFAULT_ROTATION_INTERVAL_MINUTES = 30
_DISPLAY_FOLLOWER_FRESH_SECONDS = 60.0
DEFAULT_OWNED_GAMES_FRESH_SECONDS = 24.0 * 60.0 * 60.0
DEFAULT_RECENT_GAMES_FRESH_SECONDS = 10.0 * 60.0
MAX_CACHED_ACHIEVEMENT_PROBES = 12
_request_coordinator = SteamRequestCoordinator()
_request_backoff = SteamBackoffPolicy()
_profile_locks: dict[str, threading.RLock] = {}
_profile_locks_guard = threading.Lock()


@dataclass(frozen=True)
class AbandonmentCacheSnapshot:
    """One profile-coordinated cache resolution."""

    resolved: AbandonmentResolved
    owned_result: SteamResult
    recent_result: SteamResult
    cache_age_seconds: float | None

    @property
    def has_usable_cache(self) -> bool:
        return self.owned_result.ok


@dataclass(frozen=True)
class AbandonmentRefreshOutcome:
    """Refresh result that preserves old cache on source failures."""

    snapshot: AbandonmentCacheSnapshot
    connection_needs_attention: bool = False


def load_owned_game_choices_from_cache(
    *,
    profile_key: str,
    profile: str | None = None,
    root: Path | None = None,
    limit: int = 1_000,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> tuple[tuple[int, str], ...]:
    """Return a bounded local-library picker payload without provider work."""

    result = read_record(
        cache_path_for_profile_key(
            profile_key,
            OWNED_GAMES_CACHE_KEY,
            profile=profile,
            root=root,
        )
    )
    rows = _game_rows(result)
    choices: list[tuple[int, str]] = []
    for row in rows:
        appid = _positive_int(row.get("appid"))
        if appid is None:
            continue
        name = row.get("name")
        title = " ".join(name.split()) if isinstance(name, str) and name.strip() else f"App {appid}"
        choices.append((appid, title))
    choices.sort(key=lambda choice: (choice[1].casefold(), choice[0]))
    return tuple(choices[: max(1, min(5_000, int(limit)))])


def load_abandonment_cache_snapshot(
    *,
    profile_key: str,
    selection: AbandonmentSelection = AbandonmentSelection(),
    profile: str | None = None,
    root: Path | None = None,
    now: float | None = None,
    advance_rotation: bool = False,
    rotation_interval_minutes: int = DEFAULT_ROTATION_INTERVAL_MINUTES,
    read_record: Callable[[Path], SteamResult] = read_cache_record,
) -> AbandonmentCacheSnapshot:
    """Resolve one card from local cache and profile policy state only."""

    reference_now = time.time() if now is None else float(now)
    lock = _profile_lock_for(profile_key)
    with lock:
        owned_result = read_record(
            cache_path_for_profile_key(
                profile_key,
                OWNED_GAMES_CACHE_KEY,
                profile=profile,
                root=root,
            )
        )
        recent_result = read_record(
            cache_path_for_profile_key(
                profile_key,
                RECENT_GAMES_CACHE_KEY,
                profile=profile,
                root=root,
            )
        )
        state_path = _profile_state_path(profile_key, profile=profile, root=root)
        state = read_profile_state(state_path)
        rotation = state.rotations.get(ABANDONMENT_ROTATION_STATE_KEY, {})
        if not isinstance(rotation, Mapping):
            rotation = {}
        current_appid = _positive_int(rotation.get("appid"))
        changed_at = _float_or_zero(rotation.get("changed_at"))
        policy_signature = _selection_policy_signature(selection)
        if rotation.get("policy_signature") != policy_signature:
            current_appid = None
            changed_at = 0.0
        rotation_seconds = max(5, int(rotation_interval_minutes)) * 60
        rotation_due = bool(
            advance_rotation
            and (changed_at <= 0.0 or reference_now - changed_at >= rotation_seconds)
        )
        exposures = _exposure_timestamps(state.cooldowns)
        base_candidates = build_abandonment_candidates(
            owned_result=owned_result,
            recent_result=recent_result,
            selection=selection,
            now=reference_now,
        )
        achievement_progress = _load_cached_achievement_progress(
            profile_key=profile_key,
            candidates=base_candidates,
            preferred_appids=(current_appid, _positive_int(selection.pinned_appid)),
            profile=profile,
            root=root,
            read_record=read_record,
        )
        resolved = resolve_abandonment_issues(
            owned_result=owned_result,
            recent_result=recent_result,
            selection=selection,
            now=reference_now,
            current_appid=current_appid,
            advance_rotation=rotation_due,
            exposure_timestamps=exposures,
            achievement_progress_by_appid=achievement_progress,
        )

        if selection.mode != "pinned_game" and resolved.ok:
            selected_changed = resolved.appid != current_appid
            if selected_changed or rotation_due or changed_at <= 0.0:
                rotations = dict(state.rotations)
                rotations[ABANDONMENT_ROTATION_STATE_KEY] = {
                    "appid": resolved.appid,
                    "changed_at": reference_now,
                    "policy_signature": policy_signature,
                }
                cooldowns = dict(state.cooldowns)
                if selected_changed or changed_at <= 0.0:
                    cooldowns[f"{ABANDONMENT_COOLDOWN_PREFIX}{resolved.appid}"] = reference_now
                state = SteamProfilePolicyState(
                    rotations=rotations,
                    cooldowns=cooldowns,
                    dismissals=state.dismissals,
                    updated_at=reference_now,
                )
                write_profile_state(state_path, state)

        timestamps = [
            result.fetched_at
            for result in (owned_result, recent_result)
            if result.ok and result.fetched_at is not None
        ]
        cache_age_seconds = (
            max(0.0, reference_now - min(timestamps)) if timestamps else None
        )
        return AbandonmentCacheSnapshot(
            resolved=resolved,
            owned_result=owned_result,
            recent_result=recent_result,
            cache_age_seconds=cache_age_seconds,
        )


def refresh_abandonment_cache(
    *,
    credential: SteamCredentialPayload,
    selection: AbandonmentSelection = AbandonmentSelection(),
    profile: str | None = None,
    root: Path | None = None,
    opener=None,
    now: float | None = None,
    force: bool = False,
    rotation_interval_minutes: int = DEFAULT_ROTATION_INTERVAL_MINUTES,
    owned_fresh_seconds: float = DEFAULT_OWNED_GAMES_FRESH_SECONDS,
    recent_fresh_seconds: float = DEFAULT_RECENT_GAMES_FRESH_SECONDS,
) -> AbandonmentRefreshOutcome:
    """Refresh owned/recent sources through the shared cache boundary."""

    profile_key = derive_profile_cache_key(credential.profile_identifier)
    reference_now = time.time() if now is None else float(now)
    lock = _profile_lock_for(profile_key)
    with lock:
        refresh_results = [
            _fetch_and_cache(
                profile_key=profile_key,
                cache_key=OWNED_GAMES_CACHE_KEY,
                source_id=SteamSourceId.OWNED_GAMES,
                credential=credential,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
                force=force,
                fresh_seconds=owned_fresh_seconds,
                include_appinfo=True,
                include_played_free_games=True,
            ),
            _fetch_and_cache(
                profile_key=profile_key,
                cache_key=RECENT_GAMES_CACHE_KEY,
                source_id=SteamSourceId.RECENTLY_PLAYED,
                credential=credential,
                profile=profile,
                root=root,
                opener=opener,
                now=reference_now,
                force=force,
                fresh_seconds=recent_fresh_seconds,
                count=20,
            ),
        ]
        snapshot = load_abandonment_cache_snapshot(
            profile_key=profile_key,
            selection=selection,
            profile=profile,
            root=root,
            now=reference_now,
            rotation_interval_minutes=rotation_interval_minutes,
        )
        return AbandonmentRefreshOutcome(
            snapshot=snapshot,
            connection_needs_attention=any(
                result.status == SteamResultStatus.UNAUTHORIZED
                for result in refresh_results
            ),
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
    force: bool,
    fresh_seconds: float,
    **params: Any,
) -> SteamResult:
    from core.steam.cache import get_steam_source_refresh_lock

    with get_steam_source_refresh_lock(profile_key, cache_key):
        return _fetch_and_cache_unlocked(
            profile_key=profile_key,
            cache_key=cache_key,
            source_id=source_id,
            credential=credential,
            profile=profile,
            root=root,
            opener=opener,
            now=now,
            force=force,
            fresh_seconds=fresh_seconds,
            **params,
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
    force: bool,
    fresh_seconds: float,
    **params: Any,
) -> SteamResult:
    from core.steam.backend import build_endpoint, fetch_json

    cache_path = cache_path_for_profile_key(
        profile_key,
        cache_key,
        profile=profile,
        root=root,
    )
    cached = read_cache_record(cache_path)
    freshness_window = max(_DISPLAY_FOLLOWER_FRESH_SECONDS, float(fresh_seconds))
    if (
        not force
        and cached.ok
        and cached.fetched_at is not None
        and 0.0 <= now - cached.fetched_at < freshness_window
    ):
        return cached

    request_key = SteamRequestKey.from_params(
        profile_key=profile_key,
        source_id=source_id,
        category="abandonment_issues",
    )
    decision = _request_backoff.check(request_key, now=now)
    if not decision.allowed:
        return backoff_result(request_key, decision)
    handle = _request_coordinator.begin(request_key)
    if not handle.owner:
        return cached
    endpoint = build_endpoint(
        source_id,
        api_key=credential.api_key,
        steamid=credential.profile_identifier,
        **params,
    )
    result = _request_coordinator.complete(handle, fetch_json(endpoint, opener=opener))
    _request_backoff.record_result(request_key, result, now=now)
    if result.ok:
        write_success_result(
            path=cache_path,
            cache_key=cache_key,
            result=result,
            fetched_at=now,
        )
    return result


def _profile_state_path(
    profile_key: str,
    *,
    profile: str | None,
    root: Path | None,
) -> Path:
    cache_root = root or get_steam_cache_dir(profile=profile, profile_key=profile_key)
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root / "profile_state.json"


def _load_cached_achievement_progress(
    *,
    profile_key: str,
    candidates: tuple[AbandonmentCandidate, ...],
    preferred_appids: tuple[int | None, ...],
    profile: str | None,
    root: Path | None,
    read_record: Callable[[Path], SteamResult],
) -> dict[int, AbandonmentAchievementProgress]:
    """Probe a bounded shortlist of exact cache paths without source work."""

    appids: list[int] = []
    for appid in (*preferred_appids, *(candidate.appid for candidate in candidates)):
        resolved_appid = _positive_int(appid)
        if resolved_appid is None or resolved_appid in appids:
            continue
        appids.append(resolved_appid)
        if len(appids) >= MAX_CACHED_ACHIEVEMENT_PROBES:
            break

    progress_by_appid: dict[int, AbandonmentAchievementProgress] = {}
    for appid in appids:
        result = read_record(
            cache_path_for_profile_key(
                profile_key,
                achievement_cache_key_for_app(appid),
                profile=profile,
                root=root,
            )
        )
        progress = achievement_progress_from_result(result)
        if progress is not None:
            progress_by_appid[appid] = progress
    return progress_by_appid


def _selection_policy_signature(selection: AbandonmentSelection) -> str:
    values = (
        "ranking-v2",
        str(max(0, int(selection.minimum_playtime_minutes))),
        str(max(1, int(selection.preferred_max_playtime_minutes))),
        str(max(0, int(selection.preferred_max_unlocked_achievements))),
        str(max(0, int(selection.minimum_inactivity_days))),
        str(max(0, int(selection.preferred_minimum_inactivity_days))),
        ",".join(str(appid) for appid in parse_appid_list(selection.never_show_appids)),
    )
    return hashlib.sha256("|".join(values).encode("ascii", errors="ignore")).hexdigest()[:16]


def _profile_lock_for(profile_key: str) -> threading.RLock:
    with _profile_locks_guard:
        lock = _profile_locks.get(profile_key)
        if lock is None:
            lock = threading.RLock()
            _profile_locks[profile_key] = lock
        return lock


def _exposure_timestamps(cooldowns: Mapping[str, float]) -> dict[int, float]:
    exposures: dict[int, float] = {}
    for key, value in cooldowns.items():
        if not str(key).startswith(ABANDONMENT_COOLDOWN_PREFIX):
            continue
        appid = _positive_int(str(key)[len(ABANDONMENT_COOLDOWN_PREFIX) :])
        if appid is not None:
            exposures[appid] = _float_or_zero(value)
    return exposures


def _game_rows(result: SteamResult) -> tuple[Mapping[str, Any], ...]:
    if not result.ok or not isinstance(result.payload, Mapping):
        return ()
    response = result.payload.get("response")
    games = response.get("games") if isinstance(response, Mapping) else None
    if not isinstance(games, list):
        return ()
    return tuple(row for row in games if isinstance(row, Mapping))


def _positive_int(value: object) -> int | None:
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return None
    return resolved if resolved > 0 else None


def _float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
