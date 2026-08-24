from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPixmap

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork
from widgets.media_widget import MediaWidget


def test_media_widget_track_identity_includes_artwork_key() -> None:
    stub = SimpleNamespace(
        _compute_artwork_key=lambda info: ("artwork", len(info.artwork or b"")),
    )
    info = SimpleNamespace(
        title=" Track ",
        artist=" Artist ",
        album=" Album ",
        state=SimpleNamespace(value="playing"),
        artwork=b"frame-bytes",
    )

    identity = MediaWidget._compute_track_identity(stub, info)

    assert identity == ("track", "artist", "album", "playing", ("artwork", 11))


def test_media_display_update_stores_structured_paint_metadata(qt_app) -> None:
    widget = MediaWidget()
    try:
        from widgets.media.display_update import update_display

        info = MediaTrackInfo(
            title="Healing Out Of Spite",
            artist="Catty",
            state=MediaPlaybackState.PLAYING,
        )

        update_display(widget, info)

        metadata = widget._metadata_paint
        assert widget.textFormat() == Qt.TextFormat.PlainText
        assert widget.text() == ""
        assert metadata["provider"] == widget.provider_display_name
        assert metadata["title"] == "Healing Out Of Spite"
        assert metadata["artist"] == "Catty"
        assert metadata["title_font"] == widget._font_size + 3
        assert metadata["artist_font"] == widget._font_size - 2
    finally:
        widget.deleteLater()


def test_media_widget_header_metrics_exist_before_first_metadata_update(qt_app) -> None:
    widget = MediaWidget()
    try:
        assert widget._header_font_pt > 0
        assert widget._header_logo_size > 0
        assert widget._header_logo_margin >= widget._header_logo_size
    finally:
        widget.deleteLater()


def test_media_widget_projects_accepted_runtime_snapshot(qt_app):
    widget = MediaWidget(build_default_runtime=False)
    projected = []
    track = MediaTrackInfo(
        title="Accepted Track",
        artist="Artist",
        state=MediaPlaybackState.PLAYING,
    )
    widget._update_display = lambda info, artwork, revision: projected.append(
        (info, artwork, revision)
    )
    snapshot = MediaRuntimeSnapshot(
        revision=7,
        provider="spotify",
        info=track,
        artwork=PreparedMediaArtwork((0, ""), None, 0.0),
    )

    try:
        widget.on_media_runtime_snapshot(snapshot)

        assert projected == [(track, snapshot.artwork, 7)]
        assert widget._last_runtime_revision == 7
        assert widget._artwork_update_generation == 7
    finally:
        widget.deleteLater()


def test_media_widget_runtime_replay_resets_stale_provider_projection(qt_app):
    widget = MediaWidget(build_default_runtime=False, provider="spotify")
    projected = []
    widget._applied_artwork_key = (12, "old")
    widget._last_track_identity = ("old",)
    widget._update_display = lambda info, artwork, revision: projected.append(
        (info, artwork, revision)
    )
    track = MediaTrackInfo(
        title="MusicBee Track",
        artist="Artist",
        state=MediaPlaybackState.PLAYING,
    )
    snapshot = MediaRuntimeSnapshot(
        revision=11,
        provider="musicbee",
        info=track,
        artwork=PreparedMediaArtwork((0, ""), None, 0.0),
    )

    try:
        widget.on_media_runtime_snapshot(snapshot)

        assert widget.provider == "musicbee"
        assert widget._applied_artwork_key is None
        assert widget._last_track_identity is None
        assert projected == [(track, snapshot.artwork, 11)]
    finally:
        widget.deleteLater()


def test_media_widget_delegates_provider_controls_and_refresh_to_runtime_service(qt_app):
    calls = []

    class _Runtime:
        def set_provider_runtime(self, provider, *, source):
            calls.append(("provider", provider, source))
            return True

        def play_pause(self, *, execute):
            calls.append(("play_pause", execute))
            return True

        def next_track(self, *, execute):
            calls.append(("next", execute))
            return True

        def previous_track(self, *, execute):
            calls.append(("previous", execute))
            return True

        def refresh(self, *, bust_cache=False):
            calls.append(("refresh", bust_cache))
            return True

    widget = MediaWidget(build_default_runtime=False)
    widget._runtime_service = _Runtime()
    widget._enabled = True
    widget._handle_control_feedback = lambda *args, **kwargs: None
    try:
        assert widget.set_provider_runtime("spotify") is True
        widget.play_pause(execute=False)
        widget.next_track(execute=False)
        widget.previous_track(execute=False)
        assert widget._request_refresh_after_control() is True

        assert calls == [
            ("provider", "spotify", "settings"),
            ("play_pause", False),
            ("next", False),
            ("previous", False),
            ("refresh", True),
        ]
    finally:
        widget.deleteLater()


def test_media_lifecycle_activation_without_thread_manager_fails_closed(qt_app):
    widget = MediaWidget(build_default_runtime=False)
    try:
        assert widget.initialize() is True
        assert widget.activate() is False
        assert widget._enabled is False
        assert widget._lifecycle_state.name == "INITIALIZED"
    finally:
        widget.deleteLater()


def test_media_display_update_does_not_restore_live_widget_during_custom_edit_mode(qt_app) -> None:
    from widgets.media.display_update import _ensure_widget_visible_for_active_metadata

    parent = SimpleNamespace(_custom_layout_edit_active=True)
    calls: list[str] = []
    widget = SimpleNamespace(
        parentWidget=lambda: parent,
        _custom_layout_shell_active=True,
        _telemetry_last_visibility=None,
        isVisible=lambda: False,
        _start_widget_fade_in=lambda *_args, **_kwargs: calls.append("fade"),
        _notify_spotify_widgets_visibility=lambda: calls.append("notify"),
        show=lambda: calls.append("show"),
    )

    _ensure_widget_visible_for_active_metadata(widget)

    assert calls == []
    assert widget._telemetry_last_visibility is False


def test_media_widget_no_hidden_qlabel_render_shadow_path() -> None:
    source = Path("widgets/media_widget.py").read_text(encoding="utf-8")

    assert "_ensure_native_text_shadow_pixmap" not in source
    assert "label.render" not in source


def test_media_widget_artwork_fade_uses_app_shared_animation_manager() -> None:
    source = Path("widgets/media_widget.py").read_text(encoding="utf-8")

    assert "AnimationManager.get_or_create_app_shared()" in source


def test_media_header_logo_scaling_is_cached_per_dpr_and_size(qt_app) -> None:
    from widgets.media.painting import _scaled_header_logo

    widget = MediaWidget()
    logo = QPixmap(96, 96)
    logo.fill(QColor(30, 215, 96))

    try:
        first = _scaled_header_logo(widget, logo, 72, 1.5)
        second = _scaled_header_logo(widget, logo, 72, 1.5)
        resized = _scaled_header_logo(widget, logo, 84, 1.5)

        assert second is first
        assert resized is not first
        assert widget._header_logo_scaled_cache is resized
    finally:
        widget.deleteLater()


def test_media_header_expands_into_artwork_gap_before_eliding(qt_app) -> None:
    from widgets.media.painting import _header_layout

    widget = MediaWidget()
    try:
        widget.resize(900, 420)
        widget._provider = "musicbee"
        widget._header_logo_size = 34
        widget._header_logo_margin = 54
        widget._header_font_pt = 34
        widget._artwork_size = 300
        artwork = QPixmap(300, 300)
        artwork.fill(QColor(200, 80, 40))
        widget._artwork_pixmap = artwork

        layout = _header_layout(widget)
        metrics = QFontMetrics(layout["font"])

        assert layout["text_width"] >= metrics.horizontalAdvance("MUSICBEE")
    finally:
        widget.deleteLater()


def test_media_layout_deferred_update_position_skips_invalid_widget(monkeypatch) -> None:
    from widgets import media_layout

    callbacks = []
    widget = SimpleNamespace(_update_position=lambda: (_ for _ in ()).throw(AssertionError("should not run")))

    monkeypatch.setattr(
        media_layout.ThreadManager,
        "single_shot",
        lambda _ms, cb: callbacks.append(cb),
    )
    monkeypatch.setattr(media_layout.Shiboken, "isValid", lambda _widget: False)

    media_layout._defer_update_position(widget)

    assert len(callbacks) == 1
    callbacks[0]()


def test_media_layout_deferred_update_position_runs_when_widget_still_valid(monkeypatch) -> None:
    from widgets import media_layout

    callbacks = []
    calls = []
    widget = SimpleNamespace(_update_position=lambda: calls.append("updated"))

    monkeypatch.setattr(
        media_layout.ThreadManager,
        "single_shot",
        lambda _ms, cb: callbacks.append(cb),
    )
    monkeypatch.setattr(media_layout.Shiboken, "isValid", lambda _widget: True)

    media_layout._defer_update_position(widget)

    assert len(callbacks) == 1
    callbacks[0]()
    assert calls == ["updated"]


def test_media_controls_layout_compacts_for_small_committed_card(qt_app) -> None:
    from widgets.media_layout import compute_controls_layout

    widget = MediaWidget()
    try:
        widget._show_controls = True
        widget.resize(600, 290)
        large_layout = compute_controls_layout(widget)
        large_font = large_layout["font"].pointSize()
        large_row_height = large_layout["row_rect"].height()

        widget.resize(480, 232)
        widget._controls_layout_cache = None
        small_layout = compute_controls_layout(widget)

        assert small_layout["font"].pointSize() < large_font
        assert small_layout["row_rect"].height() < large_row_height
    finally:
        widget.deleteLater()


def test_media_artwork_size_rebuilds_from_neutral_retained_snapshot(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget.resize(390, 187)
        info = MediaTrackInfo(
            title="Modest Mountains",
            artist="Field Division",
            album="Reverie State",
            state=MediaPlaybackState.PLAYING,
            artwork=b"art",
        )
        service = widget._runtime_service
        assert service is not None and service.shared_owner is not None
        service.shared_owner._current_info = info
        widget._last_info = None
        widget._has_seen_first_track = True
        artwork = QPixmap(200, 200)
        artwork.fill(QColor(200, 80, 40))
        widget._artwork_pixmap = artwork
        widget._metadata_paint = {
            "provider": "SPOTIFY",
            "title": "Modest Mountains",
            "artist": "Field Division",
            "base_font": 20,
            "header_font": 40,
            "title_font": 36,
            "artist_font": 28,
            "header_weight": 750,
            "title_weight": 700,
            "artist_weight": 600,
            "line_spacing": 8,
            "body_top_gap": 12,
        }
        widget._last_metadata_identity = widget._compute_metadata_identity(info)

        widget.set_artwork_size(130)

        assert int(widget._metadata_paint["header_font"]) < 40
        assert int(widget._metadata_paint["title_font"]) < 36
        assert int(widget._metadata_paint["artist_font"]) < 28
        assert int(widget._metadata_paint["line_spacing"]) <= 3
    finally:
        widget.deleteLater()


def test_media_keyboard_home_alias_defers_local_execution_until_timeout(qt_app) -> None:
    widget = MediaWidget()
    try:
        calls = []
        widget.handle_transport_command = lambda key, *, source="manual", execute=True: calls.append((key, source, execute)) or True  # type: ignore[method-assign]

        deferred = widget._should_defer_keyboard_alias_command("keyboard_home", "play")

        assert deferred is True
        assert widget._pending_keyboard_alias_command is not None
        assert calls == []

        widget._pending_keyboard_alias_timer.timeout.emit()

        assert calls == [("play", "keyboard_home_deferred", True)]
        assert widget._pending_keyboard_alias_command is None
        assert widget._pending_keyboard_alias_timer is None
    finally:
        widget.deleteLater()


def test_media_external_transport_feedback_consumes_pending_keyboard_home_alias(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget._should_defer_keyboard_alias_command("keyboard_home", "play")

        assert widget._pending_keyboard_alias_command is not None
        assert widget._pending_keyboard_alias_timer is not None

        widget._consume_matching_keyboard_alias("play")

        assert widget._pending_keyboard_alias_command is None
        assert widget._pending_keyboard_alias_timer is None
    finally:
        widget.deleteLater()


def test_media_duplicate_external_transport_feedback_is_suppressed(qt_app) -> None:
    widget = MediaWidget(build_default_runtime=False)
    calls = []
    widget._runtime_service = SimpleNamespace(
        play_pause=lambda *, execute: calls.append(execute) or True,
    )
    widget._handle_control_feedback = lambda *args, **kwargs: None
    try:
        assert widget.handle_transport_command(
            "play", source="appcommand:play", execute=False
        )
        assert widget.handle_transport_command(
            "play", source="media_key", execute=False
        )

        assert calls == [False]
    finally:
        widget.deleteLater()


def test_media_header_fits_spotify_in_runtime_geometry_before_eliding(qt_app) -> None:
    from widgets.media.painting import _header_layout

    widget = MediaWidget()
    try:
        widget.resize(890, 420)
        widget._provider = "spotify"
        widget._header_logo_size = 52
        widget._header_logo_margin = 52
        widget._header_font_pt = 40
        widget._artwork_size = 300
        widget.setContentsMargins(29, 12, widget._artwork_size + 40, 42)
        artwork = QPixmap(300, 300)
        artwork.fill(QColor(200, 80, 40))
        widget._artwork_pixmap = artwork

        layout = _header_layout(widget)
        metrics = QFontMetrics(layout["font"])

        assert layout["text_width"] >= metrics.horizontalAdvance("SPOTIFY") + 8
    finally:
        widget.deleteLater()


def test_media_header_elides_only_when_artwork_collision_is_unavoidable(qt_app) -> None:
    from widgets.media.painting import _header_layout

    widget = MediaWidget()
    try:
        widget.resize(340, 260)
        widget._provider = "musicbee"
        widget._header_logo_size = 34
        widget._header_logo_margin = 54
        widget._header_font_pt = 60
        widget._artwork_size = 220
        artwork = QPixmap(220, 220)
        artwork.fill(QColor(200, 80, 40))
        widget._artwork_pixmap = artwork

        layout = _header_layout(widget)
        metrics = QFontMetrics(layout["font"])

        assert layout["text_width"] < metrics.horizontalAdvance("MUSICBEE")
    finally:
        widget.deleteLater()


def test_media_set_artwork_size_respects_active_custom_rect(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget._custom_layout_local_rect = QRect(20, 30, 640, 410)
        reapply_calls = []
        widget._schedule_custom_layout_geometry_reapply = lambda: reapply_calls.append("reapply")  # type: ignore[method-assign]

        widget.set_artwork_size(360)

        assert widget.minimumHeight() == 410
        assert reapply_calls == ["reapply"]
    finally:
        widget.deleteLater()


def test_media_progress_layout_is_bounded_above_transport_controls(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget.resize(600, 320)
        widget._playback_progress_enabled = True
        widget._playback_progress_height = 8
        widget._refresh_metadata_paint_boundary()
        widget._invalidate_controls_layout()

        layout = widget._compute_controls_layout()
        progress_rect = layout["progress_rect"]
        row_rect = layout["row_rect"]

        assert progress_rect.isEmpty() is False
        assert progress_rect.height() == 8
        assert progress_rect.left() >= widget.contentsMargins().left()
        assert progress_rect.right() < widget.width() - widget.contentsMargins().right()
        assert progress_rect.bottom() < row_rect.top()
    finally:
        widget.deleteLater()


def test_media_progress_metadata_boundary_is_cached_and_inert_when_disabled(
    qt_app,
    monkeypatch,
) -> None:
    from widgets.media import painting

    widget = MediaWidget()
    calls: list[bool] = []
    original = painting.metadata_paint_bottom
    monkeypatch.setattr(
        painting,
        "metadata_paint_bottom",
        lambda owner: (calls.append(True), original(owner))[1],
    )
    try:
        widget.resize(600, 320)
        widget._playback_progress_enabled = False
        widget._invalidate_controls_layout()
        widget._compute_controls_layout()
        assert calls == []

        widget._playback_progress_enabled = True
        widget._refresh_metadata_paint_boundary()
        widget._compute_controls_layout()
        widget._compute_controls_layout()
        assert calls == [True]
    finally:
        widget.deleteLater()


def test_small_custom_media_card_hides_progress_lane_before_metadata_overlap(qt_app) -> None:
    widget = MediaWidget()
    try:
        custom_rect = QRect(20, 30, 420, 240)
        widget._custom_layout_local_rect = custom_rect
        widget.setMinimumSize(1, 1)
        widget.setMaximumSize(10_000, 10_000)
        widget.resize(custom_rect.size())
        widget._playback_progress_enabled = True
        widget._playback_progress_height = 8
        widget._artwork_size = 160
        artwork = QPixmap(160, 160)
        artwork.fill(QColor(30, 90, 160))
        widget._artwork_pixmap = artwork
        widget.setContentsMargins(29, 12, 200, 12)
        widget._metadata_paint = {
            "provider": "SPOTIFY",
            "title": (
                "A deliberately long authored title that wraps through several lines "
                "inside a compact custom media card"
            ),
            "artist": "A deliberately long artist identity",
            "header_font": 24,
            "title_font": 23,
            "artist_font": 18,
            "header_weight": 750,
            "title_weight": 700,
            "artist_weight": 600,
            "line_spacing": 3,
            "body_top_gap": 6,
        }
        widget._refresh_metadata_paint_boundary()

        layout = widget._compute_controls_layout()

        assert layout["progress_rect"].isEmpty() is True
        assert widget.geometry().size() == custom_rect.size()
    finally:
        widget.deleteLater()


def test_media_progress_config_preserves_committed_custom_geometry(qt_app) -> None:
    widget = MediaWidget()
    try:
        custom_rect = QRect(20, 30, 640, 410)
        widget._custom_layout_local_rect = custom_rect
        widget._fixed_card_height = custom_rect.height()

        widget.set_playback_progress_config(
            enabled=True,
            height=10,
            fill_color=QColor(20, 180, 240, 230),
            shadow_enabled=True,
            glow_enabled=True,
            glow_color=QColor(20, 180, 240, 180),
        )

        assert widget._fixed_card_height == custom_rect.height()
        assert widget._playback_progress_enabled is True
        assert widget._playback_progress_height == 10
    finally:
        widget.deleteLater()


def test_media_progress_config_refreshes_scalar_paint_state_without_display_pipeline(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget.resize(600, 320)
        widget._last_info = MediaTrackInfo(
            title="Track",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
            position_ms=30_000,
            duration_ms=120_000,
        )
        widget._update_display = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("progress styling must not enter the media publication pipeline")
        )
        updates: list[bool] = []
        widget._safe_update = lambda: updates.append(True)

        widget.set_playback_progress_config(
            enabled=True,
            height=8,
            fill_color=QColor(20, 180, 240, 230),
            shadow_enabled=False,
            glow_enabled=False,
            glow_color=QColor(20, 180, 240, 180),
        )

        assert updates == [True]
        assert widget._playback_progress_visible is True
        assert widget._playback_progress_fill_width > 0
    finally:
        widget.deleteLater()


def test_media_progress_resize_requantizes_existing_snapshot_immediately(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget.setMinimumSize(1, 1)
        widget.setMaximumSize(10_000, 10_000)
        widget.resize(600, 320)
        widget.show()
        qt_app.processEvents()
        widget._last_info = MediaTrackInfo(
            title="Track",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
            position_ms=60_000,
            duration_ms=120_000,
        )
        widget.set_playback_progress_config(
            enabled=True,
            height=8,
            fill_color=QColor(20, 180, 240, 230),
            shadow_enabled=False,
            glow_enabled=False,
            glow_color=QColor(20, 180, 240, 180),
        )
        old_fill_width = widget._playback_progress_fill_width
        updates: list[bool] = []
        widget._safe_update = lambda: updates.append(True)

        widget.resize(480, 320)
        qt_app.processEvents()
        layout = widget._compute_controls_layout()

        assert widget._playback_progress_fill_width == round(
            layout["progress_rect"].width() * 0.5
        )
        assert widget._playback_progress_fill_width < old_fill_width
        assert updates == [True]
    finally:
        widget.deleteLater()


def test_first_media_snapshot_requantizes_progress_after_card_geometry_commit(qt_app) -> None:
    from widgets.media.display_update import update_display

    widget = MediaWidget()
    try:
        widget.set_playback_progress_config(
            enabled=True,
            height=8,
            fill_color=QColor(20, 180, 240, 230),
            shadow_enabled=False,
            glow_enabled=False,
            glow_color=QColor(20, 180, 240, 180),
        )

        update_display(
            widget,
            MediaTrackInfo(
                title="Track",
                artist="Artist",
                state=MediaPlaybackState.PLAYING,
                position_ms=30_000,
                duration_ms=120_000,
            ),
        )
        layout = widget._compute_controls_layout()

        assert widget._playback_progress_visible is True
        assert widget._playback_progress_fill_width == round(
            layout["progress_rect"].width() * 0.25
        )
    finally:
        widget.deleteLater()
