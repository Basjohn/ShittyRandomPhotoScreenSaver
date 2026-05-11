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
    hard_exit: bool = False
    halo_shape: str = "circle"

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "InputSettings":
        """Load input settings from SettingsManager."""
        return cls(
            hard_exit=settings.get("input.hard_exit", False),
            halo_shape=str(settings.get("input.halo_shape", "circle")).lower(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "input.hard_exit": self.hard_exit,
            "input.halo_shape": self.halo_shape,
        }


@dataclass
class CacheSettings:
    """Cache-related settings."""
    prefetch_ahead: int = 5
    max_items: int = 30  # Raised from 24 to 30 (Phase 4.1)
    max_memory_mb: int = 1024
    max_concurrent: int = 2
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "CacheSettings":
        """Load cache settings from SettingsManager."""
        return cls(
            prefetch_ahead=settings.get("cache.prefetch_ahead", 5),
            max_items=settings.get("cache.max_items", 30),
            max_memory_mb=settings.get("cache.max_memory_mb", 1024),
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
    offset: list[int] = field(default_factory=lambda: [4, 4])
    blur_radius: int = 10
    text_opacity: float = 0.6
    frame_opacity: float = 0.4
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "ShadowSettings":
        """Load shadow settings from SettingsManager."""
        return cls(
            enabled=settings.get("widgets.shadows.enabled", True),
            text_enabled=settings.get("widgets.shadows.text_enabled", True),
            header_enabled=settings.get("widgets.shadows.header_enabled", True),
            color=settings.get("widgets.shadows.color", "#000000"),
            offset=settings.get("widgets.shadows.offset", [4, 4]),
            blur_radius=settings.get("widgets.shadows.blur_radius", 10),
            text_opacity=settings.get("widgets.shadows.text_opacity", 0.6),
            frame_opacity=settings.get("widgets.shadows.frame_opacity", 0.4),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        return {
            "widgets.shadows.enabled": self.enabled,
            "widgets.shadows.text_enabled": self.text_enabled,
            "widgets.shadows.header_enabled": self.header_enabled,
            "widgets.shadows.color": self.color,
            "widgets.shadows.offset": self.offset,
            "widgets.shadows.blur_radius": self.blur_radius,
            "widgets.shadows.text_opacity": self.text_opacity,
            "widgets.shadows.frame_opacity": self.frame_opacity,
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
