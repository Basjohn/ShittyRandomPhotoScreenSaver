"""Shared quarter-turn presentation helpers for the retained Visualizer.

Orientation is CUSTOM layout/presentation state, not a Visualizer preset or
technical setting.  Persisted ``viewport_extent`` remains the physical edited
world; accepted carded modes derive an effective logical world from the same
extent when the content is quarter-turned.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.settings.visualizer_mode_registry import (
    get_visualizer_mode_descriptor,
    iter_all_visualizer_mode_descriptors,
)


CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY = "content_rotation_quarters"
CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY = "content_rotation_quarters_by_mode"


def normalize_content_rotation_quarters(value: object) -> int:
    """Return a persisted-safe quarter-turn token in ``{0, 1, 2, 3}``.

    Missing/malformed legacy payloads intentionally resolve to zero rather than
    changing the CUSTOM layout schema version.
    """

    try:
        quarters = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return quarters if quarters in {0, 1, 2, 3} else 0



def content_rotation_map_from_legacy(value: object) -> dict[str, int]:
    """Expand the former global token across every capable carded mode.

    This is a one-way compatibility interpretation only. The pre-per-mode token
    applied to every accepted carded mode, including when Sphere temporarily hid
    it, so migration must preserve that behavior before modes diverge.
    """

    quarters = normalize_content_rotation_quarters(value)
    if not quarters:
        return {}
    return {
        descriptor.mode_id: quarters
        for descriptor in iter_all_visualizer_mode_descriptors()
        if descriptor.presentation_policy.content_rotation_capable
    }


def normalize_content_rotation_by_mode(value: object) -> dict[str, int]:
    """Return persisted non-zero quarter-turns keyed by capable canonical mode.

    The map lives inside the existing CUSTOM ``size_payload`` carrier. Unknown,
    malformed, zero and non-capable (for example experimental Sphere) entries are
    omitted so persistence stays sparse and stable.
    """

    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, int] = {}
    for raw_mode, raw_quarters in value.items():
        mode_id = str(raw_mode or "").strip().lower()
        try:
            descriptor = get_visualizer_mode_descriptor(mode_id)
        except KeyError:
            continue
        if not descriptor.presentation_policy.content_rotation_capable:
            continue
        quarters = normalize_content_rotation_quarters(raw_quarters)
        if quarters:
            normalized[descriptor.mode_id] = quarters
    return normalized


def resolve_content_rotation_for_mode(
    value: object,
    mode_id: object,
    *,
    legacy_value: object = 0,
) -> int:
    """Resolve one mode's retained turn from a map with legacy-scalar fallback."""

    canonical = str(mode_id or "").strip().lower()
    try:
        descriptor = get_visualizer_mode_descriptor(canonical)
    except KeyError:
        return 0
    if not descriptor.presentation_policy.content_rotation_capable:
        return 0
    if isinstance(value, Mapping) and canonical in value:
        return normalize_content_rotation_quarters(value.get(canonical))
    return normalize_content_rotation_quarters(legacy_value)


def set_content_rotation_for_mode(
    value: object,
    mode_id: object,
    content_rotation_quarters: object,
) -> dict[str, int]:
    """Return a normalized sparse map with one capable mode updated."""

    rotations = normalize_content_rotation_by_mode(value)
    canonical = str(mode_id or "").strip().lower()
    try:
        descriptor = get_visualizer_mode_descriptor(canonical)
    except KeyError:
        return rotations
    if not descriptor.presentation_policy.content_rotation_capable:
        return rotations
    quarters = normalize_content_rotation_quarters(content_rotation_quarters)
    if quarters:
        rotations[canonical] = quarters
    else:
        rotations.pop(canonical, None)
    return rotations

def rotate_quarters_clockwise(value: object, steps: int = 1) -> int:
    """Advance a normalized orientation by ``steps`` quarter-turns."""

    return (normalize_content_rotation_quarters(value) + int(steps)) % 4


def oriented_size(
    size: Sequence[object],
    content_rotation_quarters: object,
) -> tuple[float, float]:
    """Return the logical width/height after applying the quarter-turn basis."""

    if len(size) != 2:
        raise ValueError("oriented size must contain width and height")
    width = float(size[0])
    height = float(size[1])
    if width <= 0.0 or height <= 0.0:
        raise ValueError("oriented size must be positive")
    if normalize_content_rotation_quarters(content_rotation_quarters) % 2:
        return (height, width)
    return (width, height)


def logical_uv_from_physical_uv(
    uv: Sequence[object],
    content_rotation_quarters: object,
) -> tuple[float, float]:
    """Map physical item UV to the authored logical UV for clockwise rotation.

    This is the CPU oracle for the shared Quick vertex-shader transform.  The
    mapping is inverse-to-presentation: a logical image rotated clockwise once
    is sampled from physical coordinates as ``(v, 1-u)``.
    """

    if len(uv) != 2:
        raise ValueError("UV must contain two coordinates")
    u = float(uv[0])
    v = float(uv[1])
    quarters = normalize_content_rotation_quarters(content_rotation_quarters)
    if quarters == 0:
        return (u, v)
    if quarters == 1:
        return (v, 1.0 - u)
    if quarters == 2:
        return (1.0 - u, 1.0 - v)
    return (1.0 - v, u)


def logical_rect_from_physical_rect(
    rect: Sequence[object],
    *,
    physical_size: Sequence[object],
    content_rotation_quarters: object,
) -> tuple[float, float, float, float]:
    """Transform one item-local physical rectangle into logical coordinates."""

    if len(rect) != 4:
        raise ValueError("rect must contain x, y, width and height")
    if len(physical_size) != 2:
        raise ValueError("physical size must contain width and height")
    x, y, width, height = (float(value) for value in rect)
    item_width, item_height = (float(value) for value in physical_size)
    if min(width, height, item_width, item_height) < 0.0:
        raise ValueError("rect/physical size must be non-negative")
    quarters = normalize_content_rotation_quarters(content_rotation_quarters)
    if quarters == 0:
        return (x, y, width, height)
    if quarters == 1:
        return (y, item_width - (x + width), height, width)
    if quarters == 2:
        return (
            item_width - (x + width),
            item_height - (y + height),
            width,
            height,
        )
    return (item_height - (y + height), x, height, width)


__all__ = [
    "CONTENT_ROTATION_BY_MODE_PAYLOAD_KEY",
    "CONTENT_ROTATION_QUARTERS_PAYLOAD_KEY",
    "content_rotation_map_from_legacy",
    "logical_rect_from_physical_rect",
    "logical_uv_from_physical_uv",
    "normalize_content_rotation_by_mode",
    "normalize_content_rotation_quarters",
    "oriented_size",
    "resolve_content_rotation_for_mode",
    "rotate_quarters_clockwise",
    "set_content_rotation_for_mode",
]
