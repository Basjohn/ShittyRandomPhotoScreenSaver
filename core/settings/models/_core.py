"""Core application settings models: Display, Transition, Input, Cache, Source, Shadow, Clock."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.settings.default_contract import require_canonical_default

from core.settings.models._enums import (
    DisplayMode,
    TransitionType,
    WidgetPosition,
    parse_widget_position,
)
from core.settings.normalization import normalize_widget_position

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
    """Clamp persisted percentage; corrupt state returns to canonical authority."""

    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError, OverflowError):
        return int(require_canonical_default("input.widget_glow_intensity"))


def _coerce_widget_glow_distance(value: Any) -> int:
    """Clamp authored halo distance; corrupt state returns to canonical authority."""

    try:
        return max(6, min(48, int(value)))
    except (TypeError, ValueError, OverflowError):
        return int(require_canonical_default("input.widget_glow_distance"))


@dataclass
class DisplaySettings:
    """Display-related settings projected from the canonical defaults authority."""

    hw_accel: bool = bool(require_canonical_default("display.hw_accel"))
    mode: DisplayMode = DisplayMode(require_canonical_default("display.mode"))
    same_image_all_monitors: bool = bool(
        require_canonical_default("display.same_image_all_monitors")
    )
    rotation_interval: int = int(require_canonical_default("timing.interval"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "DisplaySettings":
        mode_default = DisplayMode(require_canonical_default("display.mode"))
        try:
            mode = DisplayMode(settings.get("display.mode"))
        except (TypeError, ValueError):
            mode = mode_default
        return cls(
            hw_accel=bool(settings.get("display.hw_accel")),
            mode=mode,
            same_image_all_monitors=bool(settings.get("display.same_image_all_monitors")),
            rotation_interval=int(settings.get("timing.interval")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "display.hw_accel": self.hw_accel,
            "display.mode": self.mode.value,
            "display.same_image_all_monitors": self.same_image_all_monitors,
            "timing.interval": self.rotation_interval,
        }


@dataclass
class TransitionSettings:
    """Persisted transition settings; runtime random-choice history is excluded."""

    type: TransitionType = TransitionType(require_canonical_default("transitions.type"))
    random_always: bool = bool(require_canonical_default("transitions.random_always"))
    duration_ms: int = int(require_canonical_default("transitions.duration_ms"))
    durations: Dict[str, int] = field(
        default_factory=lambda: require_canonical_default("transitions.durations")
    )
    pool: Dict[str, bool] = field(
        default_factory=lambda: require_canonical_default("transitions.pool")
    )

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "TransitionSettings":
        type_default = TransitionType(require_canonical_default("transitions.type"))
        try:
            trans_type = TransitionType(settings.get("transitions.type"))
        except (TypeError, ValueError):
            trans_type = type_default
        durations = settings.get("transitions.durations")
        pool = settings.get("transitions.pool")
        return cls(
            type=trans_type,
            random_always=bool(settings.get("transitions.random_always")),
            duration_ms=int(settings.get("transitions.duration_ms")),
            durations=dict(durations) if isinstance(durations, dict) else require_canonical_default("transitions.durations"),
            pool=dict(pool) if isinstance(pool, dict) else require_canonical_default("transitions.pool"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transitions.type": self.type.value,
            "transitions.random_always": self.random_always,
            "transitions.duration_ms": self.duration_ms,
            "transitions.durations": dict(self.durations),
            "transitions.pool": dict(self.pool),
        }


@dataclass
class InputSettings:
    """Input settings projected from canonical product defaults."""

    interaction_mode: bool = bool(require_canonical_default("input.interaction_mode"))
    halo_shape: str = str(require_canonical_default("input.halo_shape"))
    widget_glow_on_hover: bool = bool(require_canonical_default("input.widget_glow_on_hover"))
    widget_glow_on_click: bool = bool(require_canonical_default("input.widget_glow_on_click"))
    widget_glow_intensity: int = int(require_canonical_default("input.widget_glow_intensity"))
    widget_glow_distance: int = int(require_canonical_default("input.widget_glow_distance"))
    widget_glow_color: Optional[List[int]] = field(
        default_factory=lambda: require_canonical_default("input.widget_glow_color")
    )
    widget_glow_jedi_mode: bool = bool(require_canonical_default("input.widget_glow_jedi_mode"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "InputSettings":
        return cls(
            interaction_mode=settings.get_bool("input.interaction_mode"),
            halo_shape=str(settings.get("input.halo_shape")).lower(),
            widget_glow_on_hover=settings.get_bool("input.widget_glow_on_hover"),
            widget_glow_on_click=settings.get_bool("input.widget_glow_on_click"),
            widget_glow_intensity=_coerce_widget_glow_intensity(settings.get("input.widget_glow_intensity")),
            widget_glow_distance=_coerce_widget_glow_distance(settings.get("input.widget_glow_distance")),
            widget_glow_color=_coerce_widget_glow_color(settings.get("input.widget_glow_color")),
            widget_glow_jedi_mode=settings.get_bool("input.widget_glow_jedi_mode"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input.interaction_mode": self.interaction_mode,
            "input.halo_shape": self.halo_shape,
            "input.widget_glow_on_hover": self.widget_glow_on_hover,
            "input.widget_glow_on_click": self.widget_glow_on_click,
            "input.widget_glow_intensity": self.widget_glow_intensity,
            "input.widget_glow_distance": self.widget_glow_distance,
            "input.widget_glow_color": None if self.widget_glow_color is None else list(self.widget_glow_color),
            "input.widget_glow_jedi_mode": self.widget_glow_jedi_mode,
        }


@dataclass
class CacheSettings:
    """Cache settings projected from canonical product defaults."""

    prefetch_ahead: int = int(require_canonical_default("cache.prefetch_ahead"))
    max_items: int = int(require_canonical_default("cache.max_items"))
    max_memory_mb: int = int(require_canonical_default("cache.max_memory_mb"))
    max_concurrent: int = int(require_canonical_default("cache.max_concurrent"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "CacheSettings":
        return cls(
            prefetch_ahead=int(settings.get("cache.prefetch_ahead")),
            max_items=int(settings.get("cache.max_items")),
            max_memory_mb=int(settings.get("cache.max_memory_mb")),
            max_concurrent=int(settings.get("cache.max_concurrent")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache.prefetch_ahead": self.prefetch_ahead,
            "cache.max_items": self.max_items,
            "cache.max_memory_mb": self.max_memory_mb,
            "cache.max_concurrent": self.max_concurrent,
        }


@dataclass
class SourceSettings:
    """Image-source settings projected from canonical product defaults."""

    folders: List[str] = field(default_factory=lambda: require_canonical_default("sources.folders"))
    rss_feeds: List[str] = field(default_factory=lambda: require_canonical_default("sources.rss_feeds"))
    rss_save_to_disk: bool = bool(require_canonical_default("sources.rss_save_to_disk"))
    rss_save_directory: str = str(require_canonical_default("sources.rss_save_directory"))
    rss_rotating_cache_size: int = int(require_canonical_default("sources.rss_rotating_cache_size"))
    rss_background_cap: int = int(require_canonical_default("sources.rss_background_cap"))
    rss_refresh_minutes: int = int(require_canonical_default("sources.rss_refresh_minutes"))
    rss_stale_minutes: int = int(require_canonical_default("sources.rss_stale_minutes"))
    local_ratio: int = int(require_canonical_default("sources.local_ratio"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "SourceSettings":
        return cls(
            folders=list(settings.get("sources.folders")),
            rss_feeds=list(settings.get("sources.rss_feeds")),
            rss_save_to_disk=bool(settings.get("sources.rss_save_to_disk")),
            rss_save_directory=str(settings.get("sources.rss_save_directory")),
            rss_rotating_cache_size=int(settings.get("sources.rss_rotating_cache_size")),
            rss_background_cap=int(settings.get("sources.rss_background_cap")),
            rss_refresh_minutes=int(settings.get("sources.rss_refresh_minutes")),
            rss_stale_minutes=int(settings.get("sources.rss_stale_minutes")),
            local_ratio=int(settings.get("sources.local_ratio")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources.folders": list(self.folders),
            "sources.rss_feeds": list(self.rss_feeds),
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
    """Widget shadow settings projected from canonical Widget defaults."""

    enabled: bool = bool(require_canonical_default("widgets.shadows.enabled"))
    text_enabled: bool = bool(require_canonical_default("widgets.shadows.text_enabled"))
    header_enabled: bool = bool(require_canonical_default("widgets.shadows.header_enabled"))
    color: List[int] = field(default_factory=lambda: require_canonical_default("widgets.shadows.color"))
    blur_radius: int = int(require_canonical_default("widgets.shadows.blur_radius"))
    text_opacity: float = float(require_canonical_default("widgets.shadows.text_opacity"))
    frame_opacity: float = float(require_canonical_default("widgets.shadows.frame_opacity"))
    direction: str = str(require_canonical_default("widgets.shadows.direction"))
    frame_extra_offset: int = int(require_canonical_default("widgets.shadows.frame_extra_offset"))
    text_extra_offset: int = int(require_canonical_default("widgets.shadows.text_extra_offset"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "ShadowSettings":
        """Project persisted shadow state with canonical repair at one boundary."""

        def canonical(name: str) -> Any:
            return require_canonical_default(f"widgets.shadows.{name}")

        def read(name: str) -> Any:
            try:
                value = settings.get(f"widgets.shadows.{name}")
            except Exception:
                return canonical(name)
            return canonical(name) if value is None else value

        def as_bool(name: str) -> bool:
            raw = read(name)
            default = bool(canonical(name))
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                normalized = raw.strip().lower()
                if normalized in {"true", "1", "yes", "on"}:
                    return True
                if normalized in {"false", "0", "no", "off"}:
                    return False
                return default
            return bool(raw)

        def as_int(name: str) -> int:
            try:
                return int(read(name))
            except (TypeError, ValueError, OverflowError):
                return int(canonical(name))

        def as_float(name: str) -> float:
            try:
                return float(read(name))
            except (TypeError, ValueError, OverflowError):
                return float(canonical(name))

        raw_color = read("color")
        try:
            color = [int(channel) for channel in raw_color]
        except (TypeError, ValueError, OverflowError):
            color = list(canonical("color"))
        if len(color) != 4 or any(channel < 0 or channel > 255 for channel in color):
            color = list(canonical("color"))

        from core.settings.shadow_direction import ShadowDirection

        raw_direction = str(read("direction") or "").strip().upper()
        try:
            direction = ShadowDirection(raw_direction).value
        except ValueError:
            direction = ShadowDirection(str(canonical("direction")).strip().upper()).value

        return cls(
            enabled=as_bool("enabled"),
            text_enabled=as_bool("text_enabled"),
            header_enabled=as_bool("header_enabled"),
            color=color,
            blur_radius=as_int("blur_radius"),
            text_opacity=as_float("text_opacity"),
            frame_opacity=as_float("frame_opacity"),
            direction=direction,
            frame_extra_offset=as_int("frame_extra_offset"),
            text_extra_offset=as_int("text_extra_offset"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widgets.shadows.enabled": self.enabled,
            "widgets.shadows.text_enabled": self.text_enabled,
            "widgets.shadows.header_enabled": self.header_enabled,
            "widgets.shadows.color": list(self.color),
            "widgets.shadows.blur_radius": self.blur_radius,
            "widgets.shadows.text_opacity": self.text_opacity,
            "widgets.shadows.frame_opacity": self.frame_opacity,
            "widgets.shadows.direction": self.direction,
            "widgets.shadows.frame_extra_offset": self.frame_extra_offset,
            "widgets.shadows.text_extra_offset": self.text_extra_offset,
        }


@dataclass
class ClockWidgetSettings:
    """Clock widget model using only the canonical current clock schema."""

    enabled: bool = bool(require_canonical_default("widgets.clock.enabled"))
    monitor: Any = require_canonical_default("widgets.clock.monitor")
    shared_tick: bool = bool(require_canonical_default("widgets.clock.shared_tick"))
    position: WidgetPosition = parse_widget_position(require_canonical_default("widgets.clock.position"))
    format: str = str(require_canonical_default("widgets.clock.format"))
    show_seconds: bool = bool(require_canonical_default("widgets.clock.show_seconds"))
    timezone: str = str(require_canonical_default("widgets.clock.timezone"))
    show_timezone: bool = bool(require_canonical_default("widgets.clock.show_timezone"))
    show_day_of_week: bool = bool(require_canonical_default("widgets.clock.show_day_of_week"))
    show_date: bool = bool(require_canonical_default("widgets.clock.show_date"))
    show_separator: bool = bool(require_canonical_default("widgets.clock.show_separator"))
    separator_thickness: int = int(require_canonical_default("widgets.clock.separator_thickness"))
    calendar_layout: str = str(require_canonical_default("widgets.clock.calendar_layout"))
    calendar_font_size: int = int(require_canonical_default("widgets.clock.calendar_font_size"))
    font_family: str = str(require_canonical_default("widgets.clock.font_family"))
    font_size: int = int(require_canonical_default("widgets.clock.font_size"))
    color: List[int] = field(default_factory=lambda: require_canonical_default("widgets.clock.color"))
    show_background: bool = bool(require_canonical_default("widgets.clock.show_background"))
    bg_color: List[int] = field(default_factory=lambda: require_canonical_default("widgets.clock.bg_color"))
    bg_opacity: float = float(require_canonical_default("widgets.clock.bg_opacity"))
    border_color: List[int] = field(default_factory=lambda: require_canonical_default("widgets.clock.border_color"))
    border_opacity: float = float(require_canonical_default("widgets.clock.border_opacity"))
    display_mode: str = str(require_canonical_default("widgets.clock.display_mode"))
    show_numerals: bool = bool(require_canonical_default("widgets.clock.show_numerals"))
    analog_face_shadow: bool = bool(require_canonical_default("widgets.clock.analog_face_shadow"))

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.clock") -> "ClockWidgetSettings":
        position = normalize_widget_position(
            settings.get(f"{prefix}.position"),
            parse_widget_position(require_canonical_default(f"{prefix}.position")),
        )
        return cls(
            enabled=bool(settings.get(f"{prefix}.enabled")),
            monitor=settings.get(f"{prefix}.monitor"),
            shared_tick=bool(settings.get(f"{prefix}.shared_tick")),
            position=position,
            format=str(settings.get(f"{prefix}.format")),
            show_seconds=bool(settings.get(f"{prefix}.show_seconds")),
            timezone=str(settings.get(f"{prefix}.timezone")),
            show_timezone=bool(settings.get(f"{prefix}.show_timezone")),
            show_day_of_week=bool(settings.get(f"{prefix}.show_day_of_week")),
            show_date=bool(settings.get(f"{prefix}.show_date")),
            show_separator=bool(settings.get(f"{prefix}.show_separator")),
            separator_thickness=int(settings.get(f"{prefix}.separator_thickness")),
            calendar_layout=str(settings.get(f"{prefix}.calendar_layout")),
            calendar_font_size=int(settings.get(f"{prefix}.calendar_font_size")),
            font_family=str(settings.get(f"{prefix}.font_family")),
            font_size=int(settings.get(f"{prefix}.font_size")),
            color=list(settings.get(f"{prefix}.color")),
            show_background=bool(settings.get(f"{prefix}.show_background")),
            bg_color=list(settings.get(f"{prefix}.bg_color")),
            bg_opacity=float(settings.get(f"{prefix}.bg_opacity")),
            border_color=list(settings.get(f"{prefix}.border_color")),
            border_opacity=float(settings.get(f"{prefix}.border_opacity")),
            display_mode=str(settings.get(f"{prefix}.display_mode")),
            show_numerals=bool(settings.get(f"{prefix}.show_numerals")),
            analog_face_shadow=bool(settings.get(f"{prefix}.analog_face_shadow")),
        )
