"""Shared CUSTOM editable-child geometry contracts.

The outer CUSTOM layout owner remains authoritative. Child geometry is one
additive persisted role record: authored-relative size plus optional placement.
QML supplies retained presentation targets/edit constraints, but never owns a
second persistence schema or committed geometry authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY = "child_geometry"
_CHILD_SCALE_EPSILON = 1.0e-4
_CHILD_OFFSET_EPSILON = 1.0e-5
# Offsets are normalized against a family-declared stable authored reference.
# The runtime edit layer additionally clamps children to the real parent bounds;
# this generous parser bound only rejects absurd/corrupt persisted input without
# inventing a second family layout policy here.
_CHILD_OFFSET_ABS_LIMIT = 4.0
CHILD_RESIZE_HANDLES = ("top_left", "top_right", "bottom_left", "bottom_right")
_CHILD_RESIZE_HANDLES = frozenset(CHILD_RESIZE_HANDLES)


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
    # Center-owned roles grow equally on both sides of the touched edge.
    # The existing normalized size remains the sole persisted authority.
    centered_resize: bool = False
    movable: bool = False
    resize_handles: tuple[str, ...] = CHILD_RESIZE_HANDLES
    alignment_flip: bool = False
    authored_alignment: str = "left"
    semantic_corner_anchor: bool = False

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
        if self.centered_resize and (not self.uniform_scale or self.movable):
            raise ValueError(
                f"CUSTOM child role {role_id!r} centered resize requires "
                "uniform scaling and fixed center"
            )
        object.__setattr__(self, "centered_resize", bool(self.centered_resize))
        alignment = str(self.authored_alignment or "left").strip().lower()
        if alignment not in {"left", "right"}:
            raise ValueError(
                f"CUSTOM child role {role_id!r} authored alignment must be left/right"
            )
        object.__setattr__(self, "movable", bool(self.movable))
        object.__setattr__(self, "resize_handles", tuple(dict.fromkeys(handles)))
        object.__setattr__(self, "alignment_flip", bool(self.alignment_flip))
        object.__setattr__(self, "authored_alignment", alignment)
        object.__setattr__(self, "semantic_corner_anchor", bool(self.semantic_corner_anchor))

    @property
    def horizontal(self) -> bool:
        return "horizontal" in self.axes

    @property
    def vertical(self) -> bool:
        return "vertical" in self.axes

    def resize_edges(self) -> tuple[str, ...]:
        """Invisible one-axis resize edges admitted by this role.

        Left/top need placement authority so the opposite edge can remain fixed.
        Right/bottom remain truthful for size-only roles. Uniform/intrinsic roles
        keep corner-only scaling because a one-axis cursor would falsely imply
        aspect distortion.
        """

        if self.uniform_scale:
            return ()
        edges: list[str] = []
        if self.horizontal:
            if self.movable:
                edges.append("left")
            edges.append("right")
        if self.vertical:
            if self.movable:
                edges.append("top")
            edges.append("bottom")
        return tuple(edges)

    def admits_resize_handle(self, handle: str) -> bool:
        handle_id = str(handle or "")
        return handle_id in self.resize_handles or handle_id in self.resize_edges()


def freeform_layout_block_child_role(
    role_id: str,
    *,
    resize_handles: tuple[str, ...] = CHILD_RESIZE_HANDLES,
    minimum_scale: tuple[float, float] = (0.50, 0.50),
    maximum_scale: tuple[float, float] = (2.50, 2.50),
    movable: bool = False,
    alignment_flip: bool = False,
    authored_alignment: str = "left",
) -> CustomChildRoleDescriptor:
    """Build the shared freeform retained layout-block geometry contract.

    Layout blocks are presentation regions whose internal text/children keep
    their family-authored layout while CUSTOM changes the containing frame.
    This helper deliberately owns geometry semantics only; the family remains
    responsible for reflow and for deciding whether the role represents one
    block or a grouped repeated set (for example Abandonment ledger shelves).
    """

    return CustomChildRoleDescriptor(
        role_id,
        axes=("horizontal", "vertical"),
        minimum_scale=minimum_scale,
        maximum_scale=maximum_scale,
        uniform_scale=False,
        movable=movable,
        resize_handles=resize_handles,
        alignment_flip=alignment_flip,
        authored_alignment=authored_alignment,
    )


def freeform_artwork_child_role(
    role_id: str = "artwork",
    *,
    resize_handles: tuple[str, ...] = CHILD_RESIZE_HANDLES,
    minimum_scale: tuple[float, float] = (0.40, 0.40),
    maximum_scale: tuple[float, float] = (3.00, 3.00),
    movable: bool = False,
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
        movable=movable,
        resize_handles=resize_handles,
    )


@dataclass(frozen=True, slots=True)
class CustomChildSize:
    """One normalized authored-relative child geometry record.

    The historical class name is retained because the size-only phase already
    shipped test/docs seams under it. ``x_offset``/``y_offset`` are additive and
    default to zero, so every old two-field payload remains valid. Offsets are
    fractions of a stable family-declared authored normalization box, never raw
    device pixels and never the currently-expanded CUSTOM parent.
    """

    width_scale: float = 1.0
    height_scale: float = 1.0
    x_offset: float = 0.0
    y_offset: float = 0.0
    alignment: str | None = None
    anchor: str | None = None

    def to_mapping(self) -> dict[str, Any]:
        result = {
            "width_scale": float(self.width_scale),
            "height_scale": float(self.height_scale),
        }
        if abs(float(self.x_offset)) > _CHILD_OFFSET_EPSILON:
            result["x_offset"] = float(self.x_offset)
        if abs(float(self.y_offset)) > _CHILD_OFFSET_EPSILON:
            result["y_offset"] = float(self.y_offset)
        if self.alignment in {"left", "right"}:
            result["alignment"] = str(self.alignment)
        if self.anchor in {"top_left", "top_right", "bottom_left", "bottom_right"}:
            result["anchor"] = str(self.anchor)
        return result

    @property
    def is_authored(self) -> bool:
        return (
            abs(float(self.width_scale) - 1.0) <= _CHILD_SCALE_EPSILON
            and abs(float(self.height_scale) - 1.0) <= _CHILD_SCALE_EPSILON
            and abs(float(self.x_offset)) <= _CHILD_OFFSET_EPSILON
            and abs(float(self.y_offset)) <= _CHILD_OFFSET_EPSILON
            and self.alignment is None
            and self.anchor is None
        )


@dataclass(frozen=True, slots=True)
class ResolvedChildResize:
    """Descriptor-clamped result of one child-resize pointer sample.

    This is intentionally presentation-neutral.  Qt/QML may preview the exact
    geometry that a pointer sample would commit without duplicating role bounds
    or uniform-scale rules in the scene layer.  ``visible_*`` are expressed in
    the same rendered-pixel space supplied at gesture begin.
    """

    geometry: CustomChildSize
    visible_width: float
    visible_height: float


def resolve_child_resize_geometry(
    role: CustomChildRoleDescriptor,
    origin: CustomChildSize,
    *,
    handle: str,
    raw_dx: float,
    raw_dy: float,
    visible_width: float,
    visible_height: float,
    normalization_width: float,
    normalization_height: float,
    outer_scale: float,
) -> ResolvedChildResize:
    """Resolve one child-resize sample through the canonical descriptor rules.

    The helper is shared by mutation and preview paths.  Keeping this math here
    prevents QML from becoming a shadow authority for min/max scale, uniform
    intrinsic roles, or left/top authored-relative placement.
    """

    handle_id = str(handle or "")
    if not role.admits_resize_handle(handle_id):
        raise ValueError(f"Unsupported resize handle {handle_id!r} for {role.role_id!r}")

    width = max(1.0e-6, float(visible_width))
    height = max(1.0e-6, float(visible_height))
    norm_width = max(1.0e-6, float(normalization_width))
    norm_height = max(1.0e-6, float(normalization_height))
    scale = max(1.0e-6, float(outer_scale))

    dx = float(raw_dx)
    dy = float(raw_dy)
    horizontal_only = handle_id in {"left", "right"}
    vertical_only = handle_id in {"top", "bottom"}
    if horizontal_only:
        dy = 0.0
    elif vertical_only:
        dx = 0.0
    if handle_id.endswith("left"):
        dx = -dx
    top_side = handle_id == "top" or handle_id.startswith("top_")
    if top_side:
        dy = -dy
    if role.centered_resize:
        # The physical pointer moves one radius, while the full box changes
        # by two radii. Uniform intrinsic geometry stays centered without
        # saving artificial X/Y offsets that would fight the authored center.
        dx *= 2.0
        dy *= 2.0

    width_ratio = max(1.0e-6, width + dx) / width
    height_ratio = max(1.0e-6, height + dy) / height
    if role.uniform_scale:
        width_departure = abs(math.log(max(1.0e-6, width_ratio)))
        height_departure = abs(math.log(max(1.0e-6, height_ratio)))
        ratio = width_ratio if width_departure >= height_departure else height_ratio
        next_size = clamp_child_geometry(
            role,
            origin.width_scale * ratio,
            origin.height_scale * ratio,
            origin.x_offset,
            origin.y_offset,
            origin.alignment,
            origin.anchor,
        )
    else:
        next_size = clamp_child_geometry(
            role,
            origin.width_scale * width_ratio,
            origin.height_scale * height_ratio,
            origin.x_offset,
            origin.y_offset,
            origin.alignment,
            origin.anchor,
        )

    next_visible_width = width * (
        next_size.width_scale / max(1.0e-6, origin.width_scale)
    )
    next_visible_height = height * (
        next_size.height_scale / max(1.0e-6, origin.height_scale)
    )
    next_x_offset = origin.x_offset
    next_y_offset = origin.y_offset
    if handle_id.endswith("left") and role.movable:
        next_x_offset += (
            width - next_visible_width
        ) / (scale * norm_width)
    if top_side and role.movable:
        next_y_offset += (
            height - next_visible_height
        ) / (scale * norm_height)
    next_size = clamp_child_geometry(
        role,
        next_size.width_scale,
        next_size.height_scale,
        next_x_offset,
        next_y_offset,
        origin.alignment,
        origin.anchor,
    )
    return ResolvedChildResize(
        geometry=next_size,
        visible_width=next_visible_width,
        visible_height=next_visible_height,
    )


def resolve_child_move_geometry(
    role: CustomChildRoleDescriptor,
    origin: CustomChildSize,
    *,
    raw_dx: float,
    raw_dy: float,
    normalization_width: float,
    normalization_height: float,
    outer_scale: float,
    placement_compensation_x: float = 0.0,
    placement_compensation_y: float = 0.0,
) -> CustomChildSize:
    """Resolve one child-placement sample through authored-relative SSOT.

    Dense families may keep an on-rail child displaced by sibling reflow.  The
    first *real* free-placement sample folds that current logical displacement
    into the persisted normalized offset before the retained family reflow gate
    detaches. A zero-motion press/release deliberately ignores compensation so
    merely clicking a role cannot manufacture CUSTOM placement state.
    """

    if not role.movable:
        return clamp_child_geometry(
            role,
            origin.width_scale,
            origin.height_scale,
            origin.x_offset,
            origin.y_offset,
            origin.alignment,
            origin.anchor,
        )

    scale = max(1.0e-6, float(outer_scale))
    norm_width = max(1.0e-6, float(normalization_width))
    norm_height = max(1.0e-6, float(normalization_height))
    dx = float(raw_dx)
    dy = float(raw_dy)
    moved = (
        math.isfinite(dx)
        and math.isfinite(dy)
        and (abs(dx) > 1.0e-9 or abs(dy) > 1.0e-9)
    )
    compensation_x = float(placement_compensation_x) if moved else 0.0
    compensation_y = float(placement_compensation_y) if moved else 0.0
    if not math.isfinite(compensation_x):
        compensation_x = 0.0
    if not math.isfinite(compensation_y):
        compensation_y = 0.0
    if not math.isfinite(dx):
        dx = 0.0
    if not math.isfinite(dy):
        dy = 0.0

    return clamp_child_geometry(
        role,
        origin.width_scale,
        origin.height_scale,
        origin.x_offset + compensation_x / norm_width + dx / (scale * norm_width),
        origin.y_offset + compensation_y / norm_height + dy / (scale * norm_height),
        origin.alignment,
        None if (moved and role.semantic_corner_anchor) else origin.anchor,
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
    """Normalize and clamp one child role size at authored placement."""

    return clamp_child_geometry(role, width_scale, height_scale, 0.0, 0.0)


def clamp_child_geometry(
    role: CustomChildRoleDescriptor,
    width_scale: object,
    height_scale: object,
    x_offset: object = 0.0,
    y_offset: object = 0.0,
    alignment: object = None,
    anchor: object = None,
) -> CustomChildSize:
    """Normalize one full child record against descriptor/parser bounds."""

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
    try:
        offset_x = float(x_offset)
    except (TypeError, ValueError):
        offset_x = 0.0
    try:
        offset_y = float(y_offset)
    except (TypeError, ValueError):
        offset_y = 0.0
    if not math.isfinite(offset_x):
        offset_x = 0.0
    if not math.isfinite(offset_y):
        offset_y = 0.0
    alignment_value: str | None = None
    if role.alignment_flip:
        candidate_alignment = str(alignment or "").strip().lower()
        if candidate_alignment in {"left", "right"} and candidate_alignment != role.authored_alignment:
            alignment_value = candidate_alignment
    anchor_value: str | None = None
    if role.semantic_corner_anchor:
        candidate_anchor = str(anchor or "").strip().lower()
        if candidate_anchor in {"top_left", "top_right", "bottom_left", "bottom_right"}:
            anchor_value = candidate_anchor
    if not role.movable:
        offset_x = 0.0
        offset_y = 0.0
    offset_x = max(-_CHILD_OFFSET_ABS_LIMIT, min(_CHILD_OFFSET_ABS_LIMIT, offset_x))
    offset_y = max(-_CHILD_OFFSET_ABS_LIMIT, min(_CHILD_OFFSET_ABS_LIMIT, offset_y))
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
        return CustomChildSize(scale, scale, offset_x, offset_y, alignment_value, anchor_value)
    return CustomChildSize(
        max(role.minimum_scale[0], min(role.maximum_scale[0], width)),
        max(role.minimum_scale[1], min(role.maximum_scale[1], height)),
        offset_x,
        offset_y,
        alignment_value,
        anchor_value,
    )


def flip_child_alignment(
    role: CustomChildRoleDescriptor,
    geometry: CustomChildSize,
) -> CustomChildSize:
    """Toggle one descriptor-admitted left/right role alignment.

    The authored alignment is represented by ``None`` in persisted state, so a
    second flip back to authored removes the override instead of manufacturing
    sticky presentation state. Geometry and alignment remain one role record.
    """

    if not role.alignment_flip:
        return geometry
    effective = geometry.alignment or role.authored_alignment
    next_alignment = "right" if effective == "left" else "left"
    override = None if next_alignment == role.authored_alignment else next_alignment
    return clamp_child_geometry(
        role,
        geometry.width_scale,
        geometry.height_scale,
        geometry.x_offset,
        geometry.y_offset,
        override,
        geometry.anchor,
    )


def set_child_semantic_anchor(
    role: CustomChildRoleDescriptor,
    geometry: CustomChildSize,
    anchor: str | None,
) -> CustomChildSize:
    """Set/clear one descriptor-admitted semantic corner anchor."""

    requested = str(anchor or "").strip().lower() or None
    if not role.semantic_corner_anchor:
        return geometry
    if requested not in {None, "top_left", "top_right", "bottom_left", "bottom_right"}:
        return geometry
    return clamp_child_geometry(
        role,
        geometry.width_scale,
        geometry.height_scale,
        geometry.x_offset,
        geometry.y_offset,
        geometry.alignment,
        requested,
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
        size = clamp_child_geometry(
            role,
            value.get("width_scale", 1.0),
            value.get("height_scale", 1.0),
            value.get("x_offset", 0.0),
            value.get("y_offset", 0.0),
            value.get("alignment"),
            value.get("anchor"),
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
    "CHILD_RESIZE_HANDLES",
    "CUSTOM_CHILD_GEOMETRY_PAYLOAD_KEY",
    "CustomChildRoleDescriptor",
    "CustomChildSize",
    "ResolvedChildResize",
    "child_role_map",
    "clamp_child_geometry",
    "clamp_child_size",
    "flip_child_alignment",
    "freeform_artwork_child_role",
    "freeform_layout_block_child_role",
    "normalize_child_geometry",
    "resolve_child_resize_geometry",
    "set_child_semantic_anchor",
    "update_child_geometry_payload",
]
