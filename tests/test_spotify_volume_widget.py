from __future__ import annotations

import time

from PySide6.QtCore import QRect, QTimer
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


def test_spotify_volume_waits_for_secondary_stage_before_reveal(qt_app, monkeypatch):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()
    parent._overlay_fade_expected = {"clock", "weather"}
    parent._overlay_fade_started = False

    widget = SpotifyVolumeWidget(parent)
    anchor = QWidget(parent)
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._spotify_secondary_stage_registered = True  # type: ignore[attr-defined]
        anchor.show()
        widget.set_anchor_media_widget(anchor)

        calls = []

        def _fake_sync(*_args, **_kwargs):
            calls.append("sync")
            widget.show()
            return True

        monkeypatch.setattr("widgets.spotify_volume_widget.sync_anchor_dependent_visibility", _fake_sync)

        widget.sync_visibility_with_anchor()

        assert widget.isVisible() is False
        assert calls == []
    finally:
        anchor.deleteLater()
        widget.deleteLater()
        parent.deleteLater()


def test_spotify_volume_uses_track_shadow_without_outer_frame_box(qt_app):
    widget = SpotifyVolumeWidget()
    try:
        assert widget.uses_outer_frame_shadow() is False
        assert widget.uses_painted_frame_shadow() is True
    finally:
        widget.deleteLater()


def test_spotify_volume_scale_contract_respects_active_custom_rect(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    try:
        widget._custom_layout_local_rect = QRect(12, 34, 66, 288)  # type: ignore[attr-defined]
        reapply_calls = []
        monkeypatch.setattr(widget, "_schedule_custom_layout_geometry_reapply", lambda: reapply_calls.append("reapply"))  # type: ignore[method-assign]

        widget.apply_scale_contract(width=40, height=180, track_width=14, track_margin=5)

        assert widget.minimumWidth() == 66
        assert widget.minimumHeight() == 288
        assert reapply_calls == ["reapply"]
    finally:
        widget.deleteLater()


def test_spotify_volume_custom_reapply_uses_thread_manager_and_coalesces(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    try:
        widget.setGeometry(0, 0, 20, 120)
        custom_rect = QRect(12, 34, 66, 288)
        widget._custom_layout_local_rect = QRect(custom_rect)  # type: ignore[attr-defined]
        queued_callbacks = []

        monkeypatch.setattr(
            "widgets.spotify_volume_widget.ThreadManager.single_shot",
            lambda delay_ms, callback, *args, **kwargs: queued_callbacks.append(
                (int(delay_ms), lambda: callback(*args, **kwargs))
            ),
        )

        widget._schedule_custom_layout_geometry_reapply()  # type: ignore[attr-defined]
        widget._schedule_custom_layout_geometry_reapply()  # type: ignore[attr-defined]

        assert len(queued_callbacks) == 1
        assert widget.geometry() != custom_rect
        delay_ms, callback = queued_callbacks.pop()
        assert delay_ms == 0

        callback()

        assert widget.geometry() == custom_rect
        assert widget._custom_layout_geometry_reapply_pending is False  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()


def test_spotify_volume_secondary_stage_forces_sync_against_visible_anchor(qt_app, monkeypatch):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()
    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0

    widget = SpotifyVolumeWidget(parent)
    anchor = QWidget(parent)
    calls = []
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._spotify_secondary_stage_registered = True  # type: ignore[attr-defined]
        anchor.show()
        widget.set_anchor_media_widget(anchor)
        parent._position_spotify_volume = lambda: calls.append(("position", {}))  # type: ignore[attr-defined]
        monkeypatch.setattr(widget, "_request_volume_sync", lambda **kwargs: calls.append(("volume", kwargs)))  # type: ignore[method-assign]
        monkeypatch.setattr(widget, "sync_visibility_with_anchor", lambda: calls.append(("visibility", {})))  # type: ignore[method-assign]

        widget.begin_spotify_secondary_stage()

        assert widget._spotify_secondary_stage_started is True  # type: ignore[attr-defined]
        assert calls == [("position", {}), ("volume", {"force": True}), ("visibility", {})]
    finally:
        anchor.deleteLater()
        widget.deleteLater()
        parent.deleteLater()


def test_spotify_volume_keyboard_step_works_while_hidden(qt_app, monkeypatch):
    widget = SpotifyVolumeWidget()
    applied = []
    try:
        widget.hide()
        monkeypatch.setattr(widget, "_apply_step_delta", lambda delta_y: applied.append(delta_y) or True)  # type: ignore[method-assign]

        handled = widget.handle_step(1)

        assert handled is True
        assert applied == [120]
    finally:
        widget.deleteLater()
