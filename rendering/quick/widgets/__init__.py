"""Per-display retained ordinary-widget presentation host and style records."""

from __future__ import annotations

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from .weather import (
    RetainedWeatherPresentation,
    WeatherPresentationConfig,
    WeatherPresentationModel,
    WeatherPresentationSnapshot,
    WeatherPresentationStyle,
)
from .media import (
    MediaPresentationConfig,
    MediaPresentationModel,
    MediaPresentationSnapshot,
    MediaPresentationStyle,
    RetainedMediaPresentation,
)
from .reddit import (
    RedditPresentationConfig,
    RedditPresentationModel,
    RedditPresentationRow,
    RedditPresentationSnapshot,
    RedditPresentationStyle,
    RedditRowListModel,
    RetainedRedditPresentation,
)
from .clock import (
    ClockGeometryVariantStore,
    ClockPresentationConfig,
    ClockPresentationModel,
    ClockPresentationSnapshot,
    ClockPresentationStyle,
    RetainedClockPresentation,
    normalize_clock_display_mode,
)
from .registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    OrdinaryWidgetFamilyComponent,
    ordinary_widget_family_component,
)

__all__ = [
    "OrdinaryWidgetPresentationHost",
    "ORDINARY_CARD_SHADOW_BASE",
    "ORDINARY_TEXT_SHADOW_BASE",
    "OverlayCardStyle",
    "OverlayWidgetGeometry",
    "RetainedOverlayWidget",
    "ClockGeometryVariantStore",
    "ClockPresentationConfig",
    "ClockPresentationModel",
    "ClockPresentationSnapshot",
    "ClockPresentationStyle",
    "RetainedClockPresentation",
    "normalize_clock_display_mode",
    "RetainedWeatherPresentation",
    "WeatherPresentationConfig",
    "WeatherPresentationModel",
    "WeatherPresentationSnapshot",
    "WeatherPresentationStyle",
    "MediaPresentationConfig",
    "MediaPresentationModel",
    "MediaPresentationSnapshot",
    "MediaPresentationStyle",
    "RetainedMediaPresentation",
    "RedditPresentationConfig",
    "RedditPresentationModel",
    "RedditPresentationRow",
    "RedditPresentationSnapshot",
    "RedditPresentationStyle",
    "RedditRowListModel",
    "RetainedRedditPresentation",
    "ORDINARY_WIDGET_FAMILY_COMPONENTS",
    "OrdinaryWidgetFamilyComponent",
    "ordinary_widget_family_component",
]
