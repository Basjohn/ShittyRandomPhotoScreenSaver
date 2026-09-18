"""Presentation-neutral working state for CUSTOM layout editing."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Mapping

from PySide6.QtCore import QRect

from rendering.custom_child_geometry import (
    CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY,
    CustomChildRoleDescriptor,
    CustomChildSize,
    child_role_map,
)


DEFAULT_GEOMETRY_VARIANT = "default"

ViewportExtent = tuple[float, float]


def normalize_viewport_extent(value: object) -> ViewportExtent | None:
    """Return a canonical positive ``(world_width, world_height)`` pair or None.

    The extent is the Visualizer's persisted physical CUSTOM world before
    uniform visual scale and before any discrete content quarter-turn. ``None``
    means "no independent extent committed"; callers fall back to the canonical
    baseline aspect. Only viewport-resize-capable items populate it.
    """

    if value is None:
        return None
    width, height = value  # type: ignore[misc]
    width = float(width)
    height = float(height)
    if not (width > 0.0 and height > 0.0):
        raise ValueError("viewport extent must be positive")
    return (width, height)


def normalize_geometry_variant(value: object) -> str:
    """Return the canonical storage/session name for one geometry variant."""

    normalized = str(value or "").strip().lower()
    if normalized == "analogue":
        return "analog"
    return normalized or DEFAULT_GEOMETRY_VARIANT


@dataclass(frozen=True, slots=True)
class CustomLayoutKey:
    """Exact identity of one independently committed geometry variant."""

    widget_id: str
    display_identity: str
    geometry_variant: str = DEFAULT_GEOMETRY_VARIANT

    def __post_init__(self) -> None:
        widget_id = str(self.widget_id or "").strip()
        display_identity = str(self.display_identity or "").strip()
        if not widget_id:
            raise ValueError("widget_id must not be empty")
        if not display_identity:
            raise ValueError("display_identity must not be empty")
        object.__setattr__(self, "widget_id", widget_id)
        object.__setattr__(self, "display_identity", display_identity)
        object.__setattr__(
            self,
            "geometry_variant",
            normalize_geometry_variant(self.geometry_variant),
        )


@dataclass(slots=True)
class CustomLayoutSessionItem:
    """Mutable edit state for one real runtime/model item.

    QRect and payload values are copied on admission and mutation so UI objects
    cannot become accidental owners of session state through shared references.
    """

    source_key: CustomLayoutKey
    model_identity: str
    baseline_global_rect: QRect
    current_global_rect: QRect
    baseline_size_payload: dict[str, Any]
    current_size_payload: dict[str, Any]
    baseline_enabled: bool
    current_enabled: bool
    is_duplicate: bool = False
    resize_capable: bool = False
    # Absolute CUSTOM resize scale at admission.  Unlike the mutable working
    # scale below, this survives Save -> recreation -> re-entry via persisted
    # layout metadata, so the shared minimum cannot compound on an already
    # shrunken rectangle.
    baseline_resize_scale: float = 1.0
    resize_scale: float = 1.0
    removed: bool = False
    current_display_identity: str = ""
    source_monitor_route: str = "ALL"
    current_monitor_route: str = ""
    # Viewport-extent resize working state. ``resize_scale`` above stays the
    # uniform wheel operation and is never repurposed as extent; Visualizer side
    # handles change one world axis and Visualizer corners change both axes.
    # These carry the Visualizer's physical edited world width/height so uniform
    # scale and viewport extent resolve independently; content orientation may
    # derive a swapped effective logical world downstream. ``None`` means the
    # canonical baseline aspect. Only viewport-resize-capable items populate them.
    viewport_resize_capable: bool = False
    baseline_viewport_extent: ViewportExtent | None = None
    current_viewport_extent: ViewportExtent | None = None
    # Optional discrete content orientation affordance. The actual persisted
    # token remains inside size_payload so layout slots and persistence keep one
    # existing carrier rather than adding a parallel schema.
    content_rotation_capable: bool = False
    # Ordinary content-extent resize working state (distinct from the visualizer
    # viewport above). ``content_extent_axes`` names which side axes reflow the
    # widget's logical content box ("horizontal" and/or "vertical"). The existing
    # square corners/wheel remain uniform enlarge/shrink; a distinct diagonal edit
    # affordance may reflow both admitted content axes together. The box is a
    # pre-uniform-scale content size the
    # widget consumes to reflow (more rows / column reflow / less truncation)
    # instead of letterboxing. ``None`` means the canonical config-derived size.
    content_extent_axes: frozenset[str] = frozenset()
    content_extent_minimum_size: ViewportExtent | None = None
    baseline_content_extent: ViewportExtent | None = None
    current_content_extent: ViewportExtent | None = None
    # Descriptor-admitted major visual children may carry authored-relative
    # normalized size factors inside the parent's existing CUSTOM payload.
    # Keeping a normalized working map here avoids reparsing/allocating the
    # persisted payload on every pointer move.
    custom_child_roles: tuple[CustomChildRoleDescriptor, ...] = ()
    # Widget-scoped Edit preference.  False disables only editable-child peer
    # collision admission; snapping/guides, real-parent clipping/containment and
    # declared fixed obstacles remain active.  This is Settings-owned state,
    # not CUSTOM geometry/persistence, and therefore never enters size_payload.
    child_collision_enabled: bool = False
    baseline_child_sizes: dict[str, CustomChildSize] = field(default_factory=dict)
    current_child_sizes: dict[str, CustomChildSize] = field(default_factory=dict)
    # Transient retained-family minimum implied by the currently resolved child
    # geometry.  This is deliberately NOT persisted: the family presentation
    # re-reports it when selected for child editing.  The owner uses it only as
    # a floor for parent content-extent side/corner gestures so those controls
    # cannot cut back through an already-customized child.
    child_content_requirement: ViewportExtent | None = None
    # Per-widget Restore Size authority.  This is deliberately distinct from
    # the admission baseline above: baseline may already be a committed CUSTOM
    # shape/scale, while authored_reference_size is the current non-CUSTOM
    # family width/height captured from the retained presenter's authored
    # geometry.  Position/display are intentionally absent from this contract.
    size_reset_capable: bool = False
    authored_reference_size: ViewportExtent | None = None
    authored_size_payload: dict[str, Any] = field(default_factory=dict)
    authored_viewport_extent: ViewportExtent | None = None

    def __post_init__(self) -> None:
        self.model_identity = str(self.model_identity or self.source_key.widget_id)
        self.baseline_global_rect = QRect(self.baseline_global_rect)
        self.current_global_rect = QRect(self.current_global_rect)
        self.baseline_size_payload = dict(self.baseline_size_payload)
        self.current_size_payload = dict(self.current_size_payload)
        self.baseline_enabled = bool(self.baseline_enabled)
        self.current_enabled = bool(self.current_enabled)
        self.is_duplicate = bool(self.is_duplicate)
        self.child_collision_enabled = bool(self.child_collision_enabled)
        self.resize_capable = bool(self.resize_capable)
        self.baseline_resize_scale = float(self.baseline_resize_scale)
        if not self.baseline_resize_scale > 0.0:
            self.baseline_resize_scale = 1.0
        self.resize_scale = float(self.resize_scale)
        if not self.resize_scale > 0.0:
            self.resize_scale = self.baseline_resize_scale
        self.removed = bool(self.removed)
        self.viewport_resize_capable = bool(self.viewport_resize_capable)
        self.content_rotation_capable = bool(self.content_rotation_capable)
        self.baseline_viewport_extent = normalize_viewport_extent(
            self.baseline_viewport_extent
        )
        self.current_viewport_extent = normalize_viewport_extent(
            self.current_viewport_extent
            if self.current_viewport_extent is not None
            else self.baseline_viewport_extent
        )
        self.content_extent_axes = frozenset(
            str(axis)
            for axis in self.content_extent_axes
            if str(axis) in {"horizontal", "vertical"}
        )
        self.content_extent_minimum_size = normalize_viewport_extent(
            self.content_extent_minimum_size
        )
        self.baseline_content_extent = normalize_viewport_extent(
            self.baseline_content_extent
        )
        self.current_content_extent = normalize_viewport_extent(
            self.current_content_extent
            if self.current_content_extent is not None
            else self.baseline_content_extent
        )
        role_map = child_role_map(self.custom_child_roles)
        self.custom_child_roles = tuple(role_map.values())
        self.baseline_child_sizes = {
            str(role_id): size
            for role_id, size in self.baseline_child_sizes.items()
            if str(role_id) in role_map and isinstance(size, CustomChildSize)
        }
        self.current_child_sizes = {
            str(role_id): size
            for role_id, size in (
                self.current_child_sizes or self.baseline_child_sizes
            ).items()
            if str(role_id) in role_map and isinstance(size, CustomChildSize)
        }
        self.child_content_requirement = normalize_viewport_extent(
            self.child_content_requirement
        )
        self.size_reset_capable = bool(self.size_reset_capable)
        self.authored_reference_size = normalize_viewport_extent(
            self.authored_reference_size
        )
        self.authored_size_payload = dict(self.authored_size_payload)
        self.authored_viewport_extent = normalize_viewport_extent(
            self.authored_viewport_extent
        )
        self.current_display_identity = (
            str(self.current_display_identity or "").strip()
            or self.source_key.display_identity
        )
        self.source_monitor_route = str(self.source_monitor_route or "ALL")
        self.current_monitor_route = (
            str(self.current_monitor_route or "").strip()
            or self.source_monitor_route
        )

    @property
    def current_key(self) -> CustomLayoutKey:
        return CustomLayoutKey(
            widget_id=self.source_key.widget_id,
            display_identity=self.current_display_identity,
            geometry_variant=self.source_key.geometry_variant,
        )

    @property
    def content_extent_capable(self) -> bool:
        return bool(self.content_extent_axes)

    @property
    def child_geometry_capable(self) -> bool:
        return bool(self.custom_child_roles)

    def child_role(self, role_id: str) -> CustomChildRoleDescriptor | None:
        normalized = str(role_id or "").strip()
        return next(
            (role for role in self.custom_child_roles if role.role_id == normalized),
            None,
        )

    def child_size(self, role_id: str) -> CustomChildSize:
        return self.current_child_sizes.get(str(role_id), CustomChildSize())

    def set_child_size(self, role_id: str, size: CustomChildSize) -> bool:
        role = self.child_role(role_id)
        if role is None:
            return False
        normalized_id = role.role_id
        prior = self.current_child_sizes.get(normalized_id, CustomChildSize())
        if prior == size:
            return False
        if size.is_authored:
            self.current_child_sizes.pop(normalized_id, None)
        else:
            self.current_child_sizes[normalized_id] = size
        return True

    def restore_authored_child_geometry(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Clear every descriptor-owned CUSTOM child override atomically.

        Restore Size is an authored-state transaction, not an incremental role
        mutation. Keep the session's fast working cache and the one persisted
        ``child_geometry`` carrier in lockstep here so the Python owner cannot
        accidentally clear one authority while leaving stale child placement in
        the other. Unknown/retired child records are intentionally removed too:
        an explicit authored reset must not allow them to spring back after a
        later role/settings change.
        """

        result = dict(payload)
        result.pop(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY, None)
        self.current_child_sizes = {}
        self.child_content_requirement = None
        return result

    def set_geometry(
        self,
        global_rect: QRect,
        *,
        size_payload: Mapping[str, Any] | None = None,
        resize_scale: float | None = None,
        viewport_extent: ViewportExtent | None = None,
        content_extent: ViewportExtent | None = None,
    ) -> None:
        self.current_global_rect = QRect(global_rect)
        if size_payload is not None:
            self.current_size_payload = dict(size_payload)
        if resize_scale is not None:
            self.resize_scale = float(resize_scale)
        if viewport_extent is not None:
            self.current_viewport_extent = normalize_viewport_extent(viewport_extent)
        if content_extent is not None:
            self.current_content_extent = normalize_viewport_extent(content_extent)

    def set_viewport_extent(self, width: float, height: float) -> None:
        """Set the current logical world (edge operation) without touching scale."""

        self.current_viewport_extent = normalize_viewport_extent((width, height))

    def transfer_to_display(self, display_identity: str, global_rect: QRect) -> None:
        self.set_current_display(display_identity)
        self.current_global_rect = QRect(global_rect)

    def set_current_display(
        self,
        display_identity: str,
        *,
        monitor_route: str | None = None,
    ) -> None:
        target = str(display_identity or "").strip()
        if not target:
            raise ValueError("display_identity must not be empty")
        self.current_display_identity = target
        if monitor_route is not None:
            self.current_monitor_route = str(monitor_route or "ALL")

    def apply_remove_action(self) -> None:
        """Apply edit-mode X without mutating family capability state."""

        if self.is_duplicate:
            self.removed = True
            return
        self.current_enabled = False

    def restore_baseline(self) -> None:
        self.current_display_identity = self.source_key.display_identity
        self.current_monitor_route = self.source_monitor_route
        self.current_global_rect = QRect(self.baseline_global_rect)
        self.current_size_payload = dict(self.baseline_size_payload)
        self.current_enabled = self.baseline_enabled
        self.resize_scale = self.baseline_resize_scale
        self.current_viewport_extent = self.baseline_viewport_extent
        self.current_content_extent = self.baseline_content_extent
        self.current_child_sizes = dict(self.baseline_child_sizes)
        # The retained presentation re-derives this selected-parent floor. Never
        # carry a requirement from an abandoned edit gesture across Cancel/reset
        # semantics or a later re-entry.
        self.child_content_requirement = None
        self.removed = False

    def restore_authored_size(
        self,
        global_rect: QRect,
        *,
        size_payload: Mapping[str, Any],
        resize_scale: float,
        viewport_extent: ViewportExtent | None = None,
    ) -> None:
        """Restore only authored size/shape state while preserving ownership.

        The caller owns any display-fit exception.  This method intentionally
        does not touch display identity, monitor route, X/Y authority, enabled
        state, duplicate/removal state, or the admission baseline.
        """

        self.current_global_rect = QRect(global_rect)
        self.current_size_payload = dict(size_payload)
        self.resize_scale = max(1.0e-6, float(resize_scale))
        self.current_content_extent = None
        self.current_viewport_extent = normalize_viewport_extent(viewport_extent)


class CustomLayoutSession:
    """Own the working state for one global CUSTOM edit session."""

    def __init__(self) -> None:
        self._items: dict[CustomLayoutKey, CustomLayoutSessionItem] = {}
        self._change_listeners: list[
            Callable[[CustomLayoutSessionItem], None]
        ] = []
        self._selected_key: CustomLayoutKey | None = None
        self._selection_listeners: list[
            Callable[[CustomLayoutSessionItem | None], None]
        ] = []

    def add_item(self, item: CustomLayoutSessionItem) -> None:
        if item.source_key in self._items:
            raise ValueError(f"duplicate CUSTOM session key: {item.source_key!r}")
        self._items[item.source_key] = item

    def item(self, key: CustomLayoutKey) -> CustomLayoutSessionItem:
        return self._items[key]

    def items(self) -> tuple[CustomLayoutSessionItem, ...]:
        return tuple(self._items.values())

    def active_items(self) -> tuple[CustomLayoutSessionItem, ...]:
        return tuple(item for item in self._items.values() if not item.removed)

    def selected_item(self) -> CustomLayoutSessionItem | None:
        """Return the transient parent selected for child/edit-chrome focus."""

        if self._selected_key is None:
            return None
        return self._items.get(self._selected_key)

    def select_item(self, item: CustomLayoutSessionItem | None) -> bool:
        """Select one session-owned parent without creating persisted state.

        Selection is global to the CUSTOM edit transaction so multiple display
        overlays cannot each expose child/edit affordances independently. It is
        event-owned UI state only and is never written into layout persistence.
        """

        if item is not None and self._items.get(item.source_key) is not item:
            raise ValueError("selected item is not owned by this CUSTOM session")
        next_key = item.source_key if item is not None else None
        if next_key == self._selected_key:
            return False
        self._selected_key = next_key
        selected = self.selected_item()
        for listener in tuple(self._selection_listeners):
            listener(selected)
        return True

    def subscribe_selection(
        self,
        listener: Callable[[CustomLayoutSessionItem | None], None],
    ) -> None:
        if listener not in self._selection_listeners:
            self._selection_listeners.append(listener)

    def unsubscribe_selection(
        self,
        listener: Callable[[CustomLayoutSessionItem | None], None],
    ) -> None:
        self._selection_listeners = [
            entry for entry in self._selection_listeners if entry != listener
        ]

    def subscribe_changes(
        self,
        listener: Callable[[CustomLayoutSessionItem], None],
    ) -> None:
        if listener not in self._change_listeners:
            self._change_listeners.append(listener)

    def unsubscribe_changes(
        self,
        listener: Callable[[CustomLayoutSessionItem], None],
    ) -> None:
        self._change_listeners = [
            entry for entry in self._change_listeners if entry != listener
        ]

    def notify_item_changed(self, item: CustomLayoutSessionItem) -> None:
        if self._items.get(item.source_key) is not item:
            raise ValueError("changed item is not owned by this CUSTOM session")
        if self._selected_key == item.source_key and (
            item.removed or not item.current_enabled
        ):
            self.select_item(None)
        for listener in tuple(self._change_listeners):
            listener(item)

    def notify_all_items_changed(self) -> None:
        for item in self._items.values():
            self.notify_item_changed(item)

    def refresh_duplicate_state(self) -> None:
        """Derive duplicate status from current enabled, non-removed survivors."""

        grouped: dict[str, list[CustomLayoutSessionItem]] = {}
        for item in self._items.values():
            if item.current_enabled and not item.removed:
                grouped.setdefault(item.model_identity, []).append(item)
        for item in self._items.values():
            item.is_duplicate = (
                item.current_enabled
                and not item.removed
                and len(grouped.get(item.model_identity, ())) > 1
            )

    def restore_baseline(self) -> None:
        self.select_item(None)
        for item in self._items.values():
            item.restore_baseline()
        self.refresh_duplicate_state()
        self.notify_all_items_changed()
