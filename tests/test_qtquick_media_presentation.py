"""F3/F4 production-shaped gates for the retained Quick Media family."""

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
from rendering.quick.state import QuickInputState, QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.widgets.media import (
    MediaPresentationConfig,
    MediaPresentationModel,
    MediaPresentationStyle,
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
from widgets.media_volume_runtime import MediaVolumeRuntimeSnapshot
from widgets.system_mute_runtime import SystemMuteRuntimeSnapshot


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
        self.transport_calls: list[str] = []
        self.seek_calls: list[float] = []
        self.transport_result = True
        self.seek_result = True

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

    def play_pause(self, *, execute: bool = True) -> bool:
        assert execute is True
        self.transport_calls.append("play")
        return self.transport_result

    def previous_track(self, *, execute: bool = True) -> bool:
        assert execute is True
        self.transport_calls.append("previous")
        return self.transport_result

    def next_track(self, *, execute: bool = True) -> bool:
        assert execute is True
        self.transport_calls.append("next")
        return self.transport_result

    def seek_fraction(self, fraction: float, *, execute: bool = True) -> bool:
        assert execute is True
        self.seek_calls.append(float(fraction))
        return self.seek_result

    def publish(self, snapshot: MediaRuntimeSnapshot) -> None:
        if self.consumer is not None:
            self.consumer.on_media_runtime_snapshot(snapshot)


class _FakeMediaVolumeRuntime:
    def __init__(self) -> None:
        self.consumer = None
        self.thread_manager = None
        self.running = False
        self.snapshot = MediaVolumeRuntimeSnapshot(
            revision=1,
            provider="spotify",
            browser_process=None,
            supported=True,
            available=True,
            level=0.4,
            source="initial",
        )
        self.provider_calls: list[str] = []
        self.target_calls: list[tuple[str, str]] = []
        self.level_calls: list[float] = []
        self.start_result = True

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = bool(self.start_result)
        return self.start_result

    def stop(self) -> None:
        self.running = False

    def current_snapshot(self):
        return self.snapshot

    def set_provider_runtime(self, provider) -> bool:
        normalized = str(provider)
        self.provider_calls.append(normalized)
        return True

    def set_runtime_volume_source(self, provider, source_id) -> bool:
        self.target_calls.append((str(provider), str(source_id)))
        return True

    def set_volume_optimistic(self, level: float) -> bool:
        clamped = max(0.0, min(1.0, float(level)))
        self.level_calls.append(clamped)
        self.publish(
            replace(
                self.snapshot,
                revision=self.snapshot.revision + 1,
                level=clamped,
                source="optimistic",
            )
        )
        return True

    def publish(self, snapshot: MediaVolumeRuntimeSnapshot) -> None:
        self.snapshot = snapshot
        if self.consumer is not None and self.running:
            self.consumer.on_media_volume_runtime_snapshot(snapshot)


class _FakeSystemMuteRuntime:
    def __init__(self) -> None:
        self.consumer = None
        self.thread_manager = None
        self.running = False
        self.snapshot = SystemMuteRuntimeSnapshot(
            revision=1,
            available=True,
            muted=False,
            source="initial",
        )
        self.toggle_calls = 0
        self.step_calls: list[float] = []
        self.start_result = True

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def start(self) -> bool:
        self.running = bool(self.start_result)
        return self.start_result

    def stop(self) -> None:
        self.running = False

    def current_snapshot(self):
        return self.snapshot

    def toggle_mute(self) -> bool:
        self.toggle_calls += 1
        self.publish(
            replace(
                self.snapshot,
                revision=self.snapshot.revision + 1,
                muted=not self.snapshot.muted,
                source="toggle",
            )
        )
        return True

    def step_system_volume(self, delta: float) -> float:
        self.step_calls.append(float(delta))
        return 0.55

    def publish(self, snapshot: SystemMuteRuntimeSnapshot) -> None:
        self.snapshot = snapshot
        if self.consumer is not None and self.running:
            self.consumer.on_system_mute_runtime_snapshot(snapshot)


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
        "playback_progress_height": 9,
        "playback_progress_fill_color": [45, 190, 250, 230],
        "playback_progress_shadow_enabled": True,
        "playback_progress_glow_enabled": True,
        "playback_progress_glow_color": [45, 190, 250, 180],
        "spotify_volume_enabled": True,
        "spotify_volume_fill_color": [255, 255, 255, 230],
        "mute_button_enabled": True,
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
        "can_seek": True,
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


def _model(
    provider=None,
    runtime=None,
    volume_runtime=None,
    system_mute_runtime=None,
    **overrides,
):
    artwork_provider = provider or MediaArtworkImageProvider()
    config = MediaPresentationConfig.from_mapping(_values(**overrides))
    style = MediaPresentationStyle.project(config, _shadows())
    service = runtime or _FakeMediaRuntime()
    return (
        MediaPresentationModel(
            config,
            style,
            artwork_provider,
            service,
            volume_runtime_service=volume_runtime,
            system_mute_runtime_service=system_mute_runtime,
        ),
        service,
        artwork_provider,
    )


def test_media_config_and_style_project_canonical_settings_and_direction() -> None:
    config = MediaPresentationConfig.from_widgets_mapping(
        {
            "media": {
                "font_size": 31,
                "artwork_size": 210,
                "bg_opacity": 0.5,
                "playback_progress_height": 9,
                "playback_progress_fill_color": [45, 190, 250, 230],
                "playback_progress_shadow_enabled": True,
                "playback_progress_glow_enabled": True,
                "playback_progress_glow_color": [45, 190, 250, 180],
            }
        }
    )
    style = MediaPresentationStyle.project(
        config,
        _shadows(direction="NW", frame_extra_offset=2, text_extra_offset=3),
    )

    assert config.font_size == 31
    assert config.artwork_size == 210
    assert config.playback_progress_height == 9
    assert config.playback_progress_fill_color == (45, 190, 250, 230)
    assert config.playback_progress_shadow_enabled is True
    assert config.playback_progress_glow_enabled is True
    assert config.app_volume_enabled is True
    assert config.app_volume_fill_color == (79, 79, 79, 150)
    assert config.system_mute_enabled is False
    assert style.card_style.background_color.alpha() == 128
    assert style.card_style.shadow_offset_x == pytest.approx(-6.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-6.0)
    assert style.text_shadow_offset_x == pytest.approx(-5.0)
    assert style.text_shadow_offset_y == pytest.approx(-5.0)

    model = MediaPresentationModel(config, style, MediaArtworkImageProvider())
    assert model.artworkBorderColor == style.card_style.border_color
    assert model.artworkBorderWidth == pytest.approx(6.0)
    assert model.progressHeight == pytest.approx(9.0)
    assert model.progressFillColor == QColor(45, 190, 250, 230)
    assert model.progressGlowColor == QColor(45, 190, 250, 180)


def test_media_model_projects_and_routes_existing_app_volume_owner() -> None:
    volume_runtime = _FakeMediaVolumeRuntime()
    model, runtime, _provider = _model(volume_runtime=volume_runtime)
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))

    assert model.appVolumeAvailable is True
    assert model.appVolumeLevel == pytest.approx(0.4)
    assert model.appVolumeTrackColor == QColor(25, 32, 42, 255)
    assert model.appVolumeBorderColor == QColor(120, 195, 255, 255)
    assert model.appVolumeFillColor == QColor(255, 255, 255, 140)
    assert volume_runtime.consumer is model
    assert volume_runtime.running is True

    model.on_media_volume_runtime_snapshot(
        replace(volume_runtime.snapshot, revision=0, level=0.1)
    )
    assert model.appVolumeLevel == pytest.approx(0.4)
    assert model.request_app_volume(1.4) is True
    assert model.request_app_volume_step(-1) is True
    assert volume_runtime.level_calls == [pytest.approx(1.0), pytest.approx(0.95)]

    model.on_media_runtime_volume_target("spotify_browser", "firefox.exe")
    assert volume_runtime.target_calls == [("spotify_browser", "firefox.exe")]

    disabled = replace(model.config, app_volume_enabled=False)
    assert model.apply_config(disabled) is True
    assert model.appVolumeAvailable is False
    assert volume_runtime.running is False
    assert model.request_app_volume(0.2) is False

    assert model.apply_config(replace(disabled, app_volume_enabled=True)) is True
    assert volume_runtime.running is True
    assert volume_runtime.consumer is model
    model.retire()
    assert volume_runtime.running is False
    assert volume_runtime.consumer is None


def test_media_volume_start_failure_rolls_back_both_retained_leases() -> None:
    volume_runtime = _FakeMediaVolumeRuntime()
    volume_runtime.start_result = False
    model, runtime, _provider = _model(volume_runtime=volume_runtime)

    with pytest.raises(RuntimeError, match="volume runtime service failed"):
        model.activate(object())

    assert model.is_active is False
    assert runtime.running is False
    assert runtime.consumer is None
    assert volume_runtime.running is False
    assert volume_runtime.consumer is None


def test_media_model_projects_and_routes_existing_system_mute_owner() -> None:
    mute_runtime = _FakeSystemMuteRuntime()
    model, runtime, _provider = _model(system_mute_runtime=mute_runtime)
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))

    assert model.systemMuteAvailable is True
    assert model.systemMuted is False
    assert model.controlsBandAvailable is True
    assert mute_runtime.consumer is model
    assert mute_runtime.running is True

    model.on_system_mute_runtime_snapshot(
        replace(mute_runtime.snapshot, revision=0, muted=True)
    )
    assert model.systemMuted is False
    assert model.request_system_mute_toggle() is True
    assert model.systemMuted is True
    assert mute_runtime.toggle_calls == 1
    assert model.request_system_volume_step(0.05) == pytest.approx(0.55)
    assert mute_runtime.step_calls == [pytest.approx(0.05)]

    disabled = replace(model.config, system_mute_enabled=False)
    assert model.apply_config(disabled) is True
    assert model.systemMuteAvailable is False
    assert mute_runtime.running is False
    assert model.request_system_mute_toggle() is False
    assert model.request_system_volume_step(-0.05) is None

    assert model.apply_config(replace(disabled, system_mute_enabled=True)) is True
    assert mute_runtime.running is True
    model.retire()
    assert mute_runtime.running is False
    assert mute_runtime.consumer is None


def test_system_mute_start_failure_rolls_back_all_retained_media_leases() -> None:
    volume_runtime = _FakeMediaVolumeRuntime()
    mute_runtime = _FakeSystemMuteRuntime()
    mute_runtime.start_result = False
    model, runtime, _provider = _model(
        volume_runtime=volume_runtime,
        system_mute_runtime=mute_runtime,
    )

    with pytest.raises(RuntimeError, match="system-mute runtime service failed"):
        model.activate(object())

    assert model.is_active is False
    assert runtime.running is False
    assert runtime.consumer is None
    assert volume_runtime.running is False
    assert volume_runtime.consumer is None
    assert mute_runtime.running is False
    assert mute_runtime.consumer is None


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
    assert model.canSeek is True
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


def test_media_model_handles_empty_provider_change_and_f4_state() -> (
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


def test_media_model_routes_capability_gated_transport_to_existing_owner() -> None:
    model, runtime, _provider = _model()
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))

    assert model.request_transport("play") is True
    assert model.request_transport("previous") is True
    assert model.request_transport("next") is True
    assert runtime.transport_calls == ["play", "previous", "next"]

    runtime.publish(_snapshot(2, image=None, info=_info(can_next=False)))
    assert model.request_transport("next") is False
    assert runtime.transport_calls == ["play", "previous", "next"]

    runtime.transport_result = False
    assert model.request_transport("play") is False
    assert runtime.refresh_calls == [True]
    model.retire()
    assert model.request_transport("play") is False


def test_media_model_routes_capability_gated_seek_without_mutating_progress() -> None:
    model, runtime, _provider = _model()
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))
    accepted_fraction = model.progressFraction

    assert model.request_seek(1.4) is True
    assert runtime.seek_calls == [1.0]
    assert model.progressFraction == accepted_fraction
    assert model.request_seek(float("nan")) is False
    assert runtime.seek_calls == [1.0]

    runtime.publish(_snapshot(2, image=None, info=_info(can_seek=False)))
    assert model.canSeek is False
    assert model.request_seek(0.25) is False
    assert runtime.seek_calls == [1.0]

    runtime.publish(_snapshot(3, image=None, info=_info(duration_ms=0)))
    assert model.canSeek is True
    assert model.progressAvailable is False
    assert model.request_seek(0.5) is False
    assert runtime.seek_calls == [1.0]
    model.retire()
    assert model.request_seek(0.5) is False


def test_media_interaction_admission_mutates_model_without_runtime_work() -> None:
    model, runtime, _provider = _model()
    changes = []
    model.stateChanged.connect(lambda: changes.append(model.interactionEnabled))

    assert model.interactionEnabled is False
    assert model.set_interaction_enabled(True) is True
    assert model.set_interaction_enabled(True) is False
    assert model.set_interaction_enabled(False) is True
    assert changes == [True, False]
    assert runtime.refresh_calls == []
    assert runtime.transport_calls == []


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


def test_media_runtime_manager_injects_separate_app_volume_lease_into_same_model() -> (
    None
):
    provider = MediaArtworkImageProvider()
    config = MediaPresentationConfig.from_mapping(_values())
    style = MediaPresentationStyle.project(config, _shadows())
    model = MediaPresentationModel(config, style, provider, runtime_generation=91)
    owner = WidgetRuntimeManager(_RuntimeHost())

    service = owner.ensure_widget_service(
        "spotify_volume", model, {"media": {"provider": "spotify"}}
    )

    assert service is not None
    assert model._volume_runtime_service is service
    assert model._runtime_service is None
    assert service.shared_owner is None
    assert service.is_running() is False
    owner.cleanup()
    assert service.is_retired() is True


def test_media_runtime_manager_injects_system_mute_lease_into_same_model() -> None:
    provider = MediaArtworkImageProvider()
    config = MediaPresentationConfig.from_mapping(_values())
    style = MediaPresentationStyle.project(config, _shadows())
    model = MediaPresentationModel(config, style, provider, runtime_generation=91)
    owner = WidgetRuntimeManager(_RuntimeHost())

    service = owner.ensure_widget_service("mute_button", model, {"media": {}})

    assert service is not None
    assert model._system_mute_runtime_service is service
    assert model._runtime_service is None
    assert model._volume_runtime_service is None
    assert service.shared_owner is None
    assert service.is_running() is False
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
    volume_runtime = _FakeMediaVolumeRuntime()
    mute_runtime = _FakeSystemMuteRuntime()
    model, _, provider = _model(
        factory.media_artwork_provider,
        runtime,
        volume_runtime,
        mute_runtime,
    )
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
        assert item.findChild(QQuickItem, "mediaControlsRow") is not None
        assert item.findChild(QQuickItem, "mediaProgressFill") is not None
        progress_glow = item.findChild(QQuickItem, "mediaProgressGlow")
        progress_seek_area = item.findChild(QQuickItem, "mediaProgressSeekArea")
        assert progress_glow is not None
        assert progress_seek_area is not None
        assert item.seekFractionAt(-5.0, 100.0) == pytest.approx(0.0)
        assert item.seekFractionAt(45.0, 100.0) == pytest.approx(0.45)
        assert item.seekFractionAt(120.0, 100.0) == pytest.approx(1.0)
        assert item.findChild(QQuickItem, "mediaAppVolumeSlider") is not None
        assert item.findChild(QQuickItem, "mediaAppVolumeFill") is not None
        assert item.findChild(QQuickItem, "mediaSystemMuteButton") is not None
        assert item.findChild(QQuickItem, "mediaSystemMuteIcon") is not None
        assert model.hasArtwork is True
        assert model.appVolumeAvailable is True
        assert model.systemMuteAvailable is True
        assert provider.image_count == 1

        item.playPauseRequested.emit()
        item.appVolumeLevelRequested.emit(0.7)
        item.systemMuteToggleRequested.emit()
        item.seekFractionRequested.emit(0.6)
        assert runtime.transport_calls == []
        assert volume_runtime.level_calls == []
        assert mute_runtime.toggle_calls == 0
        assert runtime.seek_calls == []
        assert presentation.apply_input_state(
            QuickInputState(
                screen_index=0,
                runtime_generation=92,
                ctrl_held=True,
            )
        ) is True
        item.playPauseRequested.emit()
        item.previousRequested.emit()
        item.nextRequested.emit()
        item.appVolumeLevelRequested.emit(0.25)
        item.systemMuteToggleRequested.emit()
        item.seekFractionRequested.emit(0.6)
        assert runtime.transport_calls == ["play", "previous", "next"]
        assert volume_runtime.level_calls == [pytest.approx(0.25)]
        assert mute_runtime.toggle_calls == 1
        assert runtime.seek_calls == [pytest.approx(0.6)]
        assert model.systemMuted is True

        assert presentation.apply_input_state(
            {
                "admission_open": False,
                "interaction_mode_enabled": True,
                "ctrl_held": True,
            }
        ) is True
        item.nextRequested.emit()
        item.appVolumeLevelRequested.emit(0.8)
        item.systemMuteToggleRequested.emit()
        item.seekFractionRequested.emit(0.2)
        assert runtime.transport_calls == ["play", "previous", "next"]
        assert volume_runtime.level_calls == [pytest.approx(0.25)]
        assert mute_runtime.toggle_calls == 1
        assert runtime.seek_calls == [pytest.approx(0.6)]

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
        assert item.findChild(QQuickItem, "mediaProgressGlow") is progress_glow
        assert item.findChild(QQuickItem, "mediaProgressSeekArea") is progress_seek_area
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


def test_media_qml_and_registry_keep_actions_static_and_python_owned() -> None:
    qml = (QML_ROOT / "MediaPresentation.qml").read_text(encoding="utf-8")
    for marker in (
        "Timer {",
        "SettingsManager",
        "MediaRuntimeService",
        "MediaController",
        "QWidget",
        "MultiEffect",
        "layer.enabled",
    ):
        assert marker not in qml
    for marker in (
        "signal playPauseRequested()",
        "signal nextRequested()",
        "signal previousRequested()",
        "signal appVolumeLevelRequested(real level)",
        "signal systemMuteToggleRequested()",
        "signal seekFractionRequested(real fraction)",
        "mediaModel.interactionEnabled",
        "mediaModel.progressFraction",
        "mediaModel.appVolumeLevel",
        "mediaModel.systemMuted",
        "mediaModel.canSeek",
        'objectName: "mediaProgressGlow"',
        'objectName: "mediaProgressSeekArea"',
        "cached: true",
    ):
        assert marker in qml
    assert "anchors.margins: -3.0" not in qml
    assert "mediaProgressSeekHandle" not in qml
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
        "resolve_control_hit",
        "paint_controls_row",
        "paint_playback_progress",
        "_controls_feedback",
        "_playback_progress_paint_key",
    ):
        assert retired not in widget
    for retired_path in (
        ROOT / "widgets" / "media" / "artwork_layout.py",
        ROOT / "widgets" / "media" / "painting.py",
        ROOT / "widgets" / "media" / "feedback.py",
        ROOT / "widgets" / "spotify_volume_widget.py",
        ROOT / "widgets" / "mute_button_widget.py",
    ):
        assert not retired_path.exists()
    assert "Intentionally paint nothing" in widget
