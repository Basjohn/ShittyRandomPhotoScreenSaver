"""Committed CUSTOM hydration helpers for retained Quick presentations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from rendering.custom_layout_contract import (
    CustomLayoutEntry,
    clamp_local_rect_to_bounds,
    denormalize_local_rect,
    deserialize_custom_layout_entry,
    get_screen_layout_entries_for_screen,
    get_screen_signature,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
)
from rendering.custom_layout_session import normalize_geometry_variant
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.widget_descriptors import is_custom_position_selected_for_widget


def _clock_variant_from_widgets(
    widgets: Mapping[str, Any],
    widget_id: str,
    *,
    screen: Any | None = None,
) -> str:
    """Resolve the same Clock mode variant the retained presentation will use.

    Per-display mode toggles persist in ``display_mode_overrides``.  Pre-bind
    committed geometry must consume that exact same identity-aware projection;
    using only the shared ``display_mode`` baseline makes a correctly persisted
    analogue/digital presentation rehydrate the *other* geometry variant.
    """

    from rendering.quick.widgets.clock import ClockPresentationConfig

    display_signature = get_screen_signature(screen) if screen is not None else None
    config = ClockPresentationConfig.from_widgets_mapping(
        widget_id,
        widgets,
        display_signature=display_signature,
    )
    return normalize_geometry_variant(config.display_mode)


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



def resolve_quick_committed_variant_state(
    widgets: Mapping[str, Any],
    screen: Any,
    widget_id: str,
    *,
    geometry_variant: str,
) -> tuple[OverlayWidgetGeometry, dict[str, object]] | None:
    """Return one committed variant rect plus detached size payload.

    Clock keeps independent analogue/digital CUSTOM variants.  If an older or
    partially-authored layout has only the opposite variant, derive the missing
    target from that rect's centre and saved font scale.  This is deterministic
    replay only; hydration does not mutate Settings. A later live toggle/save can
    canonicalize the derived variant through the normal Python persistence owner.
    """

    normalized_variant = normalize_geometry_variant(geometry_variant)
    entry = resolve_quick_custom_entry(
        widgets,
        screen,
        widget_id,
        geometry_variant=normalized_variant,
    )

    def _state_from_entry(
        source: CustomLayoutEntry,
    ) -> tuple[OverlayWidgetGeometry, dict[str, object]]:
        local = clamp_local_rect_to_bounds(
            denormalize_local_rect(source.rect, screen.geometry().size()),
            screen.geometry().size(),
        )
        return (
            OverlayWidgetGeometry(
                float(local.x()),
                float(local.y()),
                float(local.width()),
                float(local.height()),
            ),
            dict(source.size_payload),
        )

    if entry is not None:
        return _state_from_entry(entry)

    if widget_id not in {"clock", "clock2", "clock3"}:
        return None

    opposite = "analog" if normalized_variant == "digital" else "digital"
    source_entry = resolve_quick_custom_entry(
        widgets,
        screen,
        widget_id,
        geometry_variant=opposite,
    )
    if source_entry is None:
        return None

    source_geometry, source_payload = _state_from_entry(source_entry)
    from rendering.quick.widgets.clock import (
        ClockPresentationConfig,
        derive_clock_variant_geometry,
        normalize_clock_display_mode,
    )

    config = ClockPresentationConfig.from_widgets_mapping(
        widget_id,
        widgets,
        display_signature=get_screen_signature(screen),
    )
    try:
        font_size = max(8, int(source_payload.get("font_size", config.font_size)))
    except (TypeError, ValueError):
        font_size = max(8, int(config.font_size))
    target_config = replace(
        config,
        display_mode=normalize_clock_display_mode(normalized_variant),
        font_size=font_size,
    )
    screen_geometry = screen.geometry()
    derived = derive_clock_variant_geometry(
        source_geometry,
        OverlayWidgetGeometry(
            0.0,
            0.0,
            float(screen_geometry.width()),
            float(screen_geometry.height()),
        ),
        target_config,
    )
    return derived, {"font_size": font_size}


def resolve_quick_committed_geometry(
    widgets: Mapping[str, Any],
    screen: Any,
    widget_id: str,
) -> OverlayWidgetGeometry | None:
    """Return a display-local committed rect for pre-bind family admission."""

    variant = (
        _clock_variant_from_widgets(widgets, widget_id, screen=screen)
        if widget_id in {"clock", "clock2", "clock3"}
        else "default"
    )
    state = resolve_quick_committed_variant_state(
        widgets,
        screen,
        widget_id,
        geometry_variant=variant,
    )
    return None if state is None else state[0]


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
        state = resolve_quick_committed_variant_state(
            widgets,
            screen,
            widget_id,
            geometry_variant=variant,
        )
        if state is None:
            continue
        _geometry, size_payload = state
        retained = host.presentation_for_model_identity(widget_id)
        if retained is not None:
            retained.apply_custom_layout_size_payload(size_payload)


__all__ = [
    "apply_quick_committed_payloads",
    "geometry_variant_for_presentation",
    "resolve_quick_committed_geometry",
    "resolve_quick_committed_variant_state",
    "resolve_quick_custom_entry",
]
