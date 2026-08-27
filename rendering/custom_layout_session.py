"""Presentation-neutral working state for CUSTOM layout editing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import QRect


DEFAULT_GEOMETRY_VARIANT = "default"


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
    resize_scale: float = 1.0
    removed: bool = False
    current_display_identity: str = ""
    source_monitor_route: str = "ALL"
    current_monitor_route: str = ""

    def __post_init__(self) -> None:
        self.model_identity = str(self.model_identity or self.source_key.widget_id)
        self.baseline_global_rect = QRect(self.baseline_global_rect)
        self.current_global_rect = QRect(self.current_global_rect)
        self.baseline_size_payload = dict(self.baseline_size_payload)
        self.current_size_payload = dict(self.current_size_payload)
        self.baseline_enabled = bool(self.baseline_enabled)
        self.current_enabled = bool(self.current_enabled)
        self.is_duplicate = bool(self.is_duplicate)
        self.resize_scale = float(self.resize_scale)
        self.removed = bool(self.removed)
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
    ) -> None:
        self.current_global_rect = QRect(global_rect)
        if size_payload is not None:
            self.current_size_payload = dict(size_payload)
        if resize_scale is not None:
            self.resize_scale = float(resize_scale)

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
        self.resize_scale = 1.0
        self.removed = False


class CustomLayoutSession:
    """Own the working state for one global CUSTOM edit session."""

    def __init__(self) -> None:
        self._items: dict[CustomLayoutKey, CustomLayoutSessionItem] = {}

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
