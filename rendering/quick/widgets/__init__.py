"""Per-display retained ordinary-widget presentation host and style records."""

from __future__ import annotations

from .host import (
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
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
    "ORDINARY_WIDGET_FAMILY_COMPONENTS",
    "OrdinaryWidgetFamilyComponent",
    "ordinary_widget_family_component",
]
