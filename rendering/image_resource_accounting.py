"""GUI-thread capture of display-owned CPU image representations.

The periodic resource sampler reads only the detached sidecar produced here;
it never touches live QPixmap objects from a background thread.
"""
from __future__ import annotations

import math
from types import MappingProxyType
from typing import Any

from PySide6.QtGui import QPixmap


_EMPTY_DISPLAY_IMAGE_ACCOUNTING = MappingProxyType(
    {
        "owner": "uninitialized",
        "generation": None,
        "total_tracked_bytes": 0,
        "resource_count": 0,
        "resources": (),
    }
)


def _candidate_roles(widget: Any) -> list[tuple[str, Any]]:
    candidates: list[tuple[str, Any]] = [
        ("display.current", getattr(widget, "current_pixmap", None)),
        ("display.previous", getattr(widget, "previous_pixmap", None)),
        ("display.seed", getattr(widget, "_seed_pixmap", None)),
    ]

    pending = getattr(widget, "_pending_transition_finish_args", None)
    if isinstance(pending, tuple):
        for index, value in enumerate(pending):
            candidates.append((f"display.pending[{index}]", value))

    presenter = getattr(widget, "_image_presenter", None)
    if presenter is not None:
        for role, attr in (
            ("presenter.current", "_current_pixmap"),
            ("presenter.previous", "_previous_pixmap"),
            ("presenter.seed", "_seed_pixmap"),
        ):
            candidates.append((role, getattr(presenter, attr, None)))

    custom = getattr(widget, "_custom_layout_manager", None)
    deferred = getattr(custom, "_deferred_processed_image", None)
    if isinstance(deferred, tuple):
        for index, value in enumerate(deferred):
            candidates.append((f"custom.deferred[{index}]", value))

    compositor = getattr(widget, "_gl_compositor", None)
    if compositor is not None:
        candidates.append(("compositor.base", getattr(compositor, "_base_pixmap", None)))
        for state_name in (
            "crossfade",
            "slide",
            "wipe",
            "warp",
            "blockflip",
            "blockspin",
            "blinds",
            "diffuse",
            "raindrops",
            "crumble",
            "particle",
            "burn",
        ):
            state = getattr(compositor, f"_{state_name}", None)
            if state is None:
                continue
            candidates.append((f"transition.{state_name}.old", getattr(state, "old_pixmap", None)))
            candidates.append((f"transition.{state_name}.new", getattr(state, "new_pixmap", None)))
    return candidates


def refresh_display_image_accounting(widget: Any):
    """Capture unique QPixmap backing stores and all roles retaining them."""
    unique: dict[int, dict[str, Any]] = {}
    for role, pixmap in _candidate_roles(widget):
        if not isinstance(pixmap, QPixmap) or pixmap.isNull():
            continue
        cache_key = int(pixmap.cacheKey())
        identity = cache_key if cache_key else id(pixmap)
        item = unique.get(identity)
        if item is None:
            width = int(pixmap.width())
            height = int(pixmap.height())
            depth = int(pixmap.depth())
            item = {
                "resource_id": f"qt-pixmap:{identity}",
                "owner": str(
                    getattr(
                        widget,
                        "_image_resource_owner",
                        f"display:{getattr(widget, 'screen_index', 'unknown')}",
                    )
                ),
                "generation": getattr(widget, "_image_resource_generation", None),
                "dimensions": (width, height),
                "format": f"QPixmap(depth={depth})",
                "tracked_bytes": width * height * math.ceil(max(0, depth) / 8),
                "lease_count": None,
                "roles": [],
            }
            unique[identity] = item
        item["roles"].append(role)

    resources = []
    for item in unique.values():
        item["roles"] = tuple(sorted(set(item["roles"])))
        resources.append(MappingProxyType(item))
    resources.sort(key=lambda item: item["resource_id"])
    widget._image_resource_accounting = MappingProxyType(
        {
            "owner": str(
                getattr(
                    widget,
                    "_image_resource_owner",
                    f"display:{getattr(widget, 'screen_index', 'unknown')}",
                )
            ),
            "generation": getattr(widget, "_image_resource_generation", None),
            "total_tracked_bytes": sum(item["tracked_bytes"] for item in resources),
            "resource_count": len(resources),
            "resources": tuple(resources),
        }
    )
    return widget._image_resource_accounting


def get_display_image_accounting(widget: Any):
    """Return the detached last GUI-thread capture."""
    snapshot = getattr(widget, "_image_resource_accounting", None)
    return snapshot if snapshot is not None else _EMPTY_DISPLAY_IMAGE_ACCOUNTING


def aggregate_display_image_accounting(
    snapshots,
    *,
    generation: Any = None,
):
    """Deduplicate immutable per-display captures without touching Qt state."""

    unique: dict[str, Any] = {}
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
