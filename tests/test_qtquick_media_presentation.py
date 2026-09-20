"""F3/F4 production-shaped gates for the retained Quick Media family."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from core.settings.default_contract import require_canonical_default
from PySide6.QtCore import QPointF, QSize
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
from rendering.widget_descriptors import get_widget_runtime_descriptor
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
        **require_canonical_default("widgets.shadows"),
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
    assert style.card_style.shadow_offset_x == pytest.approx(-4.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-4.0)
    assert style.card_style.shadow_extend_left == pytest.approx(2.0)
    assert style.card_style.shadow_extend_top == pytest.approx(2.0)
    assert style.card_style.shadow_extend_right == pytest.approx(0.0)
    assert style.card_style.shadow_extend_bottom == pytest.approx(0.0)
    assert style.text_shadow_offset_x == pytest.approx(-5.0)
    assert style.text_shadow_offset_y == pytest.approx(-5.0)

    model = MediaPresentationModel(config, style, MediaArtworkImageProvider())
    assert model.artworkBorderColor == style.card_style.border_color
    assert model.artworkBorderWidth == pytest.approx(2.75)
    assert model.progressHeight == pytest.approx(9.0)
    assert model.progressFillColor == QColor(45, 190, 250, 230)
    assert model.progressGlowColor == QColor(45, 190, 250, 180)


def test_media_runtime_provider_failover_retargets_existing_app_volume_owner() -> None:
    volume_runtime = _FakeMediaVolumeRuntime()
    model, runtime, _provider = _model(volume_runtime=volume_runtime)
    model.activate(object())

    # Runtime failover is authoritative for the whole Media family. The volume
    # owner must move to the same provider epoch before the browser's exact GSMTC
    # host identity arrives, otherwise a browser-configured owner can remain
    # unsupported forever after Media itself has failed over successfully.
    model.on_media_runtime_provider_changed(
        "spotify_browser", "spotify", source="media_runtime_autofallback", persist=True
    )
    assert volume_runtime.provider_calls == ["spotify"]

    model.on_media_runtime_provider_changed(
        "spotify", "spotify_browser", source="media_runtime_autofallback", persist=True
    )
    assert volume_runtime.provider_calls == ["spotify", "spotify_browser"]

    model.on_media_runtime_volume_target("spotify_browser", "firefox.exe")
    assert volume_runtime.target_calls == [("spotify_browser", "firefox.exe")]


def test_media_model_projects_and_routes_existing_app_volume_owner() -> None:
    volume_runtime = _FakeMediaVolumeRuntime()
    model, runtime, _provider = _model(volume_runtime=volume_runtime)
    model.activate(object())
    runtime.publish(_snapshot(1, image=_image()))

    assert model.appVolumeAvailable is True
    assert model.appVolumeLevel == pytest.approx(0.4)
    assert model.appVolumeTrackColor == QColor(*model.config.app_volume_track_color)
    assert model.appVolumeBorderColor == QColor(*model.config.app_volume_border_color)
    assert model.appVolumeFillColor == QColor(*model.config.app_volume_fill_color)
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

    assert source_a == f"image://mediaartwork/{identity_a}"
    assert returned.pixelColor(0, 0) == QColor("#ff0000")
    assert size == QSize(96, 72)
    # The provider retains source aspect/pixels; the retained QML mask owns
    # rounded presentation. Mutating a returned image cannot affect the cache.
    returned.fill(QColor("#ffffff"))
    assert provider.requestImage(identity_a, QSize(), QSize()).pixelColor(0, 0) == QColor("#ff0000")
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

    assert model.title == "No Media Playing"
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
    assert model.canSeek is False
    assert model.progressAvailable is True
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
        assert controller.apply_input_state(
            QuickInputState(
                screen_index=0,
                runtime_generation=999,
                ctrl_held=True,
            )
        ) is False
        assert model.interactionEnabled is False
        assert controller.apply_input_state(
            QuickInputState(
                screen_index=0,
                runtime_generation=92,
                ctrl_held=True,
            )
        ) is True
        play_pause_button = item.findChild(QQuickItem, "mediaPlayPauseButton")
        assert play_pause_button is not None
        assert play_pause_button.opacity() == pytest.approx(1.0)
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

        assert controller.apply_input_state(
            QuickInputState(
                screen_index=0,
                runtime_generation=92,
                admission_open=False,
                interaction_mode_enabled=True,
                ctrl_held=True,
            )
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


@pytest.mark.qt
def test_media_authored_xy_reflow_and_empty_custom_roundtrip(qt_app) -> None:
    """The old card rails reflow; child editing cannot freeze them at 600 px."""
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=93, screen=screen,
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
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        artwork = item.findChild(QQuickItem, "mediaArtworkFrame")
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        transport = item.findChild(QQuickItem, "mediaControlsRow")
        assert artwork is not None and seek is not None and transport is not None
        assert artwork.isVisible() and seek.isVisible() and transport.isVisible()
        metadata_lane = item.findChild(QQuickItem, "mediaMetadata")
        assert metadata_lane is not None

        def verify_authored_metadata_artwork_gap() -> None:
            # World-space proof, including shell insets and uniform parent
            # transforms. The edit box is the full metadata lane, not merely
            # the handful of glyph pixels visible in the screenshot.
            lane_right = metadata_lane.mapToItem(
                item, QPointF(metadata_lane.width(), 0.0)
            ).x()
            art_left = artwork.mapToItem(item, QPointF(0.0, 0.0)).x()
            assert lane_right <= art_left - 1.0, (lane_right, art_left)

        verify_authored_metadata_artwork_gap()
        authored = (artwork.x(), artwork.width(), artwork.height(),
                    seek.width(), transport.width())
        # A 1x1 artifact is a collapsed authored-rail calculation, not a
        # legitimate artwork baseline. Catch it before the extent change too.
        assert authored[1] > 32.0 and authored[2] > 32.0
        assert model.customChildGeometry == {}

        # Explicit outer content extent is the existing single reflow owner.
        # The QML artwork/seek/transport children should measure the enlarged
        # authored card, while the unedited child payload remains empty.
        assert model.set_content_extent(980, 460)
        qt_app.processEvents()
        assert artwork.width() > authored[1]
        assert artwork.height() > authored[2]
        assert seek.width() > authored[3]
        assert transport.width() > authored[4]
        assert artwork.x() > authored[0]
        verify_authored_metadata_artwork_gap()
        assert model.customChildGeometry == {}
        assert runtime.refresh_calls == []
        assert provider.image_count == 1

        # Restore authored width/height, without a child Save/reset/migration.
        assert model.clear_content_extent()
        qt_app.processEvents()
        assert artwork.x() == pytest.approx(authored[0])
        assert artwork.width() == pytest.approx(authored[1])
        assert artwork.height() == pytest.approx(authored[2])
        assert seek.width() == pytest.approx(authored[3])
        assert transport.width() == pytest.approx(authored[4])
        verify_authored_metadata_artwork_gap()
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_metadata_reset_releases_positioner_owned_y_without_stale_spacing(qt_app) -> None:
    """Independently edited metadata/status must not compete with Column's Y.

    A test of rendered coordinates, not just source literals: changing metadata
    and PAUSED child offsets then clearing them restores the same authored flow
    without reloading a CUSTOM slot or changing the outer rectangle.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=98, screen=screen,
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
            geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 330.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        lane = item.findChild(QQuickItem, "mediaMetadata")
        track = item.findChild(QQuickItem, "mediaTrackMetadata")
        track_slot = item.findChild(QQuickItem, "mediaMetadataFlowSlot")
        state = item.findChild(QQuickItem, "mediaPlaybackState")
        state_slot = item.findChild(QQuickItem, "mediaPlaybackStateFlowSlot")
        assert all(v is not None for v in (lane, track, track_slot, state, state_slot))
        assert track.parentItem() is track_slot and state.parentItem() is state_slot
        assert track_slot.parentItem() is lane and state_slot.parentItem() is lane
        assert (track.x(), track.y(), track.scale()) == pytest.approx((0, 0, 1))
        assert state_slot.y() >= track_slot.y() + track_slot.height()
        baseline = (
            state_slot.y(), track_slot.height(),
            state.mapToItem(lane, QPointF(0.0, 0.0)).y(),
        )
        assert model.set_custom_child_geometry({
            "metadata": {"x_offset": 0.035, "y_offset": 0.06,
                         "width_scale": 1.2, "height_scale": 1.2},
            "playback_state": {"x_offset": 0.02, "y_offset": -0.03,
                               "width_scale": 1.1, "height_scale": 1.1},
        })
        qt_app.processEvents()
        # Only content moves. The authored flow slots cannot inherit child X/Y.
        assert state_slot.y() == pytest.approx(baseline[0])
        assert track_slot.height() == pytest.approx(baseline[1])
        assert track.y() != 0 and state.y() != 0
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert (track.x(), track.y(), track.scale()) == pytest.approx((0, 0, 1))
        assert (state.x(), state.y(), state.scale()) == pytest.approx((0, 0, 1))
        assert state_slot.y() == pytest.approx(baseline[0])
        assert track_slot.height() == pytest.approx(baseline[1])
        assert state.mapToItem(lane, QPointF(0.0, 0.0)).y() == pytest.approx(baseline[2])
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_artist_independent_xy_and_flip_preserve_authored_crossfade_slot(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=95, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 330.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        artist = item.findChild(QQuickItem, "mediaArtist")
        title = item.findChild(QQuickItem, "mediaTitle")
        outgoing = item.findChild(QQuickItem, "mediaOutgoingArtist")
        assert artist is not None and title is not None and outgoing is not None
        assert artist.isVisible() and artist.height() > 0.0
        authored = (artist.x(), artist.y(), artist.scale(), title.x(), title.y())
        assert authored[:3] == pytest.approx((0.0, 0.0, 1.0))
        assert model.set_custom_child_geometry({"artist": {
            "x_offset": 0.02, "y_offset": 0.03,
            "width_scale": 1.25, "height_scale": 1.25,
            "alignment": "right",
        }})
        qt_app.processEvents()
        assert artist.x() == pytest.approx(0.02 * item.property("childNormalizationWidth"))
        assert artist.y() == pytest.approx(0.03 * item.property("childNormalizationHeight"))
        assert artist.scale() == pytest.approx(1.25)
        assert outgoing.x() == pytest.approx(artist.x())
        assert outgoing.y() == pytest.approx(artist.y())
        assert outgoing.scale() == pytest.approx(artist.scale())
        assert (title.x(), title.y()) == pytest.approx(authored[3:])
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert (artist.x(), artist.y(), artist.scale()) == pytest.approx(authored[:3])
        assert model.customChildGeometry == {}
        assert runtime.refresh_calls == [] and provider.image_count == 1
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
        "layer.enabled: mediaRoot.mediaModel.roundedArtwork",
        "maskSource: artworkMask",
        "canonicalCardContentWidth * 0.75",
        "readonly property real fitScale: Math.max(",
        'mediaRoot.childWidthScale("mute_button")',
        "anchors.margins: artworkFrame.imageInset",
        "scaleAwareHeaderStrokeWidth",
    ):
        assert marker in qml
    assert "anchors.margins: -3.0" not in qml
    assert "heightScale: 0.925" not in qml
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
    for retired_path in (
        ROOT / "widgets" / "media_widget.py",
        ROOT / "widgets" / "media_layout.py",
        ROOT / "widgets" / "media" / "artwork_layout.py",
        ROOT / "widgets" / "media" / "painting.py",
        ROOT / "widgets" / "media" / "feedback.py",
        ROOT / "widgets" / "spotify_volume_widget.py",
        ROOT / "widgets" / "mute_button_widget.py",
    ):
        assert not retired_path.exists()


def test_media_metadata_and_state_flip_and_resize_share_stable_top_left_projection() -> None:
    descriptor = get_widget_runtime_descriptor("media")
    roles = {role.role_id: role for role in descriptor.custom_child_roles}
    assert roles["metadata"].alignment_flip and roles["playback_state"].alignment_flip
    assert roles["artist"].alignment_flip and roles["artist"].movable
    presentation = (QML_ROOT / "MediaPresentation.qml").read_text(encoding="utf-8")
    for role in ("metadata", "playback_state"):
        assert f'x: mediaRoot.childOffsetX("{role}")' in presentation
        assert f'y: mediaRoot.childOffsetY("{role}")' in presentation
        assert f'scale: mediaRoot.childWidthScale("{role}")' in presentation
    assert 'textAlignment: mediaRoot.orientedChildAlignment("metadata", "left")' in presentation
    assert 'horizontalAlignment: mediaRoot.orientedChildAlignment("playback_state", "left")' in presentation
    assert 'artistAlignment: mediaRoot.orientedChildAlignment(' in presentation
    assert 'readonly property real flippedAuthoredRailX:' in presentation
    assert 'progressBand.width - 4.0 - width' in presentation
    assert 'property real customEditPlacementCompensationX: flippedAuthoredRailX' in presentation
    crossfade = (QML_ROOT / "MediaMetadataColumn.qml").read_text(encoding="utf-8")
    assert crossfade.count('horizontalAlignment: metadataFade.textAlignment === "right"') == 4
    assert crossfade.count('horizontalAlignment: metadataFade.artistAlignment === "right"') == 2


@pytest.mark.qt
def test_media_external_volume_bounds_and_edit_rebase_follow_live_lane(qt_app) -> None:
    """Parent X/Y changes and old child offsets must map to the visible accessory.

    The edit proxy maps the real appVolumeTrack. These scene assertions reject a
    mere paint clip over an out-of-bounds target, and verify gesture compensation
    for the pre-clamp saved offset without writing that offset on a plain click.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=92,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    # The window is not shown in offscreen Qt tests; set a real display-local
    # content rect before probing the side-selection rule.  A zero-width host
    # would otherwise place a 650 px card to the left of its own fake midpoint.
    window.setWidth(1600)
    window.setHeight(900)
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    volume_runtime = _FakeMediaVolumeRuntime()
    model, _, provider = _model(
        factory.media_artwork_provider, runtime, volume_runtime
    )
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(35.0, 40.0, 650.0, 300.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        assert model.appVolumeAvailable
        track = item.findChild(QQuickItem, "mediaAppVolumeTrack")
        lane = item.findChild(QQuickItem, "mediaAppVolumeSlider")
        assert track is not None and lane is not None and lane.isVisible()

        # A narrow Y edit shrinks the *live* track. Both signs of pre-existing
        # normalized offset, both parent X extents and either accessory side
        # must remain within the real lane (not the Media card).
        # In an offscreen QQuickWindow the window's dimensions do not
        # automatically size the detached ordinary-widget host. Set the
        # ACTUAL parent item that Media's side-of-display binding reads.
        # A zero-width parent makes every card appear on the wrong side and
        # says nothing about the production orientation contract.
        scene_host = item.parentItem()
        assert scene_host is not None
        scene_root = controller.scene_root
        scene_root.setWidth(1600.0)
        scene_root.setHeight(900.0)
        qt_app.processEvents()
        # The anchored host can only report the owning scene's actual geometry.
        assert scene_root.width() >= 1600.0
        assert scene_host.width() == pytest.approx(scene_root.width())

        for width, height in ((650, 300), (620, 210), (780, 440)):
            assert model.set_content_extent(width, height) or model.contentExtentActive
            item.setWidth(float(width))
            item.setHeight(float(height))
            for left in (False, True):
                parent_width = float(item.parentItem().width())
                assert parent_width >= 1600.0, parent_width
                if left:
                    item.setX(parent_width - item.width() - 20.0)
                else:
                    item.setX(20.0)
                qt_app.processEvents()
                assert bool(item.property("appVolumeOnLeft")) is left
                for offset in (-0.35, 0.0, 0.35):
                    model.set_custom_child_geometry({"volume_bar": {
                        "x_offset": offset, "y_offset": offset,
                    }})
                    qt_app.processEvents()
                    assert float(track.x()) >= -0.01
                    assert float(track.y()) >= -0.01
                    assert float(track.x() + track.width()) <= lane.width() + 0.01
                    assert float(track.y() + track.height()) <= lane.height() + 0.01
                    assert float(track.property("customEditPlacementCompensationX")) == pytest.approx(
                        float(track.x()) - float(track.property("requestedTrackX")), abs=0.01
                    )
                    assert float(track.property("customEditPlacementCompensationY")) == pytest.approx(
                        float(track.y()) - float(track.property("requestedTrackY")), abs=0.01
                    )
        assert runtime.refresh_calls == []
        assert provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_header_flip_swaps_artwork_and_metadata_rails_and_reset_is_identity(qt_app) -> None:
    """A semantic flip must not make metadata overlap the artwork or shift on reset."""
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=102, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 700.0, 340.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        header = item.findChild(QQuickItem, "mediaHeaderFrame")
        art = item.findChild(QQuickItem, "mediaArtworkFrame")
        metadata = item.findChild(QQuickItem, "mediaMetadata")
        assert header is not None and art is not None and metadata is not None
        assert art.isVisible() and art.width() > 32.0 and metadata.width() > 32.0
        baseline = (header.x(), art.x(), metadata.x(), metadata.width())
        assert metadata.x() + metadata.width() + 1.0 < art.x()
        text = item.findChild(QQuickItem, "mediaTrackMetadata")
        state = item.findChild(QQuickItem, "mediaPlaybackState")
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        assert text is not None and state is not None and seek is not None
        initial_seek_x = seek.x()
        initial_state_alignment = int(state.property("horizontalAlignment"))
        assert str(text.property("textAlignment")) == "left"
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert bool(item.property("headerFlipped"))
        # BrandedHeader's nested frame itself always has local x=0. Its
        # positioned parent owns the semantic rail.
        assert header.parentItem().x() > 0.0
        assert art.x() + art.width() + 1.0 < metadata.x()
        assert metadata.width() > 32.0
        assert str(text.property("textAlignment")) == "right"
        assert int(state.property("horizontalAlignment")) != initial_state_alignment
        assert seek.x() > initial_seek_x + 20.0
        # An individual metadata flip composes with global placement orientation.
        assert model.set_custom_child_geometry({
            "header": {"alignment": "right"},
            "metadata": {"alignment": "right"},
        })
        qt_app.processEvents()
        assert str(text.property("textAlignment")) == "left"
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        assert str(text.property("textAlignment")) == "right"
        assert model.set_content_extent(950, 455)
        qt_app.processEvents()
        assert art.x() + art.width() + 1.0 < metadata.x()
        assert model.clear_content_extent()
        assert model.set_custom_child_geometry({})
        qt_app.processEvents()
        assert not bool(item.property("headerFlipped"))
        assert str(text.property("textAlignment")) == "left"
        assert int(state.property("horizontalAlignment")) == initial_state_alignment
        assert seek.x() == pytest.approx(initial_seek_x)
        assert (header.x(), art.x(), metadata.x(), metadata.width()) == pytest.approx(baseline)
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_seek_child_placement_and_size_never_change_media_authored_flow_reservations(qt_app) -> None:
    """Seek CUSTOM changes must not re-size artwork/metadata or shift bands.

    Editing seek is a child-geometry transaction. Artwork's authored size and
    the parent's Column reservation must not consume the edited seek rectangle,
    even when the seek remains on its original X/Y rail while its size changes.
    This is the causal regression behind mid-gesture artwork/seek disappearance.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=121, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 700.0, 340.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        art = item.findChild(QQuickItem, "mediaArtworkFrame")
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        band = item.findChild(QQuickItem, "mediaProgressBand")
        main = item.findChild(QQuickItem, "mediaMainBand")
        metadata = item.findChild(QQuickItem, "mediaMetadata")
        controls = item.findChild(QQuickItem, "mediaControlsBandSlot")
        assert all(v is not None for v in (art, seek, band, main, metadata, controls))
        assert art.isVisible() and seek.isVisible()
        for flipped in (False, True):
            header = {"header": {"alignment": "right"}} if flipped else {}
            model.set_custom_child_geometry(header)
            qt_app.processEvents()
            baseline = (art.x(), art.y(), art.width(), art.height(),
                        main.height(), band.height(), metadata.x(),
                        metadata.width(), controls.y())
            assert baseline[2] > 32.0 and baseline[3] > 32.0
            for seek_edit in (
                {"width_scale": 1.45, "height_scale": 1.65},
                {"x_offset": 0.12, "y_offset": 0.08},
                {"x_offset": -0.16, "y_offset": -0.07,
                 "width_scale": 1.22, "height_scale": 1.35},
            ):
                assert model.set_custom_child_geometry({**header, "seek_bar": seek_edit})
                qt_app.processEvents()
                measured = (art.x(), art.y(), art.width(), art.height(),
                            main.height(), band.height(), metadata.x(),
                            metadata.width(), controls.y())
                assert measured == pytest.approx(baseline, abs=0.5), (
                    "seek edited authored layout", flipped, seek_edit,
                    baseline, measured,
                )
                assert art.isVisible() and art.width() > 32.0 and art.height() > 32.0
                assert seek.isVisible() and seek.width() > 16.0 and seek.height() > 1.0
            model.set_custom_child_geometry(header)
            qt_app.processEvents()
            restored = (art.x(), art.y(), art.width(), art.height(),
                        main.height(), band.height(), metadata.x(),
                        metadata.width(), controls.y())
            assert restored == pytest.approx(baseline, abs=0.5)
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_flipped_media_artwork_and_seek_first_drag_stays_under_pointer(qt_app) -> None:
    """An on-rail flip followed by the first REAL X/Y edit must not jump lanes.

    This exercises real QML/model geometry with the same normalized offset
    and compensation owned by the production child-move resolver. It does not
    substitute for native pointer/collision or Save/reopen acceptance.
    """
    import math
    from rendering.custom_child_geometry import (
        CustomChildSize, freeform_layout_block_child_role,
        resolve_child_move_geometry,
    )
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=120, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 700.0, 340.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        assert model.set_custom_child_geometry({"header": {"alignment": "right"}})
        qt_app.processEvents()
        art = item.findChild(QQuickItem, "mediaArtworkFrame")
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        main = item.findChild(QQuickItem, "mediaMainBand")
        assert all(v is not None for v in (art, seek, main))
        assert art.isVisible() and art.width() > 32.0 and art.height() > 32.0
        norm_width = float(item.property("childNormalizationWidth"))
        norm_height = float(item.property("childNormalizationHeight"))
        assert norm_width > 100.0 and norm_height > 100.0
        role = freeform_layout_block_child_role("artwork", movable=True)
        scale = float(item.property("presentationScale"))
        assert scale > 0.0
        # Each gesture reads the CURRENT on-rail presentation displacement.
        # Applying a tiny move must change the observed rectangle by a tiny
        # amount, not by a whole art/seek rail or the parent Column height.
        for role_id, target in (("artwork", art), ("seek_bar", seek)):
            model.set_custom_child_geometry({"header": {"alignment": "right"}})
            qt_app.processEvents()
            before = target.mapToItem(item, QPointF(0.0, 0.0))
            before_size = (target.width(), target.height())
            compensation_x = float(target.property("customEditPlacementCompensationX"))
            compensation_y = float(target.property("customEditPlacementCompensationY") or 0.0)
            assert all(map(math.isfinite, (compensation_x, compensation_y)))
            record = resolve_child_move_geometry(
                role, CustomChildSize(), raw_dx=7.0, raw_dy=5.0,
                normalization_width=norm_width,
                normalization_height=norm_height, outer_scale=scale,
                placement_compensation_x=compensation_x,
                placement_compensation_y=compensation_y,
            )
            assert model.set_custom_child_geometry({
                "header": {"alignment": "right"},
                role_id: record.to_mapping(),
            })
            qt_app.processEvents()
            after = target.mapToItem(item, QPointF(0.0, 0.0))
            assert abs(after.x() - before.x()) < 18.0, (role_id, before.x(), after.x())
            assert abs(after.y() - before.y()) < 18.0, (role_id, before.y(), after.y())
            assert target.isVisible() and target.width() > 16.0 and target.height() > 2.0
            assert target.width() == pytest.approx(before_size[0], rel=0.08)
            assert target.height() == pytest.approx(before_size[1], rel=0.08)
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_volume_opposite_axis_reflow_updates_live_edit_proxy(qt_app) -> None:
    """The volume Edit proxy follows REAL CUSTOM offsets and automatic side flips.

    The accessory slider fills its parent and cannot be repositioned by writing
    slider.x/y: its anchor binding restores both to zero. Exercise the supported
    normalized volume offsets and display-side selection instead. The source
    retains the exact painted target and the same Edit delegate throughout.
    """
    # A native event/render-loop stall must never leave Foundry waiting forever.
    # Test-only watchdog: if a Qt call blocks, emit its Python stack and exit
    # this isolated pytest process. It is not application/runtime instrumentation.
    import faulthandler
    from PySide6.QtCore import QPoint, QRect
    from rendering.custom_layout_session import (
        CustomLayoutKey, CustomLayoutSession, CustomLayoutSessionItem,
    )
    from rendering.quick.custom_layout_overlay import RetainedCustomLayoutOverlay
    from rendering.quick.widgets.host import OrdinaryWidgetPresentationHost
    from PySide6.QtQuick import QQuickWindow

    def live_item(parent: QQuickItem, name: str) -> QQuickItem | None:
        # Repeater delegates belong to the *visual* QQuickItem scene. QObject
        # findChild() can miss a live delegate whose QObject parent is its
        # QML creation context rather than its visual parent.
        pending = [parent]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        return None

    screen = qt_app.primaryScreen()
    assert screen is not None
    # Use the already-accepted Reddit scene fixture: a plain QQuickWindow and
    # real family host, without the production display controller's background,
    # render scheduling, or runtime side effects. The previous hidden
    # QuickDisplayWindow did not instantiate the Edit repeater, while exposing
    # that full controller scene had stalled the test runner.
    window = QQuickWindow()
    window.setGeometry(0, 0, 1600, 900)
    factory = QuickSceneFactory()
    context, scene_root = factory.create_display_root(
        owner=window, screen_index=0, runtime_generation=2197,
    )
    scene_root.setParent(window.contentItem())
    scene_root.setParentItem(window.contentItem())
    scene_root.setWidth(1600.0)
    scene_root.setHeight(900.0)
    host_item = scene_root.findChild(QQuickItem, "ordinaryWidgetHost")
    shadow_host = scene_root.findChild(QQuickItem, "ordinaryWidgetShadowHost")
    assert host_item is not None and shadow_host is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item, shadow_host_item=shadow_host,
        context=context, create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
        create_shadow_item=factory.create_overlay_card_shadow,
    )
    runtime = _FakeMediaRuntime()
    volume_runtime = _FakeMediaVolumeRuntime()
    model, _, _ = _model(factory.media_artwork_provider, runtime, volume_runtime)
    overlay = None
    faulthandler.dump_traceback_later(20.0, repeat=False, exit=True)
    try:
        presentation = RetainedMediaPresentation(
            host=host, model=model,
            geometry=OverlayWidgetGeometry(40.0, 50.0, 650.0, 300.0),
        )
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        widget = presentation.item
        track = widget.findChild(QQuickItem, "mediaAppVolumeTrack")
        slider = widget.findChild(QQuickItem, "mediaAppVolumeSlider")
        assert track is not None and slider is not None
        assert model.appVolumeAvailable and track.isVisible()
        descriptor = get_widget_runtime_descriptor("media")
        assert descriptor is not None
        session = CustomLayoutSession()
        rect = QRect(40, 50, 650, 300)
        session.add_item(CustomLayoutSessionItem(
            source_key=CustomLayoutKey("media", "display:media-axes"),
            model_identity="media", baseline_global_rect=rect,
            current_global_rect=rect, baseline_size_payload={},
            current_size_payload={}, baseline_enabled=True,
            current_enabled=True, custom_child_roles=descriptor.custom_child_roles,
        ))
        edit_root = scene_root.findChild(QQuickItem, "customLayoutOverlay")
        assert edit_root is not None
        overlay = RetainedCustomLayoutOverlay(edit_root)
        overlay.bind_session(
            session, display_identity="display:media-axes",
            display_origin=QPoint(0, 0),
            presentation_item_resolver=lambda _item: widget,
        )
        # Match the already-working retained scene fixture: install the model
        # before native exposure, so the Repeater's first component completion
        # receives its role model. Do not instantiate a second Edit owner.
        window.show()
        qt_app.processEvents()
        assert overlay.model.selectItem(0)
        qt_app.processEvents()
        frame = live_item(edit_root, "customLayoutEditFrame-media")
        assert frame is not None, (
            "Media Edit delegate missing after plain QQuickWindow exposure; "
            f"model rows={overlay.model.rowCount()}, editActive={edit_root.property('editActive')}, "
            f"visual children={[item.objectName() for item in edit_root.childItems()]}"
        )
        assert frame.setProperty("childEditingLocked", False)
        qt_app.processEvents()
        role = live_item(edit_root, "customLayoutChildRole-media-volume_bar")
        assert role is not None and role.property("targetReady") is True

        def mapped():
            corners = [track.mapToItem(frame, x, y) for x, y in (
                (0.0, 0.0), (track.width(), 0.0),
                (0.0, track.height()), (track.width(), track.height()),
            )]
            x0 = min(p.x() for p in corners)
            y0 = min(p.y() for p in corners)
            return (x0, y0, max(p.x() for p in corners) - x0,
                    max(p.y() for p in corners) - y0)

        def assert_proxy():
            assert (role.x(), role.y(), role.width(), role.height()) == pytest.approx(
                mapped(), abs=0.04,
            )

        assert_proxy()
        initial_track = (track.x(), track.y())
        initial_signature = role.property("mappingDependency")
        # The REAL Media model owns normalized child offsets. The slider's
        # anchors.fill deliberately makes direct slider.setX/Y inert.
        assert model.set_custom_child_geometry({"volume_bar": {
            "x_offset": 0.015, "y_offset": -0.015,
        }})
        qt_app.processEvents()
        assert (track.x(), track.y()) != pytest.approx(initial_track, abs=0.01)
        assert role.property("mappingDependency") != initial_signature
        assert live_item(edit_root, "customLayoutChildRole-media-volume_bar") is role
        assert_proxy()

        # Side choice belongs exclusively to Media's existing display-centre
        # binding. Crossing the centre must relocate the volume accessory,
        # NOT mirror its image, replace its Edit delegate or persist a side flag.
        host_width = widget.parentItem().width()
        assert host_width > widget.width() * 2.0
        widget.setX(host_width - widget.width() - 20.0)
        qt_app.processEvents()
        assert widget.property("appVolumeOnLeft") is True
        assert live_item(edit_root, "customLayoutChildRole-media-volume_bar") is role
        assert_proxy()
        widget.setX(20.0)
        qt_app.processEvents()
        assert widget.property("appVolumeOnLeft") is False
        assert live_item(edit_root, "customLayoutChildRole-media-volume_bar") is role
        assert_proxy()

        assert model.set_custom_child_geometry({"volume_bar": {
            "x_offset": 0.0, "y_offset": 0.0,
        }})
        qt_app.processEvents()
        assert (track.x(), track.y()) == pytest.approx(initial_track, abs=0.04)
        assert_proxy()
        assert live_item(edit_root, "customLayoutChildRole-media-volume_bar") is role
        overlay.clear_session()
        qt_app.processEvents()
        assert track.isVisible()
    finally:
        if overlay is not None:
            overlay.clear_session()
        window.hide()
        host.retire_all()
        scene_root.setParentItem(None)
        scene_root.setParent(None)
        scene_root.deleteLater()
        context.deleteLater()
        factory.deleteLater()
        window.deleteLater()
        qt_app.processEvents()
        faulthandler.cancel_dump_traceback_later()


@pytest.mark.qt
@pytest.mark.parametrize("flipped", (False, True), ids=("ordinary", "flipped"))
@pytest.mark.parametrize("reset_before_flip", (False, True), ids=("direct", "reset-flip-reprojection"))
def test_media_child_axis_edits_keep_live_band_flow_at_compact_y(
    qt_app, flipped: bool, reset_before_flip: bool,
) -> None:
    """Real paint regression for flipped/customized Y-only shrink.

    In the old QML, any nonzero child X/Y offset disabled Y inheritance from
    its Column band. A clean-model compact test passed while the actual saved
    child geometry left transport and seek below the clipped card. Model
    rehydration here is not a substitute for a separate full owner Save test.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=141, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 600.0, 310.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        seek_band = item.findChild(QQuickItem, "mediaProgressBand")
        transport = item.findChild(QQuickItem, "mediaControlsRow")
        transport_band = item.findChild(QQuickItem, "mediaControlsBandSlot")
        artwork = item.findChild(QQuickItem, "mediaArtworkFrame")
        title = item.findChild(QQuickItem, "mediaTitle")
        metadata = item.findChild(QQuickItem, "mediaMetadata")
        assert all(v is not None for v in (
            seek, seek_band, transport, transport_band, artwork, title, metadata,
        ))
        retained_ids = tuple(id(v) for v in (seek, transport, artwork, title))
        right_header = {"header": {"alignment": "right"}} if flipped else {}
        if reset_before_flip:
            # Reset child customization, then commit the header-flip carrier
            # before the next Edit session uses the live compacted parent.
            model.set_custom_child_geometry({})
            qt_app.processEvents()
            model.set_custom_child_geometry(right_header)
            qt_app.processEvents()
        # Preserve nonzero independent X and Y edits across subsequent parent
        # reflow. Keep the projected child values within physical card bounds.
        saved_children = {
            **right_header,
            "seek_bar": {
                "x_offset": -0.008 if flipped else 0.008,
                "y_offset": -0.005,
            },
            "transport_controls": {
                "x_offset": 0.003,
                "y_offset": -0.005,
                "width_scale": 0.985,
            },
        }
        assert model.set_custom_child_geometry(saved_children)
        qt_app.processEvents()
        def relative_y(child, band):
            return child.mapToItem(band, QPointF(0.0, 0.0)).y()
        baseline_relative = (relative_y(seek, seek_band),
                             relative_y(transport, transport_band))
        card = item.findChild(QQuickItem, "overlayWidgetCard")
        assert card is not None
        # The shared OverlayWidget uniformly scales AND centres its authored
        # canvas when only the outer height shrinks.  Absolute scene X is not a
        # valid right-rail invariant: the visible card itself moves inward.  Test
        # the actual painted relationship to that card instead.
        def right_rail_inset():
            card_right = card.mapToItem(item, QPointF(card.width(), 0.0)).x()
            metadata_right = metadata.mapToItem(
                item, QPointF(metadata.width(), 0.0)
            ).x()
            scale = float(item.property("presentationScale"))
            assert scale > 0.0
            return (card_right - metadata_right) / scale
        initial_right_inset = right_rail_inset()
        # The user-visible symptom was clipping of essential rows, not merely
        # the model's logical visibility. Preserve paint relative to the *card*,
        # which may be narrower than the full root because volume owns its own
        # independent accessory lane.
        def card_y_bounds():
            top = card.mapToItem(item, QPointF(0.0, 0.0)).y()
            bottom = card.mapToItem(item, QPointF(card.width(), card.height())).y()
            return top, bottom
        for height in (310.0, 287.0, 240.0, 220.0, 287.0, 310.0):
            presentation.set_geometry(OverlayWidgetGeometry(25.0, 30.0, 600.0, height))
            qt_app.processEvents()
            assert model.progressAvailable and model.controlsBandAvailable
            assert tuple(id(v) for v in (seek, transport, artwork, title)) == retained_ids
            if flipped:
                # A compacted right-aligned title may shrink, not move inward
                # from the right lane. The old Item.Left origin broke this.
                inset = right_rail_inset()
                assert inset == pytest.approx(initial_right_inset, abs=1.2), (
                    height, inset, initial_right_inset,
                )
            assert (relative_y(seek, seek_band), relative_y(transport, transport_band)) == pytest.approx(
                baseline_relative, abs=0.6,
            ), (flipped, reset_before_flip, height)
            card_top, card_bottom = card_y_bounds()
            for child in (seek, transport, artwork, title):
                top = child.mapToItem(item, QPointF(0.0, 0.0))
                bottom = child.mapToItem(item, QPointF(child.width(), child.height()))
                assert child.isVisible() and child.width() > 1.0 and child.height() > 1.0
                assert top.y() >= card_top - 0.6, (
                    child.objectName(), height, top.y(), card_top,
                )
                assert bottom.y() <= card_bottom + 0.6, (
                    child.objectName(), height, bottom.y(), card_bottom,
                )
        # Re-project the same saved semantic/child carrier through the existing
        # model. This is NOT an owner Save, a new model or a fresh Edit session:
        # the dedicated owner-generation suite owns those lifecycle contracts.
        model.set_custom_child_geometry({})
        model.set_custom_child_geometry(saved_children)
        presentation.set_geometry(OverlayWidgetGeometry(25.0, 30.0, 600.0, 220.0))
        qt_app.processEvents()
        for child in (seek, transport):
            bottom = child.mapToItem(item, QPointF(child.width(), child.height()))
            assert child.isVisible() and bottom.y() <= item.height() + 0.6
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_compact_media_essential_rows_survive_flip_and_transient_capability_loss(qt_app) -> None:
    """Both orientations keep actual lower painted bounds during pure Y resize.

    Provider capability/duration gaps must disable actions, not remove the seek
    or transport bands and cause a new geometry layout. Check retained mapping
    inside the card, not merely the QML visible flags. No new scene per flip.
    """
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0, runtime_generation=139, screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeMediaRuntime()
    model, _, provider = _model(factory.media_artwork_provider, runtime)
    try:
        presentation = RetainedMediaPresentation(
            host=controller.ordinary_widget_host, model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 600.0, 310.0),
        )
        item = presentation.item
        presentation.activate(object())
        runtime.publish(_snapshot(1, image=_image()))
        qt_app.processEvents()
        seek = item.findChild(QQuickItem, "mediaProgressTrack")
        controls = item.findChild(QQuickItem, "mediaControlsRow")
        art = item.findChild(QQuickItem, "mediaArtworkFrame")
        title = item.findChild(QQuickItem, "mediaTitle")
        assert all(v is not None for v in (seek, controls, art, title))
        before_ids = tuple(id(v) for v in (seek, controls, art, title))

        def inside_card(child):
            top = child.mapToItem(item, QPointF(0.0, 0.0))
            bottom = child.mapToItem(item, QPointF(child.width(), child.height()))
            # Content boundary includes the card's usual inset; assert the
            # selected essential role actually has positive visible area.
            assert child.isVisible() and child.width() > 1 and child.height() > 1
            assert top.y() >= -0.5, (child.objectName(), top.y())
            assert bottom.y() <= item.height() + 0.5, (
                child.objectName(), bottom.y(), item.height(),
            )

        next_revision = 1
        for flipped in (False, True):
            header = {"header": {"alignment": "right"}} if flipped else {}
            model.set_custom_child_geometry(header)
            for height in (310.0, 287.0, 240.0, 220.0):
                presentation.set_geometry(OverlayWidgetGeometry(25.0, 30.0, 600.0, height))
                qt_app.processEvents()
                assert model.controlsAvailable and model.progressAvailable
                for child in (seek, controls, art, title):
                    inside_card(child)
                # A temporary snapshot with metadata/artwork intact but no
                # transport capabilities and no duration must not remove rows.
                next_revision += 1
                runtime.publish(_snapshot(
                    next_revision, image=None,
                    info=_info(can_play_pause=False, can_previous=False,
                               can_next=False, can_seek=False, duration_ms=0),
                ))
                qt_app.processEvents()
                assert model.hasTrack and not model.canSeek
                assert model.controlsAvailable and model.progressAvailable
                for child in (seek, controls, art, title):
                    inside_card(child)
                assert tuple(id(v) for v in (seek, controls, art, title)) == before_ids
                next_revision += 1
                runtime.publish(_snapshot(
                    next_revision, image=None,
                ))
                qt_app.processEvents()
        assert runtime.refresh_calls == [] and provider.image_count == 1
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()
