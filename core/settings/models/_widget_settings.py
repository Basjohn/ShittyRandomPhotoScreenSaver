"""Typed models for the current persisted Widget/Accessibility settings schema.

These models deliberately project defaults from the canonical settings authority.
Retired parser aliases such as ``text_color``/``background_color`` and Weather's
old animated-icon keys are not persisted or re-emitted here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, TYPE_CHECKING

from core.media.provider_registry import preserve_provider_setting
from core.settings.default_contract import require_canonical_default
from core.settings.models._enums import WidgetPosition, parse_widget_position
from core.settings.normalization import normalize_widget_position
from core.settings.widget_capacity_policy import clamp_list_capacity

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager


def _default(prefix: str, key: str) -> Any:
    return require_canonical_default(f"{prefix}.{key}")


def _mapping_value(data: Mapping[str, Any], prefix: str, key: str) -> Any:
    dotted = f"{prefix}.{key}"
    if dotted in data:
        return data[dotted]
    if key in data:
        return data[key]
    return _default(prefix, key)


@dataclass
class WeatherWidgetSettings:
    """Weather widget settings using only the current canonical keys."""

    enabled: bool = bool(_default("widgets.weather", "enabled"))
    monitor: Any = _default("widgets.weather", "monitor")
    position: WidgetPosition = parse_widget_position(_default("widgets.weather", "position"))
    location: str = str(_default("widgets.weather", "location"))
    font_family: str = str(_default("widgets.weather", "font_family"))
    font_size: int = int(_default("widgets.weather", "font_size"))
    color: list[int] = field(default_factory=lambda: _default("widgets.weather", "color"))
    show_background: bool = bool(_default("widgets.weather", "show_background"))
    bg_color: list[int] = field(default_factory=lambda: _default("widgets.weather", "bg_color"))
    bg_opacity: float = float(_default("widgets.weather", "bg_opacity"))
    border_color: list[int] = field(default_factory=lambda: _default("widgets.weather", "border_color"))
    border_opacity: float = float(_default("widgets.weather", "border_opacity"))
    show_forecast: bool = bool(_default("widgets.weather", "show_forecast"))
    show_details_row: bool = bool(_default("widgets.weather", "show_details_row"))
    show_condition_icon: bool = bool(_default("widgets.weather", "show_condition_icon"))
    icon_alignment: str = str(_default("widgets.weather", "icon_alignment"))
    icon_size: int = int(_default("widgets.weather", "icon_size"))
    detail_icon_size: int = int(_default("widgets.weather", "detail_icon_size"))
    margin: int = int(_default("widgets.weather", "margin"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "WeatherWidgetSettings":
        prefix = "widgets.weather"
        position = normalize_widget_position(
            settings.get(f"{prefix}.position"),
            parse_widget_position(_default(prefix, "position")),
        )
        return cls(
            enabled=bool(settings.get(f"{prefix}.enabled")),
            monitor=settings.get(f"{prefix}.monitor"),
            position=position,
            location=str(settings.get(f"{prefix}.location")),
            font_family=str(settings.get(f"{prefix}.font_family")),
            font_size=int(settings.get(f"{prefix}.font_size")),
            color=list(settings.get(f"{prefix}.color")),
            show_background=bool(settings.get(f"{prefix}.show_background")),
            bg_color=list(settings.get(f"{prefix}.bg_color")),
            bg_opacity=float(settings.get(f"{prefix}.bg_opacity")),
            border_color=list(settings.get(f"{prefix}.border_color")),
            border_opacity=float(settings.get(f"{prefix}.border_opacity")),
            show_forecast=bool(settings.get(f"{prefix}.show_forecast")),
            show_details_row=bool(settings.get(f"{prefix}.show_details_row")),
            show_condition_icon=bool(settings.get(f"{prefix}.show_condition_icon")),
            icon_alignment=str(settings.get(f"{prefix}.icon_alignment")),
            icon_size=int(settings.get(f"{prefix}.icon_size")),
            detail_icon_size=int(settings.get(f"{prefix}.detail_icon_size")),
            margin=int(settings.get(f"{prefix}.margin")),
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        prefix: str = "widgets.weather",
    ) -> "WeatherWidgetSettings":
        position = normalize_widget_position(
            _mapping_value(data, prefix, "position"),
            parse_widget_position(_default(prefix, "position")),
        )
        return cls(
            enabled=bool(_mapping_value(data, prefix, "enabled")),
            monitor=_mapping_value(data, prefix, "monitor"),
            position=position,
            location=str(_mapping_value(data, prefix, "location")),
            font_family=str(_mapping_value(data, prefix, "font_family")),
            font_size=int(_mapping_value(data, prefix, "font_size")),
            color=list(_mapping_value(data, prefix, "color")),
            show_background=bool(_mapping_value(data, prefix, "show_background")),
            bg_color=list(_mapping_value(data, prefix, "bg_color")),
            bg_opacity=float(_mapping_value(data, prefix, "bg_opacity")),
            border_color=list(_mapping_value(data, prefix, "border_color")),
            border_opacity=float(_mapping_value(data, prefix, "border_opacity")),
            show_forecast=bool(_mapping_value(data, prefix, "show_forecast")),
            show_details_row=bool(_mapping_value(data, prefix, "show_details_row")),
            show_condition_icon=bool(_mapping_value(data, prefix, "show_condition_icon")),
            icon_alignment=str(_mapping_value(data, prefix, "icon_alignment")),
            icon_size=int(_mapping_value(data, prefix, "icon_size")),
            detail_icon_size=int(_mapping_value(data, prefix, "detail_icon_size")),
            margin=int(_mapping_value(data, prefix, "margin")),
        )

    def to_dict(self, prefix: str = "widgets.weather") -> Dict[str, Any]:
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.location": self.location,
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": self.font_size,
            f"{prefix}.color": list(self.color),
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.bg_color": list(self.bg_color),
            f"{prefix}.bg_opacity": self.bg_opacity,
            f"{prefix}.border_color": list(self.border_color),
            f"{prefix}.border_opacity": self.border_opacity,
            f"{prefix}.show_forecast": self.show_forecast,
            f"{prefix}.show_details_row": self.show_details_row,
            f"{prefix}.show_condition_icon": self.show_condition_icon,
            f"{prefix}.icon_alignment": self.icon_alignment,
            f"{prefix}.icon_size": self.icon_size,
            f"{prefix}.detail_icon_size": self.detail_icon_size,
            f"{prefix}.margin": self.margin,
        }


@dataclass
class RedditWidgetSettings:
    """Reddit widget settings using only current canonical keys."""

    enabled: bool = bool(_default("widgets.reddit", "enabled"))
    monitor: Any = _default("widgets.reddit", "monitor")
    position: WidgetPosition = parse_widget_position(_default("widgets.reddit", "position"))
    provider: str = str(_default("widgets.reddit", "provider"))
    subreddit: str = str(_default("widgets.reddit", "subreddit"))
    limit: int = int(_default("widgets.reddit", "limit"))
    font_family: str = str(_default("widgets.reddit", "font_family"))
    font_size: int = int(_default("widgets.reddit", "font_size"))
    color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "color"))
    show_background: bool = bool(_default("widgets.reddit", "show_background"))
    bg_color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "bg_color"))
    bg_opacity: float = float(_default("widgets.reddit", "bg_opacity"))
    show_separators: bool = bool(_default("widgets.reddit", "show_separators"))
    show_refresh_spiral: bool = bool(_default("widgets.reddit", "show_refresh_spiral"))
    exit_on_click: bool = bool(_default("widgets.reddit", "exit_on_click"))
    margin: int = int(_default("widgets.reddit", "margin"))
    border_color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "border_color"))
    border_opacity: float = float(_default("widgets.reddit", "border_opacity"))
    header_fill_color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "header_fill_color"))
    header_border_color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "header_border_color"))
    header_text_color: list[int] = field(default_factory=lambda: _default("widgets.reddit", "header_text_color"))

    @classmethod
    def from_settings(
        cls,
        settings: "SettingsManager",
        prefix: str = "widgets.reddit",
    ) -> "RedditWidgetSettings":
        position = normalize_widget_position(
            settings.get(f"{prefix}.position"),
            parse_widget_position(_default(prefix, "position")),
        )
        limit_default = int(_default(prefix, "limit"))
        return cls(
            enabled=bool(settings.get(f"{prefix}.enabled")),
            monitor=settings.get(f"{prefix}.monitor"),
            position=position,
            provider=str(settings.get(f"{prefix}.provider")),
            subreddit=str(settings.get(f"{prefix}.subreddit")),
            limit=clamp_list_capacity(settings.get(f"{prefix}.limit"), default=limit_default),
            font_family=str(settings.get(f"{prefix}.font_family")),
            font_size=int(settings.get(f"{prefix}.font_size")),
            color=list(settings.get(f"{prefix}.color")),
            show_background=bool(settings.get(f"{prefix}.show_background")),
            bg_color=list(settings.get(f"{prefix}.bg_color")),
            bg_opacity=float(settings.get(f"{prefix}.bg_opacity")),
            show_separators=bool(settings.get(f"{prefix}.show_separators")),
            show_refresh_spiral=bool(settings.get(f"{prefix}.show_refresh_spiral")),
            exit_on_click=bool(settings.get(f"{prefix}.exit_on_click")),
            margin=int(settings.get(f"{prefix}.margin")),
            border_color=list(settings.get(f"{prefix}.border_color")),
            border_opacity=float(settings.get(f"{prefix}.border_opacity")),
            header_fill_color=list(settings.get(f"{prefix}.header_fill_color")),
            header_border_color=list(settings.get(f"{prefix}.header_border_color")),
            header_text_color=list(settings.get(f"{prefix}.header_text_color")),
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        prefix: str = "widgets.reddit",
    ) -> "RedditWidgetSettings":
        position = normalize_widget_position(
            _mapping_value(data, prefix, "position"),
            parse_widget_position(_default(prefix, "position")),
        )
        limit_default = int(_default(prefix, "limit"))
        return cls(
            enabled=bool(_mapping_value(data, prefix, "enabled")),
            monitor=_mapping_value(data, prefix, "monitor"),
            position=position,
            provider=str(_mapping_value(data, prefix, "provider")),
            subreddit=str(_mapping_value(data, prefix, "subreddit")),
            limit=clamp_list_capacity(_mapping_value(data, prefix, "limit"), default=limit_default),
            font_family=str(_mapping_value(data, prefix, "font_family")),
            font_size=int(_mapping_value(data, prefix, "font_size")),
            color=list(_mapping_value(data, prefix, "color")),
            show_background=bool(_mapping_value(data, prefix, "show_background")),
            bg_color=list(_mapping_value(data, prefix, "bg_color")),
            bg_opacity=float(_mapping_value(data, prefix, "bg_opacity")),
            show_separators=bool(_mapping_value(data, prefix, "show_separators")),
            show_refresh_spiral=bool(_mapping_value(data, prefix, "show_refresh_spiral")),
            exit_on_click=bool(_mapping_value(data, prefix, "exit_on_click")),
            margin=int(_mapping_value(data, prefix, "margin")),
            border_color=list(_mapping_value(data, prefix, "border_color")),
            border_opacity=float(_mapping_value(data, prefix, "border_opacity")),
            header_fill_color=list(_mapping_value(data, prefix, "header_fill_color")),
            header_border_color=list(_mapping_value(data, prefix, "header_border_color")),
            header_text_color=list(_mapping_value(data, prefix, "header_text_color")),
        )

    def to_dict(self, prefix: str = "widgets.reddit") -> Dict[str, Any]:
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.provider": self.provider,
            f"{prefix}.subreddit": self.subreddit,
            f"{prefix}.limit": self.limit,
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": self.font_size,
            f"{prefix}.color": list(self.color),
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.bg_color": list(self.bg_color),
            f"{prefix}.bg_opacity": self.bg_opacity,
            f"{prefix}.show_separators": self.show_separators,
            f"{prefix}.show_refresh_spiral": self.show_refresh_spiral,
            f"{prefix}.exit_on_click": self.exit_on_click,
            f"{prefix}.margin": self.margin,
            f"{prefix}.border_color": list(self.border_color),
            f"{prefix}.border_opacity": self.border_opacity,
            f"{prefix}.header_fill_color": list(self.header_fill_color),
            f"{prefix}.header_border_color": list(self.header_border_color),
            f"{prefix}.header_text_color": list(self.header_text_color),
        }


@dataclass
class MediaWidgetSettings:
    """Media widget settings using only the current canonical keys."""

    enabled: bool = bool(_default("widgets.media", "enabled"))
    monitor: Any = _default("widgets.media", "monitor")
    position: WidgetPosition = parse_widget_position(_default("widgets.media", "position"))
    font_family: str = str(_default("widgets.media", "font_family"))
    font_size: int = int(_default("widgets.media", "font_size"))
    color: list[int] = field(default_factory=lambda: _default("widgets.media", "color"))
    show_background: bool = bool(_default("widgets.media", "show_background"))
    bg_color: list[int] = field(default_factory=lambda: _default("widgets.media", "bg_color"))
    bg_opacity: float = float(_default("widgets.media", "bg_opacity"))
    show_controls: bool = bool(_default("widgets.media", "show_controls"))
    show_header_frame: bool = bool(_default("widgets.media", "show_header_frame"))
    show_album: bool = bool(_default("widgets.media", "show_album"))
    show_playback_state: bool = bool(_default("widgets.media", "show_playback_state"))
    artwork_size: int = int(_default("widgets.media", "artwork_size"))
    margin: int = int(_default("widgets.media", "margin"))
    border_color: list[int] = field(default_factory=lambda: _default("widgets.media", "border_color"))
    border_opacity: float = float(_default("widgets.media", "border_opacity"))
    header_fill_color: list[int] = field(default_factory=lambda: _default("widgets.media", "header_fill_color"))
    header_border_color: list[int] = field(default_factory=lambda: _default("widgets.media", "header_border_color"))
    header_text_color: list[int] = field(default_factory=lambda: _default("widgets.media", "header_text_color"))
    rounded_artwork_border: bool = bool(_default("widgets.media", "rounded_artwork_border"))
    provider: str = str(_default("widgets.media", "provider"))
    spotify_volume_enabled: bool = bool(_default("widgets.media", "spotify_volume_enabled"))
    spotify_volume_fill_color: list[int] = field(default_factory=lambda: _default("widgets.media", "spotify_volume_fill_color"))
    spotify_volume_border_color: list[int] = field(default_factory=lambda: _default("widgets.media", "spotify_volume_border_color"))
    spotify_volume_track_color: list[int] = field(default_factory=lambda: _default("widgets.media", "spotify_volume_track_color"))
    mute_button_enabled: bool = bool(_default("widgets.media", "mute_button_enabled"))
    playback_progress_enabled: bool = bool(_default("widgets.media", "playback_progress_enabled"))
    playback_progress_height: int = int(_default("widgets.media", "playback_progress_height"))
    playback_progress_track_color: list[int] = field(default_factory=lambda: _default("widgets.media", "playback_progress_track_color"))
    playback_progress_fill_color: list[int] = field(default_factory=lambda: _default("widgets.media", "playback_progress_fill_color"))
    playback_progress_shadow_enabled: bool = bool(_default("widgets.media", "playback_progress_shadow_enabled"))
    playback_progress_shadow_color: list[int] = field(default_factory=lambda: _default("widgets.media", "playback_progress_shadow_color"))
    playback_progress_glow_enabled: bool = bool(_default("widgets.media", "playback_progress_glow_enabled"))
    playback_progress_glow_color: list[int] = field(default_factory=lambda: _default("widgets.media", "playback_progress_glow_color"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "MediaWidgetSettings":
        prefix = "widgets.media"
        position = normalize_widget_position(
            settings.get(f"{prefix}.position"),
            parse_widget_position(_default(prefix, "position")),
        )
        return cls._from_values(
            lambda key: settings.get(f"{prefix}.{key}"),
            position=position,
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        prefix: str = "widgets.media",
    ) -> "MediaWidgetSettings":
        position = normalize_widget_position(
            _mapping_value(data, prefix, "position"),
            parse_widget_position(_default(prefix, "position")),
        )
        return cls._from_values(
            lambda key: _mapping_value(data, prefix, key),
            position=position,
        )

    @classmethod
    def _from_values(cls, get_value: Any, *, position: WidgetPosition) -> "MediaWidgetSettings":
        return cls(
            enabled=bool(get_value("enabled")),
            monitor=get_value("monitor"),
            position=position,
            font_family=str(get_value("font_family")),
            font_size=int(get_value("font_size")),
            color=list(get_value("color")),
            show_background=bool(get_value("show_background")),
            bg_color=list(get_value("bg_color")),
            bg_opacity=float(get_value("bg_opacity")),
            show_controls=bool(get_value("show_controls")),
            show_header_frame=bool(get_value("show_header_frame")),
            show_album=bool(get_value("show_album")),
            show_playback_state=bool(get_value("show_playback_state")),
            artwork_size=int(get_value("artwork_size")),
            margin=int(get_value("margin")),
            border_color=list(get_value("border_color")),
            border_opacity=float(get_value("border_opacity")),
            header_fill_color=list(get_value("header_fill_color")),
            header_border_color=list(get_value("header_border_color")),
            header_text_color=list(get_value("header_text_color")),
            rounded_artwork_border=bool(get_value("rounded_artwork_border")),
            provider=preserve_provider_setting(get_value("provider")),
            spotify_volume_enabled=bool(get_value("spotify_volume_enabled")),
            spotify_volume_fill_color=list(get_value("spotify_volume_fill_color")),
            spotify_volume_border_color=list(get_value("spotify_volume_border_color")),
            spotify_volume_track_color=list(get_value("spotify_volume_track_color")),
            mute_button_enabled=bool(get_value("mute_button_enabled")),
            playback_progress_enabled=bool(get_value("playback_progress_enabled")),
            playback_progress_height=int(get_value("playback_progress_height")),
            playback_progress_track_color=list(get_value("playback_progress_track_color")),
            playback_progress_fill_color=list(get_value("playback_progress_fill_color")),
            playback_progress_shadow_enabled=bool(get_value("playback_progress_shadow_enabled")),
            playback_progress_shadow_color=list(get_value("playback_progress_shadow_color")),
            playback_progress_glow_enabled=bool(get_value("playback_progress_glow_enabled")),
            playback_progress_glow_color=list(get_value("playback_progress_glow_color")),
        )

    def to_dict(self, prefix: str = "widgets.media") -> Dict[str, Any]:
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": self.font_size,
            f"{prefix}.color": list(self.color),
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.bg_color": list(self.bg_color),
            f"{prefix}.bg_opacity": self.bg_opacity,
            f"{prefix}.show_controls": self.show_controls,
            f"{prefix}.show_header_frame": self.show_header_frame,
            f"{prefix}.show_album": self.show_album,
            f"{prefix}.show_playback_state": self.show_playback_state,
            f"{prefix}.artwork_size": self.artwork_size,
            f"{prefix}.margin": self.margin,
            f"{prefix}.border_color": list(self.border_color),
            f"{prefix}.border_opacity": self.border_opacity,
            f"{prefix}.header_fill_color": list(self.header_fill_color),
            f"{prefix}.header_border_color": list(self.header_border_color),
            f"{prefix}.header_text_color": list(self.header_text_color),
            f"{prefix}.rounded_artwork_border": self.rounded_artwork_border,
            f"{prefix}.provider": self.provider,
            f"{prefix}.spotify_volume_enabled": self.spotify_volume_enabled,
            f"{prefix}.spotify_volume_fill_color": list(self.spotify_volume_fill_color),
            f"{prefix}.spotify_volume_border_color": list(self.spotify_volume_border_color),
            f"{prefix}.spotify_volume_track_color": list(self.spotify_volume_track_color),
            f"{prefix}.mute_button_enabled": self.mute_button_enabled,
            f"{prefix}.playback_progress_enabled": self.playback_progress_enabled,
            f"{prefix}.playback_progress_height": self.playback_progress_height,
            f"{prefix}.playback_progress_track_color": list(self.playback_progress_track_color),
            f"{prefix}.playback_progress_fill_color": list(self.playback_progress_fill_color),
            f"{prefix}.playback_progress_shadow_enabled": self.playback_progress_shadow_enabled,
            f"{prefix}.playback_progress_shadow_color": list(self.playback_progress_shadow_color),
            f"{prefix}.playback_progress_glow_enabled": self.playback_progress_glow_enabled,
            f"{prefix}.playback_progress_glow_color": list(self.playback_progress_glow_color),
        }


@dataclass
class AccessibilitySettings:
    """Accessibility settings projected from canonical defaults."""

    dimming_enabled: bool = bool(require_canonical_default("accessibility.dimming.enabled"))
    dimming_opacity: int = int(require_canonical_default("accessibility.dimming.opacity"))
    pixel_shift_enabled: bool = bool(require_canonical_default("accessibility.pixel_shift.enabled"))
    pixel_shift_rate: int = int(require_canonical_default("accessibility.pixel_shift.rate"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "AccessibilitySettings":
        return cls(
            dimming_enabled=bool(settings.get("accessibility.dimming.enabled")),
            dimming_opacity=int(settings.get("accessibility.dimming.opacity")),
            pixel_shift_enabled=bool(settings.get("accessibility.pixel_shift.enabled")),
            pixel_shift_rate=int(settings.get("accessibility.pixel_shift.rate")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accessibility.dimming.enabled": self.dimming_enabled,
            "accessibility.dimming.opacity": self.dimming_opacity,
            "accessibility.pixel_shift.enabled": self.pixel_shift_enabled,
            "accessibility.pixel_shift.rate": self.pixel_shift_rate,
        }
