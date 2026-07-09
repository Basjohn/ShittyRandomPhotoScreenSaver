from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QSignalSpy

from core.steam.achievement_pulse import AchievementPulseSelection, resolve_achievement_pulse
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from widgets.steam_components import (
    STEAM_SETTINGS_TARGET,
    STEAM_STALE_CONNECTION_INFO_SECONDS,
    build_achievement_pulse_view_model,
    build_steam_connect_required_view_model,
    layout_steam_card,
    with_stale_connection_info,
)
from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget
from rendering.input_handler import InputHandler


def _success(payload, *, source_id=SteamSourceId.PLAYER_ACHIEVEMENTS, from_cache=True) -> SteamResult:
    return SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=source_id,
        payload=payload,
        from_cache=from_cache,
    )


def _recent_result() -> SteamResult:
    return _success(
        {
            "response": {
                "games": [
                    {"appid": 111, "name": "Hollow Knight", "playtime_forever": 600},
                    {"appid": 222, "name": "Celeste", "playtime_forever": 240},
                ]
            }
        },
        source_id=SteamSourceId.RECENTLY_PLAYED,
    )


def _achievements(game_name: str, rows: list[dict]) -> SteamResult:
    return _success({"playerstats": {"gameName": game_name, "achievements": rows}})


def test_achievement_pulse_resolves_recent_selection_from_cache_records_only() -> None:
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={
            111: _achievements(
                "Hollow Knight",
                [
                    {"apiname": "START", "name": "Start", "achieved": 1, "unlocktime": 10},
                    {"apiname": "LATE", "name": "Late Win", "achieved": 1, "unlocktime": 20},
                    {"apiname": "LOCKED", "name": "Locked", "achieved": 0},
                ],
            )
        },
    )

    assert resolved.ok
    assert resolved.appid == 111
    assert resolved.title == "Hollow Knight"
    assert resolved.unlocked == 2
    assert resolved.total == 3
    assert resolved.latest_achievement == "Late Win"
    assert resolved.selection_label == "Most Recent"

    model = build_achievement_pulse_view_model(resolved)
    assert model.card_id == "achievement_pulse"
    assert model.metric_value == "2/3"
    assert "Late Win" in model.subtitle
    assert model.enabled_field_ids == ("total", "latest", "playtime", "source", "selected")


def test_achievement_pulse_resolves_recent_2_without_substituting_games() -> None:
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={
            222: _achievements("Celeste", [{"apiname": "A", "name": "Climb", "achieved": 1, "unlocktime": 5}])
        },
        selection=AchievementPulseSelection(mode="recent_2"),
    )

    assert resolved.ok
    assert resolved.appid == 222
    assert resolved.selection_label == "Recent #2"


def test_achievement_pulse_custom_unavailable_is_literal_no_substitute() -> None:
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={},
        selection=AchievementPulseSelection(mode="custom", custom_appid=999),
    )

    assert not resolved.ok
    assert resolved.appid == 999
    assert resolved.title == "999"
    assert "unavailable" in resolved.unavailable_reason.lower()

    model = build_achievement_pulse_view_model(resolved)
    assert model.state == "unavailable"
    assert model.metric_value == "Unavailable"
    assert model.status == "Custom 999"


def test_steam_connect_required_prompt_has_click_target() -> None:
    model = build_steam_connect_required_view_model("achievement_pulse")
    layout = layout_steam_card(model, QRectF(0, 0, 420, 180))

    assert model.state == "connect_required"
    assert model.action_text == "Connect With Steam To Use"
    assert layout.action_rects
    target, rect = layout.action_rects[0]
    assert target == STEAM_SETTINGS_TARGET
    assert rect.contains(QPoint(int(rect.center().x()), int(rect.center().y())))


def test_stale_connection_info_icon_is_defaultable_and_waits_one_day() -> None:
    base = build_achievement_pulse_view_model(
        resolve_achievement_pulse(
            recent_result=_recent_result(),
            achievement_results={
                111: _achievements("Hollow Knight", [{"apiname": "A", "name": "Start", "achieved": 1}])
            },
        )
    )

    young = with_stale_connection_info(
        base,
        cache_age_seconds=STEAM_STALE_CONNECTION_INFO_SECONDS - 1,
        enabled=True,
        connection_needs_attention=True,
    )
    stale = with_stale_connection_info(
        base,
        cache_age_seconds=STEAM_STALE_CONNECTION_INFO_SECONDS,
        enabled=True,
        connection_needs_attention=True,
    )
    disabled = with_stale_connection_info(
        base,
        cache_age_seconds=STEAM_STALE_CONNECTION_INFO_SECONDS * 2,
        enabled=False,
        connection_needs_attention=True,
    )

    assert young.show_connection_info is False
    assert stale.show_connection_info is True
    assert stale.connection_info_target == STEAM_SETTINGS_TARGET
    assert disabled.show_connection_info is False
    assert layout_steam_card(stale, QRectF(0, 0, 420, 180)).info_rect is not None


def test_steam_card_connect_click_emits_settings_target(qt_app) -> None:
    widget = SteamCardWidget(definition=STEAM_CARD_DEFINITIONS["achievement_pulse"])
    try:
        widget.resize(420, 180)
        widget.set_view_model(build_steam_connect_required_view_model("achievement_pulse"))
        pixmap = QPixmap(widget.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        widget.render(pixmap)
        layout = widget.last_layout()
        assert layout is not None
        target, rect = layout.action_rects[0]
        spy = QSignalSpy(widget.settings_requested)

        assert widget.handle_click(QPoint(int(rect.center().x()), int(rect.center().y()))) is True
        assert target == STEAM_SETTINGS_TARGET
        assert spy.count() == 1
        assert spy.at(0)[0] == STEAM_SETTINGS_TARGET
    finally:
        widget.deleteLater()


class _FakeSettings:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self.values.get(key, default)

    def set(self, key: str, value) -> None:
        self.values[key] = value


def test_steam_settings_target_primes_widgets_steam_subtab() -> None:
    settings = _FakeSettings()
    handler = InputHandler(parent=None, settings_manager=settings)

    handler._prime_settings_section("steam")

    assert settings.values["ui.last_tab_index"] == 3
    assert settings.values["ui.tab_state"]["widgets"]["view_state"]["subtab_id"] == "steam"
