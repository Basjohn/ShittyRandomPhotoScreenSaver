"""Contracts for the temporary non-painting Media/Visualizer anchor."""

from __future__ import annotations

from types import SimpleNamespace

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_runtime import MediaRuntimeSnapshot, PreparedMediaArtwork
from widgets.media_volume_runtime import MediaVolumeRuntimeSnapshot
from widgets.media_widget import MediaWidget
from widgets.system_mute_runtime import SystemMuteRuntimeSnapshot


def test_media_anchor_projects_accepted_runtime_snapshot(qt_app) -> None:
    widget = MediaWidget(build_default_runtime=False)
    projected = []
    track = MediaTrackInfo(
        title="Accepted Track",
        artist="Artist",
        state=MediaPlaybackState.PLAYING,
    )
    widget._update_display = lambda info: projected.append(info)
    snapshot = MediaRuntimeSnapshot(
        revision=7,
        provider="spotify",
        info=track,
        artwork=PreparedMediaArtwork((0, ""), None, 0.0),
    )
    try:
        widget.on_media_runtime_snapshot(snapshot)
        assert projected == [track]
        assert widget._last_runtime_revision == 7
    finally:
        widget.deleteLater()


def test_media_anchor_runtime_replay_resets_provider_projection(qt_app) -> None:
    widget = MediaWidget(build_default_runtime=False, provider="spotify")
    projected = []
    widget._last_track_identity = ("old",)
    widget._update_display = lambda info: projected.append(info)
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
        assert widget._last_track_identity is None
        assert projected == [track]
    finally:
        widget.deleteLater()


def test_media_anchor_routes_accepted_auxiliary_actions(qt_app) -> None:
    volume_calls = []
    mute_calls = []
    volume = SimpleNamespace(
        is_running=lambda: True,
        set_volume_optimistic=lambda level: volume_calls.append(level) or True,
    )
    mute = SimpleNamespace(
        is_running=lambda: True,
        toggle_mute=lambda: mute_calls.append("toggle") or True,
        step_system_volume=lambda delta: mute_calls.append(("step", delta)) or 0.55,
        request_refresh=lambda **kwargs: mute_calls.append(("refresh", kwargs)) or True,
    )
    widget = MediaWidget(build_default_runtime=False)
    widget._volume_runtime_service = volume
    widget._system_mute_runtime_service = mute
    try:
        widget.on_media_volume_runtime_snapshot(
            MediaVolumeRuntimeSnapshot(
                revision=3,
                provider="spotify",
                browser_process=None,
                supported=True,
                available=True,
                level=0.50,
                source="test",
            )
        )
        widget.on_system_mute_runtime_snapshot(
            SystemMuteRuntimeSnapshot(
                revision=4,
                available=True,
                muted=False,
                source="test",
            )
        )

        assert widget.request_app_volume_step(+1) is True
        assert volume_calls == [0.55]
        assert widget.request_system_mute_toggle() is True
        assert widget.request_system_volume_step(-0.05) == 0.55
        assert widget.request_system_mute_refresh(force=True, source="test") is True
        assert mute_calls == [
            "toggle",
            ("step", -0.05),
            ("refresh", {"force": True, "source": "test"}),
        ]
    finally:
        widget._volume_runtime_service = None
        widget._system_mute_runtime_service = None
        widget.deleteLater()


def test_media_anchor_auxiliary_actions_are_inert_without_accepted_capability(
    qt_app,
) -> None:
    calls = []
    widget = MediaWidget(build_default_runtime=False)
    widget._volume_runtime_service = SimpleNamespace(
        is_running=lambda: True,
        set_volume_optimistic=lambda level: calls.append(level) or True,
    )
    widget._system_mute_runtime_service = SimpleNamespace(is_running=lambda: True)
    try:
        assert widget.request_app_volume_step(+1) is False
        assert widget.has_live_system_mute_runtime() is False
        assert widget.request_system_mute_toggle() is False
        assert calls == []
    finally:
        widget._volume_runtime_service = None
        widget._system_mute_runtime_service = None
        widget.deleteLater()


def test_media_anchor_lifecycle_without_thread_manager_fails_closed(qt_app) -> None:
    widget = MediaWidget(build_default_runtime=False)
    try:
        assert widget.initialize() is True
        assert widget.activate() is False
        assert widget._enabled is False
        assert widget._lifecycle_state.name == "INITIALIZED"
    finally:
        widget.deleteLater()


def test_media_layout_deferred_update_position_is_generation_safe(monkeypatch) -> None:
    from widgets import media_layout

    callbacks = []
    calls = []
    widget = SimpleNamespace(
        _runtime_generation=17,
        _update_position=lambda: calls.append("updated"),
    )
    monkeypatch.setattr(
        media_layout.ThreadManager,
        "single_shot",
        lambda _ms, callback: callbacks.append(callback),
    )
    monkeypatch.setattr(media_layout.Shiboken, "isValid", lambda _widget: True)

    media_layout._defer_update_position(widget)

    assert callbacks[0]._srpss_runtime_generation == 17
    callbacks[0]()
    assert calls == ["updated"]


def test_media_keyboard_home_alias_and_external_ingress_do_not_double_execute(
    qt_app,
) -> None:
    widget = MediaWidget(build_default_runtime=False)
    calls = []
    widget._runtime_service = SimpleNamespace(
        play_pause=lambda *, execute: calls.append(execute) or True,
    )
    try:
        assert widget._should_defer_keyboard_alias_command("keyboard_home", "play")
        assert widget.handle_transport_command(
            "play", source="appcommand:play", execute=False
        )
        assert widget.handle_transport_command(
            "play", source="media_key", execute=False
        )
        assert calls == [False]
        assert widget._pending_keyboard_alias_command is None
    finally:
        widget._runtime_service = None
        widget.deleteLater()
