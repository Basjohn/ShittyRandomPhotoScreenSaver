from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QWidget

from widgets.mute_button_widget import MuteButtonWidget


@pytest.mark.qt
def test_mute_button_waits_for_secondary_stage_before_reveal(qt_app):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()
    parent._overlay_fade_expected = {"clock", "weather"}
    parent._overlay_fade_started = False

    anchor = QWidget(parent)
    anchor.setGeometry(100, 80, 240, 120)
    anchor.show()

    mute = MuteButtonWidget(parent)
    mute._available = True
    mute.set_anchor(anchor)
    mute.set_enabled(True)
    mute._spotify_secondary_stage_registered = True

    try:
        mute.sync_visibility_with_anchor()
        assert mute.isVisible() is False
        assert mute._has_faded_in is False

        calls: list[str] = []

        def _fake_update_position() -> None:
            calls.append("update")
            mute.move(123, 77)

        def _fake_start_fade(_duration_ms=None) -> None:
            calls.append("fade")
            mute.show()
            mute._has_faded_in = True

        mute.update_position = _fake_update_position  # type: ignore[method-assign]
        mute._start_widget_fade_in = _fake_start_fade  # type: ignore[method-assign]

        mute.begin_spotify_secondary_stage()

        assert mute._spotify_secondary_stage_started is True
        assert mute.isVisible() is True
        assert mute.pos().x() == 123
        assert mute.pos().y() == 77
        assert calls
        assert calls[0] == "update"
        assert "fade" in calls
    finally:
        mute.deleteLater()
        anchor.deleteLater()
        parent.deleteLater()


@pytest.mark.qt
def test_mute_button_anchor_visibility_can_release_secondary_stage(qt_app):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()
    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0

    anchor = QWidget(parent)

    mute = MuteButtonWidget(parent)
    mute._available = True
    mute.set_anchor(anchor)
    mute.set_enabled(True)
    mute._spotify_secondary_stage_registered = True

    try:
        calls: list[str] = []

        def _fake_update_position() -> None:
            calls.append("update")

        def _fake_start_fade(_duration_ms=None) -> None:
            calls.append("fade")
            mute.show()
            mute._has_faded_in = True

        mute.update_position = _fake_update_position  # type: ignore[method-assign]
        mute._start_widget_fade_in = _fake_start_fade  # type: ignore[method-assign]

        mute.sync_visibility_with_anchor()
        assert mute._spotify_secondary_stage_started is False
        assert calls == []

        anchor.show()
        mute.sync_visibility_with_anchor()

        assert mute._spotify_secondary_stage_started is True
        assert calls[0] == "update"
        assert "fade" in calls
        assert mute.isVisible() is True
    finally:
        mute.deleteLater()
        anchor.deleteLater()
        parent.deleteLater()


@pytest.mark.qt
def test_mute_button_anchor_sync_respects_parent_secondary_stage_deadline(qt_app):
    parent = QWidget()
    parent.resize(640, 480)
    parent.show()
    parent._overlay_fade_expected = {"clock", "weather"}
    parent._overlay_fade_started = False
    parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0

    anchor = QWidget(parent)
    anchor.show()

    mute = MuteButtonWidget(parent)
    mute._available = True
    mute.set_anchor(anchor)
    mute.set_enabled(True)
    mute._spotify_secondary_stage_registered = True

    try:
        calls: list[str] = []

        def _fake_update_position() -> None:
            calls.append("update")

        def _fake_start_fade(_duration_ms=None) -> None:
            calls.append("fade")
            mute.show()
            mute._has_faded_in = True

        mute.update_position = _fake_update_position  # type: ignore[method-assign]
        mute._start_widget_fade_in = _fake_start_fade  # type: ignore[method-assign]

        mute.sync_visibility_with_anchor()
        assert mute._spotify_secondary_stage_started is False
        assert calls == []

        parent._overlay_fade_started = True
        parent._spotify_secondary_not_before_ts = time.monotonic() + 60.0
        mute.sync_visibility_with_anchor()
        assert mute._spotify_secondary_stage_started is False
        assert calls == []

        parent._spotify_secondary_not_before_ts = time.monotonic() - 1.0
        mute.sync_visibility_with_anchor()

        assert mute._spotify_secondary_stage_started is True
        assert calls[0] == "update"
        assert "fade" in calls
    finally:
        mute.deleteLater()
        anchor.deleteLater()
        parent.deleteLater()


def test_mute_button_set_enabled_false_resets_runtime_state(qt_app):
    mute = MuteButtonWidget()
    try:
        mute._available = True
        mute._thread_manager = object()
        mute._mute_poll_active = True
        mute._spotify_secondary_stage_started = True
        mute._has_faded_in = True
        mute.show()

        mute.set_enabled(False)

        assert mute._enabled is False
        assert mute._mute_poll_active is False
        assert mute._spotify_secondary_stage_started is False
        assert mute._has_faded_in is False
        assert mute.isVisible() is False
    finally:
        mute.deleteLater()


def test_mute_button_enable_restarts_poll_when_thread_manager_ready(qt_app, monkeypatch):
    mute = MuteButtonWidget()
    try:
        mute._available = True
        mute._thread_manager = object()
        calls: list[str] = []

        def _fake_start_poll() -> None:
            calls.append("start")

        mute._start_mute_poll = _fake_start_poll  # type: ignore[method-assign]

        mute.set_enabled(True)

        assert mute._enabled is True
        assert calls == ["start"]
    finally:
        mute.deleteLater()


def test_mute_button_cleanup_uses_canonical_runtime_reset(qt_app):
    mute = MuteButtonWidget()
    try:
        calls: list[tuple[bool, bool]] = []

        def _fake_reset_runtime_state(*, stop_poll: bool, reset_secondary_stage: bool) -> None:
            calls.append((stop_poll, reset_secondary_stage))

        mute._reset_runtime_state = _fake_reset_runtime_state  # type: ignore[method-assign]

        mute.cleanup()

        assert calls == [(True, True)]
    finally:
        mute.deleteLater()
