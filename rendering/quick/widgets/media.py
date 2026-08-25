"""Stable retained Media-core presentation model and artwork projection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QColor, QImage

from core.media.provider_registry import (
    get_media_provider_header_name,
    preserve_provider_setting,
)
from core.settings.shadow_direction import resolve_signed_offset
from rendering.quick.media_artwork import MediaArtworkImageProvider

if TYPE_CHECKING:
    from widgets.media_runtime import MediaRuntimeSnapshot

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)


_IMAGE_ROOT = Path(__file__).resolve().parents[3] / "images"
_PROVIDER_LOGOS = {
    "spotify": "Spotify_Primary_Logo_RGB_Black.png",
    "spotify_browser": "Spotify_Primary_Logo_RGB_Black.png",
    "musicbee": "icons8-musicbee-96.png",
}


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default if value is None else bool(value)


def _rgba(
    value: object, default: tuple[int, int, int, int]
) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(*(max(0, min(255, int(channel))) for channel in channels))
        except (TypeError, ValueError):
            color = QColor(*default)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(*default)
    return color.red(), color.green(), color.blue(), color.alpha()


def _with_alpha(rgba: tuple[int, int, int, int], scale: float) -> QColor:
    color = QColor(*rgba)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * scale)))))
    return color


def _file_source(path: Path) -> str:
    return path.resolve().as_uri() if path.is_file() else ""


@dataclass(frozen=True)
class MediaPresentationConfig:
    widget_id: str = "media"
    provider: str = "spotify"
    font_family: str = "Inter"
    font_size: int = 17
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    show_header_frame: bool = True
    artwork_size: int = 250
    rounded_artwork_border: bool = True
    show_controls: bool = True
    playback_progress_enabled: bool = False

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        widget_id: str = "media",
    ) -> "MediaPresentationConfig":
        return cls(
            widget_id=str(widget_id or "media"),
            provider=preserve_provider_setting(values.get("provider", "spotify")),
            font_family=str(values.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(values.get("font_size"), 17, 8, 256),
            text_color=_rgba(values.get("color"), (255, 255, 255, 230)),
            show_background=_as_bool(values.get("show_background"), True),
            background_color=_rgba(values.get("bg_color"), (35, 35, 35, 255)),
            background_opacity=_bounded_float(values.get("bg_opacity"), 0.3, 0.0, 1.0),
            border_color=_rgba(values.get("border_color"), (255, 255, 255, 255)),
            border_opacity=_bounded_float(values.get("border_opacity"), 1.0, 0.0, 1.0),
            show_header_frame=_as_bool(values.get("show_header_frame"), True),
            artwork_size=_bounded_int(values.get("artwork_size"), 250, 48, 512),
            rounded_artwork_border=_as_bool(values.get("rounded_artwork_border"), True),
            show_controls=_as_bool(values.get("show_controls"), True),
            playback_progress_enabled=_as_bool(
                values.get("playback_progress_enabled"), False
            ),
        )

    @classmethod
    def from_widgets_mapping(
        cls, widgets: Mapping[str, object]
    ) -> "MediaPresentationConfig":
        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {}).get("media", {})
        values = widgets.get("media", {})
        merged = dict(defaults) if isinstance(defaults, Mapping) else {}
        if isinstance(values, Mapping):
            merged.update(values)
        return cls.from_mapping(merged)


@dataclass(frozen=True)
class MediaPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: MediaPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "MediaPresentationStyle":
        direction = shadow_values.get("direction", "SE")
        frame_extra = _bounded_float(shadow_values.get("frame_extra_offset"), 0, 0, 40)
        text_extra = _bounded_float(shadow_values.get("text_extra_offset"), 0, 0, 40)
        card_offset = resolve_signed_offset(
            direction,
            ORDINARY_CARD_SHADOW_BASE[0] + frame_extra,
            ORDINARY_CARD_SHADOW_BASE[1] + frame_extra,
        )
        text_offset = resolve_signed_offset(
            direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + text_extra,
            ORDINARY_TEXT_SHADOW_BASE[1] + text_extra,
        )
        shadow_rgba = _rgba(shadow_values.get("color"), (0, 0, 0, 255))
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(
                    config.background_color, config.background_opacity
                ),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=18.0,
                padding=20.0,
                shadow_enabled=(
                    config.show_background
                    and _as_bool(shadow_values.get("enabled"), True)
                ),
                shadow_color=_with_alpha(
                    shadow_rgba,
                    _bounded_float(shadow_values.get("frame_opacity"), 0.77, 0, 1),
                ),
                shadow_blur=_bounded_float(
                    shadow_values.get("blur_radius"), 18, 0, 128
                ),
                shadow_offset_x=float(card_offset[0]),
                shadow_offset_y=float(card_offset[1]),
            ),
            text_shadow_enabled=_as_bool(shadow_values.get("text_enabled"), True),
            text_shadow_color=_with_alpha(
                shadow_rgba,
                _bounded_float(shadow_values.get("text_opacity"), 0.33, 0, 1),
            ),
            text_shadow_offset_x=float(text_offset[0]),
            text_shadow_offset_y=float(text_offset[1]),
        )


@dataclass(frozen=True)
class MediaPresentationSnapshot:
    config: MediaPresentationConfig
    style: MediaPresentationStyle
    revision: int = 0
    provider: str = "spotify"
    has_track: bool = False
    title: str = "No media playing"
    artist: str = ""
    album: str = ""
    playback_state: str = "unknown"
    can_play_pause: bool = False
    can_previous: bool = False
    can_next: bool = False
    position_ms: int = 0
    duration_ms: int = 0
    artwork_source: str = ""


class MediaPresentationModel(QObject):
    """Stable coherent snapshot consumer for one retained Media card."""

    stateChanged = Signal()
    volumeTargetChanged = Signal(str, str)

    def __init__(
        self,
        config: MediaPresentationConfig,
        style: MediaPresentationStyle,
        artwork_provider: MediaArtworkImageProvider,
        runtime_service: Any | None = None,
        *,
        runtime_generation: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime_generation = runtime_generation
        self._thread_manager = None
        self._runtime_service = runtime_service
        self._artwork_provider = artwork_provider
        self._artwork_identity = ""
        self._snapshot = MediaPresentationSnapshot(
            config=config,
            style=style,
            provider=config.provider,
        )
        self._active = False
        self._retired = False

    def set_runtime_service(self, service: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot inject a retired Media presentation model")
        if self._active and service is not self._runtime_service:
            raise RuntimeError("cannot replace the active Media runtime service")
        self._runtime_service = service

    @property
    def config(self) -> MediaPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> MediaPresentationStyle:
        return self._snapshot.style

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def activate(self, thread_manager: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot activate a retired Media presentation model")
        if self._active:
            return
        service = self._runtime_service
        if service is None:
            raise RuntimeError("Media runtime service is not configured")
        self._thread_manager = thread_manager
        service.set_thread_manager(thread_manager)
        service.attach_consumer(self)
        self._active = True
        if not service.start():
            self._active = False
            service.detach_consumer(self)
            raise RuntimeError("Media runtime service failed to start")

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        service = self._runtime_service
        if service is not None:
            service.stop()
            service.detach_consumer(self)
        self._release_artwork()

    def apply_config(self, config: MediaPresentationConfig) -> bool:
        if config == self.config:
            return False
        provider_changed = config.provider != self.config.provider
        if provider_changed:
            self._release_artwork()
            self._replace_snapshot(
                replace(
                    self._snapshot,
                    config=config,
                    provider=config.provider,
                    has_track=False,
                    title="No media playing",
                    artist="",
                    album="",
                    playback_state="unknown",
                    can_play_pause=False,
                    can_previous=False,
                    can_next=False,
                    position_ms=0,
                    duration_ms=0,
                    artwork_source="",
                )
            )
        else:
            self._replace_snapshot(replace(self._snapshot, config=config))
        if provider_changed and self._runtime_service is not None:
            self._runtime_service.set_provider_runtime(
                config.provider, source="settings"
            )
        return True

    def apply_style(self, style: MediaPresentationStyle) -> bool:
        if style == self.style:
            return False
        self._replace_snapshot(replace(self._snapshot, style=style))
        return True

    def request_refresh(self) -> bool:
        return bool(
            self.is_active
            and self._runtime_service is not None
            and self._runtime_service.refresh(bust_cache=True)
        )

    def is_media_consumer_alive(self) -> bool:
        return self.is_active

    def on_media_runtime_snapshot(self, snapshot: MediaRuntimeSnapshot) -> None:
        if not self.is_active:
            return
        try:
            revision = int(snapshot.revision)
            info = snapshot.info
            provider = str(snapshot.provider)
        except (AttributeError, TypeError, ValueError):
            return
        if revision <= self._snapshot.revision:
            return
        artwork_source = self._project_artwork(snapshot)
        if info is None:
            next_snapshot = replace(
                self._snapshot,
                revision=revision,
                provider=provider,
                has_track=False,
                title="No media playing",
                artist="",
                album="",
                playback_state="unknown",
                can_play_pause=False,
                can_previous=False,
                can_next=False,
                position_ms=0,
                duration_ms=0,
                artwork_source=artwork_source,
            )
        else:
            state = str(getattr(info.state, "value", info.state))
            position = max(0, int(info.position_ms or 0))
            duration = max(0, int(info.duration_ms or 0))
            next_snapshot = replace(
                self._snapshot,
                revision=revision,
                provider=provider,
                has_track=True,
                title=str(info.title or "Unknown title"),
                artist=str(info.artist or info.album_artist or "Unknown artist"),
                album=str(info.album or ""),
                playback_state=state,
                can_play_pause=bool(info.can_play_pause),
                can_previous=bool(info.can_previous),
                can_next=bool(info.can_next),
                position_ms=min(position, duration) if duration else position,
                duration_ms=duration,
                artwork_source=artwork_source,
            )
        self._replace_snapshot(next_snapshot)

    def on_media_runtime_provider_changed(
        self,
        old_provider: str,
        provider: str,
        *,
        source: str,
        persist: bool,
    ) -> None:
        del old_provider, source, persist
        if not self.is_active:
            return
        self._release_artwork()
        self._replace_snapshot(
            replace(
                self._snapshot,
                provider=str(provider or self.config.provider),
                has_track=False,
                title="No media playing",
                artist="",
                album="",
                playback_state="unknown",
                can_play_pause=False,
                can_previous=False,
                can_next=False,
                position_ms=0,
                duration_ms=0,
                artwork_source="",
            )
        )

    def on_media_runtime_volume_target(self, provider: str, source_id: str) -> None:
        if self.is_active:
            self.volumeTargetChanged.emit(str(provider), str(source_id))

    def _project_artwork(self, snapshot: MediaRuntimeSnapshot) -> str:
        key = snapshot.artwork.key
        identity = self._artwork_provider.identity_for_key(key)
        if not identity:
            self._release_artwork()
            return ""
        if identity == self._artwork_identity:
            return self._snapshot.artwork_source
        image = snapshot.artwork.image
        if not isinstance(image, QImage) or image.isNull():
            self._release_artwork()
            return ""
        source = self._artwork_provider.publish(key, image)
        self._release_artwork()
        self._artwork_identity = identity if source else ""
        return source

    def _release_artwork(self) -> None:
        if self._artwork_identity:
            self._artwork_provider.release(self._artwork_identity)
            self._artwork_identity = ""

    def _replace_snapshot(self, snapshot: MediaPresentationSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self.stateChanged.emit()

    @Property(int, notify=stateChanged)
    def revision(self) -> int:
        return self._snapshot.revision

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return self._snapshot.title

    @Property(str, notify=stateChanged)
    def artist(self) -> str:
        return self._snapshot.artist

    @Property(str, notify=stateChanged)
    def album(self) -> str:
        return self._snapshot.album

    @Property(str, notify=stateChanged)
    def playbackState(self) -> str:
        return self._snapshot.playback_state

    @Property(str, notify=stateChanged)
    def providerName(self) -> str:
        return get_media_provider_header_name(self._snapshot.provider) or "MEDIA"

    @Property(str, notify=stateChanged)
    def providerLogoSource(self) -> str:
        filename = _PROVIDER_LOGOS.get(self._snapshot.provider.lower(), "")
        return _file_source(_IMAGE_ROOT / filename) if filename else ""

    @Property(str, notify=stateChanged)
    def artworkSource(self) -> str:
        return self._snapshot.artwork_source

    @Property(bool, notify=stateChanged)
    def hasArtwork(self) -> bool:
        return bool(self._snapshot.artwork_source)

    @Property(bool, notify=stateChanged)
    def hasTrack(self) -> bool:
        return self._snapshot.has_track

    @Property(bool, notify=stateChanged)
    def canPlayPause(self) -> bool:
        return self._snapshot.can_play_pause

    @Property(bool, notify=stateChanged)
    def canPrevious(self) -> bool:
        return self._snapshot.can_previous

    @Property(bool, notify=stateChanged)
    def canNext(self) -> bool:
        return self._snapshot.can_next

    @Property(float, notify=stateChanged)
    def progressFraction(self) -> float:
        duration = self._snapshot.duration_ms
        return 0.0 if duration <= 0 else self._snapshot.position_ms / duration

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(float, notify=stateChanged)
    def artworkSize(self) -> float:
        return float(self.config.artwork_size)

    @Property(bool, notify=stateChanged)
    def roundedArtwork(self) -> bool:
        return self.config.rounded_artwork_border

    @Property(QColor, notify=stateChanged)
    def artworkBorderColor(self) -> QColor:
        return QColor(self.style.card_style.border_color)

    @Property(float, notify=stateChanged)
    def artworkBorderWidth(self) -> float:
        border = self.style.card_style
        if border.border_width <= 0.0 or border.border_color.alpha() <= 0:
            return 0.0
        return max(1.0, border.border_width + 2.0)

    @Property(bool, notify=stateChanged)
    def showHeaderFrame(self) -> bool:
        return self.config.show_header_frame

    @Property(bool, notify=stateChanged)
    def controlsAvailable(self) -> bool:
        return self.config.show_controls and (
            self.canPlayPause or self.canPrevious or self.canNext
        )

    @Property(bool, notify=stateChanged)
    def progressAvailable(self) -> bool:
        return self.config.playback_progress_enabled and self._snapshot.duration_ms > 0

    @Property(bool, notify=stateChanged)
    def textShadowEnabled(self) -> bool:
        return self.style.text_shadow_enabled

    @Property(QColor, notify=stateChanged)
    def textShadowColor(self) -> QColor:
        return QColor(self.style.text_shadow_color)

    @Property(float, notify=stateChanged)
    def textShadowOffsetX(self) -> float:
        return self.style.text_shadow_offset_x

    @Property(float, notify=stateChanged)
    def textShadowOffsetY(self) -> float:
        return self.style.text_shadow_offset_y


class RetainedMediaPresentation:
    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: MediaPresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 1.0,
    ) -> None:
        self._host = host
        self._model = model
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "media",
            initial_properties={"mediaModel": model},
            object_name=model.config.widget_id,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        refresh = getattr(self._retained.item, "refreshRequested", None)
        if refresh is not None and hasattr(refresh, "connect"):
            refresh.connect(model.request_refresh)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> MediaPresentationModel:
        return self._model

    def activate(self, thread_manager: Any) -> None:
        self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def apply_config(
        self,
        config: MediaPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        self._model.apply_config(config)
        style = MediaPresentationStyle.project(
            config, shadow_values, border_width=border_width
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    def retire(self) -> bool:
        return self._host.retire_widget(self._retained)


__all__ = [
    "MediaPresentationConfig",
    "MediaPresentationModel",
    "MediaPresentationSnapshot",
    "MediaPresentationStyle",
    "RetainedMediaPresentation",
]
