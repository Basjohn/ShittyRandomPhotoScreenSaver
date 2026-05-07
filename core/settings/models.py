"""
Settings dataclass models for type-safe settings access.

This module provides typed dataclass models for all settings sections,
enabling:
- Type checking at development time
- Runtime validation
- IDE autocompletion
- Centralized settings schema documentation

Usage:
    from core.settings.models import DisplaySettings, TransitionSettings
    
    display = DisplaySettings.from_settings(settings_manager)
    display.hw_accel  # bool, type-checked
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Mapping, Tuple
from enum import Enum

from core.settings.bubble_gradient_semantics import (
    CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
    get_bubble_gradient_semantics_version,
    normalize_bubble_specular_direction,
    resolve_bubble_gradient_direction,
)
from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id,
    get_preset_key,
    get_setting_prefixes,
    VISUALIZER_MODE_IDS,
)
from core.settings.visualizer_preset_indices import (
    get_missing_preset_fallback_index,
    resolve_all_preset_indices_from_getter,
    resolve_all_preset_indices_from_mapping,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_settings_contract import (
    migrate_legacy_global_technical_keys,
    migrate_legacy_global_visual_keys,
    PER_MODE_BASELINE_KEYS,
    SPECIAL_PER_MODE_KEYS,
    resolve_visualizer_active_mode_rainbow_state,
    resolve_spectrum_render_mode,
    resolve_spectrum_unique_colors,
)

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager


class DisplayMode(Enum):
    """Display scaling mode."""
    FILL = "fill"
    FIT = "fit"
    SHRINK = "shrink"


class TransitionType(Enum):
    """Available transition types."""
    CROSSFADE = "Crossfade"
    SLIDE = "Slide"
    WIPE = "Wipe"
    DIFFUSE = "Diffuse"
    BLOCK_PUZZLE_FLIP = "Block Puzzle Flip"
    BLINDS = "Blinds"
    BLOCK_SPINS = "3D Block Spins"
    RIPPLE = "Ripple"
    WARP_DISSOLVE = "Warp Dissolve"
    CRUMBLE = "Crumble"
    PARTICLE = "Particle"
    BURN = "Burn"


class WidgetPosition(Enum):
    """Standard widget positions."""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    CENTER = "center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


def coerce_widget_position(value: Any, fallback: WidgetPosition) -> WidgetPosition:
    """
    DEPRECATED: Use core.settings.normalization.normalize_widget_position() instead.
    
    Normalize a persisted widget position into a WidgetPosition enum.
    Handles legacy strings such as "WidgetPosition.TOP_LEFT" or "Top Left".
    """
    # Import here to avoid circular dependency
    from core.settings.normalization import normalize_widget_position
    return normalize_widget_position(value, fallback)


def _normalize_visualizer_direction(value: Any, default: str = "top") -> str:
    val = str(value).lower()
    valid = {
        "top", "bottom", "left", "right",
        "top_left", "top_right", "bottom_left", "bottom_right",
        "center_out", "center_out_reverse",
    }
    return val if val in valid else default


_SPECTRUM_LEGACY_NOTCHES_LINEAR = [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]]
_SPECTRUM_DEFAULT_NOTCHES_LINEAR = [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]]
_SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED = {
    "Mid": 0.60,
    "Vocal": 0.64,
    "Low-Mid": 0.70,
    "Bass": 0.80,
}
_SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR = {
    "Bass": 0.80,
    "Low-Mid": 0.70,
    "Vocal": 0.64,
    "Hi-Mid": 0.80,
    "Treble": 1.00,
}


def _normalize_spectrum_linear_notches(value: Any) -> list[list]:
    """Promote old linear notch layouts into the explicit vocal-lane family."""
    if not isinstance(value, list) or len(value) < 2:
        return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]

    try:
        normalized = [[float(x), str(label)] for x, label in value]
    except Exception:
        return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]

    if len(normalized) == 5:
        labels = [str(label).strip().lower() for _, label in normalized]
        if labels == ["bass", "low", "mid", "hi-mid", "treble"]:
            if normalized == _SPECTRUM_LEGACY_NOTCHES_LINEAR:
                return [list(n) for n in _SPECTRUM_DEFAULT_NOTCHES_LINEAR]
            return [
                [float(normalized[0][0]), "Bass"],
                [float(normalized[1][0]), "Low-Mid"],
                [float(normalized[2][0]), "Vocal"],
                [float(normalized[3][0]), "Hi-Mid"],
                [float(normalized[4][0]), "Treble"],
            ]
        if labels == ["bass", "low-mid", "mid", "hi-mid", "treble"]:
            return [
                [float(normalized[0][0]), "Bass"],
                [float(normalized[1][0]), "Low-Mid"],
                [float(normalized[2][0]), "Vocal"],
                [float(normalized[3][0]), "Hi-Mid"],
                [float(normalized[4][0]), "Treble"],
            ]

    return normalized


def _clamp_lane_strength(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(default)


def _normalize_spectrum_lane_strengths(value: Any, defaults: Mapping[str, float]) -> Dict[str, float]:
    if not isinstance(value, Mapping):
        return {label: float(default) for label, default in defaults.items()}
    normalized: Dict[str, float] = {}
    for label, default in defaults.items():
        normalized[label] = _clamp_lane_strength(value.get(label, default), default)
    return normalized


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


PER_MODE_TECHNICAL_MODES: Tuple[str, ...] = (
    "spectrum",
    "bubble",
    "blob",
    "sine_wave",
    "oscilloscope",
    "devcurve",
)

_ACTIVE_MODE_TECHNICAL_KEYS: Tuple[str, ...] = tuple(
    key for key, _coerce in PER_MODE_BASELINE_KEYS
)
_ACTIVE_MODE_SHARED_VISUAL_KEYS: Tuple[str, ...] = (
    "bar_fill_color",
    "bar_border_color",
    "bar_border_opacity",
)


def _coerce_live_visualizer_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _coerce_live_visualizer_int(value: Any, default: int) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _coerce_live_visualizer_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _build_live_visualizer_mode_kwargs(
    read_per_mode_value,
    default_model: "SpotifyVisualizerSettings",
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}

    for mode in PER_MODE_TECHNICAL_MODES:
        for key, coerce in PER_MODE_BASELINE_KEYS:
            fallback = getattr(default_model, f"{mode}_{key}")
            raw = read_per_mode_value(mode, key, fallback)
            if coerce is bool:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_bool(raw, bool(fallback))
            elif coerce is int:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_int(raw, int(fallback))
            else:
                kwargs[f"{mode}_{key}"] = _coerce_live_visualizer_float(raw, float(fallback))

    for mode, key, output_key, _fallback_unused, coerce in SPECIAL_PER_MODE_KEYS:
        fallback = getattr(default_model, output_key)
        raw = read_per_mode_value(mode, key, fallback)
        if coerce is bool:
            kwargs[output_key] = _coerce_live_visualizer_bool(raw, bool(fallback))
        elif coerce is int:
            kwargs[output_key] = _coerce_live_visualizer_int(raw, int(fallback))
        else:
            kwargs[output_key] = _coerce_live_visualizer_float(raw, float(fallback))

    return kwargs


def _build_live_visualizer_mode_shared_visual_kwargs(
    read_per_mode_value,
    default_model: "SpotifyVisualizerSettings",
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    for mode in PER_MODE_TECHNICAL_MODES:
        kwargs[f"{mode}_bar_fill_color"] = deepcopy(
            read_per_mode_value(mode, "bar_fill_color", getattr(default_model, f"{mode}_bar_fill_color"))
        )
        kwargs[f"{mode}_bar_border_color"] = deepcopy(
            read_per_mode_value(mode, "bar_border_color", getattr(default_model, f"{mode}_bar_border_color"))
        )
        kwargs[f"{mode}_bar_border_opacity"] = _coerce_live_visualizer_float(
            read_per_mode_value(mode, "bar_border_opacity", getattr(default_model, f"{mode}_bar_border_opacity")),
            float(getattr(default_model, f"{mode}_bar_border_opacity")),
        )
    return kwargs


def _resolve_active_mode_technical_state(
    mode_key: str,
    per_mode_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_mode = str(mode_key).lower()
    if normalized_mode not in PER_MODE_TECHNICAL_MODES:
        normalized_mode = PER_MODE_TECHNICAL_MODES[0]

    resolved: Dict[str, Any] = {}
    for key in _ACTIVE_MODE_TECHNICAL_KEYS:
        resolved[key] = per_mode_kwargs[f"{normalized_mode}_{key}"]
    return resolved


def _resolve_active_mode_shared_visual_state(
    mode_key: str,
    per_mode_kwargs: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized_mode = str(mode_key).lower()
    if normalized_mode not in PER_MODE_TECHNICAL_MODES:
        normalized_mode = PER_MODE_TECHNICAL_MODES[0]

    resolved: Dict[str, Any] = {}
    for key in _ACTIVE_MODE_SHARED_VISUAL_KEYS:
        resolved[key] = deepcopy(per_mode_kwargs[f"{normalized_mode}_{key}"])
    return resolved


@dataclass
class SpotifyVisualizerSettings:
    """Spotify visualizer widget settings."""

    enabled: bool = False
    visualizers_enabled: bool = True
    monitor: str = "ALL"
    bar_count: int = 32
    bar_fill_color: list | None = None
    bar_border_color: list | None = None
    bar_border_opacity: float = 0.85
    spectrum_bar_fill_color: list | None = None
    spectrum_bar_border_color: list | None = None
    spectrum_bar_border_opacity: float = 0.85
    bubble_bar_fill_color: list | None = None
    bubble_bar_border_color: list | None = None
    bubble_bar_border_opacity: float = 0.85
    blob_bar_fill_color: list | None = None
    blob_bar_border_color: list | None = None
    blob_bar_border_opacity: float = 0.85
    sine_wave_bar_fill_color: list | None = None
    sine_wave_bar_border_color: list | None = None
    sine_wave_bar_border_opacity: float = 0.85
    oscilloscope_bar_fill_color: list | None = None
    oscilloscope_bar_border_color: list | None = None
    oscilloscope_bar_border_opacity: float = 0.85
    devcurve_bar_fill_color: list | None = None
    devcurve_bar_border_color: list | None = None
    devcurve_bar_border_opacity: float = 0.85
    ghosting_enabled: bool = True
    ghost_alpha: float = 0.4
    ghost_decay: float = 0.35
    adaptive_sensitivity: bool = True
    sensitivity: float = 1.0
    dynamic_floor: bool = True
    manual_floor: float = 0.12
    dynamic_range_enabled: bool = False
    agc_strength: float = 0.5
    input_gain: float = 1.0
    kick_lane_gain: float = 1.0
    transient_pulse_gain: float = 1.0
    transient_clamp: float = 1.5
    spectrum_lane_transient_mix: float = 0.65
    spectrum_dynamic_floor: bool = True
    spectrum_manual_floor: float = 0.12
    spectrum_dynamic_range_enabled: bool = False
    spectrum_agc_strength: float = 0.5
    spectrum_input_gain: float = 1.0
    spectrum_kick_lane_gain: float = 1.0
    spectrum_transient_pulse_gain: float = 1.0
    spectrum_transient_clamp: float = 1.5
    spectrum_audio_block_size: int = 512
    spectrum_adaptive_sensitivity: bool = True
    spectrum_sensitivity: float = 0.4
    spectrum_bar_count: int = 33
    bubble_dynamic_floor: bool = True
    bubble_manual_floor: float = 0.12
    bubble_dynamic_range_enabled: bool = False
    bubble_agc_strength: float = 0.5
    bubble_input_gain: float = 1.0
    bubble_kick_lane_gain: float = 1.0
    bubble_transient_pulse_gain: float = 1.0
    bubble_transient_clamp: float = 1.5
    bubble_transient_mix_bass: float = 0.75
    bubble_transient_mix_vocal: float = 0.25
    bubble_audio_block_size: int = 512
    bubble_adaptive_sensitivity: bool = True
    bubble_sensitivity: float = 0.4
    bubble_bar_count: int = 48
    blob_dynamic_floor: bool = True
    blob_manual_floor: float = 0.12
    blob_dynamic_range_enabled: bool = False
    blob_agc_strength: float = 0.5
    blob_input_gain: float = 1.0
    blob_kick_lane_gain: float = 1.0
    blob_transient_pulse_gain: float = 1.0
    blob_transient_clamp: float = 1.5
    blob_transient_mix_bass: float = 0.5
    blob_transient_mix_vocal: float = 0.35
    blob_audio_block_size: int = 512
    blob_adaptive_sensitivity: bool = True
    blob_sensitivity: float = 0.4
    blob_bar_count: int = 32
    sine_wave_dynamic_floor: bool = True
    sine_wave_manual_floor: float = 0.12
    sine_wave_dynamic_range_enabled: bool = False
    sine_wave_agc_strength: float = 0.5
    sine_wave_input_gain: float = 1.0
    sine_wave_kick_lane_gain: float = 1.0
    sine_wave_transient_pulse_gain: float = 1.0
    sine_wave_transient_clamp: float = 1.5
    sine_wave_transient_width_mix: float = 0.4
    sine_wave_audio_block_size: int = 512
    sine_wave_adaptive_sensitivity: bool = True
    sine_wave_sensitivity: float = 0.4
    sine_wave_bar_count: int = 40
    oscilloscope_dynamic_floor: bool = True
    oscilloscope_manual_floor: float = 0.12
    oscilloscope_dynamic_range_enabled: bool = False
    oscilloscope_agc_strength: float = 0.5
    oscilloscope_input_gain: float = 1.0
    oscilloscope_kick_lane_gain: float = 1.0
    oscilloscope_transient_pulse_gain: float = 1.0
    oscilloscope_transient_clamp: float = 1.5
    oscilloscope_transient_width_mix: float = 0.35
    oscilloscope_audio_block_size: int = 512
    oscilloscope_adaptive_sensitivity: bool = True
    oscilloscope_sensitivity: float = 0.4
    oscilloscope_bar_count: int = 32
    devcurve_dynamic_floor: bool = True
    devcurve_manual_floor: float = 0.12
    devcurve_dynamic_range_enabled: bool = False
    devcurve_agc_strength: float = 0.5
    devcurve_input_gain: float = 1.0
    devcurve_kick_lane_gain: float = 1.0
    devcurve_transient_pulse_gain: float = 1.0
    devcurve_transient_clamp: float = 1.5
    devcurve_audio_block_size: int = 0
    devcurve_adaptive_sensitivity: bool = True
    devcurve_sensitivity: float = 1.0
    devcurve_bar_count: int = 32
    mode: str = "bubble"
    osc_glow_enabled: bool = True
    osc_glow_intensity: float = 0.5
    osc_glow_reactivity: float = 1.0
    osc_glow_color: list = None
    osc_reactive_glow: bool = True
    osc_line_amplitude: float = 3.0
    osc_smoothing: float = 0.7
    blob_color: list = None
    blob_glow_color: list = None
    blob_edge_color: list = None
    blob_outline_color: list = None
    blob_pulse: float = 1.0
    blob_pulse_release_ms: int = 220
    blob_width: float = 1.0
    blob_size: float = 1.0
    blob_glow_intensity: float = 0.5
    blob_reactive_glow: bool = True
    blob_glow_drive_mode: str = "bass"
    osc_line_color: list = None
    osc_line_count: int = 1
    osc_line2_color: list = None
    osc_line2_glow_color: list = None
    osc_line3_color: list = None
    osc_line3_glow_color: list = None
    osc_line4_color: list = None
    osc_line4_glow_color: list = None
    osc_line5_color: list = None
    osc_line5_glow_color: list = None
    osc_line6_color: list = None
    osc_line6_glow_color: list = None
    spectrum_growth: float = 1.0
    blob_growth: float = 2.5
    osc_speed: float = 1.0
    osc_line_dim: bool = False
    osc_line_offset_bias: float = 0.0
    osc_vertical_shift: int = 0
    osc_growth: float = 1.0
    blob_reactive_deformation: float = 1.0
    blob_constant_wobble: float = 1.0
    blob_reactive_wobble: float = 1.0
    blob_stretch: float = 0.35
    blob_stage_gain: float = 1.0
    blob_core_scale: float = 1.0
    blob_core_floor_bias: float = 0.35
    blob_stage_bias: float = 0.0
    blob_stretch_tendency: float = 0.35
    blob_stretch_inner: float = 0.0
    blob_stretch_outer: float = 0.35
    spectrum_render_mode: str = "bars"
    spectrum_unique_colors: bool = True
    spectrum_rainbow_border: bool = False
    spectrum_border_radius: float = 0.0
    spectrum_link_fill_border: bool = False
    spectrum_glow_enabled: bool = False
    spectrum_glow_intensity: float = 0.55
    spectrum_glow_color: List[int] = field(default_factory=lambda: [110, 220, 255, 235])
    spectrum_ghosting_enabled: bool = True
    spectrum_ghost_alpha: float = 0.4
    spectrum_ghost_decay: float = 0.4
    spectrum_mirrored: bool = True
    spectrum_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]])
    spectrum_notch_positions_mirrored: List[List] = field(default_factory=lambda: [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]])
    spectrum_notch_positions_linear: List[List] = field(default_factory=lambda: [[0.0, "Bass"], [0.24, "Low-Mid"], [0.46, "Vocal"], [0.72, "Hi-Mid"], [1.0, "Treble"]])
    spectrum_lane_strengths_mirrored: Dict[str, float] = field(
        default_factory=lambda: dict(_SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED)
    )
    spectrum_lane_strengths_linear: Dict[str, float] = field(
        default_factory=lambda: dict(_SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR)
    )
    spectrum_wave_amplitude: float = 0.50
    spectrum_profile_floor: float = 0.12
    spectrum_drop_speed: float = 1.0
    sine_wave_growth: float = 1.0
    sine_wave_travel: int = 0
    sine_density: float = 1.0
    sine_displacement: float = 0.0
    sine_glow_enabled: bool = True
    sine_glow_intensity: float = 0.5
    sine_glow_reactivity: float = 1.0
    sine_glow_color: list = None
    sine_line_color: list = None
    sine_reactive_glow: bool = True
    sine_ghosting_enabled: bool = True
    sine_ghost_alpha: float = 0.45
    sine_ghost_decay: float = 0.3
    sine_ghost_line2_enabled: bool = True
    sine_ghost_line3_enabled: bool = True
    sine_ghost_line4_enabled: bool = True
    sine_ghost_line5_enabled: bool = True
    sine_ghost_line6_enabled: bool = True
    sine_sensitivity: float = 1.0
    sine_smoothing: float = 0.7
    sine_speed: float = 1.0
    sine_line_count: int = 1
    sine_line_offset_bias: float = 0.0
    sine_line2_color: list = None
    sine_line2_glow_color: list = None
    sine_line3_color: list = None
    sine_line3_glow_color: list = None
    sine_line4_color: list = None
    sine_line4_glow_color: list = None
    sine_line5_color: list = None
    sine_line5_glow_color: list = None
    sine_line6_color: list = None
    sine_line6_glow_color: list = None
    sine_travel_line2: int = 0
    sine_travel_line3: int = 0
    sine_travel_line4: int = 0
    sine_travel_line5: int = 0
    sine_travel_line6: int = 0
    sine_line1_shift: float = 0.0
    sine_line2_shift: float = 0.0
    sine_line3_shift: float = 0.0
    sine_line4_shift: float = 0.0
    sine_line5_shift: float = 0.0
    sine_line6_shift: float = 0.0
    sine_wave_effect: float = 0.0
    sine_vertical_shift: int = 0
    sine_micro_wobble: float = 0.0  # legacy, hidden
    sine_crawl_amount: float = 0.25
    sine_width_reaction: float = 0.0
    sine_card_adaptation: float = 0.3
    rainbow_enabled: bool = False
    rainbow_speed: float = 0.5
    osc_ghosting_enabled: bool = False
    osc_ghost_intensity: float = 0.4
    osc_ghost_line2_enabled: bool = True
    osc_ghost_line3_enabled: bool = True
    osc_ghost_line4_enabled: bool = True
    osc_ghost_line5_enabled: bool = True
    osc_ghost_line6_enabled: bool = True
    sine_heartbeat: float = 0.0
    # Bubble visualizer
    bubble_big_bass_pulse: float = 0.5
    bubble_small_freq_pulse: float = 0.5
    bubble_stream_direction: str = "up"
    bubble_stream_constant_speed: float = 0.5
    bubble_stream_speed_cap: float = 2.0
    bubble_stream_reactivity: float = 0.5
    bubble_rotation_amount: float = 0.5
    bubble_drift_amount: float = 0.5
    bubble_drift_speed: float = 0.5
    bubble_drift_frequency: float = 0.5
    bubble_drift_direction: str = "random"  # none/left/right/diagonal/swish_{horizontal,vertical}/swirl_{cw,ccw}/random
    bubble_big_count: int = 8
    bubble_small_count: int = 25
    bubble_surface_reach: float = 0.6
    bubble_bounce_big_pct: int = 70
    bubble_bounce_small_pct: int = 30
    bubble_bounce_big_speed: float = 0.8
    bubble_bounce_small_speed: float = 0.5
    bubble_bounce_same_only: bool = False
    bubble_collision_pop_mode: str = "off"  # off/one/all
    bubble_outline_color: Any = None
    bubble_specular_color: Any = None
    bubble_gradient_light: Any = None
    bubble_gradient_dark: Any = None
    bubble_pop_color: Any = None
    bubble_specular_direction: str = "top_left"  # top/bottom/left/right + diagonals
    bubble_gradient_direction: str = "top"  # gradient vector independent of specular highlight
    bubble_big_size_max: float = 0.038
    bubble_small_size_max: float = 0.018
    bubble_big_contraction_bias: float = 1.0
    bubble_big_size_clamp: float = 4.0
    bubble_big_specular_max_size: float = 2.5
    bubble_growth: float = 3.0
    devcurve_growth: float = 3.0
    bubble_tail_opacity: float = 0.3
    bubble_trail_strength: float = 0.0
    bubble_ghosting_enabled: bool = False
    bubble_ghost_alpha: float = 0.0
    bubble_ghost_decay: float = 0.4
    blob_glow_reactivity: float = 1.0
    blob_glow_max_size: float = 1.0
    blob_ghosting_enabled: bool = False
    blob_ghost_alpha: float = 0.4
    blob_ghost_decay: float = 0.3
    sine_line_dim: bool = False
    # Blob Shaper
    blob_shaper_enabled: bool = False
    blob_shape_base_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])
    blob_shape_reaction_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])
    blob_shape_energy_nodes: List[Dict[str, Any]] = field(default_factory=list)
    blob_shaper_base_strength: float = 0.5
    blob_shaper_react_strength: float = 0.5
    blob_shaper_idle_motion: float = 0.18
    blob_shaper_audio_motion: float = 1.20
    blob_topology: str = "circle"
    blob_ring_thickness: float = 0.3
    blob_inward_liquid_enabled: bool = False
    blob_inward_liquid_reactivity: float = 1.0
    blob_inward_liquid_max_size: float = 0.28
    blob_inward_liquid_color: Any = None
    # Dev Curve visualizer
    devcurve_active_layer: str = "bass"
    devcurve_layer_bass_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_vocals_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_mids_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_layer_transients_shape_nodes: List[List[float]] = field(default_factory=lambda: [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])
    devcurve_base_level: float = 0.58
    devcurve_motion_power: float = 1.0
    devcurve_idle_motion: float = 0.20
    devcurve_idle_speed: float = 0.60
    devcurve_smoothness: float = 0.55
    devcurve_layer_bass_enabled: bool = True
    devcurve_layer_bass_color: Any = None
    devcurve_layer_bass_alpha: float = 0.55
    devcurve_layer_bass_power: float = 1.0
    devcurve_layer_bass_offset: float = 0.0
    devcurve_layer_bass_outline_color: Any = None
    devcurve_layer_bass_outline_width: float = 0.006
    devcurve_layer_bass_order: int = 1
    devcurve_layer_vocals_enabled: bool = True
    devcurve_layer_vocals_color: Any = None
    devcurve_layer_vocals_alpha: float = 0.42
    devcurve_layer_vocals_power: float = 1.0
    devcurve_layer_vocals_offset: float = -0.01
    devcurve_layer_vocals_outline_color: Any = None
    devcurve_layer_vocals_outline_width: float = 0.006
    devcurve_layer_vocals_order: int = 2
    devcurve_layer_mids_enabled: bool = True
    devcurve_layer_mids_color: Any = None
    devcurve_layer_mids_alpha: float = 0.46
    devcurve_layer_mids_power: float = 1.0
    devcurve_layer_mids_offset: float = 0.01
    devcurve_layer_mids_outline_color: Any = None
    devcurve_layer_mids_outline_width: float = 0.006
    devcurve_layer_mids_order: int = 3
    devcurve_layer_transients_enabled: bool = True
    devcurve_layer_transients_color: Any = None
    devcurve_layer_transients_alpha: float = 0.66
    devcurve_layer_transients_power: float = 1.15
    devcurve_layer_transients_offset: float = 0.0
    devcurve_layer_transients_outline_color: Any = None
    devcurve_layer_transients_outline_width: float = 0.006
    devcurve_layer_transients_order: int = 4
    devcurve_ghosting_enabled: bool = False
    devcurve_ghost_alpha: float = 0.0
    devcurve_ghost_decay: float = 0.4
    devcurve_foreground_shadow_enabled: bool = False
    devcurve_foreground_shadow_alpha: float = 0.36
    devcurve_foreground_shadow_darken: float = 0.42
    devcurve_foreground_shadow_offset: float = 0.10
    devcurve_foreground_specular_enabled: bool = False
    devcurve_foreground_specular_alpha: float = 0.78
    devcurve_foreground_specular_width: float = 0.022
    devcurve_foreground_specular_offset: float = 0.028
    devcurve_foreground_specular_crest_bias: float = 1.05
    # Visualizer presets (0=Preset 1/Default, 1=Preset 2, 2=Preset 3, 3=Custom)
    preset_spectrum: int = field(default_factory=lambda: get_missing_preset_fallback_index("spectrum"))
    preset_oscilloscope: int = field(default_factory=lambda: get_missing_preset_fallback_index("oscilloscope"))
    preset_sine_wave: int = field(default_factory=lambda: get_missing_preset_fallback_index("sine_wave"))
    preset_blob: int = field(default_factory=lambda: get_missing_preset_fallback_index("blob"))
    preset_bubble: int = field(default_factory=lambda: get_missing_preset_fallback_index("bubble"))
    preset_devcurve: int = field(default_factory=lambda: get_missing_preset_fallback_index("devcurve"))

    def __post_init__(self):
        if self.osc_glow_color is None:
            self.osc_glow_color = [0, 200, 255, 230]
        if self.bar_fill_color is None:
            self.bar_fill_color = [0, 255, 128, 230]
        if self.bar_border_color is None:
            self.bar_border_color = [255, 255, 255, 230]
        for mode in PER_MODE_TECHNICAL_MODES:
            fill_attr = f"{mode}_bar_fill_color"
            border_attr = f"{mode}_bar_border_color"
            opacity_attr = f"{mode}_bar_border_opacity"
            if getattr(self, fill_attr) is None:
                setattr(self, fill_attr, list(self.bar_fill_color))
            if getattr(self, border_attr) is None:
                setattr(self, border_attr, list(self.bar_border_color))
            try:
                mode_opacity = float(getattr(self, opacity_attr))
            except Exception:
                mode_opacity = float(self.bar_border_opacity)
            setattr(self, opacity_attr, mode_opacity)
        if self.blob_color is None:
            self.blob_color = [0, 180, 255, 230]
        if self.blob_glow_color is None:
            self.blob_glow_color = [0, 140, 255, 180]
        if self.blob_edge_color is None:
            self.blob_edge_color = [100, 220, 255, 230]
        if self.blob_outline_color is None:
            self.blob_outline_color = [0, 0, 0, 0]
        if self.blob_inward_liquid_color is None:
            self.blob_inward_liquid_color = [170, 225, 255, 190]
        self.blob_glow_drive_mode = (
            "vocal" if str(self.blob_glow_drive_mode).strip().lower() == "vocal" else "bass"
        )
        if self.osc_line_color is None:
            self.osc_line_color = [255, 255, 255, 255]
        if self.osc_line2_color is None:
            self.osc_line2_color = [255, 120, 50, 230]
        if self.osc_line2_glow_color is None:
            self.osc_line2_glow_color = [255, 120, 50, 180]
        if self.osc_line3_color is None:
            self.osc_line3_color = [50, 255, 120, 230]
        if self.osc_line3_glow_color is None:
            self.osc_line3_glow_color = [50, 255, 120, 180]
        if self.osc_line4_color is None:
            self.osc_line4_color = [255, 0, 150, 230]
        if self.osc_line4_glow_color is None:
            self.osc_line4_glow_color = [255, 0, 150, 180]
        if self.osc_line5_color is None:
            self.osc_line5_color = [0, 255, 200, 230]
        if self.osc_line5_glow_color is None:
            self.osc_line5_glow_color = [0, 255, 200, 180]
        if self.osc_line6_color is None:
            self.osc_line6_color = [200, 100, 255, 230]
        if self.osc_line6_glow_color is None:
            self.osc_line6_glow_color = [200, 100, 255, 180]
        if self.sine_glow_color is None:
            self.sine_glow_color = [0, 200, 255, 230]
        if self.sine_line_color is None:
            self.sine_line_color = [255, 255, 255, 255]
        if self.sine_line2_color is None:
            self.sine_line2_color = [255, 255, 255, 230]
        if self.sine_line2_glow_color is None:
            self.sine_line2_glow_color = [7, 114, 255, 180]
        if self.sine_line3_color is None:
            self.sine_line3_color = [255, 255, 255, 230]
        if self.sine_line3_glow_color is None:
            self.sine_line3_glow_color = [14, 159, 255, 180]
        if self.sine_line4_color is None:
            self.sine_line4_color = [255, 120, 50, 230]
        if self.sine_line4_glow_color is None:
            self.sine_line4_glow_color = [255, 120, 50, 180]
        if self.sine_line5_color is None:
            self.sine_line5_color = [50, 255, 120, 230]
        if self.sine_line5_glow_color is None:
            self.sine_line5_glow_color = [50, 255, 120, 180]
        if self.sine_line6_color is None:
            self.sine_line6_color = [255, 0, 150, 230]
        if self.sine_line6_glow_color is None:
            self.sine_line6_glow_color = [255, 0, 150, 180]
        if self.bubble_outline_color is None:
            self.bubble_outline_color = [255, 255, 255, 230]
        if self.bubble_specular_color is None:
            self.bubble_specular_color = [255, 255, 255, 255]
        if self.bubble_gradient_light is None:
            self.bubble_gradient_light = [210, 170, 120, 255]
        if self.bubble_gradient_dark is None:
            self.bubble_gradient_dark = [80, 60, 50, 255]
        if self.bubble_pop_color is None:
            self.bubble_pop_color = [255, 255, 255, 180]
        if self.devcurve_layer_bass_color is None:
            self.devcurve_layer_bass_color = [82, 167, 255, 230]
        if self.devcurve_layer_vocals_color is None:
            self.devcurve_layer_vocals_color = [136, 190, 255, 220]
        if self.devcurve_layer_mids_color is None:
            self.devcurve_layer_mids_color = [100, 145, 255, 220]
        if self.devcurve_layer_transients_color is None:
            self.devcurve_layer_transients_color = [215, 240, 255, 240]
        if self.devcurve_layer_bass_outline_color is None:
            self.devcurve_layer_bass_outline_color = [255, 255, 255, 255]
        if self.devcurve_layer_vocals_outline_color is None:
            self.devcurve_layer_vocals_outline_color = [255, 255, 255, 255]
        if self.devcurve_layer_mids_outline_color is None:
            self.devcurve_layer_mids_outline_color = [255, 255, 255, 255]
        if self.devcurve_layer_transients_outline_color is None:
            self.devcurve_layer_transients_outline_color = [255, 255, 255, 255]
        self.devcurve_active_layer = (
            str(self.devcurve_active_layer).strip().lower()
            if str(self.devcurve_active_layer).strip().lower() in {"bass", "vocals", "mids", "transients"}
            else "bass"
        )
        self.devcurve_layer_bass_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_bass_outline_width)))
        self.devcurve_layer_vocals_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_vocals_outline_width)))
        self.devcurve_layer_mids_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_mids_outline_width)))
        self.devcurve_layer_transients_outline_width = max(0.001, min(0.020, float(self.devcurve_layer_transients_outline_width)))
        for attr in (
            "devcurve_layer_bass_outline_color",
            "devcurve_layer_vocals_outline_color",
            "devcurve_layer_mids_outline_color",
            "devcurve_layer_transients_outline_color",
        ):
            value = list(getattr(self, attr))
            while len(value) < 4:
                value.append(255)
            value[3] = 255
            setattr(self, attr, value[:4])
        self.devcurve_smoothness = max(0.0, min(1.0, float(self.devcurve_smoothness)))
        self.devcurve_foreground_shadow_alpha = max(0.0, min(1.0, float(self.devcurve_foreground_shadow_alpha)))
        self.devcurve_foreground_shadow_darken = max(0.0, min(1.0, float(self.devcurve_foreground_shadow_darken)))
        self.devcurve_foreground_shadow_offset = max(0.0, min(0.45, float(self.devcurve_foreground_shadow_offset)))
        self.devcurve_foreground_specular_alpha = max(0.0, min(1.0, float(self.devcurve_foreground_specular_alpha)))
        self.devcurve_foreground_specular_width = max(0.002, min(0.120, float(self.devcurve_foreground_specular_width)))
        self.devcurve_foreground_specular_offset = max(-0.20, min(0.20, float(self.devcurve_foreground_specular_offset)))
        self.devcurve_foreground_specular_crest_bias = max(0.0, min(2.0, float(self.devcurve_foreground_specular_crest_bias)))
        if not isinstance(self.devcurve_layer_bass_shape_nodes, list) or not self.devcurve_layer_bass_shape_nodes:
            self.devcurve_layer_bass_shape_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        if not isinstance(self.devcurve_layer_vocals_shape_nodes, list) or not self.devcurve_layer_vocals_shape_nodes:
            self.devcurve_layer_vocals_shape_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        if not isinstance(self.devcurve_layer_mids_shape_nodes, list) or not self.devcurve_layer_mids_shape_nodes:
            self.devcurve_layer_mids_shape_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        if not isinstance(self.devcurve_layer_transients_shape_nodes, list) or not self.devcurve_layer_transients_shape_nodes:
            self.devcurve_layer_transients_shape_nodes = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]
        _order_pairs = [
            ("devcurve_layer_bass_order", int(self.devcurve_layer_bass_order)),
            ("devcurve_layer_vocals_order", int(self.devcurve_layer_vocals_order)),
            ("devcurve_layer_mids_order", int(self.devcurve_layer_mids_order)),
            ("devcurve_layer_transients_order", int(self.devcurve_layer_transients_order)),
        ]
        _order_pairs.sort(key=lambda item: item[1])
        for idx, (attr_name, _raw_rank) in enumerate(_order_pairs, start=1):
            setattr(self, attr_name, idx)

    @classmethod
    def from_settings(cls, settings: "SettingsManager", prefix: str = "widgets.spotify_visualizer") -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from SettingsManager."""
        get = settings.get
        try:
            bubble_gradient_semantics_version = int(get(f"{prefix}.bubble_gradient_semantics_version", 0))
        except (TypeError, ValueError):
            bubble_gradient_semantics_version = 0
        _defaults_model = cls()

        sentinel = object()

        def _mode_value(mode: str, key: str, fallback: Any) -> Any:
            attr = f"{prefix}.{mode}_{key}"
            raw = get(attr, sentinel)
            if raw is sentinel:
                return fallback
            return raw

        _mode_kwargs = _build_live_visualizer_mode_kwargs(_mode_value, _defaults_model)
        _mode_visual_kwargs = _build_live_visualizer_mode_shared_visual_kwargs(_mode_value, _defaults_model)
        _preset_kwargs = resolve_all_preset_indices_from_getter(get, prefix=prefix)
        _active_mode = coerce_visualizer_mode_id(str(get(f"{prefix}.mode", "bubble")))
        _active_technical = _resolve_active_mode_technical_state(
            _active_mode,
            _mode_kwargs,
        )
        _active_visuals = _resolve_active_mode_shared_visual_state(
            _active_mode,
            _mode_visual_kwargs,
        )
        _rainbow_kwargs = resolve_visualizer_active_mode_rainbow_state(
            lambda key, default: _mode_value(
                _active_mode,
                key,
                get(f"{prefix}.{key}", default),
            )
        )

        return cls(
            enabled=get(f"{prefix}.enabled", False),
            monitor=get(f"{prefix}.monitor", "ALL"),
            bar_count=int(_active_technical["bar_count"]),
            ghosting_enabled=bool(get(f"{prefix}.spectrum_ghosting_enabled", True)),
            ghost_alpha=float(get(f"{prefix}.spectrum_ghost_alpha", 0.4)),
            ghost_decay=float(get(f"{prefix}.spectrum_ghost_decay", 0.35)),
            adaptive_sensitivity=bool(_active_technical["adaptive_sensitivity"]),
            sensitivity=float(_active_technical["sensitivity"]),
            dynamic_floor=bool(_active_technical["dynamic_floor"]),
            manual_floor=float(_active_technical["manual_floor"]),
            dynamic_range_enabled=bool(_active_technical["dynamic_range_enabled"]),
            agc_strength=float(_active_technical["agc_strength"]),
            input_gain=float(_active_technical["input_gain"]),
            kick_lane_gain=float(_active_technical["kick_lane_gain"]),
            transient_pulse_gain=float(_active_technical["transient_pulse_gain"]),
            transient_clamp=float(_active_technical["transient_clamp"]),
            bar_fill_color=_active_visuals["bar_fill_color"],
            bar_border_color=_active_visuals["bar_border_color"],
            bar_border_opacity=float(_active_visuals["bar_border_opacity"]),
            mode=_active_mode,
            osc_glow_enabled=get(f"{prefix}.osc_glow_enabled", True),
            osc_glow_intensity=float(get(f"{prefix}.osc_glow_intensity", 0.5)),
            osc_glow_reactivity=float(get(f"{prefix}.osc_glow_reactivity", get(f"{prefix}.osc_glow_size", 1.0))),
            osc_glow_color=get(f"{prefix}.osc_glow_color", [0, 200, 255, 230]),
            osc_reactive_glow=get(f"{prefix}.osc_reactive_glow", True),
            osc_line_amplitude=float(
                get(f"{prefix}.osc_line_amplitude", 3.0)
            ),
            osc_smoothing=float(get(f"{prefix}.osc_smoothing", 0.7)),
            blob_color=get(f"{prefix}.blob_color", [0, 180, 255, 230]),
            blob_glow_color=get(f"{prefix}.blob_glow_color", [0, 140, 255, 180]),
            blob_edge_color=get(f"{prefix}.blob_edge_color", [100, 220, 255, 230]),
            blob_outline_color=get(f"{prefix}.blob_outline_color", [0, 0, 0, 0]),
            blob_pulse=float(get(f"{prefix}.blob_pulse", 1.0)),
            blob_pulse_release_ms=int(get(f"{prefix}.blob_pulse_release_ms", 220)),
            blob_width=float(get(f"{prefix}.blob_width", 1.0)),
            blob_size=float(get(f"{prefix}.blob_size", 1.0)),
            blob_glow_intensity=float(get(f"{prefix}.blob_glow_intensity", 0.5)),
            blob_reactive_glow=get(f"{prefix}.blob_reactive_glow", True),
            blob_glow_drive_mode=str(get(f"{prefix}.blob_glow_drive_mode", "bass")),
            osc_line_color=get(f"{prefix}.osc_line_color", [255, 255, 255, 255]),
            osc_line_count=int(get(f"{prefix}.osc_line_count", 1)),
            osc_line2_color=get(f"{prefix}.osc_line2_color", [255, 120, 50, 230]),
            osc_line2_glow_color=get(f"{prefix}.osc_line2_glow_color", [255, 120, 50, 180]),
            osc_line3_color=get(f"{prefix}.osc_line3_color", [50, 255, 120, 230]),
            osc_line3_glow_color=get(f"{prefix}.osc_line3_glow_color", [50, 255, 120, 180]),
            osc_line4_color=get(f"{prefix}.osc_line4_color", [255, 0, 150, 230]),
            osc_line4_glow_color=get(f"{prefix}.osc_line4_glow_color", [255, 0, 150, 180]),
            osc_line5_color=get(f"{prefix}.osc_line5_color", [0, 255, 200, 230]),
            osc_line5_glow_color=get(f"{prefix}.osc_line5_glow_color", [0, 255, 200, 180]),
            osc_line6_color=get(f"{prefix}.osc_line6_color", [200, 100, 255, 230]),
            osc_line6_glow_color=get(f"{prefix}.osc_line6_glow_color", [200, 100, 255, 180]),
            spectrum_growth=float(get(f"{prefix}.spectrum_growth", 1.0)),
            blob_growth=float(get(f"{prefix}.blob_growth", 2.5)),
            osc_speed=float(get(f"{prefix}.osc_speed", 1.0)),
            osc_line_dim=get(f"{prefix}.osc_line_dim", False),
            osc_line_offset_bias=float(get(f"{prefix}.osc_line_offset_bias", 0.0)),
            osc_vertical_shift=get(f"{prefix}.osc_vertical_shift", False),
            osc_growth=float(get(f"{prefix}.osc_growth", 1.0)),
            blob_reactive_deformation=float(get(f"{prefix}.blob_reactive_deformation", 1.0)),
            blob_constant_wobble=float(get(f"{prefix}.blob_constant_wobble", 1.0)),
            blob_reactive_wobble=float(get(f"{prefix}.blob_reactive_wobble", 1.0)),
            blob_stretch=float(get(f"{prefix}.blob_stretch", 0.35)),
            blob_stage_gain=float(get(f"{prefix}.blob_stage_gain", 1.0)),
            blob_core_scale=float(get(f"{prefix}.blob_core_scale", 1.0)),
            blob_core_floor_bias=float(get(f"{prefix}.blob_core_floor_bias", 0.35)),
            blob_stage_bias=float(get(f"{prefix}.blob_stage_bias", 0.0)),
            blob_stretch_tendency=float(get(f"{prefix}.blob_stretch_tendency", get(f"{prefix}.blob_stretch", 0.35))),
            blob_stretch_inner=float(get(f"{prefix}.blob_stretch_inner", 0.0)),
            blob_stretch_outer=float(get(f"{prefix}.blob_stretch_outer", get(f"{prefix}.blob_stretch", 0.35))),
            spectrum_render_mode=resolve_spectrum_render_mode(
                lambda key, default=None: get(f"{prefix}.{key}", default)
            ),
            spectrum_unique_colors=resolve_spectrum_unique_colors(
                lambda key, default=None: get(f"{prefix}.{key}", default)
            ),
            spectrum_rainbow_border=bool(get(f"{prefix}.spectrum_rainbow_border", False)),
            spectrum_border_radius=float(get(f"{prefix}.spectrum_border_radius", 0.0)),
            spectrum_link_fill_border=bool(get(f"{prefix}.spectrum_link_fill_border", False)),
            spectrum_glow_enabled=bool(get(f"{prefix}.spectrum_glow_enabled", False)),
            spectrum_glow_intensity=float(get(f"{prefix}.spectrum_glow_intensity", 0.55)),
            spectrum_glow_color=list(get(f"{prefix}.spectrum_glow_color", [110, 220, 255, 235])),
            spectrum_ghosting_enabled=bool(get(f"{prefix}.spectrum_ghosting_enabled", True)),
            spectrum_ghost_alpha=float(get(f"{prefix}.spectrum_ghost_alpha", 0.4)),
            spectrum_ghost_decay=float(get(f"{prefix}.spectrum_ghost_decay", 0.35)),
            spectrum_mirrored=bool(get(f"{prefix}.spectrum_mirrored", True)),
            spectrum_shape_nodes=list(
                get(
                    f"{prefix}.spectrum_shape_nodes",
                    [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]],
                )
            ),
            spectrum_notch_positions_mirrored=list(
                get(
                    f"{prefix}.spectrum_notch_positions_mirrored",
                    [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]],
                )
            ),
            spectrum_notch_positions_linear=_normalize_spectrum_linear_notches(
                get(
                    f"{prefix}.spectrum_notch_positions_linear",
                    _SPECTRUM_DEFAULT_NOTCHES_LINEAR,
                )
            ),
            spectrum_lane_strengths_mirrored=_normalize_spectrum_lane_strengths(
                get(f"{prefix}.spectrum_lane_strengths_mirrored", _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED),
                _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
            ),
            spectrum_lane_strengths_linear=_normalize_spectrum_lane_strengths(
                get(f"{prefix}.spectrum_lane_strengths_linear", _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR),
                _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
            ),
            spectrum_wave_amplitude=float(get(f"{prefix}.spectrum_wave_amplitude", 0.50)),
            spectrum_profile_floor=float(get(f"{prefix}.spectrum_profile_floor", 0.12)),
            spectrum_drop_speed=float(get(f"{prefix}.spectrum_drop_speed", 1.0)),
            sine_wave_growth=float(get(f"{prefix}.sine_wave_growth", 1.0)),
            sine_wave_travel=int(get(f"{prefix}.sine_wave_travel", 0)),
            sine_density=float(get(f"{prefix}.sine_density", 1.0)),
            sine_displacement=float(get(f"{prefix}.sine_displacement", 0.0)),
            sine_glow_enabled=get(f"{prefix}.sine_glow_enabled", True),
            sine_glow_intensity=float(get(f"{prefix}.sine_glow_intensity", 0.5)),
            sine_glow_reactivity=float(get(f"{prefix}.sine_glow_reactivity", get(f"{prefix}.sine_glow_size", 1.0))),
            sine_glow_color=get(f"{prefix}.sine_glow_color", [0, 200, 255, 230]),
            sine_line_color=get(f"{prefix}.sine_line_color", [255, 255, 255, 255]),
            sine_reactive_glow=get(f"{prefix}.sine_reactive_glow", True),
            sine_ghosting_enabled=get(f"{prefix}.sine_ghosting_enabled", True),
            sine_ghost_alpha=float(get(f"{prefix}.sine_ghost_alpha", 0.45)),
            sine_ghost_decay=float(get(f"{prefix}.sine_ghost_decay", 0.3)),
            sine_ghost_line2_enabled=bool(get(f"{prefix}.sine_ghost_line2_enabled", True)),
            sine_ghost_line3_enabled=bool(get(f"{prefix}.sine_ghost_line3_enabled", True)),
            sine_ghost_line4_enabled=bool(get(f"{prefix}.sine_ghost_line4_enabled", True)),
            sine_ghost_line5_enabled=bool(get(f"{prefix}.sine_ghost_line5_enabled", True)),
            sine_ghost_line6_enabled=bool(get(f"{prefix}.sine_ghost_line6_enabled", True)),
            sine_sensitivity=float(get(f"{prefix}.sine_sensitivity", 1.0)),
            sine_smoothing=float(get(f"{prefix}.sine_smoothing", 0.7)),
            sine_speed=float(get(f"{prefix}.sine_speed", 1.0)),
            sine_line_count=int(get(f"{prefix}.sine_line_count", 1)),
            sine_line_offset_bias=float(get(f"{prefix}.sine_line_offset_bias", 0.0)),
            sine_line2_color=get(f"{prefix}.sine_line2_color", [255, 255, 255, 230]),
            sine_line2_glow_color=get(f"{prefix}.sine_line2_glow_color", [7, 114, 255, 180]),
            sine_line3_color=get(f"{prefix}.sine_line3_color", [255, 255, 255, 230]),
            sine_line3_glow_color=get(f"{prefix}.sine_line3_glow_color", [14, 159, 255, 180]),
            sine_line4_color=get(f"{prefix}.sine_line4_color", [255, 120, 50, 230]),
            sine_line4_glow_color=get(f"{prefix}.sine_line4_glow_color", [255, 120, 50, 180]),
            sine_line5_color=get(f"{prefix}.sine_line5_color", [50, 255, 120, 230]),
            sine_line5_glow_color=get(f"{prefix}.sine_line5_glow_color", [50, 255, 120, 180]),
            sine_line6_color=get(f"{prefix}.sine_line6_color", [255, 0, 150, 230]),
            sine_line6_glow_color=get(f"{prefix}.sine_line6_glow_color", [255, 0, 150, 180]),
            sine_travel_line2=int(get(f"{prefix}.sine_travel_line2", 0)),
            sine_travel_line3=int(get(f"{prefix}.sine_travel_line3", 0)),
            sine_travel_line4=int(get(f"{prefix}.sine_travel_line4", 0)),
            sine_travel_line5=int(get(f"{prefix}.sine_travel_line5", 0)),
            sine_travel_line6=int(get(f"{prefix}.sine_travel_line6", 0)),
            sine_line1_shift=float(get(f"{prefix}.sine_line1_shift", 0.0)),
            sine_line2_shift=float(get(f"{prefix}.sine_line2_shift", 0.0)),
            sine_line3_shift=float(get(f"{prefix}.sine_line3_shift", 0.0)),
            sine_line4_shift=float(get(f"{prefix}.sine_line4_shift", 0.0)),
            sine_line5_shift=float(get(f"{prefix}.sine_line5_shift", 0.0)),
            sine_line6_shift=float(get(f"{prefix}.sine_line6_shift", 0.0)),
            sine_wave_effect=float(get(f"{prefix}.sine_wave_effect", get(f"{prefix}.sine_wobble_amount", 0.0))),
            sine_vertical_shift=int(get(f"{prefix}.sine_vertical_shift", 0)),
            sine_micro_wobble=float(get(f"{prefix}.sine_micro_wobble", 0.0)),
            sine_crawl_amount=float(get(f"{prefix}.sine_crawl_amount", 0.25)),
            sine_width_reaction=float(get(f"{prefix}.sine_width_reaction", 0.0)),
            sine_card_adaptation=float(get(f"{prefix}.sine_card_adaptation", 0.3)),
            rainbow_enabled=_rainbow_kwargs["rainbow_enabled"],
            rainbow_speed=_rainbow_kwargs["rainbow_speed"],
            osc_ghosting_enabled=bool(get(f"{prefix}.osc_ghosting_enabled", False)),
            osc_ghost_intensity=float(get(f"{prefix}.osc_ghost_intensity", 0.4)),
            osc_ghost_line2_enabled=bool(get(f"{prefix}.osc_ghost_line2_enabled", True)),
            osc_ghost_line3_enabled=bool(get(f"{prefix}.osc_ghost_line3_enabled", True)),
            osc_ghost_line4_enabled=bool(get(f"{prefix}.osc_ghost_line4_enabled", True)),
            osc_ghost_line5_enabled=bool(get(f"{prefix}.osc_ghost_line5_enabled", True)),
            osc_ghost_line6_enabled=bool(get(f"{prefix}.osc_ghost_line6_enabled", True)),
            sine_heartbeat=float(get(f"{prefix}.sine_heartbeat", 0.0)),
            # Bubble
            bubble_big_bass_pulse=float(get(f"{prefix}.bubble_big_bass_pulse", 0.5)),
            bubble_small_freq_pulse=float(get(f"{prefix}.bubble_small_freq_pulse", 0.5)),
            bubble_stream_direction=str(get(f"{prefix}.bubble_stream_direction", "up")),
            bubble_stream_constant_speed=float(
                get(
                    f"{prefix}.bubble_stream_constant_speed",
                    get(f"{prefix}.bubble_stream_speed", 0.5),
                )
            ),
            bubble_stream_speed_cap=float(
                get(
                    f"{prefix}.bubble_stream_speed_cap",
                    get(f"{prefix}.bubble_stream_speed", 2.0),
                )
            ),
            bubble_stream_reactivity=float(get(f"{prefix}.bubble_stream_reactivity", 0.5)),
            bubble_rotation_amount=float(get(f"{prefix}.bubble_rotation_amount", 0.5)),
            bubble_drift_amount=float(get(f"{prefix}.bubble_drift_amount", 0.5)),
            bubble_drift_speed=float(get(f"{prefix}.bubble_drift_speed", 0.5)),
            bubble_drift_frequency=float(get(f"{prefix}.bubble_drift_frequency", 0.5)),
            bubble_drift_direction=str(get(f"{prefix}.bubble_drift_direction", "random")),
            bubble_big_count=int(get(f"{prefix}.bubble_big_count", 8)),
            bubble_small_count=int(get(f"{prefix}.bubble_small_count", 25)),
            bubble_surface_reach=float(get(f"{prefix}.bubble_surface_reach", 0.6)),
            bubble_bounce_big_pct=int(get(f"{prefix}.bubble_bounce_big_pct", 70)),
            bubble_bounce_small_pct=int(get(f"{prefix}.bubble_bounce_small_pct", 30)),
                bubble_bounce_big_speed=float(get(f"{prefix}.bubble_bounce_big_speed", 0.8)),
                bubble_bounce_small_speed=float(get(f"{prefix}.bubble_bounce_small_speed", 0.5)),
                bubble_bounce_same_only=bool(get(f"{prefix}.bubble_bounce_same_only", False)),
                bubble_collision_pop_mode=str(get(f"{prefix}.bubble_collision_pop_mode", "off")).strip().lower(),
            bubble_outline_color=get(f"{prefix}.bubble_outline_color", [255, 255, 255, 230]),
            bubble_specular_color=get(f"{prefix}.bubble_specular_color", [255, 255, 255, 255]),
            bubble_gradient_light=get(f"{prefix}.bubble_gradient_light", [210, 170, 120, 255]),
            bubble_gradient_dark=get(f"{prefix}.bubble_gradient_dark", [80, 60, 50, 255]),
            bubble_pop_color=get(f"{prefix}.bubble_pop_color", [255, 255, 255, 180]),
            bubble_specular_direction=normalize_bubble_specular_direction(
                get(f"{prefix}.bubble_specular_direction", "top_left")
            ),
            bubble_gradient_direction=resolve_bubble_gradient_direction(
                get(f"{prefix}.bubble_gradient_direction", "top"),
                semantics_version=bubble_gradient_semantics_version,
                default="top",
            ),
            bubble_big_size_max=float(get(f"{prefix}.bubble_big_size_max", 0.038)),
            bubble_small_size_max=float(get(f"{prefix}.bubble_small_size_max", 0.018)),
            bubble_big_contraction_bias=float(get(f"{prefix}.bubble_big_contraction_bias", 1.0)),
            bubble_big_size_clamp=float(get(f"{prefix}.bubble_big_size_clamp", 4.0)),
            bubble_big_specular_max_size=float(get(f"{prefix}.bubble_big_specular_max_size", 2.5)),
            bubble_growth=float(get(f"{prefix}.bubble_growth", 3.0)),
            devcurve_growth=float(get(f"{prefix}.devcurve_growth", 3.0)),
            bubble_trail_strength=float(get(f"{prefix}.bubble_trail_strength", 0.0)),
            bubble_tail_opacity=float(get(f"{prefix}.bubble_tail_opacity", 0.0)),
            bubble_ghosting_enabled=bool(get(f"{prefix}.bubble_ghosting_enabled", False)),
            bubble_ghost_alpha=float(get(f"{prefix}.bubble_ghost_alpha", 0.0)),
            bubble_ghost_decay=float(get(f"{prefix}.bubble_ghost_decay", 0.4)),
            blob_glow_reactivity=float(get(f"{prefix}.blob_glow_reactivity", 1.0)),
            blob_glow_max_size=float(get(f"{prefix}.blob_glow_max_size", 1.0)),
            blob_ghosting_enabled=bool(get(f"{prefix}.blob_ghosting_enabled", False)),
            blob_ghost_alpha=float(get(f"{prefix}.blob_ghost_alpha", 0.4)),
            blob_ghost_decay=float(get(f"{prefix}.blob_ghost_decay", 0.3)),
            blob_shaper_enabled=bool(get(f"{prefix}.blob_shaper_enabled", False)),
            blob_shape_base_nodes=list(get(f"{prefix}.blob_shape_base_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
            blob_shape_reaction_nodes=list(get(f"{prefix}.blob_shape_reaction_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
            blob_shape_energy_nodes=list(get(f"{prefix}.blob_shape_energy_nodes", [])),
            blob_shaper_base_strength=float(get(f"{prefix}.blob_shaper_base_strength", 0.5)),
            blob_shaper_react_strength=float(get(f"{prefix}.blob_shaper_react_strength", 0.5)),
            blob_shaper_idle_motion=float(get(f"{prefix}.blob_shaper_idle_motion", 0.18)),
            blob_shaper_audio_motion=float(get(f"{prefix}.blob_shaper_audio_motion", 1.20)),
            blob_topology=str(get(f"{prefix}.blob_topology", "circle")),
            blob_ring_thickness=float(get(f"{prefix}.blob_ring_thickness", 0.3)),
            blob_inward_liquid_enabled=bool(get(f"{prefix}.blob_inward_liquid_enabled", False)),
            blob_inward_liquid_reactivity=float(get(f"{prefix}.blob_inward_liquid_reactivity", 1.0)),
            blob_inward_liquid_max_size=float(get(f"{prefix}.blob_inward_liquid_max_size", 0.28)),
            blob_inward_liquid_color=get(f"{prefix}.blob_inward_liquid_color", [170, 225, 255, 190]),
            # Dev Curve
            devcurve_active_layer=str(get(f"{prefix}.devcurve_active_layer", "bass")),
            devcurve_layer_bass_shape_nodes=list(get(f"{prefix}.devcurve_layer_bass_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_vocals_shape_nodes=list(get(f"{prefix}.devcurve_layer_vocals_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_mids_shape_nodes=list(get(f"{prefix}.devcurve_layer_mids_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_transients_shape_nodes=list(get(f"{prefix}.devcurve_layer_transients_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_base_level=float(get(f"{prefix}.devcurve_base_level", 0.58)),
            devcurve_motion_power=float(get(f"{prefix}.devcurve_motion_power", 1.0)),
            devcurve_idle_motion=float(get(f"{prefix}.devcurve_idle_motion", 0.20)),
            devcurve_idle_speed=float(get(f"{prefix}.devcurve_idle_speed", 0.60)),
            devcurve_smoothness=float(get(f"{prefix}.devcurve_smoothness", 0.55)),
            devcurve_layer_bass_enabled=bool(get(f"{prefix}.devcurve_layer_bass_enabled", True)),
            devcurve_layer_bass_color=get(f"{prefix}.devcurve_layer_bass_color", [82, 167, 255, 230]),
            devcurve_layer_bass_alpha=float(get(f"{prefix}.devcurve_layer_bass_alpha", 0.55)),
            devcurve_layer_bass_power=float(get(f"{prefix}.devcurve_layer_bass_power", 1.0)),
            devcurve_layer_bass_offset=float(get(f"{prefix}.devcurve_layer_bass_offset", 0.0)),
            devcurve_layer_bass_outline_color=get(f"{prefix}.devcurve_layer_bass_outline_color", [255, 255, 255, 255]),
            devcurve_layer_bass_outline_width=float(get(f"{prefix}.devcurve_layer_bass_outline_width", 0.006)),
            devcurve_layer_bass_order=int(get(f"{prefix}.devcurve_layer_bass_order", 1)),
            devcurve_layer_vocals_enabled=bool(get(f"{prefix}.devcurve_layer_vocals_enabled", True)),
            devcurve_layer_vocals_color=get(f"{prefix}.devcurve_layer_vocals_color", [136, 190, 255, 220]),
            devcurve_layer_vocals_alpha=float(get(f"{prefix}.devcurve_layer_vocals_alpha", 0.42)),
            devcurve_layer_vocals_power=float(get(f"{prefix}.devcurve_layer_vocals_power", 1.0)),
            devcurve_layer_vocals_offset=float(get(f"{prefix}.devcurve_layer_vocals_offset", -0.01)),
            devcurve_layer_vocals_outline_color=get(f"{prefix}.devcurve_layer_vocals_outline_color", [255, 255, 255, 255]),
            devcurve_layer_vocals_outline_width=float(get(f"{prefix}.devcurve_layer_vocals_outline_width", 0.006)),
            devcurve_layer_vocals_order=int(get(f"{prefix}.devcurve_layer_vocals_order", 2)),
            devcurve_layer_mids_enabled=bool(get(f"{prefix}.devcurve_layer_mids_enabled", True)),
            devcurve_layer_mids_color=get(f"{prefix}.devcurve_layer_mids_color", [100, 145, 255, 220]),
            devcurve_layer_mids_alpha=float(get(f"{prefix}.devcurve_layer_mids_alpha", 0.46)),
            devcurve_layer_mids_power=float(get(f"{prefix}.devcurve_layer_mids_power", 1.0)),
            devcurve_layer_mids_offset=float(get(f"{prefix}.devcurve_layer_mids_offset", 0.01)),
            devcurve_layer_mids_outline_color=get(f"{prefix}.devcurve_layer_mids_outline_color", [255, 255, 255, 255]),
            devcurve_layer_mids_outline_width=float(get(f"{prefix}.devcurve_layer_mids_outline_width", 0.006)),
            devcurve_layer_mids_order=int(get(f"{prefix}.devcurve_layer_mids_order", 3)),
            devcurve_layer_transients_enabled=bool(get(f"{prefix}.devcurve_layer_transients_enabled", True)),
            devcurve_layer_transients_color=get(f"{prefix}.devcurve_layer_transients_color", [215, 240, 255, 240]),
            devcurve_layer_transients_alpha=float(get(f"{prefix}.devcurve_layer_transients_alpha", 0.66)),
            devcurve_layer_transients_power=float(get(f"{prefix}.devcurve_layer_transients_power", 1.15)),
            devcurve_layer_transients_offset=float(get(f"{prefix}.devcurve_layer_transients_offset", 0.0)),
            devcurve_layer_transients_outline_color=get(f"{prefix}.devcurve_layer_transients_outline_color", [255, 255, 255, 255]),
            devcurve_layer_transients_outline_width=float(get(f"{prefix}.devcurve_layer_transients_outline_width", 0.006)),
            devcurve_layer_transients_order=int(get(f"{prefix}.devcurve_layer_transients_order", 4)),
            devcurve_ghosting_enabled=bool(get(f"{prefix}.devcurve_ghosting_enabled", False)),
            devcurve_ghost_alpha=float(get(f"{prefix}.devcurve_ghost_alpha", 0.0)),
            devcurve_ghost_decay=float(get(f"{prefix}.devcurve_ghost_decay", 0.4)),
            devcurve_foreground_shadow_enabled=bool(get(f"{prefix}.devcurve_foreground_shadow_enabled", False)),
            devcurve_foreground_shadow_alpha=float(get(f"{prefix}.devcurve_foreground_shadow_alpha", 0.36)),
            devcurve_foreground_shadow_darken=float(get(f"{prefix}.devcurve_foreground_shadow_darken", 0.42)),
            devcurve_foreground_shadow_offset=float(get(f"{prefix}.devcurve_foreground_shadow_offset", 0.10)),
            devcurve_foreground_specular_enabled=bool(get(f"{prefix}.devcurve_foreground_specular_enabled", False)),
            devcurve_foreground_specular_alpha=float(get(f"{prefix}.devcurve_foreground_specular_alpha", 0.78)),
            devcurve_foreground_specular_width=float(get(f"{prefix}.devcurve_foreground_specular_width", 0.022)),
            devcurve_foreground_specular_offset=float(get(f"{prefix}.devcurve_foreground_specular_offset", 0.028)),
            devcurve_foreground_specular_crest_bias=float(get(f"{prefix}.devcurve_foreground_specular_crest_bias", 1.05)),
            sine_line_dim=bool(get(f"{prefix}.sine_line_dim", False)),
            **_preset_kwargs,
            **_mode_kwargs,
            **_mode_visual_kwargs,
        )

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        prefix: str = "widgets.spotify_visualizer",
        *,
        apply_preset_overlay: bool = True,
        resolve_preset_indices: bool = True,
    ) -> "SpotifyVisualizerSettings":
        """Load Spotify visualizer settings from a plain mapping (e.g., widgets dict)."""
        # Apply visualizer preset overlay before reading individual fields.
        # For non-Custom presets with a non-empty settings dict, the preset
        # values override the stored user values.  Custom (index 3) and empty
        # preset dicts are no-ops so existing behaviour is fully preserved.
        _raw = migrate_legacy_global_visual_keys(
            migrate_legacy_global_technical_keys(dict(data), prefix=prefix),
            prefix=prefix,
        )
        _mode = coerce_visualizer_mode_id(
            _raw.get("mode", _raw.get(f"{prefix}.mode", "bubble"))
        )
        bubble_gradient_semantics_version = get_bubble_gradient_semantics_version(_raw, prefix=prefix)
        if apply_preset_overlay:
            from core.settings.visualizer_presets import apply_preset_to_config

            _preset_idx = resolve_preset_index_from_mapping(str(_mode), _raw, prefix=prefix)
            _raw = apply_preset_to_config(str(_mode), _preset_idx, _raw)

        def _get(key: str, default: Any) -> Any:
            dotted = f"{prefix}.{key}"
            # accept both dotted (full key) and plain key inside section mapping
            if dotted in _raw:
                return _raw.get(dotted, default)
            return _raw.get(key, default)

        def _get_mode_value(base_key: str, default: Any) -> Any:
            sentinel = object()
            for prefix_token in get_setting_prefixes(str(_mode)):
                value = _get(f"{prefix_token}{base_key}", sentinel)
                if value is not sentinel:
                    return value
            if _mode:
                value = _get(f"{_mode}_{base_key}", sentinel)
                if value is not sentinel:
                    return value
            return _get(base_key, default)

        def _get_per_mode_value(mode: str, base_key: str, default: Any) -> Any:
            sentinel = object()
            seen: set[str] = set()
            candidates = [f"{mode}_{base_key}"]
            candidates.extend(f"{token}{base_key}" for token in get_setting_prefixes(mode))
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                value = _get(candidate, sentinel)
                if value is not sentinel:
                    return value
            return default

        _defaults_model = cls()
        _mode_kwargs = _build_live_visualizer_mode_kwargs(_get_per_mode_value, _defaults_model)
        _mode_visual_kwargs = _build_live_visualizer_mode_shared_visual_kwargs(_get_per_mode_value, _defaults_model)
        if resolve_preset_indices:
            _preset_kwargs = resolve_all_preset_indices_from_mapping(_raw, prefix=prefix)
        else:
            def _coerce_preset_idx(raw: Any) -> int:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return 0

            _preset_kwargs = {
                get_preset_key(mode_id): _coerce_preset_idx(
                    _raw.get(get_preset_key(mode_id), _raw.get(f"{prefix}.{get_preset_key(mode_id)}", 0))
                )
                for mode_id in VISUALIZER_MODE_IDS
            }
        _active_technical = _resolve_active_mode_technical_state(
            _mode,
            _mode_kwargs,
        )
        _active_visuals = _resolve_active_mode_shared_visual_state(
            _mode,
            _mode_visual_kwargs,
        )
        _rainbow_kwargs = resolve_visualizer_active_mode_rainbow_state(
            lambda key, default: _get_mode_value(key, default)
        )

        return cls(
            enabled=_get("enabled", False),
            visualizers_enabled=_get("visualizers_enabled", True),
            monitor=_get("monitor", "ALL"),
            bar_count=int(_active_technical["bar_count"]),
            ghosting_enabled=bool(_get("spectrum_ghosting_enabled", True)),
            ghost_alpha=float(_get("spectrum_ghost_alpha", 0.4)),
            ghost_decay=float(_get("spectrum_ghost_decay", 0.35)),
            adaptive_sensitivity=bool(_active_technical["adaptive_sensitivity"]),
            sensitivity=float(_active_technical["sensitivity"]),
            dynamic_floor=bool(_active_technical["dynamic_floor"]),
            manual_floor=float(_active_technical["manual_floor"]),
            dynamic_range_enabled=bool(_active_technical["dynamic_range_enabled"]),
            agc_strength=float(_active_technical["agc_strength"]),
            input_gain=float(_active_technical["input_gain"]),
            kick_lane_gain=float(_active_technical["kick_lane_gain"]),
            transient_pulse_gain=float(_active_technical["transient_pulse_gain"]),
            transient_clamp=float(_active_technical["transient_clamp"]),
            bar_fill_color=_active_visuals["bar_fill_color"],
            bar_border_color=_active_visuals["bar_border_color"],
            bar_border_opacity=float(_active_visuals["bar_border_opacity"]),
            mode=coerce_visualizer_mode_id(str(_get("mode", "bubble"))),
            osc_glow_enabled=_get("osc_glow_enabled", True),
            osc_glow_intensity=float(_get("osc_glow_intensity", 0.5)),
            osc_glow_reactivity=float(_get("osc_glow_reactivity", _get("osc_glow_size", 1.0))),
            osc_glow_color=_get("osc_glow_color", [0, 200, 255, 230]),
            osc_reactive_glow=_get("osc_reactive_glow", True),
            osc_line_amplitude=float(
                _get("osc_line_amplitude", 3.0)
            ),
            osc_smoothing=float(_get("osc_smoothing", 0.7)),
            blob_color=_get("blob_color", [0, 180, 255, 230]),
            blob_glow_color=_get("blob_glow_color", [0, 140, 255, 180]),
            blob_edge_color=_get("blob_edge_color", [100, 220, 255, 230]),
            blob_outline_color=_get("blob_outline_color", [0, 0, 0, 0]),
            blob_pulse=float(_get("blob_pulse", 1.0)),
            blob_pulse_release_ms=int(_get("blob_pulse_release_ms", 220)),
            blob_width=float(_get("blob_width", 1.0)),
            blob_size=float(_get("blob_size", 1.0)),
            blob_glow_intensity=float(_get("blob_glow_intensity", 0.5)),
            blob_reactive_glow=_get("blob_reactive_glow", True),
            blob_glow_drive_mode=str(_get("blob_glow_drive_mode", "bass")),
            osc_line_color=_get("osc_line_color", [255, 255, 255, 255]),
            osc_line_count=int(_get("osc_line_count", 1)),
            osc_line2_color=_get("osc_line2_color", [255, 120, 50, 230]),
            osc_line2_glow_color=_get("osc_line2_glow_color", [255, 120, 50, 180]),
            osc_line3_color=_get("osc_line3_color", [50, 255, 120, 230]),
            osc_line3_glow_color=_get("osc_line3_glow_color", [50, 255, 120, 180]),
            osc_line4_color=_get("osc_line4_color", [255, 0, 150, 230]),
            osc_line4_glow_color=_get("osc_line4_glow_color", [255, 0, 150, 180]),
            osc_line5_color=_get("osc_line5_color", [0, 255, 200, 230]),
            osc_line5_glow_color=_get("osc_line5_glow_color", [0, 255, 200, 180]),
            osc_line6_color=_get("osc_line6_color", [200, 100, 255, 230]),
            osc_line6_glow_color=_get("osc_line6_glow_color", [200, 100, 255, 180]),
            spectrum_growth=float(_get("spectrum_growth", 1.0)),
            blob_growth=float(_get("blob_growth", 2.5)),
            osc_speed=float(_get("osc_speed", 1.0)),
            osc_line_dim=_get("osc_line_dim", False),
            osc_line_offset_bias=float(_get("osc_line_offset_bias", 0.0)),
            osc_vertical_shift=int(_get("osc_vertical_shift", 0)),
            osc_growth=float(_get("osc_growth", 1.0)),
            blob_reactive_deformation=float(_get("blob_reactive_deformation", 1.0)),
            blob_constant_wobble=float(_get("blob_constant_wobble", 1.0)),
            blob_reactive_wobble=float(_get("blob_reactive_wobble", 1.0)),
            blob_stretch=float(_get("blob_stretch", 0.35)),
            blob_stage_gain=float(_get("blob_stage_gain", 1.0)),
            blob_core_scale=float(_get("blob_core_scale", 1.0)),
            blob_core_floor_bias=float(_get("blob_core_floor_bias", 0.35)),
            blob_stage_bias=float(_get("blob_stage_bias", 0.0)),
            blob_stretch_tendency=float(_get("blob_stretch_tendency", _get("blob_stretch", 0.35))),
            blob_stretch_inner=float(_get("blob_stretch_inner", 0.0)),
            blob_stretch_outer=float(_get("blob_stretch_outer", _get("blob_stretch", 0.35))),
            spectrum_render_mode=resolve_spectrum_render_mode(_get),
            spectrum_unique_colors=resolve_spectrum_unique_colors(_get),
            spectrum_rainbow_border=bool(_get("spectrum_rainbow_border", False)),
            spectrum_border_radius=float(_get("spectrum_border_radius", 0.0)),
            spectrum_link_fill_border=bool(_get("spectrum_link_fill_border", False)),
            spectrum_glow_enabled=bool(_get("spectrum_glow_enabled", False)),
            spectrum_glow_intensity=float(_get("spectrum_glow_intensity", 0.55)),
            spectrum_glow_color=list(_get("spectrum_glow_color", [110, 220, 255, 235])),
            spectrum_ghosting_enabled=bool(_get("spectrum_ghosting_enabled", True)),
            spectrum_ghost_alpha=float(_get("spectrum_ghost_alpha", 0.4)),
            spectrum_ghost_decay=float(_get("spectrum_ghost_decay", 0.35)),
            spectrum_mirrored=bool(_get("spectrum_mirrored", True)),
            spectrum_shape_nodes=list(
                _get("spectrum_shape_nodes", [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]])
            ),
            spectrum_notch_positions_mirrored=list(
                _get("spectrum_notch_positions_mirrored", [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]])
            ),
            spectrum_notch_positions_linear=_normalize_spectrum_linear_notches(
                _get("spectrum_notch_positions_linear", _SPECTRUM_DEFAULT_NOTCHES_LINEAR)
            ),
            spectrum_lane_strengths_mirrored=_normalize_spectrum_lane_strengths(
                _get("spectrum_lane_strengths_mirrored", _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED),
                _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
            ),
            spectrum_lane_strengths_linear=_normalize_spectrum_lane_strengths(
                _get("spectrum_lane_strengths_linear", _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR),
                _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
            ),
            spectrum_wave_amplitude=float(_get("spectrum_wave_amplitude", 0.50)),
            spectrum_profile_floor=float(_get("spectrum_profile_floor", 0.12)),
            spectrum_drop_speed=float(_get("spectrum_drop_speed", 1.0)),
            sine_wave_growth=float(_get("sine_wave_growth", 1.0)),
            sine_wave_travel=int(_get("sine_wave_travel", 0)),
            sine_density=float(_get("sine_density", 1.0)),
            sine_displacement=float(_get("sine_displacement", 0.0)),
            sine_glow_enabled=_get("sine_glow_enabled", True),
            sine_glow_intensity=float(_get("sine_glow_intensity", 0.5)),
            sine_glow_reactivity=float(_get("sine_glow_reactivity", _get("sine_glow_size", 1.0))),
            sine_glow_color=_get("sine_glow_color", [0, 200, 255, 230]),
            sine_line_color=_get("sine_line_color", [255, 255, 255, 255]),
            sine_reactive_glow=_get("sine_reactive_glow", True),
            sine_ghosting_enabled=_get("sine_ghosting_enabled", True),
            sine_ghost_alpha=float(_get("sine_ghost_alpha", 0.45)),
            sine_ghost_decay=float(_get("sine_ghost_decay", 0.3)),
            sine_ghost_line2_enabled=bool(_get("sine_ghost_line2_enabled", True)),
            sine_ghost_line3_enabled=bool(_get("sine_ghost_line3_enabled", True)),
            sine_ghost_line4_enabled=bool(_get("sine_ghost_line4_enabled", True)),
            sine_ghost_line5_enabled=bool(_get("sine_ghost_line5_enabled", True)),
            sine_ghost_line6_enabled=bool(_get("sine_ghost_line6_enabled", True)),
            sine_sensitivity=float(_get("sine_sensitivity", 1.0)),
            sine_smoothing=float(_get("sine_smoothing", 0.7)),
            sine_speed=float(_get("sine_speed", 1.0)),
            sine_line_count=int(_get("sine_line_count", 1)),
            sine_line_offset_bias=float(_get("sine_line_offset_bias", 0.0)),
            sine_line2_color=_get("sine_line2_color", [255, 255, 255, 230]),
            sine_line2_glow_color=_get("sine_line2_glow_color", [7, 114, 255, 180]),
            sine_line3_color=_get("sine_line3_color", [255, 255, 255, 230]),
            sine_line3_glow_color=_get("sine_line3_glow_color", [14, 159, 255, 180]),
            sine_line4_color=_get("sine_line4_color", [255, 120, 50, 230]),
            sine_line4_glow_color=_get("sine_line4_glow_color", [255, 120, 50, 180]),
            sine_line5_color=_get("sine_line5_color", [50, 255, 120, 230]),
            sine_line5_glow_color=_get("sine_line5_glow_color", [50, 255, 120, 180]),
            sine_line6_color=_get("sine_line6_color", [255, 0, 150, 230]),
            sine_line6_glow_color=_get("sine_line6_glow_color", [255, 0, 150, 180]),
            sine_travel_line2=int(_get("sine_travel_line2", 0)),
            sine_travel_line3=int(_get("sine_travel_line3", 0)),
            sine_travel_line4=int(_get("sine_travel_line4", 0)),
            sine_travel_line5=int(_get("sine_travel_line5", 0)),
            sine_travel_line6=int(_get("sine_travel_line6", 0)),
            sine_line1_shift=float(_get("sine_line1_shift", 0.0)),
            sine_line2_shift=float(_get("sine_line2_shift", 0.0)),
            sine_line3_shift=float(_get("sine_line3_shift", 0.0)),
            sine_line4_shift=float(_get("sine_line4_shift", 0.0)),
            sine_line5_shift=float(_get("sine_line5_shift", 0.0)),
            sine_line6_shift=float(_get("sine_line6_shift", 0.0)),
            sine_wave_effect=float(_get("sine_wave_effect", _get("sine_wobble_amount", 0.0))),
            sine_vertical_shift=int(_get("sine_vertical_shift", 0)),
            sine_card_adaptation=float(_get("sine_card_adaptation", 0.3)),
            sine_micro_wobble=float(_get("sine_micro_wobble", 0.0)),
            sine_crawl_amount=float(_get("sine_crawl_amount", 0.25)),
            sine_width_reaction=float(_get("sine_width_reaction", 0.0)),
            rainbow_enabled=_rainbow_kwargs["rainbow_enabled"],
            rainbow_speed=_rainbow_kwargs["rainbow_speed"],
            osc_ghosting_enabled=bool(_get("osc_ghosting_enabled", False)),
            osc_ghost_intensity=float(_get("osc_ghost_intensity", 0.4)),
            osc_ghost_line2_enabled=bool(_get("osc_ghost_line2_enabled", True)),
            osc_ghost_line3_enabled=bool(_get("osc_ghost_line3_enabled", True)),
            osc_ghost_line4_enabled=bool(_get("osc_ghost_line4_enabled", True)),
            osc_ghost_line5_enabled=bool(_get("osc_ghost_line5_enabled", True)),
            osc_ghost_line6_enabled=bool(_get("osc_ghost_line6_enabled", True)),
            sine_heartbeat=float(_get("sine_heartbeat", 0.0)),
            # Bubble
            bubble_big_bass_pulse=float(_get("bubble_big_bass_pulse", 0.5)),
            bubble_small_freq_pulse=float(_get("bubble_small_freq_pulse", 0.5)),
            bubble_stream_direction=str(_get("bubble_stream_direction", "up")),
            bubble_stream_constant_speed=float(
                _get("bubble_stream_constant_speed", _get("bubble_stream_speed", 0.6))
            ),
            bubble_stream_speed_cap=float(
                _get("bubble_stream_speed_cap", _get("bubble_stream_speed", 1.0))
            ),
            bubble_stream_reactivity=float(_get("bubble_stream_reactivity", 0.5)),
            bubble_rotation_amount=float(_get("bubble_rotation_amount", 0.5)),
            bubble_drift_amount=float(_get("bubble_drift_amount", 0.5)),
            bubble_drift_speed=float(_get("bubble_drift_speed", 0.5)),
            bubble_drift_frequency=float(_get("bubble_drift_frequency", 0.5)),
            bubble_drift_direction=str(_get("bubble_drift_direction", "random")),
            bubble_big_count=int(_get("bubble_big_count", 8)),
            bubble_small_count=int(_get("bubble_small_count", 25)),
            bubble_surface_reach=float(_get("bubble_surface_reach", 0.6)),
            bubble_bounce_big_pct=int(_get("bubble_bounce_big_pct", 70)),
            bubble_bounce_small_pct=int(_get("bubble_bounce_small_pct", 30)),
                bubble_bounce_big_speed=float(_get("bubble_bounce_big_speed", 0.8)),
                bubble_bounce_small_speed=float(_get("bubble_bounce_small_speed", 0.5)),
                bubble_bounce_same_only=bool(_get("bubble_bounce_same_only", False)),
                bubble_collision_pop_mode=str(_get("bubble_collision_pop_mode", "off")).strip().lower(),
            bubble_outline_color=_get("bubble_outline_color", [255, 255, 255, 230]),
            bubble_specular_color=_get("bubble_specular_color", [255, 255, 255, 255]),
            bubble_gradient_light=_get("bubble_gradient_light", [210, 170, 120, 255]),
            bubble_gradient_dark=_get("bubble_gradient_dark", [80, 60, 50, 255]),
            bubble_pop_color=_get("bubble_pop_color", [255, 255, 255, 180]),
            bubble_specular_direction=normalize_bubble_specular_direction(
                _get("bubble_specular_direction", "top_left"),
            ),
            bubble_gradient_direction=resolve_bubble_gradient_direction(
                _get("bubble_gradient_direction", "top"),
                semantics_version=bubble_gradient_semantics_version,
                default="top",
            ),
            bubble_big_size_max=float(_get("bubble_big_size_max", 0.038)),
            bubble_small_size_max=float(_get("bubble_small_size_max", 0.018)),
            bubble_big_contraction_bias=float(_get("bubble_big_contraction_bias", 1.0)),
            bubble_big_size_clamp=float(_get("bubble_big_size_clamp", 4.0)),
            bubble_big_specular_max_size=float(_get("bubble_big_specular_max_size", 2.5)),
            bubble_growth=float(_get("bubble_growth", 3.0)),
            devcurve_growth=float(_get("devcurve_growth", 3.0)),
            bubble_trail_strength=float(_get("bubble_trail_strength", 0.0)),
            bubble_tail_opacity=float(_get("bubble_tail_opacity", 0.0)),
            bubble_ghosting_enabled=bool(_get("bubble_ghosting_enabled", False)),
            bubble_ghost_alpha=float(_get("bubble_ghost_alpha", 0.0)),
            bubble_ghost_decay=float(_get("bubble_ghost_decay", 0.4)),
            blob_glow_reactivity=float(_get("blob_glow_reactivity", 1.0)),
            blob_glow_max_size=float(_get("blob_glow_max_size", 1.0)),
            blob_ghosting_enabled=bool(_get("blob_ghosting_enabled", False)),
            blob_ghost_alpha=float(_get("blob_ghost_alpha", 0.4)),
            blob_ghost_decay=float(_get("blob_ghost_decay", 0.3)),
            blob_shaper_enabled=bool(_get("blob_shaper_enabled", False)),
            blob_shape_base_nodes=list(_get("blob_shape_base_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
            blob_shape_reaction_nodes=list(_get("blob_shape_reaction_nodes", [[0.0, 1.0], [0.25, 1.0], [0.5, 1.0], [0.75, 1.0]])),
            blob_shape_energy_nodes=list(_get("blob_shape_energy_nodes", [])),
            blob_shaper_base_strength=float(_get("blob_shaper_base_strength", 0.5)),
            blob_shaper_react_strength=float(_get("blob_shaper_react_strength", 0.5)),
            blob_shaper_idle_motion=float(_get("blob_shaper_idle_motion", 0.18)),
            blob_shaper_audio_motion=float(_get("blob_shaper_audio_motion", 1.20)),
            blob_topology=str(_get("blob_topology", "circle")),
            blob_ring_thickness=float(_get("blob_ring_thickness", 0.3)),
            blob_inward_liquid_enabled=bool(_get("blob_inward_liquid_enabled", False)),
            blob_inward_liquid_reactivity=float(_get("blob_inward_liquid_reactivity", 1.0)),
            blob_inward_liquid_max_size=float(_get("blob_inward_liquid_max_size", 0.28)),
            blob_inward_liquid_color=_get("blob_inward_liquid_color", [170, 225, 255, 190]),
            # Dev Curve
            devcurve_active_layer=str(_get("devcurve_active_layer", "bass")),
            devcurve_layer_bass_shape_nodes=list(_get("devcurve_layer_bass_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_vocals_shape_nodes=list(_get("devcurve_layer_vocals_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_mids_shape_nodes=list(_get("devcurve_layer_mids_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_layer_transients_shape_nodes=list(_get("devcurve_layer_transients_shape_nodes", [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]])),
            devcurve_base_level=float(_get("devcurve_base_level", 0.58)),
            devcurve_motion_power=float(_get("devcurve_motion_power", 1.0)),
            devcurve_idle_motion=float(_get("devcurve_idle_motion", 0.20)),
            devcurve_idle_speed=float(_get("devcurve_idle_speed", 0.60)),
            devcurve_smoothness=float(_get("devcurve_smoothness", 0.55)),
            devcurve_layer_bass_enabled=bool(_get("devcurve_layer_bass_enabled", True)),
            devcurve_layer_bass_color=_get("devcurve_layer_bass_color", [82, 167, 255, 230]),
            devcurve_layer_bass_alpha=float(_get("devcurve_layer_bass_alpha", 0.55)),
            devcurve_layer_bass_power=float(_get("devcurve_layer_bass_power", 1.0)),
            devcurve_layer_bass_offset=float(_get("devcurve_layer_bass_offset", 0.0)),
            devcurve_layer_bass_outline_color=_get("devcurve_layer_bass_outline_color", [255, 255, 255, 255]),
            devcurve_layer_bass_outline_width=float(_get("devcurve_layer_bass_outline_width", 0.006)),
            devcurve_layer_bass_order=int(_get("devcurve_layer_bass_order", 1)),
            devcurve_layer_vocals_enabled=bool(_get("devcurve_layer_vocals_enabled", True)),
            devcurve_layer_vocals_color=_get("devcurve_layer_vocals_color", [136, 190, 255, 220]),
            devcurve_layer_vocals_alpha=float(_get("devcurve_layer_vocals_alpha", 0.42)),
            devcurve_layer_vocals_power=float(_get("devcurve_layer_vocals_power", 1.0)),
            devcurve_layer_vocals_offset=float(_get("devcurve_layer_vocals_offset", -0.01)),
            devcurve_layer_vocals_outline_color=_get("devcurve_layer_vocals_outline_color", [255, 255, 255, 255]),
            devcurve_layer_vocals_outline_width=float(_get("devcurve_layer_vocals_outline_width", 0.006)),
            devcurve_layer_vocals_order=int(_get("devcurve_layer_vocals_order", 2)),
            devcurve_layer_mids_enabled=bool(_get("devcurve_layer_mids_enabled", True)),
            devcurve_layer_mids_color=_get("devcurve_layer_mids_color", [100, 145, 255, 220]),
            devcurve_layer_mids_alpha=float(_get("devcurve_layer_mids_alpha", 0.46)),
            devcurve_layer_mids_power=float(_get("devcurve_layer_mids_power", 1.0)),
            devcurve_layer_mids_offset=float(_get("devcurve_layer_mids_offset", 0.01)),
            devcurve_layer_mids_outline_color=_get("devcurve_layer_mids_outline_color", [255, 255, 255, 255]),
            devcurve_layer_mids_outline_width=float(_get("devcurve_layer_mids_outline_width", 0.006)),
            devcurve_layer_mids_order=int(_get("devcurve_layer_mids_order", 3)),
            devcurve_layer_transients_enabled=bool(_get("devcurve_layer_transients_enabled", True)),
            devcurve_layer_transients_color=_get("devcurve_layer_transients_color", [215, 240, 255, 240]),
            devcurve_layer_transients_alpha=float(_get("devcurve_layer_transients_alpha", 0.66)),
            devcurve_layer_transients_power=float(_get("devcurve_layer_transients_power", 1.15)),
            devcurve_layer_transients_offset=float(_get("devcurve_layer_transients_offset", 0.0)),
            devcurve_layer_transients_outline_color=_get("devcurve_layer_transients_outline_color", [255, 255, 255, 255]),
            devcurve_layer_transients_outline_width=float(_get("devcurve_layer_transients_outline_width", 0.006)),
            devcurve_layer_transients_order=int(_get("devcurve_layer_transients_order", 4)),
            devcurve_ghosting_enabled=bool(_get("devcurve_ghosting_enabled", False)),
            devcurve_ghost_alpha=float(_get("devcurve_ghost_alpha", 0.0)),
            devcurve_ghost_decay=float(_get("devcurve_ghost_decay", 0.4)),
            devcurve_foreground_shadow_enabled=bool(_get("devcurve_foreground_shadow_enabled", False)),
            devcurve_foreground_shadow_alpha=float(_get("devcurve_foreground_shadow_alpha", 0.36)),
            devcurve_foreground_shadow_darken=float(_get("devcurve_foreground_shadow_darken", 0.42)),
            devcurve_foreground_shadow_offset=float(_get("devcurve_foreground_shadow_offset", 0.10)),
            devcurve_foreground_specular_enabled=bool(_get("devcurve_foreground_specular_enabled", False)),
            devcurve_foreground_specular_alpha=float(_get("devcurve_foreground_specular_alpha", 0.78)),
            devcurve_foreground_specular_width=float(_get("devcurve_foreground_specular_width", 0.022)),
            devcurve_foreground_specular_offset=float(_get("devcurve_foreground_specular_offset", 0.028)),
            devcurve_foreground_specular_crest_bias=float(_get("devcurve_foreground_specular_crest_bias", 1.05)),
            sine_line_dim=bool(_get("sine_line_dim", False)),
            **_preset_kwargs,
            **_mode_kwargs,
            **_mode_visual_kwargs,
        )

    def to_dict(self, prefix: str = "widgets.spotify_visualizer") -> Dict[str, Any]:
        """Convert to dictionary for saving."""
        data = {
            f"{prefix}.enabled": self.enabled,
            f"{prefix}.visualizers_enabled": self.visualizers_enabled,
            f"{prefix}.monitor": self.monitor,
            f"{prefix}.mode": self.mode,
            f"{prefix}.osc_glow_enabled": self.osc_glow_enabled,
            f"{prefix}.osc_glow_intensity": float(self.osc_glow_intensity),
            f"{prefix}.osc_glow_reactivity": float(self.osc_glow_reactivity),
            f"{prefix}.osc_glow_color": list(self.osc_glow_color),
            f"{prefix}.osc_reactive_glow": self.osc_reactive_glow,
            f"{prefix}.osc_line_amplitude": float(self.osc_line_amplitude),
            f"{prefix}.osc_smoothing": float(self.osc_smoothing),
            f"{prefix}.blob_color": list(self.blob_color),
            f"{prefix}.blob_glow_color": list(self.blob_glow_color),
            f"{prefix}.blob_edge_color": list(self.blob_edge_color),
            f"{prefix}.blob_outline_color": list(self.blob_outline_color),
            f"{prefix}.blob_pulse": float(self.blob_pulse),
            f"{prefix}.blob_pulse_release_ms": int(self.blob_pulse_release_ms),
            f"{prefix}.blob_width": float(self.blob_width),
            f"{prefix}.blob_size": float(self.blob_size),
            f"{prefix}.blob_glow_intensity": float(self.blob_glow_intensity),
            f"{prefix}.blob_reactive_glow": self.blob_reactive_glow,
            f"{prefix}.blob_glow_drive_mode": str(self.blob_glow_drive_mode),
            f"{prefix}.osc_line_color": list(self.osc_line_color),
            f"{prefix}.osc_line_count": int(self.osc_line_count),
            f"{prefix}.osc_line2_color": list(self.osc_line2_color),
            f"{prefix}.osc_line2_glow_color": list(self.osc_line2_glow_color),
            f"{prefix}.osc_line3_color": list(self.osc_line3_color),
            f"{prefix}.osc_line3_glow_color": list(self.osc_line3_glow_color),
            f"{prefix}.osc_line4_color": list(self.osc_line4_color),
            f"{prefix}.osc_line4_glow_color": list(self.osc_line4_glow_color),
            f"{prefix}.osc_line5_color": list(self.osc_line5_color),
            f"{prefix}.osc_line5_glow_color": list(self.osc_line5_glow_color),
            f"{prefix}.osc_line6_color": list(self.osc_line6_color),
            f"{prefix}.osc_line6_glow_color": list(self.osc_line6_glow_color),
            f"{prefix}.spectrum_growth": float(self.spectrum_growth),
            f"{prefix}.blob_growth": float(self.blob_growth),
            f"{prefix}.osc_speed": float(self.osc_speed),
            f"{prefix}.osc_line_dim": self.osc_line_dim,
            f"{prefix}.osc_line_offset_bias": float(self.osc_line_offset_bias),
            f"{prefix}.osc_vertical_shift": int(self.osc_vertical_shift),
            f"{prefix}.osc_growth": float(self.osc_growth),
            f"{prefix}.blob_reactive_deformation": float(self.blob_reactive_deformation),
            f"{prefix}.blob_constant_wobble": float(self.blob_constant_wobble),
            f"{prefix}.blob_reactive_wobble": float(self.blob_reactive_wobble),
            f"{prefix}.blob_stretch": float(self.blob_stretch),
            f"{prefix}.blob_stage_gain": float(self.blob_stage_gain),
            f"{prefix}.blob_core_scale": float(self.blob_core_scale),
            f"{prefix}.blob_core_floor_bias": float(self.blob_core_floor_bias),
            f"{prefix}.blob_stage_bias": float(self.blob_stage_bias),
            f"{prefix}.blob_stretch_tendency": float(self.blob_stretch_tendency),
            f"{prefix}.blob_stretch_inner": float(self.blob_stretch_inner),
            f"{prefix}.blob_stretch_outer": float(self.blob_stretch_outer),
            f"{prefix}.spectrum_render_mode": str(self.spectrum_render_mode),
            f"{prefix}.spectrum_unique_colors": self.spectrum_unique_colors,
            f"{prefix}.spectrum_rainbow_border": self.spectrum_rainbow_border,
            f"{prefix}.spectrum_border_radius": float(self.spectrum_border_radius),
            f"{prefix}.spectrum_link_fill_border": self.spectrum_link_fill_border,
            f"{prefix}.spectrum_glow_enabled": self.spectrum_glow_enabled,
            f"{prefix}.spectrum_glow_intensity": float(self.spectrum_glow_intensity),
            f"{prefix}.spectrum_glow_color": list(self.spectrum_glow_color),
            f"{prefix}.spectrum_ghosting_enabled": self.spectrum_ghosting_enabled,
            f"{prefix}.spectrum_ghost_alpha": float(self.spectrum_ghost_alpha),
            f"{prefix}.spectrum_ghost_decay": float(self.spectrum_ghost_decay),
            f"{prefix}.spectrum_mirrored": self.spectrum_mirrored,
            f"{prefix}.spectrum_shape_nodes": self.spectrum_shape_nodes,
            f"{prefix}.spectrum_notch_positions_mirrored": self.spectrum_notch_positions_mirrored,
            f"{prefix}.spectrum_notch_positions_linear": self.spectrum_notch_positions_linear,
            f"{prefix}.spectrum_lane_strengths_mirrored": dict(self.spectrum_lane_strengths_mirrored),
            f"{prefix}.spectrum_lane_strengths_linear": dict(self.spectrum_lane_strengths_linear),
            f"{prefix}.spectrum_wave_amplitude": float(self.spectrum_wave_amplitude),
            f"{prefix}.spectrum_profile_floor": float(self.spectrum_profile_floor),
            f"{prefix}.spectrum_drop_speed": float(self.spectrum_drop_speed),
            f"{prefix}.sine_wave_growth": float(self.sine_wave_growth),
            f"{prefix}.sine_wave_travel": int(self.sine_wave_travel),
            f"{prefix}.sine_density": float(self.sine_density),
            f"{prefix}.sine_displacement": float(self.sine_displacement),
            f"{prefix}.sine_glow_enabled": self.sine_glow_enabled,
            f"{prefix}.sine_glow_intensity": float(self.sine_glow_intensity),
            f"{prefix}.sine_glow_reactivity": float(self.sine_glow_reactivity),
            f"{prefix}.sine_glow_color": list(self.sine_glow_color),
            f"{prefix}.sine_line_color": list(self.sine_line_color),
            f"{prefix}.sine_reactive_glow": self.sine_reactive_glow,
            f"{prefix}.sine_ghosting_enabled": self.sine_ghosting_enabled,
            f"{prefix}.sine_ghost_alpha": float(self.sine_ghost_alpha),
            f"{prefix}.sine_ghost_decay": float(self.sine_ghost_decay),
            f"{prefix}.sine_ghost_line2_enabled": self.sine_ghost_line2_enabled,
            f"{prefix}.sine_ghost_line3_enabled": self.sine_ghost_line3_enabled,
            f"{prefix}.sine_ghost_line4_enabled": self.sine_ghost_line4_enabled,
            f"{prefix}.sine_ghost_line5_enabled": self.sine_ghost_line5_enabled,
            f"{prefix}.sine_ghost_line6_enabled": self.sine_ghost_line6_enabled,
            f"{prefix}.sine_sensitivity": float(self.sine_sensitivity),
            f"{prefix}.sine_smoothing": float(self.sine_smoothing),
            f"{prefix}.sine_speed": float(self.sine_speed),
            f"{prefix}.sine_line_count": int(self.sine_line_count),
            f"{prefix}.sine_line_offset_bias": float(self.sine_line_offset_bias),
            f"{prefix}.sine_line2_color": list(self.sine_line2_color),
            f"{prefix}.sine_line2_glow_color": list(self.sine_line2_glow_color),
            f"{prefix}.sine_line3_color": list(self.sine_line3_color),
            f"{prefix}.sine_line3_glow_color": list(self.sine_line3_glow_color),
            f"{prefix}.sine_line4_color": list(self.sine_line4_color),
            f"{prefix}.sine_line4_glow_color": list(self.sine_line4_glow_color),
            f"{prefix}.sine_line5_color": list(self.sine_line5_color),
            f"{prefix}.sine_line5_glow_color": list(self.sine_line5_glow_color),
            f"{prefix}.sine_line6_color": list(self.sine_line6_color),
            f"{prefix}.sine_line6_glow_color": list(self.sine_line6_glow_color),
            f"{prefix}.sine_travel_line2": int(self.sine_travel_line2),
            f"{prefix}.sine_travel_line3": int(self.sine_travel_line3),
            f"{prefix}.sine_travel_line4": int(self.sine_travel_line4),
            f"{prefix}.sine_travel_line5": int(self.sine_travel_line5),
            f"{prefix}.sine_travel_line6": int(self.sine_travel_line6),
            f"{prefix}.sine_line1_shift": float(self.sine_line1_shift),
            f"{prefix}.sine_line2_shift": float(self.sine_line2_shift),
            f"{prefix}.sine_line3_shift": float(self.sine_line3_shift),
            f"{prefix}.sine_line4_shift": float(self.sine_line4_shift),
            f"{prefix}.sine_line5_shift": float(self.sine_line5_shift),
            f"{prefix}.sine_line6_shift": float(self.sine_line6_shift),
            f"{prefix}.sine_wave_effect": float(self.sine_wave_effect),
            f"{prefix}.sine_vertical_shift": int(self.sine_vertical_shift),
            f"{prefix}.sine_card_adaptation": float(self.sine_card_adaptation),
            f"{prefix}.sine_micro_wobble": float(self.sine_micro_wobble),
            f"{prefix}.sine_crawl_amount": float(self.sine_crawl_amount),
            f"{prefix}.sine_width_reaction": float(self.sine_width_reaction),
            f"{prefix}.rainbow_enabled": self.rainbow_enabled,
            f"{prefix}.rainbow_speed": float(self.rainbow_speed),
            f"{prefix}.osc_ghosting_enabled": self.osc_ghosting_enabled,
            f"{prefix}.osc_ghost_intensity": float(self.osc_ghost_intensity),
            f"{prefix}.osc_ghost_line2_enabled": self.osc_ghost_line2_enabled,
            f"{prefix}.osc_ghost_line3_enabled": self.osc_ghost_line3_enabled,
            f"{prefix}.osc_ghost_line4_enabled": self.osc_ghost_line4_enabled,
            f"{prefix}.osc_ghost_line5_enabled": self.osc_ghost_line5_enabled,
            f"{prefix}.osc_ghost_line6_enabled": self.osc_ghost_line6_enabled,
            f"{prefix}.sine_heartbeat": float(self.sine_heartbeat),
            # Bubble
            f"{prefix}.bubble_big_bass_pulse": float(self.bubble_big_bass_pulse),
            f"{prefix}.bubble_small_freq_pulse": float(self.bubble_small_freq_pulse),
            f"{prefix}.bubble_stream_direction": self.bubble_stream_direction,
            f"{prefix}.bubble_stream_constant_speed": float(self.bubble_stream_constant_speed),
            f"{prefix}.bubble_stream_speed_cap": float(self.bubble_stream_speed_cap),
            f"{prefix}.bubble_stream_reactivity": float(self.bubble_stream_reactivity),
            f"{prefix}.bubble_rotation_amount": float(self.bubble_rotation_amount),
            f"{prefix}.bubble_drift_amount": float(self.bubble_drift_amount),
            f"{prefix}.bubble_drift_speed": float(self.bubble_drift_speed),
            f"{prefix}.bubble_drift_frequency": float(self.bubble_drift_frequency),
            f"{prefix}.bubble_drift_direction": self.bubble_drift_direction,
            f"{prefix}.bubble_big_count": int(self.bubble_big_count),
            f"{prefix}.bubble_small_count": int(self.bubble_small_count),
            f"{prefix}.bubble_surface_reach": float(self.bubble_surface_reach),
            f"{prefix}.bubble_bounce_big_pct": int(self.bubble_bounce_big_pct),
            f"{prefix}.bubble_bounce_small_pct": int(self.bubble_bounce_small_pct),
            f"{prefix}.bubble_bounce_big_speed": float(self.bubble_bounce_big_speed),
            f"{prefix}.bubble_bounce_small_speed": float(self.bubble_bounce_small_speed),
            f"{prefix}.bubble_bounce_same_only": bool(self.bubble_bounce_same_only),
            f"{prefix}.bubble_collision_pop_mode": str(self.bubble_collision_pop_mode),
            f"{prefix}.bubble_outline_color": list(self.bubble_outline_color),
            f"{prefix}.bubble_specular_color": list(self.bubble_specular_color),
            f"{prefix}.bubble_gradient_light": list(self.bubble_gradient_light),
            f"{prefix}.bubble_gradient_dark": list(self.bubble_gradient_dark),
            f"{prefix}.bubble_pop_color": list(self.bubble_pop_color),
            f"{prefix}.bubble_specular_direction": self.bubble_specular_direction,
            f"{prefix}.bubble_gradient_direction": self.bubble_gradient_direction,
            f"{prefix}.bubble_gradient_semantics_version": CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
            f"{prefix}.bubble_big_size_max": float(self.bubble_big_size_max),
            f"{prefix}.bubble_small_size_max": float(self.bubble_small_size_max),
            f"{prefix}.bubble_big_contraction_bias": float(self.bubble_big_contraction_bias),
            f"{prefix}.bubble_big_size_clamp": float(self.bubble_big_size_clamp),
            f"{prefix}.bubble_big_specular_max_size": float(self.bubble_big_specular_max_size),
            f"{prefix}.bubble_growth": float(self.bubble_growth),
            f"{prefix}.devcurve_growth": float(self.devcurve_growth),
            f"{prefix}.bubble_trail_strength": float(self.bubble_trail_strength),
            f"{prefix}.bubble_tail_opacity": float(self.bubble_tail_opacity),
            f"{prefix}.bubble_ghosting_enabled": self.bubble_ghosting_enabled,
            f"{prefix}.bubble_ghost_alpha": float(self.bubble_ghost_alpha),
            f"{prefix}.bubble_ghost_decay": float(self.bubble_ghost_decay),
            f"{prefix}.blob_glow_reactivity": float(self.blob_glow_reactivity),
            f"{prefix}.blob_glow_max_size": float(self.blob_glow_max_size),
            f"{prefix}.blob_ghosting_enabled": bool(self.blob_ghosting_enabled),
            f"{prefix}.blob_ghost_alpha": float(self.blob_ghost_alpha),
            f"{prefix}.blob_ghost_decay": float(self.blob_ghost_decay),
            f"{prefix}.blob_shaper_enabled": bool(self.blob_shaper_enabled),
            f"{prefix}.blob_shape_base_nodes": self.blob_shape_base_nodes,
            f"{prefix}.blob_shape_reaction_nodes": self.blob_shape_reaction_nodes,
            f"{prefix}.blob_shape_energy_nodes": list(self.blob_shape_energy_nodes),
            f"{prefix}.blob_shaper_base_strength": float(self.blob_shaper_base_strength),
            f"{prefix}.blob_shaper_react_strength": float(self.blob_shaper_react_strength),
            f"{prefix}.blob_shaper_idle_motion": float(self.blob_shaper_idle_motion),
            f"{prefix}.blob_shaper_audio_motion": float(self.blob_shaper_audio_motion),
            f"{prefix}.blob_topology": str(self.blob_topology),
            f"{prefix}.blob_ring_thickness": float(self.blob_ring_thickness),
            f"{prefix}.blob_inward_liquid_enabled": bool(self.blob_inward_liquid_enabled),
            f"{prefix}.blob_inward_liquid_reactivity": float(self.blob_inward_liquid_reactivity),
            f"{prefix}.blob_inward_liquid_max_size": float(self.blob_inward_liquid_max_size),
            f"{prefix}.blob_inward_liquid_color": list(self.blob_inward_liquid_color),
            # Dev Curve
            f"{prefix}.devcurve_active_layer": str(self.devcurve_active_layer),
            f"{prefix}.devcurve_layer_bass_shape_nodes": list(self.devcurve_layer_bass_shape_nodes),
            f"{prefix}.devcurve_layer_vocals_shape_nodes": list(self.devcurve_layer_vocals_shape_nodes),
            f"{prefix}.devcurve_layer_mids_shape_nodes": list(self.devcurve_layer_mids_shape_nodes),
            f"{prefix}.devcurve_layer_transients_shape_nodes": list(self.devcurve_layer_transients_shape_nodes),
            f"{prefix}.devcurve_base_level": float(self.devcurve_base_level),
            f"{prefix}.devcurve_motion_power": float(self.devcurve_motion_power),
            f"{prefix}.devcurve_idle_motion": float(self.devcurve_idle_motion),
            f"{prefix}.devcurve_idle_speed": float(self.devcurve_idle_speed),
            f"{prefix}.devcurve_smoothness": float(self.devcurve_smoothness),
            f"{prefix}.devcurve_layer_bass_enabled": bool(self.devcurve_layer_bass_enabled),
            f"{prefix}.devcurve_layer_bass_color": list(self.devcurve_layer_bass_color),
            f"{prefix}.devcurve_layer_bass_alpha": float(self.devcurve_layer_bass_alpha),
            f"{prefix}.devcurve_layer_bass_power": float(self.devcurve_layer_bass_power),
            f"{prefix}.devcurve_layer_bass_offset": float(self.devcurve_layer_bass_offset),
            f"{prefix}.devcurve_layer_bass_outline_color": [int(self.devcurve_layer_bass_outline_color[0]), int(self.devcurve_layer_bass_outline_color[1]), int(self.devcurve_layer_bass_outline_color[2]), 255],
            f"{prefix}.devcurve_layer_bass_outline_width": float(self.devcurve_layer_bass_outline_width),
            f"{prefix}.devcurve_layer_bass_order": int(self.devcurve_layer_bass_order),
            f"{prefix}.devcurve_layer_vocals_enabled": bool(self.devcurve_layer_vocals_enabled),
            f"{prefix}.devcurve_layer_vocals_color": list(self.devcurve_layer_vocals_color),
            f"{prefix}.devcurve_layer_vocals_alpha": float(self.devcurve_layer_vocals_alpha),
            f"{prefix}.devcurve_layer_vocals_power": float(self.devcurve_layer_vocals_power),
            f"{prefix}.devcurve_layer_vocals_offset": float(self.devcurve_layer_vocals_offset),
            f"{prefix}.devcurve_layer_vocals_outline_color": [int(self.devcurve_layer_vocals_outline_color[0]), int(self.devcurve_layer_vocals_outline_color[1]), int(self.devcurve_layer_vocals_outline_color[2]), 255],
            f"{prefix}.devcurve_layer_vocals_outline_width": float(self.devcurve_layer_vocals_outline_width),
            f"{prefix}.devcurve_layer_vocals_order": int(self.devcurve_layer_vocals_order),
            f"{prefix}.devcurve_layer_mids_enabled": bool(self.devcurve_layer_mids_enabled),
            f"{prefix}.devcurve_layer_mids_color": list(self.devcurve_layer_mids_color),
            f"{prefix}.devcurve_layer_mids_alpha": float(self.devcurve_layer_mids_alpha),
            f"{prefix}.devcurve_layer_mids_power": float(self.devcurve_layer_mids_power),
            f"{prefix}.devcurve_layer_mids_offset": float(self.devcurve_layer_mids_offset),
            f"{prefix}.devcurve_layer_mids_outline_color": [int(self.devcurve_layer_mids_outline_color[0]), int(self.devcurve_layer_mids_outline_color[1]), int(self.devcurve_layer_mids_outline_color[2]), 255],
            f"{prefix}.devcurve_layer_mids_outline_width": float(self.devcurve_layer_mids_outline_width),
            f"{prefix}.devcurve_layer_mids_order": int(self.devcurve_layer_mids_order),
            f"{prefix}.devcurve_layer_transients_enabled": bool(self.devcurve_layer_transients_enabled),
            f"{prefix}.devcurve_layer_transients_color": list(self.devcurve_layer_transients_color),
            f"{prefix}.devcurve_layer_transients_alpha": float(self.devcurve_layer_transients_alpha),
            f"{prefix}.devcurve_layer_transients_power": float(self.devcurve_layer_transients_power),
            f"{prefix}.devcurve_layer_transients_offset": float(self.devcurve_layer_transients_offset),
            f"{prefix}.devcurve_layer_transients_outline_color": [int(self.devcurve_layer_transients_outline_color[0]), int(self.devcurve_layer_transients_outline_color[1]), int(self.devcurve_layer_transients_outline_color[2]), 255],
            f"{prefix}.devcurve_layer_transients_outline_width": float(self.devcurve_layer_transients_outline_width),
            f"{prefix}.devcurve_layer_transients_order": int(self.devcurve_layer_transients_order),
            f"{prefix}.devcurve_ghosting_enabled": self.devcurve_ghosting_enabled,
            f"{prefix}.devcurve_ghost_alpha": float(self.devcurve_ghost_alpha),
            f"{prefix}.devcurve_ghost_decay": float(self.devcurve_ghost_decay),
            f"{prefix}.devcurve_foreground_shadow_enabled": bool(self.devcurve_foreground_shadow_enabled),
            f"{prefix}.devcurve_foreground_shadow_alpha": float(self.devcurve_foreground_shadow_alpha),
            f"{prefix}.devcurve_foreground_shadow_darken": float(self.devcurve_foreground_shadow_darken),
            f"{prefix}.devcurve_foreground_shadow_offset": float(self.devcurve_foreground_shadow_offset),
            f"{prefix}.devcurve_foreground_specular_enabled": bool(self.devcurve_foreground_specular_enabled),
            f"{prefix}.devcurve_foreground_specular_alpha": float(self.devcurve_foreground_specular_alpha),
            f"{prefix}.devcurve_foreground_specular_width": float(self.devcurve_foreground_specular_width),
            f"{prefix}.devcurve_foreground_specular_offset": float(self.devcurve_foreground_specular_offset),
            f"{prefix}.devcurve_foreground_specular_crest_bias": float(self.devcurve_foreground_specular_crest_bias),
            f"{prefix}.sine_line_dim": bool(self.sine_line_dim),
            **{
                f"{prefix}.{get_preset_key(mode_id)}": int(getattr(self, get_preset_key(mode_id)))
                for mode_id in VISUALIZER_MODE_IDS
            },
        }

        for _mode in PER_MODE_TECHNICAL_MODES:
            data[f"{prefix}.{_mode}_bar_fill_color"] = list(getattr(self, f"{_mode}_bar_fill_color"))
            data[f"{prefix}.{_mode}_bar_border_color"] = list(getattr(self, f"{_mode}_bar_border_color"))
            data[f"{prefix}.{_mode}_bar_border_opacity"] = float(getattr(self, f"{_mode}_bar_border_opacity"))
            data[f"{prefix}.{_mode}_dynamic_floor"] = bool(getattr(self, f"{_mode}_dynamic_floor"))
            data[f"{prefix}.{_mode}_manual_floor"] = float(getattr(self, f"{_mode}_manual_floor"))
            data[f"{prefix}.{_mode}_dynamic_range_enabled"] = bool(getattr(self, f"{_mode}_dynamic_range_enabled"))
            data[f"{prefix}.{_mode}_agc_strength"] = float(getattr(self, f"{_mode}_agc_strength"))
            data[f"{prefix}.{_mode}_input_gain"] = float(getattr(self, f"{_mode}_input_gain"))
            data[f"{prefix}.{_mode}_kick_lane_gain"] = float(getattr(self, f"{_mode}_kick_lane_gain"))
            data[f"{prefix}.{_mode}_transient_pulse_gain"] = float(getattr(self, f"{_mode}_transient_pulse_gain"))
            data[f"{prefix}.{_mode}_transient_clamp"] = float(getattr(self, f"{_mode}_transient_clamp"))
            data[f"{prefix}.{_mode}_audio_block_size"] = int(getattr(self, f"{_mode}_audio_block_size"))
            data[f"{prefix}.{_mode}_adaptive_sensitivity"] = bool(getattr(self, f"{_mode}_adaptive_sensitivity"))
            data[f"{prefix}.{_mode}_sensitivity"] = float(getattr(self, f"{_mode}_sensitivity"))
            data[f"{prefix}.{_mode}_bar_count"] = int(getattr(self, f"{_mode}_bar_count"))
        data[f"{prefix}.spectrum_lane_transient_mix"] = float(self.spectrum_lane_transient_mix)
        data[f"{prefix}.bubble_transient_mix_bass"] = float(self.bubble_transient_mix_bass)
        data[f"{prefix}.bubble_transient_mix_vocal"] = float(self.bubble_transient_mix_vocal)
        data[f"{prefix}.blob_transient_mix_bass"] = float(self.blob_transient_mix_bass)
        data[f"{prefix}.blob_transient_mix_vocal"] = float(self.blob_transient_mix_vocal)
        data[f"{prefix}.sine_wave_transient_width_mix"] = float(self.sine_wave_transient_width_mix)
        data[f"{prefix}.oscilloscope_transient_width_mix"] = float(self.oscilloscope_transient_width_mix)

        return data

    @staticmethod
    def _normalize_mode_name(mode: str) -> str:
        mode_key = str(mode).lower()
        if mode_key in PER_MODE_TECHNICAL_MODES:
            return mode_key
        return PER_MODE_TECHNICAL_MODES[0]

    def _mode_attr_name(self, mode: str, base_key: str) -> str:
        normalized = self._normalize_mode_name(mode)
        return f"{normalized}_{base_key}"

    def resolve_dynamic_floor(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "dynamic_floor")))

    def resolve_manual_floor(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "manual_floor")))

    def resolve_dynamic_range_enabled(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "dynamic_range_enabled")))

    def resolve_agc_strength(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "agc_strength")))

    def resolve_input_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "input_gain")))

    def resolve_kick_lane_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "kick_lane_gain"), 1.0))

    def resolve_transient_pulse_gain(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "transient_pulse_gain"), 1.0))

    def resolve_transient_clamp(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "transient_clamp"), 1.5))

    def resolve_audio_block_size(self, mode: str) -> int:
        return int(getattr(self, self._mode_attr_name(mode, "audio_block_size")))

    def resolve_adaptive_sensitivity(self, mode: str) -> bool:
        return bool(getattr(self, self._mode_attr_name(mode, "adaptive_sensitivity")))

    def resolve_sensitivity(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "sensitivity")))

    def resolve_bar_count(self, mode: str) -> int:
        return int(getattr(self, self._mode_attr_name(mode, "bar_count")))

    def resolve_bar_fill_color(self, mode: str) -> list:
        return list(getattr(self, self._mode_attr_name(mode, "bar_fill_color")))

    def resolve_bar_border_color(self, mode: str) -> list:
        return list(getattr(self, self._mode_attr_name(mode, "bar_border_color")))

    def resolve_bar_border_opacity(self, mode: str) -> float:
        return float(getattr(self, self._mode_attr_name(mode, "bar_border_opacity")))

    def resolve_spectrum_lane_transient_mix(self) -> float:
        return float(self.spectrum_lane_transient_mix)

    def resolve_bubble_transient_mix_bass(self) -> float:
        return float(self.bubble_transient_mix_bass)

    def resolve_bubble_transient_mix_vocal(self) -> float:
        return float(self.bubble_transient_mix_vocal)

    def resolve_blob_transient_mix_bass(self) -> float:
        return float(self.blob_transient_mix_bass)

    def resolve_blob_transient_mix_vocal(self) -> float:
        return float(self.blob_transient_mix_vocal)

    def resolve_sine_wave_transient_width_mix(self) -> float:
        return float(self.sine_wave_transient_width_mix)

    def resolve_oscilloscope_transient_width_mix(self) -> float:
        return float(self.oscilloscope_transient_width_mix)

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
            subreddit=settings.get(f"{prefix}.subreddit", "technology"),
            limit=int(settings.get(f"{prefix}.limit", 10)),
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
            subreddit=_get("subreddit", "technology"),
            limit=int(_get("limit", 10)),
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


@dataclass
class AppSettings:
    """Complete application settings container."""
    display: DisplaySettings = field(default_factory=DisplaySettings)
    transitions: TransitionSettings = field(default_factory=TransitionSettings)
    input: InputSettings = field(default_factory=InputSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    sources: SourceSettings = field(default_factory=SourceSettings)
    shadows: ShadowSettings = field(default_factory=ShadowSettings)
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    
    @classmethod
    def from_settings(cls, settings: "SettingsManager") -> "AppSettings":
        """Load all settings from SettingsManager."""
        return cls(
            display=DisplaySettings.from_settings(settings),
            transitions=TransitionSettings.from_settings(settings),
            input=InputSettings.from_settings(settings),
            cache=CacheSettings.from_settings(settings),
            sources=SourceSettings.from_settings(settings),
            shadows=ShadowSettings.from_settings(settings),
            accessibility=AccessibilitySettings.from_settings(settings),
        )


