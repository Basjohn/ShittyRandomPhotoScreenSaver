"""Presentation-neutral persistence transaction for CUSTOM edit sessions.

Both the retained runtime editor and Settings' future Arrange surface stage a
``CustomLayoutSession``.  This module is the one place where that transaction
becomes the canonical widgets mapping; it deliberately owns no QML/runtime
objects, settings manager, or cadence.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QRect

from rendering.custom_layout_contract import (
    CONTENT_SIZED_PAYLOAD_KEY,
    PLACEMENT_ANCHOR_PAYLOAD_KEY,
    CustomLayoutEntry,
    canonicalize_screen_layout_bucket,
    canonicalize_screen_layout_aliases,
    choose_content_placement_anchor,
    clamp_local_rect_to_bounds,
    get_screen_signature_aliases,
    load_custom_layout_map,
    normalize_local_rect,
    remove_screen_layout_entry,
    set_screen_layout_entry,
    write_custom_layout_map,
)
from rendering.custom_layout_session import CustomLayoutSession, CustomLayoutSessionItem
from rendering.quick.custom_layout_size import CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY
from rendering.quick.custom_layout_size import quick_custom_minimum_size
from widgets.spotify_visualizer.presentation_orientation import (
    CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY,
    CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY,
    normalize_content_rotation_by_mode,
)
from widgets.spotify_visualizer.render_state import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
from rendering.widget_descriptors import (
    WidgetRuntimeDescriptor,
    get_custom_persistence_monitor_settings_key_for_widget,
    get_custom_persistence_position_settings_key_for_widget,
    sync_custom_layout_restore_routes,
    widget_writes_custom_monitor_key,
    widget_writes_custom_position_key,
)


def _is_all(route: object) -> bool:
    return str(route or "ALL").strip().upper() == "ALL"


def _display_parts(value: object) -> tuple[tuple[str, ...], QRect, str, object | None]:
    """Accept the public Arrange tuple and the runtime's display binding."""

    if isinstance(value, tuple) and len(value) == 3:
        aliases, geometry, route = value
        resolved = tuple(str(alias) for alias in aliases if str(alias))
        if not resolved or not isinstance(geometry, QRect):
            raise ValueError("CUSTOM commit display requires aliases and QRect geometry")
        return resolved, QRect(geometry), str(route or "ALL"), None
    screen = getattr(value, "screen", None)
    geometry = getattr(value, "geometry", None)
    route = getattr(value, "monitor_route", "ALL")
    if screen is None or not isinstance(geometry, QRect):
        raise TypeError("CUSTOM commit display must be (aliases, QRect, route)")
    return get_screen_signature_aliases(screen), QRect(geometry), str(route or "ALL"), screen


def _canonicalize_alias_bucket(custom_map: dict[str, Any], aliases: tuple[str, ...]) -> str:
    """Tuple-display equivalent of screen bucket canonicalization.

    Arrange has aliases rather than QScreen wrappers, but must retain the same
    canonical-first merge semantics as the runtime path.
    """
    return canonicalize_screen_layout_aliases(custom_map, aliases) or aliases[0]


def _migrate_visualizer_legacy_entries(custom_map: dict[str, Any], legacy_variant: str | None) -> None:
    """Promote only the interpreted legacy family; retire default on canonical writes."""
    displays = custom_map.get("displays", {})
    if isinstance(displays, dict):
        for saved_signature in tuple(displays):
            layouts = displays.get(saved_signature)
            variants = (
                layouts.get("spotify_visualizer")
                if isinstance(layouts, dict)
                else None
            )
            if isinstance(variants, dict):
                legacy_payload = variants.get("default")
                if legacy_variant and legacy_variant not in variants and isinstance(legacy_payload, Mapping):
                    variants[legacy_variant] = deepcopy(legacy_payload)
            remove_screen_layout_entry(
                custom_map,
                str(saved_signature),
                "spotify_visualizer",
                "default",
            )


def migrate_visualizer_legacy_geometry(widgets: dict[str, Any], legacy_variant: str) -> None:
    """Preserve a legacy pose before persisting a new active Visualizer mode.

    This uses the same canonical write boundary as CUSTOM Save. The mode save
    would otherwise reinterpret the legacy pose as its new family at restart.
    """
    custom_map = load_custom_layout_map(widgets)
    _migrate_visualizer_legacy_entries(custom_map, legacy_variant)
    write_custom_layout_map(widgets, custom_map)


def _write_item(
    widgets: dict[str, Any],
    custom_map: dict[str, Any],
    item: CustomLayoutSessionItem,
    descriptor: WidgetRuntimeDescriptor,
    monitor_route: str,
    display: object,
) -> None:
    aliases, geometry, _route, screen = _display_parts(display)
    signature = canonicalize_screen_layout_bucket(custom_map, screen) if screen is not None else _canonicalize_alias_bucket(custom_map, aliases)
    signature = signature or aliases[0]
    if _is_all(monitor_route):
        for alias in aliases:
            remove_screen_layout_entry(custom_map, alias, item.model_identity, item.source_key.geometry_variant)
    else:
        displays = custom_map.get("displays", {})
        if isinstance(displays, dict):
            for other in tuple(displays):
                if other != signature:
                    remove_screen_layout_entry(custom_map, str(other), item.model_identity, item.source_key.geometry_variant)
    local = clamp_local_rect_to_bounds(
        QRect(item.current_global_rect.x() - geometry.x(), item.current_global_rect.y() - geometry.y(), item.current_global_rect.width(), item.current_global_rect.height()),
        geometry.size(), min_size=quick_custom_minimum_size(item),
    )
    payload = dict(item.current_size_payload)
    if descriptor.custom_layout_resize_mode != "visualizer_rect":
        payload[CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY] = float(item.resize_scale)
    if descriptor.custom_layout_resize_mode == "clock_font":
        payload.pop("display_mode", None)
    if descriptor.custom_layout_resize_mode == "visualizer_rect":
        extent = item.current_viewport_extent
        canonical = CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
        if extent is not None and (abs(extent[0] - canonical[0]) >= 0.5 or abs(extent[1] - canonical[1]) >= 0.5):
            payload["viewport_extent"] = [extent[0], extent[1]]
        else:
            payload.pop("viewport_extent", None)
        rotations = normalize_content_rotation_by_mode(payload.get(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, {}))
        payload.pop(CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY, None)
        if rotations:
            payload[CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY] = rotations
        else:
            payload.pop(CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY, None)
    if item.content_sized:
        payload[CONTENT_SIZED_PAYLOAD_KEY] = True
        payload[PLACEMENT_ANCHOR_PAYLOAD_KEY] = (
            item.placement_anchor
            or payload.get(PLACEMENT_ANCHOR_PAYLOAD_KEY)
            or choose_content_placement_anchor(local, geometry.size())
        )
    else:
        payload.pop(CONTENT_SIZED_PAYLOAD_KEY, None)
        payload.pop(PLACEMENT_ANCHOR_PAYLOAD_KEY, None)
    if item.content_extent_capable and item.current_content_extent is not None:
        payload["content_extent"] = list(item.current_content_extent)
    elif not item.content_sized:
        payload.pop("content_extent", None)
    set_screen_layout_entry(custom_map, signature, item.model_identity, CustomLayoutEntry(
        widget_id=item.model_identity,
        geometry_variant=item.source_key.geometry_variant,
        rect=normalize_local_rect(local, geometry.size()),
        size_payload=payload,
        resize_mode=descriptor.custom_layout_resize_mode,
    ))
    if (
        item.model_identity == "spotify_visualizer"
        and item.source_key.geometry_variant != "default"
    ):
        _migrate_visualizer_legacy_entries(custom_map, item.legacy_geometry_variant)
    if widget_writes_custom_position_key(item.model_identity):
        section = widgets.setdefault(get_custom_persistence_position_settings_key_for_widget(item.model_identity), {})
        if not isinstance(section, dict):
            section = {}; widgets[get_custom_persistence_position_settings_key_for_widget(item.model_identity)] = section
        section["position"] = "Custom"
    if widget_writes_custom_monitor_key(item.model_identity):
        section = widgets.setdefault(get_custom_persistence_monitor_settings_key_for_widget(item.model_identity), {})
        if not isinstance(section, dict):
            section = {}; widgets[get_custom_persistence_monitor_settings_key_for_widget(item.model_identity)] = section
        section["monitor"] = str(monitor_route or "ALL")


def commit_custom_session(
    widgets: dict[str, Any],
    session: CustomLayoutSession,
    descriptors: Mapping[object, WidgetRuntimeDescriptor],
    displays: Mapping[str, object],
) -> dict[str, Any]:
    """Commit a staged CUSTOM session into ``widgets`` and return that mapping.

    ``displays`` maps display identity to ``(signature aliases, QRect geometry,
    monitor route)``.  Runtime callers may pass their existing binding objects;
    that adapter exists only to keep this mutation boundary presentation-neutral.
    """
    sync_custom_layout_restore_routes(widgets)
    custom_map = load_custom_layout_map(widgets)
    grouped: dict[str, list[CustomLayoutSessionItem]] = {}
    for item in session.items():
        grouped.setdefault(item.model_identity, []).append(item)
    for widget_id, items in grouped.items():
        section = widgets.setdefault(widget_id, {})
        if not isinstance(section, dict):
            section = {}; widgets[widget_id] = section
        section["enabled"] = any(item.current_enabled and not item.removed for item in items)
        for removed in (item for item in items if item.removed):
            source = displays.get(removed.source_key.display_identity)
            if source is None:
                continue
            aliases, _geometry, _route, _screen = _display_parts(source)
            for alias in aliases:
                remove_screen_layout_entry(custom_map, alias, widget_id, removed.source_key.geometry_variant)
        survivors = [item for item in items if not item.removed]
        source_had_duplicates = len(items) > 1
        for item in survivors:
            display = displays[item.current_display_identity]
            _aliases, _geometry, route, _screen = _display_parts(display)
            monitor = item.current_monitor_route
            if widget_id == "spotify_visualizer" or item.current_display_identity != item.source_key.display_identity or (source_had_duplicates and len(survivors) == 1 and _is_all(item.source_monitor_route)):
                monitor = route
            descriptor = descriptors[item.source_key]
            _write_item(widgets, custom_map, item, descriptor, monitor, display)
    write_custom_layout_map(widgets, custom_map)
    return widgets


__all__ = ["commit_custom_session", "migrate_visualizer_legacy_geometry"]
