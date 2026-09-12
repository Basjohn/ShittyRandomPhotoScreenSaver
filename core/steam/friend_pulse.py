"""Pure Friend Pulse source parsing and privacy-aware projection.

This module deliberately has no cache, credential, network, Qt, timer, or
runtime-owner dependency. Account-private normalized source state may retain a
SteamID for semantic actions; projected rows never expose it to QML.
"""

from __future__ import annotations

from collections.abc import Collection
from collections import Counter
from dataclasses import dataclass, replace
from typing import Any, Mapping

from core.steam.credentials import safe_fingerprint
from core.steam.models import SteamResult, SteamResultStatus


@dataclass(frozen=True)
class FriendPulseEntry:
    """One neutral playing observation from account-private source state."""

    identity_fingerprint: str
    display_name: str | None = None
    game_appid: int | None = None
    game_name: str | None = None
    avatar_url: str | None = None
    persona_state: int | None = None
    changed: bool = False
    steam_id: str | None = None


@dataclass(frozen=True)
class FriendPulseSnapshot:
    """Immutable accepted state suitable for cache/runtime/presentation seams."""

    status: SteamResultStatus
    accepted_at: float | None = None
    from_cache: bool = False
    stale: bool = False
    authoritative: bool = False
    entries: tuple[FriendPulseEntry, ...] = ()
    playing_count: int | None = None
    online_count: int | None = None

    @property
    def usable(self) -> bool:
        # A coherent cached success remains useful evidence even when its
        # truthful content is "nobody playing". Private/error cache states are
        # never promoted to usable activity.
        return self.authoritative or (
            self.from_cache and self.status == SteamResultStatus.SUCCESS
        )


@dataclass(frozen=True)
class FriendPulseRow:
    """Presentation-safe projected row; never carries an account identifier."""

    primary: str
    secondary: str = ""
    presence_text: str = ""
    online: bool = False
    changed: bool = False
    avatar_url: str | None = None
    count: int = 1
    game_appid: int | None = None
    # Opaque runtime identity for avatar/model reconciliation only.  It is not
    # a SteamID and no QML-facing role need expose it.
    identity_fingerprint: str = ""
    friend_action_available: bool = False


@dataclass(frozen=True)
class FriendPulseProjection:
    state: str
    primary_metric: str
    rows: tuple[FriendPulseRow, ...]
    overflow_count: int = 0


def sanitize_friend_list_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded account-private FriendList cache payload."""

    friends = _friend_rows(payload)
    normalized = {
        steamid: safe_fingerprint(steamid)
        for row in friends
        if (steamid := _steam_id_or_none(row.get("steamid")))
    }
    return {
        "friends": [
            {"identity_fingerprint": fingerprint, "steam_id": steamid}
            for steamid, fingerprint in sorted(
                normalized.items(), key=lambda item: item[1]
            )
        ]
    }


def sanitize_player_summaries_payload(
    payload: Mapping[str, Any],
    *,
    friend_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Sanitize summary rows before cache persistence.

    ``friend_ids`` rejects unrelated response rows. Accepted numeric SteamIDs
    remain only in the user's account-private cache/runtime action state and
    are never projected into a QML role or written to logs.
    """

    allowed = {value for value in friend_ids if value}
    rows: list[dict[str, Any]] = []
    for row in _player_rows(payload):
        steamid = _steam_id_or_none(row.get("steamid"))
        if not steamid or steamid not in allowed:
            continue
        item: dict[str, Any] = {
            "identity_fingerprint": safe_fingerprint(steamid),
            "steam_id": steamid,
        }
        for source_key, target_key in (
            ("personaname", "display_name"),
            ("gameid", "game_appid"),
            ("gameextrainfo", "game_name"),
            ("avatarfull", "avatar_url"),
            ("personastate", "persona_state"),
        ):
            value = row.get(source_key)
            if source_key in {"gameid", "personastate"}:
                value = _int_or_none(value)
            elif source_key != "gameid":
                value = _text(value)
            if value is not None:
                item[target_key] = value
        rows.append(item)
    rows.sort(key=lambda item: str(item["identity_fingerprint"]))
    return {"players": rows}


def friend_ids_from_payload(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Extract unique live IDs for endpoint batching; never use in a model."""

    found: list[str] = []
    for row in _friend_rows(payload):
        steamid = _steam_id_or_none(row.get("steamid"))
        if steamid and steamid not in found:
            found.append(steamid)
    return tuple(found)


def build_friend_pulse_snapshot(
    *,
    friend_result: SteamResult,
    summaries_result: SteamResult | None,
    now: float | None = None,
    previous: FriendPulseSnapshot | None = None,
    stale: bool = False,
) -> FriendPulseSnapshot:
    """Resolve only truthful accepted Friend Pulse state from sanitized results."""

    if not friend_result.ok:
        return FriendPulseSnapshot(
            status=friend_result.status,
            accepted_at=friend_result.fetched_at or now,
            from_cache=friend_result.from_cache,
            stale=stale or friend_result.from_cache,
        )
    if summaries_result is None or not summaries_result.ok:
        status = (
            summaries_result.status
            if summaries_result is not None
            else SteamResultStatus.CACHE_MISS
        )
        return FriendPulseSnapshot(
            status=status,
            accepted_at=friend_result.fetched_at or now,
            from_cache=friend_result.from_cache
            or bool(summaries_result and summaries_result.from_cache),
            stale=stale
            or friend_result.from_cache
            or bool(summaries_result and summaries_result.from_cache),
        )

    friend_fingerprints = _cached_friend_fingerprints(friend_result.payload)
    players = _cached_player_rows(summaries_result.payload)
    entries: list[FriendPulseEntry] = []
    online_count = 0
    for row in players:
        fingerprint = _text(row.get("identity_fingerprint"))
        if not fingerprint or fingerprint not in friend_fingerprints:
            continue
        persona_state = _int_or_none(row.get("persona_state"))
        if persona_state is not None and persona_state > 0:
            online_count += 1
        appid = _int_or_none(row.get("game_appid"))
        game_name = _text(row.get("game_name"))
        if appid is None or not game_name:
            continue
        entries.append(
            FriendPulseEntry(
                identity_fingerprint=fingerprint,
                steam_id=_matching_steam_id(
                    row.get("steam_id"),
                    identity_fingerprint=fingerprint,
                ),
                display_name=_text(row.get("display_name")),
                game_appid=appid,
                game_name=game_name,
                avatar_url=_text(row.get("avatar_url")),
                persona_state=persona_state,
            )
        )
    entries.sort(
        key=lambda entry: (
            (entry.game_name or "").casefold(),
            (entry.display_name or "").casefold(),
            entry.identity_fingerprint,
        )
    )
    snapshot = FriendPulseSnapshot(
        status=SteamResultStatus.SUCCESS,
        accepted_at=max(
            _time_or_zero(friend_result.fetched_at),
            _time_or_zero(summaries_result.fetched_at),
            _time_or_zero(now),
        )
        or None,
        from_cache=friend_result.from_cache or summaries_result.from_cache,
        stale=stale or friend_result.from_cache or summaries_result.from_cache,
        authoritative=not (
            stale or friend_result.from_cache or summaries_result.from_cache
        ),
        entries=tuple(entries),
        playing_count=len(entries),
        online_count=online_count,
    )
    return with_change_evidence(snapshot, previous)


def with_change_evidence(
    snapshot: FriendPulseSnapshot,
    previous: FriendPulseSnapshot | None,
) -> FriendPulseSnapshot:
    """Mark only proven fresh accepted start/game-change transitions."""

    if (
        previous is None
        or not snapshot.authoritative
        or snapshot.stale
        or not previous.authoritative
        or previous.stale
        or snapshot.status != SteamResultStatus.SUCCESS
        or previous.status != SteamResultStatus.SUCCESS
    ):
        return snapshot
    old_games = {
        entry.identity_fingerprint: entry.game_appid for entry in previous.entries
    }
    marked = tuple(
        replace(
            entry,
            changed=(old_games.get(entry.identity_fingerprint) != entry.game_appid),
        )
        for entry in snapshot.entries
    )
    # Freshly proven transitions are the most useful bounded rows. Stable rows
    # retain deterministic game/name ordering behind them.
    ranked = tuple(
        sorted(
            marked,
            key=lambda entry: (
                not entry.changed,
                (entry.game_name or "").casefold(),
                (entry.display_name or "").casefold(),
                entry.identity_fingerprint,
            ),
        )
    )
    return replace(snapshot, entries=ranked)


def project_friend_pulse(
    snapshot: FriendPulseSnapshot,
    *,
    privacy_mode: str,
    capacity: int,
    avatar_sources: Mapping[str, str] | None = None,
    friend_action_identities: Collection[str] | None = None,
) -> FriendPulseProjection:
    """Project neutral state into Strict/Balanced/Rich presentation-safe rows."""

    mode = str(privacy_mode or "Strict").strip().lower()
    local_avatars = avatar_sources or {}
    actionable_friends = (
        frozenset(friend_action_identities)
        if friend_action_identities is not None
        else frozenset(
            entry.identity_fingerprint
            for entry in snapshot.entries
            if entry.steam_id
        )
    )
    limit = max(1, int(capacity))
    if snapshot.status == SteamResultStatus.PRIVATE:
        return FriendPulseProjection("private", "Private / unavailable", ())
    if snapshot.status != SteamResultStatus.SUCCESS:
        return FriendPulseProjection("unavailable", "Unavailable", ())
    if not snapshot.entries:
        return FriendPulseProjection(
            "stale" if snapshot.stale else "empty",
            "No friends playing (cached)" if snapshot.stale else "No friends playing",
            (),
        )
    if mode == "strict":
        groups = Counter(
            (entry.game_appid, entry.game_name or "Unknown game")
            for entry in snapshot.entries
        )
        rows = tuple(
            FriendPulseRow(
                primary=game,
                secondary=f"{count} {'friend' if count == 1 else 'friends'} playing",
                presence_text="In game",
                online=True,
                count=count,
                game_appid=appid,
            )
            for (appid, game), count in sorted(
                groups.items(),
                key=lambda item: (-item[1], item[0][1].casefold()),
            )
        )
    else:
        rows = tuple(
            FriendPulseRow(
                primary=entry.display_name or "Friend",
                secondary=entry.game_name or "Unknown game",
                presence_text=_presence_text(entry.persona_state),
                online=entry.persona_state is None or entry.persona_state > 0,
                changed=entry.changed,
                avatar_url=local_avatars.get(entry.identity_fingerprint)
                if mode == "rich"
                else None,
                game_appid=entry.game_appid,
                identity_fingerprint=entry.identity_fingerprint,
                friend_action_available=(
                    entry.identity_fingerprint in actionable_friends
                ),
            )
            for entry in snapshot.entries
        )
    playing_count = snapshot.playing_count or 0
    metric = f"{playing_count} {'friend' if playing_count == 1 else 'friends'} playing"
    if snapshot.stale:
        metric += " (cached)"
    return FriendPulseProjection(
        "stale" if snapshot.stale else "ready",
        metric,
        rows[:limit],
        max(0, len(rows) - limit),
    )


def _presence_text(persona_state: int | None) -> str:
    return {
        0: "Offline",
        1: "Online",
        2: "Busy",
        3: "Away",
        4: "Snooze",
        5: "Looking to trade",
        6: "Looking to play",
    }.get(persona_state, "In game")


def _friend_rows(payload: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    root = payload.get("friendslist") if isinstance(payload, Mapping) else None
    rows = root.get("friends") if isinstance(root, Mapping) else None
    return (
        tuple(row for row in rows if isinstance(row, Mapping))
        if isinstance(rows, list)
        else ()
    )


def _player_rows(payload: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    root = payload.get("response") if isinstance(payload, Mapping) else None
    rows = root.get("players") if isinstance(root, Mapping) else None
    return (
        tuple(row for row in rows if isinstance(row, Mapping))
        if isinstance(rows, list)
        else ()
    )


def _cached_friend_fingerprints(payload: Mapping[str, Any] | None) -> set[str]:
    rows = payload.get("friends") if isinstance(payload, Mapping) else None
    return (
        {
            _text(row.get("identity_fingerprint"))
            for row in rows
            if isinstance(row, Mapping) and _text(row.get("identity_fingerprint"))
        }
        if isinstance(rows, list)
        else set()
    )


def _cached_player_rows(
    payload: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any], ...]:
    rows = payload.get("players") if isinstance(payload, Mapping) else None
    return (
        tuple(row for row in rows if isinstance(row, Mapping))
        if isinstance(rows, list)
        else ()
    )


def _text(value: Any) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def _steam_id_or_none(value: Any) -> str | None:
    text = _text(value)
    if text is None or not text.isascii() or not text.isdigit():
        return None
    return text if 15 <= len(text) <= 20 and int(text) > 0 else None


def _matching_steam_id(
    value: Any,
    *,
    identity_fingerprint: str,
) -> str | None:
    steam_id = _steam_id_or_none(value)
    if steam_id is None or safe_fingerprint(steam_id) != identity_fingerprint:
        return None
    return steam_id


def _int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else None
    except (TypeError, ValueError):
        return None


def _time_or_zero(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
