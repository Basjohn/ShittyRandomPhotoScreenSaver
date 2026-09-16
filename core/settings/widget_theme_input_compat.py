"""Persisted-input compatibility for retired Widget Theme material state.

Current Widget Theme state is colour-only schema v3.  Older profile/SST/QSettings
state could carry a root-level ``card_material_override`` and a schema-v1/v2
``custom`` payload with ``default_card_material_mode``.  Accept those names only at
persisted/import boundaries, promote the custom payload to v3, and remove the
retired material fields before current UI/runtime code sees the state.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any


_LEGACY_ROOT_MATERIAL_KEY = "card_material_override"
_LEGACY_CUSTOM_MATERIAL_KEY = "default_card_material_mode"
_CURRENT_WIDGET_THEME_SCHEMA_VERSION = 3
_LEGACY_WIDGET_THEME_SCHEMA_VERSIONS = frozenset({1, 2})


def promote_legacy_widget_theme_state(
    value: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Promote one persisted Widget Theme state mapping to current v3 shape.

    Only the abandoned material dimension is rewritten.  Selection identity,
    Keep-Synced state, Custom identity/link metadata, semantic colours, and any
    unrelated members are preserved.  A current schema-v3 custom payload is not
    relaxed or repaired here; strict v3 validation remains owned by Widget Theme
    runtime/file I/O.
    """

    promoted = deepcopy(dict(value))
    changed = False

    if _LEGACY_ROOT_MATERIAL_KEY in promoted:
        promoted.pop(_LEGACY_ROOT_MATERIAL_KEY, None)
        changed = True

    custom = promoted.get("custom")
    if isinstance(custom, Mapping):
        custom_payload = deepcopy(dict(custom))
        if custom_payload.get("schema_version") in _LEGACY_WIDGET_THEME_SCHEMA_VERSIONS:
            custom_payload.pop(_LEGACY_CUSTOM_MATERIAL_KEY, None)
            custom_payload["schema_version"] = _CURRENT_WIDGET_THEME_SCHEMA_VERSION
            promoted["custom"] = custom_payload
            changed = True

    return promoted, changed


__all__ = ["promote_legacy_widget_theme_state"]
