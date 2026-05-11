"""
Settings dataclass models for type-safe settings access.

This package provides typed dataclass models for all settings sections,
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
# Re-export all public symbols for backward compatibility.
# All existing ``from core.settings.models import X`` statements continue to work.

from core.settings.models._enums import (  # noqa: F401
    DisplayMode,
    TransitionType,
    WidgetPosition,
    coerce_widget_position,
)

from core.settings.models._core import (  # noqa: F401
    CacheSettings,
    ClockWidgetSettings,
    DisplaySettings,
    InputSettings,
    ShadowSettings,
    SourceSettings,
    TransitionSettings,
)

from core.settings.models._visualizer_helpers import (  # noqa: F401
    PER_MODE_TECHNICAL_MODES,
    _ACTIVE_MODE_SHARED_VISUAL_KEYS,
    _ACTIVE_MODE_TECHNICAL_KEYS,
    _SPECTRUM_DEFAULT_LANE_STRENGTHS_LINEAR,
    _SPECTRUM_DEFAULT_LANE_STRENGTHS_MIRRORED,
    _SPECTRUM_DEFAULT_NOTCHES_LINEAR,
    _build_live_visualizer_mode_kwargs,
    _build_live_visualizer_mode_shared_visual_kwargs,
    _clamp_lane_strength,
    _coerce_live_visualizer_bool,
    _coerce_live_visualizer_float,
    _coerce_live_visualizer_int,
    _normalize_spectrum_lane_strengths,
    _normalize_spectrum_linear_notches,
    _normalize_visualizer_direction,
    _resolve_active_mode_technical_state,
    _resolve_active_mode_shared_visual_state,
)

from core.settings.models._spotify_visualizer import (  # noqa: F401
    SpotifyVisualizerSettings,
)

from core.settings.models._widget_settings import (  # noqa: F401
    AccessibilitySettings,
    MediaWidgetSettings,
    RedditWidgetSettings,
    WeatherWidgetSettings,
)

from core.settings.models._app import (  # noqa: F401
    AppSettings,
)
