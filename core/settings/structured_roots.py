"""Settings roots that must remain nested across JSON persistence.

These roots are semantic mappings, not dotted compatibility namespaces. Keep
this shared by the store, writer and SettingsManager so a mapping cannot be
written intact and then flattened into an unreadable shape on the next load.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


STRUCTURED_SETTINGS_ROOTS = frozenset(
    {
        "transitions",
        "ui",
        "visualizer_custom_presets",
        "widgets",
        "widget_theme",
    }
)

# Canonical defaults still enumerate these mapping members as a schema registry,
# but persisted user state is intentionally sparse. SettingsManager must not
# deep-fill missing child leaves inside these paths on startup or one remembered
# open bucket would immediately expand back into a full boolean map.
SPARSE_STRUCTURED_MAPPING_PATHS = frozenset(
    {
        ("ui", "gmail_bucket_states"),
        ("ui", "visualizer_bucket_states"),
        ("ui", "visualizer_tech_bucket_states"),
        ("ui", "widget_bucket_states"),
    }
)


def merge_missing_structured_defaults(
    existing: Mapping[str, Any],
    defaults: Mapping[str, Any],
    *,
    path: tuple[str, ...] = (),
) -> tuple[dict[str, Any], bool]:
    """Deep-fill canonical structured defaults while preserving sparse subtrees.

    Sparse paths use canonical defaults only as an identity/schema registry.
    Missing sparse subtrees therefore mean "nothing currently remembered" and
    existing sparse mappings are retained exactly; their owning state contract
    is responsible for dropping stale/invalid member identities.
    """

    merged = deepcopy(dict(existing))
    changed = False
    for key, default_value in defaults.items():
        child_path = (*path, str(key))
        if child_path in SPARSE_STRUCTURED_MAPPING_PATHS:
            continue
        if key not in merged:
            merged[key] = deepcopy(default_value)
            changed = True
            continue
        existing_value = merged[key]
        if isinstance(existing_value, Mapping) and isinstance(default_value, Mapping):
            child, child_changed = merge_missing_structured_defaults(
                existing_value,
                default_value,
                path=child_path,
            )
            if child_changed:
                merged[key] = child
                changed = True
    return merged, changed


__all__ = [
    "SPARSE_STRUCTURED_MAPPING_PATHS",
    "STRUCTURED_SETTINGS_ROOTS",
    "merge_missing_structured_defaults",
]
