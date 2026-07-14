"""Pure candidate selection for the Steam Abandonment Issues card.

The resolver consumes normalized cache/provider envelopes only. It does not
perform IO, touch credentials, schedule work, or depend on Qt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from core.steam.models import SteamResult, SteamResultStatus


LAST_PLAYED_VERIFIED = "verified"
LAST_PLAYED_UNKNOWN = "unknown"
DEFAULT_MINIMUM_PLAYTIME_MINUTES = 15
DEFAULT_PREFERRED_MAX_PLAYTIME_MINUTES = 2 * 60
DEFAULT_PREFERRED_MAX_UNLOCKED_ACHIEVEMENTS = 2
DEFAULT_MINIMUM_INACTIVITY_DAYS = 12 * 7
DEFAULT_PREFERRED_MINIMUM_INACTIVITY_DAYS = 26 * 7
DEFAULT_EXPOSURE_COOLDOWN_DAYS = 7
MINIMUM_REASONABLE_STEAM_TIMESTAMP = 946_684_800  # 2000-01-01 UTC
MAXIMUM_FUTURE_SKEW_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class AbandonmentSelection:
    """Persisted, non-secret selection policy for Abandonment Issues."""

    mode: str = "smart_rotation"
    pinned_appid: int | None = None
    minimum_playtime_minutes: int = DEFAULT_MINIMUM_PLAYTIME_MINUTES
    preferred_max_playtime_minutes: int = DEFAULT_PREFERRED_MAX_PLAYTIME_MINUTES
    preferred_max_unlocked_achievements: int = DEFAULT_PREFERRED_MAX_UNLOCKED_ACHIEVEMENTS
    minimum_inactivity_days: int = DEFAULT_MINIMUM_INACTIVITY_DAYS
    preferred_minimum_inactivity_days: int = DEFAULT_PREFERRED_MINIMUM_INACTIVITY_DAYS
    never_show_appids: tuple[int, ...] = ()


@dataclass(frozen=True)
class AbandonmentAchievementProgress:
    """Optional cache-only ranking evidence from one achievement snapshot."""

    unlocked_count: int
    total_count: int
    latest_unlock_at: float | None = None

    @property
    def likely_complete(self) -> bool:
        return self.total_count > 0 and self.unlocked_count >= self.total_count


@dataclass(frozen=True)
class AbandonmentCandidate:
    """One source-proven game eligible for the rediscovery shelf."""

    appid: int
    title: str
    playtime_minutes: int
    last_played_at: float
    last_played_confidence: str
    inactivity_days: int
    preference_tier: int
    unlocked_achievement_count: int | None
    total_achievement_count: int | None
    score: float
    latest_unlock_at: float | None = None
    latest_unlock_age_days: int | None = None


@dataclass(frozen=True)
class AbandonmentResolved:
    """Cache-safe presentation state for one Abandonment Issues card."""

    status: str
    appid: int | None
    title: str
    playtime_minutes: int | None = None
    last_played_at: float | None = None
    last_played_confidence: str = LAST_PLAYED_UNKNOWN
    inactivity_days: int | None = None
    queue_position: int = 0
    queue_count: int = 0
    selection_mode: str = "smart_rotation"
    pinned: bool = False
    source_label: str = "Cache"
    unavailable_reason: str = ""
    unlocked_achievement_count: int | None = None
    total_achievement_count: int | None = None
    latest_unlock_at: float | None = None
    latest_unlock_age_days: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def parse_appid_list(value: object) -> tuple[int, ...]:
    """Normalize a comma/semicolon/whitespace-separated app-ID preference."""

    if isinstance(value, (list, tuple, set, frozenset)):
        tokens = list(value)
    else:
        normalized = str(value or "").replace(";", ",").replace("\n", ",")
        tokens = [part for group in normalized.split(",") for part in group.split()]
    appids: list[int] = []
    seen: set[int] = set()
    for token in tokens:
        appid = _coerce_positive_int(token)
        if appid is None or appid in seen:
            continue
        seen.add(appid)
        appids.append(appid)
    return tuple(appids)


def format_appid_list(appids: tuple[int, ...]) -> str:
    """Serialize a normalized Never Show list without account metadata."""

    return ", ".join(str(appid) for appid in parse_appid_list(appids))


def build_abandonment_candidates(
    *,
    owned_result: SteamResult | None,
    recent_result: SteamResult | None,
    selection: AbandonmentSelection = AbandonmentSelection(),
    now: float,
    achievement_progress_by_appid: Mapping[int, AbandonmentAchievementProgress] | None = None,
) -> tuple[AbandonmentCandidate, ...]:
    """Return smart-rotation candidates sorted by meaningful rediscovery score."""

    recent_appids = {
        appid
        for row in _game_rows(recent_result)
        if (appid := _coerce_positive_int(row.get("appid"))) is not None
    }
    never_show = set(parse_appid_list(selection.never_show_appids))
    candidates: list[AbandonmentCandidate] = []
    for row in _game_rows(owned_result):
        appid = _coerce_positive_int(row.get("appid"))
        if (
            appid is None
            or appid in recent_appids
            or appid in never_show
            or not _has_game_title(row)
        ):
            continue
        candidate = _candidate_from_row(
            row,
            now=now,
            selection=selection,
            achievement_progress=(achievement_progress_by_appid or {}).get(appid),
        )
        if candidate is None:
            continue
        if candidate.playtime_minutes < max(0, int(selection.minimum_playtime_minutes)):
            continue
        if candidate.inactivity_days < max(0, int(selection.minimum_inactivity_days)):
            continue
        candidates.append(candidate)
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                item.preference_tier,
                -item.score,
                item.title.casefold(),
                item.appid,
            ),
        )
    )


def resolve_abandonment_issues(
    *,
    owned_result: SteamResult | None,
    recent_result: SteamResult | None,
    selection: AbandonmentSelection = AbandonmentSelection(),
    now: float,
    current_appid: int | None = None,
    advance_rotation: bool = False,
    rotation_seed: int = 0,
    exposure_timestamps: Mapping[int, float] | None = None,
    exposure_cooldown_days: int = DEFAULT_EXPOSURE_COOLDOWN_DAYS,
    achievement_progress_by_appid: Mapping[int, AbandonmentAchievementProgress] | None = None,
) -> AbandonmentResolved:
    """Resolve one truthful game without inventing missing play history."""

    mode = _normalize_mode(selection.mode)
    if mode == "pinned_game":
        return _resolve_pinned(
            owned_result=owned_result,
            selection=selection,
            now=now,
            achievement_progress_by_appid=achievement_progress_by_appid,
        )

    candidates = build_abandonment_candidates(
        owned_result=owned_result,
        recent_result=recent_result,
        selection=selection,
        now=now,
        achievement_progress_by_appid=achievement_progress_by_appid,
    )
    if not candidates:
        return AbandonmentResolved(
            status="unavailable",
            appid=None,
            title="Rediscovery Shelf",
            selection_mode=mode,
            source_label=_source_label(owned_result),
            unavailable_reason=_unavailable_reason(owned_result),
        )

    current = next(
        (candidate for candidate in candidates if candidate.appid == _coerce_positive_int(current_appid)),
        None,
    )
    cooldown_seconds = max(0, int(exposure_cooldown_days)) * 24 * 60 * 60
    exposures = exposure_timestamps or {}
    better_unexposed_candidate = bool(
        current is not None
        and any(
            candidate.preference_tier < current.preference_tier
            and not _is_on_cooldown(
                candidate.appid,
                exposures,
                now=now,
                cooldown_seconds=cooldown_seconds,
            )
            for candidate in candidates
        )
    )
    if current is not None and not advance_rotation and not better_unexposed_candidate:
        queue_position = candidates.index(current) + 1
        return _resolved_from_candidate(
            current,
            queue_position=queue_position,
            queue_count=len(candidates),
            mode=mode,
            source_label=_source_label(owned_result),
            pinned=False,
        )

    available = tuple(
        candidate
        for candidate in candidates
        if not _is_on_cooldown(candidate.appid, exposures, now=now, cooldown_seconds=cooldown_seconds)
    )
    rotation_pool = available or candidates
    selected = _select_rotation_candidate(
        candidates=rotation_pool,
        current_appid=(
            None if better_unexposed_candidate else _coerce_positive_int(current_appid)
        ),
        advance=bool(advance_rotation),
        rotation_seed=rotation_seed,
    )
    queue_position = next(
        (index + 1 for index, candidate in enumerate(candidates) if candidate.appid == selected.appid),
        1,
    )
    return _resolved_from_candidate(
        selected,
        queue_position=queue_position,
        queue_count=len(candidates),
        mode=mode,
        source_label=_source_label(owned_result),
        pinned=False,
    )


def _resolve_pinned(
    *,
    owned_result: SteamResult | None,
    selection: AbandonmentSelection,
    now: float,
    achievement_progress_by_appid: Mapping[int, AbandonmentAchievementProgress] | None,
) -> AbandonmentResolved:
    appid = _coerce_positive_int(selection.pinned_appid)
    if appid is None:
        return AbandonmentResolved(
            status="unavailable",
            appid=None,
            title="Pinned Game",
            selection_mode="pinned_game",
            pinned=True,
            source_label=_source_label(owned_result),
            unavailable_reason="Choose a cached owned game to pin.",
        )
    if appid in set(parse_appid_list(selection.never_show_appids)):
        return AbandonmentResolved(
            status="unavailable",
            appid=appid,
            title="Pinned Game",
            selection_mode="pinned_game",
            pinned=True,
            source_label=_source_label(owned_result),
            unavailable_reason="The pinned game is also in Never Show.",
        )
    row = next(
        (
            game
            for game in _game_rows(owned_result)
            if _coerce_positive_int(game.get("appid")) == appid
        ),
        None,
    )
    if row is None:
        return AbandonmentResolved(
            status="unavailable",
            appid=appid,
            title="Pinned Game",
            selection_mode="pinned_game",
            pinned=True,
            source_label=_source_label(owned_result),
            unavailable_reason="The pinned game is not available in the cached owned library.",
        )
    candidate = _candidate_from_row(
        row,
        now=now,
        selection=selection,
        achievement_progress=(achievement_progress_by_appid or {}).get(appid),
    )
    if candidate is None:
        title = _game_title(row, appid)
        return AbandonmentResolved(
            status="unavailable",
            appid=appid,
            title=title,
            playtime_minutes=_coerce_non_negative_int(row.get("playtime_forever")),
            selection_mode="pinned_game",
            pinned=True,
            source_label=_source_label(owned_result),
            unavailable_reason="Previous play history is unavailable for this pinned game.",
        )
    return _resolved_from_candidate(
        candidate,
        queue_position=1,
        queue_count=1,
        mode="pinned_game",
        source_label=_source_label(owned_result),
        pinned=True,
    )


def _candidate_from_row(
    row: Mapping[str, Any],
    *,
    now: float,
    selection: AbandonmentSelection,
    achievement_progress: AbandonmentAchievementProgress | None,
) -> AbandonmentCandidate | None:
    appid = _coerce_positive_int(row.get("appid"))
    playtime = _coerce_non_negative_int(row.get("playtime_forever"))
    last_played = _coerce_timestamp(row.get("rtime_last_played"), now=now)
    if appid is None or playtime is None or last_played is None:
        return None
    inactivity_days = max(0, int((float(now) - last_played) // (24 * 60 * 60)))
    preference_tier = _preference_tier(
        playtime_minutes=playtime,
        inactivity_days=inactivity_days,
        achievement_progress=achievement_progress,
        selection=selection,
    )
    latest_unlock_at = (
        _coerce_timestamp(achievement_progress.latest_unlock_at, now=now)
        if achievement_progress is not None
        else None
    )
    latest_unlock_age_days = (
        max(0, int((float(now) - latest_unlock_at) // (24 * 60 * 60)))
        if latest_unlock_at is not None
        else None
    )
    score = math.log2(inactivity_days + 2.0) * 10.0 + math.log2(playtime + 1.0) * 1.5
    return AbandonmentCandidate(
        appid=appid,
        title=_game_title(row, appid),
        playtime_minutes=playtime,
        last_played_at=last_played,
        last_played_confidence=LAST_PLAYED_VERIFIED,
        inactivity_days=inactivity_days,
        preference_tier=preference_tier,
        unlocked_achievement_count=(
            achievement_progress.unlocked_count if achievement_progress is not None else None
        ),
        total_achievement_count=(
            achievement_progress.total_count if achievement_progress is not None else None
        ),
        score=score,
        latest_unlock_at=latest_unlock_at,
        latest_unlock_age_days=latest_unlock_age_days,
    )


def _resolved_from_candidate(
    candidate: AbandonmentCandidate,
    *,
    queue_position: int,
    queue_count: int,
    mode: str,
    source_label: str,
    pinned: bool,
) -> AbandonmentResolved:
    return AbandonmentResolved(
        status="ok",
        appid=candidate.appid,
        title=candidate.title,
        playtime_minutes=candidate.playtime_minutes,
        last_played_at=candidate.last_played_at,
        last_played_confidence=candidate.last_played_confidence,
        inactivity_days=candidate.inactivity_days,
        queue_position=max(1, int(queue_position)),
        queue_count=max(1, int(queue_count)),
        selection_mode=mode,
        pinned=pinned,
        source_label=source_label,
        unlocked_achievement_count=candidate.unlocked_achievement_count,
        total_achievement_count=candidate.total_achievement_count,
        latest_unlock_at=candidate.latest_unlock_at,
        latest_unlock_age_days=candidate.latest_unlock_age_days,
    )


def achievement_progress_from_result(
    result: SteamResult | None,
) -> AbandonmentAchievementProgress | None:
    """Extract non-authoritative ranking evidence from an existing cache result."""

    if result is None or not result.ok or not isinstance(result.payload, Mapping):
        return None
    playerstats = result.payload.get("playerstats")
    if not isinstance(playerstats, Mapping):
        return None
    rows = playerstats.get("achievements")
    if not isinstance(rows, list):
        return None
    valid_rows = tuple(row for row in rows if isinstance(row, Mapping))
    unlocked = sum(1 for row in valid_rows if _coerce_non_negative_int(row.get("achieved")) == 1)
    latest_unlock_at = max(
        (
            timestamp
            for row in valid_rows
            if _coerce_non_negative_int(row.get("achieved")) == 1
            for timestamp in (_coerce_historical_timestamp(row.get("unlocktime")),)
            if timestamp is not None
        ),
        default=None,
    )
    return AbandonmentAchievementProgress(
        unlocked_count=unlocked,
        total_count=len(valid_rows),
        latest_unlock_at=latest_unlock_at,
    )


def _preference_tier(
    *,
    playtime_minutes: int,
    inactivity_days: int,
    achievement_progress: AbandonmentAchievementProgress | None,
    selection: AbandonmentSelection,
) -> int:
    age_offset = (
        0
        if inactivity_days >= max(0, int(selection.preferred_minimum_inactivity_days))
        else 10
    )
    if achievement_progress is not None and achievement_progress.likely_complete:
        return age_offset + 6
    low_playtime = playtime_minutes < max(1, int(selection.preferred_max_playtime_minutes))
    if achievement_progress is None:
        return age_offset + (1 if low_playtime else 4)
    low_unlocks = (
        achievement_progress.unlocked_count
        <= max(0, int(selection.preferred_max_unlocked_achievements))
    )
    if low_playtime:
        return age_offset + (0 if low_unlocks else 2)
    return age_offset + (3 if low_unlocks else 5)


def _select_rotation_candidate(
    *,
    candidates: tuple[AbandonmentCandidate, ...],
    current_appid: int | None,
    advance: bool,
    rotation_seed: int = 0,
) -> AbandonmentCandidate:
    current_index = next(
        (index for index, candidate in enumerate(candidates) if candidate.appid == current_appid),
        None,
    )
    if current_index is not None and not advance:
        return candidates[current_index]
    pool = (
        tuple(candidate for candidate in candidates if candidate.appid != current_appid)
        if current_index is not None
        else candidates
    )
    if not pool:
        return candidates[current_index or 0]

    # Select a preference tier before a game so a large library cannot
    # overwhelm the strongest rediscovery evidence by candidate count.
    tier_groups: dict[int, list[AbandonmentCandidate]] = {}
    for candidate in pool:
        tier_groups.setdefault(candidate.preference_tier, []).append(candidate)
    best_tier = min(tier_groups)
    weighted_tiers: list[tuple[int, int]] = []
    for tier in sorted(tier_groups):
        delta = max(0, tier - best_tier)
        if delta == 0:
            weight = 64
        elif delta == 1:
            weight = 24
        elif delta == 2:
            weight = 8
        elif delta <= 4:
            weight = 3
        else:
            weight = 1
        weighted_tiers.append((tier, weight))

    seed = abs(int(rotation_seed))
    total_weight = sum(weight for _tier, weight in weighted_tiers)
    draw = seed % total_weight
    selected_tier = weighted_tiers[-1][0]
    for tier, weight in weighted_tiers:
        if draw < weight:
            selected_tier = tier
            break
        draw -= weight
    tier_candidates = tier_groups[selected_tier]
    return tier_candidates[(seed // total_weight) % len(tier_candidates)]


def _is_on_cooldown(
    appid: int,
    exposures: Mapping[int, float],
    *,
    now: float,
    cooldown_seconds: int,
) -> bool:
    if cooldown_seconds <= 0:
        return False
    try:
        exposed_at = float(exposures.get(appid, 0.0))
    except (TypeError, ValueError):
        return False
    age = float(now) - exposed_at
    return 0.0 <= age < cooldown_seconds


def _game_rows(result: SteamResult | None) -> tuple[Mapping[str, Any], ...]:
    if result is None or not result.ok or not isinstance(result.payload, Mapping):
        return ()
    response = result.payload.get("response")
    games = response.get("games") if isinstance(response, Mapping) else result.payload.get("games")
    if not isinstance(games, list):
        return ()
    return tuple(row for row in games if isinstance(row, Mapping))


def _game_title(row: Mapping[str, Any], appid: int) -> str:
    value = row.get("name")
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return f"App {appid}"


def _has_game_title(row: Mapping[str, Any]) -> bool:
    value = row.get("name")
    return isinstance(value, str) and bool(value.strip())


def _coerce_positive_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _coerce_non_negative_int(value: object) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _coerce_timestamp(value: object, *, now: float) -> float | None:
    timestamp = _coerce_historical_timestamp(value)
    if timestamp is None:
        return None
    if timestamp > float(now) + MAXIMUM_FUTURE_SKEW_SECONDS:
        return None
    return timestamp


def _coerce_historical_timestamp(value: object) -> float | None:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(timestamp):
        return None
    if timestamp < MINIMUM_REASONABLE_STEAM_TIMESTAMP:
        return None
    return timestamp


def _normalize_mode(value: object) -> str:
    return "pinned_game" if str(value or "").strip().lower() == "pinned_game" else "smart_rotation"


def _source_label(result: SteamResult | None) -> str:
    return "Cache" if result is not None and result.from_cache else "Steam"


def _unavailable_reason(result: SteamResult | None) -> str:
    if result is None:
        return "The owned-library source has not been cached yet."
    if result.status in {SteamResultStatus.PRIVATE, SteamResultStatus.UNAUTHORIZED}:
        return "Owned game details are private or unavailable."
    if not result.ok:
        return "The owned-library source is unavailable; no play history was inferred."
    return "No cached games meet the current playtime and inactivity thresholds."
