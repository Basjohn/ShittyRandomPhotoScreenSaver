"""Presentation-neutral working state for CUSTOM layout editing."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import QRect


DEFAULT_GEOMETRY_VARIANT = "default"

ViewportExtent = tuple[float, float]


def normalize_viewport_extent(value: object) -> ViewportExtent | None:
    """Return a canonical positive ``(world_width, world_height)`` pair or None.

    The extent is the visualizer's logical/render world before uniform visual
    scale.  ``None`` means "no independent extent committed"; callers fall back
    to the canonical baseline aspect.  This is deliberately generic session
    state: only viewport-resize-capable items ever populate it.
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
    # These carry the visualizer's logical world width/height so uniform scale
    # and viewport extent resolve independently; ``None`` means the canonical
    # baseline aspect. Only viewport-resize-capable items populate them.
    viewport_resize_capable: bool = False
    baseline_viewport_extent: ViewportExtent | None = None
    current_viewport_extent: ViewportExtent | None = None

    def __post_init__(self) -> None:
        self.model_identity = str(self.model_identity or self.source_key.widget_id)
        self.baseline_global_rect = QRect(self.baseline_global_rect)
        self.current_global_rect = QRect(self.current_global_rect)
        self.baseline_size_payload = dict(self.baseline_size_payload)
        self.current_size_payload = dict(self.current_size_payload)
        self.baseline_enabled = bool(self.baseline_enabled)
        self.current_enabled = bool(self.current_enabled)
        self.is_duplicate = bool(self.is_duplicate)
        self.resize_capable = bool(self.resize_capable)
        self.baseline_resize_scale = float(self.baseline_resize_scale)
        if not self.baseline_resize_scale > 0.0:
            self.baseline_resize_scale = 1.0
        self.resize_scale = float(self.resize_scale)
        if not self.resize_scale > 0.0:
            self.resize_scale = self.baseline_resize_scale
        self.removed = bool(self.removed)
        self.viewport_resize_capable = bool(self.viewport_resize_capable)
        self.baseline_viewport_extent = normalize_viewport_extent(
            self.baseline_viewport_extent
        )
        self.current_viewport_extent = normalize_viewport_extent(
            self.current_viewport_extent
            if self.current_viewport_extent is not None
            else self.baseline_viewport_extent
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

    def set_geometry(
        self,
        global_rect: QRect,
        *,
        size_payload: Mapping[str, Any] | None = None,
        resize_scale: float | None = None,
        viewport_extent: ViewportExtent | None = None,
    ) -> None:
        self.current_global_rect = QRect(global_rect)
        if size_payload is not None:
            self.current_size_payload = dict(size_payload)
        if resize_scale is not None:
            self.resize_scale = float(resize_scale)
        if viewport_extent is not None:
            self.current_viewport_extent = normalize_viewport_extent(viewport_extent)

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
        self.removed = False


class CustomLayoutSession:
    """Own the working state for one global CUSTOM edit session."""

    def __init__(self) -> None:
        self._items: dict[CustomLayoutKey, CustomLayoutSessionItem] = {}
        self._change_listeners: list[
            Callable[[CustomLayoutSessionItem], None]
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
        for item in self._items.values():
            item.restore_baseline()
        self.refresh_duplicate_state()
        self.notify_all_items_changed()
