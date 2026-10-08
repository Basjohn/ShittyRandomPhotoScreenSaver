"""Committed CUSTOM hydration helpers for retained Quick presentations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from rendering.custom_layout_contract import (
    CONTENT_SIZED_PAYLOAD_KEY,
    CustomLayoutEntry,
    clamp_local_rect_to_bounds,
    denormalize_local_rect,
    deserialize_custom_layout_entry,
    get_screen_layout_entries_for_screen,
    get_screen_layout_entries_for_aliases,
    get_screen_signature,
    get_screen_signature_aliases,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
)
from rendering.custom_layout_session import normalize_geometry_variant
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.widget_descriptors import is_custom_position_selected_for_widget


def clock_geometry_variant(
    widgets: Mapping[str, Any],
    widget_id: str,
    display_signature: str | None,
) -> str:
    """The Clock face variant the retained presentation uses on one display.

    Secondary clocks inherit the base Clock's face, and per-display toggles
    persist in ``display_mode_overrides`` under the display signature. Pre-bind
    committed geometry and Settings Arrange must both consume this exact
    projection; using only a section's own ``display_mode`` makes a correctly
    persisted analogue/digital presentation read the *other* geometry variant.
    """

    from rendering.quick.widgets.clock import ClockPresentationConfig

    config = ClockPresentationConfig.from_widgets_mapping(
        widget_id,
        widgets,
        display_signature=display_signature,
    )
    return normalize_geometry_variant(config.display_mode)


def _clock_variant_from_widgets(
    widgets: Mapping[str, Any],
    widget_id: str,
    *,
    screen: Any | None = None,
) -> str:
    """Resolve the same Clock mode variant the retained presentation will use."""

    display_signature = get_screen_signature(screen) if screen is not None else None
    return clock_geometry_variant(widgets, widget_id, display_signature)


def geometry_variant_for_presentation(
    widget_id: str,
    presentation: object | None,
    widgets: Mapping[str, Any] | None = None,
) -> str:
    """Resolve the independently persisted variant for one live presentation."""

    if widget_id == "spotify_visualizer":
        controller = getattr(presentation, "controller", None)
        mode_id = getattr(controller, "mode_id", None)
        if mode_id is None and isinstance(widgets, Mapping):
            section = widgets.get("spotify_visualizer", {})
            mode_id = section.get("mode") if isinstance(section, Mapping) else None
        from core.settings.visualizer_mode_registry import (
            coerce_visualizer_mode_id,
            get_visualizer_geometry_profile,
        )

        return get_visualizer_geometry_profile(
            coerce_visualizer_mode_id(str(mode_id or "spectrum"))
        )
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



def resolve_committed_visualizer_rect(entry: CustomLayoutEntry, screen_size: Any) -> Any:
    """Display-local rect of a committed Visualizer entry (QSize ``screen_size``).

    A content-sized entry resolves its saved width/height at its placement
    anchor; an explicit entry is its stored rectangle kept on the display.
    """

    from rendering.custom_layout_contract import (
        CONTENT_SIZED_PAYLOAD_KEY,
        PLACEMENT_ANCHOR_PAYLOAD_KEY,
        resolve_content_sized_rect,
    )

    payload = entry.size_payload
    if payload.get(CONTENT_SIZED_PAYLOAD_KEY) is True:
        return resolve_content_sized_rect(
            entry.rect,
            payload.get(PLACEMENT_ANCHOR_PAYLOAD_KEY),
            (float(payload.get("width", 100)), float(payload.get("height", 80))),
            screen_size,
        )
    return clamp_local_rect_to_bounds(denormalize_local_rect(entry.rect, screen_size), screen_size)


def resolve_quick_committed_entry(
    widgets: Mapping[str, Any],
    screen: Any,
    widget_id: str,
) -> CustomLayoutEntry | None:
    """The committed entry one live screen presents, in the variant it presents.

    A Clock keeps analogue/digital entries apart; its entry is the one for the
    face this screen shows. Resolving the ``default`` variant for a Clock finds
    nothing, which dropped content-sized Clock placements at generation start.
    """

    if widget_id == "spotify_visualizer":
        section = widgets.get(widget_id, {})
        mode_id = section.get("mode") if isinstance(section, Mapping) else "spectrum"
        return resolve_visualizer_custom_entry(widgets, screen, mode_id)
    variant = (
        _clock_variant_from_widgets(widgets, widget_id, screen=screen)
        if widget_id in {"clock", "clock2", "clock3"}
        else "default"
    )
    return resolve_quick_custom_entry(widgets, screen, widget_id, geometry_variant=variant)


def resolve_visualizer_custom_entry(
    widgets: Mapping[str, Any],
    screen: Any,
    mode_id: object,
    *,
    legacy_geometry_profile: str | None = None,
) -> CustomLayoutEntry | None:
    return resolve_visualizer_custom_entry_for_aliases(
        widgets, get_screen_signature_aliases(screen), mode_id,
        legacy_geometry_profile=legacy_geometry_profile,
    )


def resolve_visualizer_custom_entry_for_aliases(
    widgets: Mapping[str, Any],
    signature_aliases: tuple[str, ...],
    mode_id: object,
    *,
    legacy_geometry_profile: str | None = None,
) -> CustomLayoutEntry | None:
    """Resolve one Visualizer profile with legacy input interpretation.

    A legacy ``default`` entry has no family identity.  It is therefore read
    only for the authored active mode's family when that profile has no record, which
    preserves the pose an existing installation actually authored without
    cloning it into the other family.  Once a named profile exists it is the
    sole authority, including when its payload is invalid (that profile then
    falls back through the normal authored baseline rather than reviving a
    stale legacy pose).
    """

    from core.settings.visualizer_mode_registry import (
        coerce_visualizer_mode_id,
        get_visualizer_geometry_profile,
    )

    if not is_custom_position_selected_for_widget("spotify_visualizer", widgets):
        return None
    profile = get_visualizer_geometry_profile(
        coerce_visualizer_mode_id(str(mode_id or "spectrum"))
    )
    custom_map = load_custom_layout_map(widgets)
    _matched, entries = get_screen_layout_entries_for_aliases(custom_map, signature_aliases)
    profile_payload = get_widget_layout_variant_payload(
        entries,
        "spotify_visualizer",
        profile,
    )
    # Normalization drops non-mapping payloads. Their named key still marks a
    # corrupt authored profile, so it must not resurrect legacy geometry.
    raw_map = widgets.get("custom_layout", {})
    _, raw_entries = get_screen_layout_entries_for_aliases(
        raw_map if isinstance(raw_map, Mapping) else {}, signature_aliases
    )
    variants = raw_entries.get("spotify_visualizer", {})
    if isinstance(variants, Mapping) and profile in variants:
        return deserialize_custom_layout_entry(
            "spotify_visualizer", profile, profile_payload
        )
    section = widgets.get("spotify_visualizer", {})
    authored_mode = section.get("mode") if isinstance(section, Mapping) else None
    authored_profile = get_visualizer_geometry_profile(
        coerce_visualizer_mode_id(str(authored_mode or "spectrum"))
    )
    if profile != (legacy_geometry_profile or authored_profile):
        return None
    legacy_payload = get_widget_layout_variant_payload(
        entries, "spotify_visualizer", "default"
    )
    return deserialize_custom_layout_entry(
        "spotify_visualizer", "default", legacy_payload
    )


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
    ) -> tuple[OverlayWidgetGeometry, dict[str, object]] | None:
        # Content-sized entries are resolved only by OverlayGeometryBinding once
        # the retained item reports its real content.  Returning the historical
        # stored outer box here would seed Clock's variant handler with a guessed
        # explicit rectangle and later fight the live content policy.
        if source.size_payload.get(CONTENT_SIZED_PAYLOAD_KEY) is True:
            return None
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

    source_state = _state_from_entry(source_entry)
    if source_state is None:
        return None
    source_geometry, source_payload = source_state
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

    if widget_id == "spotify_visualizer":
        entry = resolve_quick_committed_entry(widgets, screen, widget_id)
        if entry is None:
            return None
        local = resolve_committed_visualizer_rect(entry, screen.geometry().size())
        return OverlayWidgetGeometry(
            float(local.x()), float(local.y()), float(local.width()), float(local.height())
        )
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
        entry = resolve_quick_custom_entry(
            widgets, screen, widget_id, geometry_variant=variant,
        )
        state = resolve_quick_committed_variant_state(
            widgets,
            screen,
            widget_id,
            geometry_variant=variant,
        )
        if state is None and entry is None:
            continue
        size_payload = dict(entry.size_payload) if entry is not None else state[1]
        retained = host.presentation_for_model_identity(widget_id)
        if retained is not None:
            retained.apply_custom_layout_size_payload(size_payload)


__all__ = [
    "apply_quick_committed_payloads",
    "clock_geometry_variant",
    "resolve_committed_visualizer_rect",
    "geometry_variant_for_presentation",
    "resolve_quick_committed_entry",
    "resolve_quick_committed_geometry",
    "resolve_quick_committed_variant_state",
    "resolve_quick_custom_entry",
    "resolve_visualizer_custom_entry",
    "resolve_visualizer_custom_entry_for_aliases",
]
