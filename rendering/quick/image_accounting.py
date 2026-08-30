"""Detached accounting for immutable Quick presentation-image snapshots."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any


def aggregate_presentation_image_accounting(
    snapshots: Iterable[Mapping[str, Any]],
    *,
    generation: int | None,
) -> Mapping[str, Any]:
    """Deduplicate detached image records without touching a Qt object."""

    unique: dict[str, Mapping[str, Any]] = {}
    for snapshot in snapshots:
        for item in snapshot.get("resources", ()):
            resource_id = str(item.get("resource_id", ""))
            if resource_id and resource_id not in unique:
                unique[resource_id] = item
    resources = tuple(unique[key] for key in sorted(unique))
    return MappingProxyType(
        {
            "generation": generation,
            "total_tracked_bytes": sum(
                int(item.get("tracked_bytes", 0) or 0) for item in resources
            ),
            "resource_count": len(resources),
            "resources": resources,
        }
    )


__all__ = ["aggregate_presentation_image_accounting"]
