"""Shared CUSTOM editable-child geometry contracts.

The outer CUSTOM layout owner remains authoritative.  Child geometry stores only
normalized size factors for a small descriptor-declared set of major visual
roles; QML supplies retained presentation targets for edit chrome, but never
owns persistence or a second geometry schema.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY = "child_geometry"
_CHILD_SCALE_EPSILON = 1.0e-4
_CHILD_RESIZE_HANDLES = frozenset(
    {"top_left", "top_right", "bottom_left", "bottom_right"}
)


@dataclass(frozen=True, slots=True)
class CustomChildRoleDescriptor:
    """One descriptor-admitted resizable child role.

    ``role_id`` is stable persisted identity. ``axes`` names the dimensions a
    child handle may change. ``uniform_scale`` constrains the **child rectangle**
    only for intrinsic-shape roles (for example a circle); artwork rectangles
    deliberately remain freeform while their image content preserves native
    source aspect via the family fill/crop policy. Bounds are normalized against
    the authored child baseline rather than physical pixels so saved CUSTOM state
    remains portable across display/DPI changes and outer whole-widget scaling.
    """

    role_id: str
    axes: tuple[str, ...] = ("horizontal", "vertical")
    minimum_scale: tuple[float, float] = (0.40, 0.40)
    maximum_scale: tuple[float, float] = (3.00, 3.00)
    uniform_scale: bool = False
    resize_handles: tuple[str, ...] = (
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    )

    def __post_init__(self) -> None:
        role_id = str(self.role_id or "").strip()
        if not role_id:
            raise ValueError("CUSTOM child role id must not be empty")
        axes = tuple(
            axis
            for axis in (str(value) for value in self.axes)
            if axis in {"horizontal", "vertical"}
        )
        if not axes:
            raise ValueError(f"CUSTOM child role {role_id!r} must admit an axis")
        min_w, min_h = (float(value) for value in self.minimum_scale)
        max_w, max_h = (float(value) for value in self.maximum_scale)
        if not all(math.isfinite(value) and value > 0.0 for value in (min_w, min_h, max_w, max_h)):
            raise ValueError(f"CUSTOM child role {role_id!r} scale bounds must be positive finite values")
        if min_w > max_w or min_h > max_h:
            raise ValueError(f"CUSTOM child role {role_id!r} minimum scale exceeds maximum")
        handles = tuple(
            handle
            for handle in (str(value) for value in self.resize_handles)
            if handle in _CHILD_RESIZE_HANDLES
        )
        if not handles:
            raise ValueError(f"CUSTOM child role {role_id!r} must admit a resize handle")
        object.__setattr__(self, "role_id", role_id)
        object.__setattr__(self, "axes", tuple(dict.fromkeys(axes)))
        object.__setattr__(self, "minimum_scale", (min_w, min_h))
        object.__setattr__(self, "maximum_scale", (max_w, max_h))
        object.__setattr__(self, "uniform_scale", bool(self.uniform_scale))
        object.__setattr__(self, "resize_handles", tuple(dict.fromkeys(handles)))

    @property
    def horizontal(self) -> bool:
        return "horizontal" in self.axes

    @property
    def vertical(self) -> bool:
        return "vertical" in self.axes


def freeform_artwork_child_role(
    role_id: str = "artwork",
    *,
    resize_handles: tuple[str, ...],
    minimum_scale: tuple[float, float] = (0.40, 0.40),
    maximum_scale: tuple[float, float] = (3.00, 3.00),
) -> CustomChildRoleDescriptor:
    """Build the shared freeform artwork-frame geometry contract.

    Artwork providers remain family-owned. This helper normalizes only the
    presentation geometry semantics reused by Steam cards, Media and future
    artwork-bearing widgets: free X/Y frame sizing, while each family keeps
    native source aspect through its existing crop/fill pipeline.
    """

    return CustomChildRoleDescriptor(
        role_id,
        axes=("horizontal", "vertical"),
        minimum_scale=minimum_scale,
        maximum_scale=maximum_scale,
        uniform_scale=False,
        resize_handles=resize_handles,
    )


@dataclass(frozen=True, slots=True)
class CustomChildSize:
    """Normalized authored-relative size factors for one child role."""

    width_scale: float = 1.0
    height_scale: float = 1.0

    def to_mapping(self) -> dict[str, float]:
        return {
            "width_scale": float(self.width_scale),
            "height_scale": float(self.height_scale),
        }

    @property
    def is_authored(self) -> bool:
        return (
            abs(float(self.width_scale) - 1.0) <= _CHILD_SCALE_EPSILON
            and abs(float(self.height_scale) - 1.0) <= _CHILD_SCALE_EPSILON
        )


def child_role_map(
    roles: Sequence[CustomChildRoleDescriptor],
) -> dict[str, CustomChildRoleDescriptor]:
    return {role.role_id: role for role in roles}


def clamp_child_size(
    role: CustomChildRoleDescriptor,
    width_scale: object,
    height_scale: object,
) -> CustomChildSize:
    """Normalize and clamp one child role size against descriptor bounds."""

    try:
        width = float(width_scale)
    except (TypeError, ValueError):
        width = 1.0
    try:
        height = float(height_scale)
    except (TypeError, ValueError):
        height = 1.0
    if not math.isfinite(width) or width <= 0.0:
        width = 1.0
    if not math.isfinite(height) or height <= 0.0:
        height = 1.0
    if not role.horizontal:
        width = 1.0
    if not role.vertical:
        height = 1.0
    if role.uniform_scale:
        # Uniform intrinsic-shape roles (circles, square badges, etc.) keep
        # their authored shape. Artwork rectangles deliberately do *not* use
        # this constraint: their frame may resize freely while the image keeps
        # native aspect through the family's existing crop/fit policy.
        # Callers emit one canonical scale for live gestures;
        # width is the deterministic authority when sanitising persisted input.
        low = max(role.minimum_scale[0], role.minimum_scale[1])
        high = min(role.maximum_scale[0], role.maximum_scale[1])
        scale = max(low, min(high, width if role.horizontal else height))
        return CustomChildSize(scale, scale)
    return CustomChildSize(
        max(role.minimum_scale[0], min(role.maximum_scale[0], width)),
        max(role.minimum_scale[1], min(role.maximum_scale[1], height)),
    )


def normalize_child_geometry(
    raw: object,
    roles: Sequence[CustomChildRoleDescriptor],
) -> dict[str, CustomChildSize]:
    """Parse known role factors, omitting authored/default entries.

    Unknown persisted role ids are intentionally ignored here rather than
    interpreted.  ``update_child_geometry_payload`` preserves them byte-for-byte
    at the mapping level when this version mutates a known role.
    """

    if not isinstance(raw, Mapping):
        return {}
    known = child_role_map(roles)
    resolved: dict[str, CustomChildSize] = {}
    for role_id, value in raw.items():
        role = known.get(str(role_id))
        if role is None or not isinstance(value, Mapping):
            continue
        size = clamp_child_size(
            role,
            value.get("width_scale", 1.0),
            value.get("height_scale", 1.0),
        )
        if not size.is_authored:
            resolved[role.role_id] = size
    return resolved


def update_child_geometry_payload(
    payload: Mapping[str, Any],
    roles: Sequence[CustomChildRoleDescriptor],
    overrides: Mapping[str, CustomChildSize],
) -> dict[str, Any]:
    """Return ``payload`` with known child roles updated and unknown roles kept."""

    result = dict(payload)
    existing = result.get(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY)
    persisted = dict(existing) if isinstance(existing, Mapping) else {}
    known_ids = {role.role_id for role in roles}
    for role_id in known_ids:
        persisted.pop(role_id, None)
    for role_id, size in overrides.items():
        if role_id in known_ids and not size.is_authored:
            persisted[role_id] = size.to_mapping()
    if persisted:
        result[CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY] = persisted
    else:
        result.pop(CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY, None)
    return result


__all__ = [
    "CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY",
    "CustomChildRoleDescriptor",
    "CustomChildSize",
    "child_role_map",
    "clamp_child_size",
    "freeform_artwork_child_role",
    "normalize_child_geometry",
    "update_child_geometry_payload",
]
