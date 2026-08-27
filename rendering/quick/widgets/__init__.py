"""Dormant shared retained-widget host and static family metadata."""

from __future__ import annotations

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
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
    "ORDINARY_WIDGET_FAMILY_COMPONENTS",
    "OrdinaryWidgetFamilyComponent",
    "ordinary_widget_family_component",
]
