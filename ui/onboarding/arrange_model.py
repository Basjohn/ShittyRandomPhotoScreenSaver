"""Draft-only CUSTOM layout model used by Guided Setup and Quick Start.

The model has no Settings widgets, providers, runtime or persistence owner. It
stages the existing ``CustomLayoutSession`` and delegates the one canonical
write to :mod:`rendering.custom_layout_commit`.

Geometry is the saver's own: preferred sizes are measured through each family's
QML (``OrdinaryPreferredSizeMeter``, detached items that never enter a window)
and uncommitted widgets are placed by ``project_authored_display_layout``, the
runtime's anchor/stacking/Media-docking functions. Apply after any placement
saves the whole canvas, as Runtime Edit's Save does, because CUSTOM is a
global layout mode.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import math
from types import SimpleNamespace
from typing import Any, Mapping

from PySide6.QtCore import QPoint, QRect

from core.logging.logger import get_logger
from core.settings.capability_activation import is_widget_family_effective
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    get_visualizer_presentation_policy,
)
from core.settings.layout_slots import apply_layout_slot, get_layout_slot_payload, save_layout_slot
from core.settings.widget_family_catalog import get_family_id_for_widget, get_widget_member_label
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
    resolve_resize_edge_snap,
    remove_screen_layout_entry,
    should_transfer_rect_to_screen,
    resolve_snap_local_rect_for_edit,
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
    CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY,
    capture_quick_size_payload,
    content_extent_resize_payload,
    edge_resize_rect,
    quick_custom_content_extent_minimum_size,
    quick_custom_minimum_size,
    quick_custom_payload_minimum_scale,
    scale_quick_size_payload,
    settings_side_edges,
    viewport_extent_resize_payload,
)
from rendering.widget_descriptors import (
    WidgetRuntimeDescriptor,
    get_widget_runtime_descriptors,
    get_effective_monitor_value_for_widget,
    get_effective_position_settings_key_for_widget,
    get_custom_persistence_monitor_settings_key_for_widget,
    get_custom_persistence_position_settings_key_for_widget,
)
from rendering.quick.custom_layout_hydration import clock_geometry_variant, resolve_committed_visualizer_rect
from rendering.quick.widgets.geometry_resolver import resolve_overlay_geometry_policy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from widgets.spotify_visualizer.render_state import CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
from rendering.quick.visualizer_admission import (
    requested_visualizer_screen_index,
    resolve_quick_visualizer_owner_unit,
)
from rendering.quick.widgets.authored_layout_projection import (
    ProjectedPlacement,
    project_authored_display_layout,
)
from rendering.quick.widgets.preferred_size_measurement import (
    OrdinaryPreferredSizeMeter,
    ordinary_instance_order,
)
from widgets.spotify_visualizer.presentation_geometry import resolve_visualizer_presentation

logger = get_logger(__name__)

_CLOCK_IDS = frozenset({"clock", "clock2", "clock3"})


def _visualizer_outer_size(display: "ArrangeDisplay") -> tuple[float, float]:
    """The saver's authored Visualizer outer box on ``display`` (its own resolver).

    Authored mode uses the canonical viewport at scale 1, reduced uniformly to
    fit the display; the mode policy and card style shape the inside only, so
    neutral values stand in for them here.
    """

    presentation = resolve_visualizer_presentation(
        policy=get_visualizer_presentation_policy(get_default_visualizer_mode_id()),
        display_size=(display.geometry.width(), display.geometry.height()),
        border_width=0.0, corner_radius=0.0, content_inset=0.0,
        background_color=(0, 0, 0, 0), border_color=(0, 0, 0, 0),
        shadow_enabled=False, shadow_color=(0, 0, 0, 0), shadow_blur=0.0,
        shadow_offset=(0.0, 0.0), shadow_spread=0.0, shadow_extensions=(0.0, 0.0, 0.0, 0.0),
    )
    return float(presentation.outer_rect[2]), float(presentation.outer_rect[3])
# The saver's provisional size until a family reports its own (display presenter).
_PROVISIONAL_SIZE = (100.0, 100.0)


@dataclass(frozen=True)
class ArrangeDisplay:
    identity: str
    signature_aliases: tuple[str, ...]
    # Qt logical geometry: the saver lays widgets out in these units too.
    geometry: QRect
    monitor_route: str
    # Only for text shown to people: the monitor's device resolution and scale.
    device_pixel_ratio: float = 1.0
    device_size: tuple[int, int] | None = None

    def resolution(self) -> tuple[int, int]:
        """The display's resolution in device pixels (Windows' own figure when known)."""

        if self.device_size is not None:
            return self.device_size
        return (round(self.geometry.width() * self.device_pixel_ratio),
                round(self.geometry.height() * self.device_pixel_ratio))

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

    def __init__(
        self,
        widgets: Mapping[str, Any],
        displays: tuple[ArrangeDisplay, ...],
        *,
        meter: OrdinaryPreferredSizeMeter | None = None,
    ) -> None:
        self._committed = deepcopy(dict(widgets))
        self.widgets = deepcopy(dict(widgets))
        self.displays = tuple(displays)
        self._display_map = {display.identity: display for display in self.displays}
        self._screen_map = {display.identity: _ArrangeScreen(display) for display in self.displays}
        self.descriptors = {descriptor.widget_id: descriptor for descriptor in get_widget_runtime_descriptors()}
        self.session = CustomLayoutSession()
        self._descriptors_by_key: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        self._authored_keys: set[CustomLayoutKey] = set()
        self._entry_keys: set[CustomLayoutKey] = set()
        self._reset_keys: set[CustomLayoutKey] = set()
        # Every item the operator returned to its anchor in this draft (with or
        # without a saved entry); Apply leaves exactly these uncommitted.
        self._anchored_keys: set[CustomLayoutKey] = set()
        # True once the operator placed anything; Apply then saves the canvas.
        self._arranged = False
        self._loaded_slot: str | None = None
        self._dirty = False
        self._meter = meter if meter is not None else OrdinaryPreferredSizeMeter()
        self._projections: dict[str, dict[str, ProjectedPlacement]] = {}
        self._admitted: frozenset[str] | None = None
        # (display identity, vertical guides, horizontal guides) of the last move.
        self.last_snap: tuple[str, tuple, tuple] | None = None
        self._build_session()

    def _refresh_projections(self) -> None:
        """Forget placements derived from the draft map (sizes stay memoized)."""

        self._projections.clear()
        self._admitted = None

    @property
    def pending(self) -> bool:
        return self._dirty

    def _effective(self, descriptor: WidgetRuntimeDescriptor) -> bool:
        if self._meter.presents(descriptor.widget_id):
            # An ordinary card presents only when its family admits it (a Feed
            # needs a source, Friend Pulse needs Steam), as the display binder does.
            if self._admitted is None:
                self._admitted = frozenset(ordinary_instance_order(self.widgets, self._meter.adapters))
            if descriptor.widget_id not in self._admitted:
                return False
        else:
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
        if descriptor.widget_id not in _CLOCK_IDS:
            return ("default",)
        # The saver's own face resolution (base-Clock inheritance, per-display override).
        return (clock_geometry_variant(self.widgets, descriptor.widget_id, display.identity),)

    def _routed_displays(self, descriptor: WidgetRuntimeDescriptor) -> tuple[ArrangeDisplay, ...]:
        if descriptor.widget_id == "spotify_visualizer":
            # The saver runs exactly one Visualizer: on its requested display when
            # shown, otherwise (and for ALL) the first shown display. Never one per display.
            requested = requested_visualizer_screen_index(
                get_effective_monitor_value_for_widget(descriptor.widget_id, self.widgets)
            )
            participants = [
                SimpleNamespace(screen_index=int(display.monitor_route) - 1, participating=True, display=display)
                for display in self.displays if str(display.monitor_route).isdigit()
            ]
            chosen = resolve_quick_visualizer_owner_unit(requested, participants)
            return (chosen.display,) if chosen is not None else ()
        section = self._route_section_for(descriptor)
        route = str(section.get("monitor", "ALL")) if isinstance(section, Mapping) else "ALL"
        if route.upper() == "ALL":
            return self.displays
        return tuple(display for display in self.displays if display.monitor_route == route)

    def _content_identity(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay) -> str | None:
        """The display signature a Clock's per-display face is resolved with (as the saver does)."""

        return display.identity if descriptor.widget_id in _CLOCK_IDS else None

    def _measured_size(
        self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay, *, size_payload: Mapping[str, Any] | None = None,
    ) -> tuple[float, float]:
        """The saver's own outer size for this widget on ``display`` (optionally as a committed payload presents it)."""

        if descriptor.widget_id == "spotify_visualizer":
            return _visualizer_outer_size(display)
        try:
            return self._meter.measure(
                descriptor.widget_id, self.widgets,
                display_identity=self._content_identity(descriptor, display),
                size_payload=size_payload,
            )
        except Exception:
            logger.exception(
                "[ARRANGE] Could not measure %s; showing the saver's provisional size",
                descriptor.widget_id,
            )
            return _PROVISIONAL_SIZE

    def _ordinary_on(self, widget_id: str, display: ArrangeDisplay) -> bool:
        """Effective, routed to ``display`` and not a CUSTOM entry there."""

        descriptor = self.descriptors.get(widget_id)
        if descriptor is None or not self._effective(descriptor) or display not in self._routed_displays(descriptor):
            return False
        return self._existing_entry(descriptor, display, self._variants_for(descriptor, display)[0]) is None

    def _display_projection(self, display: ArrangeDisplay) -> dict[str, ProjectedPlacement]:
        """Where the saver places every uncommitted widget on ``display``."""

        projection = self._projections.get(display.identity)
        if projection is None:
            ordinary = [
                (widget_id, self._measured_size(self.descriptors[widget_id], display))
                for widget_id in ordinary_instance_order(self.widgets, self._meter.adapters)
                if widget_id in self.descriptors and self._ordinary_on(widget_id, display)
            ]
            visualizer = None
            if self._ordinary_on("spotify_visualizer", display):
                visualizer = self._measured_size(self.descriptors["spotify_visualizer"], display)
            projection = project_authored_display_layout(
                self.widgets,
                display_size=(display.geometry.width(), display.geometry.height()),
                ordinary=ordinary,
                visualizer_size=visualizer,
            )
            self._projections[display.identity] = projection
        return projection

    def _authored_placement(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay) -> tuple[QRect, float]:
        """The saver's rectangle (global) and automatic whole-card scale."""

        placement = self._display_projection(display).get(descriptor.widget_id)
        if placement is None:
            # Not presented here by the map being projected (a reset can restore
            # another monitor route): show it on its plain anchor on this display.
            size = self._measured_size(descriptor, display)
            visualizer = descriptor.widget_id == "spotify_visualizer"
            placement = project_authored_display_layout(
                self.widgets,
                display_size=(display.geometry.width(), display.geometry.height()),
                ordinary=() if visualizer else ((descriptor.widget_id, size),),
                visualizer_size=size if visualizer else None,
            )[descriptor.widget_id]
        rect = QRect(
            display.geometry.x() + round(placement.x),
            display.geometry.y() + round(placement.y),
            max(1, round(placement.width)),
            max(1, round(placement.height)),
        )
        return rect, float(placement.scale)

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
        self._refresh_projections()
        self._anchored_keys.clear()
        self._arranged = False
        self.session = CustomLayoutSession()
        self._descriptors_by_key.clear()
        self._authored_keys.clear()
        self._entry_keys.clear()
        for descriptor in self.descriptors.values():
            if not descriptor.supports_custom_position_slot or not self._effective(descriptor):
                continue
            for display in self._routed_displays(descriptor):
                for variant in self._variants_for(descriptor, display):
                    key = CustomLayoutKey(descriptor.widget_id, display.identity, variant)
                    entry = self._existing_entry(descriptor, display, variant)
                    if entry is None:
                        rect, auto_scale = self._authored_placement(descriptor, display)
                        payload = self._authored_payload(descriptor, rect, auto_scale)
                        content_sized = False
                        self._authored_keys.add(key)
                    else:
                        self._entry_keys.add(key)
                        payload = dict(entry.size_payload)
                        content_sized = bool(payload.get("_size_from_content", False))
                        rect = self._committed_rect(descriptor, display, entry, content_sized)
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
                        content_extent_minimum_size=self._content_extent_floor(descriptor, display),
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

    def _committed_rect(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay, entry: Any, content_sized: bool) -> QRect:
        """Where the saver shows a committed entry: content-sized ones at their anchor, at today's size."""

        size = display.geometry.size()
        if descriptor.widget_id == "spotify_visualizer":
            local = resolve_committed_visualizer_rect(entry, size)
        elif content_sized:
            measured = self._measured_size(descriptor, display, size_payload=entry.size_payload)
            bounds = OverlayWidgetGeometry(0.0, 0.0, float(size.width()), float(size.height()))
            geometry = resolve_overlay_geometry_policy(
                descriptor.widget_id, self.widgets, committed_entry=entry,
            ).resolve(measured, bounds)
            local = QRect(round(geometry.x), round(geometry.y), round(geometry.width), round(geometry.height))
        else:
            local = clamp_local_rect_to_bounds(denormalize_local_rect(entry.rect, size), size)
        return QRect(display.geometry.x() + local.x(), display.geometry.y() + local.y(), local.width(), local.height())

    def _content_extent_floor(self, descriptor: WidgetRuntimeDescriptor, display: ArrangeDisplay) -> tuple[int, int] | None:
        """Runtime Edit's width/height floor: declared, or the family's own natural size when it floors there."""

        configured = descriptor.content_extent_minimum_size
        if not descriptor.content_extent_floor_at_authored_size:
            return configured
        width, height = self._measured_size(descriptor, display)
        configured_width, configured_height = configured or (1, 1)
        return (max(int(configured_width), round(width)), max(int(configured_height), round(height)))

    def _authored_payload(self, descriptor: WidgetRuntimeDescriptor, rect: QRect, auto_scale: float = 1.0) -> dict[str, Any]:
        """Runtime Edit's authored payload, from the family's own resolved config."""

        family = None
        if descriptor.custom_layout_resize_mode == "clock_font":
            family = SimpleNamespace(model=SimpleNamespace(config=self._meter.presentation_config(descriptor.widget_id, self.widgets)))
        payload = capture_quick_size_payload(descriptor, family, rect)
        if auto_scale != 1.0:
            # An overfull display shrinks whole cards; keep that scale as admitted.
            payload[CUSTOM_LAYOUT_RESIZE_SCALE_PAYLOAD_KEY] = auto_scale
        return payload

    def is_authored(self, key: CustomLayoutKey) -> bool:
        """True while the widget still follows its authored anchor (no CUSTOM entry)."""
        return key in self._authored_keys

    def _touch(self, key: CustomLayoutKey) -> None:
        """A new placement supersedes a pending reset of the same entry."""
        self._reset_keys.discard(key)
        self._arranged = True
        if key in self._anchored_keys:
            self._anchored_keys.discard(key)
            self._refresh_anchored_items()

    def item(self, key: CustomLayoutKey) -> CustomLayoutSessionItem:
        return self.session.item(key)

    def device_size(self, key: CustomLayoutKey) -> tuple[int, int]:
        """The box's size in its display's device pixels (the units of its resolution)."""

        item = self.item(key)
        ratio = self._display_map[item.current_display_identity].device_pixel_ratio
        return (round(item.current_global_rect.width() * ratio),
                round(item.current_global_rect.height() * ratio))

    def display_route(self, key: CustomLayoutKey) -> str:
        """Return the display label for a public editor selection key."""

        return self._display_map[self.item(key).current_display_identity].monitor_route

    def item_label(self, key: CustomLayoutKey) -> str:
        """Return the Settings-facing name for a canonical widget identity."""

        return get_widget_member_label(self.item(key).model_identity)

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
        self._touch(key)
        if key in self._authored_keys:
            self._promote_routed_duplicates(item)
            self._dirty = True
            self.session.notify_item_changed(item)

    def move(self, key: CustomLayoutKey, global_rect: QRect, *, cursor_global: QPoint | None = None, snap: bool = True) -> None:
        """Move through the same intentional cross-display policy as Runtime Edit.

        ``snap=False`` (keyboard nudges) only clamps, so a 1 px nudge is never
        pulled back onto the guide it is leaving.
        """

        item = self.item(key)
        self._touch(key)
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
        requested = QRect(global_rect.x() - display.geometry.x(), global_rect.y() - display.geometry.y(), global_rect.width(), global_rect.height())
        if snap:
            resolution = resolve_snap_local_rect_for_edit(requested, display.geometry.size(), peer_rects=peers)
            local = resolution.rect
            self.last_snap = (display.identity, resolution.vertical_guides, resolution.horizontal_guides)
        else:
            local = clamp_local_rect_to_bounds(requested, display.geometry.size(), min_size=quick_custom_minimum_size(item))
            self.last_snap = None
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
        self._touch(key)
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
        self._touch(key)
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

    def side_edges(self, key: CustomLayoutKey) -> tuple[str, ...]:
        """Side handles (width-only / height-only) for this item: every axis it has."""

        return settings_side_edges(self.item(key))

    def side_edges_note(self, key: CustomLayoutKey) -> str:
        """Why a widget has no width/height handles, or ""."""

        return "" if self.side_edges(key) else "scales uniformly"

    def resize_edge(self, key: CustomLayoutKey, edge: str, origin_rect: QRect, delta: QPoint) -> None:
        """Change one axis at constant scale, exactly as Runtime Edit's side handle does.

        Ordinary widgets change their logical content box; the Visualizer its
        viewport world. Children are never shown or edited here: their saved
        payload is carried unchanged, and any room they report counts in the
        shared minimum.
        """

        if edge not in self.side_edges(key):
            return
        item = self.item(key)
        self._touch(key)
        display = self._display_map[item.current_display_identity]
        minimum = (quick_custom_minimum_size(item) if item.viewport_resize_capable
                   else quick_custom_content_extent_minimum_size(item))
        horizontal = edge if edge in {"left", "right"} else None
        vertical = edge if edge in {"top", "bottom"} else None
        rect = edge_resize_rect(origin_rect, display.geometry, minimum, delta.x(), delta.y(),
                                horizontal_edge=horizontal, vertical_edge=vertical)
        local = QRect(rect.x() - display.geometry.x(), rect.y() - display.geometry.y(), rect.width(), rect.height())
        peers = [QRect(peer.current_global_rect.x() - display.geometry.x(), peer.current_global_rect.y() - display.geometry.y(),
                       peer.current_global_rect.width(), peer.current_global_rect.height())
                 for peer in self.session.active_items() if peer is not item and peer.current_display_identity == display.identity]
        resolution = resolve_resize_edge_snap(local, display.geometry.size(), horizontal_edge=horizontal,
                                              vertical_edge=vertical, peer_rects=peers, min_size=minimum)
        self.last_snap = (display.identity, resolution.vertical_guides, resolution.horizontal_guides)
        snapped = resolution.rect
        rect = QRect(display.geometry.x() + snapped.x(), display.geometry.y() + snapped.y(), snapped.width(), snapped.height())
        if item.viewport_resize_capable:
            # Pixels per world unit from the axis the gesture leaves untouched: it
            # stays exact for the whole drag (the live presentation's own scale).
            extent = item.current_viewport_extent or CANONICAL_VISUALIZER_BASELINE_VIEWPORT_SIZE
            current = item.current_global_rect
            pixels_per_world = (current.height() / float(extent[1]) if horizontal is not None
                                else current.width() / float(extent[0]))
            payload, world = viewport_extent_resize_payload(
                item, pixels_per_world, rect,
                change_width=horizontal is not None, change_height=vertical is not None,
            )
            if rect == item.current_global_rect and item.current_viewport_extent == world:
                return
            item.set_geometry(rect, size_payload=payload, viewport_extent=world)
        else:
            payload, box = content_extent_resize_payload(item, item.resize_scale, rect,
                                                         change_width=horizontal is not None, change_height=vertical is not None)
            if rect == item.current_global_rect and item.current_content_extent == box:
                return
            item.set_geometry(rect, size_payload=payload, content_extent=box)
        self._dirty = True
        self.session.notify_item_changed(item)

    def reset(self, key: CustomLayoutKey) -> None:
        """Return the widget to its authored anchor now; Apply removes its CUSTOM entry.

        The box stays on the canvas where the saver will put it (dashed)
        instead of vanishing until Apply. Moving it again makes a new placement
        that supersedes the pending reset.
        """

        item = self.item(key)
        home = self._display_map[key.display_identity]
        if key in self._entry_keys:
            self._reset_keys.add(key)
        self._anchored_keys.add(key)
        self._authored_keys.add(key)
        item.set_current_display(home.identity, monitor_route=item.source_monitor_route)
        item.placement_anchor = None
        item.removed = False
        self._dirty = True
        self._refresh_anchored_items()
        self.session.refresh_duplicate_state(); self.session.notify_item_changed(item)

    def _refresh_anchored_items(self) -> None:
        """Show every anchored item where the saver puts it after Apply.

        The rest of the canvas is committed by Apply, which makes CUSTOM global,
        so the saver keeps an anchored widget on its plain anchor. With nothing
        else committed it stays authored and stacked. Either way this is the
        saver's own projection of the exact map Apply would write.
        """

        anchored = [item for item in self.session.items() if item.source_key in self._anchored_keys]
        if not anchored:
            return
        saved = self.widgets
        projected = self._session_projection(saved)
        self._apply_resets(projected)
        try:
            self.widgets = projected
            self._refresh_projections()
            for item in anchored:
                descriptor = self._descriptors_by_key[item.source_key]
                rect, auto_scale = self._authored_placement(descriptor, self._display_map[item.source_key.display_identity])
                # The session's authored-size restore also drops any saved logical
                # box, so a later move cannot write an old content extent back.
                item.restore_authored_size(rect, size_payload=self._authored_payload(descriptor, rect, auto_scale), resize_scale=auto_scale)
                item.baseline_resize_scale = auto_scale
                self.session.notify_item_changed(item)
        finally:
            self.widgets = saved
            self._refresh_projections()

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

    def replace_displays(self, displays: tuple[ArrangeDisplay, ...]) -> bool:
        """Show a changed display set (selection or hardware), keeping any pending draft.

        Pending edits are carried as the draft map they would apply (the
        committed baseline is untouched, so Discard still restores it); pending
        resets stay pending for the displays that remain.
        """

        displays = tuple(displays)
        if displays == self.displays:
            return False
        if self._dirty:
            draft = self._session_projection(self.widgets)
            self._apply_resets(draft)
            self.widgets = draft
        self.displays = displays
        self._display_map = {display.identity: display for display in self.displays}
        self._screen_map = {display.identity: _ArrangeScreen(display) for display in self.displays}
        self._reset_keys = {key for key in self._reset_keys if key.display_identity in self._display_map}
        self._build_session()
        return True

    def discard(self) -> None:
        self.widgets = deepcopy(self._committed)
        self._reset_keys.clear(); self._loaded_slot = None; self._dirty = False; self._build_session()

    def load_slot(self, slot_id: object) -> bool:
        if get_layout_slot_payload(self.widgets, slot_id) is None:
            return False
        if not apply_layout_slot(self.widgets, slot_id):
            return False
        self._loaded_slot = str(slot_id)
        self._reset_keys.clear(); self._dirty = True; self._build_session(); return True

    def save_slot(self, slot_id: object) -> bool:
        if self.pending:
            return False
        saved = save_layout_slot(self._committed, slot_id)
        if saved:
            self.widgets = deepcopy(self._committed)
        return saved

    def apply(self, base: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Commit the draft and return the widgets map to persist.

        ``base`` is the current Settings map.  The draft is merged onto it
        rather than replacing it with this editor's snapshot, so a write made
        elsewhere while the draft was pending (a Widgets-page toggle, a slot
        saved from Quick Start) survives Apply.  Arrange never switches widgets
        on or off, so their ``enabled`` state stays as ``base`` has it -- unless
        a loaded slot is being applied, which is the slot's own authority.
        """
        if not self._dirty:
            return deepcopy(dict(base)) if base is not None else deepcopy(self._committed)
        source = deepcopy(dict(base)) if base is not None else deepcopy(self.widgets)
        if base is not None and self._loaded_slot is not None:
            apply_layout_slot(source, self._loaded_slot)
        projected = self._session_projection(source)
        self._apply_resets(projected)
        if base is not None and self._loaded_slot is None:
            for key, section in base.items():
                target = projected.get(key)
                if isinstance(section, Mapping) and "enabled" in section and isinstance(target, dict):
                    target["enabled"] = section["enabled"]
        self.widgets = projected
        self._committed = deepcopy(projected)
        self._reset_keys.clear(); self._loaded_slot = None; self._dirty = False; self._build_session()
        return deepcopy(projected)

    def _session_projection(self, source: Mapping[str, Any] | None = None) -> dict[str, Any]:
        candidate = deepcopy(dict(source)) if source is not None else deepcopy(self.widgets)
        displays = {identity: display.commit_value() for identity, display in self._display_map.items()}
        # CUSTOM is global: one saved placement stops the saver stacking and
        # docking every other widget. So once the operator places anything,
        # Apply saves each untouched box where the canvas shows it (Runtime
        # Edit's Save does the same), as a content-sized placement at its
        # nearest anchor. Viewing or a slot load alone promotes nothing, and a
        # box the operator returned to its anchor stays authored.
        changed_session = CustomLayoutSession()
        changed_descriptors: dict[CustomLayoutKey, WidgetRuntimeDescriptor] = {}
        for item in self.session.items():
            if item.source_key in self._anchored_keys or item.source_key in self._reset_keys:
                continue
            if item.source_key in self._authored_keys:
                if not self._arranged:
                    continue
                item = self._content_sized_copy(item)
            changed_session.add_item(item)
            changed_descriptors[item.source_key] = self._descriptors_by_key[item.source_key]
        if changed_descriptors:
            commit_custom_session(candidate, changed_session, changed_descriptors, displays)
        return candidate

    def _content_sized_copy(self, item: CustomLayoutSessionItem) -> CustomLayoutSessionItem:
        """An untouched authored box as a content-sized placement where it is shown."""

        display = self._display_map[item.current_display_identity]
        local = item.current_global_rect.translated(-display.geometry.x(), -display.geometry.y())
        return replace(
            item,
            content_sized=True,
            baseline_content_sized=True,
            placement_anchor=choose_content_placement_anchor(local, display.geometry.size()),
        )

    def _apply_resets(self, widgets: dict[str, Any], *, keys=None) -> None:
        """Remove only the selected parent/display entry; never erase other screens' children."""
        custom = load_custom_layout_map(widgets)
        restore = load_custom_layout_restore_map(widgets)
        for key in (self._reset_keys if keys is None else keys):
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
