"""Widget settings models: Weather, Reddit, Media, Accessibility."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, TYPE_CHECKING

from core.settings.models._enums import WidgetPosition, coerce_widget_position
from core.settings.widget_capacity_policy import clamp_list_capacity

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager



@dataclass
class WeatherWidgetSettings:
    """Weather widget settings."""
    enabled: bool = False
    monitor: str = "ALL"
    position: WidgetPosition = WidgetPosition.BOTTOM_LEFT
    location: str = ""
    font_family: str = "Inter"
    font_size: int = 24
    text_color: str = "#FFFFFF"
    show_background: bool = True
    background_color: str = "#000000"
    background_opacity: float = 0.5
    show_forecast: bool = False
    show_details_row: bool = False
    animated_icon_alignment: str = "NONE"
    animated_icon_enabled: bool = True
    desaturate_animated_icon: bool = False
    shared_animation_driver: bool = True
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "WeatherWidgetSettings":
        """Load weather widget settings from SettingsManager."""
        position = coerce_widget_position(
            settings.get("widgets.weather.position", "bottom_left"),
            WidgetPosition.BOTTOM_LEFT,
        )
        
        return cls(
            enabled=settings.get("widgets.weather.enabled", False),
            monitor=settings.get("widgets.weather.monitor", "ALL"),
            position=position,
            location=settings.get("widgets.weather.location", ""),
            font_family=settings.get("widgets.weather.font_family", "Inter"),
            font_size=settings.get("widgets.weather.font_size", 24),
            text_color=settings.get("widgets.weather.text_color", "#FFFFFF"),
            show_background=settings.get("widgets.weather.show_background", True),
            background_color=settings.get("widgets.weather.background_color", "#000000"),
            background_opacity=settings.get("widgets.weather.background_opacity", 0.5),
            show_forecast=settings.get("widgets.weather.show_forecast", False),
            show_details_row=settings.get("widgets.weather.show_details_row", False),
            animated_icon_alignment=settings.get("widgets.weather.animated_icon_alignment", "NONE"),
            animated_icon_enabled=settings.get("widgets.weather.animated_icon_enabled", True),
            desaturate_animated_icon=settings.get("widgets.weather.desaturate_animated_icon", False),
            shared_animation_driver=settings.get("widgets.weather.shared_animation_driver", True),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], prefix: str = "widgets.weather") -> "WeatherWidgetSettings":
        """Load weather widget settings from a plain mapping (e.g., widgets dict)."""
        def _get(key: str, default: Any) -> Any:
            dotted = f"{prefix}.{key}"
            if dotted in data:
                return data.get(dotted, default)
            return data.get(key, default)

        position = coerce_widget_position(_get("position", "bottom_left"), WidgetPosition.BOTTOM_LEFT)

        return cls(
            enabled=_get("enabled", False),
            monitor=_get("monitor", "ALL"),
            position=position,
            location=_get("location", ""),
            font_family=_get("font_family", "Inter"),
            font_size=int(_get("font_size", 24)),
            text_color=_get("text_color", "#FFFFFF"),
            show_background=_get("show_background", True),
            background_color=_get("background_color", "#000000"),
            background_opacity=float(_get("background_opacity", 0.5)),
            show_forecast=_get("show_forecast", False),
            show_details_row=_get("show_details_row", False),
            animated_icon_alignment=_get("animated_icon_alignment", "NONE"),
            animated_icon_enabled=_get("animated_icon_enabled", True),
            desaturate_animated_icon=_get("desaturate_animated_icon", False),
            shared_animation_driver=_get("shared_animation_driver", True),
        )

    def to_dict(self, prefix: str = "widgets.weather") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.location": self.location,
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": int(self.font_size),
            f"{prefix}.text_color": self.text_color,
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.background_color": self.background_color,
            f"{prefix}.background_opacity": float(self.background_opacity),
            f"{prefix}.show_forecast": self.show_forecast,
            f"{prefix}.show_details_row": self.show_details_row,
            f"{prefix}.animated_icon_alignment": self.animated_icon_alignment,
            f"{prefix}.animated_icon_enabled": self.animated_icon_enabled,
            f"{prefix}.desaturate_animated_icon": self.desaturate_animated_icon,
            f"{prefix}.shared_animation_driver": self.shared_animation_driver,
        }


@dataclass
class RedditWidgetSettings:
    """Reddit widget settings."""
    enabled: bool = False
    monitor: str = "ALL"
    position: WidgetPosition = WidgetPosition.TOP_RIGHT
    provider: str = "pullpush"
    subreddit: str = "technology"
    limit: int = 10
    font_family: str = "Inter"
    font_size: int = 18
    text_color: str = "#FFFFFF"
    show_background: bool = True
    background_color: str = "#000000"
    background_opacity: float = 0.6
    show_separators: bool = True
    show_refresh_spiral: bool = True
    margin: int = 30
    header_logo_px_adjust: int = 0
    border_color: list[int] = field(default_factory=lambda: [255, 255, 255, 255])
    border_opacity: float = 1.0
    color: list[int] = field(default_factory=lambda: [255, 255, 255, 230])

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.reddit") -> "RedditWidgetSettings":
        position = coerce_widget_position(
            settings.get(f"{prefix}.position", "top_right"),
            WidgetPosition.TOP_RIGHT,
        )
        return cls(
            enabled=settings.get(f"{prefix}.enabled", False),
            monitor=settings.get(f"{prefix}.monitor", "ALL"),
            position=position,
            provider=settings.get(f"{prefix}.provider", "pullpush"),
            subreddit=settings.get(f"{prefix}.subreddit", "technology"),
            limit=clamp_list_capacity(settings.get(f"{prefix}.limit", 10), default=10),
            font_family=settings.get(f"{prefix}.font_family", "Inter"),
            font_size=int(settings.get(f"{prefix}.font_size", 18)),
            text_color=settings.get(f"{prefix}.text_color", "#FFFFFF"),
            show_background=settings.get(f"{prefix}.show_background", True),
            background_color=settings.get(f"{prefix}.background_color", "#000000"),
            background_opacity=float(settings.get(f"{prefix}.background_opacity", 0.6)),
            show_separators=settings.get(f"{prefix}.show_separators", True),
            show_refresh_spiral=settings.get(f"{prefix}.show_refresh_spiral", True),
            margin=int(settings.get(f"{prefix}.margin", 30)),
            header_logo_px_adjust=int(settings.get(f"{prefix}.header_logo_px_adjust", 0)),
            border_color=settings.get(f"{prefix}.border_color", [255, 255, 255, 255]),
            border_opacity=float(settings.get(f"{prefix}.border_opacity", 1.0)),
            color=settings.get(f"{prefix}.color", [255, 255, 255, 230]),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], prefix: str = "widgets.reddit") -> "RedditWidgetSettings":
        def _get(key: str, default: Any) -> Any:
            dotted = f"{prefix}.{key}"
            if dotted in data:
                return data.get(dotted, default)
            return data.get(key, default)

        position = coerce_widget_position(_get("position", "top_right"), WidgetPosition.TOP_RIGHT)

        return cls(
            enabled=_get("enabled", False),
            monitor=_get("monitor", "ALL"),
            position=position,
            provider=_get("provider", "pullpush"),
            subreddit=_get("subreddit", "technology"),
            limit=clamp_list_capacity(_get("limit", 10), default=10),
            font_family=_get("font_family", "Inter"),
            font_size=int(_get("font_size", 18)),
            text_color=_get("text_color", "#FFFFFF"),
            show_background=_get("show_background", True),
            background_color=_get("background_color", "#000000"),
            background_opacity=float(_get("background_opacity", 0.6)),
            show_separators=_get("show_separators", True),
            show_refresh_spiral=_get("show_refresh_spiral", True),
            margin=int(_get("margin", 30)),
            header_logo_px_adjust=int(_get("header_logo_px_adjust", 0)),
            border_color=_get("border_color", [255, 255, 255, 255]),
            border_opacity=float(_get("border_opacity", 1.0)),
            color=_get("color", [255, 255, 255, 230]),
        )

    def to_dict(self, prefix: str = "widgets.reddit") -> Dict[str, Any]:
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.provider": self.provider,
            f"{prefix}.subreddit": self.subreddit,
            f"{prefix}.limit": int(self.limit),
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": int(self.font_size),
            f"{prefix}.text_color": self.text_color,
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.background_color": self.background_color,
            f"{prefix}.background_opacity": float(self.background_opacity),
            f"{prefix}.show_separators": self.show_separators,
            f"{prefix}.show_refresh_spiral": self.show_refresh_spiral,
            f"{prefix}.margin": int(self.margin),
            f"{prefix}.header_logo_px_adjust": int(self.header_logo_px_adjust),
            f"{prefix}.border_color": self.border_color,
            f"{prefix}.border_opacity": float(self.border_opacity),
            f"{prefix}.color": self.color,
        }


@dataclass
class MediaWidgetSettings:
    """Media/Spotify widget settings."""
    enabled: bool = False
    monitor: str = "ALL"
    position: WidgetPosition = WidgetPosition.BOTTOM_LEFT
    font_family: str = "Inter"
    font_size: int = 20
    text_color: str = "#FFFFFF"
    show_background: bool = True
    background_color: str = "#000000"
    background_opacity: float = 0.5
    show_controls: bool = True
    show_header_frame: bool = True
    artwork_size: int = 200
    margin: int = 30
    border_color: list[int] = field(default_factory=lambda: [128, 128, 128, 255])
    border_opacity: float = 0.8
    color: list[int] = field(default_factory=lambda: [255, 255, 255, 230])
    bg_color: list[int] = field(default_factory=lambda: [64, 64, 64, 255])
    rounded_artwork_border: bool = True
    provider: str = "spotify"
    spotify_volume_enabled: bool = True
    spotify_volume_fill_color: list[int] = field(default_factory=lambda: [66, 66, 66, 255])
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "MediaWidgetSettings":
        """Load media widget settings from SettingsManager."""
        position = coerce_widget_position(
            settings.get("widgets.media.position", "bottom_left"),
            WidgetPosition.BOTTOM_LEFT,
        )
        
        return cls(
            enabled=settings.get("widgets.media.enabled", False),
            monitor=settings.get("widgets.media.monitor", "ALL"),
            position=position,
            font_family=settings.get("widgets.media.font_family", "Inter"),
            font_size=settings.get("widgets.media.font_size", 20),
            text_color=settings.get("widgets.media.text_color", "#FFFFFF"),
            show_background=settings.get("widgets.media.show_background", True),
            background_color=settings.get("widgets.media.background_color", "#000000"),
            background_opacity=settings.get("widgets.media.background_opacity", 0.5),
            show_controls=settings.get("widgets.media.show_controls", True),
            show_header_frame=settings.get("widgets.media.show_header_frame", True),
            artwork_size=settings.get("widgets.media.artwork_size", 200),
            margin=settings.get("widgets.media.margin", 30),
            border_color=settings.get("widgets.media.border_color", [128, 128, 128, 255]),
            border_opacity=settings.get("widgets.media.border_opacity", 0.8),
            color=settings.get("widgets.media.color", [255, 255, 255, 230]),
            bg_color=settings.get("widgets.media.bg_color", [64, 64, 64, 255]),
            rounded_artwork_border=settings.get("widgets.media.rounded_artwork_border", True),
            provider=settings.get("widgets.media.provider", "spotify"),
            spotify_volume_enabled=settings.get("widgets.media.spotify_volume_enabled", True),
            spotify_volume_fill_color=settings.get("widgets.media.spotify_volume_fill_color", [66, 66, 66, 255]),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], prefix: str = "widgets.media") -> "MediaWidgetSettings":
        """Load media widget settings from a plain mapping (e.g., widgets dict)."""
        def _get(key: str, default: Any) -> Any:
            dotted = f"{prefix}.{key}"
            if dotted in data:
                return data.get(dotted, default)
            return data.get(key, default)

        position = coerce_widget_position(_get("position", "bottom_left"), WidgetPosition.BOTTOM_LEFT)

        return cls(
            enabled=_get("enabled", False),
            monitor=_get("monitor", "ALL"),
            position=position,
            font_family=_get("font_family", "Inter"),
            font_size=int(_get("font_size", 20)),
            text_color=_get("text_color", "#FFFFFF"),
            show_background=_get("show_background", True),
            background_color=_get("background_color", "#000000"),
            background_opacity=float(_get("background_opacity", 0.5)),
            show_controls=_get("show_controls", True),
            show_header_frame=_get("show_header_frame", True),
            artwork_size=int(_get("artwork_size", 200)),
            margin=int(_get("margin", 30)),
            border_color=_get("border_color", [128, 128, 128, 255]),
            border_opacity=float(_get("border_opacity", 0.8)),
            color=_get("color", [255, 255, 255, 230]),
            bg_color=_get("bg_color", [64, 64, 64, 255]),
            rounded_artwork_border=_get("rounded_artwork_border", True),
            provider=_get("provider", "spotify"),
            spotify_volume_enabled=_get("spotify_volume_enabled", True),
            spotify_volume_fill_color=_get("spotify_volume_fill_color", [66, 66, 66, 255]),
        )

    def to_dict(self, prefix: str = "widgets.media") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.position": self.position.value if isinstance(self.position, WidgetPosition) else str(self.position),
            f"{prefix}.font_family": self.font_family,
            f"{prefix}.font_size": int(self.font_size),
            f"{prefix}.text_color": self.text_color,
            f"{prefix}.show_background": self.show_background,
            f"{prefix}.background_color": self.background_color,
            f"{prefix}.background_opacity": float(self.background_opacity),
            f"{prefix}.show_controls": self.show_controls,
            f"{prefix}.show_header_frame": self.show_header_frame,
            f"{prefix}.artwork_size": int(self.artwork_size),
            f"{prefix}.margin": int(self.margin),
            f"{prefix}.border_color": self.border_color,
            f"{prefix}.border_opacity": float(self.border_opacity),
            f"{prefix}.color": self.color,
            f"{prefix}.bg_color": self.bg_color,
            f"{prefix}.rounded_artwork_border": self.rounded_artwork_border,
            f"{prefix}.provider": self.provider,
            f"{prefix}.spotify_volume_enabled": self.spotify_volume_enabled,
            f"{prefix}.spotify_volume_fill_color": self.spotify_volume_fill_color,
        }


@dataclass
class AccessibilitySettings:
    """Accessibility settings."""
    dimming_enabled: bool = False
    dimming_opacity: int = 30
    pixel_shift_enabled: bool = False
    pixel_shift_rate: int = 1
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "AccessibilitySettings":
        """Load accessibility settings from SettingsManager."""
        return cls(
            dimming_enabled=settings.get("accessibility.dimming.enabled", False),
            dimming_opacity=settings.get("accessibility.dimming.opacity", 30),
            pixel_shift_enabled=settings.get("accessibility.pixel_shift.enabled", False),
            pixel_shift_rate=settings.get("accessibility.pixel_shift.rate", 1),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "accessibility.dimming.enabled": self.dimming_enabled,
            "accessibility.dimming.opacity": self.dimming_opacity,
        }


