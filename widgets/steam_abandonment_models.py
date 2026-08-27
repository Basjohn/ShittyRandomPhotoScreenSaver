"""Presentation-neutral model and copy policy for Steam Abandonment Issues."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Mapping

from core.steam.abandonment_issues import AbandonmentResolved, LAST_PLAYED_VERIFIED
from widgets.steam_abandonment_layout import ABANDONMENT_FIELD_DEFAULTS
from widgets.steam_card_models import (
    SteamCardField,
    SteamCardViewModel,
    with_stale_connection_info,
)


ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE = "Long Forgotten"
ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES: tuple[str, ...] = (
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
_ABANDONMENT_PRIMARY_MESSAGE_BUCKETS = 60
_ABANDONMENT_MESSAGE_BUCKET_COUNT = 100


def abandonment_shelf_diagnostics(
    resolved: AbandonmentResolved,
    model: SteamCardViewModel,
    field_visibility: Mapping[str, bool] | None,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Describe configured shelf evidence without logging user-facing values."""

    visibility = field_visibility or {}
    requested = tuple(
        field_id
        for field_id, default in ABANDONMENT_FIELD_DEFAULTS.items()
        if bool(visibility.get(field_id, default))
    )
    rendered_ids = {field.field_id for field in model.fields if field.enabled}
    rendered = tuple(field_id for field_id in requested if field_id in rendered_ids)
    unavailable = tuple(field_id for field_id in requested if field_id not in rendered_ids)
    achievement_evidence = (
        resolved.unlocked_achievement_count is not None
        and resolved.total_achievement_count is not None
    )
    last_unlock_evidence = (
        resolved.unlocked_achievement_count == 0
        or resolved.latest_unlock_age_days is not None
    )
    evidence_state = {
        "playtime": "loaded" if resolved.playtime_minutes is not None else "missing",
        "achievements": "loaded" if achievement_evidence else "missing",
        "last_unlock": "loaded" if last_unlock_evidence else "missing",
        "last_played": (
            "verified"
            if resolved.last_played_confidence == LAST_PLAYED_VERIFIED
            and resolved.last_played_at is not None
            else "missing"
        ),
        "archive_class": "derived" if resolved.playtime_minutes is not None else "missing",
        "queue": "loaded" if resolved.queue_count > 0 else "empty",
        "source": "loaded" if bool(resolved.source_label) else "missing",
        "pinned": "loaded",
    }
    evidence = tuple(f"{field_id}:{evidence_state[field_id]}" for field_id in requested)
    return requested, rendered, unavailable, evidence


def format_abandonment_age(inactivity_days: int | None) -> str:
    """Format only a source-proven inactivity interval."""

    if inactivity_days is None:
        return "HISTORY UNKNOWN"
    days = max(0, int(inactivity_days))
    if days < 14:
        return f"{days} DAY{'S' if days != 1 else ''} AGO"
    if days < 70:
        weeks = max(2, int(round(days / 7.0)))
        return f"{weeks} WEEKS AGO"
    if days < 548:
        months = max(2, int(round(days / 30.4375)))
        return f"{months} MONTHS AGO"
    years = days / 365.25
    return f"{years:.1f} YEARS AGO" if years < 10 else f"{int(round(years))} YEARS AGO"


def format_abandonment_last_played(
    timestamp: float | None,
    confidence: str,
) -> str | None:
    """Return an exact UTC calendar date only for verified source evidence."""

    if confidence != LAST_PLAYED_VERIFIED or timestamp is None:
        return None
    try:
        value = float(timestamp)
        if not math.isfinite(value) or value <= 0:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%d/%m/%Y")
    except (OSError, OverflowError, ValueError):
        return None


def abandonment_archive_class(resolved: AbandonmentResolved) -> str | None:
    """Describe engagement depth without claiming that a game was abandoned."""

    if not resolved.ok or resolved.playtime_minutes is None:
        return None
    if resolved.playtime_minutes < 2 * 60:
        if (
            resolved.unlocked_achievement_count is not None
            and resolved.unlocked_achievement_count <= 2
        ):
            return "Barely Started"
        return "Short Start"
    return "Deep Backlog"


def build_abandonment_view_model(
    resolved: AbandonmentResolved,
    *,
    cache_age_seconds: float | None = None,
    connection_needs_attention: bool = False,
    show_connection_info_icon: bool = True,
    show_rediscovery_message: bool = True,
    field_visibility: Mapping[str, bool] | None = None,
) -> SteamCardViewModel:
    """Map a pure source resolution into archival card copy."""

    visibility = dict(field_visibility or {})

    def _enabled(field_id: str, default: bool) -> bool:
        return bool(visibility.get(field_id, default))

    achievement_value = (
        f"{resolved.unlocked_achievement_count} / {resolved.total_achievement_count}"
        if resolved.unlocked_achievement_count is not None
        and resolved.total_achievement_count is not None
        else None
    )
    last_unlock_value = None
    if resolved.unlocked_achievement_count == 0:
        last_unlock_value = "No Unlocks"
    elif resolved.latest_unlock_age_days is not None:
        last_unlock_value = format_abandonment_age(resolved.latest_unlock_age_days)
    last_played_value = format_abandonment_last_played(
        resolved.last_played_at,
        resolved.last_played_confidence,
    )
    archive_class_value = abandonment_archive_class(resolved)
    fields = (
        SteamCardField(
            "playtime",
            "Played",
            _format_playtime(resolved.playtime_minutes),
            _enabled("playtime", ABANDONMENT_FIELD_DEFAULTS["playtime"]),
        ),
        SteamCardField(
            "achievements",
            "Achievements",
            achievement_value or "",
            _enabled("achievements", ABANDONMENT_FIELD_DEFAULTS["achievements"])
            and achievement_value is not None,
        ),
        SteamCardField(
            "last_unlock",
            "Last Unlock",
            last_unlock_value or "",
            _enabled("last_unlock", ABANDONMENT_FIELD_DEFAULTS["last_unlock"])
            and last_unlock_value is not None,
        ),
        SteamCardField(
            "last_played",
            "Last Played",
            last_played_value or "",
            _enabled("last_played", ABANDONMENT_FIELD_DEFAULTS["last_played"])
            and last_played_value is not None,
        ),
        SteamCardField(
            "archive_class",
            "Backlog Class",
            archive_class_value or "",
            _enabled("archive_class", ABANDONMENT_FIELD_DEFAULTS["archive_class"])
            and archive_class_value is not None,
        ),
        SteamCardField(
            "queue",
            "Shelf",
            f"{resolved.queue_position} of {resolved.queue_count}"
            if resolved.queue_count
            else "Empty",
            _enabled("queue", ABANDONMENT_FIELD_DEFAULTS["queue"]),
        ),
        SteamCardField(
            "source",
            "Source",
            resolved.source_label,
            _enabled("source", ABANDONMENT_FIELD_DEFAULTS["source"]),
        ),
        SteamCardField(
            "pinned",
            "Selection",
            "Pinned" if resolved.pinned else "Smart Rotation",
            _enabled("pinned", ABANDONMENT_FIELD_DEFAULTS["pinned"]),
        ),
    )
    if resolved.ok:
        model = SteamCardViewModel(
            card_id="abandonment_issues",
            appid=resolved.appid,
            header="Abandonment Issues",
            title=resolved.title,
            subtitle=(
                abandonment_rediscovery_message(resolved.appid, resolved.title)
                if show_rediscovery_message
                else ""
            ),
            metric_label="Last Visit",
            metric_value=format_abandonment_age(resolved.inactivity_days),
            status=(
                "PINNED FILE"
                if resolved.pinned
                else f"BACKLOG {resolved.queue_position:02d}/{resolved.queue_count:02d}"
            ),
            accent="#de9d58",
            fields=fields,
        )
    else:
        model = SteamCardViewModel(
            card_id="abandonment_issues",
            appid=resolved.appid,
            header="Abandonment Issues",
            title=resolved.title or "Rediscovery Shelf",
            subtitle=resolved.unavailable_reason or "Previous play history is unavailable.",
            metric_label="History",
            metric_value=(
                "Unavailable"
                if resolved.last_played_confidence != LAST_PLAYED_VERIFIED
                else format_abandonment_age(resolved.inactivity_days)
            ),
            status="BACKLOG PAUSED",
            accent="#de9d58",
            fields=fields,
            state="unavailable",
        )
    return with_stale_connection_info(
        model,
        cache_age_seconds=cache_age_seconds,
        enabled=show_connection_info_icon,
        connection_needs_attention=connection_needs_attention,
    )


def _format_playtime(minutes: int | None) -> str:
    if minutes is None:
        return "Unknown"
    hours = max(0, int(minutes)) / 60.0
    if hours < 1.0:
        return f"{int(minutes)}m"
    if hours < 10.0:
        return f"{hours:.1f}h"
    return f"{int(round(hours))}h"


def abandonment_rediscovery_message(appid: int | None, title: str) -> str:
    """Choose stable per-game copy without repaint-time randomness."""

    identity = str(appid) if appid is not None else str(title).strip().casefold()
    digest = hashlib.sha256(f"abandonment:{identity}".encode("utf-8")).digest()
    bucket = int.from_bytes(digest[:4], "big") % _ABANDONMENT_MESSAGE_BUCKET_COUNT
    return _rediscovery_message_for_bucket(bucket)


def _rediscovery_message_for_bucket(bucket: int) -> str:
    normalized = int(bucket) % _ABANDONMENT_MESSAGE_BUCKET_COUNT
    if normalized < _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS:
        return ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE
    alternate_bucket_width = (
        _ABANDONMENT_MESSAGE_BUCKET_COUNT - _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS
    ) // len(ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES)
    alternate_index = min(
        len(ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES) - 1,
        (normalized - _ABANDONMENT_PRIMARY_MESSAGE_BUCKETS) // alternate_bucket_width,
    )
    return ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES[alternate_index]


__all__ = [
    "ABANDONMENT_ALTERNATE_REDISCOVERY_MESSAGES",
    "ABANDONMENT_PRIMARY_REDISCOVERY_MESSAGE",
    "abandonment_archive_class",
    "abandonment_rediscovery_message",
    "abandonment_shelf_diagnostics",
    "build_abandonment_view_model",
    "format_abandonment_age",
    "format_abandonment_last_played",
]
