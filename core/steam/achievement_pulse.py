"""Pure Achievement Pulse resolver for Steam cache/fixture records.

The resolver consumes already-fetched/cache-safe ``SteamResult`` payloads only.
It must not contact Steam, inspect credentials, schedule provider work, or touch
Qt. Runtime widgets can then map the resolved state into a card view model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from core.steam.models import SteamResult


RECENT_SELECTIONS: tuple[str, ...] = ("most_recent", "recent_2", "recent_3", "recent_4", "recent_5")


@dataclass(frozen=True)
class AchievementPulseSelection:
    """Authored selection for the single game shown by Achievement Pulse."""

    mode: str = "most_recent"
    custom_appid: int | None = None


@dataclass(frozen=True)
class AchievementPulseResolved:
    """Cache/fixture-derived state for one Achievement Pulse card."""

    status: str
    appid: int | None
    title: str
    selection_label: str
    unlocked: int = 0
    total: int = 0
    percent: float | None = None
    latest_achievement: str = ""
    latest_achievements: tuple[str, ...] = ()
    previous_game_title: str = ""
    playtime_forever_minutes: int | None = None
    unavailable_reason: str = ""
    source_label: str = "Cache"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _payload(result: SteamResult | None) -> Mapping[str, Any]:
    if result is None or not result.ok or not isinstance(result.payload, Mapping):
        return {}
    return result.payload


def _recent_games(recent_result: SteamResult | None) -> tuple[Mapping[str, Any], ...]:
    payload = _payload(recent_result)
    response = payload.get("response")
    if isinstance(response, Mapping):
        games = response.get("games")
    else:
        games = payload.get("games")
    if not isinstance(games, list):
        return ()
    return tuple(game for game in games if isinstance(game, Mapping) and _coerce_appid(game.get("appid")) is not None)


def _coerce_appid(value: Any) -> int | None:
    try:
        appid = int(value)
    except (TypeError, ValueError):
        return None
    return appid if appid > 0 else None


def _selection_index(mode: str) -> int:
    if mode == "most_recent":
        return 0
    if mode.startswith("recent_"):
        try:
            return max(0, int(mode.split("_", 1)[1]) - 1)
        except (TypeError, ValueError):
            return 0
    return 0


def _selection_label(selection: AchievementPulseSelection, appid: int | None = None) -> str:
    if selection.mode == "custom":
        return f"Custom {appid or selection.custom_appid or 'app'}"
    if selection.mode == "most_recent":
        return "Most Recent"
    if selection.mode.startswith("recent_"):
        return f"Recent #{_selection_index(selection.mode) + 1}"
    return "Most Recent"


def _game_name(game: Mapping[str, Any], fallback: str) -> str:
    name = game.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return fallback


def _library_game_name(library_result: SteamResult | None, appid: int) -> str:
    payload = _payload(library_result)
    response = payload.get("response")
    if isinstance(response, Mapping):
        games = response.get("games")
    else:
        games = payload.get("games")
    if not isinstance(games, list):
        return ""
    for game in games:
        if not isinstance(game, Mapping):
            continue
        if _coerce_appid(game.get("appid")) == appid:
            return _game_name(game, str(appid))
    return ""


def _achievement_payload(result: SteamResult | None) -> Mapping[str, Any]:
    payload = _payload(result)
    playerstats = payload.get("playerstats")
    if isinstance(playerstats, Mapping):
        return playerstats
    return payload


def _achievement_rows(result: SteamResult | None) -> tuple[Mapping[str, Any], ...]:
    payload = _achievement_payload(result)
    achievements = payload.get("achievements")
    if not isinstance(achievements, list):
        return ()
    return tuple(row for row in achievements if isinstance(row, Mapping))


def _achievement_title(row: Mapping[str, Any]) -> str:
    for key in ("displayName", "name", "apiname"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Achievement"


def _unlock_time(row: Mapping[str, Any]) -> int:
    try:
        return max(0, int(row.get("unlocktime") or 0))
    except (TypeError, ValueError):
        return 0


def _schema_display_names(schema_result: SteamResult | None) -> dict[str, str]:
    """Map Steam's internal achievement ids to its user-facing schema labels."""
    payload = _payload(schema_result)
    game = payload.get("game")
    if not isinstance(game, Mapping):
        return {}
    stats = game.get("availableGameStats")
    if not isinstance(stats, Mapping):
        return {}
    achievements = stats.get("achievements")
    if not isinstance(achievements, list):
        return {}
    display_names: dict[str, str] = {}
    for row in achievements:
        if not isinstance(row, Mapping):
            continue
        internal_name = row.get("name")
        display_name = row.get("displayName")
        if isinstance(internal_name, str) and internal_name and isinstance(display_name, str) and display_name.strip():
            display_names[internal_name] = display_name.strip()
    return display_names


def _playtime_forever(game: Mapping[str, Any] | None) -> int | None:
    if not isinstance(game, Mapping):
        return None
    value = game.get("playtime_forever")
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, minutes)


def resolve_achievement_pulse(
    *,
    recent_result: SteamResult | None,
    achievement_results: Mapping[int, SteamResult],
    selection: AchievementPulseSelection = AchievementPulseSelection(),
    library_result: SteamResult | None = None,
    schema_result: SteamResult | None = None,
) -> AchievementPulseResolved:
    """Resolve the selected Achievement Pulse game from cache/fixture results."""

    selected_game: Mapping[str, Any] | None = None
    appid: int | None = None
    recent_games = _recent_games(recent_result)
    previous_game_title = (
        _game_name(recent_games[1], str(recent_games[1].get("appid") or "Previous Game"))
        if len(recent_games) > 1
        else ""
    )

    if selection.mode == "custom":
        appid = _coerce_appid(selection.custom_appid)
        if appid is None:
            return AchievementPulseResolved(
                status="unavailable",
                appid=None,
                title="Custom App",
                selection_label=_selection_label(selection),
                previous_game_title=previous_game_title,
                unavailable_reason="No custom Steam app ID selected",
            )
    else:
        index = _selection_index(selection.mode)
        if index >= len(recent_games):
            return AchievementPulseResolved(
                status="unavailable",
                appid=None,
                title="Recent Game",
                selection_label=_selection_label(selection),
                previous_game_title=previous_game_title,
                unavailable_reason=f"{_selection_label(selection)} is not available in cache",
            )
        selected_game = recent_games[index]
        appid = _coerce_appid(selected_game.get("appid"))

    assert appid is not None
    achievement_result = achievement_results.get(appid)
    rows = _achievement_rows(achievement_result)
    title = ""
    if selected_game is not None:
        title = _game_name(selected_game, str(appid))
    if not title:
        ach_payload = _achievement_payload(achievement_result)
        game_name = ach_payload.get("gameName")
        title = game_name.strip() if isinstance(game_name, str) and game_name.strip() else ""
    if not title:
        title = _library_game_name(library_result, appid) or str(appid)

    if achievement_result is None or not achievement_result.ok:
        return AchievementPulseResolved(
            status="unavailable",
            appid=appid,
            title=title,
            selection_label=_selection_label(selection, appid),
            previous_game_title=previous_game_title,
            playtime_forever_minutes=_playtime_forever(selected_game),
            unavailable_reason="Achievement data is unavailable or private",
        )
    if not rows:
        return AchievementPulseResolved(
            status="unavailable",
            appid=appid,
            title=title,
            selection_label=_selection_label(selection, appid),
            previous_game_title=previous_game_title,
            playtime_forever_minutes=_playtime_forever(selected_game),
            unavailable_reason="No achievements reported for this app",
        )

    unlocked_rows = tuple(row for row in rows if bool(row.get("achieved")))
    latest_achievements: tuple[str, ...] = ()
    if unlocked_rows:
        schema_names = _schema_display_names(schema_result)
        latest_achievements = tuple(
            schema_names.get(str(row.get("apiname") or row.get("name")), "") or _achievement_title(row)
            for row in sorted(unlocked_rows, key=_unlock_time, reverse=True)[:5]
        )

    total = len(rows)
    unlocked = len(unlocked_rows)
    percent = (unlocked / total * 100.0) if total else None
    return AchievementPulseResolved(
        status="ok",
        appid=appid,
        title=title,
        selection_label=_selection_label(selection, appid),
        unlocked=unlocked,
        total=total,
        percent=percent,
        latest_achievement=latest_achievements[0] if latest_achievements else "",
        latest_achievements=latest_achievements,
        previous_game_title=previous_game_title,
        playtime_forever_minutes=_playtime_forever(selected_game),
        source_label="Cache" if achievement_result.from_cache else "Fixture",
    )
