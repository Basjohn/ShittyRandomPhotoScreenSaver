from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from core.steam.abandonment_cache import (
    load_abandonment_cache_snapshot,
    refresh_abandonment_cache,
)
from core.steam.abandonment_issues import (
    AbandonmentSelection,
    LAST_PLAYED_UNKNOWN,
    build_abandonment_candidates,
    format_appid_list,
    parse_appid_list,
    resolve_abandonment_issues,
)
from core.steam.achievement_pulse_cache import (
    OWNED_GAMES_CACHE_KEY,
    RECENT_GAMES_CACHE_KEY,
    refresh_achievement_pulse_cache,
)
from core.steam.assets import (
    abandonment_desaturation_bucket,
    prepare_desaturated_steam_artwork,
)
from core.steam.cache import (
    SteamCacheRecord,
    cache_path_for_profile_key,
    read_cache_record,
    write_cache_record,
)
from core.steam.credentials import (
    SteamCredentialPayload,
    derive_profile_cache_key,
    write_credential_metadata,
)
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId
from core.threading.manager import TaskResult
from widgets.abandonment_issues_widget import AbandonmentIssuesWidget
from widgets.base_overlay_widget import OverlayPosition
from widgets.steam_abandonment_components import (
    abandonment_authored_size,
    build_abandonment_view_model,
    layout_abandonment_card,
    render_abandonment_card,
)
from widgets.steam_card_widget import STEAM_CARD_DEFINITIONS, SteamCardWidget


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "steam"
NOW = 2_000_000_000.0


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _result(name: str, source_id: SteamSourceId, *, from_cache: bool = True) -> SteamResult:
    return SteamResult(
        status=SteamResultStatus.SUCCESS,
        source_id=source_id,
        payload=_fixture(name),
        from_cache=from_cache,
        fetched_at=NOW - 60,
    )


def _owned_result() -> SteamResult:
    return _result("owned_games_last_played.json", SteamSourceId.OWNED_GAMES)


def _recent_result() -> SteamResult:
    return _result("recent_games_for_abandonment.json", SteamSourceId.RECENTLY_PLAYED)


def test_abandonment_appid_list_normalizes_only_positive_unique_ids() -> None:
    assert parse_appid_list("440, 570; 440\n730 invalid -2 0") == (440, 570, 730)
    assert parse_appid_list([10, "20", 10, None]) == (10, 20)
    assert format_appid_list((440, 570, 440)) == "440, 570"


def test_abandonment_smart_candidates_require_meaningful_play_and_verified_age() -> None:
    candidates = build_abandonment_candidates(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(),
        now=NOW,
    )

    assert {candidate.appid for candidate in candidates} == {101, 106, 107}
    assert all(candidate.last_played_confidence == "verified" for candidate in candidates)
    assert 102 not in {candidate.appid for candidate in candidates}
    assert 103 not in {candidate.appid for candidate in candidates}
    assert 104 not in {candidate.appid for candidate in candidates}
    assert 105 not in {candidate.appid for candidate in candidates}


def test_abandonment_never_show_and_pinned_unknown_history_remain_honest() -> None:
    smart = build_abandonment_candidates(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(never_show_appids=(101,)),
        now=NOW,
    )
    pinned = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        selection=AbandonmentSelection(mode="pinned_game", pinned_appid=104),
        now=NOW,
    )

    assert 101 not in {candidate.appid for candidate in smart}
    assert pinned.ok is False
    assert pinned.appid == 104
    assert pinned.last_played_confidence == LAST_PLAYED_UNKNOWN
    assert "unavailable" in pinned.unavailable_reason.lower()


def test_abandonment_rotation_retains_current_until_advance_and_honors_cooldown() -> None:
    initial = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )
    retained = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW + 60,
        current_appid=initial.appid,
        exposure_timestamps={initial.appid: NOW},
    )
    advanced = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW + 60,
        current_appid=initial.appid,
        advance_rotation=True,
        exposure_timestamps={initial.appid: NOW},
    )

    assert retained.appid == initial.appid
    assert advanced.appid != initial.appid


def test_abandonment_profile_rotation_is_shared_across_display_followers(tmp_path) -> None:
    profile_key = derive_profile_cache_key("76561198000000001")
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    first = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW,
        rotation_interval_minutes=30,
    )
    follower = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 1,
        advance_rotation=True,
        rotation_interval_minutes=30,
    )
    advanced = load_abandonment_cache_snapshot(
        profile_key=profile_key,
        root=tmp_path,
        now=NOW + 30 * 60 + 1,
        advance_rotation=True,
        rotation_interval_minutes=30,
    )

    assert first.resolved.ok is True
    assert follower.resolved.appid == first.resolved.appid
    assert advanced.resolved.appid != first.resolved.appid
    state_payload = json.loads((tmp_path / "profile_state.json").read_text(encoding="utf-8"))
    assert state_payload["rotations"]["abandonment_issues"]["appid"] == advanced.resolved.appid


def test_abandonment_refresh_uses_owned_and_recent_sources_and_persists_success(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_123456",
        profile_identifier="76561198000000002",
    )
    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        raise AssertionError(request.full_url)

    outcome = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)

    assert outcome.snapshot.resolved.ok is True
    assert len(requests) == 2
    assert any("include_appinfo=True" in url for url in requests)
    owned_cache = read_cache_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path)
    )
    assert owned_cache.ok is True
    assert owned_cache.fetched_at == NOW


def test_abandonment_reuses_daily_library_but_manual_refreshes_both_sources(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_source_ttl_123456",
        profile_identifier="76561198000000011",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    for cache_key, source_id, payload, age in (
        (
            OWNED_GAMES_CACHE_KEY,
            SteamSourceId.OWNED_GAMES,
            _fixture("owned_games_last_played.json"),
            30 * 60,
        ),
        (
            RECENT_GAMES_CACHE_KEY,
            SteamSourceId.RECENTLY_PLAYED,
            _fixture("recent_games_for_abandonment.json"),
            11 * 60,
        ),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - age,
            ),
            cache_path_for_profile_key(profile_key, cache_key, root=tmp_path),
        )

    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        raise AssertionError(request.full_url)

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    assert sum("GetOwnedGames" in url for url in requests) == 0
    assert sum("GetRecentlyPlayedGames" in url for url in requests) == 1

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW + 1,
        force=True,
    )
    assert sum("GetOwnedGames" in url for url in requests) == 1
    assert sum("GetRecentlyPlayedGames" in url for url in requests) == 2


def test_abandonment_and_achievement_share_fresh_recent_games_source(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_shared_source_123456",
        profile_identifier="76561198000000012",
    )
    requests: list[str] = []

    class _Response:
        status = 200

        def __init__(self, payload: dict) -> None:
            self._data = json.dumps(payload).encode("utf-8")

        def read(self, _limit: int) -> bytes:
            return self._data

    def _opener(request, _timeout):
        requests.append(request.full_url)
        if "GetOwnedGames" in request.full_url:
            return _Response(_fixture("owned_games_last_played.json"))
        if "GetRecentlyPlayedGames" in request.full_url:
            return _Response(_fixture("recent_games_for_abandonment.json"))
        if "GetPlayerAchievements" in request.full_url:
            return _Response(
                {
                    "playerstats": {
                        "gameName": "Archive Candidate",
                        "achievements": [{"name": "FIRST", "achieved": 1}],
                    }
                }
            )
        if "GetSchemaForGame" in request.full_url:
            return _Response(
                {
                    "game": {
                        "availableGameStats": {
                            "achievements": [
                                {"name": "FIRST", "displayName": "First Visit"}
                            ]
                        }
                    }
                }
            )
        raise AssertionError(request.full_url)

    refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )
    refresh_achievement_pulse_cache(
        credential=credential,
        root=tmp_path,
        opener=_opener,
        now=NOW,
    )

    recent_requests = [url for url in requests if "GetRecentlyPlayedGames" in url]
    assert len(recent_requests) == 1


def test_abandonment_failed_refresh_preserves_valid_cached_library(tmp_path) -> None:
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_654321",
        profile_identifier="76561198000000003",
    )
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    write_cache_record(
        SteamCacheRecord(
            cache_key=OWNED_GAMES_CACHE_KEY,
            source_id=SteamSourceId.OWNED_GAMES,
            payload=_fixture("owned_games_last_played.json"),
            fetched_at=NOW - 1000,
        ),
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path),
    )

    class _Forbidden:
        status = 403

        def read(self, _limit: int) -> bytes:
            return b"{}"

    outcome = refresh_abandonment_cache(
        credential=credential,
        root=tmp_path,
        opener=lambda _request, _timeout: _Forbidden(),
        now=NOW,
    )

    assert outcome.connection_needs_attention is True
    assert outcome.snapshot.resolved.ok is True
    preserved = read_cache_record(
        cache_path_for_profile_key(profile_key, OWNED_GAMES_CACHE_KEY, root=tmp_path)
    )
    assert preserved.fetched_at == NOW - 1000


def test_guilt_desaturater_is_smooth_capped_and_prepared_outside_paint(tmp_path) -> None:
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 48), (230, 70, 40)).save(source)

    at_threshold = abandonment_desaturation_bucket(
        inactivity_days=84,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    later = abandonment_desaturation_bucket(
        inactivity_days=365,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    much_later = abandonment_desaturation_bucket(
        inactivity_days=5_000,
        enabled=True,
        maximum_percent=55,
        threshold_days=84,
    )
    prepared = prepare_desaturated_steam_artwork(
        source_path=source,
        cache_dir=tmp_path,
        desaturation_percent=later,
    )

    assert at_threshold == 0
    assert 0 < later < 55
    assert much_later == 55
    assert prepared != source
    assert prepared.is_file()
    assert prepare_desaturated_steam_artwork(
        source_path=source,
        cache_dir=tmp_path,
        desaturation_percent=later,
    ) == prepared


def test_abandonment_archival_layout_keeps_large_portrait_and_ledger_separate(qt_app) -> None:
    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )
    model = build_abandonment_view_model(resolved)
    authored = abandonment_authored_size(
        show_artwork=True,
        artwork_shape="square",
        artwork_size=180,
    )
    layout = layout_abandonment_card(
        model,
        QRectF(0, 0, authored.width(), authored.height()),
        show_artwork=True,
        artwork_shape="square",
        artwork_size=180,
    )

    assert authored.height() > 300
    assert layout.art_rect.bottom() < layout.authored_rect.bottom()
    assert not layout.art_rect.intersects(layout.title_rect)
    assert not layout.art_rect.intersects(layout.age_stamp_rect)
    assert all(not layout.art_rect.intersects(rect) for _field_id, rect in layout.field_rects)


def test_abandonment_renderer_produces_nonempty_archival_card(qt_app) -> None:
    resolved = resolve_abandonment_issues(
        owned_result=_owned_result(),
        recent_result=_recent_result(),
        now=NOW,
    )
    model = build_abandonment_view_model(resolved)
    image = QImage(560, 300, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    artwork = QImage(140, 196, QImage.Format.Format_RGB32)
    artwork.fill(QColor(190, 90, 45))
    painter = QPainter(image)
    try:
        layout = render_abandonment_card(
            painter,
            model,
            QRectF(0, 0, 560, 300),
            font_family="Inter",
            font_size=14,
            text_color=QColor(255, 255, 255, 230),
            logo_pixmap=None,
            artwork_image=artwork,
            show_artwork=True,
            artwork_shape="square",
            artwork_size=140,
            accent_color=QColor(222, 157, 88, 225),
        )
    finally:
        painter.end()

    assert not layout.art_rect.isNull()
    assert any(image.pixelColor(x, y).alpha() > 0 for x, y in ((30, 30), (40, 100), (250, 180)))


def test_abandonment_widget_applies_cache_before_first_coordinated_fade(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    from core.settings import storage_paths
    from core.steam import abandonment_cache

    storage_paths.reset_module_cache()
    monkeypatch.setattr(abandonment_cache.time, "time", lambda: NOW)
    credential = SteamCredentialPayload(
        api_key="fixture_api_key_111222",
        profile_identifier="76561198000000004",
    )
    write_credential_metadata(credential)
    profile_key = derive_profile_cache_key(credential.profile_identifier)
    for cache_key, source_id, payload in (
        (OWNED_GAMES_CACHE_KEY, SteamSourceId.OWNED_GAMES, _fixture("owned_games_last_played.json")),
        (RECENT_GAMES_CACHE_KEY, SteamSourceId.RECENTLY_PLAYED, _fixture("recent_games_for_abandonment.json")),
    ):
        write_cache_record(
            SteamCacheRecord(
                cache_key=cache_key,
                source_id=source_id,
                payload=payload,
                fetched_at=NOW - 60,
            ),
            cache_path_for_profile_key(profile_key, cache_key),
        )

    class _InlineThreadManager:
        def submit_io_task(self, func, *, task_id, callback):
            callback(TaskResult(success=True, result=func(), task_id=task_id))
            return task_id

    faded_models: list[tuple[str, str]] = []
    widget = AbandonmentIssuesWidget(
        definition=STEAM_CARD_DEFINITIONS["abandonment_issues"],
        position=OverlayPosition.BOTTOM_RIGHT,
        initial_view_model=SteamCardWidget.connect_required_model("abandonment_issues"),
        show_artwork=False,
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
        assert widget._view_model.appid is not None
        assert faded_models == [("content", widget._view_model.title)]
    finally:
        widget.cleanup()
        storage_paths.reset_module_cache()


def test_steam_content_transition_commits_at_hidden_midpoint_with_sparse_updates(qt_app, monkeypatch) -> None:
    animations: list[dict] = []

    class _AnimationManager:
        def animate_custom(self, **kwargs):
            animations.append(kwargs)
            return f"animation-{len(animations)}"

        def cancel_animation(self, _animation_id):
            return True

    manager = _AnimationManager()
    from core.animation.animator import AnimationManager

    monkeypatch.setattr(AnimationManager, "get_or_create_app_shared", classmethod(lambda cls: manager))
    monkeypatch.setattr(AnimationManager, "get_app_shared", classmethod(lambda cls: manager))
    widget = SteamCardWidget(definition=STEAM_CARD_DEFINITIONS["abandonment_issues"])
    commits: list[str] = []
    try:
        widget.apply_content_transition("first", lambda: commits.append("first"), animate=False)
        widget.show()
        widget._has_faded_in = True
        widget._has_displayed_valid_data = True
        widget.apply_content_transition("second", lambda: commits.append("second"), animate=True)

        assert commits == ["first"]
        assert len(animations) == 1
        animations[0]["update_callback"](0.01)
        assert widget.content_opacity() == 1.0
        animations[0]["update_callback"](1.0)
        animations[0]["on_complete"]()
        assert commits == ["first", "second"]
        assert widget.content_opacity() == 0.0
        assert len(animations) == 2
        animations[1]["update_callback"](1.0)
        animations[1]["on_complete"]()
        assert widget.content_opacity() == 1.0
    finally:
        widget.cleanup()
