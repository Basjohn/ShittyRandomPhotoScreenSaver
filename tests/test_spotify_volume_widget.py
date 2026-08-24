from __future__ import annotations

import time

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QWidget

from widgets.media_volume_runtime import MediaVolumeRuntimeService
from widgets.spotify_volume_widget import SpotifyVolumeWidget


class _FakeVolumeController:
    def __init__(self) -> None:
        self.configure_calls: list[tuple[object, object]] = []
        self.reads = 0
        self.writes: list[float] = []

    def is_available(self) -> bool:
        return True

    def configure_volume_target(self, provider, source_app_user_model_id="") -> bool:
        self.configure_calls.append((provider, source_app_user_model_id))
        return provider != "spotify_browser" or bool(source_app_user_model_id)

    def get_volume(self) -> float:
        self.reads += 1
        return 0.6

    def set_volume(self, level: float) -> bool:
        self.writes.append(float(level))
        return True


def _make_widget(provider: str = "spotify") -> tuple[SpotifyVolumeWidget, _FakeVolumeController]:
    controller = _FakeVolumeController()
    widget = SpotifyVolumeWidget(provider=provider, build_default_runtime=False)
    widget.set_runtime_service(
        MediaVolumeRuntimeService(
            provider=provider,
            shared=False,
            controller=controller,
        )
    )
    return widget, controller


def test_spotify_volume_direct_widget_owns_isolated_runtime_until_cleanup(qt_app):
    widget = SpotifyVolumeWidget()
    service = widget._runtime_service  # type: ignore[attr-defined]
    try:
        assert service is not None
        assert widget._owns_runtime_service is True  # type: ignore[attr-defined]
        assert service.shared_owner is not None

        widget.cleanup()

        assert service.is_retired() is True
        assert widget._runtime_service is None  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()


def test_spotify_volume_stop_deactivates_runtime_without_retiring_attached_owner(qt_app):
    widget, _controller = _make_widget()
    service = widget._runtime_service  # type: ignore[attr-defined]
    try:
        assert service is not None
        assert widget.start() is True
        assert service.is_running() is True

        widget.stop()

        assert widget.is_lifecycle_active() is False
        assert service.is_running() is False
        assert service.is_retired() is False
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_spotify_volume_cleanup_impl_releases_neutral_runtime(qt_app):
    widget = SpotifyVolumeWidget()
    service = widget._runtime_service  # type: ignore[attr-defined]
    try:
        widget._cleanup_impl()  # type: ignore[attr-defined]

        assert service is not None and service.is_retired() is True
        assert widget._runtime_service is None  # type: ignore[attr-defined]
    finally:
        widget.deleteLater()


def test_spotify_volume_provider_switch_delegates_and_syncs_snapshot(qt_app):
    widget, controller = _make_widget()
    try:
        controller.configure_calls.clear()

        changed = widget.set_provider_runtime("musicbee")

        assert changed is True
        assert widget._provider == "musicbee"  # type: ignore[attr-defined]
        assert controller.configure_calls == [("musicbee", "")]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_spotify_browser_provider_waits_hidden_for_exact_runtime_source(qt_app):
    widget, controller = _make_widget()
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget.show()
        controller.configure_calls.clear()

        changed = widget.set_provider_runtime("spotify_browser")

        assert changed is True
        assert widget._provider_volume_supported is False  # type: ignore[attr-defined]
        assert widget.isVisible() is False
        assert controller.configure_calls == [("spotify_browser", "")]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_spotify_browser_runtime_source_enables_and_retargets_exact_host(qt_app):
    widget, controller = _make_widget(provider="spotify_browser")
    try:
        controller.configure_calls.clear()

        assert widget.set_runtime_volume_source("spotify_browser", "firefox.exe") is True
        assert widget._provider_volume_supported is True  # type: ignore[attr-defined]
        assert widget._browser_volume_process == "firefox.exe"  # type: ignore[attr-defined]
        assert widget.set_runtime_volume_source("spotify_browser", "firefox") is False

        assert widget.set_runtime_volume_source("spotify_browser", "chrome") is True
        assert widget._browser_volume_process == "chrome.exe"  # type: ignore[attr-defined]
        assert controller.configure_calls == [
            ("spotify_browser", "firefox.exe"),
            ("spotify_browser", "chrome"),
        ]
    finally:
        widget.cleanup()
        widget.deleteLater()


def test_spotify_browser_unknown_source_clears_prior_runtime_target(qt_app):
    widget, _controller = _make_widget(provider="spotify_browser")
    try:
        assert widget.set_runtime_volume_source("spotify_browser", "firefox.exe") is True

        assert widget.set_runtime_volume_source("spotify_browser", "myfirefox.exe") is True

        assert widget._provider_volume_supported is False  # type: ignore[attr-defined]
        assert widget._browser_volume_process is None  # type: ignore[attr-defined]
        assert widget.isVisible() is False
    finally:
        widget.cleanup()
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
