"""F4-preservation tests for the temporary Media QWidget state bridge."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor

import widgets.media.display_update as display_update
from core.media.media_controller import MediaPlaybackState, MediaTrackInfo


class _StubMediaControls:
    def __init__(self) -> None:
        self._last_info = None
        self._last_track_identity = None
        self._last_display_update_ts = 0.0
        self._has_seen_first_track = True
        self._telemetry_last_visibility = True
        self._perf_media_display_total = 0
        self._playback_progress_enabled = True
        self._playback_progress_fill_color = QColor(255, 255, 255, 230)
        self._playback_progress_shadow_enabled = False
        self._playback_progress_glow_enabled = False
        self._playback_progress_glow_color = QColor(255, 255, 255, 180)
        self._playback_progress_paint_key = None
        self._playback_progress_visible = False
        self._playback_progress_fill_width = 0
        self._custom_layout_shell_active = False
        self.visible = True
        self.emitted = []
        self.updates = 0
        self.fade_calls = 0
        self.notify_calls = 0
        self.hide_calls = 0
        self.complete_hide_calls = 0

    def parent(self):
        return None

    def parentWidget(self):
        return None

    def isVisible(self) -> bool:
        return self.visible

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.hide_calls += 1
        self.visible = False

    def _complete_hide_sequence(self) -> None:
        self.complete_hide_calls += 1
        self.visible = False

    def _start_widget_fade_in(self, *_args) -> None:
        self.fade_calls += 1
        self.visible = True

    def _notify_spotify_widgets_visibility(self) -> None:
        self.notify_calls += 1

    def _emit_media_update(self, info) -> None:
        self.emitted.append(info)

    def _safe_update(self) -> None:
        self.updates += 1

    def _compute_track_identity(self, info):
        return (
            info.title,
            info.artist,
            info.album,
            info.state.value,
            info.can_play_pause,
            info.can_previous,
            info.can_next,
        )

    def _compute_controls_layout(self):
        return {"progress_rect": QRect(10, 20, 100, 8)}


def _info(**overrides) -> MediaTrackInfo:
    values = {
        "title": "Track",
        "artist": "Artist",
        "album": "Album",
        "state": MediaPlaybackState.PLAYING,
        "can_play_pause": True,
        "can_previous": True,
        "can_next": True,
        "position_ms": 25_000,
        "duration_ms": 100_000,
    }
    values.update(overrides)
    return MediaTrackInfo(**values)


def test_none_snapshot_hides_controls_without_runtime_mutation() -> None:
    widget = _StubMediaControls()
    runtime_calls = []
    widget._runtime_service = SimpleNamespace(
        refresh=lambda **kwargs: runtime_calls.append(("refresh", kwargs)),
        set_provider_runtime=lambda *args, **kwargs: runtime_calls.append(
            ("provider", args, kwargs)
        ),
    )

    display_update.update_display(widget, None)

    assert runtime_calls == []
    assert widget._last_info is None
    assert widget.complete_hide_calls == 1
    assert widget._playback_progress_visible is False


def test_first_snapshot_publishes_and_reveals_through_existing_fade_path(
    monkeypatch,
) -> None:
    widget = _StubMediaControls()
    widget._has_seen_first_track = False
    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)
    info = _info()

    display_update.update_display(widget, info)

    assert widget.emitted == [info]
    assert widget.hide_calls == 1
    assert widget.fade_calls == 1
    assert widget.notify_calls == 1


def test_playback_state_change_repaints_and_publishes_for_f4_consumers() -> None:
    widget = _StubMediaControls()
    playing = _info()
    paused = _info(state=MediaPlaybackState.PAUSED)

    display_update.update_display(widget, playing)
    widget.emitted.clear()
    widget.updates = 0
    display_update.update_display(widget, paused)

    assert widget._last_info is paused
    assert widget.emitted == [paused]
    assert widget.updates == 1


def test_custom_edit_mode_does_not_restore_hidden_controls() -> None:
    widget = _StubMediaControls()
    widget.visible = False
    widget._custom_layout_shell_active = True

    display_update.update_display(widget, _info())

    assert widget.fade_calls == 0
    assert widget.visible is False


def test_progress_pixel_change_requests_one_repaint_without_publication() -> None:
    widget = _StubMediaControls()
    first = _info(position_ms=25_000)
    second = _info(position_ms=26_000)
    display_update.update_display(widget, first)
    widget.emitted.clear()
    widget.updates = 0

    display_update.update_display(widget, second)

    assert widget._playback_progress_fill_width == 26
    assert widget.emitted == []
    assert widget.updates == 1


def test_subpixel_progress_change_requests_no_repaint() -> None:
    widget = _StubMediaControls()
    display_update.update_display(widget, _info(position_ms=25_000))
    widget.updates = 0

    display_update.update_display(widget, _info(position_ms=25_400))

    assert widget._playback_progress_fill_width == 25
    assert widget.updates == 0


def test_unknown_duration_clears_progress_once() -> None:
    widget = _StubMediaControls()
    display_update.update_display(widget, _info())
    widget.updates = 0

    display_update.update_display(widget, _info(duration_ms=0, position_ms=0))
    first_updates = widget.updates
    display_update.update_display(widget, _info(duration_ms=0, position_ms=0))

    assert widget._playback_progress_visible is False
    assert first_updates == 1
    assert widget.updates == 1


def test_paused_unchanged_progress_snapshot_is_static() -> None:
    widget = _StubMediaControls()
    paused = _info(state=MediaPlaybackState.PAUSED, position_ms=40_000)
    display_update.update_display(widget, paused)
    widget.updates = 0
    widget.emitted.clear()

    display_update.update_display(widget, paused)

    assert widget.updates == 0
    assert widget.emitted == []
