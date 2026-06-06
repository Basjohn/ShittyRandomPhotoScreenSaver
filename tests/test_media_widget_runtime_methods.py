from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPixmap

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_widget import MediaWidget


class _PollStageStub:
    def __init__(self) -> None:
        self._current_poll_stage = 0
        self._polls_at_current_stage = 0
        self._poll_intervals = [1000, 2000, 2500]
        self.ensure_timer_calls = []

    def _ensure_timer(self, *, force: bool = False) -> None:
        self.ensure_timer_calls.append(bool(force))


def test_media_widget_advance_poll_stage_restarts_timer() -> None:
    stub = _PollStageStub()

    MediaWidget._advance_poll_stage(stub)

    assert stub._current_poll_stage == 1
    assert stub._polls_at_current_stage == 0
    assert stub.ensure_timer_calls == [True]


def test_media_widget_reset_poll_stage_restarts_timer_only_when_needed() -> None:
    stub = _PollStageStub()
    stub._current_poll_stage = 2

    MediaWidget._reset_poll_stage(stub)

    assert stub._current_poll_stage == 0
    assert stub._polls_at_current_stage == 0
    assert stub.ensure_timer_calls == [True]

    MediaWidget._reset_poll_stage(stub)

    assert stub.ensure_timer_calls == [True]


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

    monkeypatch.setattr(media_layout.QTimer, "singleShot", lambda _ms, cb: callbacks.append(cb))
    monkeypatch.setattr(media_layout.Shiboken, "isValid", lambda _widget: False)

    media_layout._defer_update_position(widget)

    assert len(callbacks) == 1
    callbacks[0]()


def test_media_layout_deferred_update_position_runs_when_widget_still_valid(monkeypatch) -> None:
    from widgets import media_layout

    callbacks = []
    calls = []
    widget = SimpleNamespace(_update_position=lambda: calls.append("updated"))

    monkeypatch.setattr(media_layout.QTimer, "singleShot", lambda _ms, cb: callbacks.append(cb))
    monkeypatch.setattr(media_layout.Shiboken, "isValid", lambda _widget: True)

    media_layout._defer_update_position(widget)

    assert len(callbacks) == 1
    callbacks[0]()
    assert calls == ["updated"]


def test_media_pending_state_timer_registers_and_is_cleared_on_stop(qt_app, monkeypatch) -> None:
    widget = MediaWidget()
    registrations = []
    try:
        widget._enabled = True
        widget._thread_manager = None
        widget._safe_update = lambda: None
        widget._refresh = lambda: None
        widget._register_resource = lambda resource, description: registrations.append((resource, description))

        widget._apply_pending_state_override(MediaPlaybackState.PLAYING)

        assert widget._pending_state_timer is not None
        assert len(registrations) == 1
        assert registrations[0][0] is widget._pending_state_timer
        assert registrations[0][1] == "pending state debounce timer"

        widget.stop()

        assert widget._pending_state_timer is None
        assert widget._pending_state_override is None
    finally:
        widget.deleteLater()


def test_media_reset_update_timer_state_stops_and_optionally_deletes_timer() -> None:
    class _FakeHandle:
        def __init__(self) -> None:
            self.stop_calls = 0

        def stop(self) -> None:
            self.stop_calls += 1

    class _FakeTimer:
        def __init__(self) -> None:
            self.stop_calls = 0
            self.delete_calls = 0

        def stop(self) -> None:
            self.stop_calls += 1

        def deleteLater(self) -> None:
            self.delete_calls += 1

    stub = SimpleNamespace(
        _update_timer_handle=_FakeHandle(),
        _update_timer=_FakeTimer(),
    )

    MediaWidget._reset_update_timer_state(stub, delete_qtimer=False)

    assert stub._update_timer_handle is None
    assert stub._update_timer is None

    handle = _FakeHandle()
    timer = _FakeTimer()
    stub = SimpleNamespace(
        _update_timer_handle=handle,
        _update_timer=timer,
    )

    MediaWidget._reset_update_timer_state(stub, delete_qtimer=True)

    assert handle.stop_calls == 1
    assert timer.stop_calls == 1
    assert timer.delete_calls == 1
    assert stub._update_timer_handle is None
    assert stub._update_timer is None


def test_media_stop_timer_uses_canonical_update_timer_reset(monkeypatch) -> None:
    stub = SimpleNamespace()
    calls = []

    def _fake_reset(*, delete_qtimer: bool) -> None:
        calls.append(delete_qtimer)

    stub._reset_update_timer_state = _fake_reset

    MediaWidget._stop_timer(stub)

    assert calls == [False]


def test_media_ensure_timer_reuses_active_timer_for_same_interval(monkeypatch) -> None:
    class _FakeTimer:
        def __init__(self) -> None:
            self.set_intervals = []
            self.start_calls = 0

        def isActive(self) -> bool:
            return True

        def setInterval(self, interval: int) -> None:
            self.set_intervals.append(interval)

        def start(self) -> None:
            self.start_calls += 1

    create_calls = []
    monkeypatch.setattr("widgets.media_widget.create_overlay_timer", lambda *args, **kwargs: create_calls.append((args, kwargs)))

    timer = _FakeTimer()
    handle = SimpleNamespace(_timer=timer)
    stub = SimpleNamespace(
        _is_idle=False,
        _app_process_running=False,
        _deep_idle_poll_interval=30000,
        _idle_poll_interval=5000,
        _poll_intervals=[1000, 2000, 2500],
        _current_poll_stage=1,
        _update_timer_handle=handle,
        _update_timer=timer,
        _update_timer_interval_ms=2000,
    )

    MediaWidget._ensure_timer(stub, force=False)

    assert create_calls == []
    assert timer.set_intervals == []
    assert timer.start_calls == 0
    assert stub._update_timer_interval_ms == 2000


def test_media_ensure_timer_retunes_active_timer_in_place(monkeypatch) -> None:
    class _FakeTimer:
        def __init__(self) -> None:
            self.set_intervals = []
            self.start_calls = 0

        def isActive(self) -> bool:
            return True

        def setInterval(self, interval: int) -> None:
            self.set_intervals.append(interval)

        def start(self) -> None:
            self.start_calls += 1

    create_calls = []
    monkeypatch.setattr("widgets.media_widget.create_overlay_timer", lambda *args, **kwargs: create_calls.append((args, kwargs)))

    timer = _FakeTimer()
    handle = SimpleNamespace(_timer=timer)
    stub = SimpleNamespace(
        _is_idle=False,
        _app_process_running=False,
        _deep_idle_poll_interval=30000,
        _idle_poll_interval=5000,
        _poll_intervals=[1000, 2000, 2500],
        _current_poll_stage=2,
        _update_timer_handle=handle,
        _update_timer=timer,
        _update_timer_interval_ms=2000,
    )

    MediaWidget._ensure_timer(stub, force=True)

    assert create_calls == []
    assert timer.set_intervals == [2500]
    assert timer.start_calls == 1
    assert stub._update_timer_interval_ms == 2500


def test_media_clear_pending_state_timer_uses_canonical_reset() -> None:
    stub = SimpleNamespace()
    calls = []

    def _fake_reset(*, delete_timer: bool) -> None:
        calls.append(delete_timer)

    stub._reset_pending_state_override = _fake_reset

    MediaWidget._clear_pending_state_timer(stub)

    assert calls == [True]


def test_media_play_pause_optimistic_feedback_uses_update_not_repaint(qt_app) -> None:
    widget = MediaWidget()
    try:
        widget._enabled = True
        widget._show_controls = True
        widget._controller = SimpleNamespace(play_pause=lambda: None)
        widget._last_info = MediaTrackInfo(
            title="Song",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
        )
        widget._emit_media_update = lambda info: None  # type: ignore[method-assign]
        widget._invalidate_controls_layout = lambda: None  # type: ignore[method-assign]
        widget._apply_pending_state_override = lambda state: None  # type: ignore[method-assign]
        widget._handle_control_feedback = lambda *args, **kwargs: None  # type: ignore[method-assign]
        widget.isVisible = lambda: True  # type: ignore[method-assign]

        updates = []
        repaints = []
        widget.update = lambda: updates.append("update")  # type: ignore[method-assign]
        widget.repaint = lambda: repaints.append("repaint")  # type: ignore[method-assign]

        widget.play_pause()

        assert updates == ["update"]
        assert repaints == []
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
    widget = MediaWidget()
    try:
        widget._enabled = True
        widget._show_controls = True
        widget._last_info = MediaTrackInfo(
            title="Song",
            artist="Artist",
            state=MediaPlaybackState.PLAYING,
        )
        widget._emit_media_update = lambda info: None  # type: ignore[method-assign]
        widget._invalidate_controls_layout = lambda: None  # type: ignore[method-assign]
        widget._handle_control_feedback = lambda *args, **kwargs: None  # type: ignore[method-assign]
        widget.isVisible = lambda: True  # type: ignore[method-assign]
        widget.update = lambda: None  # type: ignore[method-assign]

        widget.handle_transport_command("play", source="appcommand:play", execute=False)
        first_state = widget._last_info.state
        widget.handle_transport_command("play", source="media_key", execute=False)

        assert first_state == MediaPlaybackState.PAUSED
        assert widget._last_info.state == MediaPlaybackState.PAUSED
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
