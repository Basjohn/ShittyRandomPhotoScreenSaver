"""Core application settings models: Display, Transition, Input, Cache, Source, Shadow, Clock."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.settings.models._enums import (
    DisplayMode,
    TransitionType,
    WidgetPosition,
    coerce_widget_position,
)

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager


def _coerce_widget_glow_color(value: Any) -> Optional[List[int]]:
    """Validate an authored colour while preserving ``None`` as Use Theme."""

    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("widget glow colour requires four RGBA channels or None")
    try:
        channels = [int(channel) for channel in value]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("widget glow colour requires numeric RGBA channels") from exc
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError("widget glow colour channels must be in [0, 255]")
    return channels

def _coerce_widget_glow_intensity(value: Any) -> int:
    """Clamp the persisted percentage without turning corrupt state into a crash."""

    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 100


def _coerce_widget_glow_distance(value: Any) -> int:
    """Clamp the authored halo travel distance in retained-scene pixels."""

    try:
        return max(6, min(48, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 14


@dataclass
class DisplaySettings:
    """Display-related settings."""
    hw_accel: bool = True
    mode: DisplayMode = DisplayMode.FILL
    same_image_all_monitors: bool = False
    rotation_interval: int = 45
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "DisplaySettings":
        """Load display settings from SettingsManager."""
        mode_str = settings.get("display.mode", "fill")
        try:
            mode = DisplayMode(mode_str)
        except ValueError:
            mode = DisplayMode.FILL

        return cls(
            hw_accel=settings.get("display.hw_accel", True),
            mode=mode,
            same_image_all_monitors=settings.get("display.same_image_all_monitors", False),
            rotation_interval=settings.get("timing.interval", 45),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "display.hw_accel": self.hw_accel,
            "display.mode": self.mode.value,
            "display.same_image_all_monitors": self.same_image_all_monitors,
            "timing.interval": self.rotation_interval,
        }


@dataclass
class TransitionSettings:
    """Transition-related settings."""
    type: TransitionType = TransitionType.CROSSFADE
    random_always: bool = True
    random_choice: Optional[str] = None
    duration_ms: int = 2000
    durations: Dict[str, int] = field(default_factory=dict)
    pool: Dict[str, bool] = field(default_factory=dict)
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "TransitionSettings":
        """Load transition settings from SettingsManager."""
        type_str = settings.get("transitions.type", "Crossfade")
        try:
            trans_type = TransitionType(type_str)
        except ValueError:
            trans_type = TransitionType.CROSSFADE
        
        return cls(
            type=trans_type,
            random_always=settings.get("transitions.random_always", True),
            random_choice=settings.get("transitions.random_choice", None),
            duration_ms=settings.get("transitions.duration_ms", 2000),
            durations=settings.get("transitions.durations", {}),
            pool=settings.get("transitions.pool", {}),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "transitions.type": self.type.value,
            "transitions.random_always": self.random_always,
            "transitions.random_choice": self.random_choice,
            "transitions.duration_ms": self.duration_ms,
            "transitions.durations": self.durations,
            "transitions.pool": self.pool,
        }


@dataclass
class InputSettings:
    """Input-related settings."""
    interaction_mode: bool = False
    halo_shape: str = "circle"
    widget_glow_on_hover: bool = False
    widget_glow_on_click: bool = False
    widget_glow_intensity: int = 100
    widget_glow_distance: int = 14
    widget_glow_color: Optional[List[int]] = None

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "InputSettings":
        """Load input settings from SettingsManager."""
        return cls(
            interaction_mode=settings.get("input.interaction_mode", False),
            halo_shape=str(settings.get("input.halo_shape", "circle")).lower(),
            widget_glow_on_hover=settings.to_bool(
                settings.get("input.widget_glow_on_hover", False), False
            ),
            widget_glow_on_click=settings.to_bool(
                settings.get("input.widget_glow_on_click", False), False
            ),
            widget_glow_intensity=_coerce_widget_glow_intensity(
                settings.get("input.widget_glow_intensity", 100)
            ),
            widget_glow_distance=_coerce_widget_glow_distance(
                settings.get("input.widget_glow_distance", 14)
            ),
            widget_glow_color=_coerce_widget_glow_color(
                settings.get("input.widget_glow_color", None)
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "input.interaction_mode": self.interaction_mode,
            "input.halo_shape": self.halo_shape,
            "input.widget_glow_on_hover": self.widget_glow_on_hover,
            "input.widget_glow_on_click": self.widget_glow_on_click,
            "input.widget_glow_intensity": self.widget_glow_intensity,
            "input.widget_glow_distance": self.widget_glow_distance,
            "input.widget_glow_color": (
                None
                if self.widget_glow_color is None
                else list(self.widget_glow_color)
            ),
        }


@dataclass
class CacheSettings:
    """Cache-related settings."""
    prefetch_ahead: int = 5
    max_items: int = 16
    max_memory_mb: int = 256
    max_concurrent: int = 2
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "CacheSettings":
        """Load cache settings from SettingsManager."""
        return cls(
            prefetch_ahead=settings.get("cache.prefetch_ahead", 5),
            max_items=settings.get("cache.max_items", 16),
            max_memory_mb=settings.get("cache.max_memory_mb", 256),
            max_concurrent=settings.get("cache.max_concurrent", 2),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "cache.prefetch_ahead": self.prefetch_ahead,
            "cache.max_items": self.max_items,
            "cache.max_memory_mb": self.max_memory_mb,
            "cache.max_concurrent": self.max_concurrent,
        }


@dataclass
class SourceSettings:
    """Image source settings."""
    folders: List[str] = field(default_factory=list)
    rss_feeds: List[str] = field(default_factory=list)
    rss_save_to_disk: bool = False
    rss_save_directory: str = ""
    rss_rotating_cache_size: int = 20
    rss_background_cap: int = 30
    rss_refresh_minutes: int = 10
    rss_stale_minutes: int = 30
    local_ratio: int = 60
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "SourceSettings":
        """Load source settings from SettingsManager."""
        return cls(
            folders=settings.get("sources.folders", []),
            rss_feeds=settings.get("sources.rss_feeds", []),
            rss_save_to_disk=settings.get("sources.rss_save_to_disk", False),
            rss_save_directory=settings.get("sources.rss_save_directory", ""),
            rss_rotating_cache_size=settings.get("sources.rss_rotating_cache_size", 20),
            rss_background_cap=settings.get("sources.rss_background_cap", 30),
            rss_refresh_minutes=settings.get("sources.rss_refresh_minutes", 10),
            rss_stale_minutes=settings.get("sources.rss_stale_minutes", 30),
            local_ratio=settings.get("sources.local_ratio", 60),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "sources.folders": self.folders,
            "sources.rss_feeds": self.rss_feeds,
            "sources.rss_save_to_disk": self.rss_save_to_disk,
            "sources.rss_save_directory": self.rss_save_directory,
            "sources.rss_rotating_cache_size": self.rss_rotating_cache_size,
            "sources.rss_background_cap": self.rss_background_cap,
            "sources.rss_refresh_minutes": self.rss_refresh_minutes,
            "sources.rss_stale_minutes": self.rss_stale_minutes,
            "sources.local_ratio": self.local_ratio,
        }


@dataclass
class ShadowSettings:
    """Widget shadow settings."""
    enabled: bool = True
    text_enabled: bool = True
    header_enabled: bool = True
    color: str = "#000000"
    blur_radius: int = 18
    text_opacity: float = 0.33
    frame_opacity: float = 0.77
    # Canonical eight-direction shadow orientation (Phase E4). Orientation only;
    # per-class magnitudes are family-authored. Default SE.
    direction: str = "SE"
    # Optional Extra Offset controls (Phase F0.5). Frame Extra Offset is
    # directional *growth*: the authored base drop offset stays in place and
    # only the selected far edge(s) extend. Text Extra Offset remains glyph
    # displacement because text has no stretchable card footprint. Default 0.
    # The retired ``widgets.shadows.offset`` pair is NOT this control and is not
    # migrated.
    frame_extra_offset: int = 0
    text_extra_offset: int = 0

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "ShadowSettings":
        """Load shadow settings from SettingsManager."""
        return cls(
            enabled=settings.get("widgets.shadows.enabled", True),
            text_enabled=settings.get("widgets.shadows.text_enabled", True),
            header_enabled=settings.get("widgets.shadows.header_enabled", True),
            color=settings.get("widgets.shadows.color", "#000000"),
            blur_radius=settings.get("widgets.shadows.blur_radius", 18),
            text_opacity=settings.get("widgets.shadows.text_opacity", 0.33),
            frame_opacity=settings.get("widgets.shadows.frame_opacity", 0.77),
            direction=settings.get("widgets.shadows.direction", "SE"),
            frame_extra_offset=settings.get("widgets.shadows.frame_extra_offset", 0),
            text_extra_offset=settings.get("widgets.shadows.text_extra_offset", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "widgets.shadows.enabled": self.enabled,
            "widgets.shadows.text_enabled": self.text_enabled,
            "widgets.shadows.header_enabled": self.header_enabled,
            "widgets.shadows.color": self.color,
            "widgets.shadows.blur_radius": self.blur_radius,
            "widgets.shadows.text_opacity": self.text_opacity,
            "widgets.shadows.frame_opacity": self.frame_opacity,
            "widgets.shadows.direction": self.direction,
            "widgets.shadows.frame_extra_offset": self.frame_extra_offset,
            "widgets.shadows.text_extra_offset": self.text_extra_offset,
        }


@dataclass
class ClockWidgetSettings:
    """Clock widget settings."""
    enabled: bool = True
    monitor: str = "ALL"
    shared_tick: bool = True
    position: WidgetPosition = WidgetPosition.TOP_RIGHT
    format: str = "12h"
    show_seconds: bool = True
    timezone: str = "local"
    show_timezone: bool = False
    show_day_of_week: bool = False
    show_date: bool = False
    show_separator: bool = False
    separator_thickness: int = 2
    calendar_layout: str = "shared_line"
    calendar_font_size: int = 20
    font_family: str = "Inter"
    font_size: int = 48
    text_color: str = "#FFFFFF"
    show_background: bool = False
    background_color: str = "#000000"
    background_opacity: float = 0.5
    display_mode: str = "digital"
    show_numerals: bool = True
    analog_face_shadow: bool = True
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.clock") -> "ClockWidgetSettings":
        """Load clock widget settings from SettingsManager."""
        position = coerce_widget_position(
            settings.get(f"{prefix}.position", "top_right"),
            WidgetPosition.TOP_RIGHT,
        )
        
        return cls(
            enabled=settings.get(f"{prefix}.enabled", True),
            monitor=settings.get(f"{prefix}.monitor", "ALL"),
            shared_tick=settings.get(f"{prefix}.shared_tick", True),
            position=position,
            format=settings.get(f"{prefix}.format", "12h"),
            show_seconds=settings.get(f"{prefix}.show_seconds", True),
            timezone=settings.get(f"{prefix}.timezone", "local"),
            show_timezone=settings.get(f"{prefix}.show_timezone", False),
            show_day_of_week=settings.get(f"{prefix}.show_day_of_week", False),
            show_date=settings.get(f"{prefix}.show_date", False),
            show_separator=settings.get(
                f"{prefix}.show_separator",
                settings.get(f"{prefix}.show_digital_separator", False),
            ),
            separator_thickness=settings.get(f"{prefix}.separator_thickness", 2),
            calendar_layout=settings.get(f"{prefix}.calendar_layout", "shared_line"),
            calendar_font_size=settings.get(f"{prefix}.calendar_font_size", 20),
            font_family=settings.get(f"{prefix}.font_family", "Inter"),
            font_size=settings.get(f"{prefix}.font_size", 48),
            text_color=settings.get(f"{prefix}.text_color", "#FFFFFF"),
            show_background=settings.get(f"{prefix}.show_background", False),
            background_color=settings.get(f"{prefix}.background_color", "#000000"),
            background_opacity=settings.get(f"{prefix}.background_opacity", 0.5),
            display_mode=settings.get(f"{prefix}.display_mode", "digital"),
            show_numerals=settings.get(f"{prefix}.show_numerals", True),
            analog_face_shadow=settings.get(f"{prefix}.analog_face_shadow", True),
        )
