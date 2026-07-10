from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QSignalSpy

from core.steam.achievement_pulse import AchievementPulseSelection, recent_game_titles, resolve_achievement_pulse
from core.steam.achievement_pulse_cache import (
    OWNED_GAMES_CACHE_KEY,
    RECENT_GAMES_CACHE_KEY,
    achievement_cache_key_for_app,
    achievement_schema_cache_key_for_app,
    load_achievement_pulse_cache_snapshot,
    load_recent_game_titles_from_cache,
    refresh_achievement_pulse_cache,
)
from core.steam.cache import SteamCacheRecord, cache_path_for_profile_key, write_cache_record
from core.steam.credentials import (
    SteamCredentialPayload,
    derive_profile_cache_key,
    write_credential_metadata,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.threading.manager import TaskResult
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


def test_recent_game_titles_preserve_cached_ordinals_and_normalize_whitespace() -> None:
    result = _success(
        {
            "response": {
                "games": [
                    {"appid": 111, "name": "  Hollow   Knight  "},
                    {"appid": 222, "name": "Celeste"},
                    {"appid": 333},
                ]
            }
        },
        source_id=SteamSourceId.RECENTLY_PLAYED,
    )

    assert recent_game_titles(result) == ("Hollow Knight", "Celeste", "App 333")


def test_recent_game_titles_load_from_one_opaque_profile_cache_record(tmp_path) -> None:
    profile_key = "profile_1234567890abcdef12345678"
    write_cache_record(
        SteamCacheRecord(
            cache_key=RECENT_GAMES_CACHE_KEY,
            source_id=SteamSourceId.RECENTLY_PLAYED,
            payload={
                "response": {
                    "games": [
                        {"appid": 111, "name": "Hollow Knight"},
                        {"appid": 222, "name": "Celeste"},
                    ]
                }
            },
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, root=tmp_path),
    )

    assert load_recent_game_titles_from_cache(profile_key=profile_key, root=tmp_path) == (
        "Hollow Knight",
        "Celeste",
    )


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
    assert resolved.latest_achievements == ("Late Win", "Start")
    assert resolved.previous_game_title == "Celeste"
    assert resolved.selection_label == "Most Recent"

    model = build_achievement_pulse_view_model(resolved)
    assert model.card_id == "achievement_pulse"
    assert model.metric_value == "2/3"
    assert model.latest_unlocks == ("Late Win",)
    assert model.enabled_field_ids == ("total", "playtime", "previous")


def test_achievement_pulse_uses_schema_display_name_instead_of_internal_id() -> None:
    icon_url = (
        "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/"
        "111/latest.jpg"
    )
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={
            111: _achievements(
                "Hollow Knight",
                [{"apiname": "BG3_Quest12", "achieved": 1, "unlocktime": 20}],
            )
        },
        schema_result=_success(
            {
                "game": {
                    "availableGameStats": {
                        "achievements": [{
                            "name": "BG3_Quest12",
                            "displayName": "A Hero's Welcome",
                            "icon": icon_url,
                        }]
                    }
                }
            },
            source_id=SteamSourceId.ACHIEVEMENT_SCHEMA,
        ),
    )

    assert resolved.latest_achievement == "A Hero's Welcome"
    assert resolved.latest_achievement_icon_url == icon_url
    assert build_achievement_pulse_view_model(resolved).latest_unlock_icon_url == icon_url


def test_achievement_pulse_omits_non_https_schema_icon_without_losing_unlock() -> None:
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={
            111: _achievements(
                "Hollow Knight",
                [{"apiname": "START", "achieved": 1, "unlocktime": 20}],
            )
        },
        schema_result=_success(
            {
                "game": {
                    "availableGameStats": {
                        "achievements": [{
                            "name": "START",
                            "displayName": "First Step",
                            "icon": "http://steamcdn-a.akamaihd.net/insecure.jpg",
                        }]
                    }
                }
            },
            source_id=SteamSourceId.ACHIEVEMENT_SCHEMA,
        ),
    )

    assert resolved.latest_achievement == "First Step"
    assert resolved.latest_achievement_icon_url == ""


def test_achievement_pulse_exposes_five_newest_unlocks_in_schema_order() -> None:
    schema_rows = [
        {"name": f"INTERNAL_{index}", "displayName": f"Unlock {index}"}
        for index in range(1, 7)
    ]
    achievement_rows = [
        {"apiname": f"INTERNAL_{index}", "achieved": 1, "unlocktime": index * 10}
        for index in range(1, 7)
    ]
    resolved = resolve_achievement_pulse(
        recent_result=_recent_result(),
        achievement_results={111: _achievements("Hollow Knight", achievement_rows)},
        schema_result=_success(
            {"game": {"availableGameStats": {"achievements": schema_rows}}},
            source_id=SteamSourceId.ACHIEVEMENT_SCHEMA,
        ),
    )

    assert resolved.latest_achievements == ("Unlock 6", "Unlock 5", "Unlock 4", "Unlock 3", "Unlock 2")
    assert build_achievement_pulse_view_model(resolved, latest_unlock_count=5).latest_unlocks == (
        "Unlock 6",
        "Unlock 5",
        "Unlock 4",
        "Unlock 3",
        "Unlock 2",
    )


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


def test_steam_connection_target_primes_the_connection_bucket() -> None:
    settings = _FakeSettings()
    handler = InputHandler(parent=None, settings_manager=settings)

    handler._prime_settings_section("steam", bucket="connection")

    assert settings.values["ui.widget_bucket_states"]["steam:connection"] is True


def test_achievement_pulse_cache_snapshot_uses_opaque_profile_key_and_real_record_age(tmp_path) -> None:
    profile_key = "profile_1234567890abcdef12345678"
    now = 10_000.0

    def _write(cache_key: str, source_id: SteamSourceId, payload: dict, fetched_at: float) -> None:
        path = cache_path_for_profile_key(profile_key, cache_key, root=tmp_path)
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=fetched_at,
            ),
            path,
        )

    _write(
        RECENT_GAMES_CACHE_KEY,
        SteamSourceId.RECENTLY_PLAYED,
        {"response": {"games": [{"appid": 111, "name": "Hollow Knight", "playtime_forever": 600}]}},
        now - 120,
    )
    _write(
        OWNED_GAMES_CACHE_KEY,
        SteamSourceId.OWNED_GAMES,
        {"response": {"games": [{"appid": 111, "name": "Hollow Knight"}]}},
        now - 120,
    )
    _write(
        achievement_cache_key_for_app(111),
        SteamSourceId.PLAYER_ACHIEVEMENTS,
        {"playerstats": {"gameName": "Hollow Knight", "achievements": [{"name": "Start", "achieved": 1}]}},
        now - 60,
    )

    snapshot = load_achievement_pulse_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=now,
    )

    assert snapshot.has_usable_cache is True
    assert snapshot.resolved.ok is True
    assert snapshot.resolved.title == "Hollow Knight"
    assert snapshot.cache_age_seconds == 120
    assert snapshot.achievement_result is not None
    assert snapshot.achievement_result.from_cache is True


def test_achievement_pulse_cache_snapshot_keeps_custom_unavailable_literal(tmp_path) -> None:
    profile_key = "profile_1234567890abcdef12345678"
    snapshot = load_achievement_pulse_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        selection=AchievementPulseSelection(mode="custom", custom_appid=999),
    )

    assert snapshot.has_usable_cache is False
    assert snapshot.resolved.ok is False
    assert snapshot.resolved.appid == 999
    assert "unavailable" in snapshot.resolved.unavailable_reason.lower()


def test_achievement_pulse_refresh_writes_cache_and_coalesces_fresh_followers(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fake_steam_api_key_123456",
        profile_identifier="76561197960265728",
    )
    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self, _limit: int) -> bytes:
            return self._payload

    def _opener(request, _timeout: float):
        requests.append(request.full_url)
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(b'{"response":{"games":[{"appid":111,"name":"Hollow Knight"}]}}')
        if "GetPlayerAchievements" in request.full_url:
            return _Response(b'{"playerstats":{"gameName":"Hollow Knight","achievements":[{"name":"Start","achieved":1}]}}')
        if "GetSchemaForGame" in request.full_url:
            return _Response(b'{"game":{"availableGameStats":{"achievements":[{"name":"Start","displayName":"First Step"}]}}}')
        raise AssertionError(request.full_url)

    first = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=10_000.0,
    )
    second = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=10_000.0,
    )
    manual = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=10_050.0,
        force=True,
    )

    assert first.resolved.ok is True
    assert second.resolved.ok is True
    assert manual.resolved.ok is True
    assert manual.cache_age_seconds == 50
    assert len(requests) == 6
    assert achievement_schema_cache_key_for_app(111) in {
        path.stem for path in tmp_path.rglob("*.json")
    }


def test_achievement_pulse_unchanged_success_suppresses_immediate_display_follower(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fake_steam_api_key_123456",
        profile_identifier="76561197960265728",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    recent_payload = {"response": {"games": [{"appid": 111, "name": "Hollow Knight"}]}}
    achievement_payload = {
        "playerstats": {
            "gameName": "Hollow Knight",
            "achievements": [{"name": "Start", "achieved": 1}],
        }
    }
    schema_payload = {
        "game": {
            "availableGameStats": {
                "achievements": [{"name": "Start", "displayName": "First Step"}]
            }
        }
    }
    for cache_key, source_id, payload in (
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, recent_payload),
        (achievement_cache_key_for_app(111), SteamSourceId.PLAYER_ACHIEVEMENTS, achievement_payload),
        (achievement_schema_cache_key_for_app(111), SteamSourceId.ACHIEVEMENT_SCHEMA, schema_payload),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=1_000.0,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self, _limit: int) -> bytes:
            return self._payload

    def _opener(request, _timeout: float):
        requests.append(request.full_url)
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(b'{"response":{"games":[{"appid":111,"name":"Hollow Knight"}]}}')
        if "GetPlayerAchievements" in request.full_url:
            return _Response(
                b'{"playerstats":{"gameName":"Hollow Knight","achievements":[{"name":"Start","achieved":1}]}}'
            )
        if "GetSchemaForGame" in request.full_url:
            return _Response(
                b'{"game":{"availableGameStats":{"achievements":[{"name":"Start","displayName":"First Step"}]}}}'
            )
        raise AssertionError(request.full_url)

    first = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=10_000.0,
    )
    follower = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=10_001.0,
    )

    assert first.resolved.ok is True
    assert follower.resolved.ok is True
    assert first.cache_age_seconds == 9_000.0
    assert follower.cache_age_seconds == 9_001.0
    assert len(requests) == 3


def test_achievement_pulse_unauthorized_refresh_keeps_cache_and_flags_connection(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fake_steam_api_key_123456",
        profile_identifier="76561197960265728",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    write_cache_record(
        SteamCacheRecord(
            cache_key=RECENT_GAMES_CACHE_KEY,
            source_id=SteamSourceId.RECENTLY_PLAYED,
            payload={"response": {"games": [{"appid": 111, "name": "Hollow Knight"}]}},
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY, root=tmp_path),
    )
    write_cache_record(
        SteamCacheRecord(
            cache_key=achievement_cache_key_for_app(111),
            source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
            payload={"playerstats": {"gameName": "Hollow Knight", "achievements": [{"name": "Start", "achieved": 1}]}},
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, achievement_cache_key_for_app(111), root=tmp_path),
    )

    class _UnauthorizedResponse:
        status = 403

        def read(self, _limit: int) -> bytes:
            return b"{}"

    outcome = refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=lambda _request, _timeout: _UnauthorizedResponse(),
        now=100_000.0,
    )

    assert outcome.connection_needs_attention is True
    assert outcome.snapshot.resolved.ok is True
    assert outcome.snapshot.cache_age_seconds == 99_000


def test_achievement_pulse_widget_applies_cache_before_requesting_first_fade(qt_app, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core.settings import storage_paths

    storage_paths.reset_module_cache()
    profile_identifier = "76561197960265728"
    credential = SteamCredentialPayload(api_key="fake_steam_api_key_123456", profile_identifier=profile_identifier)
    write_credential_metadata(credential)

    # The cache root is account-private; the card never needs to decrypt the ID to read it.
    profile_key = derive_profile_cache_key(profile_identifier)
    write_cache_record(
        SteamCacheRecord(
            cache_key=RECENT_GAMES_CACHE_KEY,
            source_id=SteamSourceId.RECENTLY_PLAYED,
            payload={"response": {"games": [{"appid": 111, "name": "Hollow Knight"}]}},
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, RECENT_GAMES_CACHE_KEY),
    )
    write_cache_record(
        SteamCacheRecord(
            cache_key=OWNED_GAMES_CACHE_KEY,
            source_id=SteamSourceId.OWNED_GAMES,
            payload={"response": {"games": [{"appid": 111, "name": "Hollow Knight"}]}},
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY),
    )
    write_cache_record(
        SteamCacheRecord(
            cache_key=achievement_cache_key_for_app(111),
            source_id=SteamSourceId.PLAYER_ACHIEVEMENTS,
            payload={"playerstats": {"gameName": "Hollow Knight", "achievements": [{"name": "Start", "achieved": 1}]}},
            fetched_at=1_000.0,
        ),
        cache_path_for_profile_key(profile_key, achievement_cache_key_for_app(111)),
    )

    class _InlineThreadManager:
        def submit_io_task(self, func, *, task_id, callback):
            callback(TaskResult(success=True, result=func(), task_id=task_id))
            return task_id

    faded_models: list[tuple[str, str]] = []
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        achievement_show_artwork=False,
    )
    try:
        widget.set_thread_manager(_InlineThreadManager())
        monkeypatch.setattr(
            widget,
            "_request_coordinated_fade",
            lambda: faded_models.append((widget._view_model.state, widget._view_model.title)),
        )
        widget._activate_impl()
        qt_app.processEvents()

        assert widget._view_model.state == "content"
        assert widget._view_model.title == "Hollow Knight"
        assert widget._has_displayed_valid_data is True
        assert faded_models == [("content", "Hollow Knight")]
    finally:
        widget.deleteLater()


def test_achievement_pulse_fresh_cache_does_not_schedule_or_decrypt(qt_app) -> None:
    class _NoTaskThreadManager:
        def submit_io_task(self, *_args, **_kwargs):
            raise AssertionError("fresh cache must not submit a Steam refresh task")

    widget = SteamCardWidget(definition=STEAM_CARD_DEFINITIONS["achievement_pulse"])
    try:
        widget.set_thread_manager(_NoTaskThreadManager())
        widget._refresh_achievement_pulse_cache(cache_age_seconds=60.0)
    finally:
        widget.deleteLater()


def test_achievement_pulse_refresh_window_honors_five_minute_minimum(qt_app, monkeypatch) -> None:
    calls: list[str] = []

    class _InlineThreadManager:
        def submit_io_task(self, func, *, task_id, callback):
            calls.append(task_id)
            callback(TaskResult(success=True, result=func(), task_id=task_id))
            return task_id

    monkeypatch.setattr("core.steam.credentials.load_credentials", lambda: None)
    widget = SteamCardWidget(
        definition=STEAM_CARD_DEFINITIONS["achievement_pulse"],
        refresh_minutes=5,
    )
    try:
        widget.set_thread_manager(_InlineThreadManager())
        assert widget._refresh_achievement_pulse_cache(cache_age_seconds=299.0) is False
        assert calls == []
        assert widget._refresh_achievement_pulse_cache(cache_age_seconds=300.0) is True
        assert calls and calls[0].startswith("steam_achievement_refresh_")
    finally:
        widget.deleteLater()


def test_achievement_pulse_manual_refresh_submits_even_when_automatic_updates_are_off(qt_app, monkeypatch) -> None:
    calls: list[str] = []

    class _InlineThreadManager:
        def submit_io_task(self, func, *, task_id, callback):
            calls.append(task_id)
            callback(TaskResult(success=True, result=func(), task_id=task_id))
            return task_id

    monkeypatch.setattr("core.steam.credentials.load_credentials", lambda: None)
    widget = SteamCardWidget(definition=STEAM_CARD_DEFINITIONS["achievement_pulse"])
    try:
        widget.set_thread_manager(_InlineThreadManager())
        assert widget.request_manual_refresh() is True
        assert calls and calls[0].startswith("steam_achievement_refresh_")
    finally:
        widget.deleteLater()
