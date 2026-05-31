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
        lambda _widget, info, prev_info: captured.update({"info": info, "prev": prev_info}),
    )
    widget.try_provider_failover = lambda: failover_info

    display_update.update_display(widget, None)

    assert captured["info"] is failover_info
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
