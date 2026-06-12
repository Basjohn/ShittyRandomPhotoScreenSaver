from __future__ import annotations

from types import SimpleNamespace

import widgets.media.display_update as display_update
from core.media.media_controller import MediaPlaybackState, MediaTrackInfo


class _StubMediaWidget:
    _shared_last_valid_info = None
    _shared_last_valid_info_ts = 0.0

    def __init__(self) -> None:
        self._last_info = None
        self._consecutive_none_count = 0
        self._idle_threshold = 99
        self._is_idle = False
        self._app_process_running = False
        self._idle_poll_interval = 5000
        self._deep_idle_poll_interval = 30000
        self._activation_time = 0.0
        self._post_activation_grace_sec = 0.0
        self._telemetry_last_visibility = True
        self._telemetry_logged_fade_request = False
        self._retained_info = None
        self._missing_session_noted = False
        self._emitted = []
        self._ensure_timer_force_calls = []
        self.hide_called = False
        self.complete_hide_called = False
        self._refresh_in_flight = False
        self._update_timer = None
        self._update_timer_handle = None
        self._enabled = True
        self._fade_in_completed = False
        self._last_track_identity = None
        self._last_metadata_identity = None
        self._polls_at_current_stage = 0
        self._current_poll_stage = 0
        self._poll_intervals = [1000, 2000, 2500]
        self._skipped_identity_updates = 0
        self._max_identity_skip = 4
        self._last_display_update_ts = 0.0
        self.provider_display_name = "SPOTIFY"
        self._font_size = 20
        self._font_family = "Jost"
        self._has_seen_first_track = True
        self._fixed_card_height = None
        self._artwork_size = 200
        self._artwork_pixmap = None
        self._scaled_artwork_cache = None
        self._scaled_artwork_cache_key = None
        self.fade_in_calls = 0
        self.notify_calls = 0
        self._visible = True
        self._width = 600
        self._height = 290

    @classmethod
    def _get_shared_valid_info(cls):
        return None

    def note_missing_session(self) -> None:
        self._missing_session_noted = True

    def get_retained_display_info(self):
        return self._retained_info

    def try_provider_failover(self):
        return None

    def _ensure_timer(self, *, force=False):
        self._ensure_timer_force_calls.append(bool(force))

    def isVisible(self):
        return self._visible

    def _complete_hide_sequence(self):
        self.complete_hide_called = True

    def hide(self):
        self.hide_called = True
        self._visible = False

    def show(self):
        self._visible = True

    def cache_retained_display_info(self, info):
        self._retained_info = info

    def _compute_track_identity(self, info):
        return (info.title, info.artist, info.album, info.state.value)

    def _compute_metadata_identity(self, info):
        return (info.title, info.artist, self._font_size, self.provider_display_name)

    def _emit_media_update(self, info):
        self._emitted.append(info)

    def _start_widget_fade_in(self, duration_ms=None):
        self.fade_in_calls += 1
        self._visible = True

    def _notify_spotify_widgets_visibility(self):
        self.notify_calls += 1

    def setTextFormat(self, _value):
        return None

    def setText(self, _value):
        return None

    def setContentsMargins(self, *_args):
        return None

    def width(self):
        return self._width

    def height(self):
        return self._height

    def _controls_row_margin(self):
        return 12

    def _controls_row_min_height(self):
        return 24

    def sizeHint(self):
        return SimpleNamespace(height=lambda: 220)

    def minimumHeight(self):
        return 220

    def setMinimumHeight(self, _value):
        return None

    def setMaximumHeight(self, _value):
        return None

    def _decode_artwork_pixmap(self, _artwork):
        return None

    def painted_frame_shadow_card_shrink(self):
        return (0, 0)

    def parent(self):
        return None

    def parentWidget(self):
        return self.parent()


def test_handle_no_media_keeps_retained_snapshot_visible():
    widget = _StubMediaWidget()
    widget._retained_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PAUSED,
        artwork=b"art",
    )

    retained = display_update._handle_no_media(widget)

    assert retained is not None
    assert retained.title == "Track"
    assert widget._missing_session_noted is True
    assert widget.complete_hide_called is False
    assert widget._telemetry_last_visibility is True
    assert widget._emitted and widget._emitted[-1].state == MediaPlaybackState.PAUSED


def test_update_display_uses_provider_failover_snapshot(monkeypatch):
    widget = _StubMediaWidget()
    failover_info = MediaTrackInfo(
        title="Other Provider Track",
        artist="Fallback Artist",
        album="Fallback Album",
        state=MediaPlaybackState.PLAYING,
    )

    captured = {}

    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)
    monkeypatch.setattr(
        display_update,
        "_build_and_apply_metadata",
        lambda _widget, info, prev_info, *, metadata_changed: captured.update(
            {"info": info, "prev": prev_info, "metadata_changed": metadata_changed}
        ),
    )
    widget.try_provider_failover = lambda: failover_info

    display_update.update_display(widget, None)

    assert captured["info"] is failover_info
    assert captured["metadata_changed"] is True
    assert widget._last_info is failover_info
    assert widget._retained_info is failover_info


def test_update_display_refades_widget_when_metadata_returns(monkeypatch):
    widget = _StubMediaWidget()
    widget._visible = False
    live_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
    )

    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)

    display_update.update_display(widget, live_info)

    assert widget.fade_in_calls == 1
    assert widget.notify_calls == 1
    assert widget._telemetry_last_visibility is True
    assert widget._emitted and widget._emitted[-1] is live_info


def test_update_display_retained_same_metadata_does_not_force_relayout(monkeypatch):
    widget = _StubMediaWidget()
    retained_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PAUSED,
    )
    widget._retained_info = retained_info
    widget._last_metadata_identity = widget._compute_metadata_identity(retained_info)

    captured = {}
    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)
    monkeypatch.setattr(
        display_update,
        "_build_and_apply_metadata",
        lambda _widget, info, prev_info, *, metadata_changed: captured.update(
            {"info": info, "prev": prev_info, "metadata_changed": metadata_changed}
        ),
    )

    display_update.update_display(widget, None)

    assert captured["info"] is retained_info
    assert captured["metadata_changed"] is False


def test_update_display_album_only_change_does_not_force_metadata_refit(monkeypatch):
    widget = _StubMediaWidget()
    first_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album A",
        state=MediaPlaybackState.PLAYING,
    )
    second_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album B",
        state=MediaPlaybackState.PLAYING,
    )
    widget._last_track_identity = None
    widget._last_metadata_identity = widget._compute_metadata_identity(first_info)

    captured = {}
    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)
    monkeypatch.setattr(
        display_update,
        "_build_and_apply_metadata",
        lambda _widget, info, prev_info, *, metadata_changed: captured.update(
            {"info": info, "metadata_changed": metadata_changed}
        ),
    )

    display_update.update_display(widget, second_info)

    assert captured["info"] is second_info
    assert captured["metadata_changed"] is False


def test_build_and_apply_metadata_reuses_existing_layout_for_same_track_identity():
    widget = _StubMediaWidget()
    widget._metadata_paint = {
        "provider": "SPOTIFY",
        "title": "Track",
        "artist": "Artist",
        "base_font": 22,
        "header_font": 27,
        "title_font": 31,
        "artist_font": 17,
        "header_weight": 750,
        "title_weight": 700,
        "artist_weight": 600,
        "line_spacing": 4,
        "body_top_gap": 8,
    }
    widget._header_font_pt = 27
    widget._header_logo_size = 35
    widget._header_logo_margin = 35
    widget._artwork_vertical_bias = 0.41

    info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PAUSED,
    )

    display_update._build_and_apply_metadata(
        widget,
        info,
        prev_info=info,
        metadata_changed=False,
    )

    assert widget._metadata_paint["title_font"] == 31
    assert widget._metadata_paint["artist_font"] == 17
    assert widget._header_font_pt == 27
    assert widget._artwork_vertical_bias == 0.41


def test_build_and_apply_metadata_shrinks_wrap_prone_metadata_more_aggressively():
    widget = _StubMediaWidget()
    info = MediaTrackInfo(
        title="Ground Control (feat. Tegan And Sara)",
        artist="All Time Low",
        album="Last Young Renegade",
        state=MediaPlaybackState.PLAYING,
    )

    display_update._build_and_apply_metadata(
        widget,
        info,
        prev_info=None,
        metadata_changed=True,
    )

    assert widget._metadata_paint["title_font"] < widget._font_size + 3
    assert widget._metadata_paint["artist_font"] < widget._font_size - 2


def test_build_and_apply_metadata_compacts_for_small_committed_card_geometry():
    widget = _StubMediaWidget()
    widget._width = 480
    widget._height = 232
    info = MediaTrackInfo(
        title="The Longest Distance Between Two Places",
        artist="The World Is A Beautiful Place And I Am No Longer Afraid To Die",
        album="Whenever, If Ever",
        state=MediaPlaybackState.PLAYING,
    )

    display_update._build_and_apply_metadata(
        widget,
        info,
        prev_info=None,
        metadata_changed=True,
    )

    assert widget._metadata_paint["title_font"] <= widget._font_size
    assert widget._metadata_paint["artist_font"] < widget._font_size - 2
    assert widget._metadata_paint["line_spacing"] <= 3
    assert widget._metadata_paint["body_top_gap"] <= 7


def test_update_display_first_track_waits_for_parent_fade_starter(monkeypatch):
    widget = _StubMediaWidget()
    widget._has_seen_first_track = False

    starters = []

    class _FadeParent:
        def request_overlay_fade_sync(self, overlay_name, starter):
            starters.append((overlay_name, starter))

    widget.parent = lambda: _FadeParent()
    monkeypatch.setattr(display_update.Shiboken, "isValid", lambda _widget: True)

    live_info = MediaTrackInfo(
        title="Track",
        artist="Artist",
        album="Album",
        state=MediaPlaybackState.PLAYING,
    )

    display_update.update_display(widget, live_info)

    assert widget.hide_called is True
    assert widget.fade_in_calls == 0
    assert [name for name, _ in starters] == ["media"]

    starters.pop(0)[1]()

    assert widget.fade_in_calls == 1
    assert widget.notify_calls == 1
