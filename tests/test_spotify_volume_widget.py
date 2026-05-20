from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from widgets.spotify_volume_widget import SpotifyVolumeWidget


def test_spotify_volume_reset_flush_state_stops_and_optionally_deletes_timer(qt_app):
    widget = SpotifyVolumeWidget()
    try:
        timer = QTimer(widget)
        timer.setSingleShot(True)
        timer.start(1000)
        widget._flush_timer = timer  # type: ignore[attr-defined]
        widget._pending_volume = 0.5  # type: ignore[attr-defined]

        widget._reset_flush_state(delete_timer=False)  # type: ignore[attr-defined]

        assert widget._flush_timer is timer  # type: ignore[attr-defined]
        assert timer.isActive() is False
        assert widget._pending_volume is None  # type: ignore[attr-defined]

        widget._pending_volume = 0.3  # type: ignore[attr-defined]
        widget._reset_flush_state(delete_timer=True)  # type: ignore[attr-defined]

        assert widget._flush_timer is None  # type: ignore[attr-defined]
        assert widget._pending_volume is None  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()


def test_spotify_volume_stop_uses_canonical_flush_reset(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    calls = []
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        monkeypatch.setattr(widget, "_reset_flush_state", lambda **kwargs: calls.append(kwargs))  # type: ignore[method-assign]
        monkeypatch.setattr(widget, "hide", lambda *args, **kwargs: calls.append({"hide": True}))  # type: ignore[method-assign]

        widget.stop()

        assert calls[0] == {"delete_timer": False}
        assert {"hide": True} in calls
    finally:
        widget.deleteLater()


def test_spotify_volume_cleanup_impl_deletes_flush_timer(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    calls = []
    try:
        monkeypatch.setattr(widget, "_reset_flush_state", lambda **kwargs: calls.append(kwargs))  # type: ignore[method-assign]

        widget._cleanup_impl()  # type: ignore[attr-defined]

        assert calls == [{"delete_timer": False}, {"delete_timer": True}]
    finally:
        widget.deleteLater()


def test_spotify_volume_provider_switch_requests_volume_sync(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    calls = []
    try:
        monkeypatch.setattr(widget, "_request_volume_sync", lambda **kwargs: calls.append(kwargs))  # type: ignore[method-assign]

        changed = widget.set_provider_runtime("musicbee")

        assert changed is True
        assert calls == [{"force": True}]
    finally:
        widget.deleteLater()


def test_spotify_volume_sync_visibility_requests_volume_sync_when_becoming_visible(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    anchor = QWidget()
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget.set_anchor_media_widget(anchor)
        calls = []
        monkeypatch.setattr(widget, "_request_volume_sync", lambda **kwargs: calls.append(kwargs))  # type: ignore[method-assign]

        def _fake_sync(*_args, **_kwargs):
            widget.show()
            return True

        monkeypatch.setattr("widgets.spotify_volume_widget.sync_anchor_dependent_visibility", _fake_sync)

        widget.hide()
        widget.sync_visibility_with_anchor()

        assert calls == [{}]
    finally:
        anchor.deleteLater()
        widget.deleteLater()
