from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

from PySide6.QtCore import Qt

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
