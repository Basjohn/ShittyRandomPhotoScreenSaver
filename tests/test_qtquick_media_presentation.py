"""F3 production-shaped gates for the retained Quick Media core."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from rendering.quick.media_artwork import MediaArtworkImageProvider
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets import (
    MediaPresentationConfig,
    MediaPresentationModel,
    MediaPresentationStyle,
    OverlayWidgetGeometry,
    RetainedMediaPresentation,
)
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from rendering.quick.window import QuickDisplayWindow
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.media_runtime import (
    MediaRuntimeSnapshot,
    PreparedMediaArtwork,
    reset_shared_media_runtime_for_tests,
)


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"
_DEFAULT_INFO = object()


class _FakeMediaRuntime:
    def __init__(self) -> None:
        self.consumer = None
        self.thread_manager = None
        self.running = False
        self.provider = "spotify"
        self.refresh_calls: list[bool] = []
        self.provider_calls: list[tuple[str, str]] = []

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = True
        return True

    def stop(self) -> None:
        self.running = False

    def refresh(self, *, bust_cache: bool = False) -> bool:
        self.refresh_calls.append(bool(bust_cache))
        return True

    def set_provider_runtime(self, provider, *, source: str = "settings") -> bool:
        normalized = str(provider)
        changed = normalized != self.provider
        self.provider = normalized
        self.provider_calls.append((normalized, source))
        return changed

    def publish(self, snapshot: MediaRuntimeSnapshot) -> None:
        if self.consumer is not None:
            self.consumer.on_media_runtime_snapshot(snapshot)


class _RuntimeHost:
    def get_runtime_widget_registry(self):
        return {}


class _PassiveTimer:
    def __init__(self) -> None:
        self.active = True

    def isActive(self) -> bool:
        return self.active

    def setInterval(self, _interval: int) -> None:
        return

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

    def deleteLater(self) -> None:
        return


class _PassiveThreadManager:
    def __init__(self) -> None:
        self.jobs = []

    def schedule_recurring(self, _interval, _callback, **_kwargs):
        return _PassiveTimer()

    def submit_io_task(self, worker, callback=None, **kwargs) -> None:
        self.jobs.append((worker, callback, kwargs))


class _PassiveController:
    def __init__(self, *, thread_manager, app_filter) -> None:
        self.thread_manager = thread_manager
        self.app_filter = app_filter
        self.runtime_generation = None
        self.retired = False

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def set_runtime_generation(self, generation) -> None:
        self.runtime_generation = generation

    def retire(self) -> None:
        self.retired = True


def _values(**overrides):
    values = {
        "provider": "spotify",
        "font_family": "Inter",
        "font_size": 19,
        "color": [245, 248, 252, 235],
        "show_background": True,
        "bg_color": [25, 32, 42, 255],
        "bg_opacity": 0.72,
        "border_color": [120, 195, 255, 255],
        "border_opacity": 0.9,
        "show_header_frame": True,
        "artwork_size": 180,
        "rounded_artwork_border": True,
        "show_controls": True,
        "playback_progress_enabled": True,
    }
    values.update(overrides)
    return values


def _shadows(**overrides):
    values = {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "text_opacity": 0.4,
        "text_extra_offset": 1,
        "direction": "SE",
    }
    values.update(overrides)
    return values


def _image(color="#e33b63") -> QImage:
    image = QImage(96, 72, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


def _info(**overrides) -> MediaTrackInfo:
    values = {
        "title": "Midnight City",
        "artist": "M83",
        "album": "Hurry Up, We're Dreaming",
        "state": MediaPlaybackState.PLAYING,
        "can_play_pause": True,
        "can_next": True,
        "can_previous": True,
        "position_ms": 45_000,
        "duration_ms": 240_000,
    }
    values.update(overrides)
    return MediaTrackInfo(**values)


def _snapshot(
    revision: int,
    *,
    key=(128, "a" * 40),
    image=None,
    info=_DEFAULT_INFO,
    provider="spotify",
) -> MediaRuntimeSnapshot:
    return MediaRuntimeSnapshot(
        revision=revision,
        provider=provider,
        info=_info() if info is _DEFAULT_INFO else info,
        artwork=PreparedMediaArtwork(key=key, image=image, decode_ms=1.25),
    )


def _model(provider=None, runtime=None, **overrides):
    artwork_provider = provider or MediaArtworkImageProvider()
    config = MediaPresentationConfig.from_mapping(_values(**overrides))
    style = MediaPresentationStyle.project(config, _shadows())
    service = runtime or _FakeMediaRuntime()
    return (
        MediaPresentationModel(config, style, artwork_provider, service),
        service,
        artwork_provider,
    )


def test_media_config_and_style_project_canonical_settings_and_direction() -> None:
    config = MediaPresentationConfig.from_widgets_mapping(
        {"media": {"font_size": 31, "artwork_size": 210, "bg_opacity": 0.5}}
    )
    style = MediaPresentationStyle.project(
        config,
        _shadows(direction="NW", frame_extra_offset=2, text_extra_offset=3),
    )

    assert config.font_size == 31
    assert config.artwork_size == 210
    assert style.card_style.background_color.alpha() == 128
    assert style.card_style.shadow_offset_x == pytest.approx(-6.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-6.0)
    assert style.text_shadow_offset_x == pytest.approx(-5.0)
    assert style.text_shadow_offset_y == pytest.approx(-5.0)

    model = MediaPresentationModel(config, style, MediaArtworkImageProvider())
    assert model.artworkBorderColor == style.card_style.border_color
    assert model.artworkBorderWidth == pytest.approx(6.0)


def test_media_artwork_provider_is_stable_bounded_and_returns_detached_images() -> None:
    provider = MediaArtworkImageProvider(unreferenced_capacity=1)
    source_a = provider.publish((10, "a" * 40), _image("#ff0000"))
    source_b = provider.publish((11, "b" * 40), _image("#00ff00"))
    identity_a = source_a.rsplit("/", 1)[-1]
    identity_b = source_b.rsplit("/", 1)[-1]
    size = QSize()
    returned = provider.requestImage(identity_a, size, QSize())
    rounded = provider.requestImage(f"{identity_a}/rounded", QSize(), QSize())

    assert source_a == f"image://mediaartwork/{identity_a}"
    assert returned.pixelColor(0, 0) == QColor("#ff0000")
    assert size == QSize(96, 72)
    assert rounded.size() == QSize(72, 72)
    assert rounded.pixelColor(0, 0).alpha() == 0
    assert rounded.pixelColor(36, 36) == QColor("#ff0000")
    provider.release(identity_a)
    provider.publish((12, "c" * 40), _image("#0000ff"))
    provider.release(identity_b)
    assert provider.contains(identity_b) is False
    assert provider.image_count == 2


def test_media_model_publishes_coherent_revisions_without_unchanged_artwork_republish() -> (
    None
):
    model, runtime, provider = _model()
    model.activate(object())
    first = _snapshot(4, image=_image())
    runtime.publish(first)
    source = model.artworkSource

    assert model.revision == 4
    assert model.title == "Midnight City"
    assert model.artist == "M83"
    assert model.album == "Hurry Up, We're Dreaming"
    assert model.playbackState == "playing"
    assert model.progressFraction == pytest.approx(0.1875)
    assert model.controlsAvailable is True
    assert model.progressAvailable is True
    assert source.startswith("image://mediaartwork/")
    assert provider.image_count == 1

    runtime.publish(
        _snapshot(
            5,
            image=None,
            info=_info(title="Midnight City - Live", position_ms=60_000),
        )
    )
    assert model.revision == 5
    assert model.title == "Midnight City - Live"
    assert model.artworkSource == source
    assert provider.image_count == 1

    runtime.publish(_snapshot(3, image=_image("#00ff00")))
    assert model.revision == 5
    assert model.title == "Midnight City - Live"
    assert model.artworkSource == source

    runtime.publish(_snapshot(5, image=_image("#00ff00"), info=_info(title="Stale")))
    assert model.title == "Midnight City - Live"
    assert model.artworkSource == source

    assert model.request_refresh() is True
    assert runtime.refresh_calls == [True]
    model.retire()
    assert runtime.consumer is None
    assert runtime.running is False


def test_media_model_handles_empty_provider_change_and_f4_state_without_actions() -> (
    None
):
    model, runtime, _provider = _model()
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))
    runtime.publish(
        _snapshot(
            2,
            key=(0, ""),
            image=None,
            info=None,
            provider="musicbee",
        )
    )

    assert model.title == "No media playing"
    assert model.hasTrack is False
    assert model.hasArtwork is False
    assert model.controlsAvailable is False
    assert model.progressAvailable is False
    assert model.providerName == "MUSICBEE"

    targets = []
    model.volumeTargetChanged.connect(
        lambda provider, source: targets.append((provider, source))
    )
    model.on_media_runtime_volume_target("musicbee", "session-7")
    assert targets == [("musicbee", "session-7")]

    runtime.publish(_snapshot(3, image=_image(), info=_info()))
    model.on_media_runtime_provider_changed(
        "musicbee", "spotify", source="settings", persist=False
    )
    assert model.hasTrack is False
    assert model.controlsAvailable is False
    assert model.progressAvailable is False
    assert model.progressFraction == 0.0
    assert model.playbackState == "unknown"


def test_media_runtime_manager_injects_retained_model_without_starting_controller() -> (
    None
):
    provider = MediaArtworkImageProvider()
    config = MediaPresentationConfig.from_mapping(_values())
    style = MediaPresentationStyle.project(config, _shadows())
    model = MediaPresentationModel(config, style, provider, runtime_generation=91)
    owner = WidgetRuntimeManager(_RuntimeHost())

    service = owner.ensure_widget_service(
        "media", model, {"media": {"provider": "spotify"}}
    )

    assert service is not None
    assert model._runtime_service is service
    assert service.shared_owner is None
    assert service.is_running() is False
    model.retire()
    assert owner.get_reusable_widget_service("media", model) is None
    assert service.is_retired() is True
    owner.cleanup()
    assert service.is_retired() is True


@pytest.mark.qt
def test_media_real_runtime_owner_activates_through_current_scene_host(qt_app) -> None:
    reset_shared_media_runtime_for_tests()
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=93,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    owner = WidgetRuntimeManager(_RuntimeHost())
    config = MediaPresentationConfig.from_mapping(_values())
    style = MediaPresentationStyle.project(config, _shadows())
    model = MediaPresentationModel(
        config,
        style,
        factory.media_artwork_provider,
        runtime_generation=93,
    )
    service = owner.ensure_widget_service(
        "media", model, {"media": {"provider": config.provider}}
    )
    assert service is not None
    service._controller_factory = _PassiveController
    thread_manager = _PassiveThreadManager()
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 520.0, 280.0),
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        presentation.activate(thread_manager)
        qt_app.processEvents()

        assert item.parentItem() is not None
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert service.shared_owner is not None
        assert service.shared_owner.controller is not None
        assert service.shared_owner.controller.runtime_generation == 93
        assert service.is_running() is True
        assert thread_manager.jobs
        assert owner.get_reusable_widget_service("media", model) is service

        controller.quiesce_for_retirement()
        assert model.is_active is False
        assert service.is_running() is False
        assert service.shared_owner is None
    finally:
        controller.quiesce_for_retirement()
        owner.cleanup()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()
        reset_shared_media_runtime_for_tests()


@pytest.mark.qt
def test_media_family_uses_current_scene_host_and_mutates_without_recreation(
    qt_app,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=92,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(35.0, 40.0, 620.0, 330.0),
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()

        assert item.parentItem() is not None
        assert item.findChild(QQuickItem, "mediaMetadata") is not None
        assert item.findChild(QQuickItem, "mediaArtworkFrame") is not None
        assert model.hasArtwork is True
        assert provider.image_count == 1

        next_config = replace(
            model.config,
            font_size=27,
            artwork_size=140,
            show_background=False,
        )
        presentation.apply_config(
            next_config, _shadows(direction="W", text_extra_offset=2)
        )
        item.refreshRequested.emit()
        qt_app.processEvents()

        assert presentation.item is item
        assert presentation.model is model
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert model.fontSize == 27.0
        assert model.artworkSize == 140.0
        assert model.textShadowOffsetX == pytest.approx(-4.0)
        assert model.textShadowOffsetY == pytest.approx(0.0)
        assert item.property("cardShellEnabled") is False
        assert runtime.refresh_calls == [True]

        controller.quiesce_for_retirement()
        assert runtime.consumer is None
        assert runtime.running is False
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_media_qml_and_registry_keep_f3_static_and_f4_actions_absent() -> None:
    qml = (QML_ROOT / "MediaPresentation.qml").read_text(encoding="utf-8")
    for marker in (
        "Timer {",
        "SettingsManager",
        "MediaRuntimeService",
        "MediaController",
        "QWidget",
        "MultiEffect",
        "layer.enabled",
        "playPauseRequested",
        "nextRequested",
        "previousRequested",
    ):
        assert marker not in qml
    assert "MediaPresentation 1.0 MediaPresentation.qml" in (
        QML_ROOT / "qmldir"
    ).read_text(encoding="utf-8")
    descriptors = [
        item for item in ORDINARY_WIDGET_FAMILY_COMPONENTS if item.family_id == "media"
    ]
    assert len(descriptors) == 1
    assert ordinary_widget_family_component("media").presentation_model_kind == (
        "MediaPresentationModel"
    )


def test_retired_qwidget_media_core_pixels_have_no_surviving_presenter() -> None:
    painting = (ROOT / "widgets" / "media" / "painting.py").read_text(
        encoding="utf-8"
    )
    widget = (ROOT / "widgets" / "media_widget.py").read_text(encoding="utf-8")

    for retired in (
        "paint_header_frame",
        "paint_header_logo",
        "paint_metadata_text",
        "paint_artwork",
        "_scaled_header_logo",
        "_artwork_pixmap",
        "_pending_artwork",
        "_metadata_paint",
        "PreparedMediaArtwork",
        "QPixmap",
        "set_rounded_artwork_border",
        "set_show_header_frame",
    ):
        assert retired not in painting
        assert retired not in widget
    assert not (ROOT / "widgets" / "media" / "artwork_layout.py").exists()
    assert "paint_controls_row" in painting
    assert "paint_playback_progress" in painting
