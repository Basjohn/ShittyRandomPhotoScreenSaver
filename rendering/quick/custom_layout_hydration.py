"""Committed CUSTOM hydration helpers for retained Quick presentations."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rendering.custom_layout_contract import (
    CustomLayoutEntry,
    clamp_local_rect_to_bounds,
    denormalize_local_rect,
    deserialize_custom_layout_entry,
    get_screen_layout_entries_for_screen,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
)
from rendering.custom_layout_session import normalize_geometry_variant
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.widget_descriptors import is_custom_position_selected_for_widget


def _clock_variant_from_widgets(
    widgets: Mapping[str, Any], widget_id: str
) -> str:
    section = widgets.get(widget_id, {})
    if not isinstance(section, Mapping):
        return "default"
    return normalize_geometry_variant(section.get("display_mode", "digital"))


def geometry_variant_for_presentation(
    widget_id: str,
    presentation: object | None,
    widgets: Mapping[str, Any] | None = None,
) -> str:
    """Resolve the independently persisted variant for one live presentation."""

    if widget_id not in {"clock", "clock2", "clock3"}:
        return "default"
    model = getattr(presentation, "model", None)
    config = getattr(model, "config", None)
    mode = getattr(config, "display_mode", None)
    if mode is None and isinstance(widgets, Mapping):
        return _clock_variant_from_widgets(widgets, widget_id)
    return normalize_geometry_variant(mode or "digital")


def resolve_quick_custom_entry(
    widgets: Mapping[str, Any],
    screen: Any,
    widget_id: str,
    *,
    geometry_variant: str = "default",
) -> CustomLayoutEntry | None:
    """Resolve one currently selected committed CUSTOM entry for a live screen."""

    if not is_custom_position_selected_for_widget(widget_id, widgets):
        return None
    custom_map = load_custom_layout_map(widgets)
    _matched, entries = get_screen_layout_entries_for_screen(custom_map, screen)
    payload = get_widget_layout_variant_payload(
        entries,
        widget_id,
        geometry_variant,
    )
    return deserialize_custom_layout_entry(widget_id, geometry_variant, payload)


def resolve_quick_committed_geometry(
    widgets: Mapping[str, Any],
    screen: Any,
    widget_id: str,
) -> OverlayWidgetGeometry | None:
    """Return a display-local committed rect for pre-bind family admission."""

    variant = (
        _clock_variant_from_widgets(widgets, widget_id)
        if widget_id in {"clock", "clock2", "clock3"}
        else "default"
    )
    entry = resolve_quick_custom_entry(
        widgets,
        screen,
        widget_id,
        geometry_variant=variant,
    )
    if entry is None:
        return None
    local = clamp_local_rect_to_bounds(
        denormalize_local_rect(entry.rect, screen.geometry().size()),
        screen.geometry().size(),
    )
    return OverlayWidgetGeometry(
        float(local.x()),
        float(local.y()),
        float(local.width()),
        float(local.height()),
    )


def apply_quick_committed_payloads(
    unit: Any,
    widgets: Mapping[str, Any],
) -> None:
    """Hydrate saved family size payloads into already-bound retained items."""

    screen = unit.runtime.window.screen()
    host = unit.runtime.scene_controller.ordinary_widget_host
    for widget_id in unit.presenter.bound_widget_ids:
        presentation = unit.presenter.presentation_for_widget_id(widget_id)
        variant = geometry_variant_for_presentation(widget_id, presentation, widgets)
        entry = resolve_quick_custom_entry(
            widgets,
            screen,
            widget_id,
            geometry_variant=variant,
        )
        if entry is None:
            continue
        retained = host.presentation_for_model_identity(widget_id)
        if retained is not None:
            retained.apply_custom_layout_size_payload(entry.size_payload)


__all__ = [
    "apply_quick_committed_payloads",
    "geometry_variant_for_presentation",
    "resolve_quick_committed_geometry",
    "resolve_quick_custom_entry",
]
