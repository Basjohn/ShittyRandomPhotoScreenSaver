"""Qt-free semantic models shared by Steam runtime owners and presenters.

This module contains immutable card state and pure mapping helpers only. It
must stay free of QWidget, QPainter, QPixmap, provider, cache, timer and task
ownership so runtime services can prepare accepted state without importing the
legacy Steam painter implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.steam.achievement_pulse import AchievementPulseResolved


STEAM_SETTINGS_TARGET = "steam_connection"
STEAM_STALE_CONNECTION_INFO_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class SteamCardField:
    """One immutable supporting field for a Steam card."""

    field_id: str
    label: str
    value: str
    enabled: bool = True

    def fingerprint(self) -> tuple[str, str, str, bool]:
        return (self.field_id, self.label, self.value, self.enabled)


@dataclass(frozen=True)
class SteamCardViewModel:
    """Immutable presentation state consumed by current and future Steam cards."""

    card_id: str
    appid: int | None
    header: str
    title: str
    subtitle: str
    metric_label: str
    metric_value: str
    status: str
    accent: str
    fields: tuple[SteamCardField, ...]
    latest_unlocks: tuple[str, ...] = ()
    latest_unlock_icon_url: str = ""
    state: str = "content"
    action_text: str = ""
    action_label: str = ""
    settings_target: str = ""
    show_connection_info: bool = False
    connection_info_target: str = ""
    connection_info_tooltip: str = ""
    cache_age_seconds: float | None = None

    @property
    def enabled_field_ids(self) -> tuple[str, ...]:
        return tuple(field.field_id for field in self.fields if field.enabled)

    def content_fingerprint(self) -> tuple[object, ...]:
        return (
            self.card_id,
            self.appid,
            self.header,
            self.title,
            self.subtitle,
            self.metric_label,
            self.metric_value,
            self.status,
            self.accent,
            tuple(field.fingerprint() for field in self.fields),
            self.latest_unlocks,
            self.latest_unlock_icon_url,
            self.state,
            self.action_text,
            self.action_label,
            self.settings_target,
            self.show_connection_info,
            self.connection_info_target,
            self.connection_info_tooltip,
            self.cache_age_seconds,
        )


def build_mock_steam_view_model(card_id: str) -> SteamCardViewModel:
    """Return deterministic fixture content for a Steam card id."""

    data = {
        "steam_progress": (
            "Steam Journey",
            "Library Pulse",
            "3 meaningful updates found",
            "Updates",
            "3",
            "Cache fixture",
            "#66c0f4",
            (
                ("owned", "Owned", "214"),
                ("updated", "Updated", "3"),
                ("window", "Window", "24h"),
                ("source", "Source", "Fixture"),
                ("noise", "Noise filter", "On"),
            ),
        ),
        "achievement_pulse": (
            "Achievement Pulse",
            "Hollow Knight",
            "Steel Soul progress is moving again",
            "Unlocked",
            "42/63",
            "Mock achievement snapshot",
            "#c7d5e0",
            (
                ("rarity", "Rarity", "12%"),
                ("session", "Session", "+2"),
                ("total", "Total", "67%"),
                ("source", "Source", "Fixture"),
                ("selected", "Selected", "Recent #1"),
            ),
        ),
        "abandonment_issues": (
            "Abandonment Issues",
            "Outer Wilds",
            "A good game has been politely haunting the shelf",
            "Last Played",
            "9 mo",
            "Observed cache fixture",
            "#f0b35f",
            (
                ("playtime", "Playtime", "18h"),
                ("recent", "Recent", "0m"),
                ("confidence", "Time", "Reliable"),
                ("cooldown", "Cooldown", "Clear"),
                ("reason", "Reason", "Lapsed"),
            ),
        ),
        "friend_pulse": (
            "Friend Pulse",
            "Two friends are active",
            "One is currently playing a game you own",
            "Active",
            "2",
            "Privacy-safe fixture",
            "#ff7aa8",
            (
                ("observed", "Observed", "12m"),
                ("overlap", "Library", "Known"),
                ("privacy", "Privacy", "Strict"),
                ("mode", "Mode", "Single"),
                ("source", "Source", "Fixture"),
            ),
        ),
    }
    header, title, subtitle, metric_label, metric_value, status, accent, fields = data.get(
        card_id,
        data["steam_progress"],
    )
    return SteamCardViewModel(
        card_id=card_id,
        appid=None,
        header=header,
        title=title,
        subtitle=subtitle,
        metric_label=metric_label,
        metric_value=metric_value,
        status=status,
        accent=accent,
        fields=tuple(
            SteamCardField(field_id, label, value)
            for field_id, label, value in fields
        ),
        latest_unlocks=(
            ("Steel Soul", "False Knight", "Charmed", "Dream No More", "Pure Completion")
            if card_id == "achievement_pulse"
            else ()
        ),
    )


def build_steam_connect_required_view_model(card_id: str) -> SteamCardViewModel:
    """Return an enabled-card prompt state for missing connection/cache."""

    base = build_mock_steam_view_model(card_id)
    return SteamCardViewModel(
        card_id=base.card_id,
        appid=base.appid,
        header=base.header,
        title="",
        subtitle="",
        metric_label="",
        metric_value="",
        status="Steam connection required",
        accent=base.accent,
        fields=(),
        state="connect_required",
        action_text="Connect With Steam To Use",
        action_label="Connect",
        settings_target=STEAM_SETTINGS_TARGET,
    )


def _format_playtime(minutes: int | None) -> str:
    if minutes is None:
        return "Unknown"
    hours = minutes / 60.0
    if hours < 1:
        return f"{minutes}m"
    return f"{hours:.1f}h" if hours < 10 else f"{int(round(hours))}h"


def build_achievement_pulse_view_model(
    resolved: AchievementPulseResolved,
    *,
    cache_age_seconds: float | None = None,
    connection_needs_attention: bool = False,
    show_connection_info_icon: bool = True,
    field_visibility: Mapping[str, bool] | None = None,
    latest_unlock_count: int = 1,
) -> SteamCardViewModel:
    """Map a pure Achievement Pulse resolution into the shared card model."""

    base = build_mock_steam_view_model("achievement_pulse")
    visibility = dict(field_visibility or {})
    field_defaults = {
        "previous": True,
        "selected": False,
        "source": False,
    }

    def _field_enabled(field_id: str) -> bool:
        return bool(visibility.get(field_id, field_defaults.get(field_id, True)))

    latest_count = max(1, min(5, int(latest_unlock_count)))
    if not resolved.ok:
        model = SteamCardViewModel(
            card_id="achievement_pulse",
            appid=resolved.appid,
            header=base.header,
            title=resolved.title or "Achievement Pulse",
            subtitle=resolved.unavailable_reason or "Achievement data is unavailable.",
            metric_label="State",
            metric_value="Unavailable",
            status=resolved.selection_label,
            accent=base.accent,
            fields=(
                SteamCardField(
                    "selected",
                    "Selected",
                    resolved.selection_label,
                    _field_enabled("selected"),
                ),
                SteamCardField(
                    "appid",
                    "App",
                    str(resolved.appid or "Unknown"),
                    _field_enabled("appid"),
                ),
                SteamCardField(
                    "previous",
                    "Previous",
                    resolved.previous_game_title or "Unavailable",
                    _field_enabled("previous"),
                ),
                SteamCardField(
                    "source",
                    "Source",
                    resolved.source_label,
                    _field_enabled("source"),
                ),
            ),
            state="unavailable",
        )
    else:
        percent_text = f"{resolved.percent:.0f}%" if resolved.percent is not None else "Unknown"
        resolved_latest = resolved.latest_achievements
        if not resolved_latest and resolved.latest_achievement:
            resolved_latest = (resolved.latest_achievement,)
        if not resolved_latest:
            resolved_latest = ("No unlocked achievement yet",)
        latest_unlocks = resolved_latest[:latest_count] if _field_enabled("latest") else ()
        model = SteamCardViewModel(
            card_id="achievement_pulse",
            appid=resolved.appid,
            header=base.header,
            title=resolved.title,
            subtitle="",
            metric_label="Unlocked",
            metric_value=f"{resolved.unlocked}/{resolved.total}",
            status=resolved.selection_label,
            accent=base.accent,
            fields=(
                SteamCardField("total", "Total", percent_text, _field_enabled("total")),
                SteamCardField(
                    "playtime",
                    "Playtime",
                    _format_playtime(resolved.playtime_forever_minutes),
                    _field_enabled("playtime"),
                ),
                SteamCardField(
                    "previous",
                    "Previous",
                    resolved.previous_game_title or "Unavailable",
                    _field_enabled("previous"),
                ),
                SteamCardField(
                    "source",
                    "Source",
                    resolved.source_label,
                    _field_enabled("source"),
                ),
                SteamCardField(
                    "selected",
                    "Selected",
                    resolved.selection_label,
                    _field_enabled("selected"),
                ),
            ),
            latest_unlocks=latest_unlocks,
            latest_unlock_icon_url=(
                resolved.latest_achievement_icon_url if latest_unlocks else ""
            ),
        )

    return with_stale_connection_info(
        model,
        cache_age_seconds=cache_age_seconds,
        enabled=show_connection_info_icon,
        connection_needs_attention=connection_needs_attention,
    )


def with_stale_connection_info(
    model: SteamCardViewModel,
    *,
    cache_age_seconds: float | None,
    enabled: bool = True,
    connection_needs_attention: bool = True,
) -> SteamCardViewModel:
    """Attach the optional stale-connection info affordance to a cached model."""

    should_show = (
        enabled
        and connection_needs_attention
        and cache_age_seconds is not None
        and cache_age_seconds >= STEAM_STALE_CONNECTION_INFO_SECONDS
    )
    return SteamCardViewModel(
        card_id=model.card_id,
        appid=model.appid,
        header=model.header,
        title=model.title,
        subtitle=model.subtitle,
        metric_label=model.metric_label,
        metric_value=model.metric_value,
        status=model.status,
        accent=model.accent,
        fields=model.fields,
        latest_unlocks=model.latest_unlocks,
        latest_unlock_icon_url=model.latest_unlock_icon_url,
        state=model.state,
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=should_show,
        connection_info_target=STEAM_SETTINGS_TARGET if should_show else "",
        connection_info_tooltip=(
            "Steam connection needs attention; cached data is at least 1 day old."
            if should_show
            else ""
        ),
        cache_age_seconds=cache_age_seconds,
    )


def with_long_title(model: SteamCardViewModel) -> SteamCardViewModel:
    """Return a long-title variant for deterministic layout bars."""

    return SteamCardViewModel(
        card_id=model.card_id,
        appid=model.appid,
        header=model.header,
        title=(
            f"{model.title}: A Very Long Localized Title That Must Scale "
            "Without Reauthoring Content"
        ),
        subtitle=f"{model.subtitle} with extra localized context that remains authored content.",
        metric_label=model.metric_label,
        metric_value=model.metric_value,
        status=model.status,
        accent=model.accent,
        fields=model.fields,
        latest_unlocks=model.latest_unlocks,
        latest_unlock_icon_url=model.latest_unlock_icon_url,
        state=model.state,
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=model.show_connection_info,
        connection_info_target=model.connection_info_target,
        connection_info_tooltip=model.connection_info_tooltip,
        cache_age_seconds=model.cache_age_seconds,
    )


def with_unavailable_state(model: SteamCardViewModel) -> SteamCardViewModel:
    """Return an unavailable/private fixture without changing authored fields."""

    return SteamCardViewModel(
        card_id=model.card_id,
        appid=model.appid,
        header=model.header,
        title=model.title,
        subtitle="Private or unavailable source; showing cache-safe fixture state.",
        metric_label="State",
        metric_value="Private",
        status="Unavailable fixture",
        accent=model.accent,
        fields=model.fields,
        latest_unlocks=model.latest_unlocks,
        latest_unlock_icon_url=model.latest_unlock_icon_url,
        state="unavailable",
        action_text=model.action_text,
        action_label=model.action_label,
        settings_target=model.settings_target,
        show_connection_info=model.show_connection_info,
        connection_info_target=model.connection_info_target,
        connection_info_tooltip=model.connection_info_tooltip,
        cache_age_seconds=model.cache_age_seconds,
    )
