"""Static ordinary-widget family component registry.

This registry contains presentation component metadata only. Canonical widget
membership and activation remain owned by ``widget_family_catalog``; the Quick
scene only needs to know which retained component presents an admitted family.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrdinaryWidgetFamilyComponent:
    """One retained family component admitted to the Quick scene."""

    family_id: str
    qml_filename: str
    presentation_model_kind: str


ORDINARY_WIDGET_FAMILY_COMPONENTS: tuple[OrdinaryWidgetFamilyComponent, ...] = (
    OrdinaryWidgetFamilyComponent(
        family_id="clocks",
        qml_filename="ClockPresentation.qml",
        presentation_model_kind="ClockPresentationModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="weather",
        qml_filename="WeatherPresentation.qml",
        presentation_model_kind="WeatherPresentationModel",
    ),
    OrdinaryWidgetFamilyComponent(
        family_id="media",
        qml_filename="MediaPresentation.qml",
        presentation_model_kind="MediaPresentationModel",
    ),
)


def ordinary_widget_family_component(
    family_id: str,
) -> OrdinaryWidgetFamilyComponent:
    """Return the exact static component descriptor for ``family_id``."""

    normalized = str(family_id or "").strip().lower()
    for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS:
        if descriptor.family_id == normalized:
            return descriptor
    raise KeyError(f"unknown ordinary-widget family: {family_id!r}")
