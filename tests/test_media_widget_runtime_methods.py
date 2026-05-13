from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from PySide6.QtCore import Qt
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


def test_media_widget_no_hidden_qlabel_render_shadow_path() -> None:
    source = Path("widgets/media_widget.py").read_text(encoding="utf-8")

    assert "_ensure_native_text_shadow_pixmap" not in source
    assert "label.render" not in source


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
