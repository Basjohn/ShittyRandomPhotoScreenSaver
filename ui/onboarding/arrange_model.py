"""Draft-only CUSTOM layout model used by Guided Setup and Quick Start.

The model has no Settings widgets, providers, QML roots, or persistence owner.
It stages the existing ``CustomLayoutSession`` and delegates the one canonical
write to :mod:`rendering.custom_layout_commit`.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from types import SimpleNamespace
from typing import Any, Mapping

from PySide6.QtCore import QPoint, QRect

from core.settings.default_contract import require_canonical_default
from core.settings.capability_activation import is_widget_family_effective
from core.settings.layout_slots import apply_layout_slot, get_layout_slot_payload, save_layout_slot
from core.settings.widget_family_catalog import get_family_id_for_widget
from rendering.custom_layout_commit import commit_custom_session
from rendering.custom_layout_contract import (
    choose_best_screen_for_global_rect,
    choose_content_placement_anchor,
    clamp_local_rect_to_bounds,
    denormalize_local_rect,
    deserialize_custom_layout_entry,
    get_widget_layout_variant_payload,
    load_custom_layout_map,
    load_custom_layout_restore_map,
    parse_content_placement_anchor,
    get_custom_layout_restore_entry,
    remove_screen_layout_entry,
    should_transfer_rect_to_screen,
    snap_local_rect_for_edit,
    write_custom_layout_map,
)
from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    normalize_child_geometry,
)
from rendering.custom_layout_session import (
    CustomLayoutKey,
    CustomLayoutSession,
    CustomLayoutSessionItem,
    normalize_viewport_extent,
)
from rendering.quick.custom_layout_size import (
    CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
    quick_custom_minimum_size,
    quick_custom_payload_minimum_scale,
    scale_quick_size_payload,
)
from rendering.widget_descriptors import (
    WidgetRuntimeDescriptor,
    get_widget_runtime_descriptors,
    get_effective_position_settings_key_for_widget,
    get_custom_persistence_monitor_settings_key_for_widget,
    get_custom_persistence_position_settings_key_for_widget,
)
from ui.widget_stack_predictor import build_widget_estimates
from rendering.widget_stacking import DisplayStackParticipant, build_display_stack_plan


@dataclass(frozen=True)
class ArrangeDisplay:
    identity: str
    signature_aliases: tuple[str, ...]
    geometry: QRect
    monitor_route: str

    def commit_value(self) -> tuple[tuple[str, ...], QRect, str]:
        return self.signature_aliases, QRect(self.geometry), self.monitor_route


class _ArrangeScreen:
    """Minimal screen adapter for the shared transfer policy."""

    def __init__(self, display: ArrangeDisplay) -> None:
        self.identity = display.identity
        self._geometry = QRect(display.geometry)

    def geometry(self) -> QRect:
        return QRect(self._geometry)


class ArrangeModel:
    """One discardable layout draft with only neutral CUSTOM operations."""

    def __init__(self, widgets: Mapping[str, Any], displays: tuple[ArrangeDisplay, ...]) -> None:
        self._committed = deepcopy(dict(widgets))
        self.widgets = deepcopy(dict(widgets))
        self.displays = tuple(displays)
        self._display_map = {display.identity: display for display in self.displays}
        self._screen_map = {display.identity: _ArrangeScreen(display) for display in self.displays}
        self.descriptors = {descriptor.widget_id: descriptor for descriptor in get_widget_runtime_descriptors()}
        self.session = CustomLayoutSession()
        self._descriptors_by_key: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        self._authored_keys: set[CustomLayoutKey] = set()
        self._reset_keys: set[CustomLayoutKey] = set()
        self._dirty = False
        self._estimates: dict[str, Any] = {}
        self._build_session()

    def _refresh_estimates(self) -> None:
        """Rebuild authored estimates from the current draft Settings map."""

        self._estimates = {
            str(estimate.widget_type.value): estimate
            for estimate in build_widget_estimates(
                self.widgets, defaults=require_canonical_default("widgets")
            )
        }

    @property
    def pending(self) -> bool:
        return self._dirty

    def _effective(self, descriptor: WidgetRuntimeDescriptor) -> bool:
        section = self._section_for(descriptor)
        if not isinstance(section, Mapping) or not bool(section.get("enabled", False)):
            return False
        family = get_family_id_for_widget(descriptor.widget_id)
        return family is None or is_widget_family_effective(self.widgets, family)

    def _section_for(self, descriptor: WidgetRuntimeDescriptor) -> Mapping[str, Any]:
        section = self.widgets.get(descriptor.widget_id, {})
        return section if isinstance(section, Mapping) else {}

    def _route_section_for(self, descriptor: WidgetRuntimeDescriptor) -> Mapping[str, Any]:
        key = get_effective_position_settings_key_for_widget(descriptor.widget_id, self.widgets)
        section = self.widgets.get(key, {})
        return section if isinstance(section, Mapping) else {}

    def _variants_for(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay) -> tuple[str, ...]:
        if descriptor.widget_id not in {"clock", "clock2", "clock3"}:
            return ("default",)
        section = self._section_for(descriptor)
        if not isinstance(section, Mapping):
            return ("digital",)
        overrides = section.get("display_mode_overrides", {})
        mode = next((overrides.get(alias) for alias in display.signature_aliases if isinstance(overrides, Mapping) and overrides.get(alias)), section.get("display_mode", "digital"))
        return (str(mode or "digital").lower().replace("analogue", "analog"),)

    def _routed_displays(self, descriptor: WidgetRuntimeDescriptor) -> tuple[ArrangeDisplay, ...]:
        section = self._route_section_for(descriptor)
        route = str(section.get("monitor", "ALL")) if isinstance(section, Mapping) else "ALL"
        if route.upper() == "ALL":
            return self.displays
        return tuple(display for display in self.displays if display.monitor_route == route)

    def _authored_rect(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay, *, include_stack: bool = True) -> QRect:
        section = self._route_section_for(descriptor)
        estimate = self._estimates.get(descriptor.widget_id)
        if estimate is None:
            # The Settings stack predictor intentionally omits the transient
            # System Audio OSD.  Its normal presentation contract already owns
            # a configured outer preferred box, so use that exact canonical
            # metadata rather than synthesising a generic canvas fallback.
            configured_width = section.get("preferred_width") if isinstance(section, Mapping) else None
            configured_height = section.get("preferred_height") if isinstance(section, Mapping) else None
            try:
                width, height = int(configured_width), int(configured_height)
            except (TypeError, ValueError):
                width = height = 0
            if width > 0 and height > 0:
                estimate = SimpleNamespace(
                    estimated_width=width,
                    estimated_height=height,
                    position=section.get("position"),
                )

        if estimate is None:
            # A partial per-display reset leaves another display CUSTOM.  Project
            # the saved authored route only for this canvas estimate.
            projected = deepcopy(self.widgets)
            restore = get_custom_layout_restore_entry(
                load_custom_layout_restore_map(projected), descriptor.widget_id,
            )
            route_key = get_effective_position_settings_key_for_widget(descriptor.widget_id, projected)
            route = projected.get(route_key)
            if not isinstance(route, dict) or restore is None:
                raise ValueError(f"Arrange has no current size estimate for authored {descriptor.widget_id!r}")
            route["position"] = restore["position"]; route["monitor"] = restore["monitor"]
            estimate = next((entry for entry in build_widget_estimates(projected, defaults=require_canonical_default("widgets")) if str(entry.widget_type.value) == descriptor.widget_id), None)
            if estimate is None:
                raise ValueError(f"Arrange has no restored size estimate for {descriptor.widget_id!r}")
        if not isinstance(section, Mapping):
            raise ValueError(f"Arrange has no widget settings section for {descriptor.widget_id!r}")
        margin = int(section["margin"])
        width, height = int(estimate.estimated_width), int(estimate.estimated_height)
        width, height = min(width, display.geometry.width()), min(height, display.geometry.height())
        position = str(estimate.position).casefold()
        x = margin if "left" in position else (display.geometry.width() - width - margin if "right" in position else (display.geometry.width() - width) // 2)
        y = margin if "top" in position else (display.geometry.height() - height - margin if "bottom" in position else (display.geometry.height() - height) // 2)
        base = QRect(display.geometry.x() + x, display.geometry.y() + y, width, height)
        if not include_stack or not bool(self.widgets.get("global", {}).get("stacking_enabled", require_canonical_default("widgets.global.stacking_enabled"))):
            return base
        offset = self._stack_offset(descriptor, display)
        return base.translated(offset.x(), offset.y())

    def _stack_offset(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay) -> QPoint:
        """Project the runtime's authored stacking plan into the draft canvas."""

        participants: list[DisplayStackParticipant] = []
        for order, candidate in enumerate(self.descriptors.values()):
            if not candidate.supports_custom_position_slot or not self._effective(candidate):
                continue
            if display not in self._routed_displays(candidate):
                continue
            if self._existing_entry(candidate, display, self._variants_for(candidate, display)[0]) is not None:
                continue
            section = self._route_section_for(candidate)
            if str(section.get("position", "")).strip().casefold() == "custom":
                continue
            rect = self._authored_rect(candidate, display, include_stack=False)
            participants.append(DisplayStackParticipant(
                key=candidate.widget_id,
                position_key=str(section.get("position", "Top Right")),
                base_x=rect.x() - display.geometry.x(),
                base_y=rect.y() - display.geometry.y(),
                width=rect.width(), height=rect.height(), order=order,
                margin=int(section.get("margin", 0) or 0),
            ))
        plan = build_display_stack_plan(
            participants,
            container_width=display.geometry.width(),
            container_height=display.geometry.height(),
        )
        placement = plan.placements.get(descriptor.widget_id)
        return QPoint(placement.offset_x, placement.offset_y) if placement is not None else QPoint()

    def _existing_entry(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay, variant: str):
        custom = load_custom_layout_map(self.widgets)
        layouts = custom.get("displays", {})
        if not isinstance(layouts, Mapping):
            return None
        bucket = next((layouts.get(alias) for alias in display.signature_aliases if isinstance(layouts.get(alias), Mapping)), None)
        if not isinstance(bucket, Mapping):
            return None
        payload = get_widget_layout_variant_payload(bucket, descriptor.widget_id, variant)
        return deserialize_custom_layout_entry(descriptor.widget_id, variant, payload)

    def _build_session(self) -> None:
        self._refresh_estimates()
        self.session = CustomLayoutSession()
        self._descriptors_by_key.clear()
        self._authored_keys.clear()
        for descriptor in self.descriptors.values():
            if not descriptor.supports_custom_position_slot or not self._effective(descriptor):
                continue
            for display in self._routed_displays(descriptor):
                for variant in self._variants_for(descriptor, display):
                    key = CustomLayoutKey(descriptor.widget_id, display.identity, variant)
                    entry = self._existing_entry(descriptor, display, variant)
                    if entry is None:
                        rect = self._authored_rect(descriptor, display)
                        section = self._section_for(descriptor)
                        if descriptor.custom_layout_resize_mode == "clock_font":
                            payload = {"font_size": int(section["font_size"])}
                        elif descriptor.custom_layout_resize_mode == "visualizer_rect":
                            payload = {"width": rect.width(), "height": rect.height()}
                        else:
                            payload = {}
                        content_sized = False
                        self._authored_keys.add(key)
                    else:
                        local = clamp_local_rect_to_bounds(denormalize_local_rect(entry.rect, display.geometry.size()), display.geometry.size())
                        rect = QRect(display.geometry.x() + local.x(), display.geometry.y() + local.y(), local.width(), local.height())
                        payload = dict(entry.size_payload)
                        content_sized = bool(payload.get("_size_from_content", False))
                    scale = float(payload.get("_custom_resize_scale", 1.0) or 1.0)
                    if not math.isfinite(scale) or scale <= 0.0:
                        scale = 1.0
                    viewport_extent = None
                    if descriptor.custom_layout_resize_mode == "visualizer_rect":
                        viewport_extent = normalize_viewport_extent(
                            payload.get("viewport_extent")
                        )
                    content_extent = None
                    if descriptor.content_extent_axes:
                        content_extent = normalize_viewport_extent(
                            payload.get("content_extent")
                        )
                    child_sizes = normalize_child_geometry(
                        payload.get(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY),
                        descriptor.custom_child_roles,
                    )
                    section = self._route_section_for(descriptor)
                    source_route = str(section.get("monitor", display.monitor_route)) if isinstance(section, Mapping) else display.monitor_route
                    item = CustomLayoutSessionItem(
                        source_key=key, model_identity=descriptor.widget_id,
                        baseline_global_rect=rect, current_global_rect=rect,
                        baseline_size_payload=payload, current_size_payload=payload,
                        baseline_enabled=True, current_enabled=True,
                        baseline_resize_scale=scale, resize_scale=scale,
                        source_monitor_route=source_route, current_monitor_route=source_route,
                        resize_capable=descriptor.supports_layout_resize_edit,
                        viewport_resize_capable=(
                            descriptor.custom_layout_resize_mode == "visualizer_rect"
                        ),
                        baseline_viewport_extent=viewport_extent,
                        current_viewport_extent=viewport_extent,
                        content_extent_axes=frozenset(descriptor.content_extent_axes),
                        content_extent_minimum_size=descriptor.content_extent_minimum_size,
                        baseline_content_extent=content_extent,
                        current_content_extent=content_extent,
                        custom_child_roles=descriptor.custom_child_roles,
                        baseline_child_sizes=child_sizes,
                        current_child_sizes=child_sizes,
                        content_sized=content_sized, baseline_content_sized=content_sized,
                        placement_anchor=str(payload.get("_placement_anchor", "") or "") or None,
                        baseline_placement_anchor=str(payload.get("_placement_anchor", "") or "") or None,
                    )
                    self.session.add_item(item)
                    self._descriptors_by_key[key] = descriptor
        self.session.refresh_duplicate_state()

    def item(self, key: CustomLayoutKey) -> CustomLayoutSessionItem:
        return self.session.item(key)

    def display_route(self, key: CustomLayoutKey) -> str:
        """Return the display label for a public editor selection key."""

        return self._display_map[self.item(key).current_display_identity].monitor_route

    def item_label(self, key: CustomLayoutKey) -> str:
        """Return the Settings-facing name for a canonical widget identity."""

        names = {
            "clock": "Clock", "clock2": "Clock 2", "clock3": "Clock 3",
            "spotify_visualizer": "Spotify Visualizer", "system_audio_osd": "System Audio OSD",
            "system_stats": "System Stats", "reddit": "Reddit 1", "reddit2": "Reddit 2",
            "feeds_custom_1": "Custom Feed 1", "feeds_custom_2": "Custom Feed 2",
            "feeds_custom_3": "Custom Feed 3", "feeds_custom_4": "Custom Feed 4",
        }
        identity = self.item(key).model_identity
        return names.get(identity, identity.replace("_", " ").title())

    def slot_is_occupied(self, slot_id: object) -> bool:
        """Expose committed slot state without leaking the draft persistence map."""

        return get_layout_slot_payload(self._committed, slot_id) is not None

    def committed_widgets(self) -> dict[str, Any]:
        """Return a defensive snapshot for the Settings persistence owner."""

        return deepcopy(self._committed)

    def free_placement(self, key: CustomLayoutKey) -> bool:
        return key not in self._authored_keys and not self.item(key).removed

    def set_free_placement(self, key: CustomLayoutKey, enabled: bool) -> None:
        if not enabled:
            self.reset(key)
            return
        item = self.item(key)
        if key in self._authored_keys:
            self._promote_routed_duplicates(item)
            self._dirty = True
            self.session.notify_item_changed(item)

    def move(self, key: CustomLayoutKey, global_rect: QRect, *, cursor_global: QPoint | None = None) -> None:
        """Move through the same intentional cross-display policy as Runtime Edit."""

        item = self.item(key)
        source = self._display_map[item.current_display_identity]
        source_screen = self._screen_map[source.identity]
        candidate = choose_best_screen_for_global_rect(
            global_rect,
            cursor_global=cursor_global,
            screens=list(self._screen_map.values()),
        )
        display = source
        if candidate is not None and candidate is not source_screen and should_transfer_rect_to_screen(
            global_rect,
            current_screen=source_screen,
            candidate_screen=candidate,
            cursor_global=cursor_global,
        ):
            display = self._display_map[candidate.identity]
        peers = [QRect(peer.current_global_rect.x() - display.geometry.x(), peer.current_global_rect.y() - display.geometry.y(), peer.current_global_rect.width(), peer.current_global_rect.height()) for peer in self.session.active_items() if peer is not item and peer.current_display_identity == display.identity]
        local = snap_local_rect_for_edit(QRect(global_rect.x() - display.geometry.x(), global_rect.y() - display.geometry.y(), global_rect.width(), global_rect.height()), display.geometry.size(), peer_rects=peers)
        if key in self._authored_keys:
            self._promote_routed_duplicates(item)
        resolved = QRect(display.geometry.x() + local.x(), display.geometry.y() + local.y(), local.width(), local.height())
        if display.identity != source.identity:
            item.set_current_display(display.identity, monitor_route=display.monitor_route)
        item.set_geometry(resolved)
        if item.content_sized:
            item.placement_anchor = choose_content_placement_anchor(local, display.geometry.size())
        self._dirty = True
        self.session.refresh_duplicate_state(); self.session.notify_item_changed(item)

    def transfer(self, key: CustomLayoutKey, target_identity: str, global_rect: QRect) -> None:
        item = self.item(key)
        target = self._display_map[target_identity]
        local = clamp_local_rect_to_bounds(QRect(global_rect.x() - target.geometry.x(), global_rect.y() - target.geometry.y(), global_rect.width(), global_rect.height()), target.geometry.size())
        if key in self._authored_keys:
            self._promote_routed_duplicates(item)
        item.set_current_display(target_identity, monitor_route=target.monitor_route)
        item.set_geometry(QRect(target.geometry.x() + local.x(), target.geometry.y() + local.y(), local.width(), local.height()))
        if item.content_sized:
            item.placement_anchor = choose_content_placement_anchor(local, target.geometry.size())
        self._dirty = True
        self.session.refresh_duplicate_state(); self.session.notify_item_changed(item)

    def scale(self, key: CustomLayoutKey, factor: float) -> None:
        item = self.item(key); descriptor = self._descriptors_by_key[key]
        if not item.resize_capable:
            return
        if key in self._authored_keys:
            self._promote_routed_duplicates(item)
        display = self._display_map[item.current_display_identity]
        requested_scale = item.resize_scale * float(factor)
        minimum = quick_custom_minimum_size(item)
        if (
            item.content_extent_capable
            and not item.viewport_resize_capable
            and item.current_content_extent is not None
        ):
            reference_width = max(1.0, float(item.current_content_extent[0]))
            reference_height = max(1.0, float(item.current_content_extent[1]))
            floor_scale = max(
                CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
                float(minimum.width()) / reference_width,
                float(minimum.height()) / reference_height,
            )
        else:
            admitted_scale = max(1.0e-6, float(item.baseline_resize_scale))
            reference_width = max(
                1.0, float(item.baseline_global_rect.width()) / admitted_scale
            )
            reference_height = max(
                1.0, float(item.baseline_global_rect.height()) / admitted_scale
            )
            floor_scale = max(
                CUSTOM_LAYOUT_MIN_RESIZE_SCALE,
                float(minimum.width()) / reference_width,
                float(minimum.height()) / reference_height,
                admitted_scale
                * quick_custom_payload_minimum_scale(
                    descriptor, item.baseline_size_payload
                ),
            )
        max_scale = min(
            float(display.geometry.width()) / reference_width,
            float(display.geometry.height()) / reference_height,
        )
        scale = min(max_scale, max(floor_scale, requested_scale))
        if abs(scale - item.resize_scale) < 1.0e-6:
            return
        rect = item.current_global_rect
        width = max(1, int(round(reference_width * scale)))
        height = max(1, int(round(reference_height * scale)))
        local = QRect(rect.x() - display.geometry.x(), rect.y() - display.geometry.y(), rect.width(), rect.height())
        horizontal, vertical = parse_content_placement_anchor(item.placement_anchor) or parse_content_placement_anchor(choose_content_placement_anchor(local, display.geometry.size()))
        def anchored_start(start: int, span: int, scaled: int, anchor: str, low: str, middle: str) -> int:
            if anchor == low:
                return start
            if anchor == middle:
                return round(start + span / 2 - scaled / 2)
            return start + span - scaled
        resized_local = clamp_local_rect_to_bounds(QRect(
            anchored_start(local.x(), local.width(), width, horizontal, "left", "center"),
            anchored_start(local.y(), local.height(), height, vertical, "top", "center"),
            width,
            height,
        ), display.geometry.size(), min_size=minimum)
        resized = QRect(
            display.geometry.x() + resized_local.x(),
            display.geometry.y() + resized_local.y(),
            resized_local.width(),
            resized_local.height(),
        )
        payload = dict(item.current_size_payload)
        if item.content_extent_capable and item.current_content_extent is not None:
            payload.update(
                width=resized_local.width(),
                height=resized_local.height(),
                content_extent=list(item.current_content_extent),
            )
        else:
            payload_scale = scale / max(
                1.0e-6, float(item.baseline_resize_scale)
            )
            if descriptor.custom_layout_resize_mode == "clock_font":
                projected = scale_quick_size_payload(
                    descriptor,
                    {"font_size": item.baseline_size_payload["font_size"]},
                    payload_scale,
                )
                payload["font_size"] = projected["font_size"]
            elif descriptor.custom_layout_resize_mode == "visualizer_rect":
                projected = scale_quick_size_payload(
                    descriptor,
                    {
                        "width": item.baseline_size_payload.get(
                            "width", item.baseline_global_rect.width()
                        ),
                        "height": item.baseline_size_payload.get(
                            "height", item.baseline_global_rect.height()
                        ),
                    },
                    payload_scale,
                )
                payload.update(width=projected["width"], height=projected["height"])
        preserve_content_size = item.content_sized
        item.set_geometry(resized, size_payload=payload, resize_scale=scale)
        # Runtime Edit's set_geometry deliberately clears this on a real resize.
        # Settings uniform scaling is D3's distinct content-size operation.
        item.content_sized = preserve_content_size
        if item.content_sized and item.placement_anchor is None:
            display = self._display_map[item.current_display_identity]
            local = QRect(resized.x() - display.geometry.x(), resized.y() - display.geometry.y(), resized.width(), resized.height())
            item.placement_anchor = choose_content_placement_anchor(local, display.geometry.size())
        self._dirty = True
        self._authored_keys.discard(key); self.session.notify_item_changed(item)

    def reset(self, key: CustomLayoutKey) -> None:
        item = self.item(key)
        self._reset_keys.add(key)
        item.removed = True
        self._dirty = True
        self.session.refresh_duplicate_state(); self.session.notify_item_changed(item)

    def _promote_routed_duplicates(self, item: CustomLayoutSessionItem) -> None:
        """An ALL route needs a committed content-sized peer on every display."""
        candidates = (item,) if item.source_monitor_route.upper() != "ALL" else (
            peer for peer in self.session.items()
            if peer.model_identity == item.model_identity and peer.source_monitor_route.upper() == "ALL"
        )
        for peer in candidates:
            if peer.source_key not in self._authored_keys:
                continue
            display = self._display_map[peer.current_display_identity]
            local = QRect(peer.current_global_rect.x() - display.geometry.x(), peer.current_global_rect.y() - display.geometry.y(), peer.current_global_rect.width(), peer.current_global_rect.height())
            peer.content_sized = True
            peer.baseline_content_sized = True
            peer.placement_anchor = choose_content_placement_anchor(local, display.geometry.size())
            self._authored_keys.remove(peer.source_key)

    def discard(self) -> None:
        self.widgets = deepcopy(self._committed)
        self._reset_keys.clear(); self._dirty = False; self._build_session()

    def load_slot(self, slot_id: object) -> bool:
        if get_layout_slot_payload(self.widgets, slot_id) is None:
            return False
        if not apply_layout_slot(self.widgets, slot_id):
            return False
        self._reset_keys.clear(); self._dirty = True; self._build_session(); return True

    def save_slot(self, slot_id: object) -> bool:
        if self.pending:
            return False
        saved = save_layout_slot(self._committed, slot_id)
        if saved:
            self.widgets = deepcopy(self._committed)
        return saved

    def apply(self) -> dict[str, Any]:
        if not self._dirty:
            return deepcopy(self._committed)
        projected = self._session_projection()
        self.widgets = projected
        self._apply_resets(self.widgets)
        self._committed = deepcopy(self.widgets)
        self._reset_keys.clear(); self._dirty = False; self._build_session()
        return deepcopy(self.widgets)

    def _session_projection(self) -> dict[str, Any]:
        candidate = deepcopy(self.widgets)
        displays = {identity: display.commit_value() for identity, display in self._display_map.items()}
        # Viewing an authored item must not promote it.  Commit only existing
        # CUSTOM entries and authored entries the operator actually touched.
        changed_session = CustomLayoutSession()
        changed_descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        for item in self.session.items():
            if item.source_key in self._authored_keys or item.source_key in self._reset_keys:
                continue
            changed_session.add_item(item)
            changed_descriptors[item.source_key] = self._descriptors_by_key[item.source_key]
        if changed_descriptors:
            commit_custom_session(candidate, changed_session, changed_descriptors, displays)
        return candidate

    def _apply_resets(self, widgets: dict[str, Any]) -> None:
        """Remove only the selected parent/display entry; never erase other screens' children."""
        custom = load_custom_layout_map(widgets)
        restore = load_custom_layout_restore_map(widgets)
        for key in self._reset_keys:
            display = self._display_map[key.display_identity]
            for alias in display.signature_aliases:
                remove_screen_layout_entry(custom, alias, key.widget_id, key.geometry_variant)
            remaining = custom.get("displays", {})
            has_remaining = any(isinstance(bucket, Mapping) and key.widget_id in bucket for bucket in remaining.values()) if isinstance(remaining, Mapping) else False
            if not has_remaining:
                route = get_custom_layout_restore_entry(restore, key.widget_id)
                if route is not None:
                    pos = widgets.setdefault(get_custom_persistence_position_settings_key_for_widget(key.widget_id), {})
                    mon = widgets.setdefault(get_custom_persistence_monitor_settings_key_for_widget(key.widget_id), {})
                    if isinstance(pos, dict): pos["position"] = route["position"]
                    if isinstance(mon, dict): mon["monitor"] = route["monitor"]
        write_custom_layout_map(widgets, custom)
